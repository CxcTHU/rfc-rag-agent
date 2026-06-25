from dataclasses import dataclass

import pytest

from app.services.generation.prompt_builder import (
    DEFAULT_SYSTEM_PROMPT,
    STRICT_CITATION_SYSTEM_PROMPT,
    build_rag_prompt,
    format_source,
    truncate_text,
)


@dataclass(frozen=True)
class FakeSearchResult:
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
    chunk_type: str = "text"
    source_image_path: str | None = None
    caption: str | None = None


def test_build_rag_prompt_numbers_sources_in_order() -> None:
    prompt = build_rag_prompt(
        "什么是堆石混凝土？",
        [
            fake_result(chunk_id=101, title="Doc A"),
            fake_result(chunk_id=202, title="Doc B"),
        ],
    )

    assert prompt.sources[0].source_id == 1
    assert prompt.sources[0].chunk_id == 101
    assert prompt.sources[1].source_id == 2
    assert prompt.sources[1].chunk_id == 202
    assert "[1]" in prompt.context_text
    assert "[2]" in prompt.context_text


def test_build_rag_prompt_creates_system_and_user_messages() -> None:
    prompt = build_rag_prompt("What is RFC?", [fake_result()])

    assert [message.role for message in prompt.messages] == ["system", "user"]
    assert "Use only the provided context" in prompt.messages[0].content
    assert "Question:" in prompt.messages[1].content
    assert "What is RFC?" in prompt.messages[1].content
    assert "Context:" in prompt.messages[1].content


def test_build_rag_prompt_includes_engineering_disclaimer() -> None:
    prompt = build_rag_prompt("什么是堆石混凝土？", [fake_result()])

    assert "不能替代规范审查、工程设计和专家判断" in prompt.messages[0].content
    assert "不能替代规范审查、工程设计和专家判断" in DEFAULT_SYSTEM_PROMPT


def test_build_rag_prompt_includes_answer_quality_requirements() -> None:
    prompt = build_rag_prompt("A 和 B 有什么区别？", [fake_result()])
    system_message = prompt.messages[0].content
    user_message = prompt.messages[1].content

    assert "Start with the direct answer" in system_message
    assert "comparison questions" in system_message
    assert "Give the direct answer first" in user_message
    assert "Use source markers like [1]" in user_message
    assert "explain the characteristics of both sides" in user_message


def test_build_rag_prompt_requires_named_sources_for_evidence_gaps() -> None:
    prompt = build_rag_prompt("Which standards mention compressive strength?", [fake_result()])
    system_message = prompt.messages[0].content
    user_message = prompt.messages[1].content

    assert "concrete retrieved Title or File name" in system_message
    assert "concrete retrieved Title or File name" in user_message
    assert "do not refer to evidence only as 'source [1]'" in user_message
    assert "Title A [1] only states X" in user_message


def test_build_rag_prompt_supports_prompt_profile_ab_test(monkeypatch) -> None:
    monkeypatch.setenv("RAG_PROMPT_PROFILE", "coverage_first")

    prompt = build_rag_prompt("What is RFC?", [fake_result()])

    assert "list all supported answer points first" in prompt.messages[0].content
    assert "enumerate the supported answer points first" in prompt.messages[1].content
    assert "Cite every factual claim" in prompt.messages[1].content


def test_build_rag_prompt_supports_explicit_strict_citation_profile(monkeypatch) -> None:
    monkeypatch.setenv("RAG_PROMPT_PROFILE", "strict_citation")

    prompt = build_rag_prompt("What is RFC?", [fake_result()])

    assert prompt.messages[0].content == STRICT_CITATION_SYSTEM_PROMPT
    assert "Give the direct answer first" in prompt.messages[1].content
    assert "Cite every factual claim" in prompt.messages[1].content


def test_build_rag_prompt_rejects_empty_question() -> None:
    with pytest.raises(ValueError, match="question must not be empty"):
        build_rag_prompt("   ", [fake_result()])


def test_build_rag_prompt_rejects_empty_search_results() -> None:
    with pytest.raises(ValueError, match="search_results must not be empty"):
        build_rag_prompt("question", [])


def test_build_rag_prompt_truncates_long_chunk_content() -> None:
    long_content = "a" * 200
    prompt = build_rag_prompt(
        "question",
        [fake_result(content=long_content)],
        max_chunk_chars=40,
    )

    assert len(prompt.sources[0].content) <= 40
    assert "[truncated]" in prompt.sources[0].content
    assert "[truncated]" in prompt.context_text


def test_build_rag_prompt_limits_total_context_sources() -> None:
    prompt = build_rag_prompt(
        "question",
        [
            fake_result(chunk_id=1, content="a" * 80),
            fake_result(chunk_id=2, content="b" * 80),
            fake_result(chunk_id=3, content="c" * 80),
        ],
        max_context_chars=320,
        max_chunk_chars=80,
    )

    assert len(prompt.sources) < 3


def test_format_source_includes_traceable_metadata() -> None:
    source = build_rag_prompt("question", [fake_result()]).sources[0]
    formatted = format_source(source)

    assert "Title: Rock-filled concrete overview" in formatted
    assert "Source type: metadata_record" in formatted
    assert "Chunk: 10 / index 0" in formatted
    assert "Score: 0.8500" in formatted


def test_format_source_includes_image_caption_when_available() -> None:
    source = build_rag_prompt(
        "question",
        [
            fake_result(
                content="Image description.",
                chunk_type="image_description",
                source_image_path="data/images/1/page2_img3.png",
                caption="Fig. 2 Image caption",
            )
        ],
    ).sources[0]

    assert "Caption: Fig. 2 Image caption" in format_source(source)


def test_truncate_text_keeps_short_text_unchanged() -> None:
    assert truncate_text(" short text ", 20) == "short text"


def fake_result(
    chunk_id: int = 10,
    title: str = "Rock-filled concrete overview",
    content: str = "Rock-filled concrete uses large rockfill and self-compacting concrete.",
    chunk_type: str = "text",
    source_image_path: str | None = None,
    caption: str | None = None,
) -> FakeSearchResult:
    return FakeSearchResult(
        document_id=1,
        document_title=title,
        source_type="metadata_record",
        source_path="https://example.test/source",
        file_name="source.md",
        chunk_id=chunk_id,
        chunk_index=0,
        content=content,
        heading_path="Overview",
        score=0.85,
        chunk_type=chunk_type,
        source_image_path=source_image_path,
        caption=caption,
    )
