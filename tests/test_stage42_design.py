from pathlib import Path


DESIGN_PATH = Path("docs/stage42_generation_quality_and_experience.md")


def read_design() -> str:
    return DESIGN_PATH.read_text(encoding="utf-8")


def test_stage42_design_documents_goal_baseline_and_main_tracks() -> None:
    design = read_design()

    for phrase in [
        "d7dfca1 Merge phase 41 post-import retrieval optimization",
        "codex/phase-42-generation-quality-and-experience",
        "documents=753",
        "indexable child chunks=19300",
        "91.52 / A / pass",
        "主线 A：生成质量校准",
        "主线 C：生产体验完善",
        "structured_final_answer",
        "answer_coverage=0.808 / citation_support=0.867 / safety_leak_check=1.000 / gate=pass",
    ]:
        assert phrase in design


def test_stage42_design_locks_phase_order_and_status_updates() -> None:
    design = read_design()

    for phrase in [
        "Phase 0：启动校准与规划落盘",
        "Phase 1：设计文档与测试合同",
        "Phase 2：Judge 评测集扩展",
        "Phase 3：低分样例分析与 prompt 微调",
        "Phase 4：长回答分段渲染",
        "Phase 5：会话管理 UX",
        "Phase 6：全量回归与 Stage 30",
        "Phase 7：浏览器 smoke",
        "Phase 8：文档与 Obsidian 收尾",
        "task_plan.md",
        "findings.md",
        "progress.md",
    ]:
        assert phrase in design


def test_stage42_design_documents_judge_contract_and_safety_outputs() -> None:
    design = read_design()

    for phrase in [
        "Stage 38 24 cases + Stage 41 12 queries",
        "默认 dry-run",
        "显式 --execute",
        "faithfulness",
        "answer_coverage",
        "citation_support",
        "refusal_correctness",
        "conciseness",
        "safety_leak_check",
        "risk_level",
        "短理由",
        "不得保存 raw answer",
        "raw_response",
        "reasoning_content",
        "Bearer token",
        "完整 chunk 正文",
        "六指标门槛",
    ]:
        assert phrase in design


def test_stage42_design_documents_frontend_and_conversation_contract() -> None:
    design = read_design()

    for phrase in [
        "段落级分段插入",
        "不做完整虚拟列表",
        "不引入 React/Vue/Node",
        "finalizeAgentStreamingMessage()",
        "sanitizeRenderedHtml",
        "citation popover",
        "AbortController",
        "hard delete",
        "DELETE /conversations/{conversation_id}",
        "PATCH /conversations/{conversation_id}",
        "Right-clicking a conversation opens a pointer-adjacent context menu",
        "must not switch/load that conversation",
        "message composer is fixed at the bottom",
        "left conversation list has its own scroll container",
        "citation detail drawer",
        "normalize_conversation_title",
    ]:
        assert phrase in design


def test_stage42_design_documents_verification_and_no_submission_boundary() -> None:
    design = read_design()

    for phrase in [
        "python -m pytest tests/test_stage42_design.py -q",
        "python -m pytest -q",
        "python scripts/score_stage30_quality.py",
        "python scripts/run_production_smoke.py",
        "390x844",
        "console errors=0",
        "不改变 Stage 30 评分规则",
        "不改变 provider 拓扑或数据源边界",
        "不让真实 API 成为 CI 或本地全量测试前提",
        "不执行 `git add`",
        "不创建 PR",
        "停在用户人工核验前",
    ]:
        assert phrase in design
