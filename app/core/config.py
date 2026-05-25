from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = ""
    database_url: str = "postgresql+asyncpg://finance:finance@localhost:5432/finance"
    admin_ids: str = ""
    app_secret: str = "change-me"
    app_base_url: str = "http://localhost:8000"
    access_token_ttl_minutes: int = 30
    default_currency: str = "ILS"
    default_timezone: str = "Asia/Jerusalem"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def admin_id_set(self) -> set[int]:
        return {int(item.strip()) for item in self.admin_ids.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
