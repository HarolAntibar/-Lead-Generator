from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.businesses.constants import BusinessSortBy
from app.features.businesses.models import Business, Contact, WebsiteAnalysis
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


async def get_businesses_for_run(session: AsyncSession, run_id: int) -> list[Business]:
    """Return all businesses that were first seen in *run_id*.

    Used by the pipeline orchestrator to score only the businesses discovered
    in the current run — avoids re-scoring everything on every run.
    """
    result = await session.execute(
        select(Business).where(Business.first_seen_run_id == run_id)
    )
    return list(result.scalars().all())


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


async def save_website_analysis(
    session: AsyncSession,
    *,
    business_id: int,
    reachable: bool,
    cms_detected: str | None,
    tech_stack: dict | None,
    has_chat: bool,
    has_booking: bool,
    freshness_signal: str | None,
    quality_score: int | None,
    raw_signals: dict | None,
    analyzed_at: str,
) -> WebsiteAnalysis:
    """Upsert a WebsiteAnalysis row (one per business, UNIQUE on business_id).

    ON CONFLICT DO UPDATE so re-running a campaign refreshes the analysis instead
    of leaving stale data or raising a duplicate-key error.
    """
    stmt = (
        insert(WebsiteAnalysis)
        .values(
            business_id=business_id,
            reachable=reachable,
            cms_detected=cms_detected,
            tech_stack=tech_stack,
            has_chat=has_chat,
            has_booking=has_booking,
            freshness_signal=freshness_signal,
            quality_score=quality_score,
            raw_signals=raw_signals,
            analyzed_at=analyzed_at,
        )
        .on_conflict_do_update(
            index_elements=["business_id"],
            set_={
                "reachable": reachable,
                "cms_detected": cms_detected,
                "tech_stack": tech_stack,
                "has_chat": has_chat,
                "has_booking": has_booking,
                "freshness_signal": freshness_signal,
                "quality_score": quality_score,
                "raw_signals": raw_signals,
                "analyzed_at": analyzed_at,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()

    row = await session.execute(
        select(WebsiteAnalysis).where(WebsiteAnalysis.business_id == business_id)
    )
    return row.scalar_one()


async def get_website_analysis(
    session: AsyncSession,
    business_id: int,
) -> WebsiteAnalysis | None:
    result = await session.execute(
        select(WebsiteAnalysis).where(WebsiteAnalysis.business_id == business_id)
    )
    return result.scalar_one_or_none()


async def save_contacts(
    session: AsyncSession,
    business_id: int,
    contacts: list[dict],
) -> None:
    """Insert extracted contacts for a business.

    Every contact is stored with is_personal_data=True (GDPR compliance — the source
    field records where the data was found so it can be audited or deleted on request).
    Contacts are always re-inserted fresh; dedup within a run is handled upstream by
    the extract stage returning a deduplicated list.
    """
    for data in contacts:
        session.add(Contact(
            business_id=business_id,
            email=data.get("email"),
            name=data.get("name"),
            role=data.get("role"),
            source=data.get("source"),
            confidence=data.get("confidence"),
            is_personal_data=True,
        ))
    await session.commit()
