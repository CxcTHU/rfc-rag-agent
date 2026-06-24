# Phase 52 Review Draft: AgentMemoryContext And Short-Term Session Memory

Status: complete before user human verification. No `git add`, commit, tag, push, or PR has been performed.

## Scope

Phase 52 unifies Phase 43 `SessionMemory` and Phase 51 LangGraph prior evidence into `AgentMemoryContext`. The scope is short-term, conversation-scoped memory engineering. It does not introduce long-term user profiles, write tools, external data sources, or default provider changes.

## Main Changes

- Added `app/services/agent/memory_context.py`.
- Added `MEMORY_CONTEXT_SCHEMA_VERSION=1` and `MEMORY_TRACE_FIELDS` as the stable memory contract.
- Added `MemoryPolicyDecision` to centralize prior-evidence reuse, retrieval augmentation, stale-anchor refresh, and citation-source boundaries.
- Added JSON-native `memory_context` to `LangGraphAgentState`.
- Updated `LangGraphAgentService.query()` to build memory context after loading checkpoint prior evidence.
- Updated `planner_node` to use prior evidence and stale-anchor decisions through memory context.
- Updated `search_knowledge_node` to add retrieval-only session memory hints for contextual follow-ups.
- Updated `generate_answer_node` to reuse prior evidence only when memory rules allow it.
- Added memory trace fields to `latency_trace`, including policy route and safe memory-usage flags.
- Added `scripts/evaluate_phase52_memory.py`.
- Added `MemoryIntentClassifier` with LLM and deterministic implementations.
- Added `PriorEvidenceRelevanceGate`; prior reuse no longer depends on `source_count >= 3`.
- Added `MemoryItem(text, turn_index, importance)` and session recency decay.
- Added and expanded `data/evaluation/phase52_memory_regression_cases.csv` to 32 deterministic cases.
- Added disabled long-term governance interfaces for consent, retention, deletion request, and audit records.
- Kept disabled provider read-none/write-none/delete-noop without echoing write payloads or deletion reasons.
- Added tests for memory context, LangGraph behavior, and evaluation outputs.

## Validation

```text
focused memory/LangGraph regression -> 63 passed
python scripts/evaluate_phase52_memory.py -> cases=32 pass=32 fail=0 pass_rate=1.0000
API/SSE/LangGraph focused regression -> 124 passed
python -m pytest -q -> 1158 passed, 1 skipped
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
Phase 52 CSV sensitive scan -> no matches
```

## Real API Memory Evaluation

Phase 52 now also includes a formal real API memory evaluation. The 100-case set calls real chat intent classification, real embedding relevance, and a real judge. Final result:

```text
current -> rows=100 completed=100 gate=pass
intent_accuracy=0.9200
correction_recall=1.0000
prior_reuse_precision=1.0000
planner_action_accuracy=0.9700
low_relevance_false_reuse_count=0
memory_citation_source_true_count=0
long_term_enabled_count=0

legacy -> gate=blocked
prior_reuse_precision=0.7317
low_relevance_false_reuse_count=11
```

See `docs/phase_reviews/phase-52-real-api-memory-eval.md` for details.

## Safety Boundary

- Memory summaries are planner/retrieval hints only.
- Final citations must come from retrieved or prior retrieved sources.
- Long-term memory remains disabled/read-none/write-none/delete-noop.
- No raw provider response, hidden reasoning, full chunk text, restricted full text, API key, bearer token, or user profile is written to Git, CSV, docs, tests, or Obsidian.

## Remaining Closeout

- User human verification.
- If approved, submit, tag, push, and open/merge PR in a later explicitly authorized step.
