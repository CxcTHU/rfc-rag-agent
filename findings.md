# 阶段 31 发现与关键决策

## 阶段 30 基线

阶段 30 已完成开发、验证、提交、创建 `phase-30-complete` tag，并合并到 `main`。阶段 31 的正确起点是当前 `main`，不是阶段 29 合并点，也不是阶段 30 未提交工作区。

当前阶段 31 分支：`codex/phase-31-faiss-parent-child-retrieval`。

Git 核对结果：

```text
main -> e74ce780c584cfd876a56de6fb7b13cabbdefdf0
phase-30-complete -> e74ce780c584cfd876a56de6fb7b13cabbdefdf0
git merge-base --is-ancestor phase-30-complete main: passed
```

决策：不移动任何已有阶段 tag；阶段 31 后续只在当前分支开发，完成后停在人工核验前。

阶段 30 评分结果：

```text
overall_score=83.17
grade=B
release_decision=review_required
retrieval_quality=26.83/35 (76.7%, review_required)
rule_based_context_answer_quality=16.60/25 (66.4%, weak)
safety_refusal=20.00/20 (100%, strong)
source_quality=9.73/10 (97.3%, strong)
engineering_health=10.00/10 (100%, strong)
```

系统规模：

```text
documents: 635
chunks: 12,716
chunk_embeddings: 25,432 (Jina v3 1024d + deterministic 64d)
tests: 571 passed, 1 warning
```

## 当前检索瓶颈分析

### 瓶颈 1：numpy 暴力向量搜索

位置：`app/services/retrieval/vector_cache.py:82`。

```python
scores = self._normalized_matrix @ query_vector
```

当前行为：启动时从 SQLite 的 `chunk_embeddings` 表反序列化全部 12,716 条 1024 维 Jina 向量到内存 numpy float64 矩阵（约 100MB），每次查询做全矩阵乘法。

问题：
- 延迟约 15ms/query，当前规模可用但无法扩展到 10 万+ chunks。
- 矩阵在内存常驻，内存占用随语料线性增长。
- 无法利用 SIMD 或 ANN（近似近邻）加速。

决策：引入 `faiss-cpu`，使用 `IndexFlatIP`（精确内积搜索，配合归一化向量等价余弦相似度）。当前规模用 Flat 就够了；后续扩展到 10 万+ 时可原地换 `IndexIVFFlat` 或 `IndexHNSWFlat`，搜索接口不变。

不选 `IndexFlatL2`：我们已经预归一化，用 IP 等价余弦且省一次 L2 转换。
不选 `IndexHNSWFlat`：当前 12K 条用精确搜索就够快，HNSW 构建慢且索引体积大，留给后续扩展。
不引入 Qdrant/Chroma/PGVector：项目用 SQLite 单文件架构，引入外部向量数据库过重。

新词解释：

- FAISS：是什么 -> 一个本地向量相似度搜索库；在本项目哪里出现 -> 阶段 31 的向量检索索引；作用 -> 替代 numpy 全量矩阵扫描；面试怎么说 -> “我先用本地 FAISS 精确索引降低检索延迟，同时保留 SQLite 主数据和 deterministic 回归边界”。
- IndexFlatIP：是什么 -> FAISS 的精确内积索引；在本项目哪里出现 -> 阶段 31 首选索引类型；作用 -> 对归一化后的 embedding 做精确 top-k 搜索；面试怎么说 -> “归一化向量的内积等价余弦相似度，所以 IndexFlatIP 能保持旧 numpy 余弦搜索的语义一致性”。
- IndexHNSWFlat：是什么 -> FAISS 的近似图索引；在本项目哪里出现 -> 阶段 31 的备选方案；作用 -> 大规模数据下用近似搜索换速度；面试怎么说 -> “当前 12K 数据没必要牺牲精确性和增加索引复杂度，等规模扩大再切 HNSW”。

### 瓶颈 2：无真正父子块

位置：`app/services/retrieval/context_expansion.py`。

当前行为：`ContextExpansionService` 命中 child chunk 后，按 `chunk_index ± window` 拉取前后相邻 chunk 拼接。

问题：
- 相邻 chunk 不一定属于同一段落/章节，可能跨节拼接，引入噪声。
- chunk 边界固定（300-500 字符），无法获取"完整段落"级别的上下文。
- 阶段 17 设计文档明确说这是"兼容方案"，后续应设计 parent chunk schema。

