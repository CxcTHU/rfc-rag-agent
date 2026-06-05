import csv
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.generation.answer_service import CitationAnswerService
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    DeterministicChatModelProvider,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from scripts.evaluate_chat import (
    ExpectedChatQuery,
    evaluate_answer,
    evaluate_queries,
    read_expected_queries,
    write_results,
)


def make_session(tmp_path):
    database_path = tmp_path / "evaluate_chat.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_chat_evaluation_document(db) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Thermal control evaluation source",
            source_type="local_file",
            source_path="thermal-chat.md",
            file_name="thermal-chat.md",
            file_extension=".md",
            content_hash="thermal-chat-evaluation-hash",
            raw_path="data/raw/thermal-chat.md",
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


@dataclass(frozen=True)
class FixedChatModelProvider:
    answer: str
    provider_name: str = "fixed"
    model_name: str = "fixed-chat-v1"

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        return ChatModelResult(
            answer=self.answer,
            provider=self.provider_name,
            model_name=self.model_name,
        )


def test_evaluate_queries_marks_supported_answer_as_passed(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_chat_evaluation_document(db)
        results = evaluate_queries(
            expected_queries=[
                ExpectedChatQuery(
                    query_id="thermal_control",
                    question="thermal control",
                    top_k=3,
                    retrieval_mode="keyword",
                    min_score=0.0,
                    expected_refused=False,
                    require_sources=True,
                    require_citations=True,
                    expected_source_title_terms=["Thermal control"],
                    expected_source_content_terms=["hydration heat"],
                    forbidden_answer_terms=["unsupported claim"],
                    notes="test",
                )
            ],
            db=db,
            chat_provider=DeterministicChatModelProvider(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        )

    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].returned_answer is True
    assert results[0].refused is False
    assert results[0].source_count == 1
    assert results[0].citations == [1]
    assert results[0].citations_valid is True
    assert results[0].expected_source_hit is True


def test_evaluate_queries_marks_missing_context_refusal_as_passed(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        results = evaluate_queries(
            expected_queries=[
                ExpectedChatQuery(
                    query_id="unsupported",
                    question="lunar habitat polymer recipe",
                    top_k=3,
                    retrieval_mode="keyword",
                    min_score=0.0,
                    expected_refused=True,
                    require_sources=False,
                    require_citations=False,
                    expected_source_title_terms=[],
                    expected_source_content_terms=[],
                    forbidden_answer_terms=["lunar habitat polymer recipe"],
                    notes="test",
                )
            ],
            db=db,
            chat_provider=DeterministicChatModelProvider(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        )

    assert results[0].passed is True
    assert results[0].refused is True
    assert results[0].refusal_matched is True
    assert results[0].source_count == 0


def test_evaluate_answer_flags_missing_required_citation(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_chat_evaluation_document(db)
        answer_result = CitationAnswerService(
            db=db,
            chat_model_provider=FixedChatModelProvider("Thermal answer [99]."),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            log_answers=False,
        ).answer("thermal control", retrieval_mode="keyword")

    evaluated = evaluate_answer(
        ExpectedChatQuery(
            query_id="bad_citation",
            question="thermal control",
            top_k=3,
            retrieval_mode="keyword",
            min_score=0.0,
            expected_refused=False,
            require_sources=True,
            require_citations=True,
            expected_source_title_terms=["Thermal control"],
            expected_source_content_terms=["hydration heat"],
            forbidden_answer_terms=[],
            notes="test",
        ),
        answer_result,
    )

    assert evaluated.passed is False
    assert evaluated.citations == []
    assert evaluated.citations_valid is True


def test_read_expected_queries_and_write_results(tmp_path) -> None:
    queries_path = tmp_path / "chat_queries.csv"
    queries_path.write_text(
        "\n".join(
            [
                ",".join(
                    [
                        "query_id",
                        "question",
                        "top_k",
                        "retrieval_mode",
                        "min_score",
                        "expected_refused",
                        "require_sources",
                        "require_citations",
                        "expected_source_title_terms",
                        "expected_source_content_terms",
                        "forbidden_answer_terms",
                        "notes",
                    ]
                ),
                "q1,thermal control,3,keyword,0,no,yes,yes,Thermal|Heat,hydration heat,forbidden,note",
            ]
        ),
        encoding="utf-8",
    )

    expected = read_expected_queries(queries_path, top_k_override=7)

    assert expected[0].top_k == 7
    assert expected[0].retrieval_mode == "keyword"
    assert expected[0].require_sources is True
    assert expected[0].expected_source_title_terms == ["Thermal", "Heat"]

    output_path = tmp_path / "chat_results.csv"
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        results = evaluate_queries(
            expected_queries=expected,
            db=db,
            chat_provider=DeterministicChatModelProvider(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        )
    write_results(output_path, results)
    with output_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["query_id"] == "q1"
    assert rows[0]["passed"] == "no"
    assert "returned_answer" in rows[0]
