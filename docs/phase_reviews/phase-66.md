# Phase 66 Tool Calling Runtime Slimming

Status: `closeout_sync_authorized`; quality gate `passed` on the
PostgreSQL/pgvector judge-backed A/B packet.

Phase 66 implements the requested real slimming of the Tool Calling runtime
after Phase 65's larger modularization. The goal was not to add another
feature flag or a parallel loop; it was to make the production path visibly
small, typed, and close to mainstream agent runtime design.

## Runtime shape

```text
user text -> ToolCallingAgentService -> RunCoordinator -> ToolExecutor -> registry adapters
uploaded image -> ToolCallingAgentService -> RunCoordinator -> analyze_user_image
```

The model-visible production inventory is exactly:

- `hybrid_search_knowledge`
- `search_tables`
- `search_figures`
- `analyze_user_image`

`ToolCallingAgentService` is now a thin facade. Prompt construction,
pre-tool gates, tool-call composition, final prompt handling, result merging,
runtime support, and coordinator support were moved into focused modules.
`ToolExecutor` is registry-driven, and tool adapters own the old toolbox
boundary.

## Deleted flag and rollback

The production `agent_run_coordinator_enabled` switch is deleted. There is no
second online Tool Calling runtime to silently fall back to. Rollback is
rollback through Git after review, not a hidden branch inside production code.

## Size and responsibility gates

Final local structure snapshot:

- `tool_calling_service.py <= 260 lines` — actual 233
- `ToolCallingAgentService.query <= 80 lines` — actual 64
- `run_coordinator.py <= 120 lines` — actual 90
- production tool count — 4
- forbidden production coordinator flag occurrences — 0

Primary receipt:

- `output/phase66/final/runtime-structure.json`

## Verification receipts

Local implementation verification completed:

- `output/phase66/final/runtime-structure.json`
- `output/phase66/final/fault-matrix.json`
- `output/phase66/final/runtime-recovery.json`

Regression evidence:

- backend: `1897 passed, 1 skipped`
- focused Phase 65 runtime regression: `199 passed`
- frontend unit: `31 passed`
- frontend lint: passed
- frontend build: passed
- compileall: passed
- final runtime-structure `--check`: passed

Evaluation scaffold:

- `output/phase66/evaluation/summary.json`
- `output/phase66/evaluation/review-packet.md`

The fresh Phase 66 evaluator is intentionally not marked pass yet. It currently
records `review_required`, because real A/B observation files and human review
still need an explicit acceptance step. The evaluator now has a safe
`--collect-http --cases ...` path for `/agent/query`, a
`--collect --observations ...` receipt path, and a coverage-aware `--merge`
gate. It writes only safe metadata such as case id, modality, HTTP status,
tool names, counts, refusal status, elapsed time, and error category; it must
not persist answer text, prompt text, source text, provider payloads, or
credentials. No real A/B observations have been accepted as final evidence.

Update: a local deterministic A/B runtime-observation smoke has now been
collected. Baseline A (`be23e215`) and candidate B were served on isolated local
ports with separate SQLite copies. Both lanes completed 30 text and 4 image
observations with `failed_case_count=0` and `unknown_error_count=0`. The merged
packet records `paired_text_cases=30` and `paired_image_cases=4`, but remains
`review_required` because answer-accuracy, citation-correctness, overall, and
judge metrics are not present.

Important boundary: this SQLite-backed packet is only an isolated local runtime
smoke. It must not be treated as Phase 66 final acceptance evidence. The final
quality/runtime gate should run against the production-like PostgreSQL/pgvector
topology, because SQLite can hide differences in vector retrieval, transaction
behavior, locking, indexes, and corpus parity.

Update: the evaluator now supports an optional in-memory judge path. When
`--collect-http --judge` is used, answer/source text is sent to `/agent/judge`
only inside the request and only numeric scores are persisted:
`answer_accuracy_score`, `citation_correctness_score`, and `overall_score`.
Judge failures are counted as `judge_failed_count` and keep the packet
`review_required`.

Update: a PostgreSQL/pgvector-backed A/B quality packet has now passed. Two
isolated local PostgreSQL clones were created from `rfc_rag_dev`
(`1153` documents, `51738` chunks, `74067` embeddings, `42051` pgvector rows).
Baseline A (`be23e215`) ran against `rfc_rag_phase66_a_20260716`; candidate B
ran against `rfc_rag_phase66_b_20260716`. The evaluator was tightened to trim
in-memory judge payloads to the `/agent/judge` API limits and retry transient
judge HTTP failures, while still persisting only safe numeric scores/status.
The fixed PG judge-backed packet in `output/phase66/evaluation_pg_judge_fixed/`
completed 30 text + 4 image cases for each lane with `failed_case_count=0`,
`unknown_error_count=0`, and `judge_failed_count=0`. Merge status is `passed`:
A overall `0.8264705882352942`, B overall `0.870343137254902`, reason
`phase66_pairing_quality_non_regression`.

