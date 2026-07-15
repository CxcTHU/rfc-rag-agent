# Phase 65A Trusted Agent Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manifest-bound Agent evaluation gate that blocks stale or incomparable evidence and freezes the current Runtime baseline before modularization.

**Architecture:** Pure manifest and metric modules sit beneath a Phase 65 execution harness. The harness reuses the existing safe SSE case executor but writes new baseline/candidate rows, multi-dimension blind-judge summaries, and independent contract/quality/runtime/absolute-latency decisions. Existing Stage 30 pages consume an evidence-status projection so a historical score cannot be rendered as current release proof.

**Tech Stack:** Python 3.11+, dataclasses, argparse, CSV/JSON, hashlib, pytest, existing FastAPI SSE evaluator and chat-model adapters.

## Global Constraints

- Establish and fingerprint the current-code baseline before any Runtime extraction.
- Reuse `data/evaluation/phase64_latency_cases.csv` as the frozen 30-case public set; do not edit its query text during Phase 65.
- Primary cold A/B is 30 cases × 3 runs × 2 variants = 180 requests with deterministic alternating order.
- Reviewer holdout contains at least 12 cases and is excluded from tuning, latency percentiles, and the primary bootstrap confidence interval.
- Blind-judge normalized completion, accuracy, citation support, and overall-quality B-minus-A paired bootstrap 95% CI lower bounds must each be at least `-0.05`.
- Candidate TTFT P95 and final P95 must be no more than 5% above baseline; successful-task token/cost must be no more than 5% above baseline.
- Phase 64 absolute targets remain independent: TTFT P50 ≤ 8 s, TTFT P95 ≤ 15 s, final P95 ≤ 30 s.
- Persist only safe IDs, queries, categories, hashes, counts, booleans, timings, scores, provider/model labels, and sanitized error categories.
- Never persist answer text, full evidence, judge prompts/reasons, provider payloads, hidden reasoning, credentials, auth headers, or private logs.
- Do not add a dependency; use the Python standard library and existing packages.
- Follow TDD: observe each focused test fail before implementation, then pass.
- Project constitution overrides the skill's default commit cadence: every task stops at a clean review boundary; do not run `git add`, `git commit`, tag, push, or PR commands without explicit user authorization after human verification.

---

### Task 1: Safe Run Manifest And Worktree Fingerprint

**Files:**
- Create: `scripts/phase65_gate_manifest.py`
- Create: `tests/test_phase65_gate_manifest.py`

**Interfaces:**
- Produces: `GitWorktreeIdentity`, `AgentGateManifest`, `sha256_file(path)`, `read_git_worktree_identity(root, scoped_paths)`, `write_manifest(path, manifest)`, and `load_manifest(path)`.
- Consumed by: Tasks 2–6 and Phase 65C.

- [ ] **Step 1: Write failing safe-serialization tests**

```python
def test_manifest_serialization_contains_fingerprints_not_secrets(tmp_path):
    manifest = AgentGateManifest(
        schema_version="phase65-agent-gate-v1",
        run_id="run-1",
        variant="baseline",
        status="complete",
        base_commit="a" * 40,
        tracked_patch_sha256="b" * 64,
        scoped_paths=("app/services/agent/tool_calling_service.py",),
        evaluator_sha256="c" * 64,
        case_set_sha256="d" * 64,
        prompt_sha256="e" * 64,
        tool_schema_sha256="f" * 64,
        corpus_fingerprint="corpus",
        index_fingerprint="index",
        provider_models=("zhipu/rerank", "deepseek/deepseek-v4-flash"),
        cache_policy="cold",
        environment_class="local-production-topology",
        expected_rows=90,
        completed_rows=90,
        started_at="2026-07-14T00:00:00+00:00",
        completed_at="2026-07-14T01:00:00+00:00",
        sanitized_errors=(),
    )
    path = tmp_path / "manifest.json"
    write_manifest(path, manifest)
    payload = path.read_text(encoding="utf-8")
    assert '"completed_rows": 90' in payload
    assert "api_key" not in payload.casefold()
    assert "authorization" not in payload.casefold()
```

