# Phase 58H Runtime Checkpoint And Resume Plan

## Goal

Add durable checkpoint/resume semantics to the default `tool_calling_agent` runtime so a stopped or interrupted thinking run can be resumed from the last completed runtime node instead of always starting from scratch.

This is not a replacement for LangGraph. It is a narrow runtime persistence layer for the current default Agent path.

## Problem

Current stop behavior is request cancellation:

```text
frontend stop -> AbortController aborts stream
backend run may stop mid-request
next user question -> new Agent run
```

The default `tool_calling_agent` does not persist the current runtime node, evidence state, completed tool results, loop counters, or cancellation state as a resumable run. It may reuse history and caches, but it cannot continue from "the last completed node".

## Target Runtime Model

Introduce an `AgentRuntimeRun` concept:

```text
run_id
conversation_id
status: running | stopped | completed | failed | expired
current_node
last_completed_node
resume_token
created_at / updated_at / expires_at
runtime_context
workflow_steps
evidence_state
tool_results_index
loop_state
latency_trace_summary
failure_reason
```

The runtime persists after every durable node boundary:

```text
context_assembled
tool_selection_completed
tool_arguments_grounded
tool_execution_completed
evidence_state_updated
final_answer_started
final_answer_completed
```

Only completed node outputs are resumable. A partially streaming final answer is not resumed token-by-token; it is regenerated from the saved evidence unless the final answer had already completed.

## Storage Contract

Use the existing application database for durable run metadata so history and run state share the same operational backup boundary.

Recommended minimal table:

```text
agent_runtime_runs
- id
- conversation_id
- run_id
- status
- current_node
- last_completed_node
- resume_token_hash
- request_question
- canonical_task
- state_json
- created_at
- updated_at
- expires_at
```

`state_json` may contain:

- runtime diagnostics fields;
- bounded workflow step summaries;
- source and citation ids;
- selected chunk ids;
- tool result chunk ids and safe scores;
- evidence counts;
- reranker/cache labels;
- stop/failure reason.

It must not contain:

- API keys, bearer tokens, JWT secrets, Redis passwords, database passwords;
- provider raw responses;
- hidden reasoning or `reasoning_content`;
- full answers unless the assistant message was already persisted through the normal conversation path;
- full chunk text or restricted full text;
- raw uploaded image bytes or private logs.

## Resume Semantics

When a user stops an active run:

```text
status = stopped
last_completed_node remains the last node that fully persisted
stop_reason = user_cancelled
```

When the next request arrives in the same conversation:

1. Runtime checks for a resumable stopped run.
2. It compares the new question to the previous request:
   - exact retry: resume automatically;
   - explicit continuation such as "继续" or "接着上次": resume;
   - new standalone topic: start fresh;
   - ambiguous near match: prefer fresh run unless the UI sends an explicit resume flag.
3. Resume loads runtime context, evidence state, workflow steps, and completed tool results.
4. Runtime skips completed expensive nodes and continues from the next node.

## API And UI Contract

Recommended API additions:

```text
POST /agent/query/stream
  resume_run_id?: string
  resume_policy?: "auto" | "force" | "never"

metadata event:
  runtime_run_id
  runtime_resume_available
  runtime_resume_status
  runtime_last_completed_node
```

Frontend behavior:

- Stop button marks the current panel as stopped.
- If a stopped run is resumable, show a compact "继续上次" affordance.
- New normal question uses `resume_policy=auto`.
- Explicit continue action uses `resume_policy=force`.

## Acceptance Criteria

- Stopping after a completed retrieval/tool node persists a resumable run.
- Re-asking "继续" in the same conversation skips already completed retrieval/tool nodes.
- A new standalone topic does not resume stale evidence.
- Resuming never bypasses guardrails, reranker hard-failure policy, or citation validation.
- Runtime diagnostics show `runtime_resumed=true`, `runtime_resume_from_node`, and skipped durable nodes.
- Tests cover exact retry, explicit continue, new-topic non-resume, expired checkpoint, and corrupted checkpoint fail-safe fresh run.

## Evaluation Hooks

The Phase 58H evaluation set must include stop/resume scenarios with synthetic runtime checkpoints and at least one integration-style stream abort smoke.

Metrics:

- `resume_available_rate`;
- `resume_success_rate`;
- `completed_node_reuse_count`;
- `tool_execution_skipped_after_resume`;
- `time_saved_ms_estimate`;
- `stale_resume_blocked_count`;
- `checkpoint_safety_failure_count`.
