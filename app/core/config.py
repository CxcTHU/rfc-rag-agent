from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RFC-RAG-Agent"
    app_version: str = "0.1.0"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/app.sqlite"

    chat_model_provider: str = ""
    chat_model_name: str = ""
    chat_model_api_key: str = ""
    chat_model_base_url: str = ""

    embedding_provider: str = ""
    embedding_model_name: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
