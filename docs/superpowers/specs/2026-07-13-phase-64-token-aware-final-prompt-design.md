# Phase 64 Token-Aware Final Prompt Design

**Status:** Approved by the ongoing Phase 64 development directive (2026-07-13)

## Objective

Reduce Phase 64 B-path final-generation time to first token without changing
the 75-candidate retrieval pool, disabling official `zhipu / rerank`, or
silently changing the user-selected Flash/Pro model. The current B prompt uses
character limits; real Chinese evidence can have much higher input-token
density than an equally sized English synthetic probe.

## Evidence

- The official reranker is not the active long tail: a fixed small stability
  probe completed 5/5 official calls with a 378.450 ms observed P95.
- Flash direct safe probes reached first content in 571 ms P50 for an empty
  prompt and 857.736 ms P50 for a 6,195-character synthetic RAG prompt.
- The same real B request, recorded as `deepseek-v4-flash`, recorded final-model
  TTFT values of 9,489.630, 11,237.923, and 12,489.349 ms across three serial
  runs. Its planner count was zero and retrieval plus rerank was materially
  shorter.

This supports a real-evidence final-prompt effect; it does not establish that
any provider is generally unstable.

## Chosen Design

### Safe prompt-shape tracing

`evidence_answer_messages()` will retain its existing return type and fill an
optional numeric collector. The collector records only final prompt character
count, source count, history character count, CJK code-point count, and
deterministic `estimated_input_tokens`. No title, source text, history, answer,
provider payload, or hidden reasoning enters the trace.

The estimate is explicitly not provider token usage: each CJK code point counts
as one unit and each run of non-CJK text contributes one unit per four
characters, rounded up. It is deterministic, dependency-free, and sufficient
for reproducible comparative sizing.

### B-only token budget

Phase 63 A remains unchanged. B may receive a configurable estimated-input
ceiling through the existing final-prompt budget boundary. It preserves every
source selected by Dynamic-K (currently bounded by its configured maximum of
12), their selected-source order, and the existing per-source snippet maximum.
The allocator reserves bounded history, guarantees a nonempty share for every
selected source, then distributes remaining units in stable source order. An
unrepresentable ceiling is ignored safely rather than dropped sources being
sent to the model.

The ceiling is chosen only after a real B trace has supplied its aggregate
prompt shape. A paired three-run probe tested `1664` against disabled budget
with the same 12 Dynamic-K sources: it reduced estimated input units from 3631
to 1657 but worsened median TTFT from 8093.490 to 11028.534 ms. The default is
therefore disabled (`0`). It must subsequently pass the frozen functional,
citation, refusal, and quality gates; latency alone cannot enable a default.

## Non-goals and safeguards

- No cache, candidate-pool, reranker, retrieval-channel, Dynamic-K selection,
  or frontend model selection behavior changes.
- No provider-specific tokenizer dependency is added.
- Blindly reducing source count, changing the final provider, or changing the
  75-candidate pool is outside this slice.
- All current cold frozen A/B and quality gates remain acceptance criteria.
