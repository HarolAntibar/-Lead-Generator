from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.campaigns.models import Campaign, SearchRun, SearchRunStatus


async def create_campaign(
    session: AsyncSession,
    name: str,
    area_text: str,
    business_type: str,
    params: dict | None,
    created_by: int | None,
) -> Campaign:
    campaign = Campaign(
        name=name,
        area_text=area_text,
        business_type=business_type,
        params=params,
        created_by=created_by,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def get_campaign_by_id(session: AsyncSession, campaign_id: int) -> Campaign | None:
    result = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    return result.scalar_one_or_none()


async def list_campaigns(
    session: AsyncSession, offset: int, limit: int
) -> list[Campaign]:
    result = await session.execute(
        select(Campaign).order_by(Campaign.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def create_search_run(session: AsyncSession, campaign_id: int) -> SearchRun:
    run = SearchRun(campaign_id=campaign_id, status=SearchRunStatus.pending)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def get_search_run_by_id(session: AsyncSession, run_id: int) -> SearchRun | None:
    result = await session.execute(
        select(SearchRun).where(SearchRun.id == run_id)
    )
    return result.scalar_one_or_none()


async def list_search_runs_by_campaign(
    session: AsyncSession, campaign_id: int
) -> list[SearchRun]:
    result = await session.execute(
        select(SearchRun)
        .where(SearchRun.campaign_id == campaign_id)
        .order_by(SearchRun.created_at.desc())
    )
    return list(result.scalars().all())


async def update_search_run(session: AsyncSession, run: SearchRun, **fields: object) -> SearchRun:
    for key, value in fields.items():
        setattr(run, key, value)
    await session.commit()
    await session.refresh(run)
    return run
