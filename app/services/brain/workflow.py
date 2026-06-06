import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.services.brain.config import WorkflowStepName
from app.services.generation.prompt_builder import ContextSource, SearchResultLike


UsedRetrievalMode = Literal["vector", "keyword", "hybrid", "none"]
CITATION_RE = re.compile(r"\[(\d+)\]")
DEFAULT_REFUSAL_ANSWER = "当前资料库中没有找到足够可靠的依据。"


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


def extract_citations(answer: str, allowed_source_ids: Sequence[int]) -> list[int]:
    allowed = set(allowed_source_ids)
    citations: list[int] = []
    for match in CITATION_RE.finditer(answer):
        citation = int(match.group(1))
        if citation not in allowed or citation in citations:
            continue
        citations.append(citation)
    return citations
