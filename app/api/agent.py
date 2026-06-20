import json
import logging
import re
import time
from collections.abc import Iterator, Sequence
from queue import Queue
from threading import Thread
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.core.structured_logging import log_event, safe_text_summary
from app.db.models import Chunk
from app.db.models import Document
from app.db.models import Message
from app.db.models import User
from app.db.repositories import ConversationRepository, MessageCreate
from app.db.repositories import deserialize_metadata
from app.db.session import get_db
from app.schemas.agent import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentSearchResultItem,
    AgentSourceItem,
    AgentToolCallItem,
    AgentWorkflowStepItem,
)
from app.services.agent.chitchat import ChitchatResult, detect_chitchat
from app.services.agent import intent_router
from app.services.agent.refusal_explainer import build_refusal_explanation
from app.services.agent.service import AgentQueryResult, AgentService
from app.services.agent.tools import image_url_from_source_image_path, page_number_from_source_image_path
from app.services.agent.react_service import ReActAgentService
from app.services.agent.tool_calling_service import ToolCallingAgentService
from app.services.agent.routing import classify_query_complexity
from app.services.agentic.graph import run_agentic_rag
from app.services.agentic.state import AgenticResult
from app.services.conversation.history import (
    history_from_messages,
    summarize_conversation_if_needed,
)
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelProvider,
    ChatModelResult,
    ChatToolDefinition,
    ToolCallingChatModelResult,
    create_chat_model_provider,
    split_streaming_text,
)
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider

router = APIRouter(prefix="/agent", tags=["agent"])

FIGURE_EVIDENCE_LIMIT = 4
agent_logger = logging.getLogger("rfc_rag_agent.agent")


def get_agent_chat_model_provider() -> ChatModelProvider:
    settings = get_settings()
    return create_chat_model_provider(
        provider_name=settings.chat_model_provider,
        model_name=settings.chat_model_name,
        api_key=settings.chat_model_api_key,
        base_url=settings.chat_model_base_url,
        temperature=settings.chat_model_temperature,
        timeout_seconds=settings.chat_model_timeout_seconds,
    )


def get_agent_planner_chat_model_provider() -> ChatModelProvider | None:
    """Optional lightweight planner provider for ReAct LLM-driven planning.

    Returns None when no dedicated planner is configured, in which case
    ReActAgentService falls back to the deterministic short-circuit plus the
    main chat model provider.
    """
    settings = get_settings()
    if not settings.planner_chat_model_provider.strip():
        return None
    return create_chat_model_provider(
        provider_name=settings.planner_chat_model_provider,
        model_name=settings.planner_chat_model_name,
        api_key=settings.planner_chat_model_api_key,
        base_url=settings.planner_chat_model_base_url,
        temperature=settings.planner_chat_model_temperature,
        timeout_seconds=settings.planner_chat_model_timeout_seconds,
    )


