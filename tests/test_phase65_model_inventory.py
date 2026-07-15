from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.health import (
    phase65_model_inventory,
    phase65_usage_receipt_inventory_value,
    retrieval_endpoint_identity_sha256,
    supports_phase65_cold_run_receipts,
)
from scripts.evaluate_phase65_agent_gate import (
    _build_manifest,
    _build_receipt_contract,
    _provider_model_receipts,
)


def _settings(**changes: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "app_name": "RFC-RAG-Agent",
        "app_env": "test",
        "chat_model_provider": "openai-compatible",
        "chat_model_name": "primary-chat",
        "planner_chat_model_provider": "planner-compatible",
        "planner_chat_model_name": "independent-planner",
        "runtime_identity_model_provider": "runtime-compatible",
        "runtime_identity_model_name": "independent-runtime",
        "embedding_provider": "embedding",
        "embedding_model_name": "embedding-v1",
        "embedding_dimension": 8,
        "reranking_provider": "reranker",
        "reranking_model_name": "reranker-v1",
        "retrieval_runtime_schema": "runtime-v1",
        "phase64_execution_graph_schema": "phase64-v1",
        "retrieval_runtime_enabled": True,
        "pgvector_search_enabled": True,
        "reranking_enabled": True,
        "retrieval_candidate_cache_enabled": True,
        "rerank_order_cache_enabled": True,
        "tool_result_cache_enabled": True,
        "semantic_evidence_cache_enabled": False,
        "phase65_cold_run_receipts_enabled": True,
        "phase65_provider_usage_receipts_verified": True,
        "phase65_provider_usage_receipt_inventory": "",
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _contract(settings: SimpleNamespace) -> dict[str, object]:
    return {
        "phase65_model_inventory": [entry.as_safe_dict() for entry in phase65_model_inventory(settings)],
        "corpus_fingerprint": "safe-corpus",
        "index_fingerprint_sha256": "a" * 64,
    }


def test_unverified_independent_planner_blocks_health_and_manifest_receipts() -> None:
    settings = _settings()
    entries = phase65_model_inventory(settings)
    chat_only = phase65_usage_receipt_inventory_value(
        [entry for entry in entries if entry.path == "chat"]
    )
    settings.phase65_provider_usage_receipt_inventory = chat_only

    assert supports_phase65_cold_run_receipts(settings) is False
    with pytest.raises(ValueError, match="phase65_model_inventory_unverified"):
        _provider_model_receipts(_contract(settings))
    with pytest.raises(ValueError, match="phase65_model_inventory_unverified"):
        _build_manifest(
            variant="baseline",
            expected_rows=1,
            completed_rows=1,
            cases=[
                {"case_id": "case-1", "category": "ordinary_text"},
                {"case_id": "case-2", "category": "ordinary_text"},
            ],
            receipt_contract=_build_receipt_contract(
                [
                    {"case_id": "case-1", "category": "ordinary_text"},
                    {"case_id": "case-2", "category": "ordinary_text"},
                ],
                runs=1,
                seed=65,
            ),
            endpoint_identity_sha256="b" * 64,
            contract=_contract(settings),
            environment_class="real_provider",
        )


def test_verified_full_inventory_allows_health_and_manifest_receipts() -> None:
    settings = _settings()
    settings.phase65_provider_usage_receipt_inventory = phase65_usage_receipt_inventory_value(
        phase65_model_inventory(settings)
    )

    assert supports_phase65_cold_run_receipts(settings) is True
    receipts = _provider_model_receipts(_contract(settings))

    assert {receipt.split(":", 1)[0] for receipt in receipts} == {
        "chat",
        "planner",
        "runtime_identity",
    }
    assert all(receipt.split(":", 1)[1].startswith("sha256:") for receipt in receipts)


def test_endpoint_identity_binds_each_enabled_model_path_without_leaking_configuration() -> None:
    settings = _settings()
    settings.phase65_provider_usage_receipt_inventory = phase65_usage_receipt_inventory_value(
        phase65_model_inventory(settings)
    )
    before = retrieval_endpoint_identity_sha256(settings, "corpus")
    settings.runtime_identity_model_name = "rotated-runtime"
    after = retrieval_endpoint_identity_sha256(settings, "corpus")

    assert before != after
    inventory = [entry.as_safe_dict() for entry in phase65_model_inventory(settings)]
    assert all("provider" not in entry and "model" not in entry for entry in inventory)
    assert all("base_url" not in entry and "api_key" not in entry for entry in inventory)


def test_endpoint_identity_can_bind_safe_operator_lane_label() -> None:
    settings = _settings()

    baseline = retrieval_endpoint_identity_sha256(settings, "corpus")
    candidate = retrieval_endpoint_identity_sha256(
        _settings(phase65_endpoint_identity_label="candidate"),
        "corpus",
    )

    assert baseline != candidate
