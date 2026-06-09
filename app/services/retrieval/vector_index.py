import hashlib
import time
from dataclasses import dataclass
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.db.repositories import ChunkEmbeddingCreate, ChunkEmbeddingRepository
from app.services.retrieval.embedding import EmbeddingProvider


T = TypeVar("T")


@dataclass(frozen=True)
class VectorIndexResult:
    total_chunks: int
    indexed_chunks: int
    skipped_chunks: int
    updated_chunks: int
    provider: str
    model_name: str
    dimension: int


class VectorIndexService:
    def __init__(self, db: Session, embedding_provider: EmbeddingProvider) -> None:
        self.db = db
        self.embedding_provider = embedding_provider
        self.embedding_repository = ChunkEmbeddingRepository(db)

    def build_index(
        self,
        limit: int | None = None,
        batch_size: int = 32,
        sleep_seconds: float = 0.0,
        max_retries: int = 0,
    ) -> VectorIndexResult:
        if limit is not None and limit <= 0:
            raise ValueError("limit must be greater than 0")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")
        if sleep_seconds < 0:
            raise ValueError("sleep_seconds must be greater than or equal to 0")
        if max_retries < 0:
            raise ValueError("max_retries must be greater than or equal to 0")

        chunks = self._list_chunks(limit=limit)
        indexed_chunks = 0
        skipped_chunks = 0
        updated_chunks = 0

        pending_chunks: list[tuple[Chunk, str, bool]] = []
        for chunk in chunks:
            content_hash = calculate_text_hash(chunk.content)
            existing_embedding = self.embedding_repository.get_embedding(
                chunk_id=chunk.id,
                provider=self.embedding_provider.provider_name,
                model_name=self.embedding_provider.model_name,
            )
            if (
                existing_embedding is not None
                and existing_embedding.content_hash == content_hash
                and existing_embedding.dimension == self.embedding_provider.dimension
            ):
                skipped_chunks += 1
                continue
            pending_chunks.append((chunk, content_hash, existing_embedding is not None))

        for batch in batched(pending_chunks, batch_size):
            embeddings = self._embed_with_retry(
                [chunk.content for chunk, _hash, _exists in batch],
                max_retries=max_retries,
            )
            if len(embeddings) != len(batch):
                raise ValueError("embedding provider returned an unexpected number of vectors")

            for (chunk, content_hash, existed), embedding in zip(batch, embeddings, strict=True):
                if len(embedding) != self.embedding_provider.dimension:
                    raise ValueError(
                        "embedding provider returned a vector with unexpected dimension"
                    )
                self.embedding_repository.save_embedding(
                    ChunkEmbeddingCreate(
                        chunk_id=chunk.id,
                        provider=self.embedding_provider.provider_name,
                        model_name=self.embedding_provider.model_name,
                        dimension=self.embedding_provider.dimension,
                        embedding=embedding,
                        content_hash=content_hash,
                    ),
                    commit=False,
                )
                if existed:
                    updated_chunks += 1
                else:
                    indexed_chunks += 1
            self.db.commit()
            # 阶段18后：可选批间停顿，配合小批量以遵守真实 embedding 服务的速率限制。
            if sleep_seconds:
                time.sleep(sleep_seconds)

        return VectorIndexResult(
            total_chunks=len(chunks),
            indexed_chunks=indexed_chunks,
            skipped_chunks=skipped_chunks,
            updated_chunks=updated_chunks,
            provider=self.embedding_provider.provider_name,
            model_name=self.embedding_provider.model_name,
            dimension=self.embedding_provider.dimension,
        )

    def _embed_with_retry(self, texts: list[str], max_retries: int = 0) -> list[list[float]]:
        """调用 embedding provider，对真实服务的瞬断/限流做有限次退避重试。

        ``max_retries=0`` 时行为与直接调用一致（默认，不影响既有测试）。
        """

        attempt = 0
        while True:
            try:
                return self.embedding_provider.embed_texts(texts)
            except Exception:  # noqa: BLE001 - 瞬断/限流均退避重试，最后一次再抛出
                if attempt >= max_retries:
                    raise
                time.sleep(min(60.0, 5.0 * (2**attempt)))
                attempt += 1

    def _list_chunks(self, limit: int | None = None) -> list[Chunk]:
        statement = select(Chunk).order_by(Chunk.id)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.db.scalars(statement).all())


def calculate_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def batched(items: list[T], batch_size: int) -> list[list[T]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]
