# 阶段 31 进度日志：FAISS 向量索引 + 父子块检索 + 前端精简

## 当前状态

- 当前阶段：阶段 31「FAISS 向量索引 + 父子块检索 + 前端精简」已完成 Phase 0 启动校准，准备进入 Phase 1 设计文档。
- 当前本地分支：`codex/phase-31-faiss-parent-child-retrieval`。
- 当前 Git 状态：从 `main -> e74ce780c584cfd876a56de6fb7b13cabbdefdf0` 创建阶段 31 分支；工作区仅有根目录三份 Planning 文件的阶段 31 改动。
- 阶段 30 已完成开发、验证、提交、创建 `phase-30-complete` tag 并合并到 `main`。
- 阶段 31 建议分支：`codex/phase-31-faiss-parent-child-retrieval`。
- 提交边界：阶段 31 开发完成后必须停在用户人工核验前；不要提交、不要创建 `phase-31-complete` tag、不要 push、不要创建 PR，直到用户明确确认。

## 阶段 30 验收基线

```text
main / origin/main -> e74ce78 Complete phase 30 rag evaluation scoring system
phase-30 分支 -> codex/phase-30-rag-evaluation-scoring-system
phase-30-complete -> e74ce78 Complete phase 30 rag evaluation scoring system
git merge-base --is-ancestor phase-30-complete main -> passed
```

阶段 30 最终验证：

```text
python -m pytest -q
571 passed, 1 warning

GET /health 200
GET /quality-report 200
GET /quality-report/data.json 200
GET /quality-report/export.csv 200
GET /quality-review 200

overall_score=83.17
grade=B
release_decision=review_required
```

系统规模：

```text
documents: 635
chunks: 12,716
chunk_embeddings: 25,432 (Jina v3 1024d + deterministic 64d)
tests: 571 passed, 1 warning
```

## 阶段 31 规划完成记录

已完成根目录三份 Planning with Files 文件改写：

- `task_plan.md`：阶段 31 Phase 0-8 任务计划（FAISS 索引构建、VectorIndexCache 集成、父子块 schema 与迁移、父子块检索、前端精简、评测回归、文档收尾）。
- `findings.md`：当前检索瓶颈分析（numpy 暴力搜索、无真正父子块、前端暴露调试参数）、FAISS 索引类型选择依据、风险与防线。
- `progress.md`：阶段 31 启动状态、阶段 30 基线和后续开发边界。

## 阶段 31 目标概述

阶段 31 要完成三个核心任务：

1. **FAISS 向量索引**：用 `faiss-cpu` 的 `IndexFlatIP` 替代 `VectorIndexCache` 的 numpy 暴力余弦搜索，索引 12,716 × 1024 维 Jina 向量，查询延迟从 ~15ms 降到 ~2-3ms。
2. **父子块检索**：在 `chunks` 表新增 `parent_chunk_id` 自引用外键，实现 child 精准向量召回 → parent 完整上下文组装的检索策略。
3. **前端精简**：把"召回数"、"工具步数"、"source_id"移入折叠的 `<details>` 高级设置区。

## 关键执行边界

- FAISS 索引文件（data/faiss/）加入 .gitignore，不提交到 Git。
- 父子块 parent_chunk_id 为可选字段，旧数据 NULL 时 fallback ContextExpansionService。
- 只对 child chunks 生成 embedding，parent chunks 不生成。
- deterministic provider 测试不受 FAISS 影响（fallback numpy 路径覆盖）。
- FAISS vs numpy 一致性测试：同 query 的 top-5 必须完全一致。
- 不引入 Qdrant / Chroma / PGVector / torch / sentence-transformers。
- 阶段 30 评分 overall_score >= 83.17（不退步）。
- 不把 API key、Bearer token、供应商原始响应写入 Git。
- 未经用户人工核验，不 git add / commit / tag / push / 建 PR。
- docs/phase_reviews/phase-31.md 必须存在。

## Phase 日志

### Phase 9：追加父子块批量落地

状态：已完成。

本 Phase 解决的问题：阶段 31 已有 `parent_chunk_id` schema 和 child -> parent 检索服务，但既有全量 chunks 尚未回填 parent，导致运行时仍主要依赖 `ContextExpansionService` fallback。

RAG 链路位置：资料结构层与检索上下文层之间。child 继续负责 FAISS 召回和引用，parent 只提供更完整回答上下文。

