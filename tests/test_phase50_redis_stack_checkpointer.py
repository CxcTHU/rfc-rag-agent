from __future__ import annotations

import os
import uuid

import pytest

from app.core.config import Settings
from app.services.agent.graph_builder import build_langgraph_agent_graph
from app.services.agent.graph_checkpointer import (
    create_graph_checkpointer,
    reset_graph_checkpointer_cache,
)
from app.services.agent.graph_nodes import (
    initialize_state,
    reset_current_toolbox,
    set_current_toolbox,
)
from tests.test_phase50_langgraph_nodes import FakeToolbox


def test_redis_stack_checkpointer_writes_real_checkpoint_when_enabled() -> None:
    redis_url = os.getenv("PHASE50_REDIS_STACK_URL")
    if not redis_url:
        pytest.skip("set PHASE50_REDIS_STACK_URL to run Redis Stack checkpointer integration")

    redis_module = pytest.importorskip("redis")
    pytest.importorskip("langgraph.checkpoint.redis")

    client = redis_module.Redis.from_url(
        redis_url,
        socket_timeout=1.0,
        socket_connect_timeout=1.0,
        decode_responses=False,
    )
    client.ping()

    module_names = set()
    for module in client.execute_command("MODULE", "LIST"):
        items = dict(zip(module[::2], module[1::2], strict=False))
        name = items.get(b"name", items.get("name", b""))
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        module_names.add(str(name).lower())
    assert any(name in module_names for name in {"search", "ft"})
    assert any(name in module_names for name in {"rejson", "json"})

    reset_graph_checkpointer_cache()
    selection = create_graph_checkpointer(
        settings=Settings(redis_url=redis_url),
        redis_client=client,
    )

    assert selection.backend == "redis"
    assert selection.reason == "ok"

    thread_id = f"phase50-redis-stack-{uuid.uuid4().hex}"
    compiled = build_langgraph_agent_graph().compile(checkpointer=selection.checkpointer)
    token = set_current_toolbox(FakeToolbox())
    try:
        compiled.invoke(
            initialize_state(question="What affects filling capacity?"),
            config={
                "recursion_limit": 15,
                "configurable": {"thread_id": thread_id},
            },
        )
    finally:
        reset_current_toolbox(token)

    checkpoint = selection.checkpointer.get_tuple(
        {"configurable": {"thread_id": thread_id}}
    )
    assert checkpoint is not None
