from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

from scripts.evaluate_phase65_agent_gate import (
    PHASE65_OUTPUT_FIELDS,
    _build_manifest,
    _build_receipt_contract,
    _filter_cases,
    _evaluation_run_namespace,
    _load_cases,
    build_schedule,
    normalize_endpoint_url,
    project_safe_row,
    resolve_execution_token,
    run_variant_case,
    validate_holdout_cases,
    validate_schedule,
    validate_output_path,
)
from scripts.phase65_gate_manifest import load_manifest, write_manifest


def test_output_fields_exclude_sensitive_payloads() -> None:
    forbidden = {
        "answer",
        "content",
        "snippet",
        "prompt",
        "raw_response",
        "reasoning_content",
        "authorization",
        "token",
    }

    assert forbidden.isdisjoint(PHASE65_OUTPUT_FIELDS)


def test_targeted_lane_receipt_contract_can_be_unbalanced() -> None:
    cases = [
        {
            "case_id": "phase64-followup-02",
            "category": "followup_figure",
        }
    ]

    with pytest.raises(ValueError, match="invalid_judge_receipt_contract"):
        _build_receipt_contract(cases, runs=1, seed=65)

    contract = _build_receipt_contract(
        cases,
        runs=1,
        seed=65,
        require_balanced_mapping=False,
    )

    assert contract.expected_count == 1


def test_execution_token_uses_local_dotenv_when_process_environment_is_unset(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("PHASE65_AUTH_TOKEN=dotenv-test-token\n", encoding="utf-8")

    token = resolve_execution_token(
        "PHASE65_AUTH_TOKEN",
        environ={},
        dotenv_path=dotenv_path,
    )

    assert token == "dotenv-test-token"


def test_execution_token_prefers_process_environment_over_local_dotenv(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("PHASE65_AUTH_TOKEN=dotenv-test-token\n", encoding="utf-8")

    token = resolve_execution_token(
        "PHASE65_AUTH_TOKEN",
        environ={"PHASE65_AUTH_TOKEN": "process-test-token"},
        dotenv_path=dotenv_path,
    )

    assert token == "process-test-token"


def test_main_reports_safe_value_error_detail(monkeypatch, capsys) -> None:
    import json
    import scripts.evaluate_phase65_agent_gate as evaluator

    def raise_value_error(_args: object) -> tuple[dict[str, object], int]:
        raise ValueError("blind_judge_invalid_json")

    monkeypatch.setattr(evaluator, "_run_execution", raise_value_error)
    monkeypatch.setattr(sys, "argv", ["evaluate_phase65_agent_gate.py", "--mode", "paired"])

    assert evaluator.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "error": "phase65_gate_blocked",
        "reason": "ValueError",
        "reason_detail": "blind_judge_invalid_json",
    }


def test_blind_judge_payload_parser_accepts_fenced_json() -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    payload = evaluator._parse_blind_judge_payload(
        """```json
{"winner":"tie","completion":0,"accuracy":0,"citation_support":0,"overall_quality":0,"reason":"similar"}
```"""
    )

    assert payload["winner"] == "tie"
    assert payload["overall_quality"] == 0


def test_blind_judge_payload_parser_flattens_nested_deltas() -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    payload = evaluator._parse_blind_judge_payload(
        '{"winner":"A","deltas":{"completion":0.1,"accuracy":0.2,"citation_support":0.3,"overall_quality":0.4},"reason":"A is stronger"}'
    )

    assert payload["winner"] == "A"
    assert payload["completion"] == 0.1
    assert payload["overall_quality"] == 0.4


def test_blind_judge_text_is_bounded_for_provider_stability() -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    text = "a" * 6000

    bounded = evaluator._bounded_blind_judge_text(text, max_chars=1000)

    assert len(bounded) <= 1000
    assert "truncated_for_judge_stability" in bounded
    assert bounded.startswith("a" * 400)
    assert bounded.endswith("a" * 400)


def test_safe_blind_judge_pair_converts_provider_runtime_error() -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    class FailingJudge:
        provider_name = "judge-provider"
        model_name = "judge-model"

        def generate(self, _messages: object) -> object:
            raise RuntimeError("provider returned empty content")

    cases = _load_cases(Path("data/evaluation/phase64_latency_cases.csv"), limit=2)
    contract = _build_receipt_contract(cases, runs=1, seed=65)

    row, category = evaluator._safe_judge_blind_pair(
        FailingJudge(),
        case=cases[0],
        run=1,
        baseline_answer="baseline cites [1]",
        candidate_answer="candidate cites [1]",
        seed=65,
        receipt_contract=contract,
    )

    assert row is None
    assert category == "blind_judge_provider_failed"


def test_safe_blind_judge_pair_retries_invalid_json_once() -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    class JudgeResult:
        def __init__(self, answer: str) -> None:
            self.answer = answer

    class FlakyJudge:
        provider_name = "judge-provider"
        model_name = "judge-model"

        def __init__(self) -> None:
            self.calls = 0

        def generate(self, _messages: object) -> object:
            self.calls += 1
            if self.calls == 1:
                return JudgeResult("not-json")
            return JudgeResult(
                '{"winner":"tie","completion":0,"accuracy":0,'
                '"citation_support":0,"overall_quality":0,"reason":"similar"}'
            )

    cases = _load_cases(Path("data/evaluation/phase64_latency_cases.csv"), limit=2)
    contract = _build_receipt_contract(cases, runs=1, seed=65)
    provider = FlakyJudge()

    row, category = evaluator._safe_judge_blind_pair(
        provider,
        case=cases[0],
        run=1,
        baseline_answer="baseline cites [1]",
        candidate_answer="candidate cites [1]",
        seed=65,
        receipt_contract=contract,
    )

    assert category is None
    assert row is not None
    assert provider.calls == 2


def test_load_cases_limit_keeps_the_frozen_case_order() -> None:
    cases = _load_cases(Path("data/evaluation/phase64_latency_cases.csv"), limit=2)

    assert len(cases) == 2
    assert [case["case_id"] for case in cases] == [
        "e2e-text-01",
        "e2e-text-02",
    ]


def test_load_cases_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="limit_must_be_positive"):
        _load_cases(Path("data/evaluation/phase64_latency_cases.csv"), limit=0)


