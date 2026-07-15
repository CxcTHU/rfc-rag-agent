import csv
import json
from pathlib import Path
from dataclasses import replace

import pytest

from scripts.score_stage30_quality import (
    evaluate_evidence_status,
    load_verified_test_receipt,
    load_scoring_config,
    score_quality,
    write_deductions,
    write_scores,
    write_summary,
)
from scripts.phase65_gate_manifest import AgentGateManifest, GitWorktreeIdentity
import scripts.score_stage30_quality as stage30_scoring


TEST_SUITE_SHA256 = "3" * 64
CURRENT_SCOPE = (
    "scripts/evaluate_phase65_agent_gate.py", "scripts/phase65_gate_manifest.py", "scripts/phase65_agent_gate.py",
    "scripts/judge_phase65_agent_gate.py", "scripts/verify_phase65_test_receipt.py",
    "scripts/collect_stage30_engineering_health.py", "scripts/score_stage30_quality.py",
    "scripts/build_stage30_quality_report.py", "app/frontend/quality_report.html",
)


@pytest.fixture(autouse=True)
def closed_scope_for_unit_receipts(monkeypatch):
    monkeypatch.setattr(stage30_scoring, "canonical_phase65_scope", lambda _root: CURRENT_SCOPE)


def verified_test_receipt() -> dict[str, object]:
    return {"schema_version": "stage30-pytest-junit-v1", "tests": 10, "failures": 0, "errors": 0, "test_suite_sha256": TEST_SUITE_SHA256, "receipt_sha256": "4" * 64}


def current_identity() -> GitWorktreeIdentity:
    return GitWorktreeIdentity(base_commit="base-commit", dirty=True, tracked_patch_sha256="a" * 64, scoped_content_sha256="b" * 64, scoped_paths=CURRENT_SCOPE)


def current_manifest(**changes: object) -> AgentGateManifest:
    values: dict[str, object] = {"schema_version": "phase65-agent-gate-v1", "run_id": "phase65-current", "variant": "candidate", "status": "complete", "base_commit": "base-commit", "tracked_patch_sha256": "a" * 64, "scoped_content_sha256": "b" * 64, "scoped_paths": CURRENT_SCOPE, "evaluator_sha256": "c" * 64, "case_set_sha256": "d" * 64, "prompt_sha256": "e" * 64, "tool_schema_sha256": "f" * 64, "corpus_fingerprint": "corpus-v1", "index_fingerprint": "index-v1", "provider_models": ("provider:model",), "endpoint_identity_sha256": "1" * 64, "judge_receipt_contract_sha256": "2" * 64, "cache_policy": "cold", "environment_class": "controlled_candidate", "expected_rows": 1, "completed_rows": 1, "started_at": "2026-07-14T00:00:00+00:00", "completed_at": "2026-07-14T00:00:01+00:00"}
    values.update(changes)
    return AgentGateManifest(**values)  # type: ignore[arg-type]


def stage29_rows() -> list[dict[str, str]]:
    return [
        {
            "query_id": "stage29_good",
            "expected_refused": "false",
            "expected_source_type": "web_page",
            "precision_at_5": "true",
            "coverage_ratio": "0.750",
            "source_type_distribution": "web_page:3;wikipedia:2",
        },
        {
            "query_id": "stage29_low_coverage",
            "expected_refused": "false",
            "expected_source_type": "wikipedia",
            "precision_at_5": "false",
            "coverage_ratio": "0.250",
            "source_type_distribution": "web_page:5",
        },
        {
            "query_id": "stage29_refusal",
            "expected_refused": "true",
            "expected_source_type": "",
            "precision_at_5": "false",
            "coverage_ratio": "0.000",
            "source_type_distribution": "",
        },
    ]


