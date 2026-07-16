from app.services.agent.tool_models import AgentToolResult
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from tests.test_agent_tools import make_session
from tests.test_phase47_user_image import make_png_bytes


def test_image_adapter_returns_tool_result_not_agent_query_result(tmp_path, monkeypatch) -> None:
    from app.services.agent.tool_adapters.user_image_analysis import UserImageAnalysisAdapter

    monkeypatch.chdir(tmp_path)
    upload_path = tmp_path / "data" / "user_uploads" / "2026-06-20" / "crack.png"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(make_png_bytes())
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        adapter = UserImageAnalysisAdapter.from_toolbox(toolbox)

        result = adapter.analyze(
            image_path=upload_path.as_posix(),
            question="Does this crack need attention?",
        )

    assert isinstance(result, AgentToolResult)
    assert result.tool_name == "analyze_user_image"


def test_image_adapter_preserves_deterministic_vision_refusal(tmp_path, monkeypatch) -> None:
    from app.services.agent.tool_adapters.user_image_analysis import UserImageAnalysisAdapter

    monkeypatch.chdir(tmp_path)
    upload_path = tmp_path / "data" / "user_uploads" / "2026-06-20" / "crack.png"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(make_png_bytes())
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(dimension=32),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )
        result = UserImageAnalysisAdapter.from_toolbox(toolbox).analyze(
            upload_path.as_posix(),
            "describe it",
        )

    assert result.refused is True
    assert result.image_analysis is not None
    assert result.image_analysis["domain_relevance"] == "test_vision"
    assert "api key" not in (result.refusal_reason or "").lower()
