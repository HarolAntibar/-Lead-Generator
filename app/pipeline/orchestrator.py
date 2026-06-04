import logging
from datetime import datetime, timezone

from app.core.database import AsyncSessionLocal
from app.features.businesses import repository as businesses_repo
from app.features.campaigns import repository as campaign_repo
from app.features.campaigns.models import SearchRunStatus
from app.features.leads import service as leads_service
from app.pipeline import places as places_stage
from app.pipeline.constants import GOOGLE_TEXT_SEARCH_COST_USD

logger = logging.getLogger(__name__)


async def run_search(run_id: int, campaign_id: int) -> None:
    # Phase 1: fetch entities and mark the run as running.
    # Uses its own session — the HTTP request session is already closed by now.
    campaign = None
    async with AsyncSessionLocal() as session:
        run = await campaign_repo.get_search_run_by_id(session, run_id)
        campaign = await campaign_repo.get_campaign_by_id(session, campaign_id)

        if not run or not campaign:
            logger.error(
                "run_id=%d or campaign_id=%d not found — aborting pipeline",
                run_id,
                campaign_id,
            )
            return

        await campaign_repo.update_search_run(
            session,
            run,
            status=SearchRunStatus.running,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    # Phase 2: run the places stage with a fresh session.
    # Each upsert inside commits individually, so partial results are safe.
    try:
        async with AsyncSessionLocal() as session:
            results_count, new_count = await places_stage.run(session, campaign, run_id)

    except Exception:
        logger.exception("Pipeline failed for run_id=%d", run_id)
        async with AsyncSessionLocal() as session:
            run = await campaign_repo.get_search_run_by_id(session, run_id)
            if run:
                await campaign_repo.update_search_run(
                    session,
                    run,
                    status=SearchRunStatus.error,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    error="Pipeline failed — check server logs for details",
                )
        return

    # Phase 3: score each new business from this run.
    # We only score businesses first seen in this run — existing ones already
    # have a score (or will be re-scored when Phase 3 scraping enriches them).
    try:
        async with AsyncSessionLocal() as session:
            new_businesses = await businesses_repo.get_businesses_for_run(session, run_id)
            for business in new_businesses:
                await leads_service.score_and_save(session, business)
    except Exception:
        logger.exception("Scoring stage failed for run_id=%d — leads may be missing scores", run_id)
        # Non-fatal: the run is still marked done; scores can be recomputed later.

    # Phase 4: mark as done and record cost.
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
