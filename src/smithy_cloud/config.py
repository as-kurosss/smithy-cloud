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


@lru_cache
def get_settings() -> Settings:
    return Settings()