def test_filter_cases_keeps_requested_case_order() -> None:
    cases = [
        {"case_id": "case-1", "category": "ordinary_text"},
        {"case_id": "case-2", "category": "ordinary_text"},
        {"case_id": "case-3", "category": "ordinary_text"},
    ]

    selected = _filter_cases(cases, ("case-3", "case-1"))

    assert [case["case_id"] for case in selected] == ["case-3", "case-1"]


def test_filter_cases_rejects_missing_case_id() -> None:
    cases = [{"case_id": "case-1", "category": "ordinary_text"}]

    with pytest.raises(ValueError, match="case_id_not_found"):
        _filter_cases(cases, ("case-2",))


def test_dry_run_manifest_is_loadable_and_explicitly_incomplete(tmp_path: Path, monkeypatch) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    identity = evaluator.read_git_worktree_identity
    monkeypatch.setattr(evaluator, "read_git_worktree_identity", lambda *_args: identity(Path(__file__).resolve().parents[1], ("scripts/evaluate_phase65_agent_gate.py",)))
    monkeypatch.setattr(evaluator, "canonical_phase65_scope", lambda _root: ("scripts/evaluate_phase65_agent_gate.py",))
    contract = {"phase65_model_inventory": [{"path": "chat", "identity_sha256": "a" * 64, "configured": True, "usage_receipt_verified": True}], "index_fingerprint_sha256": "b" * 64}
    cases = [{"case_id": f"case-{index}", "category": "ordinary_text"} for index in range(30)]
    manifest = _build_manifest(variant="baseline", expected_rows=30, completed_rows=0, cases=cases, receipt_contract=_build_receipt_contract(cases, runs=1, seed=1), endpoint_identity_sha256="c" * 64, contract=contract, environment_class="dry_run")
    path = tmp_path / "dry-run.json"
    write_manifest(path, manifest)

    loaded = load_manifest(path)

    assert loaded.status == "incomplete"
    assert loaded.cache_policy == "dry_run"


def test_dry_run_cli_returns_zero_and_writes_loadable_blocked_manifest(tmp_path: Path, monkeypatch) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    written: list[Path] = []
    original_write = evaluator.write_manifest

    def capture_manifest(_path: Path, manifest) -> None:
        destination = tmp_path / "dry-run-manifest.json"
        original_write(destination, manifest)
        written.append(destination)

    monkeypatch.setattr(evaluator, "write_manifest", capture_manifest)
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py", "--mode", "baseline", "--baseline-base-url", "http://127.0.0.1:8001",
        "--runs", "1", "--limit", "2", "--manifest-out", "output/phase65/dry-run-manifest.json",
    ])

    assert evaluator.main() == 0
    loaded = load_manifest(written[0])
    assert loaded.status == "incomplete"
    assert loaded.cache_policy == "dry_run"
    assert loaded.expected_rows == 2


def test_candidate_dry_run_cli_writes_candidate_manifest(tmp_path: Path, monkeypatch) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    written: list[Path] = []
    original_write = evaluator.write_manifest

    def capture_manifest(_path: Path, manifest) -> None:
        destination = tmp_path / "candidate-dry-run-manifest.json"
        original_write(destination, manifest)
        written.append(destination)

    monkeypatch.setattr(evaluator, "write_manifest", capture_manifest)
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "candidate",
        "--candidate-base-url",
        "http://127.0.0.1:8011",
        "--runs",
        "1",
        "--limit",
        "2",
        "--manifest-out",
        "output/phase65/candidate-dry-run-manifest.json",
    ])

    assert evaluator.main() == 0
    loaded = load_manifest(written[0])
    assert loaded.variant == "candidate"
    assert loaded.status == "incomplete"
    assert loaded.expected_rows == 2


def test_paired_dry_run_summary_includes_execution_preflight(monkeypatch) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    summaries: list[dict[str, object]] = []
    monkeypatch.setattr(evaluator, "_write_json", lambda _path, payload: summaries.append(payload))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "paired",
        "--baseline-base-url",
        "http://127.0.0.1:8001",
        "--candidate-base-url",
        "http://127.0.0.1:8002",
        "--runs",
        "1",
        "--limit",
        "2",
        "--summary-out",
        "output/phase65/paired-dry-run-summary.json",
    ])

    assert evaluator.main() == 0

    preflight = summaries[-1]["paired_execution_preflight"]
    assert preflight["schema_version"] == "phase65-paired-preflight-v1"
    assert preflight["gate"] == "blocked"
    assert preflight["ready_to_execute"] is False
    assert "paid_execution_not_authorized" in preflight["failed_required"]


