from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.services.generation.chat_model import ChatMessage, ChatModelProvider
from app.services.graphrag.schema import (
    ALLOWED_ENTITY_TYPES,
    ALLOWED_RELATION_TYPES,
    GraphEntity,
    GraphExtractionResult,
    GraphRelation,
    deduplicate_entities,
    deduplicate_relations,
)


MAX_EXTRACTION_CHARS = 4500

STANDARD_RE = re.compile(
    r"\b(?:GB/T|GB|DL/T|SL|ASTM|ACI)\s*[-A-Z0-9.]+(?:[-:]\d+)?\b",
    re.IGNORECASE,
)
VALUE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:MPa|mm|cm|m|s|min|h|kg/m3|kg/m\^3|kg/m³|%|℃|°C)\b",
    re.IGNORECASE,
)

TERM_PATTERNS: dict[str, dict[str, tuple[str, ...]]] = {
    "Material": {
        "rock-filled concrete": ("rock-filled concrete", "rock filled concrete", "RFC", "堆石混凝土"),
        "self-compacting concrete": ("self-compacting concrete", "self compacting concrete", "SCC", "自密实混凝土"),
        "cement": ("cement", "水泥"),
        "fly ash": ("fly ash", "粉煤灰"),
        "aggregate": ("aggregate", "coarse aggregate", "骨料", "粗骨料"),
        "admixture": ("admixture", "外加剂"),
    },
    "Parameter": {
        "compressive strength": ("compressive strength", "抗压强度"),
        "slump flow": ("slump flow", "坍落扩展度", "扩展度"),
        "T500": ("T500",),
        "water-binder ratio": ("water-binder ratio", "water binder ratio", "水胶比"),
        "void ratio": ("void ratio", "porosity", "孔隙率"),
        "temperature": ("temperature", "温度"),
        "adiabatic temperature rise": ("adiabatic temperature rise", "绝热温升"),
        "hydration heat": ("hydration heat", "水化热"),
    },
    "Organization": {
        "ACI": ("ACI", "American Concrete Institute"),
        "ASTM": ("ASTM",),
        "Ministry": ("Ministry", "部", "水利部", "住建部"),
    },
    "Method": {
        "mixing": ("mixing", "拌合"),
        "placement": ("placement", "pouring", "浇筑"),
        "compaction": ("compaction", "vibration", "振捣"),
        "curing": ("curing", "养护"),
        "slump-flow test": ("slump-flow test", "slump flow test", "坍落扩展度试验"),
        "L-box test": ("L-box", "L box", "L型箱"),
    },
}


@dataclass
class GraphRAGTripleExtractor:
    chat_model_provider: ChatModelProvider | None = None

    def extract(
        self,
        *,
        chunk_id: int | str,
        document_id: int | str,
        document_title: str,
        text: str,
        execute_llm: bool = False,
    ) -> GraphExtractionResult:
        if execute_llm:
            return self._extract_with_llm(
                chunk_id=chunk_id,
                document_id=document_id,
                document_title=document_title,
                text=text,
            )
        return self._extract_deterministic(
            chunk_id=chunk_id,
            document_id=document_id,
            document_title=document_title,
            text=text,
        )

    def _extract_deterministic(
        self,
        *,
        chunk_id: int | str,
        document_id: int | str,
        document_title: str,
        text: str,
    ) -> GraphExtractionResult:
        entities: list[GraphEntity] = []
        relations: list[GraphRelation] = []

        for standard in find_standards(text):
            entities.append(GraphEntity(name=standard, type="Standard"))
        for value in find_values(text):
            entities.append(GraphEntity(name=value, type="Value"))
        for entity_type, groups in TERM_PATTERNS.items():
            for canonical, mentions in groups.items():
                matched_mentions = find_mentions(text, mentions)
                if matched_mentions:
                    entities.append(
                        GraphEntity(
                            name=canonical,
                            type=entity_type,  # type: ignore[arg-type]
                            mentions=tuple(matched_mentions),
                        )
                    )

        deduped_entities = deduplicate_entities(entities)
        by_type = group_entities_by_type(deduped_entities)
        standards = by_type.get("Standard", [])
        materials = by_type.get("Material", [])
        parameters = by_type.get("Parameter", [])
        values = by_type.get("Value", [])
        methods = by_type.get("Method", [])

        for material in materials:
            for parameter in parameters:
                relations.append(
                    GraphRelation(
                        subject=material.name,
                        predicate="material_has_property",
                        object=parameter.name,
                        source_chunk_id=chunk_id,
                    )
                )
        for parameter in parameters:
            for value in values[:5]:
                relations.append(
                    GraphRelation(
                        subject=parameter.name,
                        predicate="parameter_range",
                        object=value.name,
                        source_chunk_id=chunk_id,
                    )
                )
        for standard in standards:
            for target in (*parameters[:5], *materials[:3]):
                relations.append(
                    GraphRelation(
                        subject=standard.name,
                        predicate="standard_defines",
                        object=target.name,
                        source_chunk_id=chunk_id,
                    )
                )
        for index, standard in enumerate(standards):
            for referenced in standards[index + 1 :]:
                relations.append(
                    GraphRelation(
                        subject=standard.name,
                        predicate="standard_references",
                        object=referenced.name,
                        source_chunk_id=chunk_id,
                    )
                )
        for method in methods:
            for material in materials:
                relations.append(
                    GraphRelation(
                        subject=method.name,
                        predicate="applies_to",
                        object=material.name,
                        source_chunk_id=chunk_id,
                    )
                )

        return GraphExtractionResult(
            chunk_id=chunk_id,
            document_id=document_id,
            document_title=document_title,
            entities=deduped_entities,
            relations=deduplicate_relations(relations),
            extractor="deterministic",
            metadata={"text_char_count": len(text)},
        )

    def _extract_with_llm(
        self,
        *,
        chunk_id: int | str,
        document_id: int | str,
        document_title: str,
        text: str,
    ) -> GraphExtractionResult:
        if self.chat_model_provider is None:
            raise ValueError("chat_model_provider is required when execute_llm=True")
        messages = build_llm_messages(document_title=document_title, text=text)
        result = self.chat_model_provider.generate(messages)
        payload = parse_json_object(result.answer)
        entities, relations = parse_extraction_payload(payload, source_chunk_id=chunk_id)
        return GraphExtractionResult(
            chunk_id=chunk_id,
            document_id=document_id,
            document_title=document_title,
            entities=entities,
            relations=relations,
            extractor=f"llm:{result.provider}:{result.model_name}",
            metadata={"text_char_count": len(text)},
        )


