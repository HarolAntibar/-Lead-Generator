import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.features.businesses import repository as businesses_repo
from app.features.businesses.models import Business
from app.features.campaigns import repository as campaign_repo
from app.features.campaigns.models import SearchRunStatus
from app.features.leads import service as leads_service
from app.pipeline import extract as extract_stage
from app.pipeline import places as places_stage
from app.pipeline import scraper as scraper_stage
from app.pipeline import signals as signals_stage
from app.pipeline import tech_detect as tech_detect_stage
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
    """Full pipeline execution — called inside the timeout wrapper.

    Stage order (only orchestrator.py knows this):
      1. Places   — search Google, dedup by place_id, save businesses
      2. Scraping — fetch + analyse websites concurrently (bounded by semaphore)
      3. Scoring  — viability score v2 using all four signals
    """
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

    # --- Stage 1: Google Places search + dedup + save businesses ---------------
    try:
        async with AsyncSessionLocal() as session:
            results_count, new_count = await places_stage.run(session, campaign, run_id)
    except Exception as exc:
        logger.exception("Places stage failed for run_id=%d", run_id)
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

    # --- Stage 2: Scraping (businesses with websites only) ---------------------
    # Failures here are non-fatal: a scraping error means no WebsiteAnalysis is
    # saved for that business, and scoring will fall back to Phase 2 signals only.
    try:
        async with AsyncSessionLocal() as session:
            new_businesses = await businesses_repo.get_businesses_for_run(session, run_id)
        await _run_scraping_stage(new_businesses)
    except Exception:
        logger.exception(
            "Scraping stage failed for run_id=%d — continuing to scoring with partial data",
            run_id,
        )

    # --- Stage 3: Scoring v2 (with website analysis where available) -----------
    try:
        async with AsyncSessionLocal() as session:
            new_businesses = await businesses_repo.get_businesses_for_run(session, run_id)
            for business in new_businesses:
                analysis = await businesses_repo.get_website_analysis(session, business.id)
                await leads_service.score_and_save(session, business, analysis)
    except Exception:
        logger.exception(
            "Scoring stage failed for run_id=%d — leads may be missing scores", run_id
        )

    # --- Mark run as done -------------------------------------------------------
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


async def _run_scraping_stage(businesses: list[Business]) -> None:
    """Scrape all businesses with websites concurrently, bounded by a semaphore.

    asyncio.gather launches all tasks at once but the semaphore ensures only
    scraper_max_concurrency HTTP fetches run at any given moment. Tasks waiting
    for the semaphore are suspended (not threads) so VPS memory cost is negligible.
    """
    settings = get_settings()
    with_sites = [b for b in businesses if b.has_website and b.website_url]

    if not with_sites:
        logger.info("scraping stage: no businesses with websites in this run")
        return

    logger.info("scraping stage: %d businesses to scrape", len(with_sites))
    semaphore = asyncio.Semaphore(settings.scraper_max_concurrency)
    await asyncio.gather(*[_scrape_one(b, semaphore) for b in with_sites])


async def _scrape_one(business: Business, semaphore: asyncio.Semaphore) -> None:
    """Fetch, analyse, and persist data for one business website.

    The semaphore gates only the HTTP fetch — the resource under pressure.
    Parsing (tech_detect, signals, extract) and DB saves run outside the
    semaphore; they are fast/async and don't benefit from being serialised.

    Any exception is caught here so one failing site never cancels sibling tasks.
    """
    try:
        async with semaphore:
            html = await scraper_stage.fetch_html(business.website_url)

        analyzed_at = datetime.now(timezone.utc).isoformat()

        async with AsyncSessionLocal() as session:
            if html is None:
                await businesses_repo.save_website_analysis(
                    session,
                    business_id=business.id,
                    reachable=False,
                    cms_detected=None,
                    tech_stack=None,
                    has_chat=False,
                    has_booking=False,
                    freshness_signal=None,
                    quality_score=None,
                    raw_signals=None,
                    analyzed_at=analyzed_at,
                )
                logger.info("scraping: business_id=%d unreachable — saved reachable=False", business.id)
                return

            tech = tech_detect_stage.analyze(html)
            signals = signals_stage.analyze(html)
            contacts = extract_stage.extract(html)

            await businesses_repo.save_website_analysis(
                session,
                business_id=business.id,
                reachable=True,
                cms_detected=tech.cms_detected,
                tech_stack=tech.tech_stack,
                has_chat=signals.has_chat,
                has_booking=signals.has_booking,
                freshness_signal=signals.freshness_signal,
                quality_score=signals.quality_score,
                raw_signals=signals.raw_signals,
                analyzed_at=analyzed_at,
            )

            if contacts:
                await businesses_repo.save_contacts(
                    session,
                    business.id,
                    [
                        {
                            "email": c.email,
                            "name": c.name,
                            "role": c.role,
                            "source": c.source,
                            "confidence": c.confidence,
                        }
                        for c in contacts
                    ],
                )

            logger.info(
                "scraped business_id=%d: cms=%s, opportunity_type=%s, contacts=%d",
                business.id,
                tech.cms_detected or "unknown",
                tech.opportunity_type,
                len(contacts),
            )

    except Exception:
        logger.exception(
            "scraping failed for business_id=%d url=%s", business.id, business.website_url
        )
