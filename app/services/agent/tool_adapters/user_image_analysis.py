from __future__ import annotations

from pathlib import Path

from app.services.agent import tools as agent_tools
from app.services.agent.image_analysis import ImageAnalysisResult, UserImageAnalyzer
from app.services.agent.image_storage import ImageStorageError, UserImageStorage
from app.services.agent.tool_contracts import (
    AnalyzeUserImageArguments,
    ToolArguments,
    ToolExecutionContext,
)
from app.services.agent.tool_models import AgentToolCallRecord, AgentToolResult


class UserImageAnalysisAdapter:
    def __init__(
        self,
        *,
        storage: UserImageStorage,
        analyzer: UserImageAnalyzer,
    ) -> None:
        self._storage = storage
        self._analyzer = analyzer

    @classmethod
    def from_toolbox(cls, toolbox: object, *, top_k: int = 5) -> UserImageAnalysisAdapter:
        settings = agent_tools.get_settings()
        vision_provider = agent_tools.create_vision_model_provider(
            provider_name=settings.vision_model_provider,
            model_name=settings.vision_model_name,
            api_key=settings.vision_model_api_key,
            base_url=settings.vision_model_base_url,
            timeout_seconds=settings.vision_model_timeout_seconds,
        )
        return cls(
            storage=UserImageStorage(max_size_mb=settings.user_image_max_size_mb),
            analyzer=UserImageAnalyzer(
                vision_provider=vision_provider,
                knowledge_searcher=toolbox.hybrid_search_knowledge,
                figure_searcher=toolbox.search_figures,
                text_top_k=top_k,
            ),
        )

    def analyze(
        self,
        image_path: str,
        question: str,
    ) -> AgentToolResult:
        tool_name = "analyze_user_image"
        try:
            validated_path = self._storage.validate_existing_upload_path(image_path)
            analysis = self._analyzer.describe(validated_path, question)
        except (ImageStorageError, RuntimeError, ValueError, FileNotFoundError) as exc:
            return agent_tools.failed_tool_result(tool_name, "image_path=<user_upload>", exc)
        return image_analysis_tool_result(analysis)

    def execute(
        self,
        arguments: ToolArguments,
        context: ToolExecutionContext,
    ) -> AgentToolResult:
        del context
        if not isinstance(arguments, AnalyzeUserImageArguments):
            raise TypeError("image analysis requires AnalyzeUserImageArguments")
        return self.analyze(arguments.image_path, arguments.question)


def image_analysis_tool_result(analysis: ImageAnalysisResult) -> AgentToolResult:
    tool_name = "analyze_user_image"
    if analysis.domain_relevance != "in_scope":
        return AgentToolResult(
            tool_name=tool_name,
            call=AgentToolCallRecord(
                tool_name=tool_name,
                input_summary="image_path=<user_upload>",
                output_summary=f"image refused by domain gate: {analysis.domain_relevance}",
                succeeded=True,
            ),
            answer="",
            image_analysis=analysis.to_payload(),
            refused=True,
            refusal_reason=analysis.refusal_reason,
        )

    return AgentToolResult(
        tool_name=tool_name,
        call=AgentToolCallRecord(
            tool_name=tool_name,
            input_summary="image_path=<user_upload>",
            output_summary="image described; text_results=0; similar_figures=0",
            succeeded=True,
        ),
        answer=analysis.image_description,
        image_analysis=analysis.to_payload(),
        refused=False,
    )
