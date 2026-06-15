# Phase 36 Review: Generation Reliability and Conversation Stability

Status: human verified; submission and GitHub merge authorized.
Branch: `codex/phase-36-generation-reliability-and-conversation-stability`

Baseline:

```text
main -> dc751fb
phase-35-complete -> 7877308
phase-35-complete is ancestor of main
phase 35 multiturn supplement -> 0af4a87, already merged and accepted
```

## Acceptance Conclusion

Phase 36 has completed human verification and is ready for submission.

The phase improves refusal explainability, production smoke automation, offline Judge A/B infrastructure, and conversation intent routing regression coverage. It does not change Stage 30 scoring rules, provider topology, default chat/embedding/rerank providers, external data sources, or production Brain generation strategy.

Stage 30 must remain `91.52 / A / pass`.

Judge gate is **not passed**. The offline A/B infrastructure was implemented and real `--execute` completed 20 judged queries for each strategy, but every strategy remains `review_required`. No `outline_first`, `answer_provider_ab`, or deterministic validator strategy is connected to production.

## Main Changes

- `docs/stage36_generation_reliability_and_conversation_stability.md`
- `tests/test_stage36_design.py`
- `app/services/agent/refusal_explainer.py`
- `tests/test_refusal_explainer.py`
- `scripts/run_production_smoke.py`
- `tests/test_run_production_smoke.py`
- `app/services/generation/outline_first_strategy.py`
- `scripts/judge_stage36_strategy_ab.py`
- `tests/test_stage36_judge_strategy_ab.py`
- `app/services/agent/intent_router.py`
- `tests/test_intent_router.py`

## Judge A/B Result

```text
dry-run: 20 queries * 3 strategies = 60 rows
--execute --limit 20 --timeout-seconds 180: completed Judge rows = 60
baseline: cov=0.655, cit=0.640, safety=1.000, gate=review_required
outline_first: cov=0.703, cit=0.685, safety=1.000, gate=review_required
answer_provider_ab: cov=0.772, cit=0.820, safety=0.950, gate=review_required
```

Decision: keep production Brain unchanged. Do not claim Judge pass.

## Verification So Far

```text
python -m pytest tests/test_stage36_design.py -q -> 5 passed
python -m pytest tests/test_refusal_explainer.py tests/test_agent_api.py tests/test_agent_tools.py tests/test_agent_service.py -q -> 42 passed
python -m pytest tests/test_run_production_smoke.py -q -> 6 passed
python scripts/run_production_smoke.py --execute -> rows=7 execute=true failed=0
python -m pytest tests/test_stage36_judge_strategy_ab.py -q -> 6 passed
python scripts/judge_stage36_strategy_ab.py -> rows=60 queries=20 execute=false
python scripts/judge_stage36_strategy_ab.py --execute --limit 20 --timeout-seconds 180 -> completed_rows=60; all strategies review_required
python -m pytest tests/test_intent_router.py tests/test_agent_api.py -q -> 30 passed
python -m pytest -q -> 724 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
browser smoke desktop -> no horizontal overflow, console errors=0
browser smoke 390x844 -> no horizontal overflow, console errors=0
```

Final full pytest, Stage 30 score rerun, production smoke `--execute`, and browser smoke are complete.

## Human Verification Focus

- Confirm refusal explanations are helpful and do not expose internal rules or full chunks.
- Review `stage36_production_smoke_results.csv` from the final `--execute` run.
- Review Judge A/B `review_required` conclusion and confirm no production strategy was switched.
- Confirm intent router regression covers the expected 8 conversation intents.
- Confirm the final commit/tag/push/merge records after submission.

## Submission Boundary

User authorized Phase 36 staging, commit, `phase-36-complete` tag, push, and GitHub merge on 2026-06-15.