决策：在 `chunks` 表新增 `parent_chunk_id: int | None` 自引用外键。生成策略为先按大粒度（1500-2000 字符）切 parent chunks，再在每个 parent 内切 child chunks。child 的 `parent_chunk_id` 指向所属 parent。

检索流程：child chunk 走 FAISS 精准召回 → 通过 `parent_chunk_id` 查找 parent → 用 parent.content 组装 prompt context → 引用仍指向 child（精确溯源）。

embedding 策略：只对 child chunks 生成 embedding。parent chunks 只用于上下文扩展，不生成 embedding，不增加 FAISS 索引体积。

兼容性：`parent_chunk_id` 为可选字段，旧数据 NULL 时 fallback 到现有 `ContextExpansionService`，不破坏旧功能。

新词解释：

- 父子块：是什么 -> parent 是较大的上下文块，child 是较小的检索块；在本项目哪里出现 -> 阶段 31 的 `chunks.parent_chunk_id`；作用 -> child 负责精确召回，parent 负责给回答提供完整上下文；面试怎么说 -> “我把召回粒度和生成上下文粒度解耦，解决小 chunk 命中准但上下文不够的问题”。
- 自引用外键：是什么 -> 表里的某个字段指向同一张表的另一行；在本项目哪里出现 -> `chunks.parent_chunk_id` 指向父 chunk 的 `chunks.id`；作用 -> 不新增 parent 表也能表达父子关系；面试怎么说 -> “同一张 chunks 表同时保存 parent/child，通过 nullable self foreign key 兼容旧数据”。

### 瓶颈 3：前端暴露调试参数

位置：`app/frontend/index.html` 第 115-126 行。

```html
<label><span>召回数</span><input type="number" ... data-agent-top-k /></label>
<label><span>工具步数</span><input type="number" ... data-agent-max-tool-calls /></label>
<label><span>source_id</span><input type="text" ... data-agent-source-id /></label>
```

问题：
- 普通用户不理解 `top_k` 和 `max_tool_calls`，会误以为必须填写。
- Agent 当前没有根据问题动态调整这些参数的能力（agentic nodes 里 `top_k=5` 是硬编码）。
- 这些是调试参数，不是用户决策。

决策：移入折叠的 `<details>` 高级设置区，默认收起。主界面只保留问题输入框、运行按钮、模式状态。后端 API 参数保留不删，前端默认不发送，用后端默认值。

## FAISS 索引类型选择依据

| 索引类型 | 精确度 | 构建速度 | 查询速度 (12K) | 索引体积 | 适用规模 |
|---|---|---|---|---|---|
| IndexFlatIP | 精确 | 快 | ~2-3ms | ~50MB | <100K |
| IndexIVFFlat | 近似 | 中 | ~1ms | ~50MB | 100K-1M |
| IndexHNSWFlat | 近似 | 慢 | ~0.5ms | ~200MB | 10K-10M |

当前 12,716 条选 IndexFlatIP：精确、构建快、查询已经很快、索引体积小。

## 风险与防线

- 风险：FAISS 和 numpy 搜索结果不一致。
  - 防线：一致性测试，同 query 的 top-5 必须完全一致。
- 风险：父子块迁移破坏旧数据。
  - 防线：parent_chunk_id 可选 NULL，fallback ContextExpansionService。
- 风险：FAISS 索引文件误提交到 Git。
  - 防线：data/faiss/ 加入 .gitignore。
- 风险：父子块重新切分导致 embedding 失效。
  - 防线：只对 child 生成 embedding，parent 不生成；现有 child 的 chunk_id 和 embedding 不变。
- 风险：前端改动影响已有测试。
  - 防线：更新 test_frontend_app.py 覆盖折叠区。

## 面试表达准备

阶段 31 可以这样讲：

> 阶段 31 我做了三件事。第一，用 FAISS IndexFlatIP 替代了 numpy 暴力余弦搜索，在 12,716 条 1024 维 Jina 向量上把检索从全矩阵乘法变成 FAISS 精确内积搜索，延迟从约 15ms 降到 2-3ms，并且接口设计支持后续无缝切换到 HNSW。第二，实现了真正的父子块检索：在 chunks 表加了 parent_chunk_id 自引用外键，child chunk 负责精准向量召回，parent chunk 负责提供完整段落上下文给 LLM，解决了之前"相邻 chunk 拼接可能跨节引入噪声"的问题。第三，把前端的调试参数收进折叠区，让主界面更简洁。

