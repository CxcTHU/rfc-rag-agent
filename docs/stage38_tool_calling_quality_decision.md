# Stage 38 Decision: Tool Calling Generation Quality

Status: Phase 38 development/test/docs/Obsidian draft complete; waiting for user human verification. Do not submit, tag, push, or create a PR before explicit user approval.

## Question

Should the new `structured_final_answer` strategy replace the Phase 37 default tool-calling final answer prompt?

## Short Recommendation

Yes, after human verification.

The third real Judge A/B rerun on 24 expanded Stage 38 cases shows the optimized `structured_final_answer` strategy reached the full six-metric gate:

```text
structured_final_answer:
  faithfulness=0.981
  answer_coverage=0.808
  citation_support=0.867
  refusal_correctness=0.921
  conciseness=0.925
  safety_leak_check=1.000
  judge_gate=pass
```

Keep `tool_calling_agent` as the default Agent mode, keep `structured_final_answer` as the default tool-calling final-answer strategy, and keep `mode="react_agent"` as an explicit rollback path. This remains stopped before commit/tag/push/PR until user human verification.

## Judge A/B Result

```text
python scripts/judge_stage38_tool_calling_quality.py --execute --limit 24 --timeout-seconds 180

baseline:
  completed=24/24
  faithfulness=0.958
  answer_coverage=0.775
  citation_support=0.731
  refusal_correctness=0.958
  conciseness=0.960
  safety_leak_check=1.000
  judge_gate=review_required

structured_final_answer:
  completed=24/24
  faithfulness=0.981
  answer_coverage=0.808
  citation_support=0.867
  refusal_correctness=0.921
  conciseness=0.925
  safety_leak_check=1.000
  judge_gate=pass
```

## Interpretation

The first `structured_final_answer` prompt used outline-first wording and produced `cov=0.808 / cit=0.729`. Citation-gap analysis showed 6 of 9 low-citation rows were prompt gaps: baseline passed citation support on the same query, so the evidence was likely present but the structured answer expanded without sentence-local citations.

An overly strict citation-dense prompt was tried next, but it over-compressed answers and lowered coverage. The final successful prompt is a compact citation-first structure: start with one or two cited direct-answer sentences, then use at most 3-5 short factual bullets, with every factual sentence or bullet carrying a closest `[N]` marker.

The final gate now considers all six Judge dimensions: `faithfulness`, `answer_coverage`, `citation_support`, `refusal_correctness`, `conciseness`, and `safety_leak_check`. `structured_final_answer` is a pass because every average is at least `0.80` and there are no high-risk rows. Safety did not regress: the passing run keeps `safety_leak_check=1.000`.

## Root Cause

- The failing structured prompt had too much outline-first expansion and not enough answer-format discipline.
- The over-strict variant improved citation intent but hurt coverage by encouraging under-answering.
- The successful variant balances both: compact structure, direct answer first, sentence-level citations, and explicit evidence-gap wording.
- Remaining low-citation rows include expected-refusal artifacts and a small number of retrieval/repair edge cases; they do not block the average Judge gate.
- `refusal_correctness=0.921` is above the gate but still has two anomalous rows that should be inspected during human verification.

## Current Decision

- Keep `tool_calling_agent` as the default chain after Phase 5 stability regression.
- Keep the compact citation-first `structured_final_answer` as the default tool-calling final-answer strategy.
- Do not connect deterministic citation-validator post-processing to production.
- Do not change Stage 30 scoring weights, thresholds, or release decision rules.
- Record the final Stage 38 six-metric Judge gate as `pass` for `structured_final_answer`, while preserving the earlier failed A/B attempts in the project notes.

## Default Chain Regression

Phase 5 confirmed the three default entrances:

```text
frontend default mode -> tool_calling_agent
POST /agent/query omitted mode -> tool_calling_agent
POST /agent/query/stream omitted mode -> tool_calling_agent
```

The production smoke script now records `expected_mode`, `actual_mode`, and `mode_matched`. The dry-run case count increased from 9 to 11 and includes default query/stream tool-calling checks. Explicit `mode="react_agent"` and `mode="default"` remain covered.

## Verification Summary

```text
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_run_production_smoke.py -q -> 44 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_stage38_citation_gap_analysis.py tests/test_stage38_tool_calling_eval.py tests/test_stage38_tool_calling_judge.py -q -> 27 passed
python scripts/evaluate_stage38_tool_calling_quality.py -> cases=24, tool_calling_agent errors=0
python scripts/analyze_stage38_citation_gaps.py -> rows=5; prompt_citation_gap=2; refusal_judge_artifact=1; retrieval_or_repair_gap=2
python scripts/judge_stage38_tool_calling_quality.py --execute --limit 24 --timeout-seconds 180 -> structured_final_answer gate=pass
python scripts/judge_stage38_tool_calling_quality.py --summarize-existing -> six-metric summary regenerated from existing 48 Judge rows
python scripts/run_production_smoke.py -> rows=11 execute=false failed=0
```

Final full verification is recorded in `docs/phase_reviews/phase-38.md`: full pytest `785 passed`, Stage 30 `91.52 / A / pass`, production smoke execute `rows=11 failed=0`, and browser desktop/mobile readonly smoke passed.

## Evidence Files

```text
data/evaluation/stage38_tool_calling_judge_results.csv
data/evaluation/stage38_tool_calling_judge_summary.csv
data/evaluation/stage38_tool_calling_quality_results.csv
data/evaluation/stage38_tool_calling_quality_summary.csv
```
