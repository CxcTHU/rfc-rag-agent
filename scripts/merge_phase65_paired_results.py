"""Merge safe Phase 65 baseline/candidate result projections.

This helper exists so Phase 65 can reuse an already verified baseline lane
without re-running it.  It only reads/writes the safe evaluator CSV projection;
it never accepts or persists prompts, answers, chunks, provider payloads, or
credentials.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_phase65_agent_gate import PHASE65_OUTPUT_FIELDS, validate_output_path


def merge_paired_results(
    *,
    baseline_results: Path,
    candidate_results: Path,
    out: Path,
) -> dict[str, object]:
    baseline_rows = _read_safe_rows(baseline_results, expected_variant="baseline")
    candidate_rows = _read_safe_rows(candidate_results, expected_variant="candidate")
    baseline_by_key = _index_by_case_run(baseline_rows)
    candidate_by_key = _index_by_case_run(candidate_rows)
    if set(baseline_by_key) != set(candidate_by_key):
        raise ValueError("paired_result_case_run_mismatch")

    merged: list[Mapping[str, object]] = []
    for key in sorted(baseline_by_key):
        merged.append(baseline_by_key[key])
        merged.append(candidate_by_key[key])
    _write_safe_rows(validate_output_path(out), merged)
    pair_count = len(baseline_by_key)
    return {
        "schema_version": "phase65-paired-results-merge-v1",
        "gate": "pass",
        "pair_count": pair_count,
        "baseline_rows": len(baseline_rows),
        "candidate_rows": len(candidate_rows),
    }


def _read_safe_rows(path: Path, *, expected_variant: str) -> list[dict[str, str]]:
    source = validate_output_path(path)
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != PHASE65_OUTPUT_FIELDS:
            raise ValueError("paired_result_unsafe_fields")
        rows = [{field: str(row.get(field, "")) for field in PHASE65_OUTPUT_FIELDS} for row in reader]
    for row in rows:
        if row.get("variant") != expected_variant:
            raise ValueError("paired_result_variant_mismatch")
        _case_run_key(row)
    return rows


def _index_by_case_run(rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, int], Mapping[str, str]]:
    indexed: dict[tuple[str, int], Mapping[str, str]] = {}
    for row in rows:
        key = _case_run_key(row)
        if key in indexed:
            raise ValueError("paired_result_duplicate_case_run")
        indexed[key] = row
    return indexed


def _case_run_key(row: Mapping[str, str]) -> tuple[str, int]:
    case_id = str(row.get("case_id", "")).strip()
    try:
        run = int(str(row.get("run", "")).strip())
    except ValueError as exc:
        raise ValueError("paired_result_invalid_case_run") from exc
    if not case_id or run < 1:
        raise ValueError("paired_result_invalid_case_run")
    return (case_id, run)


def _write_safe_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        dir=path.parent,
        delete=False,
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=PHASE65_OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in PHASE65_OUTPUT_FIELDS} for row in rows)
        temporary = Path(stream.name)
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge safe Phase 65 paired result CSVs.")
    parser.add_argument("--baseline-results", type=Path, required=True)
    parser.add_argument("--candidate-results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = merge_paired_results(
            baseline_results=args.baseline_results,
            candidate_results=args.candidate_results,
            out=args.out,
        )
    except (OSError, ValueError) as exc:
        detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        print(json.dumps({"error": "phase65_merge_blocked", "reason": detail}, ensure_ascii=False))
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
