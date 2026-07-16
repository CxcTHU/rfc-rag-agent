"""Safe Phase 66 runtime-convergence acceptance scaffold.

This script owns Phase 66's fresh evidence manifest and receipt validation.  It
does not reuse Phase 65 result files as acceptance evidence and it does not
pretend that dry-run validation is a quality pass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_regression_cases import load_agent_regression_cases


PHASE = 66
BASELINE_HEAD = "be23e215"
EMPTY_TRACKED_DIFF_SHA256 = hashlib.sha256(b"").hexdigest()
JUDGE_ANSWER_CHAR_LIMIT = 8000
JUDGE_SOURCE_LIMIT = 12
JUDGE_SOURCE_CONTENT_CHAR_LIMIT = 1200
JUDGE_CITATION_LIMIT = 50
JUDGE_HTTP_MAX_ATTEMPTS = 3
LATENCY_REGRESSION_RATIO = 1.20
TEXT_CASE_CATEGORIES: tuple[str, ...] = (
    "fast_text",
    "full_text",
    "figure",
    "table",
    "off_topic_refusal",
    "cache_safe",
    "checkpoint_resume",
    "cancellation",
    "provider_failure",
    "tool_failure",
)
IMAGE_CASES: tuple[str, ...] = (
    "image_only",
    "image_plus_hybrid",
    "image_plus_figure",
    "image_safe_failure",
)
MetricStatus = Literal["passed", "failed", "review_required"]


@dataclass(frozen=True)
class Phase66ManifestInputs:
    a_identity: str
    b_identity: str
    b_patch_sha256: str
    baseline_contract: Path
    repetitions: int = 1
    semantic_cache_enabled: bool = False
    tool_result_cache_enabled: bool = False


@dataclass(frozen=True)
class Phase66Case:
    case_id: str
    category: str
    modality: Literal["text", "image"]


@dataclass(frozen=True)
class Phase66HttpCase:
    case_id: str
    modality: Literal["text", "image"]
    question: str
    image_path: str = ""
    intent_category: str = ""
    expected_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    expected_refusal: bool | None = None
    expected_min_sources: int = 0
    expected_min_citations: int = 0
    latency_budget_ms: float | None = None


PostJson = Callable[[str, dict[str, object], float, str], tuple[int, dict[str, object]]]


@dataclass(frozen=True)
class Phase66Manifest:
    schema_version: str
    phase: int
    baseline_head: str
    a_identity: str
    b_identity: str
    b_patch_sha256: str
    a_tracked_diff_sha256: str
    repetitions: int
    semantic_cache_enabled: bool
    tool_result_cache_enabled: bool
    text_cases: tuple[Phase66Case, ...]
    image_cases: tuple[Phase66Case, ...]
    baseline_contract: str

    @property
    def text_case_count(self) -> int:
        return len(self.text_cases)

    @property
    def image_case_count(self) -> int:
        return len(self.image_cases)


def default_text_cases() -> tuple[Phase66Case, ...]:
    cases: list[Phase66Case] = []
    index = 1
    for category in TEXT_CASE_CATEGORIES:
        for repeat in range(3):
            cases.append(
                Phase66Case(
                    case_id=f"phase66_text_{index:02d}",
                    category=f"{category}_{repeat + 1}",
                    modality="text",
                )
            )
            index += 1
    return tuple(cases)


def default_image_cases() -> tuple[Phase66Case, ...]:
    return tuple(
        Phase66Case(
            case_id=f"phase66_image_{index:02d}",
            category=category,
            modality="image",
        )
        for index, category in enumerate(IMAGE_CASES, start=1)
    )


def build_manifest(inputs: Phase66ManifestInputs) -> Phase66Manifest:
    if inputs.a_identity == inputs.b_identity:
        raise ValueError("phase 66 requires distinct code identities")
    if inputs.repetitions != 1:
        raise ValueError("phase 66 evidence requires one cold repetition")
    if inputs.semantic_cache_enabled or inputs.tool_result_cache_enabled:
        raise ValueError("phase 66 evidence requires cold caches")
    if not _is_sha256(inputs.b_patch_sha256):
        raise ValueError("invalid B tracked patch sha256")
    if BASELINE_HEAD not in inputs.a_identity or BASELINE_HEAD not in inputs.b_identity:
        raise ValueError("phase 66 A/B identities must share the frozen baseline head")
    if "empty" not in inputs.a_identity and EMPTY_TRACKED_DIFF_SHA256 not in inputs.a_identity:
        raise ValueError("phase 66 A identity must represent an empty tracked diff")

    text_cases = default_text_cases()
    image_cases = default_image_cases()
    if len(text_cases) != 30:
        raise ValueError("phase 66 manifest must contain exactly 30 text cases")
    if len(image_cases) < 4:
        raise ValueError("phase 66 manifest must contain at least four image cases")

    return Phase66Manifest(
        schema_version="phase66-runtime-convergence-manifest-v1",
        phase=PHASE,
        baseline_head=BASELINE_HEAD,
        a_identity=inputs.a_identity,
        b_identity=inputs.b_identity,
        b_patch_sha256=inputs.b_patch_sha256,
        a_tracked_diff_sha256=EMPTY_TRACKED_DIFF_SHA256,
        repetitions=inputs.repetitions,
        semantic_cache_enabled=inputs.semantic_cache_enabled,
        tool_result_cache_enabled=inputs.tool_result_cache_enabled,
        text_cases=text_cases,
        image_cases=image_cases,
        baseline_contract=str(inputs.baseline_contract),
    )


def load_receipt(path: Path) -> dict[str, object]:
    normalized = str(path).replace("\\", "/").casefold()
    if "phase65" in normalized or "phase-65" in normalized:
        raise ValueError("phase 66 evidence cannot be satisfied by phase 65 evidence")
    payload = json.loads(path.read_text(encoding="utf-8"))
    phase = payload.get("phase")
    if phase != PHASE:
        raise ValueError("receipt is not phase 66 evidence")
    return payload


def validate_only(
    *,
    baseline: Path,
    output_root: Path,
    b_patch_sha256: str | None = None,
) -> dict[str, object]:
    baseline_payload = load_receipt(baseline)
    patch_sha = b_patch_sha256 or current_tracked_diff_sha256()
    manifest = build_manifest(
        Phase66ManifestInputs(
            a_identity=f"{BASELINE_HEAD}:empty",
            b_identity=f"{BASELINE_HEAD}:patch:{patch_sha}",
            b_patch_sha256=patch_sha,
            baseline_contract=baseline,
        )
    )
    summary = {
        "schema_version": "phase66-runtime-convergence-summary-v1",
        "phase": PHASE,
        "status": "review_required",
        "reason": "dry_run_manifest_only_no_paired_quality_evidence",
        "baseline_contract_git_head": baseline_payload.get("git_head", ""),
        "required_text_cases": manifest.text_case_count,
        "required_image_cases": manifest.image_case_count,
        "semantic_cache_enabled": manifest.semantic_cache_enabled,
        "tool_result_cache_enabled": manifest.tool_result_cache_enabled,
        "collect_a_command": (
            "python scripts/evaluate_phase66_runtime_convergence.py "
            "--collect --variant a "
            "--observations output/phase66/evaluation/a/observations.json "
            "--output-root output/phase66/evaluation/a"
        ),
        "collect_b_command": (
            "python scripts/evaluate_phase66_runtime_convergence.py "
            "--collect --variant b "
            "--observations output/phase66/evaluation/b/observations.json "
            "--output-root output/phase66/evaluation/b"
        ),
        "collect_http_a_command": (
            "python scripts/evaluate_phase66_runtime_convergence.py "
            "--collect-http --variant a --base-url http://127.0.0.1:8001 "
            "--cases data/evaluation/phase66_runtime_convergence_cases.csv "
            "--output-root output/phase66/evaluation/a"
        ),
        "collect_http_b_command": (
            "python scripts/evaluate_phase66_runtime_convergence.py "
            "--collect-http --variant b --base-url http://127.0.0.1:8011 "
            "--cases data/evaluation/phase66_runtime_convergence_cases.csv "
            "--output-root output/phase66/evaluation/b"
        ),
    }
    write_json(output_root / "manifest.json", manifest_to_json(manifest))
    write_json(output_root / "summary.json", summary)
    write_review_packet(output_root / "review-packet.md", manifest=manifest, summary=summary)
    return summary


def merge_results(*, a_results: Path, b_results: Path, output_root: Path) -> dict[str, object]:
    a_summary = load_receipt(a_results / "summary.json")
    b_summary = load_receipt(b_results / "summary.json")
    paired_text_cases = min(
        int(a_summary.get("text_case_count", 0) or 0),
        int(b_summary.get("text_case_count", 0) or 0),
    )
    paired_image_cases = min(
        int(a_summary.get("image_case_count", 0) or 0),
        int(b_summary.get("image_case_count", 0) or 0),
    )
    reason = "phase66_pairing_quality_non_regression"
    if paired_text_cases < 30 or paired_image_cases < 4:
        status: MetricStatus = "review_required"
        reason = "incomplete_phase66_pairing"
    else:
        status = compare_quality_status(a_summary, b_summary)
        if status == "failed":
            reason = "candidate_metric_regressed_or_unclassified_errors"
        elif status == "review_required":
            reason = "missing_phase66_quality_metrics"
        else:
            latency_status, latency_reason = compare_latency_status(a_summary, b_summary)
            if latency_status != "passed":
                status = latency_status
                reason = latency_reason
    summary = {
        "schema_version": "phase66-runtime-convergence-merge-v1",
        "phase": PHASE,
        "status": status,
        "reason": reason,
        "a_status": a_summary.get("status"),
        "b_status": b_summary.get("status"),
        "paired_text_cases": paired_text_cases,
        "paired_image_cases": paired_image_cases,
        "a_overall_score": a_summary.get("overall_score"),
        "b_overall_score": b_summary.get("overall_score"),
        "a_elapsed_ms_p95": a_summary.get("elapsed_ms_p95"),
        "b_elapsed_ms_p95": b_summary.get("elapsed_ms_p95"),
        "a_figure_elapsed_ms_p95": a_summary.get("figure_elapsed_ms_p95"),
        "b_figure_elapsed_ms_p95": b_summary.get("figure_elapsed_ms_p95"),
    }
    write_json(output_root / "summary.json", summary)
    write_review_packet(output_root / "review-packet.md", manifest=None, summary=summary)
    return summary


def collect_results(
    *,
    variant: Literal["a", "b"],
    observations: Path,
    output_root: Path,
) -> dict[str, object]:
    payload = load_receipt(observations)
    observation_rows = payload.get("observations")
    if not isinstance(observation_rows, list):
        raise ValueError("phase 66 collection receipt requires observations list")

    text_case_ids: set[str] = set()
    image_case_ids: set[str] = set()
    unknown_error_count = 0
    metric_names = (
        "completion_score",
        "answer_accuracy_score",
        "citation_correctness_score",
        "overall_score",
    )
    metric_values: dict[str, list[float]] = {name: [] for name in metric_names}
    elapsed_values: list[float] = []
    figure_elapsed_values: list[float] = []
    failed_case_count = 0
    judge_failed_count = 0
    contract_violation_count = 0
    for row in observation_rows:
        if not isinstance(row, dict):
            unknown_error_count += 1
            continue
        case_id = str(row.get("case_id", "")).strip()
        modality = str(row.get("modality", "")).strip()
        if modality == "text" and case_id:
            text_case_ids.add(case_id)
        elif modality == "image" and case_id:
            image_case_ids.add(case_id)
        error_category = str(row.get("error_category", "")).strip().lower()
        ok = bool(row.get("ok", False))
        if not ok:
            failed_case_count += 1
        if str(row.get("judge_status", "")).strip().lower() == "failed":
            judge_failed_count += 1
        try:
            contract_violation_count += int(row.get("contract_violation_count", 0) or 0)
        except (TypeError, ValueError):
            unknown_error_count += 1
        if error_category in {"unknown", "unclassified"} or (not ok and not error_category):
            unknown_error_count += 1
        for metric_name in metric_names:
            if metric_name in row:
                try:
                    metric_values[metric_name].append(float(row[metric_name]))
                except (TypeError, ValueError):
                    unknown_error_count += 1
        if "elapsed_ms" in row:
            try:
                elapsed_ms = float(row["elapsed_ms"])
            except (TypeError, ValueError):
                unknown_error_count += 1
            else:
                if elapsed_ms < 0:
                    unknown_error_count += 1
                else:
                    elapsed_values.append(elapsed_ms)
                    if "search_figures" in str(row.get("observed_tool_names", "")).split("|"):
                        figure_elapsed_values.append(elapsed_ms)

    text_case_count = len(text_case_ids)
    image_case_count = len(image_case_ids)
    complete_coverage = text_case_count >= 30 and image_case_count >= 4
    status: Literal["collected", "review_required", "failed"]
    if unknown_error_count:
        status = "failed"
        reason = "phase66_observations_have_unclassified_errors"
    elif failed_case_count:
        status = "review_required"
        reason = "phase66_observations_have_failed_cases"
    elif judge_failed_count:
        status = "review_required"
        reason = "phase66_observations_have_judge_failures"
    elif contract_violation_count:
        status = "review_required"
        reason = "phase66_observations_have_contract_violations"
    elif not complete_coverage:
        status = "review_required"
        reason = "incomplete_phase66_observation_coverage"
    else:
        status = "collected"
        reason = "phase66_observations_collected"

    summary: dict[str, object] = {
        "schema_version": "phase66-runtime-convergence-collection-v1",
        "phase": PHASE,
        "variant": variant,
        "status": status,
        "reason": reason,
        "text_case_count": text_case_count,
        "image_case_count": image_case_count,
        "failed_case_count": failed_case_count,
        "judge_failed_count": judge_failed_count,
        "contract_violation_count": contract_violation_count,
        "unknown_error_count": unknown_error_count,
    }
    for metric_name, values in metric_values.items():
        if values:
            summary[metric_name] = sum(values) / len(values)
    if elapsed_values:
        summary["elapsed_ms_avg"] = sum(elapsed_values) / len(elapsed_values)
        summary["elapsed_ms_p50"] = percentile(elapsed_values, 0.50)
        summary["elapsed_ms_p95"] = percentile(elapsed_values, 0.95)
    if figure_elapsed_values:
        summary["figure_elapsed_case_count"] = len(figure_elapsed_values)
        summary["figure_elapsed_ms_p50"] = percentile(figure_elapsed_values, 0.50)
        summary["figure_elapsed_ms_p95"] = percentile(figure_elapsed_values, 0.95)
    write_json(output_root / "summary.json", summary)
    write_review_packet(output_root / "review-packet.md", manifest=None, summary=summary)
    return summary


def collect_http_observations(
    *,
    variant: Literal["a", "b"],
    base_url: str,
    cases_path: Path,
    output_root: Path,
    timeout_seconds: float,
    token: str,
    post_json: PostJson | None = None,
    judge: bool = False,
    judge_post_json: PostJson | None = None,
) -> dict[str, object]:
    normalized_base_url = normalize_base_url(base_url)
    endpoint = f"{normalized_base_url}/agent/query"
    judge_endpoint = f"{normalized_base_url}/agent/judge"
    cases = load_http_cases(cases_path)
    sender = post_json or default_post_json
    judge_sender = judge_post_json or default_post_json
    observations: list[dict[str, object]] = []
    for case in cases:
        started = time.perf_counter()
        payload: dict[str, object] = {
            "question": case.question,
            "max_tool_calls": 2,
            "evaluation_run_namespace": f"phase65-phase66-{variant}",
        }
        if case.image_path:
            payload["image_path"] = case.image_path
        try:
            status_code, response_payload = sender(endpoint, payload, timeout_seconds, token)
        except (OSError, TimeoutError, error.URLError):
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
            observations.append(
                safe_observation_from_transport_error(
                    case=case,
                    elapsed_ms=elapsed_ms,
                )
            )
        else:
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
            observation = safe_observation_from_response(
                case=case,
                status_code=status_code,
                payload=response_payload,
                elapsed_ms=elapsed_ms,
            )
            if judge and 200 <= status_code < 300:
                observation.update(
                    safe_judge_scores_for_response(
                        judge_endpoint=judge_endpoint,
                        case=case,
                        payload=response_payload,
                        timeout_seconds=timeout_seconds,
                        token=token,
                        post_json=judge_sender,
                    )
                )
            observations.append(observation)

    receipt = {
        "schema_version": "phase66-http-observations-v1",
        "phase": PHASE,
        "variant": variant,
        "base_url_sha256": hashlib.sha256(normalized_base_url.encode("utf-8")).hexdigest(),
        "judge_enabled": bool(judge),
        "case_count": len(cases),
        "observations": observations,
    }
    write_json(output_root / "observations.json", receipt)
    return collect_results(
        variant=variant,
        observations=output_root / "observations.json",
        output_root=output_root,
    )


def safe_judge_scores_for_response(
    *,
    judge_endpoint: str,
    case: Phase66HttpCase,
    payload: dict[str, object],
    timeout_seconds: float,
    token: str,
    post_json: PostJson,
) -> dict[str, object]:
    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return {"judge_status": "skipped", "judge_error_category": "missing_answer"}
    judge_payload = {
        "question": case.question,
        "answer": trim_text(answer, JUDGE_ANSWER_CHAR_LIMIT),
        "sources": safe_judge_sources(payload.get("sources")),
        "citations": safe_judge_citations(payload.get("citations")),
        "refused": bool(payload.get("refused", False)),
        "refusal_reason": payload.get("refusal_reason") if isinstance(payload.get("refusal_reason"), str) else None,
    }
    response_payload: dict[str, object] = {}
    status_code = 0
    for attempt in range(1, JUDGE_HTTP_MAX_ATTEMPTS + 1):
        try:
            status_code, response_payload = post_json(
                judge_endpoint,
                judge_payload,
                timeout_seconds,
                token,
            )
        except (OSError, TimeoutError, error.URLError):
            if attempt >= JUDGE_HTTP_MAX_ATTEMPTS:
                return {"judge_status": "failed", "judge_error_category": "connection_error"}
            continue
        if 200 <= status_code < 300:
            break
        if not is_transient_judge_status(status_code) or attempt >= JUDGE_HTTP_MAX_ATTEMPTS:
            return {"judge_status": "failed", "judge_error_category": classify_http_status(status_code)}
    if not (200 <= status_code < 300):
        return {"judge_status": "failed", "judge_error_category": classify_http_status(status_code)}
    scores = response_payload.get("judge_scores")
    if not isinstance(scores, dict):
        return {"judge_status": "failed", "judge_error_category": "invalid_judge_response"}
    return safe_metric_scores_from_judge(scores)


def is_transient_judge_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def trim_text(value: str, limit: int) -> str:
    normalized = value.strip()
    if len(normalized) <= limit:
        return normalized
    marker = "\n[truncated]"
    return normalized[: max(0, limit - len(marker))] + marker


def safe_judge_sources(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    safe_sources: list[dict[str, object]] = []
    for raw_source in value[:JUDGE_SOURCE_LIMIT]:
        if not isinstance(raw_source, dict):
            continue
        source: dict[str, object] = {"title": trim_text(str(raw_source.get("title", "")), 300)}
        raw_content = raw_source.get("content")
        if isinstance(raw_content, str) and raw_content.strip():
            source["content"] = trim_text(raw_content, JUDGE_SOURCE_CONTENT_CHAR_LIMIT)
        raw_source_type = raw_source.get("source_type")
        if isinstance(raw_source_type, str):
            source["source_type"] = trim_text(raw_source_type, 80)
        raw_chunk_id = raw_source.get("chunk_id")
        if isinstance(raw_chunk_id, int):
            source["chunk_id"] = raw_chunk_id
        safe_sources.append(source)
    return safe_sources


def safe_judge_citations(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    citations: list[int] = []
    for item in value:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            citations.append(item)
        if len(citations) >= JUDGE_CITATION_LIMIT:
            break
    return citations


def safe_metric_scores_from_judge(scores: dict[object, object]) -> dict[str, object]:
    faithfulness = numeric_score(scores.get("faithfulness"))
    answer_coverage = numeric_score(scores.get("answer_coverage"))
    citation_support = numeric_score(scores.get("citation_support"))
    refusal_correctness = numeric_score(scores.get("refusal_correctness"))
    safety_leak_check = numeric_score(scores.get("safety_leak_check"))
    conciseness = numeric_score(scores.get("conciseness"))
    answer_accuracy_values = [
        value for value in (faithfulness, answer_coverage) if value is not None
    ]
    overall_values = [
        value
        for value in (
            faithfulness,
            answer_coverage,
            citation_support,
            refusal_correctness,
            safety_leak_check,
            conciseness,
        )
        if value is not None
    ]
    if not answer_accuracy_values or citation_support is None or not overall_values:
        return {"judge_status": "failed", "judge_error_category": "incomplete_judge_scores"}
    return {
        "judge_status": "completed",
        "answer_accuracy_score": sum(answer_accuracy_values) / len(answer_accuracy_values),
        "citation_correctness_score": citation_support,
        "overall_score": sum(overall_values) / len(overall_values),
    }


def numeric_score(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0.0 or score > 1.0:
        return None
    return score


def contract_violations_for_observation(
    *,
    case: Phase66HttpCase,
    observed_tools: tuple[str, ...],
    source_count: int,
    citation_count: int,
    refused: bool,
    elapsed_ms: float,
) -> tuple[str, ...]:
    violations: list[str] = []
    observed_set = set(observed_tools)
    for expected_tool in case.expected_tools:
        if expected_tool not in observed_set:
            violations.append(f"missing_tool:{expected_tool}")
    for forbidden_tool in case.forbidden_tools:
        if forbidden_tool in observed_set:
            violations.append(f"forbidden_tool:{forbidden_tool}")
    if case.expected_refusal is not None and refused is not case.expected_refusal:
        violations.append(f"refusal_mismatch:expected_{str(case.expected_refusal).lower()}")
    if source_count < case.expected_min_sources:
        violations.append(f"source_floor:{source_count}<{case.expected_min_sources}")
    if citation_count < case.expected_min_citations:
        violations.append(f"citation_floor:{citation_count}<{case.expected_min_citations}")
    if case.latency_budget_ms is not None and elapsed_ms > case.latency_budget_ms:
        violations.append(f"latency_budget:{elapsed_ms:.3f}>{case.latency_budget_ms:.3f}")
    return tuple(violations)


def load_http_cases(path: Path) -> tuple[Phase66HttpCase, ...]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
        fieldnames = set(rows[0].keys()) if rows else set()

    if "suite" in fieldnames and "intent_category" in fieldnames:
        return tuple(
            Phase66HttpCase(
                case_id=case.case_id,
                modality=case.modality,
                question=case.question,
                image_path=case.image_path,
                intent_category=case.intent_category,
                expected_tools=case.expected_tools,
                forbidden_tools=case.forbidden_tools,
                expected_refusal=case.expected_refusal,
                expected_min_sources=case.expected_min_sources,
                expected_min_citations=case.expected_min_citations,
                latency_budget_ms=case.latency_budget_ms,
            )
            for case in load_agent_regression_cases(path)
        )

    cases: list[Phase66HttpCase] = []
    for row in rows:
        case_id = str(row.get("case_id", "")).strip()
        modality = str(row.get("modality", "text")).strip().lower()
        question = str(row.get("question", "")).strip()
        image_path = str(row.get("image_path", "")).strip().replace("\\", "/")
        if not case_id or not question:
            raise ValueError("phase66 case requires case_id and question")
        if modality not in {"text", "image"}:
            raise ValueError("phase66 case modality must be text or image")
        if modality == "image" and not image_path:
            raise ValueError("phase66 image case requires image_path")
        cases.append(
            Phase66HttpCase(
                case_id=case_id,
                modality=modality,  # type: ignore[arg-type]
                question=question,
                image_path=image_path,
            )
        )
    if not cases:
        raise ValueError("phase66 case file must not be empty")
    return tuple(cases)


def safe_observation_from_response(
    *,
    case: Phase66HttpCase,
    status_code: int,
    payload: dict[str, object],
    elapsed_ms: float,
) -> dict[str, object]:
    ok = 200 <= status_code < 300
    error_category = "" if ok else classify_http_status(status_code)
    tool_names = safe_tool_names(payload.get("tool_calls"))
    citation_count = safe_len(payload.get("citations"))
    source_count = safe_len(payload.get("sources"))
    refused = bool(payload.get("refused", False)) if ok else False
    contract_violations = contract_violations_for_observation(
        case=case,
        observed_tools=tool_names,
        source_count=source_count,
        citation_count=citation_count,
        refused=refused,
        elapsed_ms=elapsed_ms,
    )
    return {
        "case_id": case.case_id,
        "modality": case.modality,
        "intent_category": case.intent_category,
        "ok": ok,
        "error_category": error_category,
        "http_status": status_code,
        "observed_tool_names": "|".join(tool_names),
        "observed_tool_count": len(tool_names),
        "expected_tool_names": "|".join(case.expected_tools),
        "forbidden_tool_names": "|".join(case.forbidden_tools),
        "citation_count": citation_count,
        "source_count": source_count,
        "refused": refused,
        "elapsed_ms": elapsed_ms,
        "completion_score": 1.0 if ok else 0.0,
        "contract_violations": "|".join(contract_violations),
        "contract_violation_count": len(contract_violations),
    }


def safe_observation_from_transport_error(
    *,
    case: Phase66HttpCase,
    elapsed_ms: float,
) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "modality": case.modality,
        "intent_category": case.intent_category,
        "ok": False,
        "error_category": "connection_error",
        "http_status": 0,
        "observed_tool_names": "",
        "observed_tool_count": 0,
        "expected_tool_names": "|".join(case.expected_tools),
        "forbidden_tool_names": "|".join(case.forbidden_tools),
        "citation_count": 0,
        "source_count": 0,
        "refused": False,
        "elapsed_ms": elapsed_ms,
        "completion_score": 0.0,
        "contract_violations": "connection_error",
        "contract_violation_count": 1,
    }


def normalize_base_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid_phase66_base_url")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid_phase66_base_url")
    host = parsed.hostname.lower()
    netloc = f"{host}:{parsed.port}" if parsed.port is not None else host
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))


def default_post_json(
    url: str,
    payload: dict[str, object],
    timeout_seconds: float,
    token: str,
) -> tuple[int, dict[str, object]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http_request = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", 200))
            response_body = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        status_code = int(exc.code)
        response_body = exc.read().decode("utf-8", errors="replace")
    try:
        parsed = json.loads(response_body) if response_body else {}
    except json.JSONDecodeError:
        parsed = {}
    return status_code, parsed if isinstance(parsed, dict) else {}


def safe_tool_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("tool_name", "")).strip()
            if name and all(char.isalnum() or char in "._:-" for char in name):
                names.append(name[:80])
    return tuple(names)


def safe_len(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def classify_http_status(status_code: int) -> str:
    if status_code in {401, 403, 404, 408, 409, 422, 429, 500, 502, 503, 504}:
        return f"http_{status_code}"
    if 400 <= status_code < 500:
        return "http_4xx"
    if 500 <= status_code < 600:
        return "http_5xx"
    return "http_error"


def compare_quality_status(a_summary: dict[str, object], b_summary: dict[str, object]) -> MetricStatus:
    if a_summary.get("unknown_error_count") or b_summary.get("unknown_error_count"):
        return "failed"
    metric_names = ("completion", "answer_accuracy", "citation_correctness", "overall")
    missing = [
        name
        for name in metric_names
        if f"{name}_score" not in a_summary or f"{name}_score" not in b_summary
    ]
    if missing:
        return "review_required"
    for name in metric_names:
        if float(b_summary[f"{name}_score"]) < float(a_summary[f"{name}_score"]):
            return "failed"
    return "passed"


def compare_latency_status(a_summary: dict[str, object], b_summary: dict[str, object]) -> tuple[MetricStatus, str]:
    a_elapsed_p95 = safe_float(a_summary.get("elapsed_ms_p95"))
    b_elapsed_p95 = safe_float(b_summary.get("elapsed_ms_p95"))
    if a_elapsed_p95 is None or b_elapsed_p95 is None:
        return "review_required", "missing_phase66_latency_metrics"

    a_figure_p95 = safe_float(a_summary.get("figure_elapsed_ms_p95"))
    b_figure_p95 = safe_float(b_summary.get("figure_elapsed_ms_p95"))
    if a_figure_p95 is not None and b_figure_p95 is not None:
        if latency_regressed(b_figure_p95, a_figure_p95):
            return "failed", "candidate_figure_latency_regressed"

    if latency_regressed(b_elapsed_p95, a_elapsed_p95):
        return "failed", "candidate_latency_regressed"

    return "passed", "phase66_latency_non_regression"


def latency_regressed(candidate_ms: float, baseline_ms: float) -> bool:
    if baseline_ms <= 0:
        return candidate_ms > 0
    return candidate_ms > baseline_ms * LATENCY_REGRESSION_RATIO


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * quantile) - 1))
    return ordered[index]


def safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def manifest_to_json(manifest: Phase66Manifest) -> dict[str, object]:
    payload = asdict(manifest)
    payload["text_case_count"] = manifest.text_case_count
    payload["image_case_count"] = manifest.image_case_count
    return payload


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def write_review_packet(
    path: Path,
    *,
    manifest: Phase66Manifest | None,
    summary: dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest_line = (
        f"- Required cases: {manifest.text_case_count} text, {manifest.image_case_count} image\n"
        if manifest is not None
        else ""
    )
    body = (
        "# Phase 66 Runtime Convergence Review Packet\n\n"
        f"- Status: {summary.get('status')}\n"
        f"- Phase: {summary.get('phase')}\n"
        f"{manifest_line}"
        "- This packet is safe metadata only; it must not contain prompts, answers, "
        "source text, credentials, or provider payloads.\n"
    )
    path.write_text(body, encoding="utf-8")


def current_tracked_diff_sha256() -> str:
    try:
        diff = subprocess.check_output(
            ["git", "-C", str(ROOT), "diff", "--binary"],
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        diff = b""
    return hashlib.sha256(diff).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Phase 66 runtime convergence evidence.")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--collect-http", action="store_true")
    parser.add_argument("--variant", choices=("a", "b"))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output-root", type=Path, default=ROOT / "output" / "phase66" / "evaluation")
    parser.add_argument("--a-results", type=Path)
    parser.add_argument("--b-results", type=Path)
    parser.add_argument("--b-patch-sha256")
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--base-url")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--token-env", default="PHASE66_EVAL_TOKEN")
    return parser.parse_args()


def read_token(name: str) -> str:
    import os

    token_name = name.strip()
    if not token_name or not all(char.isalnum() or char == "_" for char in token_name):
        raise ValueError("invalid_token_env")
    return os.environ.get(token_name, "").strip()


def main() -> int:
    args = parse_args()
    try:
        if args.validate_only:
            if args.baseline is None:
                raise ValueError("--baseline is required for --validate-only")
            summary = validate_only(
                baseline=args.baseline,
                output_root=args.output_root,
                b_patch_sha256=args.b_patch_sha256,
            )
        elif args.merge:
            if args.a_results is None or args.b_results is None:
                raise ValueError("--a-results and --b-results are required for --merge")
            summary = merge_results(
                a_results=args.a_results,
                b_results=args.b_results,
                output_root=args.output_root,
            )
        elif args.collect:
            if args.variant is None or args.observations is None:
                raise ValueError("--variant and --observations are required for --collect")
            summary = collect_results(
                variant=args.variant,
                observations=args.observations,
                output_root=args.output_root,
            )
        elif args.collect_http:
            if args.variant is None or args.base_url is None or args.cases is None:
                raise ValueError("--variant, --base-url and --cases are required for --collect-http")
            summary = collect_http_observations(
                variant=args.variant,
                base_url=args.base_url,
                cases_path=args.cases,
                output_root=args.output_root,
                timeout_seconds=args.timeout_seconds,
                token=read_token(args.token_env),
                judge=args.judge,
            )
        else:
            raise ValueError("choose --validate-only, --collect, --collect-http, or --merge")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"phase": PHASE, "status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
