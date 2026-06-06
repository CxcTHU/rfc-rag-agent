from pathlib import Path


def test_stage_7_agent_design_documents_tool_boundaries() -> None:
    design = Path("docs/agent_design.md").read_text(encoding="utf-8")

    for tool_name in [
        "search_knowledge",
        "hybrid_search_knowledge",
        "answer_with_citations",
        "list_sources",
        "get_source_detail",
    ]:
        assert tool_name in design

    for required_boundary in [
        "只读",
        "不直接拼接 SQL",
        "不直接生成没有 citations 的回答",
        "不自动允许",
        "allow_write_actions=true",
    ]:
        assert required_boundary in design


def test_stage_7_agent_design_documents_flow_and_evaluation() -> None:
    design = Path("docs/agent_design.md").read_text(encoding="utf-8")

    for phrase in [
        "POST /agent/query",
        "AgentQueryRequest",
        "AgentQueryResponse",
        "tool_calls",
        "reasoning_summary",
        "scripts/evaluate_agent.py",
        "data/evaluation/agent_results.csv",
    ]:
        assert phrase in design
