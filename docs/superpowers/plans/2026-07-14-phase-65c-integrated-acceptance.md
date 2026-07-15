# Phase 65C Integrated Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that the modular Runtime preserves public behavior, production-topology reliability, quality, latency, recovery, and cost versus the frozen pre-refactor baseline.

**Architecture:** Contract snapshots and deterministic tests run first, followed by real Postgres/Redis/auth integration and controlled fault/recovery tests. Only after those pass do two isolated baseline/candidate servers execute the 180-request cold A/B, blind judge, and reviewer holdout. A single manifest-bound report publishes four independent gate decisions and preserves the absolute Phase 64 latency result.

**Tech Stack:** Python 3.11+, pytest, FastAPI SSE, PostgreSQL 16 + pgvector, Redis Stack, Docker Compose, existing React/Vitest/Vite, Phase 65 gate scripts.

## Global Constraints

- 65A and 65B focused/full regressions must pass before real paired evaluation.
- Baseline and candidate run in isolated worktrees/processes against matching corpus/index/provider/prompt/tool contracts; endpoint identities must differ.
- Primary cold gate disables retrieval candidate, rerank-order, tool-result, and semantic evidence caches for both variants.
- Judge requests run after latency capture and are excluded from runtime percentiles.
- Fault, recovery, load, warm-cache, and holdout rows cannot satisfy primary cold latency or bootstrap gates.
- Deterministic candidate completion, route, required-channel, refusal, citation-validity, and minimum-citation rates must each be ≥ baseline.
- Four judge lower bounds must each be ≥ `-0.05`; TTFT/final P95 and successful-task token/cost ratios must each be ≤ `1.05`.
- Controlled runs require zero unclassified errors and zero repeated completed tools.
- Final Postgres, Redis, and auth evidence cannot be skipped.
- Absolute Phase 64 targets are reported independently and cannot be inferred from relative non-regression.
- No answer text, full evidence, prompt, provider payload, hidden reasoning, credential, or private log may be retained.
- No Git staging, commit, tag, push, PR, or merge before user functional verification and explicit authorization.

---

### Task 1: Freeze API, SSE, Tool, Citation, And Checkpoint Contracts

**Files:**
- Create: `scripts/snapshot_phase65_agent_contract.py`
- Create: `tests/test_phase65_contract_snapshot.py`
- Create after verification: `data/evaluation/phase65_contract_snapshot.json`
- Modify: `tests/test_phase63_unified_agent_contract.py`
- Modify: `tests/test_agent_stream_api.py`

**Interfaces:**
- Produces: `build_contract_snapshot()` containing hashes for request/response JSON schema, SSE fixture, tool definitions, citation/refusal invariants, checkpoint schema, and Runtime event vocabulary.

- [ ] **Step 1: Write failing deterministic snapshot test**

```python
def test_contract_snapshot_is_safe_and_deterministic():
    first = build_contract_snapshot()
    second = build_contract_snapshot()
    assert first == second
    assert first["agent_request_schema_sha256"]
    assert first["sse_fixture_sha256"]
    assert "answer" not in json.dumps(first).casefold()
```

- [ ] **Step 2: Observe missing-module failure**

Run: `python -m pytest tests/test_phase65_contract_snapshot.py -q`

Expected: missing-module failure.

- [ ] **Step 3: Implement canonical contract hashing**

```python
def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def build_contract_snapshot() -> dict[str, object]:
    return {
        "schema_version": "phase65-contract-v1",
        "agent_request_schema_sha256": canonical_sha256(AgentQueryRequest.model_json_schema()),
        "agent_response_schema_sha256": canonical_sha256(AgentQueryResponse.model_json_schema()),
        "tool_schema_sha256": canonical_sha256([tool.model_dump() for tool in tool_calling_tool_definitions()]),
        "sse_fixture_sha256": canonical_sha256(SSE_CONTRACT_FIXTURE),
        "checkpoint_schema_sha256": canonical_sha256(CheckpointSnapshot.schema_descriptor()),
        "runtime_event_names": sorted(ALLOWED_RUNTIME_EVENT_NAMES),
    }
```

The SSE fixture contains only event names and safe payload shapes, not question/answer text.

- [ ] **Step 4: Compare baseline and candidate snapshots**

