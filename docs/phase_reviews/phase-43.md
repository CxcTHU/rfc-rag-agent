# Phase 43 Review Draft: Multi-Turn Quality And Production Observability

## Verdict

PASS for human verification. Phase 43 completed multi-turn baseline repair, real multi-turn Judge, layered-memory decision, HTTPS template stretch work, focused tests, Stage 30 verification, normal documentation, and local Obsidian drafts. Final full regression and smoke checks are part of Phase 15 closeout and are recorded below. It is intentionally stopped before `git add`, commit, tag, push, or PR.

## Scope Alignment

- Started from Phase 42 GitHub merge `origin/main -> 5850139`.
- Working branch: `codex/phase-43-multi-turn-quality-and-observability`.
- Local `main` remains stale at `d7dfca1`; Phase 43 correctly used `origin/main`.
- Kept Stage 30 scoring rules, provider topology, data-source boundaries, and citation requirements unchanged.
- Did not add cross-session long-term memory, user profiling, external monitoring SaaS, or new data sources.

## Multi-Turn Quality Evidence

Added 16 multi-turn conversations, 32 total turns, across 8 scenarios:

- follow-up
- pronoun / ellipsis
- clarification
- topic switch
- reference previous turn
- user correction
- constrained follow-up
- multi-turn refusal

Four-way comparison:

```text
no_history avg_retrieval_hit=0.312 avg_answer_coverage=0.104
recent_only avg_retrieval_hit=0.531 avg_answer_coverage=0.125
summary_recent avg_retrieval_hit=0.594 avg_answer_coverage=0.167
layered_memory avg_retrieval_hit=0.594 avg_answer_coverage=0.208
```

Decision: do not replace the default conversation strategy with layered memory. The minimal memory improved answer coverage, especially in clarification and previous-turn-reference scenarios, but user-correction hit rate regressed in the lightweight baseline. It remains a retrieval/query-rewrite aid only.

Post-review correction: human verification found that the CSV artifacts still had `layered_memory` dry-run rows from the pre-Phase-4 state. The evaluator was rerun with `python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run`, and both Stage 43 baseline CSV files now agree with the numbers above: all four modes are completed with 32 turns each.

## Multi-Turn Judge Evidence

`scripts/judge_stage43_multi_turn_quality.py` ran real Judge for all 128 rows. Because provider latency exceeded a single command's 10-minute budget, the script was enhanced with per-row checkpointing and single-mode merge/resume. Final summary:

```text
no_history faith=0.678 citation=0.603 coherence=0.794 refusal=0.778 gate=review_required
recent_only faith=0.766 citation=0.680 coherence=0.853 refusal=0.816 gate=review_required
summary_recent faith=0.764 citation=0.641 coherence=0.784 refusal=0.794 gate=review_required
layered_memory faith=0.769 citation=0.622 coherence=0.852 refusal=0.853 gate=review_required
```

Decision after Phase 17 rerun: optimized `layered_memory` improves faithfulness, context coherence, and refusal consistency over `summary_recent`, but citation accuracy is lower than `summary_recent` and still below 0.8. It remains a query-rewrite/retrieval aid, not a default replacement. Phase 16 landed the first constraints slot and stale-anchor invalidation pass for user-correction turns; this raised the lightweight layered-memory baseline to hit=0.594 and coverage=0.208.

## Observability Evidence

- `app/core/request_logger.py` writes one sanitized JSONL request trace per request.
- `log_event()` events are aggregated under the active request trace.
- `request_id` flows through middleware, conversation loading, summary/memory assembly, query rewrite, retrieval, provider call boundaries, and final response events.
- `data/logs/` is gitignored.
- `GET /health/details` reports DB, FAISS, and provider config diagnostics without external provider ping.

## Tests And Verification

