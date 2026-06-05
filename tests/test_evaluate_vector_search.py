import csv

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService
from scripts.evaluate_vector_search import (
    ExpectedQuery,
    evaluate_queries,
    read_expected_queries,
    read_keyword_passed,
    write_results,
)


def make_session(tmp_path):
    database_path = tmp_path / "evaluate_vector_search.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_evaluation_document(db):
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Thermal control evaluation source",
            source_type="local_file",
            source_path="thermal-evaluation.md",
            file_name="thermal-evaluation.md",
            file_extension=".md",
            content_hash="thermal-evaluation-hash",
            raw_path="data/raw/thermal-evaluation.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Thermal control reduces hydration heat in rock filled concrete.",
                char_count=63,
                heading_path="Thermal",
                start_char=0,
                end_char=63,
            )
        ],
    )


def test_evaluate_queries_marks_vector_hit_and_keyword_comparison(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_evaluation_document(db)
        VectorIndexService(db, provider).build_index()
        expected = ExpectedQuery(
            query_id="thermal_control",
            question="How to control hydration heat?",
            query="thermal control",
            top_k=3,
            expected_title_terms=["Thermal control"],
            expected_content_terms=["hydration heat"],
            expected_source_types=["local_file"],
            notes="test note",
        )

        results = evaluate_queries(
            [expected],
            db,
            provider,
            keyword_passed_by_id={"thermal_control": True},
        )

    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].keyword_passed is True
    assert results[0].comparison == "same_pass"
    assert results[0].hit_rank == 1
    assert results[0].best_score > 0
    assert results[0].provider == "deterministic"


def test_read_expected_queries_supports_top_k_override_and_split_terms(tmp_path) -> None:
    queries_path = tmp_path / "queries.csv"
    queries_path.write_text(
        "\n".join(
            [
                "query_id,question,query,top_k,expected_title_terms,expected_content_terms,expected_source_types,notes",
                "q1,Question?,thermal,8,Thermal|Hydration,heat,local_file|metadata_record,note",
            ]
        ),
        encoding="utf-8",
    )

    queries = read_expected_queries(queries_path, top_k_override=5)

    assert queries[0].top_k == 5
    assert queries[0].expected_title_terms == ["Thermal", "Hydration"]
    assert queries[0].expected_source_types == ["local_file", "metadata_record"]


def test_read_keyword_passed_and_write_results(tmp_path) -> None:
    keyword_path = tmp_path / "keyword_results.csv"
    keyword_path.write_text(
        "\n".join(
            [
                "query_id,passed",
                "q1,yes",
                "q2,no",
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "vector_results.csv"

    keyword_passed = read_keyword_passed(keyword_path)

    assert keyword_passed == {"q1": True, "q2": False}

    with make_session(tmp_path)() as db:
        provider = DeterministicEmbeddingProvider(dimension=16)
        result = evaluate_queries(
            [
                ExpectedQuery(
                    query_id="missing_index",
                    question="Question?",
                    query="thermal",
                    top_k=3,
                    expected_title_terms=["Thermal"],
                    expected_content_terms=[],
                    expected_source_types=["local_file"],
                    notes="no index",
                )
            ],
            db,
            provider,
            keyword_passed_by_id={"missing_index": False},
        )[0]

    write_results(output_path, [result])
    with output_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["query_id"] == "missing_index"
    assert rows[0]["passed"] == "no"
    assert rows[0]["keyword_passed"] == "no"
