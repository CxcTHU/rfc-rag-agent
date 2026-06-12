# 阶段 29 发现与关键决策

## 为什么需要重建 embedding

### 问题：chunk_embeddings 数量膨胀且 provider 混杂

阶段 28 结束时：
- chunks = 12,716
- chunk_embeddings = 21,634

21,634 > 12,716 的原因：
1. 阶段 18 为当时的 8,918 条 chunk 建了一套 **真实 Jina v3** embedding（约 8,918 条）。
2. 阶段 18 同时建了一套 **deterministic** embedding（约 8,918 条）。
3. 阶段 28 新增了约 3,798 条 chunk（来自网页爬取、Wikipedia、标准 PDF），只用 deterministic 重建了索引。
4. 阶段 28 的 `--provider deterministic` 会跳过已有 deterministic embedding 的旧 chunk，但旧 Jina embedding 仍保留。
5. 阶段 28 Phase 8 清理了 458 个低质量文档（级联删除了对应 chunks），但这些 chunk 的旧 Jina embedding 可能有孤立残留。

结果：chunk_embeddings 表中混杂了三类数据：
- 旧 Jina embedding（覆盖旧 8,918 chunks 中仍存活的部分）
- 旧 deterministic embedding（覆盖旧 chunks）
- 新 deterministic embedding（覆盖新 chunks）

### 问题：新增语料在真实检索中"隐形"

阶段 28 新增的 170 篇文档（网页 136 + Wikipedia 25 + 标准 9）只有 deterministic embedding。deterministic embedding 是哈希假向量，无语义能力。用户真实提问时，这些文档在 VectorSearchService 中的语义匹配得分是随机的，等同于不参与检索。

### 决策：全量清理 + 统一重建

不做增量修补，而是：
1. 删除全部 chunk_embeddings（21,634 → 0）。
2. 用真实 Jina v3 重建全部 12,716 条（统一 provider、统一 model、统一维度）。
3. 再用 deterministic 重建一遍（CI/测试需要）。
4. 最终：chunk_embeddings = 25,432（12,716 × 2 provider）。

理由：增量修补需要判断哪些旧 Jina embedding 仍有效、哪些已过期，逻辑复杂且容易遗漏；全量重建虽然多花 API 调用，但结果干净、可审计。

## Jina API 调用量估算

- chunks = 12,716
- Jina embedding batch API 通常支持每次 100-2048 tokens 的文本
- 假设 batch-size = 64，约需 199 次 API 调用
- 假设 delay = 1s，纯等待约 199 秒 ≈ 3.3 分钟
- 加上网络延迟和计算，估计总耗时 5-10 分钟
- 成本：Jina v3 embedding API 对开源模型免费或极低成本

## 评测方案

### 复用已有评测集

- `data/evaluation/stage19_chinese_hard_queries.csv`：19 题（5 cross_passage + 5 confusable + 5 parameter_detail + 4 refusal）
- `data/evaluation/cn_fulltext_queries.csv`：阶段 18 中文验证集

### 新增 stage29 评测集

覆盖阶段 28 新增的三类语料：
- Wikipedia 百科语料：测试检索是否能召回大坝类型、混凝土基础知识
- 标准/规范语料：测试检索是否能召回 FEMA dam safety 等公开标准内容
- 高质量网页语料：测试检索是否能召回清理后保留的有效网页文档
- 拒答边界：确认 responsibility_gate 在新语料环境下不退化

### 评测指标

- precision@1/3/5：top-k 命中率
- coverage_ratio：答案要点覆盖率（复用阶段 20 方法论）
- refusal_accuracy：拒答边界准确率
- source_type_distribution：检索结果中各 source_type 的占比（检验新语料是否被召回）
- 与 deterministic 基线对比：量化真实语义向量的增益

## 与现有模块的关系

- `scripts/build_vector_index.py`：已有 `--provider`、`--batch-size`、`--sleep-seconds`、`--max-retries` 参数，直接复用。
- `app/services/retrieval/vector_cache.py`：Jina 重建后 VectorIndexCache 自动 invalidate 并重新加载。
- `app/services/retrieval/reranking.py`：rerank 层不受 embedding provider 影响，保持不变。
- `tests/conftest.py`：强制 pytest 使用 deterministic provider，不受真实 Jina embedding 影响。

