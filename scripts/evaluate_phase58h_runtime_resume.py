from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import yaml

from app.services.agent.runtime_checkpoint import is_explicit_continue
from app.services.retrieval.query_embedding_cache import normalize_query_text


DEFAULT_CASES = Path("data/evaluation/phase58h_runtime_resume_cases.yaml")
DEFAULT_OUT = Path("data/evaluation/phase58h_runtime_resume_eval.csv")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run Phase 58H runtime checkpoint/resume case expectations."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    rows = [evaluate_case(case) for case in cases]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    passed = sum(1 for row in rows if row["status"] == "pass")
    print(f"cases={len(rows)} passed={passed} failed={len(rows) - passed} out={args.out}")


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    return [case for case in cases if isinstance(case, dict)]


def evaluate_case(case: dict[str, Any]) -> dict[str, object]:
    first_query = normalize_query_text(str(case.get("first_query", "")))
    followup_query = normalize_query_text(str(case.get("followup_query", "")))
    expected_resume = bool(case.get("expected_resume"))
    expected_block_reason = str(case.get("expected_block_reason") or "")
    if case.get("checkpoint_expired"):
        actual_resume = False
        reason = "checkpoint_expired"
    elif case.get("checkpoint_corrupted"):
        actual_resume = False
        reason = "checkpoint_invalid"
    elif first_query and followup_query == first_query:
        actual_resume = True
        reason = "exact_retry"
    elif is_explicit_continue(followup_query):
        actual_resume = True
        reason = "explicit_continue"
    else:
        actual_resume = False
        reason = "new_topic"
    status = "pass"
    if actual_resume != expected_resume:
        status = "fail"
    if expected_block_reason and expected_block_reason != reason:
        status = "fail"
    return {
        "case_id": str(case.get("id", "")),
        "category": str(case.get("category", "")),
        "status": status,
        "expected_resume": expected_resume,
        "actual_resume": actual_resume,
        "reason": reason,
        "stop_after_node": str(case.get("stop_after_node", "")),
        "expected_resume_from_node": str(case.get("expected_resume_from_node", "")),
        "expected_skipped_node_count": len(case.get("expected_skipped_nodes", []) or []),
    }


if __name__ == "__main__":
    main()
