from sqlalchemy.ext.asyncio import AsyncSession

from app.features.campaigns import repository
from app.features.campaigns.exceptions import CampaignNotFoundError, SearchRunNotFoundError
from app.features.campaigns.models import Campaign, SearchRun
from app.features.campaigns.schemas import CampaignCreate


async def create_campaign(
    session: AsyncSession,
    data: CampaignCreate,
    created_by: int | None = None,
) -> Campaign:
    params: dict | None = None
    if data.location_bias:
        params = {
            "location_bias": {
                "lat": data.location_bias.lat,
                "lng": data.location_bias.lng,
                "radius_meters": data.location_bias.radius_meters,
            }
        }

    return await repository.create_campaign(
        session=session,
        name=data.name,
        area_text=data.area_text,
        business_type=data.business_type,
        params=params,
        created_by=created_by,
    )


async def get_campaign_or_404(session: AsyncSession, campaign_id: int) -> Campaign:
    campaign = await repository.get_campaign_by_id(session, campaign_id)
    if not campaign:
        raise CampaignNotFoundError(campaign_id)
    return campaign


async def list_campaigns(
    session: AsyncSession, offset: int, limit: int
) -> list[Campaign]:
    return await repository.list_campaigns(session, offset, limit)


async def get_search_run_or_404(session: AsyncSession, run_id: int) -> SearchRun:
    run = await repository.get_search_run_by_id(session, run_id)
    if not run:
        raise SearchRunNotFoundError(run_id)
    return run


async def list_search_runs(session: AsyncSession, campaign_id: int) -> list[SearchRun]:
    return await repository.list_search_runs_by_campaign(session, campaign_id)
