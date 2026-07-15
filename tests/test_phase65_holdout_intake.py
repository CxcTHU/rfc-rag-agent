from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.prepare_phase65_holdout_intake import (
    HOLDOUT_TEMPLATE_FIELDS,
    build_holdout_intake_packet,
    validate_private_holdout_cases,
    write_holdout_template,
)


def test_holdout_intake_template_is_header_only_and_not_executable(tmp_path: Path) -> None:
    template = tmp_path / "phase65_private_holdout_cases.template.csv"

    write_holdout_template(template)
    packet = build_holdout_intake_packet(
        template_path=template,
        target_cases_path=Path("data/evaluation/phase65_private_holdout_cases.csv"),
    )

    rows = list(csv.reader(template.open(encoding="utf-8-sig", newline="")))
    assert rows == [list(HOLDOUT_TEMPLATE_FIELDS)]
    assert packet["gate"] == "blocked"
    assert packet["template_is_executable"] is False
    assert packet["public_overlap_guard"] is True
    assert packet["excluded_cases_path"] == "data\\evaluation\\phase64_latency_cases.csv"
    assert packet["expected_min_cases"] == 12
    assert "run_holdout_command" in packet
    assert "answer" not in json.dumps(packet).casefold()
    assert "prompt" not in json.dumps(packet).casefold()


def test_holdout_intake_validator_rejects_header_only_template(tmp_path: Path) -> None:
    template = tmp_path / "phase65_private_holdout_cases.template.csv"
    write_holdout_template(template)

    with pytest.raises(ValueError, match="holdout_requires_twelve_unique_cases"):
        validate_private_holdout_cases(template)


def test_holdout_intake_validator_accepts_twelve_unique_private_cases(tmp_path: Path) -> None:
    cases = tmp_path / "phase65_private_holdout_cases.csv"
    with cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HOLDOUT_TEMPLATE_FIELDS)
        writer.writeheader()
        writer.writerows(
            {
                "case_id": f"private-holdout-{index:02d}",
                "category": "ordinary_text",
                "question": f"private reviewer case {index:02d}",
                "expected_tool": "hybrid_search_knowledge",
                "expected_graph_requirement": "disabled",
                "reviewer_notes": "",
            }
            for index in range(12)
        )

    packet = validate_private_holdout_cases(cases)

    assert packet["gate"] == "pass"
    assert packet["holdout_case_count"] == 12
    assert packet["ready_to_run_holdout"] is True
    assert "answer" not in json.dumps(packet).casefold()
    assert "prompt" not in json.dumps(packet).casefold()


def test_holdout_intake_validator_rejects_public_case_overlap(tmp_path: Path) -> None:
    cases = tmp_path / "phase65_private_holdout_cases.csv"
    public_cases = tmp_path / "phase64_latency_cases.csv"
    with public_cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "category"))
        writer.writeheader()
        writer.writerow({"case_id": "e2e-text-01", "category": "ordinary_text"})
    with cases.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HOLDOUT_TEMPLATE_FIELDS)
        writer.writeheader()
        writer.writerows(
            {
                "case_id": "e2e-text-01" if index == 0 else f"private-holdout-{index:02d}",
                "category": "ordinary_text",
                "question": f"private reviewer case {index:02d}",
                "expected_tool": "hybrid_search_knowledge",
                "expected_graph_requirement": "disabled",
                "reviewer_notes": "",
            }
            for index in range(12)
        )

    with pytest.raises(ValueError, match="holdout_overlaps_excluded_cases"):
        validate_private_holdout_cases(cases, exclude_cases_path=public_cases)
