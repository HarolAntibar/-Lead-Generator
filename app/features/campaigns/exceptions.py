from app.core.exceptions import NotFoundError
from app.features.campaigns.constants import CAMPAIGN_RESOURCE_NAME, SEARCH_RUN_RESOURCE_NAME


class CampaignNotFoundError(NotFoundError):
    def __init__(self, campaign_id: int) -> None:
        super().__init__(CAMPAIGN_RESOURCE_NAME, campaign_id)


class SearchRunNotFoundError(NotFoundError):
    def __init__(self, run_id: int) -> None:
        super().__init__(SEARCH_RUN_RESOURCE_NAME, run_id)
