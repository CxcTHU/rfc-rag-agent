# 阶段 29 任务计划：真实 Embedding 重建 + 端到端质量闭环

## 目标

在阶段 28「网页爬取 + 自动入库 + 语料清理 + Wikipedia/标准补充」已完成并合并到 `main` 的基础上，完成阶段 29：清理历史残留 embedding，用真实 Jina v3 为全部 12,716 条 chunk 统一重建语义向量索引，并跑一轮端到端检索质量评测，产出可展示的质量报告。阶段完成后停在用户人工核验前，不提交、不打 tag、不推送。

## 背景

阶段 28 用 `--provider deterministic`（哈希假向量）重建索引，新增的 170 篇文档（网页/Wikipedia/标准 PDF）在真实语义检索中是"隐形"的。同时 `chunk_embeddings=21,634` 大于 `chunks=12,716`，存在历史多批次残留（旧 Jina + 旧 deterministic 混杂）。本阶段的核心价值：让全部语料在真实检索中可用，并用真实指标量化检索效果。

## 硬约束

- 阶段 29 开发完成前后均不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。
- 不移动任何已有阶段 tag，尤其是 `phase-28-complete`。
- 保留用户或其他 session 的已有改动，不重置 Git，不覆盖无关文件。
- 不引入 `torch` / `sentence-transformers` 等重依赖。
- 真实 Jina API 调用仅在脚本中执行，不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始敏感响应写入 Git、CSV、文档、测试或 Obsidian。
- 保证现有 API 端点不被破坏。
- Jina 调用必须限速（delay ≥ 0.5s），遵守速率限额，支持断点续建。

## Phase 顺序

### Phase 0：启动校准与文件计划

**状态：已完成**

**解决的问题**：确认阶段 28 的最终状态、tag、main 起点和阶段 29 分支。

**RAG 链路位置**：阶段起点校准，不改运行链路。

**为什么现在做**：阶段 29 依赖阶段 28 已合并到 `main`，必须先确认。

**任务**
- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读阶段 28 设计文档、phase review，以及根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 核对 `phase-28-complete` tag 指向阶段 28 最终功能提交，且已合并到 main。
- 从阶段 28 完成并合并后的 main 出发，创建或切换到 `codex/phase-29-real-embedding-quality-eval`。
- 将根目录三份 Planning with Files 文件校准为阶段 29。

**验证方式**
- `git status -sb`
- `git log --oneline -5`
- `git merge-base --is-ancestor phase-28-complete main`

**完成标准**
- 当前分支为 `codex/phase-29-real-embedding-quality-eval`。
- `phase-28-complete` 不移动，且已并入 `main`。
- `task_plan.md`、`findings.md`、`progress.md` 已切换为阶段 29。

