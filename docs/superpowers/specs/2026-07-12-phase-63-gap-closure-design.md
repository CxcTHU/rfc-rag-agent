# Phase 63 Retrieval Runtime Gap Closure Design

## Status And Authority

This design supersedes the remaining-work decisions in the earlier Phase 63
retrieval-chain remediation design. It closes the six gaps confirmed by code
review and real E2E evidence before the Retrieval Runtime can become the default
production path.

No Git submission action is authorized by this document. The working tree must
remain unstaged and uncommitted until automated gates and user human verification
pass.

## Problem Statement

Phase 63 has successfully consolidated the public Agent onto Tool Calling,
restored BM25 and PostgreSQL pgvector HNSW, made FAISS observable fail-open,
introduced bounded Local GraphRAG, restored provider-token streaming, and made
live/final retrieval counts consistent. The latest safe PostgreSQL E2E artifact
passes eight cases, but its median first-token latency is about 31 seconds and
its P95 is about 61 seconds. The 60-case legacy/current dataset is still a
schema-only dry run.

Six correctness gaps remain:

1. public `source_id` is accepted but ignored by the unified Tool Calling path;
2. required graph/table/figure lanes are not guaranteed in final evidence;
3. preferred and required Graph budgets are both 2 hops/75 matches;
4. historical negative intent can override a newer explicit positive request;
5. failure of both rerankers aborts the whole request despite usable fused
   evidence;
6. explicit figure routing has a Runtime correction path while explicit table
   routing does not.

These correctness gaps must close before latency optimization and default
rollout. Performance work must not weaken the final evidence contract.

## Goals

1. Remove silent public API behavior: every accepted request field must have an
   enforced meaning.
2. Make current-turn explicit intent authoritative over conversation history.
3. Make `required` a final-evidence invariant, not only a rerank-pool hint.
4. Restore the approved Graph budgets: preferred 1 hop/20 matches, required 2
   hops/50 matches.
5. Degrade safely from primary reranker to fallback reranker to fusion ranking,
   with explicit diagnostics and an evidence-quality gate.
6. Give explicit figure and table requests symmetric code-owned routing.
7. Reduce first-token P95 to 15 seconds or less without regressing answer or
   citation quality versus the legacy path.
8. Execute the real 60-case dual-runtime comparison and separate fault-profile
   E2E before enabling the Runtime by default.

## Non-Goals

- No fourth model-visible GraphRAG tool.
- No direct model control over result counts, graph hops, candidate budgets,
  rerank settings, fusion weights, cache policy, or fallback policy.
- No Microsoft GraphRAG Global Search, community reports, DRIFT, or graph schema
  migration.
- No PostgreSQL FTS migration in this closure; the existing BM25 result contract
  remains authoritative.
- No reintroduction of legacy Agent API dispatch modes.
- No answer-body, full-chunk, provider-payload, credential, or hidden-reasoning
  storage in evaluation artifacts.

## Architecture

```text
AgentQueryRequest
  -> Agent Runtime context assembly
  -> current-turn intent extraction
  -> history augmentation (cannot override current explicit intent)
  -> optional LLM intent augmentation
  -> RetrievalPlan
       required high-level tool: figure | table | none
       internal lanes: BM25 + pgvector + optional graph/table-text/figure-caption
       code-owned budgets
  -> one high-level retrieval action
  -> channel fusion
  -> required-lane reservation in the rerank pool
  -> primary reranker
       -> fallback reranker
       -> fusion Dynamic-K fail-soft
  -> constraint-aware final evidence selection
  -> final evidence gate
  -> cited provider-token streaming answer
```

The model may propose intent and a high-level tool call. The Runtime validates
and, for current-turn explicit table/figure requests, corrects the high-level
action. All retrieval algorithms and numeric budgets remain invisible to the
model.

## Public Request Contract

`source_id` is removed from `AgentQueryRequest`. The field belonged to a retired
source-detail intent and has no valid meaning in the unified evidence-search
contract. Pydantic continues to ignore retired extra fields during the rollout,
so old clients cannot alter behavior and are not allowed to select a legacy
runtime.

If source-scoped search is required later, it must be introduced as a new typed
contract such as `retrieval_scope`, with repository-level filtering and its own
authorization tests. It must not reuse `source_id` implicitly.

The public request remains:

```text
question
max_tool_calls
history
chat_model
conversation_id
image_path
resume_run_id
resume_policy
```

`mode`, `top_k`, and `source_id` are not public runtime controls.

## Temporal Intent Precedence

Current input and history are parsed separately. Precedence is:

```text
current explicit negative
> current explicit positive
> current implicit signal or valid LLM augmentation
> historical positive/negative context
```

Examples:

| History | Current turn | Result |
|---|---|---|
| “不要图片” | “现在给我施工图片” | figure required |
| “请给表格” | “这次只用文字” | table disabled |
| “分析标准关系” | “继续” | relationship context may remain preferred |
| none | “不要分析上下游关系” | graph disabled |

The deterministic parser produces separate `current_profile` and
`history_profile`. The merge function receives both explicitly. An LLM result
may augment an unspecified current field but cannot override a current explicit
positive or negative decision.

## High-Level Tool Routing

The model-visible tool surface remains:

- `hybrid_search_knowledge`
- `search_figures`
- `search_tables`

The Retrieval Plan adds a code-owned directive:

```python
HighLevelToolName = Literal[
    "hybrid_search_knowledge",
    "search_figures",
    "search_tables",
]

@dataclass(frozen=True)
class RetrievalAction:
    required_tool: HighLevelToolName | None
    forbidden_tools: tuple[HighLevelToolName, ...]
    reason: str
```

Rules:

