from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


DEFAULT_REAL_STATUS = Path("data/evaluation/stage14_real/real_config_status.csv")
DEFAULT_COMPARISON = Path("data/evaluation/stage14_embedding_comparison.csv")
DEFAULT_PROGRESS_DOC = Path("docs/progress.md")
DEFAULT_RETRY_RESULTS = Path("data/evaluation/stage16_decompose_real_retry_results.csv")
DEFAULT_OUT = Path("data/evaluation/stage16_decompose_diagnostics.csv")

DIAGNOSTIC_FIELDS = [
    "diagnostic_id",
    "suite",
    "status_before",
    "status_after",
    "error_type",
    "root_cause",
    "reproducibility",
    "safe_to_retry",
    "blocking_status",
    "evidence",
    "next_action",
]


@dataclass(frozen=True)
class DecomposeDiagnostic:
    diagnostic_id: str
    suite: str
    status_before: str
    status_after: str
    error_type: str
    root_cause: str
    reproducibility: str
    safe_to_retry: str
    blocking_status: str
    evidence: str
    next_action: str

    def to_row(self) -> dict[str, str]:
        return {
            "diagnostic_id": self.diagnostic_id,
            "suite": self.suite,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "error_type": self.error_type,
            "root_cause": self.root_cause,
            "reproducibility": self.reproducibility,
            "safe_to_retry": self.safe_to_retry,
            "blocking_status": self.blocking_status,
            "evidence": self.evidence,
            "next_action": self.next_action,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze stage-16 real decompose diagnostic status.")
    parser.add_argument("--real-status", default=str(DEFAULT_REAL_STATUS))
    parser.add_argument("--comparison", default=str(DEFAULT_COMPARISON))
    parser.add_argument("--progress-doc", default=str(DEFAULT_PROGRESS_DOC))
    parser.add_argument("--retry-results", default=str(DEFAULT_RETRY_RESULTS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    diagnostic = build_decompose_diagnostic(
        real_status_path=Path(args.real_status),
        comparison_path=Path(args.comparison),
        progress_doc_path=Path(args.progress_doc),
        retry_results_path=Path(args.retry_results),
    )
    write_diagnostics(Path(args.out), [diagnostic])
    print_summary(diagnostic, args.out)


def build_decompose_diagnostic(
    *,
    real_status_path: Path = DEFAULT_REAL_STATUS,
    comparison_path: Path = DEFAULT_COMPARISON,
    progress_doc_path: Path = DEFAULT_PROGRESS_DOC,
    retry_results_path: Path = DEFAULT_RETRY_RESULTS,
) -> DecomposeDiagnostic:
    real_status_rows = read_csv_rows(real_status_path) if real_status_path.exists() else []
    comparison_rows = read_csv_rows(comparison_path) if comparison_path.exists() else []
    progress_text = progress_doc_path.read_text(encoding="utf-8") if progress_doc_path.exists() else ""
    retry_rows = read_csv_rows(retry_results_path) if retry_results_path.exists() else []

    status_row = first_matching(real_status_rows, "suite", "decompose")
    comparison_row = first_real_config_decompose(comparison_rows)
    status_before = (
        status_row.get("status", "").strip()
        or comparison_row.get("status", "").strip()
        or "missing"
    )
    evidence_text = collect_evidence_text(status_row, comparison_row, progress_text)
    retry_summary = summarize_retry_results(retry_rows)
    if retry_summary["all_passed"]:
        evidence_text = "\n".join(piece for piece in [retry_summary["evidence"], evidence_text] if piece)
        classification = classification_for_retry_completed()
    else:
        classification = classify_error_text(status_before, evidence_text)
    evidence = sanitize_evidence(evidence_text)
    return DecomposeDiagnostic(
        diagnostic_id="stage16_decompose_001",
        suite="decompose",
        status_before=status_before,
        status_after=classification["status_after"],
        error_type=classification["error_type"],
        root_cause=classification["root_cause"],
        reproducibility=classification["reproducibility"],
        safe_to_retry=classification["safe_to_retry"],
        blocking_status=classification["blocking_status"],
        evidence=evidence,
        next_action=classification["next_action"],
    )


def summarize_retry_results(rows: list[dict[str, str]]) -> dict[str, object]:
    if not rows:
        return {"all_passed": False, "evidence": ""}
    passed_rows = [row for row in rows if is_truthy(row.get("passed", ""))]
    all_passed = len(passed_rows) == len(rows)
    decomposed = sum(1 for row in rows if is_truthy(row.get("decompose_applied", "")))
    refused = sum(1 for row in rows if is_truthy(row.get("brain_refused", "")))
    source_hit_matched = sum(1 for row in rows if is_truthy(row.get("source_hit_matched", "")))
    evidence = (
        f"stage16 real decompose retry results: passed={len(passed_rows)}/{len(rows)}, "
        f"decomposed={decomposed}, refused={refused}, source_hit_matched={source_hit_matched}/{len(rows)}"
    )
    return {"all_passed": all_passed, "evidence": evidence}


def is_truthy(value: str) -> bool:
    return value.strip().casefold() in {"true", "yes", "1"}


def classification_for_retry_completed() -> dict[str, str]:
    return classification(
        status_after="retry_completed",
        error_type="none_after_retry",
        root_cause="embedding_header_compatibility_and_chat_timeout",
        reproducibility="stage16_real_retry_results",
        safe_to_retry="no",
        blocking_status="not_blocking",
        next_action="保留阶段 16 显式真实 decompose 重试结果；后续真实复跑建议使用兼容 embedding 请求头和更长 chat timeout。",
    )


def classify_error_text(status_before: str, evidence_text: str) -> dict[str, str]:
    normalized = normalize(evidence_text)
    status = status_before.strip().casefold()
    if status == "completed":
        return classification(
            status_after="verified_completed",
            error_type="none",
            root_cause="real_decompose_completed",
            reproducibility="result_file_present",
            safe_to_retry="no",
            blocking_status="not_blocking",
            next_action="保留真实 decompose completed 结果作为发布前校准证据。",
        )
    if status in {"skipped", "missing", "missing_results"}:
        return classification(
            status_after="explicit_skip_or_missing",
            error_type="configuration_missing",
            root_cause="real_config_missing",
            reproducibility="status_file",
            safe_to_retry="yes_after_config",
            blocking_status="manual_configuration_required",
            next_action="补齐真实配置或保留 skipped/missing 作为发布前人工核验项。",
        )
    if has_any(normalized, ["unexpected_eof", "unexpected eof", "eof_while_reading", "ssl eof"]) or (
        "ssl" in normalized and "eof" in normalized
    ):
        return classification(
            status_after="classified_external_provider_error",
            error_type="ssl_eof",
            root_cause="provider_network_ssl_eof",
            reproducibility="recorded_from_stage15_real_rerun",
            safe_to_retry="yes",
            blocking_status="manual_retry_required",
            next_action="在人工核验时可显式重试真实 decompose；默认回归继续使用 deterministic baseline，不能伪造成真实通过。",
        )
    if has_any(normalized, ["read operation timed out", "timeout", "timed out"]):
        return classification(
            status_after="classified_provider_timeout",
            error_type="timeout",
            root_cause="provider_timeout",
            reproducibility="recorded_from_stage15_real_rerun",
            safe_to_retry="yes",
            blocking_status="manual_retry_required",
            next_action="人工核验时可调大 timeout 或分批重试；默认测试不访问真实 provider。",
        )
    if has_any(normalized, ["http 429", "too many requests", "rate limit", "http 5"]):
        return classification(
            status_after="classified_provider_response_error",
            error_type="provider_http_error",
            root_cause="provider_response_error",
            reproducibility="status_or_comparison_file",
            safe_to_retry="yes",
            blocking_status="manual_retry_required",
            next_action="等待限流恢复或换网络后显式重试真实 decompose。",
        )
    if has_any(normalized, ["incomplete real configuration", "api_key", "base_url", "embedding_dimension"]):
        return classification(
            status_after="classified_configuration_missing",
            error_type="configuration_missing",
            root_cause="real_config_missing",
            reproducibility="status_file",
            safe_to_retry="yes_after_config",
            blocking_status="manual_configuration_required",
            next_action="补齐 provider、model、base_url、api_key 和 dimension 后再显式复跑。",
        )
    if has_any(normalized, ["traceback", "command failed", "exit code", "partial"]):
        return classification(
            status_after="classified_script_orchestration_error",
            error_type="script_orchestration",
            root_cause="script_timeout_or_partial_output",
            reproducibility="status_file_truncated_traceback",
            safe_to_retry="yes",
            blocking_status="review_required",
            next_action="保留为人工核验项；如需进一步确认，可显式复跑并保留完整脱敏错误尾部。",
        )
    return classification(
        status_after="classified_unknown_error",
        error_type="unknown",
        root_cause="needs_manual_review",
        reproducibility="insufficient_error_summary",
        safe_to_retry="yes",
        blocking_status="review_required",
        next_action="错误摘要不足，人工核验时显式复跑或补充脱敏日志后再分类。",
    )


def classification(
    *,
    status_after: str,
    error_type: str,
    root_cause: str,
    reproducibility: str,
    safe_to_retry: str,
    blocking_status: str,
    next_action: str,
) -> dict[str, str]:
    return {
        "status_after": status_after,
        "error_type": error_type,
        "root_cause": root_cause,
        "reproducibility": reproducibility,
        "safe_to_retry": safe_to_retry,
        "blocking_status": blocking_status,
        "next_action": next_action,
    }


def collect_evidence_text(
    status_row: dict[str, str],
    comparison_row: dict[str, str],
    progress_text: str,
) -> str:
    progress_context = extract_progress_decompose_context(progress_text)
    pieces = [
        progress_context,
        status_row.get("error_summary", ""),
        status_row.get("skipped_reason", ""),
        status_row.get("notes", ""),
        comparison_row.get("skipped_reason", ""),
        comparison_row.get("notes", ""),
    ]
    return "\n".join(piece for piece in pieces if piece)


def extract_progress_decompose_context(progress_text: str) -> str:
    related_lines = [
        line.strip()
        for line in progress_text.splitlines()
        if "decompose" in line.casefold() or "ssl" in line.casefold() or "eof" in line.casefold()
    ]
    priority_lines = [
        line for line in related_lines
        if "ssl" in line.casefold() or "eof" in line.casefold() or "unexpected_eof" in line.casefold()
    ]
    fallback_lines = [line for line in related_lines if line not in priority_lines]
    return "\n".join([*priority_lines[:8], *fallback_lines[:8]])


def sanitize_evidence(text: str, limit: int = 700) -> str:
    redacted = re.sub(r"\b(?:sk|tp)-[A-Za-z0-9._-]{8,}\b", "[REDACTED]", text)
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"\s+", " ", redacted).strip()
    if len(redacted) <= limit:
        return redacted
    head = redacted[: limit // 2].rstrip()
    tail = redacted[-(limit // 2):].lstrip()
    return f"{head} ... {tail}"


def first_matching(rows: list[dict[str, str]], field: str, value: str) -> dict[str, str]:
    for row in rows:
        if row.get(field, "").strip() == value:
            return row
    return {}


def first_real_config_decompose(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if row.get("config_name", "").strip() == "real_config" and row.get("suite", "").strip() == "decompose":
            return row
    return {}


def has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_diagnostics(path: Path, diagnostics: list[DecomposeDiagnostic]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DIAGNOSTIC_FIELDS)
        writer.writeheader()
        for diagnostic in diagnostics:
            writer.writerow(diagnostic.to_row())


def print_summary(diagnostic: DecomposeDiagnostic, output_path: str) -> None:
    print(
        "stage 16 decompose diagnostic: "
        f"{diagnostic.status_before} -> {diagnostic.status_after}; "
        f"root_cause={diagnostic.root_cause}; blocking={diagnostic.blocking_status}"
    )
    print(f"wrote diagnostics to {output_path}")


if __name__ == "__main__":
    main()
