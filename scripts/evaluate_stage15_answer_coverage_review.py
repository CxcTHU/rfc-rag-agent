from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


DEFAULT_STAGE14_REVIEW = Path("data/evaluation/stage14_answer_coverage_review.csv")
DEFAULT_REAL_USER_RESULTS = Path("data/evaluation/stage14_real/user_question_results.csv")

RESULT_FIELDS = [
    "review_id",
    "source_review_id",
    "query_id",
    "config_name",
    "question",
    "expected_answer_points",
    "answer_summary",
    "evidence_titles",
    "faithfulness",
    "answer_coverage",
    "citation_quality",
    "risk_level",
    "review_method",
    "review_note",
    "next_action",
    "skipped_reason",
]


@dataclass(frozen=True)
class Stage15CoverageReview:
    review_id: str
    source_review_id: str
    query_id: str
    config_name: str
    question: str
    expected_answer_points: str
    answer_summary: str
    evidence_titles: str
    faithfulness: str
    answer_coverage: str
    citation_quality: str
    risk_level: str
    review_method: str
    review_note: str
    next_action: str
    skipped_reason: str = ""

    def to_row(self) -> dict[str, str]:
        return {
            "review_id": self.review_id,
            "source_review_id": self.source_review_id,
            "query_id": self.query_id,
            "config_name": self.config_name,
            "question": self.question,
            "expected_answer_points": self.expected_answer_points,
            "answer_summary": self.answer_summary,
            "evidence_titles": self.evidence_titles,
            "faithfulness": self.faithfulness,
            "answer_coverage": self.answer_coverage,
            "citation_quality": self.citation_quality,
            "risk_level": self.risk_level,
            "review_method": self.review_method,
            "review_note": self.review_note,
            "next_action": self.next_action,
            "skipped_reason": self.skipped_reason,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stage-15 answer coverage review table.")
    parser.add_argument("--stage14-review", default=str(DEFAULT_STAGE14_REVIEW))
    parser.add_argument("--real-user-results", default=str(DEFAULT_REAL_USER_RESULTS))
    parser.add_argument("--out", default="data/evaluation/stage15_answer_coverage_review.csv")
    parser.add_argument("--include-low-risk", action="store_true")
    args = parser.parse_args()

    reviews = build_stage15_reviews(
        stage14_review_path=Path(args.stage14_review),
        real_user_results_path=Path(args.real_user_results),
        include_low_risk=args.include_low_risk,
    )
    write_results(Path(args.out), reviews)
    print_summary(reviews, args.out)


def build_stage15_reviews(
    *,
    stage14_review_path: Path = DEFAULT_STAGE14_REVIEW,
    real_user_results_path: Path = DEFAULT_REAL_USER_RESULTS,
    include_low_risk: bool = False,
) -> list[Stage15CoverageReview]:
    stage14_rows = read_csv_rows(stage14_review_path)
    real_rows = read_csv_rows(real_user_results_path) if real_user_results_path.exists() else []
    real_default_by_query = {
        row.get("query_id", "").strip(): row
        for row in real_rows
        if row.get("config_name", "").strip() == "default_hybrid"
    }

    selected = [
        row for row in stage14_rows
        if include_low_risk or should_review(row)
    ]
    return [
        review_stage14_row(
            index=index,
            stage14_row=row,
            real_row=real_default_by_query.get(row.get("query_id", "").strip()),
        )
        for index, row in enumerate(selected, start=1)
    ]


def should_review(row: dict[str, str]) -> bool:
    risk_level = row.get("risk_level", "").strip().casefold()
    answer_coverage = row.get("answer_coverage", "").strip().casefold()
    config_name = row.get("config_name", "").strip()
    return config_name == "default_hybrid" and (risk_level == "medium" or answer_coverage == "review")


def review_stage14_row(
    *,
    index: int,
    stage14_row: dict[str, str],
    real_row: dict[str, str] | None,
) -> Stage15CoverageReview:
    query_id = stage14_row.get("query_id", "").strip()
    expected_points = stage14_row.get("expected_answer_points", "").strip()
    if real_row is None:
        return Stage15CoverageReview(
            review_id=f"stage15_review_{index:03d}",
            source_review_id=stage14_row.get("review_id", "").strip(),
            query_id=query_id,
            config_name="real_config",
            question=stage14_row.get("question", "").strip(),
            expected_answer_points=expected_points,
            answer_summary="",
            evidence_titles=stage14_row.get("evidence_titles", "").strip(),
            faithfulness="skipped",
            answer_coverage="skipped",
            citation_quality="skipped",
            risk_level="skipped",
            review_method="skipped_no_real_answer",
            review_note="No real default_hybrid result was available for this query.",
            next_action="保留阶段 14 review 结论，等待真实回答结果或人工复核。",
            skipped_reason=f"Missing real default_hybrid result for query_id={query_id}",
        )

    faithfulness, answer_coverage, citation_quality = score_real_row(real_row, expected_points)
    risk_level = risk_from_scores(faithfulness, answer_coverage, citation_quality)
    return Stage15CoverageReview(
        review_id=f"stage15_review_{index:03d}",
        source_review_id=stage14_row.get("review_id", "").strip(),
        query_id=query_id,
        config_name="real_config",
        question=stage14_row.get("question", "").strip(),
        expected_answer_points=expected_points,
        answer_summary=summarize_answer(real_row.get("answer", "")),
        evidence_titles=real_row.get("top_source_titles", "").strip() or stage14_row.get("evidence_titles", "").strip(),
        faithfulness=faithfulness,
        answer_coverage=answer_coverage,
        citation_quality=citation_quality,
        risk_level=risk_level,
        review_method="real_model_summary",
        review_note=review_note_for_real_row(real_row, answer_coverage),
        next_action=next_action_for_scores(faithfulness, answer_coverage, citation_quality),
    )


def score_real_row(row: dict[str, str], expected_points: str) -> tuple[str, str, str]:
    expected_refused = parse_bool(row.get("expected_refused", ""))
    refused = parse_bool(row.get("refused", ""))
    returned_answer = parse_bool(row.get("returned_answer", ""))
    workflow_succeeded = parse_bool(row.get("workflow_succeeded", "yes"))
    source_hit_matched = parse_bool(row.get("source_hit_matched", ""))
    citations_valid = parse_bool(row.get("citations_valid", ""))
    forbidden_absent = parse_bool(row.get("forbidden_terms_absent", "yes"))
    error = row.get("error", "").strip()

    if expected_refused and refused:
        return "pass", "pass", "pass"
    if error or not workflow_succeeded or not returned_answer:
        return "fail", "fail", "review"
    faithfulness = "pass" if forbidden_absent and source_hit_matched else "review"
    citation_quality = "pass" if citations_valid and source_hit_matched else "review"
    if not source_hit_matched:
        answer_coverage = "fail"
    elif answer_covers_expected_points(row.get("answer", ""), expected_points):
        answer_coverage = "pass"
    else:
        answer_coverage = "review"
    return faithfulness, answer_coverage, citation_quality


def answer_covers_expected_points(answer: str, expected_points: str) -> bool:
    terms = meaningful_terms(expected_points)
    if not terms:
        return bool(answer.strip())
    normalized_answer = normalize_text(answer)
    hits = sum(1 for term in terms if term in normalized_answer)
    return hits >= max(1, min(2, len(terms)))


def meaningful_terms(text: str) -> list[str]:
    normalized = normalize_text(text)
    terms = re.findall(r"[a-z0-9]{3,}|[\u4e00-\u9fff]{2,}", normalized)
    stop_terms = {"说明", "相关", "研究", "技术", "问题", "影响", "指标", "依据", "行为"}
    return [term for term in terms if term not in stop_terms]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def risk_from_scores(faithfulness: str, answer_coverage: str, citation_quality: str) -> str:
    scores = {faithfulness, answer_coverage, citation_quality}
    if "fail" in scores:
        return "high"
    if "review" in scores:
        return "medium"
    return "low"


def review_note_for_real_row(row: dict[str, str], answer_coverage: str) -> str:
    if row.get("error", "").strip():
        return f"Real result failed with error: {row['error'].strip()}"
    if answer_coverage == "pass":
        return "Real model answer covers the expected points by rule-based term check."
    if answer_coverage == "review":
        return "Real model answer has matched sources, but expected point coverage still needs human review."
    return "Real model result did not satisfy source or answer coverage checks."


def next_action_for_scores(faithfulness: str, answer_coverage: str, citation_quality: str) -> str:
    if "fail" in {faithfulness, answer_coverage, citation_quality}:
        return "优先排查真实检索来源、模型超时或回答覆盖缺口。"
    if "review" in {faithfulness, answer_coverage, citation_quality}:
        return "保留为人工审阅样例，必要时补充资料或改进 rerank。"
    return "低风险样例，可作为真实配置发布前校准通过证据。"


def summarize_answer(answer: str, limit: int = 700) -> str:
    summary = re.sub(r"\s+", " ", answer).strip()
    if len(summary) <= limit:
        return summary
    return summary[: limit - 3].rstrip() + "..."


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def parse_bool(value: str) -> bool:
    return value.strip().casefold() in {"yes", "true", "1", "y", "pass", "passed"}


def write_results(path: Path, results: list[Stage15CoverageReview]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[Stage15CoverageReview], output_path: str) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.risk_level] = counts.get(result.risk_level, 0) + 1
    print(f"stage 15 answer coverage review: {len(results)} rows")
    print("risk counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    print(f"wrote results to {output_path}")


if __name__ == "__main__":
    main()
