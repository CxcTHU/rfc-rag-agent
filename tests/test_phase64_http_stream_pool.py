from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from app.services.generation.chat_model import ChatMessage, OpenAICompatibleChatModelProvider


@contextmanager
def fake_sse_server(*, fail_first: bool = False):
    state = {"connection_count": 0, "request_count": 0}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self) -> None:
            super().setup()
            state["connection_count"] += 1

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API.
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            state["request_count"] += 1
            body = (
                b"data: not-json\n\n"
                if fail_first and state["request_count"] == 1
                else (
                    b'data: {"choices":[{"delta":{"content":"answer"}}]}\n\n'
                    b"data: [DONE]\n\n"
                )
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_second_complete_stream_reuses_one_sse_connection() -> None:
    with fake_sse_server() as (base_url, state):
        provider = OpenAICompatibleChatModelProvider(
            model_name="phase64-test",
            api_key="test-key",
            base_url=base_url,
            max_attempts=1,
        )
        messages = [ChatMessage(role="user", content="one")]

        assert "".join(provider.stream_generate(messages)) == "answer"
        assert "".join(provider.stream_generate(messages)) == "answer"

    assert state["connection_count"] == 1


def test_broken_stream_invalidates_the_pooled_connection() -> None:
    with fake_sse_server(fail_first=True) as (base_url, state):
        provider = OpenAICompatibleChatModelProvider(
            model_name="phase64-test",
            api_key="test-key",
            base_url=base_url,
            max_attempts=1,
        )
        messages = [ChatMessage(role="user", content="one")]

        with pytest.raises(RuntimeError, match="invalid JSON"):
            list(provider.stream_generate(messages))
        assert "".join(provider.stream_generate(messages)) == "answer"

    assert state["connection_count"] == 2