为什么现在做：用户核验发现父子块“形同虚设”，需要先让 12,716 个既有 child 真正挂到 parent，再谈阶段收尾。

已完成：

- 已重新读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 已确认当前分支为 `codex/phase-31-faiss-parent-child-retrieval`。
- 已确认当前工作区存在阶段 31 未提交改动；继续在这些改动上追加，不执行 `git add` / commit / tag / push。
- 已确认 `scripts/build_faiss_index.py` 使用 `~has_children` 跳过 parent chunk，parent 不会进入 FAISS。
- 已把追加工作写入 `task_plan.md` Phase 9-11，并把关键发现写入 `findings.md`。
- 已新增 `scripts/backfill_parent_chunks.py` 和 `tests/test_backfill_parent_chunks.py`。
- 已执行 dry-run：`documents_changed=635 parent_created=6402 child_updated=12716`。
- 已正式执行 backfill：新增 6,402 个 parent，12,716 个既有 child 全部关联 parent。
- 已执行幂等 dry-run：`parent_created=0 parent_reused=6402 child_updated=0`。
- 已核验数据库：`chunks=19118 parent_rows=6402 linked_children=12716 parent_embeddings=0 embeddings=25432`。
- 聚焦测试：`python -m pytest tests\test_backfill_parent_chunks.py tests\test_faiss_index.py tests\test_vector_index_service.py -q` -> `15 passed`。

遗留风险：

- parent 是由既有 child 拼接后按约 1,800 字符切出，适合非破坏性历史回填；人工核验可抽样检查 parent 文本边界是否过宽或跨小节。

### Phase 10：追加 Prompt 质量强化

状态：已完成。

本 Phase 解决的问题：让模型在更长 parent context 下仍保持高引用密度、先回答结论、对比题不偏讲一方。

RAG 链路位置：Prompt 构建层，位于检索上下文和 ChatModelProvider 之间。

为什么现在做：父子块让上下文更完整，但如果 prompt 不约束引用密度，模型可能整段末尾只引用一次，降低阶段 30 的回答质量可审计性。

已完成：

- `DEFAULT_SYSTEM_PROMPT` 增加直接回答、逐事实引用、对比题双边说明。
- `build_user_prompt()` Answer requirements 保持 7 条，含错误前提先纠正规则。
- `tests/test_prompt_builder.py` 增加质量规则断言。
- 聚焦测试：`python -m pytest tests\test_prompt_builder.py tests\test_backfill_parent_chunks.py -q` -> `13 passed`。

### Phase 11：追加评测对比与收尾

状态：已完成。

本 Phase 解决的问题：确认 parent backfill 和 prompt 强化没有让阶段 30 评分退化，没有让 parent 进入 FAISS，也没有破坏全量测试。

RAG 链路位置：质量门禁、索引重建和文档交接层。

为什么现在做：追加代码和数据库变更完成后，必须重新建立可核验的分数、测试和文档证据。

已完成：

