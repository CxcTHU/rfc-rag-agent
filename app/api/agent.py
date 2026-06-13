import json
from collections.abc import Iterator, Sequence
from queue import Queue
from threading import Thread
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.repositories import ConversationRepository, MessageCreate
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
from app.services.agent.service import AgentQueryResult, AgentService
from app.services.agent.react_service import ReActAgentService
from app.services.agent.react_service import ReActRuntimeEvent
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
    create_chat_model_provider,
    split_streaming_text,
)
from app.services.retrieval.embedding import EmbeddingProvider, create_embedding_provider

router = APIRouter(prefix="/agent", tags=["agent"])


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
    chat_model_provider: ChatModelProvider = Depends(get_agent_chat_model_provider),
    embedding_provider: EmbeddingProvider = Depends(get_agent_embedding_provider),
) -> AgentQueryResponse:
    conversation_repository = ConversationRepository(db)
    conversation_history: list[str] = []
    if request.conversation_id is not None:
        conversation = conversation_repository.get_conversation(request.conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            )
        conversation_history = history_from_messages(
            conversation_repository.list_messages(request.conversation_id)
        )

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
        routing = classify_query_complexity(request.question)
        effective_mode = "agentic" if routing.complexity == "complex" else "default"

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
        response = agent_response_from_agentic_result(agentic_result)
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
        response = agent_response_from_result(result)
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

    response = agent_response_from_result(result)
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
    chat_model_provider: ChatModelProvider = Depends(get_agent_chat_model_provider),
    embedding_provider: EmbeddingProvider = Depends(get_agent_embedding_provider),
) -> StreamingResponse:
    conversation_repository = ConversationRepository(db)
    conversation_history: list[str] = []
    if request.conversation_id is not None:
        conversation = conversation_repository.get_conversation(request.conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            )
        conversation_history = history_from_messages(
            conversation_repository.list_messages(request.conversation_id)
        )

    return StreamingResponse(
        stream_agent_query_events(
            request=request,
            db=db,
            conversation_repository=conversation_repository,
            conversation_history=conversation_history,
            chat_model_provider=chat_model_provider,
            embedding_provider=embedding_provider,
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
    conversation_history: list[str],
    chat_model_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
) -> Iterator[str]:
    try:
        chitchat = detect_chitchat(request.question)
        summarize = True
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
            )
            if streamed_token_count == 0:
                for token in split_streaming_text(response.answer):
                    yield sse_event("token", {"text": token})

        if chitchat is not None:
            for token in split_streaming_text(response.answer):
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
) -> Iterator[str | tuple[AgentQueryResponse, int]]:
    queue: Queue[tuple[str, Any]] = Queue()

    def produce_response() -> None:
        try:
            effective_chat_model_provider = chat_model_provider
            if request.mode != "react_agent":
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
                event_sink=lambda event: queue.put(("react_event", event)),
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
        if event_type == "react_event":
            react_event: ReActRuntimeEvent = payload
            yield sse_event(react_event.event, react_event.payload)
            continue
        if event_type == "response":
            producer.join()
            return payload, streamed_token_count
        if event_type == "error":
            producer.join()
            raise payload

        producer.join()
        raise RuntimeError("unknown stream event")


def build_agent_query_response(
    *,
    request: AgentQueryRequest,
    db: Session,
    conversation_history: list[str],
    chat_model_provider: ChatModelProvider,
    embedding_provider: EmbeddingProvider,
    event_sink=None,
) -> AgentQueryResponse:
    effective_mode = request.mode
    if effective_mode is None:
        routing = classify_query_complexity(request.question)
        effective_mode = "agentic" if routing.complexity == "complex" else "default"

    if effective_mode == "agentic":
        agentic_result = run_agentic_rag(
            question=request.question,
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_model_provider,
            history=conversation_history or request.history,
        )
        return agent_response_from_agentic_result(agentic_result)

    if effective_mode == "react_agent":
        result = ReActAgentService(
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
        return agent_response_from_result(result)

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
    return agent_response_from_result(result)


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
    return AgentQueryResponse(
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
    )


def agent_response_from_result(result: AgentQueryResult) -> AgentQueryResponse:
    return AgentQueryResponse(
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
        refusal_category=refusal_category_from_refusal(
            refused=result.refused,
            refusal_reason=result.refusal_reason,
        ),
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
        summarize_conversation_if_needed(
            repository=repository,
            conversation_id=conversation_id,
            chat_model_provider=chat_model_provider,
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
        ]
    }
