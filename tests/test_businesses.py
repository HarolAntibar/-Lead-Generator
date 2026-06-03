"""Phase 1 — Business API and deduplication tests.

Covers: list/get endpoints, upsert logic, has_website flag, dedup by google_place_id,
pagination, and sort order.
All tests run against the real database; clean_tables (autouse) truncates between tests.
"""
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.businesses import service as businesses_service
from app.features.campaigns.models import SearchRun
from app.integrations.google.client import PlaceResult


URL = "/api/businesses"


def make_place(
    place_id: str = "place_test_abc",
    name: str = "Pizzeria Roma",
    *,
    website_url: str | None = "https://example.com",
    rating: float | None = 4.5,
    reviews_count: int | None = 100,
) -> PlaceResult:
    """Builds a PlaceResult for use in tests — customise only what matters."""
    return PlaceResult(
        place_id=place_id,
        name=name,
        address="Calle Mayor 1, Madrid",
        lat=40.41,
        lng=-3.70,
        phone_raw="91 123 45 67",
        website_url=website_url,
        category="restaurant",
        rating=rating,
        reviews_count=reviews_count,
    )


# ---------------------------------------------------------------------------
# HTTP endpoint — list / get
# ---------------------------------------------------------------------------

async def test_list_businesses_empty_returns_empty_list(client: AsyncClient) -> None:
    r = await client.get(URL)
    assert r.status_code == 200
    assert r.json() == []


async def test_get_business_not_found_returns_404(client: AsyncClient) -> None:
    r = await client.get(f"{URL}/99999")
    assert r.status_code == 404


async def test_list_businesses_after_upsert(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    await businesses_service.upsert_from_place_result(db_session, make_place(), search_run.id)
    r = await client.get(URL)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Pizzeria Roma"


async def test_get_business_by_id(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    place = make_place(place_id="biz_get_id_test", name="Get Me Business")
    business, _ = await businesses_service.upsert_from_place_result(db_session, place, search_run.id)
    r = await client.get(f"{URL}/{business.id}")
    assert r.status_code == 200
    assert r.json()["name"] == "Get Me Business"
    assert r.json()["google_place_id"] == "biz_get_id_test"


async def test_list_businesses_pagination(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    for i in range(5):
        await businesses_service.upsert_from_place_result(
            db_session, make_place(place_id=f"page_place_{i}", name=f"Business {i}"), search_run.id
        )
    page1 = await client.get(f"{URL}?page=1&size=3")
    page2 = await client.get(f"{URL}?page=2&size=3")
    assert len(page1.json()) == 3
    assert len(page2.json()) == 2


# ---------------------------------------------------------------------------
# has_website flag
# ---------------------------------------------------------------------------

async def test_upsert_with_website_sets_has_website_true(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    place = make_place(website_url="https://example.com")
    business, is_new = await businesses_service.upsert_from_place_result(db_session, place, search_run.id)
    assert is_new is True
    assert business.has_website is True
    assert business.website_url == "https://example.com"


async def test_upsert_without_website_sets_has_website_false(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    place = make_place(website_url=None)
    business, _ = await businesses_service.upsert_from_place_result(db_session, place, search_run.id)
    assert business.has_website is False
    assert business.website_url is None


# ---------------------------------------------------------------------------
# Deduplication by google_place_id
# ---------------------------------------------------------------------------

async def test_upsert_same_place_id_twice_second_is_not_new(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    # The anti-reprocess rule: same place_id on a second run must NOT create a new row
    place = make_place(place_id="dedup_test_place")
    _, is_new_first = await businesses_service.upsert_from_place_result(db_session, place, search_run.id)
    _, is_new_second = await businesses_service.upsert_from_place_result(db_session, place, search_run.id)
    assert is_new_first is True
    assert is_new_second is False


async def test_upsert_same_place_id_does_not_duplicate_rows(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    place = make_place(place_id="dedup_count_test")
    await businesses_service.upsert_from_place_result(db_session, place, search_run.id)
    await businesses_service.upsert_from_place_result(db_session, place, search_run.id)
    r = await client.get(URL)
    assert len(r.json()) == 1  # Still only one row


async def test_upsert_different_place_ids_both_created(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    place_a = make_place(place_id="place_alpha", name="Business Alpha")
    place_b = make_place(place_id="place_beta", name="Business Beta")
    _, new_a = await businesses_service.upsert_from_place_result(db_session, place_a, search_run.id)
    _, new_b = await businesses_service.upsert_from_place_result(db_session, place_b, search_run.id)
    assert new_a is True
    assert new_b is True


# ---------------------------------------------------------------------------
# Sort order
# ---------------------------------------------------------------------------

async def test_list_businesses_default_sort_is_alphabetical(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    for name in ["Zara", "Apple", "Microsoft"]:
        await businesses_service.upsert_from_place_result(
            db_session, make_place(place_id=f"sort_{name}", name=name), search_run.id
        )
    r = await client.get(URL)
    names = [b["name"] for b in r.json()]
    assert names == sorted(names)


async def test_list_businesses_sort_by_rating(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    for i, rating in enumerate([3.0, 5.0, 4.0]):
        await businesses_service.upsert_from_place_result(
            db_session, make_place(place_id=f"rating_biz_{i}", name=f"Biz {i}", rating=rating), search_run.id
        )
    r = await client.get(f"{URL}?sort_by=rating")
    ratings = [b["rating"] for b in r.json()]
    assert ratings == sorted(ratings, reverse=True)
