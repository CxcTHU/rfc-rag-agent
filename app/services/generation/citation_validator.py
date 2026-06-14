from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


Mode = Literal["annotate", "drop"]
UNSUPPORTED_MARKER = "[未匹配引用，证据不足]"
CITATION_RE = re.compile(r"\[(\d+)\]")
SENTENCE_RE = re.compile(r".+?(?:[。！？!?](?:[\"'”’])?|[.](?:\s|$)|$)", re.DOTALL)
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]{2,}|[\u4e00-\u9fff]{2,}")
REFUSAL_HINTS = (
    "没有找到足够",
    "没有足够",
    "证据不足",
    "资料库中没有",
    "无法回答",
    "不能替代",
    "not contain enough",
    "not enough reliable evidence",
    "insufficient evidence",
)
STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "because",
    "but",
    "can",
    "does",
    "for",
    "from",
    "has",
    "have",
    "how",
    "into",
    "its",
    "may",
    "not",
    "that",
    "the",
    "this",
    "through",
    "use",
    "uses",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "with",
}


class CitationSourceLike(Protocol):
    source_id: int
    content: str


@dataclass(frozen=True)
class SentenceValidation:
    sentence: str
    citations: tuple[int, ...]
    supported: bool
    reason: str


@dataclass(frozen=True)
class ValidatedAnswer:
    answer: str
    sentence_results: tuple[SentenceValidation, ...]
    unsupported_count: int
    dropped_count: int


def validate_and_repair_citations(
    answer: str,
    sources: Sequence[CitationSourceLike],
    *,
    mode: Mode = "annotate",
) -> ValidatedAnswer:
    if mode not in {"annotate", "drop"}:
        raise ValueError("mode must be 'annotate' or 'drop'")

    normalized_answer = (answer or "").strip()
    if not normalized_answer:
        return ValidatedAnswer(answer="", sentence_results=(), unsupported_count=0, dropped_count=0)
    if is_refusal_answer(normalized_answer):
        return ValidatedAnswer(
            answer=normalized_answer,
            sentence_results=(),
            unsupported_count=0,
            dropped_count=0,
        )

    source_map = {
        source.source_id: normalized_text(source.content)
        for source in sources
        if getattr(source, "content", "").strip()
    }
    repaired_sentences: list[str] = []
    results: list[SentenceValidation] = []
    unsupported_count = 0
    dropped_count = 0

    for sentence in split_sentences(normalized_answer):
        validation = validate_sentence(sentence, source_map)
        results.append(validation)
        if validation.supported:
            repaired_sentences.append(sentence)
            continue

        unsupported_count += 1
        if mode == "drop":
            dropped_count += 1
            continue
        repaired_sentences.append(annotate_sentence(sentence))

    return ValidatedAnswer(
        answer=" ".join(repaired_sentences).strip(),
        sentence_results=tuple(results),
        unsupported_count=unsupported_count,
        dropped_count=dropped_count,
    )


def validate_sentence(sentence: str, source_map: dict[int, str]) -> SentenceValidation:
    citations = tuple(dict.fromkeys(int(match.group(1)) for match in CITATION_RE.finditer(sentence)))
    if not citations:
        return SentenceValidation(sentence=sentence, citations=(), supported=False, reason="missing_citation")

    missing = [citation for citation in citations if citation not in source_map]
    if missing:
        return SentenceValidation(
            sentence=sentence,
            citations=citations,
            supported=False,
            reason="unknown_source_id",
        )

    sentence_keywords = evidence_keywords(strip_citations(sentence))
    if not sentence_keywords:
        return SentenceValidation(
            sentence=sentence,
            citations=citations,
            supported=True,
            reason="citation_only_or_no_keywords",
        )

    for citation in citations:
        source_text = source_map[citation]
        if keyword_overlap(sentence_keywords, source_text):
            return SentenceValidation(
                sentence=sentence,
                citations=citations,
                supported=True,
                reason="keyword_overlap",
            )

    return SentenceValidation(
        sentence=sentence,
        citations=citations,
        supported=False,
        reason="no_keyword_overlap",
    )


def split_sentences(answer: str) -> list[str]:
    compact = re.sub(r"\s+", " ", answer.strip())
    sentences = [match.group(0).strip() for match in SENTENCE_RE.finditer(compact)]
    return [sentence for sentence in sentences if sentence]


def annotate_sentence(sentence: str) -> str:
    if sentence.endswith(UNSUPPORTED_MARKER):
        return sentence
    return f"{sentence} {UNSUPPORTED_MARKER}"


def strip_citations(sentence: str) -> str:
    return CITATION_RE.sub(" ", sentence)


def evidence_keywords(text: str) -> tuple[str, ...]:
    normalized = normalized_text(text)
    keywords: list[str] = []
    for match in TOKEN_RE.finditer(normalized):
        token = match.group(0)
        if token in STOPWORDS:
            continue
        if token not in keywords:
            keywords.append(token)
    return tuple(keywords)


def keyword_overlap(keywords: Sequence[str], source_text: str) -> bool:
    return any(keyword in source_text for keyword in keywords)


def normalized_text(text: str) -> str:
    normalized = re.sub(r"\[[^\]]+\]", " ", text or "")
    normalized = re.sub(r"\b(?:api|bearer|authorization|raw_response|reasoning_content)\b", " ", normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized.casefold()).strip()


def is_refusal_answer(answer: str) -> bool:
    normalized = answer.casefold()
    return any(hint.casefold() in normalized for hint in REFUSAL_HINTS)
