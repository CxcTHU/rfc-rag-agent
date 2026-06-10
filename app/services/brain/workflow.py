import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.services.brain.config import WorkflowStepName
from app.services.generation.prompt_builder import ContextSource, SearchResultLike
from app.services.retrieval.keyword_search import expand_query_terms, normalize_text


UsedRetrievalMode = Literal["vector", "keyword", "hybrid", "none"]
CITATION_RE = re.compile(r"\[(\d+)\]")
EVIDENCE_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")
DEFAULT_REFUSAL_ANSWER = "当前资料库中没有找到足够可靠的依据。"
RESPONSIBILITY_REFUSAL_ANSWER = (
    "当前系统不能替代规范审查、工程设计、第三方检测或专家签字；"
    "不能直接判定工程是否合格、是否符合规范或能否用于实际工程。"
    "你可以改问：资料中有哪些指标、试验方法、影响因素或风险点可供人工审查参考。"
)
DEFAULT_MIN_QUERY_TOKEN_COVERAGE = 0.2
QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "does",
    "do",
    "for",
    "give",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "why",
}

# 本语料的核心领域词（堆石混凝土及其材料/力学/施工/温控等子主题，中英文）。
# 用作“主题门”：on-topic 问题几乎必含其一；明显 off-topic（烹饪/金融/LLM/量子等）
# 一个都不含。判据作用在“改写后（含 history）”的查询上，故追问也能正确放行。
# 全部小写，按 casefold 后的查询做子串匹配。
CORE_DOMAIN_TERMS = (
    # 主题与材料
    "rock-filled", "rock filled", "rock-fill", "rockfill", "rfc", "concrete",
    "self-compacting", "self compacting", "scc", "cementitious", "mortar",
    "aggregate", "堆石混凝土", "堆石", "混凝土", "自密实", "胶凝", "砂浆",
    "骨料", "粒径", "级配", "碾压", "rcc",
    # 填充/流动/密实
    "filling", "flowability", "compactness", "compaction", "填充", "充填",
    "流动", "坍落", "密实", "空隙", "孔隙", "porosity", "void",
    # 力学/耐久
    "compressive", "tensile", "modulus", "strength", "creep", "durability",
    "freeze-thaw", "itz", "interfacial", "mesoscopic", "peridynamics",
    "抗压", "抗拉", "强度", "弹性模量", "力学", "徐变", "耐久", "抗冻",
    "界面", "过渡区", "细观", "本构", "断裂", "剪切", "冷缝", "层间",
    # 温控/施工/坝工
    "thermal", "hydration", "temperature", "adiabatic", "seismic", "dam",
    "construction", "emission", "水化热", "温升", "温度", "绝热", "抗震",
    "地震", "大坝", "坝", "筑坝", "浇筑", "振捣", "施工", "碳排放", "渗透",
    "钢纤维", "steel fiber", "rock shear", "剪力键",
)

RESPONSIBILITY_GATE_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"(判定|判断|评定|认定).{0,12}(是否)?(符合|满足|达到|通过|合格|达标|有效|可用|规范|标准|要求)",
        r"(是否|是不是|能否|可否|能不能|可不可以).{0,10}(符合|满足|达到).{0,10}(规范|规程|标准|要求)",
        r"(是否|是不是|能否|可否|能不能|可不可以).{0,10}(合格|达标|有效|通过|可用)",
        r"(出具|开具|给出).{0,10}(结论|意见|报告|评定|审查|验收)",
        r"(是否|能否|可否|能不能|可不可以|可以|能).{0,8}(直接)?(用于|应用于).{0,8}(工程|施工|设计)",
        r"(工程|项目|现场|配合比|设计方案|检测报告).{0,12}(是否|是不是|能否|可否|能不能).{0,8}(合格|符合|满足|有效|通过|可用)",
    )
)


@dataclass(frozen=True)
class BrainWorkflowStepRecord:
    name: WorkflowStepName
    input_summary: str
    output_summary: str
    succeeded: bool
    error: str | None = None


