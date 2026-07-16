from app.services.agent.tool_result_cache import ToolResultCache
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService
from tests.test_agent_tools import (
    make_session,
    seed_agent_tool_image_documents,
    write_test_image,
)


def assert_tool_result_parity(actual, expected) -> None:
    assert actual.tool_name == expected.tool_name
    assert actual.call == expected.call
    assert actual.search_results == expected.search_results
    assert actual.figure_results == expected.figure_results
    assert actual.sources == expected.sources
    assert actual.refused == expected.refused
    assert actual.refusal_reason == expected.refusal_reason


def test_figure_adapter_matches_frozen_agent_toolbox_result(tmp_path, monkeypatch) -> None:
    from app.services.agent.tool_adapters.figure_search import FigureSearchAdapter

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app.services.agent.tools.get_configured_layered_cache", lambda _layer: None)
    write_test_image(tmp_path / "data" / "images" / "7" / "page12_img1.png")
    write_test_image(tmp_path / "data" / "images" / "7" / "page12_img2.png")
    write_test_image(tmp_path / "data" / "images" / "7" / "page13_img1.png", size=(20, 20))
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_agent_tool_image_documents(db)
        VectorIndexService(db, provider).build_index()
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        adapter = FigureSearchAdapter(
            db=db,
            embedding_provider=provider,
            cache=ToolResultCache(
                db=db,
                embedding_provider=provider,
                cache_factory=lambda _layer: None,
            ),
        )

        expected = toolbox.search_figures("stress strain curve compression failure morphology", top_k=4)
        actual = adapter.search("stress strain curve compression failure morphology", top_k=4)

    assert_tool_result_parity(actual, expected)
