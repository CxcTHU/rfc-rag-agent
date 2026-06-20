from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import create_embedding_provider


DEFAULT_QUESTIONS_CSV = Path("data/evaluation/phase48_table_retrieval_questions.csv")
DEFAULT_RESULTS_CSV = Path("data/evaluation/phase48_table_retrieval_results.csv")
DEFAULT_SUMMARY_CSV = Path("data/evaluation/phase48_table_retrieval_summary.csv")


@dataclass(frozen=True)
class TableQuestion:
    query_id: str
    category: str
    question: str
    expected_has_table: bool
    expected_keywords: tuple[str, ...]
    expected_values: tuple[str, ...]
    notes: str


def main() -> None:
    args = parse_args()
    questions = read_questions(args.questions_csv)
    if len(questions) < 20:
        raise ValueError("Phase 48 table retrieval evaluation set must contain at least 20 questions")
    if args.dry_run:
        print(f"questions={len(questions)}")
        print("dry_run=pass")
        return

    settings = get_settings()
    provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    if provider.provider_name.strip().casefold() in {"", "deterministic", "fake", "local"}:
        raise RuntimeError("Phase 48 table retrieval evaluation requires a real embedding provider")

    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    with SessionLocal() as db:
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        for question in questions:
            result = toolbox.search_tables(question.question, top_k=args.top_k)
            record = score_record(question, result)
            records.append(record)
            print(
                f"{record['query_id']} returned={record['returned_count']} "
                f"precision_hit={record['precision_hit']} recall={record['recall']} "
                f"format={record['format_correctness']} value={record['value_accuracy']}"
            )

    summary = summarize_records(records, elapsed_seconds=time.perf_counter() - started)
    args.results_csv.parent.mkdir(parents=True, exist_ok=True)
    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)
    write_results(args.results_csv, records)
    write_summary(args.summary_csv, summary)
    print(f"questions={len(questions)}")
    for key in ("precision", "recall", "format_correctness", "value_accuracy", "gate_decision"):
        print(f"{key}={summary[key]}")
    print(f"results_csv={args.results_csv}")
    print(f"summary_csv={args.summary_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 48 table retrieval.")
    parser.add_argument("--questions-csv", type=Path, default=DEFAULT_QUESTIONS_CSV)
    parser.add_argument("--results-csv", type=Path, default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_questions(path: Path) -> list[TableQuestion]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    questions: list[TableQuestion] = []
    for row in rows:
        questions.append(
            TableQuestion(
                query_id=require_field(row, "query_id"),
                category=require_field(row, "category"),
                question=require_field(row, "question"),
                expected_has_table=require_field(row, "expected_has_table").casefold() == "true",
                expected_keywords=split_terms(row.get("expected_keywords", "")),
                expected_values=split_terms(row.get("expected_values", "")),
                notes=(row.get("notes") or "").strip(),
            )
        )
    return questions


def require_field(row: dict[str, str], field: str) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"missing required field: {field}")
    return value


def split_terms(value: str) -> tuple[str, ...]:
    return tuple(term.strip() for term in value.split("|") if term.strip())


def score_record(question: TableQuestion, result) -> dict[str, Any]:
    items = list(getattr(result, "search_results", []) or [])
    table_items = [item for item in items if getattr(item, "chunk_type", "") == "table"]
    haystack = "\n".join(
        "\n".join(
            [
                str(getattr(item, "document_title", "") or ""),
                str(getattr(item, "heading_path", "") or ""),
                str(getattr(item, "table_content", "") or ""),
                str(getattr(item, "content", "") or ""),
            ]
        )
        for item in table_items
    )
    keyword_hits = term_hits(haystack, question.expected_keywords)
    value_hits = term_hits(haystack, question.expected_values)
    has_table = bool(table_items)
    expected_hit = bool(keyword_hits or value_hits)
    precision_hit = (
        (has_table and expected_hit)
        if question.expected_has_table
        else not expected_hit
    )
    recall = 1.0 if (not question.expected_has_table or keyword_hits) else 0.0
    value_accuracy = 1.0 if (not question.expected_has_table or value_hits) else 0.0
    format_correctness = 1.0 if (
        not question.expected_has_table
        or any("|" in (getattr(item, "table_content", "") or getattr(item, "content", "")) for item in table_items)
    ) else 0.0
    return {
        "query_id": question.query_id,
        "category": question.category,
        "expected_has_table": str(question.expected_has_table).lower(),
        "returned_count": str(len(table_items)),
        "precision_hit": str(bool(precision_hit)).lower(),
        "recall": format_float(recall),
        "format_correctness": format_float(format_correctness),
        "value_accuracy": format_float(value_accuracy),
        "keyword_hits": "|".join(keyword_hits),
        "value_hits": "|".join(value_hits),
        "top_chunk_ids": "|".join(str(getattr(item, "chunk_id", "")) for item in table_items[:5]),
    }


def term_hits(text: str, terms: tuple[str, ...]) -> list[str]:
    haystack = text.casefold()
    return [term for term in terms if term.casefold() in haystack]


def summarize_records(records: list[dict[str, Any]], *, elapsed_seconds: float) -> dict[str, str]:
    precision = boolean_rate(records, "precision_hit")
    positive_records = [record for record in records if record["expected_has_table"] == "true"]
    recall = average_float(positive_records, "recall")
    format_correctness = average_float(positive_records, "format_correctness")
    value_accuracy = average_float(positive_records, "value_accuracy")
    gate_pass = precision >= 0.75 and recall >= 0.65 and format_correctness >= 0.85
    category_counts: dict[str, int] = {}
    for row in records:
        category = str(row["category"])
        category_counts[category] = category_counts.get(category, 0) + 1
    return {
        "question_count": str(len(records)),
        "elapsed_seconds": format_float(elapsed_seconds),
        "precision": format_float(precision),
        "recall": format_float(recall),
        "format_correctness": format_float(format_correctness),
        "value_accuracy": format_float(value_accuracy),
        "gate_decision": "PASS" if gate_pass else "FAIL",
        "category_counts": ";".join(f"{key}:{category_counts[key]}" for key in sorted(category_counts)),
    }


def boolean_rate(records: list[dict[str, Any]], key: str) -> float:
    if not records:
        return 0.0
    return sum(1 for row in records if str(row[key]).casefold() == "true") / len(records)


def average_float(records: list[dict[str, Any]], key: str) -> float:
    if not records:
        return 0.0
    return sum(float(row[key]) for row in records) / len(records)


def write_results(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "query_id",
        "category",
        "expected_has_table",
        "returned_count",
        "precision_hit",
        "recall",
        "format_correctness",
        "value_accuracy",
        "keyword_hits",
        "value_hits",
        "top_chunk_ids",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def write_summary(path: Path, summary: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in summary.items():
            writer.writerow({"metric": key, "value": value})


def format_float(value: float) -> str:
    return f"{value:.4f}"


if __name__ == "__main__":
    main()