def get_agent_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return create_embedding_provider(
        provider_name=settings.embedding_provider,
        model_name=settings.embedding_model_name,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimension=settings.embedding_dimension or None,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


@router.post("/query", response_model=AgentQueryResponse)
def query_agent(
    request: AgentQueryRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
    chat_model_provider: ChatModelProvider = Depends(get_agent_chat_model_provider),
    embedding_provider: EmbeddingProvider = Depends(get_agent_embedding_provider),
    planner_chat_provider: ChatModelProvider | None = Depends(
        get_agent_planner_chat_model_provider
    ),
) -> AgentQueryResponse:
    conversation_repository = ConversationRepository(db)
    conversation_messages: list[Message] = []
    conversation_history: list[str] = []
    if request.conversation_id is not None:
        conversation = conversation_repository.get_conversation(
            request.conversation_id,
            user_id=current_user.id if current_user is not None else None,
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            )
        conversation_messages = conversation_repository.list_messages(
            request.conversation_id,
            user_id=current_user.id if current_user is not None else None,
        )
        conversation_history = history_from_messages(conversation_messages)
        log_event(
            agent_logger,
            "conversation_loaded",
            conversation_id=request.conversation_id,
            message_count=len(conversation_messages),
            history_count=len(conversation_history),
        )

    meta_response = build_agent_meta_response(
        question=request.question,
        chat_model_provider=chat_model_provider,
        embedding_provider=embedding_provider,
        planner_chat_provider=planner_chat_provider,
        conversation_messages=conversation_messages,
    )
    if meta_response is not None:
        persist_agent_conversation_messages(
            repository=conversation_repository,
            conversation_id=request.conversation_id,
            question=request.question,
            response=meta_response,
            chat_model_provider=chat_model_provider,
            summarize=False,
        )
        return meta_response

    try:
        followup_response = build_followup_transform_response(
            question=request.question,
            conversation_messages=conversation_messages,
            history=conversation_history or request.history,
            chat_model_provider=chat_model_provider,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="chat model provider is unavailable or timed out",
        ) from exc
    if followup_response is not None:
        persist_agent_conversation_messages(
            repository=conversation_repository,
            conversation_id=request.conversation_id,
            question=request.question,
            response=followup_response,
            chat_model_provider=chat_model_provider,
        )
        return followup_response

    chitchat = detect_chitchat(request.question)
    if chitchat is not None:
        response = agent_response_from_chitchat(request.question, chitchat)
        persist_agent_conversation_messages(
            repository=conversation_repository,
            conversation_id=request.conversation_id,
            question=request.question,
            response=response,
            chat_model_provider=chat_model_provider,
            summarize=False,
        )
        return response

    effective_mode = request.mode
    if effective_mode is None:
        effective_mode = "tool_calling_agent"
    log_agent_query_received(request, effective_mode=effective_mode)

    response: AgentQueryResponse
    if effective_mode == "agentic":
        try:
            agentic_result = run_agentic_rag(
                question=request.question,
                db=db,
                embedding_provider=embedding_provider,
                chat_model_provider=chat_model_provider,
                history=conversation_history or request.history,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="chat model provider is unavailable or timed out",
            ) from exc
        response = maybe_enrich_agent_response_with_figure_evidence(
            db=db,
            question=request.question,
            response=agent_response_from_agentic_result(agentic_result),
            effective_mode=effective_mode,
        )
        log_agent_response_event(response)
        persist_agent_conversation_messages(
            repository=conversation_repository,
            conversation_id=request.conversation_id,
            question=request.question,
            response=response,
            chat_model_provider=chat_model_provider,
        )
        return response

    if effective_mode == "react_agent":
        try:
            result = ReActAgentService(
                db=db,
                chat_model_provider=chat_model_provider,
                embedding_provider=embedding_provider,
                planner_chat_provider=planner_chat_provider,
            ).query(
                question=request.question,
                top_k=request.top_k,
                max_tool_calls=request.max_tool_calls,
                history=conversation_history or request.history,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="chat model provider is unavailable or timed out",
            ) from exc
        response = maybe_enrich_agent_response_with_figure_evidence(
            db=db,
            question=request.question,
            response=agent_response_from_result(result),
            effective_mode=effective_mode,
        )
        log_agent_response_event(response)
        persist_agent_conversation_messages(
            repository=conversation_repository,
            conversation_id=request.conversation_id,
            question=request.question,
            response=response,
            chat_model_provider=chat_model_provider,
        )
        return response

    if effective_mode == "tool_calling_agent":
        try:
            result = ToolCallingAgentService(
                db=db,
                chat_model_provider=chat_model_provider,
                embedding_provider=embedding_provider,
            ).query(
                question=request.question,
                top_k=request.top_k,
                max_tool_calls=request.max_tool_calls,
                history=conversation_history or request.history,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="chat model provider is unavailable or timed out",
            ) from exc
        response = maybe_enrich_agent_response_with_figure_evidence(
            db=db,
            question=request.question,
            response=agent_response_from_result(result),
            effective_mode=effective_mode,
        )
        log_agent_response_event(response)
        persist_agent_conversation_messages(
            repository=conversation_repository,
            conversation_id=request.conversation_id,
            question=request.question,
            response=response,
            chat_model_provider=chat_model_provider,
        )
        return response

    try:
        result = AgentService(
            db=db,
            chat_model_provider=chat_model_provider,
            embedding_provider=embedding_provider,
        ).query(
            question=request.question,
            top_k=request.top_k,
            max_tool_calls=request.max_tool_calls,
            source_id=request.source_id,
            history=conversation_history or request.history,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="chat model provider is unavailable or timed out",
        ) from exc

    response = maybe_enrich_agent_response_with_figure_evidence(
        db=db,
        question=request.question,
        response=agent_response_from_result(result),
        effective_mode=effective_mode,
    )
    log_agent_response_event(response)
    persist_agent_conversation_messages(
        repository=conversation_repository,
        conversation_id=request.conversation_id,
        question=request.question,
        response=response,
        chat_model_provider=chat_model_provider,
    )
    return response


@router.post("/query/stream")
def stream_query_agent(
    request: AgentQueryRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
    chat_model_provider: ChatModelProvider = Depends(get_agent_chat_model_provider),
    embedding_provider: EmbeddingProvider = Depends(get_agent_embedding_provider),
    planner_chat_provider: ChatModelProvider | None = Depends(
        get_agent_planner_chat_model_provider
    ),
) -> StreamingResponse:
    conversation_repository = ConversationRepository(db)
    conversation_messages: list[Message] = []
    conversation_history: list[str] = []
    if request.conversation_id is not None:
        conversation = conversation_repository.get_conversation(
            request.conversation_id,
            user_id=current_user.id if current_user is not None else None,
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            )
        conversation_messages = conversation_repository.list_messages(
            request.conversation_id,
            user_id=current_user.id if current_user is not None else None,
        )
        conversation_history = history_from_messages(conversation_messages)
        log_event(
            agent_logger,
            "conversation_loaded",
            conversation_id=request.conversation_id,
            message_count=len(conversation_messages),
            history_count=len(conversation_history),
        )

    return StreamingResponse(
        stream_agent_query_events(
            request=request,
            db=db,
            conversation_repository=conversation_repository,
            conversation_messages=conversation_messages,
            conversation_history=conversation_history,
            chat_model_provider=chat_model_provider,
            embedding_provider=embedding_provider,
            planner_chat_provider=planner_chat_provider,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def stream_agent_query_events(
    *,
    request: AgentQueryRequest,
    db: Session,
    conversation_repository: ConversationRepository,
    conversation_messages: list[Message] | None = None,
    conversation_history: list[str],
    chat_model_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    planner_chat_provider: ChatModelProvider | None = None,
) -> Iterator[str]:
    stream_started = time.perf_counter()
    try:
        summarize = True
        chitchat: ChitchatResult | None = None
        followup_response: AgentQueryResponse | None = None
        meta_response = build_agent_meta_response(
            question=request.question,
            chat_model_provider=chat_model_provider,
            embedding_provider=embedding_provider,
            planner_chat_provider=planner_chat_provider,
            conversation_messages=conversation_messages or [],
        )
        if meta_response is not None:
            response = meta_response
            summarize = False
        else:
            followup_response = build_followup_transform_response(
                question=request.question,
                conversation_messages=conversation_messages or [],
                history=conversation_history or request.history,
                chat_model_provider=chat_model_provider,
            )
            if followup_response is not None:
                response = followup_response
            else:
                chitchat = detect_chitchat(request.question)
                if chitchat is not None:
                    response = agent_response_from_chitchat(request.question, chitchat)
                    summarize = False
                else:
                    response, streamed_token_count = yield from stream_non_chitchat_agent_response(
                        request=request,
                        db=db,
                        conversation_history=conversation_history,
                        chat_model_provider=chat_model_provider,
                        embedding_provider=embedding_provider,
                        planner_chat_provider=planner_chat_provider,
                    )
                    if streamed_token_count == 0:
                        for token in split_streaming_text(response.answer):
                            mark_response_first_token(response, stream_started)
                            yield sse_event("token", {"text": token})

        if meta_response is not None or followup_response is not None:
            for token in split_streaming_text(response.answer):
                mark_response_first_token(response, stream_started)
                yield sse_event("token", {"text": token})
        elif chitchat is not None:
            for token in split_streaming_text(response.answer):
                mark_response_first_token(response, stream_started)
                yield sse_event("token", {"text": token})

        persist_agent_conversation_messages(
            repository=conversation_repository,
            conversation_id=request.conversation_id,
            question=request.question,
            response=response,
            chat_model_provider=chat_model_provider,
            summarize=summarize,
        )
        yield sse_event("metadata", response.model_dump(mode="json"))
        yield sse_event("done", {})
    except ValueError as exc:
        yield sse_event("error", {"detail": str(exc)})
    except RuntimeError:
        yield sse_event(
            "error",
            {"detail": "model or retrieval provider is unavailable or timed out"},
        )
    except Exception:
        yield sse_event("error", {"detail": "agent stream failed"})


def stream_non_chitchat_agent_response(
    *,
    request: AgentQueryRequest,
    db: Session,
    conversation_history: list[str],
    chat_model_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    planner_chat_provider: ChatModelProvider | None = None,
) -> Iterator[str | tuple[AgentQueryResponse, int]]:
    queue: Queue[tuple[str, Any]] = Queue()

    def produce_response() -> None:
        try:
            resolved_mode = request.mode
            if resolved_mode is None:
                resolved_mode = "tool_calling_agent"
            effective_chat_model_provider = chat_model_provider
            if resolved_mode != "react_agent":
                effective_chat_model_provider = QueueStreamingChatModelProvider(
                    base_provider=chat_model_provider,
                    queue=queue,
                )
            response = build_agent_query_response(
                request=request,
                db=db,
                conversation_history=conversation_history,
                chat_model_provider=effective_chat_model_provider,
                embedding_provider=embedding_provider,
                planner_chat_provider=planner_chat_provider,
                event_sink=lambda event: queue.put(("agent_event", event)),
            )
        except Exception as exc:  # noqa: BLE001 - forwarded to SSE error mapping.
            queue.put(("error", exc))
            return
        queue.put(("response", response))

    producer = Thread(target=produce_response, daemon=True)
    producer.start()

    streamed_token_count = 0
    while True:
        event_type, payload = queue.get()
        if event_type == "token":
            streamed_token_count += 1
            yield sse_event("token", {"text": payload})
            continue
        if event_type == "agent_event":
            yield sse_event(payload.event, payload.payload)
            continue
        if event_type == "response":
            producer.join()
            return payload, streamed_token_count
        if event_type == "error":
            producer.join()
            raise payload

        producer.join()
        raise RuntimeError("unknown stream event")


FOLLOWUP_TRANSFORM_TRIGGERS = (
    "\u7528\u4e2d\u6587",
    "\u4e2d\u6587\u56de\u7b54",
    "\u7ffb\u8bd1\u6210\u4e2d\u6587",
    "\u7ffb\u8bd1\u4e00\u4e0b",
    "\u8f6c\u8ff0\u7ffb\u8bd1",
    "\u8f6c\u6210\u4e2d\u6587",
    "\u6362\u6210\u4e2d\u6587",
    "\u91cd\u65b0\u7528\u4e2d\u6587",
    "\u7b80\u77ed\u70b9",
    "\u603b\u7ed3\u4e00\u4e0b",
    "\u6574\u7406\u6210\u8868\u683c",
    "\u6539\u6210\u8981\u70b9",
    "translate that",
    "translate it",
    "in chinese",
    "answer in chinese",
    "say that in chinese",
    "say it in chinese",
    "summarize that",
    "make it shorter",
    "turn that into bullets",
)

FOLLOWUP_PRONOUNS = (
    "that",
    "it",
    "\u521a\u624d",
    "\u4e0a\u4e00",
    "\u8fd9\u6bb5",
    "\u8fd9\u4e2a",
    "\u7b54\u6848",
)

MODEL_META_TRIGGERS = (
    "\u4ec0\u4e48\u5927\u6a21\u578b",
    "\u4ec0\u4e48\u6a21\u578b",
    "\u4f60\u7528\u7684\u6a21\u578b",
    "\u4f60\u7684\u6a21\u578b",
    "\u54ea\u4e2a\u6a21\u578b",
    "what model",
    "which model",
    "model are you using",
)

CAPABILITY_TRIGGERS = (
    "\u4f60\u80fd\u505a\u4ec0\u4e48",
    "\u600e\u4e48\u63d0\u95ee",
    "\u652f\u6301\u54ea\u4e9b\u6a21\u5f0f",
    "\u4f60\u662f\u4ec0\u4e48",
    "what can you do",
    "how should i ask",
    "what modes",
)

REFUSAL_EXPLANATION_TRIGGERS = (
    "\u4e3a\u4ec0\u4e48\u62d2\u7b54",
    "\u4e3a\u4ec0\u4e48\u62d2\u7edd",
    "\u521a\u624d\u4e3a\u4ec0\u4e48",
    "\u62d2\u7b54\u539f\u56e0",
    "why did you refuse",
    "why refuse",
)


def build_agent_meta_response(
    *,
    question: str,
    chat_model_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    planner_chat_provider: ChatModelProvider | None,
    conversation_messages: Sequence[Message],
) -> AgentQueryResponse | None:
    intent = intent_router.classify_meta_intent(question)
    if intent is None:
        return None

    normalized_question = question.strip()
    if intent == "agent_meta":
        planner_text = (
            f"{planner_chat_provider.provider_name} / {planner_chat_provider.model_name}"
            if planner_chat_provider is not None
            else "未单独配置；ReAct planner 使用确定性兜底逻辑"
        )
        answer = (
            "当前运行模型配置：\n"
            f"- 对话模型：{chat_model_provider.provider_name} / {chat_model_provider.model_name}\n"
            f"- 规划模型：{planner_text}\n"
            f"- 向量模型：{embedding_provider.provider_name} / {embedding_provider.model_name}\n"
            "我不会在聊天回答中暴露 API key、授权令牌、供应商原始响应、隐藏推理或受限全文。"
        )
        summary = "agent_meta: answered model/runtime question without retrieval"
    elif intent == "capability_help":
        answer = (
            "我可以围绕本项目资料库回答堆石混凝土、混凝土材料、水利工程和 RAG 链路相关问题，"
            "并尽量给出引用来源。也可以查看检索到的来源与 chunk，解释 Agent 的运行模式，"
            "或把上一轮回答改写成中文、摘要、要点或表格。若问题不适合回答，我会给出拒答分类"
            "和原因，例如 off_topic、responsibility_gate_triggered、evidence_insufficient 或 service_error。"
        )
        summary = "capability_help: answered capability question without retrieval"
    else:
        answer = previous_refusal_explanation(conversation_messages)
        summary = "refusal_explanation: explained refusal category without retrieval"

    return AgentQueryResponse.model_validate(
        {
            "question": normalized_question,
            "answer": answer,
            "tool_calls": [],
            "search_results": [],
            "sources": [],
            "citations": [],
            "refused": False,
            "refusal_reason": None,
            "reasoning_summary": summary,
            "mode": "meta",
            "workflow_steps": [],
            "iteration_count": 0,
            "invalid_citations": [],
            "refusal_category": None,
            "latency_trace": {},
        }
    )


def classify_meta_intent(question: str) -> str | None:
    normalized = question.casefold().strip()
    if not normalized:
        return None
    if any(trigger in normalized for trigger in MODEL_META_TRIGGERS):
        return "agent_meta"
    if any(trigger in normalized for trigger in CAPABILITY_TRIGGERS):
        return "capability_help"
    if any(trigger in normalized for trigger in REFUSAL_EXPLANATION_TRIGGERS):
        return "refusal_explanation"
    return None


def previous_refusal_explanation(conversation_messages: Sequence[Message]) -> str:
    for message in reversed(conversation_messages):
        if message.role != "assistant" or not message.content.strip():
            continue
        metadata = deserialize_metadata(message.metadata_json)
        if metadata.get("refused") is not True:
            continue
        category = metadata.get("refusal_category") or "unknown"
        reason = metadata.get("refusal_reason") or "未记录详细原因"
        return f"上一轮回答被拒答。拒答分类：{category}。原始原因：{reason}"

    return (
        "我没有在当前会话中找到已记录的拒答。常见拒答原因包括："
        "off_topic 表示问题缺少项目领域锚点；"
        "responsibility_gate_triggered 表示问题要求系统做不允许的责任认定；"
        "evidence_insufficient 表示检索证据太弱，不能可靠支撑回答；"
        "service_error 表示模型或检索工具调用失败。"
    )


def build_followup_transform_response(
    *,
    question: str,
    conversation_messages: Sequence[Message],
    history: Sequence[str],
    chat_model_provider: ChatModelProvider,
) -> AgentQueryResponse | None:
    normalized_question = question.strip()
    if not intent_router.is_followup_transform_request(normalized_question):
        return None

    previous_answer, previous_metadata = previous_assistant_answer_context(
        conversation_messages=conversation_messages,
        history=history,
    )
    if not previous_answer:
        return None

    requested_point_count = requested_point_count_from_instruction(normalized_question)
    count_instruction = (
        f" The user's latest instruction requests exactly {requested_point_count} points. "
        f"Return exactly {requested_point_count} numbered list items; do not add a fourth "
        "item, extra summary item, or separate conclusion."
        if requested_point_count is not None
        else ""
    )
    result = chat_model_provider.generate(
        [
            ChatMessage(
                role="system",
                content=(
                    "You rewrite the immediately previous assistant answer according "
                    "to the user's latest instruction. Do not retrieve new facts. "
                    "Do not add claims. Preserve citation markers like [1] exactly "
                    "when they appear in the previous answer. If the user asks for "
                    "Chinese, answer in Chinese."
                    f"{count_instruction}"
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    f"Latest user instruction:\n{normalized_question}\n\n"
                    f"Previous assistant answer:\n{previous_answer}"
                ),
            ),
        ]
    )
    answer = enforce_requested_point_count(
        result.answer.strip(),
        requested_point_count=requested_point_count,
    )
    return response_from_previous_answer_transform(
        question=normalized_question,
        answer=answer,
        previous_metadata=previous_metadata,
    )


CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def requested_point_count_from_instruction(question: str) -> int | None:
    match = re.search(
        r"([一二三四五六七八九十两\d]+)\s*(?:点|条|个要点|项)",
        question.strip(),
    )
    if not match:
        return None
    raw_count = match.group(1)
    if raw_count.isdigit():
        count = int(raw_count)
    elif raw_count == "十":
        count = 10
    elif raw_count.startswith("十") and len(raw_count) == 2:
        count = 10 + CHINESE_DIGITS.get(raw_count[1], 0)
    elif raw_count.endswith("十") and len(raw_count) == 2:
        count = CHINESE_DIGITS.get(raw_count[0], 0) * 10
    elif "十" in raw_count and len(raw_count) == 3:
        count = CHINESE_DIGITS.get(raw_count[0], 0) * 10 + CHINESE_DIGITS.get(raw_count[2], 0)
    else:
        count = CHINESE_DIGITS.get(raw_count)
    if count is None or count < 1 or count > 10:
        return None
    return count


def enforce_requested_point_count(answer: str, *, requested_point_count: int | None) -> str:
    if requested_point_count is None:
        return answer
    lines = answer.splitlines()
    item_pattern = re.compile(r"^(\s*)(?:[-*]|\d+[.)]|[一二三四五六七八九十]+[、.])\s+(.+)$")
    item_indexes = [
        index for index, line in enumerate(lines) if item_pattern.match(line.strip())
    ]
    if len(item_indexes) <= requested_point_count:
        return answer
    keep_item_indexes = set(item_indexes[:requested_point_count])
    cutoff_index = item_indexes[requested_point_count]
    kept_lines = [
        line
        for index, line in enumerate(lines)
        if index < cutoff_index and (index not in item_indexes or index in keep_item_indexes)
    ]
    return "\n".join(kept_lines).strip()


def is_followup_transform_request(question: str) -> bool:
    normalized = question.casefold().strip()
    if not normalized:
        return False
    if any(trigger in normalized for trigger in FOLLOWUP_TRANSFORM_TRIGGERS):
        return len(normalized) <= 120 or any(
            pronoun in normalized for pronoun in FOLLOWUP_PRONOUNS
        )
    return False


def previous_assistant_answer_context(
    *,
    conversation_messages: Sequence[Message],
    history: Sequence[str],
) -> tuple[str | None, dict[str, object]]:
    for message in reversed(conversation_messages):
        if message.role != "assistant" or not message.content.strip():
            continue
        metadata = deserialize_metadata(message.metadata_json)
        if metadata.get("refused") is True:
            return None, {}
        return message.content.strip(), metadata

    for item in reversed(history):
        content = intent_router.strip_assistant_history_prefix(item)
        if content:
            return content, {}
    return None, {}


def strip_assistant_history_prefix(item: str) -> str | None:
    stripped = item.strip()
    prefixes = ("\u52a9\u624b\uff1a", "assistant:", "Assistant:")
    for prefix in prefixes:
        if stripped.startswith(prefix):
            content = stripped[len(prefix):].strip()
            return content or None
    return None


def response_from_previous_answer_transform(
    *,
    question: str,
    answer: str,
    previous_metadata: dict[str, object],
) -> AgentQueryResponse:
    payload = {
        "question": question,
        "answer": answer,
        "tool_calls": previous_metadata.get("tool_calls", []),
        "search_results": previous_metadata.get("search_results", []),
        "sources": previous_metadata.get("sources", []),
        "citations": previous_metadata.get("citations", []),
        "refused": False,
        "refusal_reason": None,
        "reasoning_summary": "followup_transform: rewrote previous assistant answer without retrieval",
        "mode": previous_metadata.get("mode", "default") or "default",
        "workflow_steps": previous_metadata.get("workflow_steps", []),
        "iteration_count": previous_metadata.get("iteration_count", 0),
        "invalid_citations": previous_metadata.get("invalid_citations", []),
        "refusal_category": None,
        "latency_trace": {},
    }
    return AgentQueryResponse.model_validate(payload)


def maybe_enrich_agent_response_with_figure_evidence(
    *,
    db: Session,
    question: str,
    response: AgentQueryResponse,
    effective_mode: str,
) -> AgentQueryResponse:
    if effective_mode == "react_agent":
        return response
    if not get_settings().enable_auto_figure_enrichment:
        return response
    return enrich_agent_response_with_figure_evidence(
        db=db,
        question=question,
        response=response,
    )


def enrich_agent_response_with_figure_evidence(
    *,
    db: Session,
    question: str,
    response: AgentQueryResponse,
) -> AgentQueryResponse:
    if response.refused or any(source.image_url for source in response.sources):
        return response
    document_ids = [
        source.document_id
        for source in response.sources
        if source.document_id is not None
    ]
    if not document_ids:
        return response

    ranked_document_ids = list(dict.fromkeys(document_ids))
    existing_chunk_ids = {
        source.chunk_id
        for source in response.sources
        if source.chunk_id is not None
    }
    existing_image_urls = {
        source.image_url
        for source in response.sources
        if source.image_url
    }
    rows = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.document_id.in_(ranked_document_ids))
        .filter(Chunk.chunk_type == "image_description")
        .filter(Chunk.source_image_path.isnot(None))
        .order_by(Chunk.document_id.asc(), Chunk.chunk_index.asc())
        .all()
    )
    if not rows:
        return response

    document_rank = {document_id: index for index, document_id in enumerate(ranked_document_ids)}
    query_terms = figure_query_terms(question)
    ranked_rows = sorted(
        rows,
        key=lambda row: (
            document_rank.get(row[0].document_id, len(document_rank)),
            -figure_text_score(row[0].content, query_terms),
            row[0].chunk_index,
        ),
    )

    added_sources: list[AgentSourceItem] = []
    added_results: list[AgentSearchResultItem] = []
    for chunk, document in ranked_rows:
        if chunk.id in existing_chunk_ids:
            continue
        image_url = image_url_from_source_image_path(chunk.source_image_path)
        if not image_url or image_url in existing_image_urls:
            continue
        score = float(figure_text_score(chunk.content, query_terms))
        title = document.title or document.file_name
        added_sources.append(
            AgentSourceItem(
                source_id=f"chunk:{chunk.id}",
                title=title,
                source_type=document.source_type,
                status=None,
                trust_level=None,
                fulltext_permission=None,
                document_id=document.id,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                url=None,
                doi=None,
                content=chunk.content,
                score=score,
                chunk_type=chunk.chunk_type,
                source_image_path=chunk.source_image_path,
                image_url=image_url,
                caption=chunk.caption,
                page_number=page_number_from_source_image_path(chunk.source_image_path),
            )
        )
        added_results.append(
            AgentSearchResultItem(
                document_id=document.id,
                document_title=title,
                source_type=document.source_type,
                source_path=document.source_path,
                file_name=document.file_name,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                heading_path=chunk.heading_path,
                score=score,
                chunk_type=chunk.chunk_type,
                source_image_path=chunk.source_image_path,
                image_url=image_url,
                caption=chunk.caption,
                page_number=page_number_from_source_image_path(chunk.source_image_path),
            )
        )
        existing_chunk_ids.add(chunk.id)
        existing_image_urls.add(image_url)
        if len(added_sources) >= FIGURE_EVIDENCE_LIMIT:
            break

    if not added_sources:
        return response
    return response.model_copy(
        update={
            "sources": [*response.sources, *added_sources],
            "search_results": [*response.search_results, *added_results],
        },
    )


def figure_query_terms(question: str) -> list[str]:
    terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]+", question.lower())
    return [term for term in terms if len(term) >= 2]


