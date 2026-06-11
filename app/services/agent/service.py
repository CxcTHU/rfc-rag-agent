import re
from dataclasses import dataclass, field
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
from app.services.retrieval.embedding import EmbeddingProvider


AgentIntent = Literal[
    "greeting",
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

        intent = detect_intent(normalized_question, source_id=source_id)
        if intent == "greeting":
            return AgentQueryResult(
                question=normalized_question,
                answer=(
                    "你好，我是堆石混凝土资料库 Agent。你可以问我堆石混凝土的概念、"
                    "施工工艺、水化热、充填性能、工程案例，或让我检索相关资料。"
                ),
                tool_calls=[],
                refused=False,
                reasoning_summary="识别为寒暄问候，直接返回使用引导，不调用检索或模型。",
            )

        if intent == "get_source_detail":
            resolved_source_id = source_id or extract_source_id(normalized_question)
            if not resolved_source_id:
                return AgentQueryResult(
                    question=normalized_question,
                    answer="请提供要查询的 source_id。",
                    tool_calls=[],
                    refused=True,
                    refusal_reason="source_id is required for source detail queries.",
                    reasoning_summary="识别为来源详情查询，但缺少 source_id，因此没有调用工具。",
                )
            tool_result = self.toolbox.get_source_detail(resolved_source_id)
            return result_from_tool(
                question=normalized_question,
                answer=source_detail_answer(tool_result.sources),
                tool_result=tool_result,
                reasoning_summary=f"识别为来源详情查询，调用 get_source_detail 查询 {resolved_source_id}。",
            )

        if intent == "list_sources":
            tool_result = self.toolbox.list_sources(limit=top_k)
            return result_from_tool(
                question=normalized_question,
                answer=f"找到 {len(tool_result.sources)} 条来源记录。",
                tool_result=tool_result,
                reasoning_summary="识别为来源列表查询，调用 list_sources 获取来源登记记录。",
            )

        if intent == "search":
            tool_result = self.toolbox.hybrid_search_knowledge(normalized_question, top_k=top_k)
            return result_from_tool(
                question=normalized_question,
                answer=f"找到 {len(tool_result.search_results)} 条混合检索结果。",
                tool_result=tool_result,
                reasoning_summary="识别为资料检索意图，调用 hybrid_search_knowledge 复用阶段 6 的混合检索。",
            )

        tool_result = self.toolbox.answer_with_citations(
            normalized_question,
            top_k=top_k,
            retrieval_mode="hybrid",
            history=history,
        )
        return result_from_tool(
            question=normalized_question,
            answer=tool_result.answer or "",
            tool_result=tool_result,
            reasoning_summary="识别为引用式问答意图，调用 answer_with_citations 复用现有问答、引用和拒答链路。",
        )


def detect_intent(question: str, source_id: str | None = None) -> AgentIntent:
    normalized = question.casefold()
    if is_greeting(normalized):
        return "greeting"
    if source_id or extract_source_id(question):
        return "get_source_detail"
    if any(token in normalized for token in ["来源详情", "source detail", "source详情"]):
        return "get_source_detail"
    if any(token in normalized for token in ["来源列表", "资料来源", "list sources", "sources list"]):
        return "list_sources"
    if any(token in normalized for token in ["检索", "搜索", "查找", "search", "find", "相关资料"]):
        return "search"
    return "answer"


def is_greeting(normalized_question: str) -> bool:
    compact = re.sub(r"[\s!！。,.，？?~～]+", "", normalized_question)
    greetings = {
        "你好",
        "您好",
        "嗨",
        "hi",
        "hello",
        "hey",
        "早上好",
        "下午好",
        "晚上好",
    }
    return compact in greetings


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
