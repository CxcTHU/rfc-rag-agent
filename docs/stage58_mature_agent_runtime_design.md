# Phase 58 Mature Agent Runtime Design

## Decision

Phase 58 treats the default `tool_calling_agent` as an Agent Runtime, not as a prompt plus a few tool-loop rules.

The default tool surface stays stable:

```text
hybrid_search_knowledge
search_knowledge
search_figures
search_tables
```

The runtime layer coordinates the control plane around those tools:

```text
context assembly
-> task contextualization
-> LLM tool selection
-> tool argument grounding
-> tool execution control
-> evidence state management
-> loop control
-> guardrails
-> final answer control
-> diagnostics
```

## LLM Boundary

LLM can propose semantic intent and candidate actions:

- follow-up type;
- inherited topic;
- standalone task;
- high-level tool selection;
- tool-specific query rewrite;
- final answer synthesis.

Runtime keeps authority over:

- allowed tools;
- guardrails;
- argument validation;
- duplicate suppression;
- max iterations;
- evidence state and stop reason;
- diagnostics schema;
- final refusal decision.

The first implementation uses deterministic contextualization so local tests do not depend on real providers. The module boundary allows an LLM proposal provider to be added later.

## Runtime State

`app/services/agent/runtime.py` introduces:

- `RuntimeContext`: current query, history, recent topic, inherited topic, follow-up type, standalone task.
- `AgentRuntimeState`: context, tool argument rewrites, evidence state, stop reason, final decision.
- `EvidenceState`: bounded safe records of tool name, grounded query, result count, evidence type, and success flag.
- `AgentRuntime`: assembler and tool-call grounding facade.

## Tool Argument Grounding

Grounding runs after LLM tool selection and before actual tool execution.

Example:

```text
history: 大坝的裂缝成因有哪些？请给我详细列出来
current: 我需要图片支撑
LLM tool call: search_figures(query="我需要图片支撑")
runtime grounded query: 大坝的裂缝成因有哪些？请给我详细列出来 图片 图示 曲线 照片 视觉证据
```

The repair is tool-aware:

- `search_figures` gets visual evidence terms.
- `search_tables` gets table/data/parameter terms.
- text search tools get a standalone detail task.

The runtime does not rewrite already-specific standalone queries.

## Diagnostics

The runtime writes safe metadata into `latency_trace`:

```text
runtime_context_assembled
runtime_followup_type
runtime_recent_topic
runtime_inherited_topic
runtime_standalone_task
runtime_contextualized
runtime_contextualization_source
runtime_tool_arg_rewrite_count
runtime_tool_arg_rewrites
runtime_evidence_attempts
runtime_evidence_counts
runtime_stop_reason
runtime_final_decision
```

These fields are bounded summaries. They must not include full chunks, full answers, raw provider responses, hidden reasoning, credentials, restricted full text, or private logs.

## Compatibility

Stage 37 controls remain in place:

- one executed search tool per iteration;
- safe skipped tool messages;
- near-duplicate query blocking;
- evidence convergence;
- citation repair.

Phase 58 inserts explicit runtime state around these controls instead of replacing them.
