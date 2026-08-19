"""Router: GET /api/insights. The narrative that renders on page load.

The computed/generated split in practice: kpi_engine computes every figure,
this module formats those figures into a prompt, and the model returns prose
only. If the model is slow or down, the computed fields still ship and the
header still renders real numbers.
"""

from __future__ import annotations

import time
from datetime import date

from fastapi import APIRouter

from app.config import settings
from app.llm.base import get_client, render_prompt
from app.schemas import (
    INSIGHTS_SCHEMA,
    Callout,
    InsightResponse,
    ReasonTotal,
    WorstMachine,
)
from app.services import kpi_engine

router = APIRouter()

# The dataset is committed JSON and never changes at runtime, so the same day
# always yields the same figures and therefore the same narrative. Generating
# it once per day value rather than once per page load takes the briefing from
# 12-15s to instant on every load after the first.
#
# This is not the prewarm cache that was ruled out - that one is about a
# throwaway call whose output must be discarded. This caches a real response
# whose inputs are provably static. Pass ?refresh=true to regenerate.
_cache: dict[date, InsightResponse] = {}


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _facts_block(facts: dict) -> str:
    """Render the computed dict as flat text.

    Deliberately plain lines rather than JSON: a 7B model reproduces figures
    from a bulleted list more reliably than it extracts them from nested
    objects, and every number here must survive into the prose unchanged.
    """
    lines = [
        f"Plant OEE: {_pct(facts['oee'])}"
        f"  (availability {_pct(facts['availability'])},"
        f" performance {_pct(facts['performance'])},"
        f" quality {_pct(facts['quality'])})",
        f"Scrap rate: {_pct(facts['scrap_rate'])}",
        f"Total downtime: {facts['downtime_minutes']:.0f} minutes",
        f"Parts produced: {facts['good_count']} good of {facts['total_count']}",
    ]

    if facts["prior_oee"] is not None:
        direction = "down" if (facts["oee_delta"] or 0) < 0 else "up"
        lines.append(
            f"Prior day ({facts['prior_day']}) OEE: {_pct(facts['prior_oee'])}"
            f" - today is {direction} {abs(facts['oee_delta'] or 0) * 100:.1f} points"
        )

    lines.append("")
    lines.append("Lowest OEE machines:")
    for m in facts["worst_machines"]:
        lines.append(
            f"  - {m['machine_id']} ({m['name']}, {m['line']} line):"
            f" OEE {_pct(m['oee'])}, downtime {m['downtime_minutes']:.0f} min,"
            f" scrap {_pct(m['scrap_rate'])}"
        )

    lines.append("")
    lines.append("Downtime by reason code:")
    for r in facts["downtime_by_reason"]:
        lines.append(
            f"  - {r['reason_code']}: {r['minutes']:.0f} minutes"
            f" across {r['events']} events"
        )

    if facts["defects_by_type"]:
        lines.append("")
        lines.append("Defects by type:")
        for d in facts["defects_by_type"]:
            lines.append(f"  - {d['defect_type']}: {d['count']} parts")

    lines.append("")
    lines.append(
        f"Inventory: {facts['parts_below_reorder']} parts below reorder point,"
        f" lowest cover {facts['lowest_days_of_cover']} days"
    )
    for line_name, minutes in (facts["starved_minutes_by_line"] or {}).items():
        lines.append(f"  - {line_name} line lost {minutes:.0f} min to MATERIAL_STARVE")

    return "\n".join(lines)


@router.get("/insights", response_model=InsightResponse)
def get_insights(day: date | None = None, refresh: bool = False) -> InsightResponse:
    resolved = day or kpi_engine.latest_day()
    if not refresh:
        hit = _cache.get(resolved)
        if hit is not None:
            return hit

    facts = kpi_engine.insight_facts(resolved)

    response = InsightResponse(
        day=facts["day"],
        oee=facts["oee"],
        scrap_rate=facts["scrap_rate"],
        downtime_minutes=facts["downtime_minutes"],
        oee_delta=facts["oee_delta"],
        worst_machines=[WorstMachine(**m) for m in facts["worst_machines"]],
        downtime_by_reason=[ReasonTotal(**r) for r in facts["downtime_by_reason"]],
        parts_below_reorder=facts["parts_below_reorder"],
    )

    prompt = render_prompt(
        "kpi_insights.md",
        day=str(facts["day"]),
        facts=_facts_block(facts),
    )
    started = time.perf_counter()
    result = get_client().complete(prompt, INSIGHTS_SCHEMA, timeout=settings.insights_timeout)
    print(f"[insights] generation took {time.perf_counter() - started:.1f}s")

    if result is None:
        # Not cached: a transient model failure should not pin an empty
        # narrative to this day for the rest of the session.
        return response

    raw_callouts = result.get("callouts") or []
    callouts = [
        Callout(
            title=str(c.get("title", "")),
            detail=str(c.get("detail", "")),
            severity=(
                c.get("severity") if c.get("severity") in ("high", "medium", "low")
                else "medium"
            ),
            metric=c.get("metric") or None,
        )
        for c in raw_callouts
        if isinstance(c, dict) and c.get("title")
    ]

    response.headline = result.get("headline")
    response.narrative = result.get("narrative")
    response.callouts = callouts or None

    _cache[resolved] = response
    return response


def warm(day: date | None = None) -> None:
    """Populate the cache so the first page load is instant.

    Called on a background thread at startup: a 12-15s blocking generation
    would delay the server accepting requests, and under --reload it would
    run again on every code change.
    """
    try:
        get_insights(day)
        print("[insights] cache warmed")
    except Exception as exc:
        print(f"[insights] warm failed (non-fatal): {type(exc).__name__}: {exc}")