@dataclass(frozen=True)
class BrainRetrievalOutcome:
    results: list[SearchResultLike]
    used_retrieval_mode: UsedRetrievalMode
    refusal_reason: str | None = None


@dataclass(frozen=True)
class EvidenceConfidence:
    sufficient: bool
    score: float
    matched_terms: tuple[str, ...]
    missing_terms: tuple[str, ...]
    refusal_reason: str | None = None


@dataclass(frozen=True)
class ResponsibilityGate:
    triggered: bool
    refusal_reason: str | None = None


@dataclass(frozen=True)
class BrainAnswerResult:
    question: str
    answer: str
    citations: list[int]
    sources: list[ContextSource]
    refused: bool
    refusal_reason: str | None
    retrieval_mode: UsedRetrievalMode
    model_provider: str
    model_name: str
    workflow_steps: list[BrainWorkflowStepRecord]


def build_retrieval_outcome(
    raw_results: Sequence[SearchResultLike],
    used_retrieval_mode: UsedRetrievalMode,
    min_score: float,
) -> BrainRetrievalOutcome:
    if not raw_results:
        return BrainRetrievalOutcome(
            results=[],
            used_retrieval_mode=used_retrieval_mode,
            refusal_reason="No retrieved chunks were available.",
        )

    filtered_results = [result for result in raw_results if result.score >= min_score]
    if not filtered_results:
        return BrainRetrievalOutcome(
            results=[],
            used_retrieval_mode=used_retrieval_mode,
            refusal_reason="No retrieved chunks met the minimum score threshold.",
        )

    return BrainRetrievalOutcome(
        results=list(filtered_results),
        used_retrieval_mode=used_retrieval_mode,
        refusal_reason=None,
    )


def evaluate_evidence_confidence(
    query: str,
    results: Sequence[SearchResultLike],
    min_query_token_coverage: float = DEFAULT_MIN_QUERY_TOKEN_COVERAGE,
) -> EvidenceConfidence:
    query_terms = extract_evidence_terms(query)
    expanded_terms = extract_expanded_evidence_terms(query)
    candidate_terms = query_terms
    if expanded_terms:
        candidate_terms = expanded_terms

    if not candidate_terms:
        return EvidenceConfidence(
            sufficient=False,
            score=0.0,
            matched_terms=(),
            missing_terms=(),
            refusal_reason="No evidence-bearing query terms were available.",
        )
    if not results:
        return EvidenceConfidence(
            sufficient=False,
            score=0.0,
            matched_terms=(),
            missing_terms=tuple(candidate_terms),
            refusal_reason="No retrieved chunks were available for evidence confidence.",
        )

    evidence_text = evidence_text_from_results(results)
    raw_confidence = score_evidence_terms(query_terms, evidence_text)
    expanded_confidence = score_evidence_terms(expanded_terms, evidence_text)
    matched_terms, missing_terms, score = max(
        [raw_confidence, expanded_confidence],
        key=lambda item: item[2],
    )
    # 主题锚点：防止 off-topic 问题靠零散单字（中文按单字切词）偶然在大段证据里命中、
    # 把覆盖率顶过阈值。只有证据真正含有“领域专有词”或“查询的中文 bigram”时，
    # 才认为问题与语料同主题，否则判为 off-topic 拒答。
    anchor = has_topic_anchor(query)
    if matched_terms and score >= min_query_token_coverage and anchor:
        return EvidenceConfidence(
            sufficient=True,
            score=score,
            matched_terms=matched_terms,
            missing_terms=missing_terms,
        )

    if not anchor:
        refusal_reason = (
            "Question appears off-topic: retrieved chunks share no domain-specific "
            "evidence term or Chinese bigram with the query."
        )
    else:
        refusal_reason = (
            "Retrieved chunks did not share enough evidence-bearing query terms "
            f"(coverage={score:.2f})."
        )
    return EvidenceConfidence(
        sufficient=False,
        score=score,
        matched_terms=matched_terms,
        missing_terms=missing_terms,
        refusal_reason=refusal_reason,
    )


