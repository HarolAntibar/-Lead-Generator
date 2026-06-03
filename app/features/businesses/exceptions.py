from app.core.exceptions import NotFoundError
from app.features.businesses.constants import BUSINESS_RESOURCE_NAME


class BusinessNotFoundError(NotFoundError):
    def __init__(self, business_id: int) -> None:
        super().__init__(BUSINESS_RESOURCE_NAME, business_id)
