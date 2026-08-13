"""Router: /api/kpis. Every field is computed in pandas -- no LLM on this path."""

from datetime import date

from fastapi import APIRouter

from app.schemas import DaysResponse, KpiResponse
from app.services import kpi_engine

router = APIRouter()


@router.get("/days", response_model=DaysResponse)
def get_days() -> DaysResponse:
    """Which days the picker may offer. Days with no production are absent."""
    days = sorted({point["day"] for point in kpi_engine.trend()})
    today = date.today()
    return DaysResponse(
        days=days,
        latest=days[-1],
        earliest=days[0],
        today=today,
        days_behind=max((today - days[-1]).days, 0),
    )


@router.get("/kpis", response_model=KpiResponse)
def get_kpis(day: date | None = None) -> KpiResponse:
    """Defaults to the newest full day in the dataset (spec 6.0)."""
    return KpiResponse.model_validate(kpi_engine.snapshot(day))


@router.get("/report")
def get_report(day: date | None = None, format: str = "pdf"):
    """Download the shift report. Computed only - never triggers generation.

    A download that silently spent ten seconds on a model call would be a
    surprising thing for a Save dialog to do, so the report ships whatever
    narrative has already been generated and says so when there is none.
    """
    from fastapi import HTTPException
    from fastapi.responses import Response

    from app.services import report as report_service

    builder = report_service.BUILDERS.get(format.lower())
    if builder is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format {format!r}. Use pdf, xlsx or mis.",
        )

    build, media_type, extension = builder
    resolved = day or kpi_engine.latest_day()
    try:
        payload = build(resolved)
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Export needs a package that is not installed: {exc}",
        ) from exc

    filename = f"shift-report-{resolved.isoformat()}.{extension}"
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
