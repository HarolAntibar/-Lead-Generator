import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.integrations.google.constants import (
    DEFAULT_LOCATION_BIAS_RADIUS_METERS,
    MAX_RESULTS_PER_PAGE,
    REQUEST_TIMEOUT_SECONDS,
    TEXT_SEARCH_ENDPOINT,
    TEXT_SEARCH_FIELD_MASK,
)

logger = logging.getLogger(__name__)


@dataclass
class LocationBias:
    lat: float
    lng: float
    radius_meters: float = DEFAULT_LOCATION_BIAS_RADIUS_METERS


@dataclass
class PlaceResult:
    place_id: str
    name: str
    address: str | None
    lat: float | None
    lng: float | None
    phone_raw: str | None
    website_url: str | None
    category: str | None
    rating: float | None
    reviews_count: int | None


class GooglePlacesClient:
    def __init__(self) -> None:
        self._api_key = get_settings().google_places_api_key

    async def search_places(
        self,
        query: str,
        location_bias: LocationBias | None = None,
    ) -> list[PlaceResult]:
        payload: dict = {
            "textQuery": query,
            "maxResultCount": MAX_RESULTS_PER_PAGE,
        }

        if location_bias:
            payload["locationBias"] = {
                "circle": {
                    "center": {
                        "latitude": location_bias.lat,
                        "longitude": location_bias.lng,
                    },
                    "radius": location_bias.radius_meters,
                }
            }

        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": TEXT_SEARCH_FIELD_MASK,
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.post(
                    TEXT_SEARCH_ENDPOINT,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Google Places API error %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise ExternalServiceError("Google Places", exc.response.text) from exc
        except httpx.RequestError as exc:
            logger.error("Google Places request failed: %s", exc)
            raise ExternalServiceError("Google Places", str(exc)) from exc

        places = response.json().get("places", [])
        logger.info("Google Places returned %d results for query: %s", len(places), query)
        return [self._parse_place(p) for p in places]

    def _parse_place(self, raw: dict) -> PlaceResult:
        location = raw.get("location", {})
        return PlaceResult(
            place_id=raw["id"],
            name=raw.get("displayName", {}).get("text", ""),
            address=raw.get("formattedAddress"),
            lat=location.get("latitude"),
            lng=location.get("longitude"),
            phone_raw=raw.get("nationalPhoneNumber"),
            website_url=raw.get("websiteUri"),
            category=raw.get("primaryType"),
            rating=raw.get("rating"),
            reviews_count=raw.get("userRatingCount"),
        )
