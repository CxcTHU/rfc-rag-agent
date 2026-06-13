from tests.test_agent_stream_api import parse_sse_events
from tests.test_agent_api import make_test_client


def test_react_agent_stream_emits_step_and_tool_events_before_metadata(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 2,
                "max_tool_calls": 3,
                "mode": "react_agent",
            },
        )

    assert response.status_code == 200
    events = parse_sse_events(response.text)
    event_names = [name for name, _payload in events]

    assert "agent_step" in event_names
    assert "tool_call_start" in event_names
    assert "tool_call_result" in event_names
    assert "token" in event_names
    assert event_names.index("agent_step") < event_names.index("metadata")
    assert event_names[-2:] == ["metadata", "done"]

    metadata = next(payload for name, payload in events if name == "metadata")
    assert metadata["mode"] == "react_agent"
    assert metadata["workflow_steps"]
    assert metadata["tool_calls"]
    assert metadata["citations"] == [1]


def test_react_agent_stream_events_are_sanitized(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query/stream",
            json={
                "question": "What affects filling capacity?",
                "top_k": 2,
                "max_tool_calls": 3,
                "mode": "react_agent",
            },
        )

    assert response.status_code == 200
    events = parse_sse_events(response.text)
    react_payloads = [
        payload
        for name, payload in events
        if name in {"agent_step", "tool_call_start", "tool_call_result"}
    ]
    serialized = " ".join(str(payload) for payload in react_payloads)

    assert "secret" not in serialized
    assert "credential" not in serialized
    assert "sensitive" not in serialized
