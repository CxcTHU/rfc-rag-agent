from pathlib import Path

from app.services.retrieval.hybrid_search import HybridSearchResult
from scripts.evaluate_stage29_real_quality import (
    Stage29Query,
    coverage_ratio,
    hit_at_k,
    load_queries,
    source_type_distribution,
    summarize_results,
)


def make_result(
    *,
    title: str,
    source_type: str,
    content: str,
    chunk_id: int = 1,
) -> HybridSearchResult:
    return HybridSearchResult(
        document_id=chunk_id,
        document_title=title,
        source_type=source_type,
        source_path=None,
        file_name=f"{chunk_id}.md",
        chunk_id=chunk_id,
        chunk_index=0,
        content=content,
        heading_path=None,
        score=1.0,
        keyword_score=1.0,
        vector_score=1.0,
    )


def test_load_queries_reads_stage29_schema(tmp_path) -> None:
    path = tmp_path / "queries.csv"
    path.write_text(
        "\n".join(
            [
                "query_id,question,category,expected_source_type,expected_answer_points,expected_refused,notes",
                "stage29_q,Question?,web,web_page,point one;point two,false,note",
            ]
        ),
        encoding="utf-8",
    )

    queries = load_queries(path)

    assert queries == [
        Stage29Query(
            query_id="stage29_q",
            question="Question?",
            category="web",
            expected_source_type="web_page",
            expected_answer_points=("point one", "point two"),
            expected_refused=False,
            notes="note",
        )
    ]


def test_hit_and_coverage_use_source_type_and_expected_points() -> None:
    query = Stage29Query(
        query_id="stage29_web",
        question="Why use RFC?",
        category="web",
        expected_source_type="web_page",
        expected_answer_points=("local rocks", "special concrete"),
        expected_refused=False,
        notes="",
    )
    results = [
        make_result(
            title="Filling the gaps in large concrete dams",
            source_type="web_page",
            content="RFC is made from local rocks that are bound by special concrete.",
        )
    ]

    coverage = coverage_ratio(results, query)

    assert hit_at_k(results, query, 1) is True
    assert coverage.ratio == 1.0
    assert coverage.covered_points == ("local rocks", "special concrete")


def test_source_type_distribution_and_summary() -> None:
    rows = [
        {
            "expected_refused": "false",
            "precision_at_1": "true",
            "precision_at_3": "true",
            "precision_at_5": "true",
            "coverage_ratio": "0.500",
            "refusal_matched": "",
            "source_type_distribution": "web_page:3;wikipedia:2",
            "status": "completed",
        },
        {
            "expected_refused": "true",
            "precision_at_1": "false",
            "precision_at_3": "false",
            "precision_at_5": "false",
            "coverage_ratio": "0.000",
            "refusal_matched": "true",
            "source_type_distribution": "standard_document:1",
            "status": "completed",
        },
    ]
    results = [
        make_result(title="A", source_type="web_page", content="a"),
        make_result(title="B", source_type="web_page", content="b", chunk_id=2),
        make_result(title="C", source_type="wikipedia", content="c", chunk_id=3),
    ]

    assert source_type_distribution(results) == "web_page:2;wikipedia:1"

    summary = summarize_results(rows, provider="jina", model_name="jina-embeddings-v3")

    assert summary["precision_at_1"] == "1.000"
    assert summary["avg_coverage_ratio"] == "0.500"
    assert summary["refusal_accuracy"] == "1.000"
    assert summary["source_type_distribution"] == "standard_document:1;web_page:3;wikipedia:2"
