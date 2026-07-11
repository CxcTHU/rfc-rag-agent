import re
from pathlib import Path

from fastapi.testclient import TestClient

import app.api.frontend as frontend_api
from app.main import create_app


def test_frontend_index_is_served() -> None:
    client = TestClient(create_app())

    response = client.get("/old")

    assert response.status_code == 200
    assert "RFC-RAG-Agent" in response.text
    assert 'data-view-target="ask"' in response.text
    assert 'data-view-target="library"' in response.text
    assert 'id="ask-view"' in response.text
    assert 'id="library-view"' in response.text
    assert "data-auth-login-form" in response.text
    assert "data-auth-register-form" in response.text
    assert "data-agent-form" in response.text
    assert "data-sync-sources" in response.text
    assert "data-citation-drawer" in response.text
    assert "/static/app.js" in response.text
    assert "/static/styles.css" in response.text


def test_frontend_static_assets_are_served() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")
    script = response.text.replace("\r\n", "\n")

    assert response.status_code == 200
    assert "apiEndpoints" in script
    assert "/auth/register" in script
    assert "/auth/login" in script
    assert "/auth/me" in script
    assert "/sources" in script
    assert "/documents" in script
    assert "/chat" in script
    assert "/agent/query" in script
    assert "/agent/query/stream" in script
    assert "/search/vector" in script
    assert "/search/hybrid" in script
    assert "Authorization" in script
    assert "Bearer" in script
    assert "authHeaders" in script
    assert "renderSources" in script
    assert "renderCitations" in script
    assert "renderAgentToolCalls" in script

    styles = client.get("/static/styles.css")
    assert styles.status_code == 200
    assert "[hidden]" in styles.text
    assert "display: none !important" in styles.text
    assert "agent-chat-layout" in styles.text
    assert "auth-screen" in styles.text
    assert "citation-drawer" in styles.text
    assert "overflow-y: auto" in styles.text
    assert "overflow-x: hidden" in styles.text


def test_react_root_and_old_routes_are_served() -> None:
    client = TestClient(create_app())

    root_response = client.get("/")
    old_response = client.get("/old")

    assert root_response.status_code == 200
    assert 'id="root"' in root_response.text
    assert "/assets/" in root_response.text
    assert old_response.status_code == 200
    assert "data-workspace-band" in old_response.text
    assert "/static/app.js" in old_response.text

    legacy_redirect = client.get("/legacy", follow_redirects=False)
    assert legacy_redirect.status_code == 307
    assert legacy_redirect.headers["location"] == "/old"

    app_v2_redirect = client.get("/app-v2/library", follow_redirects=False)
    assert app_v2_redirect.status_code == 307
    assert app_v2_redirect.headers["location"] == "/library"

    for route in ("ask", "library", "evidence", "trace", "quality", "unknown-route"):
        route_response = client.get(f"/{route}")
        assert route_response.status_code == 200
        assert route_response.text == root_response.text

    asset_path = re.search(r'src="([^"]*/assets/[^"]+\.js)"', root_response.text)
    assert asset_path is not None
    asset_response = client.get(asset_path.group(1))
    assert asset_response.status_code == 200
    assert "javascript" in asset_response.headers["content-type"]
    css_path = re.search(r'href="([^"]+\.css)"', root_response.text)
    assert css_path is not None
    css_response = client.get(css_path.group(1))
    assert css_response.status_code == 200
    assert "text/css" in css_response.headers["content-type"]

    missing_asset = client.get("/assets/does-not-exist.js")
    assert missing_asset.status_code == 404
    assert 'id="root"' not in missing_asset.text


