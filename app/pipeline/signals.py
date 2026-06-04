"""Opportunity signals — detects sales gaps from raw HTML.

Single responsibility: given raw HTML, return a SignalResult with boolean flags
and a quality score. Does NOT touch the DB or make HTTP calls.

Signals detected:
  has_chat     — live chat widget (Intercom, Tidio, Crisp, Tawk, WhatsApp float)
  has_booking  — online booking system (Calendly, Acuity, Booksy, generic)
  freshness    — rough estimate of how recently the site was updated
  quality_score — 0-100 heuristic for overall site quality

These signals feed two scoring components in scoring.py:
  - no_automation  (has_chat=False AND has_booking=False)
  - outdated_site  (freshness = "old" AND quality_score < threshold)
"""
import re
from dataclasses import dataclass


@dataclass
class SignalResult:
    has_chat: bool
    has_booking: bool
    freshness_signal: str   # "recent" | "moderate" | "old" | "unknown"
    quality_score: int      # 0-100
    raw_signals: dict


# ---------------------------------------------------------------------------
# Pattern tables
# ---------------------------------------------------------------------------

_CHAT_PATTERNS = [
    "intercom",
    "tawk.to",
    "tidio",
    "crisp.chat",
    "freshchat",
    "livechat",
    "olark",
    "drift.com",
    "zopim",
    "zendesk",
    "wa.me",               # WhatsApp floating button
    "api.whatsapp.com",
    "widget.tidio",
]

_BOOKING_PATTERNS = [
    "calendly.com",
    "acuityscheduling.com",
    "booksy.com",
    "simplybook.me",
    "setmore.com",
    "square.site",
    "fresha.com",
    "vagaro.com",
    "mindbodyonline.com",
    "reservio.com",
    "book-now",
    "book_now",
    "online-booking",
    "online_booking",
    "make-appointment",
    "schedule-appointment",
]

# Copyright years in footer — rough proxy for last update year.
_YEAR_PATTERN = re.compile(r"20(1[5-9]|2[0-9])")


def _detect_chat(html: str) -> bool:
    html_lower = html.lower()
    return any(p in html_lower for p in _CHAT_PATTERNS)


def _detect_booking(html: str) -> bool:
    html_lower = html.lower()
    return any(p in html_lower for p in _BOOKING_PATTERNS)


def _detect_freshness(html: str) -> tuple[str, int | None]:
    """Return (freshness_label, most_recent_year_found)."""
    years = [int(m.group()) for m in _YEAR_PATTERN.finditer(html)]
    if not years:
        return "unknown", None

    latest = max(years)
    if latest >= 2023:
        return "recent", latest
    if latest >= 2020:
        return "moderate", latest
    return "old", latest


def _quality_score(html: str, has_chat: bool, has_booking: bool, freshness: str) -> int:
    """Heuristic quality score 0-100 based on presence of modern site features."""
    score = 0

    # HTTPS is checked in tech_detect; assume it's in tech_stack by here.
    # We give points for content richness signals.
    if len(html) > 10_000:
        score += 15     # not a near-empty placeholder page
    if len(html) > 40_000:
        score += 10     # reasonably sized page

    if has_chat:
        score += 20
    if has_booking:
        score += 20

    if freshness == "recent":
        score += 25
    elif freshness == "moderate":
        score += 10

    # Presence of structured markup (schema.org) signals professional setup.
    if "schema.org" in html or "application/ld+json" in html:
        score += 10

    return min(score, 100)


def analyze(html: str) -> SignalResult:
    """Extract opportunity signals from raw *html*."""
    has_chat = _detect_chat(html)
    has_booking = _detect_booking(html)
    freshness, latest_year = _detect_freshness(html)
    quality = _quality_score(html, has_chat, has_booking, freshness)

    raw_signals = {
        "has_chat": has_chat,
        "has_booking": has_booking,
        "freshness": freshness,
        "latest_year_found": latest_year,
        "quality_score": quality,
    }

    return SignalResult(
        has_chat=has_chat,
        has_booking=has_booking,
        freshness_signal=freshness,
        quality_score=quality,
        raw_signals=raw_signals,
    )
