# 阶段 41：导入后检索质量优化

## 目标

阶段 41 从阶段 40 合并后的 `main -> 0dc5158 Complete phase 40 streaming output safety and corpus import` 出发。阶段 40 已完成流式输出安全和语料导入，当前本地语料库为：

```text
documents=753
chunks=25687
institutional_access_pdf=431
open_access_pdf=20
Stage 30=91.52 / A / pass
```

本阶段目标不是继续扩展语料，而是让阶段 40 新导入语料进入完整检索链路：

```text
查询 embedding 覆盖情况
-> GLM-Embedding-3 + deterministic embedding 增量构建
-> parent chunk 增量补建
-> FAISS 索引重建（GLM dim=2048）
-> 评测集扩展（新增中文 RFC / 中文坝工 / 英文 RFC）
-> 检索质量评测 + Stage 30 验证
-> 按需调优或记录跳过
-> 全量回归 + 浏览器 smoke
-> 文档与 Obsidian 收尾
```

## 开工盘点

Codex 接手时已完成只读盘点：

```text
chunk_embeddings total=38192
paratera / GLM-Embedding-3 / 2048 = 12731
deterministic / hash-token-v1 / 64 = 12745
jina / jina-embeddings-v3 / 1024 = 12716
parent_chunk_id is not null = 12716
parent_chunk_id is null = 12971
```

结论：GLM-Embedding-3 与 deterministic 均只覆盖旧约 12.7k chunks；阶段 40 新增语料尚未完整 embedding。阶段 41 优先采用增量补建，补齐后再校验孤立、重复和缺失记录；只有发现混乱时才做局部清理。

口径说明：25,687 是 `chunks` 表总 rows，包含阶段 31 生成的 parent rows。按既有 parent-child retrieval 架构，parent rows 不生成 embedding、不进入 FAISS；embedding 与 FAISS 的验收对象是可索引 child chunks。

## Phase 顺序

阶段 41 严格按 `task_plan.md` 的 Phase 0-9 顺序推进：

1. Phase 0：启动校准与规划落盘。
2. Phase 1：设计文档与测试合同。
3. Phase 2：新文档 embedding 构建。
4. Phase 3：parent chunk 补建。
5. Phase 4：FAISS 索引重建。
6. Phase 5：评测集扩展。
7. Phase 6：检索质量评测。
8. Phase 7：检索调优（按需）。
9. Phase 8：全量回归与浏览器 smoke。
10. Phase 9：文档与 Obsidian 收尾。

每完成任意 Phase，必须更新 `task_plan.md`、`findings.md`、`progress.md`。开发过程中暂不写 Obsidian 小 Phase 汇报，全部开发、测试、普通文档完成后统一补齐。

## Embedding 构建策略

生产 embedding provider 是 `GLM-Embedding-3`，provider 名称沿用当前代码和数据表中的 `paratera`，维度为 `2048`。deterministic provider 是 CI 与本地回归基线，模型名为 `hash-token-v1`，维度为 `64`。Jina 不再作为默认 provider，仅保留为历史对照和回滚参考。

构建原则：

- 先查询 `chunk_embeddings` 覆盖情况，再运行构建命令。
- 优先增量补建缺失 chunks，不主动删除旧 Jina 索引或历史 embedding。
- 构建后校验每个可索引 child chunk 都有 GLM 与 deterministic embedding。
- 校验无孤立 embedding、无同一 provider/model/chunk 的重复记录。
- 真实 provider 调用只在显式命令中发生，不进入 CI 或全量 pytest 前提。

建议命令：

```powershell
python scripts/build_vector_index.py --provider glm --batch-size 64
python scripts/build_vector_index.py --provider deterministic --batch-size 64
```

如本地 `.env` 的 GLM alias 实际落表为 `paratera / GLM-Embedding-3 / 2048`，验收以表内 provider/model/dimension 为准。

## Parent Chunk 补建

阶段 31 已对旧 12,716 child chunks 完成 parent backfill。阶段 40 新增 chunks 尚未关联 parent。Phase 3 使用既有幂等脚本增量补建：

