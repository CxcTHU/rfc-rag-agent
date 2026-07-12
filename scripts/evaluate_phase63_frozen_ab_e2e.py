from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_phase63_e2e import execute_case, select_cases


DEFAULT_CASES = ROOT / "data" / "evaluation" / "phase63_e2e_cases.csv"
AB_OUTPUT_FIELDS = (
    "variant",
    "run",
    "case_id",
    "category",
    "ok",
    "error_category",
    "http_status",
    "expected_tool",
    "observed_tool_names",
    "expected_graph_requirement",
    "observed_graph_requirement",
    "citation_count",
    "selected_count",
    "live_selected_count",
    "lexical_backend",
    "vector_backend",
    "vector_degraded",
    "streaming_degraded",
    "streamed_token_count",
    "counts_match",
    "first_token_ms",
    "elapsed_ms",
    "conversation_persisted",
    "snapshot_fingerprint",
    "runtime_enabled",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a safe, real-provider frozen Phase 63 A/B SSE evaluation."
    )
    parser.add_argument("--legacy-base-url", required=True)
    parser.add_argument("--phase63-base-url", required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--case-id", default="")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--token", default="")
    parser.add_argument("--keep-conversations", action="store_true")
    parser.add_argument("--enforce-gates", action="store_true")
    return parser.parse_args()


