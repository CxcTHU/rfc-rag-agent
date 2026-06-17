from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_stage43_https_reverse_proxy_templates_exist() -> None:
    assert (ROOT / "deploy" / "nginx-https.example.conf").exists()
    assert (ROOT / "deploy" / "Caddyfile.example").exists()
    assert (ROOT / "docs" / "deployment_https_reverse_proxy.md").exists()


def test_stage43_https_templates_preserve_streaming_and_request_id() -> None:
    nginx = (ROOT / "deploy" / "nginx-https.example.conf").read_text(encoding="utf-8")
    caddy = (ROOT / "deploy" / "Caddyfile.example").read_text(encoding="utf-8")

    assert "proxy_buffering off" in nginx
    assert "X-Request-ID" in nginx
    assert "X-Request-ID" in caddy
    assert "127.0.0.1:8000" in nginx
    assert "127.0.0.1:8000" in caddy


def test_stage43_https_templates_do_not_contain_secrets() -> None:
    combined = "\n".join(
        [
            (ROOT / "deploy" / "nginx-https.example.conf").read_text(encoding="utf-8"),
            (ROOT / "deploy" / "Caddyfile.example").read_text(encoding="utf-8"),
            (ROOT / "docs" / "deployment_https_reverse_proxy.md").read_text(encoding="utf-8"),
        ]
    ).casefold()

    assert "api_key" not in combined
    assert "bearer " not in combined
    assert "sk-" not in combined
