from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import yaml

from app.services.agent.evidence_identity import build_evidence_query_identity


DEFAULT_CASES = Path("data/evaluation/phase58h_cache_canonicalization_cases.yaml")
DEFAULT_OUT = Path("data/evaluation/phase58h_cache_hit_eval.csv")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Phase 58H evidence cache canonicalization cases."
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
    history = [
        str(item.get("content", ""))
        for item in case.get("history", [])
        if isinstance(item, dict)
    ]
    first = build_evidence_query_identity(str(case.get("q1", "")), history=history)
    second = build_evidence_query_identity(str(case.get("q2", "")), history=history)
    same_identity = (
        first.safe_for_cache_reuse
        and second.safe_for_cache_reuse
        and first.entity_key == second.entity_key
        and first.intent_key == second.intent_key
        and first.canonical_query == second.canonical_query
    )
    expected_same = bool(case.get("expected_same_identity"))
    expected_entity = str(case.get("expected_entity") or case.get("expected_entity_q1") or "")
    expected_intent = str(case.get("expected_intent") or case.get("expected_intent_q1") or "")
    status = "pass"
    if same_identity != expected_same:
        status = "fail"
    if expected_entity and first.entity_key != expected_entity:
        status = "fail"
    if expected_intent and first.intent_key != expected_intent:
        status = "fail"
    return {
        "case_id": str(case.get("id", "")),
        "category": str(case.get("category", "")),
        "status": status,
        "expected_same_identity": expected_same,
        "actual_same_identity": same_identity,
        "q1_entity_key": first.entity_key,
        "q1_intent_key": first.intent_key,
        "q2_entity_key": second.entity_key,
        "q2_intent_key": second.intent_key,
        "q1_safe": first.safe_for_cache_reuse,
        "q2_safe": second.safe_for_cache_reuse,
        "q1_reason": first.reason,
        "q2_reason": second.reason,
        "canonical_query_hash": stable_short_hash(first.canonical_query if same_identity else ""),
    }


def stable_short_hash(text: str) -> str:
    import hashlib

    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


if __name__ == "__main__":
    main()
