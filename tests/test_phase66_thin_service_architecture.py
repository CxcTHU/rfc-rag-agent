import ast
from pathlib import Path

from scripts.snapshot_phase66_runtime_structure import inspect_python_file


SERVICE_PATH = Path("app/services/agent/tool_calling_service.py")
COORDINATOR_PATH = Path("app/services/agent/run_coordinator.py")


def _service_source() -> str:
    return SERVICE_PATH.read_text(encoding="utf-8")


def _method_node(class_name: str, method_name: str) -> ast.FunctionDef:
    tree = ast.parse(_service_source())
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == method_name:
                return item
    raise AssertionError(f"{class_name}.{method_name} not found")


def test_service_file_is_a_thin_facade() -> None:
    report = inspect_python_file(SERVICE_PATH)

    assert report["physical_lines"] <= 350
    assert (
        report["functions"]["ToolCallingAgentService.query"]["physical_lines"]
        <= 100
    )


def test_service_query_delegates_to_one_coordinator_run() -> None:
    query = _method_node("ToolCallingAgentService", "query")
    run_calls = [
        node
        for node in ast.walk(query)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
    ]

    assert len(run_calls) == 1


def test_service_has_no_run_coordinator_feature_flag_or_legacy_loop() -> None:
    source = _service_source()

    assert "AGENT_RUN_COORDINATOR_ENABLED" not in source
    assert "agent_run_coordinator_enabled" not in source
    assert "_query_with_run_coordinator" not in source


def test_run_coordinator_file_and_main_loop_are_slim() -> None:
    report = inspect_python_file(COORDINATOR_PATH)

    assert report["physical_lines"] <= 550
    assert report["functions"]["RunCoordinator.run"]["physical_lines"] <= 200