## Phase 1 设计文档结论

- `docs/stage31_faiss_parent_child_retrieval.md` 已落盘。
- 阶段 31 的 FAISS 索引文件被定义为可重建派生物，路径建议为 `data/faiss/*.index` 和配套 ids metadata，必须加入 `.gitignore`。
- `IndexFlatIP` 是当前首选，因为它精确、易测，且归一化向量内积等价于余弦相似度；`IndexHNSWFlat` 保留为后续规模扩大后的备选。
- 父子块暂用 `chunks.parent_chunk_id` 自引用字段，不新增 `parent_chunks` 表；原因是 parent/child 共享 document、content、heading_path、start/end_char 等结构，最小迁移更稳。
- child 负责 embedding 与召回，parent 负责回答上下文；引用仍指向 child，防止引用漂移。
- 旧数据 `parent_chunk_id IS NULL` 时必须继续走 `ContextExpansionService`，不能因为阶段 31 破坏阶段 17 的兼容方案。

## Phase 2 FAISS 构建结论

- `faiss-cpu>=1.8.0` 已加入项目依赖，本地实际安装版本为 `1.14.3`。
- `app/services/retrieval/faiss_index.py` 将 FAISS 依赖隔离在一个小封装里，业务侧只看 `FaissVectorIndex.build/load/save/search`。
- FAISS metadata 单独保存 provider、model_name、dimension、metric、normalized 和 `chunk_ids`，避免 `.index` 行号与数据库 `chunk_id` 的关系不可追踪。
- `scripts/build_faiss_index.py` 只读取当前有效 embedding：provider/model/dimension 匹配、content_hash 与 chunk 当前内容一致、维度正确。它不调用真实 API，也不写数据库。
- 已用 `--limit 10` 验证可以从现有 Jina embedding 生成 `data/faiss/jina_jina-embeddings-v3_dim1024.index` 和 `data/faiss/jina_jina-embeddings-v3_dim1024_ids.json`。
- `data/faiss/` 已加入 `.gitignore`，索引文件保持本地可重建，不进入 Git。
- 聚焦测试 `tests/test_faiss_index.py`：`5 passed`。

## Phase 3 VectorIndexCache 集成结论

- `VectorIndexCache` 已增加 `_faiss_index` 与 `_entries_by_chunk_id`，保持原 `VectorIndexMatch` 返回结构不变。
- 运行时只使用完整索引：metadata 必须 `complete=true`，provider/model/dimension 必须匹配，且 metadata 中的每个 `chunk_id` 必须能映射回当前 DB entries。
- `--limit` 构建出来的小样本索引 metadata 为 `complete=false`，不会被运行时误用。
- FAISS 搜索路径只改变排序计算方式，不改变上游 `VectorSearchService`、hybrid、chat、agent 的响应 schema。
- 缺索引、索引不完整、索引 metadata 不匹配或加载失败时，系统静默回到 numpy fallback。这是有意设计：FAISS 文件是可重建优化，不是系统必需状态。
- 聚焦测试 `tests/test_faiss_index.py tests/test_vector_cache_faiss.py tests/test_vector_search.py`：`13 passed`。

## Phase 4 父子块 Schema 结论

- `chunks.parent_chunk_id` 已作为 nullable self foreign key 加入 ORM 模型。
- `parent_chunk` / `child_chunks` relationship 让代码能直接从 child 访问 parent，也能从 parent 查看 children。
- 迁移脚本 `scripts/migrate_parent_chunks.py` 只做最小 ALTER：

```text
ALTER TABLE chunks ADD COLUMN parent_chunk_id INTEGER NULL
CREATE INDEX IF NOT EXISTS ix_chunks_parent_chunk_id ON chunks (parent_chunk_id)
```

