from __future__ import annotations

import os


def pytest_configure() -> None:
    os.environ["RERANKING_PROVIDER"] = "deterministic"
    os.environ["RERANKING_MODEL_NAME"] = "keyword-overlap-reranker-v1"
    os.environ["RERANKING_API_KEY"] = ""
    os.environ["RERANKING_BASE_URL"] = ""