def figure_text_score(text: str, terms: Sequence[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term in lowered)


def build_agent_query_response(
    *,
    request: AgentQueryRequest,
    db: Session,
    conversation_history: list[str],
    chat_model_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    planner_chat_provider: ChatModelProvider | None = None,
    event_sink=None,
) -> AgentQueryResponse:
    effective_mode = request.mode
    if effective_mode is None:
        effective_mode = "tool_calling_agent"
    log_agent_query_received(request, effective_mode=effective_mode)

    if effective_mode == "agentic":
        agentic_result = run_agentic_rag(
            question=request.question,
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_model_provider,
            history=conversation_history or request.history,
        )
        response = maybe_enrich_agent_response_with_figure_evidence(
            db=db,
            question=request.question,
            response=agent_response_from_agentic_result(agentic_result),
            effective_mode=effective_mode,
        )
        log_agent_response_event(response)
        return response

    if effective_mode == "react_agent":
        result = ReActAgentService(
            db=db,
            chat_model_provider=chat_model_provider,
            embedding_provider=embedding_provider,
            planner_chat_provider=planner_chat_provider,
        ).query(
            question=request.question,
            top_k=request.top_k,
            max_tool_calls=request.max_tool_calls,
            history=conversation_history or request.history,
            event_sink=event_sink,
        )
        response = maybe_enrich_agent_response_with_figure_evidence(
            db=db,
            question=request.question,
            response=agent_response_from_result(result),
            effective_mode=effective_mode,
        )
        log_agent_response_event(response)
        return response

    if effective_mode == "tool_calling_agent":
        result = ToolCallingAgentService(
            db=db,
            chat_model_provider=chat_model_provider,
            embedding_provider=embedding_provider,
        ).query(
            question=request.question,
            top_k=request.top_k,
            max_tool_calls=request.max_tool_calls,
            history=conversation_history or request.history,
            event_sink=event_sink,
        )
        response = maybe_enrich_agent_response_with_figure_evidence(
            db=db,
            question=request.question,
            response=agent_response_from_result(result),
            effective_mode=effective_mode,
        )
        log_agent_response_event(response)
        return response

    result = AgentService(
        db=db,
        chat_model_provider=chat_model_provider,
        embedding_provider=embedding_provider,
    ).query(
        question=request.question,
        top_k=request.top_k,
        max_tool_calls=request.max_tool_calls,
        source_id=request.source_id,
        history=conversation_history or request.history,
    )
    response = maybe_enrich_agent_response_with_figure_evidence(
        db=db,
        question=request.question,
        response=agent_response_from_result(result),
        effective_mode=effective_mode,
    )
    log_agent_response_event(response)
    return response


def log_agent_query_received(
    request: AgentQueryRequest,
    *,
    effective_mode: str,
) -> None:
    log_event(
        agent_logger,
        "query_received",
        mode=effective_mode,
        conversation_id=request.conversation_id,
        top_k=request.top_k,
        max_tool_calls=request.max_tool_calls,
        source_id=request.source_id,
        question_summary=safe_text_summary(request.question, limit=80),
    )


def log_agent_response_event(response: AgentQueryResponse) -> None:
    event = "refusal_triggered" if response.refused else "answer_generated"
    latency_ms = response.latency_trace.get("total_latency_ms")
    log_event(
        agent_logger,
        event,
        mode=response.mode,
        refused=response.refused,
        refusal_category=response.refusal_category,
        citation_count=len(response.citations),
        source_count=len(response.sources),
        tool_call_count=len(response.tool_calls),
        iteration_count=response.iteration_count,
        latency_ms=latency_ms,
    )


def sse_event(event: str, payload: dict[str, object]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"


class QueueStreamingChatModelProvider:
    def __init__(
        self,
        *,
        base_provider: ChatModelProvider,
        queue: Queue[tuple[str, Any]],
    ) -> None:
        self.base_provider = base_provider
        self.queue = queue
        self.provider_name = base_provider.provider_name
        self.model_name = base_provider.model_name

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        try:
            token_stream = self.base_provider.stream_generate(messages)
        except AttributeError:
            result = self.base_provider.generate(messages)
            for token in split_streaming_text(result.answer):
                self.queue.put(("token", token))
            return result

        answer_parts: list[str] = []
        for token in token_stream:
            self.queue.put(("token", token))
            answer_parts.append(token)
        return ChatModelResult(
            answer="".join(answer_parts),
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response=None,
        )

    def stream_generate(self, messages: Sequence[ChatMessage]) -> Iterator[str]:
        yield from self.base_provider.stream_generate(messages)

    def generate_with_tools(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ChatToolDefinition],
    ) -> ToolCallingChatModelResult:
        return self.base_provider.generate_with_tools(messages, tools)


def agent_response_from_chitchat(
    question: str,
    chitchat: ChitchatResult,
) -> AgentQueryResponse:
    return AgentQueryResponse(
        question=question.strip(),
        answer=chitchat.answer,
        tool_calls=[],
        search_results=[],
        sources=[],
        citations=[],
        refused=False,
        refusal_reason=None,
        reasoning_summary=chitchat.reasoning_summary,
        mode="default",
        workflow_steps=[],
        iteration_count=0,
        invalid_citations=[],
        refusal_category=None,
        latency_trace={},
    )


def agent_response_from_agentic_result(result: AgenticResult) -> AgentQueryResponse:
    sources = [
        AgentSourceItem(
            source_id=f"chunk:{s.chunk_id}",
            title=s.document_title,
            source_type=s.source_type,
            status=None,
            trust_level=None,
            fulltext_permission=None,
            document_id=s.document_id,
            chunk_id=s.chunk_id,
            chunk_index=s.chunk_index,
            url=None,
            doi=None,
            content=s.content,
            score=s.score,
            chunk_type=getattr(s, "chunk_type", "text"),
            source_image_path=getattr(s, "source_image_path", None),
            image_url=image_url_from_source_image_path(getattr(s, "source_image_path", None)),
            caption=getattr(s, "caption", None),
            page_number=page_number_from_source_image_path(getattr(s, "source_image_path", None)),
            table_content=getattr(s, "content", None) if getattr(s, "chunk_type", "text") == "table" else None,
            image_analysis=getattr(s, "image_analysis", None),
            content_bbox=getattr(s, "content_bbox", None),
        )
        for s in result.sources
    ]
    tool_calls = [
        AgentToolCallItem(
            tool_name=step.name,
            input_summary=step.input_summary,
            output_summary=step.output_summary,
            succeeded=step.succeeded,
            error=step.error,
        )
        for step in result.workflow_steps
    ]
    workflow_steps = [
        AgentWorkflowStepItem(
            name=step.name,
            input_summary=step.input_summary,
            output_summary=step.output_summary,
            succeeded=step.succeeded,
            error=step.error,
        )
        for step in result.workflow_steps
    ]
    response = AgentQueryResponse(
        question=result.question,
        answer=result.answer,
        tool_calls=tool_calls,
        search_results=[
            AgentSearchResultItem(
                document_id=s.document_id,
                document_title=s.document_title,
                source_type=s.source_type,
                source_path=s.source_path,
                file_name=s.file_name,
                chunk_id=s.chunk_id,
                chunk_index=s.chunk_index,
                content=s.content,
                heading_path=s.heading_path,
                score=s.score,
                chunk_type=getattr(s, "chunk_type", "text"),
                source_image_path=getattr(s, "source_image_path", None),
                image_url=image_url_from_source_image_path(getattr(s, "source_image_path", None)),
                caption=getattr(s, "caption", None),
                page_number=page_number_from_source_image_path(getattr(s, "source_image_path", None)),
                table_content=getattr(s, "content", None) if getattr(s, "chunk_type", "text") == "table" else None,
                image_analysis=getattr(s, "image_analysis", None),
                content_bbox=getattr(s, "content_bbox", None),
            )
            for s in result.sources
        ],
        sources=sources,
        citations=result.citations,
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        reasoning_summary=f"agentic RAG, iterations={result.iteration_count}",
        mode="agentic",
        workflow_steps=workflow_steps,
        iteration_count=result.iteration_count,
        invalid_citations=result.invalid_citations,
        refusal_category=refusal_category_from_agentic_result(result),
        latency_trace={},
    )
    return with_refusal_explanation(response)


def agent_response_from_result(result: AgentQueryResult) -> AgentQueryResponse:
    refusal_category = refusal_category_from_refusal(
        refused=result.refused,
        refusal_reason=result.refusal_reason,
    )
    response = AgentQueryResponse(
        question=result.question,
        answer=result.answer,
        tool_calls=[
            AgentToolCallItem(
                tool_name=call.tool_name,
                input_summary=call.input_summary,
                output_summary=call.output_summary,
                succeeded=call.succeeded,
                error=call.error,
            )
            for call in result.tool_calls
        ],
        search_results=[
            AgentSearchResultItem(
                document_id=item.document_id,
                document_title=item.document_title,
                source_type=item.source_type,
                source_path=item.source_path,
                file_name=item.file_name,
                chunk_id=item.chunk_id,
                chunk_index=item.chunk_index,
                content=item.content,
                heading_path=item.heading_path,
                score=item.score,
                chunk_type=item.chunk_type,
                source_image_path=item.source_image_path,
                image_url=item.image_url,
                caption=item.caption,
                page_number=item.page_number,
                table_content=item.table_content,
                image_analysis=item.image_analysis,
                content_bbox=item.content_bbox,
            )
            for item in result.search_results
        ],
        sources=[
            AgentSourceItem(
                source_id=source.source_id,
                title=source.title,
                source_type=source.source_type,
                status=source.status,
                trust_level=source.trust_level,
                fulltext_permission=source.fulltext_permission,
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                chunk_index=source.chunk_index,
                url=source.url,
                doi=source.doi,
                content=source.content,
                score=source.score,
                chunk_type=source.chunk_type,
                source_image_path=source.source_image_path,
                image_url=source.image_url,
                caption=source.caption,
                page_number=source.page_number,
                table_content=source.table_content,
                image_analysis=source.image_analysis,
                content_bbox=source.content_bbox,
            )
            for source in result.sources
        ],
        citations=result.citations,
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        reasoning_summary=result.reasoning_summary,
        mode=result.mode,
        workflow_steps=[
            AgentWorkflowStepItem(
                name=step.tool_name,
                input_summary=step.input_summary,
                output_summary=step.output_summary,
                succeeded=step.succeeded,
                error=step.error,
            )
            for step in result.workflow_steps
        ],
        iteration_count=result.iteration_count,
        refusal_category=refusal_category,
        latency_trace=result.latency_trace,
    )
    return with_refusal_explanation(response)


def with_refusal_explanation(response: AgentQueryResponse) -> AgentQueryResponse:
    if not response.refused:
        return response
    explanation = build_refusal_explanation(
        category=response.refusal_category,
        refusal_reason=response.refusal_reason,
        sources=response.sources,
    )
    if not explanation:
        return response
    if explanation in response.reasoning_summary:
        return response
    separator = " | " if response.reasoning_summary else ""
    return response.model_copy(
        update={
            "reasoning_summary": f"{response.reasoning_summary}{separator}{explanation}",
        }
    )


def refusal_category_from_agentic_result(result: AgenticResult) -> str | None:
    return refusal_category_from_refusal(
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        responsibility_gate_triggered=result.responsibility_gate_triggered,
    )


def refusal_category_from_refusal(
    *,
    refused: bool,
    refusal_reason: str | None,
    responsibility_gate_triggered: bool = False,
) -> str | None:
    if not refused:
        return None

    normalized_reason = (refusal_reason or "").casefold()
    if responsibility_gate_triggered or "responsibility_gate" in normalized_reason:
        return "responsibility_gate_triggered"
    if "off-topic" in normalized_reason or "no domain anchor" in normalized_reason:
        return "off_topic"
    if (
        "tool execution failed" in normalized_reason
        or "request failed" in normalized_reason
        or "request timed out" in normalized_reason
    ):
        return "service_error"
    return "evidence_insufficient"


def persist_agent_conversation_messages(
    *,
    repository: ConversationRepository,
    conversation_id: int | None,
    question: str,
    response: AgentQueryResponse,
    chat_model_provider: ChatModelProvider,
    summarize: bool = True,
) -> None:
    if conversation_id is None:
        return

    repository.add_message(
        MessageCreate(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
    )
    repository.add_message(
        MessageCreate(
            conversation_id=conversation_id,
            role="assistant",
            content=response.answer,
            mode=response.mode,
            metadata=assistant_metadata_from_response(response),
        )
    )
    if not summarize:
        return
    try:
        summary_message = summarize_conversation_if_needed(
            repository=repository,
            conversation_id=conversation_id,
            chat_model_provider=chat_model_provider,
        )
        if summary_message is not None:
            log_event(
                agent_logger,
                "summary_assembled",
                conversation_id=conversation_id,
                summary_message_id=summary_message.id,
            )
    except RuntimeError:
        # Summary compression is a best-effort optimization. Do not fail an
        # otherwise successful user answer when the model provider times out.
        return


def assistant_metadata_from_response(response: AgentQueryResponse) -> dict[str, object]:
    payload = response.model_dump(mode="json")
    return {
        key: payload[key]
        for key in [
            "tool_calls",
            "search_results",
            "sources",
            "citations",
            "refused",
            "refusal_reason",
            "reasoning_summary",
            "mode",
            "workflow_steps",
            "iteration_count",
            "invalid_citations",
            "refusal_category",
            "latency_trace",
        ]
    }


def mark_response_first_token(response: AgentQueryResponse, stream_started: float) -> None:
    if not response.latency_trace:
        response.latency_trace = {}
    if response.latency_trace.get("time_to_first_token_ms") is not None:
        return
    response.latency_trace["time_to_first_token_ms"] = round(
        (time.perf_counter() - stream_started) * 1000.0,
        3,
    )
