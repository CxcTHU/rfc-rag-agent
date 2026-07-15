"""Build a safe Phase 65 baseline-reuse waiver artifact.

This script emits only bounded receipt metadata.  It never stores prompts,
answers, retrieved chunks, provider payloads, or credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.summarize_phase65_acceptance import (
    _load_csv_rows,
    _load_json,
    _write_json,
    build_baseline_reuse_waiver,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed Phase 65 baseline-reuse waiver."
    )
    parser.add_argument("--paired-summary", type=Path, required=True)
    parser.add_argument("--paired-results", type=Path, required=True)
    parser.add_argument("--expected-pair-count", type=int, default=30)
    parser.add_argument(
        "--user-authorized-baseline-reuse",
        action="store_true",
        help="Required explicit authorization that the completed baseline may be reused.",
    )
    parser.add_argument(
        "--scope",
        default="phase65_candidate_targeted_followup_repair_only",
        help="Safe, non-secret human-readable waiver scope.",
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    waiver = build_baseline_reuse_waiver(
        paired_summary=_load_json(args.paired_summary),
        paired_rows=_load_csv_rows(args.paired_results),
        user_authorized_baseline_reuse=args.user_authorized_baseline_reuse,
        expected_pair_count=args.expected_pair_count,
        scope=args.scope,
    )
    _write_json(args.out, waiver)
    print(json.dumps(waiver, ensure_ascii=False, sort_keys=True))
    return 0 if waiver["gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
