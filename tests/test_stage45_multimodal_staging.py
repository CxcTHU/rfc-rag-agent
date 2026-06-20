from app.db.models import Base, Chunk, Document
from app.db.session import create_sqlite_engine
from scripts.import_multimodal_staging import import_rows
from app.services.generation.vision_model import DeterministicVisionModelProvider
from scripts.process_multimodal_to_staging import (
    StagingImageRow,
    build_vision_provider,
    process_image_manifests,
    summarize,
    write_document_status_outputs,
)
from argparse import Namespace
from sqlalchemy.orm import sessionmaker


def test_staging_summarize_counts_described_and_failed_images() -> None:
    rows = [
        StagingImageRow(1, "doc", 1, "data/images/1/a.png", 100, 100, "described", "desc"),
        StagingImageRow(1, "doc", 1, "data/images/1/b.png", 100, 100, "failed", error="timeout"),
        StagingImageRow(1, "doc", 1, "data/images/1/c.png", 100, 100, "skipped_existing"),
    ]

    summary = summarize(
        rows,
        selected_documents=1,
        processed_documents=1,
        failed_documents=0,
        run_started=0.0,
        provider="deterministic",
        model_name="deterministic-vision",
    )

    assert summary.extracted_images == 3
    assert summary.described_images == 1
    assert summary.failed_images == 1
    assert summary.skipped_existing_images == 1
    assert summary.provider == "deterministic"


def test_import_multimodal_staging_creates_chunks_idempotently(tmp_path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'staging.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    rows = [
        {
            "document_id": "1",
            "status": "described",
            "description": "图中展示堆石混凝土施工过程。",
            "source_image_path": "data/images/1/page1_img1.png",
        }
    ]

    with TestingSessionLocal() as db:
        db.add(
            Document(
                id=1,
                title="堆石混凝土施工",
                source_type="institutional_access_pdf",
                source_path="paper.pdf",
                file_name="paper.pdf",
                file_extension=".pdf",
                content_hash="hash",
                raw_path="paper.pdf",
            )
        )
        db.commit()
        first = import_rows(rows, db)
        second = import_rows(rows, db)
        chunks = db.query(Chunk).all()

    assert first.created_chunks == 1
    assert second.created_chunks == 0
    assert second.skipped_existing_chunks == 1
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "image_description"


def test_write_document_status_outputs_includes_partial_ids(tmp_path) -> None:
    write_document_status_outputs(
        tmp_path,
        processed_document_ids=[1],
        failed_document_ids=[2],
        no_image_document_ids=[3],
        partial_document_ids=[4],
    )

    assert (tmp_path / "processed_document_ids.txt").read_text(encoding="utf-8") == "1\n"
    assert (tmp_path / "failed_document_ids.txt").read_text(encoding="utf-8") == "2\n"
    assert (tmp_path / "no_image_document_ids.txt").read_text(encoding="utf-8") == "3\n"
    assert (tmp_path / "partial_document_ids.txt").read_text(encoding="utf-8") == "4\n"


def test_process_image_manifest_uses_workers_and_writes_timing(tmp_path) -> None:
    image_a = tmp_path / "a.png"
    image_b = tmp_path / "b.png"
    image_a.write_bytes(b"fake")
    image_b.write_bytes(b"fake")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "\ufeffdocument_id,document_title,page_num,source_image_path,width,height,status,error\n"
        f"1,doc,1,{image_a.as_posix()},100,100,pending,\n"
        f"1,doc,2,{image_b.as_posix()},100,100,pending,\n",
        encoding="utf-8",
    )

    rows, timing_events, summary = process_image_manifests(
        manifest_paths=[manifest],
        vision_provider=DeterministicVisionModelProvider(),
        provider_label="test_provider",
        output_dir=tmp_path / "out",
        checkpoint_every=1,
        workers=2,
        limit=0,
        offset=0,
    )

    assert summary.described_images == 2
    assert all(row.status == "described" for row in rows)
    assert sum(1 for event in timing_events if event.event_type == "describe_image") == 2
    assert {event.provider for event in timing_events} == {"test_provider"}


def test_build_vision_provider_uses_phase45_route_env(monkeypatch) -> None:
    monkeypatch.setenv("PARATERA_GLM_KEY", "route-secret")

    provider = build_vision_provider(
        FakeVisionSettings(),
        Namespace(
            vision_provider="paratera",
            vision_model_name="GLM-4.6V",
            vision_api_key_env="PARATERA_GLM_KEY",
            vision_api_key="",
            vision_base_url="https://llmapi.paratera.com",
            vision_timeout_seconds=45.0,
        ),
    )

    assert provider.provider_name == "paratera"
    assert provider.model_name == "GLM-4.6V"
    assert provider.base_url == "https://llmapi.paratera.com"
    assert provider.api_key == "route-secret"
    assert provider.timeout_seconds == 45.0


def test_build_vision_provider_falls_back_to_settings() -> None:
    provider = build_vision_provider(
        FakeVisionSettings(),
        Namespace(
            vision_provider="",
            vision_model_name="",
            vision_api_key_env="",
            vision_api_key="",
            vision_base_url="",
            vision_timeout_seconds=0.0,
        ),
    )

    assert provider.provider_name == "openai-compatible"
    assert provider.model_name == "settings-model"
    assert provider.base_url == "https://settings.example/v1"
    assert provider.api_key == "settings-secret"


class FakeVisionSettings:
    vision_model_provider = "openai-compatible"
    vision_model_name = "settings-model"
    vision_model_api_key = "settings-secret"
    vision_model_base_url = "https://settings.example/v1"
    vision_model_timeout_seconds = 30.0
