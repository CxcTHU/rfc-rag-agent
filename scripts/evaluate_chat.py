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
from app.services.generation.answer_service import CitationAnswerResult, CitationAnswerService  # noqa: E402
from app.services.generation.chat_model import ChatModelProvider, create_chat_model_provider  # noqa: E402
from app.services.generation.prompt_builder import ContextSource  # noqa: E402
from app.services.retrieval.embedding import EmbeddingProvider  # noqa: E402
from scripts.evaluate_vector_search import create_embedding_provider_from_settings  # noqa: E402


QUERY_FIELDS = [
    "query_id",
    "question",
    "top_k",
    "retrieval_mode",
    "min_score",
    "expected_refused",
    "require_sources",
    "require_citations",
    "expected_source_title_terms",
    "expected_source_content_terms",
    "forbidden_answer_terms",
    "notes",
]

RESULT_FIELDS = [
    "query_id",
    "question",
    "passed",
    "returned_answer",
    "expected_refused",
    "refused",
    "refusal_matched",
    "source_count",
    "citations",
    "citations_valid",
    "expected_source_hit",
    "forbidden_terms_absent",
    "retrieval_mode",
    "model_provider",
    "model_name",
    "answer",
    "top_source_titles",
    "error",
    "notes",
]


@dataclass(frozen=True)
class ExpectedChatQuery:
    query_id: str
    question: str
    top_k: int
    retrieval_mode: str
    min_score: float
    expected_refused: bool
    require_sources: bool
    require_citations: bool
    expected_source_title_terms: list[str]
    expected_source_content_terms: list[str]
    forbidden_answer_terms: list[str]
    notes: str


@dataclass(frozen=True)
class EvaluatedChatResult:
    query_id: str
    question: str
    passed: bool
    returned_answer: bool
    expected_refused: bool
    refused: bool
    refusal_matched: bool
    source_count: int
    citations: list[int]
    citations_valid: bool
    expected_source_hit: bool
    forbidden_terms_absent: bool
    retrieval_mode: str
    model_provider: str
    model_name: str
    answer: str
    top_source_titles: str
    error: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "question": self.question,
            "passed": format_bool(self.passed),
            "returned_answer": format_bool(self.returned_answer),
            "expected_refused": format_bool(self.expected_refused),
            "refused": format_bool(self.refused),
            "refusal_matched": format_bool(self.refusal_matched),
            "source_count": str(self.source_count),
            "citations": "|".join(str(citation) for citation in self.citations),
            "citations_valid": format_bool(self.citations_valid),
            "expected_source_hit": format_bool(self.expected_source_hit),
            "forbidden_terms_absent": format_bool(self.forbidden_terms_absent),
            "retrieval_mode": self.retrieval_mode,
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "answer": self.answer,
            "top_source_titles": self.top_source_titles,
            "error": self.error,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the stage-3 cited chat chain.")
    parser.add_argument("--queries", default="data/evaluation/chat_queries.csv")
    parser.add_argument("--out", default="data/evaluation/chat_results.csv")
    parser.add_argument("--top-k", type=int, default=0, help="Override top_k for every query when greater than zero.")
    parser.add_argument("--chat-provider", default="deterministic", help="Chat provider. Defaults to deterministic for stable evaluation.")
    parser.add_argument("--embedding-provider", default="", help="Embedding provider. Defaults to .env EMBEDDING_PROVIDER or deterministic.")
    parser.add_argument("--log-answers", action="store_true", help="Persist evaluation answers into qa_logs.")
    args = parser.parse_args()

    settings = get_settings()
    expected_queries = read_expected_queries(Path(args.queries), top_k_override=args.top_k)
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
        results = evaluate_queries(
            expected_queries=expected_queries,
            db=db,
            chat_provider=chat_provider,
            embedding_provider=embedding_provider,
            log_answers=args.log_answers,
        )

    write_results(Path(args.out), results)
    print_summary(results, args.out)


def chat_model_name_for_provider(provider_name: str | None, settings) -> str | None:
    provider = (provider_name or "deterministic").strip().casefold()
    if provider in {"", "deterministic", "fake", "local"}:
        return None
    return settings.chat_model_name