- FAISS 重建：`python scripts\build_faiss_index.py --provider jina --model-name jina-embeddings-v3 --dimension 1024` -> `vectors=12716`。
- 阶段 30 评分重跑：`overall=83.17 grade=B release_decision=review_required`。
- 全量测试：`593 passed, 1 warning`。
- 8000 服务重启后核心接口冒烟：`GET /health`、`GET /quality-report`、`POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 均为 200。
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/phase_reviews/phase-31.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 已准备更新 Obsidian Phase 9-11 汇报。
- 仍未执行 `git add` / commit / tag / push / PR。

### Phase 0：启动校准与计划落盘

状态：已完成。

本 Phase 解决的问题：确认阶段 31 的正确起点，避免在阶段 30 旧文档状态或错误分支上继续开发。

RAG 链路位置：版本基线和协作边界，不改运行链路。

为什么现在做：阶段 31 会改底层向量索引、chunk schema 和前端入口，必须先固定阶段 30 评分基线，否则无法判断是否退化。

已完成：

- 已读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage30_rag_evaluation_scoring_system.md`、`docs/stage30_quality_score_report.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 已运行 `git status -sb`、`git log --oneline -5`。
- 已确认 `phase-30-complete` 与 `main` 同指向 `e74ce780c584cfd876a56de6fb7b13cabbdefdf0`，且 `phase-30-complete` 是 `main` 的祖先。
- 已确认当前不是“main 停在阶段 29 合并点”的情况；阶段 31 可从阶段 30 完成后的 `main` 出发。
- 已创建并切换到 `codex/phase-31-faiss-parent-child-retrieval`。
- 已校准 `task_plan.md`、`findings.md`、`progress.md` 的 Phase 0 状态。
- 未移动任何已有阶段 tag，未执行 `git add` / `git commit` / `git tag` / `git push` / PR。

遗留风险：

- `README.md`、`docs/progress.md`、`docs/data_sources.md` 中仍有部分阶段 30 “等待人工核验”的历史文字；阶段 31 收尾时需要统一同步普通文档。
- 当前仅完成 Phase 0，尚未开始代码实现。

### Phase 1：FAISS 向量索引设计文档

状态：已完成。

本 Phase 解决的问题：在写代码前固定 FAISS 索引、父子块 schema、fallback、安全边界和验证口径。

RAG 链路位置：检索召回与回答上下文组装设计层。

为什么现在做：阶段 31 会影响 `VectorIndexCache`、`chunks` schema 和前端入口，先写设计文档能让后续实现保持可测、可回退。

已完成：

- 新增 `docs/stage31_faiss_parent_child_retrieval.md`。
- 明确选择 FAISS `IndexFlatIP`，暂不使用 `IndexHNSWFlat`。
- 明确 FAISS 文件为可重建索引派生物，需加入 `.gitignore`。
- 明确 `chunks.parent_chunk_id` 自引用外键设计。
- 明确 child 负责 embedding 和召回，parent 负责回答上下文，引用仍指向 child。
- 明确旧数据 `parent_chunk_id IS NULL` 时 fallback 到 `ContextExpansionService`。
- 明确六个核心 API、阶段 30 `overall_score >= 83.17`、全量测试和人工核验前不提交的完成标准。

新增/解释的新词：

- FAISS、IndexFlatIP、IndexHNSWFlat、父子块、自引用外键已在 `findings.md` 和阶段 31 设计文档中解释。

### Phase 2：FAISS 索引构建与集成

状态：已完成。

本 Phase 解决的问题：让现有 `chunk_embeddings` 能独立构建为本地 FAISS `.index` 文件。

RAG 链路位置：向量检索的索引构建层；尚未改变线上检索路径。

为什么现在做：`VectorIndexCache` 要优先 FAISS / fallback numpy，必须先有独立可测的 FAISS 索引对象和构建脚本。

已完成：

- `pyproject.toml` 新增 `faiss-cpu>=1.8.0`。
- `.gitignore` 新增 `data/faiss/`。
- 新增 `app/services/retrieval/faiss_index.py`，封装 FAISS `IndexFlatIP` 构建、保存、加载、搜索和 metadata 读写。
- 新增 `scripts/build_faiss_index.py`，从 SQLite `chunk_embeddings` 读取当前有效 embedding，生成 `.index` 与 ids metadata；脚本不调用真实 API、不写数据库。
- 新增 `tests/test_faiss_index.py`。
- 本地安装 `faiss-cpu` 后运行 `python -m pytest tests\test_faiss_index.py -q`：`5 passed`。
- 运行小规模索引构建验证：

```text
python scripts\build_faiss_index.py --provider jina --model-name jina-embeddings-v3 --dimension 1024 --limit 10
faiss index built ... vectors=10 ... index=data\faiss\jina_jina-embeddings-v3_dim1024.index
```

遗留风险：

- Phase 2 只完成独立构建，还未把 FAISS 接入 `VectorIndexCache` 搜索路径。
- 当前只跑了 limit=10 构建验证，全量 FAISS 索引将在 Phase 7 回归中构建。

### Phase 3：VectorIndexCache FAISS 集成

状态：已完成。

本 Phase 解决的问题：让现有向量检索运行时能优先使用完整 FAISS 索引，同时保持 numpy fallback。

RAG 链路位置：向量召回运行层，会影响 `POST /search/vector` 以及复用 vector search 的 hybrid/chat/agent 链路。

为什么现在做：独立 FAISS 文件已经能生成，下一步必须证明它可以接到现有缓存层且不破坏旧行为。

已完成：

- `app/services/retrieval/vector_cache.py` 新增完整 FAISS 索引加载与搜索路径。
- 只有 `complete=true` 的 metadata 才会启用 FAISS，避免 Phase 2 的 limit=10 样本索引被误用。
- 索引缺失、不完整、metadata 不匹配或加载失败时继续走 numpy fallback。
- 新增 `tests/test_vector_cache_faiss.py`。
- 聚焦测试：

```text
python -m pytest tests\test_faiss_index.py tests\test_vector_cache_faiss.py tests\test_vector_search.py -q
13 passed
```

遗留风险：

- 尚未构建全量 FAISS 索引并与阶段 29 评测题集做 top-k 一致性对比；留到 Phase 7。
- 当前 FAISS 路径仍只返回 child/普通 chunk，尚未实现 parent 上下文。

### Phase 4：父子块 Schema 与迁移

状态：已完成。

本 Phase 解决的问题：给 `chunks` 表增加可选 parent 指针，旧数据为空时保持兼容。

RAG 链路位置：资料结构层，为后续 child 召回 -> parent 上下文做准备。

为什么现在做：没有 schema 就无法可靠记录 child 与 parent 的对应关系，只靠相邻 chunk 拼接无法表达真实父子块。

已完成：

- `app/db/models.py` 的 `Chunk` 新增 `parent_chunk_id`、`parent_chunk`、`child_chunks`。
- 新增 `scripts/migrate_parent_chunks.py`，支持 dry-run 和幂等检查。
- 更新 `tests/test_db_models.py`，新增 `tests/test_migrate_parent_chunks.py`。
- 聚焦测试：

```text
python -m pytest tests\test_db_models.py tests\test_migrate_parent_chunks.py -q
7 passed
```

- 本地数据库迁移：

```text
python scripts\migrate_parent_chunks.py --dry-run
chunks.parent_chunk_id missing; dry-run only