- [ ] **Step 2: Run the focused test and confirm the missing module failure**

Run: `python -m pytest tests/test_phase65_gate_manifest.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'scripts.phase65_gate_manifest'`.

- [ ] **Step 3: Implement immutable manifest types and JSON round-trip**

```python
Variant = Literal["baseline", "candidate"]
RunStatus = Literal["started", "complete", "failed"]

@dataclass(frozen=True)
class GitWorktreeIdentity:
    base_commit: str
    dirty: bool
    tracked_patch_sha256: str
    scoped_paths: tuple[str, ...]

@dataclass(frozen=True)
class AgentGateManifest:
    schema_version: str
    run_id: str
    variant: Variant
    status: RunStatus
    base_commit: str
    tracked_patch_sha256: str
    scoped_paths: tuple[str, ...]
    evaluator_sha256: str
    case_set_sha256: str
    prompt_sha256: str
    tool_schema_sha256: str
    corpus_fingerprint: str
    index_fingerprint: str
    provider_models: tuple[str, ...]
    cache_policy: str
    environment_class: str
    expected_rows: int
    completed_rows: int
    started_at: str
    completed_at: str
    sanitized_errors: tuple[str, ...] = ()

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)
```

`read_git_worktree_identity()` must call `git rev-parse HEAD`, hash `git diff --binary -- <scoped paths>`, normalize scoped paths to repository-relative POSIX strings, and reject paths outside the repository. `write_manifest()` writes sorted UTF-8 JSON; `load_manifest()` rejects unknown schema/status/variant and negative row counts.

- [ ] **Step 4: Add fingerprint determinism and scope-escape tests**

```python
def test_scoped_patch_fingerprint_is_deterministic(repo_copy):
    first = read_git_worktree_identity(repo_copy, ["app/services/agent/runtime.py"])
    second = read_git_worktree_identity(repo_copy, ["app/services/agent/runtime.py"])
    assert first == second

def test_scoped_patch_rejects_parent_escape(tmp_path):
    with pytest.raises(ValueError, match="outside repository"):
        read_git_worktree_identity(ROOT, [tmp_path / "secret.txt"])
```

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_phase65_gate_manifest.py -q`

Expected: all tests in the file PASS.

- [ ] **Step 6: Stop at the constitutional review boundary**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only Phase 65 scoped files and pre-existing local artifacts are listed. Do not stage or commit.

### Task 2: Comparable Manifests And Independent Release Decisions

**Files:**
- Create: `scripts/phase65_agent_gate.py`
- Create: `tests/test_phase65_agent_gate.py`
- Create: `scripts/judge_phase65_agent_gate.py`
- Create: `tests/test_judge_phase65_agent_gate.py`

**Interfaces:**
- Consumes: `AgentGateManifest` and safe evaluator rows.
- Produces: `ManifestComparison`, `GateDecision`, `compare_manifests()`, `build_phase65_gate_decision()`, `paired_bootstrap_lower_bound()`, and `build_safe_judge_row()`.

- [ ] **Step 1: Write failing tests for stale, mismatch, and four-way decisions**

```python
def test_manifest_mismatch_blocks_every_release_decision():
    comparison = compare_manifests(baseline_manifest(), candidate_manifest(corpus_fingerprint="other"))
    assert comparison.comparable is False
    assert comparison.violations == ("corpus_fingerprint_mismatch",)

def test_relative_pass_does_not_claim_absolute_latency_closure():
    decision = build_phase65_gate_decision(
        paired_rows=passing_rows(candidate_ttft_p95=18_000.0),
        manifest_comparison=passing_comparison(),
        judge_summary=passing_judge_summary(),
        holdout_summary=passing_holdout_summary(),
    )
    assert decision.runtime_non_regression_gate == "pass"
    assert decision.phase64_latency_closure_gate == "fail"
    assert decision.phase65_acceptance == "pass"
