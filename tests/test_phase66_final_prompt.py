import ast
from pathlib import Path

from app.services.agent.final_prompt import (
    FinalPromptShape,
    citation_repair_messages,
    evidence_answer_messages,
    tool_calling_messages,
)
from app.services.agent.tool_calling_service import (
    FinalPromptShape as ServiceFinalPromptShape,
)
from app.services.agent.tool_calling_service import (
    citation_repair_messages as service_citation_repair_messages,
)
from app.services.agent.tool_calling_service import (
    evidence_answer_messages as service_evidence_answer_messages,
)
from app.services.agent.tool_calling_service import (
    tool_calling_messages as service_tool_calling_messages,
)


def test_final_prompt_import_path_is_compatibly_reexported() -> None:
    assert service_tool_calling_messages is tool_calling_messages
    assert service_evidence_answer_messages is evidence_answer_messages
    assert service_citation_repair_messages is citation_repair_messages
    assert ServiceFinalPromptShape is FinalPromptShape


def test_tool_calling_service_no_longer_defines_extracted_ownership_functions() -> None:
    source = Path("app/services/agent/tool_calling_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_name_parts = (
        "prompt",
        "citation_repair",
        "checkpoint",
        "tool_definition",
        "merge_search",
        "merge_sources",
    )

    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(part in node.name for part in forbidden_name_parts)
    ]

    assert offenders == []
