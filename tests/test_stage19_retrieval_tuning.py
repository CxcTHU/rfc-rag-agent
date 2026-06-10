"""阶段 19 检索调优纯函数 + 评测脚本结构测试。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from app.services.retrieval.source_type_reweight import (
    BASELINE_WEIGHTS,
    CORE_DOMAIN_TERMS,
    DEEP_FULLTEXT_TYPES,
    FULLTEXT_BOOST_WEIGHTS,
    METADATA_DEMOTE_WEIGHTS,
    METADATA_TYPES,
    Stage19TuningWeights,
    TOPIC_ANCHOR_STRICT_WEIGHTS,
    compute_reweighted_score,
    count_topic_anchor_hits,
    reweight_results,
)

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class FakeHybridResult:
    """与 HybridSearchResult 鸭子类型兼容的最小测试结构。"""

    document_id: int
    document_title: str
    source_type: str
    content: str
    chunk_id: int
    chunk_index: int
    score: float


def make(
    chunk_id: int,
    source_type: str,
    score: float,
    title: str = "",
    content: str = "",
) -> FakeHybridResult:
    return FakeHybridResult(
        document_id=chunk_id // 10 + 1,
        document_title=title or f"doc-{chunk_id}",
        source_type=source_type,
        content=content,
        chunk_id=chunk_id,
        chunk_index=chunk_id % 10,
        score=score,
    )


def test_baseline_does_not_change_order_when_scores_already_sorted():
    items = [
        make(1, "metadata_record", 0.9),
        make(2, "open_access_pdf", 0.5),
        make(3, "institutional_access_pdf", 0.4),
    ]
    out = reweight_results(items, BASELINE_WEIGHTS)
    assert [r.chunk_id for r in out] == [1, 2, 3]


def test_fulltext_boost_lifts_deep_fulltext_above_metadata():
    items = [
        make(1, "metadata_record", 0.6),
        make(2, "open_access_pdf", 0.4),
        make(3, "institutional_access_pdf", 0.4),
    ]
    out = reweight_results(items, FULLTEXT_BOOST_WEIGHTS)
    # 0.4 + 0.30 = 0.70 > 0.6 → 深度全文跃到 top-2 之前
    assert out[0].source_type in DEEP_FULLTEXT_TYPES
    assert out[1].source_type in DEEP_FULLTEXT_TYPES
    assert out[-1].source_type == "metadata_record"


def test_metadata_demote_pushes_metadata_down():
    items = [
        make(1, "metadata_record", 0.9),
        make(2, "metadata_record", 0.8),
        make(3, "open_access_pdf", 0.65),
    ]
    out = reweight_results(items, METADATA_DEMOTE_WEIGHTS)
    # 0.9-0.30=0.6, 0.8-0.30=0.5, fulltext 0.65 → fulltext 居首
    assert out[0].chunk_id == 3
    assert out[0].source_type == "open_access_pdf"


def test_topic_anchor_strict_helps_fulltext_with_anchor_query():
    items = [
        make(1, "metadata_record", 0.9, content="rfc"),
        make(2, "open_access_pdf", 0.6, content="rfc filling"),
    ]
    query = "rock-filled concrete 自密实 填充 ITZ"  # >=3 锚点词
    out = reweight_results(items, TOPIC_ANCHOR_STRICT_WEIGHTS, query=query)
    assert out[0].chunk_id == 2  # deep fulltext + topic anchor + 0.10 base boost 跃居


def test_topic_anchor_does_not_help_when_query_has_no_anchor():
    items = [
        make(1, "metadata_record", 0.9),
        make(2, "open_access_pdf", 0.5),
    ]
    # 完全 off-topic 查询：没有任何 CORE_DOMAIN_TERMS 命中
    out = reweight_results(items, TOPIC_ANCHOR_STRICT_WEIGHTS, query="今天上海天气")
    # 因为 fulltext_boost=0.10，deep fulltext 仍可拿到 0.10 boost；
    # 0.5+0.10=0.6 < 0.9，所以仍 metadata 在前。验证 anchor 不会无关引入巨额加分。
    assert out[0].source_type == "metadata_record"


def test_count_topic_anchor_hits_dedups_and_is_case_insensitive():
    assert count_topic_anchor_hits("rock-filled rock-filled concrete RFC") >= 2
    assert count_topic_anchor_hits("RFC RFC RFC") >= 1
    assert count_topic_anchor_hits("") == 0


def test_compute_reweighted_score_respects_bounds():
    item = make(1, "open_access_pdf", 0.5)
    weights = Stage19TuningWeights(
        name="t",
        fulltext_boost=0.2,
        topic_anchor_bonus_per_term=0.05,
        topic_anchor_cap=0.10,
    )
    # 5 个锚点命中 * 0.05 = 0.25 但 cap=0.10，最终 = 0.5+0.2+0.10 = 0.80
    assert compute_reweighted_score(item, weights, topic_anchor_hits=5) == pytest.approx(0.80)


def test_weights_dataclass_rejects_negative_values():
    with pytest.raises(ValueError):
        Stage19TuningWeights(name="bad", fulltext_boost=-0.1)
    with pytest.raises(ValueError):
        Stage19TuningWeights(name="bad", metadata_demote=-0.1)
    with pytest.raises(ValueError):
        Stage19TuningWeights(name="bad", topic_anchor_bonus_per_term=-0.1)
    with pytest.raises(ValueError):
        Stage19TuningWeights(name="bad", topic_anchor_cap=-0.1)


def test_known_chinese_anchor_terms_are_present():
    for term in ("堆石混凝土", "自密实", "界面", "抗冻", "温升", "rfc", "scc"):
        assert term in CORE_DOMAIN_TERMS


def test_reweight_results_does_not_mutate_input_items():
    items = [
        make(1, "metadata_record", 0.9),
        make(2, "open_access_pdf", 0.4),
    ]
    snapshot = [(r.chunk_id, r.score) for r in items]
    _ = reweight_results(items, METADATA_DEMOTE_WEIGHTS)
    assert [(r.chunk_id, r.score) for r in items] == snapshot


def test_evaluation_script_outputs_referenced_in_design_doc():
    design_doc = (ROOT / "docs" / "stage19_chinese_analysis_retrieval_tuning.md").read_text(
        encoding="utf-8"
    )
    assert "stage19_retrieval_tuning_results.csv" in design_doc
    assert "stage19_retrieval_tuning_summary.csv" in design_doc
    assert "source_type_reweight" in design_doc