```

- [ ] **Step 2: Confirm the tests fail because the gate module is absent**

Run: `python -m pytest tests/test_phase65_agent_gate.py tests/test_judge_phase65_agent_gate.py -q`

Expected: FAIL during collection for missing Phase 65 modules.

- [ ] **Step 3: Implement typed decisions and manifest comparison**

```python
GateStatus = Literal["pass", "fail", "blocked"]

@dataclass(frozen=True)
class ManifestComparison:
    comparable: bool
    violations: tuple[str, ...]

@dataclass(frozen=True)
class GateDecision:
    contract_gate: GateStatus
    quality_gate: GateStatus
    runtime_non_regression_gate: GateStatus
    phase64_latency_closure_gate: GateStatus
    phase65_acceptance: GateStatus
    reasons: tuple[str, ...]
    metrics: dict[str, float | int | bool | None]
```

`compare_manifests()` allows only `variant`, `run_id`, timestamps, worktree identity, and completed-row fields to differ. It blocks missing fingerprints, incomplete manifests, non-cold cache policy, identical endpoint identity hashes, or provider/corpus/index/prompt/tool-schema mismatches.

- [ ] **Step 4: Implement multi-dimension safe blind judging**

```python
JUDGE_DIMENSIONS = ("completion", "accuracy", "citation_support", "overall_quality")
JUDGE_OUTPUT_FIELDS = (
    "case_id", "run", "category", "winner", "mapping_hash",
    "completion_delta", "accuracy_delta", "citation_support_delta",
    "overall_quality_delta", "judge_latency_ms", "judge_provider",
    "judge_model", "sanitized_reason",
)

def summarize_judge_rows(rows, *, seed=650013, samples=10_000):
    return {
        f"{dimension}_lower_bound": paired_bootstrap_lower_bound(
            [float(row[f"{dimension}_delta"]) for row in rows],
            seed=seed,
            samples=samples,
        )
        for dimension in JUDGE_DIMENSIONS
    }
```

The provider-facing prompt exists only in memory. `build_safe_judge_row()` must map anonymous A/B labels back to baseline/candidate, clamp normalized deltas to `[-1, 1]`, hash the mapping, and replace free-form reasoning with a categorical receipt flag.

- [ ] **Step 5: Implement metric thresholds exactly**

`build_phase65_gate_decision()` must require deterministic candidate rates ≥ baseline, all four judge lower bounds ≥ `-0.05`, candidate TTFT/final P95 ratios ≤ `1.05`, successful-task average token/cost ratios ≤ `1.05`, zero unclassified errors, zero repeated completed tools, a clean holdout, and complete comparable manifests. It separately evaluates `8_000`, `15_000`, and `30_000` millisecond absolute thresholds.

- [ ] **Step 6: Run focused gate and judge tests**

Run: `python -m pytest tests/test_phase65_agent_gate.py tests/test_judge_phase65_agent_gate.py -q`

Expected: all tests PASS, including threshold boundary values exactly at `-0.05` and `1.05`.

- [ ] **Step 7: Review boundary**

Run: `git diff --check && git status --short`

Expected: clean whitespace result. Do not stage or commit.

### Task 3: Phase 65 Baseline/Candidate Execution Harness

**Files:**
- Create: `scripts/evaluate_phase65_agent_gate.py`
- Create: `tests/test_evaluate_phase65_agent_gate.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `execute_case()` from `scripts/evaluate_phase63_e2e.py`, Phase 65 manifests, gate engine, and judge module.
- Produces: `PHASE65_OUTPUT_FIELDS`, `deterministic_pair_order()`, `run_variant_case()`, `run_gate()`, and CLI modes `baseline`, `paired`, `holdout`, `summarize`.

- [ ] **Step 1: Write failing harness safety and ordering tests**

