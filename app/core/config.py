from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = ""
    database_url: str = "postgresql+asyncpg://finance:finance@localhost:5432/finance"
    admin_ids: str = ""
    app_secret: str = "change-me"
    app_base_url: str = "http://localhost:8000"
    render_external_url: str | None = None
    enable_bot_webhook: bool = False
    telegram_webhook_secret: str = ""
    telegram_webhook_path: str = "/telegram/webhook"
    access_token_ttl_minutes: int = 30
    default_currency: str = "ILS"
    default_timezone: str = "Asia/Jerusalem"
    log_level: str = "INFO"
    allow_developer_login: bool = False
    ocr_enabled: bool = False
    tesseract_cmd: str | None = None
    ocr_languages: str = "eng+heb"
    ocr_min_confidence: float = 0.65
    ocr_max_image_mb: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def admin_id_set(self) -> set[int]:
        return {int(item.strip()) for item in self.admin_ids.split(",") if item.strip()}

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url

    @property
    def public_base_url(self) -> str:
        return (self.render_external_url or self.app_base_url).rstrip("/")

    @property
    def telegram_webhook_url(self) -> str:
        return f"{self.public_base_url}{self.telegram_webhook_path}"

    @property
    def is_production(self) -> bool:
        return self.enable_bot_webhook or bool(self.render_external_url)

    def validate_runtime_secrets(self) -> None:
        if self.is_production and (
            self.app_secret == "change-me" or len(self.app_secret) < 32
        ):
            raise RuntimeError("APP_SECRET must be a strong 32+ character secret")


@lru_cache
def get_settings() -> Settings:
    return Settings()
