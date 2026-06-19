from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.services.generation.vision_model import VisionModelProvider
from app.services.ingestion.image_extractor import PdfImageExtractor
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexResult, VectorIndexService


@dataclass(frozen=True)
class MultimodalDocumentResult:
    document_id: int
    extracted_images: int
    created_chunks: int
    skipped_images: int
    embedding_result: VectorIndexResult | None = None


class MultimodalIngestionPipeline:
    def __init__(
        self,
        db: Session,
        image_extractor: PdfImageExtractor,
        vision_provider: VisionModelProvider,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.image_extractor = image_extractor
        self.vision_provider = vision_provider
        self.embedding_provider = embedding_provider

    def process_document(
        self,
        document_id: int,
        *,
        build_embeddings: bool = True,
    ) -> MultimodalDocumentResult:
        document = self.db.get(Document, document_id)
        if document is None:
            raise ValueError(f"document {document_id} was not found")
        if document.file_extension.casefold() != ".pdf":
            raise ValueError(f"document {document_id} is not a PDF")

        images = self.image_extractor.extract_images(document.raw_path, document_id=document.id)
        created_chunks = 0
        skipped_images = 0
        next_chunk_index = self._next_chunk_index(document.id)

        for image in images:
            if self._image_chunk_exists(image.image_path):
                skipped_images += 1
                continue
            description = self.vision_provider.describe_image(image.image_path)
            chunk = Chunk(
                document_id=document.id,
                chunk_index=next_chunk_index,
                content=description,
                char_count=len(description),
                heading_path=f"{document.title} > [图表]",
                start_char=None,
                end_char=None,
                chunk_type="image_description",
                source_image_path=image.image_path,
            )
            self.db.add(chunk)
            self.db.flush()
            next_chunk_index += 1
            created_chunks += 1

        self.db.commit()
        embedding_result = None
        if build_embeddings and self.embedding_provider is not None:
            embedding_result = VectorIndexService(self.db, self.embedding_provider).build_index()

        return MultimodalDocumentResult(
            document_id=document.id,
            extracted_images=len(images),
            created_chunks=created_chunks,
            skipped_images=skipped_images,
            embedding_result=embedding_result,
        )

    def _next_chunk_index(self, document_id: int) -> int:
        max_index = self.db.scalar(
            select(func.max(Chunk.chunk_index)).where(Chunk.document_id == document_id)
        )
        if max_index is None:
            return 0
        return int(max_index) + 1

    def _image_chunk_exists(self, image_path: str) -> bool:
        existing = self.db.scalar(
            select(Chunk.id).where(
                Chunk.chunk_type == "image_description",
                Chunk.source_image_path == image_path,
            )
        )
        return existing is not None


def resolve_document_raw_path(document: Document) -> Path:
    return Path(document.raw_path)
