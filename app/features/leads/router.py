from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_session
from app.export.csv_exporter import leads_to_csv
from app.export.excel_exporter import leads_to_excel
from app.features.leads import service as leads_service
from app.features.leads.exceptions import LeadScoreNotFound
from app.features.leads.models import LeadStatusChoice
from app.features.leads.schemas import LeadOut, LeadStatusOut, LeadStatusUpdate

router = APIRouter(prefix="/api/leads", tags=["leads"])

_settings = get_settings()


@router.get("", response_model=list[LeadOut])
async def list_leads(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    has_website: bool | None = Query(None),
    status: LeadStatusChoice | None = Query(None),
    opportunity_type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[LeadOut]:
    return await leads_service.list_leads(
        session,
        page=page,
        size=size,
        has_website=has_website,
        status=status,
        opportunity_type=opportunity_type,
    )


@router.get("/export")
async def export_leads(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    has_website: bool | None = Query(None),
    status: LeadStatusChoice | None = Query(None),
    opportunity_type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Download all matching leads as CSV or Excel.

    Accepts the same filters as GET /api/leads so the export always reflects
    the current view. No pagination — exports the full result set (up to 10 000 rows).
    """
    leads = await leads_service.list_leads(
        session,
        page=1,
        size=_settings.export_max_rows,
        has_website=has_website,
        status=status,
        opportunity_type=opportunity_type,
    )
    if format == "xlsx":
        content = leads_to_excel(leads)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=leads.xlsx"},
        )
    content = leads_to_csv(leads)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.patch("/{business_id}/status", response_model=LeadStatusOut)
async def update_lead_status(
    business_id: int,
    payload: LeadStatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> LeadStatusOut:
    updated = await leads_service.update_status(session, business_id=business_id, payload=payload)
    if updated is None:
        raise LeadScoreNotFound(business_id)
    return LeadStatusOut.model_validate(updated)
