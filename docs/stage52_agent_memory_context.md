# Stage 52 AgentMemoryContext Design

## Objective

Phase 52 unifies two existing short-term memory paths:

- Phase 43 `SessionMemory`: entities, retrieval anchors, constraints, and stale anchors extracted from the current conversation.
- Phase 51 prior evidence: `prior_sources`, `prior_citations`, and `prior_answer_summary` restored from the latest LangGraph checkpoint for the same conversation thread.

The unified object is `AgentMemoryContext`. It is short-lived, scoped to the current conversation, and used only for planner decisions and retrieval hints. It is not a citation source by itself.

## Runtime Position

```text
/agent/query mode="langgraph_agent"
-> initialize_state()
-> load latest checkpoint prior evidence
-> build AgentMemoryContext
-> planner_node
   -> decide reuse prior evidence, refresh search, refuse, or call tools
-> search / answer nodes
-> AgentQueryResponse latency_trace memory metadata
```

`AgentMemoryContext` does not replace RAG retrieval. When final answers use prior evidence, they reuse compacted source records that originally came from retrieved sources. Session summaries and memory hints are never passed as citations.

## Data Shape

```text
AgentMemoryContext
  session: SessionMemory
    entities: MemoryItem(text, turn_index, importance)
    retrieval_anchors: MemoryItem(text, turn_index, importance)
    constraints
    stale_anchors: MemoryItem(text, turn_index, importance)
  prior_evidence: PriorEvidenceMemory
    sources
    citations
    answer_summary
  prior_relevance: PriorEvidenceRelevance
    score
    passed
    threshold
  intent: MemoryIntent
    label
    confidence
    source
  long_term: LongTermMemoryState
    enabled=false
    status=disabled
  decision_hint
  policy: MemoryPolicyDecision
    planner_route
    use_prior_evidence_for_answer
    augment_retrieval_query
    memory_used_for_planning
    memory_used_for_retrieval
    memory_used_for_answer
    memory_citation_source=false
```

The context is serialized into LangGraph state as JSON-native dictionaries and lists so RedisSaver can checkpoint it safely.

The serialized state includes `schema_version=1`. Existing checkpoints without a schema version are still accepted fail-open by `agent_memory_context_from_state()`, and legacy string session-memory lists are restored as `MemoryItem(text, turn_index=0, importance=1.0)`.

## Semantic Upgrade

Phase 52G-52K adds three semantic controls:

- `MemoryIntentClassifier`: a protocol with `LLMMemoryIntentClassifier` and `DeterministicMemoryIntentClassifier`. The deterministic implementation preserves local/CI behavior; the LLM implementation uses a compact few-shot JSON classifier and falls back deterministically on invalid output.
- `PriorEvidenceRelevanceGate`: checks current question plus recent history against `prior_answer_summary` or compact prior source text/title using embedding cosine similarity. Prior evidence reuse now depends on `prior_relevance.passed`, not a fixed source-count threshold.
- `MemoryItem` recency decay: session entities and retrieval anchors carry `turn_index` and `importance`. Recent anchors are ranked ahead of old anchors, and `decay_session_memory()` can recompute importance with a half-life.

## Decision Rules

- `reuse_prior_evidence`: expansion follow-up such as "请详细回答" and enough prior evidence exists.
- `prior_evidence_available`: contextual follow-up with prior evidence available, but not necessarily enough to skip search.
- `stale_anchor_refresh_search`: user correction marks previous anchors stale; planner must search again instead of reusing old evidence.
- `session_memory_retrieval_hint`: session memory exists and can augment contextual retrieval.
- `no_memory`: no useful memory is available.

`MemoryPolicyDecision` is the explicit policy layer above these hints. It maps memory context into auditable routes such as `answer_from_prior_evidence`, `search_with_memory_context`, and `refresh_search_ignore_stale_memory`. Prior evidence can only be used for answer generation when enough prior source records exist and no stale anchors are present. Session memory can guide retrieval, but `memory_citation_source` remains false.

## Observability

Phase 52 records memory metadata in `latency_trace`:

```text
memory_context_present
memory_session_entity_count
memory_session_anchor_count
memory_session_stale_anchor_count
memory_prior_source_count
memory_prior_citation_count
memory_prior_relevance_score
memory_prior_relevance_passed
memory_long_term_enabled
memory_intent_label
memory_intent_confidence
memory_intent_source
memory_decision_hint
memory_policy_route
memory_used_for_planning
memory_used_for_retrieval
memory_used_for_answer
memory_prior_evidence_used_for_answer
memory_citation_source
memory_refusal_boundary
```

These fields are counts and labels only. They do not store full chunks, raw provider responses, user profiles, or hidden reasoning.

The code-level contract is `MEMORY_TRACE_FIELDS` in `app/services/agent/memory_context.py`. Tests assert that `AgentMemoryContext.trace()` returns exactly that safe field set.

## Long-Term Memory Boundary

Long-term memory is represented only as a disabled interface state:

```text
enabled=false
status=disabled
read_count=0
write_count=0
```

Future activation would require explicit user authorization, deletion controls, audit logs, retention limits, and data minimization. Phase 52 adds governance-shaped interfaces (`MemoryConsent`, `MemoryRetentionPolicy`, `MemoryDeletionRequest`, and `MemoryAuditRecord`) plus a disabled provider implementation. It does not write long-term memory to any database.

The disabled provider must not echo write payloads, deletion reasons, user profile text, or other sensitive content. Its audit record only reports the operation, disabled status, whether ids were present, and a generic disabled detail.

## Safety Boundary

- No new external data source.
- No real provider call is required for tests.
- No API key, bearer token, raw provider response, `raw_response`, `reasoning_content`, hidden thought, complete chunk body, restricted full text, or long-term user profile is written to Git, CSV, docs, tests, or Obsidian.
- Memory hints may improve retrieval queries, but final citations must come from retrieved or prior retrieved sources.
