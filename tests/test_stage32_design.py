from pathlib import Path


def test_stage32_design_documents_react_actions_and_tool_boundaries() -> None:
    design = Path("docs/stage32_react_agent_observability.md").read_text(
        encoding="utf-8"
    )

    for phrase in [
        "search_knowledge",
        "rewrite_query",
        "answer_with_citations",
        "refuse",
        "final_answer",
        "AgentToolbox",
        "BrainService",
        "responsibility_gate",
    ]:
        assert phrase in design

    for forbidden_boundary in [
        "不接受写入型 action",
        "不新增爬虫",
        "不新增外部资料来源",
        "不改变 `/chat` 默认链路",
    ]:
        assert forbidden_boundary in design


def test_stage32_design_documents_stream_events_and_safety() -> None:
    design = Path("docs/stage32_react_agent_observability.md").read_text(
        encoding="utf-8"
    )

    for event_name in [
        "agent_step",
        "tool_call_start",
        "tool_call_result",
        "token",
        "metadata",
        "done",
        "error",
    ]:
        assert event_name in design

    for safety_phrase in [
        "不展示模型原始 hidden thought",
        "供应商原始响应",
        "敏感凭据",
        "授权头",
        "deterministic provider",
    ]:
        assert safety_phrase in design
