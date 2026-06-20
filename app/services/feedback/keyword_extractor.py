from __future__ import annotations

import re
from collections import Counter


ENGLISH_STOPWORDS = {
    "about",
    "above",
    "after",
    "also",
    "and",
    "are",
    "because",
    "between",
    "can",
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
    "their",
    "this",
    "with",
}
DOMAIN_TERMS = (
    "rock-filled concrete",
    "self-compacting concrete",
    "mix ratio",
    "compressive strength",
    "elastic modulus",
    "durability",
    "crack",
    "citation",
    "table",
    "image",
    "堆石混凝土",
    "自密实混凝土",
    "配合比",
    "抗压强度",
    "弹性模量",
    "耐久性",
    "裂缝",
    "引用",
    "表格",
    "图片",
)
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]+|[\u4e00-\u9fff]{2,}")


def extract_keywords(text: str, top_k: int = 5) -> list[str]:
    if top_k <= 0:
        return []
    normalized = (text or "").strip().casefold()
    if not normalized:
        return []

    scores: Counter[str] = Counter()
    for term in DOMAIN_TERMS:
        occurrences = normalized.count(term.casefold())
        if occurrences:
            scores[term] += occurrences * 4

    for token in TOKEN_RE.findall(normalized):
        cleaned = token.strip("_-")
        if not is_valid_token(cleaned):
            continue
        scores[cleaned] += 1
    return [word for word, _count in scores.most_common(top_k)]


def is_valid_token(token: str) -> bool:
    if len(token) < 2:
        return False
    if token in ENGLISH_STOPWORDS:
        return False
    if token.isdigit():
        return False
    return True
