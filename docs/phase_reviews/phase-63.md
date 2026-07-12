# Phase 63 Review: Guarded Retrieval Runtime

## Outcome

Phase 63 passed user functional acceptance and is enabled by default. It
unifies optional retrieval-channel planning inside the runtime while keeping the
approved high-level Tool Calling surface and the existing Hybrid kernel. The
real-provider latency gate remains failed and is explicitly deferred to the
next phase.

## Before And After

| Area | Before | Phase 63 guarded path |
|---|---|---|
| Optional channel routing | Hybrid lexical term gates | One identity/intent proposal mapped by code-owned thresholds |
| Model-visible retrieval tools | Hybrid, keyword-only, figures, tables | Hybrid, figures, tables |
| GraphRAG implementation | Hybrid branch plus GraphEnhanced service logic | Shared bounded Local GraphRetriever |
| Graph budget | Fixed legacy channel settings | Required: up to 2 hops/50 matches; preferred: 1 hop/20 matches |
| Rerank input | Chunk content | Chunk content plus bounded safe relation provenance |
| Cache isolation | Query/config identity | Query/config plus plan digest and graph fingerprint |
| Rollout | Legacy active | Runtime default enabled; legacy is explicit fallback only |

## Automated Evidence

- Focused retrieval, graph, cache, identity, Tool Calling, and toolbox suite
  after review fixes: 122 passed.
- Agent API, SSE, and reranking suite with isolated SQLite: 66 passed.
- Evaluation CLI tests: 5 passed.
- 60-case deterministic dry-run: case/schema/output-safety validation passed;
  routing and rollout gates are explicitly marked not executed.
- Final full backend regression with isolated SQLite: 1370 passed and 1 skipped.
- Stage 30 quality gate: 91.52, grade A, release decision pass.
- Frozen real-provider SSE A/B: same corpus fingerprint (1153 documents / 51738
  chunks), strict BM25 + pgvector HNSW, no cache, and 9 paired cases. Phase 63
  completed 9/9 versus legacy 8/9; explicit asset routes completed 3/3 versus
  2/3; all Runtime backend/stream/count contracts passed.
- The same A/B recorded median end-to-end latency of 38.3s for Phase 63 versus
  21.3s for legacy. This exceeds the 15% latency gate and is carried forward as
  the Phase 64 objective; it is not treated as a Phase 63 pass.

The deterministic dry-run validates case coverage, routing metadata, and output
safety. It does not establish real-provider answer quality or latency.
Explicit execution requires two separately configured app endpoints through
`--legacy-base-url` and `--phase63-base-url`; the evaluator rejects identical
URLs so a single runtime cannot be mislabeled as an A/B comparison.
It also requires `--planner-failure-base-url` and
`--graph-unavailable-base-url`, backed by separately configured Phase 63
processes. Category labels alone never count as fault injection. Agent latency
is captured before the independent Judge call; Judge latency is recorded
separately and excluded from P95 Runtime gates.

## Acceptance and Follow-up

The user accepted the non-latency functional scope and authorized the default
switch, local/Obsidian synchronization, GitHub merge, and the Phase 63 tag.
The release must keep the latency finding visible: the next phase owns planner,
reranker, and final-generation latency decomposition and optimization.
