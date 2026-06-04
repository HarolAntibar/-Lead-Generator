from fastapi import Query


def leads_pagination(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> tuple[int, int]:
    return page, size
