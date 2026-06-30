# Phase 58H Evidence Cache Canonicalization Plan

## Goal

Make semantically equivalent evidence requests reuse expensive evidence-chain work without reusing final answers.

Example target:

```text
Q1: 堆石混凝土的优势
Q2: 堆石混凝土有哪些优点
```

The second question should be able to reuse the first question's canonical evidence query, query embedding, retrieval candidate cache, rerank order cache, and tool result cache when safe.

## Non-Goal

This is not answer-level answer caching. The old broad Semantic Cache runtime is removed; the final answer must still be generated fresh for the current user question using current sources and citations.

## Current Gap

Phase 56 layered cache exists, but most identities still depend on normalized query text:

```text
query embedding cache -> normalized query
retrieval candidate cache -> normalized query
rerank order cache -> normalized query + candidate hash
tool result cache -> stable user-question hash or tool query
```

Existing entity/anchor systems improve retrieval and memory, but they do not currently define a shared evidence cache identity. Therefore:

```text
堆石混凝土的优势 != 堆石混凝土有哪些优点
```

at the cache-key layer.

## Design

Add a runtime-owned `EvidenceQueryIdentity` before evidence-chain caches:

```text
raw_user_query
-> runtime context
-> entity extraction / canonical material or standard
-> intent canonicalization
-> canonical_evidence_query
-> evidence_cache_key
-> query embedding / retrieval / rerank / tool-result cache
-> fresh final answer
```

Suggested structure:

```text
EvidenceQueryIdentity
- raw_query
- canonical_query
- entity_key
- intent_key
- modifiers
- source: deterministic | llm_proposal | cache_hit
- confidence
- safe_for_cache_reuse
- reason
```

## Entity And Intent Canonicalization

Reuse existing capabilities where possible:

- GraphRAG material aliases and standard canonicalization;
- session/retrieval anchors;
- runtime standalone task;
- domain lexicons for common concrete/dam/material topics.

Add a narrow intent map for high-frequency evidence intents:

```text
advantages: 优势, 优点, 好处, 优越性, advantage, benefit
causes: 成因, 原因, 机理, cause, reason
measures: 措施, 方法, 方案, treatment, mitigation
classification: 类型, 分类, 种类, category
definition: 是什么, 概念, 定义, definition
comparison: 对比, 区别, 差异, compare
visual_evidence: 图片, 图示, 曲线, figure, image
table_evidence: 表格, 参数, 数据, table, parameter
```

The canonical query should remain human-readable and retrieval-friendly:

```text
堆石混凝土 优势 优点 工程性能 成本 水化热 施工效率
```

## Cache Integration

Use canonical evidence identity only for evidence-chain caches:

- query embedding cache;
- retrieval candidate cache;
- rerank order cache;
- tool result cache.

Do not change:

- displayed user question;
- final answer prompt question;
- conversation message content;
- citation/source validation.

Cache identity should include:

```text
canonical_query
entity_key
intent_key
tool_name
top_k or dynamic marker
embedding provider/model/dimension
reranker provider/model/fallback lane
corpus fingerprint
runtime schema version
```

## Safety Rules

Do not reuse canonical evidence identity when:

- current query is off-topic or fails responsibility guardrails;
- user asks for a different entity, standard, document, date, source, or constraint;
- query contains negation that changes intent;
- query asks for "最新", "本次", "这个图片", "上一段", or other context-specific references that cannot be safely canonicalized;
- entity or intent confidence is below threshold;
- runtime detects conflict between history anchor and current query anchor.

Fail-safe behavior:

```text
uncertain canonicalization -> use raw normalized query identity
```

## Diagnostics

Add safe latency trace fields:

```text
evidence_query_canonicalized
evidence_canonical_query
evidence_entity_key
evidence_intent_key
evidence_cache_identity_source
evidence_cache_identity_confidence
evidence_cache_reuse_allowed
evidence_cache_reuse_block_reason
```

Bound string lengths. Do not record full chunks, raw provider responses, hidden reasoning, or secrets.

## Acceptance Criteria

- `堆石混凝土的优势` and `堆石混凝土有哪些优点` map to the same `entity_key=intent_key` pair and canonical evidence query.
- Second run can hit query embedding, retrieval, rerank, and/or tool-result cache when Redis is healthy.
- Final answer is generated fresh and remains citation-backed.
- A different intent such as `堆石混凝土的裂缝成因` does not reuse the advantages evidence identity.
- A different entity such as `自密实混凝土的优势` does not reuse the RFC evidence identity unless explicitly configured as a comparison or related material query.
- Cache diagnostics explain hit/miss/block reasons.

## Implementation Notes

Start deterministic. Add an LLM proposal provider only after deterministic coverage is stable.

Recommended first implementation:

1. `app/services/agent/evidence_identity.py`
2. deterministic entity alias and intent lexicon;
3. runtime attaches `EvidenceQueryIdentity` to `LatencyTrace`;
4. layered cache identity functions read canonical evidence query when present;
5. tests prove exact and similar questions share evidence identity.
