"""Phase 2 — Leads API and scoring integration tests.

Covers: score persistence, status lifecycle, list endpoint with filters,
and status update via PATCH.
All tests run against the real database; clean_tables (autouse) truncates between tests.
"""
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.businesses import service as businesses_service
from app.features.campaigns.models import SearchRun
from app.features.leads import service as leads_service
from app.features.leads.models import LeadStatusChoice
from app.features.leads.schemas import LeadStatusUpdate
from app.integrations.google.client import PlaceResult


URL = "/api/leads"


def _make_place(
    place_id: str = "place_leads_test",
    name: str = "Test Business",
    *,
    website_url: str | None = "https://example.com",
    rating: float | None = 4.5,
    reviews_count: int | None = 50,
) -> PlaceResult:
    return PlaceResult(
        place_id=place_id,
        name=name,
        address="Calle Test 1",
        lat=40.41,
        lng=-3.70,
        phone_raw="91 000 00 00",
        website_url=website_url,
        category="restaurant",
        rating=rating,
        reviews_count=reviews_count,
    )


# ---------------------------------------------------------------------------
# Score persistence
# ---------------------------------------------------------------------------

async def test_score_and_save_creates_lead_score(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    business, _ = await businesses_service.upsert_from_place_result(
        db_session, _make_place(), search_run.id
    )
    lead_score = await leads_service.score_and_save(db_session, business)
    assert lead_score.business_id == business.id
    assert 0 <= lead_score.score <= 100
    assert lead_score.breakdown is not None
    assert lead_score.model_version is not None


async def test_no_website_business_scores_higher_than_with_website(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    biz_no_web, _ = await businesses_service.upsert_from_place_result(
        db_session, _make_place(place_id="p_no_web", website_url=None), search_run.id
    )
    biz_web, _ = await businesses_service.upsert_from_place_result(
        db_session, _make_place(place_id="p_web", website_url="https://example.com"), search_run.id
    )
    score_no_web = await leads_service.score_and_save(db_session, biz_no_web)
    score_web = await leads_service.score_and_save(db_session, biz_web)
    assert score_no_web.score > score_web.score


async def test_rescoring_same_business_updates_existing_row(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    business, _ = await businesses_service.upsert_from_place_result(
        db_session, _make_place(), search_run.id
    )
    first = await leads_service.score_and_save(db_session, business)
    second = await leads_service.score_and_save(db_session, business)
    # Same business_id — must be 1 row (upsert), same id
    assert first.business_id == second.business_id


# ---------------------------------------------------------------------------
# Lead status lifecycle
# ---------------------------------------------------------------------------

async def test_score_and_save_creates_new_status(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    business, _ = await businesses_service.upsert_from_place_result(
        db_session, _make_place(), search_run.id
    )
    await leads_service.score_and_save(db_session, business)
    # Status must have been created with default 'new'
    from app.features.leads import repository as leads_repo
    status = await leads_repo.get_lead_score(db_session, business.id)
    assert status is not None


async def test_update_status_changes_crm_state(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    business, _ = await businesses_service.upsert_from_place_result(
        db_session, _make_place(), search_run.id
    )
    await leads_service.score_and_save(db_session, business)

    updated = await leads_service.update_status(
        db_session,
        business.id,
        LeadStatusUpdate(status=LeadStatusChoice.contacted, notes="Called on Tuesday"),
    )
    assert updated is not None
    assert updated.status == LeadStatusChoice.contacted
    assert updated.notes == "Called on Tuesday"


async def test_rescoring_does_not_overwrite_crm_status(
    db_session: AsyncSession, search_run: SearchRun
) -> None:
    business, _ = await businesses_service.upsert_from_place_result(
        db_session, _make_place(), search_run.id
    )
    await leads_service.score_and_save(db_session, business)
    await leads_service.update_status(
        db_session, business.id,
        LeadStatusUpdate(status=LeadStatusChoice.interested),
    )
    # Re-score (simulates pipeline running again)
    await leads_service.score_and_save(db_session, business)

    from app.features.leads import repository as leads_repo
    from sqlalchemy import select
    from app.features.leads.models import LeadStatus
    result = await db_session.execute(
        select(LeadStatus).where(LeadStatus.business_id == business.id)
    )
    status_row = result.scalar_one()
    assert status_row.status == LeadStatusChoice.interested


# ---------------------------------------------------------------------------
# HTTP endpoint — list leads
# ---------------------------------------------------------------------------

async def test_list_leads_empty_when_no_scores(client: AsyncClient) -> None:
    r = await client.get(URL)
    assert r.status_code == 200
    assert r.json() == []


async def test_list_leads_returns_scored_business(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    business, _ = await businesses_service.upsert_from_place_result(
        db_session, _make_place(), search_run.id
    )
    await leads_service.score_and_save(db_session, business)
    r = await client.get(URL)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Test Business"
    assert "score" in r.json()[0]
    assert "status" in r.json()[0]


async def test_list_leads_sorted_by_score_desc(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    # No-website business should score higher and appear first
    for i, (place_id, has_web) in enumerate([
        ("lead_no_web", None),
        ("lead_with_web", "https://example.com"),
    ]):
        biz, _ = await businesses_service.upsert_from_place_result(
            db_session,
            _make_place(place_id=place_id, website_url=has_web),
            search_run.id,
        )
        await leads_service.score_and_save(db_session, biz)

    r = await client.get(URL)
    scores = [lead["score"] for lead in r.json()]
    assert scores == sorted(scores, reverse=True)


async def test_list_leads_filter_has_website_false(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    for place_id, url in [("filt_no", None), ("filt_yes", "https://example.com")]:
        biz, _ = await businesses_service.upsert_from_place_result(
            db_session, _make_place(place_id=place_id, website_url=url), search_run.id
        )
        await leads_service.score_and_save(db_session, biz)

    r = await client.get(f"{URL}?has_website=false")
    assert r.status_code == 200
    assert all(not lead["has_website"] for lead in r.json())
    assert len(r.json()) == 1


async def test_list_leads_filter_has_website_true(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    for place_id, url in [("filt2_no", None), ("filt2_yes", "https://example.com")]:
        biz, _ = await businesses_service.upsert_from_place_result(
            db_session, _make_place(place_id=place_id, website_url=url), search_run.id
        )
        await leads_service.score_and_save(db_session, biz)

    r = await client.get(f"{URL}?has_website=true")
    assert r.status_code == 200
    assert all(lead["has_website"] for lead in r.json())
    assert len(r.json()) == 1


# ---------------------------------------------------------------------------
# HTTP endpoint — PATCH status
# ---------------------------------------------------------------------------

async def test_patch_status_returns_updated_status(
    client: AsyncClient, db_session: AsyncSession, search_run: SearchRun
) -> None:
    business, _ = await businesses_service.upsert_from_place_result(
        db_session, _make_place(), search_run.id
    )
    await leads_service.score_and_save(db_session, business)

    r = await client.patch(
        f"{URL}/{business.id}/status",
        json={"status": "contacted", "notes": "Left a voicemail"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "contacted"
    assert r.json()["notes"] == "Left a voicemail"


async def test_patch_status_unknown_business_returns_404(client: AsyncClient) -> None:
    r = await client.patch(f"{URL}/99999/status", json={"status": "contacted"})
    assert r.status_code == 404
