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

    # Lead scoring weights (Phase 2)
    # Each weight is the maximum points that signal can contribute to the 0-100 score.
    score_weight_no_website: int = 35
    score_weight_rating: int = 25
    score_weight_no_automation: int = 15   # reserved for Phase 3 (scraping)
    score_weight_outdated_site: int = 25   # reserved for Phase 3 (scraping)

    # Thresholds for the rating signal
    score_rating_min_reviews: int = 20     # ignore rating if fewer reviews than this
    score_rating_good_threshold: float = 4.0

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
