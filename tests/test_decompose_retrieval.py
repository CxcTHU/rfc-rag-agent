from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine
from app.services.retrieval.decompose import DecomposeRetrievalService
from app.services.retrieval.decompose import (
    MergedEvidence,
    SubQueryRetrievalResult,
    decompose_query,
    merge_sub_query_results,
)
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


@dataclass(frozen=True)
class FakeSearchResult:
    document_id: int
    document_title: str
    source_type: str
    source_path: str | None
    file_name: str
    chunk_id: int
    chunk_index: int
    content: str
    heading_path: str | None
    score: float
    keyword_score: float = 0.0
    vector_score: float = 0.0


def fake_result(
    *,
    chunk_id: int,
    title: str,
    content: str,
    score: float,
    source_type: str = "metadata_record",
    keyword_score: float = 0.0,
    vector_score: float = 0.0,
) -> FakeSearchResult:
    return FakeSearchResult(
        document_id=chunk_id,
        document_title=title,
        source_type=source_type,
        source_path=f"{chunk_id}.md",
        file_name=f"{chunk_id}.md",
        chunk_id=chunk_id,
        chunk_index=0,
        content=content,
        heading_path=None,
        score=score,
        keyword_score=keyword_score,
        vector_score=vector_score,
    )


def make_session(tmp_path):
    database_path = tmp_path / "decompose.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_decompose_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Integrated evaluation of cost schedule and emission performance",
            source_type="open_access_pdf",
            source_path="cost-schedule-emission.md",
            file_name="cost-schedule-emission.md",
            file_extension=".md",
            content_hash="decompose-cost-hash",
            raw_path="data/raw/cost-schedule-emission.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content=(
                    "Rock-filled concrete dam construction can be evaluated by cost, "
                    "schedule and emission performance using discrete event simulation."
                ),
                char_count=130,
                heading_path="Cost schedule emission",
                start_char=0,
                end_char=130,
            )
        ],
    )


def test_decompose_query_splits_obvious_cost_schedule_emission_question() -> None:
    result = decompose_query("RFC dam construction 的成本工期和碳排放怎么评估？")

    assert result.decomposed
    assert len(result.sub_queries) == 3
    assert "cost" in result.sub_queries[0]
    assert "schedule" in result.sub_queries[1]
    assert "emission" in result.sub_queries[2]


def test_decompose_query_keeps_single_topic_and_unsupported_questions_unchanged() -> None:
    single_topic = decompose_query("Are there studies about freeze-thaw resistance of rock-filled concrete?")
    unsupported = decompose_query("zqxjvblorptasticprotocol")

    assert not single_topic.decomposed
    assert single_topic.sub_queries == ("Are there studies about freeze-thaw resistance of rock-filled concrete?",)
    assert not unsupported.decomposed
    assert unsupported.sub_queries == ("zqxjvblorptasticprotocol",)


def test_decompose_query_splits_compactness_and_porosity_patterns() -> None:
    compactness = decompose_query("现场怎么判断堆石混凝土有没有灌满以及密实度够不够？")
    porosity = decompose_query("孔隙率会怎么影响堆石混凝土抗压表现？")

    assert compactness.decomposed
    assert len(compactness.sub_queries) == 2
    assert porosity.decomposed
    assert len(porosity.sub_queries) == 2


def test_merge_sub_query_results_deduplicates_by_chunk_id_and_keeps_provenance() -> None:
    shared = fake_result(
        chunk_id=1,
        title="Integrated evaluation of cost schedule and emission",
        content="The method evaluates cost, schedule and emission performance.",
        score=0.8,
        source_type="open_access_pdf",
        keyword_score=0.8,
        vector_score=0.7,
    )
    duplicate = fake_result(
        chunk_id=1,
        title="Integrated evaluation of cost schedule and emission",
        content="The method evaluates cost, schedule and emission performance.",
        score=0.7,
        source_type="open_access_pdf",
        keyword_score=0.7,
        vector_score=0.6,
    )
    weaker = fake_result(
        chunk_id=2,
        title="General RFC dam construction",
        content="Rock-filled concrete dam construction overview.",
        score=0.6,
    )

    merged = merge_sub_query_results(
        "RFC dam construction 的成本工期和碳排放怎么评估？",
        [
            SubQueryRetrievalResult("RFC dam construction cost evaluation", "hybrid", [shared, weaker]),
            SubQueryRetrievalResult("RFC dam construction emission life-cycle assessment", "hybrid", [duplicate]),
        ],
    )

    assert len(merged) == 2
    assert isinstance(merged[0], MergedEvidence)
    assert merged[0].chunk_id == 1
    assert merged[0].both_match
    assert len(merged[0].sub_queries) == 2
    assert "both_match=True" in merged[0].explanation


def test_decompose_query_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="question"):
        decompose_query("  ")
    with pytest.raises(ValueError, match="max_sub_queries"):
        decompose_query("成本和工期", max_sub_queries=0)


def test_decompose_retrieval_service_runs_sub_query_retrieval_and_merge(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)
    provider = DeterministicEmbeddingProvider(dimension=32)

    with TestingSessionLocal() as db:
        seed_decompose_documents(db)
        VectorIndexService(db, provider).build_index()

        outcome = DecomposeRetrievalService(db, provider).retrieve(
            "RFC dam construction 的成本工期和碳排放怎么评估？",
            retrieval_mode="hybrid",
            top_k=3,
        )

    assert outcome.decomposed_query.decomposed
    assert len(outcome.sub_query_results) == 3
    assert outcome.merged_results
    assert outcome.merged_results[0].chunk_id is not None
    assert outcome.merged_results[0].sub_queries
    assert "final_score" in outcome.merged_results[0].explanation