def test_holdout_mode_requires_both_baseline_and_candidate_endpoints(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    holdout_cases = tmp_path / "holdout.csv"
    with holdout_cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category", "query"))
        writer.writeheader()
        writer.writerows(
            {
                "case_id": f"holdout-{index}",
                "category": "ordinary_text",
                "query": f"holdout query {index}",
            }
            for index in range(12)
        )
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "holdout",
        "--candidate-base-url",
        "http://127.0.0.1:8011",
        "--holdout-cases",
        str(holdout_cases),
    ])

    assert evaluator.main() == 2


def test_holdout_dry_run_schedules_baseline_and_candidate_lanes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    holdout_cases = tmp_path / "holdout.csv"
    with holdout_cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category", "query"))
        writer.writeheader()
        writer.writerows(
            {
                "case_id": f"holdout-{index}",
                "category": "ordinary_text",
                "query": f"holdout query {index}",
            }
            for index in range(12)
        )
    written_rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    monkeypatch.setattr(
        evaluator,
        "_write_csv",
        lambda _path, _fields, rows: written_rows.extend(rows),
    )
    monkeypatch.setattr(evaluator, "_write_json", lambda _path, payload: summaries.append(payload))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "holdout",
        "--baseline-base-url",
        "http://127.0.0.1:8001",
        "--candidate-base-url",
        "http://127.0.0.1:8011",
        "--holdout-cases",
        str(holdout_cases),
        "--runs",
        "1",
        "--out",
        "output/phase65/holdout-dry-run.csv",
        "--summary-out",
        "output/phase65/holdout-dry-run.json",
    ])

    assert evaluator.main() == 0
    assert len(written_rows) == 24
    assert {row["variant"] for row in written_rows} == {"baseline", "candidate"}
    assert summaries[-1]["expected_rows"] == 24
    assert summaries[-1]["holdout_summary"]["holdout_case_count"] == 12


def test_holdout_default_runs_once_per_ab_lane(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    holdout_cases = tmp_path / "holdout.csv"
    with holdout_cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category", "query"))
        writer.writeheader()
        writer.writerows(
            {
                "case_id": f"holdout-{index}",
                "category": "ordinary_text",
                "query": f"holdout query {index}",
            }
            for index in range(12)
        )
    written_rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    monkeypatch.setattr(
        evaluator,
        "_write_csv",
        lambda _path, _fields, rows: written_rows.extend(rows),
    )
    monkeypatch.setattr(evaluator, "_write_json", lambda _path, payload: summaries.append(payload))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "holdout",
        "--baseline-base-url",
        "http://127.0.0.1:8001",
        "--candidate-base-url",
        "http://127.0.0.1:8011",
        "--holdout-cases",
        str(holdout_cases),
        "--out",
        "output/phase65/holdout-default-runs.csv",
        "--summary-out",
        "output/phase65/holdout-default-runs.json",
    ])

    assert evaluator.main() == 0
    assert len(written_rows) == 24
    assert summaries[-1]["expected_rows"] == 24


def test_holdout_cli_rejects_overlap_with_cases_argument(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    public_cases = tmp_path / "public.csv"
    holdout_cases = tmp_path / "holdout.csv"
    with public_cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category"))
        writer.writeheader()
        writer.writerow({"case_id": "e2e-text-01", "category": "ordinary_text"})
    with holdout_cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category", "query"))
        writer.writeheader()
        writer.writerows(
            {
                "case_id": "e2e-text-01" if index == 0 else f"holdout-{index}",
                "category": "ordinary_text",
                "query": f"holdout query {index}",
            }
            for index in range(12)
        )
    monkeypatch.setattr(evaluator, "_write_csv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(evaluator, "_write_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "holdout",
        "--baseline-base-url",
        "http://127.0.0.1:8001",
        "--candidate-base-url",
        "http://127.0.0.1:8011",
        "--cases",
        str(public_cases),
        "--holdout-cases",
        str(holdout_cases),
    ])

    assert evaluator.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["reason_detail"] == "holdout_overlaps_public_cases"