def evaluate_responsibility_gate(query: str) -> ResponsibilityGate:
    """Reject engineering responsibility / compliance judgment requests.

    This is different from ``has_topic_anchor``: a question can be clearly
    on-topic but still ask the system to replace code review, engineering
    design, third-party testing, acceptance inspection, or expert sign-off.
    """

    normalized = re.sub(r"\s+", "", normalize_text(query))
    if not normalized:
        return ResponsibilityGate(triggered=False)
    if any(pattern.search(normalized) for pattern in RESPONSIBILITY_GATE_PATTERNS):
        return ResponsibilityGate(
            triggered=True,
            refusal_reason=(
                "responsibility_gate: question asks for engineering compliance, "
                "acceptance, design, testing, or sign-off judgment."
            ),
        )
    return ResponsibilityGate(triggered=False)


def has_topic_anchor(query: str) -> bool:
    """主题门：查询是否提到本语料的核心领域词。

    单一领域语料里，on-topic 问题几乎必然包含一个核心领域词；明显 off-topic
    （烹饪/金融/LLM/量子/乱码）一个都不含。判据作用在改写后（含 history）的查询上。
    比"证据里是否出现词"更稳——证据全是 RFC，通用词必然命中，无法区分 off-topic。
    """

    normalized = (query or "").casefold()
    return any(term in normalized for term in CORE_DOMAIN_TERMS)


def score_evidence_terms(
    query_terms: Sequence[str],
    evidence_text: str,
) -> tuple[tuple[str, ...], tuple[str, ...], float]:
    if not query_terms:
        return (), (), 0.0
    matched_terms = tuple(term for term in query_terms if term in evidence_text)
    missing_terms = tuple(term for term in query_terms if term not in matched_terms)
    score = len(matched_terms) / len(query_terms)
    return matched_terms, missing_terms, score


def extract_evidence_terms(query: str) -> tuple[str, ...]:
    raw_terms = [
        match.group(0).casefold()
        for match in EVIDENCE_TOKEN_RE.finditer(query or "")
    ]
    terms = [
        term
        for term in raw_terms
        if is_evidence_term(term)
    ]
    if not terms:
        terms = raw_terms

    unique_terms: list[str] = []
    for term in terms:
        if term not in unique_terms:
            unique_terms.append(term)
    return tuple(unique_terms)


def extract_expanded_evidence_terms(query: str) -> tuple[str, ...]:
    expanded_terms = [
        normalize_text(term.text)
        for term in expand_query_terms(query)
        if term.specific and is_evidence_phrase(term.text)
    ]

    unique_terms: list[str] = []
    for term in expanded_terms:
        if term and term not in unique_terms:
            unique_terms.append(term)
    return tuple(unique_terms)


def is_evidence_phrase(term: str) -> bool:
    normalized = normalize_text(term)
    if not normalized:
        return False
    if any(marker in normalized for marker in ["?", "？", "，", ",", "。"]):
        return False
    tokens = [token for token in EVIDENCE_TOKEN_RE.findall(normalized) if token not in QUERY_STOPWORDS]
    return bool(tokens)


def is_evidence_term(term: str) -> bool:
    if not term:
        return False
    if term in QUERY_STOPWORDS:
        return False
    if len(term) == 1 and not ("\u4e00" <= term <= "\u9fff"):
        return False
    return True


def evidence_text_from_results(results: Sequence[SearchResultLike]) -> str:
    return " ".join(
        " ".join(
            [
                result.document_title,
                result.heading_path or "",
                result.content,
            ]
        ).casefold()
        for result in results
    )


def extract_citations(answer: str, allowed_source_ids: Sequence[int]) -> list[int]:
    allowed = set(allowed_source_ids)
    citations: list[int] = []
    for match in CITATION_RE.finditer(answer):
        citation = int(match.group(1))
        if citation not in allowed or citation in citations:
            continue
        citations.append(citation)
    return citations
