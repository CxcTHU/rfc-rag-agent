#!/usr/bin/env python3
"""Small TCP forwarder for provider egress from Docker app containers.

This script carries TLS bytes only. It does not terminate TLS, inspect request
bodies, log prompts, or handle API keys.
"""

from __future__ import annotations

import os
import socket
import threading


LISTEN_HOST = os.environ.get("PROVIDER_FORWARD_LISTEN_HOST", "172.18.0.1")
BUFFER_SIZE = 65536
FORWARDS = (
    (
        int(os.environ.get("DEEPSEEK_FORWARD_PORT", "18443")),
        os.environ.get("DEEPSEEK_UPSTREAM_HOST", "api.deepseek.com"),
        int(os.environ.get("DEEPSEEK_UPSTREAM_PORT", "443")),
    ),
    (
        int(os.environ.get("PARATERA_FORWARD_PORT", "18444")),
        os.environ.get("PARATERA_UPSTREAM_HOST", "llmapi.paratera.com"),
        int(os.environ.get("PARATERA_UPSTREAM_PORT", "443")),
    ),
)


def _close_socket(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


def _pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(BUFFER_SIZE)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        _close_socket(src)
        _close_socket(dst)


def _handle(client: socket.socket, upstream_host: str, upstream_port: int) -> None:
    try:
        upstream = socket.create_connection((upstream_host, upstream_port), timeout=15)
        client.settimeout(None)
        upstream.settimeout(None)
    except OSError:
        _close_socket(client)
        return
    threading.Thread(target=_pipe, args=(client, upstream), daemon=True).start()
    threading.Thread(target=_pipe, args=(upstream, client), daemon=True).start()


def _serve(listen_port: int, upstream_host: str, upstream_port: int) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, listen_port))
    server.listen(128)
    print(
        f"listening {LISTEN_HOST}:{listen_port} -> {upstream_host}:{upstream_port}",
        flush=True,
    )
    while True:
        client, _ = server.accept()
        threading.Thread(
            target=_handle,
            args=(client, upstream_host, upstream_port),
            daemon=True,
        ).start()


def main() -> None:
    threads: list[threading.Thread] = []
    for listen_port, upstream_host, upstream_port in FORWARDS:
        thread = threading.Thread(
            target=_serve,
            args=(listen_port, upstream_host, upstream_port),
        )
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