def test_holdout_execute_blind_judge_writes_safe_judge_receipts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator
    from scripts.judge_phase65_agent_gate import JUDGE_DIMENSIONS

    holdout_cases = tmp_path / "holdout.csv"
    with holdout_cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category", "query"))
        writer.writeheader()
        writer.writerows(
            {
                "case_id": f"holdout-{index}",
                "category": "ordinary_text",
                "query": f"holdout query {index}",
            }
            for index in range(12)
        )
    rows_by_path: dict[str, list[dict[str, object]]] = {}
    summaries: list[dict[str, object]] = []

    def fake_fetch_contract(base_url: str, *, token: str, timeout_seconds: float) -> dict[str, object]:
        return {
            "endpoint_identity_sha256": hashlib.sha256(base_url.encode("utf-8")).hexdigest(),
            "index_fingerprint_sha256": "b" * 64,
            "cold_run_receipts_supported": True,
            "phase65_model_inventory": [
                {
                    "path": "chat",
                    "identity_sha256": "a" * 64,
                    "configured": True,
                    "usage_receipt_verified": True,
                }
            ],
        }

    def fake_run_variant_case(case, *, variant, run, manifest_run_id, snapshot_fingerprint, **_kwargs):
        row = {
            field: ""
            for field in PHASE65_OUTPUT_FIELDS
        }
        row.update(
            {
                "variant": variant,
                "run": run,
                "case_id": case["case_id"],
                "category": case["category"],
                "ok": True,
                "error_category": "",
                "expected_tool": "hybrid_search_knowledge",
                "observed_tool_names": "hybrid_search_knowledge|final_answer",
                "expected_graph_requirement": "disabled",
                "observed_graph_requirement": "disabled",
                "citation_count": 1,
                "selected_count": 1,
                "live_selected_count": 1,
                "counts_match": True,
                "conversation_persisted": True,
                "refused": False,
                "first_token_ms": 100.0,
                "elapsed_ms": 200.0,
                "input_tokens": 10,
                "output_tokens": 5,
                "provider_usage_request_count": 1,
                "provider_usage_receipt_count": 0,
                "provider_usage_receipt_complete": False,
                "cold_cache_receipt_status": "valid",
                "runtime_stop_reason": "completed",
                "manifest_run_id": manifest_run_id,
                "snapshot_fingerprint": snapshot_fingerprint,
            }
        )
        return row, f"{variant} cites [1]"

    def fake_safe_judge_pair(_provider, *, case, run, receipt_contract, **_kwargs):
        case_hash = hashlib.sha256(case["case_id"].encode("utf-8")).hexdigest()
        row = {
            "case_id": case_hash,
            "run": run,
            "category": "ordinary_text",
            "winner": "tie",
            "mapping_hash": receipt_contract.expected_mapping_hash(
                case_hash, run, "ordinary_text"
            ),
            "judge_latency_ms": 1.0,
            "judge_provider": "fake-judge",
            "judge_model": "fake-judge-v1",
            "sanitized_reason": "judge_rationale_unavailable",
        }
        row.update({f"{dimension}_delta": 0.0 for dimension in JUDGE_DIMENSIONS})
        return row, None

    monkeypatch.setenv("PHASE65_EVAL_TOKEN", "test-token")
    monkeypatch.setattr(evaluator, "_fetch_contract", fake_fetch_contract)
    monkeypatch.setattr(evaluator, "run_variant_case", fake_run_variant_case)
    monkeypatch.setattr(evaluator, "_configured_blind_judge_provider", lambda: object())
    monkeypatch.setattr(evaluator, "_safe_judge_blind_pair", fake_safe_judge_pair)
    monkeypatch.setattr(
        evaluator,
        "_write_csv",
        lambda path, _fields, rows: rows_by_path.setdefault(str(path), list(rows)),
    )
    monkeypatch.setattr(evaluator, "_write_json", lambda _path, payload: summaries.append(payload))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "holdout",
        "--execute",
        "--execute-blind-judge",
        "--baseline-base-url",
        "http://127.0.0.1:8001",
        "--candidate-base-url",
        "http://127.0.0.1:8011",
        "--holdout-cases",
        str(holdout_cases),
        "--out",
        "output/phase65/holdout-results.csv",
        "--judge-out",
        "output/phase65/holdout-judge.csv",
        "--summary-out",
        "output/phase65/holdout-summary.json",
    ])

    assert evaluator.main() == 0
    judge_rows = next(
        rows
        for path, rows in rows_by_path.items()
        if Path(path).as_posix().endswith("output/phase65/holdout-judge.csv")
    )
    assert len(judge_rows) == 12
    holdout_summary = summaries[-1]["holdout_summary"]
    assert holdout_summary["schema_version"] == "phase65-holdout-summary-v1"
    assert holdout_summary["clean"] is True
    assert holdout_summary["execution_mode"] == "real_api"
    assert holdout_summary["executed_ab_row_count"] == 24
    assert holdout_summary["baseline_ab_row_count"] == 12
    assert holdout_summary["candidate_ab_row_count"] == 12
    assert (
        holdout_summary["baseline_ab_case_set_sha256"]
        == holdout_summary["holdout_case_set_sha256"]
    )
    assert (
        holdout_summary["candidate_ab_case_set_sha256"]
        == holdout_summary["holdout_case_set_sha256"]
    )
    assert holdout_summary["public_overlap_exclusion_proven"] is True
    assert isinstance(holdout_summary["excluded_case_set_sha256"], str)
    assert holdout_summary["judge_summary"]["paired_count"] == 12


def test_paired_preflight_only_fetches_contracts_without_executing_cases(monkeypatch) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    summaries: list[dict[str, object]] = []
    fetched: list[str] = []

    def fetch_contract(base_url: str, *, token: str, timeout_seconds: float) -> dict[str, object]:
        fetched.append(base_url)
        return {
            "endpoint_identity_sha256": hashlib.sha256(base_url.encode("utf-8")).hexdigest(),
            "index_fingerprint_sha256": "b" * 64,
            "cold_run_receipts_supported": True,
            "phase65_model_inventory": [
                {
                    "path": "chat",
                    "identity_sha256": "a" * 64,
                    "configured": True,
                    "usage_receipt_verified": True,
                }
            ],
        }

    def execute_case_should_not_run(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("preflight-only must not execute cases")

    monkeypatch.setattr(evaluator, "_fetch_contract", fetch_contract)
    monkeypatch.setattr(evaluator, "execute_case", execute_case_should_not_run)
    monkeypatch.setattr(evaluator, "_write_json", lambda _path, payload: summaries.append(payload))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "paired",
        "--baseline-base-url",
        "http://127.0.0.1:8001",
        "--candidate-base-url",
        "http://127.0.0.1:8002",
        "--runs",
        "1",
        "--limit",
        "2",
        "--contract-gate-status",
        "pass",
        "--topology-gate-status",
        "pass",
        "--fault-gate-status",
        "pass",
        "--preflight-only",
        "--summary-out",
        "output/phase65/paired-readiness.json",
    ])

    assert evaluator.main() == 1
    assert fetched == ["http://127.0.0.1:8001", "http://127.0.0.1:8002"]
    summary = summaries[-1]
    assert summary["mode"] == "paired-preflight"
    assert summary["execute"] is False
    assert summary["completed_rows"] == 0
    assert summary["endpoint_readiness"]["gate"] == "pass"
    assert summary["paired_execution_preflight"]["gate"] == "blocked"
    assert "paid_execution_not_authorized" in summary["paired_execution_preflight"]["failed_required"]


