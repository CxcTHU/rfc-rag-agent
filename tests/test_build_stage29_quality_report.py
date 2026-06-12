import json
import re

from scripts.build_stage29_quality_report import QualityRow, build_quality_rows, write_html


def test_build_stage29_quality_rows_marks_review_required_for_known_issues() -> None:
    summary = {
        "real_config_status": "completed",
        "precision_at_1": "0.600",
        "precision_at_3": "0.867",
        "precision_at_5": "0.933",
        "avg_coverage_ratio": "0.664",
        "refusal_total": "3",
        "refusal_accuracy": "1.000",
        "source_type_distribution": "standard_document:25;web_page:28;wikipedia:9",
    }
    results = [
        {
            "expected_refused": "false",
            "precision_at_5": "false",
            "coverage_ratio": "0.250",
        },
        {
            "expected_refused": "true",
            "precision_at_5": "false",
            "coverage_ratio": "0.000",
        },
    ]
    corpus_stats = {
        "documents": "635",
        "chunks": "12716",
        "sources": "673",
        "chunk_embeddings": "25432",
        "provider_distribution": "deterministic/hash-token-v1/dim=64:12716;jina/jina-embeddings-v3/dim=1024:12716",
        "document_source_distribution": "web_page:136;wikipedia:25;standard_document:9",
    }

    rows = build_quality_rows(
        summary,
        results,
        corpus_stats,
        full_tests_status="549 passed, 1 warning",
    )
    by_section = {row.section: row for row in rows}

    assert by_section["embedding_rebuild"].status == "completed"
    assert by_section["real_jina_quality"].risk == "medium"
    assert by_section["refusal_boundary"].status == "closed"
    assert by_section["known_issues"].status == "review_required"
    assert by_section["overall"].status == "review_required"


def test_write_html_embeds_parseable_quality_json(tmp_path) -> None:
    path = tmp_path / "quality_report.html"
    rows = [
        QualityRow(
            section="real_jina_quality",
            metric="precision_and_coverage",
            status="completed",
            value="p@5=0.933, coverage<0.5",
            risk="medium",
            evidence_file="data/evaluation/stage29_real_quality_summary.csv",
            recommendation="重点复核，不伪造成全部通过。",
        )
    ]

    write_html(path, rows)

    html = path.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="quality-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    assert "&quot;" not in match.group(1)
    payload = json.loads(match.group(1))
    assert payload[0]["section"] == "real_jina_quality"
    assert payload[0]["value"] == "p@5=0.933, coverage<0.5"
