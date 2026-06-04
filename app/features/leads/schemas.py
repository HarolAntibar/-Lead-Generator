from datetime import datetime

from pydantic import BaseModel

from app.features.leads.models import LeadStatusChoice


class LeadScoreOut(BaseModel):
    business_id: int
    score: int
    breakdown: dict | None
    model_version: str | None
    computed_at: datetime | None

    model_config = {"from_attributes": True}


class LeadStatusOut(BaseModel):
    business_id: int
    status: LeadStatusChoice
    assigned_to: int | None
    notes: str | None

    model_config = {"from_attributes": True}


class LeadStatusUpdate(BaseModel):
    status: LeadStatusChoice
    notes: str | None = None
    assigned_to: int | None = None  # only applied if explicitly included in the request


class LeadOut(BaseModel):
    """Combined view: business essentials + score + CRM status."""
    business_id: int
    name: str
    category: str | None
    has_website: bool
    website_url: str | None
    rating: float | None
    reviews_count: int | None
    score: int
    breakdown: dict | None
    opportunity_type: str | None
    status: LeadStatusChoice
    computed_at: datetime | None
