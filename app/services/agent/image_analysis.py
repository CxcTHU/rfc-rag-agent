from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.generation.vision_model import VisionModelProvider


IMAGE_TO_IMAGE_MIN_SCORE = 0.55
IMAGE_TO_IMAGE_TOP_K = 5
IMAGE_OUT_OF_SCOPE_REFUSAL = (
    "当前系统只支持堆石混凝土、水工混凝土、坝工、混凝土裂缝、骨料、配合比、"
    "强度试验、表格/曲线/工程图等相关图片分析。上传图片与问题未命中这些领域锚点，"
    "因此不进行相似图片召回。"
)
TEST_VISION_REFUSAL = (
    "当前启用的是 deterministic 测试视觉模型，它不具备真实看图能力。"
    "请配置真实视觉模型后再进行用户图片分析。"
)
USER_IMAGE_ANALYSIS_PROMPT = (
    "请用中文客观分析这张用户上传的工程图片。只输出 3-5 条短要点，"
    "每条不超过 40 个汉字。重点说明：可见的混凝土/堆石/坝工或试验内容、"
    "是否有裂缝缺陷、与堆石混凝土或水工混凝土的关系、无法确认的不确定点。"
    "不要写长篇报告，不要编造图片中不可见的信息。"
)
DOMAIN_ANCHORS = (
    "rock-filled concrete",
    "rock filled concrete",
    "rfc",
    "hydraulic concrete",
    "dam",
    "concrete",
    "crack",
    "aggregate",
    "mix ratio",
    "compressive strength",
    "strength test",
    "stress strain",
    "curve",
    "data table",
    "tabulated",
    "table chart",
    "engineering drawing",
    "堆石混凝土",
    "水工混凝土",
    "坝",
    "坝工",
    "混凝土",
    "裂缝",
    "骨料",
    "配合比",
    "抗压强度",
    "强度试验",
    "应力应变",
    "表格",
    "曲线",
    "工程图",
)
OUT_OF_SCOPE_IMAGE_TERMS = (
    "landscape",
    "mountain",
    "forest",
    "tree",
    "sky",
    "cat",
    "animal",
    "smartphone",
    "phone",
    "mobile phone",
    "\u98ce\u666f",
    "\u5c71",
    "\u6811",
    "\u5929\u7a7a",
    "\u732b",
    "\u52a8\u7269",
    "\u624b\u673a",
    "\u667a\u80fd\u624b\u673a",
)


@dataclass(frozen=True)
class ImageAnalysisResult:
    image_description: str
    domain_relevance: str = "in_scope"
    refusal_reason: str | None = None
    vision_provider: str | None = None
    vision_model: str | None = None
    is_test_vision: bool = False
    related_text_chunks: list[Any] = field(default_factory=list)
    similar_figures: list[Any] = field(default_factory=list)
    search_results: list[Any] = field(default_factory=list)
    sources: list[Any] = field(default_factory=list)
    fused_context: str = ""

    def to_payload(self) -> dict[str, object]:
        return {
            "image_description": self.image_description,
            "domain_relevance": self.domain_relevance,
            "refusal_reason": self.refusal_reason,
            "vision_provider": self.vision_provider,
            "vision_model": self.vision_model,
            "is_test_vision": self.is_test_vision,
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

        provider_name = getattr(self.vision_provider, "provider_name", None)
        model_name = getattr(self.vision_provider, "model_name", None)
        is_test_vision = str(provider_name or "").casefold() in {"deterministic", "fake", "local"}
        if is_test_vision:
            return ImageAnalysisResult(
                image_description=image_description,
                domain_relevance="test_vision",
                refusal_reason=TEST_VISION_REFUSAL,
                vision_provider=provider_name,
                vision_model=model_name,
                is_test_vision=True,
                fused_context=TEST_VISION_REFUSAL,
            )

        relevance = assess_image_domain_relevance(image_description, normalized_question)
        if relevance != "in_scope":
            return ImageAnalysisResult(
                image_description=image_description,
                domain_relevance=relevance,
                refusal_reason=IMAGE_OUT_OF_SCOPE_REFUSAL,
                vision_provider=provider_name,
                vision_model=model_name,
                is_test_vision=False,
                fused_context=IMAGE_OUT_OF_SCOPE_REFUSAL,
            )

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
            domain_relevance=relevance,
            vision_provider=provider_name,
            vision_model=model_name,
            is_test_vision=False,
            related_text_chunks=related_text_chunks,
            similar_figures=similar_figures,
            search_results=[*related_text_chunks, *figure_items],
            sources=sources,
            fused_context=fused_context,
        )


def assess_image_domain_relevance(image_description: str, question: str) -> str:
    description_haystack = image_description.casefold()
    question_haystack = question.casefold()
    if any(term.casefold() in description_haystack for term in OUT_OF_SCOPE_IMAGE_TERMS):
        return "out_of_scope"
    if any(anchor.casefold() in description_haystack for anchor in DOMAIN_ANCHORS):
        return "in_scope"
    haystack = f"{description_haystack}\n{question_haystack}"
    if any(anchor.casefold() in haystack for anchor in DOMAIN_ANCHORS):
        return "in_scope"
    uncertainty_terms = (
        "uncertain",
        "cannot determine",
        "not enough information",
        "无法判断",
        "不能判断",
        "不确定",
    )
    if any(term in haystack for term in uncertainty_terms):
        return "uncertain"
    return "out_of_scope"


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


def build_concise_image_answer(
    *,
    image_description: str,
    related_text_chunks: list[Any],
    similar_figures: list[Any],
    max_points: int = 4,
    max_chars: int = 520,
) -> str:
    points = extract_image_description_points(image_description, max_points=max_points)
    lines = ["图片分析要点："]
    for point in points:
        lines.append(f"- {point}")
    if related_text_chunks or similar_figures:
        lines.append(
            f"- 已结合知识库检索到 {len(related_text_chunks)} 条文本证据、"
            f"{len(similar_figures)} 张相似图，可在来源中进一步核对。"
        )
    answer = "\n".join(lines)
    if len(answer) <= max_chars:
        return answer
    return answer[: max_chars - 3].rstrip() + "..."


def extract_image_description_points(description: str, *, max_points: int) -> list[str]:
    points: list[str] = []
    for raw_line in description.splitlines():
        line = clean_image_description_line(raw_line)
        if not line:
            continue
        if is_low_value_image_heading(line):
            continue
        points.append(truncate_for_context(line, limit=110))
        if len(points) >= max_points:
            return points

    fallback = " ".join(description.split())
    for separator in ("。", "；", ";", ". "):
        if separator in fallback:
            for part in fallback.split(separator):
                line = clean_image_description_line(part)
                if line:
                    points.append(truncate_for_context(line, limit=110))
                if len(points) >= max_points:
                    return points
            break
    if not points and fallback:
        points.append(truncate_for_context(fallback, limit=110))
    return points[:max_points]


def clean_image_description_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = cleaned.lstrip("#").strip()
    cleaned = cleaned.lstrip("-*• ").strip()
    while cleaned and cleaned[0].isdigit():
        cleaned = cleaned[1:].lstrip(".、) ").strip()
    cleaned = cleaned.replace("**", "").replace("__", "").strip()
    return cleaned


def is_low_value_image_heading(line: str) -> bool:
    normalized = line.casefold().strip(":： ")
    return normalized in {
        "objective analysis of the image",
        "visible concrete structure features",
        "cracks, defects, or imperfections",
        "contextual/engineering observations",
        "relevance to rfc (roller-compacted concrete) or hydraulic concrete",
        "uncertainty",
    }


def truncate_for_context(text: str, limit: int = 240) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."