Run the snapshot script in both isolated worktrees and compare every field. Any difference requires explicit user-approved contract change; otherwise the contract gate is `fail`.

- [ ] **Step 5: Run contract tests**

Run: `python -m pytest tests/test_phase65_contract_snapshot.py tests/test_phase63_unified_agent_contract.py tests/test_agent_stream_api.py tests/test_stage40_streaming_output_safety.py -q`

Expected: all tests PASS and snapshots match.

- [ ] **Step 6: Review boundary**

Run: `git diff --check && git status --short`

Expected: clean whitespace; do not stage or commit.

### Task 2: Mandatory Postgres + Redis + Auth Integration Gate

**Files:**
- Create: `scripts/verify_phase65_production_topology.py`
- Create: `tests/test_phase65_production_topology.py`
- Modify: `docker-compose.dev.yml` only if the test proves a missing health dependency
- Modify: `docs/deployment_guide.md`

**Interfaces:**
- Produces: safe JSON summary with `postgres`, `pgvector`, `redis`, `auth`, `checkpoint`, `agent_sse`, and `skipped_required` fields.

- [ ] **Step 1: Write failing topology-summary tests**

```python
def test_required_integration_skip_blocks_gate():
    summary = build_topology_summary(postgres="pass", redis="skip", auth="pass", checkpoint="pass", agent_sse="pass")
    assert summary["gate"] == "blocked"
    assert summary["skipped_required"] == ["redis"]

def test_all_required_components_pass():
    summary = build_topology_summary(postgres="pass", redis="pass", auth="pass", checkpoint="pass", agent_sse="pass")
    assert summary["gate"] == "pass"
```

- [ ] **Step 2: Observe failure**

Run: `python -m pytest tests/test_phase65_production_topology.py -q`

Expected: missing-module failure.

- [ ] **Step 3: Implement explicit probes**

```python
REQUIRED_COMPONENTS = ("postgres", "pgvector", "redis", "auth", "checkpoint", "agent_sse")

def build_topology_summary(**statuses: str) -> dict[str, object]:
    skipped = [name for name in REQUIRED_COMPONENTS if statuses.get(name) == "skip"]
    failed = [name for name in REQUIRED_COMPONENTS if statuses.get(name) != "pass"]
    return {"gate": "pass" if not failed else "blocked", "skipped_required": skipped, "failed_required": failed}
```

The executable probe must connect with `DATABASE_URL` and `REDIS_URL`, verify the `vector` extension, run migrations, register/login a local test user, open an authenticated Agent SSE request, stop/resume a checkpoint, and verify Redis ping. It logs categories/counts only.

- [ ] **Step 4: Start local production topology**

Run: `docker compose -f docker-compose.dev.yml up -d db redis`

Expected: both services become healthy.

- [ ] **Step 5: Run migrations and topology verification**

Run with local development environment variables: `python -m alembic upgrade head`

Expected: exit 0 against PostgreSQL.

Run: `python scripts/verify_phase65_production_topology.py --out output/phase65-topology.json`

Expected: `gate=pass`, `skipped_required=[]`, and every required component is `pass`.

- [ ] **Step 6: Run focused existing topology tests**

Run: `python -m pytest tests/test_phase65_production_topology.py tests/test_phase49_local_postgres_dev.py tests/test_phase50_redis_foundation.py tests/test_phase50_redis_stack_checkpointer.py tests/test_stage44_auth.py -q`

Expected: all tests PASS; `test_phase50_redis_stack_checkpointer.py` must execute rather than skip because `PHASE50_REDIS_STACK_URL` is set.

- [ ] **Step 7: Review boundary**

Run: `git diff --check && git status --short`

Expected: clean whitespace; do not stage or commit.

### Task 3: Fault, Cancellation, Recovery, And Load Matrix

**Files:**
- Create: `tests/test_phase65_runtime_fault_matrix.py`
- Create: `scripts/run_phase65_fault_matrix.py`
- Create after safe execution: `data/evaluation/phase65_fault_summary.json`
- Modify only when tests expose a defect: the owning 65B module and its focused test

**Interfaces:**
- Produces: safe per-case categories and aggregate `unclassified_errors`, `completed_tool_replay_count`, `cancelled_work_leak_count`, and `gate`.

