# Stage 53 Adaptive RAG And GraphRAG Plan

## Phase 53B Scope

Phase 53B adds an explicit Adaptive RAG strategy label to the existing planner
layer. It does not change routing behavior, tool permissions, retrieval
weights, reranker settings, or the default Agent mode.

The label answers a narrow observability question:

```text
planner action -> retrieval_strategy -> latency_trace
```

This makes later GraphRAG routing auditable without making the current
retrieval chain more complex.

## Strategy Labels

```text
search_knowledge       -> hybrid_knowledge_search
search_tables          -> table_search
search_figures         -> figure_search
analyze_user_image     -> user_image_analysis
rewrite_query          -> query_rewrite
answer_with_citations  -> answer_from_retrieved_evidence
prior evidence answer  -> answer_from_prior_evidence
refuse                 -> safe_refusal
final_answer           -> final_answer
no planner decision    -> none
```

`answer_from_prior_evidence` is only used when the memory policy explicitly
allows direct prior-evidence reuse. Memory summaries remain planner/retrieval
hints only and never become citation sources.

## Runtime Surface

`LatencyTrace` now initializes:

```text
retrieval_strategy=none
```

ReAct and LangGraph planner paths update this field after selecting the next
action. The field is a safe enum label only. It does not include query text,
chunk content, provider responses, keys, hidden reasoning, or user-uploaded
bytes.

## Why This Comes Before GraphRAG

GraphRAG will add a new retrieval lane:

```text
query entity extraction -> graph traversal -> graph chunk ids
```

Before adding that lane, the existing planner choices need explicit labels so
future evaluation can separate:

- ordinary hybrid text retrieval,
- table retrieval,
- figure retrieval,
- prior-evidence reuse,
- future graph-enhanced retrieval,
- safe refusal.

This keeps Stage 53C-53F changes measurable instead of hiding them behind a
generic `planner_model` or `tool_name`.

## Safety Boundary

- No external data source is added in Phase 53B.
- No real API call is required for tests.
- No provider payload, hidden thought, credentials, full chunk, or restricted
  full text is stored.
- The implementation is label-only and fail-neutral: if future code ignores
  `retrieval_strategy`, existing answer behavior is unchanged.

## Phase 53C GraphRAG Extraction

Phase 53C adds the structured extraction layer that feeds the later NetworkX
graph. It is intentionally separate from graph storage and retrieval so the
triple format can be tested before any ranking behavior changes.

The allowed entity types are:

```text
Standard
Material
Parameter
Value
Organization
Method
```

The allowed relation types are:

```text
standard_defines
standard_references
material_has_property
parameter_range
applies_to
```

`app/services/graphrag/schema.py` owns the whitelist, normalization, dict
round-trip helpers, and de-duplication. `app/services/graphrag/extractor.py`
owns two extraction modes:

- deterministic dry-run extraction, used by default and in CI;
- LLM extraction, enabled only when a caller passes `execute_llm=True` and
  provides a configured chat model provider.

The extractor never persists provider payloads. LLM responses are parsed from
the answer text into the same schema, and unsupported entity or relation types
are dropped.

## Batch Extraction Script

`scripts/extract_phase53_graphrag_triples.py` samples text chunks from the
database and writes JSON:

```powershell
.venv\Scripts\python.exe scripts\extract_phase53_graphrag_triples.py `
  --limit 100 `
  --output data\evaluation\phase53_graphrag_triples_sample.json
```

The script defaults to deterministic dry-run mode. Use `--execute` only for an
explicit real-model run with local `CHAT_MODEL_*` configuration.

Each output row includes only:

```text
chunk_id
document_id
document_title
status
extractor
entities
relations
short error, when present
```

Rows omit chunk content, provider payloads, hidden reasoning, credentials, and
restricted full text. This makes the JSON suitable as a derived extraction
artifact for graph construction and evaluation.

## Phase 53D NetworkX Graph Store

Phase 53D turns extraction rows into a persistent NetworkX `MultiDiGraph`.
The implementation lives in `app/services/graphrag/graph_store.py`.

Node ids are derived from entity type and normalized entity name:

```text
Material:rock-filled concrete
Parameter:compressive strength
Standard:gb/t 50080
```

Each node stores:

```text
name
type
normalized_name
mentions
chunk_ids
```

Each edge stores:

```text
type
source_chunk_id
short evidence, when present
```

The graph is saved as deterministic JSON rather than Python pickle, so it can
be inspected, diffed, and loaded across runs without executing serialized code.

Build a graph from a 53C extraction file:

```powershell
.venv\Scripts\python.exe scripts\build_phase53_graphrag_graph.py `
  --input data\evaluation\phase53_graphrag_triples_sample.json `
  --output data\evaluation\phase53_graphrag_graph.json `
  --stats-output data\evaluation\phase53_graphrag_graph_stats.json
```

The script prints and optionally writes:

```text
node_count
edge_count
connected_components
degree_distribution
node_type_counts
edge_type_counts
```

The graph JSON remains derived metadata only. It does not include chunk text,
provider payloads, hidden reasoning, credentials, or restricted full text.

## Phase 53E Graph-Enhanced Retrieval

Phase 53E adds `GraphEnhancedSearchService` in
`app/services/graphrag/graph_search.py`. The service wraps the existing hybrid
retrieval path instead of replacing it:

```text
query -> graph entity match -> 1-2 hop traversal -> graph chunk ids
      -> existing hybrid retrieval -> dedupe/fuse -> results
```

The graph lane matches query text against node names, normalized names, and
mentions. It then traverses an undirected view of the NetworkX graph up to two
hops, collecting chunk ids from nearby nodes and relation `source_chunk_id`
attributes.

Fusion is chunk-id based:

- existing hybrid results are preserved and can receive a small graph boost;
- graph-only chunks are appended with graph-derived scores;
- duplicate chunks are removed before the final top-k sort.

The service is fail-open. If the graph is missing, malformed, or not configured,
the service records the graph fallback in `LatencyTrace` and returns ordinary
hybrid results.

Trace fields added for graph retrieval:

```text
graph_search_latency_ms
graph_search_available
graph_search_fallback
graph_search_error
graph_entity_count
graph_candidate_chunk_count
graph_hop_count
```

These fields are numeric or enum-like operational metadata only. They do not
store queries, chunk text, provider responses, hidden reasoning, or secrets.

## Phase 53F LangGraph Integration

Phase 53F exposes graph retrieval as the read-only agent action
`search_graph_knowledge`.

The integration points are:

```text
ReActActionType              -> search_graph_knowledge
AdaptiveRetrievalStrategy    -> graph_enhanced_search
AgentToolbox                 -> search_graph_knowledge()
LangGraph node               -> search_graph_knowledge_node
LangGraph route              -> planner -> search_graph_knowledge -> planner
```

The deterministic planner only routes obvious graph-shaped questions to this
tool, such as cross-document relationships, standard reference chains, linked
RFC concepts, or explicit knowledge-graph requests. Ordinary concept and
mechanism questions still use `search_knowledge`.

The graph tool uses the Phase 53E service and therefore preserves fail-open
behavior. If the configured graph JSON is missing or malformed, the tool still
returns hybrid retrieval results and records graph fallback metadata in the
latency trace.

The agent response contract is unchanged:

```text
tool_calls
workflow_steps
search_results
sources
citations
latency_trace
```

The new tool name may appear in `tool_calls` and `workflow_steps`, and
`latency_trace.retrieval_strategy` may be `graph_enhanced_search`. Graph trace
fields remain sanitized operational metadata only.
