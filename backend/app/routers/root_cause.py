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
    EvidenceItem,
    RootCauseItem,
    RootCauseRequest,
    RootCauseResponse,
    SopCitation,
)
from app.services import root_cause as rc
from app.services.knowledge_base import get_knowledge_base

router = APIRouter()

SOP_CHUNKS = 3


def _evidence_items(bundle: dict) -> list[EvidenceItem]:
    """Flatten the assembled evidence into display rows.

    These render under the ranked causes, so a judge can see the figures the
    ranking was built on rather than taking the model's word for it.
    """
    event = bundle["event"]
    history = bundle["history"]
    nearby = bundle["nearby"]
    shift = bundle["shift"]
    inventory = bundle["inventory"]

    items: list[EvidenceItem] = []

    label = history["label"]
    if history["occurrences_on_machine"] > 1:
        detail = (
            f"{history['occurrences_on_machine']} times on {event['machine_id']} "
            f"in {history['window_days']} days "
            f"({history['occurrences_on_line']} across the {event['line']} line)"
        )
        if history["minutes_on_machine"]:
            detail += f", {history['minutes_on_machine']:.0f} minutes total"
        items.append(EvidenceItem(label=f"{label} recurrence", detail=detail))

    for note in history["recent_notes"][:3]:
        items.append(EvidenceItem(label="Previous operator note", detail=note))

    for n in nearby["downtime"][:4]:
        where = "same machine" if n["same_machine"] else n["machine_id"]
        items.append(
            EvidenceItem(
                label=f"{n['reason_code']} nearby",
                detail=(
                    f"{n['duration_minutes']:.0f} min on {where}, {n['offset']}"
                    + (f" - {n['operator_note']}" if n["operator_note"] else "")
                ),
            )
        )

    for n in nearby["quality"][:3]:
        where = "same machine" if n["same_machine"] else n["machine_id"]
        items.append(
            EvidenceItem(
                label=f"{n['defect_type']} nearby",
                detail=f"{n['count']} parts on {where}, {n['offset']}",
            )
        )

    items.append(
        EvidenceItem(
            label="Machine that day",
            detail=(
                f"{shift['machine_downtime_minutes']:.0f} min down across "
                f"{shift['machine_downtime_events']} events, "
                f"{shift['machine_good_count']} good of {shift['machine_total_count']} parts, "
                f"scrap {shift['machine_scrap_rate'] * 100:.1f}%"
            ),
        )
    )

    if shift["changeover_earlier_today"]:
        items.append(
            EvidenceItem(
                label="Changeover earlier",
                detail="A changeover ran on this machine before the event, same day",
            )
        )

    if inventory and inventory["parts_below_reorder"]:
        for part in inventory["parts_below_reorder"][:3]:
            items.append(
                EvidenceItem(
                    label="Stock below reorder",
                    detail=(
                        f"{part['part_id']} {part['description']}: "
                        f"{part['on_hand']} on hand vs reorder point "
                        f"{part['reorder_point']}, {part['days_of_cover']} days cover"
                    ),
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
        evidence="\n".join(f"- {e.label}: {e.detail}" for e in evidence),
        sops=sop_text,
    )
    result = get_client().complete(
        prompt, ROOT_CAUSE_SCHEMA, timeout=settings.root_cause_timeout
    )

    if result is None:
        return response  # evidence and citations still render

    raw_causes = result.get("causes") or []
    causes = [
        RootCauseItem(
            cause=str(c.get("cause", "")),
            likelihood=str(c.get("likelihood", "low")).lower(),
            evidence=str(c.get("evidence", "")),
            action=str(c.get("action", "")),
        )
        for c in raw_causes
        if isinstance(c, dict) and c.get("cause")
    ]

    response.summary = result.get("summary")
    response.causes = causes or None
    return response
