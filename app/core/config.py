from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RFC-RAG-Agent"
    app_version: str = "0.1.0"
    app_env: str = "development"
    # SQLite remains the safe fallback; Phase 49 local development should set
    # DATABASE_URL to the PostgreSQL dev container for dev/prod parity.
    database_url: str = "sqlite:///./data/app.sqlite"
    # Redis is optional. When unset or unreachable, embedding cache and
    # LangGraph checkpoints must fall back to in-process memory.
    redis_url: str = ""
    redis_socket_timeout_seconds: float = 1.0
    langgraph_checkpoint_ttl_minutes: int = 60
    langgraph_checkpoint_refresh_on_read: bool = True
    semantic_cache_enabled: bool = False
    semantic_cache_similarity_threshold: float = 0.92
    semantic_cache_ttl_seconds: int = 3600
    rate_limit_enabled: bool = False
    rate_limit_requests_per_minute: int = 30
    rate_limit_window_seconds: int = 60
    pgvector_search_enabled: bool = True
    hnsw_ef_search: int = 100
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
    planner_chat_model_api_keys: str = ""
    planner_chat_model_base_url: str = ""
    planner_chat_model_temperature: float = 0.0
    planner_chat_model_timeout_seconds: float = 30.0

    judge_model_provider: str = ""
    judge_model_name: str = ""
    judge_model_api_key: str = ""
    judge_model_base_url: str = ""
    judge_model_temperature: float = 0.0
    judge_model_timeout_seconds: float = 30.0
    stage34_judge_provider: str = ""
    stage34_judge_model: str = ""
    stage34_judge_api_key: str = ""
    stage34_judge_base_url: str = ""

    embedding_provider: str = ""
    embedding_model_name: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_dimension: int = 0
    embedding_timeout_seconds: float = 30.0

    reranking_enabled: bool = True
    reranking_provider: str = "remote-bge-lora"
    reranking_model_name: str = "rfc-domain-bge-lora"
    reranking_api_key: str = ""
    reranking_base_url: str = "http://127.0.0.1:8091"
    reranking_timeout_seconds: float = 30.0
    reranking_recall_k: int = 75

    vision_model_provider: str = ""
    vision_model_name: str = ""
    vision_model_api_key: str = ""
    vision_model_base_url: str = ""
    vision_model_timeout_seconds: float = 30.0

    enable_auto_figure_enrichment: bool = False
    enable_table_extraction: bool = True
    enable_user_image_upload: bool = True
    table_extraction_min_rows: int = 2
    user_image_max_size_mb: float = 10.0
    graphrag_graph_path: str = "data/knowledge_graph/domain_graph.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:
        if not self.judge_model_provider and self.stage34_judge_provider:
            self.judge_model_provider = self.stage34_judge_provider
        if not self.judge_model_name and self.stage34_judge_model:
            self.judge_model_name = self.stage34_judge_model
        if not self.judge_model_api_key and self.stage34_judge_api_key:
            self.judge_model_api_key = self.stage34_judge_api_key
        if not self.judge_model_base_url and self.stage34_judge_base_url:
            self.judge_model_base_url = self.stage34_judge_base_url
        if self.judge_model_provider.strip().casefold() in {"deepseek", "paratera", "glm", "zhipu"}:
            self.judge_model_provider = "openai-compatible"


@lru_cache
def get_settings() -> Settings:
    return Settings()
