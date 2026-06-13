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
    refresh_token_expire_days: int = 30

    game_starting_balance: int = 1500
    go_salary: int = 200
    jail_fine: int = 50

    telegram_client_id: str = ""
    telegram_client_secret: str = ""
    telegram_redirect_uri: str = ""
    telegram_issuer: str = "https://oauth.telegram.org"
    telegram_jwks_url: str = "https://oauth.telegram.org/.well-known/jwks.json"
    frontend_telegram_callback_url: str = "http://localhost:3000/auth/telegram/callback"
    frontend_telegram_connect_url: str = "http://localhost:3000/settings/telegram"

    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
