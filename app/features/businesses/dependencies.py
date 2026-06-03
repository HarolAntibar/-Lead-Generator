from typing import Annotated

from fastapi import Depends

from app.core.dependencies import SessionDep
from app.features.businesses import service
from app.features.businesses.models import Business


async def _get_business(business_id: int, session: SessionDep) -> Business:
    return await service.get_business_or_404(session, business_id)


BusinessDep = Annotated[Business, Depends(_get_business)]