def test_frontend_auth_refresh_uses_checking_state_before_signed_out() -> None:
    client = TestClient(create_app())

    response = client.get("/")
    asset_path = re.search(r'src="([^"]*/assets/[^"]+\.js)"', response.text)
    assert asset_path is not None
    legacy_script = client.get("/static/app.js").text.replace("\r\n", "\n")
    legacy_styles = client.get("/static/styles.css").text.replace("\r\n", "\n")
    legacy_index = client.get("/old").text

    react_css_path = re.search(r'href="([^"]+\.css)"', response.text)
    assert react_css_path is not None
    react_styles = client.get(react_css_path.group(1)).text
    assert ".conversation-panel" in react_styles
    assert ".conversation-list" in react_styles
    source_styles = Path("frontend/src/index.css").read_text(encoding="utf-8")
    source_app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    source_main = Path("frontend/src/main.tsx").read_text(encoding="utf-8")
    source_workspace = Path("frontend/src/features/chat/ChatWorkspaceProvider.tsx").read_text(encoding="utf-8")
    source_stream = Path("frontend/src/features/chat/useAgentStream.ts").read_text(encoding="utf-8")
    source_workflow = Path("frontend/src/features/trace/workflow.ts").read_text(encoding="utf-8")
    assert "BrowserRouter" in source_main
    assert 'basename="/app-v2"' not in source_main
    assert "QueryClientProvider" in source_main
    assert "activeView" not in source_app
    assert "apiJson" not in source_app
    assert "selectedAssistantMessageId" in source_workspace
    assert "rfc-rag-agent.activeConversationId" in source_workspace
    assert "createConversation" in source_workspace
    assert "event.type === 'metadata'" in source_stream
    assert "Stream ended without metadata" in source_stream
    assert "event.type === 'heartbeat'" in source_stream
    assert "agentStageTimeline" not in source_workflow
    assert "latency_trace" in source_workflow
    assert "overflow-y: auto" in source_styles
    assert "overflow-x: hidden" in source_styles
    assert ".composer:focus-within" in source_styles
    assert "bottom: calc(100% + 8px)" in source_styles
    assert "top: calc(100% + 8px)" not in source_styles
    assert "background: #191c22" in source_styles
    assert ".thinking-live-status" in source_styles
    assert "@keyframes thinkingTextPulse" in source_styles
    assert ".thinking-activity-rail" not in source_styles
    assert "max-width: 1460px" not in source_styles
    assert "grid-template-columns: clamp(248px, 14vw, 320px) minmax(620px, 1fr) clamp(320px, 18vw, 420px)" in source_styles
    assert "rgba(22, 38, 48" not in source_styles
    assert "rgba(56, 189, 248" not in source_styles
    assert "rgba(15, 23, 42" not in source_styles
    assert "rgba(51, 65, 85" not in source_styles
    assert "-webkit-line-clamp: 2" in source_styles
    assert 'class="app-shell is-auth-checking"' in legacy_index
    assert "authChecking: Boolean(storedAuthToken())" in legacy_script
    assert 'classList.toggle("is-auth-checking", isChecking)' in legacy_script
    assert 'classList.toggle("is-signed-out", !isChecking && !isSignedIn)' in legacy_script
    assert "authScreen.hidden = isChecking || isSignedIn" in legacy_script
    assert "workspace.hidden = isChecking || !isSignedIn" in legacy_script
    assert legacy_script.index("await loadCurrentUserFromToken();") < legacy_script.index(
        'await fetchJson("/health");'
    )
    assert ".app-shell.is-auth-checking .auth-screen" in legacy_styles
    assert ".app-shell.is-auth-checking .workspace-band" in legacy_styles


def test_quality_report_is_served_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-report")

    assert response.status_code == 200
    assert "quality-report" in response.text
    assert "overall-score" in response.text
    assert 'id="overall-score"' in response.text
    assert 'id="grade"' in response.text
    assert 'id="release-decision"' in response.text
    assert 'id="filter-section"' in response.text
    assert 'id="filter-risk"' in response.text
    assert 'id="risk-queue"' in response.text
    assert 'id="export-csv"' in response.text
    assert 'id="export-json"' in response.text


def test_quality_report_data_json_is_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-report/data.json")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
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
