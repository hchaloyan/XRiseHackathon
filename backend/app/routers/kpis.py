"""Router: /api/kpis. Every field is computed in pandas -- no LLM on this path."""

from datetime import date

from fastapi import APIRouter

from app.schemas import KpiResponse
from app.services import kpi_engine

router = APIRouter()


@router.get("/kpis", response_model=KpiResponse)
def get_kpis(day: date | None = None) -> KpiResponse:
    """Defaults to the newest full day in the dataset (spec 6.0)."""
    return KpiResponse.model_validate(kpi_engine.snapshot(day))