## Phase 0 基线核验发现

- 当前阶段 29 分支已从本地 `main` 创建：`codex/phase-29-real-embedding-quality-eval`。
- 本地 `main` 顶部为 `07dadf0 Merge phase 28 web crawl auto ingest`，阶段 28 功能提交为 `b345cd8 Complete phase 28 web crawl auto ingest`。
- `phase-28-complete` 指向 `b345cd8`，符合“tag 指向阶段 28 最终功能提交”的要求。
- `git merge-base --is-ancestor phase-28-complete main` 通过，说明阶段 28 已合并到本地 `main`。
- `git status -sb` 显示本地 `main` 领先 `origin/main` 2 个提交；阶段 29 按用户要求不推送、不创建 PR，因此该远端同步状态仅记录，不在本阶段处理。
- 根目录 `task_plan.md`、`findings.md`、`progress.md` 在开工前已有阶段 29 规划内容，视为规划方 Claude 预写的交接文件，本阶段继续在其基础上维护，不覆盖其计划结构。

## Phase 1 设计发现

- `scripts/build_vector_index.py` 已具备阶段 29 所需的 `--batch-size`、`--sleep-seconds`、`--max-retries` 参数，可直接支持限速、批处理和临时错误重试。
- `app/services/retrieval/embedding.py` 的 `create_embedding_provider()` 当前支持 `deterministic` 和 `openai-compatible`，但不支持 `jina` 别名；阶段 29 的用户指定命令是 `--provider jina`，需要补齐 alias，映射到 OpenAI-compatible embedding provider。
- `ChunkEmbedding` 表已有 `(chunk_id, provider, model_name)` 唯一约束，适合阶段 29 最终验证“同 provider/model 下无重复”。
- 设计文档已落盘到 `docs/stage29_real_embedding_quality_eval.md`，后续 Phase 以该文档为执行边界。

## Phase 2 清理发现

- 真实数据库 dry-run 结果确认阶段 29 的问题判断准确：`chunks=12716`，`chunk_embeddings=21634`。
- provider 分布为：
  - `deterministic / hash-token-v1 / dim=64`：12716 条。
  - `openai-compatible / jina-embeddings-v3 / dim=1024`：8918 条。
- 孤立 embedding 为 0，说明阶段 28 清理后没有留下指向缺失 chunk 的向量记录；本阶段仍选择全量清理，原因是旧 Jina 覆盖范围只有旧语料，不覆盖阶段 28 新增语料。
- 已执行 `cleanup_stale_embeddings.py --execute`，当前 `chunk_embeddings=0`，`chunks=12716` 不变。
- 后续 Phase 3 需要注意：历史 Jina provider 名在表中是 `openai-compatible`，但阶段 29 目标要求最终 provider 为 `jina`；这需要 provider alias 既能调用 OpenAI-compatible API，又能把 `provider_name` 保存为 `jina`。

## Phase 3 真实 Jina 重建发现

- `jina` provider alias 已补齐：底层复用 OpenAI-compatible `/embeddings` 协议，数据库中的 `provider` 保存为 `jina`，满足阶段 29 最终计数标准。
- 本地 `.env` 中 Jina embedding 配置完整：provider 原配置为 `openai-compatible`，model 为 `jina-embeddings-v3`，base URL 为 `https://api.jina.ai/v1`，dimension 为 1024，API key 已配置但未打印。
- 全量真实重建一次完成：`total=12716`、`indexed=12716`、`updated=0`、`skipped=0`。
- 重建后验证：Jina embedding 12716 条，覆盖 12716 个 distinct chunk，无孤立、无同 provider/model 重复。
- 最小 benchmark 显示真实 query embedding 单次约 0.94-1.01 秒；hybrid search 单次约 2.60-2.78 秒。该耗时可作为阶段 29 报告中的真实性能基线，但不作为 CI 门槛。

## Phase 4 deterministic 补建发现

- deterministic 补建一次完成：`total=12716`、`indexed=12716`、`updated=0`、`skipped=0`。
- 最终 `chunk_embeddings=25432`，精确等于 `12716 chunks × 2 providers`。
- provider 分布符合完成标准：
  - `jina / jina-embeddings-v3 / dim=1024`：12716 条。
  - `deterministic / hash-token-v1 / dim=64`：12716 条。