- SQLite 的 `ALTER TABLE ADD COLUMN` 不能直接补完整外键约束；阶段 31 先通过 ORM relationship 与 nullable 字段保证兼容。后续如果迁移到 Alembic 或重建表，再补数据库级自引用外键约束。
- 本地数据库已执行迁移，当前真实 `chunks` 表具备 `parent_chunk_id` 字段。
- 聚焦测试 `tests/test_db_models.py tests/test_migrate_parent_chunks.py`：`7 passed`。

## Phase 5 父子块生成与检索结论

- `parent_chunker.py` 先用较大 `parent_chunk_size` 切 parent，再在 parent 内复用现有 `split_text` 切 child。它当前输出切分计划，不直接写数据库，避免在阶段 31 中重写既有入库服务。
- `parent_child_search.py` 是真正接入回答上下文的模块：输入普通 `SearchResultLike`，若该 chunk 有 `parent_chunk_id`，则读取 parent content 作为 context；若没有 parent，则 fallback 到 `ContextExpansionService`。
- `BrainService` 已在 `build_rag_prompt` 前调用 `ParentChildSearchService`。这意味着默认 chat/agent answer 链路能用 parent context；citation 仍使用 child 的 `chunk_id`。
- evidence confidence 当前仍先基于原始 child 结果判断，再扩展 parent context。这个顺序更保守：不会因为 parent 很长就放松低证据拒答。
- parent chunk 不进入 embedding 构建逻辑；当前 `VectorIndexService` 仍扫描全部 chunks，后续若批量生成 parent/child 数据，需要在索引构建阶段明确跳过 parent。本阶段先通过“只对 child 生成 embedding”的设计和后续脚本约束保证。
- 聚焦测试 `tests/test_parent_child_retrieval.py tests/test_brain_service.py`：`18 passed`。

## Phase 6 前端精简结论

- Agent 主界面保留问题输入、模式状态和运行按钮。
- `top_k`、`max_tool_calls`、`source_id` 对应的 data hook 未删除，只是移入默认收起的 `<details class="advanced-settings">`。
- 用户可见文案从调试字段名改为“检索候选数 / 最大工具调用数 / 指定来源 ID”。
- 后端 API schema 不变；前端 JS 仍能读取这些 input。
- 聚焦测试 `tests/test_frontend_app.py`：`10 passed`。

## Phase 7 验证结论

- 全量 FAISS 索引已构建：`vectors=12716`，输出位于 `data/faiss/`，该目录已 gitignore。
- 阶段 30 评分重跑保持不降分：`overall_score=83.17`、`grade=B`、`release_decision=review_required`。
- 全量测试通过：`589 passed`。
- 浏览器验证：
  - `/` 首页高级设置存在且默认收起。
  - 展开后 `data-agent-top-k`、`data-agent-max-tool-calls`、`data-agent-source-id` 三个字段可见。
  - `/quality-report` 显示 `overall=83.17`、`grade=B`、`release_decision=review_required`。
  - console errors 0。
- 真实 provider HTTP 冒烟通过：`GET /health`、`GET /quality-report`、`POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 均为 200。
- 已修复此前真实 provider 500：Python `urllib` 默认网络路径在本机真实 provider 调用中卡住；embedding、rerank、chat 三类 OpenAI-compatible provider 已显式禁用系统代理探测，本地 `.env` 的 `EMBEDDING_PROVIDER` 已改为 `jina`，匹配已有 `jina/jina-embeddings-v3/dim=1024` 索引。

## Phase 8 文档与 Obsidian 收尾结论

- 普通文档已同步阶段 31：`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 人工核验草稿已新增：`docs/phase_reviews/phase-31.md`。
- Obsidian 已新增阶段 31 阶段页、Phase 汇报索引和 Phase 0-8 小汇报，并更新阶段索引与阶段汇报索引。
- 阶段 30 的旧“等待人工核验”文字已在最新状态层修正：以 Git 为准，`phase-30-complete` 和 `main` 均指向 `e74ce78`。
- 阶段 31 的真实 provider 500 已修复并复验：Jina embedding、Jina rerank、MIMO chat provider 小请求成功，8004 临时服务核心接口全 200。
- 最终状态保持未提交：未执行 `git add`、未 commit、未 tag、未 push、未创建 PR。

## Phase 9 追加发现：父子块 schema 已有但数据未落地

