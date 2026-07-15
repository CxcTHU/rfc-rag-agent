from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class Phase65ModelInventoryItem(BaseModel):
    path: str
    identity_sha256: str | None = None
    configured: bool
    usage_receipt_verified: bool


class RetrievalContractHealthResponse(HealthResponse):
    """Safe retrieval identity used to freeze an external A/B evaluation."""

    corpus_fingerprint: str
    index_fingerprint_sha256: str
    cold_run_receipts_supported: bool
    endpoint_identity_sha256: str
    phase65_model_inventory: list[Phase65ModelInventoryItem]
    chat_model_provider: str
    chat_model_name: str
    embedding_provider: str
    embedding_model_name: str
    embedding_dimension: int
    document_count: int
    chunk_count: int
    retrieval_runtime_enabled: bool
    retrieval_runtime_default_enabled: bool
    pgvector_search_enabled: bool
    vector_backend_policy: str
    retrieval_runtime_schema: str
    agent_short_loop_enabled: bool
    phase64_route_first_enabled: bool
    phase64_retrieval_fanout_enabled: bool
    phase64_final_non_thinking_enabled: bool
    phase64_execution_graph_schema: str
    reranking_enabled: bool
    reranking_provider: str
    reranking_model_name: str
    retrieval_candidate_cache_enabled: bool
    rerank_order_cache_enabled: bool
    tool_result_cache_enabled: bool
    semantic_evidence_cache_enabled: bool


class DatabaseHealth(BaseModel):
    status: str
    connected: bool
    document_count: int | None = None
    chunk_count: int | None = None
    error: str | None = None


class FaissIndexHealth(BaseModel):
    status: str
    provider: str | None = None
    model_name: str | None = None
    dimension: int | None = None
    metric: str | None = None
    normalized: bool | None = None
    complete: bool | None = None
    vector_count: int | None = None
    index_path: str
    metadata_path: str
    index_exists: bool
    metadata_exists: bool
    error: str | None = None


class FaissHealth(BaseModel):
    status: str
    index_dir: str
    index_count: int
    indexes: list[FaissIndexHealth]


class ProviderItemHealth(BaseModel):
    status: str
    provider: str
    model_name: str
    configured: bool
    enabled: bool = True


class ProviderConfigHealth(BaseModel):
    status: str
    chat: ProviderItemHealth
    embedding: ProviderItemHealth
    reranking: ProviderItemHealth
    deterministic_available: bool


class HealthDetailsResponse(HealthResponse):
    database: DatabaseHealth
    faiss: FaissHealth
    providers: ProviderConfigHealth
