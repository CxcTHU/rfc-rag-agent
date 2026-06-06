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
from app.services.brain.workflow import BrainAnswerResult  # noqa: E402
from app.services.generation.chat_model import ChatModelProvider, create_chat_model_provider  # noqa: E402
from app.services.retrieval.embedding import EmbeddingProvider  # noqa: E402
from scripts.evaluate_chat import (  # noqa: E402
    chat_model_name_for_provider,
    citations_map_to_sources,
    contains_any,
    format_bool,
    source_matches_expectation,
)
from scripts.evaluate_vector_search import create_embedding_provider_from_settings  # noqa: E402


QUERY_FIELDS = [
    "query_id",
    "question",
    "language_type",
    "top_k",
    "retrieval_mode",
    "expected_source_hit",
    "expected_refused",
    "expected_source_title_terms",
    "expected_source_content_terms",
    "expected_answer_points",
    "forbidden_answer_terms",
    "notes",
]

RESULT_FIELDS = [
    "config_name",
    "query_id",
    "question",
    "language_type",
    "passed",
    "returned_answer",
    "expected_refused",
    "refused",
    "refusal_matched",
    "expected_source_hit",
    "actual_source_hit",
    "source_hit_matched",
    "source_count",
    "citations",
    "citations_valid",
    "forbidden_terms_absent",
    "expected_answer_points",
    "configured_retrieval_mode",
    "actual_retrieval_mode",
    "top_k",
    "workflow_steps",
    "workflow_succeeded",
    "model_provider",
    "model_name",
    "answer",
    "top_source_titles",
    "failed_reason",
    "error",
    "notes",
]


@dataclass(frozen=True)
class ExpectedUserQuestion:
    query_id: str
    question: str
    language_type: str
    top_k: int
    retrieval_mode: str
    expected_source_hit: bool
    expected_refused: bool
    expected_source_title_terms: list[str]
    expected_source_content_terms: list[str]
    expected_answer_points: str
    forbidden_answer_terms: list[str]
    notes: str


@dataclass(frozen=True)
class NamedUserQuestionConfig:
    name: str
    retrieval_config: RetrievalConfig