```python
def test_output_fields_exclude_sensitive_payloads():
    forbidden = {"answer", "content", "snippet", "prompt", "raw_response", "reasoning_content", "authorization"}
    assert forbidden.isdisjoint(PHASE65_OUTPUT_FIELDS)

def test_primary_order_has_180_rows_and_alternates_variants():
    schedule = build_schedule(case_ids=[f"c-{i}" for i in range(30)], runs=3, seed=650013)
    assert len(schedule) == 180
    assert {item.variant for item in schedule} == {"baseline", "candidate"}
```

- [ ] **Step 2: Confirm missing-harness failure**

Run: `python -m pytest tests/test_evaluate_phase65_agent_gate.py -q`

Expected: FAIL during collection for missing `scripts.evaluate_phase65_agent_gate`.

- [ ] **Step 3: Implement CLI and safe row projection**

```python
PHASE65_OUTPUT_FIELDS = (
    "variant", "run", "case_id", "category", "ok", "error_category",
    "http_status", "expected_tool", "observed_tool_names",
    "expected_graph_requirement", "observed_graph_requirement",
    "citation_count", "selected_count", "live_selected_count",
    "counts_match", "conversation_persisted", "refused",
    "first_token_ms", "elapsed_ms", "input_tokens", "output_tokens",
    "estimated_cost", "runtime_stop_reason", "completed_tool_replay_count",
    "manifest_run_id", "snapshot_fingerprint",
)
```

The parser must accept `--mode`, `--baseline-base-url`, `--candidate-base-url`,
`--cases`, `--holdout-cases`, `--runs`, `--seed`, `--manifest-out`,
`--baseline-manifest-out`, `--baseline-manifest`, `--candidate-manifest`,
`--out`, `--results`, `--summary-out`, `--judge-out`, `--token-env`,
`--execute`, `--execute-blind-judge`, and `--enforce-gates`. Tokens are read
from the named environment variable and never written. In paired execution,
the two answers exist only as local variables until `judge_blind_pair()` returns;
the writer receives only `PHASE65_OUTPUT_FIELDS` and `JUDGE_OUTPUT_FIELDS`.

- [ ] **Step 4: Enforce row counts and endpoint separation**

```python
def validate_schedule(mode: str, rows: list[dict[str, object]], case_count: int, runs: int) -> None:
    expected = case_count * runs * (2 if mode == "paired" else 1)
    if len(rows) != expected:
        raise ValueError(f"incomplete_rows:{len(rows)}:{expected}")
```

Reject identical baseline/candidate URLs after normalization and endpoint identity hashes returned by the retrieval-contract endpoint. `--holdout-cases` is required only in holdout mode and must contain at least 12 unique case IDs.

- [ ] **Step 5: Ignore reviewer-controlled local holdout inputs**

Add exactly these patterns after the runtime-data section:

```gitignore
# Phase 65 reviewer-controlled holdout inputs are local and never committed.
data/evaluation/phase65_private_holdout*.csv
data/evaluation/phase65_private_holdout*.yaml
```

- [ ] **Step 6: Run harness tests and dry-run schedule**

Run: `python -m pytest tests/test_evaluate_phase65_agent_gate.py -q`

Expected: all tests PASS.

Run: `python scripts/evaluate_phase65_agent_gate.py --mode paired --baseline-base-url http://127.0.0.1:8001 --candidate-base-url http://127.0.0.1:8002 --cases data/evaluation/phase64_latency_cases.csv --runs 3 --out output/phase65-dry-run.csv --summary-out output/phase65-dry-run-summary.json`

Expected: `execute=false`, `cases=30`, `expected_rows=180`, no network request, and no persisted answer/evidence fields.

- [ ] **Step 7: Review boundary**

Run: `git diff --check && git status --short`

Expected: no whitespace errors. Do not stage or commit.

### Task 4: Stale-Aware Stage 30 And Quality Page

**Files:**
- Modify: `scripts/collect_stage30_engineering_health.py`
- Modify: `scripts/score_stage30_quality.py`
- Modify: `scripts/build_stage30_quality_report.py`
- Modify: `tests/test_stage30_engineering_health.py`
- Modify: `tests/test_stage30_scoring.py`
- Modify: `tests/test_build_stage30_quality_report.py`
- Modify: `app/frontend/quality_report.html`

