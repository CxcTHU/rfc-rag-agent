from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


QueryComplexity = Literal["simple", "complex"]

CLAUSE_SEPARATOR_RE = re.compile(r"[,;:，；：、?？!！]")
TOKEN_RE = re.compile(r"[A-Za-z0-9_+-]+|[\u4e00-\u9fff]")

DIRECT_SOURCE_PATTERNS = (
    "list sources",
    "sources list",
    "source detail",
    "source_id",
    "source id",
    "来源列表",
    "资料来源",
    "来源详情",
)

COMPARISON_KEYWORDS = (
    "compare",
    "comparison",
    "difference",
    "differences",
    "versus",
    " vs ",
    "tradeoff",
    "trade-off",
    "pros and cons",
    "对比",
    "比较",
    "区别",
    "差异",
    "优缺点",
)

PROCESS_KEYWORDS = (
    "process",
    "workflow",
    "steps",
    "mechanism",
    "mechanisms",
    "pathway",
    "sequence",
    "流程",
    "步骤",
    "机制",
    "路径",
    "先后",
    "如何形成",
)

MULTI_ASPECT_KEYWORDS = (
    "jointly",
    "multiple",
    "multi",
    "several",
    "both",
    "respectively",
    "combined",
    "综合",
    "结合",
    "多方面",
    "分别",
    "哪些因素",
    "同时",
)

CROSS_EVIDENCE_KEYWORDS = (
    "cross-passage",
    "cross passage",
    "multi-source",
    "multiple sources",
    "evidence merge",
    "evidence synthesis",
    "rewrite",
    "reformulate",
    "alias",
    "terminology",
    "跨段",
    "多篇",
    "证据合并",
    "术语",
    "别名",
    "改写",
    "换一种说法",
)

CAUSAL_KEYWORDS = (
    "why",
    "how",
    "affect",
    "affects",
    "influence",
    "influences",
    "原因",
    "为什么",
    "影响",
)

SEARCH_KEYWORDS = (
    "search",
    "find",
    "retrieve",
    "检索",
    "搜索",
    "查找",
)

ANALYSIS_KEYWORDS = (
    "compare",
    "explain",
    "summarize",
    "analyze",
    "contrast",
    "比较",
    "解释",
    "总结",
    "分析",
)


@dataclass(frozen=True)
class QueryComplexityResult:
    complexity: QueryComplexity
    score: int
    reasons: tuple[str, ...]
    signals: tuple[str, ...]


def classify_query_complexity(question: str) -> QueryComplexityResult:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")

    normalized = normalized_question.casefold()
    compact = re.sub(r"\s+", "", normalized_question)
    tokens = TOKEN_RE.findall(normalized_question)
    score = 0
    reasons: list[str] = []
    signals: list[str] = []

    if contains_any(normalized, DIRECT_SOURCE_PATTERNS):
        return QueryComplexityResult(
            complexity="simple",
            score=0,
            reasons=("direct source/list request should remain in default AgentService",),
            signals=("direct_source_request",),
        )

    nonspace_length = len(compact)
    token_count = len(tokens)
    if nonspace_length >= 80 or token_count >= 22:
        score += 2
        reasons.append(f"long question length chars={nonspace_length} tokens={token_count}")
        signals.append("long_question")
    elif nonspace_length >= 48 or token_count >= 14:
        score += 1
        reasons.append(f"moderate question length chars={nonspace_length} tokens={token_count}")
        signals.append("moderate_length")

    clause_count = estimate_clause_count(normalized_question)
    if clause_count >= 4:
        score += 2
        reasons.append(f"multiple clauses count={clause_count}")
        signals.append("many_clauses")
    elif clause_count >= 3:
        score += 1
        reasons.append(f"several clauses count={clause_count}")
        signals.append("several_clauses")

    score = add_keyword_signal(
        normalized,
        COMPARISON_KEYWORDS,
        "comparison",
        2,
        score,
        reasons,
        signals,
    )
    score = add_keyword_signal(
        normalized,
        PROCESS_KEYWORDS,
        "process_or_mechanism",
        1,
        score,
        reasons,
        signals,
    )
    score = add_keyword_signal(
        normalized,
        MULTI_ASPECT_KEYWORDS,
        "multi_aspect",
        1,
        score,
        reasons,
        signals,
    )
    score = add_keyword_signal(
        normalized,
        CROSS_EVIDENCE_KEYWORDS,
        "cross_evidence_or_rewrite",
        2,
        score,
        reasons,
        signals,
    )
    score = add_keyword_signal(
        normalized,
        CAUSAL_KEYWORDS,
        "causal_explanation",
        1,
        score,
        reasons,
        signals,
    )

    if contains_any(normalized, SEARCH_KEYWORDS) and contains_any(normalized, ANALYSIS_KEYWORDS):
        score += 2
        reasons.append("search plus analysis/compare intent")
        signals.append("search_analysis_combo")

    if is_complex_score(score, signals):
        return QueryComplexityResult(
            complexity="complex",
            score=score,
            reasons=tuple(reasons),
            signals=tuple(dict.fromkeys(signals)),
        )

    if not reasons:
        reasons.append("short single-intent question")
        signals.append("short_single_intent")

    return QueryComplexityResult(
        complexity="simple",
        score=score,
        reasons=tuple(reasons),
        signals=tuple(dict.fromkeys(signals)),
    )


def estimate_clause_count(question: str) -> int:
    separators = len(CLAUSE_SEPARATOR_RE.findall(question))
    connector_count = sum(
        question.casefold().count(connector)
        for connector in (
            " and ",
            " or ",
            " but ",
            " while ",
            "以及",
            "并且",
            "同时",
            "分别",
            "和",
        )
    )
    return 1 + separators + connector_count


def add_keyword_signal(
    normalized: str,
    keywords: tuple[str, ...],
    signal: str,
    weight: int,
    score: int,
    reasons: list[str],
    signals: list[str],
) -> int:
    matched = first_match(normalized, keywords)
    if matched is None:
        return score
    reasons.append(f"{signal} keyword={matched.strip()}")
    signals.append(signal)
    return score + weight


def is_complex_score(score: int, signals: list[str]) -> bool:
    strong_signals = {
        "comparison",
        "process_or_mechanism",
        "multi_aspect",
        "cross_evidence_or_rewrite",
        "search_analysis_combo",
    }
    if score >= 3:
        return True
    return score >= 2 and bool(strong_signals.intersection(signals))


def contains_any(normalized: str, keywords: tuple[str, ...]) -> bool:
    return first_match(normalized, keywords) is not None


def first_match(normalized: str, keywords: tuple[str, ...]) -> str | None:
    return next((keyword for keyword in keywords if keyword.casefold() in normalized), None)
