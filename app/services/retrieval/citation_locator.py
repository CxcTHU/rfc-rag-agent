from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document


@dataclass(frozen=True)
class CitationLocation:
    chunk_id: int
    document_id: int
    document_title: str
    file_name: str
    page_number: int | None
    bboxes: list[dict[str, float]] | None
    confidence: str
    pdf_url: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class CitationLocator:
    """Build frontend-friendly citation locations from stored chunk geometry."""

    def locate(self, chunk_id: int, db: Session) -> CitationLocation | None:
        locations = self.locate_batch([chunk_id], db)
        return locations.get(chunk_id)

    def locate_batch(
        self,
        chunk_ids: list[int],
        db: Session,
    ) -> dict[int, CitationLocation]:
        normalized_ids = sorted({int(chunk_id) for chunk_id in chunk_ids if chunk_id})
        if not normalized_ids:
            return {}

        statement = (
            select(Chunk, Document)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.id.in_(normalized_ids))
        )
        rows = db.execute(statement).all()
        return {
            chunk.id: location_from_chunk_document(chunk, document)
            for chunk, document in rows
        }


def location_from_chunk_document(chunk: Chunk, document: Document) -> CitationLocation:
    parsed = parse_content_bbox_json(chunk.content_bbox_json)
    page_number = parsed.page_number if parsed.page_number is not None else chunk.page_number
    return CitationLocation(
        chunk_id=chunk.id,
        document_id=document.id,
        document_title=document.title,
        file_name=document.file_name,
        page_number=page_number,
        bboxes=parsed.bboxes,
        confidence=parsed.confidence,
        pdf_url=pdf_url_from_document(document),
    )


@dataclass(frozen=True)
class ParsedBboxPayload:
    page_number: int | None
    bboxes: list[dict[str, float]] | None
    confidence: str


def parse_content_bbox_json(content_bbox_json: str | None) -> ParsedBboxPayload:
    if not content_bbox_json:
        return ParsedBboxPayload(page_number=None, bboxes=None, confidence="none")
    try:
        payload: Any = json.loads(content_bbox_json)
    except json.JSONDecodeError:
        return ParsedBboxPayload(page_number=None, bboxes=None, confidence="none")
    if not isinstance(payload, dict):
        return ParsedBboxPayload(page_number=None, bboxes=None, confidence="none")

    page_number = optional_int(payload.get("page"))
    confidence = payload.get("confidence")
    if confidence not in {"exact", "partial", "page_only"}:
        confidence = "none"
    raw_bboxes = payload.get("bboxes")
    bboxes = normalize_bboxes(raw_bboxes)
    if confidence == "page_only" and not bboxes:
        bboxes = None
    return ParsedBboxPayload(
        page_number=page_number,
        bboxes=bboxes,
        confidence=str(confidence),
    )


def optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def normalize_bboxes(value: object) -> list[dict[str, float]] | None:
    if not isinstance(value, list):
        return None
    normalized: list[dict[str, float]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        bbox: dict[str, float] = {}
        for key in ("x0", "y0", "x1", "y1"):
            raw = item.get(key)
            if not isinstance(raw, int | float):
                bbox = {}
                break
            bbox[key] = float(raw)
        if bbox:
            normalized.append(bbox)
    return normalized or None


def pdf_url_from_document(document: Document) -> str | None:
    if document.file_extension.casefold() != ".pdf":
        return None
    raw_path = (document.raw_path or "").replace("\\", "/").lstrip("/")
    if raw_path.startswith("data/raw/"):
        return f"/assets/raw/{raw_path[len('data/raw/'):]}"
    if raw_path.startswith("data/fulltext/"):
        return f"/assets/fulltext/{raw_path[len('data/fulltext/'):]}"
    file_name = Path(document.file_name or "").name
    return f"/assets/raw/{file_name}" if file_name else None
