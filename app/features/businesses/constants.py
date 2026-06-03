import enum

BUSINESS_RESOURCE_NAME = "Business"


class BusinessSortBy(str, enum.Enum):
    name = "name"
    rating = "rating"
    distance = "distance"
