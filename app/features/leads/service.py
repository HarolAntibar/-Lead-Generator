from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.features.businesses.models import Business, WebsiteAnalysis
from app.features.leads import repository as leads_repo
from app.features.leads.models import LeadScore, LeadStatus, LeadStatusChoice
from app.features.leads.schemas import LeadStatusUpdate
from app.features.leads.schemas import LeadOut, LeadStatusUpdate
from app.pipeline.scoring import compute_score


async def score_and_save(
    session: AsyncSession,
    business: Business,
    analysis: WebsiteAnalysis | None = None,
) -> LeadScore:
    """Compute the viability score for *business* and persist it.

    Called by the pipeline orchestrator after scraping is complete.
    *analysis* is None for businesses without a website; scoring.py handles
    that case by skipping signals 3 and 4.
    Also creates a 'new' CRM status if one doesn't exist yet (DO NOTHING if the
    salesperson has already moved it to another state).
    """
    settings = get_settings()
    result = compute_score(business, settings, analysis)

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
    # Only touch assigned_to if the client explicitly sent it in the request body.
    # model_fields_set contains the names of fields that were actually provided —
    # if assigned_to is absent from the JSON, we leave the current assignment untouched.
    update_assignment = "assigned_to" in payload.model_fields_set
    return await leads_repo.update_lead_status(
        session,
        business_id=business_id,
        status=payload.status,
        notes=payload.notes,
        update_assignment=update_assignment,
        assigned_to=payload.assigned_to if update_assignment else None,
    )


async def list_leads(
    session: AsyncSession,
    page: int,
    size: int,
    has_website: bool | None,
    status: LeadStatusChoice | None = None,
    opportunity_type: str | None = None,
) -> list[LeadOut]:
    rows = await leads_repo.list_leads(
        session,
        page=page,
        size=size,
        has_website=has_website,
        status=status,
        opportunity_type=opportunity_type,
    )
    return [LeadOut(**row) for row in rows]
