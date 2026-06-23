from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reranker import evaluate_reranker


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_evaluate_reranker_restores_query_groups_and_metrics(tmp_path) -> None:
    dataset = tmp_path / "reranker_test.jsonl"
    output_dir = tmp_path / "eval"
    write_jsonl(
        dataset,
        [
            {"query": "RFC compaction control?", "passage": "Unrelated weather passage.", "label": 0},
            {"query": "RFC compaction control?", "passage": "RFC compaction quality control evidence.", "label": 1},
            {"query": "RFC hydration heat?", "passage": "RFC hydration heat and temperature control.", "label": 1},
            {"query": "RFC hydration heat?", "passage": "Generic concrete history.", "label": 0},
        ],
    )

    groups = evaluate_reranker.load_query_groups(dataset)
    summary = evaluate_reranker.evaluate_rerankers(
        dataset_path=dataset,
        reranker_names=["none", "deterministic"],
        output_dir=output_dir,
    )

    assert len(groups) == 2
    assert sorted(c.label for c in groups[0].candidates) == [0, 1]
    assert sorted(c.label for c in groups[1].candidates) == [0, 1]
    assert summary["rerankers"]["none"]["completed"] == 2
    assert summary["rerankers"]["deterministic"]["completed"] == 2
    assert (output_dir / "reranker_eval_results.csv").exists()
    assert (output_dir / "reranker_eval_summary.json").exists()


def test_compute_metrics_handles_ranked_positive_at_second_place() -> None:
    ranking = [
        evaluate_reranker.RankedCandidate(original_index=0, score=0.9, label=0),
        evaluate_reranker.RankedCandidate(original_index=1, score=0.8, label=1),
        evaluate_reranker.RankedCandidate(original_index=2, score=0.7, label=0),
    ]

    metrics = evaluate_reranker.compute_metrics(ranking, k=5)

    assert metrics["mrr_at_5"] == 0.5
    assert round(metrics["ndcg_at_5"], 6) == 0.63093
    assert metrics["precision_at_1"] == 0.0


def test_evaluate_reranker_does_not_initialize_real_provider_by_default(monkeypatch) -> None:
    def fail_provider(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("default rerankers must not initialize real provider")

    monkeypatch.setattr(evaluate_reranker, "create_reranking_provider", fail_provider)

    rerankers = evaluate_reranker.build_rerankers(
        ["none", "deterministic"],
        local_lora_model_path=None,
        max_length=128,
        execute=False,
    )

    assert [reranker.name for reranker in rerankers] == ["none", "deterministic"]


def test_evaluate_reranker_rejects_glm_without_execute() -> None:
    with pytest.raises(ValueError, match="glm-rerank requires --execute"):
        evaluate_reranker.build_rerankers(
            ["glm-rerank"],
            local_lora_model_path=None,
            max_length=128,
            execute=False,
        )


def test_evaluate_reranker_local_lora_requires_model_path(tmp_path) -> None:
    with pytest.raises(ValueError, match="local-lora requires"):
        evaluate_reranker.build_rerankers(
            ["local-lora"],
            local_lora_model_path=None,
            max_length=128,
            execute=False,
        )
    with pytest.raises(FileNotFoundError, match="local LoRA model path not found"):
        evaluate_reranker.build_rerankers(
            ["local-lora"],
            local_lora_model_path=tmp_path / "missing-model",
            max_length=128,
            execute=False,
        )


def test_evaluate_reranker_rejects_group_without_positive(tmp_path) -> None:
    dataset = tmp_path / "reranker_test.jsonl"
    write_jsonl(dataset, [{"query": "q", "passage": "p", "label": 0}])

    with pytest.raises(ValueError, match="no positive candidate"):
        evaluate_reranker.load_query_groups(dataset)
