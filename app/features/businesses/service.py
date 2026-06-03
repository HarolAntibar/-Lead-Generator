from sqlalchemy.ext.asyncio import AsyncSession

from app.features.businesses import repository
from app.features.businesses.constants import BusinessSortBy
from app.features.businesses.exceptions import BusinessNotFoundError
from app.features.businesses.models import Business
from app.integrations.google.client import PlaceResult


async def upsert_from_place_result(
    session: AsyncSession,
    place: PlaceResult,
    run_id: int,
) -> tuple[Business, bool]:
    return await repository.upsert_business(session, place, run_id)


async def get_business_or_404(session: AsyncSession, business_id: int) -> Business:
    business = await repository.get_business_by_id(session, business_id)
    if not business:
        raise BusinessNotFoundError(business_id)
    return business


async def list_businesses(
    session: AsyncSession,
    offset: int,
    limit: int,
    sort_by: BusinessSortBy = BusinessSortBy.name,
    ref_lat: float | None = None,
    ref_lng: float | None = None,
) -> list[Business]:
    return await repository.list_businesses(session, offset, limit, sort_by, ref_lat, ref_lng)
