from pathlib import Path

from app.db.models import Base, Document
from app.db.session import create_sqlite_engine
from scripts.process_multimodal import (
    ProcessMultimodalRow,
    maybe_write_checkpoint,
    read_document_ids_file,
    sanitize_error,
    select_document_ids,
    summarize,
)
from sqlalchemy.orm import sessionmaker


def test_select_document_ids_supports_limit_offset_and_existing_files(tmp_path: Path) -> None:
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'docs.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    existing_pdf = tmp_path / "existing.pdf"
    existing_pdf.write_bytes(b"%PDF-1.4\n")

    with TestingSessionLocal() as db:
        for doc_id, raw_path in [
            (1, str(tmp_path / "missing.pdf")),
            (2, str(existing_pdf)),
            (3, str(existing_pdf)),
        ]:
            db.add(
                Document(
                    id=doc_id,
                    title=f"doc {doc_id}",
                    source_type="institutional_access_pdf",
                    source_path=raw_path,
                    file_name=f"doc{doc_id}.pdf",
                    file_extension=".pdf",
                    content_hash=f"hash-{doc_id}",
                    raw_path=raw_path,
                )
            )
        db.commit()

        selected = select_document_ids(
            db,
            0,
            limit=1,
            offset=1,
            only_existing_files=True,
        )

    assert selected == [3]


def test_summarize_process_multimodal_rows() -> None:
    summary = summarize(
        [
            ProcessMultimodalRow(document_id=1, status="processed", extracted_images=2, created_chunks=2),
            ProcessMultimodalRow(document_id=2, status="failed", error="boom"),
        ],
        selected_documents=2,
    )

    assert summary.selected_documents == 2
    assert summary.processed_documents == 1
    assert summary.failed_documents == 1
    assert summary.extracted_images == 2


def test_read_document_ids_file_ignores_blank_lines_and_comments(tmp_path: Path) -> None:
    ids_path = tmp_path / "ids.txt"
    ids_path.write_text("\ufeff11\n\n# retry later\n20\n", encoding="utf-8")

    assert read_document_ids_file(ids_path) == [11, 20]


def test_sanitize_error_collapses_windows_connection_timeout() -> None:
    exc = RuntimeError("[WinError 10060] connection attempt failed")

    assert sanitize_error(exc) == "RuntimeError: provider_timeout"


def test_maybe_write_checkpoint_preserves_total_selected_documents(tmp_path: Path) -> None:
    output_dir = tmp_path / "checkpoint"
    rows = [ProcessMultimodalRow(document_id=1, status="processed", extracted_images=1, created_chunks=1)]

    maybe_write_checkpoint(rows, selected_documents=3, output_dir=str(output_dir), checkpoint_every=1)

    summary = (output_dir / "process_multimodal_summary.json").read_text(encoding="utf-8")
    assert '"selected_documents": 3' in summary
    assert '"processed_documents": 1' in summary
