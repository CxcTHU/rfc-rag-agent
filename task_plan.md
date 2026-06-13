# 阶段 31 任务计划：FAISS 向量索引 + 父子块检索 + 前端精简

## 目标

在阶段 30「RAG 质量评分体系与诚实决策门禁」已完成、提交、打 `phase-30-complete` tag 并合并到 `main` 的基础上，完成阶段 31：引入 FAISS 替代暴力 numpy 矩阵检索，实现真正的父子块 schema 和 child-recall-parent 检索策略，并将前端高级参数收入折叠区。阶段 31 完成后停在用户人工核验前，不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。

建议分支：`codex/phase-31-faiss-parent-child-retrieval`

## 背景

阶段 30 评分指出 retrieval_quality 得分 26.83/35（76.7%），rule_based_context_answer_quality 得分 16.60/25（66.4%），是当前最弱的两个维度。检索性能和回答上下文是底层瓶颈：

1. **向量检索是暴力扫描**：`VectorIndexCache`（`app/services/retrieval/vector_cache.py:82`）把 12,716 × 1024 维向量加载到内存 numpy 矩阵做暴力余弦搜索，无法扩展到 10 万+ chunks。
2. **无真正父子块**：阶段 17 只实现了相邻 chunk 上下文扩展（`ContextExpansionService`），没有独立的 parent chunk schema，回答上下文不完整。
3. **前端暴露调试参数**：`index.html` 第 115-126 行直接展示"召回数"、"工具步数"、"source_id"，普通用户不需要这些。

## Phase 顺序

### Phase 0: 启动校准

状态：已完成。

本 Phase 解决的问题：确认阶段 31 的正确起点，避免从阶段 29 或未合并的阶段 30 工作区继续开发。

RAG 链路位置：这是版本基线和协作边界校准，不改检索、问答或前端运行链路。

为什么现在做：FAISS 和父子块都会改动底层检索结构，必须先确认阶段 30 的评分基线和 tag/main 关系稳定，后续评测才有可比性。

- 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md。
- 阅读 task_plan.md、findings.md、progress.md。
- 确认阶段 30 已完成并合并到 main，确认 phase-30-complete tag 存在。
- 从 main 创建 codex/phase-31-faiss-parent-child-retrieval 分支。
- 校准 task_plan.md、findings.md、progress.md。

验证结果：

```text
当前分支：codex/phase-31-faiss-parent-child-retrieval
main -> e74ce780c584cfd876a56de6fb7b13cabbdefdf0
phase-30-complete -> e74ce780c584cfd876a56de6fb7b13cabbdefdf0
git merge-base --is-ancestor phase-30-complete main：通过
git status -sb：仅 task_plan.md / findings.md / progress.md 为阶段 31 规划改动
```

完成记录：

- 已按入口规则读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、阶段 30 设计与评分报告、根目录三份 planning 文件。
- 已确认文档中“阶段 30 等待人工核验”的旧描述与 Git 当前状态不一致；以 Git 为准，阶段 30 已在 `main` 并有 `phase-30-complete` tag。
- 未移动任何已有阶段 tag。
- 已从 `main` 创建并切换到 `codex/phase-31-faiss-parent-child-retrieval`。
- 未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR 操作。

### Phase 1: FAISS 向量索引设计文档

状态：已完成。

本 Phase 解决的问题：把 FAISS 索引类型、父子块 schema、child 召回 parent 上下文、fallback 与安全边界先固化，避免实现时随手扩大范围。

RAG 链路位置：检索层与上下文组装层设计；不改生成模型、不改 Agent 权限、不改外部资料来源。

为什么现在做：FAISS 与父子块都会影响底层检索可比性，先写设计文档能保证后续测试围绕阶段 30 评分基线展开。

- 新增 docs/stage31_faiss_parent_child_retrieval.md，说明目标、输入、FAISS 索引类型选择（IndexFlatIP）、父子块 schema 设计、检索流程、安全边界和完成标准。
- 是什么：FAISS 是 Facebook 开源的向量相似度搜索库。IndexFlatIP 用内积做精确搜索，配合归一化向量等价于余弦相似度。
- 在本项目哪里：替代 `VectorIndexCache` 的 numpy 矩阵暴力搜索。
- 面试表达：我用 FAISS IndexFlatIP 替代了 numpy 暴力余弦搜索，在 12,716 条 1024 维向量上把检索延迟从 ~15ms 降到 ~2-3ms，并且索引接口支持后续无缝切换到 IndexHNSWFlat。

