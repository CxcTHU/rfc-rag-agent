from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal


EntityType = Literal[
    "Standard",
    "Material",
    "Parameter",
    "Value",
    "Organization",
    "Method",
]
RelationType = Literal[
    "standard_defines",
    "standard_references",
    "material_has_property",
    "parameter_range",
    "applies_to",
]

ALLOWED_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "Standard",
        "Material",
        "Parameter",
        "Value",
        "Organization",
        "Method",
    }
)
ALLOWED_RELATION_TYPES: frozenset[str] = frozenset(
    {
        "standard_defines",
        "standard_references",
        "material_has_property",
        "parameter_range",
        "applies_to",
    }
)

_SPACE_RE = re.compile(r"\s+")


def normalize_entity_name(name: str) -> str:
    normalized = _SPACE_RE.sub(" ", name.strip())
    return normalized.casefold()


@dataclass(frozen=True)
class GraphEntity:
    name: str
    type: EntityType
    normalized_name: str = ""
    mentions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        cleaned_name = _SPACE_RE.sub(" ", self.name.strip())
        if not cleaned_name:
            raise ValueError("entity name must not be empty")
        if self.type not in ALLOWED_ENTITY_TYPES:
            raise ValueError(f"unsupported entity type: {self.type}")
        normalized = self.normalized_name.strip() or normalize_entity_name(cleaned_name)
        mentions = tuple(
            dict.fromkeys(
                _SPACE_RE.sub(" ", mention.strip())
                for mention in (self.mentions or (cleaned_name,))
                if mention and mention.strip()
            )
        )
        object.__setattr__(self, "name", cleaned_name)
        object.__setattr__(self, "normalized_name", normalized)
        object.__setattr__(self, "mentions", mentions or (cleaned_name,))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "normalized_name": self.normalized_name,
            "mentions": list(self.mentions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphEntity":
        return cls(
            name=str(data.get("name") or ""),
            type=str(data.get("type") or ""),  # type: ignore[arg-type]
            normalized_name=str(data.get("normalized_name") or ""),
            mentions=tuple(str(item) for item in data.get("mentions") or ()),
        )


@dataclass(frozen=True)
class GraphRelation:
    subject: str
    predicate: RelationType
    object: str
    source_chunk_id: int | str | None = None
    evidence: str = ""

    def __post_init__(self) -> None:
        subject = _SPACE_RE.sub(" ", self.subject.strip())
        object_name = _SPACE_RE.sub(" ", self.object.strip())
        if not subject:
            raise ValueError("relation subject must not be empty")
        if not object_name:
            raise ValueError("relation object must not be empty")
        if self.predicate not in ALLOWED_RELATION_TYPES:
            raise ValueError(f"unsupported relation type: {self.predicate}")
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "object", object_name)
        object.__setattr__(self, "evidence", _SPACE_RE.sub(" ", self.evidence.strip()))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
        }
        if self.source_chunk_id is not None:
            data["source_chunk_id"] = self.source_chunk_id
        if self.evidence:
            data["evidence"] = self.evidence[:240]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphRelation":
        return cls(
            subject=str(data.get("subject") or ""),
            predicate=str(data.get("predicate") or ""),  # type: ignore[arg-type]
            object=str(data.get("object") or ""),
            source_chunk_id=data.get("source_chunk_id"),
            evidence=str(data.get("evidence") or ""),
        )


@dataclass(frozen=True)
class GraphExtractionResult:
    chunk_id: int | str
    document_id: int | str
    document_title: str
    entities: tuple[GraphEntity, ...] = ()
    relations: tuple[GraphRelation, ...] = ()
    extractor: str = "deterministic"
    status: str = "ok"
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_title": self.document_title[:160],
            "status": self.status,
            "extractor": self.extractor,
            "entities": [entity.to_dict() for entity in self.entities],
            "relations": [relation.to_dict() for relation in self.relations],
        }
        if self.error:
            data["error"] = self.error[:240]
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphExtractionResult":
        return cls(
            chunk_id=data.get("chunk_id") or "",
            document_id=data.get("document_id") or "",
            document_title=str(data.get("document_title") or ""),
            status=str(data.get("status") or "ok"),
            extractor=str(data.get("extractor") or "deterministic"),
            error=str(data.get("error") or ""),
            entities=tuple(
                GraphEntity.from_dict(item)
                for item in data.get("entities") or ()
                if isinstance(item, dict)
            ),
            relations=tuple(
                GraphRelation.from_dict(item)
                for item in data.get("relations") or ()
                if isinstance(item, dict)
            ),
            metadata=dict(data.get("metadata") or {}),
        )


def deduplicate_entities(entities: list[GraphEntity]) -> tuple[GraphEntity, ...]:
    by_key: dict[tuple[str, str], GraphEntity] = {}
    for entity in entities:
        key = (entity.type, entity.normalized_name)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = entity
            continue
        mentions = tuple(dict.fromkeys((*existing.mentions, *entity.mentions)))
        by_key[key] = GraphEntity(
            name=existing.name,
            type=existing.type,
            normalized_name=existing.normalized_name,
            mentions=mentions,
        )
    return tuple(by_key.values())


def deduplicate_relations(relations: list[GraphRelation]) -> tuple[GraphRelation, ...]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[GraphRelation] = []
    for relation in relations:
        key = (
            normalize_entity_name(relation.subject),
            relation.predicate,
            normalize_entity_name(relation.object),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(relation)
    return tuple(deduped)

