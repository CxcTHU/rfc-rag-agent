# Phase 58H Checkpoint And Cache Evaluation Plan

## Goal

Create a repeatable evaluation set for two Phase 58H capabilities:

1. runtime checkpoint/resume after stop;
2. similar-question evidence cache reuse.

The evaluation must be safe for Git: no full answers, full chunks, provider raw responses, secrets, private logs, or restricted full text.

## Evaluation Artifacts

Required files:

```text
data/evaluation/phase58h_runtime_resume_cases.yaml
data/evaluation/phase58h_cache_canonicalization_cases.yaml
scripts/evaluate_phase58h_runtime_resume.py
scripts/evaluate_phase58h_cache_hits.py
data/evaluation/phase58h_runtime_resume_eval.csv
data/evaluation/phase58h_cache_hit_eval.csv
```

CSV outputs should contain only:

- case id and category;
- sanitized query labels or short query hashes;
- status;
- elapsed milliseconds;
- runtime node labels;
- checkpoint/resume booleans;
- cache hit booleans;
- selected chunk ids;
- source count / citation count;
- safe error summaries.

## Runtime Resume Case Set

Minimum cases:

```yaml
- id: resume_after_retrieval_exact_retry
  first_query: 堆石混凝土的优势
  stop_after_node: tool_execution_completed
  followup_query: 继续
  expected_resume: true
  expected_skipped_nodes:
    - tool_execution

- id: resume_after_visual_tool_followup
  history:
    - 大坝裂缝成因有哪些？请详细列出
  first_query: 我需要图片支撑
  stop_after_node: tool_execution_completed
  followup_query: 继续上次
  expected_resume: true

- id: exact_retry_after_stop
  first_query: 堆石混凝土的优势
  stop_after_node: evidence_state_updated
  followup_query: 堆石混凝土的优势
  expected_resume: true

- id: new_topic_blocks_resume
  first_query: 堆石混凝土的优势
  stop_after_node: tool_execution_completed
  followup_query: 大坝裂缝成因有哪些？
  expected_resume: false

- id: expired_checkpoint_blocks_resume
  first_query: 堆石混凝土的优势
  stop_after_node: tool_execution_completed
  followup_query: 继续
  checkpoint_expired: true
  expected_resume: false

- id: corrupted_checkpoint_fails_safe
  first_query: 堆石混凝土的优势
  stop_after_node: tool_execution_completed
  followup_query: 继续
  checkpoint_corrupted: true
  expected_resume: false
```

The initial YAML case file has been created at:

```text
data/evaluation/phase58h_runtime_resume_cases.yaml
```

## Cache Canonicalization Case Set

Minimum pairs:

```yaml
- id: rfc_advantage_synonym
  q1: 堆石混凝土的优势
  q2: 堆石混凝土有哪些优点
  expected_same_identity: true
  expected_intent: advantages
  expected_entity: rock-filled concrete

- id: rfc_benefit_synonym
  q1: RFC的优势
  q2: rock-filled concrete 有什么好处
  expected_same_identity: true
  expected_intent: advantages

- id: rfc_cause_not_advantage
  q1: 堆石混凝土的优势
  q2: 堆石混凝土裂缝成因
  expected_same_identity: false

- id: different_entity_no_reuse
  q1: 堆石混凝土的优势
  q2: 自密实混凝土的优势
  expected_same_identity: false

- id: visual_followup_identity
  history:
    - 大坝裂缝成因有哪些？请详细列出
  q1: 我需要图片支撑
  q2: 给我相关图示
  expected_same_identity: true
  expected_intent: visual_evidence

- id: table_followup_identity
  history:
    - 堆石混凝土材料参数有哪些？
  q1: 给我表格
  q2: 有参数表吗
  expected_same_identity: true
  expected_intent: table_evidence
```

The initial YAML case file has been created at:

```text
data/evaluation/phase58h_cache_canonicalization_cases.yaml
```

## Metrics

Runtime resume:

```text
resume_success_rate
stale_resume_block_rate
checkpoint_corruption_fail_safe_rate
tool_execution_skipped_after_resume_count
median_resume_elapsed_ms
median_fresh_elapsed_ms
```

Evidence cache:

```text
same_identity_accuracy
different_identity_accuracy
query_embedding_cache_hit_rate
retrieval_cache_hit_rate
rerank_cache_hit_rate
tool_result_cache_hit_rate
median_warm_elapsed_ms
median_cold_elapsed_ms
costly_step_skip_count
```

## Test Strategy

Unit tests:

- deterministic canonical identity;
- safety blockers;
- checkpoint serialization/deserialization;
- resume policy selection.

Integration-style tests:

- fake runtime run repository with stop/resume;
- fake Redis layered cache proving second similar query hits;
- API/stream metadata contains resume and canonical cache fields.

Real-chain optional evaluation:

- only when Redis and reranker are healthy;
- bounded case count;
- sanitized CSV output only.

## Acceptance Gate

Phase 58H is ready for human verification only if:

- focused unit/integration tests pass;
- evaluation scripts can run in dry-run mode without external providers;
- optional real-chain run shows at least one similar-query pair hitting evidence cache layers;
- stop/resume cases demonstrate resumed runs skip at least one completed expensive node;
- all generated artifacts pass the project's data safety boundary.