**Interfaces:**
- Consumes: an `AgentGateManifest` path supplied by CLI.
- Produces: `evidence_status` (`current`, `stale`, `blocked`), `evidence_reasons`, and a report banner that never presents stale `91.52 / A / pass` as current release readiness.

- [ ] **Step 1: Add failing stale-report tests**

```python
def test_old_engineering_health_cannot_render_current_pass(tmp_path):
    health = health_payload(generated_at="2026-06-13T00:00:00+00:00", full_tests_status="571 passed")
    status = evaluate_evidence_status(health=health, manifest=current_manifest())
    assert status.status == "stale"
    assert "test_fingerprint_mismatch" in status.reasons

def test_html_labels_historical_score_when_evidence_is_stale(tmp_path):
    html = render_report(evidence_status="stale", release_decision="pass")
    assert "历史评分，不可作为当前发布门禁" in html
    assert "当前发布门禁：PASS" not in html
```

- [ ] **Step 2: Run focused tests and observe failure**

Run: `python -m pytest tests/test_stage30_engineering_health.py tests/test_stage30_scoring.py tests/test_build_stage30_quality_report.py -q`

Expected: FAIL because evidence status and manifest binding do not exist.

- [ ] **Step 3: Add manifest/test fingerprints to engineering health**

```python
health.update({
    "schema_version": "stage30-engineering-health-v2",
    "manifest_run_id": manifest.run_id,
    "base_commit": manifest.base_commit,
    "tracked_patch_sha256": manifest.tracked_patch_sha256,
    "test_suite_sha256": sha256_file(test_inventory_path),
    "full_tests_status": full_tests_status,
})
```

The collector remains read-only and still does not run pytest, rebuild embeddings, write the database, or call real APIs. It consumes test status and inventory produced by the verification command.

- [ ] **Step 4: Make scoring and report rendering fail closed**

When evidence is not `current`, `score_stage30_quality.py` writes `release_decision=blocked` while retaining the historical numeric score under `historical_overall_score`. The HTML/Markdown builders display the evidence reason and manifest run ID; they never turn `blocked` back into `pass`.

- [ ] **Step 5: Run Stage 30 focused tests**

Run: `python -m pytest tests/test_stage30_engineering_health.py tests/test_stage30_scoring.py tests/test_build_stage30_quality_report.py -q`

Expected: all tests PASS and old v1 fixtures are classified as `stale`.

- [ ] **Step 6: Review boundary**

Run: `git diff --check && git status --short`

Expected: no whitespace errors. Do not stage or commit.

### Task 5: Capture The Pre-Refactor Baseline

**Files:**
- Create after execution and safe review: `data/evaluation/phase65_baseline_manifest.json`
- Create after execution and safe review: `data/evaluation/phase65_baseline_results.csv`
- Create after execution and safe review: `data/evaluation/phase65_baseline_summary.json`
- Modify: `findings.md`
- Modify: `progress.md`
- Modify: `handoff.md`
- Modify: `obsidian-agent开发/阶段/阶段 65 - Agent 真实质量门禁与 Runtime 模块化/01-开发记录.md`

**Interfaces:**
- Consumes: completed Tasks 1–4 and the frozen current Runtime endpoint.
- Produces: an immutable safe baseline fingerprint and 90 baseline rows used as pre-refactor evidence; Phase 65C still reruns alternating A/B for the final decision.

- [ ] **Step 1: Run all 65A focused tests**

Run: `python -m pytest tests/test_phase65_gate_manifest.py tests/test_phase65_agent_gate.py tests/test_judge_phase65_agent_gate.py tests/test_evaluate_phase65_agent_gate.py tests/test_stage30_engineering_health.py tests/test_stage30_scoring.py tests/test_build_stage30_quality_report.py -q`

Expected: all focused tests PASS.

- [ ] **Step 2: Start the frozen baseline server in the execution worktree**

