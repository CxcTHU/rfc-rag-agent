"""Tests for stage 21 agentic evaluation script and design doc."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_design_doc_exists():
    doc = ROOT / "docs" / "stage21_langgraph_agentic_rag.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "LangGraph" in text
    assert "AgenticState" in text
    assert "MAX_ITERATIONS" in text
    assert "responsibility_gate" in text
    assert "接入门槛" in text


def test_design_doc_covers_completion_criteria():
    doc = ROOT / "docs" / "stage21_langgraph_agentic_rag.md"
    text = doc.read_text(encoding="utf-8")
    for keyword in [
        "pyproject.toml",
        "deterministic",
        "迭代上界",
        "citations",
        "拒答",
        "coverage_ratio",
        "p@1",
        "deep_top1",
        "/search",
        "/chat",
        "/agent/query",
        "/quality-report",
    ]:
        assert keyword in text, f"Missing keyword: {keyword}"


def test_langgraph_in_pyproject():
    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert "langgraph" in text


def test_agentic_module_structure():
    agentic = ROOT / "app" / "services" / "agentic"
    assert agentic.is_dir()
    assert (agentic / "__init__.py").exists()
    assert (agentic / "state.py").exists()
    assert (agentic / "nodes.py").exists()
    assert (agentic / "graph.py").exists()


def test_eval_script_exists():
    script = ROOT / "scripts" / "evaluate_stage21_agentic_rag.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "baseline_hybrid" in text
    assert "agentic_rag" in text
    assert "coverage_ratio" in text
    assert "precision_at_1" in text
    assert "delta_p1" in text


def test_agent_schema_ignores_retired_mode():
    from app.schemas.agent import AgentQueryRequest
    req = AgentQueryRequest(question="test", mode="agentic")
    assert not hasattr(req, "mode")
    req_default = AgentQueryRequest(question="test")
    assert not hasattr(req_default, "mode")
