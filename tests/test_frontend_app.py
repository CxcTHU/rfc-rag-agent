from fastapi.testclient import TestClient

import app.api.frontend as frontend_api
from app.main import create_app


def test_frontend_index_is_served() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "面向堆石混凝土的 RAG 智能检索系统" in response.text
    assert "RFC-RAG-Agent" in response.text
    assert 'data-view-target="ask"' in response.text
    assert 'data-view-target="library"' in response.text
    assert 'id="ask-view"' in response.text
    assert 'id="library-view"' in response.text
    assert "资料库工作台" in response.text
    assert "混合检索" in response.text
    assert "流式回答" in response.text
    assert "结构化分块" in response.text
    assert "/static/app.js" in response.text
    assert 'class="hero-layout"' in response.text
    assert 'class="demo-panel"' in response.text
    assert 'id="agent-panel"' in response.text
    assert 'id="library-panel"' in response.text
    assert 'data-sources-body' in response.text
    assert 'data-documents-body' in response.text
    assert 'data-source-filter' in response.text
    assert '<div class="operations-grid" hidden style="display: none">' in response.text
    assert '<div class="answer-grid" hidden style="display: none">' in response.text
    assert 'data-chat-form' in response.text
    assert 'data-agent-form' in response.text
    assert 'data-agent-mode-status' in response.text
    assert 'class="advanced-settings"' in response.text
    assert "<summary>高级设置</summary>" in response.text
    assert "检索候选数" in response.text
    assert "最大工具调用数" in response.text
    assert "指定来源 ID" in response.text
    assert "source_id" not in response.text
    assert '<select data-agent-mode' not in response.text
    assert '<option value="agentic">agentic</option>' not in response.text
    assert 'data-agent-tools-list' in response.text
    assert 'data-agent-chat-list' in response.text
    assert 'data-conversation-list' in response.text
    assert 'data-new-conversation' in response.text
    assert 'data-delete-conversation' in response.text
    assert 'data-refresh-conversations' in response.text
    assert 'class="chat-messages"' in response.text
    assert 'data-citations-list' in response.text
    assert 'data-search-form' in response.text
    assert '<option value="hybrid">hybrid</option>' in response.text
    assert 'data-chunks-list' in response.text
    assert 'data-sync-sources' in response.text


def test_frontend_static_assets_are_served() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")
    script = response.text.replace("\r\n", "\n")

    assert response.status_code == 200
    assert "apiEndpoints" in response.text
    assert "/sources" in response.text
    assert "/documents" in response.text
    assert "/chat" in response.text
    assert "/agent/query" in response.text
    assert "/conversations" in response.text
    assert "/search/vector" in response.text
    assert "/search/hybrid" in response.text
    assert "renderSources" in response.text
    assert "renderCitations" in response.text
    assert "renderAgentToolCalls" in response.text
    assert "renderAgentWorkflowSteps" in response.text
    assert "appendAgentUserMessage" in response.text
    assert "appendAgentAssistantMessage" in response.text
    assert "appendAgentSummaryMessage" in response.text
    assert "appendAgentThinkingMessage" in response.text
    assert "appendAgentLiveStep" in response.text
    assert "liveAgentEventView" in response.text
    assert "agentThoughtHtml" in response.text
    assert "agent-thinking-status" in response.text
    assert "agent-thought-panel" in response.text
    assert "data-agent-live-steps" in response.text
    assert "agent_step" in response.text
    assert "tool_call_start" in response.text
    assert "tool_call_result" in response.text
    assert "onAgentStep" in response.text
    assert "onToolCallStart" in response.text
    assert "onToolCallResult" in response.text
    assert "appendAgentErrorMessage" in response.text
    assert "正在思考" in response.text
    assert "pendingThinkingMessage?.remove()" in response.text
    assert "生成失败" in response.text
    assert "setConversationListPlaceholder" in response.text
    assert "加载失败" in response.text
    assert "loadAgentConversations" in response.text
    assert "loadConversationMessages" in response.text
    assert "createAgentConversation" in response.text
    assert "deleteCurrentConversation" in response.text
    assert "agentRequestInFlight" in response.text
    assert "setAgentBusy" in response.text
    assert "setAgentPanelStatus" in response.text
    assert "querySelectorAll" in response.text
    assert "bindViewNavigation" in response.text
    assert "switchView" in response.text
    assert "[data-view-target]" in response.text
    assert "[data-view]" in response.text
    assert "timeoutMs: 45000" in response.text
    assert "请求超时" in response.text
    assert "pendingUserMessage.remove()" not in response.text
    assert "body.conversation_id = state.currentConversationId" in response.text
    assert "scrollAgentChatToBottom" in response.text
    assert 'insertAdjacentHTML(\n    "beforeend"' in script
    assert "/agent/query/stream" in response.text
    assert "streamAgentQuery" in response.text
    assert "response.body" in response.text
    assert "getReader()" in response.text
    assert "TextDecoder" in response.text
    assert "parseSseEvent" in response.text
    assert "consumeSseBuffer" in response.text
    assert "async function consumeSseBuffer" in response.text
    assert "await consumeSseBuffer" in response.text
    assert "waitForAgentTokenPaint" in response.text
    assert "await waitForAgentTokenPaint()" in response.text
    assert "await handlers.onToken" in response.text
    assert "finalizeAgentStreamingMessage" in response.text
    assert "appendTokenToAgentMessage" in response.text
    assert 'setAgentPanelStatus(result?.refused ? "refused" : "answered")' in response.text
    assert '"Accept": "text/event-stream"' in response.text
    assert "apiEndpoints.agentStream" in response.text
    assert "workflow_steps" in response.text
    assert "iteration_count" in response.text
    assert "invalid_citations" in response.text
    assert "refusal_category" in response.text
    assert "formatRefusalCategory" in response.text
    assert "responsibility_gate_triggered" in response.text
    assert "updateAgentModeStatus" in response.text
    assert "[data-agent-mode-status]" in response.text
    assert "[data-agent-mode]" not in response.text
    assert 'body.mode = "agentic"' not in response.text
    assert 'mode: "react_agent"' in response.text
    assert 'updateAgentModeStatus("auto")' in response.text
    assert "reindexSource" in response.text

    styles = client.get("/static/styles.css")
    assert styles.status_code == 200
    assert "[hidden]" in styles.text
    assert "display: none !important" in styles.text
    assert "hero-layout" in styles.text
    assert "demo-panel" in styles.text
    assert "view-section" in styles.text
    assert "advanced-settings" in styles.text
    assert "advanced-settings-grid" in styles.text
    assert ".advanced-settings:not([open]) .advanced-settings-grid" in styles.text
    assert 'aria-current="page"' in styles.text
    assert "linear-gradient" in styles.text
    assert "chat-message--thinking" in styles.text
    assert "chat-message--error" in styles.text
    assert "thinking-text" in styles.text
    assert "agent-live-steps" in styles.text
    assert "agent-live-step" in styles.text
    assert "agent-thinking-status" in styles.text
    assert "agent-thought-panel" in styles.text
    assert "overflow-wrap: anywhere" in styles.text


