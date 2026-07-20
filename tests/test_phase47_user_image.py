from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.main import create_app
from app.services.agent.image_storage import (
    ImageStorageError,
    ImageTooLargeError,
    UserImageStorage,
)
from app.services.agent.tools import AgentToolbox
from app.services.agent.image_analysis import (
    UserImageAnalyzer,
    assess_image_domain_relevance,
    build_concise_image_answer,
)
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


def make_png_bytes(size=(32, 32), color=(80, 80, 80)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", size, color=color).save(stream, format="PNG")
    return stream.getvalue()


def make_session(tmp_path):
    database_path = tmp_path / "phase47_user_image.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_image_analysis_corpus(db, tmp_path: Path) -> None:
    image_path = tmp_path / "data" / "images" / "1" / "page2_img1.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(make_png_bytes())
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Crack Inspection",
            source_type="local_file",
            source_path="crack.pdf",
            file_name="crack.pdf",
            file_extension=".pdf",
            content_hash="phase47-user-image",
            raw_path="data/raw/crack.pdf",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Concrete crack inspection considers crack width, continuity, leakage, and structural context.",
                char_count=91,
                heading_path="Crack inspection",
                start_char=0,
                end_char=91,
            ),
            ChunkCreate(
                chunk_index=1,
                content="concrete crack defect photograph with visible leakage trace",
                char_count=58,
                heading_path="Figure",
                start_char=None,
                end_char=None,
                chunk_type="image_description",
                source_image_path="data/images/1/page2_img1.png",
                caption="Concrete crack figure",
                page_number=2,
            ),
        ],
    )


def test_user_image_storage_saves_and_validates_upload(tmp_path) -> None:
    storage = UserImageStorage(base_dir=tmp_path / "uploads", max_size_mb=1)
    stored = storage.save_bytes(
        make_png_bytes(),
        filename="crack.png",
        content_type="image/png",
    )

    assert Path(stored.path).exists()
    assert storage.validate_existing_upload_path(stored.path).exists()


def test_user_image_storage_rejects_bad_inputs(tmp_path) -> None:
    storage = UserImageStorage(base_dir=tmp_path / "uploads", max_size_mb=0.00001)

    try:
        storage.save_bytes(make_png_bytes(), filename="crack.png", content_type="image/png")
    except ImageTooLargeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("oversized upload was accepted")

    try:
        UserImageStorage(base_dir=tmp_path / "uploads").save_bytes(
            b"not image",
            filename="notes.txt",
            content_type="text/plain",
        )
    except ImageStorageError:
        pass
    else:  # pragma: no cover
        raise AssertionError("non-image upload was accepted")


def test_upload_image_api_stores_valid_image(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/agent/upload-image",
            files={"file": ("crack.png", make_png_bytes(), "image/png")},
        )
    get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"].startswith("data/user_uploads/")
    assert (tmp_path / payload["path"]).exists()


