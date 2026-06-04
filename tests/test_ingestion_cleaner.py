from app.services.ingestion.cleaner import clean_text


def test_clean_text_normalizes_whitespace_and_line_breaks() -> None:
    raw_text = "\ufeff# 标题\r\n\r\n\r\n堆石\t\t混凝土  资料\u0000\r\n  第二行  "

    cleaned = clean_text(raw_text)

    assert "\u0000" not in cleaned
    assert "\r" not in cleaned
    assert "\n\n\n" not in cleaned
    assert cleaned == "# 标题\n\n堆石 混凝土 资料\n第二行"


def test_clean_text_returns_empty_string_for_blank_input() -> None:
    assert clean_text(" \n\t\n ") == ""
