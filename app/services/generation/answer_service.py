from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.services.brain.config import RetrievalConfig
from app.services.brain.service import BrainService
from app.services.brain.workflow import (
    DEFAULT_REFUSAL_ANSWER,
    BrainAnswerResult,
    BrainRetrievalOutcome,
    UsedRetrievalMode,
    build_retrieval_outcome,
    extract_citations,
)
from app.services.generation.chat_model import ChatModelProvider
from app.services.generation.prompt_builder import ContextSource
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider


RetrievalMode = Literal["auto", "vector", "keyword", "hybrid"]
RetrievalOutcome = BrainRetrievalOutcome
SUPPORTED_RETRIEVAL_MODES = {"auto", "vector", "keyword", "hybrid"}


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
        normalized_question = self._validate_answer_params(
            question=question,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            min_score=min_score,
        )
        config = self._config_from_chat_params(
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            min_score=min_score,
        )
        brain_result = self._brain_service().answer(
            question=normalized_question,
            config=config,
        )
        return citation_answer_result_from_brain_result(brain_result)

    def retrieve(
        self,
        question: str,
        top_k: int,
        retrieval_mode: RetrievalMode,
        min_score: float,
    ) -> RetrievalOutcome:
        normalized_question = self._validate_answer_params(
            question=question,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            min_score=min_score,
        )
        config = self._config_from_chat_params(
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            min_score=min_score,
        )
        return self._brain_service().retrieve(
            question=normalized_question,
            config=config,
        )

    def _brain_service(self) -> BrainService:
        return BrainService(
            db=self.db,
            chat_model_provider=self.chat_model_provider,
            embedding_provider=self.embedding_provider,
            log_answers=self.log_answers,
        )

    def _validate_answer_params(
        self,
        *,
        question: str,
        top_k: int,
        retrieval_mode: RetrievalMode,
        min_score: float,
    ) -> str:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if min_score < 0:
            raise ValueError("min_score must be greater than or equal to 0")
        if retrieval_mode not in SUPPORTED_RETRIEVAL_MODES:
            raise ValueError(f"Unsupported retrieval mode: {retrieval_mode}")
        return normalized_question

    def _config_from_chat_params(
        self,
        *,
        top_k: int,
        retrieval_mode: RetrievalMode,
        min_score: float,
    ) -> RetrievalConfig:
        try:
            return RetrievalConfig.from_chat_request(
                top_k=top_k,
                retrieval_mode=retrieval_mode,
                min_score=min_score,
                model_provider=self.chat_model_provider.provider_name,
            )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc


def citation_answer_result_from_brain_result(
    result: BrainAnswerResult,
) -> CitationAnswerResult:
    return CitationAnswerResult(
        question=result.question,
        answer=result.answer,
        citations=result.citations,
        sources=result.sources,
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        retrieval_mode=result.retrieval_mode,
        model_provider=result.model_provider,
        model_name=result.model_name,
    )


AnswerService = CitationAnswerService
