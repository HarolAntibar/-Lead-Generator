import enum

from sqlalchemy import Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class LeadStatusChoice(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    interested = "interested"
    discarded = "discarded"
    client = "client"


class LeadScore(TimestampMixin, Base):
    __tablename__ = "lead_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_version: Mapped[str | None] = mapped_column(nullable=True)
    computed_at: Mapped[str | None] = mapped_column(nullable=True)


class LeadStatus(TimestampMixin, Base):
    __tablename__ = "lead_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    status: Mapped[LeadStatusChoice] = mapped_column(Enum(LeadStatusChoice), nullable=False, default=LeadStatusChoice.new)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
