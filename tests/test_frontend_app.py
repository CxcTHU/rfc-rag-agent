from fastapi.testclient import TestClient

import app.api.frontend as frontend_api
from app.main import create_app


def test_frontend_index_is_served() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "RAG" in response.text
    assert "RFC-RAG-Agent" in response.text
    assert 'data-view-target="ask"' in response.text
    assert 'data-view-target="library"' in response.text
    assert 'id="ask-view"' in response.text
    assert 'id="library-view"' in response.text
    assert "agent-workspace-panel" in response.text
    assert "operations-grid" in response.text
    assert "answer-grid" in response.text
    assert "data-agent-form" in response.text
    assert "data-auth-login-form" in response.text
    assert "data-auth-register-form" in response.text
    assert "data-auth-screen" in response.text
    assert "data-auth-mode=\"login\"" in response.text
    assert "data-auth-mode=\"register\"" in response.text
    assert "创建账号" in response.text
    assert "登录后继续" in response.text
    assert "data-workspace-band" in response.text
    assert "data-auth-logout" in response.text
    assert "data-auth-status" in response.text
    assert "data-auth-username" in response.text
    assert "/static/app.js?v=phase51-followup-toolcalling-fix1" in response.text
    assert "/static/styles.css?v=phase51-followup-toolcalling-fix1" in response.text
    assert 'class="hero-layout"' in response.text
    assert "hero-kicker" not in response.text
    assert 'class="demo-panel agent-workspace-panel"' in response.text
    assert "data-home-link" in response.text
    assert 'id="agent-panel"' in response.text
    assert 'id="library-panel"' in response.text
    assert 'data-sources-body' in response.text
    assert 'data-documents-body' in response.text
    assert 'data-source-filter' in response.text
    assert '<div class="operations-grid" hidden style="display: none">' in response.text
    assert '<div class="answer-grid" hidden style="display: none">' in response.text
    assert 'data-chat-form' in response.text
    assert 'data-agent-form' in response.text
    assert 'data-agent-submit' in response.text
    assert 'data-agent-mode-status' not in response.text
    assert 'class="advanced-settings"' not in response.text
    assert "advanced-settings" not in response.text
    assert "data-agent-mode-status" not in response.text
    assert "data-agent-max-tool-calls" not in response.text
    assert "source_id" not in response.text
    assert "source_id" not in response.text
    assert '<select data-agent-mode' not in response.text
    assert '<option value="agentic">agentic</option>' not in response.text
    assert 'data-agent-tools-list' in response.text
    assert 'data-agent-chat-list' in response.text
    assert 'data-conversation-list' in response.text
    assert 'data-conversation-title' in response.text
    assert 'data-new-conversation' in response.text
    assert 'data-rename-conversation' in response.text
    assert 'data-delete-conversation' in response.text
    assert 'data-refresh-conversations' in response.text
    assert 'class="agent-chat-layout"' in response.text
    assert 'class="conversation-sidebar"' in response.text
    assert 'class="conversation-main"' in response.text
    assert 'data-conversation-menu' in response.text
    assert '<select data-conversation-list' not in response.text
    assert 'class="chat-messages"' in response.text
    assert 'data-citations-list' in response.text
    assert 'data-search-form' in response.text
    assert '<option value="hybrid">hybrid</option>' in response.text
    assert 'data-chunks-list' in response.text
    assert 'data-sync-sources' in response.text
    assert 'data-citation-drawer' in response.text
    assert 'data-citation-drawer-list' in response.text
    assert 'data-close-citation-drawer' in response.text


