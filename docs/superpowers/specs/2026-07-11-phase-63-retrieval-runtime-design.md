# Phase 63 Retrieval Runtime Upgrade Design

## Status And Scope

Phase 63 upgrades the default retrieval chain without replacing the default
`tool_calling_agent` shell or exposing retrieval algorithms to the model.

The default model-visible retrieval tools remain:

```text
hybrid_search_knowledge
search_tables
search_figures
```

`search_knowledge` remains available for compatibility, debugging, and direct
keyword-search evaluation, but is removed from the default tool-calling model's
tool definitions.

Phase 63 does not add a single `retrieve_evidence` super-tool. It does not add
Microsoft GraphRAG community reports, Global Search, or DRIFT. It upgrades the
existing local entity-and-relation GraphRAG path.

## Goals

1. Make one structured retrieval-intent plan the source of truth for optional
   channel activation.
2. Replace the default graph channel's primary hard-coded term gate with an LLM
   semantic intent proposal plus deterministic Runtime validation and fallback.
3. Represent graph retrieval as a standard internal `GraphRetriever` with a
   bounded request plan, safe provenance, and one implementation shared by the
   default Hybrid path and graph-specific compatibility APIs.
4. Keep candidate budgets, graph depth, fusion weights, and evidence quotas
   Runtime-owned. The model may propose intent and confidence but cannot choose
   arbitrary numeric budgets.
5. Preserve one final Hybrid rerank and Dynamic-K path. Graph candidates must not
   be reranked independently before entering the default Hybrid pool.
6. Version retrieval cache identity with the Phase 63 plan, budget profile,
   fusion configuration, and graph content fingerprint.
7. Roll out behind configuration and compare legacy versus Phase 63 behavior
   before any default switch.

## Non-Goals

- No new graph extraction or graph schema migration.
- No community detection, community-report generation, map-reduce Global Search,
  or DRIFT follow-up generation.
- No learned online budget optimizer.
- No direct LLM control over `top_k_entities`, relationship limits, graph hops,
  rerank candidate counts, or cache policy.
- No replacement of Structured TableRAG or figure-asset search.
- No change to public Agent request/response schemas.
- No silent reranker fallback.

## Architecture

```text
ToolCallingAgentService
  -> AgentRuntime context assembly
  -> runtime_identity_provider structured proposal
  -> RetrievalIntentProfile + EvidenceQueryIdentity
  -> RetrievalPlanner validation and budget-profile mapping
  -> current RetrievalPlan bound to request context
  -> model selects one of three high-level evidence tools
  -> HybridSearchService reads RetrievalPlan
     -> KeywordSearchService
     -> VectorSearchService
     -> GraphRetriever when graph is preferred/required
     -> table-text channel when planned
     -> figure-caption channel when planned
     -> weighted RRF and chunk-id dedupe
     -> one primary/fallback rerank path
     -> Dynamic K
  -> tool result converted to existing AgentSearchItem/source contracts
  -> Agent Runtime answer/refusal control
```

The retrieval plan uses a request-scoped `ContextVar`, following the existing
HyDE vector-query and latency-trace patterns. Direct `/search/hybrid` requests
that do not bind a Phase 63 plan continue to use the legacy deterministic
channel plan unless the new default switch is explicitly enabled.

## Components

### RetrievalIntentProfile

`app/services/retrieval/runtime.py` introduces an immutable profile:

```python
RetrievalExplicitness = Literal["explicit", "implicit", "none", "negative"]
GraphSearchMode = Literal["none", "local"]

@dataclass(frozen=True)
class RetrievalIntentProfile:
    visual_intent: float = 0.0
    table_intent: float = 0.0
    relationship_intent: float = 0.0
    relationship_type: str = "none"
    graph_search_mode: GraphSearchMode = "none"
    visual_explicitness: RetrievalExplicitness = "none"
    table_explicitness: RetrievalExplicitness = "none"
    relationship_explicitness: RetrievalExplicitness = "none"
    entities: tuple[str, ...] = ()
    required_evidence_types: tuple[str, ...] = ()
    source: str = "deterministic"
```

All confidence fields are clamped to `[0.0, 1.0]`. They are routing scores, not
calibrated probabilities.

### RetrievalPlan

