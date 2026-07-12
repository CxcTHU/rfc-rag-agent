from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.vector_cache import VectorIndexEntry, VectorIndexMatch
from app.services.retrieval.vector_index import calculate_text_hash


@dataclass(frozen=True)
class PgVectorSearchStatus:
    enabled: bool
    reason: str = ""


@dataclass(frozen=True)
class PgVectorSearchOutcome:
    matches: list[VectorIndexMatch] | None
    enabled: bool
    reason: str = ""


class PgVectorSearchService:
    """PostgreSQL pgvector HNSW search with safe FAISS fallback boundaries."""

    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.settings = settings or get_settings()

    def status(self) -> PgVectorSearchStatus:
        if not self.settings.pgvector_search_enabled:
            return PgVectorSearchStatus(enabled=False, reason="disabled")
        bind = self.db.get_bind()
        if bind.dialect.name != "postgresql":
            return PgVectorSearchStatus(enabled=False, reason=f"unsupported_dialect:{bind.dialect.name}")
        if self.embedding_provider.dimension != 2048:
            return PgVectorSearchStatus(enabled=False, reason="unsupported_dimension")
        return PgVectorSearchStatus(enabled=True)

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int,
    ) -> PgVectorSearchOutcome:
        status = self.status()
        if not status.enabled:
            return PgVectorSearchOutcome(
                matches=None,
                enabled=False,
                reason=bounded_pgvector_reason(status.reason),
            )
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if len(query_embedding) != self.embedding_provider.dimension:
            raise ValueError("query embedding dimension does not match pgvector configuration")

        query_literal = format_pgvector_literal(query_embedding, expected_dimension=self.embedding_provider.dimension)
        ef_search = max(1, int(self.settings.hnsw_ef_search))
        try:
            self.db.execute(text(f"SET LOCAL hnsw.ef_search = {ef_search}"))
            rows = self.db.execute(
                text(
                    """
                    SELECT
                        d.id AS document_id,
                        d.title AS document_title,
                        d.source_type AS source_type,
                        d.source_path AS source_path,
                        d.file_name AS file_name,
                        c.id AS chunk_id,
                        c.chunk_index AS chunk_index,
                        c.content AS content,
                        c.heading_path AS heading_path,
                        c.chunk_type AS chunk_type,
                        c.source_image_path AS source_image_path,
                        c.caption AS caption,
                        c.page_number AS page_number,
                        ce.content_hash AS content_hash,
                        ce.embedding_vector::halfvec(2048) <=> CAST(:query_vector AS halfvec(2048)) AS distance
                    FROM chunk_embeddings ce
                    JOIN chunks c ON ce.chunk_id = c.id
                    JOIN documents d ON c.document_id = d.id
                    WHERE ce.provider = :provider
                      AND ce.model_name = :model_name
                      AND ce.dimension = :dimension
                      AND ce.embedding_vector IS NOT NULL
                    ORDER BY ce.embedding_vector::halfvec(2048) <=> CAST(:query_vector AS halfvec(2048))
                    LIMIT :limit
                    """
                ),
                {
                    "query_vector": query_literal,
                    "provider": self.embedding_provider.provider_name,
                    "model_name": self.embedding_provider.model_name,
                    "dimension": self.embedding_provider.dimension,
                    "limit": top_k,
                },
            ).mappings()
        except SQLAlchemyError:
            return PgVectorSearchOutcome(matches=None, enabled=True, reason="sql_error")

        matches: list[VectorIndexMatch] = []
        for row in rows:
            content = str(row["content"])
            if row["content_hash"] != calculate_text_hash(content):
                continue
            distance = float(row["distance"])
            matches.append(
                VectorIndexMatch(
                    entry=VectorIndexEntry(
                        document_id=int(row["document_id"]),
                        document_title=str(row["document_title"]),
                        source_type=str(row["source_type"]),
                        source_path=row["source_path"],
                        file_name=str(row["file_name"]),
                        chunk_id=int(row["chunk_id"]),
                        chunk_index=int(row["chunk_index"]),
                        content=content,
                        heading_path=row["heading_path"],
                        chunk_type=str(row["chunk_type"]),
                        source_image_path=row["source_image_path"],
                        caption=row["caption"],
                        page_number=row["page_number"],
                    ),
                    score=max(0.0, 1.0 - distance),
                )
            )
        return PgVectorSearchOutcome(matches=matches, enabled=True)


def bounded_pgvector_reason(reason: str) -> str:
    if reason.startswith("unsupported_dialect"):
        return "unsupported_dialect"
    if reason in {"disabled", "unsupported_dimension", "sql_error"}:
        return reason
    return "unavailable"


def format_pgvector_literal(vector: Sequence[float], *, expected_dimension: int) -> str:
    if len(vector) != expected_dimension:
        raise ValueError("query embedding dimension does not match pgvector configuration")
    values: list[str] = []
    for value in vector:
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("query embedding contains a non-finite value")
        values.append(format(numeric_value, ".12g"))
    return "[" + ",".join(values) + "]"