def read_expected_queries(path: Path, top_k_override: int = 0) -> list[ExpectedChatQuery]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(QUERY_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing query fields: {', '.join(sorted(missing))}")
        return [
            ExpectedChatQuery(
                query_id=row["query_id"],
                question=row["question"],
                top_k=top_k_override or parse_top_k(row["top_k"]),
                retrieval_mode=(row["retrieval_mode"] or "auto").strip(),
                min_score=parse_float(row["min_score"]),
                expected_refused=parse_bool(row["expected_refused"]),
                require_sources=parse_bool(row["require_sources"]),
                require_citations=parse_bool(row["require_citations"]),
                expected_source_title_terms=split_terms(row["expected_source_title_terms"]),
                expected_source_content_terms=split_terms(row["expected_source_content_terms"]),
                forbidden_answer_terms=split_terms(row["forbidden_answer_terms"]),
                notes=row["notes"],
            )
            for row in reader
        ]


def evaluate_queries(
    expected_queries: list[ExpectedChatQuery],
    db,
    chat_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    log_answers: bool = False,
) -> list[EvaluatedChatResult]:
    service = CitationAnswerService(
        db=db,
        chat_model_provider=chat_provider,
        embedding_provider=embedding_provider,
        log_answers=log_answers,
    )
    results: list[EvaluatedChatResult] = []
    for expected in expected_queries:
        try:
            answer_result = service.answer(
                question=expected.question,
                top_k=expected.top_k,
                retrieval_mode=expected.retrieval_mode,  # type: ignore[arg-type]
                min_score=expected.min_score,
            )
        except Exception as exc:  # pragma: no cover - exercised by CLI failures.
            results.append(error_result(expected, str(exc), chat_provider))
            continue

        results.append(evaluate_answer(expected, answer_result))
    return results


def evaluate_answer(
    expected: ExpectedChatQuery,
    result: CitationAnswerResult,
) -> EvaluatedChatResult:
    returned_answer = bool(result.answer.strip())
    refusal_matched = result.refused == expected.expected_refused
    sources_ok = (not expected.require_sources) or bool(result.sources)
    citations_valid = citations_map_to_sources(result.citations, result.sources)
    citations_ok = citations_valid and ((not expected.require_citations) or bool(result.citations))
    expected_source_hit = source_matches_expectation(
        sources=result.sources,
        expected_title_terms=expected.expected_source_title_terms,
        expected_content_terms=expected.expected_source_content_terms,
    )
    forbidden_terms_absent = not contains_any(result.answer, expected.forbidden_answer_terms)
    passed = all(
        [
            returned_answer,
            refusal_matched,
            sources_ok,
            citations_ok,
            expected_source_hit,
            forbidden_terms_absent,
        ]
    )

    return EvaluatedChatResult(
        query_id=expected.query_id,
        question=expected.question,
        passed=passed,
        returned_answer=returned_answer,
        expected_refused=expected.expected_refused,
        refused=result.refused,
        refusal_matched=refusal_matched,
        source_count=len(result.sources),
        citations=result.citations,
        citations_valid=citations_valid,
        expected_source_hit=expected_source_hit,
        forbidden_terms_absent=forbidden_terms_absent,
        retrieval_mode=result.retrieval_mode,
        model_provider=result.model_provider,
        model_name=result.model_name,
        answer=result.answer,
        top_source_titles=" || ".join(source.document_title for source in result.sources),
        error="",
        notes=expected.notes,
    )


def error_result(
    expected: ExpectedChatQuery,
    error: str,
    chat_provider: ChatModelProvider,
) -> EvaluatedChatResult:
    return EvaluatedChatResult(
        query_id=expected.query_id,
        question=expected.question,
        passed=False,
        returned_answer=False,
        expected_refused=expected.expected_refused,
        refused=False,
        refusal_matched=False,
        source_count=0,
        citations=[],
        citations_valid=False,
        expected_source_hit=False,
        forbidden_terms_absent=False,
        retrieval_mode=expected.retrieval_mode,
        model_provider=chat_provider.provider_name,
        model_name=chat_provider.model_name,
        answer="",
        top_source_titles="",
        error=error,
        notes=expected.notes,
    )


def citations_map_to_sources(citations: list[int], sources: list[ContextSource]) -> bool:
    source_ids = {source.source_id for source in sources}
    return all(citation in source_ids for citation in citations)


def source_matches_expectation(
    sources: list[ContextSource],
    expected_title_terms: list[str],
    expected_content_terms: list[str],
) -> bool:
    if not expected_title_terms and not expected_content_terms:
        return True
    for source in sources:
        title_ok = (not expected_title_terms) or contains_any(source.document_title, expected_title_terms)
        content_ok = (not expected_content_terms) or contains_any(source.content, expected_content_terms)
        if title_ok and content_ok:
            return True
    return False


def parse_top_k(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return 5
    return parsed if parsed > 0 else 5


def parse_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        return 0.0
    return parsed if parsed >= 0 else 0.0


def parse_bool(value: str) -> bool:
    return (value or "").strip().casefold() in {"yes", "true", "1", "pass", "passed"}


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def split_terms(value: str) -> list[str]:
    return [term.strip() for term in (value or "").split("|") if term.strip()]


def contains_any(value: str, terms: list[str]) -> bool:
    normalized = normalize(value)
    return any(normalize(term) in normalized for term in terms)


def normalize(value: str) -> str:
    return (value or "").casefold()


def write_results(path: Path, results: list[EvaluatedChatResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[EvaluatedChatResult], output_path: str) -> None:
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    refused = sum(1 for result in results if result.refused)
    citation_failures = sum(1 for result in results if not result.citations_valid)
    print(f"chat evaluation: {passed}/{total} passed\trefused={refused}\tcitation_failures={citation_failures}")
    print(f"wrote results to {output_path}")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{status}\t{result.query_id}\trefused={format_bool(result.refused)}\t"
            f"sources={result.source_count}\tcitations={len(result.citations)}\t"
            f"retrieval={result.retrieval_mode}"
        )


if __name__ == "__main__":
    main()
