# Phase 58 Task Plan: Mature Agent Runtime Layer

## Goal

Phase 58 upgrades the default `tool_calling_agent` from a service with embedded loop rules into an explicit Agent Runtime control plane.

The architecture direction is:

```text
ToolCallingAgentService
-> AgentRuntime
   -> RuntimeContextAssembler
   -> TaskContextualizer
   -> LLM tool selection adapter
   -> ToolArgumentGrounder
   -> ToolExecutionController
   -> EvidenceStateManager
   -> LoopController
   -> GuardrailController
   -> FinalAnswerController
   -> RuntimeDiagnostics
-> AgentToolbox / Workflow kernels
```

Query rewrite is only one part of the runtime. Phase 58 must make context assembly, tool argument grounding, evidence state, loop control, guardrails, diagnostics, and final answer control explicit and testable.

Target branch:

```text
codex/phase-58-mature-agent-runtime
```

## Current Baseline

- Current branch starts from Phase 57 current head.
- Default runtime mode is still `tool_calling_agent`.
- Phase 57 completed gated multi-channel retrieval inside `hybrid_search_knowledge`.
- Manual verification exposed a runtime gap:

```text
Turn 1: 大坝的裂缝成因有哪些？请给我详细列出来
Turn 2: 我需要图片支撑
```

The model selected `search_figures`, but passed the raw follow-up as the tool query. `search_figures(query="我需要图片支撑")` failed its visual-intent gate because the runtime had not grounded the tool argument with the prior topic.

## Runtime LLM Boundary

LLM may be used where semantic interpretation is needed:

- classify follow-up type;
- infer inherited topic;
- propose a standalone task;
- propose tool-specific query rewrites;
- propose high-level tool calls;
- synthesize final cited answers from runtime-approved evidence.

Runtime must keep final control over:

- guardrail decisions;
- allowed tools and tool permissions;
- tool argument validation;
- loop limits and duplicate suppression;
- evidence sufficiency state;
- cache and diagnostics identity;
- final refusal vs answer decision.

Principle:

```text
LLM proposes semantic intent and candidate actions;
Runtime validates, executes, records, and decides control flow.
```

## Non-Goals

- Do not replace the default `tool_calling_agent` with LangGraph/ReAct.
- Do not expose `search_graph_knowledge` as a new default parallel tool.
- Do not add write-capable Agent tools.
- Do not add external corpus sources, crawlers, PDFs, model weights, or embeddings.
- Do not reintroduce broad answer-level Semantic Cache as the quality solution.
- Do not store API keys, bearer tokens, provider raw responses, hidden reasoning, full answers, full chunks, restricted full text, private logs, or raw uploaded images in Git/CSV/docs/tests/Obsidian.
- Do not run `git add`, commit, tag, push, or PR before user human verification.

## Phase 58A: Startup Calibration And Runtime Boundary Audit

Status: completed

Tasks:
- Re-read required project files and current root planning files.
- Run `git status -sb` and `git log --oneline -5`.
- Create/switch to `codex/phase-58-mature-agent-runtime`.
- Audit `ToolCallingAgentService`, Stage 37 loop controls, `AgentToolbox`, Phase 52 memory context, Phase 56 cache diagnostics, and Phase 57 retrieval kernel.

Acceptance:
- Baseline explains why Phase 58 is a runtime layer, not a query rewrite patch.

## Phase 58B: Runtime Design And Planning Files

Status: completed

Tasks:
- Update `task_plan.md`, `findings.md`, and `progress.md`.
- Add `docs/stage58_mature_agent_runtime_goal_prompt.md`.
- Add runtime design documentation.

Acceptance:
- Planning states which runtime layers use LLM and which remain deterministic.

## Phase 58C: Runtime State And Context Assembly

Status: completed

Tasks:
- Add an explicit runtime module for `AgentRuntimeState`, `RuntimeContext`, `StandaloneTask`, `EvidenceState`, and diagnostics.
- Assemble current question, history, recent topic, follow-up type, inherited topic, and standalone task.
- Prefer deterministic rules first; use LLM-compatible boundaries through structured message helpers where later providers can be injected.

Acceptance:
- Multi-turn context is represented as structured state and exported through safe latency diagnostics.

## Phase 58D: Tool Argument Grounding And Validation

Status: completed

Tasks:
- Ground tool query arguments before execution.
- Repair short elliptical follow-ups such as "我需要图片支撑", "给我表格", "继续详细说".
- Make `search_figures` and `search_tables` inherit topic safely when the current turn is a follow-up.
- Preserve user topic changes: off-topic or new-topic requests must not inherit stale anchors.

Acceptance:
- The dam-crack image follow-up executes `search_figures` with a standalone visual query that contains the inherited topic.

## Phase 58E: Execution, Evidence, Loop, And Final Answer Control

Status: completed

Tasks:
- Record evidence attempts by tool and evidence type: text, table, figure, graph-derived text.
- Record runtime stop reasons and evidence sufficiency labels.
- Preserve Stage 37 one-search-per-iteration, duplicate suppression, skipped tool messages, and citation repair behavior.
- Ensure failed zero-result tool calls can be explained through diagnostics instead of silently looping.

Acceptance:
- Runtime diagnostics expose safe evidence and loop state without full chunks or provider payloads.

## Phase 58F: Tests And Evaluation Fixtures

Status: completed

