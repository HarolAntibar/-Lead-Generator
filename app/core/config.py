from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str

    # Session security
    secret_key: str

    # Environment
    app_env: str = "development"
    debug: bool = False

    # Google Places API (Phase 1)
    google_places_api_key: str = ""

    # Gemini API (Phase 4)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    # Hard timeout on LLM API calls — prevents hanging the request if the provider
    # is slow or unresponsive. Frees the connection and returns an error to the user.
    llm_timeout_seconds: int = 30
    # Max draft requests per user per minute — protects against accidental loops
    # or abuse that would burn API quota.
    llm_rate_limit: str = "10/minute"

    # Pipeline safety limits (Phase 2)
    # Hard ceiling on businesses processed per run — prevents runaway Google API spend.
    max_places_per_run: int = 60
    # Seconds before the whole pipeline background task is cancelled and marked error.
    # Protects against runs stuck in "running" forever due to unexpected crashes.
    pipeline_run_timeout_seconds: int = 300

    # Scraping (Phase 3)
    # httpx-based scraper — no JS execution needed; HTML shell is enough to classify tech.
    scraper_timeout_seconds: int = 10
    # Hard cap on downloaded HTML to avoid pulling in huge files or PDFs.
    scraper_max_content_bytes: int = 512_000
    # Max redirects to follow (HTTP → HTTPS is standard for business sites).
    scraper_max_redirects: int = 5
    # Polite User-Agent so we're not mistaken for a bad actor.
    scraper_user_agent: str = (
        "Mozilla/5.0 (compatible; LeadBot/1.0; +https://example.com/bot)"
    )
    # Max parallel scrape tasks per pipeline run — keeps VPS load manageable.
    scraper_max_concurrency: int = 5

    # Lead scoring weights (Phase 2 — active; Phase 3 weights now also active)
    # Each weight is the maximum points that signal can contribute to the 0-100 score.
    score_weight_no_website: int = 35
    score_weight_rating: int = 25
    score_weight_no_automation: int = 15
    score_weight_outdated_site: int = 25

    # Thresholds for the rating signal
    score_rating_min_reviews: int = 20
    score_rating_good_threshold: float = 4.0

    # Threshold for the outdated-site signal (Phase 3).
    # quality_score is 0-100 from signals.py. Sites below this value are considered
    # poor/outdated and earn the full score_weight_outdated_site points.
    score_outdated_site_quality_threshold: int = 40

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
