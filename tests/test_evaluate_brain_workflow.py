import csv

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService
from scripts.evaluate_chat import ExpectedChatQuery
from scripts.evaluate_brain_workflow import (
    build_named_configs,
    evaluate_queries,
    write_results,
)


def make_session(tmp_path):
    database_path = tmp_path / "evaluate_brain_workflow.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_brain_evaluation_document(db) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Thermal Brain workflow source",
            source_type="local_file",
            source_path="thermal-brain.md",
            file_name="thermal-brain.md",
            file_extension=".md",
            content_hash="thermal-brain-evaluation-hash",
            raw_path="data/raw/thermal-brain.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Thermal control reduces hydration heat in rock-filled concrete dams.",
                char_count=68,
                heading_path="Thermal",
                start_char=0,
                end_char=68,
            )
        ],
    )


def expected_thermal_query() -> ExpectedChatQuery:
    return ExpectedChatQuery(
        query_id="thermal_control",
        question="thermal control",
        top_k=3,
        retrieval_mode="keyword",
        min_score=0.0,
        expected_refused=False,
        require_sources=True,
        require_citations=True,
        expected_source_title_terms=["Thermal"],
        expected_source_content_terms=["hydration heat"],
        forbidden_answer_terms=["unsupported claim"],
        notes="test",
    )


def test_build_named_configs_compares_required_modes() -> None:
    configs = build_named_configs(expected_thermal_query())

    assert [config.name for config in configs] == [
        "default_hybrid",
        "keyword_baseline",
        "vector_only",
    ]
    assert [config.retrieval_config.retrieval_mode for config in configs] == [
        "hybrid",
        "keyword",
        "vector",
    ]


def test_evaluate_brain_workflow_runs_all_configs(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        embedding_provider = DeterministicEmbeddingProvider(dimension=32)
        seed_brain_evaluation_document(db)
        VectorIndexService(db, embedding_provider).build_index()

        results = evaluate_queries(
            expected_queries=[expected_thermal_query()],
            db=db,
            chat_provider=DeterministicChatModelProvider(),
            embedding_provider=embedding_provider,
        )

    assert len(results) == 3
    assert {result.config_name for result in results} == {
        "default_hybrid",
        "keyword_baseline",
        "vector_only",
    }
    assert all(result.workflow_steps.endswith("generate_answer") for result in results)
    assert all(result.workflow_succeeded for result in results)
    assert all(result.returned_answer for result in results)


def test_write_brain_workflow_results(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        embedding_provider = DeterministicEmbeddingProvider(dimension=32)
        seed_brain_evaluation_document(db)
        VectorIndexService(db, embedding_provider).build_index()
        results = evaluate_queries(
            expected_queries=[expected_thermal_query()],
            db=db,
            chat_provider=DeterministicChatModelProvider(),
            embedding_provider=embedding_provider,
        )

    output_path = tmp_path / "brain_workflow_results.csv"
    write_results(output_path, results)

    with output_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["config_name"] == "default_hybrid"
    assert "workflow_steps" in rows[0]
    assert "actual_retrieval_mode" in rows[0]
