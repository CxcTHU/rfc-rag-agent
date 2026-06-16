from pathlib import Path


DESIGN_PATH = Path("docs/stage39_production_deployment.md")


def test_stage39_design_documents_baseline_and_goal() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "33b63e0 Merge phase 38 tool calling generation quality",
        "default Agent 链路已经稳定为 `tool_calling_agent`",
        "structured_final_answer",
        "Stage 30 保持 `91.52 / A / pass`",
        "可部署、可运维、可交付",
    ]:
        assert phrase in design


def test_stage39_design_documents_main_tracks() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "Dockerfile / docker-compose 更新",
        "结构化日志",
        "前端体验打磨",
        "部署文档与配置指南",
        "回归验证与人工核验前收尾",
    ]:
        assert phrase in design


def test_stage39_design_locks_non_goals() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for boundary in [
        "不动检索策略",
        "不动 prompt 策略",
        "不动 Stage 30 评分权重",
        "不替换默认 embedding provider",
        "不替换默认 rerank provider",
        "不新增外部数据源",
        "不让真实 API 成为 CI 或本地全量 pytest 前提",
        "不把 deterministic `citation_validator`",
    ]:
        assert boundary in design


def test_stage39_design_documents_sensitive_data_boundary() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "API key",
        "Bearer token",
        "Authorization header",
        "raw provider response",
        "`reasoning_content`",
        "hidden thought",
        "用户完整原始问题全文日志",
        "完整 chunk 全文",
        "受限全文",
    ]:
        assert phrase in design


def test_stage39_design_documents_docker_contract() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "chainlit run chainlit_app.py",
        "uvicorn app.main:app --host 0.0.0.0 --port 8000",
        "多阶段构建",
        "`pyproject.toml`",
        "`.dockerignore`",
        "`docker-compose.yml`",
        "healthcheck",
        "`GET /health`",
    ]:
        assert phrase in design


def test_stage39_design_documents_logging_contract() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "Python 标准 `logging`",
        "JSON 日志",
        "FastAPI middleware",
        "request_id",
        "query_received",
        "tool_call_executed",
        "answer_generated",
        "refusal_triggered",
        "不得记录用户完整问题",
    ]:
        assert phrase in design


def test_stage39_design_documents_frontend_and_deployment_contract() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "加载态",
        "中文友好错误",
        "`[N]` 引用可点击或 hover",
        "会话标题",
        "390x844",
        "`docs/deployment_guide.md`",
        "README Quick Start",
        "`.env.example`",
    ]:
        assert phrase in design


def test_stage39_design_documents_final_verification_and_no_submission() -> None:
    design = DESIGN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "python -m pytest -q",
        "python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass",
        "python scripts/run_production_smoke.py --execute",
        "docker build",
        "browser smoke desktop + 390x844 mobile",
        "最终不提交、不打 tag、不推送、不创建 PR",
    ]:
        assert phrase in design
