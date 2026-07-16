from pathlib import Path

import pytest

from scripts.agent_regression_cases import load_agent_regression_cases, parse_pipe_list


ROOT = Path(__file__).resolve().parents[1]


def test_parse_pipe_list_trims_and_drops_empty_values() -> None:
    assert parse_pipe_list(" search_figures | hybrid_search_knowledge | ") == (
        "search_figures",
        "hybrid_search_knowledge",
    )


def test_common_agent_regression_suite_is_fixed_and_covered() -> None:
    cases = load_agent_regression_cases(ROOT / "data" / "evaluation" / "agent_regression_cases.csv")

    assert len(cases) == 34
    assert sum(1 for case in cases if case.modality == "text") == 30
    assert sum(1 for case in cases if case.modality == "image") == 4
    assert {case.suite for case in cases} == {"agent_common_v1"}
    assert len({case.case_id for case in cases}) == len(cases)


def test_common_agent_regression_suite_contains_tool_and_refusal_contracts() -> None:
    cases = {
        case.case_id: case
        for case in load_agent_regression_cases(ROOT / "data" / "evaluation" / "agent_regression_cases.csv")
    }

    assert cases["agent_reg_text_010"].expected_tools == ("search_figures",)
    assert cases["agent_reg_text_010"].forbidden_tools == ("hybrid_search_knowledge",)
    assert cases["agent_reg_text_013"].expected_refusal is True
    assert cases["agent_reg_text_016"].forbidden_tools == ("search_figures",)
    assert cases["agent_reg_image_002"].expected_tools == (
        "analyze_user_image",
        "hybrid_search_knowledge",
    )


def test_loader_rejects_image_case_without_image_path(tmp_path: Path) -> None:
    path = tmp_path / "cases.csv"
    path.write_text(
        "case_id,suite,modality,question,image_path,intent_category,expected_tools,"
        "forbidden_tools,expected_refusal,expected_min_sources,expected_min_citations,"
        "latency_budget_ms,notes\n"
        "bad,agent_common_v1,image,question,,user_image_only,analyze_user_image,,false,0,0,1,note\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="image_path"):
        load_agent_regression_cases(path)
