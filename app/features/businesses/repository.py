from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.businesses.constants import BusinessSortBy
from app.features.businesses.models import Business
from app.integrations.google.client import PlaceResult


async def upsert_business(
    session: AsyncSession,
    place: PlaceResult,
    run_id: int,
) -> tuple[Business, bool]:
    stmt = (
        insert(Business)
        .values(
            google_place_id=place.place_id,
            name=place.name,
            address=place.address,
            lat=place.lat,
            lng=place.lng,
            phone_raw=place.phone_raw,
            website_url=place.website_url,
            has_website=place.website_url is not None,
            category=place.category,
            rating=place.rating,
            reviews_count=place.reviews_count,
            first_seen_run_id=run_id,
        )
        .on_conflict_do_nothing(index_elements=["google_place_id"])
    )
    result = await session.execute(stmt)
    await session.commit()

    is_new = result.rowcount > 0

    existing = await session.execute(
        select(Business).where(Business.google_place_id == place.place_id)
    )
    return existing.scalar_one(), is_new


async def get_business_by_id(session: AsyncSession, business_id: int) -> Business | None:
    result = await session.execute(
        select(Business).where(Business.id == business_id)
    )
    return result.scalar_one_or_none()


async def list_businesses(
    session: AsyncSession,
    offset: int,
    limit: int,
    sort_by: BusinessSortBy = BusinessSortBy.name,
    ref_lat: float | None = None,
    ref_lng: float | None = None,
) -> list[Business]:
    stmt = select(Business)

    if sort_by == BusinessSortBy.rating:
        stmt = stmt.order_by(Business.rating.desc().nullslast())
    elif sort_by == BusinessSortBy.distance and ref_lat is not None and ref_lng is not None:
        # Euclidean distance on coordinates — accurate enough for sorting within a region
        distance = func.sqrt(
            func.power(Business.lat - ref_lat, 2)
            + func.power(Business.lng - ref_lng, 2)
        )
        stmt = stmt.order_by(distance.asc().nullslast())
    else:
        stmt = stmt.order_by(Business.name.asc())

    result = await session.execute(stmt.offset(offset).limit(limit))
    return list(result.scalars().all())
