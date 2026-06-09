"""阶段 18：PDF 文本结构化加固的 deterministic 测试（不依赖真实 PDF）。"""

from app.services.ingestion.pdf_text import (
    dehyphenate,
    detect_heading,
    detect_repeated_header_footer,
    is_noise_line,
    is_table_row,
    render_table_block,
    structure_page_text,
    structure_pdf_pages,
)
from app.services.ingestion.splitter import find_heading_path


def test_dehyphenate_merges_line_break_hyphenation() -> None:
    assert dehyphenate("concre-\nte is strong") == "concrete is strong"
    assert dehyphenate("rock-\nfilled concrete") == "rockfilled concrete"
    # 不合并真正的破折号列表（前为大写句首或非字母）。
    assert dehyphenate("value: -\n10") == "value: -\n10"


def test_detect_heading_numbered_sections() -> None:
    assert detect_heading("1 Introduction") == (1, "1 Introduction")
    assert detect_heading("2.1 Materials and Methods") == (2, "2.1 Materials and Methods")
    assert detect_heading("3.2.1 Mix Design") == (3, "3.2.1 Mix Design")


def test_detect_heading_keywords_and_allcaps() -> None:
    assert detect_heading("Abstract") == (1, "Abstract")
    assert detect_heading("REFERENCES") == (1, "REFERENCES")
    assert detect_heading("Conclusions") == (1, "Conclusions")


def test_detect_heading_chinese_sections() -> None:
    # 中文章节关键词（含被抽取拆开的 "结 论"）。
    assert detect_heading("摘要") == (1, "摘要")
    assert detect_heading("关键词") == (1, "关键词")
    assert detect_heading("结 论") == (1, "结 论")
    assert detect_heading("参考文献") == (1, "参考文献")
    # 中文数字章节标题需带顿号/括号。
    assert detect_heading("一、引言") == (1, "一、引言")
    assert detect_heading("（三）结论") == (1, "（三）结论")


def test_detect_heading_rejects_chinese_prose_and_measurements() -> None:
    # "一是 / 一方面 / 一旦" 是正文，不是章节标题。
    assert detect_heading("一是震中距较小") is None
    assert detect_heading("一方面") is None
    assert detect_heading("一旦建坝蓄水就容易形成大型水库") is None
    # 测量值 / 表格行不是编号标题。
    assert detect_heading("150 m") is None
    assert detect_heading("17 km") is None
    assert detect_heading("9 DA M 0 + 251") is None
    assert detect_heading("1 ITZ 2009 233 660 160") is None
    # 空格拆开的字母碎片不是全大写标题。
    assert detect_heading("D A M") is None
    assert detect_heading("DO I") is None


def test_detect_heading_rejects_sentences() -> None:
    # 以句末标点结尾的“编号行”不是标题，而是正文。
    assert detect_heading("1. This is a normal sentence ending with a period.") is None
    # 普通混合大小写长句不是标题。
    assert detect_heading("Rock-filled concrete uses self-compacting concrete.") is None


def test_is_table_row_and_render() -> None:
    assert is_table_row("Mix    Strength    Modulus") is False  # 无数字
    assert is_table_row("Sample A    30.5    25.1") is True
    assert is_table_row("just normal text here") is False

    block = render_table_block(["Sample A    30.5    25.1", "Sample B    28.0    24.3"])
    assert block.startswith("[表格]")
    assert "Sample A | 30.5 | 25.1" in block
    assert "Sample B | 28.0 | 24.3" in block


def test_is_noise_line_drops_page_numbers_and_symbols() -> None:
    assert is_noise_line("12") is True
    assert is_noise_line("•·—") is True
    assert is_noise_line("Rock-filled concrete") is False
    assert is_noise_line("Table 3 results") is False


def test_detect_repeated_header_footer() -> None:
    footer = "Journal of RFC, Vol. 1"
    pages = [
        f"{footer}\n1 Introduction\nbody text one",
        f"{footer}\n2 Methods\nbody text two",
        f"{footer}\n3 Results\nbody text three",
        f"{footer}\n4 Discussion\nbody text four",
    ]
    repeated = detect_repeated_header_footer(pages)
    assert footer in repeated


def test_structure_page_text_produces_markdown_headings_for_heading_path() -> None:
    raw = (
        "1 Introduction\n"
        "Rock-filled concrete is a mass concrete technology.\n"
        "2 Materials and Methods\n"
        "2.1 Mix Design\n"
        "The self-compacting concrete mix is designed for filling capacity.\n"
    )
    structured = structure_page_text(raw)
    assert "# 1 Introduction" in structured
    assert "## 2.1 Mix Design" in structured or "# 2.1 Mix Design" in structured

    # heading_path 现在能从结构化文本里恢复章节层级。
    position = structured.index("self-compacting concrete mix")
    heading_path = find_heading_path(structured, position)
    assert heading_path is not None
    assert "Mix Design" in heading_path


def test_structure_pdf_pages_keeps_page_markers_and_dehyphenates() -> None:
    pages = [
        "1 Introduction\nThis para is split across con-\ncrete lines.",
        "2 Results\nThe modulus increased.",
    ]
    out = structure_pdf_pages(pages)
    assert "## Page 1" in out
    assert "## Page 2" in out
    assert "concrete lines" in out  # 断词被合并


def test_structure_pdf_pages_handles_empty_and_single_sentence() -> None:
    # 单句普通文本应原样保留（向后兼容旧 PDF 导入）。
    out = structure_pdf_pages(["Rock-filled concrete uses self-compacting concrete."])
    assert "## Page 1" in out
    assert "Rock-filled concrete uses self-compacting concrete." in out
    # 全空页面不产出。
    assert structure_pdf_pages(["", "   "]) == ""
