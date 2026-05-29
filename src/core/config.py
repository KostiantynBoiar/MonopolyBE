from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # Comma-separated in .env (e.g. http://localhost:3000,http://127.0.0.1:3000).
    # Stored as str so pydantic-settings does not JSON-decode the env value.
    cors_origins: str = "http://localhost:3000"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    game_starting_balance: int = 1500
    go_salary: int = 200
    jail_fine: int = 50

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
