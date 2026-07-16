from app.services.agent.tool_result_cache import ToolResultCache
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService
from tests.test_agent_tools import make_session, seed_agent_tool_documents


def assert_tool_result_parity(actual, expected) -> None:
    assert actual.tool_name == expected.tool_name
    assert actual.call == expected.call
    assert actual.search_results == expected.search_results
    assert actual.sources == expected.sources
    assert actual.refused == expected.refused
    assert actual.refusal_reason == expected.refusal_reason


def test_hybrid_adapter_matches_frozen_agent_toolbox_result(tmp_path, monkeypatch) -> None:
    from app.services.agent.tool_adapters.hybrid_search import HybridSearchAdapter

    TestingSessionLocal = make_session(tmp_path)
    monkeypatch.setattr("app.services.agent.tools.get_configured_layered_cache", lambda _layer: None)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_agent_tool_documents(db)
        VectorIndexService(db, provider).build_index()
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        adapter = HybridSearchAdapter(
            db=db,
            embedding_provider=provider,
            cache=ToolResultCache(
                db=db,
                embedding_provider=provider,
                cache_factory=lambda _layer: None,
            ),
        )

        expected = toolbox.hybrid_search_knowledge("filling capacity", top_k=3)
        actual = adapter.search("filling capacity", top_k=3)

    assert_tool_result_parity(actual, expected)
