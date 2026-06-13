from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, ChunkEmbeddingRepository, DocumentCreate, DocumentRepository, deserialize_embedding
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.faiss_index import FaissVectorIndex, default_faiss_paths
from app.services.retrieval.vector_cache import VectorIndexCache
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "vector_cache_faiss.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_documents(db):
    return DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="FAISS cache fixture",
            source_type="local_file",
            source_path="fixture.md",
            file_name="fixture.md",
            file_extension=".md",
            content_hash="faiss-cache-fixture-hash",
            raw_path="data/raw/fixture.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Thermal control reduces hydration heat.",
                char_count=39,
                heading_path="Thermal",
                start_char=0,
                end_char=39,
            ),
            ChunkCreate(
                chunk_index=1,
                content="Filling capacity depends on flowability.",
                char_count=39,
                heading_path="Filling",
                start_char=40,
                end_char=79,
            ),
        ],
    )


def write_faiss_index(db, provider, output_dir, complete: bool = True) -> None:
    embeddings = ChunkEmbeddingRepository(db).list_embeddings(
        provider=provider.provider_name,
        model_name=provider.model_name,
    )
    chunk_ids = [embedding.chunk_id for embedding in embeddings]
    vectors = [deserialize_embedding(embedding.embedding_json) for embedding in embeddings]
    index = FaissVectorIndex.build(
        embeddings=vectors,
        chunk_ids=chunk_ids,
        provider=provider.provider_name,
        model_name=provider.model_name,
        dimension=provider.dimension,
        complete=complete,
    )
    index_path, metadata_path = default_faiss_paths(
        output_dir=output_dir,
        provider=provider.provider_name,
        model_name=provider.model_name,
        dimension=provider.dimension,
    )
    index.save(index_path=index_path, metadata_path=metadata_path)


def test_vector_index_cache_uses_complete_faiss_index(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        seed_documents(db)
        VectorIndexService(db, provider).build_index()
        write_faiss_index(db, provider, output_dir=tmp_path / "data/faiss", complete=True)

        cache = VectorIndexCache(db, provider)
        results = cache.search(provider.embed_query("thermal control"), top_k=2)

    assert results
    assert cache._faiss_index is not None
    assert results[0].entry.chunk_index == 0


def test_vector_index_cache_ignores_incomplete_faiss_index(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        seed_documents(db)
        VectorIndexService(db, provider).build_index()
        write_faiss_index(db, provider, output_dir=tmp_path / "data/faiss", complete=False)

        cache = VectorIndexCache(db, provider)
        results = cache.search(provider.embed_query("filling capacity"), top_k=2)

    assert results
    assert cache._faiss_index is None
    assert results[0].entry.chunk_index == 1