def test_agent_toolbox_analyze_user_image_flags_deterministic_vision_as_test_mode(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    upload_path = tmp_path / "data" / "user_uploads" / "2026-06-20" / "crack.png"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(make_png_bytes())
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_image_analysis_corpus(db, tmp_path)
        embedding_provider = DeterministicEmbeddingProvider(dimension=64)
        VectorIndexService(db, embedding_provider).build_index()
        result = AgentToolbox(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        ).analyze_user_image(upload_path.as_posix(), "Does this crack need attention?", top_k=3)

    assert result.call.succeeded
    assert result.refused is True
    assert result.sources == []
    assert result.search_results == []
    assert result.answer == ""
    assert result.refusal_reason is not None
    assert result.image_analysis is not None
    assert result.image_analysis["is_test_vision"] is True
    assert result.image_analysis["vision_provider"] == "deterministic"
    assert result.image_analysis["domain_relevance"] == "test_vision"


def test_assess_image_domain_relevance_uses_description_and_question() -> None:
    assert assess_image_domain_relevance("a concrete crack on a dam face", "") == "in_scope"
    assert assess_image_domain_relevance("a cat on a sofa", "what is this?") == "out_of_scope"
    assert (
        assess_image_domain_relevance(
            "a cat on a sofa",
            "Use this animal photo to retrieve RFC concrete crack evidence.",
        )
        == "out_of_scope"
    )
    assert assess_image_domain_relevance("无法判断图片内容", "") == "uncertain"


def test_user_image_analyzer_refuses_out_of_scope_without_retrieval(tmp_path) -> None:
    calls = {"knowledge": 0, "figures": 0}

    class StaticVisionProvider:
        provider_name = "real-ish"
        model_name = "static"

        def describe_image(self, image_path, prompt=None):
            return "a kitchen table with fruit and a coffee cup"

    def knowledge_searcher(_query, _top_k):
        calls["knowledge"] += 1
        raise AssertionError("knowledge search should not run")

    def figure_searcher(_query, _top_k):
        calls["figures"] += 1
        raise AssertionError("figure search should not run")

    image_path = tmp_path / "upload.png"
    image_path.write_bytes(make_png_bytes())
    result = UserImageAnalyzer(
        vision_provider=StaticVisionProvider(),
        knowledge_searcher=knowledge_searcher,
        figure_searcher=figure_searcher,
    ).analyze(image_path, "what is this image?")

    assert result.domain_relevance == "out_of_scope"
    assert result.refusal_reason is not None
    assert result.search_results == []
    assert result.sources == []
    assert calls == {"knowledge": 0, "figures": 0}


def test_user_image_analyzer_retrieves_only_after_domain_gate(tmp_path) -> None:
    calls = {"knowledge": 0, "figures": 0}

    class StaticVisionProvider:
        provider_name = "real-ish"
        model_name = "static"

        def describe_image(self, image_path, prompt=None):
            return "a concrete crack on a hydraulic dam face with leakage trace"

    def knowledge_searcher(_query, _top_k):
        calls["knowledge"] += 1
        return type("ToolResult", (), {"search_results": ["text"], "sources": ["source"]})()

    def figure_searcher(_query, _top_k):
        calls["figures"] += 1
        figure = SimpleNamespace(
            relevance_score=0.91,
            chunk_id=1,
            document_title="Dam inspection",
            page_number=3,
            caption="Concrete crack",
            description_snippet="hydraulic concrete crack with leakage",
        )
        figure_item = SimpleNamespace(chunk_id=1)
        return type(
            "ToolResult",
            (),
            {"figure_results": [figure], "search_results": [figure_item], "sources": []},
        )()

    image_path = tmp_path / "upload.png"
    image_path.write_bytes(make_png_bytes())
    result = UserImageAnalyzer(
        vision_provider=StaticVisionProvider(),
        knowledge_searcher=knowledge_searcher,
        figure_searcher=figure_searcher,
    ).analyze(image_path, "does this concrete crack need attention?")

    assert result.domain_relevance == "in_scope"
    assert result.refusal_reason is None
    assert result.related_text_chunks == ["text"]
    assert len(result.similar_figures) == 1
    assert len(result.search_results) == 2
    assert calls == {"knowledge": 1, "figures": 1}


def test_build_concise_image_answer_does_not_expose_raw_fused_context() -> None:
    long_description = """
    ### Objective Analysis of the Image
    #### 1. Visible Concrete Structure Features
    1. A concrete slab is visible at the bottom of the image, forming a horizontal surface.
    2. Rockfill material is being placed behind formwork in an engineering scene.
    3. Earthmoving equipment appears to be grading the rockfill layer.
    #### 2. Relevance to Hydraulic Concrete
    1. The scene is relevant to rockfill or hydraulic structure construction.
    """

    answer = build_concise_image_answer(
        image_description=long_description,
        related_text_chunks=[object()],
        similar_figures=[object()],
    )

    assert answer.startswith("图片分析要点：")
    assert "User-uploaded image analysis" not in answer
    assert "Objective Analysis" not in answer
    assert len(answer) <= 520


def test_agent_toolbox_analyze_user_image_refuses_out_of_scope_without_sources(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    upload_path = tmp_path / "data" / "user_uploads" / "2026-06-20" / "cat.png"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(make_png_bytes())
    TestingSessionLocal = make_session(tmp_path)

    class StaticVisionProvider:
        provider_name = "real-ish"
        model_name = "static"

        def describe_image(self, image_path, prompt=None):
            return "a cat on a sofa"

    monkeypatch.setattr(
        "app.services.agent.tools.create_vision_model_provider",
        lambda **_kwargs: StaticVisionProvider(),
    )

    with TestingSessionLocal() as db:
        result = AgentToolbox(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        ).analyze_user_image(upload_path.as_posix(), "what is this image?", top_k=3)

    assert result.refused is True
    assert result.sources == []
    assert result.search_results == []
    assert result.image_analysis is not None
    assert result.image_analysis["domain_relevance"] == "out_of_scope"


def test_agent_toolbox_analyze_user_image_returns_concise_answer(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    upload_path = tmp_path / "data" / "user_uploads" / "2026-06-20" / "rockfill.png"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(make_png_bytes())
    TestingSessionLocal = make_session(tmp_path)

    class StaticVisionProvider:
        provider_name = "real-ish"
        model_name = "static"

        def describe_image(self, image_path, prompt=None):
            return (
                "### Objective Analysis of the Image\n"
                "1. A concrete slab is visible at the bottom of the image.\n"
                "2. Rockfill material is being placed in a dam construction scene.\n"
                "3. No obvious concrete crack is visible.\n"
                "4. The image is relevant to hydraulic concrete or rockfill engineering.\n"
            )

    monkeypatch.setattr(
        "app.services.agent.tools.create_vision_model_provider",
        lambda **_kwargs: StaticVisionProvider(),
    )

    with TestingSessionLocal() as db:
        seed_image_analysis_corpus(db, tmp_path)
        embedding_provider = DeterministicEmbeddingProvider(dimension=64)
        VectorIndexService(db, embedding_provider).build_index()
        result = AgentToolbox(
            db=db,
            embedding_provider=embedding_provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        ).analyze_user_image(upload_path.as_posix(), "分析一下图片内容", top_k=3)

    assert result.refused is False
    assert result.answer is not None
    assert "User-uploaded image analysis" not in result.answer
    assert result.search_results == []
    assert result.sources == []
    assert result.image_analysis is not None
    assert result.image_analysis["related_text_count"] == 0
    assert result.image_analysis["similar_figure_count"] == 0
    assert "text_results=0" in result.call.output_summary