- [ ] **Step 1: Write the parameterized fault matrix**

```python
@pytest.mark.parametrize(
    ("fault", "expected_stop", "expected_category"),
    [
        ("planner_invalid", None, "deterministic_fallback"),
        ("planner_timeout", None, "deterministic_fallback"),
        ("optional_channel_timeout", None, "optional_channel_failed"),
        ("required_evidence_missing", "insufficient_evidence", "required_evidence_missing"),
        ("rerank_failure", "insufficient_evidence", "reranking_failed"),
        ("checkpoint_write_failure", "checkpoint_unavailable", "checkpoint_write_failed"),
        ("deadline", "deadline_exhausted", "deadline_exhausted"),
        ("cancel", "cancelled", "client_stream_aborted"),
    ],
)
def test_fault_matrix(fault, expected_stop, expected_category, injected_runtime):
    result = injected_runtime.run(fault)
    assert result.safe_category == expected_category
    assert result.stop_reason == expected_stop
```

- [ ] **Step 2: Run tests and observe real failures before fixes**

Run: `python -m pytest tests/test_phase65_runtime_fault_matrix.py -q`

Expected: each unimplemented injection/normalization test fails specifically; do not weaken assertions.

- [ ] **Step 3: Add injectable adapter failures at module boundaries**

Use test doubles for planner, toolbox, reranker adapter, checkpoint repository, clock, and cancellation token. Do not add production-only debug endpoints or provider fallbacks.

- [ ] **Step 4: Prove cancellation and resume idempotency**

```python
def test_cancel_then_resume_never_replays_completed_tool(runtime, executor):
    stopped = runtime.run(cancel_after_tool="runtime-retrieval-1")
    resumed = runtime.resume(stopped.run_id)
    assert executor.execution_count("runtime-retrieval-1") == 1
    assert resumed.completed_tool_replay_count == 0
```

- [ ] **Step 5: Execute bounded load/fault summary**

Run: `python scripts/run_phase65_fault_matrix.py --concurrency 8 --requests 80 --out data/evaluation/phase65_fault_summary.json`

Expected: `unclassified_errors=0`, `completed_tool_replay_count=0`, `cancelled_work_leak_count=0`, `gate=pass`.

- [ ] **Step 6: Safety scan and review boundary**

Run: `rg -n -i "answer|snippet|raw_response|reasoning_content|authorization|bearer |api[_-]?key|password|secret" data/evaluation/phase65_fault_summary.json`

Expected: no sensitive-value matches.

Run: `git diff --check && git status --short`

Expected: clean whitespace; do not stage or commit.

### Task 4: Execute Frozen 180-Request Cold A/B And Blind Judge

**Files:**
- Create after execution and safe review: `data/evaluation/phase65_paired_manifest_baseline.json`
- Create after execution and safe review: `data/evaluation/phase65_paired_manifest_candidate.json`
- Create after execution and safe review: `data/evaluation/phase65_paired_results.csv`
- Create after execution and safe review: `data/evaluation/phase65_paired_judge.csv`
- Create after execution and safe review: `data/evaluation/phase65_paired_summary.json`

- [ ] **Step 1: Verify both worktrees and manifests before paid execution**

Run the contract snapshot and manifest dry-run against baseline port 8001 and candidate port 8002.

Expected: different endpoint identity hashes; matching corpus/index/provider/prompt/tool schema/cache policy; baseline worktree matches the frozen 65A identity; candidate worktree matches the reviewed patch fingerprint.

- [ ] **Step 2: Run a two-case × one-run paid smoke**

Run: `python scripts/evaluate_phase65_agent_gate.py --mode paired --execute --baseline-base-url http://127.0.0.1:8001 --candidate-base-url http://127.0.0.1:8002 --cases data/evaluation/phase64_latency_cases.csv --limit 2 --runs 1 --seed 650013 --token-env PHASE65_AUTH_TOKEN --out output/phase65-paired-smoke.csv --summary-out output/phase65-paired-smoke-summary.json`

Expected: 4 completed rows, zero unclassified errors, observed models/contracts match. Smoke rows cannot satisfy the release gate.

- [ ] **Step 3: Execute the full cold paired run**

