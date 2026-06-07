from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings, get_settings  # noqa: E402
from scripts.evaluate_model_configs import is_deterministic  # noqa: E402


DEFAULT_USER_QUESTION_RESULTS = Path("data/evaluation/user_question_results.csv")
DEFAULT_USER_QUESTIONS = Path("data/evaluation/user_questions.csv")
DEFAULT_DECOMPOSE_RESULTS = Path("data/evaluation/stage13_decompose_results.csv")

RESULT_FIELDS = [
    "review_id",
    "query_id",
    "config_name",
    "question",
    "expected_answer_points",
    "answer",
    "evidence_titles",
    "evidence_source_ids",
    "faithfulness",
    "answer_coverage",
    "citation_quality",
    "risk_level",
    "review_method",
    "decompose_applied",
    "provenance_summary",
    "skipped_reason",
    "recommendation",
    "notes",
]


@dataclass(frozen=True)
class CoverageReview:
    review_id: str
    query_id: str
    config_name: str
    question: str
    expected_answer_points: str
    answer: str
    evidence_titles: str
    evidence_source_ids: str
    faithfulness: str
    answer_coverage: str
    citation_quality: str
    risk_level: str
    review_method: str
    decompose_applied: str
    provenance_summary: str
    skipped_reason: str
    recommendation: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "review_id": self.review_id,
            "query_id": self.query_id,
            "config_name": self.config_name,
            "question": self.question,
            "expected_answer_points": self.expected_answer_points,
            "answer": self.answer,
            "evidence_titles": self.evidence_titles,
            "evidence_source_ids": self.evidence_source_ids,
            "faithfulness": self.faithfulness,
            "answer_coverage": self.answer_coverage,
            "citation_quality": self.citation_quality,
            "risk_level": self.risk_level,
            "review_method": self.review_method,
            "decompose_applied": self.decompose_applied,
            "provenance_summary": self.provenance_summary,
            "skipped_reason": self.skipped_reason,
            "recommendation": self.recommendation,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stage-14 answer coverage review table.")
    parser.add_argument("--user-results", default=str(DEFAULT_USER_QUESTION_RESULTS))
    parser.add_argument("--questions", default=str(DEFAULT_USER_QUESTIONS))
    parser.add_argument("--decompose-results", default=str(DEFAULT_DECOMPOSE_RESULTS))
    parser.add_argument("--out", default="data/evaluation/stage14_answer_coverage_review.csv")
    parser.add_argument("--include-config", action="append", default=["default_hybrid"])
    parser.add_argument(
        "--include-real-config",
        action="store_true",
        help="Add rows from a real user-question result file or skipped rows when chat config/results are missing.",
    )
    parser.add_argument(
        "--real-user-results",
        default="data/evaluation/stage14_real/user_question_results.csv",
        help="Precomputed real chat/embedding user question results.",
    )
    args = parser.parse_args()

    settings = get_settings()
    reviews = build_answer_coverage_reviews(
        user_results_path=Path(args.user_results),
        questions_path=Path(args.questions),
        decompose_results_path=Path(args.decompose_results),
        include_configs=tuple(args.include_config),
        include_real_config=args.include_real_config,
        real_user_results_path=Path(args.real_user_results),
        settings=settings,
    )
    write_results(Path(args.out), reviews)
    print_summary(reviews, args.out)


