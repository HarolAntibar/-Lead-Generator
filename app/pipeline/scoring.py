"""Lead viability scoring — pure function, no DB or HTTP side effects.

Scoring model v1 (Phase 2 — Places data only):
  - No website:        up to SCORE_WEIGHT_NO_WEBSITE pts
  - Good rating:       up to SCORE_WEIGHT_RATING pts
  - No automation:     reserved for Phase 3 (scraping)
  - Outdated website:  reserved for Phase 3 (scraping)

The breakdown dict stored in lead_scores.breakdown explains every component
so salespeople and future-you can understand why a lead got its score.
"""
from dataclasses import dataclass

from app.core.config import Settings
from app.features.businesses.models import Business

SCORING_MODEL_VERSION = "v1-places-only"


@dataclass(frozen=True)
class ScoreResult:
    score: int
    breakdown: dict
    model_version: str


def compute_score(business: Business, settings: Settings) -> ScoreResult:
    """Return a ScoreResult for *business* using the weights in *settings*.

    The function is intentionally stateless: it reads from the ORM object
    (already loaded by the caller) and returns a plain dataclass.  No DB
    writes happen here — that is the responsibility of the leads service.
    """
    components: dict[str, dict] = {}
    total = 0

    # --- Signal 1: no website --------------------------------------------------
    # A business without a website is the clearest opportunity: we can sell them
    # one.  Full weight awarded as a binary flag.
    no_website_pts = settings.score_weight_no_website if not business.has_website else 0
    components["no_website"] = {
        "points": no_website_pts,
        "max": settings.score_weight_no_website,
        "reason": "no website found" if not business.has_website else "has website",
    }
    total += no_website_pts

    # --- Signal 2: rating / review volume --------------------------------------
    # High rating + enough reviews signals: the business is active, trusted, and
    # probably has budget.  We ignore rating when reviews_count is too low because
    # a 5.0 from 3 friends is not meaningful.
    rating_pts, rating_reason = _rating_points(business, settings)
    components["rating"] = {
        "points": rating_pts,
        "max": settings.score_weight_rating,
        "reason": rating_reason,
    }
    total += rating_pts

    # --- Signals 3 & 4: reserved for Phase 3 (scraping) -----------------------
    components["no_automation"] = {
        "points": 0,
        "max": settings.score_weight_no_automation,
        "reason": "not yet evaluated (requires scraping)",
    }
    components["outdated_site"] = {
        "points": 0,
        "max": settings.score_weight_outdated_site,
        "reason": "not yet evaluated (requires scraping)",
    }

    # Cap at 100 as a safety net in case weights are misconfigured via .env.
    final_score = min(total, 100)

    breakdown = {
        "components": components,
        "raw_total": total,
        "final_score": final_score,
    }
    return ScoreResult(score=final_score, breakdown=breakdown, model_version=SCORING_MODEL_VERSION)


def _rating_points(business: Business, settings: Settings) -> tuple[int, str]:
    """Calculate rating signal points and a human-readable reason string."""
    if business.rating is None:
        return 0, "no rating available"

    reviews = business.reviews_count or 0
    if reviews < settings.score_rating_min_reviews:
        return 0, f"too few reviews ({reviews} < {settings.score_rating_min_reviews})"

    rating = float(business.rating)
    if rating >= settings.score_rating_good_threshold:
        return settings.score_weight_rating, f"good rating {rating} with {reviews} reviews"

    # Partial credit: scale linearly between 0 and the threshold.
    # e.g. threshold=4.0, rating=3.0 -> 3/4 * weight = 75 % of max points.
    ratio = rating / settings.score_rating_good_threshold
    pts = int(settings.score_weight_rating * ratio)
    return pts, f"below-threshold rating {rating} with {reviews} reviews (partial {pts} pts)"