Tasks:
- Add focused tests for runtime context assembly, tool argument grounding, visual follow-up repair, table follow-up repair, new-topic non-inheritance, duplicate suppression preservation, and diagnostics.
- Run focused test suites.
- Run Stage 30 score if code path risk justifies it.

Acceptance:
- Focused tests pass and existing tool-calling behavior remains compatible.

## Phase 58G: Documentation And Handoff

Status: completed

Tasks:
- Update README, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, and add `docs/phase_reviews/phase-58.md`.
- Add/update local Obsidian phase note.
- Update root planning files with final validation and stopped-before-commit state.

Acceptance:
- Handoff explains branch, changed files, runtime design, LLM boundary, tests, risks, and manual verification checklist.

## Phase 58H: Runtime Resume And Similar-Question Evidence Cache Reuse

Status: completed

Tasks:
- Add a durable checkpoint/resume design for default `tool_calling_agent` runtime runs.
- Add evidence-query identity canonicalization so semantically equivalent questions can reuse evidence-chain caches without reusing final answers.
- Create a Phase 58H evaluation plan covering stop/resume and similar-question cache-hit behavior.
- Add execution prompt for the follow-up development pass.

Planning files:

```text
docs/stage58h_runtime_checkpoint_resume_plan.md
docs/stage58h_evidence_cache_canonicalization_plan.md
docs/stage58h_checkpoint_cache_evaluation_plan.md
docs/stage58h_checkpoint_cache_goal_prompt.md
data/evaluation/phase58h_runtime_resume_cases.yaml
data/evaluation/phase58h_cache_canonicalization_cases.yaml
```

Acceptance:
- The next development pass has explicit checkpoint/resume semantics, cache identity semantics, evaluation cases, metrics, safety boundaries, and tests to implement.
- The design states that final answers are generated fresh and only evidence-chain work is reused.
- Stop before git staging, commit, tag, push, or PR until user verification.

Validation:

```text
python scripts\evaluate_phase58h_cache_hits.py -> cases=7 passed=7 failed=0
python scripts\evaluate_phase58h_runtime_resume.py -> cases=6 passed=6 failed=0
python -m pytest tests/test_phase58h_runtime_checkpoint_cache.py -q -> 9 passed
python -m pytest tests/test_phase58h_runtime_checkpoint_cache.py tests/test_phase56_layered_cache.py tests/test_tool_calling_agent_service.py -q -> 35 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_hybrid_search.py tests/test_agent_tools.py -q -> 85 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 47 passed
git diff --check -> no whitespace errors; CRLF warnings only
```

## Completion Standard

- Default `tool_calling_agent` remains the default mode and keeps the same tool surface.
- A clear Agent Runtime layer owns context, grounding, execution control, evidence state, loop control, guardrails, diagnostics, and final answer decision.
- LLM is only used/provisioned for semantic proposal layers; runtime keeps deterministic control authority.
- The dam-crack image follow-up failure is fixed through runtime grounding, not a `search_figures` special-case patch.
- Diagnostics are safe and useful: standalone task, inherited topic, follow-up type, rewritten tool query, evidence counts, stop reason, and final decision.
- Focused tests pass.
- No secrets, raw responses, full answers, full chunks, or restricted full text enter Git/docs/tests/CSV/Obsidian.
- Stop before git staging, commit, tag, push, or PR until user verification.

## Validation Completed

```text
python -m py_compile app\services\agent\runtime.py app\services\agent\tool_calling_service.py app\services\observability\latency_trace.py -> passed
python -m pytest tests/test_tool_calling_agent_service.py -q -> 21 passed
python -m pytest tests/test_agent_api.py::test_agent_api_detail_followup_uses_agent_tool_decision tests/test_agent_api.py::test_agent_api_accepts_optional_history_for_contextual_answer tests/test_tool_calling_agent_service.py::test_tool_calling_runtime_grounds_visual_followup_tool_query -q -> 3 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_agent_tools.py tests/test_agent_api.py tests/test_agent_stream_api.py -q -> 81 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
git diff --check -> no whitespace errors; CRLF warnings only
```

## Phase 58I: Semantic Evidence Cache And HyDE Runtime Flow

Status: in_progress

Tasks:
- Add three planning files for semantic evidence cache, HyDE retrieval, and runtime flow evaluation.
- Add an execution goal prompt for Phase 58I.
- Implement semantic evidence cache lookup before LLM tool selection.
- Ensure semantic cache hit reuses hydrated evidence/tool results only and still regenerates final answers.
- Add HyDE generation only after semantic evidence cache miss.
- Use HyDE only to augment vector retrieval, never as cited evidence.
- Add trace fields for `semantic_cache_hit`, `canonical_task`, `hyde_generated`, `hyde_used_for_vector`, and rerank/cache visibility.
- Add focused regression tests.

Planning files:

```text
docs/stage58i_semantic_evidence_cache_plan.md
docs/stage58i_hyde_runtime_retrieval_plan.md
docs/stage58i_runtime_flow_evaluation_plan.md
docs/stage58i_semantic_cache_hyde_goal_prompt.md
```

Acceptance:
- Similar questions with the same semantic identity can skip tool selection/retrieval/rerank through cached evidence/tool results.
- HyDE runs only on semantic evidence cache miss and is not included in sources/citations.
- Final answers are never reused from cache.
- Diagnostics are safe and explicit.
