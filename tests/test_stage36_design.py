from pathlib import Path


DESIGN_PATH = Path("docs/stage36_generation_reliability_and_conversation_stability.md")


def test_stage36_design_documents_goal_baseline_and_flow() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "Stage 30 = 91.52 / A / pass",
        "Judge gate = 显式攻坚，不强行包装通过",
        "phase-35-complete -> 7877308",
        "main / origin/main -> dc751fb",
        "拒答可解释性升级",
        "生产 smoke 一键自动化",
        "outline-first + answer provider A/B",
    ]:
        assert phrase in design


def test_stage36_design_documents_refusal_explainability_requirements() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "off_topic",
        "evidence_insufficient",
        "改写建议",
        "检索命中的来源摘要",
        "单条摘要不超过 200 字符",
        "不暴露完整 chunk 全文",
        "不得让 LLM 编造检索摘要",
        "不修改 `/agent/query` 外部响应 schema",
    ]:
        assert phrase in design


def test_stage36_design_documents_production_smoke_contract() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "scripts/run_production_smoke.py",
        "--execute",
        "GET /health",
        "GET /quality-report",
        "GET /quality-report/data.json",
        "POST /agent/query",
        "POST /agent/query/stream",
        "stage36_production_smoke_results.csv",
        "validator_marker",
        "sensitive_field_detected",
    ]:
        assert phrase in design


def test_stage36_design_documents_judge_offline_gate() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "只做离线实验",
        "不接生产链路",
        "不改默认 provider 拓扑",
        "Judge gate 攻坚时限为不超过 2 周",
        "真实 Judge 样本不少于 20 条",
        "answer_coverage >= 0.80",
        "citation_support >= 0.80",
        "safety_leak_check >= 0.80",
        "不强行包装为通过",
    ]:
        assert phrase in design


def test_stage36_design_keeps_provider_scoring_and_data_boundaries() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for boundary in [
        "不接 `citation_validator`",
        "不替换默认 chat provider",
        "不替换默认 embedding provider",
        "不替换默认 rerank provider",
        "不动 chat provider 拓扑",
        "不改 Stage 30 评分权重",
        "不引入新外部数据源",
        "不做 tool-calling 协议迁移",
        "不做多用户隔离",
        "不做写入型 Agent 工具",
    ]:
        assert boundary in design

    for forbidden in [
        "API key",
        "Bearer token",
        "raw provider response",
        "reasoning_content",
        "hidden thought",
        "完整 chunk 全文",
        "受限全文",
    ]:
        assert forbidden in design
