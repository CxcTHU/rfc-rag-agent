"""Tests for the LLM-driven ReAct planner branch.

When a dedicated `planner_chat_provider` is passed to ReActAgentService, the
deterministic short-circuit is disabled and the planner provider is consulted
on every iteration. Tests use a scripted provider so we can exercise that
branch deterministically and without real network calls.

Behaviors covered (stage 34 LLM-driven planner change):
- LLM may refuse on iteration 1 when the question is clearly out-of-scope.
- LLM picks answer_with_citations on iteration 2 by its own decision, not by
  a hard rule; planner is called every iteration.
- LLM may continue searching across multiple iterations if it decides
  evidence is insufficient.
- Invalid planner JSON falls back to a safe action (answer when prior
  evidence exists, otherwise refuse) instead of crashing.
- When `planner_chat_provider` is NOT passed, the existing elif short-circuit
  stays in effect — backward compatibility guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Sequence

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agent.react_service import ReActAgentService
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    DeterministicChatModelProvider,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "react_llm_planner.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Rock-filled concrete filling guide",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="react-llm-planner-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Filling capacity depends on self-compacting concrete "
                    "flowability in rock-filled concrete voids."
                ),
                char_count=98,
                heading_path="Filling",
                start_char=0,
                end_char=98,
            )
        ],
    )


@dataclass
class ScriptedPlannerProvider:
    """Scripted chat provider for the planner role only.

    provider_name != 'deterministic' so the LLM branch of `_plan_action` is
    taken. Each `generate` call consumes one canned output from
    `planner_outputs` in order.
    """

    planner_outputs: list[str]
    provider_name: str = "scripted-planner"
    model_name: str = "scripted-planner-v1"

    def __post_init__(self) -> None:
        self.calls: int = 0

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        if self.calls >= len(self.planner_outputs):
            raise AssertionError(
                "scripted planner ran out of canned outputs at call "
                f"{self.calls + 1}"
            )
        answer = self.planner_outputs[self.calls]
        self.calls += 1
        return ChatModelResult(
            answer=answer,
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def stream_generate(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        yield self.generate(messages).answer


def make_service(
    db: Session,
    planner_chat_provider: ScriptedPlannerProvider | None = None,
) -> ReActAgentService:
    embedding = DeterministicEmbeddingProvider(dimension=32)
    VectorIndexService(db, embedding).build_index()
    return ReActAgentService(
        db=db,
        embedding_provider=embedding,
        chat_model_provider=DeterministicChatModelProvider(),
        log_answers=False,
        planner_chat_provider=planner_chat_provider,
    )


def test_llm_planner_can_refuse_on_iteration_1_without_searching(tmp_path) -> None:
    planner = ScriptedPlannerProvider(
        planner_outputs=[
            '{"action": "refuse", '
            '"refusal_reason": "Question is outside the rock-filled concrete scope.", '
            '"reasoning_summary": "Out of scope."}',
        ],
    )

    with make_session(tmp_path)() as db:
        seed_documents(db)
        result = make_service(db, planner_chat_provider=planner).query(
            "How do I bake a cake?",
            top_k=2,
            max_tool_calls=3,
        )

    assert result.refused
    assert result.refusal_reason == "Question is outside the rock-filled concrete scope."
    assert result.iteration_count == 1
    assert result.tool_calls == []
    assert planner.calls == 1


def test_llm_planner_searches_then_answers_when_evidence_is_sufficient(tmp_path) -> None:
    planner = ScriptedPlannerProvider(
        planner_outputs=[
            '{"action": "search_knowledge", '
            '"query": "filling capacity rock-filled concrete", '
            '"reasoning_summary": "Need evidence."}',
            '{"action": "answer_with_citations", '
            '"question": "What affects filling capacity in rock-filled concrete?", '
            '"reasoning_summary": "Evidence is sufficient."}',
        ],
    )

    with make_session(tmp_path)() as db:
        seed_documents(db)
        result = make_service(db, planner_chat_provider=planner).query(
            "What affects filling capacity in rock-filled concrete?",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.iteration_count == 2
    assert [call.tool_name for call in result.tool_calls] == [
        "hybrid_search_knowledge",
        "answer_with_citations",
    ]
    assert planner.calls == 2


def test_llm_planner_can_continue_searching_across_multiple_iterations(tmp_path) -> None:
    planner = ScriptedPlannerProvider(
        planner_outputs=[
            '{"action": "search_knowledge", '
            '"query": "filling", '
            '"reasoning_summary": "Need evidence."}',
            '{"action": "search_knowledge", '
            '"query": "rock-filled concrete flowability self-compacting", '
            '"reasoning_summary": "Refine query for better evidence."}',
            '{"action": "answer_with_citations", '
            '"question": "What affects filling capacity in rock-filled concrete?", '
            '"reasoning_summary": "Evidence is now sufficient."}',
        ],
    )

    with make_session(tmp_path)() as db:
        seed_documents(db)
        result = make_service(db, planner_chat_provider=planner).query(
            "What affects filling capacity in rock-filled concrete?",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.iteration_count == 3
    tool_names = [call.tool_name for call in result.tool_calls]
    assert tool_names.count("hybrid_search_knowledge") == 2
    assert tool_names[-1] == "answer_with_citations"
    assert planner.calls == 3


def test_llm_planner_invalid_json_falls_back_to_refuse_without_evidence(tmp_path) -> None:
    planner = ScriptedPlannerProvider(
        planner_outputs=["this is not json at all"],
    )

    with make_session(tmp_path)() as db:
        seed_documents(db)
        result = make_service(db, planner_chat_provider=planner).query(
            "What affects filling capacity in rock-filled concrete?",
            top_k=2,
            max_tool_calls=3,
        )

    assert result.refused
    assert result.refusal_reason == "Planner output was unparseable; refusing safely."
    assert result.iteration_count == 1
    assert result.tool_calls == []


def test_llm_planner_invalid_json_falls_back_to_answer_when_evidence_exists(tmp_path) -> None:
    planner = ScriptedPlannerProvider(
        planner_outputs=[
            '{"action": "search_knowledge", '
            '"query": "filling capacity", '
            '"reasoning_summary": "Need evidence."}',
            "garbled non-json planner output",
        ],
    )

    with make_session(tmp_path)() as db:
        seed_documents(db)
        result = make_service(db, planner_chat_provider=planner).query(
            "What affects filling capacity in rock-filled concrete?",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.iteration_count == 2
    assert [call.tool_name for call in result.tool_calls] == [
        "hybrid_search_knowledge",
        "answer_with_citations",
    ]


def test_without_planner_provider_elif_short_circuit_stays_active(tmp_path) -> None:
    """Backward compat: when no planner_chat_provider is passed, the existing
    deterministic short-circuit path is preserved and only deterministic
    planner is consulted (LLM branch is never reached)."""

    with make_session(tmp_path)() as db:
        seed_documents(db)
        result = make_service(db, planner_chat_provider=None).query(
            "What affects filling capacity in rock-filled concrete?",
            top_k=2,
            max_tool_calls=3,
        )

    assert not result.refused
    assert result.iteration_count == 2
    assert [call.tool_name for call in result.tool_calls] == [
        "hybrid_search_knowledge",
        "answer_with_citations",
    ]