def test_paired_preflight_only_reports_identical_endpoint_identity(monkeypatch) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    summaries: list[dict[str, object]] = []

    def fetch_contract(base_url: str, *, token: str, timeout_seconds: float) -> dict[str, object]:
        return {
            "endpoint_identity_sha256": "c" * 64,
            "index_fingerprint_sha256": "b" * 64,
            "cold_run_receipts_supported": True,
            "phase65_model_inventory": [
                {
                    "path": "chat",
                    "identity_sha256": "a" * 64,
                    "configured": True,
                    "usage_receipt_verified": True,
                }
            ],
        }

    monkeypatch.setattr(evaluator, "_fetch_contract", fetch_contract)
    monkeypatch.setattr(evaluator, "_write_json", lambda _path, payload: summaries.append(payload))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "paired",
        "--baseline-base-url",
        "http://127.0.0.1:8001",
        "--candidate-base-url",
        "http://127.0.0.1:8002",
        "--runs",
        "1",
        "--limit",
        "2",
        "--contract-gate-status",
        "pass",
        "--topology-gate-status",
        "pass",
        "--fault-gate-status",
        "pass",
        "--preflight-only",
        "--summary-out",
        "output/phase65/paired-readiness.json",
    ])

    assert evaluator.main() == 1
    readiness = summaries[-1]["endpoint_readiness"]
    assert readiness["gate"] == "blocked"
    assert readiness["components"]["endpoint_identity_distinct"] == "blocked"
    assert "endpoint_identity_not_distinct" in readiness["failed_required"]


def test_paired_preflight_only_can_auto_auth_each_endpoint(monkeypatch) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    token_requests: list[str] = []
    contract_tokens: list[str] = []
    summaries: list[dict[str, object]] = []

    def auto_auth(base_url: str, *, timeout_seconds: float) -> str:
        token_requests.append(base_url)
        return f"token-for-{base_url.rsplit(':', 1)[-1]}"

    def fetch_contract(base_url: str, *, token: str, timeout_seconds: float) -> dict[str, object]:
        contract_tokens.append(token)
        return {
            "endpoint_identity_sha256": hashlib.sha256(f"{base_url}:{token}".encode("utf-8")).hexdigest(),
            "index_fingerprint_sha256": "b" * 64,
            "cold_run_receipts_supported": True,
            "phase65_model_inventory": [
                {
                    "path": "chat",
                    "identity_sha256": "a" * 64,
                    "configured": True,
                    "usage_receipt_verified": True,
                }
            ],
        }

    monkeypatch.setattr(evaluator, "_auto_auth_token", auto_auth)
    monkeypatch.setattr(evaluator, "_fetch_contract", fetch_contract)
    monkeypatch.setattr(evaluator, "_write_json", lambda _path, payload: summaries.append(payload))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "paired",
        "--preflight-only",
        "--auto-auth",
        "--baseline-base-url",
        "http://127.0.0.1:8001",
        "--candidate-base-url",
        "http://127.0.0.1:8002",
        "--runs",
        "1",
        "--limit",
        "2",
        "--contract-gate-status",
        "pass",
        "--topology-gate-status",
        "pass",
        "--fault-gate-status",
        "pass",
        "--summary-out",
        "output/phase65/paired-readiness.json",
    ])

    assert evaluator.main() == 1
    assert token_requests == ["http://127.0.0.1:8001", "http://127.0.0.1:8002"]
    assert contract_tokens == ["token-for-8001", "token-for-8002"]
    assert summaries[-1]["endpoint_readiness"]["gate"] == "pass"


def test_paired_preflight_only_reports_auto_auth_failure_without_contract_fetch(monkeypatch) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    summaries: list[dict[str, object]] = []
    fetched: list[str] = []

    def auto_auth(base_url: str, *, timeout_seconds: float) -> str:
        if base_url.endswith(":8001"):
            raise ValueError("auto_auth_failed")
        return "candidate-token"

    def fetch_contract(base_url: str, *, token: str, timeout_seconds: float) -> dict[str, object]:
        fetched.append(base_url)
        return {
            "endpoint_identity_sha256": hashlib.sha256(base_url.encode("utf-8")).hexdigest(),
            "index_fingerprint_sha256": "b" * 64,
            "cold_run_receipts_supported": True,
            "phase65_model_inventory": [
                {
                    "path": "chat",
                    "identity_sha256": "a" * 64,
                    "configured": True,
                    "usage_receipt_verified": True,
                }
            ],
        }

    monkeypatch.setattr(evaluator, "_auto_auth_token", auto_auth)
    monkeypatch.setattr(evaluator, "_fetch_contract", fetch_contract)
    monkeypatch.setattr(evaluator, "_write_json", lambda _path, payload: summaries.append(payload))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "paired",
        "--preflight-only",
        "--auto-auth",
        "--baseline-base-url",
        "http://127.0.0.1:8001",
        "--candidate-base-url",
        "http://127.0.0.1:8002",
        "--runs",
        "1",
        "--limit",
        "2",
        "--summary-out",
        "output/phase65/paired-readiness.json",
    ])

    assert evaluator.main() == 1
    assert fetched == ["http://127.0.0.1:8002"]
    readiness = summaries[-1]["endpoint_readiness"]
    assert readiness["gate"] == "blocked"
    assert "baseline_auto_auth_not_ready" in readiness["failed_required"]


