import csv
import json

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Base, Chunk, Document
from app.db.session import create_database_engine
from scripts.evaluate_phase54_extraction_sample import (
    overlap_metrics,
    write_manual_review_csv,
    write_quality_csv,
)
from scripts.review_phase54_extraction_sample import review_rows
from scripts.extract_phase53_graphrag_triples import (
    build_planner_extractor,
    extract_selected_chunks_to_rows,
    select_diverse_chunks,
)
from scripts.extract_phase54_graphrag_full import (
    extract_full_rows,
    load_rows_many,
    merge_extraction_rows,
    score_high_value_chunk,
    select_high_value_chunk_pairs,
)


def make_phase54_db(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'phase54.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        document = Document(
            title="RFC graph evaluation",
            file_name="phase54.pdf",
            file_extension=".pdf",
            content_hash="phase54-hash",
            raw_path="/tmp/phase54.pdf",
        )
        db.add(document)
        db.flush()
        chunks = [
            Chunk(
                document_id=document.id,
                chunk_index=0,
                chunk_type="text",
                heading_path="materials > strength",
                content="GB/T 50080 defines compressive strength for rock-filled concrete at 45 MPa.",
                char_count=80,
            ),
            Chunk(
                document_id=document.id,
                chunk_index=1,
                chunk_type="text",
                heading_path="materials > flow",
                content="ACI 237 discusses slump flow for SCC with 650 mm target value.",
                char_count=72,
            ),
            Chunk(
                document_id=document.id,
                chunk_index=2,
                chunk_type="text",
                heading_path="construction > curing",
                content="Curing applies to self-compacting concrete and controls temperature.",
                char_count=70,
            ),
        ]
        db.add_all(chunks)
        db.commit()
    return engine


def test_phase54_diverse_sample_and_rows_omit_chunk_content(tmp_path) -> None:
    engine = make_phase54_db(tmp_path)
    with Session(engine) as db:
        chunks = select_diverse_chunks(db, limit=2, seed=54)
        rows = extract_selected_chunks_to_rows(
            chunks,
            extractor=build_planner_extractor(execute_llm=False),
            execute_llm=False,
        )

    assert len(rows) == 2
    assert {row["metadata"]["heading_bucket"] for row in rows}
    serialized = json.dumps(rows, ensure_ascii=False)
    assert "defines compressive strength" not in serialized
    assert "raw_response" not in serialized


def test_phase54_quality_and_manual_review_outputs_are_sanitized(tmp_path) -> None:
    llm_rows = [
        {
            "chunk_id": 1,
            "document_id": 2,
            "document_title": "Short title",
            "status": "ok",
            "entities": [
                {"name": "RFC", "type": "Material", "normalized_name": "rfc"},
                {"name": "45 MPa", "type": "Value", "normalized_name": "45 mpa"},
            ],
            "relations": [
                {
                    "subject": "RFC",
                    "predicate": "material_has_property",
                    "object": "compressive strength",
                }
            ],
            "metadata": {"heading_bucket": "materials"},
        }
    ]
    regex_rows = [
        {
            "chunk_id": 1,
            "entities": [{"name": "45 MPa", "type": "Value", "normalized_name": "45 mpa"}],
            "relations": [],
        }
    ]

    metrics = overlap_metrics(llm_rows, regex_rows)
    assert metrics["entity_overlap"] == 1
    assert metrics["entity_overlap_precision_proxy"] == "0.5000"

    quality_path = tmp_path / "quality.csv"
    manual_path = tmp_path / "manual.csv"
    write_quality_csv(
        quality_path,
        metrics=metrics,
        llm_rows=llm_rows,
        regex_rows=regex_rows,
        execute_llm=True,
    )
    write_manual_review_csv(
        manual_path,
        llm_rows=llm_rows,
        regex_rows=regex_rows,
        sample_size=20,
    )

    quality_text = quality_path.read_text(encoding="utf-8")
    manual_text = manual_path.read_text(encoding="utf-8")
    assert "entity_overlap_precision_proxy" in quality_text
    assert "entity_precision_manual" in manual_text
    assert "raw_response" not in quality_text + manual_text

    with quality_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert any(row["section"] == "manual_review_gate" for row in rows)


