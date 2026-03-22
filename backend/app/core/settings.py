from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    app_name: str = "Reader System"
    app_base_url: str = "http://localhost:8000"
    web_app_url: str = "http://localhost:8000/app"

    postgres_db: str = "reader"
    postgres_user: str = "reader"
    postgres_password: str = "reader"
    database_url: str = "postgresql+psycopg://reader:reader@postgres:5432/reader"

    bot_token: str = ""
    bot_api_token: str = ""
    bot_service_email: str = "bot-service@local"
    backend_base_url: str = "http://backend:8000"
    telegram_bot_username: str = ""

    jwt_secret: str = Field(default="change-me", min_length=12)
    jwt_access_ttl_seconds: int = 900
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"
    smtp_use_tls: bool = True
    email_magic_link_ttl_seconds: int = 900

    max_book_size_mb: int = 50
    max_epub_unpacked_mb: int = 200

    library_root: Path = Path("/data/library/books")
    temp_root: Path = Path("/data/temp")
    static_root: Path = Path("app/web")

    processing_poll_interval_seconds: float = 1.5
    processing_max_attempts: int = 3

    @field_validator("max_book_size_mb", "max_epub_unpacked_mb")
    @classmethod
    def positive_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("limits must be > 0")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
