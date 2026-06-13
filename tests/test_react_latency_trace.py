from tests.test_agent_api import make_test_client
from tests.test_agent_stream_api import parse_sse_events


LATENCY_FIELDS = [
    "query_embedding_latency_ms",
    "vector_search_latency_ms",
    "rerank_latency_ms",
    "planner_latency_ms",
    "answer_latency_ms",
    "tool_latency_ms",
    "time_to_first_token_ms",
    "time_to_final_ms",
    "iteration_count",
    "tool_call_count",
]


def test_react_agent_response_includes_safe_latency_trace(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post(
            "/agent/query",
            json={
                "question": "What affects filling capacity in rock-filled concrete?",
                "top_k": 2,
                "max_tool_calls": 3,
                "mode": "react_agent",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    trace = payload["latency_trace"]

    for field in LATENCY_FIELDS:
        assert field in trace

    assert trace["iteration_count"] == payload["iteration_count"]
    assert trace["tool_call_count"] == len(payload["tool_calls"])
    assert trace["time_to_final_ms"] >= 0
    assert trace["planner_latency_ms"] >= 0
    assert trace["tool_latency_ms"] >= 0

    serialized = str(trace)
    for forbidden in [
        "hidden thought",
        "reasoning_content",
        "raw_response",
        "Bearer",
        "Authorization",
        "api_key",
    ]:
        assert forbidden not in serialized


def test_react_agent_stream_metadata_includes_time_to_first_token(tmp_path) -> None:
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
    metadata = next(payload for name, payload in events if name == "metadata")
    trace = metadata["latency_trace"]

    assert trace["time_to_first_token_ms"] is not None
    assert trace["time_to_first_token_ms"] >= 0
    assert trace["time_to_final_ms"] >= 0
    assert trace["iteration_count"] == metadata["iteration_count"]
    assert trace["tool_call_count"] == len(metadata["tool_calls"])
