"""统一全文导入器的纯函数测试（不联网、不写库）。"""

from pathlib import Path

from scripts.import_papers_corpus import (
    classify_topic,
    clean_title,
    collect_files,
    is_pdf,
)


def test_clean_title_strips_author_and_dup_marker() -> None:
    assert clean_title("堆石混凝土填充性能研究_张三 (1)") == "堆石混凝土填充性能研究"
    assert clean_title("Rock-Filled Concrete Review_Jin") == "Rock-Filled Concrete Review"
    assert clean_title("no_suffix_change (2)") == "no_suffix"  # 去重复标记 + 去末段


def test_classify_topic() -> None:
    assert classify_topic("堆石混凝土抗压强度.pdf") == "rfc_core"
    assert classify_topic("self-compacting rock-filled concrete.pdf") == "rfc_core"
    assert classify_topic("某面板坝施工组织设计.pdf") == "dam_engineering"


def test_is_pdf_detects_header(tmp_path) -> None:
    real = tmp_path / "a.pdf"
    real.write_bytes(b"%PDF-1.7\n...")
    fake = tmp_path / "b.caj"
    fake.write_bytes(b"HN\x00\x00rest")
    assert is_pdf(real) is True
    assert is_pdf(fake) is False
    assert is_pdf(tmp_path / "missing.pdf") is False


def test_collect_files_multiple_globs(tmp_path) -> None:
    (tmp_path / "x.pdf").write_bytes(b"%PDF")
    (tmp_path / "y.caj").write_bytes(b"HN")
    (tmp_path / "z.txt").write_text("ignore", encoding="utf-8")
    found = {p.name for p in collect_files(tmp_path, "*.pdf,*.caj")}
    assert found == {"x.pdf", "y.caj"}
