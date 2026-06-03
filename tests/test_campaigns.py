"""Phase 1 — Campaign and SearchRun API tests.

Covers: CRUD for campaigns, search run creation/listing, 404 and 422 error cases.
All tests run against the real database; clean_tables (autouse) truncates between tests.
"""
import pytest
from httpx import AsyncClient


URL = "/api/campaigns"


@pytest.fixture
async def campaign(client: AsyncClient) -> dict:
    """Creates a campaign and returns its JSON response."""
    body = {"name": "Pizzerias Madrid", "area_text": "Madrid", "business_type": "restaurante"}
    r = await client.post(URL, json=body)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# Campaign CRUD
# ---------------------------------------------------------------------------

async def test_create_campaign_returns_201_with_fields(client: AsyncClient) -> None:
    body = {"name": "Gyms BCN", "area_text": "Barcelona", "business_type": "gym"}
    r = await client.post(URL, json=body)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Gyms BCN"
    assert data["area_text"] == "Barcelona"
    assert data["business_type"] == "gym"
    assert data["params"] is None
    assert data["id"] > 0


async def test_create_campaign_with_location_bias_stores_params(client: AsyncClient) -> None:
    body = {
        "name": "Gyms Sevilla",
        "area_text": "Sevilla",
        "business_type": "gym",
        "location_bias": {"lat": 37.38, "lng": -5.99, "radius_meters": 3000.0},
    }
    r = await client.post(URL, json=body)
    assert r.status_code == 201
    params = r.json()["params"]
    assert params is not None
    assert params["location_bias"]["lat"] == 37.38
    assert params["location_bias"]["radius_meters"] == 3000.0


async def test_create_campaign_missing_required_fields_returns_422(client: AsyncClient) -> None:
    # Only name provided — area_text and business_type are required
    r = await client.post(URL, json={"name": "Incomplete"})
    assert r.status_code == 422


async def test_list_campaigns_empty_returns_empty_list(client: AsyncClient) -> None:
    r = await client.get(URL)
    assert r.status_code == 200
    assert r.json() == []


async def test_list_campaigns_returns_created_items(client: AsyncClient, campaign: dict) -> None:
    r = await client.get(URL)
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert campaign["id"] in ids


async def test_list_campaigns_multiple(client: AsyncClient) -> None:
    for i in range(3):
        await client.post(URL, json={"name": f"Camp {i}", "area_text": "Area", "business_type": "Type"})
    r = await client.get(URL)
    assert len(r.json()) == 3


async def test_get_campaign_by_id_returns_correct_name(client: AsyncClient, campaign: dict) -> None:
    r = await client.get(f"{URL}/{campaign['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == campaign["name"]


async def test_get_campaign_not_found_returns_404(client: AsyncClient) -> None:
    r = await client.get(f"{URL}/99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# SearchRun lifecycle
# ---------------------------------------------------------------------------

async def test_trigger_search_run_returns_202_with_pending_status(
    client: AsyncClient, campaign: dict
) -> None:
    r = await client.post(f"{URL}/{campaign['id']}/runs")
    assert r.status_code == 202
    data = r.json()
    assert data["campaign_id"] == campaign["id"]
    assert data["status"] == "pending"
    assert data["results_count"] == 0
    assert data["new_count"] == 0


async def test_trigger_run_for_unknown_campaign_returns_404(client: AsyncClient) -> None:
    r = await client.post(f"{URL}/99999/runs")
    assert r.status_code == 404


async def test_list_runs_for_campaign(client: AsyncClient, campaign: dict) -> None:
    await client.post(f"{URL}/{campaign['id']}/runs")
    await client.post(f"{URL}/{campaign['id']}/runs")
    r = await client.get(f"{URL}/{campaign['id']}/runs")
    assert r.status_code == 200
    assert len(r.json()) == 2


async def test_list_runs_empty_for_new_campaign(client: AsyncClient, campaign: dict) -> None:
    r = await client.get(f"{URL}/{campaign['id']}/runs")
    assert r.status_code == 200
    assert r.json() == []


async def test_get_run_by_id_returns_run(client: AsyncClient, campaign: dict) -> None:
    run = (await client.post(f"{URL}/{campaign['id']}/runs")).json()
    r = await client.get(f"{URL}/runs/{run['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == run["id"]
    assert r.json()["campaign_id"] == campaign["id"]


async def test_get_run_not_found_returns_404(client: AsyncClient) -> None:
    r = await client.get(f"{URL}/runs/99999")
    assert r.status_code == 404
