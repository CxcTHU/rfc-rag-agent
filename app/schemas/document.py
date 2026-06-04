from datetime import datetime

from pydantic import BaseModel


class DocumentImportResponse(BaseModel):
    document_id: int
    title: str
    chunk_count: int
    status: str
    content_hash: str
    raw_path: str


class DocumentListItem(BaseModel):
    id: int
    title: str
    source_type: str
    source_path: str | None
    file_name: str
    file_extension: str
    status: str
    chunk_count: int
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]


class DocumentChunkItem(BaseModel):
    id: int
    chunk_index: int
    content: str
    char_count: int
    heading_path: str | None
    start_char: int | None
    end_char: int | None
    created_at: datetime


class DocumentChunksResponse(BaseModel):
    document_id: int
    title: str
    source_path: str | None
    file_name: str
    chunk_count: int
    chunks: list[DocumentChunkItem]
