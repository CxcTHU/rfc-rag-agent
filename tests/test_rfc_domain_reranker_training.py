from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.reranker import train_lora


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def make_args(tmp_path: Path, *, train: Path, val: Path, execute: bool = False) -> Namespace:
    return Namespace(
        train=train,
        val=val,
        output_dir=tmp_path / "model-output",
        base_model="BAAI/bge-reranker-base",
        epochs=1.0,
        batch_size=2,
        lr=2e-5,
        max_length=64,
        lora_r=16,
        lora_alpha=32,
        lora_dropout=0.1,
        resume_from_checkpoint=None,
        dry_run=not execute,
        execute=execute,
    )


def test_train_lora_dry_run_validates_without_training(tmp_path, monkeypatch) -> None:
    train = tmp_path / "train.jsonl"
    val = tmp_path / "val.jsonl"
    rows = [
        {"query": "RFC compaction?", "passage": "Rock-filled concrete compaction evidence.", "label": 1},
        {"query": "RFC compaction?", "passage": "Unrelated arch dam passage.", "label": 0},
    ]
    write_jsonl(train, rows)
    write_jsonl(val, rows)
    called = False

    def fail_training(_args):
        nonlocal called
        called = True
        raise AssertionError("dry-run must not train")

    monkeypatch.setattr(train_lora, "run_training", fail_training)
    args = make_args(tmp_path, train=train, val=val)

    summary = train_lora.prepare_training_run(args)

    assert called is False
    assert summary["mode"] == "dry_run"
    assert summary["config"]["base_model"] == "BAAI/bge-reranker-base"
    assert summary["config"]["lora_r"] == 16
    assert summary["config"]["lora_alpha"] == 32
    assert summary["config"]["lora_dropout"] == 0.1
    assert summary["train"]["rows"] == 2
    assert summary["train"]["labels"] == {"0": 1, "1": 1}


def test_train_lora_rejects_bad_schema_and_label(tmp_path) -> None:
    bad_schema = tmp_path / "bad_schema.jsonl"
    bad_label = tmp_path / "bad_label.jsonl"
    write_jsonl(bad_schema, [{"query": "q", "passage": "p", "label": 1, "extra": "no"}])
    write_jsonl(bad_label, [{"query": "q", "passage": "p", "label": 2}])

    with pytest.raises(ValueError, match="fields must be exactly"):
        train_lora.load_training_jsonl(bad_schema)
    with pytest.raises(ValueError, match="label must be 0 or 1"):
        train_lora.load_training_jsonl(bad_label)


def test_train_lora_reports_length_and_truncation_stats(tmp_path) -> None:
    train = tmp_path / "train.jsonl"
    val = tmp_path / "val.jsonl"
    long_passage = "x" * 120
    rows = [
        {"query": "short", "passage": "short passage", "label": 1},
        {"query": "another", "passage": long_passage, "label": 0},
    ]
    write_jsonl(train, rows)
    write_jsonl(val, rows)
    args = make_args(tmp_path, train=train, val=val)

    summary = train_lora.prepare_training_run(args)

    assert summary["train"]["passage_length"]["max_chars"] == 120
    assert summary["train"]["passage_length"]["truncated_ratio"] == 0.5
    assert summary["train"]["pair_length"]["truncated_ratio"] == 0.5


def test_train_lora_execute_requires_optional_dependencies(tmp_path, monkeypatch) -> None:
    train = tmp_path / "train.jsonl"
    val = tmp_path / "val.jsonl"
    rows = [{"query": "q", "passage": "p", "label": 1}]
    write_jsonl(train, rows)
    write_jsonl(val, rows)
    args = make_args(tmp_path, train=train, val=val, execute=True)

    monkeypatch.setitem(__import__("sys").modules, "torch", None)

    with pytest.raises(RuntimeError, match="optional dependencies"):
        train_lora.run_training(args)