def stage29_summary() -> dict[str, str]:
    return {
        "precision_at_1": "0.600",
        "precision_at_3": "0.867",
        "precision_at_5": "0.933",
        "avg_coverage_ratio": "0.664",
        "refusal_accuracy": "1.000",
        "source_type_distribution": "metadata_record:2;web_page:5;wikipedia:3;standard_document:1",
    }


def health() -> dict[str, object]:
    return {
        "schema_version": "stage30-engineering-health-v2",
        "manifest_run_id": "phase65-current",
        "base_commit": "base-commit",
        "tracked_patch_sha256": "a" * 64,
        "test_suite_sha256": TEST_SUITE_SHA256,
        "pytest_receipt_schema_version": "stage30-pytest-junit-v1",
        "pytest_receipt_tests": 10,
        "pytest_receipt_failures": 0,
        "pytest_receipt_errors": 0,
        "pytest_receipt_test_suite_sha256": TEST_SUITE_SHA256,
        "pytest_receipt_receipt_sha256": "4" * 64,
        "full_tests_status": "556 passed, 1 warning",
        "chunk_count": 10,
        "embedding_count": 20,
        "jina_embedding_count": 10,
        "deterministic_embedding_count": 10,
        "orphan_embeddings": 0,
        "duplicate_provider_model_groups": 0,
        "quality_report_smoke": "passed",
    }


def test_stage30_weights_sum_to_100_and_keep_rule_based_names() -> None:
    config = load_scoring_config(Path("data/evaluation/stage30_scoring_weights.yaml"))

    assert sum(config.weights.values()) == 100
    assert "rule_based_context_answer_quality" in config.weights
    assert "faithfulness" not in config.weights
    assert config.scoring_mode == "deterministic_rule_based"


def test_stage30_score_outputs_review_required_for_known_risks(tmp_path) -> None:
    config = load_scoring_config(Path("data/evaluation/stage30_scoring_weights.yaml"))

    result = score_quality(
        stage29_rows(),
        stage29_summary(),
        health(),
        config,
        run_id="test-run",
        run_at="2026-06-12T00:00:00+00:00",
        previous_scores_path=tmp_path / "missing.csv",
        manifest=current_manifest(),
        test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=verified_test_receipt(),
        current_worktree_identity=current_identity(),
    )

    assert result.grade == "B"
    assert result.release_decision == "review_required"
    assert result.dimension_scores["engineering_health"] == 10
    assert any(item.query_id == "stage29_low_coverage" for item in result.deductions)
    assert "faithfulness" not in json.dumps(result.dimension_scores)


def test_stage30_score_writers_create_expected_csvs(tmp_path) -> None:
    config = load_scoring_config(Path("data/evaluation/stage30_scoring_weights.yaml"))
    result = score_quality(
        stage29_rows(),
        stage29_summary(),
        health(),
        config,
        run_id="test-run",
        run_at="2026-06-12T00:00:00+00:00",
        previous_scores_path=tmp_path / "scores.csv",
        manifest=current_manifest(),
        test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=verified_test_receipt(),
        current_worktree_identity=current_identity(),
    )
    scores_path = tmp_path / "scores.csv"
    summary_path = tmp_path / "summary.csv"
    deductions_path = tmp_path / "deductions.csv"

    write_scores(scores_path, result, append=False)
    write_summary(summary_path, result, config)
    write_deductions(deductions_path, result)

    with scores_path.open("r", encoding="utf-8", newline="") as file:
        score_rows = list(csv.DictReader(file))
    assert score_rows[0]["run_id"] == "test-run"
    assert score_rows[0]["dimension_scores"]
    assert "recommended_actions" in score_rows[0]

    with summary_path.open("r", encoding="utf-8", newline="") as file:
        summary_rows = list(csv.DictReader(file))
    assert {row["dimension"] for row in summary_rows} >= {"retrieval_quality", "overall"}

    with deductions_path.open("r", encoding="utf-8", newline="") as file:
        deduction_rows = list(csv.DictReader(file))
    assert deduction_rows
    assert all("raw_response" not in json.dumps(row).lower() for row in deduction_rows)


