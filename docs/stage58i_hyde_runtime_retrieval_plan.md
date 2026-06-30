# Phase 58I HyDE Runtime Retrieval Plan

## Goal

Add HyDE only after semantic evidence cache miss and only as a vector-retrieval
recall enhancer.

## Boundary

HyDE generates a hypothetical evidence passage for embedding/search. It is not
evidence, is never cited, and is never shown as a source.

```text
canonical_task
-> small model hypothetical passage
-> vector query augmentation
-> real corpus retrieval
-> real source citations only
```

## Execution Policy

HyDE runs only when all are true:

- semantic evidence cache did not hit;
- runtime has a standalone `canonical_task` or semantic identity;
- a runtime identity/planner small model is configured;
- the request is a text evidence retrieval path.

HyDE does not run when:

- semantic/tool cache already hit;
- request is already satisfied by checkpoint resume;
- no model is configured;
- provider fails or returns empty output.

Failures fail open to normal retrieval.

## Retrieval Integration

Keyword/BM25 query remains the canonical/tool query.

Vector query may use:

```text
canonical_task + "\n\nHypothetical evidence:\n" + hyde_passage
```

Retrieval cache identity must include whether HyDE was used and the bounded
HyDE vector-query hash. This prevents mixing non-HyDE and HyDE candidate pools.

## Diagnostics

Trace fields:

```text
hyde_generated=true/false
hyde_used_for_vector=true/false
hyde_model=provider/model
hyde_reason=generated/cache_hit_skipped/provider_unavailable/empty/provider_error
```

Do not store the full HyDE passage in logs, CSVs, docs, or frontend diagnostics.
