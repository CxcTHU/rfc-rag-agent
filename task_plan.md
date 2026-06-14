# Phase 35 Task Plan: Retrieval Quality Calibration and Stage 30 Breakthrough

## Goal

Continue from the merged Phase 34 baseline and finish Phase 35 on branch `codex/phase-35-retrieval-quality-calibration`, stopping before human verification. The work must optimize retrieval quality, not scoring rules.

Hard boundaries:

- Do not change Stage 30 scoring weights, grade boundaries, release decision rules, or provider topology.
- Do not add query-specific expected-answer terms to `SYNONYM_RULES`.
- Do not replace default chat, embedding, or rerank providers.
- Do not add external data sources or write-capable Agent tools.
- Do not run `git add`, commit, tag, push, or create a PR before user approval.

## Phase Order

### Phase 0: Startup Calibration

Status: completed.

Confirmed `phase-34-complete -> 8028acb`, merged into `main -> d9053a6`, and continued on `codex/phase-35-retrieval-quality-calibration` without moving existing tags.

### Phase 1: Design Contract

Status: completed.

Added `docs/stage35_retrieval_quality_calibration.md` and `tests/test_stage35_design.py` to fix the Phase 35 scope: classify Stage 30 deductions, repair retrieval and prompt issues minimally, rerun real Judge and Stage 30, and document any remaining root cause honestly.

### Phase 2: Deduction Attribution

Status: completed.

Added `scripts/analyze_stage35_deduction_causes.py`, `tests/test_stage35_deduction_causes.py`, and `data/evaluation/stage35_deduction_root_causes.csv`. After the clean final rerun, Stage 30 deduction rows are empty, so the root-cause CSV contains only the header.

### Phase 3: Clean Retrieval Repair

Status: completed.

Removed the leaked RCC dam synonym rule that copied literal answer points from `stage29_new_corpus_queries.csv`. Replaced the earlier query-specific patching approach with mechanism-level retrieval changes:

- Rank full source pages before metadata-only rows.
- Filter English stopwords in deterministic reranking overlap.
- Add `HybridRrfTailSearchService`, preserving the existing hybrid top 3 and filling tail slots with BM25+vector RRF candidates.
- Add `--retrieval-mode hybrid|bm25_rrf|hybrid_rrf_tail` to `scripts/evaluate_stage29_real_quality.py`.

### Phase 4: Prompt and Citation A/B

Status: completed.

Added prompt profiles for `legacy`, `strict_citation`, and `coverage_first`. A/B results showed strict citation improved citation support but suppressed answer coverage; coverage-first did not stabilize both. The application and Judge CLI now default to `legacy`.

### Phase 5: Real Judge Rerun

Status: completed with review risk.

Latest 10-row Judge run:

```text
avg_answer_coverage=0.605
avg_citation_support=0.455
high_risk_count=0
judge_quality_gate=review_required
```

Conclusion: retrieval is improved, but generation coverage/citation stability remains a human-review risk. Phase 35 must not claim the Judge gate passed.

### Phase 6: Stage 30 Score Rerun and Density Analysis

Status: completed.

Clean final Stage 29 and Stage 30 results:

```text
python scripts/evaluate_stage29_real_quality.py --provider glm --retrieval-mode hybrid_rrf_tail
p@1=0.933 p@3=0.933 p@5=1.000 coverage=0.731 refusal_accuracy=1.000

python scripts/score_stage30_quality.py
overall=91.52 grade=A release_decision=pass

python scripts/analyze_stage35_score_density.py
current=91.52 target=88.00 gap=0.00 recorded_deductions=0.00
```

The final pass does not rely on the leaked synonym rule and does not modify scoring.

### Phase 7: Documentation and Verification

Status: completed, awaiting human verification.

Updated `docs/phase_reviews/phase-35.md`, `docs/phase_reviews/phase-35-remediation.md`, `data/evaluation/stage35_quality_summary.csv`, Stage 30 report outputs, and retrieval/Judge evaluation artifacts.

Final verification:

```text
python -m pytest -q
684 passed

Browser /quality-report desktop and 390x844:
Overall=91.52, Grade=A, pass
horizontal overflow=false
console errors=0
```

Stop condition: no staging, commit, tag, push, or PR.
