# Phase 35 Remediation Review: Leakage Removal and Retrieval Strategy

Status: awaiting human verification.
Branch: `codex/phase-35-retrieval-quality-calibration`

## Test Set Leakage Removed

User review found that `app/services/retrieval/keyword_search.py` had added an unsafe `SYNONYM_RULES` entry:

```text
rcc dam construction / dam construction develop / construction method does it resemble
-> alpe gera dam / road paving / vibratory rollers / compaction
```

`Alpe Gera Dam`, `road paving`, and `compaction` match literal values from `data/evaluation/stage29_new_corpus_queries.csv` for `stage29_wiki_dam_applications.expected_answer_points`. This is test set leakage and has been removed. The remaining RCC rule only keeps domain-generic abbreviation/synonym expansion:

```text
rcc / roller-compacted concrete / rolled concrete
-> roller-compacted concrete / rolled concrete / rollcrete
```

The retired leakage-influenced intermediate result `84.40 / B / review_required` must not be used as acceptance evidence.

## Clean Retrieval Strategy

The final clean retrieval work does not add answer-point terms to `SYNONYM_RULES`. It keeps mechanism-level changes:

- `source_type_rank` now ranks `web_page`, `wikipedia`, and `standard_document` before `metadata_record`.
- `DeterministicReRankingProvider.tokenize()` filters common English stopwords so local reranking focuses on evidence-bearing terms.
- `HybridRrfTailSearchService` preserves the existing hybrid top 3 and fills tail slots with BM25+vector RRF candidates.

This follows the open-source RAG pattern of using hybrid retrieval plus Reciprocal Rank Fusion for recall, while avoiding a full default replacement that would degrade top-1 precision.

## Clean Metrics

```text
python scripts/evaluate_stage29_real_quality.py --provider jina --retrieval-mode hybrid_rrf_tail
p@1=0.867 p@3=0.933 p@5=1.000 coverage=0.731 refusal_accuracy=1.000

python scripts/score_stage30_quality.py
overall=90.48 grade=A release_decision=pass

python scripts/analyze_stage35_deduction_causes.py
rows=0

python scripts/analyze_stage35_score_density.py
current=90.48 target=88.00 gap=0.00 recorded_deductions=0.00
```

## Judge Gate Still Requires Review

The real Judge gate remains failed and below the requested dual threshold:

```text
jina-era artifact:
answer_coverage=0.605 citation_support=0.455 safety_leak_check=0.400 high=0

production GLM before citation_validator:
answer_coverage=0.525 citation_support=0.750 safety_leak_check=0.700 high=0

production GLM after citation_validator drop mode and Judge safety prompt repair:
answer_coverage=0.410 citation_support=0.635 safety_leak_check=1.000 high=0
```

Prompt A/B after retrieval cleanup did not find a profile that simultaneously satisfies citation support and answer coverage. `legacy` is less conservative but citation support is weak; `strict_citation` improves citations but suppresses coverage; `coverage_first` still fails to stabilize both. The deterministic `citation_validator` repairs or drops unsupported sentences, but Brain `drop` mode lowers coverage by more than 5 percentage points and still leaves citation support below 0.80. Therefore Phase 35 should be reported as: retrieval quality and Stage 30 scoring are cleanly improved, while real Judge generation quality remains failed pending human review.

## Acceptance Boundary

No scoring weights, grade boundaries, release-decision rules, provider topology, or external data sources were changed. No commit, tag, push, or PR has been created.
