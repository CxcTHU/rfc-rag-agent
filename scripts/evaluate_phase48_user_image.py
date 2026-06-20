from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.agent.image_analysis import UserImageAnalyzer
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.generation.vision_model import create_vision_model_provider
from app.services.retrieval.embedding import create_embedding_provider


DEFAULT_IMAGE_DIR = Path("data/evaluation/phase48_user_images")
DEFAULT_QUESTIONS_CSV = Path("data/evaluation/phase48_user_image_questions.csv")
DEFAULT_RESULTS_CSV = Path("data/evaluation/phase48_user_image_results.csv")
DEFAULT_SUMMARY_CSV = Path("data/evaluation/phase48_user_image_summary.csv")


@dataclass(frozen=True)
class UserImageQuestion:
    eval_id: str
    image_filename: str
    category: str
    question: str
    expected_refusal: bool
    expected_description_keywords: tuple[str, ...]
    expected_text_keywords: tuple[str, ...]
    expected_similar_figure_topic: tuple[str, ...]
    notes: str


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    questions = read_questions(args.questions_csv)
    validate_questions(questions, image_dir=args.image_dir)

    if args.dry_run:
        print(f"questions={len(questions)}")
        print(f"image_dir={args.image_dir}")
        print("dry_run=pass")
        return

    settings = get_settings()
    vision_provider = create_vision_model_provider(
        provider_name=settings.vision_model_provider,
        model_name=settings.vision_model_name,
        api_key=settings.vision_model_api_key,
        base_url=settings.vision_model_base_url,
        timeout_seconds=settings.vision_model_timeout_seconds,
    )
    embedding_provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    if is_deterministic_provider(getattr(vision_provider, "provider_name", "")):
        raise RuntimeError("Phase 48 user-image evaluation requires a real vision provider")
    if is_deterministic_provider(getattr(embedding_provider, "provider_name", "")):
        raise RuntimeError("Phase 48 user-image evaluation requires a real embedding provider")

    args.results_csv.parent.mkdir(parents=True, exist_ok=True)
    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    with SessionLocal() as db:
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        analyzer = UserImageAnalyzer(
            vision_provider=vision_provider,
            knowledge_searcher=toolbox.hybrid_search_knowledge,
            figure_searcher=toolbox.search_figures,
            text_top_k=args.text_top_k,
            figure_top_k=args.figure_top_k,
            image_min_score=args.image_min_score,
        )
        for question in questions:
            image_path = args.image_dir / question.image_filename
            try:
                analysis = analyzer.analyze(image_path, question.question)
                record = score_record(question, analysis)
            except Exception as exc:  # noqa: BLE001 - evaluation records failures as rows.
                record = failed_record(question, exc)
            records.append(record)
            print(
                f"{record['eval_id']} refused={record['refused']} "
                f"description={record['description_accuracy']} "
                f"text={record['text_retrieval_relevance']} "
                f"image_hit={record['image_to_image_hit']}"
            )

    summary = summarize_records(records, elapsed_seconds=time.perf_counter() - started)
    write_results(args.results_csv, records)
    write_summary(args.summary_csv, summary)
    print(f"questions={len(questions)}")
    for key in (
        "description_accuracy",
        "text_retrieval_relevance",
        "image_to_image_hit_rate",
        "refusal_correctness",
        "gate_decision",
    ):
        print(f"{key}={summary[key]}")
    print(f"results_csv={args.results_csv}")
    print(f"summary_csv={args.summary_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 48 user-uploaded image analysis.")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--questions-csv", type=Path, default=DEFAULT_QUESTIONS_CSV)
    parser.add_argument("--results-csv", type=Path, default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--text-top-k", type=int, default=5)
    parser.add_argument("--figure-top-k", type=int, default=5)
    parser.add_argument("--image-min-score", type=float, default=0.55)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_questions(path: Path) -> list[UserImageQuestion]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    questions: list[UserImageQuestion] = []
    for row in rows:
        questions.append(
            UserImageQuestion(
                eval_id=require_field(row, "eval_id"),
                image_filename=require_field(row, "image_filename"),
                category=require_field(row, "category"),
                question=require_field(row, "question"),
                expected_refusal=require_field(row, "expected_refusal").casefold() == "true",
                expected_description_keywords=split_terms(row.get("expected_description_keywords", "")),
                expected_text_keywords=split_terms(row.get("expected_text_keywords", "")),
                expected_similar_figure_topic=split_terms(row.get("expected_similar_figure_topic", "")),
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


def validate_questions(questions: list[UserImageQuestion], *, image_dir: Path) -> None:
    if len(questions) < 20:
        raise ValueError("Phase 48 user-image evaluation set must contain at least 20 questions")
    missing = [question.image_filename for question in questions if not (image_dir / question.image_filename).is_file()]
    if missing:
        raise FileNotFoundError(f"missing evaluation images: {', '.join(missing)}")
    category_counts: dict[str, int] = {}
    for question in questions:
        category_counts[question.category] = category_counts.get(question.category, 0) + 1
    expected_counts = {
        "crack": 5,
        "aggregate_surface": 3,
        "test_equipment": 3,
        "construction_site": 3,
        "chart": 3,
        "negative": 3,
    }
    for category, count in expected_counts.items():
        if category_counts.get(category, 0) != count:
            raise ValueError(f"category {category} expected {count}, got {category_counts.get(category, 0)}")


def score_record(question: UserImageQuestion, analysis) -> dict[str, Any]:
    description = str(getattr(analysis, "image_description", "") or "")
    related_text_chunks = list(getattr(analysis, "related_text_chunks", []) or [])
    similar_figures = list(getattr(analysis, "similar_figures", []) or [])
    refused = getattr(analysis, "domain_relevance", "") != "in_scope"

    description_hits = term_hits(description, question.expected_description_keywords)
    text_haystack = "\n".join(str(getattr(item, "content", "") or "") for item in related_text_chunks)
    figure_haystack = "\n".join(
        " ".join(
            [
                str(getattr(item, "document_title", "") or ""),
                str(getattr(item, "caption", "") or ""),
                str(getattr(item, "description_snippet", "") or ""),
            ]
        )
        for item in similar_figures
    )

    description_accuracy = keyword_score(description_hits, question.expected_description_keywords)
    text_relevance = keyword_score(term_hits(text_haystack, question.expected_text_keywords), question.expected_text_keywords)
    image_to_image_hit = (
        question.expected_refusal
        or any(term.casefold() in figure_haystack.casefold() for term in question.expected_similar_figure_topic)
    )
    refusal_correct = refused if question.expected_refusal else not refused

    return {
        "eval_id": question.eval_id,
        "category": question.category,
        "image_filename": question.image_filename,
        "expected_refusal": str(question.expected_refusal).lower(),
        "refused": str(refused).lower(),
        "domain_relevance": str(getattr(analysis, "domain_relevance", "")),
        "description_accuracy": format_float(description_accuracy),
        "description_hits": "|".join(description_hits),
        "text_retrieval_relevance": format_float(text_relevance),
        "text_hits": "|".join(term_hits(text_haystack, question.expected_text_keywords)),
        "image_to_image_hit": str(bool(image_to_image_hit)).lower(),
        "similar_figure_count": str(len(similar_figures)),
        "related_text_count": str(len(related_text_chunks)),
        "refusal_correct": str(bool(refusal_correct)).lower(),
        "error": "",
    }


def failed_record(question: UserImageQuestion, exc: Exception) -> dict[str, Any]:
    return {
        "eval_id": question.eval_id,
        "category": question.category,
        "image_filename": question.image_filename,
        "expected_refusal": str(question.expected_refusal).lower(),
        "refused": "true",
        "domain_relevance": "error",
        "description_accuracy": "0.0000",
        "description_hits": "",
        "text_retrieval_relevance": "0.0000",
        "text_hits": "",
        "image_to_image_hit": str(question.expected_refusal).lower(),
        "similar_figure_count": "0",
        "related_text_count": "0",
        "refusal_correct": str(question.expected_refusal).lower(),
        "error": sanitize_error(exc),
    }


def term_hits(text: str, terms: tuple[str, ...]) -> list[str]:
    haystack = text.casefold()
    return [term for term in terms if term.casefold() in haystack]


def keyword_score(hits: list[str], terms: tuple[str, ...]) -> float:
    if not terms:
        return 1.0
    return 1.0 if hits else 0.0


def summarize_records(records: list[dict[str, Any]], *, elapsed_seconds: float) -> dict[str, str]:
    description_accuracy = average_float(records, "description_accuracy")
    text_relevance = average_float([row for row in records if row["expected_refusal"] == "false"], "text_retrieval_relevance")
    positive_rows = [row for row in records if row["expected_refusal"] == "false"]
    image_hit_rate = boolean_rate(positive_rows, "image_to_image_hit")
    refusal_correctness = boolean_rate(records, "refusal_correct")
    gate_pass = (
        description_accuracy >= 0.75
        and text_relevance >= 0.70
        and image_hit_rate >= 0.60
        and refusal_correctness >= 0.90
    )
    category_counts: dict[str, int] = {}
    for row in records:
        category = str(row["category"])
        category_counts[category] = category_counts.get(category, 0) + 1
    return {
        "question_count": str(len(records)),
        "elapsed_seconds": format_float(elapsed_seconds),
        "description_accuracy": format_float(description_accuracy),
        "text_retrieval_relevance": format_float(text_relevance),
        "image_to_image_hit_rate": format_float(image_hit_rate),
        "refusal_correctness": format_float(refusal_correctness),
        "gate_decision": "PASS" if gate_pass else "FAIL",
        "category_counts": ";".join(f"{key}:{category_counts[key]}" for key in sorted(category_counts)),
    }


def average_float(records: list[dict[str, Any]], key: str) -> float:
    if not records:
        return 0.0
    return sum(float(row[key]) for row in records) / len(records)


def boolean_rate(records: list[dict[str, Any]], key: str) -> float:
    if not records:
        return 0.0
    return sum(1 for row in records if str(row[key]).casefold() == "true") / len(records)


def write_results(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "eval_id",
        "category",
        "image_filename",
        "expected_refusal",
        "refused",
        "domain_relevance",
        "description_accuracy",
        "description_hits",
        "text_retrieval_relevance",
        "text_hits",
        "image_to_image_hit",
        "similar_figure_count",
        "related_text_count",
        "refusal_correct",
        "error",
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


def is_deterministic_provider(provider_name: str) -> bool:
    return provider_name.strip().casefold() in {"", "deterministic", "fake", "local"}


def sanitize_error(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    return message[:240]


def format_float(value: float) -> str:
    return f"{value:.4f}"


if __name__ == "__main__":
    main()