Latency follow-up: the original Phase 66 evaluator recorded `elapsed_ms` before
the HTTP `/agent/query` call, so those stored values measured payload
construction rather than true Agent response time. The PG judge-backed packet
therefore remains valid as a quality non-regression packet, but must not be
cited as latency evidence. The evaluator now records elapsed time after the
HTTP sender returns or raises, summarizes `elapsed_ms_p50` / `elapsed_ms_p95`,
summarizes `figure_elapsed_ms_p50` / `figure_elapsed_ms_p95` for rows that call
`search_figures`, and fails merge when candidate p95 latency regresses beyond
the configured A/B tolerance.

Latency repair follow-up: a small local A/B probe on two figure-heavy prompts
showed the remaining slowdown concentrated in final answer generation rather
than the `search_figures` adapter itself. The final provider now always applies
the configured final-answer output cap, even when the broader short-loop route
is disabled, and the default cap is tightened to `600` tokens. DeepSeek v4 final
answers now also use non-thinking mode by default via
`PHASE64_FINAL_NON_THINKING_ENABLED=true`; this is scoped to final answer
generation and does not turn on route-first planning. In the local probe,
DeepSeek final TTFT for the crack/defect figure prompt dropped from roughly
`11.7s` to `0.67s`, and the end-to-end case dropped from the earlier
`47-60s` range to about `25s` with caches disabled.

Default-model correction: the user-facing Agent default is Flash, not Pro. The
React workbench already selected `deepseek-v4-flash` unless the user explicitly
picked Pro, but bare `/agent/query` requests without `chat_model` previously
fell back to the backend `CHAT_MODEL_NAME`, which can be locally configured as
Pro. Phase 66 now adds `AGENT_DEFAULT_CHAT_MODEL=deepseek-v4-flash` and resolves
omitted Agent model selections to Flash for real OpenAI-compatible providers,
while still honoring an explicit Pro request.

Flash latency follow-up: after the default-model correction, a local PostgreSQL
/ pgvector probe on `127.0.0.1:8000` confirmed omitted `chat_model` requests
return `deepseek-v4-flash`. Tool-level latency attribution was added because the
post-final-generation probe showed an unaccounted gap before first answer
token. The new trace fields include `tool_execution_latency_ms`,
`search_figures_latency_ms`, and `hybrid_search_knowledge_latency_ms`.

With Flash and the final-answer cap active, pure figure lookup prompts were
still dominated by sequential `search_figures + hybrid_search_knowledge`
execution. Phase 66 now skips the hybrid supplement only for pure figure lookup
requests such as "展示/检索图片证据"; explanatory figure questions containing
terms such as "说明", "边界", "比较", or "分析" still keep the hybrid supplement.
The local probe measured:

```text
pure figure failure-mode prompt:
  before pure-figure optimization: ~21.1s, search_figures ~7.6s, hybrid ~8.1s
  after optimization: ~11.9s, search_figures only, 4 sources, 4 citations

pure crack/defect figure prompt:
  after optimization: ~10.4s, search_figures only, 4 sources, 4 citations

explanatory visual-boundary prompt:
  after optimization: ~27.1s, search_figures + hybrid retained, 13 sources, 7 citations
```

This closes the immediate "default Flash + pure figure lookup" latency
regression, but it is not yet a broad latency release gate. Explanatory visual
questions still spend most of their time inside the two evidence tools, and a
formal PG/pgvector A/B latency packet should be collected before release
acceptance.

## Fixed common Agent regression suite

Phase 66 introduced a reusable common Agent regression suite at:

`data/evaluation/agent_regression_cases.csv`

This file supersedes ad hoc smoke prompts for release evidence. The suite is
versioned as `agent_common_v1` and contains 30 text cases plus 4 image cases.
Each case has an explicit runtime contract:

- expected tools
- forbidden tools
- expected refusal behavior
- minimum source count
- minimum citation count
- latency budget in milliseconds

The historical Phase 66 file remains available at
`data/evaluation/phase66_runtime_convergence_cases.csv`, but new A/B evidence
should prefer the common suite.

Collect candidate observations against a running local Agent:

```powershell
python scripts/evaluate_phase66_runtime_convergence.py `
  --collect-http `
  --variant b `
  --base-url http://127.0.0.1:8000 `
  --cases data/evaluation/agent_regression_cases.csv `
  --output-root output/phase66/evaluation_common/b
```

The resulting `observations.json` includes `contract_violations` per case, and
`summary.json` includes `contract_violation_count`.

## Current release boundary

The user authorized Phase 66 closeout synchronization on 2026-07-16, including
local Git submission, GitHub PR, and merge when checks pass. The accepted scope
is the Tool Calling runtime slimming, the single coordinator path, the fixed
common Agent regression suite, the refusal-answer wording repair, and the
PostgreSQL/pgvector judge-backed non-regression packet.

Do not overstate the acceptance boundary:

- The PG/pgvector quality packet passed for 30 text + 4 image cases per lane.
- The common regression suite is now fixed and reusable, but one candidate
  common-suite collection still showed contract violations that should drive
  follow-up hardening.
- The latency fix improved pure figure lookup and default Flash behavior, but a
  broad formal latency release gate was not rerun.
- Phase 65's wider holdout/judge closeout remains a separate gate and is not
  made pass by Phase 66.

GitHub closeout state should be recorded by the PR once this branch is pushed
and merged.
