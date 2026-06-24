import pytest
from pydantic import ValidationError

from app.services.brain.config import (
    DEFAULT_WORKFLOW_STEPS,
    RetrievalConfig,
    WorkflowConfig,
    WorkflowStepConfig,
)


def test_default_retrieval_config_contains_required_fields_and_workflow() -> None:
    config = RetrievalConfig()

    assert config.retrieval_mode == "auto"
    assert config.top_k == 8
    assert config.min_score == 0.0
    assert config.max_history == 0
    assert config.rerank_top_n == 0
    assert config.prompt_profile == "citation_default"
    assert config.model_provider == "deterministic"
    assert config.workflow_config.enabled_step_names == DEFAULT_WORKFLOW_STEPS


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("top_k", 0),
        ("top_k", 51),
        ("min_score", -0.1),
        ("max_history", -1),
        ("max_history", 51),
        ("rerank_top_n", -1),
        ("rerank_top_n", 51),
    ],
)
def test_retrieval_config_rejects_invalid_numeric_values(
    field_name: str, value: int | float
) -> None:
    with pytest.raises(ValidationError):
        RetrievalConfig(**{field_name: value})


def test_retrieval_config_rejects_rerank_top_n_greater_than_top_k() -> None:
    with pytest.raises(ValidationError, match="rerank_top_n"):
        RetrievalConfig(top_k=3, rerank_top_n=4)


def test_retrieval_config_from_chat_request_preserves_chat_fields() -> None:
    config = RetrievalConfig.from_chat_request(
        top_k=8,
        retrieval_mode="hybrid",
        min_score=0.2,
        model_provider="deterministic",
    )

    assert config.top_k == 8
    assert config.retrieval_mode == "hybrid"
    assert config.min_score == 0.2
    assert config.model_provider == "deterministic"
    assert config.workflow_config.enabled_step_names == DEFAULT_WORKFLOW_STEPS


def test_workflow_config_rejects_unknown_step() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfig(steps=(WorkflowStepConfig(name="unknown"),))


def test_workflow_config_requires_retrieve_and_generate_answer() -> None:
    with pytest.raises(ValidationError, match="retrieve"):
        WorkflowConfig(
            steps=(
                WorkflowStepConfig(name="filter_history"),
                WorkflowStepConfig(name="generate_answer"),
            )
        )

    with pytest.raises(ValidationError, match="generate_answer"):
        WorkflowConfig(steps=(WorkflowStepConfig(name="retrieve"),))


def test_workflow_config_rejects_retrieve_after_generate_answer() -> None:
    with pytest.raises(ValidationError, match="before generate_answer"):
        WorkflowConfig(
            steps=(
                WorkflowStepConfig(name="generate_answer"),
                WorkflowStepConfig(name="retrieve"),
            )
        )