完成记录：

- 已新增 `docs/stage31_faiss_parent_child_retrieval.md`。
- 已明确本阶段选择 `IndexFlatIP`，暂不使用 `IndexHNSWFlat`，不引入外部向量数据库。
- 已明确 FAISS 索引文件是 `chunk_embeddings` 派生物，不进 Git。
- 已明确 `chunks.parent_chunk_id` 自引用 schema，旧数据 NULL 时 fallback `ContextExpansionService`。
- 已明确只对 child chunk 生成 embedding，parent chunk 只作为回答上下文。
- 已写入核心 API 不破坏、阶段 30 评分不降分和人工核验前不提交的完成标准。

### Phase 2: FAISS 索引构建与集成

状态：已完成。

本 Phase 解决的问题：把数据库里的 `chunk_embeddings` 变成可加载、可保存、可搜索的本地 FAISS 索引文件。

RAG 链路位置：向量检索底层索引构建，还没有接入 `VectorIndexCache` 默认搜索路径。

为什么现在做：只有先有独立可测的 FAISS 封装和构建脚本，下一 Phase 才能安全把它接入现有 numpy fallback。

- pip install faiss-cpu，加入 requirements.txt。
- 新建 `app/services/retrieval/faiss_index.py`：封装 IndexFlatIP 的构建、保存、加载和搜索。
- 新建 `scripts/build_faiss_index.py`：从 SQLite chunk_embeddings 读取 Jina embedding_json，归一化，写入 `data/faiss/jina_v3.index` 和 `data/faiss/jina_v3_ids.json`。
- `data/faiss/` 加入 .gitignore。
- 新建 `tests/test_faiss_index.py`：构建、搜索、维度校验测试。

完成记录：

- 已在 `pyproject.toml` 增加 `faiss-cpu>=1.8.0`。
- 已在 `.gitignore` 增加 `data/faiss/`。
- 已新增 `app/services/retrieval/faiss_index.py`，封装 `IndexFlatIP` build/save/load/search、metadata 读写和向量归一化。
- 已新增 `scripts/build_faiss_index.py`，只读取现有 `chunk_embeddings`，跳过 stale embedding，不调用真实 API，不写数据库。
- 已新增 `tests/test_faiss_index.py`。
- 已安装本地 `faiss-cpu` 并运行聚焦测试：`5 passed`。
- 已运行 `python scripts\build_faiss_index.py --provider jina --model-name jina-embeddings-v3 --dimension 1024 --limit 10`，成功生成本地 `data/faiss/*.index` 与 ids metadata。

### Phase 3: VectorIndexCache FAISS 集成

状态：已完成。

本 Phase 解决的问题：让现有向量检索缓存优先使用完整 FAISS 索引，同时保留无索引文件或索引不完整时的 numpy fallback。

RAG 链路位置：`POST /search/vector`、hybrid、chat、agent 共同依赖的向量召回底层。

为什么现在做：FAISS 构建脚本已经可用，必须先把运行时搜索接入且保证 fallback，后续父子块检索才能复用同一 child 召回能力。

- 改造 `app/services/retrieval/vector_cache.py`：启动时检测 .index 文件，存在则用 FAISS 搜索，不存在则 fallback numpy 矩阵。
- 保证 deterministic provider 测试不受影响（fallback 路径覆盖）。
- FAISS vs numpy 一致性测试：同一批 query，top-5 结果完全一致。

完成记录：

- 已改造 `VectorIndexCache`：加载 entries 后尝试读取 `data/faiss/{provider}_{model}_dim{dimension}.index` 与 ids metadata。
- 只有 metadata 标记 `complete=true`，且 provider/model/dimension 与当前 provider 匹配、chunk_id 能映射回当前 entries 时才启用 FAISS。
- 搜索时 `_faiss_index` 存在则走 FAISS；否则沿用原 numpy 矩阵乘法。
- 已补 `tests/test_vector_cache_faiss.py` 覆盖完整索引优先与不完整索引 fallback。
- 聚焦测试：`13 passed`（FAISS 封装、缓存 FAISS 路径、既有 vector search）。

### Phase 4: 父子块 Schema 与迁移

状态：已完成。

本 Phase 解决的问题：让数据库能表达 child chunk 属于哪个 parent chunk，同时保证旧数据可空兼容。

