from pathlib import Path

from scripts.seed_chinese_standards_metadata import (
    METADATA_ONLY_TERMS,
    STANDARDS,
    candidate_from_standard,
    seed_standards,
    standard_markdown,
)


def test_seed_contains_priority_chinese_hydraulic_standards() -> None:
    standard_numbers = {record.standard_no for record in STANDARDS}

    assert "NB/T 10077-2018" in standard_numbers
    assert "DL/T 5806-2020" in standard_numbers
    assert "GB 50496-2018" in standard_numbers
    assert "SL/T 352-2020" in standard_numbers
    assert "DL/T 5330-2015" in standard_numbers


def test_sl_314_is_recorded_as_rcc_correction_not_rfc_standard() -> None:
    sl_314 = next(record for record in STANDARDS if record.standard_no == "SL 314-2018")

    assert sl_314.title == "碾压混凝土坝设计规范"
    assert "纠错" in sl_314.notes
    assert "rfc_standard" not in sl_314.category
    assert "comparison_standard" in sl_314.category


def test_standard_markdown_is_metadata_only_and_searchable() -> None:
    record = next(record for record in STANDARDS if record.standard_no == "DL/T 5806-2020")
    markdown = standard_markdown(record)

    assert "仅包含公开题录" in markdown
    assert "不包含受版权或购买限制的标准正文条文" in markdown
    assert "堆石混凝土施工" in markdown
    assert METADATA_ONLY_TERMS in markdown


def test_candidate_from_standard_preserves_standard_document_type(tmp_path: Path) -> None:
    record = next(record for record in STANDARDS if record.standard_no == "NB/T 10077-2018")
    card_path = tmp_path / "nb_t_10077.md"

    candidate = candidate_from_standard(record, card_path, "collected")

    assert candidate.source_type == "standard_document"
    assert candidate.access_rights == "metadata"
    assert candidate.language == "zh"
    assert candidate.local_path == str(card_path)
    assert "metadata_only" in candidate.license_or_terms


def test_seed_dry_run_does_not_write_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "cards"
    manifest_path = tmp_path / "manifest.csv"
    results_path = tmp_path / "results.csv"

    candidates, results = seed_standards(
        output_dir=output_dir,
        manifest_path=manifest_path,
        results_path=results_path,
        dry_run=True,
    )

    assert len(candidates) == len(STANDARDS)
    assert len(results) == len(STANDARDS)
    assert not manifest_path.exists()
    assert not results_path.exists()
    assert list(output_dir.glob("*.md")) == []
