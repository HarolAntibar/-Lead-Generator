import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.features.campaigns.models import SearchRun
from app.features.campaigns.repository import create_campaign, create_search_run
from app.main import app


@pytest.fixture
async def db_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
async def clean_tables(db_session: AsyncSession) -> None:
    # Delete in FK-safe order so constraints don't block truncation.
    # website_analyses and contacts reference businesses (CASCADE), so remove them first.
    # businesses.first_seen_run_id -> search_runs (SET NULL) — businesses before runs.
    # search_runs.campaign_id -> campaigns (CASCADE) — runs before campaigns.
    await db_session.execute(text("DELETE FROM website_analyses"))
    await db_session.execute(text("DELETE FROM contacts"))
    await db_session.execute(text("DELETE FROM lead_scores"))
    await db_session.execute(text("DELETE FROM lead_status"))
    await db_session.execute(text("DELETE FROM businesses"))
    await db_session.execute(text("DELETE FROM search_runs"))
    await db_session.execute(text("DELETE FROM campaigns"))
    await db_session.commit()


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def search_run(db_session: AsyncSession) -> SearchRun:
    """Creates a minimal campaign + search_run so tests have a valid FK run_id."""
    campaign = await create_campaign(
        db_session, name="Fixture Campaign", area_text="Test Area",
        business_type="test_type", params=None, created_by=None,
    )
    return await create_search_run(db_session, campaign.id)
