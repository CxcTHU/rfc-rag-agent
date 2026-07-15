from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api import agent as agent_api_module
from app.schemas.agent import AgentQueryRequest
from app.services.agent.service import AgentQueryResult
from app.services.agent import planning_policy as planning_policy_module
from app.services.agent.tool_calling_service import ToolCallingAgentService
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelResult,
    OpenAICompatibleChatModelProvider,
    record_stream_usage,
)
from app.services.observability.latency_trace import (
    LatencyTrace,
    active_agent_cache_scope,
    bind_agent_conversation_cache_scope,
    get_current_latency_trace,
    reset_current_latency_trace,
    set_current_latency_trace,
)


class _TraceObservingPlanner:
    provider_name = "remote-test"
    model_name = "remote-test-v1"

    def __init__(self) -> None:
        self.seen_trace: LatencyTrace | None = None

    def generate(self, _messages: object) -> ChatModelResult:
        self.seen_trace = get_current_latency_trace()
        return ChatModelResult(
            answer=(
                '{"entity_key":"rfc","intent_key":"test",'
                '"canonical_query":"rfc test","confidence":0.9,'
                '"safe_for_cache_reuse":false}'
            ),
            provider=self.provider_name,
            model_name=self.model_name,
        )

    def stream_generate(self, _messages: object):
        return iter(())

    def generate_with_tools(self, _messages: object, _tools: object):
        raise AssertionError("planner must not use tool generation")


class _UnusedEmbeddingProvider:
    provider_name = "test"
    model_name = "test"
    dimension = 2

    def embed_query(self, _text: str) -> list[float]:
        raise AssertionError("off-topic query must not reach retrieval")

    def embed_texts(self, _texts: list[str]) -> list[list[float]]:
        raise AssertionError("off-topic query must not reach retrieval")


def test_phase65_namespace_isolated_cache_scope_and_safe_cold_receipt() -> None:
    trace = LatencyTrace()

    bind_agent_conversation_cache_scope(
        trace,
        conversation_id=None,
        evaluation_run_namespace="phase65-baseline-run-1",
    )
    trace.set_value("retrieval_cache_hit", False)
    trace.set_value("retrieval_cache_reason", "miss")
    trace.set_value("rerank_cache_primary_hit", False)
    trace.set_value("rerank_cache_primary_reason", "miss")
    trace.set_value("tool_result_cache_hit", False)
    trace.set_value("tool_result_cache_reason", "miss")

    finalized = trace.finalize(iteration_count=1, tool_call_count=1)
    receipt = finalized["evaluation_cold_cache_receipt"]

    assert active_agent_cache_scope() == ""
    assert finalized["agent_cache_scope"].startswith("evaluation:phase65-cache-isolation-v1:")
    assert receipt == {
        "schema_version": "phase65-cold-cache-receipt-v1",
        "namespace_sha256": receipt["namespace_sha256"],
        "request_binding_sha256": receipt["request_binding_sha256"],
        "isolation_version": "phase65-cache-isolation-v1",
        "cache_miss_confirmed": True,
    }
    assert len(receipt["namespace_sha256"]) == 64
    assert len(receipt["request_binding_sha256"]) == 64
    assert "phase65-baseline-run-1" not in repr(receipt)


def test_non_evaluation_cache_scope_remains_request_or_conversation_compatible() -> None:
    request_trace = LatencyTrace()
    conversation_trace = LatencyTrace()

    bind_agent_conversation_cache_scope(request_trace, conversation_id=None)
    bind_agent_conversation_cache_scope(conversation_trace, conversation_id=42)

    assert request_trace.values["agent_cache_scope"].startswith("request:")
    assert conversation_trace.values["agent_cache_scope"] == "conversation:42"
    assert "evaluation_cold_cache_receipt" not in request_trace.finalize(
        iteration_count=0, tool_call_count=0
    )