**实际完成记录**
- 已按入口规则阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-28.md`、`task_plan.md`、`findings.md`、`progress.md`。
- `git log --oneline -5` 显示 `07dadf0 Merge phase 28 web crawl auto ingest` 位于当前 `main` 顶部，`b345cd8 Complete phase 28 web crawl auto ingest` 为阶段 28 最终功能提交。
- `phase-28-complete` 当前指向 `b345cd8 Complete phase 28 web crawl auto ingest`，未移动 tag。
- `git merge-base --is-ancestor phase-28-complete main` 通过，确认阶段 28 已并入本地 `main`。
- 已从阶段 28 合并后的 `main` 创建并切换到 `codex/phase-29-real-embedding-quality-eval`。
- 当前遵守阶段 29 提交边界：未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

### Phase 1：阶段 29 设计文档

**状态：已完成**

**解决的问题**：固化 embedding 清理策略、Jina 重建方案、评测方法论和质量报告格式。

**RAG 链路位置**：向量化层 + 评测层。

**为什么现在做**：先设计再执行，确保清理和重建操作可控、可回滚。

**任务**
- 新增 `docs/stage29_real_embedding_quality_eval.md`。
- 说明 embedding 残留分析：为什么 21,634 > 12,716，哪些是过期的。
- 说明清理策略：删除全部 chunk_embeddings，从零重建。
- 说明 Jina 重建方案：`build_vector_index.py --provider jina`，限速、批次、断点续建、重试。
- 说明 deterministic 索引保留策略：真实 Jina 重建后，再跑一遍 deterministic 保证 CI 测试可用。
- 说明评测方案：复用 stage19/20 评测集 + 新增 stage29 覆盖新语料的查询。
- 说明质量报告格式和完成标准。

**完成标准**
- `docs/stage29_real_embedding_quality_eval.md` 已创建。

**实际完成记录**
- 已新增 `docs/stage29_real_embedding_quality_eval.md`。
- 设计文档已覆盖 embedding 残留原因、全量清理策略、Jina 重建限速与断点续建、deterministic 补建、评测集与指标、质量报告和安全边界。
- 代码预检发现：当前 `create_embedding_provider()` 支持 OpenAI-compatible provider，但尚未支持用户指定命令中的 `--provider jina` 别名；后续实现阶段需要补 alias 与测试。

### Phase 2：Embedding 残留清理

**状态：已完成**

**解决的问题**：chunk_embeddings 表存在 21,634 条混杂记录（旧 Jina 8918 条 + deterministic 12,716 条），部分旧 Jina embedding 关联的 chunk 已在阶段 28 清理中被级联删除。需要清理到干净起点。

**RAG 链路位置**：向量索引层。

**为什么现在做**：在重建前先清理，避免残留影响重建结果和检索质量。

**任务**
- 新增 `scripts/cleanup_stale_embeddings.py`，清理 chunk_embeddings 表：
  - 统计当前 provider 分布（deterministic / jina / 其他）。
  - 找出关联 chunk 已不存在的孤立 embedding（如有）。
  - 提供 `--dry-run` 预览和 `--execute` 实际删除。
  - 支持按 provider 选择性删除或全部删除。
- 执行清理，目标：chunk_embeddings = 0（干净起点）。
- 补测试 `tests/test_cleanup_stale_embeddings.py`。

**验证方式**
- 清理后 `SELECT COUNT(*) FROM chunk_embeddings` = 0。
- `SELECT COUNT(*) FROM chunks` 仍 = 12,716（chunks 不受影响）。
- 测试通过。

**完成标准**
- chunk_embeddings 表已清空。
- chunks 表数量不变。
- 清理脚本有 dry-run 和测试。

**实际完成记录**
- 已新增 `scripts/cleanup_stale_embeddings.py`，支持 `--dry-run`、`--execute` 和可选 `--provider` 过滤。
- 已新增 `tests/test_cleanup_stale_embeddings.py`，覆盖 dry-run 不删除、execute 删除、provider 过滤和孤立 embedding 统计。
- 聚焦测试通过：`4 passed`。
- 真实数据库 dry-run：`chunks=12716`、`chunk_embeddings=21634`、`orphan_embeddings=0`；provider 分布为 deterministic 12716、openai-compatible/jina-embeddings-v3 8918。
- 已执行清理：`chunk_embeddings 21634 -> 0`。
- 清理后验证：`chunks=12716`，`chunk_embeddings=0`。

### Phase 3：真实 Jina Embedding 重建

**状态：已完成**

**解决的问题**：用真实 Jina v3 语义模型为全部 12,716 条 chunk 生成 embedding，让所有语料在语义检索中真正可用。

**RAG 链路位置**：向量化层，是 VectorSearchService 和 HybridSearchService 的数据基础。

**为什么现在做**：清理完成后立即重建，一步到位。

**任务**
- 确认本地 `.env` 中 Jina embedding 配置（provider、model_name、api_key、base_url）可用。
- 运行 `scripts/build_vector_index.py --provider jina --batch-size 64 --sleep-seconds 1 --max-retries 3`。
- 监控进度：记录总耗时、成功/失败/跳过数量。
- 如果中途因速率限制中断，用同一命令续建（已有 embedding 的 chunk 应被跳过）。
- 重建完成后验证：`chunk_embeddings` 数量应 = 12,716，provider 全部为 jina。

**验证方式**
- `SELECT COUNT(*) FROM chunk_embeddings WHERE provider='jina'` = 12,716。
- `SELECT COUNT(DISTINCT chunk_id) FROM chunk_embeddings` = 12,716。
- 运行 `scripts/benchmark_retrieval.py` 确认检索耗时正常。

**完成标准**
- 全部 12,716 条 chunk 均有 Jina embedding。
- 无孤立或重复 embedding。
- benchmark 检索耗时可接受。

**实际完成记录**
- 已为 `create_embedding_provider()` 增加 `jina` provider 别名，复用 OpenAI-compatible embedding 请求逻辑，并将索引 provider 名保存为 `jina`。
- 已补 `tests/test_embedding_provider.py` 中的 Jina alias 测试。
- 聚焦测试通过：`tests/test_embedding_provider.py tests/test_cleanup_stale_embeddings.py` 共 `17 passed`。
- 已确认本地 `.env` Jina embedding 配置完整，仅输出 key 是否存在，未打印密钥。
- 已运行真实重建命令：`scripts/build_vector_index.py --provider jina --batch-size 64 --sleep-seconds 1 --max-retries 3`。
- 重建结果：`total=12716`、`indexed=12716`、`updated=0`、`skipped=0`、`provider=jina`、`model=jina-embeddings-v3`、`dimension=1024`。
- 数据库验证：`jina_embeddings=12716`、`distinct_jina_chunk_ids=12716`、`orphan_embeddings=0`、`duplicate_provider_model_groups=0`。
- 已运行 `scripts/benchmark_retrieval.py --provider jina --runs 1`，两条默认 query 均完成；Jina query embedding 约 0.94-1.01 秒，vector search 约 1.04-3.04 秒，hybrid search 约 2.60-2.78 秒。

### Phase 4：Deterministic 索引补建（CI 保障）

**状态：已完成**

**解决的问题**：CI 和本地全量测试依赖 deterministic provider，需要在真实 Jina 之外保留一套 deterministic embedding。

**RAG 链路位置**：测试基础设施。

**为什么现在做**：Phase 3 只建了 Jina embedding，测试框架仍需 deterministic。

**任务**
- 运行 `scripts/build_vector_index.py --provider deterministic --batch-size 64`。
- 验证 deterministic embedding 数量也 = 12,716。
- 全量测试确认通过。

**验证方式**
- `SELECT COUNT(*) FROM chunk_embeddings WHERE provider='deterministic'` = 12,716。
- 总 chunk_embeddings = 25,432（12,716 Jina + 12,716 deterministic）。
- `python -m pytest -q` 全量通过。

**完成标准**
- 双 provider embedding 完整。
- 全量测试通过。

**实际完成记录**
- 已运行 `scripts/build_vector_index.py --provider deterministic --batch-size 64`。
- 补建结果：`total=12716`、`indexed=12716`、`updated=0`、`skipped=0`、`provider=deterministic`、`model=hash-token-v1`、`dimension=64`。
- 最终索引验证：`chunk_embeddings=25432`，其中 `jina/jina-embeddings-v3/dim=1024 = 12716`、`deterministic/hash-token-v1/dim=64 = 12716`。
- 每个 provider 均覆盖 12716 个 distinct chunk；`orphan_embeddings=0`；`duplicate_provider_model_groups=0`。
- 全量测试通过：`549 passed, 1 warning`。

### Phase 5：评测数据集更新

**状态：已完成**

**解决的问题**：现有评测集（stage19/20）针对旧语料设计，缺少对阶段 28 新增语料（网页、Wikipedia、标准 PDF）的覆盖。

**RAG 链路位置**：评测层。

**为什么现在做**：重建完成后，需要评测集能验证新旧语料的检索效果。

**任务**
- 复用 `data/evaluation/stage19_chinese_hard_queries.csv`（19 题）。
- 复用 `data/evaluation/cn_fulltext_queries.csv`（阶段 18 验证集）。
- 新增 `data/evaluation/stage29_new_corpus_queries.csv`，覆盖：
  - Wikipedia 百科知识题（3-5 题）：检验百科语料是否在检索中被召回。
  - 标准/规范相关题（3-5 题）：检验 FEMA/USBR 标准语料是否在检索中被召回。
  - 高质量网页语料题（3-5 题）：检验清理后保留的网页文档是否有效。
  - 拒答边界题（2-3 题）：确认 responsibility_gate 不退化。
- 合并为统一评测集或在评测脚本中同时加载多个 CSV。

**完成标准**
- 新增评测查询覆盖三类新语料 + 拒答边界。
- 评测集格式与现有评测脚本兼容。

**实际完成记录**
- 已新增 `data/evaluation/stage29_new_corpus_queries.csv`，共 18 题。
- 覆盖范围：Wikipedia 5 题、标准/指南 5 题、web_page 5 题、拒答边界 3 题。
- 已新增 `tests/test_stage29_new_corpus_queries.py`，校验题量、类别覆盖、拒答题数量、字段完整性和 source_type 合法性。
- 聚焦测试通过：`2 passed`。

### Phase 6：端到端质量评测

**状态：已完成**

**解决的问题**：用真实 Jina embedding 运行端到端检索+问答评测，量化系统的真实检索效果。

**RAG 链路位置**：全链路评测（query embedding → vector search → hybrid search → rerank → agent answer）。

**为什么现在做**：重建和评测集就绪后，产出真实质量数据。

**任务**
- 新增 `scripts/evaluate_stage29_real_quality.py`：
  - 使用真实 Jina embedding（query 也用 Jina 编码）。
  - 对每道评测题：记录 top-k 检索结果、precision@1/3/5、source_type 分布、coverage_ratio。
  - 对拒答题：记录 refusal 是否正确触发。
  - 输出 `data/evaluation/stage29_real_quality_results.csv` 和 `stage29_real_quality_summary.csv`。
- 与阶段 19/20 的 deterministic 基线对比，量化真实 Jina 的增益。
- 运行基准脚本 `scripts/benchmark_retrieval.py` 记录性能数据。

**验证方式**
- 评测脚本运行无错误。
- 产出 results CSV 和 summary CSV。
- precision@1 和 coverage_ratio 有具体数值（不要求特定门槛，诚实记录）。

**完成标准**
- 评测结果 CSV 已生成。
- 质量数据诚实记录，不伪造。

**实际完成记录**
- 已新增 `scripts/evaluate_stage29_real_quality.py`，使用真实 Jina embedding provider 运行 hybrid 检索，并用 deterministic chat provider 检查拒答边界。
- 脚本进程内强制 reranking 使用 deterministic provider，避免阶段 29 评测误触发真实 reranking API。
- 已新增 `tests/test_evaluate_stage29_real_quality.py`，覆盖查询读取、hit/coverage 计算、source_type_distribution 和 summary。
- 聚焦测试通过：`3 passed`。
- 已运行 `scripts/evaluate_stage29_real_quality.py --provider jina --top-k 5`。
- 已生成 `data/evaluation/stage29_real_quality_results.csv` 和 `data/evaluation/stage29_real_quality_summary.csv`。
- 真实评测 summary：`total_queries=18`、`non_refusal_total=15`、`precision_at_1=0.600`、`precision_at_3=0.867`、`precision_at_5=0.933`、`avg_coverage_ratio=0.664`、`refusal_total=3`、`refusal_accuracy=1.000`。
- 诚实记录的主要问题：`stage29_wiki_dam_applications` 未命中 expected source_type；`stage29_web_rfc_advantages` 命中正确网页但 coverage_ratio 仅 0.250；拒答边界 3/3 正确。

### Phase 7：质量报告与 /quality-report 更新

**状态：已完成**

**解决的问题**：把评测结果整理成可展示的质量报告，更新 API 端点。

**RAG 链路位置**：可观测层。

**为什么现在做**：评测数据就绪后，产出面试可展示的报告。

**任务**
- 新增 `docs/stage29_quality_report.md`，包含：
  - 语料概况（635 文档、12,716 chunks、各 source_type 分布）。
  - 真实 Jina embedding 检索质量（precision@k、coverage_ratio、refusal accuracy）。
  - 与 deterministic 基线的对比。
  - 性能基准（检索耗时）。
  - 结论和下一步建议。
- 更新 `GET /quality-report` 静态报告内容。

**完成标准**
- 质量报告文档已生成。
- /quality-report 端点返回最新数据。

**实际完成记录**
- 已新增 `scripts/build_stage29_quality_report.py`，从阶段 29 results/summary 生成质量汇总 CSV、Markdown 和 HTML。
- 已生成 `docs/stage29_quality_report.md`。
- 已生成 `data/evaluation/stage29_quality_summary.csv`。
- 已更新 `app/frontend/quality_report.html` 为阶段 29 只读质量报告。
- 已更新 `app/api/frontend.py`，使 `/quality-report/data.json` 和 `/quality-report/export.csv` 读取/导出 `stage29_quality_summary.csv`。
- 已新增 `tests/test_build_stage29_quality_report.py`，并更新 `tests/test_frontend_app.py` 的阶段 29 断言。
- 聚焦测试通过：`tests/test_build_stage29_quality_report.py tests/test_frontend_app.py` 共 `7 passed`。
- 报告质量门槛：`review_required/medium`；人工复核重点为 `stage29_wiki_dam_applications` 和 `stage29_web_rfc_advantages`。

### Phase 8：回归验证 + 文档与 Obsidian 收尾

**状态：已完成**

**解决的问题**：确保阶段 29 改动不破坏现有功能，同步入口文档。

**RAG 链路位置**：全链路回归。

**为什么现在做**：阶段收尾必做。

**任务**
- 全量测试 `python -m pytest -q`。
- 同步 `README.md`、`docs/progress.md`、`docs/architecture.md`、`AGENT.MD`。
- 补 `docs/phase_reviews/phase-29.md` 验收草稿。
- 补 Obsidian 阶段 29 汇报。
- 给出面试表达。

**完成标准**
- 全量测试通过。
- 入口文档已同步。
- phase review 已生成。
- 阶段停在人工核验前：未提交、未打 tag、未推送。

**实际完成记录**
- 已同步 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 已新增 `docs/phase_reviews/phase-29.md` 验收草稿。
- 已补 Obsidian 阶段页、阶段 29 汇报索引和阶段 29 汇总草稿。
- 最终全量测试通过：`556 passed, 1 warning`。
- `/quality-report`、`/quality-report/data.json`、`/quality-report/export.csv` 冒烟检查通过。
- 浏览器验证发现并修复 `quality_report.html` 中 JSON payload 被 HTML entity 转义导致表格不渲染的问题；已补 `tests/test_build_stage29_quality_report.py` 防回归。
- 数据库最终核验：`chunks=12716`、`chunk_embeddings=25432`、Jina 12716、deterministic 12716、孤立 0、重复 0。
- 阶段曾按要求停在人工核验前；用户现已明确授权提交阶段 29 整体开发工作并上传 merge 至 GitHub。