def test_summarize_can_emit_blocked_summary_with_incomplete_optional_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    rows_path = tmp_path / "paired.csv"
    with rows_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PHASE65_OUTPUT_FIELDS)
        writer.writeheader()

    baseline_manifest_path = tmp_path / "baseline.json"
    candidate_manifest_path = tmp_path / "candidate.json"
    cases = _load_cases(Path("data/evaluation/phase64_latency_cases.csv"), limit=2)
    contract = {
        "phase65_model_inventory": [
            {
                "path": "chat",
                "identity_sha256": "a" * 64,
                "configured": True,
                "usage_receipt_verified": True,
            }
        ],
        "index_fingerprint_sha256": "b" * 64,
    }
    receipt = _build_receipt_contract(cases, runs=1, seed=650013)
    write_manifest(
        baseline_manifest_path,
        _build_manifest(
            variant="baseline",
            expected_rows=2,
            completed_rows=2,
            cases=cases,
            receipt_contract=receipt,
            endpoint_identity_sha256="c" * 64,
            contract=contract,
            environment_class="controlled_candidate",
        ),
    )
    write_manifest(
        candidate_manifest_path,
        _build_manifest(
            variant="candidate",
            expected_rows=2,
            completed_rows=2,
            cases=cases,
            receipt_contract=receipt,
            endpoint_identity_sha256="d" * 64,
            contract=contract,
            environment_class="controlled_candidate",
        ),
    )
    monkeypatch.setattr(evaluator, "validate_output_path", lambda path: path)
    monkeypatch.setattr(sys, "argv", [
        "evaluate_phase65_agent_gate.py",
        "--mode",
        "summarize",
        "--results",
        str(rows_path),
        "--baseline-manifest",
        str(baseline_manifest_path),
        "--candidate-manifest",
        str(candidate_manifest_path),
        "--runs",
        "1",
        "--limit",
        "2",
        "--allow-incomplete-evidence",
        "--summary-out",
        str(tmp_path / "summary.json"),
    ])

    assert evaluator.main() == 0
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["gate_decision"]["phase65_acceptance"] == "blocked"
    assert "paired_rows_incomplete" in summary["gate_decision"]["reasons"]


def test_endpoint_readiness_blocks_contract_fetch_when_auth_failed_before_fetch() -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    summary = evaluator._build_endpoint_readiness_summary(
        contracts={},
        endpoint_hashes={},
        active_variants=("candidate",),
        endpoint_failures={"candidate": ["auto_auth"]},
    )

    assert summary["components"]["candidate_auto_auth"] == "blocked"
    assert summary["components"]["candidate_contract_fetch"] == "blocked"
    assert "candidate_contract_fetch_not_ready" in summary["failed_required"]


def test_auto_auth_falls_back_to_local_eval_account_when_registration_is_disabled(
    monkeypatch,
) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator
    from scripts import verify_phase65_production_topology as topology

    def blocked_public_registration(*, base_url, token_sink=None):
        assert base_url == "http://127.0.0.1:8011"
        assert token_sink == {}
        return topology.ProbeResult("fail", "auth_register_failed")

    monkeypatch.setattr(topology, "probe_auth", blocked_public_registration)
    monkeypatch.setattr(
        evaluator,
        "_bootstrap_local_eval_token",
        lambda base_url, timeout_seconds: "local-eval-token",
        raising=False,
    )

    token = evaluator._auto_auth_token(
        "http://127.0.0.1:8011",
        timeout_seconds=1.0,
    )

    assert token == "local-eval-token"


def test_primary_order_has_180_rows_and_alternates_variants() -> None:
    schedule = build_schedule(
        case_ids=[f"c-{index}" for index in range(30)], runs=3, seed=650013
    )

    assert len(schedule) == 180
    assert {item.variant for item in schedule} == {"baseline", "candidate"}
    assert all(
        {schedule[index].variant, schedule[index + 1].variant}
        == {"baseline", "candidate"}
        for index in range(0, len(schedule), 2)
    )


def test_safe_projection_discards_ephemeral_answers_and_raw_payloads() -> None:
    projected = project_safe_row(
        {
            "case_id": "case-1",
            "category": "ordinary_text",
            "ok": True,
            "error_category": "",
            "http_status": 200,
            "expected_tool": "hybrid_search_knowledge",
            "observed_tool_names": "hybrid_search_knowledge",
            "expected_graph_requirement": "disabled",
            "observed_graph_requirement": "disabled",
            "citation_count": 1,
            "selected_count": 2,
            "live_selected_count": 2,
            "counts_match": True,
            "conversation_persisted": True,
            "refused": False,
            "first_token_ms": 120.0,
            "elapsed_ms": 500.0,
            "input_tokens": 3,
            "output_tokens": 4,
            "estimated_cost": 0.01,
            "provider_usage_request_count": 1,
            "provider_usage_receipt_count": 1,
            "provider_usage_receipt_complete": True,
            "runtime_stop_reason": "completed",
            "completed_tool_replay_count": 0,
            "_ephemeral_answer": "must never persist",
            "answer": "must never persist",
            "raw_response": {"secret": "must never persist"},
        },
        variant="candidate",
        run=1,
        manifest_run_id="run-1",
        snapshot_fingerprint="a" * 64,
    )

    assert tuple(projected) == PHASE65_OUTPUT_FIELDS
    assert "must never persist" not in repr(projected)
    assert projected["variant"] == "candidate"