def test_frontend_static_assets_are_served() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")
    script = response.text.replace("\r\n", "\n")

    assert response.status_code == 200
    assert "apiEndpoints" in response.text
    assert "/auth/register" in response.text
    assert "/auth/login" in response.text
    assert "/auth/me" in response.text
    assert "AUTH_TOKEN_STORAGE_KEY" in response.text
    assert "authRememberMeSelected" in response.text
    assert "window.sessionStorage" in response.text
    assert "authHeaders" in response.text
    assert "Authorization" in response.text
    assert "Bearer" in response.text
    assert "submitAuthLogin" in response.text
    assert "submitAuthRegister" in response.text
    assert "loadCurrentUserFromToken" in response.text
    assert "ensureAuthenticated" in response.text
    assert "setAuthMode" in response.text
    assert "authErrorMessage" in response.text
    assert "setAuthHelp" in response.text
    assert "error.status = response.status" in response.text
    assert "error.url = url" in response.text
    assert "用户名至少 3 位" in response.text
    assert "密码需为 8 到 72 位字符" in response.text
    assert "请先登录或创建账号，再使用 Agent 对话。" in response.text
    assert "登录后加载会话" in response.text
    assert "window.localStorage" in response.text
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
    assert "agent-thinking-timer" in response.text
    assert "startAgentThinkingTimer" in response.text
    assert "stopAgentThinkingTimer" in response.text
    assert "已处理" in response.text
    assert "agent-thought-panel" in response.text
    assert "data-agent-live-steps" in response.text
    assert "agent_step" in response.text
    assert "tool_call_start" in response.text
    assert "tool_call_result" in response.text
    assert "跳过重复工具调用" in response.text
    assert "分析问题并选择检索工具" in response.text
    assert "step.name || step.tool_name || step.action" in response.text
    assert "userFacingAgentSummary" in response.text
    assert "isSkippedAgentStep" in response.text
    assert "onAgentStep" in response.text
    assert "onToolCallStart" in response.text
    assert "onToolCallResult" in response.text
    assert "appendAgentErrorMessage" in response.text
    assert "正在思考..." in response.text
    assert "pendingThinkingMessage?.remove()" in response.text
    assert "Agent failed" in response.text
    assert "setConversationListPlaceholder" in response.text
    assert "Load failed" in response.text
    assert "loadAgentConversations" in response.text
    assert "loadConversationMessages" in response.text
    assert "createAgentConversation" in response.text
    assert "deleteCurrentConversation" in response.text
    assert "renameCurrentConversation" in response.text
    assert "showConversationMenu" in response.text
    assert "hideConversationMenu" in response.text
    assert "data-conversation-item" in response.text
    assert "contextmenu" in response.text
    contextmenu_block = response.text.split('addEventListener("contextmenu"', 1)[1].split("showConversationMenu", 1)[0]
    assert "loadConversationMessages" not in contextmenu_block
    assert "window.prompt" in response.text
    assert 'method: "PATCH"' in response.text
    assert "agentRequestInFlight" in response.text
    assert "activeAgentAbortController" in response.text
    assert "setAgentBusy" in response.text
    assert "abortAgentStream" in response.text
    assert "markAgentStreamingAborted" in response.text
    assert "Stopping generation" in response.text
    assert "command-button--stop" in response.text
    assert "Stop generation" in response.text
    assert "data-agent-stop" not in response.text
    assert 'querySelector("[data-agent-submit]")?.addEventListener("click"' in response.text
    assert "event.preventDefault();" in response.text
    assert "setAgentPanelStatus" in response.text
    assert "querySelectorAll" in response.text
    assert "bindViewNavigation" in response.text
    assert "switchView" in response.text
    assert "[data-view-target]" in response.text
    assert "[data-view]" in response.text
    assert "timeoutMs: 45000" in response.text
    fallback_agent_block = response.text.split("result = await fetchJson(apiEndpoints.agent", 1)[1].split("});", 1)[0]
    assert "headers: authHeaders()" in fallback_agent_block
    assert "Request timed out" in response.text
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
    assert "ANSWER_SEGMENT_MAX_CHARS" in response.text
    assert "answerRenderSegments" in response.text
    assert "renderAnswerSegmentsHtml" in response.text
    assert "renderSegmentedAnswerInto" in response.text
    assert "answer-text--segmented" in response.text
    assert "answer-segment" in response.text
    assert "createAgentTokenFlushScheduler" in response.text
    assert "tokenScheduler.push(token)" in response.text
    assert "tokenScheduler.flushNow()" in response.text
    assert "await handlers.onToken" in response.text
    assert "finalizeAgentStreamingMessage" in response.text
    assert "appendTokenToAgentMessage" in response.text
    assert 'setAgentPanelStatus(result?.aborted ? "aborted" : result?.refused ? "refused" : "answered")' in response.text
    assert '"Accept": "text/event-stream"' in response.text
    assert "...authHeaders()" in response.text
    assert "signal:" in response.text
    assert "apiEndpoints.agentStream" in response.text
    assert "workflow_steps" in response.text
    assert "iteration_count" in response.text
    assert "invalid_citations" in response.text
    assert "refusal_category" in response.text
    assert "formatRefusalCategory" in response.text
    assert "responsibility_gate_triggered" in response.text
    assert "updateAgentModeStatus" not in response.text
    assert "[data-agent-mode-status]" not in response.text
    assert "[data-agent-mode]" not in response.text
    assert 'body.mode = "agentic"' not in response.text
    assert 'mode: "tool_calling_agent"' in response.text
    assert 'mode: "langgraph_agent"' not in response.text
    assert 'updateAgentModeStatus("auto")' not in response.text
    assert "reindexSource" in response.text
    assert "bindEnterToSubmit" in response.text
    assert "textarea[data-agent-question], textarea[data-chat-question]" in response.text
    assert 'textarea.closest("form")' in response.text
    assert 'event.key !== "Enter"' in response.text
    assert "event.shiftKey" in response.text
    assert "event.isComposing" in response.text
    assert "form.requestSubmit()" in response.text
    assert "conversationTitleFromQuestion" in response.text
    assert "userFriendlyErrorMessage" in response.text
    assert "citationReferenceHtml" in response.text
    assert "sourceClusterHtml" in response.text
    assert "figureEvidenceHtml" in response.text
    assert "data-figure-open" in response.text
    assert "openFigureLightbox" in response.text
    assert "closeFigureLightbox" in response.text
    assert "data-close-figure-lightbox" in response.text
    assert 'event.key === "Escape"' in response.text
    assert "Figure ${figureNumber}" in response.text
    assert "figureSourceLine(source, figureNumber)" in response.text
    assert "Figure [${escapeHtml(citation)}] /" not in response.text
    assert "openCitationDrawer" in response.text
    assert "closeCitationDrawer" in response.text
    assert "const activeCitation = preferredCitation || citations[0] || \"\"" in response.text
    assert "activeItem?.classList.add(\"is-active\")" in response.text
    assert "data-source-cluster" in response.text
    assert "data-citation-set" in response.text
    assert "data-citation-drawer-item" in response.text
    assert "scrollIntoView" in response.text
    assert "CSS.escape" in response.text
    assert "normalizeCitationDisplay" in response.text
    assert "citation_source_map" in response.text
    assert "citationNumbersInAnswer" in response.text
    assert "renderAnswerWithCitationLinks" in response.text
    assert "renderMarkdownBlocks" in response.text
    assert "markdownTableHtml" in response.text
    assert "table-evidence-content" in response.text
    assert "messageElement._streamedAnswerText" in response.text
    assert "answerText.innerHTML = renderMarkdownBlocks" in response.text
    assert 'start="${listStart}"' in response.text
    assert '"start"' in response.text
    assert "renderInlineMarkdown" in response.text
    assert "sanitizeRenderedHtml" in response.text
    assert "SAFE_RENDERED_TAGS" in response.text
    assert "DANGEROUS_RENDERED_TAGS" in response.text
    assert "javascript:" in response.text
    assert 'name.startsWith("on")' in response.text
    assert '"TABLE"' in response.text
    assert '"THEAD"' in response.text
    assert '"TD"' in response.text
    assert "<strong>" in response.text
    assert "data-citation-ref" in response.text
    assert "citation-popover" in response.text
    assert "loading-spinner" in response.text
    assert "Request failed. Please retry later or check service logs." in response.text

    styles = client.get("/static/styles.css")
    assert styles.status_code == 200
    assert "[hidden]" in styles.text
    assert "display: none !important" in styles.text
    assert "hero-layout" in styles.text
    assert "demo-panel" in styles.text
    assert "view-section" in styles.text
    assert "advanced-settings" not in styles.text
    assert "advanced-settings-grid" not in styles.text
    assert ".advanced-settings:not([open]) .advanced-settings-grid" not in styles.text
    assert 'aria-current="page"' in styles.text
    assert "linear-gradient" in styles.text
    assert "chat-message--thinking" in styles.text
    assert "chat-message--error" in styles.text
    assert "thinking-text" in styles.text
    assert "agent-live-steps" in styles.text
    assert "agent-live-step" in styles.text
    assert "agent-thinking-status" in styles.text
    assert "agent-thinking-timer" in styles.text
    assert "agent-thinking-label" in styles.text
    assert "agent-thought-panel" in styles.text
    assert "overflow-wrap: anywhere" in styles.text
    assert "@keyframes loading-spin" in styles.text
    assert "loading-spinner" in styles.text
    assert "citation-ref" in styles.text
    assert "citation-popover" in styles.text
    assert ".citation-ref:hover .citation-popover" in styles.text
    assert "source-cluster" in styles.text
    assert "citation-drawer" in styles.text
    assert "citation-drawer-item" in styles.text
    assert "citation-drawer-chip" in styles.text
    assert ".citation-drawer-item.is-active" in styles.text
    assert "vertical-align: super" in styles.text
    assert "font-size: 11px" in styles.text
    assert "white-space: nowrap" in styles.text
    assert "height: 1.3em" in styles.text
    assert "agent-live-step--tool-call-result.skipped" in styles.text
    assert "command-button--stop" in styles.text
    assert ".chat-message--thinking .answer-text" not in styles.text
    assert "chat-message--aborted" in styles.text
    assert "agent-stream-status" in styles.text
    assert "answer-text--segmented" in styles.text
    assert "answer-segment + .answer-segment" in styles.text
    assert ".answer-text ol" in styles.text
    assert ".answer-text li + li" in styles.text
    assert ".markdown-table-wrap" in styles.text
    assert ".markdown-table th" in styles.text
    assert "agent-chat-layout" in styles.text
    assert "conversation-sidebar" in styles.text
    assert "conversation-list-item" in styles.text
    assert "conversation-context-menu" in styles.text
    assert "agent-composer" in styles.text
    assert "auth-panel" in styles.text
    assert "auth-screen" in styles.text
    assert "auth-card" in styles.text
    assert "auth-tabs" in styles.text
    assert "auth-tab.is-active" in styles.text
    assert "auth-help.is-error" in styles.text
    assert "auth-form" in styles.text
    assert "auth-remember" in styles.text
    assert "auth-summary" in styles.text
    assert "height: calc(100vh - 108px)" in styles.text
    assert "grid-template-rows: auto minmax(0, 1fr)" in styles.text


