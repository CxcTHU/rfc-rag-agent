from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.brain.config import RetrievalConfig  # noqa: E402
from app.services.brain.service import BrainService  # noqa: E402
from app.services.generation.chat_model import create_chat_model_provider  # noqa: E402
from app.services.retrieval.decompose import DecomposeRetrievalService  # noqa: E402
from scripts.evaluate_chat import (  # noqa: E402
    chat_model_name_for_provider,
    format_bool,
    source_matches_expectation,
)
from scripts.evaluate_user_questions import ExpectedUserQuestion, read_expected_questions  # noqa: E402
from scripts.evaluate_vector_search import create_embedding_provider_from_settings  # noqa: E402


PRIORITY_QUERY_IDS = {
    "user_mixed_cost_emission",
    "user_cn_colloquial_compactness",
    "user_cn_porosity_compression",
    "user_en_freeze_thaw",
    "user_cn_creep",
    "user_unsupported_random",
}

RESULT_FIELDS = [
    "query_id",
    "question",
    "language_type",
    "passed",
    "expected_refused",
    "brain_refused",
    "refusal_matched",
    "decompose_applied",
    "sub_query_count",
    "sub_queries",
    "raw_result_count",
    "merged_result_count",
    "deduplicated_count",
    "provenance_present",
    "expected_source_hit",
    "actual_source_hit",
    "source_hit_matched",
    "answer_coverage_proxy",
    "top_source_titles",
    "rerank_explanations",
    "failed_reason",
    "notes",
]


@dataclass(frozen=True)
class EvaluatedDecomposeResult:
    query_id: str
    question: str
    language_type: str
    passed: bool
    expected_refused: bool
    brain_refused: bool
    refusal_matched: bool
    decompose_applied: bool
    sub_query_count: int
    sub_queries: tuple[str, ...]
    raw_result_count: int
    merged_result_count: int
    deduplicated_count: int
    provenance_present: bool
    expected_source_hit: bool
    actual_source_hit: bool
    source_hit_matched: bool
    answer_coverage_proxy: bool
    top_source_titles: str
    rerank_explanations: str
    failed_reason: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "question": self.question,
            "language_type": self.language_type,
            "passed": format_bool(self.passed),
            "expected_refused": format_bool(self.expected_refused),
            "brain_refused": format_bool(self.brain_refused),
            "refusal_matched": format_bool(self.refusal_matched),
            "decompose_applied": format_bool(self.decompose_applied),
            "sub_query_count": str(self.sub_query_count),
            "sub_queries": " || ".join(self.sub_queries),
            "raw_result_count": str(self.raw_result_count),
            "merged_result_count": str(self.merged_result_count),
            "deduplicated_count": str(self.deduplicated_count),
            "provenance_present": format_bool(self.provenance_present),
            "expected_source_hit": format_bool(self.expected_source_hit),
            "actual_source_hit": format_bool(self.actual_source_hit),
            "source_hit_matched": format_bool(self.source_hit_matched),
            "answer_coverage_proxy": format_bool(self.answer_coverage_proxy),
            "top_source_titles": self.top_source_titles,
            "rerank_explanations": self.rerank_explanations,
            "failed_reason": self.failed_reason,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate stage-13 Decompose evidence merge.")
    parser.add_argument("--queries", default="data/evaluation/user_questions.csv")
    parser.add_argument("--out", default="data/evaluation/stage13_decompose_results.csv")
    parser.add_argument("--chat-provider", default="deterministic")
    parser.add_argument("--embedding-provider", default="")
    parser.add_argument("--include-all", action="store_true", help="Evaluate all user questions instead of priority set.")
    args = parser.parse_args()

    settings = get_settings()
    expected_questions = read_expected_questions(Path(args.queries))
    selected_questions = select_questions(expected_questions, include_all=args.include_all)
    chat_provider = create_chat_model_provider(
        provider_name=args.chat_provider,
        model_name=chat_model_name_for_provider(args.chat_provider, settings),
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )
    embedding_provider = create_embedding_provider_from_settings(args.embedding_provider, settings)

    init_db()
    with SessionLocal() as db:
        results = [
            evaluate_question(
                expected=expected,
                decompose_service=DecomposeRetrievalService(db, embedding_provider),
                brain_service=BrainService(
                    db=db,
                    chat_model_provider=chat_provider,
                    embedding_provider=embedding_provider,
                    log_answers=False,
                ),
            )
            for expected in selected_questions
        ]

    write_results(Path(args.out), results)
    print_summary(results, args.out)


def select_questions(
    expected_questions: list[ExpectedUserQuestion],
    include_all: bool = False,
) -> list[ExpectedUserQuestion]:
    if include_all:
        return expected_questions
    return [question for question in expected_questions if question.query_id in PRIORITY_QUERY_IDS]


