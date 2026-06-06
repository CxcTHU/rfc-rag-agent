import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.services.brain.config import WorkflowStepName
from app.services.generation.prompt_builder import ContextSource, SearchResultLike


UsedRetrievalMode = Literal["vector", "keyword", "hybrid", "none"]
CITATION_RE = re.compile(r"\[(\d+)\]")
EVIDENCE_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")
DEFAULT_REFUSAL_ANSWER = "当前资料库中没有找到足够可靠的依据。"
DEFAULT_MIN_QUERY_TOKEN_COVERAGE = 0.2
QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "does",
    "do",
    "for",
    "give",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "why",
}


@dataclass(frozen=True)
class BrainWorkflowStepRecord:
    name: WorkflowStepName
    input_summary: str
    output_summary: str
    succeeded: bool
    error: str | None = None


@dataclass(frozen=True)
class BrainRetrievalOutcome:
    results: list[SearchResultLike]
    used_retrieval_mode: UsedRetrievalMode
    refusal_reason: str | None = None


@dataclass(frozen=True)
class EvidenceConfidence:
    sufficient: bool
    score: float
    matched_terms: tuple[str, ...]
    missing_terms: tuple[str, ...]
    refusal_reason: str | None = None


@dataclass(frozen=True)
class BrainAnswerResult:
    question: str
    answer: str
    citations: list[int]
    sources: list[ContextSource]
    refused: bool
    refusal_reason: str | None
    retrieval_mode: UsedRetrievalMode
    model_provider: str
    model_name: str
    workflow_steps: list[BrainWorkflowStepRecord]


def build_retrieval_outcome(
    raw_results: Sequence[SearchResultLike],
    used_retrieval_mode: UsedRetrievalMode,
    min_score: float,
) -> BrainRetrievalOutcome:
    if not raw_results:
        return BrainRetrievalOutcome(
            results=[],
            used_retrieval_mode=used_retrieval_mode,
            refusal_reason="No retrieved chunks were available.",
        )

    filtered_results = [result for result in raw_results if result.score >= min_score]
    if not filtered_results:
        return BrainRetrievalOutcome(
            results=[],
            used_retrieval_mode=used_retrieval_mode,
            refusal_reason="No retrieved chunks met the minimum score threshold.",
        )

    return BrainRetrievalOutcome(
        results=list(filtered_results),
        used_retrieval_mode=used_retrieval_mode,
        refusal_reason=None,
    )


def evaluate_evidence_confidence(
    query: str,
    results: Sequence[SearchResultLike],
    min_query_token_coverage: float = DEFAULT_MIN_QUERY_TOKEN_COVERAGE,
) -> EvidenceConfidence:
    query_terms = extract_evidence_terms(query)
    if not query_terms:
        return EvidenceConfidence(
            sufficient=False,
            score=0.0,
            matched_terms=(),
            missing_terms=(),
            refusal_reason="No evidence-bearing query terms were available.",
        )
    if not results:
        return EvidenceConfidence(
            sufficient=False,
            score=0.0,
            matched_terms=(),
            missing_terms=tuple(query_terms),
            refusal_reason="No retrieved chunks were available for evidence confidence.",
        )

    evidence_text = evidence_text_from_results(results)
    matched_terms = tuple(term for term in query_terms if term in evidence_text)
    missing_terms = tuple(term for term in query_terms if term not in matched_terms)
    score = len(matched_terms) / len(query_terms)
    if matched_terms and score >= min_query_token_coverage:
        return EvidenceConfidence(
            sufficient=True,
            score=score,
            matched_terms=matched_terms,
            missing_terms=missing_terms,
        )

    return EvidenceConfidence(
        sufficient=False,
        score=score,
        matched_terms=matched_terms,
        missing_terms=missing_terms,
        refusal_reason=(
            "Retrieved chunks did not share enough evidence-bearing query terms "
            f"(coverage={score:.2f})."
        ),
    )


def extract_evidence_terms(query: str) -> tuple[str, ...]:
    raw_terms = [
        match.group(0).casefold()
        for match in EVIDENCE_TOKEN_RE.finditer(query or "")
    ]
    terms = [
        term
        for term in raw_terms
        if is_evidence_term(term)
    ]
    if not terms:
        terms = raw_terms

    unique_terms: list[str] = []
    for term in terms:
        if term not in unique_terms:
            unique_terms.append(term)
    return tuple(unique_terms)


def is_evidence_term(term: str) -> bool:
    if not term:
        return False
    if term in QUERY_STOPWORDS:
        return False
    if len(term) == 1 and not ("\u4e00" <= term <= "\u9fff"):
        return False
    return True


def evidence_text_from_results(results: Sequence[SearchResultLike]) -> str:
    return " ".join(
        " ".join(
            [
                result.document_title,
                result.heading_path or "",
                result.content,
            ]
        ).casefold()
        for result in results
    )


def extract_citations(answer: str, allowed_source_ids: Sequence[int]) -> list[int]:
    allowed = set(allowed_source_ids)
    citations: list[int] = []
    for match in CITATION_RE.finditer(answer):
        citation = int(match.group(1))
        if citation not in allowed or citation in citations:
            continue
        citations.append(citation)
    return citations
