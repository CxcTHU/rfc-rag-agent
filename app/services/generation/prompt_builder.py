from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from app.services.generation.chat_model import ChatMessage


DEFAULT_MAX_CONTEXT_CHARS = 6000
DEFAULT_MAX_CHUNK_CHARS = 1200

DEFAULT_SYSTEM_PROMPT = """You are RFC-RAG-Agent, a citation-first assistant for rock-filled concrete study.
Use only the provided context to answer the user's question.
If the context is not enough, say that the current knowledge base does not contain enough reliable evidence.
Start with the direct answer, then explain the reasoning or details.
Attach source markers like [1] or [2] to each factual claim; do not cite only once at the end of a paragraph.
Separate facts from engineering judgment or uncertainty.
For comparison questions, describe both sides before stating the difference.
If the user's question contains an incorrect assumption or premise that contradicts the context, you must explicitly correct the misconception first, then provide the accurate answer with citations. Never agree with a false premise.
This system is for learning and document retrieval only, not a substitute for code review, engineering design, or expert judgment.
本系统仅用于学习和资料检索，不能替代规范审查、工程设计和专家判断。"""


class SearchResultLike(Protocol):
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    score: float


@dataclass(frozen=True)
class ContextSource:
    source_id: int
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    score: float


@dataclass(frozen=True)
class RagPrompt:
    messages: list[ChatMessage]
    context_text: str
    sources: list[ContextSource]


def build_rag_prompt(
    question: str,
    search_results: Sequence[SearchResultLike],
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> RagPrompt:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")
    if not search_results:
        raise ValueError("search_results must not be empty")
    if max_context_chars <= 0:
        raise ValueError("max_context_chars must be greater than 0")
    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars must be greater than 0")

    sources = [
        context_source_from_search_result(source_id=index, result=result)
        for index, result in enumerate(search_results, start=1)
    ]
    limited_sources = limit_sources_for_context(
        sources=sources,
        max_context_chars=max_context_chars,
        max_chunk_chars=max_chunk_chars,
    )
    if not limited_sources:
        raise ValueError("no source content remained after context limiting")

    context_text = format_context(limited_sources)
    user_prompt = build_user_prompt(normalized_question, context_text)
    return RagPrompt(
        messages=[
            ChatMessage(role="system", content=system_prompt.strip()),
            ChatMessage(role="user", content=user_prompt),
        ],
        context_text=context_text,
        sources=limited_sources,
    )


def context_source_from_search_result(
    source_id: int,
    result: SearchResultLike,
) -> ContextSource:
    return ContextSource(
        source_id=source_id,
        document_id=result.document_id,
        document_title=result.document_title,
        source_type=result.source_type,
        source_path=result.source_path,
        file_name=result.file_name,
        chunk_id=result.chunk_id,
        chunk_index=result.chunk_index,
        content=result.content.strip(),
        heading_path=result.heading_path,
        score=result.score,
    )


def limit_sources_for_context(
    sources: Sequence[ContextSource],
    max_context_chars: int,
    max_chunk_chars: int,
) -> list[ContextSource]:
    limited_sources: list[ContextSource] = []
    used_chars = 0
    for source in sources:
        limited_content = truncate_text(source.content, max_chunk_chars)
        if not limited_content:
            continue
        candidate = replace(source, content=limited_content)
        formatted_candidate = format_source(candidate)
        candidate_length = len(formatted_candidate)
        if used_chars and used_chars + candidate_length > max_context_chars:
            break
        if not used_chars and candidate_length > max_context_chars:
            candidate = replace(
                candidate,
                content=truncate_text(candidate.content, max_context_chars),
            )
            formatted_candidate = format_source(candidate)
            candidate_length = len(formatted_candidate)
        limited_sources.append(candidate)
        used_chars += candidate_length
    return limited_sources


def format_context(sources: Sequence[ContextSource]) -> str:
    return "\n\n".join(format_source(source) for source in sources)


def format_source(source: ContextSource) -> str:
    heading = source.heading_path or "None"
    source_path = source.source_path or "None"
    return "\n".join(
        [
            f"[{source.source_id}]",
            f"Title: {source.document_title}",
            f"Source type: {source.source_type}",
            f"Source path: {source_path}",
            f"File name: {source.file_name}",
            f"Chunk: {source.chunk_id} / index {source.chunk_index}",
            f"Heading: {heading}",
            f"Score: {source.score:.4f}",
            "Content:",
            source.content,
        ]
    )


def build_user_prompt(question: str, context_text: str) -> str:
    return "\n".join(
        [
            "Question:",
            question,
            "",
            "Context:",
            context_text,
            "",
            "Answer requirements:",
            "- Answer in the same language as the question.",
            "- Give the direct answer first, then explain; do not open with a long background section.",
            "- Cite every factual claim with [1], [2], etc.; do not cite only once at the end of a paragraph.",
            "- Do not use information outside the context.",
            "- If evidence is insufficient, refuse clearly.",
            "- If the question contains a wrong assumption, correct it before answering. Do not start with agreement words like '是的' or 'Yes' when the premise is factually incorrect according to the context.",
            "- For difference or comparison questions, explain the characteristics of both sides before comparing them.",
        ]
    )


def truncate_text(text: str, max_chars: int) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    suffix = "... [truncated]"
    if max_chars <= len(suffix):
        return stripped[:max_chars].strip()
    return f"{stripped[: max_chars - len(suffix)].rstrip()}{suffix}"
