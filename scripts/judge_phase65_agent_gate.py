"""Fail-closed safe projections for Phase 65 blind judging."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


JUDGE_DIMENSIONS = ("completion", "accuracy", "citation_support", "overall_quality")
JUDGE_SUMMARY_SCHEMA_VERSION = "phase65-judge-summary-v1"
JUDGE_MAPPING_SCHEMA_VERSION = "phase65-anonymous-mapping-v1"
JUDGE_RECEIPT_CONTRACT_SCHEMA_VERSION = "phase65-judge-receipt-contract-v1"
JUDGE_CATEGORIES = (
    "ordinary_text",
    "graph_intent",
    "table_intent",
    "visual_adjacent",
    "boundary",
)
JUDGE_OUTPUT_FIELDS = (
    "case_id",
    "run",
    "category",
    "winner",
    "mapping_hash",
    "completion_delta",
    "accuracy_delta",
    "citation_support_delta",
    "overall_quality_delta",
    "judge_latency_ms",
    "judge_provider",
    "judge_model",
    "sanitized_reason",
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SOURCE_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_SENSITIVE_PATTERNS = (
    re.compile(r"\bauthorization\s*[:=]", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|x-api-key|secret|password)\s*[:=]", re.IGNORECASE),
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"\braw[_ -]?response\b", re.IGNORECASE),
    re.compile(r"\bprovider[_ -]?payload\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class JudgeReceiptContract:
    """A safe, predeclared blind-judge set with no answer or prompt content."""

    case_set_sha256: str
    expected_pairs: tuple[tuple[str, int, str], ...]
    expected_mapping_hashes: tuple[str, ...]
    require_balanced_mapping: bool = True

    def __post_init__(self) -> None:
        mapping_hashes = set(self.expected_mapping_hashes)
        canonical_mapping_hashes = set(canonical_anonymous_mapping_hashes())
        if (
            not _SHA256_PATTERN.fullmatch(self.case_set_sha256)
            or not self.expected_pairs
            or len(self.expected_pairs) != len(self.expected_mapping_hashes)
            or not mapping_hashes
            or not mapping_hashes.issubset(canonical_mapping_hashes)
        ):
            raise ValueError("invalid_judge_receipt_contract")
        mapping_counts = {
            mapping_hash: self.expected_mapping_hashes.count(mapping_hash)
            for mapping_hash in canonical_anonymous_mapping_hashes()
        }
        if self.require_balanced_mapping:
            mapping_count_values = tuple(mapping_counts.values())
            if (
                mapping_hashes != canonical_mapping_hashes
                or min(mapping_count_values) < 1
                or abs(mapping_count_values[0] - mapping_count_values[1]) > 1
            ):
                raise ValueError("invalid_judge_receipt_contract")
        seen: set[tuple[str, int]] = set()
        for case_id, run, category in self.expected_pairs:
            if (
                not _SHA256_PATTERN.fullmatch(case_id)
                or not _strict_positive_int(run)
                or category not in JUDGE_CATEGORIES
                or (case_id, run) in seen
            ):
                raise ValueError("invalid_judge_receipt_contract")
            seen.add((case_id, run))

    @property
    def expected_count(self) -> int:
        return len(self.expected_pairs)

    def contains(self, case_id: str, run: int, category: str) -> bool:
        return (case_id, run, category) in self.expected_pairs

    def expected_mapping_hash(self, case_id: str, run: int, category: str) -> str | None:
        for receipt, mapping_hash in zip(self.expected_pairs, self.expected_mapping_hashes):
            if receipt == (case_id, run, category):
                return mapping_hash
        return None

    @property
    def canonical_sha256(self) -> str:
        return canonical_judge_receipt_contract_sha256(self)


def build_safe_judge_row(
    *,
    case_id: str,
    run: int,
    category: str,
    mapping: Mapping[str, str],
    winner_label: str,
    label_deltas: Mapping[str, float],
    judge_latency_ms: float,
    judge_provider: str,
    judge_model: str,
    reason: str,
    receipt_contract: JudgeReceiptContract,
) -> dict[str, object]:
    """Project a valid receipt-contract member without retaining raw judge data."""
    if (
        not isinstance(case_id, str)
        or not _SHA256_PATTERN.fullmatch(case_id)
        or not _strict_positive_int(run)
        or category not in JUDGE_CATEGORIES
        or not receipt_contract.contains(case_id, run, category)
    ):
        raise ValueError("blind_judge_invalid_receipt")
    _reject_sensitive(judge_provider)
    _reject_sensitive(judge_model)
    try:
        latency_ms = float(judge_latency_ms)
    except (TypeError, ValueError) as exc:
        raise ValueError("blind_judge_invalid_latency") from exc
    if not math.isfinite(latency_ms) or latency_ms < 0:
        raise ValueError("blind_judge_invalid_latency")

    normalized_mapping = {str(label): str(variant) for label, variant in mapping.items()}
    if set(normalized_mapping) != {"A", "B"} or set(normalized_mapping.values()) != {
        "baseline",
        "candidate",
    }:
        raise ValueError("blind_judge_invalid_mapping")
    direction = 1.0 if normalized_mapping["B"] == "candidate" else -1.0
    deltas: dict[str, float] = {}
    for dimension in JUDGE_DIMENSIONS:
        try:
            value = float(label_deltas[dimension])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("blind_judge_invalid_dimension") from exc
        if not math.isfinite(value):
            raise ValueError("blind_judge_invalid_dimension")
        deltas[dimension] = round(max(-1.0, min(1.0, value)) * direction, 6)

    winner = normalized_mapping.get(winner_label, "tie") if winner_label in {"A", "B"} else "tie"
    mapping_hash = anonymous_mapping_hash(normalized_mapping)
    if mapping_hash != receipt_contract.expected_mapping_hash(case_id, run, category):
        raise ValueError("blind_judge_mapping_not_scheduled")
    row = {
        "case_id": case_id,
        "run": run,
        "category": category,
        "winner": winner,
        "mapping_hash": mapping_hash,
        "completion_delta": deltas["completion"],
        "accuracy_delta": deltas["accuracy"],
        "citation_support_delta": deltas["citation_support"],
        "overall_quality_delta": deltas["overall_quality"],
        "judge_latency_ms": round(latency_ms, 3),
        "judge_provider": _canonical_id(judge_provider),
        "judge_model": _canonical_id(judge_model),
        "sanitized_reason": "judge_rationale_received"
        if str(reason).strip()
        else "judge_rationale_unavailable",
    }
    return row


def validate_safe_judge_rows(
    rows: Sequence[Mapping[str, object]], *, receipt_contract: JudgeReceiptContract
) -> bool:
    """Verify complete case/run/category and anonymous-mapping receipt coverage."""
    if len(rows) != receipt_contract.expected_count:
        return False
    seen: set[tuple[str, int, str]] = set()
    for row in rows:
        if tuple(row.keys()) != JUDGE_OUTPUT_FIELDS:
            return False
        case_id = row.get("case_id")
        run = row.get("run")
        category = row.get("category")
        if (
            not isinstance(case_id, str)
            or not _SHA256_PATTERN.fullmatch(case_id)
            or not _strict_positive_int(run)
            or not isinstance(category, str)
            or not receipt_contract.contains(case_id, run, category)
        ):
            return False
        receipt = (case_id, run, category)
        if receipt in seen:
            return False
        seen.add(receipt)
        if row.get("winner") not in {"baseline", "candidate", "tie"}:
            return False
        if not isinstance(row.get("mapping_hash"), str) or not _SHA256_PATTERN.fullmatch(
            row["mapping_hash"]
        ) or row["mapping_hash"] != receipt_contract.expected_mapping_hash(case_id, run, category):
            return False
        if not _finite_nonnegative_number(row.get("judge_latency_ms")):
            return False
        if not all(
            isinstance(row.get(field), str) and _CANONICAL_ID_PATTERN.fullmatch(row[field])
            for field in ("judge_provider", "judge_model")
        ):
            return False
        if row.get("sanitized_reason") not in {
            "judge_rationale_received",
            "judge_rationale_unavailable",
        }:
            return False
        for dimension in JUDGE_DIMENSIONS:
            value = _finite_number(row.get(f"{dimension}_delta"))
            if value is None or not -1.0 <= value <= 1.0:
                return False
    return seen == set(receipt_contract.expected_pairs)


def summarize_judge_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    seed: int = 650013,
    samples: int = 10_000,
    receipt_contract: JudgeReceiptContract | None = None,
) -> dict[str, float | int | str]:
    """Return only reproducible numeric/categorical aggregate judge evidence."""
    summary: dict[str, float | int | str] = {
        "schema_version": JUDGE_SUMMARY_SCHEMA_VERSION,
        "paired_count": len(rows),
        "judge_expected_pairs": len(rows),
        "bootstrap_seed": seed,
        "bootstrap_samples": samples,
    }
    if receipt_contract is not None:
        summary["case_set_sha256"] = receipt_contract.case_set_sha256
        summary["receipt_contract_sha256"] = receipt_contract.canonical_sha256
    for dimension in JUDGE_DIMENSIONS:
        try:
            deltas = [float(row[f"{dimension}_delta"]) for row in rows]
        except (KeyError, TypeError, ValueError):
            summary[f"{dimension}_lower_bound"] = float("nan")
            continue
        summary[f"{dimension}_lower_bound"] = paired_bootstrap_lower_bound(
            deltas, seed=seed, samples=samples
        )
    return summary


def paired_bootstrap_lower_bound(
    deltas: Sequence[float], *, seed: int = 650013, samples: int = 10_000, alpha: float = 0.05
) -> float:
    values = [float(value) for value in deltas]
    if not values or not all(math.isfinite(value) for value in values):
        return float("nan")
    if samples < 1:
        raise ValueError("samples must be positive")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")
    generator = random.Random(seed)
    size = len(values)
    means = sorted(
        sum(values[generator.randrange(size)] for _ in range(size)) / size
        for _ in range(samples)
    )
    return round(means[min(samples - 1, int(math.floor(alpha * samples)))], 6)


def _reject_sensitive(value: object) -> None:
    if (
        not isinstance(value, str)
        or not _SOURCE_LABEL_PATTERN.fullmatch(value)
        or any(pattern.search(value) for pattern in _SENSITIVE_PATTERNS)
    ):
        raise ValueError("blind_judge_unsafe_identifier")


def _canonical_id(value: str) -> str:
    return f"sha256:{_sha256(value)}"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def anonymous_mapping_hash(mapping: Mapping[str, str]) -> str:
    """Return one of the two public canonical anonymous A/B mapping digests."""
    normalized = {str(label): str(variant) for label, variant in mapping.items()}
    if normalized == {"A": "baseline", "B": "candidate"}:
        return _canonical_mapping_hash("baseline_on_a")
    if normalized == {"A": "candidate", "B": "baseline"}:
        return _canonical_mapping_hash("candidate_on_a")
    raise ValueError("blind_judge_invalid_mapping")


def canonical_anonymous_mapping_hashes() -> tuple[str, str]:
    """Return the only permitted, answer-free anonymous mapping receipt digests."""
    return (_canonical_mapping_hash("baseline_on_a"), _canonical_mapping_hash("candidate_on_a"))


def canonical_judge_receipt_contract_sha256(contract: JudgeReceiptContract) -> str:
    """Hash the complete, answer-free trusted judge receipt contract canonically."""
    payload = {
        "schema_version": JUDGE_RECEIPT_CONTRACT_SCHEMA_VERSION,
        "case_set_sha256": contract.case_set_sha256,
        "expected_pairs": [list(receipt) for receipt in contract.expected_pairs],
        "expected_mapping_hashes": list(contract.expected_mapping_hashes),
    }
    if not contract.require_balanced_mapping:
        payload["require_balanced_mapping"] = False
    return _sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def _canonical_mapping_hash(direction: str) -> str:
    payload = {
        "schema_version": JUDGE_MAPPING_SCHEMA_VERSION,
        "direction": direction,
    }
    return _sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def _strict_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_nonnegative_number(value: object) -> bool:
    number = _finite_number(value)
    return number is not None and number >= 0
