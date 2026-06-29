# Phase 57 Multi-Channel Hybrid Retrieval Design

Phase 57 keeps the default Agent shell stable:

```text
tool_calling_agent -> hybrid_search_knowledge
```

The change is inside the retrieval workflow kernel. The default tool-calling model
does not receive a new `search_graph_knowledge` tool. Instead,
`HybridSearchService` can collect candidates from multiple retrieval channels and
send one deduplicated pool into the existing reranker and dynamic-K path.

## Candidate Channels

```text
keyword       -> ordinary lexical evidence, always eligible
vector        -> semantic evidence, always eligible
graph         -> gated cross-document / standards / relationship evidence
table_text    -> gated table chunks for numeric or parameter-like questions
figure_caption-> gated image-description chunks as text evidence only
```

`search_tables` and `search_figures` remain explicit tools for raw table and image
asset requests. The caption channel is not an image asset fetcher.

## Gating

Graph gating is intentionally conservative. It should fire for standard-reference,
cross-document relationship, parameter-range, applies-to, or "defined by standard"
questions. It should not fire for every ordinary concept explanation.

Table-text gating should fire for table, row/column, parameter, mix-ratio, numeric
range, and test-data language.

Figure-caption gating should fire for figure, chart, curve, diagram, photo,
microscopy, crack, failure morphology, or other visual-language prompts, but only
as text evidence inside `hybrid_search_knowledge`.

## Fusion

Raw scores from keyword, vector, graph, table, and figure-caption channels are not
comparable. The multi-channel path uses reciprocal-rank style fusion:

```text
per-channel ranked lists
-> chunk_id dedupe
-> sum channel_weight / (rank_constant + rank)
-> channel labels retained
-> existing reranker
```

This avoids hard-adding unrelated score scales.

## Caching And Diagnostics

Retrieval cache identity must include:

```text
enabled channels
channel gate decisions
fusion method/version
graph path/fingerprint when graph is enabled
table/figure channel config
existing provider/model/dimension/corpus identity
```

Diagnostics expose safe metadata only:

```text
enabled channel labels
eligible channel labels
per-channel candidate counts
selected channel labels
graph fallback/error/counts
chunk ids and short source previews
```

No full chunks, full answers, provider raw payloads, credentials, hidden reasoning,
restricted full text, or private logs may be stored in Git/CSV/docs/tests/Obsidian.

## Rollout

The implementation is guarded by conservative configuration switches. Phase 57
can evaluate the multi-channel path without forcing a production default before
the 30-case real default-chain run and user human verification.
