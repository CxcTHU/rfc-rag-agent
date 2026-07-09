from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any


UNIT_PATTERN = re.compile(
    r"(kg/m(?:3|³)|g/cm(?:3|³)|m3|m³|cm3|cm³|mpa|kpa|pa|kn|n|mm|cm|m|%|℃|°c|t|kg|g)",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"[-+]?(?:\d+(?:,\d{3})*|\d+)(?:\.\d+)?")
SEPARATOR_PATTERN = re.compile(r"^\s*:?-{2,}:?\s*$")


def normalize_cell_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\r", "\n").split())


def normalize_lookup_text(value: str) -> str:
    return " ".join(value.lower().replace("：", ":").split())


def normalize_rows(rows: Sequence[Sequence[Any]]) -> tuple[tuple[str, ...], ...]:
    normalized: list[tuple[str, ...]] = []
    for row in rows:
        cells = tuple(normalize_cell_text(cell) for cell in row)
        if any(cells):
            normalized.append(cells)
    if not normalized:
        return ()
    width = max(len(row) for row in normalized)
    return tuple(row + ("",) * (width - len(row)) for row in normalized)


def headers_from_rows(rows: Sequence[Sequence[str]]) -> tuple[str, ...]:
    if not rows:
        return ()
    first = list(rows[0])
    headers: list[str] = []
    for index, value in enumerate(first):
        normalized = normalize_cell_text(value)
        headers.append(normalized if normalized else f"列{index + 1}")
    return tuple(headers)


def units_from_headers(headers: Sequence[str]) -> dict[str, str]:
    units: dict[str, str] = {}
    for index, header in enumerate(headers):
        unit = extract_unit(header)
        if unit:
            units[str(index)] = unit
    return units


def extract_unit(text: str) -> str | None:
    match = UNIT_PATTERN.search(text or "")
    if not match:
        return None
    return canonical_unit(match.group(1))


def canonical_unit(value: str) -> str:
    normalized = value.strip().lower().replace("³", "3").replace("°c", "℃")
    aliases = {
        "kg/m3": "kg/m3",
        "g/cm3": "g/cm3",
        "m3": "m3",
        "cm3": "cm3",
        "mpa": "MPa",
        "kpa": "kPa",
        "pa": "Pa",
        "kn": "kN",
        "n": "N",
        "℃": "℃",
    }
    return aliases.get(normalized, normalized)


def parse_numbers(text: str) -> tuple[float, ...]:
    numbers: list[float] = []
    for match in NUMBER_PATTERN.finditer(text or ""):
        try:
            numbers.append(float(match.group(0).replace(",", "")))
        except ValueError:
            continue
    return tuple(numbers)


def first_numeric_value(text: str) -> float | None:
    numbers = parse_numbers(text)
    return numbers[0] if numbers else None


def parse_units(text: str) -> tuple[str, ...]:
    seen: list[str] = []
    for match in UNIT_PATTERN.finditer(text or ""):
        unit = canonical_unit(match.group(1))
        if unit not in seen:
            seen.append(unit)
    return tuple(seen)


def quality_score(rows: Sequence[Sequence[str]]) -> float:
    if not rows:
        return 0.0
    width = max((len(row) for row in rows), default=0)
    if width <= 1:
        return 0.0
    cell_count = len(rows) * width
    nonempty = sum(1 for row in rows for cell in row if cell.strip())
    row_coverage = sum(1 for row in rows if sum(1 for cell in row if cell.strip()) >= 2) / len(rows)
    density = nonempty / cell_count if cell_count else 0.0
    header_bonus = 0.15 if any(cell.strip() for cell in rows[0]) else 0.0
    return round(min(1.0, density * 0.55 + row_coverage * 0.30 + header_bonus), 4)


def structure_hash(rows: Sequence[Sequence[str]], headers: Sequence[str]) -> str:
    payload = {
        "headers": list(headers),
        "rows": [list(row) for row in rows],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_preview(text: str, limit: int = 120) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def parse_markdown_table(markdown: str) -> tuple[tuple[str, ...], ...]:
    rows: list[tuple[str, ...]] = []
    for raw_line in (markdown or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or "|" not in line[1:]:
            continue
        cells = split_markdown_row(line)
        if cells and all(SEPARATOR_PATTERN.match(cell) for cell in cells):
            continue
        if cells:
            rows.append(tuple(normalize_cell_text(cell) for cell in cells))
    return normalize_rows(rows)


def split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).strip())
    return cells
