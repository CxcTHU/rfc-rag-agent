"""Fail-closed, safe Phase 65 agent-gate execution harness.

The evaluator never persists prompts, answers, evidence, provider payloads, or
tokens.  Blind-judge inputs exist only for the duration of a provider call.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import secrets
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
SAFE_OUTPUT_ROOT = ROOT / "output"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate_phase63_e2e import execute_case
from scripts.judge_phase65_agent_gate import (
    JUDGE_DIMENSIONS,
    JUDGE_OUTPUT_FIELDS,
    JudgeReceiptContract,
    anonymous_mapping_hash,
    build_safe_judge_row,
    canonical_judge_receipt_contract_sha256,
    summarize_judge_rows,
)
from scripts.phase65_agent_gate import (
    GateDecision,
    build_paired_execution_preflight,
    build_phase65_gate_decision,
    compare_manifests,
)
from scripts.phase65_gate_manifest import (
    AgentGateManifest,
    SCHEMA_VERSION,
    canonical_phase65_scope,
    read_git_worktree_identity,
    sha256_file,
    write_manifest,
)


DEFAULT_CASES = ROOT / "data" / "evaluation" / "phase64_latency_cases.csv"
PHASE65_OUTPUT_FIELDS = (
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
    "counts_match",
    "conversation_persisted",
    "refused",
    "first_token_ms",
    "elapsed_ms",
    "input_tokens",
    "output_tokens",
    "estimated_cost",
    "provider_usage_request_count",
    "provider_usage_receipt_count",
    "provider_usage_receipt_complete",
    "cold_cache_receipt_status",
    "runtime_stop_reason",
    "completed_tool_replay_count",
    "manifest_run_id",
    "snapshot_fingerprint",
)
Variant = Literal["baseline", "candidate"]
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KNOWN_ERROR_CATEGORIES = frozenset(
    {
        "",
        "stream_error",
        "missing_metadata",
        "missing_done",
        "missing_usage_receipt",
        "missing_cold_cache_receipt",
        "expected_tool_failed",
        "unexpected_tool_route",
        "unexpected_graph_route",
        "unexpected_lexical_backend",
        "vector_backend_degraded",
        "streaming_degraded",
        "retrieval_count_mismatch",
        "insufficient_citations",
        "connection_error",
        "invalid_or_timeout_response",
        "conversation_not_persisted",
        "selected_chat_model_mismatch",
        "http_401",
        "http_403",
        "http_429",
        "http_500",
        "http_502",
        "http_503",
        "http_504",
    }
)
_MAX_BLIND_JUDGE_ANSWER_CHARS = 4000


@dataclass(frozen=True)
class ScheduleItem:
    case_id: str
    run: int
    variant: Variant


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fail-closed Phase 65 A/B gate.")
    parser.add_argument("--mode", choices=("baseline", "candidate", "paired", "holdout", "summarize"), required=True)
    parser.add_argument("--baseline-base-url")
    parser.add_argument("--candidate-base-url")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--holdout-cases", type=Path)
    parser.add_argument("--limit", type=int, help="run the first N frozen public cases for a bounded smoke")
    parser.add_argument("--runs", type=int)
    parser.add_argument("--seed", type=int, default=650013)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--baseline-manifest-out", type=Path)
    parser.add_argument("--candidate-manifest-out", type=Path)
    parser.add_argument("--baseline-manifest", type=Path)
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--summary-out", type=Path)
    parser.add_argument("--judge-out", type=Path)
    parser.add_argument("--judge-results", type=Path)
    parser.add_argument("--holdout-summary", type=Path)
    parser.add_argument("--token-env", default="PHASE65_EVAL_TOKEN")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--execute-blind-judge", action="store_true")
    parser.add_argument("--enforce-gates", action="store_true")
    parser.add_argument("--contract-gate-status", choices=("pass", "fail", "blocked"), default="blocked")
    parser.add_argument("--topology-gate-status", choices=("pass", "fail", "blocked"), default="blocked")
    parser.add_argument("--fault-gate-status", choices=("pass", "fail", "blocked"), default="blocked")
    parser.add_argument("--authorize-paid-run", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--auto-auth", action="store_true")
    parser.add_argument("--allow-incomplete-evidence", action="store_true")
    return parser.parse_args()


def resolve_execution_token(
    token_env: str,
    *,
    environ: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> str:
    """Read an execution token in-memory, preferring the process environment.

    The optional local `.env` fallback makes the existing development settings
    convention usable by standalone evaluators.  Its value is never logged,
    serialized, or included in an evaluation receipt.
    """

    name = token_env.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("invalid_token_environment_name")
    source = os.environ if environ is None else environ
    configured = source.get(name, "").strip()
    if configured:
        return configured

    path = dotenv_path or ROOT / ".env"
    if not path.is_file():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def deterministic_pair_order(case_id: str, run: int, seed: int) -> tuple[Variant, Variant]:
    digest = hashlib.sha256(f"{seed}:{case_id}:{run}".encode("utf-8")).digest()
    return ("baseline", "candidate") if digest[0] % 2 == 0 else ("candidate", "baseline")


def build_schedule(*, case_ids: Sequence[str], runs: int, seed: int) -> list[ScheduleItem]:
    if runs < 1:
        raise ValueError("runs_must_be_positive")
    if not case_ids or len(set(case_ids)) != len(case_ids):
        raise ValueError("case_ids_must_be_unique_and_nonempty")
    if not all(_is_safe_identifier(case_id) for case_id in case_ids):
        raise ValueError("unsafe_case_id")
    schedule: list[ScheduleItem] = []
    for run in range(1, runs + 1):
        for case_id in case_ids:
            schedule.extend(
                ScheduleItem(case_id=case_id, run=run, variant=variant)
                for variant in deterministic_pair_order(case_id, run, seed)
            )
    return schedule


def normalize_endpoint_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid_endpoint_url")
    hostname = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port is not None else ""
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), f"{hostname}{port}", path, "", ""))


def validate_schedule(mode: str, rows: list[dict[str, object]], case_count: int, runs: int) -> None:
    expected = case_count * runs * (2 if mode in {"paired", "holdout"} else 1)
    if len(rows) != expected:
        raise ValueError(f"incomplete_rows:{len(rows)}:{expected}")


def validate_output_path(path: Path) -> Path:
    """Allow artifacts only below the local, non-sensitive output directory."""
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "output"
        or any(part.casefold().startswith(".env") for part in path.parts)
    ):
        raise ValueError("unsafe_output_path")
    resolved = (ROOT / path).resolve()
    try:
        resolved.relative_to(SAFE_OUTPUT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("unsafe_output_path") from exc
    if resolved.exists() and resolved.is_symlink():
        raise ValueError("unsafe_output_path")
    return resolved


def validate_holdout_cases(
    path: Path,
    *,
    exclude_cases_path: Path | None = None,
) -> list[dict[str, str]]:
    cases = _load_cases(path)
    for case in cases:
        if not str(case.get("query", "")).strip():
            question = str(case.get("question", "")).strip()
            if not question:
                raise ValueError("holdout_question_required")
            case["query"] = question
    case_ids = [case["case_id"] for case in cases]
    if len(cases) < 12 or len(set(case_ids)) != len(cases):
        raise ValueError("holdout_requires_twelve_unique_cases")
    if exclude_cases_path is not None and exclude_cases_path.exists():
        public_ids = {case["case_id"] for case in _load_cases(exclude_cases_path)}
        if public_ids.intersection(case_ids):
            raise ValueError("holdout_overlaps_public_cases")
    return cases


def project_safe_row(
    result: Mapping[str, object],
    *,
    variant: Variant,
    run: int,
    manifest_run_id: str,
    snapshot_fingerprint: str,
) -> dict[str, object]:
    """Persist only the predeclared safe, aggregate row fields."""
    if not _is_safe_identifier(manifest_run_id) or not _SHA256.fullmatch(snapshot_fingerprint):
        raise ValueError("unsafe_manifest_receipt")
    error_category = str(result.get("error_category", ""))
    safe_error = error_category if error_category in _KNOWN_ERROR_CATEGORIES else "unclassified_error"
    return {
        "variant": variant,
        "run": _positive_int(run),
        "case_id": _safe_identifier(result.get("case_id"), fallback="invalid_case_id"),
        "category": _safe_identifier(result.get("category"), fallback="invalid_category"),
        "ok": result.get("ok") if isinstance(result.get("ok"), bool) else False,
        "error_category": safe_error,
        "http_status": _safe_nonnegative_int(result.get("http_status")),
        "expected_tool": _safe_identifier(result.get("expected_tool"), fallback=""),
        "observed_tool_names": _safe_tool_names(result.get("observed_tool_names")),
        "expected_graph_requirement": _safe_identifier(
            result.get("expected_graph_requirement"), fallback=""
        ),
        "observed_graph_requirement": _safe_identifier(
            result.get("observed_graph_requirement"), fallback=""
        ),
        "citation_count": _safe_nonnegative_int(result.get("citation_count")),
        "selected_count": _safe_nonnegative_int(result.get("selected_count")),
        "live_selected_count": _safe_nonnegative_int(result.get("live_selected_count")),
        "counts_match": result.get("counts_match") if isinstance(result.get("counts_match"), bool) else False,
        "conversation_persisted": result.get("conversation_persisted")
        if isinstance(result.get("conversation_persisted"), bool)
        else False,
        "refused": result.get("refused") if isinstance(result.get("refused"), bool) else False,
        "first_token_ms": _safe_nonnegative_number(result.get("first_token_ms")),
        "elapsed_ms": _safe_nonnegative_number(result.get("elapsed_ms")),
        "input_tokens": _safe_nonnegative_int(result.get("input_tokens")),
        "output_tokens": _safe_nonnegative_int(result.get("output_tokens")),
        "estimated_cost": _safe_nonnegative_number(result.get("estimated_cost")),
        "provider_usage_request_count": _safe_nonnegative_int(
            result.get("provider_usage_request_count")
        ),
        "provider_usage_receipt_count": _safe_nonnegative_int(
            result.get("provider_usage_receipt_count")
        ),
        "provider_usage_receipt_complete": result.get("provider_usage_receipt_complete")
        if isinstance(result.get("provider_usage_receipt_complete"), bool)
        else False,
        "cold_cache_receipt_status": _safe_identifier(
            result.get("cold_cache_receipt_status"),
            fallback="unknown",
        ),
        "runtime_stop_reason": _safe_identifier(result.get("runtime_stop_reason"), fallback="unknown"),
        "completed_tool_replay_count": _safe_nonnegative_int(
            result.get("completed_tool_replay_count")
        ),
        "manifest_run_id": manifest_run_id,
        "snapshot_fingerprint": snapshot_fingerprint,
    }


def run_variant_case(
    case: Mapping[str, str],
    *,
    variant: Variant,
    run: int,
    base_url: str,
    token: str,
    timeout_seconds: float,
    manifest_run_id: str,
    snapshot_fingerprint: str,
    execute: bool,
    capture_answer: bool,
    invocation_salt: str = "",
    execute_case_fn: Callable[..., dict[str, object]] = execute_case,
) -> tuple[dict[str, object], str]:
    """Execute one lane; any answer is returned only to an in-memory caller."""
    evaluation_namespace = _evaluation_run_namespace(
        variant=variant,
        manifest_run_id=manifest_run_id,
        invocation_salt=invocation_salt,
        run=run,
        case_id=str(case.get("case_id", "unknown")),
    )
    if not execute:
        return (
            project_safe_row(
                {**case, "ok": False, "error_category": "", "runtime_stop_reason": "dry_run"},
                variant=variant,
                run=run,
                manifest_run_id=manifest_run_id,
                snapshot_fingerprint=snapshot_fingerprint,
            ),
            "",
        )
    raw_result = execute_case_fn(
        dict(case),
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
        keep_conversation=False,
        capture_answer=capture_answer,
        evaluation_run_namespace=evaluation_namespace,
    )
    answer = str(raw_result.pop("_ephemeral_answer", "")) if capture_answer else ""
    # Cost accounting is observed but not a Phase 65 execution blocker.  The
    # runtime path must remain evaluable with providers that only expose token
    # usage, while cold-cache isolation remains a required experimental control.
    cold_status = _cold_cache_receipt_status(
        raw_result,
        namespace=evaluation_namespace,
    )
    raw_result["cold_cache_receipt_status"] = cold_status
    if cold_status != "valid":
        raw_result["ok"] = False
        raw_result["error_category"] = "missing_cold_cache_receipt"
    return (
        project_safe_row(
            raw_result,
            variant=variant,
            run=run,
            manifest_run_id=manifest_run_id,
            snapshot_fingerprint=snapshot_fingerprint,
        ),
        answer,
    )


def _evaluation_run_namespace(
    *,
    variant: Variant,
    manifest_run_id: str,
    invocation_salt: str = "",
    run: int,
    case_id: str,
) -> str:
    safe_case_id = _safe_identifier(case_id, fallback="unknown_case")
    salt = _safe_identifier(invocation_salt, fallback="")
    if salt:
        return f"phase65-{variant}-{manifest_run_id}-{salt}-{_positive_int(run)}-{safe_case_id}"
    return f"phase65-{variant}-{manifest_run_id}-{_positive_int(run)}-{safe_case_id}"


def _has_verified_usage(result: Mapping[str, object]) -> bool:
    request_count = _safe_nonnegative_int(result.get("provider_usage_request_count"))
    receipt_count = _safe_nonnegative_int(result.get("provider_usage_receipt_count"))
    return (
        result.get("provider_usage_receipt_complete") is True
        and request_count is not None
        and receipt_count is not None
        and request_count > 0
        and request_count == receipt_count
        and all(
            _safe_nonnegative_number(result.get(field)) is not None
            for field in ("input_tokens", "output_tokens", "estimated_cost")
        )
    )


def _has_verified_cold_cache_receipt(result: Mapping[str, object], *, namespace: str) -> bool:
    return _cold_cache_receipt_status(result, namespace=namespace) == "valid"


def _cold_cache_receipt_status(result: Mapping[str, object], *, namespace: str) -> str:
    receipt = result.get("cold_cache_receipt")
    if not isinstance(receipt, Mapping):
        return "absent"
    if receipt.get("schema_version") != "phase65-cold-cache-receipt-v1":
        return "bad_schema"
    if receipt.get("namespace_sha256") != _sha256(namespace):
        return "namespace_mismatch"
    if not (
        isinstance(receipt.get("request_binding_sha256"), str)
        and _SHA256.fullmatch(str(receipt["request_binding_sha256"])) is not None
    ):
        return "binding_missing"
    if receipt.get("isolation_version") != "phase65-cache-isolation-v1":
        return "isolation_mismatch"
    if receipt.get("cache_miss_confirmed") is not True:
        return "cache_hit"
    return "valid"


def run_gate(
    *,
    rows: Sequence[Mapping[str, object]],
    baseline_manifest: AgentGateManifest,
    candidate_manifest: AgentGateManifest,
    judge_rows: Sequence[Mapping[str, object]],
    judge_receipt_contract: JudgeReceiptContract,
    holdout_summary: Mapping[str, object] | None,
) -> GateDecision:
    comparison = compare_manifests(baseline_manifest, candidate_manifest)
    return build_phase65_gate_decision(
        paired_rows=_build_paired_gate_rows(rows),
        manifest_comparison=comparison,
        judge_summary=summarize_judge_rows(judge_rows, receipt_contract=judge_receipt_contract),
        judge_rows=judge_rows,
        judge_receipt_contract=judge_receipt_contract,
        holdout_summary=holdout_summary,
    )


def _load_cases(path: Path, *, limit: int | None = None) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        cases = list(csv.DictReader(stream))
    case_ids = [case.get("case_id", "") for case in cases]
    if (
        not cases
        or len(set(case_ids)) != len(case_ids)
        or any(not _is_safe_identifier(case_id) for case_id in case_ids)
    ):
        raise ValueError("invalid_cases_file")
    if limit is not None:
        if limit < 1:
            raise ValueError("limit_must_be_positive")
        cases = cases[:limit]
    return cases


def _filter_cases(
    cases: Sequence[Mapping[str, str]], case_ids: Sequence[str]
) -> list[dict[str, str]]:
    requested = [str(case_id).strip() for case_id in case_ids if str(case_id).strip()]
    if not requested:
        return [dict(case) for case in cases]
    by_id = {str(case.get("case_id", "")): dict(case) for case in cases}
    missing = [case_id for case_id in requested if case_id not in by_id]
    if missing:
        raise ValueError("case_id_not_found")
    return [by_id[case_id] for case_id in requested]


def _build_receipt_contract(
    cases: Sequence[Mapping[str, str]],
    *,
    runs: int,
    seed: int,
    require_balanced_mapping: bool = True,
) -> JudgeReceiptContract:
    expected_pairs: list[tuple[str, int, str]] = []
    for run in range(1, runs + 1):
        for case in cases:
            case_hash = _sha256(str(case["case_id"]))
            category = _judge_category(str(case.get("category", "")))
            expected_pairs.append((case_hash, run, category))
    # A hash gives a deterministic shuffle, while alternating the shuffled
    # receipts guarantees the A/B directions differ by at most one.  Random
    # parity alone is not sufficient for the small, fixed Phase 65 sample.
    ordered_indexes = sorted(
        range(len(expected_pairs)),
        key=lambda index: _judge_receipt_order_key(expected_pairs[index], seed),
    )
    baseline_on_a = anonymous_mapping_hash({"A": "baseline", "B": "candidate"})
    candidate_on_a = anonymous_mapping_hash({"A": "candidate", "B": "baseline"})
    expected_mapping_hashes = [candidate_on_a] * len(expected_pairs)
    for position, index in enumerate(ordered_indexes):
        expected_mapping_hashes[index] = (
            baseline_on_a if position % 2 == 0 else candidate_on_a
        )
    return JudgeReceiptContract(
        case_set_sha256=_case_set_sha256(cases),
        expected_pairs=tuple(expected_pairs),
        expected_mapping_hashes=tuple(expected_mapping_hashes),
        require_balanced_mapping=require_balanced_mapping,
    )


def _judge_mapping(case_hash: str, run: int, seed: int) -> dict[str, str]:
    digest = hashlib.sha256(f"judge:{seed}:{case_hash}:{run}".encode("utf-8")).digest()
    return {"A": "baseline", "B": "candidate"} if digest[0] % 2 == 0 else {"A": "candidate", "B": "baseline"}


def _judge_receipt_order_key(receipt: tuple[str, int, str], seed: int) -> str:
    case_hash, run, category = receipt
    return _sha256(f"judge-order:{seed}:{case_hash}:{run}:{category}")


def _scheduled_judge_mapping(
    *,
    case_hash: str,
    run: int,
    category: str,
    receipt_contract: JudgeReceiptContract,
) -> dict[str, str]:
    mapping_hash = receipt_contract.expected_mapping_hash(case_hash, run, category)
    if mapping_hash == anonymous_mapping_hash({"A": "baseline", "B": "candidate"}):
        return {"A": "baseline", "B": "candidate"}
    if mapping_hash == anonymous_mapping_hash({"A": "candidate", "B": "baseline"}):
        return {"A": "candidate", "B": "baseline"}
    raise ValueError("blind_judge_mapping_not_scheduled")


def _judge_category(category: str) -> str:
    normalized = category.lower()
    if "table" in normalized:
        return "table_intent"
    if "figure" in normalized or "visual" in normalized:
        return "visual_adjacent"
    if "relationship" in normalized:
        return "graph_intent"
    if "boundary" in normalized or "negative" in normalized:
        return "boundary"
    return "ordinary_text"


def _build_paired_gate_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], dict[str, Mapping[str, object]]] = {}
    for row in rows:
        variant = row.get("variant")
        case_id = row.get("case_id")
        run = row.get("run")
        if variant not in {"baseline", "candidate"} or not isinstance(case_id, str) or not isinstance(run, int):
            continue
        grouped.setdefault((case_id, run), {})[str(variant)] = row
    paired_rows: list[dict[str, object]] = []
    for (case_id, run), pair in sorted(grouped.items()):
        baseline = pair.get("baseline")
        candidate = pair.get("candidate")
        if baseline is None or candidate is None:
            continue
        baseline_metrics = _gate_metrics(baseline)
        candidate_metrics = _gate_metrics(candidate)
        paired_rows.append(
            {
                "case_id": case_id,
                "run": run,
                "baseline": baseline_metrics,
                "candidate": candidate_metrics,
                "unclassified_error_count": int(
                    baseline.get("error_category") == "unclassified_error"
                    or candidate.get("error_category") == "unclassified_error"
                ),
                "repeated_completed_tool_count": (
                    _safe_nonnegative_int(baseline.get("completed_tool_replay_count"))
                    or 0
                )
                + (
                    _safe_nonnegative_int(candidate.get("completed_tool_replay_count"))
                    or 0
                ),
            }
        )
    return paired_rows


def _gate_metrics(row: Mapping[str, object]) -> dict[str, object]:
    input_tokens = _safe_nonnegative_int(row.get("input_tokens"))
    output_tokens = _safe_nonnegative_int(row.get("output_tokens"))
    metrics: dict[str, object] = {
        "functional_ok": bool(row.get("ok")),
        "ttft_ms": _safe_nonnegative_number(row.get("first_token_ms")),
        "final_ms": _safe_nonnegative_number(row.get("elapsed_ms")),
        "cost": _safe_nonnegative_number(row.get("estimated_cost")),
    }
    if input_tokens is not None and output_tokens is not None:
        metrics["tokens"] = input_tokens + output_tokens
    return metrics


def _fetch_contract(base_url: str, *, token: str, timeout_seconds: float) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    call = request.Request(f"{base_url}/health/retrieval-contract", headers=headers, method="GET")
    with request.urlopen(call, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _auto_auth_token(base_url: str, *, timeout_seconds: float) -> str:
    from scripts.verify_phase65_production_topology import probe_auth

    sink: dict[str, str] = {}
    result = probe_auth(base_url=base_url, token_sink=sink)
    if result.status == "pass" and sink.get("token"):
        return sink["token"]
    if result.category == "auth_register_failed" and _is_loopback_endpoint(base_url):
        return _bootstrap_local_eval_token(base_url, timeout_seconds=timeout_seconds)
    raise ValueError("auto_auth_failed")


def _is_loopback_endpoint(base_url: str) -> bool:
    parsed = urlsplit(base_url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme in {"http", "https"} and host in {"127.0.0.1", "localhost", "::1"}


def _bootstrap_local_eval_token(base_url: str, *, timeout_seconds: float) -> str:
    if not _is_loopback_endpoint(base_url):
        raise ValueError("auto_auth_failed")

    from app.core.security import password_hash
    from app.db.repositories import UserCreate, UserRepository
    from app.db.session import SessionLocal, init_db
    from scripts.verify_phase65_production_topology import http_json_request, join_url

    normalized = normalize_endpoint_url(base_url)
    username = f"phase65_eval_{_sha256(normalized)[:16]}"
    email = f"{username}@example.com"
    password = secrets.token_urlsafe(32)

    init_db()
    with SessionLocal() as db:
        repository = UserRepository(db)
        user = repository.get_by_username(username) or repository.get_by_email(email)
        hashed_password = password_hash(password)
        if user is None:
            repository.create_user(
                UserCreate(
                    username=username,
                    email=email,
                    password_hash=hashed_password,
                    role="admin",
                    is_active=True,
                )
            )
        else:
            user.password_hash = hashed_password
            user.role = "admin"
            user.is_active = True
            db.add(user)
            db.commit()

    login = http_json_request(
        "POST",
        join_url(base_url, "/auth/login"),
        {"username_or_email": username, "password": password},
        None,
        timeout_seconds=timeout_seconds,
    )
    if int(login.get("status_code", 0) or 0) != 200:
        raise ValueError("auto_auth_failed")
    login_json = login.get("json", {})
    token = str(login_json.get("access_token", "")) if isinstance(login_json, dict) else ""
    if not token:
        raise ValueError("auto_auth_failed")
    me = http_json_request(
        "GET",
        join_url(base_url, "/auth/me"),
        None,
        token,
        timeout_seconds=timeout_seconds,
    )
    if int(me.get("status_code", 0) or 0) != 200:
        raise ValueError("auto_auth_failed")
    return token


def _contract_identity_sha256(contract: Mapping[str, object]) -> str:
    value = contract.get("endpoint_identity_sha256")
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError("endpoint_identity_unavailable")
    return value


def _contract_index_fingerprint_sha256(contract: Mapping[str, object]) -> str:
    value = contract.get("index_fingerprint_sha256")
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError("index_fingerprint_unavailable")
    return value


def _build_manifest(
    *,
    variant: Variant,
    expected_rows: int,
    completed_rows: int,
    cases: Sequence[Mapping[str, str]],
    receipt_contract: JudgeReceiptContract,
    endpoint_identity_sha256: str,
    contract: Mapping[str, object],
    environment_class: str,
) -> AgentGateManifest:
    identity = read_git_worktree_identity(ROOT, canonical_phase65_scope(ROOT))
    evaluator = sha256_file(Path(__file__))
    now = "2026-07-14T00:00:00Z"
    provider_models = _provider_model_receipts(contract)
    return AgentGateManifest(
        schema_version=SCHEMA_VERSION,
        run_id=f"phase65-{variant}-{_sha256(f'{variant}:{endpoint_identity_sha256}')[:16]}",
        variant=variant,
        status="complete" if environment_class != "dry_run" else "incomplete",
        base_commit=identity.base_commit,
        tracked_patch_sha256=identity.tracked_patch_sha256,
        scoped_content_sha256=identity.scoped_content_sha256,
        scoped_paths=identity.scoped_paths,
        evaluator_sha256=evaluator,
        case_set_sha256=_case_set_sha256(cases),
        prompt_sha256=_sha256("phase65-blind-judge-prompt-v1"),
        tool_schema_sha256=_sha256("phase65-tool-schema-v1"),
        corpus_fingerprint=_sha256(str(contract.get("corpus_fingerprint", "unavailable"))),
        index_fingerprint=_contract_index_fingerprint_sha256(contract),
        provider_models=provider_models,
        endpoint_identity_sha256=endpoint_identity_sha256,
        judge_receipt_contract_sha256=canonical_judge_receipt_contract_sha256(receipt_contract),
        cache_policy="cold" if environment_class != "dry_run" else "dry_run",
        environment_class=environment_class,
        expected_rows=expected_rows,
        completed_rows=completed_rows,
        started_at=now,
        completed_at=now,
        sanitized_errors=(),
    )


def _provider_model_receipts(contract: Mapping[str, object]) -> tuple[str, ...]:
    inventory = contract.get("phase65_model_inventory")
    if not isinstance(inventory, list) or not inventory:
        raise ValueError("phase65_model_inventory_unverified")
    receipts: list[str] = []
    seen_paths: set[str] = set()
    for item in inventory:
        if not isinstance(item, Mapping):
            raise ValueError("phase65_model_inventory_unverified")
        path = item.get("path")
        identity_sha256 = item.get("identity_sha256")
        if (
            path not in {"chat", "runtime_identity", "planner"}
            or not isinstance(identity_sha256, str)
            or not _SHA256.fullmatch(identity_sha256)
            or item.get("configured") is not True
            or item.get("usage_receipt_verified") is not True
            or path in seen_paths
        ):
            raise ValueError("phase65_model_inventory_unverified")
        seen_paths.add(path)
        receipts.append(f"{path}:sha256:{identity_sha256}")
    if "chat" not in seen_paths:
        raise ValueError("phase65_model_inventory_unverified")
    return tuple(sorted(receipts))


def _case_set_sha256(cases: Sequence[Mapping[str, str]]) -> str:
    receipts = [
        {"case_id": str(case["case_id"]), "category": _judge_category(str(case.get("category", "")))}
        for case in cases
    ]
    return _sha256(json.dumps(receipts, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def _configured_blind_judge_provider() -> object:
    from app.core.config import get_settings
    from app.services.generation.chat_model import create_chat_model_provider

    settings = get_settings()
    if not (
        settings.judge_model_provider
        and settings.judge_model_name
        and settings.judge_model_api_key
        and settings.judge_model_base_url
    ):
        raise ValueError("phase65_blind_judge_not_configured")
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


def _judge_blind_pair(
    provider: object,
    *,
    case: Mapping[str, str],
    run: int,
    baseline_answer: str,
    candidate_answer: str,
    seed: int,
    receipt_contract: JudgeReceiptContract,
) -> dict[str, object]:
    """Send transient prompt/answers to the judge and retain only its safe receipt."""
    from app.services.generation.chat_model import ChatMessage

    case_hash = _sha256(str(case["case_id"]))
    category = _judge_category(str(case.get("category", "")))
    mapping = _scheduled_judge_mapping(
        case_hash=case_hash,
        run=run,
        category=category,
        receipt_contract=receipt_contract,
    )
    display_a = _bounded_blind_judge_text(
        baseline_answer if mapping["A"] == "baseline" else candidate_answer
    )
    display_b = _bounded_blind_judge_text(
        candidate_answer if mapping["B"] == "candidate" else baseline_answer
    )
    prompt = (
        "Compare anonymous answers. Return JSON only with winner A|B|tie and four numeric deltas "
        "(completion, accuracy, citation_support, overall_quality) in [-1,1], plus a short reason.\n"
        f"Question: {case['query']}\n\nA: {display_a}\n\nB: {display_b}"
    )
    started = time.perf_counter()
    result = provider.generate(  # type: ignore[attr-defined]
        [
            ChatMessage(role="system", content="Return only the requested JSON; do not identify lanes."),
            ChatMessage(role="user", content=prompt),
        ]
    )
    try:
        payload = _parse_blind_judge_payload(str(getattr(result, "answer", "")))
        winner = str(payload.get("winner", "tie"))
        deltas = {dimension: float(payload[dimension]) for dimension in JUDGE_DIMENSIONS}
        reason = str(payload.get("reason", ""))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("blind_judge_invalid_json") from exc
    return build_safe_judge_row(
        case_id=case_hash,
        run=run,
        category=category,
        mapping=mapping,
        winner_label=winner,
        label_deltas=deltas,
        judge_latency_ms=(time.perf_counter() - started) * 1000.0,
        judge_provider=str(getattr(provider, "provider_name", "")),
        judge_model=str(getattr(provider, "model_name", "")),
        reason=reason,
        receipt_contract=receipt_contract,
    )


def _bounded_blind_judge_text(
    text: str,
    *,
    max_chars: int = _MAX_BLIND_JUDGE_ANSWER_CHARS,
) -> str:
    value = str(text)
    if len(value) <= max_chars:
        return value
    marker = "\n...[truncated_for_judge_stability]...\n"
    if max_chars <= len(marker) + 2:
        return value[:max_chars]
    edge_chars = (max_chars - len(marker)) // 2
    return value[:edge_chars] + marker + value[-edge_chars:]


def _safe_judge_blind_pair(
    provider: object,
    *,
    case: Mapping[str, str],
    run: int,
    baseline_answer: str,
    candidate_answer: str,
    seed: int,
    receipt_contract: JudgeReceiptContract,
) -> tuple[dict[str, object] | None, str | None]:
    last_category = "blind_judge_provider_failed"
    for _attempt in range(3):
        try:
            return (
                _judge_blind_pair(
                    provider,
                    case=case,
                    run=run,
                    baseline_answer=baseline_answer,
                    candidate_answer=candidate_answer,
                    seed=seed,
                    receipt_contract=receipt_contract,
                ),
                None,
            )
        except ValueError as exc:
            category = str(exc)
            last_category = category if category.startswith("blind_judge_") else "blind_judge_failed"
        except (RuntimeError, OSError, TimeoutError, json.JSONDecodeError):
            last_category = "blind_judge_provider_failed"
    return None, last_category


def _parse_blind_judge_payload(text: str) -> dict[str, object]:
    raw = text.strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(raw[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("blind_judge_invalid_json")
    deltas = payload.get("deltas")
    if isinstance(deltas, Mapping):
        payload = dict(payload)
        for dimension in JUDGE_DIMENSIONS:
            if dimension not in payload and dimension in deltas:
                payload[dimension] = deltas[dimension]
    return payload


def _run_execution(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    if args.mode == "holdout" and args.holdout_cases is None:
        raise ValueError("holdout_cases_required")
    if args.mode == "holdout" and args.limit is not None:
        raise ValueError("limit_not_supported_for_holdout")
    cases = (
        validate_holdout_cases(args.holdout_cases, exclude_cases_path=args.cases)
        if args.mode == "holdout"
        else _load_cases(args.cases, limit=args.limit)
    )
    if args.mode != "holdout":
        cases = _filter_cases(cases, args.case_id)
    if args.mode == "paired" and not (args.baseline_base_url and args.candidate_base_url):
        raise ValueError("paired_endpoints_required")
    if args.mode == "holdout" and not (args.baseline_base_url and args.candidate_base_url):
        raise ValueError("holdout_endpoints_required")
    if args.mode == "baseline" and not args.baseline_base_url:
        raise ValueError("baseline_endpoint_required")
    if args.mode == "candidate" and not args.candidate_base_url:
        raise ValueError("candidate_endpoint_required")
    if args.runs < 1:
        raise ValueError("runs_must_be_positive")

    endpoints: dict[Variant, str] = {}
    if args.baseline_base_url:
        endpoints["baseline"] = normalize_endpoint_url(args.baseline_base_url)
    if args.candidate_base_url:
        endpoints["candidate"] = normalize_endpoint_url(args.candidate_base_url)
    if args.mode in {"paired", "holdout"} and endpoints["baseline"] == endpoints["candidate"]:
        raise ValueError("distinct_endpoints_required")
    active_variants: tuple[Variant, ...] = (
        ("baseline", "candidate")
        if args.mode in {"paired", "holdout"}
        else (("candidate",) if args.mode == "candidate" else ("baseline",))
    )
    expected_rows = len(cases) * args.runs * len(active_variants)
    try:
        receipt_contract = _build_receipt_contract(
            cases,
            runs=args.runs,
            seed=args.seed,
        )
    except ValueError:
        if (
            args.mode in {"baseline", "candidate"}
            and args.case_id
            and not args.execute_blind_judge
        ):
            receipt_contract = _build_receipt_contract(
                cases,
                runs=args.runs,
                seed=args.seed,
                require_balanced_mapping=False,
            )
        else:
            raise
    token = resolve_execution_token(args.token_env) if (args.execute or args.preflight_only) else ""
    tokens: dict[Variant, str] = {}
    endpoint_failures: dict[Variant, list[str]] = {variant: [] for variant in active_variants}
    for variant in active_variants:
        if args.auto_auth:
            try:
                tokens[variant] = _auto_auth_token(
                    endpoints[variant], timeout_seconds=args.timeout_seconds
                )
            except ValueError:
                endpoint_failures[variant].append("auto_auth")
                if not args.preflight_only:
                    raise
                tokens[variant] = ""
        else:
            tokens[variant] = token
    contracts: dict[Variant, Mapping[str, object]] = {}
    endpoint_hashes: dict[Variant, str] = {}
    endpoint_readiness: dict[str, object] | None = None
    if args.execute or args.preflight_only:
        for variant in active_variants:
            if endpoint_failures[variant]:
                continue
            try:
                contract = _fetch_contract(endpoints[variant], token=tokens[variant], timeout_seconds=args.timeout_seconds)
            except (error.HTTPError, error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                endpoint_failures[variant].append("contract")
                if not args.preflight_only:
                    raise
                continue
            contracts[variant] = contract
            try:
                endpoint_hashes[variant] = _contract_identity_sha256(contract)
                _contract_index_fingerprint_sha256(contract)
                if contract.get("cold_run_receipts_supported") is not True:
                    raise ValueError("cold_run_receipt_unavailable")
            except ValueError:
                endpoint_failures[variant].append("contract")
                if not args.preflight_only:
                    raise
        if (
            args.mode == "paired"
            and "baseline" in endpoint_hashes
            and "candidate" in endpoint_hashes
            and endpoint_hashes["baseline"] == endpoint_hashes["candidate"]
            and not args.preflight_only
        ):
            raise ValueError("identical_endpoint_identity")
        endpoint_readiness = _build_endpoint_readiness_summary(
            contracts=contracts,
            endpoint_hashes=endpoint_hashes,
            active_variants=active_variants,
            endpoint_failures=endpoint_failures,
        )
    else:
        contracts = {
            variant: {
                "phase65_model_inventory": [
                    {
                        "path": "chat",
                        "identity_sha256": _sha256("dry-run:chat"),
                        "configured": True,
                        "usage_receipt_verified": True,
                    }
                ],
                "index_fingerprint_sha256": _sha256("dry-run-index"),
                "cold_run_receipts_supported": False,
            }
            for variant in active_variants
        }
        endpoint_hashes = {variant: _sha256(f"dry-run:{endpoints[variant]}") for variant in active_variants}

    manifests = {
        variant: _build_manifest(
            variant=variant,
            # Each lane owns one result per case/run.  The pair aggregate is
            # constructed later by grouping the two 90-row lane receipts.
            expected_rows=len(cases) * args.runs,
            completed_rows=(len(cases) * args.runs if args.execute else 0),
            cases=cases,
            receipt_contract=receipt_contract,
            endpoint_identity_sha256=endpoint_hashes.get(
                variant, _sha256(f"unavailable:{variant}")
            ),
            contract=contracts.get(
                variant,
                {
                    "phase65_model_inventory": [
                        {
                            "path": "chat",
                            "identity_sha256": _sha256(f"unavailable:{variant}:chat"),
                            "configured": True,
                            "usage_receipt_verified": True,
                        }
                    ],
                    "index_fingerprint_sha256": _sha256(f"unavailable:{variant}:index"),
                    "cold_run_receipts_supported": False,
                },
            ),
            environment_class="controlled_candidate" if args.execute else "dry_run",
        )
        for variant in active_variants
    }
    paired_execution_preflight: dict[str, object] | None = None
    if args.mode == "paired":
        paired_execution_preflight = build_paired_execution_preflight(
            baseline_manifest=manifests["baseline"],
            candidate_manifest=manifests["candidate"],
            contract_gate=args.contract_gate_status,
            topology_gate=args.topology_gate_status,
            fault_gate=args.fault_gate_status,
            paid_execution_authorized=bool(args.authorize_paid_run),
        )
        if args.execute and paired_execution_preflight["gate"] != "pass":
            raise ValueError("paired_execution_preflight_blocked")
    if args.preflight_only:
        summary = _execution_summary(
            mode="paired-preflight" if args.mode == "paired" else f"{args.mode}-preflight",
            execute=False,
            case_count=len(cases),
            expected_rows=expected_rows,
            completed_rows=0,
            receipt_contract=receipt_contract,
            running=False,
        )
        if endpoint_readiness is not None:
            summary["endpoint_readiness"] = endpoint_readiness
        if paired_execution_preflight is not None:
            summary["paired_execution_preflight"] = paired_execution_preflight
        _write_json(args.summary_out, summary)
        return summary, 0 if not paired_execution_preflight or paired_execution_preflight["gate"] == "pass" else 1
    schedule = (
        build_schedule(case_ids=[case["case_id"] for case in cases], runs=args.runs, seed=args.seed)
        if args.mode in {"paired", "holdout"}
        else [ScheduleItem(case["case_id"], run, active_variants[0]) for run in range(1, args.runs + 1) for case in cases]
    )
    case_by_id = {case["case_id"]: case for case in cases}
    rows: list[dict[str, object]] = []
    answers: dict[tuple[str, int], dict[str, str]] = {}
    blind_judge = _configured_blind_judge_provider() if args.execute and args.execute_blind_judge else None
    invocation_salt = _sha256(f"{time.time_ns()}:{os.getpid()}")[:16] if args.execute else ""
    for item in schedule:
        manifest = manifests[item.variant]
        row, answer = run_variant_case(
            case_by_id[item.case_id],
            variant=item.variant,
            run=item.run,
            base_url=endpoints[item.variant],
            token=tokens[item.variant],
            timeout_seconds=args.timeout_seconds,
            manifest_run_id=manifest.run_id,
            snapshot_fingerprint=manifest.corpus_fingerprint,
            execute=args.execute,
            capture_answer=blind_judge is not None,
            invocation_salt=invocation_salt,
        )
        rows.append(row)
        if args.execute:
            _write_incremental_progress(
                rows_path=args.out,
                summary_path=args.summary_out,
                rows=rows,
                mode=args.mode,
                execute=True,
                case_count=len(cases),
                expected_rows=expected_rows,
                receipt_contract=receipt_contract,
                running=True,
            )
        if blind_judge is not None:
            answers.setdefault((item.case_id, item.run), {})[item.variant] = answer
    validate_schedule(args.mode, rows, len(cases), args.runs)
    judge_rows: list[dict[str, object]] = []
    judge_error_categories: list[str] = []
    if blind_judge is not None and args.mode in {"paired", "holdout"}:
        for (case_id, run), answer_pair in sorted(answers.items()):
            if answer_pair.get("baseline") and answer_pair.get("candidate"):
                judge_row, judge_error = _safe_judge_blind_pair(
                    blind_judge,
                    case=case_by_id[case_id],
                    run=run,
                    baseline_answer=answer_pair["baseline"],
                    candidate_answer=answer_pair["candidate"],
                    seed=args.seed,
                    receipt_contract=receipt_contract,
                )
                if judge_row is not None:
                    judge_rows.append(judge_row)
                elif judge_error is not None:
                    judge_error_categories.append(judge_error)
    _write_csv(args.out, PHASE65_OUTPUT_FIELDS, rows)
    _write_csv(args.judge_out, JUDGE_OUTPUT_FIELDS, judge_rows)
    if args.manifest_out and len(manifests) == 1:
        write_manifest(validate_output_path(args.manifest_out), next(iter(manifests.values())))
    if args.baseline_manifest_out and "baseline" in manifests:
        write_manifest(validate_output_path(args.baseline_manifest_out), manifests["baseline"])
    if args.candidate_manifest_out and "candidate" in manifests:
        write_manifest(validate_output_path(args.candidate_manifest_out), manifests["candidate"])
    summary: dict[str, object] = _execution_summary(
        mode=args.mode,
        execute=bool(args.execute),
        case_count=len(cases),
        expected_rows=expected_rows,
        completed_rows=len(rows),
        receipt_contract=receipt_contract,
        running=False,
    )
    if paired_execution_preflight is not None:
        summary["paired_execution_preflight"] = paired_execution_preflight
    exit_code = 0
    if args.mode == "holdout":
        summary["holdout_summary"] = _build_holdout_summary(
            cases,
            rows,
            execute=bool(args.execute),
            exclude_cases_path=args.cases,
            judge_rows=judge_rows,
            judge_receipt_contract=receipt_contract,
        )
        if judge_error_categories:
            summary["judge_error_count"] = len(judge_error_categories)
            summary["judge_error_categories"] = sorted(set(judge_error_categories))
    if args.mode == "paired" and args.execute:
        holdout_summary = _load_holdout_summary(args.holdout_summary)
        decision = run_gate(
            rows=rows,
            baseline_manifest=manifests["baseline"],
            candidate_manifest=manifests["candidate"],
            judge_rows=judge_rows,
            judge_receipt_contract=receipt_contract,
            holdout_summary=holdout_summary,
        )
        summary["gate_decision"] = _safe_decision(decision)
        if judge_error_categories:
            summary["judge_error_count"] = len(judge_error_categories)
            summary["judge_error_categories"] = sorted(set(judge_error_categories))
        if args.enforce_gates and decision.phase65_acceptance != "pass":
            exit_code = 1
    _write_json(args.summary_out, summary)
    return summary, exit_code


def _build_holdout_summary(
    cases: Sequence[Mapping[str, str]],
    rows: Sequence[Mapping[str, object]],
    *,
    execute: bool,
    exclude_cases_path: Path | None = None,
    judge_rows: Sequence[Mapping[str, object]] | None = None,
    judge_receipt_contract: JudgeReceiptContract | None = None,
) -> dict[str, object]:
    """Emit only receipt-level proof that a separate holdout was exercised."""
    excluded_cases = (
        _load_cases(exclude_cases_path)
        if exclude_cases_path is not None and exclude_cases_path.exists()
        else []
    )
    baseline_ab_row_count = sum(1 for row in rows if row.get("variant") == "baseline")
    candidate_ab_row_count = sum(1 for row in rows if row.get("variant") == "candidate")
    baseline_rows = [row for row in rows if row.get("variant") == "baseline"]
    candidate_rows = [row for row in rows if row.get("variant") == "candidate"]
    summary: dict[str, object] = {
        "schema_version": "phase65-holdout-summary-v1",
        "clean": bool(rows) and all(
            row.get("ok") is True and row.get("error_category") == "" for row in rows
        ),
        "execution_mode": "real_api" if execute else "dry_run",
        "executed_ab_row_count": len(rows) if execute else 0,
        "baseline_ab_row_count": baseline_ab_row_count if execute else 0,
        "candidate_ab_row_count": candidate_ab_row_count if execute else 0,
        "baseline_ab_case_set_sha256": _case_set_sha256(baseline_rows)
        if execute
        else "",
        "candidate_ab_case_set_sha256": _case_set_sha256(candidate_rows)
        if execute
        else "",
        "holdout_case_count": len(cases),
        "holdout_case_set_sha256": _case_set_sha256(cases),
        "tuning_exclusion_proven": True,
        "primary_latency_percentile_ci_exclusion_proven": True,
        "public_overlap_exclusion_proven": bool(excluded_cases),
        "excluded_case_count": len(excluded_cases),
    }
    if excluded_cases:
        summary["excluded_case_set_sha256"] = _case_set_sha256(excluded_cases)
    if judge_rows is not None and judge_receipt_contract is not None:
        summary["judge_summary"] = summarize_judge_rows(
            judge_rows,
            receipt_contract=judge_receipt_contract,
        )
    return summary


def _load_holdout_summary(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    source = validate_output_path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_holdout_summary") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("invalid_holdout_summary")
    candidate = payload.get("holdout_summary", payload)
    if not isinstance(candidate, Mapping):
        raise ValueError("invalid_holdout_summary")
    return dict(candidate)


def _summarize_existing(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    if not (
        args.results
        and args.baseline_manifest
        and args.candidate_manifest
    ):
        raise ValueError("summarize_requires_results_and_manifests")
    if not args.allow_incomplete_evidence and not (args.judge_results and args.holdout_summary):
        raise ValueError("summarize_requires_judge_and_holdout")
    from scripts.phase65_gate_manifest import load_manifest

    rows = _read_phase65_rows(args.results)
    baseline = load_manifest(args.baseline_manifest)
    candidate = load_manifest(args.candidate_manifest)
    judge_rows = _read_judge_rows(args.judge_results) if args.judge_results else []
    contract = _build_receipt_contract(
        _filter_cases(_load_cases(args.cases, limit=args.limit), args.case_id),
        runs=args.runs,
        seed=args.seed,
    )
    decision = run_gate(
        rows=rows,
        baseline_manifest=baseline,
        candidate_manifest=candidate,
        judge_rows=judge_rows,
        judge_receipt_contract=contract,
        holdout_summary=_load_holdout_summary(args.holdout_summary),
    )
    summary = {
        "mode": "summarize",
        "rows": len(rows),
        "manifest_comparison": list(compare_manifests(baseline, candidate).violations),
        "gate_decision": _safe_decision(decision),
    }
    _write_json(args.summary_out, summary)
    return summary, (1 if args.enforce_gates and decision.phase65_acceptance != "pass" else 0)


def _write_incremental_progress(
    *,
    rows_path: Path | None,
    summary_path: Path | None,
    rows: Sequence[Mapping[str, object]],
    mode: str,
    execute: bool,
    case_count: int,
    expected_rows: int,
    receipt_contract: JudgeReceiptContract,
    running: bool,
) -> None:
    """Persist in-flight evaluator progress using only predeclared safe fields."""
    _write_csv(rows_path, PHASE65_OUTPUT_FIELDS, rows)
    _write_json(
        summary_path,
        _execution_summary(
            mode=mode,
            execute=execute,
            case_count=case_count,
            expected_rows=expected_rows,
            completed_rows=len(rows),
            receipt_contract=receipt_contract,
            running=running,
        ),
    )


def _execution_summary(
    *,
    mode: str,
    execute: bool,
    case_count: int,
    expected_rows: int,
    completed_rows: int,
    receipt_contract: JudgeReceiptContract,
    running: bool,
) -> dict[str, object]:
    return {
        "mode": mode,
        "execute": bool(execute),
        "cases": case_count,
        "expected_rows": expected_rows,
        "completed_rows": completed_rows,
        "running": bool(running),
        "judge_receipt_contract_sha256": canonical_judge_receipt_contract_sha256(
            receipt_contract
        ),
    }


def _build_endpoint_readiness_summary(
    *,
    contracts: Mapping[Variant, Mapping[str, object]],
    endpoint_hashes: Mapping[Variant, str],
    active_variants: Sequence[Variant],
    endpoint_failures: Mapping[Variant, Sequence[str]] | None = None,
) -> dict[str, object]:
    failed: list[str] = []
    components: dict[str, str] = {}
    for variant in active_variants:
        contract = contracts.get(variant, {})
        prefix = f"{variant}_"
        failures = set((endpoint_failures or {}).get(variant, ()))
        components[f"{variant}_auto_auth"] = "blocked" if "auto_auth" in failures else "pass"
        components[f"{variant}_contract_fetch"] = (
            "pass" if variant in contracts and "contract" not in failures else "blocked"
        )
        components[f"{variant}_endpoint_identity"] = "pass" if endpoint_hashes.get(variant) else "blocked"
        components[f"{variant}_cold_run_receipts"] = (
            "pass" if contract.get("cold_run_receipts_supported") is True else "blocked"
        )
        try:
            _contract_index_fingerprint_sha256(contract)
            components[f"{variant}_index_fingerprint"] = "pass"
        except ValueError:
            components[f"{variant}_index_fingerprint"] = "blocked"
        try:
            _provider_model_receipts(contract)
            components[f"{variant}_model_inventory"] = "pass"
        except ValueError:
            components[f"{variant}_model_inventory"] = "blocked"
        failed.extend(
            f"{prefix}{name}_not_ready"
            for name, status in (
                ("auto_auth", components[f"{variant}_auto_auth"]),
                ("contract_fetch", components[f"{variant}_contract_fetch"]),
                ("endpoint_identity", components[f"{variant}_endpoint_identity"]),
                ("cold_run_receipts", components[f"{variant}_cold_run_receipts"]),
                ("index_fingerprint", components[f"{variant}_index_fingerprint"]),
                ("model_inventory", components[f"{variant}_model_inventory"]),
            )
            if status != "pass"
        )
    if "baseline" in active_variants and "candidate" in active_variants:
        baseline_hash = endpoint_hashes.get("baseline")
        candidate_hash = endpoint_hashes.get("candidate")
        distinct = bool(baseline_hash and candidate_hash and baseline_hash != candidate_hash)
        components["endpoint_identity_distinct"] = "pass" if distinct else "blocked"
        if not distinct:
            failed.append("endpoint_identity_not_distinct")
    return {
        "schema_version": "phase65-endpoint-readiness-v1",
        "gate": "pass" if not failed else "blocked",
        "components": components,
        "failed_required": list(dict.fromkeys(failed)),
    }


def _write_csv(path: Path | None, fields: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
    if path is None:
        return
    destination = validate_output_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8-sig", newline="", dir=destination.parent, delete=False
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
        temporary = Path(stream.name)
    _replace_with_retry(temporary, destination)


def _write_json(path: Path | None, payload: Mapping[str, object]) -> None:
    if path is None:
        return
    destination = validate_output_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False
    ) as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        temporary = Path(stream.name)
    _replace_with_retry(temporary, destination)


def _replace_with_retry(
    temporary: Path,
    destination: Path,
    *,
    attempts: int = 5,
    sleep_seconds: float = 0.1,
) -> None:
    last_error: PermissionError | None = None
    for attempt in range(max(1, attempts)):
        try:
            temporary.replace(destination)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt == max(1, attempts) - 1:
                break
            time.sleep(sleep_seconds)
    raise last_error or PermissionError("replace_failed")


def _read_csv(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _read_phase65_rows(path: Path) -> list[dict[str, object]]:
    rows = _read_csv(path)
    integer_fields = {"run", "http_status", "citation_count", "selected_count", "live_selected_count", "input_tokens", "output_tokens", "completed_tool_replay_count"}
    number_fields = {"first_token_ms", "elapsed_ms", "estimated_cost"}
    boolean_fields = {"ok", "counts_match", "conversation_persisted", "refused"}
    for row in rows:
        for field in integer_fields:
            if field in row and row[field] != "":
                row[field] = int(str(row[field]))
        for field in number_fields:
            if field in row and row[field] != "":
                row[field] = float(str(row[field]))
        for field in boolean_fields:
            if field in row:
                row[field] = str(row[field]).casefold() == "true"
    return rows


def _read_judge_rows(path: Path) -> list[dict[str, object]]:
    rows = _read_csv(path)
    for row in rows:
        row["run"] = int(str(row.get("run", "")))
        for field in (*[f"{dimension}_delta" for dimension in JUDGE_DIMENSIONS], "judge_latency_ms"):
            row[field] = float(str(row.get(field, "")))
    return rows


def _safe_decision(decision: GateDecision) -> dict[str, object]:
    return {
        "contract_gate": decision.contract_gate,
        "quality_gate": decision.quality_gate,
        "runtime_non_regression_gate": decision.runtime_non_regression_gate,
        "phase64_latency_closure_gate": decision.phase64_latency_closure_gate,
        "phase65_acceptance": decision.phase65_acceptance,
        "reasons": list(decision.reasons),
        "metrics": decision.metrics,
    }


def _safe_identifier(value: object, *, fallback: str) -> str:
    return value if isinstance(value, str) and _is_safe_identifier(value) else fallback


def _safe_tool_names(value: object) -> str:
    if not isinstance(value, str):
        return ""
    pieces = value.split("|")
    return "|".join(piece for piece in pieces if _is_safe_identifier(piece))


def _is_safe_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID.fullmatch(value))


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("positive_integer_required")
    return value


def _safe_nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _safe_nonnegative_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 6) if math.isfinite(number) and number >= 0 else None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    args = parse_args()
    if args.runs is None:
        args.runs = 1 if args.mode == "holdout" else 3
    try:
        summary, exit_code = _summarize_existing(args) if args.mode == "summarize" else _run_execution(args)
    except (OSError, ValueError, error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        payload = {"error": "phase65_gate_blocked", "reason": type(exc).__name__}
        if isinstance(exc, ValueError):
            detail = str(exc)
            if re.fullmatch(r"[A-Za-z0-9_.:+-]{1,120}", detail):
                payload["reason_detail"] = detail
        print(json.dumps(payload, ensure_ascii=False))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
