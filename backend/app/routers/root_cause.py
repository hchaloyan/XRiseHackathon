"""Router: POST /api/root-cause. Inline expansion of an event row (rule 7).

Order matters: assemble evidence in pandas, retrieve the SOP sections that
apply, and only then call the model to rank hypotheses. The model receives
facts and documents; it produces ordering and prose.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.llm.base import get_client, render_prompt
from app.schemas import (
    ROOT_CAUSE_SCHEMA,
    EventContext,
    Evidence,
    Hypothesis,
    RootCauseRequest,
    RootCauseResponse,
    SopCitation,
)
from app.services import root_cause as rc
from app.services.knowledge_base import get_knowledge_base

router = APIRouter()

SOP_CHUNKS = 3


def _evidence_items(bundle: dict) -> list[Evidence]:
    """Flatten the assembled evidence into display rows.

    `label` is what the model quotes in supporting_evidence, so labels are
    kept short and made unique - a model asked to cite "Previous operator
    note" three times over cannot say which one it meant.
    """
    event = bundle["event"]
    history = bundle["history"]
    nearby = bundle["nearby"]
    shift = bundle["shift"]
    inventory = bundle["inventory"]

    items: list[Evidence] = []

    label = history["label"]
    if history["occurrences_on_machine"] > 1:
        detail = f"{history['occurrences_on_line']} across the {event['line']} line"
        if history["minutes_on_machine"]:
            detail += f", {history['minutes_on_machine']:.0f} minutes total"
        items.append(
            Evidence(
                label=f"{label} recurrence",
                value=(
                    f"{history['occurrences_on_machine']} times on "
                    f"{event['machine_id']} in {history['window_days']} days"
                ),
                detail=detail,
            )
        )

    for i, note in enumerate(history["recent_notes"][:3], start=1):
        items.append(Evidence(label=f"Previous note {i}", value=note))

    for n in nearby["downtime"][:4]:
        where = "same machine" if n["same_machine"] else n["machine_id"]
        items.append(
            Evidence(
                label=f"{n['reason_code']} {n['offset']}",
                value=f"{n['duration_minutes']:.0f} min on {where}",
                detail=n["operator_note"] or None,
            )
        )

    for n in nearby["quality"][:3]:
        where = "same machine" if n["same_machine"] else n["machine_id"]
        items.append(
            Evidence(
                label=f"{n['defect_type']} {n['offset']}",
                value=f"{n['count']} parts on {where}",
            )
        )

    items.append(
        Evidence(
            label="Machine that day",
            value=(
                f"{shift['machine_downtime_minutes']:.0f} min down across "
                f"{shift['machine_downtime_events']} events"
            ),
            detail=(
                f"{shift['machine_good_count']} good of "
                f"{shift['machine_total_count']} parts, "
                f"scrap {shift['machine_scrap_rate'] * 100:.1f}%"
            ),
        )
    )

    if shift["changeover_earlier_today"]:
        items.append(
            Evidence(
                label="Changeover earlier",
                value="A changeover ran on this machine before the event, same day",
            )
        )

    if inventory and inventory["parts_below_reorder"]:
        for part in inventory["parts_below_reorder"][:3]:
            items.append(
                Evidence(
                    label=f"{part['part_id']} below reorder",
                    value=(
                        f"{part['on_hand']} on hand vs reorder point "
                        f"{part['reorder_point']}"
                    ),
                    detail=f"{part['description']}, {part['days_of_cover']} days cover",
                )
            )

    return items


def _event_text(event: dict) -> str:
    parts = [
        f"Event {event['event_id']} ({event['kind']}) on {event['machine_id']} "
        f"{event['name']}, a {event['machine_type']} machine on the {event['line']} line",
        f"Started {event['start']}, shift {event['shift']}",
    ]
    if event["kind"] == "downtime":
        parts.append(f"Reason code: {event['reason_code']}")
        parts.append(f"Duration: {event['duration_minutes']:.0f} minutes")
        if event["operator_note"]:
            parts.append(f"Operator note: {event['operator_note']}")
    else:
        parts.append(f"Defect type: {event['defect_type']}")
        parts.append(f"Parts affected: {event['defect_count']}")
    return "\n".join(parts)


@router.post("/root-cause", response_model=RootCauseResponse)
def analyze_root_cause(payload: RootCauseRequest) -> RootCauseResponse:
    bundle = rc.assemble(payload.event_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"No event {payload.event_id}")

    event = bundle["event"]
    evidence = _evidence_items(bundle)

    # Retrieve SOP sections deterministically from the reason code / defect
    # type, not from the operator's phrasing. Retrieval failures are not fatal.
    chunks: list[dict] = []
    try:
        chunks = get_knowledge_base().search(rc.sop_query(event), top_k=SOP_CHUNKS)
    except Exception as exc:
        print(f"[root_cause] SOP retrieval failed: {type(exc).__name__}: {exc}")

    sources = [
        SopCitation(
            doc_id=c["doc_id"],
            title=c["title"],
            section=c["section"],
        )
        for c in chunks
    ]

    response = RootCauseResponse(
        event_id=event["event_id"],
        event=EventContext(
            event_id=event["event_id"],
            kind=event["kind"],
            machine_id=event["machine_id"],
            machine_name=event["name"],
            machine_type=event["machine_type"],
            line=event["line"],
            start=event["start"],
            shift=event["shift"],
            duration_minutes=event["duration_minutes"],
            reason_code=event["reason_code"],
            operator_note=event["operator_note"],
            defect_type=event["defect_type"],
            defect_count=event["defect_count"],
        ),
        evidence=evidence,
        sources=sources,
    )

    sop_text = (
        "\n\n".join(
            f"**{c['doc_id']} - {c['title']} / {c['section']}**\n{c['content']}"
            for c in chunks
        )
        or "No SOP section matched this event."
    )

    prompt = render_prompt(
        "root_cause.md",
        event=_event_text(event),
        evidence="\n".join(
            f"- {e.label}: {e.value}" + (f" ({e.detail})" if e.detail else "")
            for e in evidence
        ),
        sops=sop_text,
    )
    result = get_client().complete(
        prompt, ROOT_CAUSE_SCHEMA, timeout=settings.root_cause_timeout
    )

    if result is None:
        return response  # evidence and citations still render

    known_labels = {e.label for e in evidence}
    raw = result.get("hypotheses") or []
    hypotheses = [
        Hypothesis(
            rank=int(h.get("rank") or i),
            cause=str(h.get("cause", "")),
            confidence=(
                h.get("confidence") if h.get("confidence") in ("high", "medium", "low")
                else "low"
            ),
            reasoning=str(h.get("reasoning", "")),
            # Drop invented labels - the UI highlights these against the
            # evidence list, and a label that matches nothing highlights nothing.
            supporting_evidence=[
                s for s in (h.get("supporting_evidence") or []) if s in known_labels
            ],
            recommended_action=h.get("recommended_action") or None,
        )
        for i, h in enumerate(raw, start=1)
        if isinstance(h, dict) and h.get("cause")
    ]
    hypotheses.sort(key=lambda h: h.rank)

    response.summary = result.get("summary")
    response.hypotheses = hypotheses or None
    return response
