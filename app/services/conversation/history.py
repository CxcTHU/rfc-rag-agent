from __future__ import annotations

from collections.abc import Sequence

from app.db.models import Message
from app.db.repositories import ConversationRepository, MessageCreate
from app.services.generation.chat_model import ChatMessage, ChatModelProvider


SUMMARY_TRIGGER_NON_SUMMARY_MESSAGES = 16
SUMMARY_RECENT_NON_SUMMARY_MESSAGES = 6


def format_message_for_history(message: Message) -> str:
    if message.role == "summary":
        return f"对话摘要：{message.content}"
    if message.role == "user":
        return f"用户：{message.content}"
    if message.role == "assistant":
        return f"助手：{message.content}"
    return message.content


def history_from_messages(messages: Sequence[Message]) -> list[str]:
    if not messages:
        return []

    latest_summary_index = latest_summary_message_index(messages)
    selected_messages = (
        messages[latest_summary_index:]
        if latest_summary_index is not None
        else messages
    )
    return [format_message_for_history(message) for message in selected_messages]


def latest_summary_message_index(messages: Sequence[Message]) -> int | None:
    latest_index: int | None = None
    for index, message in enumerate(messages):
        if message.role == "summary":
            latest_index = index
    return latest_index


def summarize_conversation_if_needed(
    *,
    repository: ConversationRepository,
    conversation_id: int,
    chat_model_provider: ChatModelProvider,
    trigger_message_count: int = SUMMARY_TRIGGER_NON_SUMMARY_MESSAGES,
    keep_recent_message_count: int = SUMMARY_RECENT_NON_SUMMARY_MESSAGES,
) -> Message | None:
    messages = repository.list_messages(conversation_id)
    latest_summary_index = latest_summary_message_index(messages)
    messages_after_summary = (
        messages[latest_summary_index + 1:]
        if latest_summary_index is not None
        else messages
    )
    non_summary_after_summary = [
        message for message in messages_after_summary if message.role != "summary"
    ]
    if len(non_summary_after_summary) <= trigger_message_count:
        return None

    messages_to_summarize = non_summary_after_summary[:-keep_recent_message_count]
    if not messages_to_summarize:
        return None

    previous_summary = messages[latest_summary_index] if latest_summary_index is not None else None
    summary_text = generate_summary(
        previous_summary=previous_summary,
        messages_to_summarize=messages_to_summarize,
        chat_model_provider=chat_model_provider,
    )
    summarized_messages = (
        ([previous_summary] if previous_summary is not None else [])
        + list(messages_to_summarize)
    )
    summarized_ids = [message.id for message in summarized_messages]
    return repository.add_message(
        MessageCreate(
            conversation_id=conversation_id,
            role="summary",
            content=summary_text,
            metadata={
                "summary_of_message_ids": summarized_ids,
                "kept_recent_non_summary_messages": keep_recent_message_count,
            },
        )
    )


def generate_summary(
    *,
    previous_summary: Message | None,
    messages_to_summarize: Sequence[Message],
    chat_model_provider: ChatModelProvider,
) -> str:
    conversation_text = "\n".join(
        format_message_for_history(message) for message in messages_to_summarize
    )
    previous_summary_text = (
        f"已有摘要：\n{previous_summary.content}\n\n"
        if previous_summary is not None
        else ""
    )
    prompt = "\n".join(
        [
            "请把下面的多轮对话压缩成 200-400 字中文摘要。",
            "保留用户真实目标、关键约束、已经给出的结论、引用主题和未解决问题。",
            "不要加入对话之外的新资料，不要保存 API key、token 或供应商原始响应。",
            "",
            previous_summary_text + "待摘要消息：",
            conversation_text,
        ]
    )
    result = chat_model_provider.generate(
        [
            ChatMessage(
                role="system",
                content="你是 RFC-RAG-Agent 的会话摘要器，只做短期对话摘要。",
            ),
            ChatMessage(role="user", content=prompt),
        ]
    )
    return result.answer.strip()
