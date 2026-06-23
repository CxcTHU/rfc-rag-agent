"""Offline RFC reranker evaluation.

The default configurations are fully local: ``none`` preserves candidate order
and ``deterministic`` uses the project's keyword-overlap reranker. Real API
reranking requires ``--execute``; local LoRA evaluation requires an explicit
model path.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.retrieval.reranking import (  # noqa: E402
    DeterministicReRankingProvider,
    ReRankResult,
    create_reranking_provider,
)
from scripts.reranker.export_training_pairs import DEFAULT_OUTPUT_DIR, normalize_text  # noqa: E402
from scripts.reranker.train_lora import REQUIRED_FIELDS, validate_training_row  # noqa: E402

DEFAULT_TEST = DEFAULT_OUTPUT_DIR / "reranker_test.jsonl"
DEFAULT_RESULTS = DEFAULT_OUTPUT_DIR / "reranker_eval_results.csv"
DEFAULT_SUMMARY = DEFAULT_OUTPUT_DIR / "reranker_eval_summary.json"
DEFAULT_RERANKERS = ["none", "deterministic"]


@dataclass(frozen=True)
class Candidate:
    index: int
    passage: str
    label: int


@dataclass(frozen=True)
class QueryGroup:
    query: str
    candidates: list[Candidate]


@dataclass(frozen=True)
class RankedCandidate:
    original_index: int
    score: float
    label: int


class OfflineReranker(Protocol):
    name: str

    def rerank(self, query: str, candidates: list[Candidate]) -> list[RankedCandidate]:
        """Return candidates sorted from most to least relevant."""


@dataclass(frozen=True)
class NoneReranker:
    name: str = "none"

    def rerank(self, query: str, candidates: list[Candidate]) -> list[RankedCandidate]:
        return [
            RankedCandidate(original_index=candidate.index, score=float(-candidate.index), label=candidate.label)
            for candidate in candidates
        ]


@dataclass(frozen=True)
class DeterministicOfflineReranker:
    name: str = "deterministic"

    def rerank(self, query: str, candidates: list[Candidate]) -> list[RankedCandidate]:
        provider = DeterministicReRankingProvider()
        results = provider.rerank(query, [candidate.passage for candidate in candidates], top_k=len(candidates))
        return convert_rerank_results(results, candidates)


@dataclass(frozen=True)
class ProviderOfflineReranker:
    name: str
    provider: Any

    def rerank(self, query: str, candidates: list[Candidate]) -> list[RankedCandidate]:
        results = self.provider.rerank(query, [candidate.passage for candidate in candidates], top_k=len(candidates))
        return convert_rerank_results(results, candidates)


@dataclass(frozen=True)
class LocalLoraReranker:
    model_path: Path
    max_length: int
    name: str = "local-lora"
    _tokenizer: Any = field(init=False, repr=False)
    _model: Any = field(init=False, repr=False)
    _device: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"local LoRA model path not found: {self.model_path}")
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("local-lora evaluation requires torch and transformers") from exc

        tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()
        object.__setattr__(self, "_tokenizer", tokenizer)
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_device", device)

    def rerank(self, query: str, candidates: list[Candidate]) -> list[RankedCandidate]:
        import torch

        encoded = self._tokenizer(
            [query] * len(candidates),
            [candidate.passage for candidate in candidates],
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="pt",
        )
        if hasattr(encoded, "to"):
            encoded = encoded.to(self._device)
        else:
            encoded = {
                key: value.to(self._device) if hasattr(value, "to") else value
                for key, value in encoded.items()
            }
        with torch.no_grad():
            logits = self._model(**encoded).logits.reshape(-1).tolist()
        ranked = [
            RankedCandidate(original_index=candidate.index, score=float(score), label=candidate.label)
            for candidate, score in zip(candidates, logits, strict=True)
        ]
        return sorted(ranked, key=lambda item: (-item.score, item.original_index))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RFC reranker candidates offline.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--rerankers", nargs="+", default=list(DEFAULT_RERANKERS))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--local-lora-model-path", type=Path)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--execute", action="store_true", help="Allow real API rerank provider calls.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = evaluate_rerankers(
        dataset_path=args.dataset,
        reranker_names=args.rerankers,
        output_dir=args.output_dir,
        local_lora_model_path=args.local_lora_model_path,
        max_length=args.max_length,
        execute=args.execute,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def evaluate_rerankers(
    *,
    dataset_path: Path,
    reranker_names: list[str],
    output_dir: Path,
    local_lora_model_path: Path | None = None,
    max_length: int = 512,
    execute: bool = False,
) -> dict[str, Any]:
    groups = load_query_groups(dataset_path)
    rerankers = build_rerankers(
        reranker_names,
        local_lora_model_path=local_lora_model_path,
        max_length=max_length,
        execute=execute,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    result_rows: list[dict[str, Any]] = []
    for reranker in rerankers:
        for group_index, group in enumerate(groups, start=1):
            started = time.perf_counter()
            try:
                ranking = reranker.rerank(group.query, group.candidates)
                latency_ms = (time.perf_counter() - started) * 1000
                metrics = compute_metrics(ranking, k=5)
                result_rows.append(
                    {
                        "reranker": reranker.name,
                        "query_id": stable_query_id(group.query),
                        "group_index": group_index,
                        "candidate_count": len(group.candidates),
                        "positive_count": sum(candidate.label for candidate in group.candidates),
                        "mrr_at_5": metrics["mrr_at_5"],
                        "ndcg_at_5": metrics["ndcg_at_5"],
                        "precision_at_1": metrics["precision_at_1"],
                        "latency_ms": round(latency_ms, 3),
                        "top_original_index": ranking[0].original_index if ranking else "",
                        "top_label": ranking[0].label if ranking else "",
                        "status": "completed",
                        "error": "",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                latency_ms = (time.perf_counter() - started) * 1000
                result_rows.append(
                    {
                        "reranker": reranker.name,
                        "query_id": stable_query_id(group.query),
                        "group_index": group_index,
                        "candidate_count": len(group.candidates),
                        "positive_count": sum(candidate.label for candidate in group.candidates),
                        "mrr_at_5": 0.0,
                        "ndcg_at_5": 0.0,
                        "precision_at_1": 0.0,
                        "latency_ms": round(latency_ms, 3),
                        "top_original_index": "",
                        "top_label": "",
                        "status": "error",
                        "error": sanitize_error(str(exc)),
                    }
                )
    write_results_csv(output_dir / DEFAULT_RESULTS.name, result_rows)
    summary = summarize_results(result_rows)
    (output_dir / DEFAULT_SUMMARY.name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def load_query_groups(path: Path) -> list[QueryGroup]:
    if not path.exists():
        raise FileNotFoundError(f"evaluation dataset not found: {path}")
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if set(payload) != REQUIRED_FIELDS:
                raise ValueError(f"{path}:{line_number} fields must be exactly {sorted(REQUIRED_FIELDS)}")
            row = validate_training_row(payload, path=path, line_number=line_number)
            grouped[row.query].append(
                Candidate(index=len(grouped[row.query]), passage=row.passage, label=row.label)
            )
    groups = [QueryGroup(query=query, candidates=candidates) for query, candidates in grouped.items()]
    if not groups:
        raise ValueError(f"{path} contains no evaluation rows")
    for group in groups:
        if not any(candidate.label == 1 for candidate in group.candidates):
            raise ValueError(f"query group has no positive candidate: {stable_query_id(group.query)}")
    return shuffle_candidates(groups)


def shuffle_candidates(groups: list[QueryGroup]) -> list[QueryGroup]:
    """Deterministic per-query shuffle so positives don't always sit at index 0."""
    shuffled: list[QueryGroup] = []
    for group in groups:
        seed = int(hashlib.sha256(group.query.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed)
        candidates = list(group.candidates)
        rng.shuffle(candidates)
        reindexed = [
            Candidate(index=new_index, passage=c.passage, label=c.label)
            for new_index, c in enumerate(candidates)
        ]
        shuffled.append(QueryGroup(query=group.query, candidates=reindexed))
    return shuffled


def build_rerankers(
    names: list[str],
    *,
    local_lora_model_path: Path | None,
    max_length: int,
    execute: bool,
) -> list[OfflineReranker]:
    rerankers: list[OfflineReranker] = []
    for raw_name in names:
        name = raw_name.strip().casefold()
        if name == "none":
            rerankers.append(NoneReranker())
        elif name == "deterministic":
            rerankers.append(DeterministicOfflineReranker())
        elif name == "local-lora":
            if local_lora_model_path is None:
                raise ValueError("local-lora requires --local-lora-model-path")
            rerankers.append(LocalLoraReranker(local_lora_model_path, max_length=max_length))
        elif name == "glm-rerank":
            if not execute:
                raise ValueError("glm-rerank requires --execute")
            settings = get_settings()
            provider = create_reranking_provider(
                provider_name=settings.reranking_provider,
                model_name=settings.reranking_model_name,
                api_key=settings.reranking_api_key,
                base_url=settings.reranking_base_url,
                timeout_seconds=settings.reranking_timeout_seconds,
            )
            if provider is None:
                raise ValueError("glm-rerank provider is disabled")
            rerankers.append(ProviderOfflineReranker(name="glm-rerank", provider=provider))
        else:
            raise ValueError(f"unsupported reranker: {raw_name}")
    return rerankers


def convert_rerank_results(results: list[ReRankResult], candidates: list[Candidate]) -> list[RankedCandidate]:
    return [
        RankedCandidate(
            original_index=result.index,
            score=result.score,
            label=candidates[result.index].label,
        )
        for result in results
    ]


def compute_metrics(ranking: list[RankedCandidate], *, k: int = 5) -> dict[str, float]:
    top_k = ranking[:k]
    first_positive_rank = next((index + 1 for index, item in enumerate(top_k) if item.label == 1), None)
    dcg = sum((2**item.label - 1) / math.log2(index + 2) for index, item in enumerate(top_k))
    ideal_labels = sorted((item.label for item in ranking), reverse=True)[:k]
    ideal_dcg = sum((2**label - 1) / math.log2(index + 2) for index, label in enumerate(ideal_labels))
    return {
        "mrr_at_5": round((1.0 / first_positive_rank) if first_positive_rank else 0.0, 6),
        "ndcg_at_5": round((dcg / ideal_dcg) if ideal_dcg else 0.0, 6),
        "precision_at_1": 1.0 if ranking and ranking[0].label == 1 else 0.0,
    }


def summarize_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_reranker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_reranker[str(row["reranker"])].append(row)
    summary: dict[str, Any] = {"rerankers": {}}
    for reranker, reranker_rows in by_reranker.items():
        completed = [row for row in reranker_rows if row["status"] == "completed"]
        summary["rerankers"][reranker] = {
            "queries": len(reranker_rows),
            "completed": len(completed),
            "errors": len(reranker_rows) - len(completed),
            "mrr_at_5": average_metric(completed, "mrr_at_5"),
            "ndcg_at_5": average_metric(completed, "ndcg_at_5"),
            "precision_at_1": average_metric(completed, "precision_at_1"),
            "avg_latency_ms": average_metric(completed, "latency_ms"),
        }
    return summary


def average_metric(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row[key]) for row in rows) / len(rows), 6)


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "reranker",
        "query_id",
        "group_index",
        "candidate_count",
        "positive_count",
        "mrr_at_5",
        "ndcg_at_5",
        "precision_at_1",
        "latency_ms",
        "top_original_index",
        "top_label",
        "status",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def stable_query_id(query: str) -> str:
    return hashlib.sha256(normalize_text(query).encode("utf-8")).hexdigest()[:16]


def sanitize_error(message: str) -> str:
    return message.replace("\n", " ")[:300]


if __name__ == "__main__":
    main()
