from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document
from app.db.repositories import deserialize_embedding
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.faiss_index import FaissVectorIndex, default_faiss_paths
from app.services.retrieval.vector_index import calculate_text_hash
from app.services.observability.latency_trace import latency_timer


@dataclass(frozen=True)
class VectorIndexEntry:
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    chunk_type: str = "text"
    source_image_path: str | None = None


@dataclass(frozen=True)
class VectorIndexMatch:
    entry: VectorIndexEntry
    score: float


class VectorIndexCache:
    """In-process vector cache with FAISS first and numpy fallback."""

    def __init__(self, db: Session, embedding_provider: EmbeddingProvider) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self._lock = RLock()
        self._loaded = False
        self._entries: list[VectorIndexEntry] = []
        self._entries_by_chunk_id: dict[int, VectorIndexEntry] = {}
        self._normalized_matrix: np.ndarray = np.empty(
            (0, embedding_provider.dimension),
            dtype=np.float64,
        )
        self._faiss_index: FaissVectorIndex | None = None
        self.load_mode = "empty"

    def bind_session(self, db: Session) -> None:
        with self._lock:
            self.db = db

    def invalidate(self) -> None:
        with self._lock:
            self._loaded = False
            self._entries = []
            self._entries_by_chunk_id = {}
            self._normalized_matrix = np.empty(
                (0, self.embedding_provider.dimension),
                dtype=np.float64,
            )
            self._faiss_index = None
            self.load_mode = "empty"

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int,
    ) -> list[VectorIndexMatch]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if len(query_embedding) != self.embedding_provider.dimension:
            raise ValueError("query embedding dimension does not match the vector cache")

        self._ensure_loaded()
        if not self._entries:
            return []

        query_vector = normalize_query_vector(query_embedding)
        if query_vector is None:
            return []

        with self._lock:
            if self._faiss_index is not None:
                with latency_timer("faiss_search_latency_ms"):
                    return self._search_faiss(query_vector=query_vector, top_k=top_k)

            with latency_timer("numpy_search_latency_ms"):
                scores = self._normalized_matrix @ query_vector
            if scores.size == 0:
                return []

            candidate_count = min(top_k, scores.size)
            candidate_indexes = np.argpartition(scores, -candidate_count)[-candidate_count:]
            ordered_indexes = candidate_indexes[np.argsort(scores[candidate_indexes])[::-1]]
            return [
                VectorIndexMatch(
                    entry=self._entries[int(index)],
                    score=float(scores[int(index)]),
                )
                for index in ordered_indexes
                if float(scores[int(index)]) > 0
            ]

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._loaded:
                return
            faiss_payload = self._load_faiss_entries_if_available()
            if faiss_payload is not None:
                entries, faiss_index = faiss_payload
                self._entries = entries
                self._entries_by_chunk_id = {entry.chunk_id: entry for entry in entries}
                self._normalized_matrix = np.empty(
                    (0, self.embedding_provider.dimension),
                    dtype=np.float64,
                )
                self._faiss_index = faiss_index
                self.load_mode = "faiss_only" if entries else "empty"
                self._loaded = True
                return

            entries, matrix = self._load_entries_and_matrix()
            self._entries = entries
            self._entries_by_chunk_id = {entry.chunk_id: entry for entry in entries}
            self._normalized_matrix = normalize_matrix(matrix)
            self._faiss_index = None
            self.load_mode = "numpy_fallback" if entries else "empty"
            self._loaded = True

    def _search_faiss(
        self,
        query_vector: np.ndarray,
        top_k: int,
    ) -> list[VectorIndexMatch]:
        if self._faiss_index is None:
            return []
        matches: list[VectorIndexMatch] = []
        for faiss_match in self._faiss_index.search(query_vector, top_k=top_k):
            entry = self._entries_by_chunk_id.get(faiss_match.chunk_id)
            if entry is None:
                continue
            matches.append(VectorIndexMatch(entry=entry, score=faiss_match.score))
        return matches

    def _load_entries_and_matrix(self) -> tuple[list[VectorIndexEntry], np.ndarray]:
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
        entries: list[VectorIndexEntry] = []
        embeddings: list[list[float]] = []
        for chunk_embedding, chunk, document in self.db.execute(statement).all():
            if chunk_embedding.content_hash != calculate_text_hash(chunk.content):
                continue
            embedding = deserialize_embedding(chunk_embedding.embedding_json)
            if len(embedding) != self.embedding_provider.dimension:
                continue
            entries.append(
                VectorIndexEntry(
                    document_id=document.id,
                    document_title=document.title,
                    source_type=document.source_type,
                    source_path=document.source_path,
                    file_name=document.file_name,
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    heading_path=chunk.heading_path,
                    chunk_type=chunk.chunk_type,
                    source_image_path=chunk.source_image_path,
                )
            )
            embeddings.append(embedding)

        if not embeddings:
            return entries, np.empty((0, self.embedding_provider.dimension), dtype=np.float64)
        return entries, np.asarray(embeddings, dtype=np.float64)

    def _load_faiss_entries_if_available(self) -> tuple[list[VectorIndexEntry], FaissVectorIndex] | None:
        faiss_index = self._load_faiss_index_if_available()
        if faiss_index is None:
            return None

        faiss_chunk_ids = set(faiss_index.metadata.chunk_ids)
        if len(faiss_chunk_ids) != len(faiss_index.metadata.chunk_ids):
            return None

        entries = self._load_entries_metadata_only()
        entry_chunk_ids = {entry.chunk_id for entry in entries}
        if entry_chunk_ids != faiss_chunk_ids:
            return None
        return entries, faiss_index

    def _load_entries_metadata_only(self) -> list[VectorIndexEntry]:
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
        entries: list[VectorIndexEntry] = []
        for chunk_embedding, chunk, document in self.db.execute(statement).all():
            if chunk_embedding.content_hash != calculate_text_hash(chunk.content):
                continue
            entries.append(
                VectorIndexEntry(
                    document_id=document.id,
                    document_title=document.title,
                    source_type=document.source_type,
                    source_path=document.source_path,
                    file_name=document.file_name,
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    heading_path=chunk.heading_path,
                    chunk_type=chunk.chunk_type,
                    source_image_path=chunk.source_image_path,
                )
            )
        return entries

    def _load_faiss_index_if_available(self) -> FaissVectorIndex | None:
        index_path, metadata_path = default_faiss_paths(
            Path("data/faiss"),
            provider=self.embedding_provider.provider_name,
            model_name=self.embedding_provider.model_name,
            dimension=self.embedding_provider.dimension,
        )
        if not index_path.exists() or not metadata_path.exists():
            return None
        try:
            faiss_index = FaissVectorIndex.load(index_path=index_path, metadata_path=metadata_path)
        except (OSError, RuntimeError, ValueError):
            return None
        if not faiss_index.metadata.complete:
            return None
        if faiss_index.metadata.provider != self.embedding_provider.provider_name:
            return None
        if faiss_index.metadata.model_name != self.embedding_provider.model_name:
            return None
        if faiss_index.metadata.dimension != self.embedding_provider.dimension:
            return None
        return faiss_index


