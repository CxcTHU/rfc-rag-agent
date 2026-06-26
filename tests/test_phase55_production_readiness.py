from pathlib import Path

from scripts.audit_phase55_production_readiness import (
    FIELDS,
    build_audit_rows,
    summarize,
    write_csv,
)


def test_phase55_audit_covers_required_areas() -> None:
    rows = build_audit_rows(Path("."))
    rows_by_id = {row.requirement_id: row for row in rows}

    assert rows_by_id["compose_auth_enabled"].status == "complete"
    assert rows_by_id["compose_pgvector_redis"].status == "complete"
    assert rows_by_id["bge_cpu_to_gpu_topology"].status == "complete"
    assert rows_by_id["auth_enabled_smoke_script"].status == "complete"
    assert rows_by_id["backup_restore_runbook"].status == "complete"
    assert rows_by_id["server_runtime_smoke"].status == "manual_required"


def test_phase55_audit_summary_keeps_manual_runtime_separate() -> None:
    rows = build_audit_rows(Path("."))
    summary = summarize(rows)

    assert summary["complete"] >= 8
    assert summary["manual_required"] == 1
    assert summary["partial"] == 0


def test_phase55_audit_csv_is_sanitized(tmp_path: Path) -> None:
    output = tmp_path / "phase55.csv"

    write_csv(output, build_audit_rows(Path(".")))
    content = output.read_text(encoding="utf-8")

    assert ",".join(FIELDS) in content
    assert "sk-" not in content
    assert "Bearer " not in content
    assert "Authorization:" not in content
    assert "raw_response" not in content
    assert "reasoning_content" not in content
