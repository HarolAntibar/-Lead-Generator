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

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
