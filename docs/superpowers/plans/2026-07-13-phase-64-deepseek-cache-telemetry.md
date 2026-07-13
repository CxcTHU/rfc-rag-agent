# Phase 64 DeepSeek Cache Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely record DeepSeek streamed prompt-cache usage for Phase 64 latency diagnosis without changing answer behavior.

**Architecture:** DeepSeek-only streaming requests opt into the official usage-only final SSE chunk. The shared parser reads only usage integers and writes them to the existing context-bound `LatencyTrace`; it never yields or persists the chunk content because it has none.

**Tech Stack:** Python 3.11, existing OpenAI-compatible provider, `LatencyTrace`, pytest.

## Global Constraints

- Apply `stream_options.include_usage` only to DeepSeek streaming requests.
- Retain existing output token streaming and connection-pool completion behavior.
- Never record answer text, reasoning content, raw payloads, sources, credentials, or user identifiers.
- Cache fields are diagnostic only and cannot satisfy the cold-chain gate.
- Do not stage, commit, push, tag, or create a PR.

---

### Task 1: DeepSeek usage request and parser trace

**Files:** `app/services/generation/chat_model.py`, `app/services/observability/latency_trace.py`, and `tests/test_chat_model_provider.py`.

- [ ] **Step 1: Write failing tests**

```python
def test_deepseek_stream_request_requests_usage_chunk() -> None:
    request = provider_for("https://api.deepseek.com")._build_request(messages, stream=True)
    assert json.loads(request.data)["stream_options"] == {"include_usage": True}

def test_stream_usage_updates_trace_without_yielding_content() -> None:
    trace = LatencyTrace()
    token = set_current_latency_trace(trace)
    try:
        assert list(parse_openai_compatible_stream([usage_chunk, done_chunk])) == []
    finally:
        reset_current_latency_trace(token)
    assert trace.values["provider_prompt_cache_hit_tokens"] == 12
```

- [ ] **Step 2: Run RED** — `python -m pytest tests/test_chat_model_provider.py -k "stream_usage or deepseek_stream_request" -q`; expect missing stream option and cache trace fields.

- [ ] **Step 3: Implement minimal behavior** — add `stream_options` only when `stream` and `is_deepseek_endpoint(base_url)` are both true. Parse the final usage chunk into nonnegative integers and store only the three numeric values in the active trace.

- [ ] **Step 4: Run GREEN** — `python -m pytest tests/test_chat_model_provider.py -k "stream_usage or deepseek_stream_request" -q`; expect PASS.

### Task 2: Regression and real diagnostic probe

**Files:** `data/evaluation/phase64_deepseek_cache_probe.json`, `findings.md`, `progress.md`, `handoff.md`, and `obsidian-agent开发/阶段/阶段 64 - 主流 Agent 延迟优化/01-开发记录.md`.

- [ ] **Step 1:** run `python -m pytest tests/test_chat_model_provider.py tests/test_phase64_http_stream_pool.py tests/test_phase64_short_loop.py -q --tb=short` and `git diff --check`.
- [ ] **Step 2:** run two serial, same-case B requests with official rerank, Dynamic-K and Flash; retain only cache usage integers, model label, route, source count, citation count, and timing. Stop the temporary server afterward.
- [ ] **Step 3:** document whether cache metrics are present and whether the probe is diagnostic only; do not claim a cold-chain pass.
