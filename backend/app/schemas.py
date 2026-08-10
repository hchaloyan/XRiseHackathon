"""ALL Pydantic request/response models. This file is the API contract.

Two rules govern every model here (spec 4.1):
  - COMPUTED fields come from pandas. Always present, never Optional.
  - GENERATED fields come from the LLM. Always Optional, default None.

Mirror every change into frontend/src/api/types.ts by hand.
Serialization uses camelCase aliases; Python stays snake_case.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import List, Optional


class ApiModel(BaseModel):
    """Base: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


# Models are defined during the 0:00-0:45 contract slice.
# Nothing else in the codebase may define a response shape.

# ===== KNOWLEDGE BASE =====

# Spec 7.1: the fixed redirect for queries the SOP corpus cannot answer.
OFF_TOPIC_MESSAGE = (
    "I answer from SOPs and manuals. For line data, click any row below."
)


class SearchRequest(ApiModel):
    query: str


class SOPResult(ApiModel):
    """All COMPUTED - retrieval only, no model involved."""

    id: str  # chunk id, e.g. "SOP-002#3"
    doc_id: str
    title: str
    section: str
    content: str
    distance: float


class SearchResponse(ApiModel):
    query: str
    results: List[SOPResult]
    # Non-null only when nothing cleared the similarity floor.
    fallback_message: Optional[str] = None


class ExplainRequest(ApiModel):
    query: str
    sop_ids: List[str]  # chunk ids returned by /api/search


class ExplainStep(ApiModel):
    action: str
    why: str


class ExplainResponse(ApiModel):
    query: str
    sources: List[str]  # doc_ids actually shown to the model - COMPUTED
    # GENERATED below: all Optional, all None when the model fails or times out.
    explanation: Optional[str] = None
    steps: Optional[List[ExplainStep]] = None
    common_mistake: Optional[str] = None
    estimated_minutes: Optional[int] = None


# JSON schema handed to Ollama's `format` param. Every array carries explicit
# minItems/maxItems (spec 8).
EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "steps": {
            "type": "array",
            "minItems": 2,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["action", "why"],
            },
        },
        "common_mistake": {"type": "string"},
        "estimated_minutes": {"type": "integer"},
    },
    "required": ["explanation", "steps", "common_mistake", "estimated_minutes"],
}


# ===== KPI INSIGHTS =====
# Names follow frontend/src/api/types.ts, which the redesigned components are
# already built against. The computed block below is an addition to that
# contract, not a change to it: without it the header renders empty whenever
# the model is slow, which is the one moment it must not (spec 5).

Severity = Literal["high", "medium", "low"]


class WorstMachine(ApiModel):
    machine_id: str
    name: str
    line: str
    oee: float
    downtime_minutes: float
    scrap_rate: float


class ReasonTotal(ApiModel):
    reason_code: str
    minutes: float
    events: int


class Callout(ApiModel):
    """One highlighted finding in the morning brief. GENERATED."""

    title: str
    detail: str
    severity: Severity
    # Pre-formatted by pandas. The model quotes it; it never computes it.
    metric: Optional[str] = None


class InsightResponse(ApiModel):
    """COMPUTED first, GENERATED after."""

    day: date

    # COMPUTED - always present, so the header shows real numbers even when
    # every generated field below is null.
    oee: float
    scrap_rate: float
    downtime_minutes: float
    oee_delta: Optional[float] = None  # None only on the first day of the window
    worst_machines: List[WorstMachine] = []
    downtime_by_reason: List[ReasonTotal] = []
    parts_below_reorder: int = 0

    # GENERATED - null when the model fails or times out.
    headline: Optional[str] = None
    narrative: Optional[str] = None
    callouts: Optional[List[Callout]] = None


INSIGHTS_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "narrative": {"type": "string"},
        "callouts": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "metric": {"type": "string"},
                },
                "required": ["title", "detail", "severity", "metric"],
            },
        },
    },
    "required": ["headline", "narrative", "callouts"],
}


