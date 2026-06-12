from __future__ import annotations

import asyncio
import json
from typing import Any
from typing import NamedTuple

from pydantic import ValidationError

from app.api.agent import (
    get_agent_chat_model_provider,
    get_agent_embedding_provider,
    stream_agent_query_events,
)
from app.db.repositories import ConversationCreate, ConversationRepository
from app.db.session import SessionLocal, init_db
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse
from app.services.conversation.history import history_from_messages

try:
    import chainlit as cl
except ModuleNotFoundError:  # pragma: no cover - used only before dependencies install.
    cl = None  # type: ignore[assignment]


class ParsedStreamEvent(NamedTuple):
    name: str
    payload: dict[str, Any]


def parse_sse_event(raw_event: str) -> ParsedStreamEvent | None:
    event_name = ""
    data = "{}"
    for line in raw_event.strip().splitlines():
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data = line.removeprefix("data:").strip()
    if not event_name:
        return None
    return ParsedStreamEvent(name=event_name, payload=json.loads(data or "{}"))


def next_stream_event(iterator) -> str | None:
    try:
        return next(iterator)
    except StopIteration:
        return None


def sources_markdown(response: AgentQueryResponse) -> str:
    if not response.sources:
        return "本轮没有返回引用来源。"

    lines = ["# 引用来源"]
    for index, source in enumerate(response.sources, start=1):
        citation = index
        title = source.title or "Untitled source"
        source_type = source.source_type or "unknown"
        chunk = (
            f"chunk={source.chunk_id}, index={source.chunk_index}"
            if source.chunk_id is not None
            else "source-level record"
        )
        score = f", score={source.score:.4f}" if source.score is not None else ""
        lines.append(f"- [{citation}] {title} ({source_type}; {chunk}{score})")
        if source.content:
            excerpt = " ".join(source.content.split())[:280]
            lines.append(f"  - 摘要：{excerpt}")
    return "\n".join(lines)


def workflow_markdown(response: AgentQueryResponse) -> str:
    if not response.workflow_steps:
        return "本轮走 default AgentService，没有 agentic workflow 步骤。"

    lines = ["# Agentic Workflow"]
    for index, step in enumerate(response.workflow_steps, start=1):
        status = "ok" if step.succeeded else "failed"
        lines.append(f"{index}. {step.name} - {status}")
        if step.input_summary:
            lines.append(f"   - input: {step.input_summary}")
        if step.output_summary:
            lines.append(f"   - output: {step.output_summary}")
        if step.error:
            lines.append(f"   - error: {step.error}")
    return "\n".join(lines)


def response_metadata(response: AgentQueryResponse) -> dict[str, Any]:
    return {
        "mode": response.mode,
        "refused": response.refused,
        "refusal_category": response.refusal_category,
        "citations": response.citations,
        "iteration_count": response.iteration_count,
        "invalid_citations": response.invalid_citations,
    }


def ensure_conversation(repository: ConversationRepository, existing_id: int | None) -> int:
    if existing_id is not None and repository.get_conversation(existing_id) is not None:
        return existing_id
    conversation = repository.create_conversation(ConversationCreate(title="Chainlit 对话"))
    return int(conversation.id)


async def emit_workflow_steps(response: AgentQueryResponse) -> None:
    if cl is None:
        return
    steps = response.workflow_steps or response.tool_calls
    if not steps:
        return

    for step_item in steps:
        step_name = getattr(step_item, "name", None) or getattr(step_item, "tool_name", "step")
        async with cl.Step(name=step_name, type="tool", show_input=True) as step:
            step.input = getattr(step_item, "input_summary", "")
            step.output = getattr(step_item, "output_summary", "")
            if getattr(step_item, "error", None):
                step.output = f"{step.output}\n\nerror: {step_item.error}"
                step.is_error = True


async def handle_chainlit_message(message) -> None:
    if cl is None:
        raise RuntimeError("chainlit is not installed")

    try:
        request = AgentQueryRequest(question=message.content)
    except ValidationError as exc:
        await cl.Message(content=f"请求无效：{exc.errors()[0]['msg']}").send()
        return

    init_db()
    db = SessionLocal()
    try:
        repository = ConversationRepository(db)
        conversation_id = ensure_conversation(
            repository,
            cl.user_session.get("conversation_id"),
        )
        cl.user_session.set("conversation_id", conversation_id)
        request.conversation_id = conversation_id
        conversation_history = history_from_messages(repository.list_messages(conversation_id))

        answer_message = await cl.Message(content="").send()
        response: AgentQueryResponse | None = None
        stream_iterator = stream_agent_query_events(
            request=request,
            db=db,
            conversation_repository=repository,
            conversation_history=conversation_history,
            chat_model_provider=get_agent_chat_model_provider(),
            embedding_provider=get_agent_embedding_provider(),
        )

        while True:
            raw_event = await asyncio.to_thread(next_stream_event, stream_iterator)
            if raw_event is None:
                break
            event = parse_sse_event(raw_event)
            if event is None:
                continue
            if event.name == "token":
                await answer_message.stream_token(str(event.payload.get("text", "")))
            elif event.name == "metadata":
                response = AgentQueryResponse.model_validate(event.payload)
            elif event.name == "error":
                detail = event.payload.get("detail") or event.payload.get("message")
                if answer_message.content:
                    answer_message.content += f"\n\n错误：{detail}"
                    await answer_message.update()
                else:
                    await cl.Message(content=f"错误：{detail}").send()
                return

        if response is not None:
            answer_message.metadata = response_metadata(response)
            answer_message.elements = [
                cl.Text(
                    name="引用来源",
                    content=sources_markdown(response),
                    display="inline",
                ),
                cl.Text(
                    name="运行步骤",
                    content=workflow_markdown(response),
                    display="inline",
                ),
            ]
            await answer_message.update()
            await emit_workflow_steps(response)
        else:
            await answer_message.update()
    finally:
        db.close()


if cl is not None:

    @cl.on_chat_start
    async def on_chat_start() -> None:
        init_db()
        db = SessionLocal()
        try:
            repository = ConversationRepository(db)
            conversation_id = ensure_conversation(repository, None)
            cl.user_session.set("conversation_id", conversation_id)
        finally:
            db.close()
        await cl.Message(
            content=(
                "你好，我是 RFC-RAG-Agent。你可以直接问堆石混凝土资料问题，"
                "我会流式回答并附上引用来源和运行步骤。"
            )
        ).send()

    @cl.on_message
    async def on_message(message) -> None:
        await handle_chainlit_message(message)
