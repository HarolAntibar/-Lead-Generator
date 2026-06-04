from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_session
from app.features.leads import service as leads_service
from app.features.leads.exceptions import LeadScoreNotFound
from app.features.leads.models import LeadStatusChoice
from app.features.leads.schemas import LeadOut, LeadStatusOut, LeadStatusUpdate

router = APIRouter(prefix="/api/leads", tags=["leads"])


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