def evaluate_question(
    expected: ExpectedUserQuestion,
    decompose_service: DecomposeRetrievalService,
    brain_service: BrainService,
) -> EvaluatedDecomposeResult:
    decompose_outcome = decompose_service.retrieve(
        expected.question,
        retrieval_mode="hybrid",
        top_k=expected.top_k,
    )
    brain_result = brain_service.answer(
        question=expected.question,
        config=RetrievalConfig(retrieval_mode="hybrid", top_k=expected.top_k),
    )
    raw_result_count = sum(len(item.results) for item in decompose_outcome.sub_query_results)
    merged_result_count = len(decompose_outcome.merged_results)
    deduplicated_count = max(0, raw_result_count - merged_result_count)
    provenance_present = all(
        bool(item.sub_queries)
        for item in decompose_outcome.merged_results
    ) if decompose_outcome.merged_results else not decompose_outcome.decomposed_query.decomposed
    actual_source_hit = actual_source_hit_for_expected_question(expected, brain_result.sources)
    refusal_matched = brain_result.refused == expected.expected_refused
    source_hit_matched = actual_source_hit == expected.expected_source_hit
    answer_coverage_proxy = (
        refusal_matched
        and (expected.expected_refused or (actual_source_hit and bool(brain_result.citations)))
    )
    passed = all(
        [
            refusal_matched,
            source_hit_matched,
            provenance_present,
            decompose_outcome.decomposed_query.sub_queries,
            decompose_outcome.decomposed_query.sub_queries
            and len(decompose_outcome.decomposed_query.sub_queries) <= 3,
            expected.expected_refused or answer_coverage_proxy,
        ]
    )
    failed_reason = failure_reason(
        passed=passed,
        refusal_matched=refusal_matched,
        source_hit_matched=source_hit_matched,
        provenance_present=provenance_present,
        answer_coverage_proxy=answer_coverage_proxy,
    )
    return EvaluatedDecomposeResult(
        query_id=expected.query_id,
        question=expected.question,
        language_type=expected.language_type,
        passed=passed,
        expected_refused=expected.expected_refused,
        brain_refused=brain_result.refused,
        refusal_matched=refusal_matched,
        decompose_applied=decompose_outcome.decomposed_query.decomposed,
        sub_query_count=len(decompose_outcome.decomposed_query.sub_queries),
        sub_queries=decompose_outcome.decomposed_query.sub_queries,
        raw_result_count=raw_result_count,
        merged_result_count=merged_result_count,
        deduplicated_count=deduplicated_count,
        provenance_present=provenance_present,
        expected_source_hit=expected.expected_source_hit,
        actual_source_hit=actual_source_hit,
        source_hit_matched=source_hit_matched,
        answer_coverage_proxy=answer_coverage_proxy,
        top_source_titles=" || ".join(source.document_title for source in brain_result.sources),
        rerank_explanations=" || ".join(item.explanation for item in decompose_outcome.merged_results[: expected.top_k]),
        failed_reason=failed_reason,
        notes=expected.notes,
    )


def failure_reason(
    *,
    passed: bool,
    refusal_matched: bool,
    source_hit_matched: bool,
    provenance_present: bool,
    answer_coverage_proxy: bool,
) -> str:
    if passed:
        return ""
    reasons = []
    if not refusal_matched:
        reasons.append("refusal_mismatch")
    if not source_hit_matched:
        reasons.append("source_hit_mismatch")
    if not provenance_present:
        reasons.append("missing_provenance")
    if not answer_coverage_proxy:
        reasons.append("answer_coverage_proxy_failed")
    return "|".join(reasons)


def actual_source_hit_for_expected_question(expected: ExpectedUserQuestion, sources) -> bool:
    if not expected.expected_source_hit:
        return bool(sources)
    return source_matches_expectation(
        sources=sources,
        expected_title_terms=expected.expected_source_title_terms,
        expected_content_terms=expected.expected_source_content_terms,
    )


def write_results(path: Path, results: list[EvaluatedDecomposeResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[EvaluatedDecomposeResult], output_path: str) -> None:
    passed = sum(1 for result in results if result.passed)
    decompose_applied = sum(1 for result in results if result.decompose_applied)
    refused = sum(1 for result in results if result.brain_refused)
    source_hit_matched = sum(1 for result in results if result.source_hit_matched)
    print(
        f"decompose evaluation: {passed}/{len(results)} passed\t"
        f"decomposed={decompose_applied}\trefused={refused}\t"
        f"source_hit_matched={source_hit_matched}/{len(results)}"
    )
    print(f"wrote results to {output_path}")


if __name__ == "__main__":
    main()
