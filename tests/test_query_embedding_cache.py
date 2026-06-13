from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.query_embedding_cache import QueryEmbeddingCache, normalize_query_text
from app.services.retrieval.vector_index import VectorIndexService
from app.services.retrieval.vector_search import VectorSearchService


class CountingEmbeddingProvider:
    def __init__(
        self,
        *,
        dimension: int = 16,
        provider_name: str = "counting",
        model_name: str = "counting-model",
    ) -> None:
        self.dimension = dimension
        self.provider_name = provider_name
        self.model_name = model_name
        self.delegate = DeterministicEmbeddingProvider(
            dimension=dimension,
            provider_name=provider_name,
            model_name=model_name,
        )
        self.query_calls = 0

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return self.delegate.embed_texts(texts)

    def embed_query(self, query: str) -> list[float]:
        self.query_calls += 1
        return self.delegate.embed_query(query)


def make_session(tmp_path):
    database_path = tmp_path / "query_embedding_cache.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_documents(db) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Query cache fixture",
            source_type="local_file",
            source_path="fixture.md",
            file_name="fixture.md",
            file_extension=".md",
            content_hash="query-cache-fixture-hash",
            raw_path="data/raw/fixture.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity depends on flowability.",
                char_count=39,
                heading_path="Filling",
                start_char=0,
                end_char=39,
            )
        ],
    )


def test_normalize_query_text_collapses_outer_and_inner_whitespace() -> None:
    assert normalize_query_text("  filling   capacity \n test  ") == "filling capacity test"


def test_query_embedding_cache_reuses_same_query_embedding(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    provider = CountingEmbeddingProvider(dimension=16)
    cache = QueryEmbeddingCache(max_size=8, ttl_seconds=60)

    with TestingSessionLocal() as db:
        seed_documents(db)
        VectorIndexService(db, provider).build_index()
        provider.query_calls = 0

        service = VectorSearchService(db, provider, query_embedding_cache=cache)
        first = service.search("filling capacity", top_k=1)
        second = service.search("  filling   capacity  ", top_k=1)

    assert first
    assert second
    assert provider.query_calls == 1
    assert cache.stats().hits == 1
    assert cache.stats().misses == 1


def test_query_embedding_cache_key_separates_provider_model_and_dimension() -> None:
    cache = QueryEmbeddingCache(max_size=8, ttl_seconds=60)
    first = CountingEmbeddingProvider(dimension=16, provider_name="p1", model_name="m")
    second = CountingEmbeddingProvider(dimension=16, provider_name="p2", model_name="m")
    third = CountingEmbeddingProvider(dimension=8, provider_name="p1", model_name="m")

    cache.get_or_embed(first, "same query")
    cache.get_or_embed(first, "same   query")
    cache.get_or_embed(second, "same query")
    cache.get_or_embed(third, "same query")

    assert first.query_calls == 1
    assert second.query_calls == 1
    assert third.query_calls == 1
    assert len(cache.keys()) == 3


def test_query_embedding_cache_evicts_oldest_entry_when_capacity_is_exceeded() -> None:
    cache = QueryEmbeddingCache(max_size=1, ttl_seconds=60)
    provider = CountingEmbeddingProvider(dimension=16)

    cache.get_or_embed(provider, "first query")
    cache.get_or_embed(provider, "second query")
    cache.get_or_embed(provider, "first query")

    assert provider.query_calls == 3
    assert cache.stats().evictions == 2