def find_standards(text: str) -> list[str]:
    return unique_preserve_order(match.group(0).strip() for match in STANDARD_RE.finditer(text))


def find_values(text: str) -> list[str]:
    return unique_preserve_order(match.group(0).strip() for match in VALUE_RE.finditer(text))


def find_mentions(text: str, mentions: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for mention in mentions:
        flags = 0 if contains_cjk(mention) else re.IGNORECASE
        pattern = re.escape(mention)
        if mention.isascii() and re.match(r"^[A-Za-z0-9 -]+$", mention):
            pattern = rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])"
        if re.search(pattern, text, flags):
            found.append(mention)
    return unique_preserve_order(found)


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def unique_preserve_order(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = str(value).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(str(value))
    return result


def group_entities_by_type(entities: tuple[GraphEntity, ...]) -> dict[str, list[GraphEntity]]:
    grouped: dict[str, list[GraphEntity]] = {}
    for entity in entities:
        grouped.setdefault(entity.type, []).append(entity)
    return grouped


def build_llm_messages(*, document_title: str, text: str) -> list[ChatMessage]:
    schema_text = (
        "Return one strict JSON object with keys entities and relations. "
        "Entity type must be one of: Standard, Material, Parameter, Value, Organization, Method. "
        "Relation predicate must be one of: standard_defines, standard_references, "
        "material_has_property, parameter_range, applies_to. "
        "Do not include raw source text, hidden reasoning, markdown, or commentary."
    )
    clipped_text = text[:MAX_EXTRACTION_CHARS]
    return [
        ChatMessage(role="system", content="You extract RFC domain knowledge graph triples."),
        ChatMessage(
            role="user",
            content=(
                f"{schema_text}\n\n"
                f"Document title: {document_title[:160]}\n"
                f"Chunk excerpt:\n{clipped_text}"
            ),
        ),
    ]


def parse_json_object(answer: str) -> dict[str, Any]:
    text = answer.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GraphRAG extractor response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("GraphRAG extractor response must be a JSON object")
    return payload


def parse_extraction_payload(
    payload: dict[str, Any],
    *,
    source_chunk_id: int | str,
) -> tuple[tuple[GraphEntity, ...], tuple[GraphRelation, ...]]:
    entities: list[GraphEntity] = []
    relations: list[GraphRelation] = []

    for item in payload.get("entities") or ():
        if not isinstance(item, dict):
            continue
        entity_type = str(item.get("type") or "")
        if entity_type not in ALLOWED_ENTITY_TYPES:
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        mentions = item.get("mentions")
        entities.append(
            GraphEntity(
                name=name,
                type=entity_type,  # type: ignore[arg-type]
                mentions=tuple(str(mention) for mention in mentions or (name,)),
            )
        )

    entity_names = {entity.name for entity in entities}
    for item in payload.get("relations") or ():
        if not isinstance(item, dict):
            continue
        predicate = str(item.get("predicate") or item.get("type") or "")
        if predicate not in ALLOWED_RELATION_TYPES:
            continue
        subject = str(item.get("subject") or "").strip()
        object_name = str(item.get("object") or "").strip()
        if not subject or not object_name:
            continue
        if entity_names and (subject not in entity_names or object_name not in entity_names):
            continue
        relations.append(
            GraphRelation(
                subject=subject,
                predicate=predicate,  # type: ignore[arg-type]
                object=object_name,
                source_chunk_id=source_chunk_id,
                evidence=str(item.get("evidence") or ""),
            )
        )

    return deduplicate_entities(entities), deduplicate_relations(relations)
