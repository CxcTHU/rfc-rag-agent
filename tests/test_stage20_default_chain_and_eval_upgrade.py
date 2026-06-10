"""阶段 20 设计文档断言测试。"""

from __future__ import annotations

from pathlib import Path


DESIGN_PATH = Path("docs/stage20_default_chain_and_eval_upgrade.md")


def read_design() -> str:
    assert DESIGN_PATH.exists(), f"missing {DESIGN_PATH}"
    return DESIGN_PATH.read_text(encoding="utf-8")


def test_stage_20_design_documents_core_artifacts_and_flow() -> None:
    design = read_design()

    for phrase in (
        "coverage_ratio",
        "真实 Jina query 端校验",
        "source_type_reweight",
        "responsibility_gate",
        "quality gate",
        "POST /search/hybrid",
        "POST /chat",
        "POST /agent/query",
    ):
        assert phrase in design


def test_stage_20_design_defines_default_switch_gate() -> None:
    design = read_design()

    for phrase in (
        "delta_precision_at_1 >= 0.10",
        "delta_deep_fulltext_top1_rate >= 0.20",
        "refusal_accuracy >= baseline_refusal_accuracy",
        "keep_existing_hybrid",
        "HYBRID_SOURCE_TYPE_REWEIGHT_ENABLED",
        "HYBRID_SOURCE_TYPE_REWEIGHT_PROFILE",
    ):
        assert phrase in design


def test_stage_20_design_keeps_real_api_and_manual_verification_boundaries() -> None:
    design = read_design()

    for phrase in (
        "不重做 chunk embedding",
        "真实 API key",
        "供应商原始敏感响应",
        "不进入 CI",
        "不提交",
        "不打 `phase-20-complete` tag",
        "不 push",
        "不 PR",
    ):
        assert phrase in design
