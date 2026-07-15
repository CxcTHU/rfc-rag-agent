"""Safe, ordered internal events with a compatibility SSE projection."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from app.services.observability.latency_trace import LatencyTrace


RuntimeEventName = Literal["agent_step", "tool_call_start", "tool_call_result"]
_ALLOWED_PAYLOAD_FIELDS: dict[str, frozenset[str]] = {
    "agent_step": frozenset({"iteration", "action", "step_summary"}),
    "tool_call_start": frozenset({"iteration", "step_id", "tool_name", "input_summary"}),
    "tool_call_result": frozenset(
        {"iteration", "step_id", "tool_name", "observation_summary", "succeeded", "skipped", "selected_count"}
    ),
}


@dataclass(frozen=True)
class RuntimeEvent:
    run_id: str
    sequence: int
    stage: str
    name: RuntimeEventName
    elapsed_ms: float
    payload: Mapping[str, object]


@dataclass(frozen=True)
class ToolCallingRuntimeEvent:
    """Temporary compatibility shape consumed by the existing SSE adapter."""

    event: str
    payload: dict[str, object]


class RuntimeEventBus:
    def __init__(
        self,
        *,
        run_id: str,
        trace: LatencyTrace | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.run_id = run_id
        self.trace = trace
        self._clock = clock
        self._started_at = clock()
        self._sequence = 0
        self._subscribers: list[Callable[[RuntimeEvent], None]] = []

    def subscribe(self, subscriber: Callable[[RuntimeEvent], None]) -> None:
        self._subscribers.append(subscriber)

    def emit(
        self,
        stage: str,
        name: RuntimeEventName,
        payload: Mapping[str, object],
    ) -> RuntimeEvent:
        self._sequence += 1
        if self.trace is not None:
            self.trace.mark_progress()
        event = RuntimeEvent(
            run_id=self.run_id,
            sequence=self._sequence,
            stage=stage,
            name=name,
            elapsed_ms=round((self._clock() - self._started_at) * 1000.0, 3),
            payload=sanitize_event_payload(name, payload),
        )
        for subscriber in tuple(self._subscribers):
            subscriber(event)
        return event


def sanitize_event_payload(name: str, payload: Mapping[str, object]) -> dict[str, object]:
    allowed = _ALLOWED_PAYLOAD_FIELDS.get(name, frozenset())
    return {
        key: value
        for key, value in payload.items()
        if key in allowed and isinstance(value, (str, int, float, bool))
    }


def project_tool_calling_event(event: RuntimeEvent) -> ToolCallingRuntimeEvent:
    return ToolCallingRuntimeEvent(event=event.name, payload=dict(event.payload))


def publish_tool_call_result(
    bus: RuntimeEventBus,
    *,
    iteration: int,
    record: object,
    selected_count: int = 0,
) -> RuntimeEvent:
    """Emit the one safe result shape shared by execution and cached paths."""
    error = getattr(record, "error", None)
    return bus.emit(
        "retrieval",
        "tool_call_result",
        {
            "iteration": iteration,
            "step_id": str(getattr(record, "step_id", "")),
            "tool_name": str(getattr(record, "tool_name", "")),
            "observation_summary": str(getattr(record, "output_summary", "")),
            "succeeded": bool(getattr(record, "succeeded", False)),
            "skipped": bool(error and "skipped" in str(error)),
            "selected_count": max(0, int(selected_count)),
        },
    )
