from sqlalchemy.orm import sessionmaker

import chainlit_app
from app.db.models import Base
from app.db.repositories import ConversationRepository
from app.db.session import create_sqlite_engine
from app.schemas.agent import (
    AgentQueryResponse,
    AgentSourceItem,
    AgentToolCallItem,
    AgentWorkflowStepItem,
)


def make_response() -> AgentQueryResponse:
    return AgentQueryResponse(
        question="What affects filling capacity?",
        answer="Filling capacity depends on SCC flowability [1].",
        tool_calls=[
            AgentToolCallItem(
                tool_name="answer_with_citations",
                input_summary="question",
                output_summary="answer",
                succeeded=True,
                error=None,
            )
        ],
        search_results=[],
        sources=[
            AgentSourceItem(
                source_id="chunk:1",
                title="Filling source",
                source_type="local_file",
                status=None,
                trust_level=None,
                fulltext_permission=None,
                document_id=1,
                chunk_id=1,
                chunk_index=0,
                url=None,
                doi=None,
                content="Filling capacity depends on self-compacting concrete flowability.",
                score=0.91,
            )
        ],
        citations=[1],
        refused=False,
        refusal_reason=None,
        reasoning_summary="default",
        mode="default",
        workflow_steps=[],
        iteration_count=0,
        invalid_citations=[],
        refusal_category=None,
    )


def test_parse_sse_event_reads_event_name_and_payload() -> None:
    event = chainlit_app.parse_sse_event(
        'event: token\ndata: {"text":"hello"}\n\n'
    )

    assert event is not None
    assert event.name == "token"
    assert event.payload == {"text": "hello"}


def test_sources_markdown_lists_citations_without_full_sensitive_payload() -> None:
    markdown = chainlit_app.sources_markdown(make_response())

    assert "# 引用来源" in markdown
    assert "[1] Filling source" in markdown
    assert "chunk=1" in markdown
    assert "score=0.9100" in markdown


def test_workflow_markdown_describes_default_and_agentic_paths() -> None:
    default_markdown = chainlit_app.workflow_markdown(make_response())
    agentic_response = make_response().model_copy(
        update={
            "mode": "agentic",
            "workflow_steps": [
                AgentWorkflowStepItem(
                    name="retrieve",
                    input_summary="query",
                    output_summary="1 source",
                    succeeded=True,
                    error=None,
                )
            ],
        }
    )

    assert "default AgentService" in default_markdown
    assert "retrieve - ok" in chainlit_app.workflow_markdown(agentic_response)


def test_response_metadata_keeps_display_safe_fields_only() -> None:
    metadata = chainlit_app.response_metadata(make_response())

    assert metadata == {
        "mode": "default",
        "refused": False,
        "refusal_category": None,
        "citations": [1],
        "iteration_count": 0,
        "invalid_citations": [],
    }


def test_ensure_conversation_reuses_existing_or_creates_new(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'chainlit.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        repository = ConversationRepository(db)
        first_id = chainlit_app.ensure_conversation(repository, None)
        reused_id = chainlit_app.ensure_conversation(repository, first_id)
        replacement_id = chainlit_app.ensure_conversation(repository, 999)

    assert reused_id == first_id
    assert replacement_id != first_id
