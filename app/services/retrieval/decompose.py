import re
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.generation.prompt_builder import SearchResultLike
from app.services.retrieval.embedding import EmbeddingProvider
from app.services.retrieval.hybrid_search import HybridSearchService
from app.services.retrieval.keyword_search import (
    KeywordSearchService,
    capped_count,
    expand_query_terms,
    normalize_text,
    source_type_rank,
)
from app.services.retrieval.vector_search import VectorSearchService


MAX_SUB_QUERIES = 3
MIN_TOPICS_FOR_DECOMPOSE = 2
CONJUNCTION_RE = re.compile(r"(、|，|,|和|与|以及|\band\b|\bor\b)", re.IGNORECASE)


@dataclass(frozen=True)
class DecomposedQuery:
    original_question: str
    sub_queries: tuple[str, ...]
    decomposed: bool
    reason: str


@dataclass(frozen=True)
class SubQueryRetrievalResult:
    sub_query: str
    retrieval_mode: str
    results: list[SearchResultLike]


@dataclass(frozen=True)
class MergedEvidence(SearchResultLike):
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    score: float
    sub_queries: tuple[str, ...]
    keyword_score: float
    vector_score: float
    topic_score: float
    source_type_score: float
    both_match: bool
    final_score: float
    explanation: str
    chunk_type: str = "text"
    source_image_path: str | None = None
    caption: str | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class DecomposeRetrievalOutcome:
    decomposed_query: DecomposedQuery
    sub_query_results: list[SubQueryRetrievalResult]
    merged_results: list[MergedEvidence]


@dataclass(frozen=True)
class TopicRule:
    name: str
    sub_query: str
    triggers: tuple[str, ...]


TOPIC_RULES: tuple[TopicRule, ...] = (
    TopicRule("cost", "RFC dam construction cost evaluation", ("成本", "cost")),
    TopicRule("schedule", "RFC dam construction schedule evaluation", ("工期", "schedule")),
    TopicRule("emission", "RFC dam construction emission life-cycle assessment", ("碳排放", "排放", "emission", "life-cycle", "life cycle")),
    TopicRule("filling", "rock-filled concrete filling performance", ("灌满", "灌实", "填充", "充填", "filling")),
    TopicRule("compactness", "rock-filled concrete compactness compaction detection", ("密实度", "compactness", "compaction detection")),
    TopicRule("porosity", "rock-filled concrete porosity void defects", ("孔隙率", "孔洞", "孔隙", "porosity", "void", "pores")),
    TopicRule("compression", "rock-filled concrete compressive behavior strength", ("抗压", "compressive", "compression", "strength")),
    TopicRule("freeze_thaw", "rock-filled concrete freeze-thaw resistance", ("冻融", "抗冻", "freeze-thaw", "freeze thaw")),
    TopicRule("impermeability", "rock-filled concrete impermeability durability", ("抗渗", "impermeability", "durability")),
    TopicRule("creep", "rock-filled concrete creep long-term deformation", ("徐变", "长期变形", "creep", "long-term deformation")),
    TopicRule("itz", "rock and SCC interface ITZ", ("界面", "接触界面", "itz", "interface", "interfacial transition zone")),
    TopicRule("shear", "rock-filled concrete cold joint shear performance", ("冷缝", "剪切", "shear", "cold joint")),
)


class DecomposeRetrievalService:
    def __init__(self, db: Session, embedding_provider: EmbeddingProvider) -> None:
        self.db = db
        self.embedding_provider = embedding_provider

    def retrieve(
        self,
        question: str,
        retrieval_mode: str = "hybrid",
        top_k: int = 5,
    ) -> DecomposeRetrievalOutcome:
        decomposed_query = decompose_query(question)
        sub_query_results = [
            SubQueryRetrievalResult(
                sub_query=sub_query,
                retrieval_mode=retrieval_mode,
                results=self._retrieve_single(sub_query, retrieval_mode, top_k=max(top_k * 2, top_k)),
            )
            for sub_query in decomposed_query.sub_queries
        ]
        merged_results = merge_sub_query_results(question, sub_query_results)[:top_k]
        return DecomposeRetrievalOutcome(
            decomposed_query=decomposed_query,
            sub_query_results=sub_query_results,
            merged_results=merged_results,
        )

    def _retrieve_single(
        self,
        query: str,
        retrieval_mode: str,
        top_k: int,
    ) -> list[SearchResultLike]:
        if retrieval_mode == "keyword":
            return list(KeywordSearchService(self.db).search(query, top_k=top_k))
        if retrieval_mode == "vector":
            return list(VectorSearchService(self.db, self.embedding_provider).search(query, top_k=top_k))
        if retrieval_mode == "hybrid":
            return list(HybridSearchService(self.db, self.embedding_provider).search(query, top_k=top_k))
        raise ValueError(f"Unsupported retrieval mode for decompose: {retrieval_mode}")


def decompose_query(question: str, max_sub_queries: int = MAX_SUB_QUERIES) -> DecomposedQuery:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")
    if max_sub_queries <= 0:
        raise ValueError("max_sub_queries must be greater than 0")

    matched_rules = match_topic_rules(normalized_question)
    if len(matched_rules) < MIN_TOPICS_FOR_DECOMPOSE:
        return DecomposedQuery(
            original_question=normalized_question,
            sub_queries=(normalized_question,),
            decomposed=False,
            reason="single topic or unsupported structure",
        )
    if not should_decompose(normalized_question, matched_rules):
        return DecomposedQuery(
            original_question=normalized_question,
            sub_queries=(normalized_question,),
            decomposed=False,
            reason="no explicit conjunction or fixed multi-topic pattern",
        )

    sub_queries = tuple(rule.sub_query for rule in matched_rules[:max_sub_queries])
    return DecomposedQuery(
        original_question=normalized_question,
        sub_queries=sub_queries,
        decomposed=True,
        reason=f"matched topics: {', '.join(rule.name for rule in matched_rules[:max_sub_queries])}",
    )