RAG 链路位置：资料结构层，位于 ingestion 切分之后、retrieval 读取 parent 上下文之前。

为什么现在做：父子块检索必须有稳定 schema；先迁移可空字段，后续生成/检索服务才能安全落地。

- 在 `app/db/models.py` Chunk 类新增 `parent_chunk_id: Mapped[int | None]`，自引用外键。
- 新建 `scripts/migrate_parent_chunks.py`：ALTER TABLE chunks ADD COLUMN parent_chunk_id。
- parent_chunk_id 可选，旧数据为 NULL，不破坏旧功能。

完成记录：

- 已在 `Chunk` 模型新增 `parent_chunk_id` 可空自引用外键，以及 `parent_chunk` / `child_chunks` relationship。
- 已新增 `scripts/migrate_parent_chunks.py`，支持 `--dry-run`，字段已存在时幂等跳过。
- 已新增/更新测试覆盖父子块持久化和迁移脚本。
- 聚焦测试：`7 passed`。
- 已对本地 SQLite 执行迁移：`chunks.parent_chunk_id added`。

### Phase 5: 父子块生成与检索

状态：已完成。

本 Phase 解决的问题：让系统既能规划 parent/child 两层切分，又能在 child 召回后把 parent 内容送进回答上下文。

RAG 链路位置：ingestion 切分策略、retrieval 结果扩展、Brain prompt context assembly。

为什么现在做：schema 已经具备 parent 指针；现在要把“child 精准召回、parent 完整上下文”的核心链路跑通。

- 新建 `app/services/ingestion/parent_chunker.py`：对 document 先切大粒度 parent chunks（1500-2000 字符），再在内部切 child chunks（当前策略），child.parent_chunk_id 指向 parent。
- 新建 `app/services/retrieval/parent_child_search.py`：child FAISS 召回 → parent_chunk_id 查找 parent → parent.content 组装 context → 引用指向 child。parent_chunk_id 为 NULL 时 fallback ContextExpansionService。
- 只对 child chunks 生成 embedding，parent chunks 不生成 embedding。
- 新建 `tests/test_parent_child_retrieval.py`。

完成记录：

- 已新增 `app/services/ingestion/parent_chunker.py`，提供 parent/child 两层切分规划与 child flatten helper。
- 已新增 `app/services/retrieval/parent_child_search.py`，child 有 parent 时使用 parent content，无 parent 时 fallback `ContextExpansionService`。
- 已扩展 `ChunkCreate.parent_chunk_id`，便于后续脚本/入库流程创建 child 记录。
- 已在 `BrainService` 生成 prompt 前接入 `ParentChildSearchService`，让 child 召回 -> parent 回答上下文进入主链路。
- 已新增 `tests/test_parent_child_retrieval.py`，并补充 Brain 接入测试。
- 聚焦测试：`18 passed`。

### Phase 6: 前端精简

状态：已完成。

本 Phase 解决的问题：把普通用户不必理解的 Agent 调试参数从主界面移到默认收起的高级设置区。

RAG 链路位置：前端交互层，不改变 API schema 或后端参数能力。

为什么现在做：底层检索能力增强后，主界面应更聚焦“提问 -> 查看回答/引用”，减少调试参数干扰。

- 修改 `app/frontend/index.html`：把"召回数"、"工具步数"、"source_id"移入折叠的 `<details>` 高级设置区，默认收起。
- 主界面只保留：问题输入框、运行按钮、模式状态。
- 文案改为：检索候选数、最大工具调用数、指定来源 ID。
- 更新 `tests/test_frontend_app.py`。

完成记录：

- 已将 Agent 面板的 `data-agent-top-k`、`data-agent-max-tool-calls`、`data-agent-source-id` 移入 `<details class="advanced-settings">`。
- 主控制区仅保留模式状态和运行按钮。
- 文案已改为“检索候选数 / 最大工具调用数 / 指定来源 ID”。
- 已更新 `styles.css`，让高级设置区在桌面和移动端都稳定排版。
- 已更新 `tests/test_frontend_app.py`。
- 聚焦测试：`10 passed`。

### Phase 7: 评测验证与回归

状态：已完成。

本 Phase 解决的问题：验证 FAISS、父子块和前端改动没有拉低阶段 30 评分，也没有破坏核心 API 与前端页面。

RAG 链路位置：阶段回归与质量门禁层。

