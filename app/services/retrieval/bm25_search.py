import math
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.services.retrieval.keyword_search import (
    SearchTerm,
    SYNONYM_RULES,
    capped_count,
    expand_query_terms,
    normalize_text,
    source_type_rank,
)


TITLE_WEIGHT = 3.0
HEADING_WEIGHT = 1.6
CONTENT_WEIGHT = 1.0
DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


@dataclass(frozen=True)
class BM25SearchResult:
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
    matched_terms: tuple[str, ...]
    title_score: float
    heading_score: float
    content_score: float
    chunk_type: str = "text"
    source_image_path: str | None = None
    caption: str | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class _BM25Document:
    chunk: Chunk
    document: Document
    title: str
    heading: str
    content: str
    length: int


class BM25SearchService:
    def __init__(self, db: Session, k1: float = DEFAULT_K1, b: float = DEFAULT_B) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be greater than 0")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")
        self.db = db
        self.k1 = k1
        self.b = b

    def search(self, query: str, top_k: int = 5) -> list[BM25SearchResult]:
        terms = expand_bm25_query_terms(query)
        if not terms:
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        corpus = self._list_documents()
        if not corpus:
            return []

        avg_length = sum(item.length for item in corpus) / len(corpus)
        document_frequency = {
            term.text: count_documents_with_term(term, corpus)
            for term in terms
        }
        results = [
            result
            for item in corpus
            if (result := score_document(item, terms, document_frequency, len(corpus), avg_length, self.k1, self.b))
            is not None
        ]
        sorted_results = sorted(
            results,
            key=lambda item: (
                -item.score,
                source_type_rank(item.source_type),
                item.document_id,
                item.chunk_index,
            ),
        )
        return diversify_bm25_results(sorted_results, top_k)

    def _list_documents(self) -> list[_BM25Document]:
        statement = select(Chunk, Document).join(Document, Chunk.document_id == Document.id).order_by(Document.id, Chunk.chunk_index)
        rows = self.db.execute(statement).all()
        return [
            _BM25Document(
                chunk=chunk,
                document=document,
                title=normalize_text(document.title),
                heading=normalize_text(chunk.heading_path),
                content=normalize_text(chunk.content),
                length=max(1, lexical_length(chunk.content)),
            )
            for chunk, document in rows
        ]


def expand_bm25_query_terms(query: str) -> list[SearchTerm]:
    expanded = {term.text: term for term in expand_query_terms(query)}
    normalized_query = normalize_text(query)
    for triggers, _additions in SYNONYM_RULES:
        for trigger in triggers:
            normalized_trigger = normalize_text(trigger)
            if normalized_trigger and normalized_trigger in normalized_query:
                existing = expanded.get(normalized_trigger)
                candidate = SearchTerm(text=normalized_trigger, weight=1.6, specific=True)
                if existing is None or candidate.weight > existing.weight:
                    expanded[normalized_trigger] = candidate
    return list(expanded.values())


def score_document(
    item: _BM25Document,
    terms: list[SearchTerm],
    document_frequency: dict[str, int],
    corpus_size: int,
    avg_length: float,
    k1: float,
    b: float,
) -> BM25SearchResult | None:
    matched_terms: list[str] = []
    title_score = 0.0
    heading_score = 0.0
    content_score = 0.0
    has_specific_terms = any(term.specific for term in terms)
    specific_hit = False

    for term in terms:
        normalized_term = normalize_text(term.text)
        if not normalized_term:
            continue
        df = document_frequency.get(term.text, 0)
        if df <= 0:
            continue
        idf = inverse_document_frequency(corpus_size, df)
        specificity_weight = 1.0 if term.specific else 0.25
        term_weight = term.weight * specificity_weight

        title_hits = capped_count(item.title, normalized_term)
        heading_hits = capped_count(item.heading, normalized_term)
        content_hits = capped_count(item.content, normalized_term)
        if term.specific and (title_hits or heading_hits or content_hits):
            specific_hit = True
        if title_hits or heading_hits or content_hits:
            matched_terms.append(normalized_term)

        title_score += bm25_term_score(title_hits, idf, field_length=lexical_length(item.document.title), avg_length=avg_length, k1=k1, b=0.2) * term_weight * TITLE_WEIGHT
        heading_score += bm25_term_score(title_hits + heading_hits, idf, field_length=lexical_length(item.chunk.heading_path or ""), avg_length=avg_length, k1=k1, b=0.4) * term_weight * HEADING_WEIGHT
        content_score += bm25_term_score(content_hits, idf, field_length=item.length, avg_length=avg_length, k1=k1, b=b) * term_weight * CONTENT_WEIGHT

    if has_specific_terms and not specific_hit:
        return None
    score = title_score + heading_score + content_score
    if score <= 0:
        return None

    return BM25SearchResult(
        document_id=item.document.id,
        document_title=item.document.title,
        source_type=item.document.source_type,
        source_path=item.document.source_path,
        file_name=item.document.file_name,
        chunk_id=item.chunk.id,
        chunk_index=item.chunk.chunk_index,
        content=item.chunk.content,
        heading_path=item.chunk.heading_path,
        score=score,
        matched_terms=tuple(dict.fromkeys(matched_terms)),
        title_score=title_score,
        heading_score=heading_score,
        content_score=content_score,
        chunk_type=item.chunk.chunk_type,
        source_image_path=item.chunk.source_image_path,
        caption=item.chunk.caption,
        page_number=item.chunk.page_number,
    )


def inverse_document_frequency(corpus_size: int, document_frequency: int) -> float:
    return math.log(1 + (corpus_size - document_frequency + 0.5) / (document_frequency + 0.5))


def bm25_term_score(
    term_frequency: int,
    idf: float,
    field_length: int,
    avg_length: float,
    k1: float,
    b: float,
) -> float:
    if term_frequency <= 0:
        return 0.0
    normalized_length = field_length / avg_length if avg_length > 0 else 1.0
    denominator = term_frequency + k1 * (1 - b + b * normalized_length)
    return idf * ((term_frequency * (k1 + 1)) / denominator)


def count_documents_with_term(term: SearchTerm, corpus: list[_BM25Document]) -> int:
    normalized_term = normalize_text(term.text)
    if not normalized_term:
        return 0
    return sum(
        1
        for item in corpus
        if normalized_term in item.title or normalized_term in item.heading or normalized_term in item.content
    )


def lexical_length(text: str | None) -> int:
    normalized = normalize_text(text)
    latin_terms = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", normalized)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    return max(1, len(latin_terms) + len(chinese_chars))


def diversify_bm25_results(
    results: list[BM25SearchResult],
    top_k: int,
) -> list[BM25SearchResult]:
    if len(results) <= top_k:
        return results

    metadata_limit = max(1, int(top_k * 0.6))
    selected: list[BM25SearchResult] = []
    deferred: list[BM25SearchResult] = []
    selected_documents: set[int] = set()
    metadata_count = 0

    for result in results:
        if len(selected) >= top_k:
            deferred.append(result)
            continue
        if result.document_id in selected_documents:
            deferred.append(result)
            continue
        if result.source_type == "metadata_record" and metadata_count >= metadata_limit:
            deferred.append(result)
            continue

        selected.append(result)
        selected_documents.add(result.document_id)
        if result.source_type == "metadata_record":
            metadata_count += 1

    for result in deferred:
        if len(selected) >= top_k:
            break
        selected.append(result)

    return selected
