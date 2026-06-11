from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_cache import VectorIndexCache
from app.services.retrieval.vector_index import VectorIndexService
from app.services.retrieval.vector_search import VectorSearchService, cosine_similarity


def make_session(tmp_path):
    database_path = tmp_path / "vector_cache.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_cache_documents(db, *, title: str = "Filling capacity guide") -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title=title,
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash=f"{title}-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity depends on self compacting concrete flowability.",
                char_count=65,
                heading_path="Filling",
                start_char=0,
                end_char=65,
            ),
        ],
    )


def test_vector_index_cache_matches_python_cosine_similarity(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_cache_documents(db)
        VectorIndexService(db, provider).build_index()
        query_embedding = provider.embed_query("filling capacity")
        expected_embedding = provider.embed_texts(
            ["Filling capacity depends on self compacting concrete flowability."]
        )[0]

        matches = VectorIndexCache(db, provider).search(query_embedding, top_k=1)

    assert len(matches) == 1
    assert abs(matches[0].score - cosine_similarity(query_embedding, expected_embedding)) < 1e-6


def test_vector_index_cache_reuses_loaded_matrix(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        seed_cache_documents(db)
        VectorIndexService(db, provider).build_index()
        cache = VectorIndexCache(db, provider)

        first = cache.search(provider.embed_query("filling capacity"), top_k=1)
        second = cache.search(provider.embed_query("filling capacity"), top_k=1)

    assert first[0].entry.chunk_id == second[0].entry.chunk_id
    assert abs(first[0].score - second[0].score) < 1e-12


def test_vector_index_service_invalidates_global_cache_after_update(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        seed_cache_documents(db)
        VectorIndexService(db, provider).build_index()

        initial = VectorSearchService(db, provider).search("filling capacity", top_k=3)
        seed_cache_documents(db, title="Second filling capacity guide")
        VectorIndexService(db, provider).build_index()
        refreshed = VectorSearchService(db, provider).search("filling capacity", top_k=3)

    assert len(initial) == 1
    assert len(refreshed) == 2
