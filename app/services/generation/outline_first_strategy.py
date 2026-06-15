from collections.abc import Sequence
from dataclasses import dataclass

from app.services.brain.workflow import extract_citations
from app.services.generation.chat_model import (
    ChatMessage,
    ChatModelProvider,
    ChatModelResult,
)
from app.services.generation.prompt_builder import ContextSource, format_context


@dataclass(frozen=True)
class OutlineFirstResult:
    answer: str
    outline: str
    citations: list[int]
    provider: str
    model_name: str


def generate_outline_first_answer(
    *,
    question: str,
    sources: Sequence[ContextSource],
    chat_model_provider: ChatModelProvider,
) -> OutlineFirstResult:
    if not question.strip():
        raise ValueError("question must not be empty")
    if not sources:
        raise ValueError("sources must not be empty")

    outline_result = chat_model_provider.generate(
        build_outline_messages(question=question, sources=sources)
    )
    final_result = chat_model_provider.generate(
        build_final_messages(
            question=question,
            sources=sources,
            outline=outline_result.answer,
        )
    )
    allowed_source_ids = [source.source_id for source in sources]
    citations = extract_citations(final_result.answer, allowed_source_ids)
    return OutlineFirstResult(
        answer=final_result.answer,
        outline=outline_result.answer,
        citations=citations,
        provider=final_result.provider,
        model_name=final_result.model_name,
    )


def build_outline_messages(
    *,
    question: str,
    sources: Sequence[ContextSource],
) -> list[ChatMessage]:
    context = format_context(sources)
    return [
        ChatMessage(
            role="system",
            content=(
                "You prepare evidence-grounded answer outlines for RFC-RAG-Agent. "
                "Return concise bullets only. Each bullet must include the source "
                "marker that supports it, such as [1]. Do not include hidden "
                "reasoning or unsupported claims."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Question:\n{question.strip()}\n\n"
                f"Context:\n{context}\n\n"
                "Build an outline of supported answer points. If a requested "
                "aspect is missing from the context, include a bullet saying the "
                "evidence is not found."
            ),
        ),
    ]


def build_final_messages(
    *,
    question: str,
    sources: Sequence[ContextSource],
    outline: str,
) -> list[ChatMessage]:
    context = format_context(sources)
    return [
        ChatMessage(
            role="system",
            content=(
                "You write citation-first answers for RFC-RAG-Agent. Use only the "
                "provided context and the evidence outline. Keep citations next "
                "to the exact sentence they support. Do not expose chain-of-thought, "
                "raw provider responses, credentials, or restricted full text."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Question:\n{question.strip()}\n\n"
                f"Evidence outline:\n{outline.strip()}\n\n"
                f"Context:\n{context}\n\n"
                "Write the final answer in the same language as the question. "
                "Cover every supported outline point and clearly say when evidence "
                "for a requested aspect was not found."
            ),
        ),
    ]


def outline_first_result_to_chat_result(result: OutlineFirstResult) -> ChatModelResult:
    return ChatModelResult(
        answer=result.answer,
        provider=result.provider,
        model_name=result.model_name,
        raw_response=None,
    )
