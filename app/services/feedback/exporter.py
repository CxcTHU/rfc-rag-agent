from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import QAFeedback
from app.services.feedback.feedback_service import FeedbackService
from app.services.feedback.keyword_extractor import extract_keywords


DEFAULT_OUTPUT_PATH = Path("data/evaluation/phase47_user_feedback_eval.csv")
FIELDNAMES = [
    "query_id",
    "question",
    "expected_answer_keywords",
    "difficulty",
    "category",
    "source",
]
SENSITIVE_PATTERNS = (
    re.compile(r"\bapi[_-]?key\b", re.IGNORECASE),
    re.compile(r"\bauthorization\b", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{12,}\b"),
)


@dataclass(frozen=True)
class FeedbackExportResult:
    rows: list[dict[str, str]]
    output_path: Path
    dry_run: bool
    candidates: int
    exported: int
    skipped_sensitive: int
    skipped_duplicate: int


def export_feedback_to_eval(
    db: Session,
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    min_length: int = 50,
    since_days: int | None = None,
    dry_run: bool = False,
) -> FeedbackExportResult:
    service = FeedbackService(db)
    candidates = service.get_positive_feedback_for_export(
        min_answer_length=min_length,
        since_days=since_days,
    )
    rows, skipped_sensitive, skipped_duplicate = build_export_rows(candidates)
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
    return FeedbackExportResult(
        rows=rows,
        output_path=output_path,
        dry_run=dry_run,
        candidates=len(candidates),
        exported=len(rows),
        skipped_sensitive=skipped_sensitive,
        skipped_duplicate=skipped_duplicate,
    )


def build_export_rows(feedback_items: list[QAFeedback]) -> tuple[list[dict[str, str]], int, int]:
    rows: list[dict[str, str]] = []
    seen_questions: set[str] = set()
    skipped_sensitive = 0
    skipped_duplicate = 0
    for feedback in feedback_items:
        question_key = normalize_question(feedback.question)
        if question_key in seen_questions:
            skipped_duplicate += 1
            continue
        seen_questions.add(question_key)
        if contains_sensitive_material(feedback.question, feedback.answer, feedback.comment):
            skipped_sensitive += 1
            continue
        rows.append(
            {
                "query_id": f"feedback_{len(rows) + 1:03d}",
                "question": feedback.question.strip(),
                "expected_answer_keywords": ",".join(extract_keywords(feedback.answer, top_k=5)),
                "difficulty": "medium",
                "category": classify_feedback_question(feedback.question),
                "source": "user_feedback",
            }
        )
    return rows, skipped_sensitive, skipped_duplicate


def contains_sensitive_material(*values: str | None) -> bool:
    text = "\n".join(value or "" for value in values)
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


def classify_feedback_question(question: str) -> str:
    normalized = question.casefold()
    if any(term in normalized for term in ("crack", "裂缝", "defect")):
        return "structural_defect"
    if any(term in normalized for term in ("mix ratio", "配合比", "water-cement")):
        return "mix_design"
    if any(term in normalized for term in ("strength", "强度", "modulus")):
        return "mechanical_property"
    if any(term in normalized for term in ("table", "表格")):
        return "table_evidence"
    if any(term in normalized for term in ("image", "figure", "图片", "图")):
        return "image_evidence"
    return "general"


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().casefold())
