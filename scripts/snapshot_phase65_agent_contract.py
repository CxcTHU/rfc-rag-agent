"""Build a safe Phase 65 public contract snapshot.

The snapshot intentionally stores only canonical hashes and bounded enum/shape
metadata. It must not persist user questions, generated answers, prompts,
provider payloads, credentials, or evidence text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, get_args

from app.schemas.agent import AgentQueryRequest, AgentQueryResponse
from app.services.agent.checkpoint_repository import CheckpointSnapshot
from app.services.agent.runtime_events import RuntimeEventName
from app.services.agent.tool_calling_service import tool_calling_tool_definitions


SSE_CONTRACT_FIXTURE: tuple[dict[str, object], ...] = (
    {
        "event": "agent_step",
        "payload_fields": ("action", "iteration", "step_summary"),
    },
    {
        "event": "tool_call_start",
        "payload_fields": ("input_summary", "iteration", "step_id", "tool_name"),
    },
    {
        "event": "tool_call_result",
        "payload_fields": (
            "iteration",
            "observation_summary",
            "selected_count",
            "skipped",
            "step_id",
            "succeeded",
            "tool_name",
        ),
    },
    {"event": "token", "payload_fields": ("content",)},
    {
        "event": "metadata",
        "payload_fields": (
            "conversation_id",
            "latency_trace",
            "refused",
            "sources_count",
        ),
    },
    {"event": "done", "payload_fields": ()},
)

FORBIDDEN_SNAPSHOT_TERMS = (
    "answer",
    "prompt",
    "raw_response",
    "reasoning_content",
    "authorization",
    "bearer",
)


def canonicalize(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return canonicalize(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    return value


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_contract_snapshot() -> dict[str, object]:
    tool_definitions = [asdict(definition) for definition in tool_calling_tool_definitions()]
    snapshot: dict[str, object] = {
        "schema_version": "phase65-contract-v1",
        "agent_request_schema_sha256": canonical_sha256(
            AgentQueryRequest.model_json_schema()
        ),
        "agent_response_schema_sha256": canonical_sha256(
            AgentQueryResponse.model_json_schema()
        ),
        "tool_schema_sha256": canonical_sha256(tool_definitions),
        "sse_fixture_sha256": canonical_sha256(SSE_CONTRACT_FIXTURE),
        "checkpoint_schema_sha256": canonical_sha256(
            CheckpointSnapshot.schema_descriptor()
        ),
        "runtime_event_names": sorted(str(name) for name in get_args(RuntimeEventName)),
    }
    assert_snapshot_safe(snapshot)
    return snapshot


def assert_snapshot_safe(snapshot: dict[str, object]) -> None:
    serialized = json.dumps(snapshot, ensure_ascii=False).casefold()
    forbidden = [term for term in FORBIDDEN_SNAPSHOT_TERMS if term in serialized]
    if forbidden:
        raise ValueError(
            "contract snapshot contains forbidden term(s): "
            + ", ".join(sorted(forbidden))
        )


def write_snapshot(path: Path) -> dict[str, object]:
    snapshot = build_contract_snapshot()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/evaluation/phase65_contract_snapshot.json"),
        help="Safe JSON snapshot output path.",
    )
    args = parser.parse_args(argv)
    snapshot = write_snapshot(args.out)
    print(
        "schema_version={schema_version} runtime_event_names={runtime_event_names}".format(
            **snapshot
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
