from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.generation.vision_model import VisionModelProvider


IMAGE_TO_IMAGE_MIN_SCORE = 0.55
IMAGE_TO_IMAGE_TOP_K = 5
USER_IMAGE_ANALYSIS_PROMPT = (
    "Analyze this user-uploaded engineering image objectively. Describe visible "
    "concrete structure features, cracks, defects, specimen or site context, and "
    "possible RFC/hydraulic concrete relevance. Do not invent information that is "
    "not visible; state uncertainty when needed."
)


@dataclass(frozen=True)
class ImageAnalysisResult:
    image_description: str
    related_text_chunks: list[Any] = field(default_factory=list)
    similar_figures: list[Any] = field(default_factory=list)
    search_results: list[Any] = field(default_factory=list)
    sources: list[Any] = field(default_factory=list)
    fused_context: str = ""

    def to_payload(self) -> dict[str, object]:
        return {
            "image_description": self.image_description,
            "related_text_count": len(self.related_text_chunks),
            "similar_figure_count": len(self.similar_figures),
            "fused_context": self.fused_context,
        }


class UserImageAnalyzer:
    def __init__(
        self,
        *,
        vision_provider: VisionModelProvider,
        knowledge_searcher: Callable[[str, int], Any],
        figure_searcher: Callable[[str, int], Any],
        text_top_k: int = 5,
        figure_top_k: int = IMAGE_TO_IMAGE_TOP_K,
        image_min_score: float = IMAGE_TO_IMAGE_MIN_SCORE,
    ) -> None:
        if text_top_k <= 0:
            raise ValueError("text_top_k must be greater than 0")
        if figure_top_k <= 0:
            raise ValueError("figure_top_k must be greater than 0")
        self.vision_provider = vision_provider
        self.knowledge_searcher = knowledge_searcher
        self.figure_searcher = figure_searcher
        self.text_top_k = text_top_k
        self.figure_top_k = figure_top_k
        self.image_min_score = image_min_score

    def analyze(self, image_path: str | Path, user_question: str) -> ImageAnalysisResult:
        normalized_question = user_question.strip()
        if not normalized_question:
            raise ValueError("user_question must not be empty")

        image_description = self.vision_provider.describe_image(
            image_path,
            prompt=USER_IMAGE_ANALYSIS_PROMPT,
        ).strip()
        if not image_description:
            raise RuntimeError("vision model returned an empty image description")

        retrieval_query = build_image_retrieval_query(
            image_description=image_description,
            user_question=normalized_question,
        )
        text_result = self.knowledge_searcher(retrieval_query, self.text_top_k)
        figure_result = self.figure_searcher(retrieval_query, self.figure_top_k)

        related_text_chunks = list(getattr(text_result, "search_results", []) or [])
        similar_figures = [
            figure
            for figure in list(getattr(figure_result, "figure_results", []) or [])
            if getattr(figure, "relevance_score", 0.0) >= self.image_min_score
        ]
        figure_chunk_ids = {getattr(figure, "chunk_id", None) for figure in similar_figures}
        figure_items = [
            item
            for item in list(getattr(figure_result, "search_results", []) or [])
            if not figure_chunk_ids or getattr(item, "chunk_id", None) in figure_chunk_ids
        ]
        sources = [
            *list(getattr(text_result, "sources", []) or []),
            *[
                source
                for source in list(getattr(figure_result, "sources", []) or [])
                if not figure_chunk_ids or getattr(source, "chunk_id", None) in figure_chunk_ids
            ],
        ]
        fused_context = build_fused_context(
            image_description=image_description,
            related_text_chunks=related_text_chunks,
            similar_figures=similar_figures,
        )
        return ImageAnalysisResult(
            image_description=image_description,
            related_text_chunks=related_text_chunks,
            similar_figures=similar_figures,
            search_results=[*related_text_chunks, *figure_items],
            sources=sources,
            fused_context=fused_context,
        )


def build_image_retrieval_query(*, image_description: str, user_question: str) -> str:
    return f"{user_question.strip()}\n\nUser-uploaded image description: {image_description.strip()}"


def build_fused_context(
    *,
    image_description: str,
    related_text_chunks: list[Any],
    similar_figures: list[Any],
) -> str:
    lines = ["User-uploaded image analysis:", image_description.strip()]
    if related_text_chunks:
        lines.append("\nRelated text evidence:")
        for index, item in enumerate(related_text_chunks, start=1):
            title = getattr(item, "document_title", "unknown")
            content = truncate_for_context(getattr(item, "content", ""))
            lines.append(f"[T{index}] {title}: {content}")
    if similar_figures:
        lines.append("\nSimilar corpus figures:")
        for index, figure in enumerate(similar_figures, start=1):
            title = getattr(figure, "document_title", "unknown")
            page = getattr(figure, "page_number", None)
            caption = getattr(figure, "caption", None) or "untitled"
            snippet = truncate_for_context(getattr(figure, "description_snippet", ""))
            page_text = f", page={page}" if page is not None else ""
            lines.append(f"[F{index}] {title}{page_text}: {caption}; {snippet}")
    if not related_text_chunks and not similar_figures:
        lines.append("\nNo related text evidence or similar corpus figures were found.")
    return "\n".join(lines)


def truncate_for_context(text: str, limit: int = 240) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."
