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
    layered_cache_namespace: str = "phase56-v1"
    retrieval_candidate_cache_enabled: bool = True
    retrieval_candidate_cache_ttl_seconds: int = 900
    rerank_order_cache_enabled: bool = True
    rerank_order_cache_ttl_seconds: int = 900
    tool_result_cache_enabled: bool = True
    tool_result_cache_ttl_seconds: int = 900
    rate_limit_enabled: bool = False
    rate_limit_required_in_prod: bool = True
    rate_limit_requests_per_minute: int = 30
    rate_limit_window_seconds: int = 60
    trust_forwarded_for: bool = False
    pgvector_search_enabled: bool = True
    hnsw_ef_search: int = 100
    vector_backend_policy: str = "prefer_pgvector"
    raw_data_dir: str = "data/raw"
    auth_enabled: bool = False
    auth_required_in_prod: bool = True
    auth_allow_public_registration: bool = False
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
    runtime_identity_model_provider: str = ""
    runtime_identity_model_name: str = ""
    runtime_identity_model_api_key: str = ""
    runtime_identity_model_base_url: str = ""
    runtime_identity_model_temperature: float = 0.0
    runtime_identity_model_timeout_seconds: float = 10.0

    judge_model_provider: str = ""
    judge_model_name: str = ""
    judge_model_api_key: str = ""
    judge_model_base_url: str = ""
    judge_model_temperature: float = 0.0
    judge_model_timeout_seconds: float = 30.0
    judge_model_max_attempts: int = 1
    judge_model_max_tokens: int = 512
    judge_model_disable_thinking: bool = False
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
    reranking_provider: str = "paratera"
    reranking_model_name: str = "GLM-Rerank"
    reranking_api_key: str = ""
    reranking_base_url: str = "https://llmapi.paratera.com/v1/p002"
    reranking_timeout_seconds: float = 30.0
    reranking_health_check_enabled: bool = True
    reranking_health_check_timeout_seconds: float = 2.0
    reranking_unavailable_ttl_seconds: float = 30.0
    reranking_recall_k: int = 75
    reranking_dynamic_top_k_enabled: bool = True
    reranking_dynamic_min_results: int = 4
    reranking_dynamic_max_results: int = 12
    reranking_dynamic_relative_score_threshold: float = 0.65
    reranking_fallback_enabled: bool = False
    reranking_fusion_fail_soft_enabled: bool = True
    reranking_fallback_provider: str = "paratera"
    reranking_fallback_model_name: str = "GLM-Rerank"
    reranking_fallback_api_key: str = ""
    reranking_fallback_base_url: str = "https://llmapi.paratera.com/v1/p002"
    reranking_fallback_timeout_seconds: float = 30.0
    hybrid_multichannel_enabled: bool = True
    hybrid_graph_channel_enabled: bool = True
    hybrid_table_text_channel_enabled: bool = True
    hybrid_figure_caption_channel_enabled: bool = True
    hybrid_channel_rank_constant: int = 60
    hybrid_graph_channel_weight: float = 1.1
    hybrid_table_text_channel_weight: float = 0.9
    hybrid_figure_caption_channel_weight: float = 0.8
    hybrid_graph_max_matches: int = 50
    retrieval_runtime_enabled: bool = True
    retrieval_runtime_default_enabled: bool = True
    retrieval_runtime_schema: str = "phase63-gap-closure-v1"
    retrieval_relationship_required_threshold: float = 0.80
    retrieval_relationship_preferred_threshold: float = 0.45
    retrieval_graph_preferred_max_hops: int = 1
    retrieval_graph_preferred_max_matches: int = 20
    retrieval_graph_required_max_hops: int = 2
    retrieval_graph_required_max_matches: int = 50

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
    source_sync_allowed_roots: str = "data"
    export_allowed_dir: str = "data/evaluation"
    table_rag_enabled: bool = False
    agent_default_mode: str = "tool_calling_agent"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:
        if self.app_env.strip().casefold() == "production":
            if self.auth_required_in_prod:
                self.auth_enabled = True
            if self.rate_limit_required_in_prod:
                self.rate_limit_enabled = True
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
        if (
            not self.reranking_fallback_api_key
            and self.reranking_fallback_provider.strip().casefold() == "paratera"
            and self.embedding_api_key
        ):
            self.reranking_fallback_api_key = self.embedding_api_key
        if (
            not self.reranking_api_key
            and self.reranking_provider.strip().casefold() == "paratera"
            and (self.reranking_fallback_api_key or self.embedding_api_key)
        ):
            self.reranking_api_key = self.reranking_fallback_api_key or self.embedding_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
