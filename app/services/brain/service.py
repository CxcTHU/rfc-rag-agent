from collections.abc import Sequence
from dataclasses import replace
import re

from sqlalchemy.orm import Session

from app.db.repositories import QuestionAnswerLogCreate, QuestionAnswerLogRepository
from app.services.brain.config import RetrievalConfig
from app.services.brain.workflow import (
    DEFAULT_REFUSAL_ANSWER,
    RESPONSIBILITY_REFUSAL_ANSWER,
    BrainAnswerResult,
    BrainRetrievalOutcome,
    BrainWorkflowStepRecord,
    UsedRetrievalMode,
    build_retrieval_outcome,
    evaluate_evidence_confidence,
    evaluate_responsibility_gate,
    extract_citations,
)
from app.services.generation.chat_model import ChatModelProvider
from app.services.generation.prompt_builder import SearchResultLike, build_rag_prompt
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider
from app.services.retrieval.decompose import DecomposeRetrievalService, decompose_query
from app.services.retrieval.hybrid_rrf_tail import HybridRrfTailSearchService
from app.services.retrieval.parent_child_search import ParentChildSearchService
from app.services.retrieval.keyword_search import KeywordSearchService
from app.services.retrieval.vector_search import VectorSearchService


CONTEXT_REFERENCE_RE = re.compile(
    r"(它|这个技术|这项技术|这类问题|这种技术|这个问题|其|上面|刚才)"
)


