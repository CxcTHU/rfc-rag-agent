from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import sessionmaker

from app.api.image_upload import router as image_upload_router
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
from app.services.agent.react_service import ReActAgentService
from app.services.agent.tools import AgentToolbox
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


def test_agent_toolbox_analyze_user_image_uses_deterministic_vision(tmp_path, monkeypatch) -> None:
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
    assert result.image_analysis is not None
    assert result.answer is not None
    assert "User-uploaded image analysis" in result.answer


def test_react_agent_analyzes_image_when_image_path_is_present(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    upload_path = tmp_path / "data" / "user_uploads" / "2026-06-20" / "crack.png"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(make_png_bytes())
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = ReActAgentService(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(),
            chat_model_provider=DeterministicChatModelProvider(),
        ).query(
            "Please analyze this image.",
            image_path=upload_path.as_posix(),
            max_tool_calls=1,
        )

    assert result.tool_calls[0].tool_name == "analyze_user_image"
    assert result.image_analysis is not None
