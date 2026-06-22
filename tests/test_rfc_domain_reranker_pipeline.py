from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select

from app.db.models import Base, QuestionAnswerLog
from app.services.agent.service import AgentQueryResult
from scripts.reranker import build_dataset as dataset_builder
from scripts.reranker import collect_real_agent_cases as collector
from scripts.reranker import generate_synthetic_queries as synthetic


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_collect_real_agent_cases_dry_run_does_not_initialize_provider(tmp_path, monkeypatch) -> None:
    eval_queries = tmp_path / "eval_queries.jsonl"
    output = tmp_path / "real_agent_cases.jsonl"
    write_jsonl(
        eval_queries,
        [
            {"query_id": "q1", "question": "RFC construction compaction?", "category": "construction"},
            {"query_id": "q2", "question": "RFC hydration heat control?", "category": "hydration_heat"},
        ],
    )

    def fail_provider(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("dry-run must not initialize providers")

    monkeypatch.setattr(collector, "create_chat_model_provider", fail_provider)
    cases = collector.collect_real_agent_cases(
        eval_queries_path=eval_queries,
        output_path=output,
        limit=2,
        execute=False,
        log_answers=False,
    )

    assert [case.status for case in cases] == ["dry_run", "dry_run"]
    assert len(read_jsonl(output)) == 2


def test_collect_real_agent_cases_log_answers_requires_execute(tmp_path) -> None:
    with pytest_raises_value_error("log_answers requires execute=True"):
        collector.collect_real_agent_cases(
            eval_queries_path=tmp_path / "missing.jsonl",
            output_path=tmp_path / "out.jsonl",
            execute=False,
            log_answers=True,
        )


def test_collect_real_agent_cases_infers_balanced_target_categories() -> None:
    rows = [
        {"question": "How is RFC construction quality controlled?"},
        {"question": "影响堆石混凝土填充能力的关键因素有哪些？"},
        {"question": "RFC hydration heat and temperature control evidence?"},
        {"question": "堆石混凝土弹性模量有什么研究？"},
        {"question": "界面过渡区如何影响堆石混凝土的断裂模式？"},
        {"question": "Give an engineering application example for rock-filled concrete dams."},
        {"question": "请替我审核工程配合比并签字", "expected_refused": "true"},
    ]

    selected = collector.select_balanced_queries(rows, limit=7)

    assert [row["category"] for row in selected] == [
        "construction",
        "filling",
        "hydration_heat",
        "mechanics",
        "crack",
        "case",
        "refusal",
    ]


def test_collect_real_agent_cases_execute_can_write_qa_logs(tmp_path, monkeypatch) -> None:
    eval_queries = tmp_path / "eval_queries.jsonl"
    output = tmp_path / "real_agent_cases.jsonl"
    db_path = tmp_path / "qa.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    write_jsonl(eval_queries, [{"query_id": "q1", "question": "RFC construction?", "category": "construction"}])

    @dataclass(frozen=True)
    class FakeProvider:
        provider_name: str = "fake-chat"
        model_name: str = "fake-model"

    monkeypatch.setattr(collector, "create_database_engine", lambda _url: engine)
    monkeypatch.setattr(
        collector,
        "get_settings",
        lambda: SimpleNamespace(
            database_url=f"sqlite:///{db_path}",
            chat_model_provider="fake-chat",
            chat_model_name="fake-model",
            chat_model_api_key="",
            chat_model_base_url="",
            chat_model_temperature=0.0,
            chat_model_timeout_seconds=1,
            embedding_provider="fake-embedding",
            embedding_model_name="fake-embedding-model",
            embedding_api_key="",
            embedding_base_url="",
            embedding_dimension=None,
            embedding_timeout_seconds=1,
        ),
    )
    monkeypatch.setattr(collector, "create_chat_model_provider", lambda **_kwargs: FakeProvider())
    monkeypatch.setattr(collector, "create_embedding_provider", lambda **_kwargs: object())
    monkeypatch.setattr(
        collector,
        "run_agent_case",
        lambda **_kwargs: AgentQueryResult(
            question="RFC construction?",
            answer="Answer with citation [1].",
            tool_calls=[],
            sources=[SimpleNamespace(chunk_id=123)],
            citations=[1],
            refused=False,
        ),
    )

    cases = collector.collect_real_agent_cases(
        eval_queries_path=eval_queries,
        output_path=output,
        database_url=f"sqlite:///{db_path}",
        limit=1,
        execute=True,
        log_answers=True,
    )

    assert cases[0].status == "completed"
    assert cases[0].qa_log_written is True
    with engine.connect() as connection:
        logs = list(connection.execute(select(QuestionAnswerLog)).all())
    assert len(logs) == 1


def test_generate_synthetic_queries_dry_run(tmp_path, monkeypatch) -> None:
    sampled = tmp_path / "sampled_chunks.jsonl"
    output = tmp_path / "synthetic_queries.jsonl"
    write_jsonl(
        sampled,
        [
            {
                "chunk_id": 1,
                "document_id": 10,
                "chunk_type": "text",
                "document_title": "Dam Case",
                "content": "RFC construction placement and compaction passage.",
            }
        ],
    )

    monkeypatch.setattr(
        synthetic,
        "create_chat_model_provider",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("dry-run must not call provider")),
    )
    rows = synthetic.generate_synthetic_queries(
        input_path=sampled,
        output_path=output,
        limit=1,
        execute=False,
    )

    assert rows[0].status == "dry_run"
    assert "RFC" in rows[0].query
    assert len(read_jsonl(output)) == 1


