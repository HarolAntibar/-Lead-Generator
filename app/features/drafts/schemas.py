from datetime import datetime

from pydantic import BaseModel, Field

from app.features.drafts.models import DraftChannel


class DraftRequest(BaseModel):
    channel: DraftChannel
    # Optional notes from the seller — e.g. "mention our free consultation offer".
    # Passed to the prompt as extra context but truncated inside prompts.py.
    extra_context: str | None = Field(default=None, max_length=500)


class DraftOut(BaseModel):
    id: int
    business_id: int
    channel: DraftChannel
    subject: str | None
    body: str
    model_used: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
