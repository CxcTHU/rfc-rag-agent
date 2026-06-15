from pathlib import Path


DESIGN_PATH = Path("docs/stage37_tool_calling_loop_migration.md")


def test_stage37_design_documents_baseline_goal_and_flow() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "phase-36-complete -> 9516b22",
        "main / origin/main -> d747169",
        "Stage 30 = 91.52 / A / pass",
        "mode=\"tool_calling_agent\"",
        "planner LLM -> 检索工具 -> planner LLM -> answer LLM",
        "LLM(messages, tools)",
        "role=\"tool\"",
        "继续 loop",
    ]:
        assert phrase in design


def test_stage37_design_requires_real_tool_calling_loop() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "tool-calling 是模型用标准结构表达“我要调用工具”的协议",
        "loop 是外层 Agent 控制结构",
        "必须实现 tool-calling loop",
        "不是只给 provider 加一次 `tools` 参数",
        "多次 tool_calls",
        "重复 query 必须拦截",
        "工具错误必须收敛",
        "max_iterations",
    ]:
        assert phrase in design


def test_stage37_design_documents_provider_contract() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "OpenAI-compatible `tools`",
        "`tool_calls` 结构化解析",
        "`role=\"tool\"` 消息回灌",
        "deterministic provider 离线模拟单轮 tool_call、多轮 tool_call 和最终 answer",
        "旧 `generate()` 与 `stream_generate()` 行为保持兼容",
        "不保存 raw provider response",
    ]:
        assert phrase in design


def test_stage37_design_keeps_parallel_mode_and_boundaries() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for boundary in [
        "不引入 LangGraph",
        "不删除、不替换 `react_agent`",
        "不自动切默认",
        "不替换默认 chat provider",
        "不替换默认 embedding provider",
        "不替换默认 rerank provider",
        "不动 provider 拓扑",
        "不改 Stage 30 评分权重",
        "不新增外部数据源",
        "不接 `citation_validator`",
        "不做多用户隔离",
        "不做写入型 Agent 工具",
    ]:
        assert boundary in design


def test_stage37_design_documents_readonly_tools_and_safety() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "只暴露只读 `search_knowledge` / `hybrid_search_knowledge`",
        "tool result 回灌给模型时必须只包含必要的脱敏结构化摘要",
        "不暴露完整 chunk 全文",
        "内部规则",
        "raw provider response",
        "reasoning_content",
        "hidden thought",
        "API key",
        "Bearer token",
        "Authorization header",
        "受限全文",
    ]:
        assert phrase in design


def test_stage37_design_documents_comparison_and_smoke_contract() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "scripts/evaluate_stage37_tool_calling_vs_react.py",
        "stage37_tool_calling_vs_react_results.csv",
        "stage37_tool_calling_vs_react_summary.csv",
        "--execute",
        "stage37_tool_calling_vs_react_real_results.csv",
        "stage37_tool_calling_vs_react_real_summary.csv",
        "tiered provider",
        "Flash planner + V4-Pro answer",
        "missing_tool_backed_citations",
        "单跳定义题",
        "对比题",
        "多维问题",
        "中英术语题",
        "追问题",
        "evidence_insufficient",
        "off-topic 拒答题",
        "多跳检索题",
        "llm_call_count",
        "tool_call_count",
        "same_refusal_as_react",
        "same_top_source_as_react",
        "decision_candidate",
        "scripts/run_production_smoke.py",
        "tool_calling_agent",
        "浏览器 smoke：桌面 + 390x844 移动端",
    ]:
        assert phrase in design