def normalize_query_vector(vector: Sequence[float]) -> np.ndarray | None:
    array = np.asarray(vector, dtype=np.float64)
    norm = np.linalg.norm(array)
    if norm == 0:
        return None
    return array / norm


def normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1)
    safe_norms = np.where(norms == 0, 1.0, norms)
    normalized = matrix / safe_norms[:, np.newaxis]
    normalized[norms == 0] = 0.0
    return normalized


_GLOBAL_CACHES: dict[tuple[str, str, str, int], VectorIndexCache] = {}
_GLOBAL_CACHES_LOCK = RLock()


def get_vector_index_cache(
    db: Session,
    embedding_provider: EmbeddingProvider,
) -> VectorIndexCache:
    bind = db.get_bind()
    key = (
        str(bind.url),
        embedding_provider.provider_name,
        embedding_provider.model_name,
        embedding_provider.dimension,
    )
    with _GLOBAL_CACHES_LOCK:
        cache = _GLOBAL_CACHES.get(key)
        if cache is None:
            cache = VectorIndexCache(db, embedding_provider)
            _GLOBAL_CACHES[key] = cache
        else:
            cache.bind_session(db)
        return cache


def invalidate_vector_index_cache(
    db: Session,
    embedding_provider: EmbeddingProvider,
) -> None:
    bind = db.get_bind()
    key = (
        str(bind.url),
        embedding_provider.provider_name,
        embedding_provider.model_name,
        embedding_provider.dimension,
    )
    with _GLOBAL_CACHES_LOCK:
        cache = _GLOBAL_CACHES.get(key)
        if cache is not None:
            cache.invalidate()
