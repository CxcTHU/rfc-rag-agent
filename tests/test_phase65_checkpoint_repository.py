from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.agent.checkpoint_repository import (
    AgentRuntimeRunRepository,
    CheckpointRepository,
    CheckpointSnapshot,
    ResumeDecision,
    decide_resume,
)


def test_checkpoint_drops_sensitive_fields_and_records_completed_tool_ids() -> None:
    snapshot = CheckpointSnapshot(
        workflow_steps=({"tool_name": "search_tables"},),
        tool_calls=({"step_id": "tool-1"},),
        sources=({"source_id": "s1"},),
        completed_tool_ids=("tool-1",),
        safe_trace={"stop_reason": "completed", "reasoning": "secret"},
    )

    payload = snapshot.to_json_dict()

    assert "reasoning" not in json.dumps(payload).casefold()
    assert payload["completed_tool_ids"] == ["tool-1"]
    assert CheckpointSnapshot.schema_descriptor()["limits"]["sources"] == 12


class RecordingRunStore:
    def __init__(self) -> None:
        self.created = None
        self.persisted = None

    def create_run(self, **kwargs):
        self.created = kwargs
        return "run-1"

    def persist_node(self, run, **kwargs) -> None:
        self.persisted = (run, kwargs)


def test_checkpoint_repository_persists_sanitized_snapshot() -> None:
    store = RecordingRunStore()
    repository = CheckpointRepository(store)
    snapshot = CheckpointSnapshot((), (), (), (), {"reasoning": "secret"})

    run = repository.start(
        conversation_id=7,
        question="问题",
        canonical_task="任务",
        state={"runtime_context": {"stop_reason": "not_stopped"}},
    )
    repository.persist(run, node="tool_execution_completed", snapshot=snapshot)

    assert run == "run-1"
    assert store.created["conversation_id"] == 7
    assert store.created["state"]["runtime_context"]["stop_reason"] == "not_stopped"
    assert store.persisted[1]["state"]["safe_trace"] == {}


def test_checkpoint_repository_persists_legacy_state_through_one_boundary() -> None:
    store = RecordingRunStore()
    repository = CheckpointRepository(store)

    repository.persist_state(
        "run-1",
        node="final_answer_completed",
        state={"raw_response": "secret", "sources": [{"source_id": "s1"}]},
        status="completed",
    )

    assert store.persisted[1]["status"] == "completed"
    assert "raw_response" not in store.persisted[1]["state"]


def test_checkpoint_repository_completes_run_with_safe_outcome_state() -> None:
    store = RecordingRunStore()
    repository = CheckpointRepository(store)

    repository.complete("run-1", {"answer": "secret", "stop_reason": "completed"})

    assert store.persisted[1]["node"] == "completed"
    assert store.persisted[1]["status"] == "completed"
    assert "answer" not in store.persisted[1]["state"]


def test_checkpoint_repository_complete_preserves_existing_safe_state() -> None:
    store = RecordingRunStore()
    repository = CheckpointRepository(store)
    run = SimpleNamespace(
        state_json=json.dumps(
            {
                "completed_tool_ids": ["runtime-retrieval-1"],
                "sources": [{"source_id": "s1"}],
                "raw_response": "secret",
            }
        )
    )

    repository.complete(run, {"answer": "secret", "stop_reason": "completed"})

    state = store.persisted[1]["state"]
    assert state["completed_tool_ids"] == ["runtime-retrieval-1"]
    assert state["sources"] == [{"source_id": "s1"}]
    assert state["stop_reason"] == "completed"
    assert "raw_response" not in state
    assert "answer" not in state


def test_checkpoint_repository_reads_completed_tool_ids_from_safe_state() -> None:
    repository = CheckpointRepository(RecordingRunStore())
    run = SimpleNamespace(
        state_json=json.dumps(
            {
                "completed_tool_ids": [
                    "runtime-retrieval-1",
                    42,
                    "",
                    "x" * 200,
                ],
                "raw_response": "secret",
            }
        )
    )

    completed = repository.completed_tool_ids(run)

    assert completed == frozenset({"runtime-retrieval-1", "42", "x" * 120})


def test_checkpoint_repository_starts_from_coordinator_request_and_planning() -> None:
    store = RecordingRunStore()
    repository = CheckpointRepository(store)

    repository.start(
        SimpleNamespace(conversation_id=9, question="问题"),
        SimpleNamespace(canonical_task="任务", runtime_state=SimpleNamespace(diagnostics=lambda: {})),
    )

    assert store.created["conversation_id"] == 9
    assert store.created["canonical_task"] == "任务"


def test_checkpoint_module_owns_legacy_run_store_and_resume_boundary() -> None:
    """The old module is compatibility-only; new callers import this boundary."""
    assert AgentRuntimeRunRepository.__module__.endswith("checkpoint_repository")
    assert ResumeDecision.__module__.endswith("checkpoint_repository")
    assert callable(decide_resume)
