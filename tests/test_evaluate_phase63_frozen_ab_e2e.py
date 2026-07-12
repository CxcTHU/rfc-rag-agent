from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.evaluate_phase63_frozen_ab_e2e import (
    AB_OUTPUT_FIELDS,
    build_summary,
    validate_frozen_contract,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_phase63_frozen_ab_e2e.py"


def test_phase63_frozen_ab_script_is_directly_runnable() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "frozen" in completed.stdout


def _row(variant: str, case_id: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "variant": variant,
        "run": 1,
        "case_id": case_id,
        "ok": True,
        "error_category": "",
        "elapsed_ms": 100.0 if variant == "legacy" else 108.0,
        "first_token_ms": 50.0,
        "citation_count": 2,
        "selected_count": 8,
        "live_selected_count": 8,
        "expected_tool": "hybrid_search_knowledge",
        "observed_tool_names": "hybrid_search_knowledge",
        "expected_graph_requirement": "disabled",
        "observed_graph_requirement": "disabled",
        "lexical_backend": "bm25",
        "vector_backend": "pgvector_hnsw",
        "vector_degraded": False,
        "streaming_degraded": False,
        "streamed_token_count": 8,
        "counts_match": True,
        "conversation_persisted": True,
        "snapshot_fingerprint": "same-snapshot",
        "runtime_enabled": variant == "phase63",
    }
    row.update(overrides)
    return row


def test_phase63_frozen_ab_rejects_mismatched_snapshot_or_runtime() -> None:
    legacy = {
        "corpus_fingerprint": "same",
        "document_count": 1,
        "chunk_count": 1,
        "retrieval_runtime_enabled": False,
        "retrieval_runtime_default_enabled": False,
        "pgvector_search_enabled": True,
        "vector_backend_policy": "require_pgvector",
    }
    phase63 = {
        **legacy,
        "corpus_fingerprint": "other",
        "retrieval_runtime_enabled": True,
        "retrieval_runtime_default_enabled": True,
    }

    result = validate_frozen_contract(legacy, phase63)

    assert result["ok"] is False
    assert "snapshot_fingerprint_mismatch" in result["violations"]


def test_phase63_frozen_ab_summary_requires_real_e2e_and_contract_health() -> None:
    rows = [_row("legacy", "text"), _row("phase63", "text")]

    summary = build_summary(rows, frozen_contract={"ok": True, "violations": []})

    assert summary["validation_mode"] == "real_frozen_ab_sse"
    assert summary["paired_case_count"] == 1
    assert summary["metrics"]["completion_rate_delta"] == 0.0
    assert summary["metrics"]["median_latency_delta_ms"] == 8.0
    assert summary["gates_passed"] is True


def test_phase63_frozen_ab_summary_fails_when_new_runtime_regresses_contract() -> None:
    rows = [
        _row("legacy", "text"),
        _row(
            "phase63",
            "text",
            vector_backend="faiss_fail_open",
            vector_degraded=True,
            ok=False,
            error_category="vector_backend_degraded",
        ),
    ]

    summary = build_summary(rows, frozen_contract={"ok": True, "violations": []})

    assert summary["gates"]["phase63_runtime_contract"] is False
    assert summary["gates_passed"] is False


def test_phase63_frozen_ab_output_schema_never_persists_answer_content() -> None:
    forbidden = {"answer", "content", "raw_response", "reasoning", "source_content"}

    assert forbidden.isdisjoint(AB_OUTPUT_FIELDS)
