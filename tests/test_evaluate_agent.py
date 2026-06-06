import csv

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    DocumentCreate,
    DocumentRepository,
    SourceCreate,
    SourceRepository,
)
from app.db.session import create_sqlite_engine
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from scripts.evaluate_agent import (
    ExpectedAgentQuery,
    evaluate_queries,
    read_expected_queries,
    write_results,
)


def make_session(tmp_path):
    database_path = tmp_path / "evaluate_agent.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_agent_evaluation_data(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Agent evaluation filling source",
            source_type="local_file",
            source_path="agent-eval-filling.md",
            file_name="agent-eval-filling.md",
            file_extension=".md",
            content_hash="agent-evaluation-filling-hash",
            raw_path="data/raw/agent-eval-filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity depends on self-compacting concrete flowability in rock-filled concrete.",
                char_count=86,
                heading_path="Filling",
                start_char=0,
                end_char=86,
            )
        ],
    )
    SourceRepository(db).create_source(
        SourceCreate(
            source_id="agent_eval_source",
            title="Agent evaluation filling source",
            normalized_title="agent evaluation filling source",
            authors="Example Author",
            year="2014",
            venue="Example Journal",
            category="filling_capacity",
            discovered_via="test",
            doi=None,
            normalized_doi=None,
            url="https://example.org/agent-eval-filling",
            normalized_url="https://example.org/agent-eval-filling",
            pdf_url=None,
            abstract="A source about filling capacity.",
            keywords="rock-filled concrete; filling capacity",
            language="en",
            citation_count=10,
            source_type="metadata_record",
            trust_level="high",
            access_rights="metadata",
            fulltext_permission="metadata_only",
            license_or_terms=None,
            local_path=None,
            status="collected",
            notes="test source",
            document_id=None,
        )
    )


def test_evaluate_agent_marks_answer_and_search_queries_as_passed(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_agent_evaluation_data(db)
        results = evaluate_queries(
            expected_queries=[
                ExpectedAgentQuery(
                    query_id="answer",
                    question="What affects filling capacity?",
                    top_k=3,
                    source_id=None,
                    expected_tool="answer_with_citations",
                    expected_refused=False,
                    require_sources=True,
                    require_citations=True,
                    expected_source_title_terms=["filling"],
                    expected_source_content_terms=["flowability"],
                    notes="answer",
                ),
                ExpectedAgentQuery(
                    query_id="search",
                    question="检索 filling capacity 相关资料",
                    top_k=3,
                    source_id=None,
                    expected_tool="hybrid_search_knowledge",
                    expected_refused=False,
                    require_sources=True,
                    require_citations=False,
                    expected_source_title_terms=["filling"],
                    expected_source_content_terms=["flowability"],
                    notes="search",
                ),
            ],
            db=db,
            chat_provider=DeterministicChatModelProvider(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        )

    assert [result.passed for result in results] == [True, True]
    assert results[0].actual_tools == ["answer_with_citations"]
    assert results[0].citations == [1]
    assert results[1].actual_tools == ["hybrid_search_knowledge"]


def test_evaluate_agent_marks_missing_source_refusal_as_passed(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = evaluate_queries(
            expected_queries=[
                ExpectedAgentQuery(
                    query_id="missing_source",
                    question="查看来源详情",
                    top_k=3,
                    source_id="missing_source",
                    expected_tool="get_source_detail",
                    expected_refused=True,
                    require_sources=False,
                    require_citations=False,
                    expected_source_title_terms=[],
                    expected_source_content_terms=[],
                    notes="missing",
                )
            ],
            db=db,
            chat_provider=DeterministicChatModelProvider(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        )[0]

    assert result.passed is True
    assert result.refused is True
    assert result.tool_matched is True
    assert result.refusal_matched is True


def test_read_expected_agent_queries_and_write_results(tmp_path) -> None:
    queries_path = tmp_path / "agent_queries.csv"
    queries_path.write_text(
        "\n".join(
            [
                ",".join(
                    [
                        "query_id",
                        "question",
                        "top_k",
                        "source_id",
                        "expected_tool",
                        "expected_refused",
                        "require_sources",
                        "require_citations",
                        "expected_source_title_terms",
                        "expected_source_content_terms",
                        "notes",
                    ]
                ),
                "q1,检索 filling capacity,3,,hybrid_search_knowledge,no,yes,no,Filling,flowability,note",
            ]
        ),
        encoding="utf-8",
    )

    expected = read_expected_queries(queries_path, top_k_override=7)

    assert expected[0].top_k == 7
    assert expected[0].expected_tool == "hybrid_search_knowledge"
    assert expected[0].require_sources is True
    assert expected[0].expected_source_title_terms == ["Filling"]

    output_path = tmp_path / "agent_results.csv"
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
    assert "actual_tools" in rows[0]
    assert "tool_call_count" in rows[0]
