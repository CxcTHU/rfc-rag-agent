"""阶段 18：难评测集与多配置对比脚本的结构与逻辑测试（不联网）。"""

from pathlib import Path

from scripts.evaluate_stage18_hard_set import (
    CONFIGS,
    HardQuery,
    build_comparison,
    contains_any,
    default_chain_decision,
    find_hit,
    read_hard_queries,
)


HARD_QUERIES = Path("data/evaluation/stage18_hard_queries.csv")


class _FakeResult:
    def __init__(self, title="", source_type="", content="", score=0.0, document_id=0):
        self.document_title = title
        self.source_type = source_type
        self.content = content
        self.score = score
        self.document_id = document_id


def test_hard_query_set_has_three_difficulty_types_and_refusals() -> None:
    queries = read_hard_queries(HARD_QUERIES)
    assert len(queries) >= 18
    types = {q.difficulty_type for q in queries}
    assert {"cross_passage", "confusable", "refusal"}.issubset(types)
    refusals = [q for q in queries if q.expected_refused]
    assert len(refusals) >= 3
    # 需拒答查询不应带期望命中条件。
    for q in refusals:
        assert not q.expected_title_terms and not q.expected_content_terms
    # 可回答查询必须带至少一个期望命中条件，保证“命中”可判定。
    for q in queries:
        if not q.expected_refused:
            assert q.expected_title_terms or q.expected_content_terms or q.expected_source_types


def test_find_hit_respects_title_and_content_terms() -> None:
    query = HardQuery(
        query_id="t",
        query="q",
        difficulty_type="confusable",
        language_type="en",
        top_k=8,
        expected_title_terms=["Elastic Modulus"],
        expected_content_terms=[],
        expected_source_types=[],
        expected_refused=False,
        notes="",
    )
    results = [
        _FakeResult(title="Compressive Strength Study"),
        _FakeResult(title="Comparative Analysis of the Elastic Modulus"),
    ]
    assert find_hit(query, results) == 1
    # 没有任一期望命中文献则返回 None。
    assert find_hit(query, [_FakeResult(title="Seismic Behavior")]) is None


def test_contains_any_case_insensitive() -> None:
    assert contains_any("Rock-Filled Concrete Dam", ["rock-filled"])
    assert not contains_any("Self-Compacting Concrete", ["peridynamics"])


def test_default_chain_decision_keeps_hybrid_without_clear_win() -> None:
    comparison = [
        {"config": "hybrid", "hits": "15", "rank1_hits": "14", "mean_hit_rank": "1.07", "distinct_wins": "0"},
        {"config": "bm25_rrf", "hits": "15", "rank1_hits": "14", "mean_hit_rank": "1.13", "distinct_wins": "0"},
    ]
    assert default_chain_decision(comparison) == "keep_existing_hybrid"


def test_default_chain_decision_suggests_switch_when_rrf_better() -> None:
    comparison = [
        {"config": "hybrid", "hits": "12", "rank1_hits": "10", "mean_hit_rank": "1.5", "distinct_wins": "0"},
        {"config": "bm25_rrf", "hits": "14", "rank1_hits": "13", "mean_hit_rank": "1.2", "distinct_wins": "1"},
    ]
    assert default_chain_decision(comparison) == "consider_switch_to_bm25_rrf"


def test_build_comparison_reports_all_configs() -> None:
    queries = read_hard_queries(HARD_QUERIES)
    comparison = build_comparison([], queries)
    assert [row["config"] for row in comparison] == CONFIGS
    for row in comparison:
        assert "precision_at_1" in row and "rank1_hits" in row
