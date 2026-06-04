import re
from dataclasses import dataclass


HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
METADATA_LINE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:\s*.+$")


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    content: str
    char_count: int
    heading_path: str | None
    start_char: int
    end_char: int


def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be greater than or equal to 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    prepared_text = strip_leading_metadata_block(text).strip()
    if not prepared_text:
        return []

    chunks: list[TextChunk] = []
    start = 0
    text_length = len(prepared_text)

    while start < text_length:
        end = choose_chunk_end(prepared_text, start, chunk_size)
        raw_content = prepared_text[start:end]
        leading = len(raw_content) - len(raw_content.lstrip())
        trailing = len(raw_content) - len(raw_content.rstrip())
        content = raw_content.strip()

        if content:
            adjusted_start = start + leading
            adjusted_end = end - trailing
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    content=content,
                    char_count=len(content),
                    heading_path=find_heading_path(prepared_text, adjusted_start),
                    start_char=adjusted_start,
                    end_char=adjusted_end,
                )
            )

        if end >= text_length:
            break

        next_start = choose_next_chunk_start(
            prepared_text,
            current_start=start,
            current_end=end,
            chunk_overlap=chunk_overlap,
        )
        if next_start <= start:
            next_start = end
        start = next_start

    return chunks


def strip_leading_metadata_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines:
        return text

    first_content_index = next(
        (index for index, line in enumerate(lines) if line.strip()),
        None,
    )
    if first_content_index is None:
        return text

    first_line = lines[first_content_index]
    if not is_heading_level(first_line, 1):
        return text

    scan_index = first_content_index + 1
    while scan_index < len(lines) and not lines[scan_index].strip():
        scan_index += 1

    metadata_start = scan_index
    metadata_end = scan_index
    saw_metadata = False
    while metadata_end < len(lines):
        line = lines[metadata_end]
        stripped = line.strip()
        if not stripped:
            metadata_end += 1
            continue
        if HEADING_RE.match(stripped):
            break
        if METADATA_LINE_RE.match(stripped):
            saw_metadata = True
            metadata_end += 1
            continue
        return text

    if not saw_metadata:
        return text

    kept_lines = [
        *lines[: first_content_index + 1],
        "\n",
        *lines[metadata_end:],
    ]
    return "".join(kept_lines)


def choose_chunk_end(text: str, start: int, chunk_size: int) -> int:
    max_end = min(start + chunk_size, len(text))
    if max_end == len(text):
        return max_end

    lower_bound = start + max(chunk_size // 2, 1)
    for separator in ("\n\n", "\n", "。", "；", "."):
        boundary = text.rfind(separator, start, max_end)
        if boundary >= lower_bound:
            return boundary + len(separator)

    return max_end


def choose_next_chunk_start(
    text: str,
    current_start: int,
    current_end: int,
    chunk_overlap: int,
) -> int:
    if chunk_overlap == 0:
        return current_end

    proposed_start = max(current_start, current_end - chunk_overlap)
    if proposed_start <= current_start:
        return current_end

    forward_limit = current_end
    for separator in ("\n\n", "\n", "。", "；", "."):
        boundary = text.find(separator, proposed_start, forward_limit)
        if boundary != -1:
            return skip_whitespace(text, boundary + len(separator))

    backward_limit = current_start + 1
    for separator in ("\n\n", "\n", "。", "；", "."):
        boundary = text.rfind(separator, backward_limit, proposed_start)
        if boundary != -1:
            return skip_whitespace(text, boundary + len(separator))

    return proposed_start


def skip_whitespace(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def is_heading_level(line: str, level: int) -> bool:
    match = HEADING_RE.match(line.strip())
    return bool(match and len(match.group(1)) == level)


def find_heading_path(text: str, position: int) -> str | None:
    stack: list[str] = []
    cursor = 0

    for line in text.splitlines(keepends=True):
        line_start = cursor
        cursor += len(line)
        if line_start > position:
            break

        match = HEADING_RE.match(line.strip())
        if not match:
            continue

        level = len(match.group(1))
        title = match.group(2).strip()
        stack = stack[: level - 1]
        stack.append(title)

    if not stack:
        return None
    return " > ".join(stack)
