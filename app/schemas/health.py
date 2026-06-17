from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


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
