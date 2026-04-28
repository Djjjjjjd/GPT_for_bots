from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_proxy_url: str | None = Field(default=None, alias="TELEGRAM_PROXY_URL")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(alias="OPENAI_MODEL")

    max_file_mb: int = Field(default=15, alias="MAX_FILE_MB", ge=1)
    max_pdf_pages: int = Field(default=10, alias="MAX_PDF_PAGES", ge=1)
    user_daily_limit: int = Field(default=20, alias="USER_DAILY_LIMIT", ge=1)
    user_min_seconds_between_requests: int = Field(
        default=10,
        alias="USER_MIN_SECONDS_BETWEEN_REQUESTS",
        ge=0,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