def test_unbound_health_is_blocked_and_keeps_historical_score(tmp_path) -> None:
    config = load_scoring_config(Path("data/evaluation/stage30_scoring_weights.yaml"))
    stale_health = health()
    stale_health["tracked_patch_sha256"] = "0" * 64
    result = score_quality(
        stage29_rows(), stage29_summary(), stale_health, config,
        run_id="test-run", run_at="2026-07-14T00:00:00+00:00", previous_scores_path=tmp_path / "missing.csv",
        manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=verified_test_receipt(), current_worktree_identity=current_identity(),
    )
    assert result.release_decision == "blocked"
    assert result.historical_overall_score is not None
    assert result.evidence_status == "stale"


def test_local_integrity_only_receipt_is_blocked() -> None:
    status = evaluate_evidence_status(
        health=health(), manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=verified_test_receipt() | {"trust_level": "local_integrity_only"},
        current_worktree_identity=current_identity(),
    )
    assert status.status == "blocked"
    assert "local_integrity_only" in status.reasons


def test_score_writer_upgrades_legacy_history_header_before_append(tmp_path) -> None:
    config = load_scoring_config(Path("data/evaluation/stage30_scoring_weights.yaml"))
    result = score_quality(
        stage29_rows(), stage29_summary(), health(), config,
        run_id="test-run", run_at="2026-07-14T00:00:00+00:00", previous_scores_path=tmp_path / "scores.csv",
        manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=verified_test_receipt(), current_worktree_identity=current_identity(),
    )
    scores_path = tmp_path / "scores.csv"
    scores_path.write_text(
        "run_id,run_at,scoring_version,scoring_mode,overall_score,grade,release_decision,dimension_scores,score_delta,main_deductions,recommended_actions\n"
        "legacy,old,stage30-v1,deterministic_rule_based,91.52,A,pass,{},,,old action\n",
        encoding="utf-8",
    )
    write_scores(scores_path, result, append=True)
    with scores_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[-1]["evidence_status"] == "current"


def test_score_writer_neutralizes_spreadsheet_formula_cells(tmp_path) -> None:
    config = load_scoring_config(Path("data/evaluation/stage30_scoring_weights.yaml"))
    result = replace(
        score_quality(
            stage29_rows(), stage29_summary(), health(), config,
            run_id="test-run", run_at="2026-07-14T00:00:00+00:00", previous_scores_path=tmp_path / "missing.csv",
            manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256,
            test_receipt=verified_test_receipt(), current_worktree_identity=current_identity(),
        ),
        run_id="=unsafe",
        recommended_actions=["+unsafe"],
    )
    path = tmp_path / "scores.csv"
    write_scores(path, result, append=False)
    with path.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["run_id"] == "'=unsafe"
    assert row["recommended_actions"].startswith("'+unsafe")


@pytest.mark.parametrize("value", ["=FORMULA", "\t=FORMULA", "  =FORMULA", "\r\n=FORMULA"])
def test_csv_safe_normalizes_controls_before_formula_guard(value: str) -> None:
    from scripts.score_stage30_quality import csv_safe
    assert csv_safe(value) == "'=FORMULA"


def test_actual_worktree_recalculation_blocks_changed_scoped_source(monkeypatch) -> None:
    changed = GitWorktreeIdentity(
        base_commit="base-commit", dirty=True, tracked_patch_sha256="a" * 64,
        scoped_content_sha256="0" * 64, scoped_paths=("scripts/score_stage30_quality.py",),
    )
    monkeypatch.setattr(stage30_scoring, "read_git_worktree_identity", lambda *_: changed)
    status = evaluate_evidence_status(health=health(), manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256, test_receipt=verified_test_receipt())
    assert status.status == "stale"
    assert "worktree_scoped_content_mismatch" in status.reasons


