from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


VALID_MODALITIES = {"text", "image"}
VALID_REFUSAL_VALUES = {"true", "false"}
REQUIRED_COLUMNS = {
    "case_id",
    "suite",
    "modality",
    "question",
    "image_path",
    "intent_category",
    "expected_tools",
    "forbidden_tools",
    "expected_refusal",
    "expected_min_sources",
    "expected_min_citations",
    "latency_budget_ms",
    "notes",
}


@dataclass(frozen=True)
class AgentRegressionCase:
    case_id: str
    suite: str
    modality: Literal["text", "image"]
    question: str
    image_path: str
    intent_category: str
    expected_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    expected_refusal: bool | None
    expected_min_sources: int
    expected_min_citations: int
    latency_budget_ms: float | None
    notes: str


def parse_pipe_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value or "").split("|") if item.strip())


def parse_optional_bool(value: str) -> bool | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in VALID_REFUSAL_VALUES:
        raise ValueError(f"expected_refusal must be true or false, got {value!r}")
    return normalized == "true"


def parse_non_negative_int(value: str, *, column: str, case_id: str) -> int:
    try:
        parsed = int(str(value or "0").strip())
    except ValueError as exc:
        raise ValueError(f"{case_id} {column} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{case_id} {column} must be non-negative")
    return parsed


def parse_optional_positive_float(value: str, *, column: str, case_id: str) -> float | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        parsed = float(normalized)
    except ValueError as exc:
        raise ValueError(f"{case_id} {column} must be a number") from exc
    if parsed <= 0:
        raise ValueError(f"{case_id} {column} must be positive")
    return parsed


def load_agent_regression_cases(path: Path) -> tuple[AgentRegressionCase, ...]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or ())
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(f"agent regression case file missing columns: {', '.join(missing)}")
        rows = list(reader)

    cases: list[AgentRegressionCase] = []
    seen_ids: set[str] = set()
    for row_index, row in enumerate(rows, start=2):
        case_id = str(row.get("case_id", "")).strip()
        suite = str(row.get("suite", "")).strip()
        modality = str(row.get("modality", "")).strip().lower()
        question = str(row.get("question", "")).strip()
        image_path = str(row.get("image_path", "")).strip().replace("\\", "/")
        intent_category = str(row.get("intent_category", "")).strip()

        if not case_id:
            raise ValueError(f"row {row_index} requires case_id")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)
        if not suite:
            raise ValueError(f"{case_id} requires suite")
        if modality not in VALID_MODALITIES:
            raise ValueError(f"{case_id} modality must be text or image")
        if not question:
            raise ValueError(f"{case_id} requires question")
        if modality == "image" and not image_path:
            raise ValueError(f"{case_id} image case requires image_path")
        if not intent_category:
            raise ValueError(f"{case_id} requires intent_category")

        cases.append(
            AgentRegressionCase(
                case_id=case_id,
                suite=suite,
                modality=modality,  # type: ignore[arg-type]
                question=question,
                image_path=image_path,
                intent_category=intent_category,
                expected_tools=parse_pipe_list(str(row.get("expected_tools", ""))),
                forbidden_tools=parse_pipe_list(str(row.get("forbidden_tools", ""))),
                expected_refusal=parse_optional_bool(str(row.get("expected_refusal", ""))),
                expected_min_sources=parse_non_negative_int(
                    str(row.get("expected_min_sources", "0")),
                    column="expected_min_sources",
                    case_id=case_id,
                ),
                expected_min_citations=parse_non_negative_int(
                    str(row.get("expected_min_citations", "0")),
                    column="expected_min_citations",
                    case_id=case_id,
                ),
                latency_budget_ms=parse_optional_positive_float(
                    str(row.get("latency_budget_ms", "")),
                    column="latency_budget_ms",
                    case_id=case_id,
                ),
                notes=str(row.get("notes", "")).strip(),
            )
        )

    if not cases:
        raise ValueError("agent regression case file must not be empty")
    return tuple(cases)
