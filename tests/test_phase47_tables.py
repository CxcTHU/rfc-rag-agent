import json

from sqlalchemy.orm import sessionmaker

from app.api.agent import agent_response_from_result
from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.agent.service import AgentQueryResult
from app.services.agent.tools import AgentToolbox
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.ingestion.table_extractor import extract_tables_from_page, has_table_structure
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from scripts.backfill_phase47_tables import chunk_create_from_table
from app.services.ingestion.table_extractor import TableChunk


class FakeTable:
    bbox = (10, 40, 200, 140)

    def extract(self):
        return [["Mix", "Strength"], ["A", "42 MPa"], ["B", "48 MPa"]]


class FakeTableFinder:
    tables = [FakeTable()]


class FakePage:
    def find_tables(self):
        return FakeTableFinder()

    def get_text(self, _mode):
        return {
            "blocks": [
                {
                    "bbox": (10, 20, 190, 35),
                    "lines": [{"spans": [{"text": "Table 3 Mix ratio results"}]}],
                }
            ]
        }


def make_session(tmp_path):
    database_path = tmp_path / "phase47_tables.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_extract_tables_from_page_outputs_markdown_and_header() -> None:
    tables, skipped = extract_tables_from_page(FakePage(), page_number=2, min_rows=2)

    assert skipped == 0
    assert len(tables) == 1
    assert tables[0].page_number == 2
    assert tables[0].header_text == "Table 3 Mix ratio results"
    assert "| Mix | Strength |" in tables[0].markdown_content
    assert tables[0].bbox == (10.0, 40.0, 200.0, 140.0)


def test_table_structure_rejects_rows_collapsed_into_one_cell() -> None:
    assert not has_table_structure(
        [
            ["all values were collapsed into one noisy cell", "", ""],
            ["another collapsed row", "", ""],
        ]
    )
    assert not has_table_structure(
        [
            ["Header", "Value", ""],
            ["Subheader", "Value", ""],
            ["collapsed drawing coordinates", "", ""],
            ["more drawing coordinates", "", ""],
            ["more drawing coordinates", "", ""],
            ["more drawing coordinates", "", ""],
        ]
    )
    assert has_table_structure([["Name", "Value"], ["A", "42 MPa"]])


def test_chunk_create_from_table_stores_table_metadata() -> None:
    chunk = chunk_create_from_table(
        TableChunk(
            page_number=3,
            bbox=(1, 2, 3, 4),
            markdown_content="| A | B |\n| --- | --- |\n| 1 | 2 |",
            header_text="Table 1",
            row_count=2,
            col_count=2,
        ),
        chunk_index=5,
    )

    assert chunk.chunk_type == "table"
    payload = json.loads(chunk.content_bbox_json or "{}")
    assert payload["page"] == 3
    assert payload["bbox"]["x0"] == 1
    assert payload["row_count"] == 2


def test_agent_toolbox_search_tables_returns_table_content_and_bbox(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    with TestingSessionLocal() as db:
        DocumentRepository(db).create_with_chunks(
            DocumentCreate(
                title="Mix Tables",
                source_type="local_file",
                source_path="mix.pdf",
                file_name="mix.pdf",
                file_extension=".pdf",
                content_hash="phase47-table",
                raw_path="data/raw/mix.pdf",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="| Mix | Strength |\n| --- | --- |\n| A | 42 MPa |",
                    char_count=49,
                    heading_path="Table 1",
                    start_char=None,
                    end_char=None,
                    chunk_type="table",
                    page_number=4,
                    content_bbox_json=json.dumps(
                        {
                            "page": 4,
                            "bboxes": [{"x0": 1, "y0": 2, "x1": 3, "y1": 4}],
                            "confidence": "exact",
                        }
                    ),
                )
            ],
        )
        result = AgentToolbox(
            db=db,
            embedding_provider=DeterministicEmbeddingProvider(),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        ).search_tables("strength table", top_k=3)

    assert result.call.succeeded
    assert result.search_results[0].chunk_type == "table"
    assert result.search_results[0].table_content.startswith("| Mix |")
    assert result.sources[0].content_bbox is not None


def test_agent_response_from_result_passes_table_and_bbox_fields() -> None:
    from app.services.agent.tools import AgentSearchItem, AgentSourceReference

    bbox = {"page_number": 1, "confidence": "exact"}
    result = AgentQueryResult(
        question="show table",
        answer="See [1]",
        tool_calls=[],
        search_results=[
            AgentSearchItem(
                document_id=1,
                document_title="Doc",
                source_type="local_file",
                source_path="doc.pdf",
                file_name="doc.pdf",
                chunk_id=10,
                chunk_index=0,
                content="| A | B |",
                heading_path="Table",
                score=1.0,
                chunk_type="table",
                table_content="| A | B |",
                content_bbox=bbox,
            )
        ],
        sources=[
            AgentSourceReference(
                source_id="chunk:10",
                title="Doc",
                source_type="local_file",
                chunk_id=10,
                content="| A | B |",
                score=1.0,
                chunk_type="table",
                table_content="| A | B |",
                content_bbox=bbox,
            )
        ],
        citations=[1],
        reasoning_summary="test",
    )

    response = agent_response_from_result(result)

    assert response.search_results[0].table_content == "| A | B |"
    assert response.search_results[0].content_bbox == bbox
    assert response.sources[0].table_content == "| A | B |"
