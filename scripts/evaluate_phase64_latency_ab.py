from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_phase63_e2e import execute_case, select_cases
from scripts.judge_phase64_latency_ab import (
    JUDGE_OUTPUT_FIELDS,
    judge_blind_pair,
    summarize_judge_rows,
)


DEFAULT_CASES = ROOT / "data" / "evaluation" / "phase64_latency_cases.csv"
PHASE63_CHAT_MODEL = "deepseek-v4-pro"
PHASE64_CHAT_MODEL = "deepseek-v4-flash"
PHASE64_OUTPUT_FIELDS = (
    "variant",
    "run",
    "case_id",
    "category",
    "ok",
    "error_category",
    "requested_chat_model",
    "observed_chat_model",
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
    "conversation_persisted",
    "first_token_ms",
    "elapsed_ms",
    "retrieval_total_latency_ms",
    "glm_rerank_latency_ms",
    "planner_call_count",
    "final_generation_call_count",
    "final_model_ttft_ms",
    "provider_http_latency_ms",
    "provider_http_request_count",
    "provider_http_reused_connection_count",
    "provider_http_last_connection_reused",
    "citation_repair_count",
    "citation_repair_latency_ms",
    "phase64_execution_graph",
    "phase64_route_kind",
    "phase64_route_reason",
    "agent_short_loop_enabled",
    "reranking_provider",
    "reranking_model_name",
    "retrieval_candidate_cache_enabled",
    "rerank_order_cache_enabled",
    "tool_result_cache_enabled",
    "semantic_evidence_cache_enabled",
    "snapshot_fingerprint",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a safe frozen Phase 63 versus Phase 64 latency A/B SSE evaluation."
    )
    parser.add_argument("--phase63-base-url", required=True)
    parser.add_argument("--phase64-base-url", required=True)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=640013)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--case-id", default="")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--token", default="")
    parser.add_argument("--keep-conversations", action="store_true")
    parser.add_argument("--execute-blind-judge", action="store_true")
    parser.add_argument("--judge-out", type=Path)
    parser.add_argument("--enforce-gates", action="store_true")
    return parser.parse_args()


def deterministic_pair_order(case_id: str, run: int, seed: int) -> tuple[str, str]:
    digest = hashlib.sha256(f"{seed}:{case_id}:{run}".encode("utf-8")).digest()
    return ("phase63", "phase64") if digest[0] % 2 == 0 else ("phase64", "phase63")


def selected_chat_model_for_variant(variant: str) -> str:
    """Return the frozen user-visible model selection for one A/B lane."""
    if variant == "phase63":
        return PHASE63_CHAT_MODEL
    if variant == "phase64":
        return PHASE64_CHAT_MODEL
    raise ValueError(f"unknown_phase64_variant:{variant}")


