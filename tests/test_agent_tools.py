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
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "agent_tools.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_agent_tool_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Filling Capacity Evaluation of Self-Compacting Concrete",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="agent-tools-filling-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity depends on self-compacting concrete flowability in prepacked rock voids.",
                char_count=88,
                heading_path="Filling",
                start_char=0,
                end_char=88,
            )
        ],
    )


def source_record(**overrides) -> SourceCreate:
    data = {
        "source_id": "rfc_source_001",
        "title": "Filling Capacity Evaluation of Self-Compacting Concrete",
        "normalized_title": "filling capacity evaluation of self-compacting concrete",
        "authors": "Example Author",
        "year": "2014",
        "venue": "Example Journal",
        "category": "filling_capacity",
        "discovered_via": "test",
        "doi": "10.123/example",
        "normalized_doi": "10.123/example",
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


def make_toolbox(db: Session) -> AgentToolbox:
    return AgentToolbox(
        db=db,
        embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        chat_model_provider=DeterministicChatModelProvider(),
        log_answers=False,
    )


class FailingEmbeddingProvider:
    provider_name = "failing-embedding"
    model_name = "failing-embedding-v1"
    dimension = 32

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("Embedding provider unavailable")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding provider unavailable")


def test_agent_toolbox_search_knowledge_returns_keyword_results(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_agent_tool_documents(db)
        result = make_toolbox(db).search_knowledge("filling capacity", top_k=3)

    assert result.tool_name == "search_knowledge"
    assert result.call.succeeded
    assert not result.refused
    assert result.search_results
    assert result.search_results[0].document_title == "Filling Capacity Evaluation of Self-Compacting Concrete"
    assert result.sources[0].source_id.startswith("chunk:")


def test_agent_toolbox_hybrid_search_uses_hybrid_tool_name_and_results(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_agent_tool_documents(db)
        VectorIndexService(db, provider).build_index()
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )

        result = toolbox.hybrid_search_knowledge("filling capacity", top_k=3)

    assert result.tool_name == "hybrid_search_knowledge"
    assert result.call.succeeded
    assert result.search_results
    assert result.sources[0].score is not None


def test_agent_toolbox_hybrid_search_reports_provider_failures(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_agent_tool_documents(db)
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=FailingEmbeddingProvider(),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )

        result = toolbox.hybrid_search_knowledge("filling capacity", top_k=3)

    assert result.tool_name == "hybrid_search_knowledge"
    assert not result.call.succeeded
    assert result.call.error == "Embedding provider unavailable"
    assert result.refused


def test_agent_toolbox_answer_with_citations_reuses_answer_service(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_agent_tool_documents(db)
        result = make_toolbox(db).answer_with_citations(
            "What affects filling capacity in rock-filled concrete?",
            retrieval_mode="hybrid",
            top_k=2,
        )

    assert result.tool_name == "answer_with_citations"
    assert result.call.succeeded
    assert not result.refused
    assert result.answer is not None
    assert result.citations == [1]
    assert result.sources


def test_agent_toolbox_list_and_get_source_detail_are_read_only_source_tools(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        SourceRepository(db).create_source(source_record())
        toolbox = make_toolbox(db)

        listed = toolbox.list_sources(limit=5)
        detailed = toolbox.get_source_detail("rfc_source_001")

    assert listed.tool_name == "list_sources"
    assert listed.call.succeeded
    assert listed.sources[0].source_id == "rfc_source_001"
    assert listed.sources[0].fulltext_permission == "metadata_only"
    assert detailed.tool_name == "get_source_detail"
    assert detailed.call.succeeded
    assert detailed.sources[0].title == "Filling Capacity Evaluation of Self-Compacting Concrete"


def test_agent_toolbox_get_source_detail_returns_auditable_failure(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = make_toolbox(db).get_source_detail("missing_source")

    assert result.refused
    assert not result.call.succeeded
    assert result.call.error == "Source missing_source was not found."
    assert result.refusal_reason == "Source missing_source was not found."


def test_agent_toolbox_rejects_invalid_tool_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        toolbox = make_toolbox(db)
        search_result = toolbox.search_knowledge("   ")
        list_result = toolbox.list_sources(limit=0)

    assert search_result.refused
    assert not search_result.call.succeeded
    assert "query" in (search_result.refusal_reason or "")
    assert list_result.refused
    assert "limit" in (list_result.refusal_reason or "")
