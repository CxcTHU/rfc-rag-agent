"""Safe checkpoint snapshot contract for Runtime persistence."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentRuntimeRun, utc_now
from app.services.agent.evidence_identity import (
    EXPLICIT_CONTINUE_TERMS,
    build_evidence_query_identity,
)
from app.services.retrieval.query_embedding_cache import normalize_query_text


_SENSITIVE_FIELD_MARKERS = (
    "api_key",
    "token",
    "password",
    "secret",
    "raw_response",
    "reasoning",
)

RuntimeRunStatus = Literal["running", "stopped", "completed", "failed", "expired"]


@dataclass(frozen=True)
class ResumeDecision:
    should_resume: bool
    run: AgentRuntimeRun | None = None
    reason: str = "none"


@dataclass
class RuntimeRunSnapshot:
    workflow_steps: list[dict[str, object]] = field(default_factory=list)
    tool_calls: list[dict[str, object]] = field(default_factory=list)
    search_result_chunk_ids: list[int] = field(default_factory=list)
    source_chunk_ids: list[int] = field(default_factory=list)
    evidence_state: dict[str, object] = field(default_factory=dict)
    latency_trace: dict[str, object] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "workflow_steps": self.workflow_steps[:20],
            "tool_calls": self.tool_calls[:20],
            "search_result_chunk_ids": self.search_result_chunk_ids[:50],
            "source_chunk_ids": self.source_chunk_ids[:50],
            "evidence_state": self.evidence_state,
            "latency_trace": self.latency_trace,
        }


class AgentRuntimeRunRepository:
    """Persistence adapter for bounded, resumable runtime state."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_run(
        self,
        *,
        conversation_id: int | None,
        question: str,
        canonical_task: str,
        resume_token: str | None = None,
        ttl_minutes: int = 60,
        state: dict[str, object] | None = None,
    ) -> AgentRuntimeRun:
        token = resume_token or uuid.uuid4().hex
        now = utc_now()
        run = AgentRuntimeRun(
            conversation_id=conversation_id,
            run_id=uuid.uuid4().hex,
            status="running",
            current_node="context_assembled",
            last_completed_node="context_assembled",
            resume_token_hash=hash_resume_token(token),
            request_question=normalize_query_text(question)[:500],
            canonical_task=normalize_query_text(canonical_task)[:500],
            state_json=serialize_runtime_state(state or {}),
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(minutes=max(ttl_minutes, 1)),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def persist_node(
        self,
        run: AgentRuntimeRun | None,
        *,
        node: str,
        state: dict[str, object] | None = None,
        status: RuntimeRunStatus = "running",
    ) -> None:
        if run is None:
            return
        run.current_node = node
        run.last_completed_node = node
        run.status = status
        if state is not None:
            run.state_json = serialize_runtime_state(state)
        run.updated_at = utc_now()
        self.db.commit()

    def mark_stopped(
        self, run: AgentRuntimeRun | None, *, reason: str = "user_cancelled"
    ) -> None:
        if run is None:
            return
        state = load_runtime_state(run)
        state["stop_reason"] = reason
        run.status = "stopped"
        run.current_node = "stopped"
        run.state_json = serialize_runtime_state(state)
        run.updated_at = utc_now()
        self.db.commit()

    def latest_resumable_run(self, conversation_id: int | None) -> AgentRuntimeRun | None:
        if conversation_id is None:
            return None
        statement = (
            select(AgentRuntimeRun)
            .where(AgentRuntimeRun.conversation_id == conversation_id)
            .where(AgentRuntimeRun.status == "stopped")
            .order_by(AgentRuntimeRun.updated_at.desc(), AgentRuntimeRun.id.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def latest_running_run(self, conversation_id: int | None) -> AgentRuntimeRun | None:
        if conversation_id is None:
            return None
        statement = (
            select(AgentRuntimeRun)
            .where(AgentRuntimeRun.conversation_id == conversation_id)
            .where(AgentRuntimeRun.status == "running")
            .order_by(AgentRuntimeRun.updated_at.desc(), AgentRuntimeRun.id.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def mark_latest_running_stopped(
        self, conversation_id: int | None, *, reason: str = "client_stream_aborted"
    ) -> AgentRuntimeRun | None:
        run = self.latest_running_run(conversation_id)
        if run is None:
            return None
        self.mark_stopped(run, reason=reason)
        return run


@dataclass(frozen=True)
class CheckpointSnapshot:
    workflow_steps: tuple[dict[str, object], ...]
    tool_calls: tuple[dict[str, object], ...]
    sources: tuple[dict[str, object], ...]
    completed_tool_ids: tuple[str, ...]
    safe_trace: dict[str, object]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "workflow_steps": [sanitize_checkpoint_value(item) for item in self.workflow_steps[:20]],
            "tool_calls": [sanitize_checkpoint_value(item) for item in self.tool_calls[:20]],
            "sources": [sanitize_checkpoint_value(item) for item in self.sources[:12]],
            "completed_tool_ids": [str(value)[:120] for value in self.completed_tool_ids[:20]],
            "safe_trace": sanitize_checkpoint_value(self.safe_trace),
        }

    @classmethod
    def schema_descriptor(cls) -> dict[str, object]:
        return {
            "fields": [
                "completed_tool_ids",
                "safe_trace",
                "sources",
                "tool_calls",
                "workflow_steps",
            ],
            "limits": {
                "completed_tool_ids": 20,
                "sources": 12,
                "tool_calls": 20,
                "workflow_steps": 20,
            },
        }


class CheckpointRepository:
    """Thin safe adapter around the existing database run store."""

    def __init__(self, run_store: Any) -> None:
        self._run_store = run_store

    def start(
        self,
        request: object | None = None,
        planning: object | None = None,
        *,
        conversation_id: int | None = None,
        question: str | None = None,
        canonical_task: str | None = None,
        state: dict[str, object] | None = None,
    ) -> Any:
        if request is not None:
            conversation_id = getattr(request, "conversation_id", None)
            question = str(getattr(request, "question", ""))
            canonical_task = str(getattr(planning, "canonical_task", question))
            runtime_state = getattr(planning, "runtime_state", None)
            diagnostics = getattr(runtime_state, "diagnostics", None)
            state = {"runtime_context": diagnostics()} if callable(diagnostics) else state
        return self._run_store.create_run(
            conversation_id=conversation_id,
            question=question or "",
            canonical_task=canonical_task or question or "",
            state=sanitize_checkpoint_value(state or {}),
        )

    def resume(self, request: object, planning: object | None = None) -> Any:
        resume_run_id = str(getattr(request, "resume_run_id", "") or "").strip()
        if not resume_run_id:
            return self.start(request, planning)
        db = getattr(self._run_store, "db", None)
        if db is None:
            return self.start(request, planning)
        statement = select(AgentRuntimeRun).where(AgentRuntimeRun.run_id == resume_run_id)
        conversation_id = getattr(request, "conversation_id", None)
        if conversation_id is not None:
            statement = statement.where(AgentRuntimeRun.conversation_id == conversation_id)
        run = db.scalar(statement)
        if run is None:
            return self.start(request, planning)
        return run

    def persist(
        self,
        run: Any,
        *,
        node: str,
        snapshot: CheckpointSnapshot,
        status: str = "running",
    ) -> None:
        self._run_store.persist_node(
            run,
            node=node,
            state=snapshot.to_json_dict(),
            status=status,
        )

    def persist_state(
        self,
        run: Any,
        *,
        node: str,
        state: dict[str, object] | None = None,
        status: str = "running",
    ) -> None:
        self._run_store.persist_node(
            run,
            node=node,
            state=sanitize_checkpoint_value(state or {}),
            status=status,
        )

    def complete(self, run: Any, outcome: object) -> None:
        if isinstance(outcome, dict):
            stop_reason = str(outcome.get("stop_reason") or "completed")
        else:
            stop_reason = str(getattr(outcome, "stop_reason", "completed") or "completed")
        try:
            state = load_runtime_state(run) if run is not None else {}
        except ValueError:
            state = {}
        state["stop_reason"] = stop_reason[:80]
        self.persist_state(
            run,
            node="completed",
            state=state,
            status="completed",
        )

    def completed_tool_ids(self, run: Any) -> frozenset[str]:
        if run is None:
            return frozenset()
        try:
            state = load_runtime_state(run)
        except ValueError:
            return frozenset()
        values = state.get("completed_tool_ids")
        if not isinstance(values, list | tuple):
            return frozenset()
        return frozenset(
            str(value)[:120]
            for value in values[:20]
            if str(value).strip()
        )


def sanitize_checkpoint_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return None
    if isinstance(value, dict):
        return {
            str(key)[:80]: sanitize_checkpoint_value(item, depth=depth + 1)
            for key, item in value.items()
            if not any(marker in str(key).casefold() for marker in _SENSITIVE_FIELD_MARKERS)
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_checkpoint_value(item, depth=depth + 1) for item in value[:80]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


def decide_resume(
    *,
    repository: AgentRuntimeRunRepository,
    conversation_id: int | None,
    question: str,
    history: list[str] | tuple[str, ...] = (),
    resume_policy: str = "auto",
    resume_run_id: str | None = None,
) -> ResumeDecision:
    if resume_policy == "never":
        return ResumeDecision(False, reason="resume_disabled")
    run = find_requested_or_latest_run(
        repository=repository,
        conversation_id=conversation_id,
        resume_run_id=resume_run_id,
    )
    if run is None:
        return ResumeDecision(False, reason="no_checkpoint")
    if run.expires_at is not None and as_utc(run.expires_at) <= datetime.now(timezone.utc):
        run.status = "expired"
        repository.db.commit()
        return ResumeDecision(False, run=run, reason="checkpoint_expired")
    try:
        load_runtime_state(run)
    except ValueError:
        return ResumeDecision(False, run=run, reason="checkpoint_invalid")
    if resume_policy == "force":
        return ResumeDecision(True, run=run, reason="force")
    normalized_question = normalize_query_text(question)
    if normalized_question == normalize_query_text(run.request_question):
        return ResumeDecision(True, run=run, reason="exact_retry")
    if is_explicit_continue(normalized_question):
        return ResumeDecision(True, run=run, reason="explicit_continue")
    previous_identity = build_evidence_query_identity(run.request_question, history=history)
    current_identity = build_evidence_query_identity(normalized_question, history=history)
    if (
        previous_identity.safe_for_cache_reuse
        and current_identity.safe_for_cache_reuse
        and previous_identity.entity_key == current_identity.entity_key
        and previous_identity.intent_key == current_identity.intent_key
    ):
        return ResumeDecision(True, run=run, reason="same_evidence_identity")
    return ResumeDecision(False, run=run, reason="new_topic")


def find_requested_or_latest_run(
    *,
    repository: AgentRuntimeRunRepository,
    conversation_id: int | None,
    resume_run_id: str | None,
) -> AgentRuntimeRun | None:
    if resume_run_id:
        statement = select(AgentRuntimeRun).where(AgentRuntimeRun.run_id == resume_run_id)
        if conversation_id is not None:
            statement = statement.where(AgentRuntimeRun.conversation_id == conversation_id)
        return repository.db.scalar(statement)
    return repository.latest_resumable_run(conversation_id)


def runtime_resume_diagnostics(decision: ResumeDecision) -> dict[str, object]:
    run = decision.run
    return {
        "runtime_resume_available": bool(run is not None and run.status == "stopped"),
        "runtime_resumed": decision.should_resume,
        "runtime_resume_reason": decision.reason,
        "runtime_run_id": run.run_id if run is not None else "",
        "runtime_resume_from_node": (
            run.last_completed_node if decision.should_resume and run is not None else ""
        ),
    }


def load_runtime_state(run: AgentRuntimeRun) -> dict[str, object]:
    try:
        values = json.loads(run.state_json or "{}")
    except Exception as exc:
        raise ValueError("checkpoint state is not valid JSON") from exc
    if not isinstance(values, dict):
        raise ValueError("checkpoint state must be a JSON object")
    return dict(values)


def serialize_runtime_state(state: dict[str, object]) -> str:
    return json.dumps(
        sanitize_runtime_state(state), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def sanitize_runtime_state(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return None
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(
                secret in key_text.casefold()
                for secret in ("api_key", "token", "password", "secret", "raw_response", "reasoning")
            ):
                continue
            safe[key_text[:80]] = sanitize_runtime_state(item, depth=depth + 1)
        return safe
    if isinstance(value, list):
        return [sanitize_runtime_state(item, depth=depth + 1) for item in value[:80]]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


def hash_resume_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_explicit_continue(question: str) -> bool:
    normalized = question.casefold()
    return any(term.casefold() in normalized for term in EXPLICIT_CONTINUE_TERMS)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
