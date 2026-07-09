from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, Document, DocumentTable, TableRetrievalUnit
from app.db.session import create_sqlite_engine
from app.services.ingestion.table_extractor import extract_tables_from_page
from app.services.table_rag.extraction import draft_from_rows, draft_from_table_chunk
from app.services.table_rag.normalization import parse_markdown_table
from app.services.table_rag.repository import StructuredTableRepository
from app.services.table_rag.retrieval_units import build_retrieval_units
from app.services.table_rag.search import StructuredTableSearchService


class FakeRawTable:
    bbox = (10.0, 20.0, 110.0, 90.0)

    def extract(self) -> list[list[str]]:
        return [
            ["材料", "用量 kg/m3", "备注"],
            ["水泥", "120", "P.O 42.5"],
            ["水", "150", ""],
        ]


class FakeFinder:
    tables = [FakeRawTable()]


class FakePage:
    def find_tables(self) -> FakeFinder:
        return FakeFinder()

    def get_text(self, _mode: str) -> dict[str, object]:
        return {"blocks": []}


def make_session(tmp_path):
    database_path = tmp_path / "phase60.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_table_extractor_preserves_structured_rows() -> None:
    tables, skipped = extract_tables_from_page(FakePage(), page_number=12, min_rows=2)

    assert skipped == 0
    assert len(tables) == 1
    assert tables[0].rows == (
        ("材料", "用量 kg/m3", "备注"),
        ("水泥", "120", "P.O 42.5"),
        ("水", "150", ""),
    )
    assert "| 材料 | 用量 kg/m3 | 备注 |" in tables[0].markdown_content


def test_markdown_table_parser_is_fallback_only_but_structured() -> None:
    rows = parse_markdown_table(
        """
        表 1 配合比
        | 材料 | 用量 kg/m3 | 备注 |
        | --- | ---: | --- |
        | 水泥 | 120 | P.O 42.5 |
        | 水 | 150 |  |
        """
    )

    assert rows == (
        ("材料", "用量 kg/m3", "备注"),
        ("水泥", "120", "P.O 42.5"),
        ("水", "150", ""),
    )


def test_structured_table_repository_generates_rows_cells_and_units(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        document = Document(
            title="配合比资料",
            source_type="local_file",
            source_path="mix.pdf",
            file_name="mix.pdf",
            file_extension=".pdf",
            content_hash="phase60-doc-hash",
            raw_path="data/raw/mix.pdf",
            status="imported",
            chunks=[
                Chunk(
                    chunk_index=0,
                    content="| 材料 | 用量 kg/m3 | 备注 |\n| --- | --- | --- |\n| 水泥 | 120 | P.O 42.5 |",
                    char_count=75,
                    heading_path="配合比参数",
                    start_char=None,
                    end_char=None,
                    chunk_type="table",
                    page_number=12,
                )
            ],
        )
        db.add(document)
        db.commit()
        chunk_id = document.chunks[0].id

        draft = draft_from_rows(
            [
                ["材料", "用量 kg/m3", "备注"],
                ["水泥", "120", "P.O 42.5"],
                ["水", "150", ""],
            ],
            document_id=document.id,
            table_index=0,
            page_number=12,
            bbox=(10.0, 20.0, 110.0, 90.0),
            caption="配合比参数",
            header_text="配合比参数",
            source_table_chunk_id=chunk_id,
            extraction_run_id=None,
            source="unit_test",
        )
        repository = StructuredTableRepository(db)
        table, created = repository.save_table(draft)
        units = repository.replace_retrieval_units(table.id, build_retrieval_units(draft))
        db.commit()

        assert created is True
        assert db.query(DocumentTable).count() == 1
        assert table.row_count == 3
        assert table.col_count == 3
        assert {column.unit for column in table.columns} >= {"kg/m3", None}
        assert len(table.rows) == 3
        assert any(cell.text == "120" and cell.numeric_value == 120.0 for cell in table.cells)
        assert {unit.unit_type for unit in units} >= {
            "table_summary",
            "table_schema",
            "row_pack",
            "column_pack",
            "cell_fact",
            "caption_context",
        }


def test_structured_table_search_hydrates_precise_table_result(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        document = Document(
            title="配合比资料",
            source_type="local_file",
            source_path="mix.pdf",
            file_name="mix.pdf",
            file_extension=".pdf",
            content_hash="phase60-search-doc-hash",
            raw_path="data/raw/mix.pdf",
            status="imported",
        )
        db.add(document)
        db.commit()
        table_chunk, _skipped = extract_tables_from_page(FakePage(), page_number=12, min_rows=2)
        draft = draft_from_table_chunk(
            table_chunk[0],
            document_id=document.id,
            table_index=0,
            source_table_chunk_id=None,
        )
        repository = StructuredTableRepository(db)
        table, _created = repository.save_table(draft)
        repository.replace_retrieval_units(table.id, build_retrieval_units(draft))
        db.commit()

        result = StructuredTableSearchService(db).search("水泥 用量 120 kg/m3", top_k=3)[0]

        assert result.table_id == table.id
        assert result.headers == ("材料", "用量 kg/m3", "备注")
        assert ("水泥", "120", "P.O 42.5") in result.rows
        assert result.citation.document_id == document.id
        assert result.citation.page == 12
        assert {match.type for match in result.matched_units} & {
            "cell_fact",
            "exact_cell",
            "exact_header",
            "numeric_unit",
        }
        assert db.query(TableRetrievalUnit).count() > 0

        assert StructuredTableSearchService(db).search("今天北京天气怎么样", top_k=3) == []