```text
python -m pytest tests/test_stage43_design.py -q -> 6 passed
python -m pytest tests/test_stage43_multi_turn_eval.py -q -> 5 passed
python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run -> completed
python -m pytest tests/test_session_memory.py tests/test_stage43_multi_turn_eval.py tests/test_brain_service.py::test_brain_service_rewrites_contextual_question_before_retrieval -q -> 10 passed
python -m pytest tests/test_request_logger.py tests/test_stage39_logging.py tests/test_session_memory.py tests/test_brain_service.py::test_brain_service_rewrites_contextual_question_before_retrieval -q -> 11 passed
python -m pytest tests/test_health_details.py tests/test_request_logger.py -q -> 5 passed
python -m pytest tests/test_stage43_multi_turn_judge.py -q -> 5 passed
python scripts/judge_stage43_multi_turn_quality.py --history-mode all -> rows=128 execute=false
python scripts/judge_stage43_multi_turn_quality.py --history-mode summary_recent --execute -> 32/32 completed
python scripts/judge_stage43_multi_turn_quality.py --history-mode layered_memory --execute -> 32/32 completed
python scripts/judge_stage43_multi_turn_quality.py --history-mode recent_only --execute -> 32/32 completed
python scripts/judge_stage43_multi_turn_quality.py --history-mode no_history --execute -> 32/32 completed
python scripts/judge_stage43_multi_turn_quality.py --history-mode layered_memory --execute --force-rerun -> 32/32 completed
python -m pytest tests/test_stage43_https_templates.py -q -> 3 passed
python -m pytest -q -> 876 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py -> rows=11 execute=false failed=0
python -m pytest tests/test_session_memory.py tests/test_stage43_multi_turn_eval.py tests/test_stage43_multi_turn_judge.py -q -> 19 passed
python scripts/evaluate_stage43_multi_turn.py --history-mode layered_memory --no-dry-run -> layered_memory avg_hit=0.594 avg_cov=0.208
```

Browser smoke on `http://127.0.0.1:8023`:

- Desktop Agent page load passed.
- Two-turn local chitchat `你好` / `谢谢` passed without real provider usage.
- Desktop console errors=0 and horizontal overflow=false.
- Mobile `390x844` showed input and run controls, retained recent chat, console errors=0, and horizontal overflow=false.
- Temporary server was stopped after smoke.

Phase 15 browser smoke on `http://127.0.0.1:8024`:

- Desktop Agent page load passed.
- Two-turn local chitchat `hello` / `thanks` passed without real provider usage.
- Desktop status=`answered`, console errors=0, horizontal overflow=false.
- Mobile `390x844` showed Agent region, input and run controls, console errors=0, horizontal overflow=false.
- Temporary server was stopped after smoke.

## Safety And Compliance

- Memory is current-conversation only.
- Memory and summary are not citation sources.
- No external provider ping in `/health/details`.
- No Sentry, Datadog, Prometheus, or external monitoring integration.
- Full tests and CI do not require real API calls.
- No API key, Bearer token, Authorization header, vendor raw response, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, or full chunk body was written to code, CSV, tests, docs, or Obsidian drafts.

## Documentation

Updated:

- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage43_multi_turn_quality_and_observability.md`
- `docs/stage43_multi_turn_judge.md`
- `docs/deployment_https_reverse_proxy.md`
- `task_plan.md`
- `findings.md`
- `progress.md`

Local Obsidian drafts updated:

- `obsidian-vault/阶段/阶段 43 - 多轮对话质量与生产可观测性强化.md`
- `obsidian-vault/阶段汇报/阶段 43 - 多轮对话质量与生产可观测性强化/阶段 43 Phase 汇报索引.md`
- Phase report drafts under the same folder.
- `obsidian-vault/首页.md`
- `obsidian-vault/阶段索引.md`
- `obsidian-vault/阶段汇报索引.md`

## Residual Observations

- `layered_memory` is useful but not yet a default replacement. Phase 16 now filters stale anchors on user-correction turns and promotes current-question anchors; Phase 17 real Judge rerun shows citation accuracy remains the limiting metric.
- Real Judge confirms layered memory's coherence/refusal benefit over `summary_recent`, but citation accuracy remains the limiting metric.
- `/health/details` intentionally checks provider configuration only; it does not prove external provider reachability.
- JSONL request traces are local runtime artifacts and are intentionally excluded from Git.

## Submission Boundary

Stop before human verification. Do not run `git add`, commit, tag, push, or create a PR until the user explicitly authorizes Phase 43 submission.
