# Phase 35 Remediation Progress

Status: completed for human verification, not committed.

## Completed

- Removed the leaked `SYNONYM_RULES` entry that used literal Stage 29 expected answer points.
- Kept only the legitimate RCC abbreviation/synonym expansion.
- Added `scripts/analyze_stage35_score_density.py` and `tests/test_stage35_score_density.py`.
- Added score-density output: `data/evaluation/stage35_score_density.csv`.
- Added `HybridRrfTailSearchService` and tests.
- Added Stage 29 retrieval mode comparison support:
  - `hybrid`
  - `bm25_rrf`
  - `hybrid_rrf_tail`
- Re-ran clean Stage 29 with `hybrid_rrf_tail`.
- Re-ran Stage 30 scoring and deduction/root-cause analysis.
- Re-ran real Judge with 10 samples.
- Added `docs/phase_reviews/phase-35-remediation.md`.
- Added `findings_phase35_remediation.md`.

## Current Evidence

```text
python scripts/evaluate_stage29_real_quality.py --provider jina --retrieval-mode hybrid_rrf_tail
p@1=0.867 p@3=0.933 p@5=1.000 coverage=0.731 refusal_accuracy=1.000

python scripts/score_stage30_quality.py
overall=90.48 grade=A release_decision=pass

python scripts/analyze_stage35_deduction_causes.py
rows=0

python scripts/judge_stage34_generation_quality.py --execute --limit 10 --prompt-profile legacy
answer_coverage=0.605 citation_support=0.455 high=0 gate=review_required
```

## Boundary

- No `git add`.
- No commit.
- No tag.
- No push.
- No PR.
- Stage 30 scoring logic, weights, grade boundaries, and release rules were not changed.
