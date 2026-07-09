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
    open_url: str | None = None
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
    chunk_type: str = "text"
    source_image_path: str | None = None
    caption: str | None = None
    page_number: int | None = None
    created_at: datetime


class DocumentChunksResponse(BaseModel):
    document_id: int
    title: str
    source_path: str | None
    file_name: str
    chunk_count: int
    chunks: list[DocumentChunkItem]
