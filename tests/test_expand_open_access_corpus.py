"""阶段 18：开放获取扩充管线纯函数测试（不联网、不下载）。"""

import csv

from app.services.source_collection import SourceCandidate
from scripts.expand_open_access_corpus import (
    append_manifest_rows,
    is_permissive_open_access,
    manifest_row_from_candidate,
)


def _candidate(**kwargs) -> SourceCandidate:
    base = {
        "source_id": "openalex_test",
        "title": "Rock-Filled Concrete Test Paper",
        "pdf_url": "https://example.org/test.pdf",
        "url": "https://example.org/test",
    }
    base.update(kwargs)
    return SourceCandidate(**base)


def test_permissive_license_accepts_cc_by_and_oa_status() -> None:
    assert is_permissive_open_access(_candidate(license_or_terms="cc-by"))
    assert is_permissive_open_access(_candidate(license_or_terms="CC BY 4.0"))
    assert is_permissive_open_access(_candidate(license_or_terms="cc-by-nc-nd"))
    assert is_permissive_open_access(_candidate(access_rights="gold"))
    assert is_permissive_open_access(_candidate(access_rights="green"))


def test_permissive_license_rejects_unknown_and_closed() -> None:
    assert not is_permissive_open_access(_candidate(license_or_terms="", access_rights="unknown"))
    assert not is_permissive_open_access(_candidate(license_or_terms="all rights reserved", access_rights="closed"))


def test_manifest_row_marks_open_access_permission() -> None:
    row = manifest_row_from_candidate(
        _candidate(license_or_terms="cc-by", local_path="data/fulltext/open_access_auto/x.pdf")
    )
    assert row["source_type"] == "open_access_pdf"
    assert row["access_rights"] == "open access"
    assert row["license_or_terms"] == "cc-by"
    assert "stage18" in row["notes"]


def test_append_manifest_rows_dedupes_by_local_path(tmp_path) -> None:
    manifest = tmp_path / "manifest.csv"
    row = manifest_row_from_candidate(
        _candidate(license_or_terms="cc-by", local_path="data/fulltext/open_access_auto/a.pdf")
    )
    added_first = append_manifest_rows(manifest, [row])
    added_second = append_manifest_rows(manifest, [row])  # same local_path -> no dup
    assert added_first == 1
    assert added_second == 0

    with manifest.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert sum(1 for r in rows if r["local_path"].endswith("a.pdf")) == 1
