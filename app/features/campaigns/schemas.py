from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.features.campaigns.models import SearchRunStatus


class LocationBiasSchema(BaseModel):
    lat: float
    lng: float
    radius_meters: float = Field(5000.0, gt=0)


class CampaignCreate(BaseModel):
    name: str = Field(..., max_length=255)
    area_text: str = Field(..., max_length=500)
    business_type: str = Field(..., max_length=255)
    location_bias: LocationBiasSchema | None = None


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    area_text: str
    business_type: str
    params: dict | None
    created_by: int | None
    created_at: datetime


class SearchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    status: SearchRunStatus
    results_count: int
    new_count: int
    api_cost_est: float | None
    error: str | None
    started_at: str | None
    finished_at: str | None
    created_at: datetime
