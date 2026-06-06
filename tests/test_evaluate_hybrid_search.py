import csv

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate
from app.db.repositories import DocumentCreate
from app.db.repositories import DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService
from scripts.evaluate_hybrid_search import ExpectedQuery
from scripts.evaluate_hybrid_search import compare_with_baselines
from scripts.evaluate_hybrid_search import evaluate_queries
from scripts.evaluate_hybrid_search import read_passed_by_id
from scripts.evaluate_hybrid_search import write_results


def make_session(tmp_path):
    database_path = tmp_path / "evaluate_hybrid_search.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_document(db):
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Filling Capacity Evaluation source",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="evaluate-hybrid-filling-hash",
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
            )
        ],
    )


def test_evaluate_queries_marks_hybrid_hit_and_rescue(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_document(db)
        VectorIndexService(db, provider).build_index()
        expected = ExpectedQuery(
            query_id="filling",
            question="Question?",
            query="filling capacity",
            top_k=3,
            expected_title_terms=["Filling Capacity"],
            expected_content_terms=[],
            expected_source_types=["local_file"],
            notes="test note",
        )

        results = evaluate_queries(
            [expected],
            db,
            provider,
            keyword_passed_by_id={"filling": True},
            vector_passed_by_id={"filling": False},
        )

    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].comparison == "hybrid_rescued_vector"
    assert results[0].hit_rank == 1
    assert results[0].keyword_passed is True
    assert results[0].vector_passed is False


def test_read_passed_by_id_and_write_results(tmp_path) -> None:
    passed_path = tmp_path / "results.csv"
    passed_path.write_text("query_id,passed\nq1,yes\nq2,no\n", encoding="utf-8")
    output_path = tmp_path / "hybrid_results.csv"

    assert read_passed_by_id(passed_path) == {"q1": True, "q2": False}

    with make_session(tmp_path)() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        result = evaluate_queries(
            [
                ExpectedQuery(
                    query_id="missing",
                    question="Question?",
                    query="filling",
                    top_k=3,
                    expected_title_terms=["Filling"],
                    expected_content_terms=[],
                    expected_source_types=["local_file"],
                    notes="no docs",
                )
            ],
            db,
            provider,
            keyword_passed_by_id={"missing": False},
            vector_passed_by_id={"missing": False},
        )[0]

    write_results(output_path, [result])
    with output_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["query_id"] == "missing"
    assert rows[0]["passed"] == "no"
    assert rows[0]["comparison"] == "all_fail"


def test_compare_with_baselines_labels_key_outcomes() -> None:
    assert compare_with_baselines(True, True, True) == "all_pass"
    assert compare_with_baselines(True, True, False) == "hybrid_rescued_vector"
    assert compare_with_baselines(False, True, False) == "hybrid_regressed_keyword"
    assert compare_with_baselines(False, False, True) == "hybrid_regressed_vector"
