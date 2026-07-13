# Phase 64 DeepSeek Cache Telemetry Design

**Status:** Approved by the ongoing Phase 64 development directive (2026-07-13)

## Objective

Expose safe DeepSeek context-cache usage for streamed final generation so Phase
64 can distinguish cache misses from provider scheduling or inference delay.
This is observability only: it does not change the final prompt, model lane,
cache policy, retrieval path, or release gate.

## Design

For OpenAI-compatible requests to a DeepSeek endpoint, streaming requests add
the documented `stream_options: {"include_usage": true}` option. The extra
usage-only SSE chunk contains no generated text. The stream parser extracts
only these non-content integers into the current latency trace:

- `provider_prompt_tokens`;
- `provider_prompt_cache_hit_tokens`; and
- `provider_prompt_cache_miss_tokens`.

All other providers retain their existing payload. The parser ignores absent,
malformed, negative, or non-integer usage values. No raw SSE frame, answer,
reasoning content, source, title, provider payload, user identifier, or
credential is retained.

## Interpretation

DeepSeek caching is automatic and best-effort. These fields are diagnostics:
they must not be used to pass the Phase 64 cold-chain gate. A later design may
consider stable-prefix construction only if repeated real evidence requests
show cache miss-dominated TTFT and a quality-safe A/B supports the change.

## Non-goals

- no `user_id` routing or user identity propagation;
- no Beta chat-prefix completion;
- no semantic-answer cache;
- no change to Dynamic-K, the 75-candidate pool, official `zhipu / rerank`, or
  user-selected Flash/Pro behavior.
