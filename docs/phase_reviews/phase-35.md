# Phase 35 Review: Retrieval Quality Calibration and Stage 30 Breakthrough

Status: awaiting human verification.
Branch: `codex/phase-35-retrieval-quality-calibration`

Baseline: `phase-34-complete -> 8028acb`, merged into `main -> d9053a6`. Phase 35 did not move any existing phase tag.

## Acceptance Conclusion

Phase 35 is ready for human verification, not submission.

The clean final result is `91.52 / A / pass` on Stage 30 under the default GLM embedding provider, achieved without changing scoring weights, grade boundaries, release rules, default providers, provider topology, or external data sources. The earlier `84.40 / B / review_required` result is retired because it included a test-set leakage synonym rule and must not be used as acceptance evidence.

Judge gate status: FAIL (`answer_coverage<0.80`, `citation_support<0.80`; safety leakage regression was traced to Judge false positives and repaired in the Judge prompt).

The citation validator has been decoupled from the production Brain path because its drop-mode behavior measurably hurt answer coverage (-0.115) and citation support (-0.115). The function and tests remain available for offline Judge experiments and future generation strategy work. Phase 35 ends with: Stage 30 = 91.52 / A / pass (clean, on production GLM); Judge gate FAIL; no production regression introduced.

The real LLM Judge gate remains failed after the production GLM rerun and citation validator experiment. Retrieval quality and Stage 30 scoring are cleanly fixed; generated answer coverage/citation stability remains a separate human-review risk.

## Test Set Leakage Found and Removed

User review found that `app/services/retrieval/keyword_search.py` had added this unsafe `SYNONYM_RULES` entry:

```text
rcc dam construction / dam construction develop / construction method does it resemble
-> alpe gera dam / road paving / vibratory rollers / compaction
```

`Alpe Gera Dam`, `road paving`, and `compaction` match literal answer points from `data/evaluation/stage29_new_corpus_queries.csv` for `stage29_wiki_dam_applications.expected_answer_points`. That is test set leakage because the retrieval dictionary encoded evaluation answers.

This rule has been deleted. The remaining RCC rule is domain-generic abbreviation expansion only:

```text
rcc / roller-compacted concrete / rolled concrete
-> roller-compacted concrete / rolled concrete / rollcrete
```

`data/evaluation/stage35_quality_summary.csv` now includes `leakage_status`; the final score rows are marked `clean_final`, and the leaked intermediate score is marked `leaked_retired`.

## Clean Retrieval Strategy

Phase 35 no longer adds query-specific answer terms to `SYNONYM_RULES`. The final retrieval changes are mechanism-level:

- `source_type_rank` ranks full web/source documents ahead of metadata-only records.
- `DeterministicReRankingProvider.tokenize()` filters common English stopwords before overlap scoring.
- `HybridRrfTailSearchService` preserves the existing hybrid top 3 and uses BM25+vector Reciprocal Rank Fusion only to fill tail recall slots.
- `BrainService` uses `HybridRrfTailSearchService` on the default non-decomposed hybrid path; explicit `/search/hybrid` remains compatible.

Architecture note: `HybridRrfTailSearchService` is a retrieval strategy wrapper. In this project it appears under `app/services/retrieval/` and keeps the trusted hybrid head while borrowing RRF tail recall. In an interview, explain it as: "I did not tune the exam answers into the keyword dictionary; I added a retrieval strategy that improves recall through rank fusion while preserving the stable top results."

## External Architecture Reference

The user asked to learn from `CxcTHU/claude-code-analysis`. The useful lesson was architectural, not code copying: keep orchestration, tools, context, and policy as layered components with observable boundaries. Phase 35 applies that idea by isolating retrieval strategy (`HybridRrfTailSearchService`) from scoring logic and prompt/Judge logic.

RRF was selected because it is a standard hybrid retrieval pattern: it merges result rankings from different retrieval signals without requiring comparable raw scores. That fits this project better than adding more hard-coded keyword rules.

## Clean Metrics

```text
python scripts/evaluate_stage29_real_quality.py --provider glm --retrieval-mode hybrid_rrf_tail
p@1=0.933 p@3=0.933 p@5=1.000 coverage=0.731 refusal_accuracy=1.000

python scripts/score_stage30_quality.py
overall=91.52 grade=A release_decision=pass

python scripts/analyze_stage35_deduction_causes.py
rows=0

python scripts/analyze_stage35_score_density.py
current=91.52 target=88.00 gap=0.00 recorded_deductions=0.00
```

Stage 30 score density now shows no remaining deduction rows. The "break 88" cost is therefore zero after clean retrieval rerun; before the clean rerun, density analysis showed that small per-query fixes were not a sustainable method and justified switching to a retrieval strategy change.

## Judge A/B Result

Prompt A/B and validator A/B did not find a profile that satisfies both coverage and citation gates:

