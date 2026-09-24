"""Environment-driven settings for the copilot. Grows across the course."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "fake"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    loopline_database_url: str = "sqlite:///./sample_app/loopline/loopline.db"
    loopline_source_root: str = "./sample_app/loopline/app"
    loopline_docs_root: str = "./sample_app/loopline/docs"
    loopline_logs_root: str = "./sample_app/loopline/logs"

    # query_database's connection, kept deliberately separate from
    # loopline_database_url above: that URL is the APP's own (read-write) database,
    # this one is what the copilot's read-only tool uses. Empty (the default) means
    # "use the SQLite path" (tools/database.py), unchanged since Episode 12. Set to a
    # mysql+pymysql:// URL (Episode 16) to switch query_database to MySQL - directly
    # in-process, or via a standalone MCP server if use_database_mcp is also true.
    loopline_readonly_database_url: str = ""
    use_database_mcp: bool = False


settings = Settings()
