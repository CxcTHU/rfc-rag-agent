"""Build a safe Phase 65 human-acceptance review packet.

The packet is a review aid, not a substitute for the user's decision.  It
contains gate labels, required actions, and evidence pointers only; it must not
store prompts, answers, evidence text, provider payloads, credentials, or raw
logs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.summarize_phase65_acceptance import _load_json, _write_json


DEFAULT_REVIEW_CHECKLIST = (
    "confirm_phase65_acceptance_summary_matches_visible_gate_state",
    "review_baseline_reuse_waiver_scope_and_limitations",
    "confirm_reviewer_holdout_status_is_understood",
    "exercise_primary_agent_ui_or_api_flow",
    "confirm_no_sensitive_payloads_are_present_in_safe_artifacts",
)


def build_human_acceptance_packet(
    *,
    acceptance_summary: Mapping[str, object],
    reviewer_label: str,
) -> dict[str, object]:
    if acceptance_summary.get("schema_version") != "phase65-acceptance-summary-v1":
        raise ValueError("invalid_acceptance_summary")
    if not isinstance(reviewer_label, str) or not reviewer_label:
        raise ValueError("reviewer_label_required")
    components = acceptance_summary.get("components")
    if not isinstance(components, Mapping):
        raise ValueError("invalid_acceptance_summary")
    failed_required = acceptance_summary.get("failed_required")
    if not isinstance(failed_required, list) or not all(
        isinstance(item, str) for item in failed_required
    ):
        raise ValueError("invalid_acceptance_summary")
    digest = _safe_json_sha256(acceptance_summary)
    return {
        "schema_version": "phase65-human-acceptance-packet-v1",
        "gate": "blocked",
        "human_acceptance_summary": {
            "schema_version": "phase65-human-acceptance-summary-v1",
            "gate": "blocked",
            "status": "pending_user_review",
            "reviewer_label": reviewer_label,
            "acceptance_summary_sha256": digest,
            "acceptance_gate": acceptance_summary.get("gate"),
            "failed_required": list(failed_required),
            "review_checklist": list(DEFAULT_REVIEW_CHECKLIST),
            "reviewer_action_required": True,
        },
        "next_required_actions": [
            "review the Phase 65 acceptance summary, exercise the UI/API, and explicitly record pass or fail"
        ],
    }


def _safe_json_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a safe Phase 65 human-acceptance review packet."
    )
    parser.add_argument("--acceptance-summary", type=Path, required=True)
    parser.add_argument("--reviewer-label", default="user")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = _load_json(args.acceptance_summary)
    if summary is None:
        raise ValueError("acceptance_summary_required")
    packet = build_human_acceptance_packet(
        acceptance_summary=summary,
        reviewer_label=args.reviewer_label,
    )
    _write_json(args.out, packet)
    print(json.dumps(packet, ensure_ascii=False, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