Run: `python scripts/evaluate_phase65_agent_gate.py --mode paired --execute --execute-blind-judge --baseline-base-url http://127.0.0.1:8001 --candidate-base-url http://127.0.0.1:8002 --cases data/evaluation/phase64_latency_cases.csv --runs 3 --seed 650013 --token-env PHASE65_AUTH_TOKEN --manifest-out data/evaluation/phase65_paired_manifest_candidate.json --baseline-manifest-out data/evaluation/phase65_paired_manifest_baseline.json --out data/evaluation/phase65_paired_results.csv --judge-out data/evaluation/phase65_paired_judge.csv --summary-out data/evaluation/phase65_paired_summary.json`

Expected: 180 complete request rows, 90 safe judge rows, and zero unclassified
errors. For each pair, both request latencies are finalized before its judge call;
judge latency is excluded from runtime percentiles. Answers remain in memory only
until that pair's judge projection is built.

- [ ] **Step 4: Verify the in-process blind-judge projection**

Run: `python -c "import csv; from pathlib import Path; rows=list(csv.DictReader(Path('data/evaluation/phase65_paired_judge.csv').open(encoding='utf-8-sig'))); assert len(rows)==90; forbidden={'answer','prompt','reason','raw_response','reasoning_content'}; assert forbidden.isdisjoint(rows[0]); print('judge_rows=90 safe_schema=true')"`

Expected: `judge_rows=90 safe_schema=true`; all four normalized dimensions exist,
and no answer/prompt/reason text is persisted.

- [ ] **Step 5: Rebuild the paired summary with enforced gates**

Run: `python scripts/evaluate_phase65_agent_gate.py --mode summarize --baseline-manifest data/evaluation/phase65_paired_manifest_baseline.json --candidate-manifest data/evaluation/phase65_paired_manifest_candidate.json --results data/evaluation/phase65_paired_results.csv --judge-out data/evaluation/phase65_paired_judge.csv --summary-out data/evaluation/phase65_paired_summary.json --enforce-gates`

Expected: the report emits all four independent decisions. Record PASS/FAIL/BLOCKED exactly; never edit thresholds or rows to obtain PASS.

- [ ] **Step 6: Safety scan**

Run: `rg -n -i "answer|snippet|prompt|raw_response|reasoning_content|authorization|bearer |api[_-]?key|password|secret" data/evaluation/phase65_paired_*.json data/evaluation/phase65_paired_*.csv`

Expected: no sensitive-value matches; inspect field-name-only matches manually.

### Task 5: Execute Reviewer Holdout And Cost Gate

**Files:**
- Local input, never committed: `data/evaluation/phase65_private_holdout_cases.csv`
- Create after execution and safe review: `data/evaluation/phase65_holdout_summary.json`
- Modify: `data/evaluation/phase65_paired_summary.json`

- [ ] **Step 1: Validate holdout without revealing it to implementation code**

Run: `python scripts/evaluate_phase65_agent_gate.py --mode holdout --baseline-base-url http://127.0.0.1:8001 --candidate-base-url http://127.0.0.1:8002 --holdout-cases data/evaluation/phase65_private_holdout_cases.csv --out output/phase65-holdout-dry-run.csv --summary-out output/phase65-holdout-dry-run.json`

Expected: at least 12 unique cases, required schema present, no execution, and the local input remains ignored.

- [ ] **Step 2: Execute one A/B observation per holdout case**

Run with `--execute`, `--token-env PHASE65_AUTH_TOKEN`, and `--execute-blind-judge`, writing only `data/evaluation/phase65_holdout_summary.json`.

Expected: every case has baseline/candidate contract results; no deterministic regression or newly unsafe answer/refusal class. Holdout timing is excluded from primary percentiles.

- [ ] **Step 3: Calculate successful-task token and cost ratios**

```python
def successful_task_ratio(rows, metric):
    baseline = mean(float(row[metric]) for row in rows if row["variant"] == "baseline" and row["ok"])
    candidate = mean(float(row[metric]) for row in rows if row["variant"] == "candidate" and row["ok"])
    return candidate / baseline if baseline > 0 else None
```

Use provider-reported token/cost values when available. Otherwise use token counts plus a manifest-bound pricing snapshot and label cost `estimated`; never invent missing usage.

- [ ] **Step 4: Merge holdout/cost status into the final decision**

