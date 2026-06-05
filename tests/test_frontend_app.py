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
    assert 'data-citations-list' in response.text
    assert 'data-search-form' in response.text
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
    assert "/search/vector" in response.text
    assert "renderSources" in response.text
    assert "renderCitations" in response.text
    assert "reindexSource" in response.text


def test_favicon_request_does_not_404() -> None:
    client = TestClient(create_app())

    response = client.get("/favicon.ico")

    assert response.status_code == 204