```powershell
python scripts/backfill_parent_chunks.py
```

验收标准：

- 新导入文档 child chunks 已关联 `parent_chunk_id`。
- parent rows 不生成 embedding，不进入 FAISS。
- child chunk 仍负责召回、引用和来源追踪；parent chunk 仅用于回答上下文扩展。

## FAISS 重建

FAISS 文件位于 `data/faiss/`，是 gitignored 的可重建派生产物。阶段 41 必须基于完整 GLM embedding 重建生产索引：

```powershell
python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048
```

验收标准：

- GLM FAISS 向量数等于完整可索引 child chunks 数。
- `_ids.json` 与索引文件 provider/model/dimension 匹配。
- `VectorIndexCache` 能以 `load_mode="faiss_only"` 加载新索引。
- deterministic FAISS 可按测试或回归需要构建，但生产验收以 GLM 索引为主。

## 评测集扩展与检索评测

阶段 41 新增或扩展 `data/evaluation/` 下的检索评测集，覆盖阶段 40 新导入语料：

- 新增中文 RFC / 堆石混凝土论文。
- 新增中文坝工或工程应用论文。
- 新增英文 RFC 相关论文。

评测字段至少包含：

- `query_id`
- `question`
- `expected_source_type`
- `expected_keywords`
- `expected_coverage`
- `category`

检索评测至少输出：

- precision@1 / precision@3 / precision@5
- coverage_ratio
- source_type_distribution
- top source title / source type / rank
- decision 与 next_action

Phase 6 必须重跑：

```powershell
python scripts/score_stage30_quality.py
```

Stage 30 必须维持 `91.52 / A / pass` 或更高。

## 按需调优边界

Phase 7 只在评测暴露问题时进行，调优应优先选择低风险、可解释改动：

- 补充通用领域同义词或中英术语扩展。
- 调整评测脚本中的对照配置。
- 记录 query expansion 缺口、chunk 粒度问题或 rerank 排序问题。

不得为了通过评测写入具体答案泄漏规则，不得修改 Stage 30 评分规则，不得改变 prompt 策略、provider 拓扑、前端代码或数据源边界。若评测已达标，Phase 7 应明确记录跳过原因。

## 安全边界

阶段 41 严格不做：

- 不新增外部数据源。
- 不改变 prompt 策略。
- 不改变 Stage 30 评分权重、等级阈值或 release decision 规则。
- 不改变默认 chat / embedding / rerank provider 拓扑。
- 不改前端代码。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR，直到用户人工核验并明确确认。

任何代码、CSV、文档、测试和 Obsidian 草稿都不得写入：

- API key
- Bearer token
- Authorization header
- 供应商原始响应
- raw_response
- `reasoning_content`
- hidden thought
- 完整 chunk 全文
- 受限全文

## 验证合同

阶段 41 收尾至少运行：

```powershell
python -m pytest tests/test_stage41_design.py -q
python -m pytest -q
python scripts/score_stage30_quality.py
```

浏览器 smoke 覆盖桌面与 390x844 移动端：

- Agent 正常问答。
- 新导入语料能被检索到。
- 阶段 40 的停止生成仍可用。
- 无横向溢出。
- console errors=0。

## 完成标准

- `docs/stage41_post_import_retrieval_optimization.md` 已新增。
- 全部可索引 child chunks 拥有 GLM-Embedding-3 与 deterministic 两套 embedding，无孤立/重复；parent rows 不生成 embedding。
- 新文档 parent chunks 已补建并关联。
- GLM FAISS 索引基于完整 embedding 重建，`VectorIndexCache` 可正常加载。
- 评测集覆盖新增中文 RFC、中文坝工和英文 RFC，检索评测有可追踪 CSV。
- Stage 30 维持 `91.52 / A / pass` 或更高。
- 全量 pytest 通过。
- 桌面与移动浏览器 smoke 通过。
- README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-41.md` 与 Obsidian 草稿完成。
- 最终停在人工核验前状态。
