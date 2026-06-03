"""Phase 1 — Pipeline places stage tests.

Tests the places.run() orchestration function with a mocked GooglePlacesClient
so no real Google API calls or costs are incurred.

What we verify:
- Returned places are inserted as businesses in the DB
- results_count and new_count are accurate
- Re-running the same places returns new_count=0 (dedup)
- location_bias is forwarded correctly from campaign params
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.campaigns.models import Campaign
from app.features.campaigns.repository import create_campaign, create_search_run
from app.integrations.google.client import PlaceResult
from app.pipeline import places as places_stage


def _make_place(place_id: str, name: str) -> PlaceResult:
    return PlaceResult(
        place_id=place_id,
        name=name,
        address="Test Address",
        lat=40.4,
        lng=-3.7,
        phone_raw="91 000 00 00",
        website_url="https://example.com",
        category="restaurant",
        rating=4.2,
        reviews_count=50,
    )


FAKE_PLACES = [
    _make_place("place_001", "Restaurante Uno"),
    _make_place("place_002", "Restaurante Dos"),
    _make_place("place_003", "Restaurante Tres"),
]


@pytest.fixture
async def campaign_and_run(db_session: AsyncSession) -> tuple[Campaign, int]:
    """Creates a campaign + first run, returning (campaign, run_id)."""
    campaign = await create_campaign(
        db_session,
        name="Pipeline Test Campaign",
        area_text="Madrid",
        business_type="restaurante",
        params=None,
        created_by=None,
    )
    run = await create_search_run(db_session, campaign.id)
    return campaign, run.id


async def test_places_stage_inserts_businesses_and_returns_counts(
    db_session: AsyncSession, campaign_and_run: tuple[Campaign, int]
) -> None:
    campaign, run_id = campaign_and_run

    with patch(
        "app.pipeline.places.GooglePlacesClient.search_places",
        new=AsyncMock(return_value=FAKE_PLACES),
    ):
        results_count, new_count = await places_stage.run(db_session, campaign, run_id)

    assert results_count == 3
    assert new_count == 3


async def test_places_stage_dedup_on_second_run(
    db_session: AsyncSession, campaign_and_run: tuple[Campaign, int]
) -> None:
    campaign, run_id = campaign_and_run
    run2 = await create_search_run(db_session, campaign.id)

    with patch(
        "app.pipeline.places.GooglePlacesClient.search_places",
        new=AsyncMock(return_value=FAKE_PLACES),
    ):
        await places_stage.run(db_session, campaign, run_id)
        results_count, new_count = await places_stage.run(db_session, campaign, run2.id)

    # Same places returned by Google a second time — none should be "new"
    assert results_count == 3
    assert new_count == 0


async def test_places_stage_empty_response_returns_zero_counts(
    db_session: AsyncSession, campaign_and_run: tuple[Campaign, int]
) -> None:
    campaign, run_id = campaign_and_run

    with patch(
        "app.pipeline.places.GooglePlacesClient.search_places",
        new=AsyncMock(return_value=[]),
    ):
        results_count, new_count = await places_stage.run(db_session, campaign, run_id)

    assert results_count == 0
    assert new_count == 0


async def test_places_stage_partial_dedup(
    db_session: AsyncSession, campaign_and_run: tuple[Campaign, int]
) -> None:
    campaign, run_id = campaign_and_run
    run2 = await create_search_run(db_session, campaign.id)

    first_batch = FAKE_PLACES[:2]  # place_001, place_002
    new_place = _make_place("place_004", "Restaurante Cuatro")
    second_batch = FAKE_PLACES[:2] + [new_place]  # place_001, place_002 again + one new

    with patch(
        "app.pipeline.places.GooglePlacesClient.search_places",
        new=AsyncMock(return_value=first_batch),
    ):
        await places_stage.run(db_session, campaign, run_id)

    with patch(
        "app.pipeline.places.GooglePlacesClient.search_places",
        new=AsyncMock(return_value=second_batch),
    ):
        results_count, new_count = await places_stage.run(db_session, campaign, run2.id)

    assert results_count == 3
    assert new_count == 1  # Only place_004 is truly new


async def test_places_stage_builds_query_from_campaign_fields(
    db_session: AsyncSession, campaign_and_run: tuple[Campaign, int]
) -> None:
    campaign, run_id = campaign_and_run
    mock_search = AsyncMock(return_value=[])

    with patch("app.pipeline.places.GooglePlacesClient.search_places", new=mock_search):
        await places_stage.run(db_session, campaign, run_id)

    # The query passed to Google must combine business_type and area_text
    call_args = mock_search.call_args
    query_used = call_args.args[0]
    assert campaign.business_type in query_used
    assert campaign.area_text in query_used


async def test_places_stage_forwards_location_bias(
    db_session: AsyncSession
) -> None:
    campaign = await create_campaign(
        db_session,
        name="Location Bias Test",
        area_text="Sevilla",
        business_type="gym",
        params={"location_bias": {"lat": 37.38, "lng": -5.99, "radius_meters": 2000.0}},
        created_by=None,
    )
    run = await create_search_run(db_session, campaign.id)
    mock_search = AsyncMock(return_value=[])

    with patch("app.pipeline.places.GooglePlacesClient.search_places", new=mock_search):
        await places_stage.run(db_session, campaign, run.id)

    # Second positional arg is the LocationBias object
    call_args = mock_search.call_args
    location_bias = call_args.args[1]
    assert location_bias is not None
    assert location_bias.lat == pytest.approx(37.38)
    assert location_bias.lng == pytest.approx(-5.99)
    assert location_bias.radius_meters == pytest.approx(2000.0)
