from fastapi import APIRouter, Query

from app.core.dependencies import PaginationDep, SessionDep
from app.features.businesses import service
from app.features.businesses.constants import BusinessSortBy
from app.features.businesses.dependencies import BusinessDep
from app.features.businesses.schemas import BusinessRead

router = APIRouter(prefix="/api/businesses", tags=["businesses"])


@router.get("", response_model=list[BusinessRead])
async def list_businesses(
    session: SessionDep,
    pagination: PaginationDep,
    sort_by: BusinessSortBy = Query(BusinessSortBy.name),
    ref_lat: float | None = Query(None, description="Reference latitude for distance sort"),
    ref_lng: float | None = Query(None, description="Reference longitude for distance sort"),
) -> list[BusinessRead]:
    businesses = await service.list_businesses(
        session=session,
        offset=pagination.offset,
        limit=pagination.size,
        sort_by=sort_by,
        ref_lat=ref_lat,
        ref_lng=ref_lng,
    )
    return [BusinessRead.model_validate(b) for b in businesses]


@router.get("/{business_id}", response_model=BusinessRead)
async def get_business(business: BusinessDep) -> BusinessRead:
    return BusinessRead.model_validate(business)
