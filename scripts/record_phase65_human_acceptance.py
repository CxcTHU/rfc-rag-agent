"""Record a safe Phase 65 human acceptance decision.

The recorder never decides acceptance by itself.  It only turns an explicit
reviewer pass/fail decision into a bounded receipt.  A pass decision is rejected
while any non-human release gate remains open in the referenced acceptance
packet.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.summarize_phase65_acceptance import (
    _load_json,
    _safe_json_sha256,
    _write_json,
)

HUMAN_FAILURE_REASONS = {
    "human_acceptance_missing",
    "human_acceptance_not_pass",
}


def record_human_acceptance(
    *,
    acceptance_packet: Mapping[str, object],
    current_acceptance_summary: Mapping[str, object] | None = None,
    decision: str,
    reviewer_label: str,
    checklist_confirmed: bool,
) -> dict[str, object]:
    if decision not in {"pass", "fail"}:
        raise ValueError("invalid_human_acceptance_decision")
    if not isinstance(reviewer_label, str) or not reviewer_label:
        raise ValueError("reviewer_label_required")
    if checklist_confirmed is not True:
        raise ValueError("review_checklist_not_confirmed")
    packet_summary = acceptance_packet.get("human_acceptance_summary")
    if not isinstance(packet_summary, Mapping):
        raise ValueError("invalid_human_acceptance_packet")
    if packet_summary.get("schema_version") != "phase65-human-acceptance-summary-v1":
        raise ValueError("invalid_human_acceptance_packet")
    failed_required = packet_summary.get("failed_required")
    if not isinstance(failed_required, list) or not all(
        isinstance(item, str) for item in failed_required
    ):
        raise ValueError("invalid_human_acceptance_packet")
    open_non_human = [
        item for item in failed_required if item not in HUMAN_FAILURE_REASONS
    ]
    if decision == "pass" and open_non_human:
        raise ValueError("cannot_pass_with_open_non_human_gates")
    acceptance_summary_sha256 = packet_summary.get("acceptance_summary_sha256")
    if not isinstance(acceptance_summary_sha256, str) or not acceptance_summary_sha256:
        raise ValueError("invalid_human_acceptance_packet")
    if decision == "pass":
        if current_acceptance_summary is None:
            raise ValueError("current_acceptance_summary_required")
        if (
            current_acceptance_summary.get("schema_version")
            != "phase65-acceptance-summary-v1"
        ):
            raise ValueError("invalid_current_acceptance_summary")
        if _safe_json_sha256(current_acceptance_summary) != acceptance_summary_sha256:
            raise ValueError("human_acceptance_summary_mismatch")
    gate = "pass" if decision == "pass" else "blocked"
    status = "accepted" if decision == "pass" else "rejected"
    return {
        "schema_version": "phase65-human-acceptance-record-v1",
        "gate": gate,
        "human_acceptance_summary": {
            "schema_version": "phase65-human-acceptance-summary-v1",
            "gate": gate,
            "status": status,
            "reviewer_label": reviewer_label,
            "acceptance_summary_sha256": acceptance_summary_sha256,
            "review_checklist_confirmed": True,
            "decision": decision,
            "open_non_human_gate_count": len(open_non_human),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record a safe explicit Phase 65 human acceptance decision."
    )
    parser.add_argument("--acceptance-packet", type=Path, required=True)
    parser.add_argument("--current-acceptance-summary", type=Path)
    parser.add_argument("--decision", choices=("pass", "fail"), required=True)
    parser.add_argument("--reviewer-label", default="user")
    parser.add_argument(
        "--confirm-checklist",
        action="store_true",
        help="Required: confirms the reviewer completed the packet checklist.",
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        packet = _load_json(args.acceptance_packet)
        if packet is None:
            raise ValueError("human_acceptance_packet_required")
        current_summary = (
            _load_json(args.current_acceptance_summary)
            if args.current_acceptance_summary
            else None
        )
        record = record_human_acceptance(
            acceptance_packet=packet,
            current_acceptance_summary=current_summary,
            decision=args.decision,
            reviewer_label=args.reviewer_label,
            checklist_confirmed=args.confirm_checklist,
        )
    except ValueError as exc:
        error = {
            "schema_version": "phase65-human-acceptance-record-v1",
            "gate": "blocked",
            "error_category": str(exc),
        }
        print(json.dumps(error, ensure_ascii=False, sort_keys=True))
        return 1
    _write_json(args.out, record)
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return 0 if record["gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
