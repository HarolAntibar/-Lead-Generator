import enum

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class ContactSource(str, enum.Enum):
    website_email = "website_email"
    website_contact_page = "website_contact_page"
    website_about_page = "website_about_page"
    website_footer = "website_footer"


class Business(TimestampMixin, Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_place_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Phone (from Google Places)
    phone_raw: Mapped[str | None] = mapped_column(String(50), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Location (from Google Places)
    address: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Website
    website_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    has_website: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Google Maps rating
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True)
    reviews_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    first_seen_run_id: Mapped[int | None] = mapped_column(ForeignKey("search_runs.id", ondelete="SET NULL"), nullable=True)


class WebsiteAnalysis(TimestampMixin, Base):
    __tablename__ = "website_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    reachable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cms_detected: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tech_stack: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    has_chat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_booking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    freshness_signal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    analyzed_at: Mapped[str | None] = mapped_column(nullable=True)


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[ContactSource | None] = mapped_column(Enum(ContactSource), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_personal_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
