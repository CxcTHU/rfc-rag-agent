"""Prepare and optionally run BGE reranker LoRA fine-tuning.

The default path is a dry-run validator. It reads the train/validation JSONL,
checks schema and label balance, prints a compact summary, and exits without
importing ML libraries or downloading a model. Real training requires
``--execute``.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reranker.export_training_pairs import DEFAULT_OUTPUT_DIR, normalize_text  # noqa: E402

DEFAULT_TRAIN = DEFAULT_OUTPUT_DIR / "reranker_train.jsonl"
DEFAULT_VAL = DEFAULT_OUTPUT_DIR / "reranker_val.jsonl"
DEFAULT_MODEL_OUTPUT_DIR = ROOT / "models" / "bge-reranker-base-rfc-lora"
DEFAULT_BASE_MODEL = "BAAI/bge-reranker-base"
REQUIRED_FIELDS = {"query", "passage", "label"}


@dataclass(frozen=True)
class TrainingExample:
    query: str
    passage: str
    label: int


@dataclass(frozen=True)
class LengthStats:
    min_chars: int
    max_chars: int
    avg_chars: float
    p50_chars: int
    p90_chars: int
    truncated_ratio: float


@dataclass(frozen=True)
class DatasetSummary:
    path: str
    rows: int
    labels: dict[str, int]
    query_length: LengthStats
    passage_length: LengthStats
    pair_length: LengthStats


@dataclass(frozen=True)
class TrainingConfig:
    base_model: str
    output_dir: str
    epochs: float
    batch_size: int
    lr: float
    max_length: int
    lora_r: int
    lora_alpha: int
    lora_dropout: float
    resume_from_checkpoint: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate or train RFC-DomainReranker LoRA adapter.")
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--val", type=Path, default=DEFAULT_VAL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MODEL_OUTPUT_DIR)
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.1)
    parser.add_argument("--resume-from-checkpoint", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs only. This is the default.")
    parser.add_argument("--execute", action="store_true", help="Run real model download/training.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = prepare_training_run(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.execute:
        run_training(args)


def prepare_training_run(args: argparse.Namespace) -> dict[str, Any]:
    validate_training_config(args)
    train_examples = load_training_jsonl(args.train)
    val_examples = load_training_jsonl(args.val)
    config = TrainingConfig(
        base_model=args.base_model,
        output_dir=str(args.output_dir),
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        max_length=args.max_length,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        resume_from_checkpoint=str(args.resume_from_checkpoint) if args.resume_from_checkpoint else None,
    )
    return {
        "mode": "execute" if args.execute else "dry_run",
        "config": asdict(config),
        "train": asdict(summarize_dataset(args.train, train_examples, args.max_length)),
        "val": asdict(summarize_dataset(args.val, val_examples, args.max_length)),
    }


def validate_training_config(args: argparse.Namespace) -> None:
    if args.execute and args.dry_run:
        raise ValueError("--dry-run and --execute cannot be used together")
    if args.epochs <= 0:
        raise ValueError("--epochs must be greater than 0")
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be greater than 0")
    if args.lr <= 0:
        raise ValueError("--lr must be greater than 0")
    if args.max_length <= 0:
        raise ValueError("--max-length must be greater than 0")
    if args.lora_r <= 0:
        raise ValueError("--lora-r must be greater than 0")
    if args.lora_alpha <= 0:
        raise ValueError("--lora-alpha must be greater than 0")
    if not 0 <= args.lora_dropout < 1:
        raise ValueError("--lora-dropout must be in [0, 1)")
    ensure_safe_output_dir(args.output_dir)


def load_training_jsonl(path: Path) -> list[TrainingExample]:
    if not path.exists():
        raise FileNotFoundError(f"training file not found: {path}")
    rows: list[TrainingExample] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON") from exc
            rows.append(validate_training_row(payload, path=path, line_number=line_number))
    if not rows:
        raise ValueError(f"{path} contains no training rows")
    return rows


def validate_training_row(payload: object, *, path: Path, line_number: int) -> TrainingExample:
    if not isinstance(payload, dict):
        raise ValueError(f"{path}:{line_number} must be a JSON object")
    fields = set(payload)
    if fields != REQUIRED_FIELDS:
        raise ValueError(f"{path}:{line_number} fields must be exactly {sorted(REQUIRED_FIELDS)}")
    query = normalize_text(str(payload["query"]))
    passage = normalize_text(str(payload["passage"]))
    if not query:
        raise ValueError(f"{path}:{line_number} query must not be empty")
    if not passage:
        raise ValueError(f"{path}:{line_number} passage must not be empty")
    label = payload["label"]
    if isinstance(label, bool) or not isinstance(label, int) or label not in {0, 1}:
        raise ValueError(f"{path}:{line_number} label must be 0 or 1")
    return TrainingExample(query=query, passage=passage, label=label)


def summarize_dataset(path: Path, examples: list[TrainingExample], max_length: int) -> DatasetSummary:
    label_counts = Counter(example.label for example in examples)
    return DatasetSummary(
        path=str(path),
        rows=len(examples),
        labels={str(label): label_counts.get(label, 0) for label in (0, 1)},
        query_length=summarize_lengths([len(example.query) for example in examples], max_length=max_length),
        passage_length=summarize_lengths([len(example.passage) for example in examples], max_length=max_length),
        pair_length=summarize_lengths(
            [len(example.query) + len(example.passage) for example in examples],
            max_length=max_length,
        ),
    )


def summarize_lengths(lengths: list[int], *, max_length: int) -> LengthStats:
    ordered = sorted(lengths)
    return LengthStats(
        min_chars=ordered[0],
        max_chars=ordered[-1],
        avg_chars=round(mean(ordered), 3),
        p50_chars=percentile(ordered, 50),
        p90_chars=percentile(ordered, 90),
        truncated_ratio=round(sum(length > max_length for length in ordered) / len(ordered), 6),
    )


def percentile(sorted_values: list[int], percent: int) -> int:
    if not sorted_values:
        return 0
    index = math.ceil((percent / 100) * len(sorted_values)) - 1
    return sorted_values[min(max(index, 0), len(sorted_values) - 1)]


def ensure_safe_output_dir(path: Path) -> None:
    resolved = path.resolve()
    try:
        relative_path = resolved.relative_to(ROOT)
    except ValueError:
        return
    candidates = [relative_path.as_posix(), relative_path.as_posix().rstrip("/") + "/"]
    is_ignored = any(
        subprocess.run(
            ["git", "check-ignore", "-q", candidate],
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
        for candidate in candidates
    )
    if not is_ignored:
        raise ValueError(f"output dir must be gitignored when it is inside the repo: {path}")


def run_training(args: argparse.Namespace) -> None:
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Real LoRA training requires optional dependencies: torch, transformers, datasets, peft"
        ) from exc

    train_examples = load_training_jsonl(args.train)
    val_examples = load_training_jsonl(args.val)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        raise RuntimeError("Real LoRA training requires a CUDA GPU; dry-run works on CPU")

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(args.base_model, num_labels=1)
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.SEQ_CLS,
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            bias="none",
        ),
    )

    def tokenize_batch(batch: dict[str, list[Any]]) -> dict[str, Any]:
        return tokenizer(
            batch["query"],
            batch["passage"],
            truncation=True,
            max_length=args.max_length,
            padding="max_length",
        )

    train_dataset = Dataset.from_list([asdict(example) for example in train_examples]).map(
        tokenize_batch,
        batched=True,
        remove_columns=["query", "passage"],
    )
    val_dataset = Dataset.from_list([asdict(example) for example in val_examples]).map(
        tokenize_batch,
        batched=True,
        remove_columns=["query", "passage"],
    )

    def rename_labels(example: dict[str, Any]) -> dict[str, Any]:
        example["labels"] = float(example.pop("label"))
        return example

    train_dataset = train_dataset.map(rename_labels)
    val_dataset = val_dataset.map(rename_labels)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        logging_steps=20,
        fp16=torch.cuda.is_available(),
        report_to=[],
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
    )
    trainer.train(resume_from_checkpoint=str(args.resume_from_checkpoint) if args.resume_from_checkpoint else None)
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    (args.output_dir / "training_config_summary.json").write_text(
        json.dumps(prepare_training_run(args)["config"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
