# Phase 56 Task Plan: layered semantic cache and Agent latency reduction

## Goal

Phase 56 turns the existing Redis foundation into a real layered cache for the current production Agent chain. The objective is to reduce repeated or near-repeated question latency without downgrading providers, without disabling tool calling, and without relying on answer-level semantic cache as the main speed path.

The user-facing symptom that motivates this phase is clear: two same production questions still showed long thinking times (`31s` then `53s`). That means the old cache did not shorten the real Agent path. Phase 56 must make cache hits observable and make warm runs skip expensive retrieval/rerank/tool-result work while preserving final-answer quality and citation safety.

Target branch suggestion:

```text
codex/phase-56-layered-agent-cache
```

## Current Baseline

- Phase 55 has been submitted, pushed, and merged into `main`.
- Current production app is reachable through `http://36.103.199.132:8044` and `http://rag.rfc-agent.com:8044`; both point to the CPU server app.
- The app runs in Docker on the CPU server. PostgreSQL/pgvector is the primary database/vector substrate; FAISS is the local file fallback.
- HNSW is preferred when PostgreSQL + pgvector + 2048-dimensional GLM embeddings are valid. If HNSW is unavailable, the vector service can fail open to FAISS/numpy fallback.
- Private BGE reranker is primary when the GPU server and tunnel are available. Phase 55 supplement added GLM reranker fallback through existing provider config when BGE is unavailable.
- Redis Stack already exists in dev/prod compose. Current Redis roles: query embedding cache, LangGraph checkpoint, optional answer-level Semantic Cache, and optional rate limiting.
- Production `SEMANTIC_CACHE_ENABLED` is intentionally disabled. The existing answer-level Semantic Cache is not sufficient for repeated Agent questions because the default path is tool-calling and may include conversation/history/source/image eligibility gates.
- Default Agent path remains `tool_calling_agent`: model with tools -> safe tool execution -> retrieval/rerank -> final cited answer.

## Non-Goals

- Do not downgrade `deepseek-v4-pro`, `deepseek-v4-flash`, `GLM-Embedding-3`, BGE, or GLM reranker configuration.
- Do not make final-answer semantic cache the primary solution or enable it broadly in production by default.
- Do not store API keys, bearer tokens, JWT secrets, Redis passwords, provider raw responses, hidden reasoning, full answers, full chunks, restricted full text, or long-term user profiles in Git/CSV/docs/tests/Obsidian.
- Do not add external data sources, crawlers, corpus imports, or new write-capable Agent tools.
- Do not treat domain/HTTPS work as part of this cache phase.
- Do not execute `git add`, commit, tag, push, or PR before user human verification.

## Phase 56A: startup audit and cold/warm baseline

Status: completed

