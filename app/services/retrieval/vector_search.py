import math
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document
from app.db.repositories import deserialize_embedding
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.vector_index import calculate_text_hash


@dataclass(frozen=True)
class VectorSearchResult:
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    score: float


class VectorSearchService:
    def __init__(self, db: Session, embedding_provider: EmbeddingProvider) -> None:
        self.db = db
        self.embedding_provider = embedding_provider

    def search(self, query: str, top_k: int = 5) -> list[VectorSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        query_embedding = self.embedding_provider.embed_query(normalized_query)
        if len(query_embedding) != self.embedding_provider.dimension:
            raise ValueError("embedding provider returned a vector with unexpected dimension")
        if is_zero_vector(query_embedding):
            return []

        rows = self._list_indexed_chunks()
        results: list[VectorSearchResult] = []
        for chunk_embedding, chunk, document in rows:
            if chunk_embedding.content_hash != calculate_text_hash(chunk.content):
                continue

            stored_embedding = deserialize_embedding(chunk_embedding.embedding_json)
            if len(stored_embedding) != len(query_embedding):
                continue

            score = cosine_similarity(query_embedding, stored_embedding)
            if score <= 0:
                continue

            results.append(
                VectorSearchResult(
                    document_id=document.id,
                    document_title=document.title,
                    source_type=document.source_type,
                    source_path=document.source_path,
                    file_name=document.file_name,
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    heading_path=chunk.heading_path,
                    score=score,
                )
            )

        return sorted(
            results,
            key=lambda item: (-item.score, item.document_id, item.chunk_index),
        )[:top_k]

    def _list_indexed_chunks(self) -> list[tuple[ChunkEmbedding, Chunk, Document]]:
        statement = (
            select(ChunkEmbedding, Chunk, Document)
            .join(Chunk, ChunkEmbedding.chunk_id == Chunk.id)
            .join(Document, Chunk.document_id == Document.id)
            .where(
                ChunkEmbedding.provider == self.embedding_provider.provider_name,
                ChunkEmbedding.model_name == self.embedding_provider.model_name,
                ChunkEmbedding.dimension == self.embedding_provider.dimension,
            )
            .order_by(ChunkEmbedding.id)
        )
        return list(self.db.execute(statement).all())


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")

    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0

    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    similarity = dot_product / (left_norm * right_norm)
    return max(-1.0, min(1.0, similarity))


def is_zero_vector(vector: Sequence[float]) -> bool:
    return all(value == 0 for value in vector)
