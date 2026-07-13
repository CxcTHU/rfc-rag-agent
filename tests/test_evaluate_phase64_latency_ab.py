from __future__ import annotations

import csv
import json
from pathlib import Path

import scripts.evaluate_phase64_latency_ab as phase64_evaluator
from scripts.evaluate_phase64_latency_ab import (
    PHASE64_OUTPUT_FIELDS,
    build_phase64_summary,
    deterministic_pair_order,
    run_case,
    selected_chat_model_for_variant,
    validate_frozen_contract,
)


def test_phase64_output_keeps_safe_retrieval_and_rerank_component_timings() -> None:
    assert "retrieval_total_latency_ms" in PHASE64_OUTPUT_FIELDS
    assert "glm_rerank_latency_ms" in PHASE64_OUTPUT_FIELDS
    assert "final_model_ttft_ms" in PHASE64_OUTPUT_FIELDS
    assert "citation_repair_latency_ms" in PHASE64_OUTPUT_FIELDS
    assert "provider_http_request_count" in PHASE64_OUTPUT_FIELDS
    assert "provider_http_reused_connection_count" in PHASE64_OUTPUT_FIELDS
    assert "provider_http_last_connection_reused" in PHASE64_OUTPUT_FIELDS


def test_phase64_variant_models_are_explicit_and_distinct() -> None:
    assert selected_chat_model_for_variant("phase63") == "deepseek-v4-pro"
    assert selected_chat_model_for_variant("phase64") == "deepseek-v4-flash"


