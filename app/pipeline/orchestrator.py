import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.features.businesses import repository as businesses_repo
from app.features.campaigns import repository as campaign_repo
from app.features.campaigns.models import SearchRunStatus
from app.features.leads import service as leads_service
from app.pipeline import places as places_stage
from app.pipeline.constants import GOOGLE_TEXT_SEARCH_COST_USD

logger = logging.getLogger(__name__)


async def run_search(run_id: int, campaign_id: int) -> None:
    """Entry point called by BackgroundTasks.

    Wraps _execute() with a hard timeout so a run can never be stuck in
    'running' forever if the pipeline crashes between status updates.
    """
    timeout = get_settings().pipeline_run_timeout_seconds
    try:
        await asyncio.wait_for(_execute(run_id, campaign_id), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(
            "Pipeline timed out after %ds for run_id=%d — marking as error",
            timeout, run_id,
        )
        async with AsyncSessionLocal() as session:
            run = await campaign_repo.get_search_run_by_id(session, run_id)
            if run:
                await campaign_repo.update_search_run(
                    session,
                    run,
                    status=SearchRunStatus.error,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error=f"Pipeline timed out after {timeout}s",
                )


async def _execute(run_id: int, campaign_id: int) -> None:
    """Full pipeline execution — called inside the timeout wrapper."""
    async with AsyncSessionLocal() as session:
        run = await campaign_repo.get_search_run_by_id(session, run_id)
        campaign = await campaign_repo.get_campaign_by_id(session, campaign_id)

        if not run or not campaign:
            logger.error(
                "run_id=%d or campaign_id=%d not found — aborting pipeline",
                run_id, campaign_id,
            )
            return

        await campaign_repo.update_search_run(
            session,
            run,
            status=SearchRunStatus.running,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    try:
        async with AsyncSessionLocal() as session:
            results_count, new_count = await places_stage.run(session, campaign, run_id)

    except Exception as exc:
        logger.exception("Pipeline failed for run_id=%d", run_id)
        async with AsyncSessionLocal() as session:
            run = await campaign_repo.get_search_run_by_id(session, run_id)
            if run:
                await campaign_repo.update_search_run(
                    session,
                    run,
                    status=SearchRunStatus.error,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error=f"Pipeline failed: {exc}",
                )
        return

    try:
        async with AsyncSessionLocal() as session:
            new_businesses = await businesses_repo.get_businesses_for_run(session, run_id)
            for business in new_businesses:
                await leads_service.score_and_save(session, business)
    except Exception:
        logger.exception("Scoring stage failed for run_id=%d — leads may be missing scores", run_id)

    async with AsyncSessionLocal() as session:
        run = await campaign_repo.get_search_run_by_id(session, run_id)
        if run:
            await campaign_repo.update_search_run(
                session,
                run,
                status=SearchRunStatus.done,
                finished_at=datetime.now(timezone.utc).isoformat(),
                results_count=results_count,
                new_count=new_count,
                api_cost_est=GOOGLE_TEXT_SEARCH_COST_USD,
            )