def percentile(values: Sequence[float], q: float) -> float | None:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return round(ordered[index], 3)


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
    phase63: dict[str, Any], phase64: dict[str, Any]
) -> dict[str, object]:
    violations: list[str] = []
    if not phase63 or not phase64:
        violations.append("missing_retrieval_contract")
    for field in ("corpus_fingerprint", "document_count", "chunk_count"):
        if phase63.get(field) != phase64.get(field):
            violations.append(f"{field}_mismatch")
    for name, contract, short_loop_enabled in (
        ("phase63", phase63, False),
        ("phase64", phase64, True),
    ):
        if contract.get("pgvector_search_enabled") is not True:
            violations.append(f"{name}_pgvector_not_enabled")
        if contract.get("vector_backend_policy") != "require_pgvector":
            violations.append(f"{name}_vector_policy_not_strict")
        if contract.get("agent_short_loop_enabled") is not short_loop_enabled:
            violations.append(f"{name}_short_loop_misconfigured")
        if contract.get("reranking_enabled") is not True:
            violations.append(f"{name}_reranking_not_enabled")
        if contract.get("reranking_provider") != "zhipu":
            violations.append(f"{name}_reranking_provider_invalid")
        if contract.get("reranking_model_name") != "rerank":
            violations.append(f"{name}_reranking_model_invalid")
        for cache_name in (
            "retrieval_candidate_cache_enabled",
            "rerank_order_cache_enabled",
            "tool_result_cache_enabled",
            "semantic_evidence_cache_enabled",
        ):
            if contract.get(cache_name) is not False:
                violations.append(f"{name}_{cache_name}_not_cold")
    for name, contract, route_first_enabled, fanout_enabled in (
        ("phase63", phase63, False, False),
        ("phase64", phase64, True, True),
    ):
        if contract.get("phase64_route_first_enabled") is not route_first_enabled:
            violations.append(f"{name}_route_first_misconfigured")
        if contract.get("phase64_retrieval_fanout_enabled") is not fanout_enabled:
            violations.append(f"{name}_fanout_misconfigured")
        if contract.get("phase64_final_non_thinking_enabled") is not route_first_enabled:
            violations.append(f"{name}_final_non_thinking_misconfigured")
        if contract.get("phase64_execution_graph_schema") != "phase64-route-first-v1":
            violations.append(f"{name}_execution_graph_schema_invalid")
    return {"ok": not violations, "violations": violations}