def test_zero_row_or_non_cold_manifest_is_blocked() -> None:
    zero_rows = current_manifest(expected_rows=0, completed_rows=0)
    status = evaluate_evidence_status(
        health=health(), manifest=zero_rows, test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=verified_test_receipt(), current_worktree_identity=current_identity(),
    )
    assert status.status == "blocked"
    assert "manifest_incomplete" in status.reasons


def test_manifest_without_current_stage30_scope_is_blocked() -> None:
    status = evaluate_evidence_status(
        health=health(), manifest=current_manifest(scoped_paths=("scripts/score_stage30_quality.py",)),
        test_suite_sha256=TEST_SUITE_SHA256, test_receipt=verified_test_receipt(),
        current_worktree_identity=current_identity(),
    )
    assert status.status == "blocked"
    assert "manifest_scope_incomplete" in status.reasons


def test_closed_scope_rejects_manifest_that_omits_changed_tool_calling_service(monkeypatch) -> None:
    closed_scope = CURRENT_SCOPE + ("app/services/agent/tool_calling_service.py",)
    monkeypatch.setattr(stage30_scoring, "canonical_phase65_scope", lambda _root: closed_scope, raising=False)
    status = evaluate_evidence_status(
        health=health(), manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=verified_test_receipt(), current_worktree_identity=current_identity(),
    )
    assert status.status == "blocked"
    assert "manifest_scope_incomplete" in status.reasons


def test_change_to_any_closed_scope_file_is_stale(monkeypatch) -> None:
    closed_scope = CURRENT_SCOPE + ("app/services/agent/tool_calling_service.py",)
    manifest = current_manifest(scoped_paths=closed_scope)
    changed = GitWorktreeIdentity(
        base_commit="base-commit", dirty=True, tracked_patch_sha256="a" * 64,
        scoped_content_sha256="0" * 64, scoped_paths=closed_scope,
    )
    monkeypatch.setattr(stage30_scoring, "canonical_phase65_scope", lambda _root: closed_scope, raising=False)
    status = evaluate_evidence_status(
        health=health(), manifest=manifest, test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=verified_test_receipt(), current_worktree_identity=changed,
    )
    assert status.status == "stale"
    assert "worktree_scoped_content_mismatch" in status.reasons


def test_ignore_configuration_change_blocks_old_closed_scope_manifest(monkeypatch) -> None:
    closed_scope = CURRENT_SCOPE + (".gitignore", "app/services/agent/tool_calling_service.py")
    monkeypatch.setattr(stage30_scoring, "canonical_phase65_scope", lambda _root: closed_scope, raising=False)
    status = evaluate_evidence_status(
        health=health(), manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=verified_test_receipt(), current_worktree_identity=current_identity(),
    )
    assert status.status == "blocked"
    assert "manifest_scope_incomplete" in status.reasons


def test_bundle_manifest_binding_must_match_supplied_manifest() -> None:
    receipt = verified_test_receipt() | {"manifest_run_id": "different-run", "manifest_base_commit": "different-base", "manifest_tracked_patch_sha256": "z" * 64, "manifest_scoped_content_sha256": "y" * 64, "manifest_scoped_paths": ("scripts/score_stage30_quality.py",)}
    status = evaluate_evidence_status(health=health(), manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256, test_receipt=receipt, current_worktree_identity=current_identity())
    assert status.status == "blocked"
    assert "bundle_manifest_mismatch" in status.reasons


def test_bundle_full_safe_manifest_must_match_provider_and_endpoint_binding() -> None:
    receipt = verified_test_receipt() | {
        "manifest": current_manifest(endpoint_identity_sha256="9" * 64).to_safe_dict(),
    }
    status = evaluate_evidence_status(
        health=health(), manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt=receipt, current_worktree_identity=current_identity(),
    )
    assert status.status == "blocked"
    assert "bundle_manifest_mismatch" in status.reasons


