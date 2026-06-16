from pathlib import Path


DESIGN_PATH = Path("docs/stage40_streaming_output_safety.md")
FRONTEND_PATH = Path("app/frontend/static/app.js")
INDEX_PATH = Path("app/frontend/index.html")
STYLES_PATH = Path("app/frontend/static/styles.css")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_stage40_design_documents_goal_chain_and_baseline() -> None:
    design = read(DESIGN_PATH)

    for phrase in [
        "c6e7927 Merge phase 39 production deployment",
        "默认 Agent 链路稳定为 `tool_calling_agent`",
        "Stage 30 保持 `91.52 / A / pass`",
        "/agent/query/stream",
        "fetch + ReadableStream 手动解析 SSE",
        "token buffer + requestAnimationFrame/定时 flush",
        "安全渲染文本/Markdown/citation",
        "AbortController 停止生成",
        "保留已收到 token 并标记“已停止生成”",
    ]:
        assert phrase in design


def test_stage40_design_documents_four_main_tracks_and_boundaries() -> None:
    design = read(DESIGN_PATH)

    for phrase in [
        "Markdown sanitize",
        "AbortController 停止生成",
        "中断后半截内容保留",
        "Token 渲染节流",
        "不做长回答虚拟列表",
        "不改变检索策略",
        "不改变 embedding/rerank/chat provider 拓扑",
        "不新增外部数据源或语料库",
        "不做登录系统",
        "不做部署优化",
    ]:
        assert phrase in design


def test_stage40_design_documents_sensitive_data_boundary() -> None:
    design = read(DESIGN_PATH)

    for phrase in [
        "API key",
        "Bearer token",
        "Authorization header",
        "raw provider response",
        "`reasoning_content`",
        "hidden thought",
        "完整 chunk 全文",
        "受限全文",
    ]:
        assert phrase in design


def test_stage40_design_documents_verification_and_no_submission() -> None:
    design = read(DESIGN_PATH)

    for phrase in [
        "node --check app/frontend/static/app.js",
        "tests/test_stage40_streaming_output_safety.py tests/test_frontend_app.py tests/test_agent_stream_api.py",
        "python -m pytest -q",
        "browser smoke desktop + 390x844 mobile",
        "最终不执行 `git add`、`git commit`、`git tag`、`git push`",
    ]:
        assert phrase in design


def test_frontend_contract_includes_local_sanitizer_hooks() -> None:
    script = read(FRONTEND_PATH)
    lowered = script.casefold()

    for phrase in [
        "function sanitizeRenderedHtml",
        "sanitizeRenderedHtml(",
        "renderAnswerWithCitationLinks",
        "citationReferenceHtml",
    ]:
        assert phrase in script

    for phrase in [
        "script",
        "iframe",
        "javascript:",
    ]:
        assert phrase in lowered

    assert 'name.startsWith("on")' in script

    assert "https://cdn" not in lowered
    assert "unpkg.com" not in lowered


def test_frontend_contract_includes_abort_and_stop_generation_ui() -> None:
    script = read(FRONTEND_PATH)
    index = read(INDEX_PATH)
    styles = read(STYLES_PATH)

    for phrase in [
        "activeAgentAbortController",
        "AbortController",
        "signal:",
        "abortAgentStream",
        "data-agent-submit",
        "command-button--stop",
        "停止生成",
        "已停止生成",
    ]:
        assert phrase in script or phrase in index or phrase in styles


def test_frontend_contract_includes_token_flush_scheduler() -> None:
    script = read(FRONTEND_PATH)

    for phrase in [
        "createAgentTokenFlushScheduler",
        "requestAnimationFrame",
        "flush",
        "flushNow",
        "metadata",
        "done",
        "error",
        "abort",
    ]:
        assert phrase in script

    assert ".chat-message--thinking .answer-text" not in read(STYLES_PATH)


def test_stream_parser_keeps_existing_sse_event_contract() -> None:
    script = read(FRONTEND_PATH)

    for event_name in [
        "token",
        "metadata",
        "done",
        "error",
        "agent_step",
        "tool_call_start",
        "tool_call_result",
    ]:
        assert f'event.name === "{event_name}"' in script or f'"{event_name}"' in script
