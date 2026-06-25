from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_OUTPUT = Path("data/evaluation/phase54_completion_audit.csv")


def read_metric_csv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["metric"]: row["value"] for row in csv.DictReader(handle)}


def read_check_csv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["check"]: row["status"] for row in csv.DictReader(handle)}


def read_check_values_csv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["check"]: row.get("value", "") for row in csv.DictReader(handle)}


def read_stage30_overall(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("dimension") == "overall":
                return row
    return {}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def audit_rows(root: Path) -> list[dict[str, str]]:
    coverage = read_json(root / "data/evaluation/phase54_llm_coverage_plan.json")
    graph_stats = read_metric_csv(root / "data/evaluation/phase54_graph_stats.csv")
    retrieval = read_metric_csv(root / "data/evaluation/phase54_graphrag_eval_summary_retrieval_only.csv")
    answer_only = read_metric_csv(root / "data/evaluation/phase54_graphrag_eval_summary_answer_only_full.csv")
    preflight_path = root / "data/evaluation/phase54_graphrag_eval_preflight.csv"
    preflight = read_check_csv(preflight_path)
    preflight_values = read_check_values_csv(preflight_path)
    formal_summary = read_metric_csv(root / "data/evaluation/phase54_graphrag_eval_summary_real_api.csv")
    stage30 = read_stage30_overall(root / "data/evaluation/stage30_quality_summary.csv")
    validation = read_check_csv(root / "data/evaluation/phase54_prejudge_validation.csv")
    docs_ok, docs_evidence = phase54_docs_synced(root)
    return [
        row(
            "llm_coverage_target_complete",
            "complete" if nested(coverage, "combined", "remaining_target") == 0 else "missing",
            f"completed={nested(coverage, 'combined', 'completed_target')} target={nested(coverage, 'combined', 'target')} remaining={nested(coverage, 'combined', 'remaining_target')}",
            "none",
        ),
        row(
            "graph_isolated_node_gate",
            "complete" if float_value(graph_stats.get("isolated_node_ratio")) < 0.30 else "missing",
            f"isolated_node_ratio={graph_stats.get('isolated_node_ratio', '')}",
            "rebuild graph with normalization/pruning if >=0.30",
        ),
        row(
            "graph_lcc_gate",
            "complete" if float_value(graph_stats.get("largest_connected_component_ratio")) > 0.40 else "missing",
            f"largest_connected_component_ratio={graph_stats.get('largest_connected_component_ratio', '')}",
            "rebuild graph with stronger canonicalization if <=0.40",
        ),
        row(
            "preflight_non_judge_prereqs",
            "complete" if non_judge_preflight_ready(preflight) else "missing",
            f"cases={preflight.get('cases_total', '')} graph={preflight.get('graph_file_exists', '')} chat={preflight.get('chat_provider_configured', '')} embedding={preflight.get('embedding_provider_configured', '')}",
            "fix cases/graph/chat/embedding configuration",
        ),
        row(
            "judge_provider_ready",
            "complete" if preflight.get("judge_provider_configured") == "pass" else "missing",
            f"judge_provider_configured={preflight.get('judge_provider_configured', '')} missing_fields={preflight_values.get('judge_model_missing_fields', '')}",
            "configure local JUDGE_MODEL_*",
        ),
        row(
            "retrieval_only_all_cases",
            "complete" if retrieval.get("retrieval_only_rows") == "47" and retrieval.get("error_rows") == "0" else "missing",
            f"retrieval_only_rows={retrieval.get('retrieval_only_rows', '')} error_rows={retrieval.get('error_rows', '')}",
            "rerun --execute-retrieval --resume",
        ),
        row(
            "negative_graph_false_positive_gate",
            "complete" if retrieval.get("negative_graph_false_positive_count") == "0" else "missing",
            f"negative_graph_false_positive_count={retrieval.get('negative_graph_false_positive_count', '')}",
            "tighten graph matching filters",
        ),
        row(
            "answer_only_all_cases",
            "complete" if answer_only.get("answer_only_rows") == "47" and answer_only.get("error_rows") == "0" else "missing",
            f"answer_only_rows={answer_only.get('answer_only_rows', '')} error_rows={answer_only.get('error_rows', '')}",
            "rerun --execute-answers --resume",
        ),
        row(
            "stage30_quality_gate",
            "complete" if stage30.get("status") == "pass" and stage30.get("score") == "91.52" else "missing",
            f"score={stage30.get('score', '')} status={stage30.get('status', '')} evidence={stage30.get('evidence', '')}",
            "rerun python scripts\\score_stage30_quality.py",
        ),
        row(
            "full_pytest_baseline",
            "complete" if validation.get("full_pytest") == "pass" else "missing",
            f"status={validation.get('full_pytest', '')}",
            "rerun python -m pytest -q",
        ),
        row(
            "diff_check_clean",
            "complete" if validation.get("git_diff_check") == "pass" else "missing",
            f"status={validation.get('git_diff_check', '')}",
            "rerun git diff --check",
        ),
        row(
            "phase54_sensitive_scan",
            "complete" if validation.get("phase54_sensitive_scan") == "pass" else "missing",
            f"status={validation.get('phase54_sensitive_scan', '')}",
            "rerun targeted Phase 54 sensitive scan",
        ),
        row(
            "phase54_docs_synced",
            "complete" if docs_ok else "missing",
            docs_evidence,
            "sync README/AGENT/docs/phase review with current Phase 54 status",
        ),
        row(
            "git_submission_boundary",
            "complete" if validation.get("git_staged_changes_absent") == "pass" else "missing",
            f"status={validation.get('git_staged_changes_absent', '')}",
            "keep git index unstaged until user verification",
        ),
        row(
            "formal_judge_rows",
            formal_judge_status(formal_summary),
            f"completed={formal_summary.get('completed_rows', '')} scored={formal_summary.get('formal_judge_scored_rows', '')} total={formal_summary.get('total_cases', '')}",
            "run formal --execute after judge preflight passes",
        ),
        row(
            "formal_judge_gate",
            "complete" if formal_summary.get("formal_judge_gate_decision") == "pass" else "missing",
            f"decision={formal_summary.get('formal_judge_gate_decision', '')} reason={formal_summary.get('formal_judge_gate_reason', '')}",
            "inspect formal gate reason and tune if review_required",
        ),
    ]


def row(requirement: str, status: str, evidence: str, next_action: str) -> dict[str, str]:
    return {
        "requirement": requirement,
        "status": status,
        "evidence": evidence,
        "next_action": next_action,
    }


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def float_value(value: str | None) -> float:
    try:
        return float(value or "nan")
    except ValueError:
        return float("nan")


def non_judge_preflight_ready(preflight: dict[str, str]) -> bool:
    return all(
        preflight.get(key) == "pass"
        for key in (
            "cases_total",
            "graph_intent_cases",
            "negative_offtopic_cases",
            "graph_file_exists",
            "chat_provider_configured",
            "embedding_provider_configured",
        )
    )


def phase54_docs_synced(root: Path) -> tuple[bool, str]:
    required_markers = {
        "README.md": "formal_judge_gate_decision=pass",
        "AGENT.MD": "answer-only full",
        "docs/progress.md": "answer-only full",
        "docs/architecture.md": "Only `--execute` rows",
        "docs/data_sources.md": "Formal Phase 54D",
        "docs/phase_reviews/phase-54.md": "answer-only full",
        "docs/stage54_graphrag_evaluation_prompt.md": "completion_audit=complete 16",
        "docs/phase54_completion_audit.md": "phase54_completion_audit complete=16",
    }
    missing: list[str] = []
    for relative_path, marker in required_markers.items():
        path = root / relative_path
        if not path.exists():
            missing.append(f"{relative_path}:missing")
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if marker not in content:
            missing.append(f"{relative_path}:marker")
    if missing:
        return False, "missing=" + "|".join(missing)
    return True, f"synced_files={len(required_markers)}"


def formal_judge_status(summary: dict[str, str]) -> str:
    if not summary:
        return "missing"
    total = summary.get("total_cases")
    completed = summary.get("completed_rows")
    scored = summary.get("formal_judge_scored_rows")
    if total and completed == total and scored == total:
        return "complete"
    if completed and completed != "0":
        return "partial"
    return "missing"


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["requirement", "status", "evidence", "next_action"])
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Phase 54 completion evidence without provider calls.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = audit_rows(ROOT)
    write_csv(Path(args.output), rows)
    missing = sum(1 for item in rows if item["status"] == "missing")
    partial = sum(1 for item in rows if item["status"] == "partial")
    complete = sum(1 for item in rows if item["status"] == "complete")
    print(f"phase54_completion_audit complete={complete} partial={partial} missing={missing} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
