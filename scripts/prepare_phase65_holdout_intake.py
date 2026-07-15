"""Prepare and validate Phase 65 private reviewer-holdout case intake.

The generated template is intentionally header-only so it cannot accidentally be
used as executable holdout evidence.  Real private holdout cases must be filled
by the reviewer/operator and then validated before running the A/B holdout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.summarize_phase65_acceptance import _write_json

HOLDOUT_TEMPLATE_FIELDS = (
    "case_id",
    "category",
    "question",
    "expected_tool",
    "expected_graph_requirement",
    "reviewer_notes",
)
DEFAULT_TARGET_CASES_PATH = Path("data/evaluation/phase65_private_holdout_cases.csv")
DEFAULT_EXCLUDED_CASES_PATH = Path("data/evaluation/phase64_latency_cases.csv")
_SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


def write_holdout_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HOLDOUT_TEMPLATE_FIELDS)


def build_holdout_intake_packet(
    *,
    template_path: Path,
    target_cases_path: Path = DEFAULT_TARGET_CASES_PATH,
    excluded_cases_path: Path = DEFAULT_EXCLUDED_CASES_PATH,
    expected_min_cases: int = 12,
) -> dict[str, object]:
    if expected_min_cases <= 0:
        raise ValueError("expected_min_cases_invalid")
    return {
        "schema_version": "phase65-holdout-intake-v1",
        "gate": "blocked",
        "template_path": _safe_path_label(template_path),
        "target_cases_path": _safe_path_label(target_cases_path),
        "excluded_cases_path": _safe_path_label(excluded_cases_path),
        "public_overlap_guard": True,
        "required_columns": list(HOLDOUT_TEMPLATE_FIELDS),
        "expected_min_cases": expected_min_cases,
        "template_is_executable": False,
        "next_required_actions": [
            "copy the template to the target private holdout case path and fill at least twelve unique reviewer cases",
            "validate the completed private holdout cases before running holdout A/B with blind judge",
        ],
        "run_holdout_command": (
            ".venv\\Scripts\\python.exe scripts\\evaluate_phase65_agent_gate.py "
            "--mode holdout --execute --execute-blind-judge "
            "--holdout-cases data\\evaluation\\phase65_private_holdout_cases.csv "
            "--baseline-base-url <baseline-url> --candidate-base-url <candidate-url> "
            "--out output\\phase65\\holdout-results.csv "
            "--judge-out output\\phase65\\holdout-judge.csv "
            "--summary-out output\\phase65\\holdout-summary.json"
        ),
    }


def validate_private_holdout_cases(
    path: Path,
    *,
    expected_min_cases: int = 12,
    exclude_cases_path: Path | None = None,
) -> dict[str, object]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    case_ids = [str(row.get("case_id", "")).strip() for row in rows]
    if (
        len(rows) < expected_min_cases
        or len(set(case_ids)) != len(case_ids)
        or any(not _SAFE_CASE_ID.fullmatch(case_id) for case_id in case_ids)
    ):
        raise ValueError("holdout_requires_twelve_unique_cases")
    missing_question = [
        case_id
        for case_id, row in zip(case_ids, rows, strict=True)
        if not str(row.get("question", "")).strip()
    ]
    if missing_question:
        raise ValueError("holdout_question_required")
    excluded_case_ids = _load_case_ids(exclude_cases_path) if exclude_cases_path else set()
    if excluded_case_ids.intersection(case_ids):
        raise ValueError("holdout_overlaps_excluded_cases")
    case_set_sha256 = hashlib.sha256(
        "\n".join(sorted(case_ids)).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "phase65-holdout-intake-validation-v1",
        "gate": "pass",
        "ready_to_run_holdout": True,
        "holdout_case_count": len(rows),
        "holdout_case_set_sha256": case_set_sha256,
        "excluded_case_overlap_count": 0,
        "required_columns": list(HOLDOUT_TEMPLATE_FIELDS),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare or validate Phase 65 private holdout case intake."
    )
    parser.add_argument("--template-out", type=Path)
    parser.add_argument("--target-cases", type=Path, default=DEFAULT_TARGET_CASES_PATH)
    parser.add_argument("--validate-cases", type=Path)
    parser.add_argument(
        "--exclude-cases",
        type=Path,
        default=DEFAULT_EXCLUDED_CASES_PATH,
        help="Public/frozen case CSV whose case_id values must not overlap private holdout cases.",
    )
    parser.add_argument("--summary-out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.validate_cases is not None:
        try:
            payload = validate_private_holdout_cases(
                args.validate_cases,
                exclude_cases_path=args.exclude_cases if args.exclude_cases.exists() else None,
            )
        except ValueError as exc:
            payload = {
                "schema_version": "phase65-holdout-intake-validation-v1",
                "gate": "blocked",
                "error_category": str(exc),
            }
            _write_json(args.summary_out, payload)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return 1
        _write_json(args.summary_out, payload)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if args.template_out is None:
        raise ValueError("template_out_required")
    write_holdout_template(args.template_out)
    payload = build_holdout_intake_packet(
        template_path=args.template_out,
        target_cases_path=args.target_cases,
        excluded_cases_path=args.exclude_cases,
    )
    _write_json(args.summary_out, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 1


def _safe_path_label(path: Path) -> str:
    return str(path).replace("/", "\\")


def _load_case_ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {
            str(row.get("case_id", "")).strip()
            for row in csv.DictReader(stream)
            if str(row.get("case_id", "")).strip()
        }


if __name__ == "__main__":
    raise SystemExit(main())