def build_answer_coverage_reviews(
    *,
    user_results_path: Path = DEFAULT_USER_QUESTION_RESULTS,
    questions_path: Path = DEFAULT_USER_QUESTIONS,
    decompose_results_path: Path | None = DEFAULT_DECOMPOSE_RESULTS,
    include_configs: tuple[str, ...] = ("default_hybrid",),
    include_real_config: bool = False,
    real_user_results_path: Path | None = None,
    settings: Settings | None = None,
) -> list[CoverageReview]:
    expected_questions = read_questions(questions_path)
    decompose_by_query = read_decompose_results(decompose_results_path) if decompose_results_path else {}
    user_rows = read_csv_rows(user_results_path)
    reviews = reviews_from_user_rows(
        user_rows=user_rows,
        expected_questions=expected_questions,
        decompose_by_query=decompose_by_query,
        include_configs=include_configs,
        review_prefix="stage14_det",
        review_method="deterministic_rule_review",
    )

    if not include_real_config:
        return reviews

    active_settings = settings or get_settings()
    skipped_reason = real_chat_skipped_reason(active_settings)
    if skipped_reason:
        reviews.extend(skipped_real_reviews(expected_questions, skipped_reason))
        return reviews

    real_path = real_user_results_path or Path("data/evaluation/stage14_real/user_question_results.csv")
    if not real_path.exists():
        reviews.extend(skipped_real_reviews(expected_questions, f"Missing result file: {real_path}"))
        return reviews

    real_rows = read_csv_rows(real_path)
    reviews.extend(
        reviews_from_user_rows(
            user_rows=real_rows,
            expected_questions=expected_questions,
            decompose_by_query=decompose_by_query,
            include_configs=("default_hybrid",),
            review_prefix="stage14_real",
            review_method="real_model_review",
            output_config_name="real_config",
        )
    )
    return reviews


def reviews_from_user_rows(
    *,
    user_rows: list[dict[str, str]],
    expected_questions: dict[str, dict[str, str]],
    decompose_by_query: dict[str, dict[str, str]],
    include_configs: tuple[str, ...],
    review_prefix: str,
    review_method: str,
    output_config_name: str | None = None,
) -> list[CoverageReview]:
    reviews: list[CoverageReview] = []
    selected_rows = [
        row for row in user_rows
        if row.get("config_name", "").strip() in include_configs
    ]
    for index, row in enumerate(selected_rows, start=1):
        query_id = row.get("query_id", "").strip()
        expected = expected_questions.get(query_id, {})
        decompose = decompose_by_query.get(query_id, {})
        faithfulness, answer_coverage, citation_quality = score_row(row)
        risk_level = risk_from_scores(faithfulness, answer_coverage, citation_quality)
        reviews.append(
            CoverageReview(
                review_id=f"{review_prefix}_{index:03d}",
                query_id=query_id,
                config_name=output_config_name or row.get("config_name", "").strip(),
                question=row.get("question", "").strip(),
                expected_answer_points=(
                    row.get("expected_answer_points", "").strip()
                    or expected.get("expected_answer_points", "").strip()
                ),
                answer=row.get("answer", "").strip(),
                evidence_titles=row.get("top_source_titles", "").strip(),
                evidence_source_ids=row.get("citations", "").strip(),
                faithfulness=faithfulness,
                answer_coverage=answer_coverage,
                citation_quality=citation_quality,
                risk_level=risk_level,
                review_method=review_method,
                decompose_applied=decompose.get("decompose_applied", ""),
                provenance_summary=build_provenance_summary(decompose),
                skipped_reason="",
                recommendation=recommendation_for_scores(
                    row=row,
                    faithfulness=faithfulness,
                    answer_coverage=answer_coverage,
                    citation_quality=citation_quality,
                ),
                notes=row.get("notes", "").strip(),
            )
        )
    return reviews


def score_row(row: dict[str, str]) -> tuple[str, str, str]:
    expected_refused = parse_bool(row.get("expected_refused", ""))
    refused = parse_bool(row.get("refused", ""))
    returned_answer = parse_bool(row.get("returned_answer", ""))
    source_hit_matched = parse_bool(row.get("source_hit_matched", ""))
    citations_valid = parse_bool(row.get("citations_valid", ""))
    forbidden_absent = parse_bool(row.get("forbidden_terms_absent", "yes"))
    workflow_succeeded = parse_bool(row.get("workflow_succeeded", "yes"))

    if expected_refused and refused:
        return "pass", "pass", "pass"
    if not workflow_succeeded or not returned_answer or not forbidden_absent:
        return "fail", "fail", "fail"

    faithfulness = "pass" if forbidden_absent and source_hit_matched else "review"
    if not source_hit_matched:
        answer_coverage = "fail"
    elif is_deterministic(row.get("model_provider")):
        answer_coverage = "review"
    else:
        answer_coverage = "pass"
    citation_quality = "pass" if citations_valid and source_hit_matched else "review"
    return faithfulness, answer_coverage, citation_quality


