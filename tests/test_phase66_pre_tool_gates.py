from app.services.agent.pre_tool_gates import (
    ToolCallingCoordinatorGateAdapter,
    build_tool_calling_pre_tool_gate_decision,
)
from app.services.agent.tool_calling_service import (
    ToolCallingCoordinatorGateAdapter as ServiceGateAdapter,
)
from app.services.agent.tool_calling_service import (
    build_tool_calling_pre_tool_gate_decision as service_pre_tool_gate,
)


def test_pre_tool_gate_import_path_is_compatibly_reexported() -> None:
    assert service_pre_tool_gate is build_tool_calling_pre_tool_gate_decision
    assert ServiceGateAdapter is ToolCallingCoordinatorGateAdapter
