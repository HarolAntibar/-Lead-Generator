from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.businesses.models import Business
from app.features.leads import repository as leads_repo
from app.features.leads.models import LeadScore, LeadStatus, LeadStatusChoice
from app.features.leads.schemas import LeadOut, LeadStatusUpdate
from app.pipeline.scoring import compute_score


async def score_and_save(session: AsyncSession, business: Business) -> LeadScore:
    """Compute the viability score for *business* and persist it.

    Called by the pipeline orchestrator after a business is inserted/confirmed.
    Also creates a 'new' CRM status if one doesn't exist yet (DO NOTHING if the
    salesperson has already moved it to another state).
    """
    settings = get_settings()
    result = compute_score(business, settings)

    lead_score = await leads_repo.upsert_lead_score(
        session,
        business_id=business.id,
        score=result.score,
        breakdown=result.breakdown,
        model_version=result.model_version,
    )
    await leads_repo.upsert_lead_status(session, business_id=business.id)
    return lead_score


async def update_status(
    session: AsyncSession,
    business_id: int,
    payload: LeadStatusUpdate,
) -> LeadStatus | None:
    return await leads_repo.update_lead_status(
        session,
        business_id=business_id,
        status=payload.status,
        notes=payload.notes,
    )


async def list_leads(
    session: AsyncSession,
    page: int,
    size: int,
    has_website: bool | None,
) -> list[LeadOut]:
    rows = await leads_repo.list_leads(session, page=page, size=size, has_website=has_website)
    return [LeadOut(**row) for row in rows]