class BrainService:
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
        config: RetrievalConfig | None = None,
        history: Sequence[str] | None = None,
    ) -> BrainAnswerResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")

        active_config = config or RetrievalConfig()
        workflow_steps: list[BrainWorkflowStepRecord] = []
        current_question = normalized_question
        filtered_history: tuple[str, ...] = ()
        retrieval_outcome = BrainRetrievalOutcome(
            results=[],
            used_retrieval_mode="none",
            refusal_reason="retrieve step has not run.",
        )

        for step_name in active_config.workflow_config.enabled_step_names:
            if step_name == "filter_history":
                filtered_history, step = self._filter_history_step(
                    history=history or (),
                    max_history=active_config.max_history,
                )
                workflow_steps.append(step)
            elif step_name == "rewrite_query":
                current_question, step = self._rewrite_query_step(
                    question=current_question,
                    history=filtered_history,
                )
                workflow_steps.append(step)
            elif step_name == "retrieve":
                retrieval_outcome, step = self._retrieve_step(
                    question=current_question,
                    config=active_config,
                )
                workflow_steps.append(step)
            elif step_name == "optional_rerank":
                retrieval_outcome, step = self._optional_rerank_step(
                    retrieval_outcome=retrieval_outcome,
                    rerank_top_n=active_config.rerank_top_n,
                )
                workflow_steps.append(step)
            elif step_name == "generate_answer":
                result = self._generate_answer_step(
                    original_question=normalized_question,
                    retrieval_question=current_question,
                    retrieval_outcome=retrieval_outcome,
                    workflow_steps=workflow_steps,
                )
                return result

        workflow_steps.append(
            BrainWorkflowStepRecord(
                name="generate_answer",
                input_summary="workflow ended before generate_answer",
                output_summary="refused=True",
                succeeded=False,
                error="Workflow did not include an enabled generate_answer step.",
            )
        )
        return self._refuse(
            question=normalized_question,
            retrieval_mode=retrieval_outcome.used_retrieval_mode,
            refusal_reason="Workflow did not include an enabled generate_answer step.",
            workflow_steps=workflow_steps,
        )

    def retrieve(self, question: str, config: RetrievalConfig) -> BrainRetrievalOutcome:
        if config.retrieval_mode == "vector":
            return self._retrieve_with_vector(question, config.top_k, config.min_score)
        if config.retrieval_mode == "keyword":
            return self._retrieve_with_keyword(question, config.top_k, config.min_score)
        if config.retrieval_mode == "hybrid":
            return self._retrieve_with_hybrid(question, config.top_k, config.min_score)

        vector_outcome = self._retrieve_with_vector(
            question,
            config.top_k,
            config.min_score,
        )
        if vector_outcome.results:
            return vector_outcome

        keyword_outcome = self._retrieve_with_keyword(
            question,
            config.top_k,
            config.min_score,
        )
        if keyword_outcome.results:
            return keyword_outcome

        refusal_reason = keyword_outcome.refusal_reason or vector_outcome.refusal_reason
        return BrainRetrievalOutcome(
            results=[],
            used_retrieval_mode="none",
            refusal_reason=refusal_reason,
        )

    def _filter_history_step(
        self,
        history: Sequence[str],
        max_history: int,
    ) -> tuple[tuple[str, ...], BrainWorkflowStepRecord]:
        filtered_history = tuple(item.strip() for item in history if item.strip())
        if max_history:
            filtered_history = filtered_history[-max_history:]
        else:
            filtered_history = ()

        return filtered_history, BrainWorkflowStepRecord(
            name="filter_history",
            input_summary=f"history={len(history)} max_history={max_history}",
            output_summary=f"kept_history={len(filtered_history)}",
            succeeded=True,
        )

    def _rewrite_query_step(
        self,
        question: str,
        history: Sequence[str],
    ) -> tuple[str, BrainWorkflowStepRecord]:
        rewritten_question = rewrite_contextual_question(question, history)
        changed = rewritten_question != question
        output_summary = "query rewritten from recent history" if changed else "query unchanged"
        return rewritten_question, BrainWorkflowStepRecord(
            name="rewrite_query",
            input_summary=f"question={question[:80]}",
            output_summary=output_summary,
            succeeded=True,
        )

    def _retrieve_step(
        self,
        question: str,
        config: RetrievalConfig,
    ) -> tuple[BrainRetrievalOutcome, BrainWorkflowStepRecord]:
        try:
            outcome = self.retrieve(question=question, config=config)
        except Exception as exc:
            outcome = BrainRetrievalOutcome(
                results=[],
                used_retrieval_mode="none",
                refusal_reason=str(exc),
            )
            return outcome, BrainWorkflowStepRecord(
                name="retrieve",
                input_summary=(
                    f"mode={config.retrieval_mode} top_k={config.top_k} "
                    f"min_score={config.min_score}"
                ),
                output_summary="results=0 mode=none",
                succeeded=False,
                error=str(exc),
            )

        return outcome, BrainWorkflowStepRecord(
            name="retrieve",
            input_summary=(
                f"mode={config.retrieval_mode} top_k={config.top_k} "
                f"min_score={config.min_score}"
            ),
            output_summary=(
                f"results={len(outcome.results)} mode={outcome.used_retrieval_mode}"
            ),
            succeeded=True,
        )

    def _optional_rerank_step(
        self,
        retrieval_outcome: BrainRetrievalOutcome,
        rerank_top_n: int,
    ) -> tuple[BrainRetrievalOutcome, BrainWorkflowStepRecord]:
        if rerank_top_n <= 0 or not retrieval_outcome.results:
            return retrieval_outcome, BrainWorkflowStepRecord(
                name="optional_rerank",
                input_summary=f"results={len(retrieval_outcome.results)}",
                output_summary="disabled",
                succeeded=True,
            )

        reranked_results = list(retrieval_outcome.results[:rerank_top_n])
        return replace(retrieval_outcome, results=reranked_results), BrainWorkflowStepRecord(
            name="optional_rerank",
            input_summary=(
                f"results={len(retrieval_outcome.results)} rerank_top_n={rerank_top_n}"
            ),
            output_summary=f"kept={len(reranked_results)}",
            succeeded=True,
        )

    def _generate_answer_step(
        self,
        original_question: str,
        retrieval_question: str,
        retrieval_outcome: BrainRetrievalOutcome,
        workflow_steps: list[BrainWorkflowStepRecord],
    ) -> BrainAnswerResult:
        responsibility_gate = evaluate_responsibility_gate(retrieval_question)
        if responsibility_gate.triggered:
            workflow_steps.append(
                BrainWorkflowStepRecord(
                    name="generate_answer",
                    input_summary="responsibility_gate=True",
                    output_summary="refused=True responsibility_gate",
                    succeeded=True,
                )
            )
            return self._refuse(
                question=original_question,
                retrieval_mode=retrieval_outcome.used_retrieval_mode,
                refusal_reason=(
                    responsibility_gate.refusal_reason
                    or "Question asks for engineering responsibility judgment."
                ),
                workflow_steps=workflow_steps,
                answer=RESPONSIBILITY_REFUSAL_ANSWER,
            )

        if not retrieval_outcome.results:
            workflow_steps.append(
                BrainWorkflowStepRecord(
                    name="generate_answer",
                    input_summary="sources=0",
                    output_summary="refused=True",
                    succeeded=True,
                )
            )
            return self._refuse(
                question=original_question,
                retrieval_mode=retrieval_outcome.used_retrieval_mode,
                refusal_reason=(
                    retrieval_outcome.refusal_reason
                    or "No retrieved chunks were available."
                ),
                workflow_steps=workflow_steps,
            )

        evidence_confidence = evaluate_evidence_confidence(
            retrieval_question,
            retrieval_outcome.results,
        )
        if not evidence_confidence.sufficient:
            workflow_steps.append(
                BrainWorkflowStepRecord(
                    name="generate_answer",
                    input_summary=(
                        f"sources={len(retrieval_outcome.results)} "
                        f"evidence_confidence={evidence_confidence.score:.2f}"
                    ),
                    output_summary="refused=True low_evidence",
                    succeeded=True,
                )
            )
            return self._refuse(
                question=original_question,
                retrieval_mode=retrieval_outcome.used_retrieval_mode,
                refusal_reason=(
                    evidence_confidence.refusal_reason
                    or "Retrieved chunks did not provide enough evidence."
                ),
                workflow_steps=workflow_steps,
            )

        context_results = ParentChildSearchService(self.db).expand_results(
            retrieval_outcome.results,
        )
        try:
            rag_prompt = build_rag_prompt(
                question=retrieval_question,
                search_results=context_results,
            )
        except ValueError as exc:
            workflow_steps.append(
                BrainWorkflowStepRecord(
                    name="generate_answer",
                    input_summary=f"sources={len(retrieval_outcome.results)}",
                    output_summary="refused=True",
                    succeeded=False,
                    error=str(exc),
                )
            )
            return self._refuse(
                question=original_question,
                retrieval_mode=retrieval_outcome.used_retrieval_mode,
                refusal_reason=str(exc),
                workflow_steps=workflow_steps,
            )

        model_result = self.chat_model_provider.generate(rag_prompt.messages)
        allowed_source_ids = [source.source_id for source in rag_prompt.sources]
        citations = extract_citations(model_result.answer, allowed_source_ids)
        workflow_steps.append(
            BrainWorkflowStepRecord(
                name="generate_answer",
                input_summary=f"sources={len(rag_prompt.sources)}",
                output_summary=(
                    f"refused=False citations={len(citations)} "
                    f"provider={model_result.provider}"
                ),
                succeeded=True,
            )
        )

        result = BrainAnswerResult(
            question=original_question,
            answer=model_result.answer,
            citations=citations,
            sources=rag_prompt.sources,
            refused=False,
            refusal_reason=None,
            retrieval_mode=retrieval_outcome.used_retrieval_mode,
            model_provider=model_result.provider,
            model_name=model_result.model_name,
            workflow_steps=list(workflow_steps),
        )
        return self._log_and_return(result)

    def _retrieve_with_vector(
        self,
        question: str,
        top_k: int,
        min_score: float,
    ) -> BrainRetrievalOutcome:
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
    ) -> BrainRetrievalOutcome:
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
    ) -> BrainRetrievalOutcome:
        decomposed_query = decompose_query(question)
        if decomposed_query.decomposed:
            decompose_outcome = DecomposeRetrievalService(self.db, self.embedding_provider).retrieve(
                question=question,
                retrieval_mode="hybrid",
                top_k=top_k,
            )
            return build_retrieval_outcome(
                raw_results=decompose_outcome.merged_results,
                used_retrieval_mode="hybrid",
                min_score=min_score,
            )

        raw_results = HybridRrfTailSearchService(self.db, self.embedding_provider).search(
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
        workflow_steps: list[BrainWorkflowStepRecord],
        answer: str = DEFAULT_REFUSAL_ANSWER,
    ) -> BrainAnswerResult:
        result = BrainAnswerResult(
            question=question,
            answer=answer,
            citations=[],
            sources=[],
            refused=True,
            refusal_reason=refusal_reason,
            retrieval_mode=retrieval_mode,
            model_provider=self.chat_model_provider.provider_name,
            model_name=self.chat_model_provider.model_name,
            workflow_steps=list(workflow_steps),
        )
        return self._log_and_return(result)

    def _log_and_return(self, result: BrainAnswerResult) -> BrainAnswerResult:
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


def rewrite_contextual_question(question: str, history: Sequence[str]) -> str:
    normalized_question = question.strip()
    if not normalized_question:
        return normalized_question
    if not history:
        return normalized_question
    if not CONTEXT_REFERENCE_RE.search(normalized_question):
        return normalized_question

    latest_context = next((item.strip() for item in reversed(history) if item.strip()), "")
    if not latest_context:
        return normalized_question
    if latest_context in normalized_question:
        return normalized_question

    return f"{latest_context}；追问：{normalized_question}"
