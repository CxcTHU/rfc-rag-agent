import pytest

from app.services.ingestion.splitter import split_text


def test_split_text_creates_overlapping_chunks() -> None:
    text = "0123456789" * 10

    chunks = split_text(text, chunk_size=30, chunk_overlap=10)

    assert len(chunks) == 5
    assert chunks[0].content == text[:30]
    assert chunks[1].start_char == 20
    assert chunks[1].content == text[20:50]
    assert all(chunk.char_count <= 30 for chunk in chunks)


def test_split_text_keeps_markdown_heading_path() -> None:
    text = "# 概念\n堆石混凝土由堆石体和自密实混凝土组成。\n\n## 施工\n施工质量控制关注填充密实性。"

    chunks = split_text(text, chunk_size=35, chunk_overlap=5)

    assert chunks[0].heading_path == "概念"
    assert any(chunk.heading_path == "概念 > 施工" for chunk in chunks)


def test_split_text_returns_empty_list_for_blank_text() -> None:
    assert split_text(" \n\n ") == []


def test_split_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        split_text("abc", chunk_size=10, chunk_overlap=10)


def test_split_text_skips_leading_metadata_block() -> None:
    text = (
        "# 堆石混凝土资料卡\n\n"
        "source_id: rfc_seed_test\n"
        "title: 堆石混凝土资料卡\n"
        "url: https://example.com/article\n"
        "copyright_note: 只保存公开摘要转述。\n\n"
        "## 核心定位\n\n"
        "堆石混凝土依靠自密实混凝土填充堆石体空隙。\n\n"
        "## 质量控制\n\n"
        "施工质量控制需要关注填充密实性。"
    )

    chunks = split_text(text, chunk_size=120, chunk_overlap=20)
    joined_content = "\n".join(chunk.content for chunk in chunks)

    assert "source_id:" not in joined_content
    assert "https://example.com/article" not in joined_content
    assert "copyright_note:" not in joined_content
    assert "## 核心定位" in joined_content
    assert "填充密实性" in joined_content


def test_split_text_prefers_clean_start_after_overlap() -> None:
    text = (
        "# 堆石混凝土资料\n\n"
        "## 核心定位\n\n"
        "堆石混凝土通过自密实混凝土填充堆石体空隙，形成整体结构。\n\n"
        "## 质量控制\n\n"
        "质量控制需要关注流动性、抗离析能力和填充密实性。"
    )

    chunks = split_text(text, chunk_size=62, chunk_overlap=18)

    assert len(chunks) >= 2
    assert chunks[1].content.startswith("## 质量控制")
    assert chunks[1].heading_path == "堆石混凝土资料 > 质量控制"
