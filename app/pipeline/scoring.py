"""Lead viability scoring — pure function, no DB or HTTP side effects.

Scoring model v2 (Phase 3 — all four signals active):
  - No website:       up to SCORE_WEIGHT_NO_WEBSITE pts     → opportunity type "website"
  - Good rating:      up to SCORE_WEIGHT_RATING pts          → all types
  - No automation:    up to SCORE_WEIGHT_NO_AUTOMATION pts   → "automation" and "both" only
  - Outdated website: up to SCORE_WEIGHT_OUTDATED_SITE pts   → "website" and "both" only

opportunity_type is derived here from tech detection + automation signals:
  "website"    → no website, or legacy CMS that already has some automation
  "automation" → modern framework (React/Next/Vue/Angular) without full automation
  "both"       → legacy CMS + missing chat/booking (sell redesign + automation)
  "low"        → modern framework + already has chat AND booking (deprioritise)

The breakdown dict stored in lead_scores.breakdown records every component
so salespeople can understand why a lead got its score.
"""
from dataclasses import dataclass

from app.core.config import Settings
from app.features.businesses.models import Business, WebsiteAnalysis

SCORING_MODEL_VERSION = "v2-scraping"


@dataclass(frozen=True)
class ScoreResult:
    score: int
    breakdown: dict
    model_version: str


def _compute_opportunity_type(business: Business, analysis: WebsiteAnalysis | None) -> str:
    """Derive the final opportunity type from tech detection + automation signals.

    tech_detect.py stores an initial opportunity_type ("website" or "automation")
    inside the tech_stack JSONB. This function refines it using the automation
    signals (has_chat, has_booking) that signals.py detected.
    """
    if not business.has_website or analysis is None:
        return "website"

    tech_type = (analysis.tech_stack or {}).get("opportunity_type", "website")

    if tech_type == "automation":
        # Modern framework — already well-equipped if it has both chat AND booking.
        if analysis.has_chat and analysis.has_booking:
            return "low"
        return "automation"

    # Legacy CMS or unknown stack — check if automation features are missing.
    has_automation = analysis.has_chat or analysis.has_booking
    if not has_automation:
        return "both"   # sell redesign + automation package
    return "website"    # has some automation already, needs site improvement only


def compute_score(
    business: Business,
    settings: Settings,
    analysis: WebsiteAnalysis | None = None,
) -> ScoreResult:
    """Return a ScoreResult for *business* using the weights in *settings*.

    Intentionally stateless: reads ORM objects already loaded by the caller
    and returns a plain dataclass. No DB writes happen here — that is the
    leads service's responsibility.

    *analysis* is None for businesses without a website; signals 3 and 4 are
    skipped automatically in that case.
    """
    opportunity_type = _compute_opportunity_type(business, analysis)
    components: dict[str, dict] = {}
    total = 0

    # --- Signal 1: no website --------------------------------------------------
    no_website_pts = settings.score_weight_no_website if not business.has_website else 0
    components["no_website"] = {
        "points": no_website_pts,
        "max": settings.score_weight_no_website,
        "reason": "no website found" if not business.has_website else "has website",
    }
    total += no_website_pts

    # --- Signal 2: rating / review volume (applies to all types) ---------------
    rating_pts, rating_reason = _rating_points(business, settings)
    components["rating"] = {
        "points": rating_pts,
        "max": settings.score_weight_rating,
        "reason": rating_reason,
    }
    total += rating_pts

    # --- Signal 3: no automation (applies to "automation" and "both") ----------
    no_auto_pts, no_auto_reason = _no_automation_points(analysis, opportunity_type, settings)
    components["no_automation"] = {
        "points": no_auto_pts,
        "max": settings.score_weight_no_automation,
        "reason": no_auto_reason,
    }
    total += no_auto_pts

    # --- Signal 4: outdated/poor site (applies to "website" and "both") --------
    outdated_pts, outdated_reason = _outdated_site_points(analysis, opportunity_type, settings)
    components["outdated_site"] = {
        "points": outdated_pts,
        "max": settings.score_weight_outdated_site,
        "reason": outdated_reason,
    }
    total += outdated_pts

    # Cap at 100 as a safety net in case weights are misconfigured via .env.
    final_score = min(total, 100)

    breakdown = {
        "opportunity_type": opportunity_type,
        "components": components,
        "raw_total": total,
        "final_score": final_score,
    }
    return ScoreResult(score=final_score, breakdown=breakdown, model_version=SCORING_MODEL_VERSION)


# ---------------------------------------------------------------------------
# Signal helpers — each returns (points, human-readable reason)
# ---------------------------------------------------------------------------

def _rating_points(business: Business, settings: Settings) -> tuple[int, str]:
    if business.rating is None:
        return 0, "no rating available"

    reviews = business.reviews_count or 0
    if reviews < settings.score_rating_min_reviews:
        return 0, f"too few reviews ({reviews} < {settings.score_rating_min_reviews})"

    rating = float(business.rating)
    if rating >= settings.score_rating_good_threshold:
        return settings.score_weight_rating, f"good rating {rating} with {reviews} reviews"

    # Partial credit: scale linearly below the threshold.
    ratio = rating / settings.score_rating_good_threshold
    pts = int(settings.score_weight_rating * ratio)
    return pts, f"below-threshold rating {rating} with {reviews} reviews (partial {pts} pts)"


def _no_automation_points(
    analysis: WebsiteAnalysis | None,
    opportunity_type: str,
    settings: Settings,
) -> tuple[int, str]:
    if opportunity_type not in ("automation", "both"):
        return 0, "not applicable for this opportunity type"
    if analysis is None:
        return 0, "not yet evaluated (requires scraping)"

    has_automation = analysis.has_chat or analysis.has_booking
    if has_automation:
        features = []
        if analysis.has_chat:
            features.append("chat")
        if analysis.has_booking:
            features.append("booking")
        return 0, f"already has automation: {', '.join(features)}"

    return settings.score_weight_no_automation, "no chat or booking detected"


def _outdated_site_points(
    analysis: WebsiteAnalysis | None,
    opportunity_type: str,
    settings: Settings,
) -> tuple[int, str]:
    if opportunity_type not in ("website", "both"):
        return 0, "not applicable for this opportunity type"
    if analysis is None:
        return 0, "not yet evaluated (requires scraping)"
    if not analysis.reachable:
        return 0, "site was not reachable — cannot assess quality"

    quality = analysis.quality_score or 0
    freshness = analysis.freshness_signal or "unknown"
    is_outdated = (
        freshness in ("old", "unknown")
        or quality < settings.score_outdated_site_quality_threshold
    )

    if is_outdated:
        return (
            settings.score_weight_outdated_site,
            f"outdated site: freshness={freshness}, quality_score={quality}",
        )
    return 0, f"site appears acceptable: freshness={freshness}, quality_score={quality}"
