import pytest
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
from app.services.agent.service import AgentService, detect_intent, extract_source_id
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider


def make_session(tmp_path):
    database_path = tmp_path / "agent_service.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_agent_service_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Rock-filled concrete filling guide",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="agent-service-filling-hash",
            raw_path="data/raw/filling.md",
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


def source_record(**overrides) -> SourceCreate:
    data = {
        "source_id": "rfc_source_001",
        "title": "Rock-filled concrete filling guide",
        "normalized_title": "rock-filled concrete filling guide",
        "authors": "Example Author",
        "year": "2014",
        "venue": "Example Journal",
        "category": "filling_capacity",
        "discovered_via": "test",
        "doi": None,
        "normalized_doi": None,
        "url": "https://example.org/filling",
        "normalized_url": "https://example.org/filling",
        "pdf_url": None,
        "abstract": "A source about filling capacity.",
        "keywords": "rock-filled concrete; filling capacity",
        "language": "en",
        "citation_count": 10,
        "source_type": "metadata_record",
        "trust_level": "high",
        "access_rights": "metadata",
        "fulltext_permission": "metadata_only",
        "license_or_terms": None,
        "local_path": None,
        "status": "collected",
        "notes": "test source",
        "document_id": None,
    }
    data.update(overrides)
    return SourceCreate(**data)


def make_service(db: Session) -> AgentService:
    return AgentService(
        db=db,
        embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        chat_model_provider=DeterministicChatModelProvider(),
        log_answers=False,
    )


def test_agent_service_routes_answer_questions_to_citation_tool(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_agent_service_documents(db)
        result = make_service(db).query("What affects filling capacity?", top_k=2)

    assert result.tool_calls[0].tool_name == "answer_with_citations"
    assert "引用式问答" in result.reasoning_summary
    assert not result.refused
    assert result.citations == [1]
    assert result.sources


def test_agent_service_routes_search_queries_to_hybrid_search(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_agent_service_documents(db)
        result = make_service(db).query("检索 filling capacity 相关资料", top_k=2)

    assert result.tool_calls[0].tool_name == "hybrid_search_knowledge"
    assert "混合检索" in result.reasoning_summary
    assert result.search_results
    assert "找到" in result.answer


def test_agent_service_routes_source_list_and_detail_queries(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        SourceRepository(db).create_source(source_record())
        service = make_service(db)

        listed = service.query("请列出资料来源列表", top_k=3)
        detailed = service.query("查看来源详情", source_id="rfc_source_001")

    assert listed.tool_calls[0].tool_name == "list_sources"
    assert listed.sources[0].source_id == "rfc_source_001"
    assert detailed.tool_calls[0].tool_name == "get_source_detail"
    assert detailed.sources[0].title == "Rock-filled concrete filling guide"


def test_agent_service_refuses_source_detail_without_source_id(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = make_service(db).query("请查看来源详情")

    assert result.refused
    assert result.tool_calls == []
    assert "source_id" in (result.refusal_reason or "")


def test_agent_service_rejects_invalid_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        service = make_service(db)

        with pytest.raises(ValueError, match="question"):
            service.query("   ")
        with pytest.raises(ValueError, match="top_k"):
            service.query("question", top_k=0)
        with pytest.raises(ValueError, match="max_tool_calls"):
            service.query("question", max_tool_calls=0)


def test_detect_intent_and_extract_source_id_are_stable() -> None:
    assert detect_intent("search filling capacity") == "search"
    assert detect_intent("请列出资料来源") == "list_sources"
    assert detect_intent("source_id=rfc_source_001") == "get_source_detail"
    assert detect_intent("What is rock-filled concrete?") == "answer"
    assert extract_source_id("source_id=rfc_source_001") == "rfc_source_001"
