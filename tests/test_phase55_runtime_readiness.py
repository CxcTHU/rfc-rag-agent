from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import Base, Chunk, ChunkEmbedding, Document
from scripts.check_phase55_runtime_readiness import (
    build_runtime_rows,
    summarize,
    write_csv,
)


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_phase55_runtime_readiness_reports_db_assets_and_manual_reranker(tmp_path: Path) -> None:
    db = make_session()
    data_dir = tmp_path / "data"
    (data_dir / "images").mkdir(parents=True)
    (data_dir / "faiss").mkdir()
    (data_dir / "faiss" / "paratera_GLM-Embedding-3_dim2048.index").write_text("index", encoding="utf-8")
    (data_dir / "knowledge_graph").mkdir()
    (data_dir / "knowledge_graph" / "domain_graph.json").write_text("{}", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        app_env="production",
        auth_enabled=True,
        jwt_secret_key="x" * 32,
        embedding_dimension=2048,
        graphrag_graph_path=str(data_dir / "knowledge_graph" / "domain_graph.json"),
        reranking_enabled=True,
    )

    rows = build_runtime_rows(
        settings=settings,
        db=db,
        data_dir=data_dir,
        check_reranker=False,
        urlopen_func=lambda *args, **kwargs: FakeResponse(),
    )
    rows_by_id = {row.check_id: row for row in rows}

    assert rows_by_id["documents"].status == "ok"
    assert rows_by_id["chunks_text"].status == "ok"
    assert rows_by_id["faiss_index_files"].status == "ok"
    assert rows_by_id["reranker_health"].status == "manual"
    assert rows_by_id["pgvector_extension"].status == "warn"


def test_phase55_runtime_readiness_can_check_reranker_health(tmp_path: Path) -> None:
    db = make_session()
    settings = Settings(
        _env_file=None,
        app_env="production",
        auth_enabled=True,
        jwt_secret_key="x" * 32,
        embedding_dimension=2048,
        reranking_enabled=True,
        reranking_base_url="http://gpu-private.example.invalid:8091",
    )

    rows = build_runtime_rows(
        settings=settings,
        db=db,
        data_dir=tmp_path,
        check_reranker=True,
        urlopen_func=lambda *args, **kwargs: FakeResponse(),
    )
    rows_by_id = {row.check_id: row for row in rows}

    assert rows_by_id["reranker_health"].status == "ok"
    assert summarize(rows)["error"] >= 1  # tmp_path lacks runtime asset directories.


def test_phase55_runtime_readiness_csv_is_sanitized(tmp_path: Path) -> None:
    db = make_session()
    settings = Settings(
        _env_file=None,
        app_env="production",
        auth_enabled=True,
        jwt_secret_key="secret-value-that-must-not-appear",
        embedding_dimension=2048,
    )
    output = tmp_path / "runtime.csv"

    rows = build_runtime_rows(
        settings=settings,
        db=db,
        data_dir=tmp_path,
        check_reranker=False,
        urlopen_func=lambda *args, **kwargs: FakeResponse(),
    )
    write_csv(output, rows)
    content = output.read_text(encoding="utf-8")

    assert "secret-value-that-must-not-appear" not in content
    assert "Bearer " not in content
    assert "Authorization:" not in content
    assert "raw_response" not in content
    assert "reasoning_content" not in content


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    document = Document(
        title="doc",
        source_type="local_file",
        file_name="doc.md",
        file_extension=".md",
        content_hash="hash",
        raw_path="data/raw/doc.md",
    )
    db.add(document)
    db.flush()
    chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="content",
        char_count=7,
        chunk_type="text",
    )
    db.add(chunk)
    db.flush()
    db.add(
        ChunkEmbedding(
            chunk_id=chunk.id,
            provider="paratera",
            model_name="GLM-Embedding-3",
            dimension=2048,
            embedding_json="[0.1, 0.2]",
            content_hash="hash",
        )
    )
    db.commit()
    return db
