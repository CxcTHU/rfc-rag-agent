from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


OUTPUT_FIELDS = [
    "case_id",
    "source_file",
    "query_id",
    "config_name",
    "question",
    "expected_refused",
    "refused",
    "configured_retrieval_mode",
    "actual_retrieval_mode",
    "source_count",
    "citations",
    "failure_type",
    "failure_mode",
    "expected_evidence",
    "actual_top_titles",
    "likely_reason",
    "suggested_fix",
    "before_status",
    "after_status",
    "notes",
]


@dataclass(frozen=True)
class RealRagFailureCase:
    case_id: str
    source_file: str
    query_id: str
    config_name: str
    question: str
    expected_refused: str
    refused: str
    configured_retrieval_mode: str
    actual_retrieval_mode: str
    source_count: str
    citations: str
    failure_type: str
    failure_mode: str
    expected_evidence: str
    actual_top_titles: str
    likely_reason: str
    suggested_fix: str
    before_status: str
    after_status: str = "pending_stage_10"
    notes: str = ""

    def to_row(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "source_file": self.source_file,
            "query_id": self.query_id,
            "config_name": self.config_name,
            "question": self.question,
            "expected_refused": self.expected_refused,
            "refused": self.refused,
            "configured_retrieval_mode": self.configured_retrieval_mode,
            "actual_retrieval_mode": self.actual_retrieval_mode,
            "source_count": self.source_count,
            "citations": self.citations,
            "failure_type": self.failure_type,
            "failure_mode": self.failure_mode,
            "expected_evidence": self.expected_evidence,
            "actual_top_titles": self.actual_top_titles,
            "likely_reason": self.likely_reason,
            "suggested_fix": self.suggested_fix,
            "before_status": self.before_status,
            "after_status": self.after_status,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze real RAG quality failures from stage 9.1.")
    parser.add_argument(
        "--brain-results",
        default="data/evaluation/mimo_jina_brain_workflow_results.csv",
    )
    parser.add_argument("--vector-results", default="data/evaluation/vector_results.csv")
    parser.add_argument("--out", default="data/evaluation/real_rag_failure_cases.csv")
    args = parser.parse_args()

    cases = analyze_real_rag_failures(
        brain_results_path=Path(args.brain_results),
        vector_results_path=Path(args.vector_results),
    )
    write_failure_cases(Path(args.out), cases)
    print(f"real RAG failure cases: {len(cases)}")
    print(f"wrote results to {args.out}")
    for case in cases:
        print(f"{case.case_id}\t{case.failure_type}\t{case.failure_mode}")


def analyze_real_rag_failures(
    brain_results_path: Path,
    vector_results_path: Path,
) -> list[RealRagFailureCase]:
    cases: list[RealRagFailureCase] = []
    cases.extend(analyze_brain_failures(brain_results_path))
    cases.extend(analyze_vector_failures(vector_results_path))
    return cases


def analyze_brain_failures(path: Path) -> list[RealRagFailureCase]:
    cases: list[RealRagFailureCase] = []
    for row in read_csv(path):
        if parse_bool(row.get("passed", "")):
            continue

        query_id = row.get("query_id", "")
        config_name = row.get("config_name", "")
        failure_type = brain_failure_type(row)
        failure_mode = brain_failure_mode(row)
        cases.append(
            RealRagFailureCase(
                case_id=f"brain_{config_name}_{query_id}",
                source_file=str(path),
                query_id=query_id,
                config_name=config_name,
                question=row.get("question", ""),
                expected_refused=row.get("expected_refused", ""),
                refused=row.get("refused", ""),
                configured_retrieval_mode=row.get("configured_retrieval_mode", ""),
                actual_retrieval_mode=row.get("actual_retrieval_mode", ""),
                source_count=row.get("source_count", ""),
                citations=row.get("citations", ""),
                failure_type=failure_type,
                failure_mode=failure_mode,
                expected_evidence=expected_evidence_for_brain(row),
                actual_top_titles=row.get("top_source_titles", ""),
                likely_reason=brain_failure_reason(failure_type, failure_mode),
                suggested_fix=brain_suggested_fix(failure_type, failure_mode),
                before_status=(
                    f"brain workflow failed; expected_refused={row.get('expected_refused', '')}; "
                    f"refused={row.get('refused', '')}; mode={row.get('configured_retrieval_mode', '')}"
                ),
                notes=row.get("notes", ""),
            )
        )
    return cases


def analyze_vector_failures(path: Path) -> list[RealRagFailureCase]:
    cases: list[RealRagFailureCase] = []
    for row in read_csv(path):
        if parse_bool(row.get("passed", "")):
            continue

        query_id = row.get("query_id", "")
        cases.append(
            RealRagFailureCase(
                case_id=f"vector_{query_id}",
                source_file=str(path),
                query_id=query_id,
                config_name="jina_vector_baseline",
                question=row.get("query", ""),
                expected_refused="no",
                refused="no",
                configured_retrieval_mode="vector",
                actual_retrieval_mode="vector",
                source_count=row.get("result_count", ""),
                citations="",
                failure_type="vector_expected_source_miss",
                failure_mode=vector_failure_mode(row),
                expected_evidence=vector_expected_evidence(row),
                actual_top_titles=row.get("top_titles", ""),
                likely_reason=vector_failure_reason(row),
                suggested_fix=vector_suggested_fix(row),
                before_status=(
                    f"vector failed; comparison={row.get('comparison', '') or 'unknown'}; "
                    f"best_score={row.get('best_score', '')}"
                ),
                notes=row.get("notes", ""),
            )
        )
    return cases


def brain_failure_type(row: dict[str, str]) -> str:
    if not parse_bool(row.get("refusal_matched", "")):
        if parse_bool(row.get("expected_refused", "")) and not parse_bool(row.get("refused", "")):
            return "under_refusal"
        if not parse_bool(row.get("expected_refused", "")) and parse_bool(row.get("refused", "")):
            return "over_refusal"
        return "refusal_mismatch"
    if not parse_bool(row.get("expected_source_hit", "")):
        return "source_miss"
    if not parse_bool(row.get("citations_valid", "")):
        return "citation_miss"
    if not parse_bool(row.get("forbidden_terms_absent", "")):
        return "faithfulness_risk"
    return "workflow_quality_failure"


def brain_failure_mode(row: dict[str, str]) -> str:
    if parse_bool(row.get("expected_refused", "")) and not parse_bool(row.get("refused", "")):
        return "unsupported_low_evidence"
    if row.get("configured_retrieval_mode", "") == "vector":
        return "vector_topic_drift"
    if row.get("configured_retrieval_mode", "") == "hybrid":
        return "hybrid_evidence_mismatch"
    return "rag_quality_mismatch"


def expected_evidence_for_brain(row: dict[str, str]) -> str:
    if parse_bool(row.get("expected_refused", "")):
        return "No reliable corpus evidence; answer should refuse with no sources or citations."
    if row.get("query_id") == "filling_capacity":
        return "Sources should mention filling capacity, flowability, self-compacting concrete, or 填充."
    return "Sources should match the expected title/content terms from chat_queries.csv."


def brain_failure_reason(failure_type: str, failure_mode: str) -> str:
    if failure_mode == "unsupported_low_evidence":
        return "The workflow treated retrieved vector/hybrid results as sufficient evidence for an out-of-corpus token query."
    if failure_mode == "vector_topic_drift":
        return "Vector-only retrieval returned semantically nearby RFC papers, but the evidence did not match the expected topic."
    if failure_type == "source_miss":
        return "The answer had sources, but they did not satisfy the expected evidence terms."
    return "The real RAG workflow failed one or more quality checks."


def brain_suggested_fix(failure_type: str, failure_mode: str) -> str:
    if failure_mode == "unsupported_low_evidence":
        return "Add low-evidence refusal before generation using query-token coverage, keyword anchors, score thresholds, or hybrid channel support."
    if failure_mode == "vector_topic_drift":
        return "Add vector-only evidence validation or lightweight rerank/query expansion so topic anchors like filling capacity are preserved."
    if failure_type == "source_miss":
        return "Inspect retrieval ranking and add evidence coverage checks before calling the chat model."
    return "Inspect retrieval, citation, and workflow checks before changing model provider."


def vector_failure_mode(row: dict[str, str]) -> str:
    query = row.get("query", "")
    if contains_cjk(query):
        return "cross_language_topic_gap"
    return "vector_topic_drift"


def vector_expected_evidence(row: dict[str, str]) -> str:
    if row.get("query_id") == "mesoscopic_modeling":
        return "Sources should mention mesoscopic, numerical modeling, simulation, or 细观/数值/模拟."
    return "Top vector results should satisfy the expected title/content/source constraints."


def vector_failure_reason(row: dict[str, str]) -> str:
    if vector_failure_mode(row) == "cross_language_topic_gap":
        return "The query mixes Chinese topic terms with expected English corpus terms, and vector-only retrieval drifted to broad RFC sources."
    return "Vector-only retrieval returned related but insufficiently specific evidence."


def vector_suggested_fix(row: dict[str, str]) -> str:
    if vector_failure_mode(row) == "cross_language_topic_gap":
        return "Add query expansion for Chinese/English technical synonyms or rerank by topic anchors before accepting vector-only results."
    return "Add query-token coverage, topic anchors, min_score, or rerank before accepting vector-only results."


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_failure_cases(path: Path, cases: list[RealRagFailureCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for case in cases:
            writer.writerow(case.to_row())


def parse_bool(value: str) -> bool:
    return value.strip().casefold() in {"yes", "true", "1"}


def contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


if __name__ == "__main__":
    main()
