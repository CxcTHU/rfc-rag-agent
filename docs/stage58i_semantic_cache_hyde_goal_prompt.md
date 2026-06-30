# Phase 58I Goal Prompt: Semantic Evidence Cache And HyDE Runtime Flow

You are implementing Phase 58I in `codex/phase-58-mature-agent-runtime`.

## Objective

Upgrade the default `tool_calling_agent` runtime flow:

```text
Context Assembly
-> Query Rewrite / Contextualization
-> Semantic Evidence Cache Lookup
-> HyDE on miss
-> Retrieval
-> Rerank
-> Evidence State
-> Final Answer
```

## Requirements

1. Do not restore answer-level Semantic Cache.
2. Semantic cache hit means cached evidence/tool result hit, not old answer reuse.
3. Use runtime semantic identity (`entity_key`, `intent_key`, constraints) as the
   stable cache identity. Do not key primarily on free-form `canonical_query`.
4. On semantic evidence hit, hydrate current DB sources and generate a fresh
   final answer.
5. HyDE runs only after semantic evidence cache miss.
6. HyDE is used only for vector retrieval recall and is never cited as evidence.
7. BGE primary and GLM fallback rerank policy remains strict: if both fail, the
   Agent turn fails visibly.
8. Trace must expose:

```text
contextualized
canonical_task
semantic_cache_hit
hyde_generated
tool_cache_hit
retrieval_cache_hit
rerank_cache_hit
rerank_provider
retrieval_selected_chunk_ids
```

## Safety Boundary

Never write `.env`, credentials, API keys, bearer tokens, provider raw responses,
hidden reasoning, full answers, full chunks, HyDE passage text, restricted full
text, private logs, or raw uploaded image bytes to Git/docs/tests/CSV/Obsidian.

## Validation

Run focused tests for:

- semantic evidence hit;
- HyDE miss path;
- structured cache identity;
- existing Phase 56/58H cache behavior;
- tool-calling runtime behavior.

Stop before git staging, commit, tag, push, or PR until user human verification.
