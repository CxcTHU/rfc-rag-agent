# Phase 38 Review: Tool Calling Generation Quality

Status: draft; waiting for user human verification.
Branch: `codex/phase-38-tool-calling-generation-quality`

Baseline:

```text
main / origin/main -> 25344a8 Merge phase 37 tool calling loop migration
phase-37-complete -> 62eff40 Complete phase 37 tool calling loop migration
Phase 37 is ancestor of main and origin/main
```

## Acceptance Conclusion

Phase 38 development, tests, normal docs, Obsidian drafts, and decision drafts are complete. The branch is intentionally stopped before human verification.

The phase keeps `tool_calling_agent` as the default Agent chain, expands quality evaluation from 8 to 24 cases, implements a tool-calling-native `structured_final_answer` prompt strategy, runs real Judge A/B, and locks the frontend/query/stream default entrances to `tool_calling_agent`.

After the citation-gap follow-up, the compact citation-first `structured_final_answer` strategy passes the real six-metric Judge generation-quality gate. Earlier failed runs remain documented as prompt root-cause evidence.

Stage 30 remains `91.52 / A / pass`.

## Main Changes

- `docs/stage38_tool_calling_generation_quality.md`
- `docs/stage38_tool_calling_quality_decision.md`
- `app/services/agent/tool_calling_service.py`
- `app/api/agent.py`
- `scripts/evaluate_stage38_tool_calling_quality.py`
- `scripts/judge_stage38_tool_calling_quality.py`
- `scripts/analyze_stage38_citation_gaps.py`
- `scripts/run_production_smoke.py`
- `tests/test_stage38_design.py`
- `tests/test_stage38_tool_calling_eval.py`
- `tests/test_stage38_tool_calling_judge.py`
- `tests/test_stage38_citation_gap_analysis.py`
- `tests/test_tool_calling_agent_service.py`
- `tests/test_agent_api.py`
- `tests/test_agent_stream_api.py`
- `tests/test_run_production_smoke.py`
- `data/evaluation/stage38_tool_calling_quality_results.csv`
- `data/evaluation/stage38_tool_calling_quality_summary.csv`
- `data/evaluation/stage38_tool_calling_judge_results.csv`
- `data/evaluation/stage38_tool_calling_judge_summary.csv`
- `data/evaluation/stage38_citation_gap_analysis.csv`

## Judge Result

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

Conclusion: the original outline-first structured prompt failed on citation granularity. The final compact citation-first structured prompt passes all six average Judge gates: `faithfulness`, `answer_coverage`, `citation_support`, `refusal_correctness`, `conciseness`, and `safety_leak_check` are all `>= 0.80`. `refusal_correctness=0.921` is above the gate but has two anomalous rows to inspect during human verification.

## Default Chain Regression

```text
frontend default mode -> tool_calling_agent
POST /agent/query omitted mode -> tool_calling_agent
POST /agent/query/stream omitted mode -> tool_calling_agent
explicit mode="react_agent" -> still supported as rollback
explicit mode="default" -> still supported for legacy RAG/source-detail flows
```

`scripts/run_production_smoke.py` now writes `expected_mode`, `actual_mode`, and `mode_matched`, and fails an executed smoke row if the actual response mode does not match the case expectation.

## Verification

Focused verification completed before final full run:

```text
python -m pytest tests/test_stage38_design.py -q -> 8 passed
python -m pytest tests/test_stage38_tool_calling_eval.py -q -> 5 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_stage38_design.py tests/test_stage38_tool_calling_eval.py -q -> 28 passed
python -m pytest tests/test_stage38_tool_calling_judge.py -q -> 4 passed
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_run_production_smoke.py -q -> 44 passed
python -m pytest tests/test_stage38_design.py tests/test_stage38_tool_calling_eval.py tests/test_stage38_tool_calling_judge.py tests/test_tool_calling_agent_service.py -q -> 32 passed
python -m pytest tests/test_tool_calling_agent_service.py tests/test_stage38_citation_gap_analysis.py tests/test_stage38_tool_calling_eval.py tests/test_stage38_tool_calling_judge.py -q -> 27 passed
python scripts/evaluate_stage38_tool_calling_quality.py -> cases=24, tool_calling_agent errors=0
python scripts/analyze_stage38_citation_gaps.py -> rows=5; prompt_citation_gap=2; refusal_judge_artifact=1; retrieval_or_repair_gap=2
python scripts/judge_stage38_tool_calling_quality.py --execute --limit 24 --timeout-seconds 180 -> structured_final_answer gate=pass
python scripts/judge_stage38_tool_calling_quality.py --summarize-existing -> six-metric summary regenerated from existing 48 Judge rows
python scripts/run_production_smoke.py -> rows=11 execute=false failed=0
```

Final Phase 6 verification:

```text
python -m pytest -q -> 785 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120 -> rows=11 execute=true failed=0
browser smoke desktop readonly -> Agent page present, horizontal overflow=false, console errors=0
browser smoke 390x844 readonly -> Agent page present, horizontal overflow=false, console errors=0
```

Browser text input was blocked by the Browser runtime virtual clipboard during final verification. Default mode execution is still covered by production smoke execute, including `expected_mode=tool_calling_agent`, `actual_mode=tool_calling_agent`, and `mode_matched=true` for both query and stream default cases.

## Human Verification Focus

- Review `docs/stage38_tool_calling_quality_decision.md`.
- Inspect `data/evaluation/stage38_tool_calling_judge_summary.csv` and medium-risk rows in `stage38_tool_calling_judge_results.csv`.
- Manually compare `baseline` and `structured_final_answer` behavior on citation-heavy questions.
- Confirm default query and stream responses return `mode="tool_calling_agent"` when `mode` is omitted.
- Confirm explicit `mode="react_agent"` still works as rollback and explicit `mode="default"` still covers legacy source-detail flows.
- Confirm no deterministic citation-validator post-processing was connected to production.
- Confirm no Stage 30 scoring weights, thresholds, or release decision rules were changed.
- Confirm no API key, Bearer token, raw provider response, `reasoning_content`, hidden thought, restricted full text, or response body was written into CSV/docs/tests/Obsidian.

## Submission Boundary

Do not run `git add`, commit, tag, push, or create a PR until the user completes human verification and explicitly authorizes submission.
