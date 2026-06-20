from pathlib import Path


STAGE45_DESIGN_DOC = Path("docs/stage45_data_migration_multimodal_rag.md")


def test_stage45_design_document_records_two_tracks_and_boundaries() -> None:
    document = STAGE45_DESIGN_DOC.read_text(encoding="utf-8")

    assert "Track A: incremental SQLite to PostgreSQL data migration" in document
    assert "Track B: PDF image extraction" in document
    assert "VisionModelProvider" in document
    assert "image_description" in document
    assert "normal retrieval without special routing" in document
    assert "must not become CI or local full-test prerequisites" in document


def test_stage45_design_document_keeps_sensitive_values_out() -> None:
    document = STAGE45_DESIGN_DOC.read_text(encoding="utf-8")

    forbidden_literals = [
        "Bearer ey",
        "sk-",
        "JWT_SECRET_KEY=",
        "password=",
        'raw_response":',
        'reasoning_content":',
    ]
    for literal in forbidden_literals:
        assert literal not in document


def test_stage45_planning_records_main_baseline_and_boundaries() -> None:
    document = STAGE45_DESIGN_DOC.read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Phase 45 starts from `origin/main -> de3a96c" in readme
    assert "Track A: incremental SQLite to PostgreSQL data migration" in document
    assert "Track B: PDF image extraction" in document
    assert "stops before `git add`, commit, tag, push, or PR creation" in document


def test_stage45_findings_records_deterministic_vision_and_incremental_migration() -> None:
    document = STAGE45_DESIGN_DOC.read_text(encoding="utf-8")

    assert "The script reports inserted, skipped, and failed counts per table" in document
    assert "PyMuPDF" in document
    assert "DeterministicVisionModelProvider" in document
    assert "image_description" in document
