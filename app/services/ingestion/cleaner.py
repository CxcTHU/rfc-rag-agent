import re


def clean_text(text: str) -> str:
    cleaned = remove_surrogate_codepoints(text)
    cleaned = cleaned.replace("\ufeff", "").replace("\u0000", "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    lines = [normalize_line(line) for line in cleaned.split("\n")]
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def normalize_line(line: str) -> str:
    line = line.replace("\t", " ")
    line = re.sub(r" {2,}", " ", line)
    return line.strip()


def remove_surrogate_codepoints(text: str) -> str:
    """Drop invalid lone surrogate codepoints emitted by some PDF extractors."""

    return "".join(char for char in text if not 0xD800 <= ord(char) <= 0xDFFF)
