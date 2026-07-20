from pathlib import Path


DESIGN_PATH = Path("docs/stage38_tool_calling_generation_quality.md")


def test_stage38_design_documents_baseline_goal_and_default_chain() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "phase-37-complete -> 62eff40",
        "main / origin/main -> 25344a8",
        "Stage 30 = 91.52 / A / pass",
        "default Agent mode = tool_calling_agent",
        "tool_calling_agent baseline Judge",
        "baseline vs structured_final_answer",
    ]:
        assert phrase in design


def test_stage38_design_documents_four_main_tracks() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "Judge 攻坚",
        "专属生成策略",
        "评测扩充",
        "默认链路回归",
        "20-30 条",
        "11+ 类场景",
    ]:
        assert phrase in design


def test_stage38_design_locks_judge_and_ab_contract() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "answer_coverage >= 0.80",
        "citation_support >= 0.80",
        "safety_leak_check >= 0.80",
        "当前默认 tool_calling_agent prompt",
        "structured_final_answer",
        "不调用 AgentToolbox.answer_with_citations 生成最终答案",
        "不能把 `review_required` 包装成 pass",
    ]:
        assert phrase in design


def test_stage38_design_keeps_tool_calling_native_final_synthesis() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "LLM(messages, tools) -> tool_calls -> role=\"tool\" feedback -> LLM final content",
        "evidence_answer_messages()",
        "citation_repair_messages()",
        "每个事实性句子贴近对应 `[N]` 引用",
        "citation repair 只能补引用，不得新增事实",
        "不允许把旧 `answer_with_citations` 工具硬接回 tool-calling 最终生成",
    ]:
        assert phrase in design


def test_stage38_design_documents_expanded_eval_categories() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for category in [
        "single_hop",
        "comparison",
        "multi_dimensional",
        "multi_hop",
        "numeric_comparison",
        "bilingual",
        "long_question",
        "ambiguous_query",
        "followup",
        "evidence_insufficient",
        "off_topic",
        "responsibility_boundary",
        "citation_repair",
        "evidence_convergence",
        "skip_tool",
        "duplicate_tool_call",
    ]:
        assert category in design


def test_stage38_design_keeps_provider_scoring_data_and_security_boundaries() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for boundary in [
        "不改 Stage 30 评分权重",
        "不替换默认 embedding provider",
        "不替换默认 rerank provider",
        "不新增外部数据源",
        "不引入 LangGraph",
        "不把 `citation_validator`",
        "不让真实 API 成为 CI 或本地全量 pytest 前提",
        "API key",
        "Bearer token",
        "Authorization header",
        "raw provider response",
        "reasoning_content",
        "hidden thought",
        "完整 chunk 全文",
        "受限全文",
    ]:
        assert boundary in design


def test_stage38_design_documents_final_artifacts_and_no_submission() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "docs/stage38_tool_calling_quality_decision.md",
        "docs/phase_reviews/phase-38.md",
        "python -m pytest -q",
        "python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass",
        "python scripts/run_production_smoke.py --execute",
        "browser smoke desktop + 390x844 mobile",
        "不执行 `git add`、`git commit`、`git tag`、`git push`",
    ]:
        assert phrase in design
