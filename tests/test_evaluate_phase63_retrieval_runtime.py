from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from scripts.evaluate_phase63_retrieval_runtime import gate_summary


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_phase63_retrieval_runtime.py"


def test_phase63_evaluator_dry_run_is_safe(tmp_path: Path) -> None:
    output = tmp_path / "phase63.csv"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(output), "--limit", "2"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert '"validation_mode": "case_schema_only"' in completed.stdout
    assert '"routing_metrics": "not_executed"' in completed.stdout
    with output.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4
    assert {row["runtime_mode"] for row in rows} == {"legacy", "phase63"}
    assert "answer" not in rows[0]
    assert "raw_response" not in rows[0]
    assert "evidence_content" not in rows[0]


def test_phase63_evaluator_case_set_covers_required_slices() -> None:
    cases_path = ROOT / "data" / "evaluation" / "phase63_retrieval_runtime_cases.csv"

    with cases_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) >= 36
    assert {
        "ordinary",
        "explicit_relationship",
        "implicit_relationship",
        "standard_reference",
        "graph_negative",
        "relationship_negation",
        "explicit_table",
        "explicit_figure",
        "followup_relationship",
        "topic_shift",
        "planner_failure",
        "graph_unavailable",
    } <= {row["category"] for row in rows}


def test_phase63_execute_requires_separately_configured_endpoints(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--out",
            str(tmp_path / "not-written.csv"),
            "--execute",
            "--limit",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "execute_requires_distinct_runtime_endpoints" in completed.stdout


def test_phase63_real_gate_summary_covers_quality_routing_and_latency() -> None:
    rows: list[dict[str, object]] = []

    def add_pair(
        case_id: str,
        category: str,
        expected_tool: str,
        graph_requirement: str,
        *,
        planner_fallback: bool = False,
        graph_fallback: bool = False,
    ) -> None:
        for mode, elapsed, accuracy, citation in (
            ("legacy", 100.0, 0.80, 0.80),
            ("phase63", 110.0, 0.82, 0.82),
        ):
            rows.append(
                {
                    "case_id": case_id,
                    "category": category,
                    "runtime_mode": mode,
                    "ok": True,
                    "expected_tool": expected_tool,
                    "observed_tool_names": expected_tool,
                    "expected_graph_requirement": graph_requirement,
                    "observed_graph_requirement": (
                        graph_requirement if mode == "phase63" else "legacy_term_gate"
                    ),
                    "elapsed_ms": elapsed,
                    "answer_accuracy_score": accuracy,
                    "citation_validity_score": citation,
                    "planner_fallback": planner_fallback and mode == "phase63",
                    "graph_fallback": graph_fallback and mode == "phase63",
                    "reranking_degraded": False,
                    "lexical_backend": "bm25" if mode == "phase63" else "legacy",
                    "vector_backend": "pgvector_hnsw" if mode == "phase63" else "legacy",
                    "vector_degraded": False,
                    "streaming_degraded": False,
                    "counts_match": True,
                }
            )

    add_pair("ordinary", "ordinary", "hybrid_search_knowledge", "disabled")
    add_pair("relation", "explicit_relationship", "hybrid_search_knowledge", "required")
    add_pair("figure", "explicit_figure", "search_figures", "disabled")
    add_pair("table", "explicit_table", "search_tables", "disabled")
    add_pair(
        "planner",
        "planner_failure",
        "hybrid_search_knowledge",
        "disabled",
        planner_fallback=True,
    )
    add_pair(
        "graph-missing",
        "graph_unavailable",
        "hybrid_search_knowledge",
        "required",
        graph_fallback=True,
    )

    summary = gate_summary(rows, executed=True)

    assert summary["validation_mode"] == "dual_runtime_execution"
    assert summary["metrics"]["relationship_route_precision"] == 1.0
    assert summary["metrics"]["relationship_route_recall"] == 1.0
    assert summary["metrics"]["graph_negative_false_positives"] == 0
    assert summary["gates"]["production_retrieval_contract"] is True
    assert summary["gates_passed"] is True

    degraded_rows = [dict(row) for row in rows]
    degraded = next(row for row in degraded_rows if row["runtime_mode"] == "phase63")
    degraded["vector_backend"] = "faiss_fail_open"
    degraded["vector_degraded"] = True

    degraded_summary = gate_summary(degraded_rows, executed=True)

    assert degraded_summary["gates"]["production_retrieval_contract"] is False
    assert degraded_summary["gates_passed"] is False


def test_phase63_execute_requires_real_fault_profile_endpoints(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--out",
            str(tmp_path / "not-written.csv"),
            "--execute",
            "--limit",
            "1",
            "--legacy-base-url",
            "http://127.0.0.1:8100",
            "--phase63-base-url",
            "http://127.0.0.1:8101",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "execute_requires_fault_profile_endpoints" in completed.stdout
