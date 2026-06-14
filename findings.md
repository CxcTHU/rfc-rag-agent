# Phase 35 Findings

## Main Correction

The user was right to challenge the earlier direction: Phase 35 must optimize retrieval, not chase the Stage 30 score with per-query answer patches.

The leaked synonym rule in `app/services/retrieval/keyword_search.py` copied literal expected answer points for `stage29_wiki_dam_applications`:

```text
rcc dam construction / dam construction develop / construction method does it resemble
-> alpe gera dam / road paving / vibratory rollers / compaction
```

This has been removed. The retired `84.40 / B / review_required` result is invalid for acceptance.

## External Architecture Lesson

The `CxcTHU/claude-code-analysis` project is useful as an architecture reference: keep layers separated and observable. For this project, that means retrieval strategy belongs in `app/services/retrieval/`, not inside scoring scripts or query-specific keyword dictionaries.

Phase 35 applies that lesson through `HybridRrfTailSearchService`, a small retrieval strategy wrapper:

- keep the stable hybrid head;
- use BM25+vector RRF for tail recall;
- do not let evaluation answer text influence retrieval expansion.

Interview wording: "I avoided encoding the benchmark answers into retrieval rules. Instead I isolated retrieval strategy as a service and used rank fusion to improve recall while preserving stable top results."

## Clean Retrieval Results

Final clean Stage 29 rerun:

```text
retrieval_mode=hybrid_rrf_tail
p@1=0.933
p@3=0.933
p@5=1.000
avg_coverage_ratio=0.731
refusal_accuracy=1.000
```

Final Stage 30 rerun:

```text
overall=91.52
grade=A
release_decision=pass
deduction_rows=0
```

No Stage 30 scoring weights, grade thresholds, or release-decision rules changed.

## Judge Finding

Prompt A/B did not solve real Judge stability:

```text
latest official 10-row Judge summary:
answer_coverage=0.605
citation_support=0.455
high_risk_count=0
gate=review_required
```

Strict citation profiles made answers more conservative and hurt coverage. Coverage-first did not repair both metrics. The honest conclusion is: retrieval and rule-based Stage 30 are cleanly improved; real generated answer coverage/citation support still needs review.

## Safety Finding

`stage35_quality_summary.csv` now includes `leakage_status`:

- `clean_final` for accepted current metrics;
- `leaked_retired` for the invalid intermediate 84.40 result.

No raw provider response, reasoning content, hidden thought, API key, Bearer token, or restricted full text should be present in the new CSV or docs.