def test_run_variant_case_keeps_answer_ephemeral() -> None:
    received: list[dict[str, object]] = []

    def execute_stub(*_args: object, **kwargs: object) -> dict[str, object]:
        received.append(dict(kwargs))
        return {
            "case_id": "case-1",
            "category": "ordinary_text",
            "_ephemeral_answer": "in-memory only",
            "ok": True,
        }

    row, answer = run_variant_case(
        {"case_id": "case-1", "category": "ordinary_text"},
        variant="baseline",
        run=1,
        base_url="http://127.0.0.1:8001",
        token="not-persisted",
        timeout_seconds=1.0,
        manifest_run_id="run-1",
        snapshot_fingerprint="a" * 64,
        execute=True,
        capture_answer=True,
        execute_case_fn=execute_stub,
    )

    assert received and received[0]["capture_answer"] is True
    assert received[0]["evaluation_run_namespace"] == "phase65-baseline-run-1-1-case-1"
    assert answer == "in-memory only"
    assert "in-memory only" not in repr(row)


def test_evaluation_namespace_includes_invocation_salt() -> None:
    first = _evaluation_run_namespace(
        variant="baseline",
        manifest_run_id="run-1",
        run=1,
        case_id="case-1",
        invocation_salt="salt-a",
    )
    second = _evaluation_run_namespace(
        variant="baseline",
        manifest_run_id="run-1",
        run=1,
        case_id="case-1",
        invocation_salt="salt-b",
    )

    assert first == "phase65-baseline-run-1-salt-a-1-case-1"
    assert second == "phase65-baseline-run-1-salt-b-1-case-1"
    assert first != second


def test_run_variant_case_blocks_missing_cold_cache_receipt() -> None:
    def execute_stub(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "case_id": "case-1",
            "category": "ordinary_text",
            "ok": True,
            "input_tokens": 3,
            "output_tokens": 4,
            "estimated_cost": 0.01,
            "provider_usage_request_count": 1,
            "provider_usage_receipt_count": 1,
            "provider_usage_receipt_complete": True,
        }

    row, _ = run_variant_case(
        {"case_id": "case-1", "category": "ordinary_text"},
        variant="baseline",
        run=1,
        base_url="http://127.0.0.1:8001",
        token="not-persisted",
        timeout_seconds=1.0,
        manifest_run_id="run-1",
        snapshot_fingerprint="a" * 64,
        execute=True,
        capture_answer=False,
        execute_case_fn=execute_stub,
    )

    assert row["ok"] is False
    assert row["error_category"] == "missing_cold_cache_receipt"
    assert row["cold_cache_receipt_status"] == "absent"


def test_run_variant_case_records_cache_hit_cold_receipt_status() -> None:
    def execute_stub(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "case_id": "case-1",
            "category": "ordinary_text",
            "ok": True,
            "cold_cache_receipt": {
                "schema_version": "phase65-cold-cache-receipt-v1",
                "namespace_sha256": hashlib.sha256(
                    b"phase65-baseline-run-1-1-case-1"
                ).hexdigest(),
                "request_binding_sha256": "b" * 64,
                "isolation_version": "phase65-cache-isolation-v1",
                "cache_miss_confirmed": False,
            },
        }

    row, _ = run_variant_case(
        {"case_id": "case-1", "category": "ordinary_text"},
        variant="baseline",
        run=1,
        base_url="http://127.0.0.1:8001",
        token="not-persisted",
        timeout_seconds=1.0,
        manifest_run_id="run-1",
        snapshot_fingerprint="a" * 64,
        execute=True,
        capture_answer=False,
        execute_case_fn=execute_stub,
    )

    assert row["ok"] is False
    assert row["error_category"] == "missing_cold_cache_receipt"
    assert row["cold_cache_receipt_status"] == "cache_hit"


def test_run_variant_case_allows_missing_cost_receipt_when_cold_cache_is_confirmed() -> None:
    def execute_stub(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "case_id": "case-1",
            "category": "ordinary_text",
            "ok": True,
            "provider_usage_request_count": 2,
            "provider_usage_receipt_count": 0,
            "provider_usage_receipt_complete": False,
            "cold_cache_receipt": {
                "schema_version": "phase65-cold-cache-receipt-v1",
                "namespace_sha256": hashlib.sha256(
                    b"phase65-baseline-run-1-1-case-1"
                ).hexdigest(),
                "request_binding_sha256": "b" * 64,
                "isolation_version": "phase65-cache-isolation-v1",
                "cache_miss_confirmed": True,
            },
        }

    row, _ = run_variant_case(
        {"case_id": "case-1", "category": "ordinary_text"},
        variant="baseline",
        run=1,
        base_url="http://127.0.0.1:8001",
        token="not-persisted",
        timeout_seconds=1.0,
        manifest_run_id="run-1",
        snapshot_fingerprint="a" * 64,
        execute=True,
        capture_answer=False,
        execute_case_fn=execute_stub,
    )

    assert row["ok"] is True
    assert row["error_category"] == ""
    assert row["cold_cache_receipt_status"] == "valid"


