from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = (
        "postgresql+asyncpg://smithy:smithy_dev_password@localhost:5432/smithy_cloud"
    )
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    LOCAL_INGEST_ENABLED: bool = False
    DEV_CREATE_TABLES: bool = False
    # -- user auth (RBAC foundation) -------------------------------------
    AUTH_ENABLED: bool = False
    SECRET_KEY: str = ""
    ACCESS_TOKEN_TTL_MIN: int = 30
    REFRESH_TOKEN_TTL_DAYS: int = 7
    REGISTRATION_OPEN: bool = True
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