def test_quality_report_is_served_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-report")

    assert response.status_code == 200
    assert "quality-report" in response.text
    assert "overall-score" in response.text
    assert 'id="overall-score"' in response.text
    assert 'id="grade"' in response.text
    assert 'id="release-decision"' in response.text
    # 闂傚倸鍊搁崐鎼佸疮閹惰棄鏄ラ柡宥庡弾閺?30 闂傚倷鑳堕、濠勭礄娴兼潙纾块梺顒€绉寸粻鐔兼煃閳轰礁鏆熼柍鐟扮У缁绘繈妫冨☉娆愭倷闂佷紮瀵岄崳锝夊蓟濞戞ǚ鏋庢俊顖濐潐閹癸絽顪冮妶鍡樼濠㈢懓妫涢崚鎺楁濞戞帗顫嶉梺鍐茬亪閺呮稒绂嶉幆褜鐔嗛悹楦挎婢ф劙鏌涚€ｎ偅灏扮紒妤冨枛閸┾偓妞ゆ帒濯绘径鎰缂備焦菤閹稿啴姊洪崘鍙夋儓闁瑰啿绻楅·鍌炴⒒娴ｅ憡鍟為悽顖涱殜婵＄敻鎮欓悽鐢电暥閻庡厜鍋撻柍褜鍓熼崺鈧い鎺戝€归弳鈺呮煕濡姴娲ら崥瑙勩亜閹惧崬鐏╂潻?
    assert 'id="filter-section"' in response.text
    assert 'id="filter-risk"' in response.text
    assert 'id="risk-queue"' in response.text
    assert 'id="export-csv"' in response.text
    assert 'id="export-json"' in response.text
    assert "git add" in response.text