# ===== ROOT CAUSE =====

class RootCauseRequest(ApiModel):
    event_id: str


class EventContext(ApiModel):
    """The row the user clicked. All COMPUTED."""

    event_id: str
    kind: Literal["downtime", "quality"]
    machine_id: str
    machine_name: str
    machine_type: str
    line: str
    start: datetime
    shift: str
    duration_minutes: Optional[float] = None
    reason_code: Optional[str] = None
    operator_note: Optional[str] = None
    defect_type: Optional[str] = None
    defect_count: Optional[int] = None


class Evidence(ApiModel):
    """One supporting data point. COMPUTED in pandas before the model runs,
    so a judge can see the figure the ranking was built on."""

    label: str
    value: str
    detail: Optional[str] = None


class SopCitation(ApiModel):
    """Where the answer came from. COMPUTED by retrieval, not by the model -
    the model cannot cite a document that was not put in front of it."""

    doc_id: str
    title: str
    section: str


class Hypothesis(ApiModel):
    """GENERATED. Ranked against the evidence above, never inventing figures."""

    rank: int
    cause: str
    confidence: Severity
    reasoning: str
    # Labels drawn from evidence[], so the ranking is traceable to numbers.
    supporting_evidence: List[str] = []
    recommended_action: Optional[str] = None


class RootCauseResponse(ApiModel):
    event_id: str
    # COMPUTED - both render even when the model fails (spec 5).
    event: EventContext
    evidence: List[Evidence]
    sources: List[SopCitation]
    # GENERATED.
    hypotheses: Optional[List[Hypothesis]] = None
    summary: Optional[str] = None


ROOT_CAUSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "hypotheses": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "cause": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reasoning": {"type": "string"},
                    "supporting_evidence": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {"type": "string"},
                    },
                    "recommended_action": {"type": "string"},
                },
                "required": [
                    "rank", "cause", "confidence", "reasoning",
                    "supporting_evidence", "recommended_action",
                ],
            },
        },
    },
    "required": ["summary", "hypotheses"],
}


# --- GET /api/kpis -----------------------------------------------------------
# All computed. kpi_engine.py produces every number here; the model sees this
# payload but never writes to it.


class KpiValues(ApiModel):
    oee: float
    availability: float
    performance: float
    quality: float
    scrap_rate: float
    downtime_minutes: float
    good_count: int
    total_count: int


class MachineKpi(KpiValues):
    machine_id: str
    name: str
    machine_type: str
    keywords: list[str]  # search terms: "3d printing", "molder", "cnc"
    line: str
    cell: str


class TrendPoint(KpiValues):
    day: date


class EventRow(ApiModel):
    """Downtime and quality rows share one shape so the event table can sort
    them together. The kind-specific fields are null on the other kind -- these
    are computed, not generated, despite being nullable."""

    event_id: str
    kind: Literal["downtime", "quality"]
    machine_id: str
    machine_name: str
    machine_type: str
    line: str
    shift: str
    start: datetime

    duration_minutes: float | None = None
    reason_code: str | None = None
    operator_note: str | None = None

    defect_type: str | None = None
    defect_count: int | None = None


class InventoryItem(ApiModel):
    part_id: str
    description: str
    line: str
    uom: str
    on_hand: int
    reorder_point: int
    daily_usage: int
    days_of_cover: float
    below_reorder: bool


class Inventory(ApiModel):
    """CLAUDE.md capability 1 names inventory alongside OEE, scrap and downtime."""

    parts_tracked: int
    parts_below_reorder: int
    lowest_days_of_cover: float
    items: list[InventoryItem]


class KpiResponse(ApiModel):
    """Event rows ride along here rather than in a fifth endpoint: CLAUDE.md
    names four routers, and the single screen loads in one fetch."""

    day: date
    plant: KpiValues
    trend: list[TrendPoint]
    machines: list[MachineKpi]
    events: list[EventRow]
    inventory: Inventory