def test_phase64_run_case_sends_flash_and_rejects_observed_model_mismatch(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_execute_case(*_args, **kwargs):
        received.update(kwargs)
        return {"ok": True, "observed_chat_model": "deepseek-v4-pro"}

    monkeypatch.setattr(phase64_evaluator, "execute_case", fake_execute_case)

    row = run_case(
        {"case_id": "case-1", "category": "ordinary_text"},
        variant="phase64",
        run=1,
        base_url="http://phase64.test",
        contract={},
        token="",
        timeout_seconds=1.0,
        keep_conversations=False,
    )

    assert received["chat_model"] == "deepseek-v4-flash"
    assert row["ok"] is False
    assert row["error_category"] == "selected_chat_model_mismatch"


def _row(variant: str, case_id: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "variant": variant,
        "run": 1,
        "case_id": case_id,
        "category": "ordinary_text",
        "ok": True,
        "error_category": "",
        "expected_tool": "hybrid_search_knowledge",
        "observed_tool_names": "hybrid_search_knowledge",
        "expected_graph_requirement": "disabled",
        "observed_graph_requirement": "disabled",
        "citation_count": 1,
        "selected_count": 8,
        "live_selected_count": 8,
        "lexical_backend": "bm25",
        "vector_backend": "pgvector_hnsw",
        "vector_degraded": False,
        "streaming_degraded": False,
        "streamed_token_count": 1,
        "counts_match": True,
        "conversation_persisted": True,
        "first_token_ms": 7900.0,
        "elapsed_ms": 29900.0,
        "agent_short_loop_enabled": variant == "phase64",
        "reranking_provider": "zhipu",
        "reranking_model_name": "rerank",
        "retrieval_candidate_cache_enabled": False,
        "rerank_order_cache_enabled": False,
        "tool_result_cache_enabled": False,
        "semantic_evidence_cache_enabled": False,
    }
    row.update(overrides)
    return row


def _passing_judge_summary() -> dict[str, object]:
    return {"paired_quality_lower_bound": 0.0, "loss_rate": 0.0}


def test_pair_order_is_reproducible_and_uses_both_variants() -> None:
    first = [
        deterministic_pair_order(f"case-{index}", run, 640013)
        for index in range(30)
        for run in range(1, 4)
    ]
    second = [
        deterministic_pair_order(f"case-{index}", run, 640013)
        for index in range(30)
        for run in range(1, 4)
    ]

    assert first == second
    assert {pair[0] for pair in first} == {"phase63", "phase64"}


def test_frozen_contract_requires_route_first_only_for_phase64() -> None:
    common = {
        "corpus_fingerprint": "same",
        "document_count": 1,
        "chunk_count": 2,
        "pgvector_search_enabled": True,
        "vector_backend_policy": "require_pgvector",
        "reranking_enabled": True,
        "reranking_provider": "zhipu",
        "reranking_model_name": "rerank",
        "retrieval_candidate_cache_enabled": False,
        "rerank_order_cache_enabled": False,
        "tool_result_cache_enabled": False,
        "semantic_evidence_cache_enabled": False,
        "phase64_execution_graph_schema": "phase64-route-first-v1",
        "phase64_final_non_thinking_enabled": False,
    }
    phase63 = {
        **common,
        "agent_short_loop_enabled": False,
        "phase64_route_first_enabled": False,
        "phase64_retrieval_fanout_enabled": False,
    }
    phase64 = {
        **common,
        "agent_short_loop_enabled": True,
        "phase64_route_first_enabled": True,
        "phase64_retrieval_fanout_enabled": True,
        "phase64_final_non_thinking_enabled": True,
    }

    assert validate_frozen_contract(phase63, phase64)["ok"] is True
    phase64["phase64_final_non_thinking_enabled"] = False
    assert "phase64_final_non_thinking_misconfigured" in validate_frozen_contract(
        phase63,
        phase64,
    )["violations"]
    phase64["phase64_final_non_thinking_enabled"] = True
    phase64["phase64_retrieval_fanout_enabled"] = False
    assert "phase64_fanout_misconfigured" in validate_frozen_contract(phase63, phase64)[
        "violations"
    ]


def test_frozen_contract_requires_official_zhipu_rerank() -> None:
    common = {
        "corpus_fingerprint": "same",
        "document_count": 1,
        "chunk_count": 2,
        "pgvector_search_enabled": True,
        "vector_backend_policy": "require_pgvector",
        "reranking_enabled": True,
        "reranking_provider": "zhipu",
        "reranking_model_name": "rerank",
        "retrieval_candidate_cache_enabled": False,
        "rerank_order_cache_enabled": False,
        "tool_result_cache_enabled": False,
        "semantic_evidence_cache_enabled": False,
        "phase64_execution_graph_schema": "phase64-route-first-v1",
    }
    phase63 = {
        **common,
        "agent_short_loop_enabled": False,
        "phase64_route_first_enabled": False,
        "phase64_retrieval_fanout_enabled": False,
        "phase64_final_non_thinking_enabled": False,
    }
    phase64 = {
        **common,
        "agent_short_loop_enabled": True,
        "phase64_route_first_enabled": True,
        "phase64_retrieval_fanout_enabled": True,
        "phase64_final_non_thinking_enabled": True,
    }

    assert validate_frozen_contract(phase63, phase64)["ok"] is True
    phase63["reranking_provider"] = "paratera"
    phase63["reranking_model_name"] = "GLM-Rerank"
    assert "phase63_reranking_provider_invalid" in validate_frozen_contract(
        phase63, phase64
    )["violations"]


def test_summary_enforces_absolute_latency_and_zero_functional_regression() -> None:
    rows = [
        _row("phase63", "case-1"),
        _row("phase64", "case-1", phase64_route_kind="fast"),
        _row("phase63", "case-2"),
        _row("phase64", "case-2", phase64_route_kind="complex"),
    ]

    summary = build_phase64_summary(
        rows,
        frozen_contract={"ok": True, "violations": []},
        judge_summary=_passing_judge_summary(),
    )

    assert summary["gates"]["first_token_p50"] is True
    assert summary["gates"]["first_token_p95"] is True
    assert summary["gates"]["final_p95"] is True
    assert summary["gates"]["functional_non_regression"] is True
    assert summary["gates_passed"] is True


def test_summary_pairs_component_timings_by_case_and_run_not_list_position() -> None:
    rows = [
        _row(
            "phase63",
            "case-a",
            run=1,
            retrieval_total_latency_ms=10.0,
            glm_rerank_latency_ms=3.0,
        ),
        _row(
            "phase64",
            "case-b",
            run=1,
            retrieval_total_latency_ms=99.0,
            glm_rerank_latency_ms=1.0,
        ),
        _row(
            "phase64",
            "case-a",
            run=1,
            retrieval_total_latency_ms=5.0,
            glm_rerank_latency_ms=2.0,
        ),
        _row(
            "phase63",
            "case-b",
            run=1,
            retrieval_total_latency_ms=20.0,
            glm_rerank_latency_ms=4.0,
        ),
    ]

    summary = build_phase64_summary(
        rows,
        frozen_contract={"ok": True, "violations": []},
        judge_summary=_passing_judge_summary(),
    )

    assert summary["paired_metrics"]["critical_path_delta_p50_ms"] == -6.0
    assert summary["metrics"]["phase63_first_token_p50_ms"] == 7900.0
    assert summary["metrics"]["phase64_first_token_p50_ms"] == 7900.0


def test_summary_requires_functional_non_regression_for_each_route() -> None:
    rows = [
        _row("phase63", "case-fast"),
        _row("phase64", "case-fast", phase64_route_kind="fast"),
        _row("phase63", "case-complex"),
        _row("phase64", "case-complex", phase64_route_kind="complex", ok=False),
    ]

    summary = build_phase64_summary(
        rows,
        frozen_contract={"ok": True, "violations": []},
        judge_summary=_passing_judge_summary(),
    )

    assert summary["gates"]["fast_functional_non_regression"] is True
    assert summary["gates"]["complex_functional_non_regression"] is False
    assert summary["gates_passed"] is False


def test_output_schema_records_execution_graph_without_answer_text() -> None:
    assert "phase64_execution_graph" in PHASE64_OUTPUT_FIELDS
    assert "phase64_route_kind" in PHASE64_OUTPUT_FIELDS


def test_output_schema_excludes_answers_evidence_and_provider_payloads() -> None:
    forbidden = {
        "answer",
        "content",
        "snippet",
        "raw_response",
        "reasoning_content",
        "authorization",
    }

    assert forbidden.isdisjoint(PHASE64_OUTPUT_FIELDS)


def test_phase64_case_set_is_frozen_stratified_and_safe() -> None:
    root = Path(__file__).resolve().parents[1]
    cases_path = root / "data" / "evaluation" / "phase64_latency_cases.csv"
    with cases_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    required_columns = {
        "case_id",
        "category",
        "query",
        "history_json",
        "expected_tool",
        "expected_graph_requirement",
        "minimum_citations",
        "expected_refused",
        "judge_dimension",
    }
    assert len(rows) == 30
    assert len({row["case_id"] for row in rows}) == 30
    assert required_columns.issubset(rows[0])
    assert {
        "ordinary_text",
        "relationship",
        "table",
        "figure",
        "boundary_refusal",
        "followup_text",
        "followup_figure",
        "followup_table",
    }.issubset({row["category"] for row in rows})
    assert all(isinstance(json.loads(row["history_json"]), list) for row in rows)
    assert {"api_key", "authorization", "raw_response", "reasoning_content"}.isdisjoint(
        rows[0]
    )
