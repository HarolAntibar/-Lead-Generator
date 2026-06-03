from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BusinessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    google_place_id: str
    name: str
    category: str | None
    phone_raw: str | None
    phone_e164: str | None
    address: str | None
    lat: float | None
    lng: float | None
    website_url: str | None
    has_website: bool
    rating: float | None
    reviews_count: int | None
    first_seen_run_id: int | None
    created_at: datetime
