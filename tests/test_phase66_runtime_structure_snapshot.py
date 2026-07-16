from pathlib import Path

from scripts.snapshot_phase66_runtime_structure import (
    build_runtime_structure_snapshot,
    evaluate_completion_gates,
    inspect_python_file,
)


def test_structure_snapshot_counts_named_method_lines(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "class Service:\n"
        "    def query(self):\n"
        "        coordinator.run()\n"
        "        return 1\n",
        encoding="utf-8",
    )

    report = inspect_python_file(source)

    assert report["physical_lines"] == 4
    assert report["functions"]["Service.query"]["physical_lines"] == 3
    assert report["functions"]["Service.query"]["coordinator_run_calls"] == 1


def test_structure_snapshot_finds_forbidden_dynamic_constructs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "from types import SimpleNamespace\n"
        "def run(value: Any) -> Any:\n"
        "    return SimpleNamespace(value=getattr(value, 'x', None))\n",
        encoding="utf-8",
    )

    report = inspect_python_file(source)

    assert report["simple_namespace_calls"] == 1
    assert report["getattr_calls"] == 1
    assert report["public_any_annotations"] == ["run:value", "run:return"]


def test_current_runtime_structure_passes_final_completion_gates() -> None:
    snapshot = build_runtime_structure_snapshot(Path("."))

    gates = evaluate_completion_gates(snapshot)

    assert gates["all_pass"] is True
    assert gates["failed"] == []
