from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Document
from app.db.session import create_sqlite_engine
from scripts.import_phase45_manifest_ready import import_ready_rows


def make_session(tmp_path: Path):
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'phase45.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_phase45_manifest_imports_only_ready_rows_and_skips_duplicates(tmp_path: Path) -> None:
    ready_file = tmp_path / "ready.txt"
    duplicate_file = tmp_path / "duplicate.txt"
    ready_file.write_text("堆石混凝土施工质量控制需要关注填充密实性和温控。", encoding="utf-8")
    duplicate_file.write_text("堆石混凝土重复论文。", encoding="utf-8")
    manifest_rows = [
        {
            "file_name": "ready.txt",
            "original_path": str(ready_file),
            "status": "ready",
            "guessed_title": "可导入论文",
        },
        {
            "file_name": "duplicate.txt",
            "original_path": str(duplicate_file),
            "status": "duplicate_candidate",
            "guessed_title": "重复论文",
        },
        {
            "file_name": "ready-again.txt",
            "original_path": str(ready_file),
            "status": "ready",
            "guessed_title": "可导入论文",
        },
    ]
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        summary, results = import_ready_rows(manifest_rows, db=db, raw_dir=tmp_path / "raw")
        documents = db.scalars(select(Document)).all()

    assert summary.manifest_rows == 3
    assert summary.ready_rows == 2
    assert summary.imported == 1
    assert summary.duplicate == 1
    assert summary.skipped_not_ready == 1
    assert summary.failed == 0
    assert len(documents) == 1
    assert documents[0].source_type == "institutional_access_pdf"
    assert [result.import_status for result in results] == [
        "imported",
        "skipped_not_ready",
        "duplicate",
    ]
