from fastapi.testclient import TestClient

from app.main import create_app


def test_frontend_index_is_served() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "堆石混凝土资料工作台" in response.text
    assert "/static/app.js" in response.text
    assert 'data-sources-body' in response.text
    assert 'data-documents-body' in response.text
    assert 'data-source-filter' in response.text
    assert 'data-chat-form' in response.text
    assert 'data-agent-form' in response.text
    assert 'data-agent-mode-status' in response.text
    assert '<select data-agent-mode' not in response.text
    assert '<option value="agentic">agentic</option>' not in response.text
    assert 'data-agent-tools-list' in response.text
    assert 'data-citations-list' in response.text
    assert 'data-search-form' in response.text
    assert '<option value="hybrid">hybrid</option>' in response.text
    assert 'data-chunks-list' in response.text
    assert 'data-sync-sources' in response.text


def test_frontend_static_assets_are_served() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "apiEndpoints" in response.text
    assert "/sources" in response.text
    assert "/documents" in response.text
    assert "/chat" in response.text
    assert "/agent/query" in response.text
    assert "/search/vector" in response.text
    assert "/search/hybrid" in response.text
    assert "renderSources" in response.text
    assert "renderCitations" in response.text
    assert "renderAgentToolCalls" in response.text
    assert "renderAgentWorkflowSteps" in response.text
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
    assert "reindexSource" in response.text


def test_quality_report_is_served_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-report")

    assert response.status_code == 200
    assert "阶段 20 质量门槛报告" in response.text
    assert "只读质量报告" in response.text
    # 阶段 20 报告保持只读筛选、风险队列与导出。
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
    # 应包含阶段 20 质量门槛行，且不泄露敏感字段。
    if payload:
        assert {"section", "metric", "status", "risk"}.issubset(payload[0].keys())
        serialized = response.text.lower()
        assert "api_key" not in serialized
        assert "bearer" not in serialized


def test_quality_report_export_csv_download() -> None:
    client = TestClient(create_app())

    response = client.get("/quality-report/export.csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "stage20_quality_summary.csv" in response.headers.get("content-disposition", "")
    assert "section" in response.text


def test_favicon_request_does_not_404() -> None:
    client = TestClient(create_app())

    response = client.get("/favicon.ico")

    assert response.status_code == 204
