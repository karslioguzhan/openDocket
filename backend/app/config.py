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
    enable_demo: bool = True
    trash_purge_days: int = 30
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    # Comma-separated hostnames the server may contact for AI requests
    # (scan-to-contract autofill and the assistant). Public provider hosts are
    # pre-listed; add your own provider, or set LLM_ALLOW_PRIVATE=true to allow
    # local/private endpoints such as a self-hosted Ollama.
    llm_allowed_hosts: str = (
        "opencode.ai,api.openai.com,openrouter.ai,api.groq.com,api.deepseek.com"
    )
    # DANGEROUS: allows AI endpoints on any host, including loopback and private
    # addresses. Only enable on a single-user, fully trusted deployment.
    llm_allow_private: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
