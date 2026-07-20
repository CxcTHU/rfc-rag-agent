from __future__ import annotations

import sys

import pytest

from app.services.retrieval.reranking import ReRankResult
from scripts.reranker import evaluate_rag_reranker_ab as ab
from scripts.reranker import evaluate_rag_reranker_pool_ab as pool_ab
from scripts.reranker import serve_lora_reranker as service


def test_lora_service_parse_openai_style_rerank_request() -> None:
    request = service.parse_rerank_request(
        {
            "model": "bge-reranker-base-rfc-lora",
            "query": "filling capacity",
            "documents": ["first", "second"],
            "top_n": 1,
        }
    )

    assert request.model == "bge-reranker-base-rfc-lora"
    assert request.query == "filling capacity"
    assert request.documents == ["first", "second"]
    assert request.top_n == 1


def test_lora_service_rejects_empty_documents() -> None:
    with pytest.raises(ValueError, match="documents"):
        service.parse_rerank_request(
            {
                "model": "bge-reranker-base-rfc-lora",
                "query": "filling capacity",
                "documents": ["ok", " "],
            }
        )


def test_stage3_build_rerankers_requires_explicit_glm_execute() -> None:
    with pytest.raises(ValueError, match="execute-glm"):
        ab.build_rerankers(
            ["glm-reranker"],
            execute_glm=False,
            remote_bge_url="",
            remote_bge_api_key="",
            remote_bge_model=ab.DEFAULT_REMOTE_BGE_MODEL,
        )


def test_stage3_build_rerankers_requires_remote_bge_url() -> None:
    with pytest.raises(ValueError, match="remote-bge-url"):
        ab.build_rerankers(
            ["remote-bge-lora"],
            execute_glm=False,
            remote_bge_url="",
            remote_bge_api_key="",
            remote_bge_model=ab.DEFAULT_REMOTE_BGE_MODEL,
        )


def test_stage3_parse_args_defaults_to_local_only_provider(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["evaluate_rag_reranker_ab.py"])

    args = ab.parse_args()

    assert args.provider == "deterministic"
    assert args.include_tool_calling_cases is True
    assert args.limit == 0


def test_stage3_load_queries_can_include_tool_calling_cases() -> None:
    queries = ab.load_queries([], include_tool_calling_cases=True)

    assert any(query.dataset == ab.TOOL_CALLING_CASE_SOURCE for query in queries)
    assert any(query.expected_refused for query in queries)


def test_stage3_load_queries_rejects_empty_inputs_without_phase51() -> None:
    with pytest.raises(ValueError, match="no evaluation queries"):
        ab.load_queries([], include_tool_calling_cases=False)


def test_stage3_remote_bge_uses_explicit_url_without_local_model(monkeypatch) -> None:
    created = {}

    class FakeProvider:
        provider_name = "remote-bge-lora"
        model_name = "bge-reranker-base-rfc-lora"

        def __init__(self, **kwargs):
            created.update(kwargs)

        def rerank(self, query, candidates, top_k=5):
            return [ReRankResult(index=0, score=1.0, content=candidates[0])]

    monkeypatch.setattr(ab, "OpenAICompatibleReRankingProvider", FakeProvider)

    rerankers = ab.build_rerankers(
        ["remote-bge-lora"],
        execute_glm=False,
        remote_bge_url="http://gpu.example.test:8091/v1",
        remote_bge_api_key="",
        remote_bge_model="bge-reranker-base-rfc-lora",
    )

    assert rerankers[0].name == "remote-bge-lora"
    assert created["base_url"] == "http://gpu.example.test:8091/v1"
    assert created["api_key"] == ""


def test_stage3_snapshot_does_not_include_candidate_content() -> None:
    query = ab.EvalQuery(
        query_id="q1",
        question="filling capacity",
        dataset="fixture",
        category="test",
        expected_source_type="local_file",
        expected_terms=("filling",),
    )
    candidate = ab.Candidate(
        index=0,
        chunk_id=42,
        document_title="Filling Capacity Study",
        source_type="local_file",
        content="full chunk text must not be serialized",
        score=0.8,
        relevant=True,
    )

    snapshot = ab.snapshot_candidates(query, [candidate])[0]

    assert snapshot["query_id"] == "q1"
    assert snapshot["chunk_id"] == 42
    assert snapshot["title"] == "Filling Capacity Study"
    assert "content" not in snapshot


def test_stage3_compute_metrics_uses_frozen_candidate_labels() -> None:
    query = ab.EvalQuery(
        query_id="q1",
        question="filling capacity",
        dataset="fixture",
        category="test",
        expected_source_type="local_file",
        expected_terms=("filling",),
    )
    candidates = [
        ab.Candidate(0, 1, "Thermal", "local_file", "thermal", 0.9, False),
        ab.Candidate(1, 2, "Filling", "local_file", "filling capacity", 0.1, True),
    ]
    ranking = [
        ab.RankedCandidate(original_index=1, score=2.0, relevant=True),
        ab.RankedCandidate(original_index=0, score=1.0, relevant=False),
    ]

    metrics = ab.compute_metrics(ranking, candidates, query, k=2)

    assert metrics["mrr_at_5"] == 1.0
    assert metrics["ndcg_at_5"] == 1.0
    assert metrics["precision_at_1"] == 1.0
    assert metrics["coverage_ratio"] == 1.0


def test_stage3_pool_parse_combos_defaults_and_custom_values() -> None:
    assert pool_ab.parse_combos([]) == [(25, 5), (50, 5), (50, 8), (75, 8), (100, 10)]
    assert pool_ab.parse_combos(["50:8", "100:10"]) == [(50, 8), (100, 10)]


def test_stage3_pool_parse_combos_rejects_invalid_top_k() -> None:
    with pytest.raises(ValueError, match="top_k"):
        pool_ab.parse_combos(["5:8"])


def test_stage3_pool_metrics_keep_at5_and_topk_metrics_separate() -> None:
    query = ab.EvalQuery(
        query_id="q1",
        question="filling capacity durability",
        dataset="fixture",
        category="test",
        expected_source_type="local_file",
        expected_terms=("filling", "durability"),
    )
    candidates = [
        ab.Candidate(0, 1, "Other", "local_file", "other", 0.9, False),
        ab.Candidate(1, 2, "Other", "local_file", "other", 0.8, False),
        ab.Candidate(2, 3, "Other", "local_file", "other", 0.7, False),
        ab.Candidate(3, 4, "Other", "local_file", "other", 0.6, False),
        ab.Candidate(4, 5, "Other", "local_file", "other", 0.5, False),
        ab.Candidate(5, 6, "Filling", "local_file", "filling capacity", 0.4, True),
        ab.Candidate(6, 7, "Durability", "local_file", "durability", 0.3, True),
        ab.Candidate(7, 8, "Other", "local_file", "other", 0.2, False),
    ]
    ranking = [
        ab.RankedCandidate(original_index=index, score=float(10 - index), relevant=candidates[index].relevant)
        for index in range(len(candidates))
    ]

    metrics = pool_ab.compute_pool_metrics(ranking=ranking, candidates=candidates, query=query, top_k=8)

    assert metrics["mrr_at_5"] == 0.0
    assert metrics["precision_at_5"] == 0.0
    assert metrics["precision_at_8"] == 1.0
    assert metrics["ndcg_at_8"] > 0.0
    assert metrics["coverage_ratio"] == 1.0
    assert metrics["candidate_recall_hit"] == 1.0