def match_topic_rules(question: str) -> list[TopicRule]:
    normalized = normalize_text(question)
    matched: list[TopicRule] = []
    for rule in TOPIC_RULES:
        if any(normalize_text(trigger) in normalized for trigger in rule.triggers):
            matched.append(rule)
    return matched


def should_decompose(question: str, matched_rules: Sequence[TopicRule]) -> bool:
    normalized = normalize_text(question)
    if len(matched_rules) < MIN_TOPICS_FOR_DECOMPOSE:
        return False
    if CONJUNCTION_RE.search(normalized):
        return True
    fixed_multi_topic_markers = [
        ("成本", "工期", "碳排放"),
        ("cost", "schedule", "emission"),
        ("孔隙率", "抗压"),
        ("porosity", "compressive"),
        ("灌满", "密实度"),
        ("filling", "compactness"),
    ]
    return any(all(marker in normalized for marker in markers) for markers in fixed_multi_topic_markers)


def merge_sub_query_results(
    original_question: str,
    sub_query_results: Sequence[SubQueryRetrievalResult],
) -> list[MergedEvidence]:
    candidates: dict[int, list[tuple[str, SearchResultLike]]] = {}
    for sub_query_result in sub_query_results:
        for result in sub_query_result.results:
            candidates.setdefault(result.chunk_id, []).append((sub_query_result.sub_query, result))

    max_score = max(
        (result.score for entries in candidates.values() for _, result in entries),
        default=0.0,
    )
    merged = [
        build_merged_evidence(original_question, entries, max_score)
        for entries in candidates.values()
    ]
    return sorted(
        merged,
        key=lambda item: (
            -item.final_score,
            source_type_rank(item.source_type),
            item.document_id,
            item.chunk_index,
        ),
    )


def build_merged_evidence(
    original_question: str,
    entries: Sequence[tuple[str, SearchResultLike]],
    max_score: float,
) -> MergedEvidence:
    sub_queries = tuple(dict.fromkeys(sub_query for sub_query, _ in entries))
    representative = max((result for _, result in entries), key=lambda item: item.score)
    keyword_score = max((getattr(result, "keyword_score", 0.0) for _, result in entries), default=0.0)
    vector_score = max((getattr(result, "vector_score", 0.0) for _, result in entries), default=0.0)
    both_match = any(
        getattr(result, "keyword_score", 0.0) > 0 and getattr(result, "vector_score", 0.0) > 0
        for _, result in entries
    )
    topic_score, matched_terms = topic_match_score([original_question, *sub_queries], representative)
    normalized_score = normalize_candidate_score(representative.score, max_score)
    source_type_score = source_type_bonus(representative.source_type)
    coverage_bonus = min(0.20, max(0, len(sub_queries) - 1) * 0.05)
    both_match_bonus = 0.15 if both_match else 0.0
    final_score = normalized_score + topic_score + source_type_score + coverage_bonus + both_match_bonus
    explanation = (
        f"sub_queries={len(sub_queries)}; topic_terms={','.join(matched_terms) or 'none'}; "
        f"both_match={both_match}; source_type={representative.source_type}; "
        f"raw_score={representative.score:.4f}; final_score={final_score:.4f}"
    )
    return MergedEvidence(
        document_id=representative.document_id,
        document_title=representative.document_title,
        source_type=representative.source_type,
        source_path=representative.source_path,
        file_name=representative.file_name,
        chunk_id=representative.chunk_id,
        chunk_index=representative.chunk_index,
        content=representative.content,
        heading_path=representative.heading_path,
        score=final_score,
        sub_queries=sub_queries,
        keyword_score=keyword_score,
        vector_score=vector_score,
        topic_score=topic_score,
        source_type_score=source_type_score,
        both_match=both_match,
        final_score=final_score,
        explanation=explanation,
        chunk_type=getattr(representative, "chunk_type", "text"),
        source_image_path=getattr(representative, "source_image_path", None),
        caption=getattr(representative, "caption", None),
        page_number=getattr(representative, "page_number", None),
    )


def topic_match_score(queries: Sequence[str], result: SearchResultLike) -> tuple[float, tuple[str, ...]]:
    terms = []
    for query in queries:
        terms.extend(term for term in expand_query_terms(query) if term.specific)
    normalized_text = " ".join(
        [
            normalize_text(result.document_title),
            normalize_text(result.heading_path),
            normalize_text(result.content),
        ]
    )
    matched_terms: list[str] = []
    raw_score = 0.0
    for term in terms:
        normalized_term = normalize_text(term.text)
        if not normalized_term or normalized_term in matched_terms:
            continue
        hit_count = capped_count(normalized_text, normalized_term)
        if hit_count <= 0:
            continue
        matched_terms.append(normalized_term)
        raw_score += min(2, hit_count) * term.weight
    if raw_score <= 0:
        return 0.0, ()
    return min(0.35, raw_score / 20.0), tuple(matched_terms[:8])


def normalize_candidate_score(score: float, max_score: float) -> float:
    if score <= 0 or max_score <= 0:
        return 0.0
    return min(1.0, score / max_score)


def source_type_bonus(source_type: str) -> float:
    rank = source_type_rank(source_type)
    if rank == 0:
        return 0.12
    if rank in {1, 2}:
        return 0.08
    if rank == 3:
        return 0.02
    return 0.0
