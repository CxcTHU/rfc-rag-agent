from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_phase66_review_records_status_and_receipts() -> None:
    review = read("docs/phase_reviews/phase-66.md")

    assert "Phase 66 Tool Calling Runtime Slimming" in review
    assert "closeout_sync_authorized" in review
    assert "PostgreSQL/pgvector judge-backed" in review
    assert "phase66_pairing_quality_non_regression" in review
    assert "review_required" in review

    for receipt_path in [
        "output/phase66/final/runtime-structure.json",
        "output/phase66/final/fault-matrix.json",
        "output/phase66/final/runtime-recovery.json",
        "output/phase66/evaluation/summary.json",
        "output/phase66/evaluation/review-packet.md",
        "output/phase66/evaluation_pg_judge_fixed/",
    ]:
        assert receipt_path in review


def test_phase66_architecture_documents_one_runtime_and_tool_inventory() -> None:
    architecture = read("docs/architecture.md")

    assert "Phase 66 Tool Calling Runtime Addendum" in architecture
    assert "user text -> ToolCallingAgentService -> RunCoordinator -> ToolExecutor -> registry adapters" in architecture
    assert "uploaded image -> ToolCallingAgentService -> RunCoordinator -> analyze_user_image" in architecture

    for tool_name in [
        "hybrid_search_knowledge",
        "search_tables",
        "search_figures",
        "analyze_user_image",
    ]:
        assert tool_name in architecture


def test_phase66_documentation_records_slimming_gates_and_deleted_flag() -> None:
    combined = "\n".join(
        [
            read("README.md"),
            read("docs/progress.md"),
            read("task_plan.md"),
            read("findings.md"),
            read("progress.md"),
        ]
    )

    assert "agent_run_coordinator_enabled" in combined
    assert "deleted" in combined
    assert "rollback through Git" in combined
    assert "tool_calling_service.py <= 260 lines" in combined
    assert "ToolCallingAgentService.query <= 80 lines" in combined
    assert "run_coordinator.py <= 120 lines" in combined


def test_phase66_obsidian_handoff_files_exist() -> None:
    phase_dir = ROOT / "obsidian-agent开发" / "阶段" / "阶段 66 - Tool Calling Runtime 真正瘦身"

    for filename in [
        "00-阶段总览.md",
        "01-开发记录.md",
        "02-收尾交接.md",
        "03-文件地图与恢复顺序.md",
    ]:
        path = phase_dir / filename
        assert path.exists(), path
        assert "阶段 66" in path.read_text(encoding="utf-8")
