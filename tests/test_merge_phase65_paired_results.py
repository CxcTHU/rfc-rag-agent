from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.evaluate_phase65_agent_gate import PHASE65_OUTPUT_FIELDS
import scripts.merge_phase65_paired_results as merger
from scripts.merge_phase65_paired_results import merge_paired_results


def _row(*, variant: str, case_id: str, run: int) -> dict[str, object]:
    row = {field: "" for field in PHASE65_OUTPUT_FIELDS}
    row.update(
        {
            "variant": variant,
            "run": run,
            "case_id": case_id,
            "category": "ordinary_text",
            "ok": "True",
            "error_category": "",
            "http_status": "200",
            "first_token_ms": "1000",
            "elapsed_ms": "2000",
            "cold_cache_receipt_status": "valid",
            "completed_tool_replay_count": "0",
        }
    )
    return row


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PHASE65_OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_merge_paired_results_keeps_only_safe_projection(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(merger, "validate_output_path", lambda path: path)
    baseline = tmp_path / "baseline.csv"
    candidate = tmp_path / "candidate.csv"
    out = tmp_path / "paired.csv"
    _write_csv(
        baseline,
        [_row(variant="baseline", case_id="case-2", run=1), _row(variant="baseline", case_id="case-1", run=1)],
    )
    _write_csv(
        candidate,
        [_row(variant="candidate", case_id="case-1", run=1), _row(variant="candidate", case_id="case-2", run=1)],
    )

    summary = merge_paired_results(
        baseline_results=baseline,
        candidate_results=candidate,
        out=out,
    )

    rows = _read_rows(out)
    assert summary == {
        "schema_version": "phase65-paired-results-merge-v1",
        "gate": "pass",
        "pair_count": 2,
        "baseline_rows": 2,
        "candidate_rows": 2,
    }
    assert [row["variant"] for row in rows] == ["baseline", "candidate", "baseline", "candidate"]
    assert [row["case_id"] for row in rows] == ["case-1", "case-1", "case-2", "case-2"]
    assert set(rows[0]) == set(PHASE65_OUTPUT_FIELDS)
    serialized = json.dumps(rows).casefold()
    assert "answer" not in serialized
    assert "raw_response" not in serialized


def test_merge_paired_results_blocks_mismatched_case_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(merger, "validate_output_path", lambda path: path)
    baseline = tmp_path / "baseline.csv"
    candidate = tmp_path / "candidate.csv"
    out = tmp_path / "paired.csv"
    _write_csv(baseline, [_row(variant="baseline", case_id="case-1", run=1)])
    _write_csv(candidate, [_row(variant="candidate", case_id="case-2", run=1)])

    with pytest.raises(ValueError, match="paired_result_case_run_mismatch"):
        merge_paired_results(
            baseline_results=baseline,
            candidate_results=candidate,
            out=out,
        )


def test_merge_paired_results_blocks_wrong_variant(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(merger, "validate_output_path", lambda path: path)
    baseline = tmp_path / "baseline.csv"
    candidate = tmp_path / "candidate.csv"
    out = tmp_path / "paired.csv"
    _write_csv(baseline, [_row(variant="candidate", case_id="case-1", run=1)])
    _write_csv(candidate, [_row(variant="candidate", case_id="case-1", run=1)])

    with pytest.raises(ValueError, match="paired_result_variant_mismatch"):
        merge_paired_results(
            baseline_results=baseline,
            candidate_results=candidate,
            out=out,
        )
