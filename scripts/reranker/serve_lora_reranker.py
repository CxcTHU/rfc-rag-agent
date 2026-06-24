"""Serve the RFC-domain BGE LoRA reranker over an OpenAI-style HTTP API.

This script is intended for the GPU server. It imports torch/transformers only
when starting the service, so local Windows tests can import helper functions
without downloading models or requiring CUDA.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_BASE_MODEL = "BAAI/bge-reranker-base"


@dataclass(frozen=True)
class RerankRequest:
    model: str
    query: str
    documents: list[str]
    top_n: int


@dataclass
class LoraReranker:
    model_path: Path
    base_model: str
    max_length: int
    require_cuda: bool

    def __post_init__(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"model path not found: {self.model_path}")
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Serving LoRA reranker requires torch, transformers, and peft") from exc

        cuda_available = torch.cuda.is_available()
        if self.require_cuda and not cuda_available:
            raise RuntimeError("CUDA is required for this reranker service but is not available")

        device = torch.device("cuda" if cuda_available else "cpu")
        tokenizer_source = self.model_path if (self.model_path / "tokenizer_config.json").exists() else self.base_model
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_source)
        base = AutoModelForSequenceClassification.from_pretrained(self.base_model)
        model = PeftModel.from_pretrained(base, self.model_path)
        model.to(device)
        model.eval()

        self.torch = torch
        self.tokenizer = tokenizer
        self.model = model
        self.device = device
        self.cuda_available = bool(cuda_available)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "model_loaded": True,
            "cuda_available": self.cuda_available,
            "device": str(self.device),
            "model_name": self.base_model,
            "model_path": str(self.model_path),
            "max_length": self.max_length,
        }

    def rerank(self, request: RerankRequest) -> dict[str, Any]:
        started = time.perf_counter()
        encoded = self.tokenizer(
            [request.query] * len(request.documents),
            request.documents,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="pt",
        )
        if hasattr(encoded, "to"):
            encoded = encoded.to(self.device)
        else:
            encoded = {
                key: value.to(self.device) if hasattr(value, "to") else value
                for key, value in encoded.items()
            }
        with self.torch.no_grad():
            scores = self.model(**encoded).logits.reshape(-1).tolist()
        ranked = sorted(
            (
                {
                    "index": index,
                    "relevance_score": float(score),
                }
                for index, score in enumerate(scores)
            ),
            key=lambda item: (-item["relevance_score"], item["index"]),
        )[: request.top_n]
        return {
            "model": request.model,
            "results": ranked,
            "usage": {
                "documents": len(request.documents),
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
            },
        }


class RerankHandler(BaseHTTPRequestHandler):
    server_version = "RFCBgeLoraReranker/1.0"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path.rstrip("/") == "/health":
            self._write_json(200, self.server.reranker.health())  # type: ignore[attr-defined]
            return
        self._write_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path.rstrip("/") not in {"/rerank", "/v1/rerank"}:
            self._write_json(404, {"error": "not_found"})
            return
        try:
            request = parse_rerank_request(self._read_json())
            payload = self.server.reranker.rerank(request)  # type: ignore[attr-defined]
        except ValueError as exc:
            self._write_json(400, {"error": sanitize_error(str(exc))})
            return
        except Exception as exc:  # noqa: BLE001 - service boundary returns sanitized errors
            self._write_json(500, {"error": sanitize_error(str(exc))})
            return
        self._write_json(200, payload)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), format % args))

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("request body is empty")
        raw = self.rfile.read(length).decode("utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def parse_rerank_request(payload: dict[str, Any]) -> RerankRequest:
    model = str(payload.get("model") or "").strip()
    query = str(payload.get("query") or "").strip()
    documents = payload.get("documents")
    top_n = payload.get("top_n", payload.get("top_k", 5))
    if not model:
        raise ValueError("model must not be empty")
    if not query:
        raise ValueError("query must not be empty")
    if not isinstance(documents, list) or not documents:
        raise ValueError("documents must be a non-empty list")
    normalized_documents = [str(document) for document in documents]
    if any(not document.strip() for document in normalized_documents):
        raise ValueError("documents must not contain empty text")
    if not isinstance(top_n, int) or top_n <= 0:
        raise ValueError("top_n must be a positive integer")
    return RerankRequest(
        model=model,
        query=query,
        documents=normalized_documents,
        top_n=min(top_n, len(normalized_documents)),
    )


def sanitize_error(message: str) -> str:
    return message.replace("\n", " ")[:300]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve RFC-domain BGE LoRA reranker.")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--require-cuda", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reranker = LoraReranker(
        model_path=args.model_path,
        base_model=args.base_model,
        max_length=args.max_length,
        require_cuda=args.require_cuda,
    )
    server = ThreadingHTTPServer((args.host, args.port), RerankHandler)
    server.reranker = reranker  # type: ignore[attr-defined]
    print(
        json.dumps(
            {
                "status": "serving",
                "host": args.host,
                "port": args.port,
                "health": reranker.health(),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
