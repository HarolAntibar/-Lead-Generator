from enum import StrEnum

# Google Places API pricing — Advanced tier (includes phone, website fields)
# Source: https://developers.google.com/maps/documentation/places/web-service/usage-and-billing
GOOGLE_TEXT_SEARCH_COST_USD: float = 0.035


class OpportunityType(StrEnum):
    """Lead opportunity classification — determines which service to pitch and scoring weights.

    StrEnum means each member IS a str (e.g. OpportunityType.WEBSITE == "website"),
    so existing JSONB storage and string comparisons keep working without conversion.
    """
    WEBSITE    = "website"
    AUTOMATION = "automation"
    BOTH       = "both"
    LOW        = "low"
