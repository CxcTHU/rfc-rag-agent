from __future__ import annotations

import os


def pytest_configure() -> None:
    os.environ["APP_ENV"] = "development"
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["PLANNER_CHAT_MODEL_PROVIDER"] = ""
    os.environ["PLANNER_CHAT_MODEL_NAME"] = ""
    os.environ["PLANNER_CHAT_MODEL_API_KEY"] = ""
    os.environ["PLANNER_CHAT_MODEL_BASE_URL"] = ""
    os.environ["PLANNER_CHAT_MODEL_TEMPERATURE"] = "0"
    os.environ["PLANNER_CHAT_MODEL_TIMEOUT_SECONDS"] = "10"
    os.environ["VISION_MODEL_PROVIDER"] = ""
    os.environ["VISION_MODEL_NAME"] = ""
    os.environ["VISION_MODEL_API_KEY"] = ""
    os.environ["VISION_MODEL_BASE_URL"] = ""
    os.environ["VISION_MODEL_TIMEOUT_SECONDS"] = "30"
    os.environ["RERANKING_PROVIDER"] = "deterministic"
    os.environ["RERANKING_MODEL_NAME"] = "keyword-overlap-reranker-v1"
    os.environ["RERANKING_API_KEY"] = ""
    os.environ["RERANKING_BASE_URL"] = ""


def pytest_runtest_setup() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()
