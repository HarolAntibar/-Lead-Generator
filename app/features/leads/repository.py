from datetime import datetime, timezone

from sqlalchemy import Float, cast, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.businesses.models import Business
from app.features.leads.models import LeadScore, LeadStatus, LeadStatusChoice


async def upsert_lead_score(
    session: AsyncSession,
    business_id: int,
    score: int,
    breakdown: dict,
    model_version: str,
) -> LeadScore:
    """Insert or update the lead score for *business_id*.

    Uses INSERT ... ON CONFLICT (business_id) DO UPDATE so that re-running the
    pipeline with richer data (e.g. after scraping in Phase 3) refreshes the score
    instead of creating a duplicate row.
    """
    now = datetime.now(timezone.utc).isoformat()
    stmt = (
        insert(LeadScore)
        .values(
            business_id=business_id,
            score=score,
            breakdown=breakdown,
            model_version=model_version,
            computed_at=now,
        )
        .on_conflict_do_update(
            index_elements=["business_id"],
            set_={
                "score": score,
                "breakdown": breakdown,
                "model_version": model_version,
                "computed_at": now,
            },
        )
        .returning(LeadScore)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def upsert_lead_status(
    session: AsyncSession,
    business_id: int,
    status: LeadStatusChoice = LeadStatusChoice.new,
) -> LeadStatus:
    """Insert a 'new' status for *business_id* if one does not exist yet.

    DO NOTHING on conflict — the pipeline must never overwrite a status that a
    salesperson has already set (e.g. 'contacted', 'interested').
    """
    stmt = (
        insert(LeadStatus)
        .values(business_id=business_id, status=status)
        .on_conflict_do_nothing(index_elements=["business_id"])
        .returning(LeadStatus)
    )
    result = await session.execute(stmt)
    await session.commit()
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    row = await session.execute(
        select(LeadStatus).where(LeadStatus.business_id == business_id)
    )
    return row.scalar_one()


async def update_lead_status(
    session: AsyncSession,
    business_id: int,
    status: LeadStatusChoice,
    notes: str | None,
    update_assignment: bool = False,
    update_notes: bool = False,
    assigned_to: int | None = None,
) -> LeadStatus | None:
    row = await session.execute(
        select(LeadStatus).where(LeadStatus.business_id == business_id)
    )
    lead_status = row.scalar_one_or_none()
    if lead_status is None:
        return None
    lead_status.status = status
    # Only overwrite notes if the caller explicitly included it in the request.
    # Inline list updates only send status — we must not wipe existing notes.
    if update_notes:
        lead_status.notes = notes
    if update_assignment:
        lead_status.assigned_to = assigned_to
    await session.commit()
    await session.refresh(lead_status)
    return lead_status


async def get_lead_score(session: AsyncSession, business_id: int) -> LeadScore | None:
    result = await session.execute(
        select(LeadScore).where(LeadScore.business_id == business_id)
    )
    return result.scalar_one_or_none()


async def get_stats(session: AsyncSession) -> dict:
    """Return aggregate counts for the home page dashboard.

    Three queries: total leads, count per CRM status, count per opportunity type.
    Kept as separate queries (not a single GROUP BY ROLLUP) for clarity — the
    result sets are tiny so there is no meaningful performance difference.
    """
    from sqlalchemy import func

    total = (await session.execute(
        select(func.count()).select_from(LeadScore)
    )).scalar_one()

    status_rows = (await session.execute(
        select(LeadStatus.status, func.count().label("cnt"))
        .group_by(LeadStatus.status)
    )).all()
    by_status = {row.status.value: row.cnt for row in status_rows}

    opp_rows = (await session.execute(
        select(
            LeadScore.breakdown["opportunity_type"].as_string().label("opp_type"),
            func.count().label("cnt"),
        ).group_by("opp_type")
    )).all()
    by_opp_type = {row.opp_type: row.cnt for row in opp_rows if row.opp_type}

    return {"total": total, "by_status": by_status, "by_opp_type": by_opp_type}


def _leads_select_query():
    """Base SELECT joining businesses + lead_scores + lead_status.

    Extracted so list_leads and get_single_lead share the same column set
    without duplicating the join definition.
    """
    return (
        select(
            Business.id.label("business_id"),
            Business.name,
            Business.category,
            Business.has_website,
            Business.website_url,
            cast(Business.rating, Float).label("rating"),
            Business.reviews_count,
            LeadScore.score,
            LeadScore.breakdown,
            LeadScore.breakdown["opportunity_type"].as_string().label("opportunity_type"),
            LeadScore.computed_at,
            LeadStatus.status,
            LeadStatus.notes,
            LeadStatus.assigned_to,
        )
        .join(LeadScore, LeadScore.business_id == Business.id)
        .join(LeadStatus, LeadStatus.business_id == Business.id)
        .order_by(LeadScore.score.desc())
    )


async def list_leads(
    session: AsyncSession,
    page: int = 1,
    size: int = 20,
    has_website: bool | None = None,
    status: LeadStatusChoice | None = None,
    opportunity_type: str | None = None,
) -> list[dict]:
    """Return a flat list of dicts combining businesses + scores + statuses.

    Uses a raw join so we return everything in one query without loading three
    separate ORM trees per lead. opportunity_type is extracted from the
    breakdown JSONB column using PostgreSQL's -> operator.
    """
    query = _leads_select_query()

    if has_website is not None:
        query = query.where(Business.has_website == has_website)
    if status is not None:
        query = query.where(LeadStatus.status == status)
    if opportunity_type is not None:
        query = query.where(
            LeadScore.breakdown["opportunity_type"].as_string() == opportunity_type
        )

    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await session.execute(query)
    return [row._asdict() for row in result.all()]


async def get_single_lead(
    session: AsyncSession,
    business_id: int,
) -> dict | None:
    """Return the combined lead row for one business, or None if not scored yet."""
    query = _leads_select_query().where(Business.id == business_id)
    result = await session.execute(query)
    row = result.one_or_none()
    return row._asdict() if row is not None else None
