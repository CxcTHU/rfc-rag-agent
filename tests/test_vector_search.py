from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService
from app.services.retrieval.vector_search import VectorSearchService, cosine_similarity


def make_session(tmp_path):
    database_path = tmp_path / "vector_search.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


class ConstantEmbeddingProvider:
    provider_name = "constant"
    model_name = "constant-v1"
    dimension = 2

    def embed_texts(self, texts):
        return [[1.0, 0.0] for _text in texts]

    def embed_query(self, query):
        return [1.0, 0.0]


def seed_search_documents(db):
    repository = DocumentRepository(db)
    return repository.create_with_chunks(
        DocumentCreate(
            title="Thermal control guide",
            source_type="local_file",
            source_path="thermal.md",
            file_name="thermal.md",
            file_extension=".md",
            content_hash="thermal-vector-search-hash",
            raw_path="data/raw/thermal.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Thermal control reduces hydration heat in rock filled concrete.",
                char_count=63,
                heading_path="Thermal",
                start_char=0,
                end_char=63,
            ),
            ChunkCreate(
                chunk_index=1,
                content="Filling capacity depends on self compacting concrete flowability.",
                char_count=65,
                heading_path="Filling",
                start_char=64,
                end_char=129,
            ),
        ],
    )


def test_vector_search_returns_most_similar_indexed_chunk(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_search_documents(db)
        VectorIndexService(db, provider).build_index()

        results = VectorSearchService(db, provider).search("thermal control", top_k=2)

    assert len(results) >= 1
    assert results[0].document_title == "Thermal control guide"
    assert results[0].chunk_index == 0
    assert "Thermal control" in results[0].content
    assert 0 < results[0].score <= 1


def test_vector_search_returns_empty_when_index_is_missing(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        seed_search_documents(db)

        results = VectorSearchService(db, provider).search("thermal control", top_k=3)

    assert results == []


def test_vector_search_reranks_vector_ties_by_topic_anchor(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = ConstantEmbeddingProvider()
        seed_search_documents(db)
        VectorIndexService(db, provider).build_index()

        results = VectorSearchService(db, provider).search("filling capacity", top_k=2)

    assert results[0].chunk_index == 1
    assert "Filling capacity" in results[0].content


def test_vector_search_skips_stale_embeddings(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        document = seed_search_documents(db)
        VectorIndexService(db, provider).build_index()

        chunk = DocumentRepository(db).list_chunks(document.id)[0]
        chunk.content = "This chunk has changed and must be re-indexed before vector search."
        db.commit()

        results = VectorSearchService(db, provider).search("thermal control", top_k=3)

    assert all(result.chunk_index != 0 for result in results)


def test_vector_search_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        service = VectorSearchService(db, provider)

        try:
            service.search("   ")
        except ValueError as exc:
            assert "query" in str(exc)
        else:
            raise AssertionError("Expected ValueError for empty query")

        try:
            service.search("thermal", top_k=0)
        except ValueError as exc:
            assert "top_k" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid top_k")


def test_cosine_similarity_handles_basic_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
