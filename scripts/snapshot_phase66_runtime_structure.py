"""Capture the Phase 66 pre-refactor runtime structure snapshot.

The snapshot is intentionally structural. It records file/function sizes,
AST-derived call and dynamic-typing counts, forbidden routing remnants, and
tool registration names. It must not persist prompts, answers, evidence text,
provider payloads, credentials, or full chunk contents.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGETS = (
    "app/services/agent/tool_calling_service.py",
    "app/services/agent/run_coordinator.py",
    "app/services/agent/tool_executor.py",
    "app/services/agent/tool_registry.py",
    "app/services/agent/runtime_ports.py",
    "app/services/agent/tools.py",
)

FORBIDDEN_ROUTING_NAMES = (
    "AGENT_RUN_COORDINATOR_ENABLED",
    "agent_run_coordinator_enabled",
)


def _qualified_name(stack: list[str], node: ast.AST) -> str:
    name = getattr(node, "name", "<anonymous>")
    if stack:
        return ".".join([*stack, str(name)])
    return str(name)


def _is_simple_namespace_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "SimpleNamespace"
    if isinstance(func, ast.Attribute):
        return func.attr == "SimpleNamespace"
    return False


def _is_getattr_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id == "getattr"


def _is_coordinator_run_call(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "run"
        and isinstance(func.value, ast.Name)
        and func.value.id == "coordinator"
    )


def _annotation_contains_any(annotation: ast.AST | None) -> bool:
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name):
        return annotation.id == "Any"
    if isinstance(annotation, ast.Attribute):
        return annotation.attr == "Any"
    return any(_annotation_contains_any(child) for child in ast.iter_child_nodes(annotation))


class _FunctionCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.class_stack: list[str] = []
        self.functions: dict[str, dict[str, object]] = {}
        self.public_any_annotations: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._record_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._record_function(node)
        self.generic_visit(node)

    def _record_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualified = _qualified_name(self.class_stack, node)
        end_lineno = getattr(node, "end_lineno", node.lineno)
        call_nodes = [child for child in ast.walk(node) if isinstance(child, ast.Call)]
        self.functions[qualified] = {
            "lineno": node.lineno,
            "end_lineno": end_lineno,
            "physical_lines": end_lineno - node.lineno + 1,
            "call_count": len(call_nodes),
            "coordinator_run_calls": sum(
                1 for call in call_nodes if _is_coordinator_run_call(call)
            ),
            "getattr_calls": sum(1 for call in call_nodes if _is_getattr_call(call)),
            "simple_namespace_calls": sum(
                1 for call in call_nodes if _is_simple_namespace_call(call)
            ),
        }

        if node.name.startswith("_"):
            return
        for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            if _annotation_contains_any(arg.annotation):
                self.public_any_annotations.append(f"{qualified}:{arg.arg}")
        if node.args.vararg and _annotation_contains_any(node.args.vararg.annotation):
            self.public_any_annotations.append(f"{qualified}:{node.args.vararg.arg}")
        if node.args.kwarg and _annotation_contains_any(node.args.kwarg.annotation):
            self.public_any_annotations.append(f"{qualified}:{node.args.kwarg.arg}")
        if _annotation_contains_any(node.returns):
            self.public_any_annotations.append(f"{qualified}:return")


def _forbidden_occurrences(tree: ast.AST) -> list[dict[str, object]]:
    occurrences: list[dict[str, object]] = []
    forbidden = set(FORBIDDEN_ROUTING_NAMES)
    for node in ast.walk(tree):
        name: str | None = None
        kind = type(node).__name__
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in forbidden:
                name = node.value
                kind = "StringConstant"
        if name in forbidden:
            occurrences.append(
                {
                    "name": name,
                    "kind": kind,
                    "lineno": getattr(node, "lineno", None),
                }
            )
    return occurrences


def inspect_python_file(path: Path) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    collector = _FunctionCollector()
    collector.visit(tree)
    call_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "physical_lines": len(source.splitlines()),
        "functions": collector.functions,
        "call_count": len(call_nodes),
        "simple_namespace_calls": sum(
            1 for call in call_nodes if _is_simple_namespace_call(call)
        ),
        "getattr_calls": sum(1 for call in call_nodes if _is_getattr_call(call)),
        "public_any_annotations": collector.public_any_annotations,
        "forbidden_routing_occurrences": _forbidden_occurrences(tree),
    }


def _git_head(repository_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repository_root), "rev-parse", "--short=8", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _production_tool_registrations() -> dict[str, object]:
    try:
        from app.services.agent.tool_registry import default_tool_registry

        names = list(default_tool_registry().names)
    except Exception as exc:
        return {
            "status": "unavailable",
            "error_category": type(exc).__name__,
            "tool_names": [],
            "tool_count": 0,
        }
    return {"status": "captured", "tool_names": names, "tool_count": len(names)}


def build_runtime_structure_snapshot(repository_root: Path) -> dict[str, object]:
    repository_root = repository_root.resolve()
    files: dict[str, object] = {}
    forbidden: list[dict[str, object]] = []
    for target in TARGETS:
        path = repository_root / target
        if not path.exists():
            files[target] = {"path": target, "exists": False}
            continue
        report = inspect_python_file(path)
        report["exists"] = True
        files[target] = report
        for occurrence in report.get("forbidden_routing_occurrences", []):
            item = dict(occurrence)
            item["path"] = target
            forbidden.append(item)

    snapshot = {
        "schema_version": 1,
        "git_head": _git_head(repository_root),
        "captured_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "targets": list(TARGETS),
        "files": files,
        "forbidden_routing_occurrences": forbidden,
        "production_tool_registrations": _production_tool_registrations(),
    }
    snapshot["completion_gates"] = evaluate_completion_gates(snapshot)
    return snapshot


def evaluate_completion_gates(snapshot: dict[str, object]) -> dict[str, object]:
    files = snapshot.get("files", {})
    if not isinstance(files, dict):
        return {"all_pass": False, "failed": ["files_missing"]}

    failed: list[str] = []

    def file_report(path: str) -> dict[str, object]:
        value = files.get(path, {})
        return value if isinstance(value, dict) else {}

    def function_lines(path: str, qualified_name: str) -> int:
        report = file_report(path)
        functions = report.get("functions", {})
        if not isinstance(functions, dict):
            return 10**9
        function = functions.get(qualified_name, {})
        if not isinstance(function, dict):
            return 10**9
        return int(function.get("physical_lines", 10**9) or 10**9)

    service_path = "app/services/agent/tool_calling_service.py"
    coordinator_path = "app/services/agent/run_coordinator.py"
    service = file_report(service_path)
    coordinator = file_report(coordinator_path)

    if int(service.get("physical_lines", 10**9) or 10**9) > 350:
        failed.append("tool_calling_service_lines_gt_350")
    if function_lines(service_path, "ToolCallingAgentService.query") > 100:
        failed.append("tool_calling_service_query_lines_gt_100")
    if int(coordinator.get("physical_lines", 10**9) or 10**9) > 550:
        failed.append("run_coordinator_lines_gt_550")
    if function_lines(coordinator_path, "RunCoordinator.run") > 200:
        failed.append("run_coordinator_run_lines_gt_200")

    if snapshot.get("forbidden_routing_occurrences"):
        failed.append("forbidden_run_coordinator_flag_present")

    for path in (
        coordinator_path,
        "app/services/agent/runtime_ports.py",
        "app/services/agent/tool_executor.py",
        "app/services/agent/tool_registry.py",
    ):
        report = file_report(path)
        if report.get("public_any_annotations"):
            failed.append(f"{path}:public_any_annotations")
        if int(report.get("simple_namespace_calls", 0) or 0) > 0:
            failed.append(f"{path}:simple_namespace_calls")

    registrations = snapshot.get("production_tool_registrations", {})
    expected_tools = [
        "hybrid_search_knowledge",
        "search_figures",
        "search_tables",
        "analyze_user_image",
    ]
    if not isinstance(registrations, dict) or registrations.get("tool_names") != expected_tools:
        failed.append("production_tool_registry_not_exactly_four")

    return {"all_pass": not failed, "failed": failed}


def write_snapshot(
    repository_root: Path,
    output_path: Path,
) -> dict[str, object]:
    snapshot = build_runtime_structure_snapshot(repository_root)
    if not output_path.is_absolute():
        output_path = repository_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/phase66/baseline/runtime-structure.json"),
    )
    parser.add_argument("--profile", choices=("baseline", "final"), default="baseline")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    snapshot = write_snapshot(args.repository_root, args.output)
    print(
        "schema_version={schema_version} git_head={git_head} files={file_count} "
        "forbidden_routing_occurrences={forbidden_count}".format(
            schema_version=snapshot["schema_version"],
            git_head=snapshot["git_head"],
            file_count=len(snapshot["files"]),
            forbidden_count=len(snapshot["forbidden_routing_occurrences"]),
        )
    )
    gates = snapshot.get("completion_gates", {})
    if args.check and args.profile == "final":
        failed = gates.get("failed", []) if isinstance(gates, dict) else ["gates_missing"]
        if failed:
            print("completion_gates_failed=" + ",".join(str(item) for item in failed))
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