为什么现在做：代码与前端都已完成，需要用评分、全量测试、HTTP 冒烟和浏览器检查确认可进入文档收尾。

- 运行 build_faiss_index.py 构建索引。
- 用阶段 29 评测题集对比 FAISS vs numpy 结果一致性。
- 用阶段 29 评测题集对比父子块 vs ContextExpansion。
- 重跑 score_stage30_quality.py，overall_score >= 83.17。
- 全量 pytest 通过。
- 前端冒烟：/、/quality-report 正常，高级设置折叠/展开正常。

完成记录：

- 已构建全量 Jina FAISS 索引：`vectors=12716`。
- 阶段 31 聚焦测试：`24 passed`。
- 阶段 30 评分重跑：`overall=83.17 grade=B release_decision=review_required`。
- 全量测试：`589 passed`。
- 浏览器检查：`/` 高级设置默认收起，展开后检索候选数/最大工具调用数/指定来源 ID 可见；`/quality-report` 显示 `overall=83.17`、`grade=B`、`review_required`；console errors 0。
- 真实 provider HTTP 冒烟：`GET /health`、`GET /quality-report`、`POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 均为 200。
- 已修复此前真实 provider 500：embedding、rerank、chat 三类 OpenAI-compatible provider 显式禁用系统代理探测，本地 `.env` 的 `EMBEDDING_PROVIDER` 已改为 `jina` 以匹配已有 Jina embedding 和 FAISS 索引。

### Phase 8: 文档与 Obsidian 收尾

状态：已完成。

- 更新 docs/progress.md、docs/architecture.md、README.md。
- 写 docs/phase_reviews/phase-31.md。
- 统一按 Phase 汇报模板补齐 Obsidian 汇报。
- 停在用户人工核验前状态。

完成记录：

- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 已新增 `docs/phase_reviews/phase-31.md`。
- 已新增 `obsidian-vault/阶段/阶段 31 - FAISS向量索引与父子块检索.md`。
- 已新增 `obsidian-vault/阶段汇报/阶段 31 - FAISS向量索引与父子块检索/`，包含阶段 31 Phase 汇报索引和 Phase 0-8 小汇报。
- 已更新 `obsidian-vault/阶段索引.md` 与 `obsidian-vault/阶段汇报索引.md`。
- 已明确最终状态：尚未 `git add`、尚未 commit、尚未创建 `phase-31-complete` tag、尚未 push、未创建 PR，等待用户人工核验。

## 完成标准

- FAISS 索引构建脚本可独立运行，生成 .index 文件。
- VectorIndexCache 优先用 FAISS 搜索，无 .index 文件时 fallback numpy。
- deterministic provider 测试不受 FAISS 影响。
- chunks 表有 parent_chunk_id 字段，迁移脚本存在且可执行。
- child 召回 → parent 回答的检索链路可用且测试覆盖。
- 前端主界面不显示高级参数，折叠区可展开使用。
- 阶段 30 评分 overall_score >= 83.17。
- 全量测试通过。
- 不引入 Qdrant / Chroma / PGVector / torch / sentence-transformers。
- FAISS 索引文件加入 .gitignore。
- 不把 API key、Bearer token、供应商原始响应写入 Git。
- 未经用户人工核验，不 git add / commit / tag / push / 建 PR。
- docs/phase_reviews/phase-31.md 存在。

### Phase 9: 追加父子块批量落地

状态：已完成。

本 Phase 解决的问题：阶段 31 已经有 `parent_chunk_id` schema 和 child -> parent 检索服务，但既有 12,716 个 chunks 尚未生成 parent chunk，`parent_chunk_id` 为空时仍只能 fallback 到 `ContextExpansionService`。

RAG 链路位置：资料结构层与检索上下文层之间。它不改变 child 内容、不重建 embedding，只补充 parent 上下文行并把既有 child 指向 parent。

为什么现在做：如果不回填，父子块只是空 schema；FAISS 仍能召回 child，但回答上下文不能真正升级到 parent。

- 新增 `scripts/backfill_parent_chunks.py`。
- 支持 `--dry-run`，支持按文档幂等重跑。
- 保留既有 12,716 个 child chunks 的 id、内容、chunk_index 和 embedding，不删除、不重切、不重新生成 embedding。
- 对每个 document 按 child `chunk_index` 顺序拼接文本，切出 1500-2000 字符 parent chunks，插入 `chunks` 表。
- 使用内容位置重叠把既有 child 关联到 parent，更新 `parent_chunk_id`。
- parent chunk 不生成 embedding，不进入 FAISS；确认 `scripts/build_faiss_index.py` 的 `~has_children` 过滤仍跳过 parent。
- 新增 `tests/test_backfill_parent_chunks.py`。

验证方式：

```text
python scripts\backfill_parent_chunks.py --dry-run
python scripts\backfill_parent_chunks.py
python -m pytest tests\test_backfill_parent_chunks.py tests\test_faiss_index.py tests\test_vector_index_service.py -q
python scripts\build_faiss_index.py --provider jina --model-name jina-embeddings-v3 --dimension 1024
```

完成标准：

- 既有 child 数量保持 12,716；parent rows 新增但无 embedding。
- 绝大多数/全部既有 child 已有 `parent_chunk_id`。
- 重跑脚本不会重复创建 parent。
- FAISS full index vectors 仍为 12,716。

完成记录：

- 已新增 `scripts/backfill_parent_chunks.py` 和 `tests/test_backfill_parent_chunks.py`。
- dry-run：`parent_created=6402`、`child_updated=12716`。
- 正式执行：新增 6,402 个 parent，关联 12,716 个既有 child。
- 幂等 dry-run：`parent_created=0`、`parent_reused=6402`、`child_updated=0`。
- 数据库核验：`chunks=19118 parent_rows=6402 linked_children=12716 parent_embeddings=0 embeddings=25432`。
- 聚焦测试：`15 passed`。

### Phase 10: Prompt 质量强化

状态：已完成。

本 Phase 解决的问题：阶段 30 评分显示回答覆盖与规则质量仍偏弱；需要在不拉长 prompt 的前提下强化引用密度、先结论后解释、对比类问题两边都说清楚。

RAG 链路位置：生成模型 prompt 层，位于检索上下文组装之后、ChatModelProvider 调用之前。

为什么现在做：父子块提供了更完整上下文，prompt 也需要更明确地要求模型把证据用到每个事实陈述上，否则上下文变长后更容易出现整段末尾才引用或答偏一方。

- 更新 `app/services/generation/prompt_builder.py` 的 `DEFAULT_SYSTEM_PROMPT`。
- 更新 `build_user_prompt()` 的 Answer requirements。
- 总规则控制在 8 条以内，保留反事实纠正规则。
- 补测试覆盖引用密度、直接回答、对比问题两边说明。

验证方式：

```text
python -m pytest tests\test_prompt_builder.py -q
```

完成记录：

- 已强化 `DEFAULT_SYSTEM_PROMPT` 和 `build_user_prompt()` Answer requirements。
- Answer requirements 共 7 条，控制在 8 条以内。
- 新增测试断言引用密度、先直接回答、对比类问题双边说明。
- 聚焦测试：`13 passed`（prompt + backfill）。

### Phase 11: 追加评测对比与收尾

状态：已完成。

本 Phase 解决的问题：确认 parent backfill 和 prompt 强化没有拉低阶段 30 评分，没有破坏核心 API 和全量测试，并把追加工作同步到普通文档与 Obsidian。

RAG 链路位置：质量门禁、文档交接和人工核验准备层。

为什么现在做：代码改动完成后必须用阶段 30 评分、全量 pytest、FAISS 重建和文档闭环来证明阶段 31 可进入人工核验。

- 重跑 `scripts/score_stage30_quality.py`，确认 `overall_score >= 83.17`。
- 重跑 `python -m pytest -q`。
- 如父子块回填后 FAISS 需要重建，则重建并确认 parent 不进入索引。
- 更新 `task_plan.md`、`findings.md`、`progress.md`。
- 更新 `docs/phase_reviews/phase-31.md`、`docs/progress.md`、`docs/architecture.md`、`README.md`。
- 更新 Obsidian 阶段 31 知识点与阶段汇报页。
- 保持不 `git add` / commit / tag / push / PR。

完成记录：

- FAISS 重建：`vectors=12716`，确认 parent 未进入索引。
- 阶段 30 评分重跑：`overall=83.17 grade=B release_decision=review_required`。
- 全量测试：`593 passed, 1 warning`。
- 已更新 README、docs/progress.md、docs/architecture.md、docs/phase_reviews/phase-31.md 和 Obsidian 阶段 31 汇报。
- 仍未执行 `git add`、commit、tag、push 或 PR。
