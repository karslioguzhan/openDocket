from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "openDocket"
    database_url: str = "postgresql+asyncpg://opendocket:opendocket@localhost:5432/opendocket"
    secret: str = "change-me"
    file_storage_dir: str = "./data/files"
    cookie_secure: bool = False
    session_lifetime_seconds: int = 60 * 60 * 24 * 30
    admin_email: str = ""
    admin_password: str = ""
    admin_is_superuser: bool = True
    auto_create_tables: bool = False
    trash_purge_days: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