def test_phase54_execute_extractor_uses_planner_provider(monkeypatch) -> None:
    monkeypatch.setenv("PLANNER_CHAT_MODEL_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PLANNER_CHAT_MODEL_NAME", "deepseek-v4-flash")
    monkeypatch.setenv("PLANNER_CHAT_MODEL_API_KEY", "test-key")
    monkeypatch.delenv("PLANNER_CHAT_MODEL_API_KEYS", raising=False)
    monkeypatch.setenv("PLANNER_CHAT_MODEL_BASE_URL", "https://example.test/v1")
    get_settings.cache_clear()
    try:
        extractor = build_planner_extractor(execute_llm=True, max_attempts=1)
    finally:
        get_settings.cache_clear()

    assert extractor.chat_model_provider is not None
    assert extractor.chat_model_provider.model_name == "deepseek-v4-flash"
    assert getattr(extractor.chat_model_provider, "max_attempts") == 1


def test_phase54_execute_extractor_supports_planner_api_key_pool(monkeypatch) -> None:
    monkeypatch.setenv("PLANNER_CHAT_MODEL_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PLANNER_CHAT_MODEL_NAME", "deepseek-v4-flash")
    monkeypatch.setenv("PLANNER_CHAT_MODEL_API_KEY", "single-test-key")
    monkeypatch.setenv("PLANNER_CHAT_MODEL_API_KEYS", "test-key-a, test-key-b, test-key-c")
    monkeypatch.setenv("PLANNER_CHAT_MODEL_BASE_URL", "https://example.test/v1")
    get_settings.cache_clear()
    try:
        extractor = build_planner_extractor(execute_llm=True, max_attempts=1)
    finally:
        get_settings.cache_clear()

    provider = extractor.chat_model_provider
    assert provider is not None
    assert provider.model_name == "deepseek-v4-flash"
    assert len(getattr(provider, "providers")) == 4
    assert {child.model_name for child in provider.providers} == {"deepseek-v4-flash"}


def test_phase54_planner_api_key_pool_can_come_from_settings(monkeypatch) -> None:
    monkeypatch.setenv("PLANNER_CHAT_MODEL_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PLANNER_CHAT_MODEL_NAME", "deepseek-v4-flash")
    monkeypatch.setenv("PLANNER_CHAT_MODEL_API_KEY", "")
    monkeypatch.delenv("PLANNER_CHAT_MODEL_API_KEYS", raising=False)
    monkeypatch.setenv("PLANNER_CHAT_MODEL_API_KEYS", "settings-key-a,settings-key-b")
    monkeypatch.setenv("PLANNER_CHAT_MODEL_BASE_URL", "https://example.test/v1")
    get_settings.cache_clear()
    try:
        extractor = build_planner_extractor(execute_llm=True, max_attempts=1)
    finally:
        get_settings.cache_clear()

    provider = extractor.chat_model_provider
    assert provider is not None
    assert len(getattr(provider, "providers")) == 2


def test_phase54_review_rows_score_grounded_entities_without_content() -> None:
    extraction_rows = [
        {
            "chunk_id": 1,
            "document_id": 2,
            "document_title": "short title",
            "status": "ok",
            "entities": [
                {"name": "rock-filled concrete", "type": "Material"},
                {"name": "compressive strength", "type": "Parameter"},
                {"name": "not present", "type": "Method"},
            ],
            "relations": [
                {
                    "subject": "rock-filled concrete",
                    "predicate": "material_has_property",
                    "object": "compressive strength",
                }
            ],
            "metadata": {"heading_bucket": "materials"},
        }
    ]

    rows = review_rows(
        extraction_rows,
        chunk_text_by_id={
            1: "Rock-filled concrete has compressive strength requirements.",
        },
        sample_size=20,
    )

    assert rows[0]["entity_precision_manual"] == "0.6667"
    assert rows[0]["relation_precision_manual"] == "1.0000"
    serialized = json.dumps(rows, ensure_ascii=False)
    assert "Rock-filled concrete has" not in serialized


