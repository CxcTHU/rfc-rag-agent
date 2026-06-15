# Stage 37 Decision Draft: Tool Calling Loop vs ReAct

Status: draft for human verification. Do not switch defaults until the user explicitly accepts.

Update after Phase 37 refinement: still do not switch defaults. The runtime now includes tool-call budgeting, skip-as-tool-result feedback, near-duplicate query defense, evidence convergence, and citation repair. These changes materially improve real-provider behavior, but source-order agreement and upstream timeout stability still need human review.

## Question

Should `mode="tool_calling_agent"` replace `mode="react_agent"` or the default Agent path?

## Short Recommendation

Do not switch the default in Phase 37.

Keep `tool_calling_agent` as a parallel review mode. It has passed deterministic tests, API/SSE integration, production smoke, and browser smoke, but the comparison shows source-order differences that deserve human review before any default change.

## Evidence

```text
python scripts/evaluate_stage37_tool_calling_vs_react.py
react_agent: errors=0, same_refusal=8/8, same_top_source=8/8
tool_calling_agent: errors=0, same_refusal=8/8, same_top_source=6/8
```

Verification:

```text
python -m pytest -q -> 758 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120 -> rows=9 execute=true failed=0
browser desktop -> no horizontal overflow, console errors=0
browser 390x844 -> no horizontal overflow, console errors=0
```

Real-provider comparison:

```text
python scripts/evaluate_stage37_tool_calling_vs_react.py --execute --limit 8
react_agent: errors=0, avg_tools=1.750, same_refusal=8/8, same_top_source=8/8
tool_calling_agent: errors=0, avg_llm_calls=2.625, avg_tools=1.875, same_refusal=8/8, same_top_source=7/8
```

The real-provider comparison is now implemented and executed successfully after the provider rate limit recovered. It shows a strong latency improvement for `tool_calling_agent` on the 8-query set, but still does not justify switching defaults automatically because one top source differs and the single-model tool-calling tradeoff remains.

Refined real-provider comparison after adding evidence convergence:

```text
react_agent: errors=0, refused=1/8, same_refusal=8/8, same_top_source=8/8
tool_calling_agent: errors=0, refused=2/8, avg_tools=1.750, avg_executed_tools=0.875, avg_skipped_tools=0.875, same_refusal=7/8, same_top_source=4/8
```

Latest full real-provider attempt after adding citation repair:

```text
react_agent: errors=1/8, error_summary=provider_timeout on multi_hop_retrieval
tool_calling_agent: errors=0, refused=1/8, avg_tools=1.750, avg_executed_tools=0.875, avg_skipped_tools=0.875
```

Interpretation: the Phase 37 loop is improved and no longer primarily fails by repeated tool execution, but the default should still remain `react_agent` until human review resolves source-order differences and provider timeout noise.

## What Improved

- Tool requests now use a standard OpenAI-compatible `tools/tool_calls` protocol.
- The new loop supports repeated LLM-with-tools turns, `role="tool"` feedback, repeated query guard, tool error convergence, max iteration guard, safe refusal, and citation validation.
- The runtime now treats skipped tool calls as valid tool results, which keeps the provider transcript well-formed while enforcing RAG search budget.
- Evidence convergence forces a bounded no-tools final synthesis over sanitized sources when the model keeps asking for more tools after evidence is available.
- Citation repair gives one bounded opportunity to add missing `[N]` markers to an already source-backed draft; if repair fails, the safe refusal remains.
- The provider contract can simulate single-round and multi-round tool calls offline.
- `/agent/query` and SSE can explicitly select `mode="tool_calling_agent"`.

## Remaining Risk

- `same_top_source_as_react=6/8` means the new mode does not always anchor to the same first source as ReAct.
- Real provider latency is still high enough that production smoke needs a 90-second per-request timeout.
- OpenAI-compatible providers can differ in exact `tools/tool_calls` behavior; Phase 37 validates the project adapter but should not overclaim provider universality.
- Tiered provider tradeoff: `react_agent` can use Flash planner + V4-Pro answer, while `tool_calling_agent` merges planning and answering into a single tools-capable model. Flash may be faster but weaker for final answers; V4-Pro may be stronger but can erase the latency benefit on every tool iteration.
- Citation strictness risk: `tool_calling_agent` refuses final model content when it lacks valid `[N]` tool-backed citations. This is safer but may be less forgiving than `react_agent` / Brain citation handling when a real model gives a useful answer but forgets citation markers. The evaluation CSV tracks this as `missing_tool_backed_citations`.

## Human Verification Focus

- Review `data/evaluation/stage37_tool_calling_vs_react_results.csv`.
- Review `data/evaluation/stage37_tool_calling_vs_react_real_results.csv`, especially the one real-provider top-source mismatch row.
- Compare answer quality on the two source-order mismatch cases.
- Confirm safe refusal behavior for off-topic, responsibility-gate, and evidence-insufficient questions.
- Check whether any real-provider `tool_calling_agent` rows show `refusal_reason_summary=missing_tool_backed_citations`.
- Confirm SSE events are useful but do not expose hidden reasoning or full chunks.
- Decide whether Phase 38 should widen the evaluation set, tune source ordering, or evaluate LangGraph/checkpointing later.

## Draft Decision

Codex recommendation: keep `tool_calling_agent` parallel and available, keep `react_agent` and default routing unchanged, and revisit default switching only after human review plus a larger real-provider comparison.
