"""Thin compatibility facade for agent tools.

Phase 66 keeps the historical `app.services.agent.tools` import path stable
while the production tool bodies move into typed adapters and the old toolbox
implementation lives in `legacy_toolbox.py`.
"""

from __future__ import annotations

from app.services.agent import legacy_toolbox as _legacy
from app.services.agent.legacy_toolbox import *  # noqa: F401,F403
from app.services.generation.chat_model import ChatModelProvider
from app.services.retrieval.embedding import EmbeddingProvider
from sqlalchemy.orm import Session


_enrich_results_with_citation_location = _legacy._enrich_results_with_citation_location
_enrich_sources_with_citation_location = _legacy._enrich_sources_with_citation_location
_trace_tool_cache_selected_results = _legacy._trace_tool_cache_selected_results


class AgentToolbox(_legacy.AgentToolbox):
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
        chat_model_provider: ChatModelProvider,
        log_answers: bool = True,
    ) -> None:
        _legacy.get_configured_layered_cache = get_configured_layered_cache
        super().__init__(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=chat_model_provider,
            log_answers=log_answers,
        )
