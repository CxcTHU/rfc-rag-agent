from pathlib import Path


PLAN_PATH = Path("docs/stage13_decompose_plan.md")


def test_stage_13_decompose_plan_documents_data_flow_and_boundaries() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "rule-based decompose",
        "deduplicate by chunk_id",
        "sub_query",
        "Brain evidence confidence",
        "SYNONYM_RULES",
        "unsupported",
        "default_hybrid",
    ]:
        assert phrase in plan


def test_stage_13_decompose_plan_keeps_hyde_and_memory_out_of_default_path() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    for phrase in [
        "不建议进入默认链路",
        "不能作为 deterministic 自动回归前提",
        "不应把它扩成长期记忆系统",
        "只保留最近 1-3 条问题",
    ]:
        assert phrase in plan
