"""Application configuration and environment settings."""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment or .env file."""
    BEACON_SECRET_KEY: str = "dev_beacon_secret_key_default_minimum_32_characters_long"
    ADMIN_SECRET_TOKEN: str = "dev_admin_secret_token_12345"
    CHALLENGE_TIMEOUT_SECONDS: float = 3.0
    RATE_LIMIT_CHALLENGE: str = "12/minute"
    RATE_LIMIT_DISPATCH: str = "6/minute"
    MAX_BODY_SIZE_BYTES: int = 16384  # 16 KB strict body limit
    MAX_STORED_DISPATCHES: int = 5000
    DISCORD_WEBHOOK_URL: Optional[str] = None
    DATABASE_URL: str = "sqlite:///./beacon.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
