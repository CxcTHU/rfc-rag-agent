# Phase 58I Runtime Flow Evaluation Plan

## Goal

Verify the mature runtime flow after semantic evidence cache and HyDE are added.

## Evaluation Cases

### Semantic Evidence Cache Hit

Pairs should share semantic evidence identity and hit on the second run:

```text
堆石混凝土的劣势呢？
堆石混凝土的缺点有哪些？

堆石混凝土裂缝问题
堆石混凝土裂纹/缝隙问题
```

Expected second run:

```text
semantic_cache_hit=true
tool_result_cache_hit=true
hyde_generated=false
retrieval_cache_reason=not_checked
rerank_cache_reason=not_checked
answer generated fresh
```

### Semantic Evidence Cache Miss + HyDE

First run for a new semantic identity should miss evidence cache and may run
HyDE:

```text
semantic_cache_hit=false
hyde_generated=true
retrieval_cache_hit=false or true
rerank_provider visible
selected_chunk_ids present
```

### Different Intent Does Not Reuse

Different entity or materially different intent must not reuse evidence:

```text
堆石混凝土的缺点有哪些？
堆石混凝土配合比参数表
```

Expected:

```text
semantic_cache_hit=false
evidence_intent_key differs
```

## Regression Tests

Unit tests should cover:

- semantic evidence hit skips tool selection and HyDE;
- canonical query text drift does not split structured cache identity;
- HyDE trace is generated only on miss;
- HyDE text is not included in final sources or citations;
- retrieval vector query can differ from keyword query when HyDE is active.

## Safety Checks

Evaluation artifacts store only case ids, booleans, timings, tool names,
selected chunk ids, short labels, and safe trace flags. They must not store full
answers, full chunks, HyDE passage text, raw provider responses, hidden
reasoning, secrets, or restricted full text.