def test_unverified_pytest_status_text_cannot_replace_junit_receipt() -> None:
    status = evaluate_evidence_status(
        health=health(), manifest=current_manifest(), test_suite_sha256=TEST_SUITE_SHA256,
        test_receipt={"schema_version": "stage30-pytest-junit-v1", "tests": 0, "failures": 0, "errors": 0},
        current_worktree_identity=current_identity(),
    )
    assert status.status == "blocked"
    assert "pytest_receipt_invalid" in status.reasons


def test_junit_receipt_requires_controlled_inventory_and_zero_failures(tmp_path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_sample.py").write_text("def test_sample():\n    assert True\n", encoding="utf-8")
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"schema_version": "stage30-test-inventory-v1", "paths": ["tests/test_sample.py"]}), encoding="utf-8")
    receipt = tmp_path / "junit.xml"
    receipt.write_text('<testsuite name="pytest" tests="1" failures="0" errors="0"><testcase classname="tests.test_sample" name="test_sample"/></testsuite>', encoding="utf-8")
    verified = load_verified_test_receipt(receipt, inventory, repository_root=tmp_path)
    assert verified["tests"] == 1
    receipt.write_text('<testsuite name="pytest" tests="1" failures="1" errors="0"><testcase classname="tests.test_sample" name="test_sample"/></testsuite>', encoding="utf-8")
    with pytest.raises(ValueError, match="pytest_receipt_invalid"):
        load_verified_test_receipt(receipt, inventory, repository_root=tmp_path)


def test_junit_receipt_rejects_partial_inventory_and_missing_pytest_modules(tmp_path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_one.py").write_text("def test_one():\n    assert True\n", encoding="utf-8")
    (tmp_path / "tests" / "test_two.py").write_text("def test_two():\n    assert True\n", encoding="utf-8")
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps({"schema_version": "stage30-test-inventory-v1", "paths": ["tests/test_one.py"]}),
        encoding="utf-8",
    )
    receipt = tmp_path / "junit.xml"
    receipt.write_text('<testsuites name="pytest" tests="1" failures="0" errors="0"><testsuite><testcase classname="tests.test_one" name="test_one"/></testsuite></testsuites>', encoding="utf-8")
    with pytest.raises(ValueError, match="test_inventory_not_canonical"):
        load_verified_test_receipt(receipt, inventory, repository_root=tmp_path)
    inventory.write_text(
        json.dumps({"schema_version": "stage30-test-inventory-v1", "paths": ["tests/test_one.py", "tests/test_two.py"]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="pytest_receipt_incomplete"):
        load_verified_test_receipt(receipt, inventory, repository_root=tmp_path)


def test_junit_receipt_rejects_one_fake_case_per_module_when_collection_has_more_nodes(tmp_path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_one.py").write_text("def test_one(): pass\ndef test_two(): pass\n", encoding="utf-8")
    (tmp_path / "tests" / "test_two.py").write_text("def test_three(): pass\n", encoding="utf-8")
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"schema_version": "stage30-test-inventory-v1", "paths": ["tests/test_one.py", "tests/test_two.py"]}), encoding="utf-8")
    receipt = tmp_path / "junit.xml"
    receipt.write_text('<testsuites name="pytest" tests="2" failures="0" errors="0"><testsuite><testcase classname="tests.test_one" name="test_one"/><testcase classname="tests.test_two" name="test_three"/></testsuite></testsuites>', encoding="utf-8")
    from scripts.verify_phase65_test_receipt import build_producer_receipt
    collection = tmp_path / "collection.json"
    collection.write_text(json.dumps(build_producer_receipt(root=tmp_path, inventory_path=inventory, junit_path=receipt, node_ids=["tests/test_one.py::test_one", "tests/test_one.py::test_two", "tests/test_two.py::test_three"], pytest_version="8.0", manifest={}), sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="pytest_collection_mismatch"):
        load_verified_test_receipt(receipt, inventory, collection_receipt_path=collection, repository_root=tmp_path)
