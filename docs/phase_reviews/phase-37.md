# Phase 37 Review: Tool Calling Loop Migration and ReAct Comparison

Status: draft; waiting for user human verification.
Branch: `codex/phase-37-tool-calling-loop-migration`

Baseline:

```text
main / origin/main -> d747169 Merge phase 36 generation reliability and conversation stability
phase-36-complete -> 9516b22 Complete phase 36 generation reliability and conversation stability
phase-36-complete is ancestor of main
PR #6 merged
```

## Acceptance Conclusion

Phase 37 development, tests, normal docs, Obsidian drafts, and decision drafts are complete. The branch is intentionally stopped before human verification.

The phase adds a parallel `tool_calling_agent` loop using OpenAI-compatible `tools/tool_calls`. It keeps `react_agent`, keeps the default routing unchanged, does not introduce LangGraph, does not change provider topology, and does not add data sources.

Stage 30 remains `91.52 / A / pass`.

## Main Changes

- `docs/stage37_tool_calling_loop_migration.md`
- `tests/test_stage37_design.py`
- `app/services/generation/chat_model.py`
- `tests/test_chat_model_provider.py`
- `app/services/agent/tool_calling_service.py`
- `tests/test_tool_calling_agent_service.py`
- `app/schemas/agent.py`
- `app/api/agent.py`
- `tests/test_agent_api.py`
- `tests/test_agent_stream_api.py`
- `scripts/evaluate_stage37_tool_calling_vs_react.py`
- `tests/test_stage37_tool_calling_eval.py`
- `scripts/run_production_smoke.py`
- `tests/test_run_production_smoke.py`
- `docs/stage37_tool_calling_vs_react_decision.md`

## Comparison Result

```text
react_agent: errors=0, same_refusal=8/8, same_top_source=8/8
tool_calling_agent: errors=0, same_refusal=8/8, same_top_source=6/8
```

Real-provider comparison has been implemented with `--execute`:

```text
python scripts/evaluate_stage37_tool_calling_vs_react.py --execute --limit 8
react_agent: errors=0, avg_tools=1.750, same_refusal=8/8, same_top_source=8/8
tool_calling_agent: errors=0, avg_llm_calls=2.625, avg_tools=1.875, same_refusal=8/8, same_top_source=7/8
```

This real-provider run is usable and shows `tool_calling_agent` is a viable parallel candidate with materially lower latency. It still should not switch defaults automatically because one top source differs and the tiered-provider tradeoff remains unresolved.

Decision draft: keep `tool_calling_agent` as a parallel review mode. Do not switch defaults automatically.

Additional risks captured after review:

- `tool_calling_agent` does not support the Stage 34 tiered provider split in the same way as ReAct. ReAct can run Flash planner + V4-Pro answer; tool-calling loop must choose one tools-capable model for both planning and final answer.
- The final citation gate is stricter than ReAct/Brain. Useful real-provider content without `[N]` citation markers becomes a safe refusal, tracked in evaluation as `missing_tool_backed_citations`.

## Verification

```text
python -m pytest tests/test_stage37_design.py -q -> 6 passed
python -m pytest tests/test_chat_model_provider.py -q -> 30 passed
python -m pytest tests/test_tool_calling_agent_service.py -q -> 8 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_react_stream_events.py tests/test_tool_calling_agent_service.py -q -> 45 passed
python -m pytest tests/test_stage37_tool_calling_eval.py tests/test_tool_calling_agent_service.py -q -> 12 passed
python scripts/evaluate_stage37_tool_calling_vs_react.py -> react_agent errors=0; tool_calling_agent errors=0
python scripts/evaluate_stage37_tool_calling_vs_react.py --execute --limit 8 -> real-provider CSV written; tool_calling_agent same_refusal=8/8, same_top_source=7/8
python -m pytest tests/test_run_production_smoke.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 43 passed
python -m pytest -q -> 758 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120 -> rows=9 execute=true failed=0
browser smoke desktop -> no horizontal overflow, console errors=0
browser smoke 390x844 -> no horizontal overflow, console errors=0
```

## Human Verification Focus

- Review `docs/stage37_tool_calling_vs_react_decision.md`.
- Inspect `data/evaluation/stage37_tool_calling_vs_react_results.csv` and source-order mismatch rows.
- Inspect `data/evaluation/stage37_tool_calling_vs_react_real_results.csv`, especially the one real-provider top-source mismatch row.
- Manually compare `react_agent` and `tool_calling_agent` answers on representative domain questions.
- Decide whether the single-model tool-calling tradeoff is acceptable versus Flash planner + V4-Pro answer tiering.
- Check for `missing_tool_backed_citations` rows in real-provider output.
- Confirm tool result feedback remains truncated and safe.
- Confirm no default mode, provider topology, Stage 30 scoring rule, tag, or data source was changed.

## Submission Boundary

Do not run `git add`, commit, tag, push, or create a PR until the user completes human verification and explicitly authorizes submission.

## Refinement Note: Tool Runtime Controls

After user review, Phase 37 was refined rather than deferred to Phase 38.

Additional implementation:

- Reviewed `CxcTHU/claude-code-analysis` for mainstream tool-runtime patterns.
- Added one-search-per-turn execution budget.
- Added safe skipped tool results for every skipped `tool_call_id`.
- Added near-duplicate query detection.
- Added evidence convergence over sanitized sources.
- Added citation repair for source-backed drafts missing `[N]` markers.
- Added evaluation metrics for executed, skipped, near-duplicate, and repair counts.

Focused verification:

```text
python -m pytest tests/test_tool_calling_agent_service.py tests/test_stage37_tool_calling_eval.py -q -> 17 passed
python scripts/evaluate_stage37_tool_calling_vs_react.py -> deterministic comparison refreshed
```

Real-provider status after refinement:

```text
Clean post-convergence run:
react_agent errors=0, same_refusal=8/8, same_top_source=8/8
tool_calling_agent errors=0, same_refusal=7/8, same_top_source=4/8, avg_tools=1.750

Latest post-repair full run:
react_agent errors=1/8, provider_timeout on multi_hop_retrieval
tool_calling_agent errors=0, refused=1/8, avg_tools=1.750
```

Review decision remains unchanged: keep `tool_calling_agent` available as a parallel review mode; do not switch default routing before human verification.
