from app.services.agent.tool_calling_composition import compose_tool_calling_runtime


def test_composition_registers_four_tools_once() -> None:
    runtime = compose_tool_calling_runtime()

    assert runtime.registry.names == (
        "hybrid_search_knowledge",
        "search_figures",
        "search_tables",
        "analyze_user_image",
    )
