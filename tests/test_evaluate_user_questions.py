import csv

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService
from scripts.evaluate_user_questions import (
    ExpectedUserQuestion,
    build_named_configs,
    evaluate_questions,
    read_expected_questions,
    write_results,
)


def make_session(tmp_path):
    database_path = tmp_path / "evaluate_user_questions.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_user_question_document(db) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Thermal control user question source",
            source_type="local_file",
            source_path="thermal-user.md",
            file_name="thermal-user.md",
            file_extension=".md",
            content_hash="thermal-user-evaluation-hash",
            raw_path="data/raw/thermal-user.md",
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


def expected_supported_question() -> ExpectedUserQuestion:
    return ExpectedUserQuestion(
        query_id="user_thermal",
        question="thermal control",
        language_type="en",
        top_k=3,
        retrieval_mode="hybrid",
        expected_source_hit=True,
        expected_refused=False,
        expected_source_title_terms=["Thermal"],
        expected_source_content_terms=["hydration heat"],
        expected_answer_points="thermal control and hydration heat",
        forbidden_answer_terms=["unsupported claim"],
        notes="test",
    )


def expected_unsupported_question() -> ExpectedUserQuestion:
    return ExpectedUserQuestion(
        query_id="user_unsupported",
        question="zqxjvblorptasticprotocol",
        language_type="unsupported",
        top_k=3,
        retrieval_mode="hybrid",
        expected_source_hit=False,
        expected_refused=True,
        expected_source_title_terms=[],
        expected_source_content_terms=[],
        expected_answer_points="should refuse",
        forbidden_answer_terms=["zqxjvblorptasticprotocol"],
        notes="test",
    )


def test_read_expected_questions_and_named_configs(tmp_path) -> None:
    queries_path = tmp_path / "user_questions.csv"
    queries_path.write_text(
        "\n".join(
            [
                ",".join(
                    [
                        "query_id",
                        "question",
                        "language_type",
                        "top_k",
                        "retrieval_mode",
                        "expected_source_hit",
                        "expected_refused",
                        "expected_source_title_terms",
                        "expected_source_content_terms",
                        "expected_answer_points",
                        "forbidden_answer_terms",
                        "notes",
                    ]
                ),
                "q1,thermal control,en,3,hybrid,yes,no,Thermal,hydration heat,thermal point,forbidden,note",
            ]
        ),
        encoding="utf-8",
    )

    expected = read_expected_questions(queries_path, top_k_override=5)
    configs = build_named_configs(expected[0])

    assert expected[0].top_k == 5
    assert expected[0].language_type == "en"
    assert expected[0].expected_source_hit is True
    assert [config.name for config in configs] == [
        "default_hybrid",
        "keyword_baseline",
        "vector_only",
    ]


def test_evaluate_user_questions_runs_required_configs(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        embedding_provider = DeterministicEmbeddingProvider(dimension=32)
        seed_user_question_document(db)
        VectorIndexService(db, embedding_provider).build_index()
        results = evaluate_questions(
            expected_questions=[
                expected_supported_question(),
                expected_unsupported_question(),
            ],
            db=db,
            chat_provider=DeterministicChatModelProvider(),
            embedding_provider=embedding_provider,
        )

    assert len(results) == 6
    assert {result.config_name for result in results} == {
        "default_hybrid",
        "keyword_baseline",
        "vector_only",
    }
    assert all(result.language_type in {"en", "unsupported"} for result in results)
    assert all(result.returned_answer for result in results)
    assert all(result.refusal_matched for result in results)
    unsupported_results = [result for result in results if result.query_id == "user_unsupported"]
    assert all(result.source_hit_matched for result in unsupported_results)


def test_write_user_question_results_includes_quality_fields(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        embedding_provider = DeterministicEmbeddingProvider(dimension=32)
        seed_user_question_document(db)
        VectorIndexService(db, embedding_provider).build_index()
        results = evaluate_questions(
            expected_questions=[expected_supported_question()],
            db=db,
            chat_provider=DeterministicChatModelProvider(),
            embedding_provider=embedding_provider,
        )

    output_path = tmp_path / "user_question_results.csv"
    write_results(output_path, results)

    with output_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["query_id"] == "user_thermal"
    assert "language_type" in rows[0]
    assert "failed_reason" in rows[0]
    assert "expected_answer_points" in rows[0]
