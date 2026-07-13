import math
import re
from dataclasses import dataclass
from threading import RLock
from weakref import WeakKeyDictionary

from sqlalchemy import func, select
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
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    raw_content: str
    heading_path: str | None
    title: str
    heading: str
    content: str
    length: int
    title_length: int
    heading_length: int
    chunk_type: str
    source_image_path: str | None
    caption: str | None
    page_number: int | None


_BM25_CORPUS_CACHE: WeakKeyDictionary[
    object,
    tuple[tuple[object, ...], tuple[_BM25Document, ...]],
] = WeakKeyDictionary()
_BM25_CORPUS_CACHE_LOCK = RLock()


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
            for item in self._candidate_documents(corpus, terms)
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

    @staticmethod
    def _candidate_documents(
        corpus: list[_BM25Document],
        terms: list[SearchTerm],
    ) -> list[_BM25Document]:
        """Discard documents that cannot score before the full BM25 calculation."""
        normalized_terms = tuple(term.text for term in terms if term.text)
        if not normalized_terms:
            return []
        return [
            item
            for item in corpus
            if any(
                term in field
                for term in normalized_terms
                for field in (item.title, item.heading, item.content)
            )
        ]

    def _list_documents(self) -> list[_BM25Document]:
        bind = self.db.get_bind()
        fingerprint = self._corpus_fingerprint()
        with _BM25_CORPUS_CACHE_LOCK:
            cached = _BM25_CORPUS_CACHE.get(bind)
            if cached is not None and cached[0] == fingerprint:
                return list(cached[1])
            corpus = tuple(self._load_documents())
            _BM25_CORPUS_CACHE[bind] = (fingerprint, corpus)
            return list(corpus)

    def _corpus_fingerprint(self) -> tuple[object, ...]:
        statement = (
            select(
                func.count(Chunk.id),
                func.max(Chunk.id),
                func.max(Chunk.created_at),
                func.max(Document.updated_at),
            )
            .select_from(Chunk)
            .join(Document, Chunk.document_id == Document.id)
        )
        return tuple(self.db.execute(statement).one())

    def _load_documents(self) -> list[_BM25Document]:
        statement = select(Chunk, Document).join(Document, Chunk.document_id == Document.id).order_by(Document.id, Chunk.chunk_index)
        rows = self.db.execute(statement).all()
        return [
            _BM25Document(
                document_id=document.id,
                document_title=document.title,
                source_type=document.source_type,
                source_path=document.source_path,
                file_name=document.file_name,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                raw_content=chunk.content,
                heading_path=chunk.heading_path,
                title=normalize_text(document.title),
                heading=normalize_text(chunk.heading_path),
                content=normalize_text(chunk.content),
                length=max(1, lexical_length(chunk.content)),
                title_length=lexical_length(document.title),
                heading_length=lexical_length(chunk.heading_path or ""),
                chunk_type=chunk.chunk_type,
                source_image_path=chunk.source_image_path,
                caption=chunk.caption,
                page_number=chunk.page_number,
            )
            for chunk, document in rows
        ]


def clear_bm25_corpus_cache() -> None:
    with _BM25_CORPUS_CACHE_LOCK:
        _BM25_CORPUS_CACHE.clear()


def warm_bm25_corpus(db: Session) -> int:
    """Build the reusable lexical corpus before serving the first request."""
    return len(BM25SearchService(db)._list_documents())


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
        normalized_term = term.text
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

        title_score += bm25_term_score(title_hits, idf, field_length=item.title_length, avg_length=avg_length, k1=k1, b=0.2) * term_weight * TITLE_WEIGHT
        heading_score += bm25_term_score(title_hits + heading_hits, idf, field_length=item.heading_length, avg_length=avg_length, k1=k1, b=0.4) * term_weight * HEADING_WEIGHT
        content_score += bm25_term_score(content_hits, idf, field_length=item.length, avg_length=avg_length, k1=k1, b=b) * term_weight * CONTENT_WEIGHT

    if has_specific_terms and not specific_hit:
        return None
    score = title_score + heading_score + content_score
    if score <= 0:
        return None

    return BM25SearchResult(
        document_id=item.document_id,
        document_title=item.document_title,
        source_type=item.source_type,
        source_path=item.source_path,
        file_name=item.file_name,
        chunk_id=item.chunk_id,
        chunk_index=item.chunk_index,
        content=item.raw_content,
        heading_path=item.heading_path,
        score=score,
        matched_terms=tuple(dict.fromkeys(matched_terms)),
        title_score=title_score,
        heading_score=heading_score,
        content_score=content_score,
        chunk_type=item.chunk_type,
        source_image_path=item.source_image_path,
        caption=item.caption,
        page_number=item.page_number,
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
