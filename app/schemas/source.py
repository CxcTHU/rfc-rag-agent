from datetime import datetime

from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    id: int
    source_id: str
    title: str
    authors: str | None
    year: str | None
    venue: str | None
    category: str | None
    discovered_via: str | None
    doi: str | None
    url: str | None
    pdf_url: str | None
    source_type: str
    trust_level: str
    access_rights: str
    fulltext_permission: str
    local_path: str | None
    status: str
    document_id: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SourceListResponse(BaseModel):
    sources: list[SourceItem]


class SourceSyncRequest(BaseModel):
    include_defaults: bool = True
    candidate_csvs: list[str] = Field(default_factory=list)
    fulltext_manifests: list[str] = Field(default_factory=list)
    metadata_csvs: list[str] = Field(default_factory=list)
    metadata_cards_dirs: list[str] = Field(default_factory=list)


class SourceSyncResponse(BaseModel):
    total: int
    created: int
    updated: int
    duplicates: int


class SourceReindexRequest(BaseModel):
    metadata_cards_dir: str | None = None


class SourceReindexResponse(BaseModel):
    source_id: str
    document_id: int
    title: str
    chunk_count: int
    import_status: str
    source_status: str
    raw_path: str
