import csv
import json
from pathlib import Path

from scripts.audit_phase54_completion import audit_rows, write_csv


def test_phase54_completion_audit_reports_missing_formal_judge(tmp_path, monkeypatch) -> None:
    root = tmp_path
    evaluation = root / "data" / "evaluation"
    evaluation.mkdir(parents=True)
    (evaluation / "phase54_llm_coverage_plan.json").write_text(
        json.dumps({"combined": {"target": 4331, "completed_target": 4331, "remaining_target": 0}}),
        encoding="utf-8",
    )
    write_metric_csv(
        evaluation / "phase54_graph_stats.csv",
        {
            "isolated_node_ratio": "0.1408",
            "largest_connected_component_ratio": "0.8002",
        },
    )
    write_metric_csv(
        evaluation / "phase54_graphrag_eval_summary_retrieval_only.csv",
        {
            "retrieval_only_rows": "47",
            "error_rows": "0",
            "negative_graph_false_positive_count": "0",
        },
    )
    write_metric_csv(
        evaluation / "phase54_graphrag_eval_summary_answer_only_full.csv",
        {
            "answer_only_rows": "47",
            "error_rows": "0",
        },
    )
    write_stage30_summary(evaluation / "stage30_quality_summary.csv", score="91.52", status="pass")
    write_check_csv(
        evaluation / "phase54_prejudge_validation.csv",
        {
            "full_pytest": "pass",
            "git_diff_check": "pass",
            "phase54_sensitive_scan": "pass",
            "git_staged_changes_absent": "pass",
        },
    )
    write_phase54_docs(root)
    write_check_csv(
        evaluation / "phase54_graphrag_eval_preflight.csv",
        {
            "cases_total": "pass",
            "graph_intent_cases": "pass",
            "negative_offtopic_cases": "pass",
            "graph_file_exists": "pass",
            "chat_provider_configured": "pass",
            "judge_provider_configured": "fail",
            "embedding_provider_configured": "pass",
        },
    )

    rows = audit_rows(root)
    by_requirement = {row["requirement"]: row for row in rows}

    assert by_requirement["llm_coverage_target_complete"]["status"] == "complete"
    assert by_requirement["graph_isolated_node_gate"]["status"] == "complete"
    assert by_requirement["answer_only_all_cases"]["status"] == "complete"
    assert by_requirement["stage30_quality_gate"]["status"] == "complete"
    assert by_requirement["full_pytest_baseline"]["status"] == "complete"
    assert by_requirement["diff_check_clean"]["status"] == "complete"
    assert by_requirement["phase54_sensitive_scan"]["status"] == "complete"
    assert by_requirement["phase54_docs_synced"]["status"] == "complete"
    assert by_requirement["git_submission_boundary"]["status"] == "complete"
    assert by_requirement["judge_provider_ready"]["status"] == "missing"
    assert by_requirement["formal_judge_rows"]["status"] == "missing"
    assert by_requirement["formal_judge_gate"]["status"] == "missing"


def test_phase54_completion_audit_detects_complete_formal_judge(tmp_path) -> None:
    root = tmp_path
    evaluation = root / "data" / "evaluation"
    evaluation.mkdir(parents=True)
    (evaluation / "phase54_llm_coverage_plan.json").write_text(
        json.dumps({"combined": {"target": 4331, "completed_target": 4331, "remaining_target": 0}}),
        encoding="utf-8",
    )
    write_metric_csv(
        evaluation / "phase54_graph_stats.csv",
        {
            "isolated_node_ratio": "0.1408",
            "largest_connected_component_ratio": "0.8002",
        },
    )
    write_metric_csv(
        evaluation / "phase54_graphrag_eval_summary_retrieval_only.csv",
        {
            "retrieval_only_rows": "47",
            "error_rows": "0",
            "negative_graph_false_positive_count": "0",
        },
    )
    write_metric_csv(
        evaluation / "phase54_graphrag_eval_summary_answer_only_full.csv",
        {
            "answer_only_rows": "47",
            "error_rows": "0",
        },
    )
    write_stage30_summary(evaluation / "stage30_quality_summary.csv", score="91.52", status="pass")
    write_check_csv(
        evaluation / "phase54_prejudge_validation.csv",
        {
            "full_pytest": "pass",
            "git_diff_check": "pass",
            "phase54_sensitive_scan": "pass",
            "git_staged_changes_absent": "pass",
        },
    )
    write_phase54_docs(root)
    write_check_csv(
        evaluation / "phase54_graphrag_eval_preflight.csv",
        {
            "cases_total": "pass",
            "graph_intent_cases": "pass",
            "negative_offtopic_cases": "pass",
            "graph_file_exists": "pass",
            "chat_provider_configured": "pass",
            "judge_provider_configured": "pass",
            "embedding_provider_configured": "pass",
        },
    )
    write_metric_csv(
        evaluation / "phase54_graphrag_eval_summary_real_api.csv",
        {
            "total_cases": "47",
            "completed_rows": "47",
            "formal_judge_scored_rows": "47",
            "formal_judge_gate_decision": "pass",
            "formal_judge_gate_reason": "all_phase54d_gates_passed",
        },
    )

    rows = audit_rows(root)
    by_requirement = {row["requirement"]: row for row in rows}

    assert by_requirement["judge_provider_ready"]["status"] == "complete"
    assert by_requirement["formal_judge_rows"]["status"] == "complete"
    assert by_requirement["formal_judge_gate"]["status"] == "complete"


def write_metric_csv(path: Path, rows: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for metric, value in rows.items():
            writer.writerow({"metric": metric, "value": value})


def write_check_csv(path: Path, rows: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "value"])
        writer.writeheader()
        for check, status in rows.items():
            writer.writerow({"check": check, "status": status, "value": ""})


def write_stage30_summary(path: Path, *, score: str, status: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "run_id",
                "dimension",
                "weight",
                "score",
                "max_score",
                "normalized_score",
                "status",
                "evidence",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "run_id": "stage30-test",
                "dimension": "overall",
                "weight": "100.00",
                "score": score,
                "max_score": "100.00",
                "normalized_score": "0.915",
                "status": status,
                "evidence": "grade=A; scoring_mode=deterministic_rule_based",
            }
        )


def write_phase54_docs(root: Path) -> None:
    files = {
        "README.md": "Phase 54 formal_judge_gate_decision=pass",
        "AGENT.MD": "Phase 54 answer-only full",
        "docs/progress.md": "Phase 54 answer-only full",
        "docs/architecture.md": "Only `--execute` rows",
        "docs/data_sources.md": "Formal Phase 54D",
        "docs/phase_reviews/phase-54.md": "answer-only full",
        "docs/stage54_graphrag_evaluation_prompt.md": "completion_audit=complete 16",
        "docs/phase54_completion_audit.md": "phase54_completion_audit complete=16",
    }
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
