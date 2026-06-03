BASE_URL = "https://places.googleapis.com/v1"
TEXT_SEARCH_ENDPOINT = f"{BASE_URL}/places:searchText"

# Only request the fields we actually store — every extra field increases API cost.
# Tier reference: https://developers.google.com/maps/documentation/places/web-service/usage-and-billing
# Basic tier: id, displayName, formattedAddress, location, primaryType
# Advanced tier: nationalPhoneNumber, websiteUri, rating, userRatingCount
TEXT_SEARCH_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.primaryType",
])

MAX_RESULTS_PER_PAGE = 20
REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_LOCATION_BIAS_RADIUS_METERS = 5000.0
