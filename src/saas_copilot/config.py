"""Environment-driven settings for the copilot. Grows across the course."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "fake"
    llm_api_key: str = ""

    loopline_database_url: str = "sqlite:///./sample_app/loopline/loopline.db"
    loopline_source_root: str = "./sample_app/loopline/app"
    loopline_docs_root: str = "./sample_app/loopline/docs"
    loopline_logs_root: str = "./sample_app/loopline/logs"


settings = Settings()
