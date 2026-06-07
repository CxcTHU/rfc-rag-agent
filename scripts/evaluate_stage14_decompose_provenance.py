from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


DEFAULT_DECOMPOSE_RESULTS = Path("data/evaluation/stage13_decompose_results.csv")

RESULT_FIELDS = [
    "query_id",
    "question",
    "language_type",
    "decompose_applied",
    "sub_query_count",
    "sub_queries",
    "evidence_rank",
    "evidence_title",
    "evidence_sub_query_count",
    "topic_terms",
    "both_match",
    "source_type",
    "raw_score",
    "final_score",
    "deduplicated_count",
    "provenance_present",
    "source_hit_matched",
    "answer_coverage_proxy",
    "review_note",
]


@dataclass(frozen=True)
class ProvenanceReviewRow:
    query_id: str
    question: str
    language_type: str
    decompose_applied: str
    sub_query_count: str
    sub_queries: str
    evidence_rank: int
    evidence_title: str
    evidence_sub_query_count: str
    topic_terms: str
    both_match: str
    source_type: str
    raw_score: str
    final_score: str
    deduplicated_count: str
    provenance_present: str
    source_hit_matched: str
    answer_coverage_proxy: str
    review_note: str

    def to_row(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "question": self.question,
            "language_type": self.language_type,
            "decompose_applied": self.decompose_applied,
            "sub_query_count": self.sub_query_count,
            "sub_queries": self.sub_queries,
            "evidence_rank": str(self.evidence_rank),
            "evidence_title": self.evidence_title,
            "evidence_sub_query_count": self.evidence_sub_query_count,
            "topic_terms": self.topic_terms,
            "both_match": self.both_match,
            "source_type": self.source_type,
            "raw_score": self.raw_score,
            "final_score": self.final_score,
            "deduplicated_count": self.deduplicated_count,
            "provenance_present": self.provenance_present,
            "source_hit_matched": self.source_hit_matched,
            "answer_coverage_proxy": self.answer_coverage_proxy,
            "review_note": self.review_note,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Make stage-13 Decompose provenance easier to review.")
    parser.add_argument("--decompose-results", default=str(DEFAULT_DECOMPOSE_RESULTS))
    parser.add_argument("--out", default="data/evaluation/stage14_decompose_provenance_review.csv")
    args = parser.parse_args()

    rows = build_provenance_review(Path(args.decompose_results))
    write_results(Path(args.out), rows)
    print_summary(rows, args.out)


def build_provenance_review(path: Path = DEFAULT_DECOMPOSE_RESULTS) -> list[ProvenanceReviewRow]:
    source_rows = read_csv_rows(path)
    review_rows: list[ProvenanceReviewRow] = []
    for source_row in source_rows:
        titles = split_multi_value(source_row.get("top_source_titles", ""))
        explanations = split_multi_value(source_row.get("rerank_explanations", ""))
        if not explanations:
            explanations = [""]
        for index, explanation in enumerate(explanations, start=1):
            parsed = parse_rerank_explanation(explanation)
            review_rows.append(
                ProvenanceReviewRow(
                    query_id=source_row.get("query_id", ""),
                    question=source_row.get("question", ""),
                    language_type=source_row.get("language_type", ""),
                    decompose_applied=source_row.get("decompose_applied", ""),
                    sub_query_count=source_row.get("sub_query_count", ""),
                    sub_queries=source_row.get("sub_queries", ""),
                    evidence_rank=index,
                    evidence_title=titles[index - 1] if index <= len(titles) else "",
                    evidence_sub_query_count=parsed.get("sub_queries", ""),
                    topic_terms=parsed.get("topic_terms", ""),
                    both_match=parsed.get("both_match", ""),
                    source_type=parsed.get("source_type", ""),
                    raw_score=parsed.get("raw_score", ""),
                    final_score=parsed.get("final_score", ""),
                    deduplicated_count=source_row.get("deduplicated_count", ""),
                    provenance_present=source_row.get("provenance_present", ""),
                    source_hit_matched=source_row.get("source_hit_matched", ""),
                    answer_coverage_proxy=source_row.get("answer_coverage_proxy", ""),
                    review_note=build_review_note(source_row, parsed),
                )
            )
    return review_rows


def parse_rerank_explanation(explanation: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in explanation.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def build_review_note(source_row: dict[str, str], parsed: dict[str, str]) -> str:
    notes: list[str] = []
    if source_row.get("decompose_applied") == "yes":
        notes.append("decomposed query")
    else:
        notes.append("single query")
    if source_row.get("provenance_present") == "yes":
        notes.append("provenance present")
    else:
        notes.append("check missing provenance")
    if parsed.get("both_match") == "True":
        notes.append("keyword/vector both-match")
    if source_row.get("source_hit_matched") != "yes":
        notes.append("source hit needs review")
    if source_row.get("answer_coverage_proxy") != "yes":
        notes.append("coverage proxy needs review")
    return "; ".join(notes)


def split_multi_value(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(" || ") if item.strip()]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_results(path: Path, rows: list[ProvenanceReviewRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_row())


def print_summary(rows: list[ProvenanceReviewRow], output_path: str) -> None:
    decomposed = sum(1 for row in rows if row.decompose_applied == "yes")
    both_match = sum(1 for row in rows if row.both_match == "True")
    print(
        f"stage 14 decompose provenance review: {len(rows)} evidence rows, "
        f"decomposed_rows={decomposed}, both_match_rows={both_match}"
    )
    print(f"wrote results to {output_path}")


if __name__ == "__main__":
    main()