def test_phase65_cold_receipt_accepts_cache_layers_not_used_by_the_route() -> None:
    trace = LatencyTrace()

    bind_agent_conversation_cache_scope(
        trace,
        conversation_id=None,
        evaluation_run_namespace="phase65-baseline-run-2",
    )

    receipt = trace.finalize(iteration_count=0, tool_call_count=0)[
        "evaluation_cold_cache_receipt"
    ]

    assert receipt["cache_miss_confirmed"] is True


def test_cold_run_health_capability_requires_explicit_verified_provider_receipts() -> None:
    from app.api.health import (
        phase65_model_inventory,
        phase65_usage_receipt_inventory_value,
        supports_phase65_cold_run_receipts,
    )

    configured = SimpleNamespace(
        chat_model_provider="openai-compatible",
        chat_model_name="receipt-capable-model",
        phase65_cold_run_receipts_enabled=True,
        phase65_provider_usage_receipts_verified=True,
        phase65_provider_usage_receipt_inventory="",
    )

    # A broad legacy boolean cannot prove this configured model was the one
    # that returned real usage/cost receipts.
    assert supports_phase65_cold_run_receipts(configured) is False
    configured.phase65_provider_usage_receipt_inventory = phase65_usage_receipt_inventory_value(
        phase65_model_inventory(configured)
    )
    assert supports_phase65_cold_run_receipts(configured) is True
    configured.phase65_provider_usage_receipts_verified = False
    assert supports_phase65_cold_run_receipts(configured) is False


def test_provider_usage_uses_only_explicit_provider_receipts_and_aggregates() -> None:
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        from app.services.generation.chat_model import record_provider_usage_request_started

        record_provider_usage_request_started()
        record_stream_usage(
            {
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 5,
                    "cost": 0.12,
                }
            }
        )
        record_provider_usage_request_started()
        record_stream_usage(
            {
                "usage": {
                    "input_tokens": 7,
                    "output_tokens": 11,
                    "cost": 0.08,
                }
            }
        )
    finally:
        reset_current_latency_trace(token)

    assert trace.values["provider_prompt_tokens"] == 10
    assert trace.values["provider_completion_tokens"] == 16
    assert trace.values["provider_estimated_cost"] == 0.2
    assert trace.values["provider_usage_receipt_complete"] is True


def test_provider_usage_with_missing_cost_is_not_a_complete_receipt() -> None:
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        record_stream_usage(
            {"usage": {"prompt_tokens": 3, "completion_tokens": 5, "cost": 0.12}}
        )
        record_stream_usage(
            {"usage": {"prompt_tokens": 7, "completion_tokens": 11}}
        )
    finally:
        reset_current_latency_trace(token)

    assert trace.values["provider_usage_receipt_complete"] is False