Tasks:
- Re-read `AGENT.MD`, `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `task_plan.md`, `findings.md`, and `progress.md`.
- Run `git status -sb` and `git log --oneline -5`; confirm Phase 55 is merged and start from `main`.
- Audit current cache code: Redis client, query embedding cache, answer Semantic Cache, latency trace, tool-calling service, Agent toolbox, hybrid search, reranking, pgvector/FAISS fallback, and API cache eligibility.
- Reproduce a sanitized cold/warm latency baseline for one or more repeated standalone questions. Record only safe timings, cache flags, provider/model labels, source counts, and citation counts.

Acceptance:
- Baseline explains why the current cache does not reduce the observed repeated-question thinking time.
- Baseline output contains no answer text, provider payload, token, full chunk, or restricted text.

## Phase 56B: cache identity, versioning, and invalidation contract

Status: completed

Tasks:
- Define versioned cache keys for retrieval, rerank, and tool result layers.
- Include corpus/version identity, embedding provider/model/dimension, normalized query, source/filter args, retrieval mode, top_k/fetch_k, HNSW/FAISS relevant identity, GraphRAG graph fingerprint where applicable, reranker provider/model/recall_k, and candidate chunk id order.
- Define invalidation rules for data import, PostgreSQL restore, FAISS refresh, GraphRAG rebuild, embedding provider change, reranker change, and deployment version change.
- Decide what may be stored in Redis: prefer ids, scores, labels, and safe summaries; hydrate source text from DB at request time.

Acceptance:
- A design note or doc section states exact key components, TTL defaults, fail-open behavior, and privacy boundaries.
- Cache keys cannot collide across different corpus/model/reranker configurations.

## Phase 56C: retrieval candidate cache

Status: completed

Tasks:
- Add optional Redis-backed retrieval candidate cache for normalized query + filters + corpus/vector identity.
- Cache merged candidate chunk ids, safe scores, chunk_type/source labels, and backend summary; do not cache full chunk bodies as the durable contract.
- Hydrate cached ids from PostgreSQL before returning Agent sources so citations remain current.
- Integrate with hybrid search and vector backend trace fields.
- Fail open to normal keyword + pgvector/FAISS search when Redis is unavailable, stale, invalid, or empty.

Acceptance:
- Cold run is miss; warm repeated run shows `retrieval_cache_hit=true` and reduced retrieval latency.
- HNSW unavailable still falls back to FAISS; retrieval cache must not mask a broken fallback path.

## Phase 56D: rerank order cache

Status: completed

Tasks:
- Add optional Redis-backed rerank cache keyed by query identity, candidate chunk id list/hash, top_k, primary/fallback reranker provider/model, and recall_k.
- Cache reranked candidate ids/order/scores only, not provider raw responses or full candidate text.
- Support both BGE primary and GLM fallback identities.
- Record cache hit/miss, backend, fallback state, and latency in `latency_trace`.

Acceptance:
- With identical candidates, warm repeated run skips the remote reranker call and preserves ranked chunk ids.
- If BGE is off, GLM fallback identity is used correctly and does not reuse BGE cache entries.

## Phase 56E: tool result cache for the tool-calling Agent

Status: completed

Tasks:
- Add a safe tool-result cache around read-only Agent tools such as `hybrid_search_knowledge`, `search_knowledge`, `search_tables`, and `search_figures`.
- Key by tool name, normalized args, corpus/graph/cache version, retrieval/rerank identities, top_k, source filters, and image/table mode where relevant.
- Store structured ids/results sufficient to reconstruct `AgentToolResult` through DB hydration. Avoid storing final answer text as the main path.
- Wire cache into `ToolCallingAgentService` or `AgentToolbox` so repeated questions can skip expensive tool execution while still letting the final LLM synthesize the answer.

Acceptance:
- Second identical standalone tool-calling query records tool cache hit and lower tool execution latency.
- Tool cache is bypassed for user-upload image analysis, unsafe args, history-dependent queries, or unsupported mutable contexts.

## Phase 56F: answer-level cache guardrails

Status: completed

Tasks:
- Keep broad answer-level Semantic Cache disabled by default in production until dedicated acceptance.
- If reused, tighten eligibility to standalone no-history/no-image/no-source-filter cases and include corpus/version, final-answer strategy, provider/model, retrieval/rerank identities, and source id set in `cache_context`.
- Consider exact/FAQ answer cache only as a guarded optimization after layered retrieval/rerank/tool cache proves useful.

Acceptance:
- Phase 56 speedup does not depend on answer-level semantic cache.
- Existing `SEMANTIC_CACHE_ENABLED=false` production default is preserved unless the user explicitly approves a narrower production rollout.

## Phase 56G: observability, frontend metadata, and operations

Status: completed

Tasks:
- Extend `latency_trace` with safe cache fields: retrieval/rerank/tool cache hit/miss, backend, TTL/stale reason, estimated saved milliseconds, and cache layer summary.
- Ensure API/SSE metadata can expose safe cache summaries without leaking answer text, raw chunks, provider payloads, or secrets.
- Add env examples for cache switches and TTLs: retrieval cache, rerank cache, tool-result cache, and optional answer cache.
- Update deployment/runbook docs with Redis Stack requirements, flush/invalidation commands using placeholders, and fail-open behavior.

Acceptance:
- The user can tell from a response trace whether the repeated question used cache and which layer saved time.
- Redis off or unavailable returns normal answers rather than 500s.

## Phase 56H: evaluation and regression

Status: completed

Tasks:
- Add focused tests for cache key stability, privacy, Redis fail-open, HNSW-to-FAISS fallback compatibility, reranker identity separation, and tool-cache eligibility.
- Add or extend a Phase 56 evaluation script that compares cold vs warm runs with sanitized CSV output.
- Run focused tests, `python scripts/score_stage30_quality.py`, and full `python -m pytest -q` if code paths change materially.
- Run `git diff --check` and a sensitive-field scan for new docs/scripts/CSV.

Acceptance:
- Warm repeated queries show measurable reduction in retrieval/rerank/tool latency and visible cache-hit trace fields.
- Stage 30 remains `A / pass`; existing Agent, chat, stream, health, quality-report, pgvector, FAISS, BGE/GLM fallback tests remain intact.

## Phase 56I: documentation, Obsidian, and handoff

Status: completed

Tasks:
- Update `README.md`, `AGENT.MD` handoff if appropriate, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, and a Phase 56 review/design doc.
- Update local Obsidian phase notes and knowledge points after development and tests are complete.
- Stop before user human verification; do not stage, commit, tag, push, or create PR.

Acceptance:
- Final report explains branch, changed files, tests, latency evidence, cache-hit evidence, security scan, remaining risks, and human verification checklist.

## Phase 56J: evidence-chain diagnostics, dynamic K, and post-cache evaluation

Status: completed

Tasks:
- Keep the completed skipped-tool-name UI behavior, and add the missing execution evidence chain to the Agent thinking panel.
- Expose safe diagnostics for actual retrieval query, retrieval candidate chunk ids, selected chunk ids, selected source titles/source types, rerank cache hit/miss, rerank fallback state, tool-result cache hit/miss, and answer-level `semantic_cache_hit`.
- Do not expose full chunks, full answers, provider raw payloads, hidden reasoning, secrets, tokens, restricted full text, or user-private logs in UI/debug output.
- Add dynamic rerank K controls without hard-coded domain terms: keep candidate pool at `RERANKING_RECALL_K=75`; when enabled, retain a baseline `RERANKING_DYNAMIC_MIN_RESULTS=4`, then include additional reranked results only while they pass `RERANKING_DYNAMIC_RELATIVE_SCORE_THRESHOLD=0.65`, capped by `RERANKING_DYNAMIC_MAX_RESULTS=12`.
- Extend the Phase 56 evaluation script and CSV with evidence-chain diagnostics and dynamic-K rows.
- Re-run focused tests and the Phase 56 eval after these changes; update docs/progress/handoff with the new evidence.

Acceptance:
- A user can inspect a single response and see which tool ran, which tool was skipped, the actual retrieval query, candidate ids, selected ids, selected source title/source_type preview, rerank fallback/cache state, and semantic-cache state.
- Dynamic K does not hard-code standards or any domain entity. It uses reranker scores and configuration only.
- The sanitized Phase 56 CSV shows cache hit behavior, diagnostic-field presence, and dynamic-K selected count without writing full content.

## Completion Standard

- Repeated standalone Agent questions no longer run the full expensive retrieval/rerank/tool path when cache keys are valid.
- Cache hits are proven by trace fields and latency measurements, not inferred from UI time alone.
- Redis is used where appropriate and remains optional/fail-open.
- Retrieval cache, rerank cache, and tool-result cache have separate keys, TTLs, invalidation rules, tests, and documentation.
- HNSW primary / FAISS fallback and BGE primary / GLM fallback semantics remain correct.
- No secret, provider raw response, full answer, full chunk, restricted full text, or long-term user profile is written to Git/CSV/docs/tests/Obsidian.