```python
ChannelRequirement = Literal["disabled", "preferred", "required"]
GraphBudgetProfile = Literal["disabled", "preferred", "relation"]

@dataclass(frozen=True)
class RetrievalPlan:
    schema: str
    canonical_query: str
    graph_requirement: ChannelRequirement
    graph_budget_profile: GraphBudgetProfile
    graph_max_hops: int
    graph_max_matches: int
    table_text_requirement: ChannelRequirement
    figure_caption_requirement: ChannelRequirement
    required_evidence_types: tuple[str, ...]
    intent_source: str
```

The first implementation uses deterministic profiles:

| Profile | Max hops | Max graph matches | Final graph evidence rule |
|---|---:|---:|---|
| disabled | 0 | 0 | none |
| preferred | 1 | 20 | no minimum |
| relation | 2 | 50 | at least one graph-supported candidate when available |

The configured `HYBRID_GRAPH_MAX_MATCHES` remains a hard upper bound. Runtime
profiles may reduce it but never increase it.

### LLM Proposal And Deterministic Fallback

The existing `runtime_identity_provider` call is extended rather than adding a
new provider request. Its JSON response includes the existing cache-identity
fields plus:

```json
{
  "visual_intent": 0.0,
  "table_intent": 0.0,
  "relationship_intent": 0.0,
  "relationship_type": "none",
  "graph_search_mode": "none",
  "visual_explicitness": "none",
  "table_explicitness": "none",
  "relationship_explicitness": "none",
  "entities": [],
  "required_evidence_types": []
}
```

The Runtime validator applies these rules:

1. Invalid JSON, provider failure, unsupported labels, or non-finite confidence
   values produce a deterministic fallback profile.
2. Explicit negative image/table/relationship instructions disable that evidence
   type even if a positive term is also present.
3. A `relationship_type` without a relationship intent or local graph mode is
   normalized to `none`.
4. `relationship_intent >= 0.80` maps to `required` when explicit and to
   `preferred` when implicit.
5. `0.45 <= relationship_intent < 0.80` maps to `preferred`.
6. Lower scores map to `disabled`.
7. Deterministic graph terms remain only as provider-failure fallback. They are
   not allowed to override a valid LLM plan.

The thresholds are configuration values so evaluation can calibrate them without
changing code.

### GraphRetriever

`app/services/graphrag/retriever.py` owns local graph retrieval:

```python
@dataclass(frozen=True)
class GraphCandidate:
    chunk_id: int
    score: float
    hop_count: int
    matched_entities: tuple[str, ...]
    relation_types: tuple[str, ...]
    relation_evidence: tuple[str, ...]

class GraphRetriever:
    def retrieve(
        self,
        query: str,
        *,
        max_hops: int,
        max_matches: int,
        relation_focus: str | None = None,
    ) -> list[GraphCandidate]:
        ...
```

It reuses existing graph-store and graph-search primitives. It does not generate
answers or perform a separate rerank. It maps graph matches to original chunks
and retains bounded provenance for diagnostics and relation-aware reranking.

### Fusion And Relation-Aware Rerank

Graph candidates enter the same weighted RRF pool as keyword and vector
candidates. Raw graph scores are never directly added to vector or keyword
scores.

When a graph candidate reaches the final rerank pool, its rerank text may append
a bounded relation hint:

```text
<original chunk content>

Relation context: GB/T 50081 --defines--> compressive-strength test method
```

The relation hint is retrieval metadata only. Final citations and answer evidence
continue to point to original chunks. The hint is never exposed as an independent
source and is not persisted as raw provider output.

For `required` graph plans, candidate selection reserves one graph-supported slot
before filling the rest of the rerank pool. This preserves relationship evidence
without forcing graph-only answers.

### Table And Figure Planning

Phase 63 records visual and table intents in the shared plan, but does not replace
the explicit table and figure workflows.

- `hybrid_search_knowledge` may use `table_text` and `figure_caption` as textual
  evidence channels according to the plan.
- `search_tables` continues to return Structured TableRAG/table assets.
- `search_figures` continues to return real image assets.
- Tool Calling remains responsible for selecting a high-level asset tool.
- Runtime diagnostics record requested and satisfied evidence types so a later
  stage can add full cross-tool EvidenceBundle merging without changing Phase 63
  routing semantics.

## Cache Identity

The Phase 63 retrieval cache identity includes:

```text
retrieval_pipeline_schema=phase63-retrieval-runtime-v1
plan schema
intent source
graph requirement and budget profile
graph max hops and match limit
table-text and figure-caption requirements
enabled and eligible channels
fusion method and all channel weights
graph content fingerprint
HyDE vector-query hash
embedding provider/model/dimension
corpus fingerprint
```