def test_synthetic_query_filter_rejects_short_or_off_domain_queries() -> None:
    assert synthetic.query_is_usable("How does RFC construction compaction work?", min_chars=10)
    assert not synthetic.query_is_usable("RFC?", min_chars=10)
    assert not synthetic.query_is_usable("What is the weather today in Beijing?", min_chars=10)


def test_build_dataset_writes_splits_without_group_leakage(tmp_path) -> None:
    chunks = []
    positives = []
    for index in range(12):
        doc_id = 100 + index
        positive_chunk_id = index * 10 + 1
        chunks.extend(
            [
                {
                    "chunk_id": positive_chunk_id,
                    "document_id": doc_id,
                    "chunk_type": "text",
                    "content": f"RFC positive passage {index} about construction and hydration.",
                },
                {
                    "chunk_id": index * 10 + 2,
                    "document_id": doc_id,
                    "chunk_type": "text",
                    "content": f"RFC same document hard negative {index}.",
                },
                {
                    "chunk_id": index * 10 + 3,
                    "document_id": 900 + index,
                    "chunk_type": "text",
                    "content": f"RFC different document easy negative {index}.",
                },
            ]
        )
        positives.append(
            {
                "query": f"How should RFC construction case {index} be controlled?",
                "chunk_id": positive_chunk_id,
                "document_id": doc_id,
                "content": f"RFC positive passage {index} about construction and hydration.",
                "label": 1,
                "source": "qa_log",
            }
        )
    qa_pairs = tmp_path / "qa_log_pairs.jsonl"
    synthetic_path = tmp_path / "synthetic_queries.jsonl"
    chunks_path = tmp_path / "sampled_chunks.jsonl"
    output_dir = tmp_path / "dataset"
    write_jsonl(qa_pairs, positives)
    write_jsonl(synthetic_path, [])
    write_jsonl(chunks_path, chunks)

    summary = dataset_builder.build_dataset(
        qa_pairs_path=qa_pairs,
        synthetic_path=synthetic_path,
        chunks_path=chunks_path,
        output_dir=output_dir,
        seed=7,
        review_sample_size=5,
    )

    assert summary["total_rows"] == 36
    split_queries: dict[str, set[str]] = {}
    for split_name in ("train", "val", "test"):
        rows = read_jsonl(output_dir / f"reranker_{split_name}.jsonl")
        split_queries[split_name] = {row["query"] for row in rows}
        assert rows
        assert all(set(row) == {"query", "passage", "label"} for row in rows)
    assert split_queries["train"].isdisjoint(split_queries["val"])
    assert split_queries["train"].isdisjoint(split_queries["test"])
    assert split_queries["val"].isdisjoint(split_queries["test"])
    assert (output_dir / "manual_review_sample.csv").exists()


class pytest_raises_value_error:
    def __init__(self, expected: str) -> None:
        self.expected = expected

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:  # noqa: ANN001
        assert exc_type is ValueError
        assert self.expected in str(exc)
        return True
