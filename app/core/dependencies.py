from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(20, ge=1, le=100, description="Results per page"),
    ) -> None:
        self.page = page
        self.size = size
        self.offset = (page - 1) * size


PaginationDep = Annotated[PaginationParams, Depends(PaginationParams)]