The graph fingerprint is derived from safe file metadata plus file content hash;
the graph body is not written to diagnostics or cache payloads. Tool-result cache
identity for `hybrid_search_knowledge` includes the retrieval-pipeline schema and
plan digest so a legacy result cannot satisfy a Phase 63 request.

## Diagnostics

Safe trace fields include:

```text
retrieval_plan_schema
retrieval_intent_source
retrieval_visual_intent
retrieval_table_intent
retrieval_relationship_intent
retrieval_relationship_type
retrieval_graph_requirement
retrieval_graph_budget_profile
retrieval_graph_max_hops
retrieval_graph_max_matches
retrieval_required_evidence_types
retrieval_plan_fallback
retrieval_plan_fallback_reason
graph_candidate_count
graph_selected_count
graph_selected_chunk_ids
graph_relation_type_preview
graph_fingerprint
```

Diagnostics remain bounded and must not contain complete chunks, complete answers,
provider payloads, hidden reasoning, credentials, restricted text, or private logs.

## Failure Handling

- Intent provider unavailable: deterministic plan fallback; normal retrieval
  continues.
- Intent JSON invalid: deterministic plan fallback with a safe diagnostic reason.
- Graph file unavailable/corrupt: graph channel returns no candidates and records
  fallback; keyword/vector continue.
- Graph required but unavailable: evidence coverage records the gap; the Agent may
  answer supported non-relationship facts but must not invent the relationship.
- Primary reranker failure: preserve current strict fallback/refusal behavior.
- Redis unavailable/corrupt cache: preserve fail-open retrieval behavior.
- Request without a bound plan: use legacy channel planning unless the Phase 63
  default switch is enabled.

## Configuration And Rollout

New settings:

```text
RETRIEVAL_RUNTIME_ENABLED=false
RETRIEVAL_RUNTIME_DEFAULT_ENABLED=false
RETRIEVAL_RUNTIME_SCHEMA=phase63-retrieval-runtime-v1
RETRIEVAL_RELATIONSHIP_REQUIRED_THRESHOLD=0.80
RETRIEVAL_RELATIONSHIP_PREFERRED_THRESHOLD=0.45
RETRIEVAL_GRAPH_PREFERRED_MAX_HOPS=1
RETRIEVAL_GRAPH_PREFERRED_MAX_MATCHES=20
RETRIEVAL_GRAPH_REQUIRED_MAX_HOPS=2
RETRIEVAL_GRAPH_REQUIRED_MAX_MATCHES=50
```

Evaluation may enable `RETRIEVAL_RUNTIME_ENABLED` explicitly. Production/default
behavior remains legacy until automated gates and user human verification pass.

## Evaluation

The Phase 63 evaluation set contains at least these balanced slices:

```text
ordinary
explicit_relationship
implicit_relationship
standard_reference
graph_negative
relationship_negation
explicit_table
explicit_figure
followup_relationship
topic_shift
planner_failure
graph_unavailable
```

Required gates:

| Metric | Gate |
|---|---:|
| ordinary answer accuracy delta | `>= 0` versus legacy |
| relationship route precision | `>= 0.90` |
| relationship route recall | `>= 0.90` |
| graph-negative false positives | `0` |
| explicit figure fulfillment delta | `>= 0` |
| explicit table fulfillment delta | `>= 0` |
| citation validity delta | `>= 0` |
| planner failure fallback completion | `100%` |
| ordinary P95 latency increase | `<= 15%` |
| relationship P95 latency increase | `<= 30%` |
| silent reranker degradation | `0` |

The first evaluation is deterministic/dry-run. Real provider execution requires
an explicit `--execute` flag and stores only safe metadata.

## Compatibility

- Public Agent API and SSE schemas remain unchanged.
- Default high-level tool names remain unchanged.
- Direct keyword/vector/hybrid Search APIs remain available.
- Existing Stage 57, 58, 58H/I, and 60 tests remain regression gates.
- Legacy and Phase 63 paths coexist until human verification authorizes the
  default switch.

## Security

No Phase 63 artifact may include `.env`, `.env.prod`, credentials, API keys,
Bearer tokens, provider raw responses, raw answer text, hidden reasoning, full
chunks, restricted full text, private service logs, or long-term user profiles.
