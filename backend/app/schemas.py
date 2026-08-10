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


class ApiModel(BaseModel):
    """Base: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


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
    # line -> minutes lost to MATERIAL_STARVE on the selected day
    starved_minutes_by_line: dict[str, float]
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
