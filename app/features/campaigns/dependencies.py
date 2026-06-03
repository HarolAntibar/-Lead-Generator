from typing import Annotated

from fastapi import Depends

from app.core.dependencies import SessionDep
from app.features.campaigns import service
from app.features.campaigns.models import Campaign


async def _get_campaign(campaign_id: int, session: SessionDep) -> Campaign:
    return await service.get_campaign_or_404(session, campaign_id)


CampaignDep = Annotated[Campaign, Depends(_get_campaign)]