def test_planner_provider_is_bound_to_latency_trace_before_early_off_topic_return(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    planner = _TraceObservingPlanner()
    observed_traces: list[LatencyTrace | None] = []

    def capture_identity_call(*_args: object, **kwargs: object):
        observed_traces.append(get_current_latency_trace())
        return kwargs["base_identity"]

    monkeypatch.setattr(
        planning_policy_module,
        "refine_evidence_query_identity_with_llm",
        capture_identity_call,
    )
    try:
        result = ToolCallingAgentService(
            db=object(),
            embedding_provider=_UnusedEmbeddingProvider(),
            chat_model_provider=planner,
            runtime_identity_provider=planner,
            log_answers=False,
        ).query("unrelated question", resume_policy="never")
    finally:
        get_settings.cache_clear()

    assert result.refused is True
    assert observed_traces and observed_traces[0] is not None
    assert get_current_latency_trace() is None


def test_service_early_off_topic_return_includes_phase65_cold_receipt(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    planner = _TraceObservingPlanner()
    try:
        result = ToolCallingAgentService(
            db=object(),
            embedding_provider=_UnusedEmbeddingProvider(),
            chat_model_provider=planner,
            runtime_identity_provider=planner,
            log_answers=False,
        ).query(
            "unrelated question",
            resume_policy="never",
            evaluation_run_namespace="phase65-test-service-early-off-topic",
        )
    finally:
        get_settings.cache_clear()

    receipt = result.latency_trace["evaluation_cold_cache_receipt"]
    assert result.refused is True
    assert receipt["schema_version"] == "phase65-cold-cache-receipt-v1"
    assert receipt["cache_miss_confirmed"] is True
    assert len(receipt["namespace_sha256"]) == 64


def test_nonstream_provider_request_requires_one_complete_usage_receipt() -> None:
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        # These APIs intentionally do not exist before the runtime-contract fix.
        from app.services.generation.chat_model import (
            record_provider_usage_response,
            record_provider_usage_request_started,
        )

        record_provider_usage_request_started()
        record_provider_usage_response(
            {"usage": {"prompt_tokens": 3, "completion_tokens": 5, "cost": 0.12}}
        )
        record_provider_usage_request_started()
        record_provider_usage_response({"usage": {"prompt_tokens": 7, "completion_tokens": 11}})
    finally:
        reset_current_latency_trace(token)

    assert trace.values["provider_usage_request_count"] == 2
    assert trace.values["provider_usage_receipt_count"] == 1
    assert trace.values["provider_usage_receipt_complete"] is False


def test_stream_provider_request_without_final_usage_receipt_is_incomplete(monkeypatch) -> None:
    class _StreamWithoutUsage:
        def __iter__(self):
            return iter(
                [
                    b'data: {"choices":[{"delta":{"content":"answer"}}]}\n\n',
                    b"data: [DONE]\n\n",
                ]
            )

        def mark_complete(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "app.services.generation.chat_model.HTTP_JSON_CONNECTION_POOL.open_sse",
        lambda _request, **_kwargs: _StreamWithoutUsage(),
    )
    provider = OpenAICompatibleChatModelProvider(
        model_name="test-model",
        api_key="test-key",
        base_url="https://example.test/v1",
        retry_backoff_seconds=0,
    )
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        assert list(provider.stream_generate([ChatMessage(role="user", content="test")])) == ["answer"]
    finally:
        reset_current_latency_trace(token)

    assert trace.values["provider_usage_request_count"] == 1
    assert trace.values["provider_usage_receipt_count"] == 0
    assert trace.values["provider_usage_receipt_complete"] is False


def test_provider_parse_exception_invalidates_an_already_complete_usage_receipt(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.generation.chat_model.request_json_without_proxy",
        lambda *_args, **_kwargs: {
            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "cost": 0.12},
            "choices": [],
        },
    )
    provider = OpenAICompatibleChatModelProvider(
        model_name="test-model",
        api_key="test-key",
        base_url="https://example.test/v1",
        retry_backoff_seconds=0,
    )
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        with pytest.raises(RuntimeError, match="did not include choices"):
            provider.generate([ChatMessage(role="user", content="test")])
    finally:
        reset_current_latency_trace(token)

    assert trace.values["provider_usage_request_count"] == 1
    assert trace.values["provider_usage_receipt_count"] == 1
    assert trace.values["provider_usage_receipt_complete"] is False


def test_sync_and_stream_build_paths_forward_evaluation_namespace(monkeypatch) -> None:
    received: list[dict[str, object]] = []

    class CapturingService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def query(self, **kwargs: object) -> AgentQueryResult:
            received.append(kwargs)
            return AgentQueryResult(
                question=str(kwargs["question"]),
                answer="safe test answer",
                tool_calls=[],
                mode="tool_calling_agent",
                latency_trace={},
            )

    monkeypatch.setattr(agent_api_module, "ToolCallingAgentService", CapturingService)
    request = AgentQueryRequest(
        question="What affects filling capacity in rock-filled concrete?",
        evaluation_run_namespace="phase65-candidate-run-2",
    )
    provider = SimpleNamespace(provider_name="test", model_name="test-model")

    agent_api_module.query_agent(
        request=request,
        db=object(),
        current_user=None,
        chat_model_provider=provider,
        embedding_provider=provider,
    )
    agent_api_module.build_agent_query_response(
        request=request,
        db=object(),
        conversation_history=[],
        chat_model_provider=provider,
        embedding_provider=provider,
    )

    assert len(received) == 2
    assert all(
        item["evaluation_run_namespace"] == "phase65-candidate-run-2"
        for item in received
    )
