# Phase 35 Progress Log

## Current State

Status: Phase 35 implementation and verification are complete, awaiting human verification.

Branch: `codex/phase-35-retrieval-quality-calibration`

Submission boundary: no `git add`, no commit, no `phase-35-complete` tag, no push, no PR.

## Baseline

```text
phase-34-complete -> 8028acb
main -> d9053a6
phase-34-complete is merged into main
```

## Remediation Log

### Leakage Removal

Removed the unsafe `SYNONYM_RULES` entry that copied `Alpe Gera Dam`, `road paving`, and `compaction` from expected answer points. Kept only the legitimate generic RCC abbreviation/synonym rule.

### Retrieval Optimization

Implemented mechanism-level retrieval improvements:

- `source_type_rank` prefers full sources over metadata records.
- Deterministic reranking removes common English stopwords before overlap scoring.
- Added `HybridRrfTailSearchService` to preserve the hybrid top 3 and fill tail recall with BM25+vector RRF.
- Default non-decomposed Brain hybrid retrieval now uses the tail-fusion service.

### Score Density

Added `scripts/analyze_stage35_score_density.py` and `tests/test_stage35_score_density.py`. Final density output shows the clean score is already above target:

```text
current=91.52
target=88.00
gap=0.00
recorded_deductions=0.00
```

### Prompt A/B

Added prompt profiles and Judge CLI profile selection. The default is back to `legacy` because stricter citation wording caused coverage regression and coverage-first did not stabilize both Judge dimensions.

### Final Evaluations

```text
python scripts/evaluate_stage29_real_quality.py --provider glm --retrieval-mode hybrid_rrf_tail
p@1=0.933 p@3=0.933 p@5=1.000 coverage=0.731 refusal_accuracy=1.000

python scripts/score_stage30_quality.py
overall=91.52 grade=A release_decision=pass

python scripts/analyze_stage35_deduction_causes.py
rows=0

python scripts/judge_stage34_generation_quality.py --execute --limit 10 --prompt-profile legacy
answer_coverage=0.605 citation_support=0.455 high=0 gate=review_required
```

## Verification

```text
python -m pytest tests/test_stage34_llm_judge.py tests/test_prompt_builder.py -q
16 passed

python -m pytest tests/test_hybrid_rrf_tail.py tests/test_evaluate_stage29_real_quality.py tests/test_rrf_fusion.py tests/test_hybrid_search.py tests/test_reranking.py tests/test_keyword_search.py tests/test_stage35_score_density.py -q
39 passed

python -m pytest tests/test_stage35_deduction_causes.py -q
3 passed

python -m pytest -q
694 passed
```

Browser smoke on `/quality-report`:

```text
desktop: Overall=91.52, Grade=A, pass, overflow=false, console errors=0
390x844: Overall=91.52, Grade=A, pass, overflow=false, console errors=0
```

API smoke:

```text
GET /health -> 200
GET /quality-report -> 200
GET /quality-report/data.json -> 200
GET /quality-report/export.csv -> 200
POST /search/hybrid -> 200
```

## Remaining Review Risk

The Stage 30 pass is clean and retrieval-driven. The real Judge gate is not passed: generated answer coverage and citation support remain unstable and should be reviewed manually before submission.

## Phase 35 Continuation Cleanup

The citation validator experiment remains in the codebase as an offline/Judge guard, but it has been decoupled from the production Brain path after drop mode measurably reduced answer coverage and citation support.

The default `/agent/query` `react_agent` path now handles first-iteration non-JSON planner output more conservatively for in-scope RFC/concrete/hydraulic-engineering questions: it searches first, then answers from retrieved evidence if available. Out-of-scope questions with unparseable planner output still refuse safely.

Verification:

```text
python -m pytest tests/test_react_llm_planner.py tests/test_react_agent_service.py tests/test_agent_api.py -q
33 passed

python -m pytest -q
694 passed

POST /agent/query mode=react_agent
refused=false
tool_calls=hybrid_search_knowledge,answer_with_citations
validator_marker=false
```