def test_phase54_merge_prefers_regex_and_supplements_llm() -> None:
    regex_rows = [
        {
            "chunk_id": 1,
            "document_id": 2,
            "document_title": "title",
            "status": "ok",
            "entities": [
                {
                    "name": "GB/T 50080",
                    "type": "Standard",
                    "normalized_name": "gb/t 50080",
                    "mentions": ["GB/T 50080"],
                }
            ],
            "relations": [],
        }
    ]
    llm_rows = [
        {
            "chunk_id": 1,
            "document_id": 2,
            "document_title": "title",
            "status": "ok",
            "entities": [
                {
                    "name": "GB/T 50080",
                    "type": "Standard",
                    "normalized_name": "gb/t 50080",
                    "mentions": ["GB/T 50080"],
                },
                {
                    "name": "slump flow",
                    "type": "Parameter",
                    "normalized_name": "slump flow",
                    "mentions": ["slump flow"],
                },
            ],
            "relations": [
                {
                    "subject": "GB/T 50080",
                    "predicate": "standard_defines",
                    "object": "slump flow",
                    "source_chunk_id": 1,
                }
            ],
        }
    ]

    merged = merge_extraction_rows(llm_rows=llm_rows, regex_rows=regex_rows)

    assert len(merged) == 1
    assert merged[0]["extractor"] == "phase54_merge_regex_priority"
    assert len(merged[0]["entities"]) == 2
    assert merged[0]["relations"][0]["predicate"] == "standard_defines"


def test_phase54_full_extract_rows_are_sanitized(tmp_path) -> None:
    engine = make_phase54_db(tmp_path)
    output_path = tmp_path / "full.json"
    with Session(engine) as db:
        rows = extract_full_rows(
            db,
            chunk_type="text",
            extractor=build_planner_extractor(execute_llm=False),
            execute_llm=False,
            output_path=output_path,
            limit=2,
            offset=0,
            batch_size=1,
            flush_every=1,
            resume=False,
        )

    serialized = output_path.read_text(encoding="utf-8")
    assert len(rows) == 2
    assert "defines compressive strength" not in serialized
    assert "raw_response" not in serialized


def test_phase54_high_value_selection_prioritizes_semantic_candidates(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'high_value.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        document = Document(
            title="Neutral construction notes",
            file_name="notes.pdf",
            file_extension=".pdf",
            content_hash="notes-hash",
            raw_path="/tmp/notes.pdf",
        )
        db.add(document)
        db.flush()
        low_value = Chunk(
            document_id=document.id,
            chunk_index=0,
            chunk_type="text",
            heading_path="preface",
            content="This section introduces the document organization.",
            char_count=52,
        )
        high_value = Chunk(
            document_id=document.id,
            chunk_index=1,
            chunk_type="text",
            heading_path="materials > strength",
            content="GB/T 50080 defines compressive strength for rock-filled concrete at 45 MPa.",
            char_count=80,
        )
        table_value = Chunk(
            document_id=document.id,
            chunk_index=2,
            chunk_type="table",
            heading_path="mix proportion table",
            content="| material | parameter | value |\n| RFC | slump | 650 mm |",
            char_count=60,
        )
        db.add_all([low_value, high_value, table_value])
        db.commit()

        pairs = [(low_value, document), (high_value, document), (table_value, document)]
        report_path = tmp_path / "candidates.csv"
        selected = select_high_value_chunk_pairs(
            pairs,
            limit=2,
            min_score=1,
            report_output=report_path,
        )
        selected_ids = [chunk.id for chunk, _ in selected]
        high_value_score = score_high_value_chunk(high_value, document)
        low_value_score = score_high_value_chunk(low_value, document)
        table_value_id = table_value.id
        high_value_id = high_value.id

    assert selected_ids == [table_value_id, high_value_id]
    assert high_value_score > low_value_score
    report_text = report_path.read_text(encoding="utf-8")
    assert "score" in report_text
    assert "defines compressive strength" not in report_text


def test_phase54_load_rows_many_combines_text_and_table_outputs(tmp_path) -> None:
    first = tmp_path / "text.json"
    second = tmp_path / "table.json"
    first.write_text(json.dumps({"rows": [{"chunk_id": 1, "status": "ok"}]}), encoding="utf-8")
    second.write_text(json.dumps({"rows": [{"chunk_id": 2, "status": "ok"}]}), encoding="utf-8")

    rows = load_rows_many([first, second])

    assert [row["chunk_id"] for row in rows] == [1, 2]
