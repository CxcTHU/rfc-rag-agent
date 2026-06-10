"""阶段 19 候选重权（纯函数）。

用途：在 ``HybridSearchService`` 召回结果之后做后处理重权，
让深度全文（open_access_pdf / institutional_access_pdf）或主题锚点命中的 chunk
有机会盖过题录卡片（metadata_record）。

约束：
- 纯函数，不读 DB、不发请求、不依赖 LLM。
- 不修改默认 ``HybridSearchService`` 行为；只在阶段 19 评测脚本里组合使用。
- 输入与输出元素都使用 ``HybridSearchResult``（或与其结构兼容），稳定排序。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Protocol


# 深度全文与题录两组 source_type
DEEP_FULLTEXT_TYPES = frozenset({"open_access_pdf", "institutional_access_pdf"})
METADATA_TYPES = frozenset({"metadata_record", "local_file"})


# 与 Brain workflow.CORE_DOMAIN_TERMS 含义一致，但在此模块内独立维护一份精简版，
# 避免阶段 19 评测脚本和默认拒答门相互耦合；后续如需统一，再合并。
CORE_DOMAIN_TERMS: tuple[str, ...] = (
    # 主题与材料
    "rock-filled", "rock filled", "rock-fill", "rockfill", "rfc",
    "self-compacting", "self compacting", "scc",
    "堆石混凝土", "堆石", "自密实", "胶凝", "骨料",
    "粒径", "级配", "碾压", "rcc",
    # 填充/流动/密实
    "filling", "flowability", "compaction", "compactness",
    "填充", "充填", "流动", "坍落", "密实", "空隙", "孔隙",
    "porosity", "void",
    # 力学/耐久/微观
    "compressive", "tensile", "modulus", "strength", "durability",
    "freeze-thaw", "itz", "interfacial", "mesoscopic", "peridynamics",
    "抗压", "抗拉", "强度", "弹性模量", "力学", "耐久",
    "抗冻", "冻融", "界面", "过渡区", "细观", "断裂",
    # 温控/施工/坝工
    "thermal", "hydration", "temperature", "adiabatic", "seismic", "dam",
    "construction", "水化热", "温升", "温度", "绝热", "抗震",
    "大坝", "坝", "筑坝", "浇筑", "振捣", "施工", "渗透",
    "钢纤维", "steel fiber", "剪力键",
)


@dataclass(frozen=True)
class Stage19TuningWeights:
    """阶段 19 调优权重。所有字段都是 ``score`` 上的加性偏移。

    name: 配置名（用于 CSV 标识）。
    fulltext_boost: 命中深度全文 source_type 时给 ``score`` 增加的偏移量。
    metadata_demote: 命中 metadata/local_file 时给 ``score`` 减去的偏移量（传正值）。
    topic_anchor_bonus_per_term: 命中一个主题锚点词时给 ``score`` 增加的偏移量。
    topic_anchor_cap: 主题锚点加分上限（避免命中大量词时无限叠加）。
    """

    name: str
    fulltext_boost: float = 0.0
    metadata_demote: float = 0.0
    topic_anchor_bonus_per_term: float = 0.0
    topic_anchor_cap: float = 0.0

    def __post_init__(self) -> None:
        if self.fulltext_boost < 0:
            raise ValueError("fulltext_boost must be non-negative")
        if self.metadata_demote < 0:
            raise ValueError("metadata_demote must be non-negative")
        if self.topic_anchor_bonus_per_term < 0:
            raise ValueError("topic_anchor_bonus_per_term must be non-negative")
        if self.topic_anchor_cap < 0:
            raise ValueError("topic_anchor_cap must be non-negative")


# 4 套阶段 19 默认评测配置
BASELINE_WEIGHTS = Stage19TuningWeights(name="hybrid_baseline")
FULLTEXT_BOOST_WEIGHTS = Stage19TuningWeights(
    name="hybrid_fulltext_boost",
    fulltext_boost=0.30,
)
METADATA_DEMOTE_WEIGHTS = Stage19TuningWeights(
    name="hybrid_metadata_demote",
    metadata_demote=0.30,
)
TOPIC_ANCHOR_STRICT_WEIGHTS = Stage19TuningWeights(
    name="hybrid_topic_anchor_strict",
    topic_anchor_bonus_per_term=0.06,
    topic_anchor_cap=0.30,
    fulltext_boost=0.10,
)


class _ScorableResult(Protocol):
    """与 HybridSearchResult 兼容的结构（鸭子类型）。"""

    source_type: str
    score: float
    document_title: str
    content: str
    chunk_id: int
    chunk_index: int
    document_id: int


def count_topic_anchor_hits(query: str, terms: Iterable[str] = CORE_DOMAIN_TERMS) -> int:
    """统计 query 命中多少个主题锚点词（去重，大小写不敏感）。"""
    normalized = (query or "").casefold()
    if not normalized:
        return 0
    matched = {term for term in terms if term in normalized}
    return len(matched)


def compute_reweighted_score(
    result: _ScorableResult,
    weights: Stage19TuningWeights,
    topic_anchor_hits: int = 0,
) -> float:
    """根据权重计算单条结果的重权后分数。"""
    score = float(result.score)
    if result.source_type in DEEP_FULLTEXT_TYPES:
        score += weights.fulltext_boost
    if result.source_type in METADATA_TYPES:
        score -= weights.metadata_demote
    if weights.topic_anchor_bonus_per_term > 0 and topic_anchor_hits > 0:
        bonus = topic_anchor_hits * weights.topic_anchor_bonus_per_term
        if weights.topic_anchor_cap > 0:
            bonus = min(bonus, weights.topic_anchor_cap)
        if result.source_type in DEEP_FULLTEXT_TYPES:
            score += bonus
    return score


def reweight_results(
    results: Iterable[_ScorableResult],
    weights: Stage19TuningWeights,
    query: str = "",
) -> list[_ScorableResult]:
    """对一批 hybrid 召回结果应用 source_type/topic-anchor 重权并稳定重排。

    返回新的列表，不修改输入；不可比的字段（document_title 等）保持原值。
    排序键：``(-new_score, source_type_rank, document_id, chunk_index)``。
    """
    anchor_hits = count_topic_anchor_hits(query) if weights.topic_anchor_bonus_per_term > 0 else 0
    rescored: list[tuple[float, _ScorableResult]] = []
    for result in results:
        new_score = compute_reweighted_score(result, weights, anchor_hits)
        try:
            rescored.append((new_score, replace(result, score=new_score)))
        except TypeError:
            # 兼容非 dataclass 的结构
            rescored.append((new_score, result))

    def _source_type_rank(source_type: str) -> int:
        # 深度全文最优，题录卡片次之，其它最后
        if source_type in DEEP_FULLTEXT_TYPES:
            return 0
        if source_type in METADATA_TYPES:
            return 2
        return 1

    rescored.sort(
        key=lambda item: (
            -item[0],
            _source_type_rank(item[1].source_type),
            item[1].document_id,
            item[1].chunk_index,
        )
    )
    return [result for _score, result in rescored]