```text
jina-era Judge artifact:
answer_coverage=0.605 citation_support=0.455 safety_leak_check=0.400 high=0

production GLM rerun before citation_validator:
answer_coverage=0.525 citation_support=0.750 safety_leak_check=0.700 high=0

strict_citation:
citation_support improved, answer_coverage regressed

coverage_first:
did not stabilize both coverage and citation support

production GLM after citation_validator in Brain drop mode and Judge safety prompt repair:
answer_coverage=0.410 citation_support=0.635 safety_leak_check=1.000 high=0
```

`citation_validator` is implemented as a deterministic post-generation guard, but it is no longer connected to the production Brain path. Its default pure-function mode is `annotate`; the failed production experiment used Brain `drop` mode to avoid exposing validator markers in user-facing answers. The A/B result shows safety is repaired, but answer coverage drops by more than 5 percentage points and citation support remains below 0.80, so Phase 35 must not claim the real Judge gate as passed and must not keep the drop-mode regression in production.

## Remaining Review Risk

The remaining risk is generation quality, not retrieval scoring. `validate_and_repair_citations()` removes or annotates sentences that lack a valid source id or have no keyword overlap with cited source content. In the reverted Brain `drop` experiment, the GLM Judge sample moved safety from `0.700` to `1.000`, but coverage moved from `0.525` to `0.410` and citation support from `0.750` to `0.635`. This confirms deterministic citation repair is useful as an offline safety/citation hygiene guard, but it is too lossy for production answers and has been withdrawn from `BrainService`.

Post-remediation smoke also found that the default `/agent/query` `react_agent` path could refuse in-scope questions when the LLM planner returned non-JSON on the first iteration. The fallback now searches first for clearly in-scope RFC/concrete/hydraulic-engineering questions, while still refusing out-of-scope questions when no evidence exists. This is a production-path stability fix and does not change scoring rules, provider topology, or Judge thresholds.

Safety attribution is recorded in `data/evaluation/stage35_safety_leak_attribution.csv`: all six low-safety rows in the earlier `stage35_llm_judge_results.csv` were `judge_false_positive` cases where the short reason described coverage, citation, refusal, or faithfulness issues rather than hidden thought, raw provider metadata, credentials, authorization material, or restricted full text leakage. The repaired Judge prompt distinguishes those categories, and the final GLM rerun reports `avg_safety_leak_check=1.000`.

## Verification

```text
python -m pytest tests/test_stage34_llm_judge.py tests/test_prompt_builder.py -q
16 passed

python -m pytest tests/test_hybrid_rrf_tail.py tests/test_evaluate_stage29_real_quality.py tests/test_rrf_fusion.py tests/test_hybrid_search.py tests/test_reranking.py tests/test_keyword_search.py tests/test_stage35_score_density.py -q
39 passed

python -m pytest tests/test_stage35_deduction_causes.py -q
3 passed

python -m pytest tests/test_react_llm_planner.py tests/test_react_agent_service.py tests/test_agent_api.py -q
33 passed

python -m pytest -q
694 passed

python scripts/build_stage30_quality_report.py
stage30 quality report built score=91.52 grade=A
```

Browser smoke on `http://127.0.0.1:8001/quality-report`:

```text
desktop:
  Overall=91.52, Grade=A, release_decision=pass
  horizontal overflow=false
  console errors=0

390x844:
  Overall=91.52, Grade=A, release_decision=pass
  horizontal overflow=false
  console errors=0
```

API smoke:

```text
GET /health -> 200
GET /quality-report -> 200
GET /quality-report/data.json -> 200
GET /quality-report/export.csv -> 200
POST /search/hybrid -> 200
POST /agent/query mode=react_agent -> 200, refused=false, tool_calls=hybrid_search_knowledge,answer_with_citations, marker=false
```

## Safety Boundary

- No API key, Bearer token, authorization header, raw provider response, `reasoning_content`, hidden thought, or restricted full text was written to CSV, docs, tests, or Obsidian drafts.
- Real provider calls remain explicit and are not required for CI.
- `/chat`, `/agent/query`, `/agent/query/stream`, `/search/*`, and `/quality-report` remain compatible.
- No scoring weights, grade boundaries, or release-decision rules were changed.

## Human Verification Focus

- Confirm `keyword_search.py` contains no literal terms copied from `expected_answer_points`.
- Review `HybridRrfTailSearchService` as a mechanism-level retrieval change rather than a scoring workaround.
- Confirm `/quality-report` shows the clean `91.52 / A / pass` result.
- Review real Judge outputs because answer coverage and citation support are still below target.
- Confirm the working tree is intentionally unstaged and uncommitted.

## Submission Boundary

Current state is stopped before human verification:

- No `git add`
- No `git commit`
- No `phase-35-complete` tag
- No `git push`
- No PR