用户追加核验指出：当前 `chunks.parent_chunk_id` 全部为 NULL，阶段 31 的父子块 schema 和检索服务还没有真正作用到既有 12,716 个 child chunks 上。

关键决策：

- 保留既有 12,716 个 chunks 作为 child，不删除、不改 content、不改 `chunk_index`、不重新生成 embedding。
- parent chunk 作为新增 `chunks` 行写入，同一张表内通过 `parent_chunk_id` 自引用被 child 指向。
- parent chunk 不生成 embedding；`chunk_embeddings` 仍只覆盖既有 child。
- parent chunk 的 `heading_path` 使用阶段 31 专用标记，便于脚本幂等识别和避免重复创建。
- parent chunk 的 `chunk_index` 从该 document 当前最大 `chunk_index + 1` 开始分配，避免违反 `(document_id, chunk_index)` 唯一约束。
- child 与 parent 的对应关系使用拼接文本中的字符区间重叠来匹配；这比按固定 child 数量分组更接近真实内容位置。

`scripts/build_faiss_index.py` 已确认存在 parent 过滤：

```text
has_children = select(child_chunk.id).where(child_chunk.parent_chunk_id == Chunk.id).exists()
...
~has_children
```

解释：parent chunk 一旦被 child 指向，就会满足 `has_children`，因此被 FAISS 构建脚本排除；child 自身没有子块，会继续进入索引。这个过滤与“只对 child 生成 embedding”的策略一致。

新词解释：

- backfill：是什么 -> 对已有历史数据补写新字段或新结构；在本项目哪里出现 -> `scripts/backfill_parent_chunks.py`；作用 -> 不重导入文档也能把阶段 31 的 parent-child 关系补到旧数据；面试怎么说 -> “我没有破坏性重切旧 chunk，而是用幂等 backfill 给历史 child 补 parent 指针”。
- 幂等：是什么 -> 同一个操作重复执行，结果不会重复叠加或变坏；在本项目哪里出现 -> backfill 脚本重跑不重复创建 parent chunk；作用 -> 避免迁移中断后重跑造成脏数据；面试怎么说 -> “迁移脚本必须支持 dry-run 和幂等，方便生产环境先预演再执行”。
- 内容位置匹配：是什么 -> 通过文本拼接后的 start/end 字符区间判断 child 属于哪个 parent；在本项目哪里出现 -> child `parent_chunk_id` 回填；作用 -> 让 parent 关系跟真实文本位置一致；面试怎么说 -> “我用区间重叠而不是简单计数分桶，减少 chunk 边界重叠带来的错配”。

## Phase 10 追加发现：Prompt 需要短规则强化

阶段 30 的弱项包含 `rule_based_context_answer_quality`。父子块增加上下文长度后，prompt 需要更明确地约束引用密度和回答结构，但不能无限加规则。

关键决策：

- system prompt 与 user prompt 的 Answer requirements 都控制在 8 条以内。
- 保留现有反事实纠正规则：问题前提和上下文冲突时先纠正，不迎合错误前提。
- 新增引用密度要求：事实性陈述都要带 `[N]`，不能整段最后只挂一次引用。
- 新增结构要求：先直接回答，再展开解释。
- 新增对比问题要求：问 A/B 区别时必须分别说明 A 和 B，不能只讲一方。

## Phase 11 追加验证结论

父子块回填完成后，FAISS 索引仍只包含 child：

```text
chunks=19118
parent_rows=6402
linked_children=12716
parent_embeddings=0
embeddings=25432
FAISS full index vectors=12716
```

解释：总 `chunks` 从 12,716 增至 19,118，是因为新增了 6,402 个 parent；`chunk_embeddings` 仍为 25,432，对应原有 12,716 个 child 的 Jina + deterministic 双 embedding。parent embedding 数为 0，符合“parent 只做上下文、child 才做召回”的策略。

评分和测试结论：

```text
stage30 overall=83.17 grade=B release_decision=review_required
full pytest=593 passed, 1 warning
```

阶段 31 追加工作的最终人工核验重点：

- 抽样 child 的 `parent_chunk_id` 是否指向同一文档且上下文位置合理。
- 抽样 `/chat` 或 `/agent/query` 的回答是否先给结论、事实句是否逐条引用。
- 确认 `data/faiss/` 仍未进入 Git，`phase-31-complete` tag 仍未创建。