def request_json(url: str, *, token: str, timeout_seconds: float) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    call = request.Request(url, headers=headers, method="GET")
    with request.urlopen(call, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def fetch_retrieval_contract(
    base_url: str, *, token: str, timeout_seconds: float
) -> dict[str, Any]:
    return request_json(
        f"{base_url.rstrip('/')}/health/retrieval-contract",
        token=token,
        timeout_seconds=timeout_seconds,
    )


def validate_frozen_contract(
    legacy: dict[str, Any], phase63: dict[str, Any]
) -> dict[str, object]:
    violations: list[str] = []
    if not legacy or not phase63:
        violations.append("missing_retrieval_contract")
    if legacy.get("corpus_fingerprint") != phase63.get("corpus_fingerprint"):
        violations.append("snapshot_fingerprint_mismatch")
    if legacy.get("document_count") != phase63.get("document_count"):
        violations.append("document_count_mismatch")
    if legacy.get("chunk_count") != phase63.get("chunk_count"):
        violations.append("chunk_count_mismatch")
    if legacy.get("retrieval_runtime_enabled") is not False:
        violations.append("legacy_runtime_not_disabled")
    if phase63.get("retrieval_runtime_enabled") is not True:
        violations.append("phase63_runtime_not_enabled")
    if phase63.get("retrieval_runtime_default_enabled") is not True:
        violations.append("phase63_runtime_default_not_enabled")
    for name, contract in (("legacy", legacy), ("phase63", phase63)):
        if contract.get("pgvector_search_enabled") is not True:
            violations.append(f"{name}_pgvector_not_enabled")
        if contract.get("vector_backend_policy") != "require_pgvector":
            violations.append(f"{name}_vector_policy_not_strict")
    return {"ok": not violations, "violations": violations}


def float_values(rows: list[dict[str, object]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        try:
            value = float(row.get(field, ""))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def rate(rows: list[dict[str, object]], predicate) -> float:
    return round(sum(1 for row in rows if predicate(row)) / len(rows), 4) if rows else 0.0


def contract_row_ok(row: dict[str, object]) -> bool:
    expected_tool = str(row.get("expected_tool", ""))
    lexical_ok = expected_tool != "hybrid_search_knowledge" or row.get("lexical_backend") == "bm25"
    return bool(
        row.get("ok")
        and lexical_ok
        and row.get("vector_backend") == "pgvector_hnsw"
        and not bool(row.get("vector_degraded"))
        and not bool(row.get("streaming_degraded"))
        and bool(row.get("counts_match"))
        and bool(row.get("conversation_persisted"))
    )


def build_summary(
    rows: list[dict[str, object]], *, frozen_contract: dict[str, object]
) -> dict[str, object]:
    legacy = [row for row in rows if row.get("variant") == "legacy"]
    phase63 = [row for row in rows if row.get("variant") == "phase63"]
    legacy_success = rate(legacy, lambda row: bool(row.get("ok")))
    phase63_success = rate(phase63, lambda row: bool(row.get("ok")))
    legacy_contract = rate(legacy, contract_row_ok)
    phase63_contract = rate(phase63, contract_row_ok)
    legacy_latency = median(float_values(legacy, "elapsed_ms"))
    phase63_latency = median(float_values(phase63, "elapsed_ms"))
    latency_delta = (
        round(phase63_latency - legacy_latency, 3)
        if legacy_latency is not None and phase63_latency is not None
        else None
    )
    latency_ratio = (
        round(phase63_latency / legacy_latency - 1, 4)
        if legacy_latency and phase63_latency is not None
        else None
    )
    explicit = {"figure", "table", "relationship"}
    legacy_explicit = [row for row in legacy if row.get("category") in explicit]
    phase63_explicit = [row for row in phase63 if row.get("category") in explicit]
    legacy_explicit_success = rate(legacy_explicit, lambda row: bool(row.get("ok")))
    phase63_explicit_success = rate(phase63_explicit, lambda row: bool(row.get("ok")))
    metrics = {
        "legacy_completion_rate": legacy_success,
        "phase63_completion_rate": phase63_success,
        "completion_rate_delta": round(phase63_success - legacy_success, 4),
        "legacy_runtime_contract_rate": legacy_contract,
        "phase63_runtime_contract_rate": phase63_contract,
        "legacy_explicit_route_rate": legacy_explicit_success,
        "phase63_explicit_route_rate": phase63_explicit_success,
        "explicit_route_rate_delta": round(
            phase63_explicit_success - legacy_explicit_success, 4
        ),
        "legacy_median_elapsed_ms": legacy_latency,
        "phase63_median_elapsed_ms": phase63_latency,
        "median_latency_delta_ms": latency_delta,
        "median_latency_relative_delta": latency_ratio,
    }
    substantive_gain = (
        metrics["completion_rate_delta"] > 0
        or metrics["explicit_route_rate_delta"] > 0
    )
    gates = {
        "frozen_contract": bool(frozen_contract.get("ok")),
        "paired_real_e2e_rows": bool(legacy and phase63) and len(legacy) == len(phase63),
        "phase63_runtime_contract": phase63_contract == 1.0,
        "completion_non_regression": phase63_success >= legacy_success,
        "explicit_route_non_regression": phase63_explicit_success >= legacy_explicit_success,
        "median_latency_budget": latency_ratio is not None and latency_ratio <= 0.15,
    }
    return {
        "validation_mode": "real_frozen_ab_sse",
        "paired_case_count": min(len(legacy), len(phase63)),
        "frozen_contract": frozen_contract,
        "metrics": metrics,
        "gates": gates,
        "gates_passed": all(gates.values()),
        "upgrade_evidenced": substantive_gain,
    }


def run_case(
    case: dict[str, str],
    *,
    variant: str,
    run: int,
    base_url: str,
    contract: dict[str, Any],
    token: str,
    timeout_seconds: float,
    keep_conversations: bool,
) -> dict[str, object]:
    result = execute_case(
        case,
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
        keep_conversation=keep_conversations,
    )
    return {
        "variant": variant,
        "run": run,
        **result,
        "snapshot_fingerprint": str(contract.get("corpus_fingerprint", "")),
        "runtime_enabled": bool(contract.get("retrieval_runtime_enabled", False)),
    }


def main() -> int:
    args = parse_args()
    if args.legacy_base_url.rstrip("/") == args.phase63_base_url.rstrip("/"):
        print(json.dumps({"error": "distinct_endpoints_required"}, ensure_ascii=False))
        return 2
    if args.runs < 1:
        print(json.dumps({"error": "runs_must_be_positive"}, ensure_ascii=False))
        return 2
    try:
        legacy_contract = fetch_retrieval_contract(
            args.legacy_base_url, token=args.token, timeout_seconds=args.timeout_seconds
        )
        phase63_contract = fetch_retrieval_contract(
            args.phase63_base_url, token=args.token, timeout_seconds=args.timeout_seconds
        )
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
        print(json.dumps({"error": "retrieval_contract_unavailable"}, ensure_ascii=False))
        return 2
    frozen_contract = validate_frozen_contract(legacy_contract, phase63_contract)
    if not frozen_contract["ok"]:
        print(json.dumps({"error": "frozen_contract_invalid", **frozen_contract}, ensure_ascii=False))
        return 2
    with args.cases.open(encoding="utf-8-sig", newline="") as stream:
        cases = select_cases(list(csv.DictReader(stream)), case_id=args.case_id, limit=args.limit)
    rows: list[dict[str, object]] = []
    # Alternate first variant by run to avoid an ordering advantage while keeping the run deterministic.
    for run in range(1, args.runs + 1):
        variants = (
            (("legacy", args.legacy_base_url, legacy_contract), ("phase63", args.phase63_base_url, phase63_contract))
            if run % 2
            else (("phase63", args.phase63_base_url, phase63_contract), ("legacy", args.legacy_base_url, legacy_contract))
        )
        for case in cases:
            for variant, base_url, contract in variants:
                rows.append(
                    run_case(
                        case,
                        variant=variant,
                        run=run,
                        base_url=base_url,
                        contract=contract,
                        token=args.token,
                        timeout_seconds=args.timeout_seconds,
                        keep_conversations=args.keep_conversations,
                    )
                )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=AB_OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in AB_OUTPUT_FIELDS} for row in rows)
    summary = build_summary(rows, frozen_contract=frozen_contract)
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if not args.enforce_gates or bool(summary["gates_passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
