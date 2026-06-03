import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.businesses import service as businesses_service
from app.features.campaigns.models import Campaign
from app.integrations.google.client import GooglePlacesClient, LocationBias
from app.integrations.google.constants import DEFAULT_LOCATION_BIAS_RADIUS_METERS

logger = logging.getLogger(__name__)


async def run(
    session: AsyncSession,
    campaign: Campaign,
    run_id: int,
) -> tuple[int, int]:
    query = f"{campaign.business_type} in {campaign.area_text}"

    location_bias: LocationBias | None = None
    if campaign.params and "location_bias" in campaign.params:
        lb = campaign.params["location_bias"]
        location_bias = LocationBias(
            lat=lb["lat"],
            lng=lb["lng"],
            radius_meters=lb.get("radius_meters", DEFAULT_LOCATION_BIAS_RADIUS_METERS),
        )

    logger.info("Places stage: querying '%s'", query)
    client = GooglePlacesClient()
    places = await client.search_places(query, location_bias)

    results_count = len(places)
    new_count = 0

    for place in places:
        _, is_new = await businesses_service.upsert_from_place_result(session, place, run_id)
        if is_new:
            new_count += 1

    logger.info(
        "Places stage done: %d results, %d new (run_id=%d)",
        results_count,
        new_count,
        run_id,
    )
    return results_count, new_count
