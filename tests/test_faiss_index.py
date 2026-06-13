from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, ChunkEmbedding, Document
from app.db.session import create_sqlite_engine
from app.services.retrieval.faiss_index import (
    FaissVectorIndex,
    default_faiss_paths,
    normalize_embeddings,
    safe_index_stem,
)
from app.services.retrieval.vector_index import calculate_text_hash
from scripts.build_faiss_index import list_current_embeddings


def test_faiss_index_builds_saves_loads_and_searches(tmp_path) -> None:
    index = FaissVectorIndex.build(
        embeddings=[
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.7, 0.7, 0.0],
        ],
        chunk_ids=[101, 102, 103],
        provider="deterministic",
        model_name="hash-token-v1",
        dimension=3,
    )

    matches = index.search([1.0, 0.0, 0.0], top_k=2)

    assert [match.chunk_id for match in matches] == [101, 103]
    assert matches[0].score > matches[1].score > 0

    index_path = tmp_path / "sample.index"
    metadata_path = tmp_path / "sample_ids.json"
    index.save(index_path=index_path, metadata_path=metadata_path)

    loaded = FaissVectorIndex.load(index_path=index_path, metadata_path=metadata_path)
    loaded_matches = loaded.search([0.0, 1.0, 0.0], top_k=2)

    assert [match.chunk_id for match in loaded_matches] == [102, 103]
    assert loaded.metadata.provider == "deterministic"
    assert loaded.metadata.model_name == "hash-token-v1"
    assert loaded.metadata.dimension == 3
    assert loaded.metadata.complete is True


def test_faiss_index_rejects_mismatched_lengths() -> None:
    try:
        FaissVectorIndex.build(
            embeddings=[[1.0, 0.0]],
            chunk_ids=[1, 2],
            provider="deterministic",
            model_name="hash-token-v1",
            dimension=2,
        )
    except ValueError as exc:
        assert "same length" in str(exc)
    else:
        raise AssertionError("Expected ValueError for mismatched inputs")


def test_normalize_embeddings_rejects_dimension_mismatch() -> None:
    try:
        normalize_embeddings([[1.0, 0.0, 0.0]], dimension=2)
    except ValueError as exc:
        assert "dimension" in str(exc)
    else:
        raise AssertionError("Expected ValueError for mismatched dimensions")


def test_normalize_embeddings_keeps_zero_vectors_zero() -> None:
    matrix = normalize_embeddings([[0.0, 0.0], [3.0, 4.0]], dimension=2)

    assert matrix.tolist()[0] == [0.0, 0.0]
    assert matrix.tolist()[1] == [0.6000000238418579, 0.800000011920929]


def test_default_faiss_paths_are_stable() -> None:
    index_path, metadata_path = default_faiss_paths(
        output_dir=__import__("pathlib").Path("data/faiss"),
        provider="jina",
        model_name="jina/embeddings:v3",
        dimension=1024,
    )

    assert index_path.as_posix() == "data/faiss/jina_jina_embeddings_v3_dim1024.index"
    assert metadata_path.as_posix() == "data/faiss/jina_jina_embeddings_v3_dim1024_ids.json"
    assert safe_index_stem("a/b", "c:d", 3) == "a_b_c_d_dim3"


def test_list_current_embeddings_skips_parent_chunks(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'faiss.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        document = Document(
            title="FAISS 父子块资料",
            source_type="local_file",
            source_path="faiss-parent-child.md",
            file_name="faiss-parent-child.md",
            file_extension=".md",
            content_hash="faiss-parent-child-hash",
            raw_path="data/raw/faiss-parent-child.md",
        )
        parent = Chunk(
            document=document,
            chunk_index=0,
            content="parent context only",
            char_count=19,
            heading_path="parent",
            start_char=0,
            end_char=19,
        )
        child = Chunk(
            document=document,
            chunk_index=1,
            content="child retrieval target",
            char_count=22,
            heading_path="parent",
            start_char=0,
            end_char=22,
            parent_chunk=parent,
        )
        db.add_all([document, parent, child])
        db.flush()
        db.add_all(
            [
                ChunkEmbedding(
                    chunk_id=parent.id,
                    provider="deterministic",
                    model_name="hash-token-v1",
                    dimension=2,
                    embedding_json="[1.0, 0.0]",
                    content_hash=calculate_text_hash(parent.content),
                ),
                ChunkEmbedding(
                    chunk_id=child.id,
                    provider="deterministic",
                    model_name="hash-token-v1",
                    dimension=2,
                    embedding_json="[0.0, 1.0]",
                    content_hash=calculate_text_hash(child.content),
                ),
            ]
        )
        db.commit()

        chunk_ids, embeddings = list_current_embeddings(
            db,
            provider="deterministic",
            model_name="hash-token-v1",
            dimension=2,
        )

    assert chunk_ids == [child.id]
    assert embeddings == [[0.0, 1.0]]