@dataclass(frozen=True)
class EvaluatedUserQuestionResult:
    config_name: str
    query_id: str
    question: str
    language_type: str
    passed: bool
    returned_answer: bool
    expected_refused: bool
    refused: bool
    refusal_matched: bool
    expected_source_hit: bool
    actual_source_hit: bool
    source_hit_matched: bool
    source_count: int
    citations: list[int]
    citations_valid: bool
    forbidden_terms_absent: bool
    expected_answer_points: str
    configured_retrieval_mode: str
    actual_retrieval_mode: str
    top_k: int
    workflow_steps: str
    workflow_succeeded: bool
    model_provider: str
    model_name: str
    answer: str
    top_source_titles: str
    failed_reason: str
    error: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "config_name": self.config_name,
            "query_id": self.query_id,
            "question": self.question,
            "language_type": self.language_type,
            "passed": format_bool(self.passed),
            "returned_answer": format_bool(self.returned_answer),
            "expected_refused": format_bool(self.expected_refused),
            "refused": format_bool(self.refused),
            "refusal_matched": format_bool(self.refusal_matched),
            "expected_source_hit": format_bool(self.expected_source_hit),
            "actual_source_hit": format_bool(self.actual_source_hit),
            "source_hit_matched": format_bool(self.source_hit_matched),
            "source_count": str(self.source_count),
            "citations": "|".join(str(citation) for citation in self.citations),
            "citations_valid": format_bool(self.citations_valid),
            "forbidden_terms_absent": format_bool(self.forbidden_terms_absent),
            "expected_answer_points": self.expected_answer_points,
            "configured_retrieval_mode": self.configured_retrieval_mode,
            "actual_retrieval_mode": self.actual_retrieval_mode,
            "top_k": str(self.top_k),
            "workflow_steps": self.workflow_steps,
            "workflow_succeeded": format_bool(self.workflow_succeeded),
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "answer": self.answer,
            "top_source_titles": self.top_source_titles,
            "failed_reason": self.failed_reason,
            "error": self.error,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate stage-11 real user questions.")
    parser.add_argument("--queries", default="data/evaluation/user_questions.csv")
    parser.add_argument("--out", default="data/evaluation/user_question_results.csv")
    parser.add_argument("--top-k", type=int, default=0, help="Override top_k for every query when greater than zero.")
    parser.add_argument("--chat-provider", default="deterministic")
    parser.add_argument("--embedding-provider", default="")
    parser.add_argument("--log-answers", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    expected_questions = read_expected_questions(Path(args.queries), top_k_override=args.top_k)
    chat_provider = create_chat_model_provider(
        provider_name=args.chat_provider,
        model_name=chat_model_name_for_provider(args.chat_provider, settings),
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )
    embedding_provider = create_embedding_provider_from_settings(
        args.embedding_provider,
        settings,
    )

    init_db()
    with SessionLocal() as db:
        results = evaluate_questions(
            expected_questions=expected_questions,
            db=db,
            chat_provider=chat_provider,
            embedding_provider=embedding_provider,
            log_answers=args.log_answers,
        )

    write_results(Path(args.out), results)
    print_summary(results, args.out)


def read_expected_questions(path: Path, top_k_override: int = 0) -> list[ExpectedUserQuestion]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(QUERY_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing user question fields: {', '.join(sorted(missing))}")
        return [
            ExpectedUserQuestion(
                query_id=row["query_id"].strip(),
                question=row["question"].strip(),
                language_type=row["language_type"].strip(),
                top_k=top_k_override or parse_top_k(row["top_k"]),
                retrieval_mode=(row["retrieval_mode"] or "hybrid").strip(),
                expected_source_hit=parse_bool(row["expected_source_hit"]),
                expected_refused=parse_bool(row["expected_refused"]),
                expected_source_title_terms=split_terms(row["expected_source_title_terms"]),
                expected_source_content_terms=split_terms(row["expected_source_content_terms"]),
                expected_answer_points=row["expected_answer_points"].strip(),
                forbidden_answer_terms=split_terms(row["forbidden_answer_terms"]),
                notes=row["notes"],
            )
            for row in reader
        ]


def build_named_configs(expected: ExpectedUserQuestion) -> list[NamedUserQuestionConfig]:
    return [
        NamedUserQuestionConfig(
            name="default_hybrid",
            retrieval_config=RetrievalConfig(
                retrieval_mode="hybrid",
                top_k=expected.top_k,
            ),
        ),
        NamedUserQuestionConfig(
            name="keyword_baseline",
            retrieval_config=RetrievalConfig(
                retrieval_mode="keyword",
                top_k=expected.top_k,
            ),
        ),
        NamedUserQuestionConfig(
            name="vector_only",
            retrieval_config=RetrievalConfig(
                retrieval_mode="vector",
                top_k=expected.top_k,
            ),
        ),
    ]


def evaluate_questions(
    expected_questions: list[ExpectedUserQuestion],
    db,
    chat_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    log_answers: bool = False,
) -> list[EvaluatedUserQuestionResult]:
    service = BrainService(
        db=db,
        chat_model_provider=chat_provider,
        embedding_provider=embedding_provider,
        log_answers=log_answers,
    )
    results: list[EvaluatedUserQuestionResult] = []
    for expected in expected_questions:
        for named_config in build_named_configs(expected):
            try:
                answer_result = service.answer(
                    question=expected.question,
                    config=named_config.retrieval_config,
                )
            except Exception as exc:  # pragma: no cover - exercised by CLI failures.
                results.append(error_result(expected, named_config, str(exc), chat_provider))
                continue
            results.append(evaluate_answer(expected, named_config, answer_result))
    return results


def evaluate_answer(
    expected: ExpectedUserQuestion,
    named_config: NamedUserQuestionConfig,
    result: BrainAnswerResult,
) -> EvaluatedUserQuestionResult:
    returned_answer = bool(result.answer.strip())
    refusal_matched = result.refused == expected.expected_refused
    has_source_expectation = bool(
        expected.expected_source_title_terms or expected.expected_source_content_terms
    )
    actual_source_hit = (
        source_matches_expectation(
            sources=result.sources,
            expected_title_terms=expected.expected_source_title_terms,
            expected_content_terms=expected.expected_source_content_terms,
        )
        if has_source_expectation
        else False
    )
    source_hit_matched = actual_source_hit == expected.expected_source_hit
    citations_valid = citations_map_to_sources(result.citations, result.sources)
    citations_ok = citations_valid and (result.refused or bool(result.citations))
    forbidden_terms_absent = not contains_any(result.answer, expected.forbidden_answer_terms)
    workflow_succeeded = all(step.succeeded for step in result.workflow_steps)
    failed_reason = build_failed_reason(
        returned_answer=returned_answer,
        refusal_matched=refusal_matched,
        source_hit_matched=source_hit_matched,
        citations_ok=citations_ok,
        forbidden_terms_absent=forbidden_terms_absent,
        workflow_succeeded=workflow_succeeded,
    )
    passed = not failed_reason
    config = named_config.retrieval_config

    return EvaluatedUserQuestionResult(
        config_name=named_config.name,
        query_id=expected.query_id,
        question=expected.question,
        language_type=expected.language_type,
        passed=passed,
        returned_answer=returned_answer,
        expected_refused=expected.expected_refused,
        refused=result.refused,
        refusal_matched=refusal_matched,
        expected_source_hit=expected.expected_source_hit,
        actual_source_hit=actual_source_hit,
        source_hit_matched=source_hit_matched,
        source_count=len(result.sources),
        citations=result.citations,
        citations_valid=citations_valid,
        forbidden_terms_absent=forbidden_terms_absent,
        expected_answer_points=expected.expected_answer_points,
        configured_retrieval_mode=config.retrieval_mode,
        actual_retrieval_mode=result.retrieval_mode,
        top_k=config.top_k,
        workflow_steps=">".join(step.name for step in result.workflow_steps),
        workflow_succeeded=workflow_succeeded,
        model_provider=result.model_provider,
        model_name=result.model_name,
        answer=result.answer,
        top_source_titles=" || ".join(source.document_title for source in result.sources),
        failed_reason=failed_reason,
        error="",
        notes=expected.notes,
    )


def build_failed_reason(
    *,
    returned_answer: bool,
    refusal_matched: bool,
    source_hit_matched: bool,
    citations_ok: bool,
    forbidden_terms_absent: bool,
    workflow_succeeded: bool,
) -> str:
    failures: list[str] = []
    if not returned_answer:
        failures.append("missing_answer")
    if not refusal_matched:
        failures.append("refusal_mismatch")
    if not source_hit_matched:
        failures.append("source_hit_mismatch")
    if not citations_ok:
        failures.append("citation_failure")
    if not forbidden_terms_absent:
        failures.append("forbidden_terms_present")
    if not workflow_succeeded:
        failures.append("workflow_failure")
    return "|".join(failures)


def error_result(
    expected: ExpectedUserQuestion,
    named_config: NamedUserQuestionConfig,
    error: str,
    chat_provider: ChatModelProvider,
) -> EvaluatedUserQuestionResult:
    config = named_config.retrieval_config
    return EvaluatedUserQuestionResult(
        config_name=named_config.name,
        query_id=expected.query_id,
        question=expected.question,
        language_type=expected.language_type,
        passed=False,
        returned_answer=False,
        expected_refused=expected.expected_refused,
        refused=False,
        refusal_matched=False,
        expected_source_hit=expected.expected_source_hit,
        actual_source_hit=False,
        source_hit_matched=False,
        source_count=0,
        citations=[],
        citations_valid=True,
        forbidden_terms_absent=True,
        expected_answer_points=expected.expected_answer_points,
        configured_retrieval_mode=config.retrieval_mode,
        actual_retrieval_mode="none",
        top_k=config.top_k,
        workflow_steps="",
        workflow_succeeded=False,
        model_provider=chat_provider.provider_name,
        model_name=chat_provider.model_name,
        answer="",
        top_source_titles="",
        failed_reason="error",
        error=error,
        notes=expected.notes,
    )


def parse_top_k(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("top_k must be greater than 0")
    return parsed


def parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"yes", "true", "1"}:
        return True
    if normalized in {"no", "false", "0"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def split_terms(value: str) -> list[str]:
    return [term.strip() for term in value.split("|") if term.strip()]


def write_results(path: Path, results: list[EvaluatedUserQuestionResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[EvaluatedUserQuestionResult], output_path: str) -> None:
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    failed = total - passed
    refusal_matches = sum(1 for result in results if result.refusal_matched)
    source_matches = sum(1 for result in results if result.source_hit_matched)
    print(
        f"user questions: {passed}/{total} passed, failed={failed}, "
        f"refusal_matched={refusal_matches}/{total}, source_hit_matched={source_matches}/{total}; "
        f"results written to {output_path}"
    )


if __name__ == "__main__":
    main()
