from inspect import signature

import pytest
from pydantic import ValidationError

from app.services.agent.tool_contracts import (
    AnalyzeUserImageArguments,
    RetrievalArguments,
    ToolAdapter,
    ToolExecutionContext,
)


def test_retrieval_arguments_reject_blank_query() -> None:
    with pytest.raises(ValidationError):
        RetrievalArguments(query="   ")


def test_retrieval_arguments_are_immutable_and_trim_query() -> None:
    arguments = RetrievalArguments(query="  spillway crack  ", top_k=3)

    assert arguments.query == "spillway crack"
    with pytest.raises(ValidationError):
        arguments.query = "changed"


def test_retrieval_arguments_reject_extra_fields_and_invalid_top_k() -> None:
    with pytest.raises(ValidationError):
        RetrievalArguments(query="spillway", top_k=0)
    with pytest.raises(ValidationError):
        RetrievalArguments(query="spillway", unexpected=True)


def test_image_arguments_require_image_path_and_question() -> None:
    with pytest.raises(ValidationError):
        AnalyzeUserImageArguments(image_path="", question="what is shown")
    with pytest.raises(ValidationError):
        AnalyzeUserImageArguments(image_path="image.png", question="   ")


def test_image_arguments_are_immutable_and_trim_values() -> None:
    arguments = AnalyzeUserImageArguments(
        image_path="  uploads/example.png  ",
        question="  what is shown  ",
    )

    assert arguments.image_path == "uploads/example.png"
    assert arguments.question == "what is shown"
    with pytest.raises(ValidationError):
        arguments.question = "changed"


def test_tool_execution_context_is_immutable() -> None:
    context = ToolExecutionContext(
        run_id="run-1",
        step_id="step-1",
        iteration=1,
        deadline_monotonic=None,
        cancelled=False,
    )
    with pytest.raises((AttributeError, ValidationError)):
        context.iteration = 2


def test_public_tool_adapter_has_no_any_annotation() -> None:
    rendered = str(signature(ToolAdapter.execute))
    assert "Any" not in rendered
