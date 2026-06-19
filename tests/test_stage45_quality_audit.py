import sqlite3
from pathlib import Path

from scripts.audit_phase45_import_quality import audit_quality, summarize, upsert_sources


def test_phase45_quality_audit_flags_review_and_upserts_sources(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.sqlite"
    with sqlite3.connect(db_path) as connection:
        create_schema(connection)
        connection.execute(
            "insert into documents (id, title, source_type, source_path, file_name, file_extension, content_hash, raw_path, status) "
            "values (1, '2024堆石混凝土施工论文', 'institutional_access_pdf', 'paper.pdf', 'paper.pdf', '.pdf', "
            "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'data/raw/paper.pdf', 'imported')"
        )
        connection.execute(
            "insert into chunks (id, document_id, chunk_index, content, char_count, chunk_type) "
            "values (1, 1, 0, '堆石混凝土施工质量控制需要关注填充密实性、温控、浇筑节奏、块石级配、模板稳定、现场试验和后期养护，这些内容构成完整工程论文摘要。', 120, 'text')"
        )
        manifest_rows = [
            {"file_name": "paper.pdf", "status": "ready", "page_count": "1", "guessed_title": "2024堆石混凝土施工论文"},
            {"file_name": "empty.pdf", "status": "ready", "page_count": "4", "guessed_title": "空文本论文"},
        ]
        import_rows = [
            {"file_name": "paper.pdf", "manifest_status": "ready", "import_status": "imported", "document_id": "1"},
            {"file_name": "empty.pdf", "manifest_status": "ready", "import_status": "empty", "document_id": ""},
        ]

        rows = audit_quality(manifest_rows, import_rows, connection)
        sources_upserted = upsert_sources(connection, rows)
        source_count = connection.execute("select count(1) from sources").fetchone()[0]

    summary = summarize(rows, sources_upserted=sources_upserted)

    assert len(rows) == 2
    assert rows[0].year_guess == "2024"
    assert rows[0].category_guess == "rfc_core"
    assert rows[0].review_status == "cloud_candidate"
    assert rows[1].review_status == "review_required"
    assert "empty_text" in rows[1].review_reasons
    assert summary.imported_rows == 1
    assert summary.empty_rows == 1
    assert sources_upserted == 1
    assert source_count == 1


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        create table documents (
            id integer primary key,
            title text,
            source_type text,
            source_path text,
            file_name text,
            file_extension text,
            content_hash text,
            raw_path text,
            status text
        )
        """
    )
    connection.execute(
        """
        create table chunks (
            id integer primary key,
            document_id integer,
            chunk_index integer,
            content text,
            char_count integer,
            chunk_type text
        )
        """
    )
    connection.execute(
        """
        create table sources (
            id integer primary key,
            source_id text unique,
            title text,
            normalized_title text,
            authors text,
            year text,
            venue text,
            category text,
            discovered_via text,
            doi text,
            normalized_doi text,
            url text,
            normalized_url text,
            pdf_url text,
            abstract text,
            keywords text,
            language text,
            citation_count integer,
            source_type text,
            trust_level text,
            access_rights text,
            fulltext_permission text,
            license_or_terms text,
            local_path text,
            status text,
            notes text,
            document_id integer,
            created_at text,
            updated_at text
        )
        """
    )
