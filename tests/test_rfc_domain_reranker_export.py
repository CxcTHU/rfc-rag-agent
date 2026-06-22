import json

from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Chunk, Document, QuestionAnswerLog
from app.db.session import create_sqlite_engine
from scripts.reranker.export_training_pairs import (
    collect_eval_queries,
    export_reranker_step1_data,
    export_qa_log_pairs,
    sample_high_quality_chunks,
)


def make_session(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'reranker.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_reranker_fixture(db):
    document = Document(
        title="RFC密实度检测文献",
        source_type="institutional_access_pdf",
        source_path="data/raw/rfc.pdf",
        file_name="rfc.pdf",
        file_extension=".pdf",
        content_hash="reranker-doc",
        raw_path="data/raw/reranker-doc.pdf",
    )
    parent = Chunk(
        document=document,
        chunk_index=0,
        content="父块上下文不应进入采样。" * 20,
        char_count=200,
        heading_path="parent",
        start_char=0,
        end_char=200,
        chunk_type="text",
    )
    positive = Chunk(
        document=document,
        chunk_index=1,
        content="堆石混凝土密实度可以通过超声波检测、钻芯和现场质量控制指标综合判断。" * 4,
        char_count=148,
        heading_path="密实度",
        start_char=0,
        end_char=148,
        chunk_type="text",
        parent_chunk=parent,
    )
    negative = Chunk(
        document=document,
        chunk_index=2,
        content="拱坝结构会把水压力传递到两岸稳定基岩，适合狭窄峡谷地形。" * 4,
        char_count=128,
        heading_path="拱坝",
        start_char=149,
        end_char=277,
        chunk_type="text",
        parent_chunk=parent,
    )
    db.add(document)
    db.flush()
    db.add(
        QuestionAnswerLog(
            question="堆石混凝土密实度怎么检测？",
            answer="可用超声波等方法。[1]",
            retrieved_chunk_ids=f"[{positive.id},{negative.id}]",
            citations="[1]",
            model_provider="deterministic",
            model_name="test",
            retrieval_mode="hybrid",
            refused=False,
        )
    )
    db.commit()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_export_qa_log_pairs_marks_cited_rank_as_positive(tmp_path):
    SessionLocal = make_session(tmp_path)
    with SessionLocal() as db:
        seed_reranker_fixture(db)
        rows = export_qa_log_pairs(db)

    assert [row.label for row in rows] == [1, 0]
    assert rows[0].source == "qa_log_cited"
    assert rows[0].citation_index == 1
    assert rows[1].source == "qa_log_retrieved_negative"


def test_sample_high_quality_chunks_excludes_parent_rows(tmp_path):
    SessionLocal = make_session(tmp_path)
    with SessionLocal() as db:
        seed_reranker_fixture(db)
        rows = sample_high_quality_chunks(db, sample_size=10, seed=1)

    assert {row.chunk_type for row in rows} == {"text"}
    assert all("父块上下文" not in row.content for row in rows)
    assert len(rows) == 2


def test_collect_eval_queries_keeps_domain_questions(tmp_path):
    csv_path = tmp_path / "queries.csv"
    csv_path.write_text(
        "query_id,question,category,expected_answer_points,expected_refused\n"
        "q1,堆石混凝土密实度怎么检测？,quality,超声波,false\n"
        "q2,What is the weather today?,offtopic,,true\n",
        encoding="utf-8",
    )

    rows = collect_eval_queries([csv_path])

    assert len(rows) == 1
    assert rows[0].query_id == "q1"
    assert rows[0].expected_source_terms == "超声波"


def test_export_reranker_step1_data_writes_expected_files(tmp_path):
    SessionLocal = make_session(tmp_path)
    eval_path = tmp_path / "eval.csv"
    eval_path.write_text(
        "query_id,question,category,expected_source_type,expected_refused\n"
        "q1,RFC施工质量控制关注哪些指标？,construction,text,false\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "reranker_training"

    with SessionLocal() as db:
        seed_reranker_fixture(db)
        summary = export_reranker_step1_data(
            db,
            output_dir=output_dir,
            sample_size=10,
            seed=1,
            eval_query_files=[eval_path],
        )

    assert summary.qa_log_pairs == 2
    assert summary.sampled_chunks == 2
    assert summary.eval_queries == 1
    assert len(read_jsonl(output_dir / "qa_log_pairs.jsonl")) == 2
    assert len(read_jsonl(output_dir / "sampled_chunks.jsonl")) == 2
    assert len(read_jsonl(output_dir / "eval_queries.jsonl")) == 1


def test_export_reranker_step1_data_handles_uninitialized_database(tmp_path):
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'empty.sqlite').as_posix()}")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    output_dir = tmp_path / "reranker_training"

    with SessionLocal() as db:
        summary = export_reranker_step1_data(
            db,
            output_dir=output_dir,
            sample_size=10,
            seed=1,
            eval_query_files=[],
        )

    assert summary.qa_log_pairs == 0
    assert summary.sampled_chunks == 0
    assert summary.eval_queries == 0
    assert read_jsonl(output_dir / "qa_log_pairs.jsonl") == []
    assert read_jsonl(output_dir / "sampled_chunks.jsonl") == []
    assert read_jsonl(output_dir / "eval_queries.jsonl") == []