- explicit current figure intent requires `search_figures`;
- explicit current table intent requires `search_tables`;
- explicit negative figure/table intent forbids that asset tool;
- ordinary and relationship questions use Hybrid;
- implicit modality intent may remain model-selected;
- GraphRAG remains an internal Hybrid lane.

For a required asset tool, the Runtime executes one normal, observable preflight
tool action before final generation. It emits the same start/result events and
stable step ID as a model-originated tool call. It does not run Hybrid first and
then append asset evidence as an untracked correction.

## Graph Budget Contract

| Requirement | Max hops | Max graph matches | Final evidence rule |
|---|---:|---:|---|
| disabled | 0 | 0 | no graph lane |
| preferred | 1 | 20 | no minimum |
| required | 2 | 50 | at least one graph-supported item when available |

`HYBRID_GRAPH_MAX_MATCHES=50` is the hard global ceiling. Runtime profiles may
reduce but never raise it. Cache identity includes requirement, hops, matches,
graph fingerprint, and retrieval schema so old 75-match entries cannot satisfy
the new contract.

## Required Evidence Invariant

Required evidence is enforced at two points:

1. `reserve_required_channel_candidates` ensures at least one available
   candidate from each required internal lane enters the bounded rerank pool.
2. `select_constrained_evidence` applies Dynamic-K over reranker order while
   preserving one reranked item from each required lane when available.

This is constraint-aware selection, not post-rerank evidence injection. Every
selected item has passed through the same reranker or the explicitly diagnosed
fusion fail-soft path.

The final `EvidenceRequirementStatus` records:

```python
@dataclass(frozen=True)
class EvidenceRequirementStatus:
    required_channels: tuple[str, ...]
    satisfied_channels: tuple[str, ...]
    missing_channels: tuple[str, ...]
    available_required_candidates: tuple[str, ...]
```

If a current explicit requirement remains missing, final generation receives an
evidence-insufficient decision and must not claim that the requested relation,
table, or figure was found. It may provide supported text facts only when it
clearly states the requested evidence type was unavailable; otherwise it
refuses.

## Reranker Failure Policy

The balanced availability policy is:

```text
primary BGE reranker
  -> configured GLM fallback reranker
  -> fused BM25/pgvector/optional-lane ordering + Dynamic-K
```

The third lane is allowed only when retrieval candidates exist. It records:

```text
reranking_degraded=true
reranking_degradation_level=fusion_fail_soft
reranking_error_type=<bounded code>
retrieval_selection_reason=reranker_unavailable_fusion_dynamic
```

Raw exception text and provider responses are excluded. Required evidence and
minimum support checks still run after fail-soft selection. A request fails only
when no usable evidence remains or the final evidence gate cannot support a safe
answer.

Normal release cases require no reranking degradation. Dedicated fault-profile
cases require 100% completion through the diagnosed fusion lane.

## Latency Strategy

Correctness tasks precede performance changes. The performance pass then:

1. skips the identity-model call when current deterministic intent and canonical
   evidence identity are sufficient;
2. directly executes required figure/table actions without an unnecessary model
   tool-selection round;
3. preserves retrieval/rerank/tool-result cache fast paths;
4. records non-overlapping identity, tool-decision, retrieval, rerank, answer,
   first-token, and final latency;
5. keeps real provider-token streaming and never treats post-completion text
   slicing as success.

Release targets:

| Metric | Gate |
|---|---:|
| first-token P50 | `<= 8s` |
| first-token P95 | `<= 15s` |
| final P95 | `<= 30s` |
| ordinary answer accuracy delta | `>= 0` versus legacy |
| citation validity delta | `>= 0` versus legacy |

If provider latency makes the absolute targets impossible, rollout remains
disabled; the gate is not relaxed by documentation.

## Evaluation And Rollout

The existing 60-case dataset is executed against distinct legacy and Phase 63
endpoints. The evaluator must not send retired `mode`, `top_k`, or `source_id`
fields. Separate endpoints inject identity-provider, graph, pgvector, primary
reranker, and dual-reranker failures.

Required gates:

| Gate | Requirement |
|---|---:|
| relationship route precision/recall | `>= 0.90 / >= 0.90` |
| explicit figure/table fulfillment | `100% / 100%` |
| current-turn override cases | `100%` |
| graph-negative false positives | `0` |
| required channel satisfaction when candidates exist | `100%` |
| planner/graph fault completion | `100%` |
| dual-reranker fault completion | `100%` |
| normal BM25 backend | `100%` Hybrid cases |
| normal pgvector HNSW backend | `100%` retrieval cases |
| live/final selected-count equality | `100%` |
| true streaming | `100%` normal cases |
| answer/citation quality delta | `>= 0` versus legacy |

After all automated gates pass, a PostgreSQL/pgvector process runs on port 8000
with both Retrieval Runtime flags enabled for user human verification. The
default configuration changes only after that verification. No stage, commit,
tag, push, or PR occurs before explicit authorization.

## Security And Observability

Safe diagnostics contain bounded enums, counts, IDs, hashes, backend names,
selected chunk IDs, short title/type previews, and timings. They do not contain
full chunks, raw answers, provider payloads, hidden reasoning, credentials,
Bearer tokens, database passwords, private logs, or restricted full text.

## Acceptance Criteria

Phase 63 gap closure is complete only when:

1. all six correctness gaps have RED/GREEN regression coverage;
2. focused and full backend/frontend suites pass;
3. normal PostgreSQL E2E proves BM25, pgvector HNSW, Dynamic-K consistency, and
   provider-token streaming;
4. separate fault E2E proves graph, pgvector, and dual-reranker degradation;
5. the 60-case real dual-runtime A/B passes all quality and latency gates;
6. Runtime-enabled port 8000 browser E2E passes;
7. user human verification passes;
8. only then may the default flags and Git submission state change.
