from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_cors_origins(value: str | list[str]) -> list[str]:
    if isinstance(value, str):
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    mongodb_uri: str = "mongodb://mongodb:27017"
    mongodb_db: str = "monopoly"
    redis_url: str = "redis://redis:6379/0"
    cors_origins: Annotated[
        list[str],
        NoDecode,
        BeforeValidator(_parse_cors_origins),
    ] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