Run in a dedicated terminal with the already approved local environment: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001`

Expected: `/health` and `/health/retrieval-contract` return HTTP 200; the contract reports cold caches, strict pgvector, current reranker, and the frozen model configuration.

- [ ] **Step 3: Execute 90 baseline requests**

Run: `python scripts/evaluate_phase65_agent_gate.py --mode baseline --execute --baseline-base-url http://127.0.0.1:8001 --cases data/evaluation/phase64_latency_cases.csv --runs 3 --seed 650013 --token-env PHASE65_AUTH_TOKEN --manifest-out data/evaluation/phase65_baseline_manifest.json --out data/evaluation/phase65_baseline_results.csv --summary-out data/evaluation/phase65_baseline_summary.json`

Expected: `cases=30`, `rows=90`, `completed_rows=90`, `unclassified_errors=0`. Baseline mode records metrics but does not claim candidate non-regression.

- [ ] **Step 4: Run an explicit safety scan over generated artifacts**

Run: `rg -n -i "answer|snippet|raw_response|reasoning_content|authorization|api[_-]?key|bearer |password|secret" data/evaluation/phase65_baseline_manifest.json data/evaluation/phase65_baseline_results.csv data/evaluation/phase65_baseline_summary.json`

Expected: no matches except approved schema labels such as `answer_token` when represented as numeric timing field names; manually inspect every match before retaining artifacts.

- [ ] **Step 5: Record only observed values**

Update `findings.md`, `progress.md`, `handoff.md`, and the Obsidian development record with the exact manifest run ID, row counts, sanitized failure categories, and numeric metrics. Do not describe unrun candidate, judge, holdout, or absolute gates as passed.

- [ ] **Step 6: Constitutional review boundary**

Run: `git diff --check && git status -sb`

Expected: baseline artifacts and scoped Phase 65 files are visible; pre-existing `.playwright-cli/`, `output/`, screenshots, and `.superpowers/` remain excluded. Do not stage or commit.

### Task 6: 65A Verification And Handoff To 65B

**Files:**
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `handoff.md`
- Modify: `obsidian-agent开发/阶段/阶段 65 - Agent 真实质量门禁与 Runtime 模块化/02-收尾交接.md`
- Modify: `obsidian-agent开发/阶段/阶段 65 - Agent 真实质量门禁与 Runtime 模块化/03-文件地图与恢复顺序.md`

- [ ] **Step 1: Run 65A plus existing evaluator regressions**

Run: `python -m pytest tests/test_phase65_gate_manifest.py tests/test_phase65_agent_gate.py tests/test_judge_phase65_agent_gate.py tests/test_evaluate_phase65_agent_gate.py tests/test_evaluate_phase64_latency_ab.py tests/test_judge_phase64_latency_ab.py tests/test_stage30_engineering_health.py tests/test_stage30_scoring.py tests/test_build_stage30_quality_report.py -q`

Expected: all selected tests PASS.

- [ ] **Step 2: Run the full backend regression before Runtime extraction**

Run: `python -m pytest -q`

Expected: exit 0; record the exact pass/skip counts in controlled work-memory files.

- [ ] **Step 3: Rebuild current Stage 30 evidence against the baseline manifest**

Run the collector, scorer, and report builder with `--manifest data/evaluation/phase65_baseline_manifest.json` and the exact full-test result from Step 2.

Expected: the report says `current` only when every fingerprint matches; otherwise it says `blocked` with explicit reasons.

- [ ] **Step 4: Freeze the 65B starting contract**

Record the hashes of public Pydantic Agent schemas, SSE event fixture, public tool definitions, Phase 65 manifest, and baseline result file in `handoff.md`. Hashes are evidence; do not copy answers or full payloads.

- [ ] **Step 5: Stop for user review**

Run: `git diff --check && git status -sb`

Expected: no whitespace errors. Present 65A evidence to the user. 65B cannot begin until the baseline and stale-report behavior are reviewed; do not stage or commit without explicit authorization.
