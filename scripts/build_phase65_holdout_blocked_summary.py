"""Build a safe blocked Phase 65 reviewer-holdout receipt.

This is used when the private reviewer holdout set is unavailable.  It records
the missing evidence as an explicit blocked receipt so acceptance summaries can
distinguish "not run / blocked" from "no holdout artifact was provided".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.summarize_phase65_acceptance import _write_json


def build_holdout_blocked_summary(
    *,
    reason: str,
    expected_min_cases: int = 12,
) -> dict[str, object]:
    if not isinstance(reason, str) or not reason:
        raise ValueError("holdout_blocked_reason_required")
    if not isinstance(expected_min_cases, int) or expected_min_cases <= 0:
        raise ValueError("expected_min_cases_invalid")
    failed_required = [reason]
    fingerprint = hashlib.sha256(f"missing-holdout:{reason}".encode("utf-8")).hexdigest()
    return {
        "schema_version": "phase65-holdout-blocked-summary-v1",
        "gate": "blocked",
        "failed_required": failed_required,
        "next_required_actions": [
            "provide a private reviewer holdout case set and run baseline/candidate A/B holdout with blind judge"
        ],
        "holdout_summary": {
            "clean": False,
            "holdout_case_count": 0,
            "holdout_case_set_sha256": fingerprint,
            "tuning_exclusion_proven": False,
            "primary_latency_percentile_ci_exclusion_proven": False,
            "expected_min_cases": expected_min_cases,
            "safe_projection_only": True,
            "failed_required": failed_required,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a safe blocked Phase 65 reviewer-holdout receipt."
    )
    parser.add_argument("--reason", default="private_holdout_cases_missing")
    parser.add_argument("--expected-min-cases", type=int, default=12)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_holdout_blocked_summary(
        reason=args.reason,
        expected_min_cases=args.expected_min_cases,
    )
    _write_json(args.out, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
