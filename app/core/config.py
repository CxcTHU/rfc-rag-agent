from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RFC-RAG-Agent"
    app_version: str = "0.1.0"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/app.sqlite"
    raw_data_dir: str = "data/raw"
    auth_enabled: bool = False
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    chat_model_provider: str = ""
    chat_model_name: str = ""
    chat_model_api_key: str = ""
    chat_model_base_url: str = ""
    chat_model_temperature: float = 0.2
    chat_model_timeout_seconds: float = 30.0

    # Optional dedicated planner provider for ReAct LLM-driven planning.
    # When planner_chat_model_provider is empty the ReAct service falls back
    # to the deterministic short-circuit + chat_model_provider behavior.
    # When set, the ReAct service uses this provider for every planner
    # decision and disables the deterministic short-circuit so the LLM
    # truly drives action selection.
    planner_chat_model_provider: str = ""
    planner_chat_model_name: str = ""
    planner_chat_model_api_key: str = ""
    planner_chat_model_base_url: str = ""
    planner_chat_model_temperature: float = 0.0
    planner_chat_model_timeout_seconds: float = 30.0

    embedding_provider: str = ""
    embedding_model_name: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_dimension: int = 0
    embedding_timeout_seconds: float = 30.0

    reranking_enabled: bool = True
    reranking_provider: str = "deterministic"
    reranking_model_name: str = "keyword-overlap-reranker-v1"
    reranking_api_key: str = ""
    reranking_base_url: str = ""
    reranking_timeout_seconds: float = 30.0
    reranking_recall_k: int = 25

    vision_model_provider: str = ""
    vision_model_name: str = ""
    vision_model_api_key: str = ""
    vision_model_base_url: str = ""
    vision_model_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
