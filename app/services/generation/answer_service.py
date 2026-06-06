import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.db.repositories import QuestionAnswerLogCreate, QuestionAnswerLogRepository
from app.services.generation.chat_model import ChatModelProvider
from app.services.generation.prompt_builder import (
    ContextSource,
    SearchResultLike,
    build_rag_prompt,
)
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider
from app.services.retrieval.hybrid_search import HybridSearchService
from app.services.retrieval.keyword_search import KeywordSearchService
from app.services.retrieval.vector_search import VectorSearchService


RetrievalMode = Literal["auto", "vector", "keyword", "hybrid"]
UsedRetrievalMode = Literal["vector", "keyword", "hybrid", "none"]
CITATION_RE = re.compile(r"\[(\d+)\]")
DEFAULT_REFUSAL_ANSWER = "当前资料库中没有找到足够可靠的依据。"


@dataclass(frozen=True)
class RetrievalOutcome:
    results: list[SearchResultLike]
    used_retrieval_mode: UsedRetrievalMode
    refusal_reason: str | None = None


@dataclass(frozen=True)
class CitationAnswerResult:
    question: str
    answer: str
    citations: list[int]
    sources: list[ContextSource]
    refused: bool
    refusal_reason: str | None
    retrieval_mode: UsedRetrievalMode
    model_provider: str
    model_name: str


class CitationAnswerService:
    def __init__(
        self,
        db: Session,
        chat_model_provider: ChatModelProvider,
        embedding_provider: EmbeddingProvider | None = None,
        log_answers: bool = True,
    ) -> None:
        self.db = db
        self.chat_model_provider = chat_model_provider
        self.embedding_provider = embedding_provider or create_embedding_provider()
        self.log_answers = log_answers

    def answer(
        self,
        question: str,
        top_k: int = 5,
        retrieval_mode: RetrievalMode = "auto",
        min_score: float = 0.0,
    ) -> CitationAnswerResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if min_score < 0:
            raise ValueError("min_score must be greater than or equal to 0")
        if retrieval_mode not in {"auto", "vector", "keyword", "hybrid"}:
            raise ValueError(f"Unsupported retrieval mode: {retrieval_mode}")

        retrieval_outcome = self.retrieve(
            question=normalized_question,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            min_score=min_score,
        )
        if not retrieval_outcome.results:
            return self._refuse(
                question=normalized_question,
                retrieval_mode=retrieval_outcome.used_retrieval_mode,
                refusal_reason=retrieval_outcome.refusal_reason
                or "No retrieved chunks were available.",
            )

        try:
            rag_prompt = build_rag_prompt(
                question=normalized_question,
                search_results=retrieval_outcome.results,
            )
        except ValueError as exc:
            return self._refuse(
                question=normalized_question,
                retrieval_mode=retrieval_outcome.used_retrieval_mode,
                refusal_reason=str(exc),
            )

        model_result = self.chat_model_provider.generate(rag_prompt.messages)
        allowed_source_ids = [source.source_id for source in rag_prompt.sources]
        citations = extract_citations(model_result.answer, allowed_source_ids)

        result = CitationAnswerResult(
            question=normalized_question,
            answer=model_result.answer,
            citations=citations,
            sources=rag_prompt.sources,
            refused=False,
            refusal_reason=None,
            retrieval_mode=retrieval_outcome.used_retrieval_mode,
            model_provider=model_result.provider,
            model_name=model_result.model_name,
        )
        return self._log_and_return(result)

    def retrieve(
        self,
        question: str,
        top_k: int,
        retrieval_mode: RetrievalMode,
        min_score: float,
    ) -> RetrievalOutcome:
        if retrieval_mode == "vector":
            return self._retrieve_with_vector(question, top_k, min_score)
        if retrieval_mode == "keyword":
            return self._retrieve_with_keyword(question, top_k, min_score)
        if retrieval_mode == "hybrid":
            return self._retrieve_with_hybrid(question, top_k, min_score)

        vector_outcome = self._retrieve_with_vector(question, top_k, min_score)
        if vector_outcome.results:
            return vector_outcome

        keyword_outcome = self._retrieve_with_keyword(question, top_k, min_score)
        if keyword_outcome.results:
            return keyword_outcome

        refusal_reason = keyword_outcome.refusal_reason or vector_outcome.refusal_reason
        return RetrievalOutcome(
            results=[],
            used_retrieval_mode="none",
            refusal_reason=refusal_reason,
        )

    def _retrieve_with_vector(
        self,
        question: str,
        top_k: int,
        min_score: float,
    ) -> RetrievalOutcome:
        raw_results = VectorSearchService(self.db, self.embedding_provider).search(
            query=question,
            top_k=top_k,
        )
        return build_retrieval_outcome(
            raw_results=raw_results,
            used_retrieval_mode="vector",
            min_score=min_score,
        )

    def _retrieve_with_keyword(
        self,
        question: str,
        top_k: int,
        min_score: float,
    ) -> RetrievalOutcome:
        raw_results = KeywordSearchService(self.db).search(
            query=question,
            top_k=top_k,
        )
        return build_retrieval_outcome(
            raw_results=raw_results,
            used_retrieval_mode="keyword",
            min_score=min_score,
        )

    def _retrieve_with_hybrid(
        self,
        question: str,
        top_k: int,
        min_score: float,
    ) -> RetrievalOutcome:
        raw_results = HybridSearchService(self.db, self.embedding_provider).search(
            query=question,
            top_k=top_k,
        )
        return build_retrieval_outcome(
            raw_results=raw_results,
            used_retrieval_mode="hybrid",
            min_score=min_score,
        )

    def _refuse(
        self,
        question: str,
        retrieval_mode: UsedRetrievalMode,
        refusal_reason: str,
    ) -> CitationAnswerResult:
        result = CitationAnswerResult(
            question=question,
            answer=DEFAULT_REFUSAL_ANSWER,
            citations=[],
            sources=[],
            refused=True,
            refusal_reason=refusal_reason,
            retrieval_mode=retrieval_mode,
            model_provider=self.chat_model_provider.provider_name,
            model_name=self.chat_model_provider.model_name,
        )
        return self._log_and_return(result)

    def _log_and_return(self, result: CitationAnswerResult) -> CitationAnswerResult:
        if not self.log_answers:
            return result

        QuestionAnswerLogRepository(self.db).save_log(
            QuestionAnswerLogCreate(
                question=result.question,
                answer=result.answer,
                retrieved_chunk_ids=[source.chunk_id for source in result.sources],
                citations=result.citations,
                model_provider=result.model_provider,
                model_name=result.model_name,
                retrieval_mode=result.retrieval_mode,
                refused=result.refused,
                refusal_reason=result.refusal_reason,
            )
        )
        return result


def build_retrieval_outcome(
    raw_results: Sequence[SearchResultLike],
    used_retrieval_mode: UsedRetrievalMode,
    min_score: float,
) -> RetrievalOutcome:
    if not raw_results:
        return RetrievalOutcome(
            results=[],
            used_retrieval_mode=used_retrieval_mode,
            refusal_reason="No retrieved chunks were available.",
        )

    filtered_results = [
        result for result in raw_results if result.score >= min_score
    ]
    if not filtered_results:
        return RetrievalOutcome(
            results=[],
            used_retrieval_mode=used_retrieval_mode,
            refusal_reason="No retrieved chunks met the minimum score threshold.",
        )

    return RetrievalOutcome(
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


AnswerService = CitationAnswerService