def test_quality_report_is_served_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-report")

    assert response.status_code == 200
    assert "阶段 30 RAG 质量评分与诚实门禁" in response.text
    assert "只读质量评分报告" in response.text
    assert 'id="overall-score"' in response.text
    assert 'id="grade"' in response.text
    assert 'id="release-decision"' in response.text
    # 阶段 30 报告保持只读筛选、风险队列与导出。
    assert 'id="filter-section"' in response.text
    assert 'id="filter-risk"' in response.text
    assert 'id="risk-queue"' in response.text
    assert 'id="export-csv"' in response.text
    assert 'id="export-json"' in response.text
    assert "当前不执行 git add、commit、tag、push 或 PR" in response.text


def test_quality_report_data_json_is_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-report/data.json")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    # 应包含阶段 30 质量评分汇总行，且不泄露敏感字段。
    if payload:
        assert {"dimension", "weight", "score", "status"}.issubset(payload[0].keys())
        serialized = response.text.lower()
        assert "api_key" not in serialized
        assert "bearer" not in serialized
        assert "raw_response" not in serialized


def test_quality_review_workbench_is_served_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-review")

    assert response.status_code == 200
    assert "阶段 30 人工复核工作台" in response.text
    assert 'id="case-list"' in response.text
    assert "/quality-review/data.json" in response.text
    assert "/quality-review/reviews" in response.text
    assert "接受低分判断" in response.text
    assert "检索或来源标签需调优" in response.text


def test_quality_review_data_json_merges_stage30_artifacts() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-review/data.json")

    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "cases" in payload
    assert int(payload["summary"]["case_count"]) >= 1
    first_case = payload["cases"][0]
    assert {"query_id", "question", "judge", "deductions", "review_status"}.issubset(
        first_case.keys()
    )
    assert "semantic_average" in first_case["judge"]
    assert "rule_based_coverage_ratio" in first_case
    serialized = response.text.lower()
    assert "api_key" not in serialized
    assert "bearer" not in serialized
    assert "authorization" not in serialized
    assert "raw_response" not in serialized


def test_quality_review_decision_can_be_saved_to_local_csv(tmp_path, monkeypatch) -> None:
    review_path = tmp_path / "stage30_human_review.csv"
    monkeypatch.setattr(frontend_api, "STAGE30_HUMAN_REVIEW_PATH", review_path)
    client = TestClient(create_app())

    response = client.post(
        "/quality-review/reviews",
        json={
            "query_id": "stage29_wiki_dam_applications",
            "review_decision": "accept_judge_low_score",
            "reviewer_note": "低分合理，Top-5 来源类型不匹配。",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "saved"
    assert review_path.exists()

    data_response = client.get("/quality-review/data.json")
    reviewed = [
        case
        for case in data_response.json()["cases"]
        if case["query_id"] == "stage29_wiki_dam_applications"
    ][0]
    assert reviewed["human_review"]["review_decision"] == "accept_judge_low_score"
    assert "Top-5" in reviewed["human_review"]["reviewer_note"]

    update_response = client.post(
        "/quality-review/reviews",
        json={
            "query_id": "stage29_wiki_dam_applications",
            "review_decision": "needs_retrieval_tuning",
            "reviewer_note": "改判为检索调优。",
        },
    )
    assert update_response.status_code == 200
    rows = review_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2
    assert "needs_retrieval_tuning" in rows[1]


def test_quality_review_rejects_sensitive_review_note(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(frontend_api, "STAGE30_HUMAN_REVIEW_PATH", tmp_path / "review.csv")
    client = TestClient(create_app())

    response = client.post(
        "/quality-review/reviews",
        json={
            "query_id": "stage29_wiki_dam_applications",
            "review_decision": "accept_judge_low_score",
            "reviewer_note": "raw_response should not be saved",
        },
    )

    assert response.status_code == 400


def test_quality_report_export_csv_download() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-report/export.csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "stage30_quality_summary.csv" in response.headers.get("content-disposition", "")
    assert "dimension" in response.text


def test_favicon_request_does_not_404() -> None:
    client = TestClient(create_app())

    response = client.get("/favicon.ico")

    assert response.status_code == 204
