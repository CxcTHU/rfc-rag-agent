from pathlib import Path


DESIGN_PATH = Path("docs/stage43_multi_turn_quality_and_observability.md")


def read_design() -> str:
    return DESIGN_PATH.read_text(encoding="utf-8")


def test_stage43_design_documents_goal_baseline_and_tracks() -> None:
    design = read_design()

    for phrase in [
        "5850139 Merge pull request #9",
        "00e1424 Complete phase 42 generation quality and experience",
        "codex/phase-43-multi-turn-quality-and-observability",
        "91.52 / A / pass",
        "answer_coverage=0.828 / citation_support=0.856 / safety_leak_check=1.000 / gate=pass",
        "documents=753",
        "indexable child chunks=19300",
        "主线 A：多轮对话质量评测与会话内分层记忆",
        "主线 B：request_id 追踪与自包含诊断",
    ]:
        assert phrase in design


def test_stage43_design_locks_phase_order_and_status_updates() -> None:
    design = read_design()

    for phrase in [
        "Phase 0：启动校准与规划落盘",
        "Phase 1：设计文档与测试合同",
        "Phase 2：多轮对话评测集",
        "Phase 3：多轮质量 baseline 对比",
        "Phase 4：最小分层会话记忆",
        "Phase 5：多轮质量优化（条件执行）",
        "Phase 6：request_id 贯穿链路追踪",
        "Phase 7：健康诊断增强",
        "Phase 8：全量回归与 Stage 30",
        "Phase 9：浏览器 smoke",
        "Phase 10：文档与 Obsidian 收尾",
        "task_plan.md",
        "findings.md",
        "progress.md",
    ]:
        assert phrase in design


def test_stage43_design_documents_multi_turn_eval_contract() -> None:
    design = read_design()

    for phrase in [
        "data/evaluation/stage43_multi_turn_eval_cases.csv",
        "至少包含 16 组多轮对话",
        "每组 2-4 轮",
        "追问",
        "指代/省略",
        "澄清",
        "话题切换",
        "引用前轮内容",
        "用户纠错",
        "带约束追问",
        "多轮拒答",
        "scripts/evaluate_stage43_multi_turn.py",
        "--history-mode",
        "no_history",
        "recent_only",
        "summary_recent",
        "layered_memory",
        "data/evaluation/stage43_multi_turn_baseline_results.csv",
    ]:
        assert phrase in design


def test_stage43_design_documents_session_memory_boundaries() -> None:
    design = read_design()

    for phrase in [
        "app/services/conversation/session_memory.py",
        "entities",
        "retrieval_anchors",
        "不做跨会话长期记忆",
        "不做用户画像",
        "不做私人偏好记忆",
        "memory 只能辅助检索和上下文理解",
        "不能替代资料库证据",
        "回答中的 `[N]` 引用仍必须来自知识库 retrieval sources",
        "summary、recent messages 和 memory 均不得成为 citation source",
    ]:
        assert phrase in design


def test_stage43_design_documents_observability_and_health_contract() -> None:
    design = read_design()

    for phrase in [
        "X-Request-ID",
        "conversation loading",
        "summary assembly",
        "memory assembly",
        "query rewrite",
        "keyword / vector / hybrid retrieval",
        "embedding / rerank / chat provider call",
        "final response",
        "data/logs/request_traces.jsonl",
        "request_id",
        "conversation_id",
        "latency_ms",
        "citation_count",
        "GET /health/details",
        "DB 可连接",
        "FAISS index 文件是否存在",
        "deterministic provider 可用",
        "不做外部 provider 真实 ping",
    ]:
        assert phrase in design


def test_stage43_design_documents_verification_and_no_submission_boundary() -> None:
    design = read_design()

    for phrase in [
        "python -m pytest tests/test_stage43_design.py -q",
        "python -m pytest -q",
        "python scripts/score_stage30_quality.py",
        "python scripts/run_production_smoke.py",
        "390x844",
        "console errors=0",
        "横向溢出=false",
        "不改变 Stage 30 评分规则",
        "不改变 provider 拓扑或数据源边界",
        "不让真实 API 成为 CI 或本地全量测试前提",
        "不接 Sentry、Datadog、Prometheus、Grafana",
        "JSONL trace",
        "不执行 `git add`",
        "不创建 PR",
        "停在用户人工核验前",
    ]:
        assert phrase in design
