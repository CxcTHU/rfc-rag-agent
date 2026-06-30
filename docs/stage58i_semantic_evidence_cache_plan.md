# Phase 58I Semantic Evidence Cache Plan

## Goal

Phase 58I adds a runtime-level semantic evidence cache path to the default
`tool_calling_agent`.

This is not answer-level Semantic Cache. A hit reuses cached evidence/tool
results and still generates a fresh final answer from current hydrated sources.

## Runtime Flow

```text
Context Assembly
-> Query Rewrite / Contextualization
-> Semantic Evidence Cache Lookup
   -> hit: hydrate cached tool result evidence, skip tool selection/retrieval/rerank
   -> miss: continue to HyDE and normal retrieval
-> HyDE
-> Retrieval / Rerank
-> Evidence State
-> Final Answer
```

## Cache Identity

The cache identity must prefer structured semantic identity:

```text
entity_key + intent_key + constraints fingerprint
```

`canonical_query` is allowed to drive retrieval text, but it must not be the
primary cache key because a small model may emit semantically equivalent Chinese
or English canonical queries.

## Hit Semantics

On hit:

- hydrate chunk ids from PostgreSQL;
- rebuild sources and citation locations;
- record a normal workflow/tool step with `cache hit`;
- set `semantic_cache_hit=true`;
- set `tool_result_cache_hit=true`;
- skip HyDE, retrieval, and rerank;
- generate a fresh final answer from hydrated evidence.

On miss:

- set `semantic_cache_hit=false`;
- continue to HyDE and normal tool execution.

## Safety

Redis stores ids, ranks, scores, labels, timestamps, and bounded metadata only.
It must not store final answers, full chunk text as the durable cache contract,
provider raw responses, hidden reasoning, credentials, restricted full text, or
raw uploaded image bytes.
