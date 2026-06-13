from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class FaissIndexMetadata:
    provider: str
    model_name: str
    dimension: int
    metric: str
    normalized: bool
    complete: bool
    chunk_ids: tuple[int, ...]


@dataclass(frozen=True)
class FaissSearchMatch:
    chunk_id: int
    score: float


class FaissVectorIndex:
    """Small wrapper around FAISS IndexFlatIP for normalized chunk embeddings."""

    def __init__(self, index: Any, metadata: FaissIndexMetadata) -> None:
        self.index = index
        self.metadata = metadata

    @classmethod
    def build(
        cls,
        embeddings: Sequence[Sequence[float]],
        chunk_ids: Sequence[int],
        provider: str,
        model_name: str,
        dimension: int,
        complete: bool = True,
    ) -> FaissVectorIndex:
        if dimension <= 0:
            raise ValueError("dimension must be greater than 0")
        if len(embeddings) != len(chunk_ids):
            raise ValueError("embeddings and chunk_ids must have the same length")

        matrix = normalize_embeddings(embeddings, dimension=dimension)
        faiss = import_faiss()
        index = faiss.IndexFlatIP(dimension)
        if matrix.size:
            index.add(matrix)
        metadata = FaissIndexMetadata(
            provider=provider,
            model_name=model_name,
            dimension=dimension,
            metric="inner_product",
            normalized=True,
            complete=complete,
            chunk_ids=tuple(int(chunk_id) for chunk_id in chunk_ids),
        )
        return cls(index=index, metadata=metadata)

    @classmethod
    def load(cls, index_path: Path, metadata_path: Path) -> FaissVectorIndex:
        if not index_path.exists():
            raise FileNotFoundError(index_path)
        if not metadata_path.exists():
            raise FileNotFoundError(metadata_path)

        faiss = import_faiss()
        index = faiss.read_index(str(index_path))
        metadata = read_metadata(metadata_path)
        if index.d != metadata.dimension:
            raise ValueError("FAISS index dimension does not match metadata")
        if index.ntotal != len(metadata.chunk_ids):
            raise ValueError("FAISS index row count does not match metadata chunk_ids")
        return cls(index=index, metadata=metadata)

    def save(self, index_path: Path, metadata_path: Path) -> None:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        faiss = import_faiss()
        faiss.write_index(self.index, str(index_path))
        write_metadata(metadata_path, self.metadata)

    def search(self, query_embedding: Sequence[float], top_k: int) -> list[FaissSearchMatch]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        query = normalize_embeddings([query_embedding], dimension=self.metadata.dimension)
        if query.size == 0 or np.all(query == 0):
            return []

        candidate_count = min(top_k, len(self.metadata.chunk_ids))
        if candidate_count == 0:
            return []
        scores, indexes = self.index.search(query, candidate_count)
        matches: list[FaissSearchMatch] = []
        for score, row_index in zip(scores[0], indexes[0], strict=True):
            if row_index < 0:
                continue
            score_value = float(score)
            if score_value <= 0:
                continue
            matches.append(
                FaissSearchMatch(
                    chunk_id=self.metadata.chunk_ids[int(row_index)],
                    score=score_value,
                )
            )
        return matches


def normalize_embeddings(
    embeddings: Sequence[Sequence[float]],
    dimension: int,
) -> np.ndarray:
    if not embeddings:
        return np.empty((0, dimension), dtype=np.float32)

    matrix = np.asarray(embeddings, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[1] != dimension:
        raise ValueError("embedding dimension does not match metadata")
    norms = np.linalg.norm(matrix, axis=1)
    safe_norms = np.where(norms == 0, 1.0, norms)
    normalized = matrix / safe_norms[:, np.newaxis]
    normalized[norms == 0] = 0.0
    return np.ascontiguousarray(normalized, dtype=np.float32)


def default_faiss_paths(
    output_dir: Path,
    provider: str,
    model_name: str,
    dimension: int,
) -> tuple[Path, Path]:
    stem = safe_index_stem(provider=provider, model_name=model_name, dimension=dimension)
    return output_dir / f"{stem}.index", output_dir / f"{stem}_ids.json"


def safe_index_stem(provider: str, model_name: str, dimension: int) -> str:
    raw = f"{provider}_{model_name}_dim{dimension}"
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in raw)


def write_metadata(path: Path, metadata: FaissIndexMetadata) -> None:
    payload = {
        "provider": metadata.provider,
        "model_name": metadata.model_name,
        "dimension": metadata.dimension,
        "metric": metadata.metric,
        "normalized": metadata.normalized,
        "complete": metadata.complete,
        "chunk_ids": list(metadata.chunk_ids),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_metadata(path: Path) -> FaissIndexMetadata:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunk_ids = payload.get("chunk_ids")
    if not isinstance(chunk_ids, list):
        raise ValueError("metadata chunk_ids must be a list")
    return FaissIndexMetadata(
        provider=str(payload["provider"]),
        model_name=str(payload["model_name"]),
        dimension=int(payload["dimension"]),
        metric=str(payload["metric"]),
        normalized=bool(payload["normalized"]),
        complete=bool(payload.get("complete", False)),
        chunk_ids=tuple(int(chunk_id) for chunk_id in chunk_ids),
    )


def import_faiss():
    try:
        import faiss  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only when dependency missing
        raise RuntimeError(
            "faiss-cpu is required for FAISS index operations. Install project dependencies."
        ) from exc
    return faiss
