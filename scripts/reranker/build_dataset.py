from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reranker.export_training_pairs import DEFAULT_OUTPUT_DIR, normalize_text  # noqa: E402

DEFAULT_QA_PAIRS = DEFAULT_OUTPUT_DIR / "qa_log_pairs.jsonl"
DEFAULT_SYNTHETIC = DEFAULT_OUTPUT_DIR / "synthetic_queries.jsonl"
DEFAULT_CHUNKS = DEFAULT_OUTPUT_DIR / "sampled_chunks.jsonl"


@dataclass(frozen=True)
class DatasetRow:
    query: str
    passage: str
    label: int
    group_id: str
    source: str
    chunk_id: int
    positive_chunk_id: int
    negative_type: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build RFC reranker train/val/test JSONL datasets.")
    parser.add_argument("--qa-pairs", type=Path, default=DEFAULT_QA_PAIRS)
    parser.add_argument("--synthetic", type=Path, default=DEFAULT_SYNTHETIC)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=51)
    parser.add_argument("--review-sample-size", type=int, default=50)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_dataset(
        qa_pairs_path=args.qa_pairs,
        synthetic_path=args.synthetic,
        chunks_path=args.chunks,
        output_dir=args.output_dir,
        seed=args.seed,
        review_sample_size=args.review_sample_size,
    )
    print("dataset_build " + " ".join(f"{key}={value}" for key, value in summary.items()))


def build_dataset(
    *,
    qa_pairs_path: Path,
    synthetic_path: Path,
    chunks_path: Path,
    output_dir: Path,
    seed: int = 51,
    review_sample_size: int = 50,
) -> dict[str, int]:
    rng = random.Random(seed)
    chunks = {int(row["chunk_id"]): row for row in read_jsonl(chunks_path)}
    positives = collect_positive_examples(qa_pairs_path, synthetic_path)
    rows: list[DatasetRow] = []
    for positive in positives:
        positive_chunk_id = int(positive["chunk_id"])
        query = normalize_text(str(positive["query"]))
        passage = normalize_text(str(positive.get("content", "")))
        if not query or not passage:
            continue
        group_id = stable_group_id(query)
        rows.append(
            DatasetRow(
                query=query,
                passage=passage,
                label=1,
                group_id=group_id,
                source=str(positive.get("source", "")),
                chunk_id=positive_chunk_id,
                positive_chunk_id=positive_chunk_id,
            )
        )
        for negative_type, negative in (
            ("hard", choose_hard_negative(positive, chunks, rng)),
            ("easy", choose_easy_negative(positive, chunks, rng)),
        ):
            if negative is None:
                continue
            rows.append(
                DatasetRow(
                    query=query,
                    passage=normalize_text(str(negative.get("content", ""))),
                    label=0,
                    group_id=group_id,
                    source=str(positive.get("source", "")),
                    chunk_id=int(negative["chunk_id"]),
                    positive_chunk_id=positive_chunk_id,
                    negative_type=negative_type,
                )
            )

    splits = split_by_group(rows, rng)
    output_dir.mkdir(parents=True, exist_ok=True)
    for split_name, split_rows in splits.items():
        write_dataset_jsonl(output_dir / f"reranker_{split_name}.jsonl", split_rows)
    write_review_sample(output_dir / "manual_review_sample.csv", rows, rng, review_sample_size)
    summary = {f"{name}_rows": len(split_rows) for name, split_rows in splits.items()}
    summary["total_rows"] = len(rows)
    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def collect_positive_examples(qa_pairs_path: Path, synthetic_path: Path) -> list[dict[str, object]]:
    positives = [
        row for row in read_jsonl(qa_pairs_path)
        if int(row.get("label", 0) or 0) == 1
    ]
    positives.extend(
        {
            **row,
            "label": 1,
            "source": row.get("source") or "synthetic_llm",
        }
        for row in read_jsonl(synthetic_path)
        if row.get("query") and row.get("content") and row.get("status") in {"completed", "dry_run", None}
    )
    return positives


def choose_hard_negative(
    positive: dict[str, object],
    chunks: dict[int, dict[str, object]],
    rng: random.Random,
) -> dict[str, object] | None:
    positive_chunk_id = int(positive["chunk_id"])
    document_id = int(positive.get("document_id", 0) or 0)
    candidates = [
        row for row in chunks.values()
        if int(row.get("document_id", -1) or -1) == document_id
        and int(row.get("chunk_id", -1) or -1) != positive_chunk_id
    ]
    return rng.choice(candidates) if candidates else None


def choose_easy_negative(
    positive: dict[str, object],
    chunks: dict[int, dict[str, object]],
    rng: random.Random,
) -> dict[str, object] | None:
    positive_chunk_id = int(positive["chunk_id"])
    document_id = int(positive.get("document_id", 0) or 0)
    candidates = [
        row for row in chunks.values()
        if int(row.get("document_id", -1) or -1) != document_id
        and int(row.get("chunk_id", -1) or -1) != positive_chunk_id
    ]
    return rng.choice(candidates) if candidates else None


def split_by_group(rows: list[DatasetRow], rng: random.Random) -> dict[str, list[DatasetRow]]:
    grouped: dict[str, list[DatasetRow]] = defaultdict(list)
    for row in rows:
        grouped[row.group_id].append(row)
    group_ids = list(grouped)
    rng.shuffle(group_ids)
    train_cut = int(len(group_ids) * 0.8)
    val_cut = int(len(group_ids) * 0.9)
    split_groups = {
        "train": set(group_ids[:train_cut]),
        "val": set(group_ids[train_cut:val_cut]),
        "test": set(group_ids[val_cut:]),
    }
    return {
        split_name: [row for group_id in group_ids if group_id in ids for row in grouped[group_id]]
        for split_name, ids in split_groups.items()
    }


def stable_group_id(query: str) -> str:
    import hashlib

    return hashlib.sha256(normalize_text(query).encode("utf-8")).hexdigest()[:16]


def write_dataset_jsonl(path: Path, rows: list[DatasetRow]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            payload = {"query": row.query, "passage": row.passage, "label": row.label}
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_review_sample(path: Path, rows: list[DatasetRow], rng: random.Random, size: int) -> None:
    sample = list(rows)
    rng.shuffle(sample)
    sample = sample[: max(size, 0)]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query",
                "label",
                "negative_type",
                "source",
                "chunk_id",
                "positive_chunk_id",
                "passage",
            ],
        )
        writer.writeheader()
        for row in sample:
            writer.writerow(
                {
                    "query": row.query,
                    "label": row.label,
                    "negative_type": row.negative_type,
                    "source": row.source,
                    "chunk_id": row.chunk_id,
                    "positive_chunk_id": row.positive_chunk_id,
                    "passage": row.passage[:500],
                }
            )


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
