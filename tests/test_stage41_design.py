from pathlib import Path


DESIGN_PATH = Path("docs/stage41_post_import_retrieval_optimization.md")


def read_design() -> str:
    return DESIGN_PATH.read_text(encoding="utf-8")


def test_stage41_design_documents_goal_baseline_and_flow() -> None:
    design = read_design()

    for phrase in [
        "0dc5158 Complete phase 40 streaming output safety and corpus import",
        "documents=753",
        "chunks=25687",
        "Stage 30=91.52 / A / pass",
        "GLM-Embedding-3 + deterministic embedding 增量构建",
        "parent chunk 增量补建",
        "FAISS 索引重建（GLM dim=2048）",
        "新增中文 RFC / 中文坝工 / 英文 RFC",
    ]:
        assert phrase in design


def test_stage41_design_locks_phase_order_and_status_files() -> None:
    design = read_design()

    for phrase in [
        "Phase 0：启动校准与规划落盘",
        "Phase 1：设计文档与测试合同",
        "Phase 2：新文档 embedding 构建",
        "Phase 3：parent chunk 补建",
        "Phase 4：FAISS 索引重建",
        "Phase 5：评测集扩展",
        "Phase 6：检索质量评测",
        "Phase 7：检索调优（按需）",
        "Phase 8：全量回归与浏览器 smoke",
        "Phase 9：文档与 Obsidian 收尾",
        "task_plan.md",
        "findings.md",
        "progress.md",
    ]:
        assert phrase in design


def test_stage41_design_documents_embedding_parent_and_faiss_contracts() -> None:
    design = read_design()

    for phrase in [
        "paratera / GLM-Embedding-3 / 2048",
        "deterministic / hash-token-v1 / 64",
        "Jina 不再作为默认 provider",
        "parent rows 不生成 embedding、不进入 FAISS",
        "可索引 child chunks",
        "python scripts/build_vector_index.py --provider glm --batch-size 64",
        "python scripts/build_vector_index.py --provider deterministic --batch-size 64",
        "python scripts/backfill_parent_chunks.py",
        "python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048",
        "VectorIndexCache",
        "load_mode=\"faiss_only\"",
    ]:
        assert phrase in design


def test_stage41_design_documents_evaluation_and_stage30_gate() -> None:
    design = read_design()

    for phrase in [
        "expected_source_type",
        "expected_keywords",
        "expected_coverage",
        "precision@1",
        "precision@3",
        "precision@5",
        "coverage_ratio",
        "source_type_distribution",
        "python scripts/score_stage30_quality.py",
        "Stage 30 必须维持 `91.52 / A / pass` 或更高",
    ]:
        assert phrase in design


def test_stage41_design_keeps_safety_and_submission_boundaries() -> None:
    design = read_design()

    for phrase in [
        "不新增外部数据源",
        "不改变 prompt 策略",
        "不改变 Stage 30 评分权重",
        "不改变默认 chat / embedding / rerank provider 拓扑",
        "不改前端代码",
        "不让真实 API 成为 CI 或本地全量测试前提",
        "不执行 `git add`、`git commit`、`git tag`、`git push`",
        "API key",
        "Bearer token",
        "供应商原始响应",
        "raw_response",
        "`reasoning_content`",
        "hidden thought",
        "完整 chunk 全文",
        "受限全文",
    ]:
        assert phrase in design
