from pathlib import Path


def test_stage45_design_document_records_two_tracks_and_boundaries() -> None:
    document = Path("docs/stage45_data_migration_multimodal_rag.md").read_text(encoding="utf-8")

    assert "Track A: incremental SQLite to PostgreSQL data migration" in document
    assert "Track B: PDF image extraction" in document
    assert "VisionModelProvider" in document
    assert "image_description" in document
    assert "normal retrieval without special routing" in document
    assert "must not become CI or local full-test prerequisites" in document


def test_stage45_design_document_keeps_sensitive_values_out() -> None:
    document = Path("docs/stage45_data_migration_multimodal_rag.md").read_text(encoding="utf-8")

    forbidden_literals = [
        "Bearer ey",
        "sk-",
        "JWT_SECRET_KEY=",
        "password=",
        "raw_response\":",
        "reasoning_content\":",
    ]
    for literal in forbidden_literals:
        assert literal not in document


def test_stage45_planning_records_ten_phases_and_main_baseline() -> None:
    task_plan = Path("task_plan.md").read_text(encoding="utf-8")

    assert "10 个 Phase" in task_plan
    assert "origin/main -> de3a96c" in task_plan
    assert "codex/phase-45-data-migration-multimodal-rag" in task_plan
    assert "不要执行 git add、git commit、git tag、git push" in task_plan


def test_stage45_findings_records_deterministic_vision_and_incremental_migration() -> None:
    findings = Path("findings.md").read_text(encoding="utf-8")

    assert "数据迁移按表增量" in findings
    assert "PyMuPDF" in findings
    assert "DeterministicVisionModelProvider" in findings
    assert "image_description chunk 统一检索" in findings