- 每个 provider 均覆盖 12716 个 distinct chunk，孤立记录和重复 provider/model 组均为 0。
- 全量测试 `549 passed, 1 warning`，说明新增 Jina alias 和清理脚本没有破坏 deterministic 回归。

## Phase 5 评测集发现

- 阶段 29 新增评测集采用独立 schema：`query_id,question,category,expected_source_type,expected_answer_points,expected_refused,notes`，便于 Phase 6 脚本同时兼容新语料题和拒答边界题。
- 新增 18 题覆盖：
  - Wikipedia：RCC dam、拱坝、水利工程、concrete cover、dam applications。
  - standard_document：FEMA EAP、earthquake analysis、Living With Dams、Pocket Safety Guide、inundation mapping。
  - web_page：RFC 优势、RFC 发明者、Jin Feng standards、ACI 318 范围、ACI inspection/testing。
  - refusal：工程签字、API key/Bearer token、绕过付费墙。
- 测试首次发现 CSV 中英文问题含逗号导致列错位，已修正为无逗号文本，并用 `tests/test_stage29_new_corpus_queries.py` 防止回归。

## Phase 6 真实质量评测发现

- `scripts/evaluate_stage29_real_quality.py` 已生成真实 Jina 评测结果；脚本只让 Jina 参与 embedding/query 检索，聊天回答与 reranking 均保持 deterministic，避免扩大真实 API 依赖面。
- 评测结果：
  - `precision_at_1=0.600`
  - `precision_at_3=0.867`
  - `precision_at_5=0.933`
  - `avg_coverage_ratio=0.664`
  - `refusal_accuracy=1.000`
- 检索 source_type 分布显示新语料确实参与召回：`standard_document=25`、`web_page=28`、`wikipedia=9`，同时旧的 institutional/open_access/metadata 语料也仍会进入 top-k。
- 主要问题必须诚实写入质量报告：
  - `stage29_wiki_dam_applications` 未命中 Wikipedia，top1 为 `web_page/Introduction`。
  - `stage29_web_rfc_advantages` top1 命中正确网页，但 expected points 中 `local rocks`、`special concrete`、`construction breakthroughs` 未在 top5 合并证据中完全覆盖，coverage 仅 0.250。
  - 拒答题的 p@k 字段为 false 是因为它们不按检索命中计分；真正的拒答指标看 `refusal_accuracy=1.000`。

## Phase 7 质量报告发现

- `docs/stage29_quality_report.md`、`data/evaluation/stage29_quality_summary.csv` 和 `app/frontend/quality_report.html` 均由 `scripts/build_stage29_quality_report.py` 生成，避免手工复制指标造成不一致。
- `/quality-report/data.json` 和 `/quality-report/export.csv` 已切换到阶段 29 summary；导出文件名为 `stage29_quality_summary.csv`。
- 阶段 29 quality gate 不是强行 pass，而是 `review_required/medium`，原因是真实评测仍有 `p@5_misses=1` 和 `low_coverage=2`。
- 只读报告继续保留筛选、风险队列和导出能力；不触发真实 API、不写数据库、不暴露密钥。

## Phase 8 文档收尾发现

- `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD` 均已更新到阶段 29 人工核验前状态。
- `docs/phase_reviews/phase-29.md` 当前是验收草稿，结论保持 `REVIEW_REQUIRED`，不抢先写 PASS。
- Obsidian 按用户要求只补阶段 29 总页、Phase 汇报索引和总汇报，没有在开发过程中写入小 Phase 汇报。
- 阶段 29 的文档口径统一为：真实 embedding 和评测已完成，但 `/quality-report` overall 仍为 `review_required/medium`，人工需要重点看 1 条 Top-5 未命中和 2 条低覆盖查询。
- 浏览器冒烟发现 `quality_report.html` 内联 JSON 被 `html.escape()` 转成 `&quot;`，导致 `JSON.parse()` 失败后表格为空；已改为只转义 `</script>`，并补测试确认内联 JSON 可被 `json.loads()` 解析。
- 最终全量测试为 `556 passed, 1 warning`；`/quality-report` 页面实际渲染 7 行 summary、3 行风险队列，控制台无 error。
- 阶段 29 收尾仍必须保持不暂存、不提交、不打 tag、不推送。
