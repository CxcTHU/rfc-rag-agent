import json

from sqlalchemy.orm import Session

from app.db.models import Base, Chunk, Document
from app.db.session import create_database_engine
from app.services.generation.chat_model import ChatMessage, ChatModelResult
from app.services.graphrag.extractor import GraphRAGTripleExtractor
from app.services.graphrag.schema import (
    ALLOWED_ENTITY_TYPES,
    ALLOWED_RELATION_TYPES,
    GraphEntity,
    GraphExtractionResult,
    GraphRelation,
)
from scripts.extract_phase53_graphrag_triples import extract_chunks_to_rows


def test_phase53_schema_allows_required_entity_and_relation_types() -> None:
    assert ALLOWED_ENTITY_TYPES == {
        "Standard",
        "Material",
        "Parameter",
        "Value",
        "Organization",
        "Method",
    }
    assert ALLOWED_RELATION_TYPES == {
        "standard_defines",
        "standard_references",
        "material_has_property",
        "parameter_range",
        "applies_to",
    }

    result = GraphExtractionResult(
        chunk_id=1,
        document_id=2,
        document_title="RFC guide",
        entities=(GraphEntity(name="RFC", type="Material", mentions=("RFC",)),),
        relations=(
            GraphRelation(
                subject="RFC",
                predicate="material_has_property",
                object="compressive strength",
                source_chunk_id=1,
            ),
        ),
    )

    assert GraphExtractionResult.from_dict(result.to_dict()).to_dict() == result.to_dict()


def test_deterministic_extractor_finds_domain_entities_and_relations() -> None:
    text = (
        "GB/T 50080 defines slump flow for self-compacting concrete. "
        "Rock-filled concrete uses SCC to improve filling capacity; "
        "compressive strength reached 45 MPa after curing."
    )

    result = GraphRAGTripleExtractor().extract(
        chunk_id=10,
        document_id=20,
        document_title="RFC test standard",
        text=text,
    )

    entities = {(entity.type, entity.name) for entity in result.entities}
    assert ("Standard", "GB/T 50080") in entities
    assert ("Material", "rock-filled concrete") in entities
    assert ("Material", "self-compacting concrete") in entities
    assert ("Parameter", "compressive strength") in entities
    assert ("Value", "45 MPa") in entities
    assert any(
        relation.predicate == "material_has_property"
        and relation.object == "compressive strength"
        for relation in result.relations
    )
    assert any(relation.predicate == "parameter_range" for relation in result.relations)


class FakeGraphExtractionProvider:
    provider_name = "fake"
    model_name = "graph-extractor"

    def generate(self, messages: list[ChatMessage]) -> ChatModelResult:
        assert "Do not include raw source text" in messages[1].content
        return ChatModelResult(
            answer=json.dumps(
                {
                    "entities": [
                        {"name": "ACI 237", "type": "Standard"},
                        {"name": "slump flow", "type": "Parameter"},
                        {"name": "650 mm", "type": "Value"},
                    ],
                    "relations": [
                        {
                            "subject": "ACI 237",
                            "predicate": "standard_defines",
                            "object": "slump flow",
                            "evidence": "short note",
                        },
                        {
                            "subject": "slump flow",
                            "predicate": "parameter_range",
                            "object": "650 mm",
                        },
                    ],
                }
            ),
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response={"must_not_be_serialized": True},
        )


def test_llm_extractor_parses_json_without_persisting_raw_response() -> None:
    result = GraphRAGTripleExtractor(FakeGraphExtractionProvider()).extract(
        chunk_id=3,
        document_id=4,
        document_title="ACI guide",
        text="ACI 237 discusses SCC slump flow of 650 mm.",
        execute_llm=True,
    )

    serialized = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "llm:fake:graph-extractor" in serialized
    assert "must_not_be_serialized" not in serialized
    assert any(entity.name == "ACI 237" for entity in result.entities)
    assert any(relation.predicate == "standard_defines" for relation in result.relations)


def test_batch_extraction_rows_omit_chunk_content_and_provider_raw_response(tmp_path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'phase53.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        document = Document(
            title="RFC standard",
            file_name="rfc.pdf",
            file_extension=".pdf",
            content_hash="phase53-graphrag-hash",
            raw_path="/tmp/rfc.pdf",
        )
        db.add(document)
        db.flush()
        db.add(
            Chunk(
                document_id=document.id,
                chunk_index=0,
                chunk_type="text",
                content="堆石混凝土的抗压强度达到 50 MPa，养护适用于 rock-filled concrete。",
                char_count=64,
            )
        )
        db.commit()

    with Session(engine) as db:
        rows = extract_chunks_to_rows(
            db,
            extractor=GraphRAGTripleExtractor(),
            limit=100,
        )

    assert len(rows) == 1
    serialized = json.dumps(rows, ensure_ascii=False)
    assert "content" not in rows[0]
    assert "raw_response" not in serialized
    assert "堆石混凝土的抗压强度达到" not in serialized
    assert rows[0]["entities"]
    assert rows[0]["relations"]
