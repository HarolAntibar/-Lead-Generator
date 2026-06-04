"""Phase 2 — Unit tests for the scoring engine (pipeline/scoring.py).

These are PURE unit tests: no database, no HTTP, no mocks needed.
We build Business objects directly in memory and assert on the ScoreResult.

This is the ideal test for a pure function — fast, isolated, and exhaustive.
"""
from app.core.config import Settings
from app.features.businesses.models import Business
from app.pipeline.scoring import SCORING_MODEL_VERSION, ScoreResult, compute_score


def _settings(**overrides) -> Settings:
    """Build a Settings object with test-friendly defaults + any overrides."""
    base = {
        "database_url": "postgresql+asyncpg://x:x@localhost/x",
        "secret_key": "test-secret",
        "score_weight_no_website": 35,
        "score_weight_rating": 25,
        "score_weight_no_automation": 15,
        "score_weight_outdated_site": 25,
        "score_rating_min_reviews": 20,
        "score_rating_good_threshold": 4.0,
    }
    base.update(overrides)
    return Settings(**base)


def _business(**fields) -> Business:
    """Build a minimal Business ORM object without touching the DB."""
    defaults = {
        "id": 1,
        "google_place_id": "test_place",
        "name": "Test Business",
        "has_website": True,
        "website_url": None,
        "rating": None,
        "reviews_count": None,
    }
    defaults.update(fields)
    b = Business()
    for k, v in defaults.items():
        setattr(b, k, v)
    return b


# ---------------------------------------------------------------------------
# Return type and structure
# ---------------------------------------------------------------------------

def test_compute_score_returns_score_result():
    result = compute_score(_business(has_website=False), _settings())
    assert isinstance(result, ScoreResult)
    assert isinstance(result.score, int)
    assert isinstance(result.breakdown, dict)
    assert result.model_version == SCORING_MODEL_VERSION


def test_breakdown_contains_all_components():
    result = compute_score(_business(), _settings())
    components = result.breakdown["components"]
    assert "no_website" in components
    assert "rating" in components
    assert "no_automation" in components
    assert "outdated_site" in components


# ---------------------------------------------------------------------------
# No-website signal
# ---------------------------------------------------------------------------

def test_no_website_awards_full_weight():
    s = _settings(score_weight_no_website=35)
    result = compute_score(_business(has_website=False), s)
    assert result.breakdown["components"]["no_website"]["points"] == 35


def test_has_website_awards_zero_for_no_website_signal():
    result = compute_score(_business(has_website=True), _settings())
    assert result.breakdown["components"]["no_website"]["points"] == 0


# ---------------------------------------------------------------------------
# Rating signal
# ---------------------------------------------------------------------------

def test_good_rating_with_enough_reviews_awards_full_weight():
    s = _settings(score_weight_rating=25, score_rating_min_reviews=20, score_rating_good_threshold=4.0)
    b = _business(has_website=True, rating=4.5, reviews_count=50)
    result = compute_score(b, s)
    assert result.breakdown["components"]["rating"]["points"] == 25


def test_below_threshold_rating_awards_partial_points():
    s = _settings(score_weight_rating=25, score_rating_min_reviews=20, score_rating_good_threshold=4.0)
    b = _business(has_website=True, rating=2.0, reviews_count=50)
    result = compute_score(b, s)
    pts = result.breakdown["components"]["rating"]["points"]
    assert 0 < pts < 25


def test_too_few_reviews_awards_zero_for_rating():
    s = _settings(score_rating_min_reviews=20)
    b = _business(has_website=True, rating=5.0, reviews_count=5)
    result = compute_score(b, s)
    assert result.breakdown["components"]["rating"]["points"] == 0


def test_no_rating_awards_zero():
    b = _business(has_website=True, rating=None, reviews_count=None)
    result = compute_score(b, _settings())
    assert result.breakdown["components"]["rating"]["points"] == 0


# ---------------------------------------------------------------------------
# Reserved signals (Phase 3)
# ---------------------------------------------------------------------------

def test_phase3_signals_are_zero():
    result = compute_score(_business(), _settings())
    assert result.breakdown["components"]["no_automation"]["points"] == 0
    assert result.breakdown["components"]["outdated_site"]["points"] == 0


# ---------------------------------------------------------------------------
# Score bounds and combinations
# ---------------------------------------------------------------------------

def test_score_is_capped_at_100_even_with_inflated_weights():
    s = _settings(score_weight_no_website=60, score_weight_rating=60)
    b = _business(has_website=False, rating=5.0, reviews_count=100)
    result = compute_score(b, s)
    assert result.score <= 100


def test_worst_case_score_is_zero():
    b = _business(has_website=True, rating=None, reviews_count=None)
    result = compute_score(b, _settings())
    assert result.score == 0


def test_best_phase2_score_equals_no_website_plus_full_rating():
    s = _settings(score_weight_no_website=35, score_weight_rating=25)
    b = _business(has_website=False, rating=5.0, reviews_count=100)
    result = compute_score(b, s)
    assert result.score == 60  # 35 + 25; Phase 3 signals are still 0


def test_score_respects_custom_weights_from_settings():
    s = _settings(score_weight_no_website=10, score_weight_rating=5)
    b = _business(has_website=False, rating=5.0, reviews_count=100)
    result = compute_score(b, s)
    assert result.score == 15
