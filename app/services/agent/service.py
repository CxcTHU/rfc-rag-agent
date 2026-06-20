import re
import time
from dataclasses import dataclass, field, replace
from collections.abc import Sequence
from typing import Literal

from sqlalchemy.orm import Session

from app.services.agent.tools import (
    AgentSearchItem,
    AgentSourceReference,
    AgentToolbox,
    AgentToolCallRecord,
)
from app.services.generation.chat_model import ChatModelProvider
from app.services.observability.latency_trace import (
    LatencyTrace,
    reset_current_latency_trace,
    set_current_latency_trace,
)
from app.services.retrieval.embedding import EmbeddingProvider


AgentIntent = Literal[
    "answer",
    "search",
    "list_sources",
    "get_source_detail",
]


@dataclass(frozen=True)
class AgentQueryResult:
    question: str
    answer: str
    tool_calls: list[AgentToolCallRecord]
    sources: list[AgentSourceReference] = field(default_factory=list)
    search_results: list[AgentSearchItem] = field(default_factory=list)
    citations: list[int] = field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    reasoning_summary: str = ""
    mode: str = "default"
    workflow_steps: list[AgentToolCallRecord] = field(default_factory=list)
    iteration_count: int = 0
    latency_trace: dict[str, object] = field(default_factory=dict)
    image_analysis: dict[str, object] | None = None


class AgentService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        chat_model_provider: ChatModelProvider,
        log_answers: bool = True,
    ) -> None:
        self.toolbox = AgentToolbox(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_model_provider,
            log_answers=log_answers,
        )

    def query(
        self,
        question: str,
        top_k: int = 5,
        max_tool_calls: int = 2,
        source_id: str | None = None,
        history: Sequence[str] | None = None,
    ) -> AgentQueryResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be greater than 0")

        latency_trace = LatencyTrace()
        latency_token = set_current_latency_trace(latency_trace)
        try:
            intent = detect_intent(normalized_question, source_id=source_id)
            if intent == "get_source_detail":
                resolved_source_id = source_id or extract_source_id(normalized_question)
                if not resolved_source_id:
                    return with_latency_trace(
                        AgentQueryResult(
                            question=normalized_question,
                            answer="请提供要查询的 source_id。",
                            tool_calls=[],
                            refused=True,
                            refusal_reason="source_id is required for source detail queries.",
                            reasoning_summary="识别为来源详情查询，但缺少 source_id，因此没有调用工具。",
                        ),
                        latency_trace,
                    )
                tool_started = time.perf_counter()
                tool_result = self.toolbox.get_source_detail(resolved_source_id)
                latency_trace.add_duration("tool_latency_ms", elapsed_ms(tool_started))
                return with_latency_trace(
                    result_from_tool(
                        question=normalized_question,
                        answer=source_detail_answer(tool_result.sources),
                        tool_result=tool_result,
                        reasoning_summary=f"识别为来源详情查询，调用 get_source_detail 查询 {resolved_source_id}。",
                    ),
                    latency_trace,
                )

            if intent == "list_sources":
                tool_started = time.perf_counter()
                tool_result = self.toolbox.list_sources(limit=top_k)
                latency_trace.add_duration("tool_latency_ms", elapsed_ms(tool_started))
                return with_latency_trace(
                    result_from_tool(
                        question=normalized_question,
                        answer=f"找到 {len(tool_result.sources)} 条来源记录。",
                        tool_result=tool_result,
                        reasoning_summary="识别为来源列表查询，调用 list_sources 获取来源登记记录。",
                    ),
                    latency_trace,
                )

            if intent == "search":
                tool_started = time.perf_counter()
                tool_result = self.toolbox.hybrid_search_knowledge(normalized_question, top_k=top_k)
                latency_trace.add_duration("tool_latency_ms", elapsed_ms(tool_started))
                return with_latency_trace(
                    result_from_tool(
                        question=normalized_question,
                        answer=f"找到 {len(tool_result.search_results)} 条混合检索结果。",
                        tool_result=tool_result,
                        reasoning_summary="识别为资料检索意图，调用 hybrid_search_knowledge 复用阶段 6 的混合检索。",
                    ),
                    latency_trace,
                )

            tool_started = time.perf_counter()
            tool_result = self.toolbox.answer_with_citations(
                normalized_question,
                top_k=top_k,
                retrieval_mode="hybrid",
                history=history,
            )
            answer_duration_ms = elapsed_ms(tool_started)
            latency_trace.add_duration("tool_latency_ms", answer_duration_ms)
            latency_trace.add_duration("answer_latency_ms", answer_duration_ms)
            return with_latency_trace(
                result_from_tool(
                    question=normalized_question,
                    answer=tool_result.answer or "",
                    tool_result=tool_result,
                    reasoning_summary="识别为引用式问答意图，调用 answer_with_citations 复用现有问答、引用和拒答链路。",
                ),
                latency_trace,
            )
        finally:
            reset_current_latency_trace(latency_token)


def detect_intent(question: str, source_id: str | None = None) -> AgentIntent:
    normalized = question.casefold()
    if source_id or extract_source_id(question):
        return "get_source_detail"
    if any(token in normalized for token in ["来源详情", "source detail", "source详情"]):
        return "get_source_detail"
    if any(token in normalized for token in ["来源列表", "资料来源", "list sources", "sources list"]):
        return "list_sources"
    if any(token in normalized for token in ["检索", "搜索", "查找", "search", "find", "相关资料"]):
        return "search"
    return "answer"


def extract_source_id(question: str) -> str | None:
    patterns = [
        r"source_id\s*[:=]\s*([A-Za-z0-9_.:-]+)",
        r"source\s+([A-Za-z0-9_.:-]+)",
        r"来源\s*([A-Za-z0-9_.:-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def result_from_tool(
    question: str,
    answer: str,
    tool_result,
    reasoning_summary: str,
) -> AgentQueryResult:
    return AgentQueryResult(
        question=question,
        answer=answer,
        tool_calls=[tool_result.call],
        sources=tool_result.sources,
        search_results=tool_result.search_results,
        citations=tool_result.citations,
        refused=tool_result.refused,
        refusal_reason=tool_result.refusal_reason,
        reasoning_summary=reasoning_summary,
    )


def source_detail_answer(sources: list[AgentSourceReference]) -> str:
    if not sources:
        return "没有找到对应来源。"
    source = sources[0]
    return f"来源 {source.source_id}: {source.title}"


def elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


def with_latency_trace(
    result: AgentQueryResult,
    latency_trace: LatencyTrace,
) -> AgentQueryResult:
    return replace(
        result,
        latency_trace=latency_trace.finalize(
            iteration_count=result.iteration_count,
            tool_call_count=len(result.tool_calls),
        ),
    )
