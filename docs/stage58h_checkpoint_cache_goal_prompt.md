# Phase 58H Goal Prompt: Runtime Checkpoint/Resume And Evidence Cache Hit Reuse

Read `AGENT.MD`, `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `task_plan.md`, `findings.md`, and `progress.md` before coding. Run `git status -sb` and `git log --oneline -5`.

Set the working goal:

```text
Complete Phase 58H: add durable runtime checkpoint/resume and similar-question evidence cache canonicalization for the default tool_calling_agent, with safe diagnostics, evaluation sets, focused tests, and documentation updates. Stop before git staging or commit until user human verification.
```

## Background

Phase 58 created the first explicit Agent Runtime around the default `tool_calling_agent`: context assembly, follow-up grounding, evidence state, loop diagnostics, and final-answer control.

Two follow-up gaps remain:

1. Clicking stop during thinking cancels the stream but does not persist a resumable runtime node.
2. Similar evidence questions such as:

```text
堆石混凝土的优势
堆石混凝土有哪些优点
```

do not reliably share evidence-chain cache identity, even though Phase 56 layered cache already exists.

## Scope

Implement the next runtime layer:

```text
runtime checkpoint/resume
evidence query identity canonicalization
evaluation sets for resume and cache hit behavior
```

Do not reintroduce broad answer-level Semantic Cache as the solution. Final answers must remain freshly generated from current evidence and citations.

## Required Planning Files

Use these as the detailed design references:

```text
docs/stage58h_runtime_checkpoint_resume_plan.md
docs/stage58h_evidence_cache_canonicalization_plan.md
docs/stage58h_checkpoint_cache_evaluation_plan.md
```

## Implementation Phases

### Phase 58H-1: Runtime Run Repository

- Add a durable `AgentRuntimeRun` repository/model for run state.
- Persist after completed runtime node boundaries.
- Store only safe bounded metadata and ids.
- Add tests for serialization, expiration, corruption handling, and safety constraints.

### Phase 58H-2: Stop And Resume Policy

- Add runtime resume policy:
  - exact retry resumes;
  - explicit "继续/接着上次" resumes;
  - new standalone topic starts fresh;
  - expired/corrupt checkpoints fail safe to fresh run.
- Add API/stream metadata fields for `runtime_run_id`, `runtime_resume_available`, `runtime_resumed`, and `runtime_resume_from_node`.
- Add frontend affordance only if needed by the implementation; keep UI compact.

### Phase 58H-3: Evidence Query Identity

- Add `EvidenceQueryIdentity` with deterministic entity and intent canonicalization.
- Reuse existing entity/anchor knowledge where safe.
- Start with a narrow high-value lexicon:
  - advantages;
  - causes;
  - measures;
  - classification;
  - definition;
  - comparison;
  - visual evidence;
  - table evidence.
- Make uncertain cases fall back to raw normalized query.

### Phase 58H-4: Cache Integration

- Route query embedding, retrieval candidate, rerank order, and tool-result cache identities through canonical evidence identity when safe.
- Do not change the displayed user question or final answer prompt question.
- Add latency diagnostics for canonicalization and cache reuse/block reasons.

### Phase 58H-5: Evaluation Sets And Scripts

- Create:

```text
data/evaluation/phase58h_runtime_resume_cases.yaml
data/evaluation/phase58h_cache_canonicalization_cases.yaml
scripts/evaluate_phase58h_runtime_resume.py
scripts/evaluate_phase58h_cache_hits.py
```

- Dry-run mode must not require external providers.
- Real-chain mode must produce sanitized CSV only.

### Phase 58H-6: Tests And Documentation

- Add focused unit/integration tests for:
  - resume after completed node;
  - explicit continue;
  - stale/new-topic non-resume;
  - corrupted checkpoint fail-safe;
  - similar query same identity;
  - different intent/entity no reuse;
  - cache-hit diagnostics.
- Update README, docs/progress.md, docs/architecture.md, docs/data_sources.md, root planning files, and phase review.

## Acceptance Criteria

- Stop/resume can skip at least one completed expensive runtime node.
- Similar questions can share evidence-chain cache identity:

```text
堆石混凝土的优势
堆石混凝土有哪些优点
```

- Different intent/entity questions do not incorrectly reuse evidence identity.
- Final answers are not answer-cache hits; they are regenerated from citations.
- Redis unavailable remains fail-open.
- Reranker hard-failure policy remains visible and is not hidden by resume/cache reuse.
- Evaluation scripts write only safe sanitized metadata.
- Focused tests pass.
- No `git add`, commit, tag, push, or PR before user verification.

## Safety Boundary

Do not write secrets, real `.env` values, API keys, bearer tokens, JWT secrets, Redis passwords, database passwords, provider raw responses, hidden reasoning, full answers, full chunks, restricted full text, raw uploaded image bytes, or private service logs to Git/docs/tests/CSV/Obsidian.
