import json

from scripts.snapshot_phase65_agent_contract import build_contract_snapshot


def test_contract_snapshot_is_safe_and_deterministic() -> None:
    first = build_contract_snapshot()
    second = build_contract_snapshot()

    assert first == second
    assert first["schema_version"] == "phase65-contract-v1"
    assert first["agent_request_schema_sha256"]
    assert first["agent_response_schema_sha256"]
    assert first["tool_schema_sha256"]
    assert first["sse_fixture_sha256"]
    assert first["checkpoint_schema_sha256"]
    assert first["runtime_event_names"] == [
        "agent_step",
        "tool_call_result",
        "tool_call_start",
    ]

    serialized = json.dumps(first, ensure_ascii=False).casefold()
    for forbidden in (
        "answer",
        "prompt",
        "raw_response",
        "reasoning_content",
        "authorization",
        "bearer",
    ):
        assert forbidden not in serialized