def risk_from_scores(faithfulness: str, answer_coverage: str, citation_quality: str) -> str:
    scores = {faithfulness, answer_coverage, citation_quality}
    if "fail" in scores:
        return "high"
    if "review" in scores:
        return "medium"
    return "low"


def recommendation_for_scores(
    *,
    row: dict[str, str],
    faithfulness: str,
    answer_coverage: str,
    citation_quality: str,
) -> str:
    if parse_bool(row.get("expected_refused", "")) and parse_bool(row.get("refused", "")):
        return "保留为拒答回归样例。"
    if answer_coverage == "fail":
        return "优先复核检索来源和真实 embedding 配置，再进行真实模型回答校准。"
    if answer_coverage == "review" or citation_quality == "review" or faithfulness == "review":
        return "使用真实模型回答或人工摘要复核 Answer Coverage、Faithfulness 和 Citation Quality。"
    return "当前样例低风险，保留为阶段 14 质量对照。"


def build_provenance_summary(decompose: dict[str, str]) -> str:
    if not decompose:
        return ""
    parts = []
    if decompose.get("sub_queries"):
        parts.append(f"sub_queries={decompose['sub_queries']}")
    if decompose.get("deduplicated_count"):
        parts.append(f"deduplicated_count={decompose['deduplicated_count']}")
    if decompose.get("provenance_present"):
        parts.append(f"provenance_present={decompose['provenance_present']}")
    if decompose.get("rerank_explanations"):
        parts.append(f"rerank_explanations={decompose['rerank_explanations'][:240]}")
    return " ; ".join(parts)


def skipped_real_reviews(
    expected_questions: dict[str, dict[str, str]],
    skipped_reason: str,
) -> list[CoverageReview]:
    reviews = []
    for index, (query_id, question) in enumerate(expected_questions.items(), start=1):
        reviews.append(
            CoverageReview(
                review_id=f"stage14_real_skipped_{index:03d}",
                query_id=query_id,
                config_name="real_config",
                question=question.get("question", ""),
                expected_answer_points=question.get("expected_answer_points", ""),
                answer="",
                evidence_titles="",
                evidence_source_ids="",
                faithfulness="skipped",
                answer_coverage="skipped",
                citation_quality="skipped",
                risk_level="skipped",
                review_method="real_model_review",
                decompose_applied="",
                provenance_summary="",
                skipped_reason=skipped_reason,
                recommendation="真实模型结果缺失，保留 deterministic 校准表并等待显式真实评测结果。",
                notes=question.get("notes", ""),
            )
        )
    return reviews


def read_questions(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_rows(path)
    return {row["query_id"].strip(): row for row in rows if row.get("query_id")}


def read_decompose_results(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows = read_csv_rows(path)
    return {row["query_id"].strip(): row for row in rows if row.get("query_id")}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def real_chat_skipped_reason(settings: Settings) -> str:
    missing: list[str] = []
    if is_deterministic(settings.chat_model_provider):
        missing.append("CHAT_MODEL_PROVIDER")
    if not settings.chat_model_name.strip():
        missing.append("CHAT_MODEL_NAME")
    if not settings.chat_model_api_key.strip():
        missing.append("CHAT_MODEL_API_KEY")
    if not settings.chat_model_base_url.strip():
        missing.append("CHAT_MODEL_BASE_URL")
    if missing:
        return "Incomplete real chat configuration: " + ", ".join(missing)
    return ""


def parse_bool(value: str) -> bool:
    return value.strip().casefold() in {"yes", "true", "1", "y", "pass", "passed"}


def write_results(path: Path, results: list[CoverageReview]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[CoverageReview], output_path: str) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.risk_level] = counts.get(result.risk_level, 0) + 1
    print(f"stage 14 answer coverage review: {len(results)} rows")
    print("risk counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"wrote results to {output_path}")


if __name__ == "__main__":
    main()