python scripts\migrate_parent_chunks.py
chunks.parent_chunk_id added
```

遗留风险：

- SQLite 通过 `ALTER TABLE ADD COLUMN` 增加字段时没有补数据库级外键约束；当前由 ORM relationship、索引和应用逻辑保证关系正确。后续若引入正式迁移工具，可重建表补完整约束。

### Phase 5：父子块生成与检索

状态：已完成。

本 Phase 解决的问题：让 child 召回后可以使用 parent chunk 作为回答上下文，同时保留旧数据 fallback。

RAG 链路位置：切分规划、检索结果扩展和 Brain prompt context assembly。

为什么现在做：`parent_chunk_id` 字段已存在，必须把它接到回答上下文，否则只是空 schema。

已完成：

- 新增 `app/services/ingestion/parent_chunker.py`，提供 parent/child 两层切分规划。
- 新增 `app/services/retrieval/parent_child_search.py`，根据 `parent_chunk_id` 使用 parent content；为空或 parent 缺失时 fallback `ContextExpansionService`。
- 扩展 `ChunkCreate.parent_chunk_id`。
- `BrainService` 在 `build_rag_prompt` 前接入 `ParentChildSearchService`，使默认回答链路可以使用 parent context。
- 新增 `tests/test_parent_child_retrieval.py`，并补充 Brain 主链路测试。
- 聚焦测试：

```text
python -m pytest tests\test_parent_child_retrieval.py tests\test_brain_service.py -q
18 passed
```

遗留风险：

- 当前 parent/child 生成是服务级切分计划，尚未对全量既有语料批量重切；阶段 31 先保证 schema 和主链路可用。
- `VectorIndexService` 仍会索引所有 chunks；后续若批量创建 parent chunk，需要在批处理脚本中只对 child 构建 embedding，避免 parent 进入索引。

### Phase 6：前端精简

状态：已完成。

本 Phase 解决的问题：降低 Agent 主界面的调试参数噪声，让普通用户优先看到提问入口和运行状态。

RAG 链路位置：前端交互层，不改变后端检索、问答或 Agent API。

为什么现在做：阶段 31 已增强底层检索，前端应把高级参数降级为可展开设置，而不是默认占据主流程。

已完成：

- `app/frontend/index.html`：`data-agent-top-k`、`data-agent-max-tool-calls`、`data-agent-source-id` 移入默认收起的 `<details class="advanced-settings">`。
- `app/frontend/static/styles.css`：新增高级设置区和响应式布局样式。
- `tests/test_frontend_app.py`：新增高级设置断言。
- 聚焦测试：

```text
python -m pytest tests\test_frontend_app.py -q
10 passed
```

### Phase 7：评测验证与回归

状态：已完成。

本 Phase 解决的问题：确认阶段 31 改动不降低阶段 30 评分、不破坏核心 API、不破坏前端。

RAG 链路位置：质量门禁与回归验证层。

为什么现在做：FAISS、parent-child 和前端都已实现，必须先通过验证才能进入文档与 Obsidian 收尾。

已完成：

- 全量 FAISS 索引构建：

```text
python scripts\build_faiss_index.py --provider jina --model-name jina-embeddings-v3 --dimension 1024
faiss index built ... vectors=12716
```

- 阶段 31 聚焦测试：

```text
python -m pytest tests\test_faiss_index.py tests\test_vector_cache_faiss.py tests\test_parent_child_retrieval.py tests\test_migrate_parent_chunks.py tests\test_frontend_app.py -q
24 passed
```

- 阶段 30 评分重跑：

```text
python scripts\score_stage30_quality.py
stage30 quality score overall=83.17 grade=B release_decision=review_required
```

- 全量测试：

```text
python -m pytest -q
589 passed
```

- 浏览器验证：

```text
/ 首页：高级设置存在，默认收起；展开后三个高级参数可见
/quality-report：overall=83.17，grade=B，release_decision=review_required
console errors=0
```

- 真实 provider HTTP 冒烟：

```text
GET /health 200
GET /quality-report 200
POST /search 200
POST /search/vector 200
POST /search/hybrid 200
POST /chat 200
POST /agent/query 200
```

遗留风险：

- 真实 provider 500 已修复：Python `urllib` 默认网络路径在本机真实 provider 调用中卡住；已让 embedding、rerank、chat 三类 OpenAI-compatible provider 显式禁用系统代理探测，并将本地 `.env` 的 `EMBEDDING_PROVIDER` 调整为 `jina`。8004 临时服务已验证核心接口全 200。

### Phase 8：文档与 Obsidian 收尾

状态：已完成。

本 Phase 解决的问题：把阶段 31 的代码、验证、风险和人工核验重点同步到普通文档与 Obsidian，确保后续 Agent 或用户能从正确状态继续。

RAG 链路位置：项目交接与知识沉淀层，不改变运行链路。

为什么现在做：阶段 31 已完成代码和验证，必须在提交前把设计、验证证据和遗留风险写清楚，避免人工核验时信息散落在对话里。

已完成：

- `README.md`：新增阶段 31 当前状态、完成内容、验证结果和未提交边界。
- `docs/progress.md`：新增阶段 31 最新状态，记录 FAISS、父子块、前端、测试、浏览器和 API 冒烟。
- `docs/architecture.md`：新增阶段 31 架构增量，说明 FAISS、VectorIndexCache fallback、`parent_chunk_id` 和 parent context。
- `docs/data_sources.md`：说明阶段 31 不新增外部资料来源，`data/faiss/` 是可重建派生产物。
- `AGENT.MD`：新增阶段 31 最新交接状态。
- `docs/phase_reviews/phase-31.md`：新增人工核验草稿。
- `obsidian-vault/阶段/阶段 31 - FAISS向量索引与父子块检索.md`：新增阶段页。
- `obsidian-vault/阶段汇报/阶段 31 - FAISS向量索引与父子块检索/`：新增 Phase 汇报索引和 Phase 0-8 小汇报。
- `obsidian-vault/阶段索引.md`、`obsidian-vault/阶段汇报索引.md`：新增阶段 31 入口，并把阶段 30 移到已完成。

阶段 31 最终状态：

```text
当前分支：codex/phase-31-faiss-parent-child-retrieval
阶段 30 基线：main 和 phase-30-complete 均指向 e74ce78
阶段 31：开发、测试、普通文档、Obsidian 草稿完成
提交状态：尚未 git add / commit / tag / push，未创建 PR
下一步：等待用户人工核验和明确授权
```

最终遗留风险：

- 既有全量语料未做破坏性父子块重切；当前完成 schema、切分计划、主检索链路和测试样例，旧数据 fallback `ContextExpansionService`。
- SQLite 迁移不能补完整数据库级外键约束；当前通过 ORM relationship、索引、可空字段和测试控制风险。
- 真实 provider 核心 API 已全 200；后续若切换网络、代理或 key，建议先复跑 provider 小请求和 8004 冒烟。
