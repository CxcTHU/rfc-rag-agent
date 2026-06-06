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
from app.services.agent.service import AgentQueryResult, AgentService  # noqa: E402
from app.services.generation.chat_model import ChatModelProvider, create_chat_model_provider  # noqa: E402
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider  # noqa: E402


QUERY_FIELDS = [
    "query_id",
    "question",
    "top_k",
    "source_id",
    "expected_tool",
    "expected_refused",
    "require_sources",
    "require_citations",
    "expected_source_title_terms",
    "expected_source_content_terms",
    "notes",
]

RESULT_FIELDS = [
    "query_id",
    "question",
    "passed",
    "expected_tool",
    "actual_tools",
    "tool_matched",
    "expected_refused",
    "refused",
    "refusal_matched",
    "source_count",
    "citations",
    "citations_valid",
    "expected_source_hit",
    "tool_call_count",
    "answer",
    "reasoning_summary",
    "error",
    "notes",
]


@dataclass(frozen=True)
class ExpectedAgentQuery:
    query_id: str
    question: str
    top_k: int
    source_id: str | None
    expected_tool: str
    expected_refused: bool
    require_sources: bool
    require_citations: bool
    expected_source_title_terms: list[str]
    expected_source_content_terms: list[str]
    notes: str


@dataclass(frozen=True)
class EvaluatedAgentResult:
    query_id: str
    question: str
    passed: bool
    expected_tool: str
    actual_tools: list[str]
    tool_matched: bool
    expected_refused: bool
    refused: bool
    refusal_matched: bool
    source_count: int
    citations: list[int]
    citations_valid: bool
    expected_source_hit: bool
    tool_call_count: int
    answer: str
    reasoning_summary: str
    error: str
    notes: str

    def to_row(self) -> dict[str, str]:
        return {
            "query_id": self.query_id,
            "question": self.question,
            "passed": format_bool(self.passed),
            "expected_tool": self.expected_tool,
            "actual_tools": "|".join(self.actual_tools),
            "tool_matched": format_bool(self.tool_matched),
            "expected_refused": format_bool(self.expected_refused),
            "refused": format_bool(self.refused),
            "refusal_matched": format_bool(self.refusal_matched),
            "source_count": str(self.source_count),
            "citations": "|".join(str(citation) for citation in self.citations),
            "citations_valid": format_bool(self.citations_valid),
            "expected_source_hit": format_bool(self.expected_source_hit),
            "tool_call_count": str(self.tool_call_count),
            "answer": self.answer,
            "reasoning_summary": self.reasoning_summary,
            "error": self.error,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the stage-7 Agent tool orchestration.")
    parser.add_argument("--queries", default="data/evaluation/agent_queries.csv")
    parser.add_argument("--out", default="data/evaluation/agent_results.csv")
    parser.add_argument("--top-k", type=int, default=0, help="Override top_k for every query when greater than zero.")
    parser.add_argument("--chat-provider", default="deterministic", help="Chat provider. Defaults to deterministic for stable evaluation.")
    parser.add_argument("--embedding-provider", default="", help="Embedding provider. Defaults to .env EMBEDDING_PROVIDER or deterministic.")
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


def read_expected_queries(path: Path, top_k_override: int = 0) -> list[ExpectedAgentQuery]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = set(QUERY_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing query fields: {', '.join(sorted(missing))}")
        return [
            ExpectedAgentQuery(
                query_id=row["query_id"],
                question=row["question"],
                top_k=top_k_override or parse_top_k(row["top_k"]),
                source_id=clean_optional(row["source_id"]),
                expected_tool=row["expected_tool"].strip(),
                expected_refused=parse_bool(row["expected_refused"]),
                require_sources=parse_bool(row["require_sources"]),
                require_citations=parse_bool(row["require_citations"]),
                expected_source_title_terms=split_terms(row["expected_source_title_terms"]),
                expected_source_content_terms=split_terms(row["expected_source_content_terms"]),
                notes=row["notes"],
            )
            for row in reader
        ]


def evaluate_queries(
    expected_queries: list[ExpectedAgentQuery],
    db,
    chat_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    log_answers: bool = False,
) -> list[EvaluatedAgentResult]:
    service = AgentService(
        db=db,
        chat_model_provider=chat_provider,
        embedding_provider=embedding_provider,
        log_answers=log_answers,
    )
    results: list[EvaluatedAgentResult] = []
    for expected in expected_queries:
        try:
            agent_result = service.query(
                question=expected.question,
                top_k=expected.top_k,
                source_id=expected.source_id,
            )
        except Exception as exc:  # pragma: no cover - exercised by CLI failures.
            results.append(error_result(expected, str(exc)))
            continue
        results.append(evaluate_agent_result(expected, agent_result))
    return results


def evaluate_agent_result(
    expected: ExpectedAgentQuery,
    result: AgentQueryResult,
) -> EvaluatedAgentResult:
    actual_tools = [call.tool_name for call in result.tool_calls]
    tool_matched = expected.expected_tool in actual_tools
    refusal_matched = result.refused == expected.expected_refused
    sources_ok = (not expected.require_sources) or bool(result.sources)
    citations_valid = citations_map_to_sources(result.citations, result.sources)
    citations_ok = citations_valid and ((not expected.require_citations) or bool(result.citations))
    expected_source_hit = source_matches_expectation(
        result=result,
        expected_title_terms=expected.expected_source_title_terms,
        expected_content_terms=expected.expected_source_content_terms,
    )
    passed = all(
        [
            bool(result.answer.strip()),
            tool_matched,
            refusal_matched,
            sources_ok,
            citations_ok,
            expected_source_hit,
            bool(result.reasoning_summary.strip()),
            len(actual_tools) <= 2,
        ]
    )

    return EvaluatedAgentResult(
        query_id=expected.query_id,
        question=expected.question,
        passed=passed,
        expected_tool=expected.expected_tool,
        actual_tools=actual_tools,
        tool_matched=tool_matched,
        expected_refused=expected.expected_refused,
        refused=result.refused,
        refusal_matched=refusal_matched,
        source_count=len(result.sources),
        citations=result.citations,
        citations_valid=citations_valid,
        expected_source_hit=expected_source_hit,
        tool_call_count=len(actual_tools),
        answer=result.answer,
        reasoning_summary=result.reasoning_summary,
        error="",
        notes=expected.notes,
    )


def error_result(expected: ExpectedAgentQuery, error: str) -> EvaluatedAgentResult:
    return EvaluatedAgentResult(
        query_id=expected.query_id,
        question=expected.question,
        passed=False,
        expected_tool=expected.expected_tool,
        actual_tools=[],
        tool_matched=False,
        expected_refused=expected.expected_refused,
        refused=False,
        refusal_matched=False,
        source_count=0,
        citations=[],
        citations_valid=False,
        expected_source_hit=False,
        tool_call_count=0,
        answer="",
        reasoning_summary="",
        error=error,
        notes=expected.notes,
    )


def citations_map_to_sources(citations, sources) -> bool:
    source_ids = {int(source.source_id) for source in sources if source.source_id.isdigit()}
    return all(citation in source_ids for citation in citations)


def source_matches_expectation(
    result: AgentQueryResult,
    expected_title_terms: list[str],
    expected_content_terms: list[str],
) -> bool:
    if not expected_title_terms and not expected_content_terms:
        return True
    for source in result.sources:
        title_ok = (not expected_title_terms) or contains_any(source.title, expected_title_terms)
        content_ok = (not expected_content_terms) or contains_any(source.content or "", expected_content_terms)
        if title_ok and content_ok:
            return True
    for item in result.search_results:
        title_ok = (not expected_title_terms) or contains_any(item.document_title, expected_title_terms)
        content_ok = (not expected_content_terms) or contains_any(item.content, expected_content_terms)
        if title_ok and content_ok:
            return True
    return False


def parse_top_k(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return 5
    return parsed if parsed > 0 else 5


def parse_bool(value: str) -> bool:
    return (value or "").strip().casefold() in {"yes", "true", "1", "pass", "passed"}


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


def split_terms(value: str) -> list[str]:
    return [term.strip() for term in (value or "").split("|") if term.strip()]


def clean_optional(value: str) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def contains_any(value: str, terms: list[str]) -> bool:
    normalized = normalize(value)
    return any(normalize(term) in normalized for term in terms)


def normalize(value: str) -> str:
    return (value or "").casefold()


def write_results(path: Path, results: list[EvaluatedAgentResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[EvaluatedAgentResult], output_path: str) -> None:
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    refused = sum(1 for result in results if result.refused)
    tool_failures = sum(1 for result in results if not result.tool_matched)
    citation_failures = sum(1 for result in results if not result.citations_valid)
    print(
        f"agent evaluation: {passed}/{total} passed\t"
        f"refused={refused}\ttool_failures={tool_failures}\tcitation_failures={citation_failures}"
    )
    print(f"wrote results to {output_path}")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{status}\t{result.query_id}\ttools={'|'.join(result.actual_tools)}\t"
            f"refused={format_bool(result.refused)}\tsources={result.source_count}\t"
            f"citations={len(result.citations)}"
        )


if __name__ == "__main__":
    main()
