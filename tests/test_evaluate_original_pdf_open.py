from __future__ import annotations

from scripts.evaluate_original_pdf_open import build_cases, evaluate_case, join_url


def test_build_cases_forces_included_document_and_samples_sources() -> None:
    documents = [
        {
            "id": 10,
            "source_type": "institutional_access_pdf",
            "file_extension": "pdf",
            "file_name": "a.pdf",
            "open_url": "/documents/10/open",
        },
        {
            "id": 11,
            "source_type": "institutional_access_pdf",
            "file_extension": "pdf",
            "file_name": "b.pdf",
            "open_url": "/documents/11/open",
        },
        {
            "id": 2073,
            "source_type": "institutional_access_pdf",
            "file_extension": "pdf",
            "file_name": "target.pdf",
            "open_url": "/documents/2073/open",
        },
        {
            "id": 20,
            "source_type": "metadata_record",
            "file_extension": "",
            "file_name": "",
            "open_url": None,
        },
    ]

    cases = build_cases(
        documents,
        limit=2,
        per_source=1,
        include_document_ids={2073},
        source_types={"institutional_access_pdf"},
    )

    assert [case.document_id for case in cases] == [2073, 10]
    assert all(case.source_type == "institutional_access_pdf" for case in cases)


def test_evaluate_case_fails_when_open_url_is_missing() -> None:
    row = evaluate_case(
        "http://example.test",
        build_cases(
            [
                {
                    "id": 1,
                    "source_type": "institutional_access_pdf",
                    "file_extension": "pdf",
                    "file_name": "missing.pdf",
                    "open_url": None,
                }
            ],
            limit=1,
            per_source=1,
            include_document_ids={1},
            source_types={"institutional_access_pdf"},
        )[0],
        run_at="2026-07-09T00:00:00+00:00",
        timeout_seconds=0.1,
    )

    assert row["status"] == "failed"
    assert row["error_summary"] == "missing_open_url"
    assert row["open_url_present"] == "false"


def test_join_url_keeps_absolute_urls_and_joins_relative_paths() -> None:
    assert join_url("http://example.test/app", "https://cdn.example.test/file.pdf") == (
        "https://cdn.example.test/file.pdf"
    )
    assert join_url("http://example.test/app", "/documents/1/open") == (
        "http://example.test/documents/1/open"
    )