def _float_values(rows: Sequence[dict[str, object]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        try:
            value = float(row.get(field, ""))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def _row_float(row: dict[str, object], field: str) -> float | None:
    try:
        value = float(row.get(field, ""))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _critical_path_value(row: dict[str, object]) -> float | None:
    retrieval = _row_float(row, "retrieval_total_latency_ms")
    rerank = _row_float(row, "glm_rerank_latency_ms")
    if retrieval is None or rerank is None:
        return None
    return retrieval + rerank


def _paired_rows(rows: Sequence[dict[str, object]]) -> list[tuple[dict[str, object], dict[str, object]]]:
    indexed: dict[tuple[str, int], dict[str, dict[str, object]]] = {}
    for row in rows:
        variant = str(row.get("variant", ""))
        if variant not in {"phase63", "phase64"}:
            continue
        try:
            key = (str(row.get("case_id", "")), int(row.get("run", 0)))
        except (TypeError, ValueError):
            continue
        if not key[0] or key[1] <= 0:
            continue
        indexed.setdefault(key, {})[variant] = row
    return [
        (variants["phase63"], variants["phase64"])
        for _, variants in sorted(indexed.items())
        if {"phase63", "phase64"}.issubset(variants)
    ]


def _paired_deltas(
    pairs: Sequence[tuple[dict[str, object], dict[str, object]]],
    *,
    value: Callable[[dict[str, object]], float | None],
) -> list[float]:
    deltas: list[float] = []
    for phase63, phase64 in pairs:
        baseline = value(phase63)
        candidate = value(phase64)
        if baseline is not None and candidate is not None:
            deltas.append(candidate - baseline)
    return deltas


def _rate(rows: Sequence[dict[str, object]], predicate: Callable[[dict[str, object]], bool]) -> float:
    return round(sum(1 for row in rows if predicate(row)) / len(rows), 4) if rows else 0.0


def _functional_row_ok(row: dict[str, object]) -> bool:
    expected_tool = str(row.get("expected_tool", ""))
    observed_tools = str(row.get("observed_tool_names", ""))
    lexical_ok = expected_tool != "hybrid_search_knowledge" or row.get("lexical_backend") == "bm25"
    route_ok = expected_tool in observed_tools or expected_tool in {
        "off_topic_gate",
        "responsibility_gate",
    }
    return bool(
        row.get("ok")
        and route_ok
        and lexical_ok
        and row.get("vector_backend") == "pgvector_hnsw"
        and not bool(row.get("vector_degraded"))
        and not bool(row.get("streaming_degraded"))
        and bool(row.get("counts_match"))
        and bool(row.get("conversation_persisted"))
    )


def _route_functional_rates(
    pairs: Sequence[tuple[dict[str, object], dict[str, object]]],
    route_kind: str,
) -> tuple[float, float, int]:
    matched = [pair for pair in pairs if pair[1].get("phase64_route_kind") == route_kind]
    return (
        _rate([pair[0] for pair in matched], _functional_row_ok),
        _rate([pair[1] for pair in matched], _functional_row_ok),
        len(matched),
    )


def _judge_summary_passes(judge_summary: dict[str, object] | None) -> bool:
    if not judge_summary:
        return False
    try:
        lower_bound = float(judge_summary.get("paired_quality_lower_bound", ""))
        loss_rate = float(judge_summary.get("loss_rate", ""))
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(lower_bound)
        and lower_bound >= -0.02
        and math.isfinite(loss_rate)
        and loss_rate <= 0.10
    )


def build_phase64_summary(
    rows: list[dict[str, object]],
    *,
    frozen_contract: dict[str, object],
    judge_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    phase63 = [row for row in rows if row.get("variant") == "phase63"]
    phase64 = [row for row in rows if row.get("variant") == "phase64"]
    phase63_functional_rate = _rate(phase63, _functional_row_ok)
    phase64_functional_rate = _rate(phase64, _functional_row_ok)
    phase63_first_tokens = _float_values(phase63, "first_token_ms")
    phase64_first_tokens = _float_values(phase64, "first_token_ms")
    phase63_elapsed = _float_values(phase63, "elapsed_ms")
    phase64_elapsed = _float_values(phase64, "elapsed_ms")
    phase63_critical_path = [
        value for row in phase63 if (value := _critical_path_value(row)) is not None
    ]
    phase64_critical_path = [
        value for row in phase64 if (value := _critical_path_value(row)) is not None
    ]
    pairs = _paired_rows(rows)
    fast_phase63_rate, fast_phase64_rate, fast_pair_count = _route_functional_rates(
        pairs,
        "fast",
    )
    complex_phase63_rate, complex_phase64_rate, complex_pair_count = _route_functional_rates(
        pairs,
        "complex",
    )
    paired_metrics = {
        "first_token_delta_p50_ms": percentile(
            _paired_deltas(pairs, value=lambda row: _row_float(row, "first_token_ms")),
            0.50,
        ),
        "first_token_delta_p95_ms": percentile(
            _paired_deltas(pairs, value=lambda row: _row_float(row, "first_token_ms")),
            0.95,
        ),
        "final_delta_p50_ms": percentile(
            _paired_deltas(pairs, value=lambda row: _row_float(row, "elapsed_ms")),
            0.50,
        ),
        "final_delta_p95_ms": percentile(
            _paired_deltas(pairs, value=lambda row: _row_float(row, "elapsed_ms")),
            0.95,
        ),
        "critical_path_delta_p50_ms": percentile(
            _paired_deltas(pairs, value=_critical_path_value),
            0.50,
        ),
        "critical_path_delta_p95_ms": percentile(
            _paired_deltas(pairs, value=_critical_path_value),
            0.95,
        ),
    }
    metrics = {
        "phase63_functional_rate": phase63_functional_rate,
        "phase64_functional_rate": phase64_functional_rate,
        "functional_rate_delta": round(phase64_functional_rate - phase63_functional_rate, 4),
        "phase63_first_token_p50_ms": percentile(phase63_first_tokens, 0.50),
        "phase63_first_token_p95_ms": percentile(phase63_first_tokens, 0.95),
        "phase64_first_token_p50_ms": percentile(phase64_first_tokens, 0.50),
        "phase64_first_token_p95_ms": percentile(phase64_first_tokens, 0.95),
        "phase63_final_p95_ms": percentile(phase63_elapsed, 0.95),
        "phase64_final_p95_ms": percentile(phase64_elapsed, 0.95),
        "phase63_retrieval_plus_glm_rerank_p95_ms": percentile(
            phase63_critical_path,
            0.95,
        ),
        "phase64_retrieval_plus_glm_rerank_p95_ms": percentile(
            phase64_critical_path,
            0.95,
        ),
        "fast_phase63_functional_rate": fast_phase63_rate,
        "fast_phase64_functional_rate": fast_phase64_rate,
        "complex_phase63_functional_rate": complex_phase63_rate,
        "complex_phase64_functional_rate": complex_phase64_rate,
    }
    paired_case_count = len(pairs)
    gates = {
        "frozen_contract": bool(frozen_contract.get("ok")),
        "paired_real_e2e_rows": bool(phase63 and phase64) and len(phase63) == len(phase64),
        "first_token_p50": metrics["phase64_first_token_p50_ms"] is not None
        and metrics["phase64_first_token_p50_ms"] <= 8000.0,
        "first_token_p95": metrics["phase64_first_token_p95_ms"] is not None
        and metrics["phase64_first_token_p95_ms"] <= 15000.0,
        "final_p95": metrics["phase64_final_p95_ms"] is not None
        and metrics["phase64_final_p95_ms"] <= 30000.0,
        "functional_non_regression": phase64_functional_rate >= phase63_functional_rate,
        "fast_functional_non_regression": bool(fast_pair_count)
        and fast_phase64_rate >= fast_phase63_rate,
        "complex_functional_non_regression": bool(complex_pair_count)
        and complex_phase64_rate >= complex_phase63_rate,
        "blind_judge_non_regression": _judge_summary_passes(judge_summary),
    }
    return {
        "validation_mode": "real_frozen_phase63_phase64_sse",
        "paired_case_count": paired_case_count,
        "frozen_contract": frozen_contract,
        "metrics": metrics,
        "paired_metrics": paired_metrics,
        "judge_summary": judge_summary or {},
        "gates": gates,
        "gates_passed": all(gates.values()),
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
    capture_answer: bool = False,
) -> dict[str, object]:
    chat_model = selected_chat_model_for_variant(variant)
    result = execute_case(
        case,
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
        keep_conversation=keep_conversations,
        capture_answer=capture_answer,
        chat_model=chat_model,
    )
    if str(result.get("observed_chat_model", "")) != chat_model:
        result["ok"] = False
        result["error_category"] = "selected_chat_model_mismatch"
    return {
        "variant": variant,
        "run": run,
        **result,
        "agent_short_loop_enabled": bool(contract.get("agent_short_loop_enabled", False)),
        "reranking_provider": str(contract.get("reranking_provider", "")),
        "reranking_model_name": str(contract.get("reranking_model_name", "")),
        "retrieval_candidate_cache_enabled": bool(
            contract.get("retrieval_candidate_cache_enabled", True)
        ),
        "rerank_order_cache_enabled": bool(contract.get("rerank_order_cache_enabled", True)),
        "tool_result_cache_enabled": bool(contract.get("tool_result_cache_enabled", True)),
        "semantic_evidence_cache_enabled": bool(
            contract.get("semantic_evidence_cache_enabled", True)
        ),
        "phase64_execution_graph": str(result.get("phase64_execution_graph", "")),
        "phase64_route_kind": str(result.get("phase64_route_kind", "")),
        "phase64_route_reason": str(result.get("phase64_route_reason", "")),
        "snapshot_fingerprint": str(contract.get("corpus_fingerprint", "")),
        **(
            {"_ephemeral_answer": str(result.get("_ephemeral_answer", ""))}
            if capture_answer
            else {}
        ),
    }


def _configured_blind_judge_provider():
    from app.core.config import get_settings
    from app.services.generation.chat_model import create_chat_model_provider

    settings = get_settings()
    if not (
        settings.judge_model_provider
        and settings.judge_model_name
        and settings.judge_model_api_key
        and settings.judge_model_base_url
    ):
        raise ValueError("phase64_blind_judge_not_configured")
    return create_chat_model_provider(
        provider_name=settings.judge_model_provider,
        model_name=settings.judge_model_name,
        api_key=settings.judge_model_api_key,
        base_url=settings.judge_model_base_url,
        temperature=settings.judge_model_temperature,
        timeout_seconds=settings.judge_model_timeout_seconds,
        max_attempts=settings.judge_model_max_attempts,
        max_tokens=settings.judge_model_max_tokens,
    )


def main() -> int:
    args = parse_args()
    if args.phase63_base_url.rstrip("/") == args.phase64_base_url.rstrip("/"):
        print(json.dumps({"error": "distinct_endpoints_required"}, ensure_ascii=False))
        return 2
    if args.runs < 1:
        print(json.dumps({"error": "runs_must_be_positive"}, ensure_ascii=False))
        return 2
    try:
        blind_judge = _configured_blind_judge_provider() if args.execute_blind_judge else None
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    try:
        phase63_contract = fetch_retrieval_contract(
            args.phase63_base_url, token=args.token, timeout_seconds=args.timeout_seconds
        )
        phase64_contract = fetch_retrieval_contract(
            args.phase64_base_url, token=args.token, timeout_seconds=args.timeout_seconds
        )
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
        print(json.dumps({"error": "retrieval_contract_unavailable"}, ensure_ascii=False))
        return 2
    frozen_contract = validate_frozen_contract(phase63_contract, phase64_contract)
    if not frozen_contract["ok"]:
        print(json.dumps({"error": "frozen_contract_invalid", **frozen_contract}, ensure_ascii=False))
        return 2
    with args.cases.open(encoding="utf-8-sig", newline="") as stream:
        cases = select_cases(
            list(csv.DictReader(stream)), case_id=args.case_id, limit=args.limit
        )
    variants = {
        "phase63": (args.phase63_base_url, phase63_contract),
        "phase64": (args.phase64_base_url, phase64_contract),
    }
    rows: list[dict[str, object]] = []
    ephemeral_answers: dict[tuple[str, int], dict[str, str]] = {}
    for run in range(1, args.runs + 1):
        for case in cases:
            for variant in deterministic_pair_order(case["case_id"], run, args.seed):
                base_url, contract = variants[variant]
                row = run_case(
                        case,
                        variant=variant,
                        run=run,
                        base_url=base_url,
                        contract=contract,
                        token=args.token,
                        timeout_seconds=args.timeout_seconds,
                        keep_conversations=args.keep_conversations,
                        capture_answer=blind_judge is not None,
                    )
                if blind_judge is not None:
                    ephemeral_answers.setdefault((case["case_id"], run), {})[variant] = str(
                        row.pop("_ephemeral_answer", "")
                    )
                rows.append(row)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PHASE64_OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(
            {field: row.get(field, "") for field in PHASE64_OUTPUT_FIELDS} for row in rows
        )
    judge_rows: list[dict[str, object]] = []
    if blind_judge is not None:
        case_by_id = {case["case_id"]: case for case in cases}
        for (case_id, run), answers in sorted(ephemeral_answers.items()):
            if not answers.get("phase63") or not answers.get("phase64"):
                continue
            case = case_by_id[case_id]
            try:
                judge_rows.append(
                    judge_blind_pair(
                        blind_judge,
                        case_id=case_id,
                        run=run,
                        category=case["category"],
                        question=case["query"],
                        answer_phase63=answers["phase63"],
                        answer_phase64=answers["phase64"],
                        seed=args.seed,
                    )
                )
            except ValueError:
                continue
    judge_summary = (
        summarize_judge_rows(judge_rows, seed=args.seed) if blind_judge is not None else None
    )
    if args.judge_out:
        args.judge_out.parent.mkdir(parents=True, exist_ok=True)
        with args.judge_out.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=JUDGE_OUTPUT_FIELDS)
            writer.writeheader()
            writer.writerows(
                {field: row.get(field, "") for field in JUDGE_OUTPUT_FIELDS}
                for row in judge_rows
            )
    summary = build_phase64_summary(
        rows,
        frozen_contract=frozen_contract,
        judge_summary=judge_summary,
    )
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if not args.enforce_gates or bool(summary["gates_passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
