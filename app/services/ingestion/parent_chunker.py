from __future__ import annotations

from dataclasses import dataclass

from app.services.ingestion.splitter import TextChunk, split_text


@dataclass(frozen=True)
class ParentChildChunkPlan:
    parent: TextChunk
    children: tuple[TextChunk, ...]


def split_parent_child_text(
    text: str,
    *,
    parent_chunk_size: int = 1800,
    parent_chunk_overlap: int = 120,
    child_chunk_size: int = 800,
    child_chunk_overlap: int = 120,
) -> list[ParentChildChunkPlan]:
    """Split text into large parent chunks and smaller child chunks.

    Parent chunks are intended for answer context. Child chunks are intended for
    embedding and retrieval.
    """

    if parent_chunk_size <= child_chunk_size:
        raise ValueError("parent_chunk_size must be greater than child_chunk_size")
    if parent_chunk_overlap < 0:
        raise ValueError("parent_chunk_overlap must be greater than or equal to 0")
    if parent_chunk_overlap >= parent_chunk_size:
        raise ValueError("parent_chunk_overlap must be smaller than parent_chunk_size")

    parents = split_text(
        text,
        chunk_size=parent_chunk_size,
        chunk_overlap=parent_chunk_overlap,
    )
    plans: list[ParentChildChunkPlan] = []
    for parent in parents:
        children = split_text(
            parent.content,
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap,
        )
        if not children:
            children = [parent]
        plans.append(ParentChildChunkPlan(parent=parent, children=tuple(children)))
    return plans


def flatten_child_chunks(plans: list[ParentChildChunkPlan]) -> list[TextChunk]:
    children: list[TextChunk] = []
    for plan in plans:
        children.extend(plan.children)
    return children