Expected: missing usage or holdout evidence yields `blocked`; token and cost ratios must both be ≤ `1.05` when measurable.

- [ ] **Step 5: Safety scan and review boundary**

Run: `git check-ignore -q data/evaluation/phase65_private_holdout_cases.csv && git diff --check && git status -sb`

Expected: holdout input is ignored; no whitespace errors. Do not stage or commit.

### Task 6: Final Verification, Documentation, And Human Acceptance

**Files:**
- Create: `docs/phase_reviews/phase-65.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/data_sources.md`
- Modify: `docs/progress.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `handoff.md`
- Modify: `obsidian-agent开发/阶段/阶段 65 - Agent 真实质量门禁与 Runtime 模块化/00-阶段总览.md`
- Modify: `obsidian-agent开发/阶段/阶段 65 - Agent 真实质量门禁与 Runtime 模块化/01-开发记录.md`
- Modify: `obsidian-agent开发/阶段/阶段 65 - Agent 真实质量门禁与 Runtime 模块化/02-收尾交接.md`
- Modify: `obsidian-agent开发/阶段/阶段 65 - Agent 真实质量门禁与 Runtime 模块化/03-文件地图与恢复顺序.md`
- Modify: `obsidian-agent开发/阶段/00-索引.md`

- [ ] **Step 1: Run all focused Phase 65 tests**

Run: `python -m pytest tests/test_phase65_gate_manifest.py tests/test_phase65_agent_gate.py tests/test_judge_phase65_agent_gate.py tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_runtime_contracts.py tests/test_phase65_runtime_events.py tests/test_phase65_planning_policy.py tests/test_phase65_tool_executor.py tests/test_phase65_evidence_state_machine.py tests/test_phase65_final_answer_controller.py tests/test_phase65_checkpoint_repository.py tests/test_phase65_run_coordinator.py tests/test_phase65_contract_snapshot.py tests/test_phase65_production_topology.py tests/test_phase65_runtime_fault_matrix.py -q`

Expected: all tests PASS.

- [ ] **Step 2: Run full backend verification**

Run: `python -m pytest -q`

Expected: exit 0; record exact pass/skip counts. A required Postgres/Redis/auth integration skip blocks final acceptance even if pytest exits 0.

- [ ] **Step 3: Run frontend verification**

Run from `frontend`: `npm run test:unit && npm run lint && npm run build`

Expected: all commands exit 0 with exact test count recorded.

- [ ] **Step 4: Build current quality report and enforce final gate**

Run Stage 30 collection/scoring/reporting against the final candidate manifest, then run the Phase 65 summarize command with contract, topology, fault, paired judge, holdout, and cost artifacts.

Expected: stale/missing/mismatched evidence cannot render PASS. The report explicitly lists `contract_gate`, `quality_gate`, `runtime_non_regression_gate`, and `phase64_latency_closure_gate`.

- [ ] **Step 5: Write evidence-backed documentation**

Document only observed architecture and results. `docs/phase_reviews/phase-65.md` must distinguish functional human acceptance, Phase 65 relative acceptance, and Phase 64 absolute latency closure. Include exact commands/counts, manifest IDs/hashes, safe metrics, failures, and unclosed gates.

- [ ] **Step 6: Run documentation and safety checks**

Run: `rg -n -i "bearer [a-z0-9]|api[_-]?key\s*[:=]\s*[^<]|password\s*[:=]\s*[^<]|reasoning_content|raw_response" docs data/evaluation task_plan.md findings.md progress.md handoff.md`

Expected: no credential, raw payload, or hidden-reasoning disclosure; inspect legitimate schema mentions manually.

Run: `git diff --check && git status -sb`

Expected: no whitespace errors and only scoped Phase 65 changes plus known local artifacts.

- [ ] **Step 7: User human verification**

Present the default Agent UI/API flow, progress/SSE behavior, citations/refusals, resume/cancel behavior, current-quality report, four gate decisions, and remaining limitations. Record the user's explicit PASS/FAIL without inferring it.

- [ ] **Step 8: Stop before Git operations**

Do not stage, commit, tag, push, open a PR, or merge until the user explicitly authorizes each requested Git action after verification. When authorized, use the project constitution and the Superpowers finishing-development-branch skill to select the integration path.