def test_quality_report_data_json_is_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-report/data.json")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    # 闂備礁婀遍崢褔鎮洪妸鈺佽摕闁靛ě鈧崑鎾诲垂椤愵剝鈧法鈧娲忛崕鐢搞€侀弴銏℃櫆閻熸瑱绲鹃悗杈ㄧ節?30 闂備浇宕垫慨鐢稿礉閹达箑绀夐柟杈剧畱闂傤垶鏌ц箛姘兼綈閻庢碍宀搁弻娑㈠即閵娿儰绨婚梺璇叉捣缁垶骞堥妸鈺傚仭闁绘鐗嗛ˇ鈺呮⒑闁偛鑻晶顖涗繆閸欏娴柕鍡曠窔楠炲鏁傞懞銉︾彨闂佽绻掗崑鐘诲磻閹扮増鍋℃い鎺嗗亾闁宠棄顦甸獮妯虹暦閸ュ棴绲块惀顏堫敇閻樻祴鏋呭┑鈽嗗亗缁舵艾鐣烽敐鍡楃窞閻庯綆鍋嗚ぐ鐢告⒒娴ｇ瓔娼愬鐟版瀹曠増鎯旈妸锕€浠遍悷婊冪Ч閸┿垽骞樼紒妯衡偓鐑芥煕韫囨搩妲稿ù?
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
    assert "quality-review" in response.text
    assert 'id="case-list"' in response.text
    assert "/quality-review/data.json" in response.text
    assert "/quality-review/reviews" in response.text
    assert "case-list" in response.text
    assert "quality-review/data.json" in response.text


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
            "reviewer_note": "Top-5 evidence supports accepting the low score.",
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
            "reviewer_note": "Needs retrieval tuning before release.",
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
