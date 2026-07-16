from app.services.agent import tool_models
from app.services.agent import tools
from app.services.agent.tool_models import AgentToolCallRecord, AgentToolResult
from app.services.agent.tool_result_cache import ToolResultCache
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider


def test_tools_module_reexports_canonical_result_models() -> None:
    assert tools.AgentToolResult is tool_models.AgentToolResult
    assert tools.AgentSearchItem is tool_models.AgentSearchItem
    assert tools.AgentSourceReference is tool_models.AgentSourceReference
    assert tools.AgentToolCallRecord is tool_models.AgentToolCallRecord


def test_cache_identity_is_stable_for_equivalent_queries() -> None:
    cache = ToolResultCache(db=None, embedding_provider=None)

    first = cache.identity("hybrid_search_knowledge", " RFC 9110 ", 8)
    second = cache.identity("hybrid_search_knowledge", "RFC 9110", 8)

    assert first == second


def test_cache_round_trip_restores_result_when_backend_disabled() -> None:
    cache = ToolResultCache(db=None, embedding_provider=None)
    result = AgentToolResult(
        tool_name="search_tables",
        call=AgentToolCallRecord(
            tool_name="search_tables",
            input_summary="status codes",
            output_summary="1 result",
            succeeded=True,
        ),
    )

    cache.store("search_tables", "status codes", 6, result)

    assert cache.lookup("search_tables", "status codes", 6) == result


def test_cache_uses_injected_backend_factory_for_sql_backed_cache() -> None:
    seen_layers: list[str] = []

    def disabled_cache(layer: str) -> None:
        seen_layers.append(layer)
        return None

    cache = ToolResultCache(
        db=object(),
        embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        cache_factory=disabled_cache,
    )

    assert cache.lookup("hybrid_search_knowledge", "RFC 9110", 3) is None
    assert seen_layers == ["tool"]


def test_agent_toolbox_delegates_cache_identity_to_extracted_cache() -> None:
    toolbox = AgentToolbox(
        db=None,
        embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        chat_model_provider=DeterministicChatModelProvider(),
        log_answers=False,
    )

    assert isinstance(toolbox._tool_result_cache, ToolResultCache)
    assert toolbox._tool_cache_identity("hybrid_search_knowledge", " RFC 9110 ", 8) == (
        toolbox._tool_result_cache.identity("hybrid_search_knowledge", " RFC 9110 ", 8)
    )
