from fastapi import HTTPException, status


class LeadScoreNotFound(HTTPException):
    def __init__(self, business_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No lead score found for business_id={business_id}",
        )
