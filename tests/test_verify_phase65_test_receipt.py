import json
from pathlib import Path

import pytest

from scripts.score_stage30_quality import load_verified_test_receipt


def test_stage30_rejects_legacy_handwritten_collection_receipt(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_safe.py").write_text("def test_safe(): pass\n", encoding="utf-8")
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps({"schema_version": "stage30-test-inventory-v1", "paths": ["tests/test_safe.py"]}), encoding="utf-8")
    junit = tmp_path / "junit.xml"
    junit.write_text('<testsuite name="pytest" tests="1" failures="0" errors="0"><testcase classname="tests.test_safe" name="test_safe"/></testsuite>', encoding="utf-8")
    handwritten = tmp_path / "collection.json"
    handwritten.write_text(json.dumps({"schema_version": "stage30-pytest-collection-v1", "command": "python -m pytest --collect-only -q", "pytest_version": "8", "node_ids": ["tests/test_safe.py::test_safe"]}), encoding="utf-8")

    with pytest.raises(ValueError, match="pytest_receipt_producer_invalid"):
        load_verified_test_receipt(junit, inventory, collection_receipt_path=handwritten, repository_root=tmp_path)
