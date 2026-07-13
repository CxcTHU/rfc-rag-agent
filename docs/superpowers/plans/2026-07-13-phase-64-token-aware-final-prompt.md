# Phase 64 Token-Aware Final Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure and bound the B final RAG prompt by deterministic estimated token units, reducing real-evidence first-token latency without changing retrieval quality controls.

**Architecture:** The existing final-prompt builder remains the single constructor. A numeric `FinalPromptShape` reports aggregate content shape only. B gets an optional ceiling through `phase64_final_prompt_budgets()` and uses Dynamic-K's configured maximum only as a safety bound, while A receives no new argument.

**Tech Stack:** Python 3.11, FastAPI/SSE latency trace, existing agent prompt builder, pytest, frozen Phase 64 evaluator.

## Global Constraints

- Keep the 75-candidate pool, Dynamic-K's actual 4–12 selected-source range and ordering, official `zhipu / rerank`, strict pgvector, and cold-cache contract unchanged.
- Do not change user-selected Flash/Pro routing or expose a public tuning control.
- Do not put prompt text, source text, titles, answers, provider payloads, hidden reasoning, or credentials in traces, tests, data artifacts, or docs.
- A (`AGENT_SHORT_LOOP_ENABLED=false`) must not receive the token ceiling or modified prompt construction.
- Do not add dependencies or perform Git submission actions.

---

### Task 1: Add safe B final-prompt shape observation

**Files:** `app/services/agent/tool_calling_service.py`, `app/services/observability/latency_trace.py`, `tests/test_phase64_short_loop.py`, and `tests/test_phase64_latency_trace.py`.

- [ ] **Step 1: Write the failing tests**

```python
def test_final_prompt_shape_is_numeric_and_cjk_sensitive() -> None:
    shape = FinalPromptShape()
    evidence_answer_messages("问题", sources=[source_with_content("中文证据" * 40)], prompt_shape=shape)
    assert shape.source_count == 1
    assert shape.cjk_character_count > 0
    assert shape.estimated_input_tokens > 0
    assert "中文证据" not in str(shape.as_trace_values())

def test_b_trace_records_final_prompt_shape(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "true")
    assert build_short_loop_service(tmp_path, provider).query("堆石混凝土优势").latency_trace["final_prompt_estimated_input_tokens"] > 0
```

- [ ] **Step 2: Run RED** — `python -m pytest tests/test_phase64_short_loop.py -k final_prompt_shape -q`; expect a missing collector/trace-field failure.

- [ ] **Step 3: Implement minimal observation** — add `FinalPromptShape` with character, CJK, source, history, and estimated-token integers plus `as_trace_values()`. Fill it after existing clipping; pass it only from B final streaming and store its numeric projection before opening the final stream.

- [ ] **Step 4: Run GREEN** — `python -m pytest tests/test_phase64_short_loop.py tests/test_phase64_latency_trace.py -q --tb=short`; expect PASS.

### Task 2: Collect one real B profile and choose a ceiling

**Files:** `data/evaluation/phase64_token_prompt_profile.json`, `findings.md`, `progress.md`, `handoff.md`, and `obsidian-agent开发/阶段/阶段 64 - 主流 Agent 延迟优化.md`.

- [ ] **Step 1:** start an isolated B server with local `.env`, development auth settings, strict pgvector, four cold caches disabled, official rerank, and all B flags; do not print environment values.
- [ ] **Step 2:** execute one frozen ordinary-text case with `chat_model="deepseek-v4-flash"` and persist only case ID, model, numeric prompt shape, numeric timings, route, status, and citation count.
- [ ] **Step 3:** choose the largest multiple of 128 that is at most 70% of observed `final_prompt_estimated_input_tokens` and can retain one character per selected source after bounded history; record only arithmetic and aggregate values, then stop the temporary server and verify its port is free.

### Task 3: Add B-only ceiling with TDD

**Files:** `app/core/config.py`, `app/services/agent/tool_calling_service.py`, `tests/test_phase64_short_loop.py`, and `tests/test_phase64_latency_trace.py`.

- [ ] **Step 1: Write the failing tests**

```python
def test_b_token_budget_keeps_all_selected_sources_in_order() -> None:
    messages = evidence_answer_messages("问题", sources=eight_sources, max_sources=8, snippet_chars=320, estimated_input_token_budget=chosen_budget)
    assert source_markers(messages) == list(range(1, 9))
    assert measured_shape(messages).estimated_input_tokens <= chosen_budget

def test_a_omits_token_budget(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_SHORT_LOOP_ENABLED", "false")
    assert "estimated_input_token_budget" not in phase64_final_prompt_budgets(get_settings())
```

- [ ] **Step 2: Run RED** — `python -m pytest tests/test_phase64_short_loop.py -k token_budget -q`; expect failure because no B-only ceiling exists.

- [ ] **Step 3: Implement minimal allocator** — configure `AGENT_FINAL_ESTIMATED_INPUT_TOKEN_BUDGET` (zero disables it), reserve bounded history, allocate a nonzero equal minimum to every selected source, distribute remaining units in source order, and respect `snippet_chars`. If headers plus one character per source cannot fit, ignore the invalid ceiling and record `final_prompt_budget_applied=false`; never drop a source.

- [ ] **Step 4: Run GREEN** — `python -m pytest tests/test_phase64_short_loop.py tests/test_phase64_latency_trace.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_tool_calling_agent_service.py -q --tb=short`; expect PASS.

### Task 4: Re-run real B verification and work memory

**Files:** `data/evaluation/phase64_token_budget_probe.json`, `task_plan.md`, `findings.md`, `progress.md`, `handoff.md`, and `obsidian-agent开发/阶段/阶段 64 - 主流 Agent 延迟优化.md`.

- [ ] **Step 1:** execute the same serial B case before/after; save only case ID, model, aggregate prompt shape, route, citation count, status, and numeric latency fields. This is diagnostic evidence, not the release gate.
- [ ] **Step 2:** run `python -m py_compile app/core/config.py app/services/agent/tool_calling_service.py`, `python -m pytest tests/test_phase64_short_loop.py tests/test_phase64_latency_trace.py tests/test_evaluate_phase64_latency_ab.py tests/test_health_details.py -q --tb=short`, and `git diff --check`; all must exit 0.
- [ ] **Step 3:** record the exact outcome and unchanged official reranker/75-candidate policy. Do not claim completion until the full frozen 30-case, three-run, quality-judged gate passes.

## Execution Result (2026-07-13)

- [x] Task 1 completed with RED/GREEN and a numeric-only B final-prompt trace.
- [x] Task 2 completed: corrected Dynamic-K bound is 4–12, and an unbudgeted
  12-source real profile measured 3631 estimated input units.
- [x] Task 3 completed with RED/GREEN: B follows `reranking_dynamic_max_results`;
  a nonzero budget preserves all actual selected sources and their order.
- [x] Task 4 diagnostic completed: the 1664-unit paired probe had a worse
  three-run median TTFT than disabled budget, so the default is `0`.
- [ ] The full 30-case × 3 cold A/B, blind judge, Stage 30, and human review
  remain required Phase 64 gates.
