from dataclasses import fields
from inspect import signature

import pytest

from app.services.agent.runtime_ports import (
    CheckpointPort,
    EvidencePolicyPort,
    FinalAnswerPort,
    PlanningPort,
    RuntimeEventSink,
    ToolExecutionPort,
)
from app.services.agent.runtime_contracts import (
    CancellationState,
    CheckpointSession,
    CoordinatorOutcome,
    EvidenceEvaluationRequest,
)


def test_runtime_contracts_add_immutable_phase66_requests() -> None:
    request = EvidenceEvaluationRequest(
        planning=None,
        outcome=None,
        budget=None,
        cancelled=False,
        deadline_exhausted=False,
    )
    session = CheckpointSession(
        run_id="run-1",
        checkpoint_id="checkpoint-1",
        resumed=False,
    )
    cancellation = CancellationState(cancelled=True, reason="client_stream_aborted")

    assert [field.name for field in fields(EvidenceEvaluationRequest)] == [
        "planning",
        "outcome",
        "budget",
        "cancelled",
        "deadline_exhausted",
    ]
    assert cancellation.cancelled is True
    with pytest.raises(AttributeError):
        request.cancelled = True
    with pytest.raises(AttributeError):
        session.resumed = True
    with pytest.raises(AttributeError):
        cancellation.reason = "changed"


def test_coordinator_outcome_is_typed_and_immutable() -> None:
    outcome = CoordinatorOutcome(
        result=None,
        stop_reason="completed",
        final_decision="answer",
        citations=(),
        citation_repair_count=0,
        checkpoint_session=None,
        cancelled=False,
    )

    assert [field.name for field in fields(CoordinatorOutcome)] == [
        "result",
        "stop_reason",
        "final_decision",
        "citations",
        "citation_repair_count",
        "checkpoint_session",
        "cancelled",
    ]
    with pytest.raises(AttributeError):
        outcome.cancelled = True


@pytest.mark.parametrize(
    "method",
    [
        PlanningPort.plan,
        PlanningPort.escalate_once,
        ToolExecutionPort.execute,
        EvidencePolicyPort.evaluate,
        FinalAnswerPort.generate,
        FinalAnswerPort.refuse,
        CheckpointPort.start_or_resume,
        CheckpointPort.persist_tool,
        CheckpointPort.persist_terminal,
        RuntimeEventSink.emit,
    ],
)
def test_public_runtime_ports_have_no_any_annotation(method: object) -> None:
    rendered = str(signature(method))
    assert "Any" not in rendered
