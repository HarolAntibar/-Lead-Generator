from fastapi import APIRouter, BackgroundTasks

from app.core.dependencies import PaginationDep, SessionDep
from app.features.campaigns import repository as campaign_repo
from app.features.campaigns import service
from app.features.campaigns.dependencies import CampaignDep
from app.features.campaigns.schemas import CampaignCreate, CampaignRead, SearchRunRead
from app.pipeline import orchestrator

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignRead, status_code=201)
async def create_campaign(data: CampaignCreate, session: SessionDep) -> CampaignRead:
    campaign = await service.create_campaign(session, data)
    return CampaignRead.model_validate(campaign)


@router.get("", response_model=list[CampaignRead])
async def list_campaigns(session: SessionDep, pagination: PaginationDep) -> list[CampaignRead]:
    campaigns = await service.list_campaigns(session, pagination.offset, pagination.size)
    return [CampaignRead.model_validate(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(campaign: CampaignDep) -> CampaignRead:
    return CampaignRead.model_validate(campaign)


@router.post("/{campaign_id}/runs", response_model=SearchRunRead, status_code=202)
async def trigger_search_run(
    campaign: CampaignDep,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> SearchRunRead:
    run = await campaign_repo.create_search_run(session, campaign.id)
    background_tasks.add_task(orchestrator.run_search, run.id, campaign.id)
    return SearchRunRead.model_validate(run)


@router.get("/{campaign_id}/runs", response_model=list[SearchRunRead])
async def list_search_runs(campaign: CampaignDep, session: SessionDep) -> list[SearchRunRead]:
    runs = await service.list_search_runs(session, campaign.id)
    return [SearchRunRead.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=SearchRunRead)
async def get_search_run(run_id: int, session: SessionDep) -> SearchRunRead:
    run = await service.get_search_run_or_404(session, run_id)
    return SearchRunRead.model_validate(run)
