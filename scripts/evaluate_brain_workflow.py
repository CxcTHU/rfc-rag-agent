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
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider  # noqa: E402
from scripts.evaluate_chat import (  # noqa: E402
    ExpectedChatQuery,
    citations_map_to_sources,
    contains_any,
    format_bool,
    read_expected_queries,
    source_matches_expectation,
)


RESULT_FIELDS = [
    "config_name",
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
    "configured_retrieval_mode",
    "actual_retrieval_mode",
    "top_k",
    "min_score",
    "rerank_top_n",
    "workflow_steps",
    "workflow_succeeded",
    "model_provider",
    "model_name",
    "answer",
    "top_source_titles",
    "error",
    "notes",
]


@dataclass(frozen=True)
class NamedBrainWorkflowConfig:
    name: str
    retrieval_config: RetrievalConfig


@dataclass(frozen=True)
class EvaluatedBrainWorkflowResult:
    config_name: str
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
    configured_retrieval_mode: str
    actual_retrieval_mode: str
    top_k: int
    min_score: float
    rerank_top_n: int
    workflow_steps: str
    workflow_succeeded: bool
    model_provider: str
    model_name: str
    answer: str
    top_source_titles: str
    error: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "config_name": self.config_name,
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
            "configured_retrieval_mode": self.configured_retrieval_mode,
            "actual_retrieval_mode": self.actual_retrieval_mode,
            "top_k": str(self.top_k),
            "min_score": str(self.min_score),
            "rerank_top_n": str(self.rerank_top_n),
            "workflow_steps": self.workflow_steps,
            "workflow_succeeded": format_bool(self.workflow_succeeded),
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "answer": self.answer,
            "top_source_titles": self.top_source_titles,
            "error": self.error,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate configurable Brain RAG workflows.")
    parser.add_argument("--queries", default="data/evaluation/chat_queries.csv")
    parser.add_argument("--out", default="data/evaluation/brain_workflow_results.csv")
    parser.add_argument(
        "--top-k",
        type=int,
        default=0,
        help="Override top_k for every query when greater than zero.",
    )
    parser.add_argument(
        "--chat-provider",
        default="deterministic",
        help="Chat provider. Defaults to deterministic for stable evaluation.",
    )
    parser.add_argument(
        "--embedding-provider",
        default="",
        help="Embedding provider. Defaults to .env EMBEDDING_PROVIDER or deterministic.",
    )
    parser.add_argument("--log-answers", action="store_true", help="Persist evaluation answers into qa_logs.")
    args = parser.parse_args()

    settings = get_settings()
    expected_queries = read_expected_queries(Path(args.queries), top_k_override=args.top_k)
    chat_provider = create_chat_model_provider(
        provider_name=args.chat_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )
    embedding_provider = create_embedding_provider(
        args.embedding_provider or settings.embedding_provider or "deterministic"
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


def build_named_configs(expected: ExpectedChatQuery) -> list[NamedBrainWorkflowConfig]:
    return [
        NamedBrainWorkflowConfig(
            name="default_hybrid",
            retrieval_config=RetrievalConfig(
                retrieval_mode="hybrid",
                top_k=expected.top_k,
                min_score=expected.min_score,
                rerank_top_n=0,
            ),
        ),
        NamedBrainWorkflowConfig(
            name="keyword_baseline",
            retrieval_config=RetrievalConfig(
                retrieval_mode="keyword",
                top_k=expected.top_k,
                min_score=expected.min_score,
                rerank_top_n=0,
            ),
        ),
        NamedBrainWorkflowConfig(
            name="vector_only",
            retrieval_config=RetrievalConfig(
                retrieval_mode="vector",
                top_k=expected.top_k,
                min_score=expected.min_score,
                rerank_top_n=0,
            ),
        ),
    ]


def evaluate_queries(
    expected_queries: list[ExpectedChatQuery],
    db,
    chat_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    log_answers: bool = False,
) -> list[EvaluatedBrainWorkflowResult]:
    service = BrainService(
        db=db,
        chat_model_provider=chat_provider,
        embedding_provider=embedding_provider,
        log_answers=log_answers,
    )
    results: list[EvaluatedBrainWorkflowResult] = []
    for expected in expected_queries:
        for named_config in build_named_configs(expected):
            try:
                answer_result = service.answer(
                    question=expected.question,
                    config=named_config.retrieval_config,
                )
            except Exception as exc:  # pragma: no cover - exercised by CLI failures.
                results.append(error_result(expected, named_config, str(exc), chat_provider))
                continue

            results.append(
                evaluate_answer(
                    expected=expected,
                    named_config=named_config,
                    result=answer_result,
                )
            )
    return results


def evaluate_answer(
    expected: ExpectedChatQuery,
    named_config: NamedBrainWorkflowConfig,
    result: BrainAnswerResult,
) -> EvaluatedBrainWorkflowResult:
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
    workflow_succeeded = all(step.succeeded for step in result.workflow_steps)
    passed = all(
        [
            returned_answer,
            refusal_matched,
            sources_ok,
            citations_ok,
            expected_source_hit,
            forbidden_terms_absent,
            workflow_succeeded,
        ]
    )
    config = named_config.retrieval_config

    return EvaluatedBrainWorkflowResult(
        config_name=named_config.name,
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
        configured_retrieval_mode=config.retrieval_mode,
        actual_retrieval_mode=result.retrieval_mode,
        top_k=config.top_k,
        min_score=config.min_score,
        rerank_top_n=config.rerank_top_n,
        workflow_steps=">".join(step.name for step in result.workflow_steps),
        workflow_succeeded=workflow_succeeded,
        model_provider=result.model_provider,
        model_name=result.model_name,
        answer=result.answer,
        top_source_titles=" || ".join(source.document_title for source in result.sources),
        error="",
        notes=expected.notes,
    )


def error_result(
    expected: ExpectedChatQuery,
    named_config: NamedBrainWorkflowConfig,
    error: str,
    chat_provider: ChatModelProvider,
) -> EvaluatedBrainWorkflowResult:
    config = named_config.retrieval_config
    return EvaluatedBrainWorkflowResult(
        config_name=named_config.name,
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
        configured_retrieval_mode=config.retrieval_mode,
        actual_retrieval_mode="none",
        top_k=config.top_k,
        min_score=config.min_score,
        rerank_top_n=config.rerank_top_n,
        workflow_steps="",
        workflow_succeeded=False,
        model_provider=chat_provider.provider_name,
        model_name=chat_provider.model_name,
        answer="",
        top_source_titles="",
        error=error,
        notes=expected.notes,
    )


def write_results(path: Path, results: list[EvaluatedBrainWorkflowResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[EvaluatedBrainWorkflowResult], output_path: str) -> None:
    by_config: dict[str, list[EvaluatedBrainWorkflowResult]] = {}
    for result in results:
        by_config.setdefault(result.config_name, []).append(result)

    print(f"brain workflow evaluation: {len(results)} config-query runs")
    for config_name, config_results in sorted(by_config.items()):
        passed = sum(1 for result in config_results if result.passed)
        total = len(config_results)
        refused = sum(1 for result in config_results if result.refused)
        print(f"{config_name}: {passed}/{total} passed\trefused={refused}")
    print(f"wrote results to {output_path}")


if __name__ == "__main__":
    main()
