from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.agent import tools as agent_tools

from scripts.evaluate_phase46_real_image_retrieval import (
    EvaluationQuestion,
    read_questions as read_phase46_questions,
    run_evaluation,
    summarize_records,
    write_results,
    write_summary,
)


DEFAULT_QUESTIONS_CSV = Path("data/evaluation/phase48_image_edge_questions.csv")
DEFAULT_RESULTS_CSV = Path("data/evaluation/phase48_image_edge_results.csv")
DEFAULT_SUMMARY_CSV = Path("data/evaluation/phase48_image_edge_summary.csv")


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    questions = read_edge_questions(args.questions_csv)
    args.results_csv.parent.mkdir(parents=True, exist_ok=True)
    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)

    original_min_score = agent_tools.MIN_IMAGE_RELEVANCE_SCORE
    agent_tools.MIN_IMAGE_RELEVANCE_SCORE = args.min_score
    try:
        records = run_evaluation(
            questions=questions,
            database_url=args.database_url or get_settings().database_url,
            top_k=args.top_k,
            query_embedding_mode=args.query_embedding_mode,
        )
    finally:
        agent_tools.MIN_IMAGE_RELEVANCE_SCORE = original_min_score

    summary = summarize_records(
        records,
        elapsed_seconds=time.perf_counter() - started,
        min_score=args.min_score,
        query_embedding_mode=args.query_embedding_mode,
    )
    summary["edge_question_count"] = str(len(questions))
    summary["edge_categories"] = summarize_edge_categories(args.questions_csv)
    write_results(args.results_csv, records)
    write_summary(args.summary_csv, summary)

    print(f"questions={len(questions)}")
    print(f"query_embedding_mode={args.query_embedding_mode}")
    for metric in (
        "image_precision",
        "must_have_recall",
        "image_suppression",
        "topk_caption_match_rate",
        "threshold_decision",
    ):
        print(f"{metric}={summary[metric]}")
    print(f"results_csv={args.results_csv}")
    print(f"summary_csv={args.summary_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 48 image edge retrieval cases.")
    parser.add_argument("--questions-csv", type=Path, default=DEFAULT_QUESTIONS_CSV)
    parser.add_argument("--results-csv", type=Path, default=DEFAULT_RESULTS_CSV)
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--min-score", type=float, default=agent_tools.MIN_IMAGE_RELEVANCE_SCORE)
    parser.add_argument(
        "--query-embedding-mode",
        choices=["real", "stored_embedding_proxy"],
        default="real",
    )
    parser.add_argument("--database-url", default="")
    return parser.parse_args()


def read_edge_questions(path: Path) -> list[EvaluationQuestion]:
    questions = read_phase46_questions_without_size_floor(path)
    if len(questions) < 20:
        raise ValueError("Phase 48 image edge evaluation set must contain at least 20 questions")
    return questions


def read_phase46_questions_without_size_floor(path: Path) -> list[EvaluationQuestion]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    temp_path = path.with_suffix(".phase46_compatible.tmp.csv")
    fields = [
        "query_id",
        "question",
        "category",
        "expected_has_image",
        "expected_image_keywords",
        "expected_caption_keywords",
        "expected_doc_keywords",
        "expected_source_image_path",
        "expected_page_number",
        "notes",
    ]
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fields})
        try:
            return read_phase46_questions(temp_path)
        except ValueError as exc:
            if "at least 100 questions" not in str(exc):
                raise
            return [
                EvaluationQuestion(
                    query_id=(row.get("query_id") or "").strip(),
                    question=(row.get("question") or "").strip(),
                    category=(row.get("category") or "").strip(),
                    expected_has_image=(row.get("expected_has_image") or "").strip().casefold()
                    == "true",
                    expected_image_keywords=split_terms(row.get("expected_image_keywords") or ""),
                    expected_caption_keywords=split_terms(row.get("expected_caption_keywords") or ""),
                    expected_doc_keywords=split_terms(row.get("expected_doc_keywords") or ""),
                    expected_source_image_path=(row.get("expected_source_image_path") or "").strip(),
                    expected_page_number=parse_optional_int(row.get("expected_page_number") or ""),
                    notes=(row.get("notes") or "").strip(),
                )
                for row in rows
            ]
    finally:
        if temp_path.exists():
            temp_path.unlink()


def split_terms(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def parse_optional_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    return int(value)


def summarize_edge_categories(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts: dict[str, int] = {}
    for row in rows:
        key = (row.get("edge_category") or "unknown").strip() or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return ";".join(f"{key}:{counts[key]}" for key in sorted(counts))


if __name__ == "__main__":
    main()
