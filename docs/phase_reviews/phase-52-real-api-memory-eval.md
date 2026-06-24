# Phase 52 Real API Memory Evaluation

Status: complete before user human verification. No `git add`, commit, tag, push, or PR has been performed.

## Scope

This review covers the Phase 52 real API memory evaluation pass. It evaluates whether the current `AgentMemoryContext` semantic memory policy satisfies the memory-module goals under real provider calls, and whether it improves over a legacy source-count prior-reuse baseline.

Formal conclusions in this report use real API results only. Deterministic tests are treated as code-regression guards, not semantic quality evidence.

## Real API Artifacts

```text
data/evaluation/phase52_memory_real_api_cases.csv
scripts/evaluate_phase52_memory_real_api.py
data/evaluation/phase52_memory_real_api_results.csv
data/evaluation/phase52_memory_real_api_summary.csv
data/evaluation/phase52_memory_real_api_ablation.csv
```

The evaluation set contains 100 manually labeled cases:

```text
followup=20
new_topic=20
correction=15
stale_recency=15
refusal_boundary=10
citation_boundary=10
low_relevance_context=10
```

Each formal run uses the configured real chat model for memory intent classification, the configured real embedding model for prior relevance, and a real chat judge for residual-risk scoring. CSV outputs store structured labels, scores, model metadata, and sanitized short reasons only.

## Final Real API Result

```text
current:
  rows=100 completed=100 errors=0 skipped=0
  intent_accuracy=0.9200
  correction_recall=1.0000
  prior_reuse_precision=1.0000
  planner_action_accuracy=0.9700
  low_relevance_false_reuse_count=0
  stale_anchor_prior_reuse_count=0
  memory_citation_source_true_count=0
  long_term_enabled_count=0
  judge_high_risk_count=0
  gate=pass

legacy:
  rows=100 completed=100 errors=0 skipped=0
  intent_accuracy=0.9200
  correction_recall=1.0000
  prior_reuse_precision=0.7317
  planner_action_accuracy=0.8800
  low_relevance_false_reuse_count=11
  stale_anchor_prior_reuse_count=0
  memory_citation_source_true_count=0
  long_term_enabled_count=0
  judge_high_risk_count=11
  gate=blocked
```

## Improvement Over Legacy

```text
prior_reuse_precision: 1.0000 vs 0.7317, delta=+0.2683
planner_action_accuracy: 0.9700 vs 0.8800, delta=+0.0900
low_relevance_false_reuse_count: 0 vs 11, delta=-11
memory_citation_source_true_count: 0 vs 0
long_term_enabled_count: 0 vs 0
```

The main measured improvement is that current Phase 52 blocks low-relevance prior evidence under real API conditions, while legacy source-count reuse still incorrectly answers from unrelated prior evidence.

## Fixes Made During Evaluation

The real API run found issues that deterministic regression did not expose:

- Off-topic intent could still produce a memory-context route. `decide_memory_policy()` now routes off-topic requests to `refuse_or_clarify` without using memory for retrieval or answer.
- English `it` contextual matching used substring logic and could match words such as `testing`. It now uses word boundaries for `it` / `that`.
- Long conversations with recent topic shifts could still directly reuse a moderately similar prior summary. Direct prior reuse is now blocked when recent session anchors indicate a newer topic and prior relevance is below the stricter direct-reuse threshold.
- The correction detector missed "不是 X，..." / "不是 X。" and "Not X; continue ..." stale-anchor corrections. The detector now covers those forms while avoiding citation constraints such as "do not cite memory".
- The real API judge rubric now distinguishes residual risk in the observed decision from the inherent difficulty of a case.

## Safety Scan

Sensitive-field scan over formal real API CSV outputs found no matches for:

```text
api_key
bearer
authorization
raw_response
reasoning_content
```

The outputs do not store API keys, bearer tokens, hidden reasoning, raw provider responses, full model answers, complete chunks, restricted full text, or long-term user profiles.

## Conclusion

Phase 52 current memory policy passes the real API memory gate and demonstrates real progress over the legacy source-count prior reuse baseline. Long-term memory remains disabled, memory summaries are not citation sources, and prior evidence reuse is constrained by real semantic relevance plus stale-anchor policy.