def test_incremental_progress_outputs_only_safe_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import json

    import scripts.evaluate_phase65_agent_gate as evaluator

    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    monkeypatch.setattr(evaluator, "SAFE_OUTPUT_ROOT", tmp_path / "output")
    contract = _build_receipt_contract(
        [
            {"case_id": "case-1", "category": "ordinary_text"},
            {"case_id": "case-2", "category": "ordinary_text"},
        ],
        runs=1,
        seed=1,
    )
    row = project_safe_row(
        {
            "case_id": "case-1",
            "category": "ordinary_text",
            "ok": True,
            "error_category": "",
            "observed_tool_names": "hybrid_search_knowledge|final_answer",
            "cold_cache_receipt_status": "valid",
            "answer": "must never persist",
            "raw_response": {"secret": "must never persist"},
        },
        variant="baseline",
        run=1,
        manifest_run_id="run-1",
        snapshot_fingerprint="a" * 64,
    )

    evaluator._write_incremental_progress(
        rows_path=Path("output/phase65/live-rows.csv"),
        summary_path=Path("output/phase65/live-summary.json"),
        rows=[row],
        mode="baseline",
        execute=True,
        case_count=1,
        expected_rows=3,
        receipt_contract=contract,
        running=True,
    )

    csv_text = (tmp_path / "output/phase65/live-rows.csv").read_text(
        encoding="utf-8-sig"
    )
    summary = json.loads(
        (tmp_path / "output/phase65/live-summary.json").read_text(encoding="utf-8")
    )

    assert "must never persist" not in csv_text
    assert "raw_response" not in csv_text
    assert ",answer," not in csv_text
    assert "hybrid_search_knowledge|final_answer" in csv_text
    assert summary["completed_rows"] == 1
    assert summary["expected_rows"] == 3
    assert summary["running"] is True


def test_atomic_replace_retries_transient_permission_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import scripts.evaluate_phase65_agent_gate as evaluator

    source = tmp_path / "temporary.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("updated", encoding="utf-8")
    original_replace = Path.replace
    attempts = {"count": 0}

    def flaky_replace(self: Path, target: Path) -> Path:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise PermissionError("simulated windows reader lock")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)

    evaluator._replace_with_retry(source, destination, attempts=2, sleep_seconds=0)

    assert attempts["count"] == 2
    assert destination.read_text(encoding="utf-8") == "updated"


def test_validate_schedule_rejects_incomplete_rows() -> None:
    with pytest.raises(ValueError, match="incomplete_rows:1:2"):
        validate_schedule("paired", [{"variant": "baseline"}], case_count=1, runs=1)


def test_endpoint_urls_must_be_distinct_after_normalization() -> None:
    assert normalize_endpoint_url("http://127.0.0.1:8001/") == "http://127.0.0.1:8001"
    assert normalize_endpoint_url("HTTP://127.0.0.1:8001") == "http://127.0.0.1:8001"


def test_holdout_requires_twelve_unique_cases(tmp_path: Path) -> None:
    cases = tmp_path / "holdout.csv"
    with cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category", "query"))
        writer.writeheader()
        writer.writerows(
            {
                "case_id": f"holdout-{index}",
                "category": "ordinary_text",
                "query": f"holdout query {index}",
            }
            for index in range(12)
        )

    loaded = validate_holdout_cases(cases)

    assert len(loaded) == 12
    assert {row["case_id"] for row in loaded} == {f"holdout-{index}" for index in range(12)}


def test_holdout_question_field_is_mapped_to_executor_query(tmp_path: Path) -> None:
    cases = tmp_path / "holdout.csv"
    with cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category", "question"))
        writer.writeheader()
        writer.writerows(
            {
                "case_id": f"holdout-{index}",
                "category": "ordinary_text",
                "question": f"private reviewer question {index}",
            }
            for index in range(12)
        )

    loaded = validate_holdout_cases(cases)

    assert loaded[0]["query"] == "private reviewer question 0"


def test_holdout_rejects_overlap_with_public_cases(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout.csv"
    public = tmp_path / "public.csv"
    with public.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category"))
        writer.writeheader()
        writer.writerow({"case_id": "e2e-text-01", "category": "ordinary_text"})
    with holdout.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category", "query"))
        writer.writeheader()
        writer.writerows(
            {
                "case_id": "e2e-text-01" if index == 0 else f"holdout-{index}",
                "category": "ordinary_text",
                "query": f"holdout query {index}",
            }
            for index in range(12)
        )

    with pytest.raises(ValueError, match="holdout_overlaps_public_cases"):
        validate_holdout_cases(holdout, exclude_cases_path=public)


def test_judge_receipt_contract_balances_anonymous_mapping_directions() -> None:
    contract = _build_receipt_contract(
        [{"case_id": f"case-{index}", "category": "ordinary_text"} for index in range(30)],
        runs=3,
        seed=650013,
    )

    assert contract.expected_count == 90
    assert abs(
        contract.expected_mapping_hashes.count(contract.expected_mapping_hashes[0])
        - contract.expected_mapping_hashes.count(contract.expected_mapping_hashes[-1])
    ) <= 1


def test_output_path_rejects_absolute_escape_and_sensitive_file() -> None:
    with pytest.raises(ValueError, match="unsafe_output_path"):
        validate_output_path(Path(".env"))
    with pytest.raises(ValueError, match="unsafe_output_path"):
        validate_output_path(Path("../output/phase65.csv"))
    with pytest.raises(ValueError, match="unsafe_output_path"):
        validate_output_path(Path("C:/temp/phase65.csv"))


def test_output_path_accepts_only_relative_output_directory() -> None:
    assert validate_output_path(Path("output/phase65/results.csv")).as_posix().endswith(
        "output/phase65/results.csv"
    )


def test_output_path_rejects_dotenv_component() -> None:
    with pytest.raises(ValueError, match="unsafe_output_path"):
        validate_output_path(Path("output/.env.local/results.csv"))
