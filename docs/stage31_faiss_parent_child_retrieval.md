# 阶段 31 设计：FAISS 向量索引与父子块检索

## 目标

阶段 31 在阶段 30 质量评分基线之上，处理两个底层检索问题和一个前端体验问题：

```text
当前 VectorIndexCache numpy 暴力搜索
-> FAISS IndexFlatIP 本地向量索引
-> VectorIndexCache 优先 FAISS / fallback numpy
-> chunks.parent_chunk_id 自引用字段
-> child chunk 精准召回
-> parent chunk 回答上下文
-> 前端高级参数收入折叠区
-> 阶段 30 评分重跑验证不降分
```

本阶段不新增外部资料来源，不新增爬虫，不做写入型 Agent 工具，不做登录系统，不做部署优化，不引入 Qdrant、Chroma、PGVector、torch 或 sentence-transformers。

## 新词解释

- FAISS：一个本地向量相似度搜索库。本项目用它读取已存在的 `chunk_embeddings`，生成可重建的 `.index` 文件，加速 `POST /search/vector` 和上游 hybrid / chat / agent 链路。
- IndexFlatIP：FAISS 的精确内积索引。因为本项目会先把 embedding 归一化，内积就等价于余弦相似度，所以它可以保持阶段 26 numpy 余弦搜索的排序语义。
- parent chunk：较大的上下文块，用来给回答提供完整段落或章节片段。
- child chunk：较小的检索块，用来做 embedding 和精准召回。
- 自引用外键：同一张表里某个字段指向本表另一行。本项目计划让 `chunks.parent_chunk_id` 指向同表的 parent chunk。

## 阶段 30 基线

阶段 30 已完成并进入 `main`：

```text
main -> e74ce780c584cfd876a56de6fb7b13cabbdefdf0
phase-30-complete -> e74ce780c584cfd876a56de6fb7b13cabbdefdf0
overall_score=83.17
grade=B
release_decision=review_required
full tests=571 passed, 1 warning
```

阶段 31 的质量约束是：重跑阶段 30 评分后 `overall_score >= 83.17`，且不破坏这些外部接口：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
GET /quality-report
```

## 当前问题

### 1. numpy 暴力搜索瓶颈

`app/services/retrieval/vector_cache.py` 当前把同一 provider/model/dimension 的 embedding 加载成 numpy 归一化矩阵，并在每次查询时执行：

```python
scores = self._normalized_matrix @ query_vector
```

这条链路对当前 12,716 条 chunk 可用，但本质仍是全量扫描。语料继续增长到 10 万级 chunk 后，内存占用和查询延迟都会线性增长。

### 2. ContextExpansionService 只是相邻 chunk 拼接

`ContextExpansionService` 当前按同一个 `document_id` 下的 `chunk_index ± window` 拼接上下文。它是阶段 17 的兼容方案，优点是无需迁移 schema；缺点是相邻 chunk 不一定等于同一个完整段落或章节，可能跨边界引入噪声，也可能没有覆盖回答需要的完整背景。

### 3. 前端主界面暴露高级参数

原生前端 Agent 面板直接展示 `top_k`、`max_tool_calls` 和 `source_id`。这些参数对调试有用，但对普通用户不是主流程，容易误导用户以为必须理解或填写这些配置。

## FAISS 索引类型选择

本阶段选择 `IndexFlatIP`，暂不选择 `IndexHNSWFlat`。

| 方案 | 特点 | 本阶段结论 |
| --- | --- | --- |
| IndexFlatIP | 精确搜索；构建简单；内积搜索；配合归一化向量等价余弦相似度 | 采用 |
| IndexFlatL2 | 精确 L2 距离搜索；需要把余弦相似度转换成 L2 语义 | 不采用 |
| IndexHNSWFlat | 近似图搜索；大规模时更快；构建和参数更复杂 | 暂不采用 |
| Qdrant / Chroma / PGVector | 外部向量数据库或数据库扩展 | 不引入 |

取舍理由：

- 当前规模约 12K 条 Jina embedding，精确搜索足够快，不需要近似索引牺牲可解释性。
- 阶段 26 的旧逻辑是精确 numpy 余弦搜索，`IndexFlatIP` 最容易做一致性测试。
- FAISS 被封装在本地服务层，后续如果扩展到 10 万+ chunks，可以在不改 API 的情况下切换到 `IndexHNSWFlat` 或 IVF 类索引。

## FAISS 文件设计

FAISS 索引是由 `chunk_embeddings` 派生出的可重建文件，不是新的资料来源，不提交到 Git。

建议路径：

```text
data/faiss/
  jina_jina-embeddings-v3_dim1024.index
  jina_jina-embeddings-v3_dim1024_ids.json
```

`.index` 保存 FAISS 向量索引；`ids.json` 保存 FAISS 行号到 `chunk_id` 的映射和元数据校验信息：

```json
{
  "provider": "jina",
  "model_name": "jina-embeddings-v3",
  "dimension": 1024,
  "metric": "inner_product",
  "normalized": true,
  "chunk_ids": [1, 2, 3]
}
```

构建脚本：

```text
scripts/build_faiss_index.py
```

构建脚本只读取现有 SQLite 数据和 `chunk_embeddings`，不调用真实 embedding API，不重建 embedding，不写数据库。

## VectorIndexCache 集成策略

`VectorIndexCache` 保留原有 numpy fallback。阶段 31 的集成策略是：

```text
search(query_embedding, top_k)
-> 校验维度
-> 尝试加载匹配 provider/model/dimension 的 FAISS index
   -> 存在且 ids metadata 匹配：FAISS search
   -> 不存在或加载失败：numpy fallback
-> 返回 VectorIndexMatch
```

关键边界：

- deterministic provider 默认仍可走 numpy fallback，保证 CI 和本地全量测试不依赖 FAISS 索引文件。
- FAISS 搜索结果需要映射回现有 `VectorIndexEntry`，避免破坏 `VectorSearchService` 和上游 schema。
- 一致性测试必须覆盖：同一批 query 下 FAISS 与 numpy top-5 的 `chunk_id` 顺序一致。

## 父子块 Schema 设计

本阶段在 `chunks` 表新增可选字段：

```text
parent_chunk_id INTEGER NULL REFERENCES chunks(id) ON DELETE SET NULL
```

语义：

- parent chunk：`parent_chunk_id IS NULL`，较大粒度，只用于回答上下文。
- child chunk：`parent_chunk_id = parent.id`，较小粒度，用于 embedding 和召回。
- 旧数据：`parent_chunk_id IS NULL`，保持兼容。

为什么不新增 `parent_chunks` 表：

- 当前 `chunks` 已经承载 document、content、heading_path、start/end_char 等字段，parent 和 child 共享这些结构。
- 自引用字段迁移最小，旧 API 和 repository 读取路径更容易兼容。
- 后续如果需要区分 chunk role，可再评估新增 `chunk_type`，但阶段 31 先不扩大 schema。

## 父子块生成策略

推荐流程：

```text
document text
-> 大粒度 parent split，约 1500-2000 字符
-> 每个 parent 内复用当前 child split 策略
-> 写入 parent chunk
-> 写入 child chunks，并设置 parent_chunk_id
-> 只对 child chunks 构建 embedding
```

embedding 策略：

- 只对 child 生成 embedding。
- parent 不生成 embedding，不进入 FAISS 索引。
- 原因是 parent 过长会降低向量召回精度，也会增加索引体积；parent 的职责是补上下文，不是做精准匹配。

## 检索流程

父子块检索链路：

```text
用户问题
-> query embedding
-> FAISS child top-k 召回
-> 对每个 child:
   -> 如果 parent_chunk_id 存在：读取 parent.content 作为回答上下文
   -> 如果 parent_chunk_id 为空：fallback ContextExpansionService
-> 引用仍指向 child chunk_id
-> Brain / Chat / Agent 继续做 evidence confidence、拒答和引用检查
```

引用策略：

- 回答上下文可以来自 parent。
- citation 仍指向 child，因为 child 是实际被召回的证据锚点。
- 这样既提升上下文完整度，又避免引用漂移到过大的 parent。

## 前端精简

主界面保留：

```text
问题输入框
运行按钮
模式状态 / 引用 / workflow 展示
```

高级设置折叠区默认收起，包含：

```text
检索候选数
最大工具调用数
指定来源 ID
```

后端请求 schema 不删除这些字段；前端只是降低视觉优先级。

## 安全边界

- 不提交 `data/faiss/*.index` 或 `data/faiss/*_ids.json`。
- 不把 API key、Bearer token、Authorization header、供应商原始响应、raw_response 或受限全文写入 Git、CSV、文档、测试或 Obsidian。
- FAISS 构建不调用真实 API。
- 父子块迁移脚本必须可重复运行或能安全检测字段已存在。
- 旧 `parent_chunk_id IS NULL` 数据必须可正常检索。
- 真实 API 不能成为 CI 或本地全量测试前提。

## 验证计划

聚焦验证：

```text
tests/test_faiss_index.py
tests/test_parent_child_retrieval.py
tests/test_frontend_app.py
```

回归验证：

```text
python scripts/build_faiss_index.py --provider jina
python scripts/score_stage30_quality.py
python -m pytest -q
```

必须确认：

- FAISS index 可独立构建。
- 无 `.index` 文件时 numpy fallback 可用。
- deterministic provider 测试不受 FAISS 文件影响。
- `parent_chunk_id` 为 NULL 时 fallback 到 `ContextExpansionService`。
- 阶段 30 `overall_score >= 83.17`。
- 六个核心 API 不被破坏。

## 完成标准

- `docs/stage31_faiss_parent_child_retrieval.md` 存在并说明设计边界。
- FAISS 索引构建脚本可独立运行并生成 `.index` 文件。
- `data/faiss/` 已加入 `.gitignore`。
- `VectorIndexCache` 优先用 FAISS，无索引文件时 fallback numpy。
- `chunks` 表有 `parent_chunk_id` 字段，迁移脚本存在且可执行。
- 父子块生成可对现有语料执行；child 正确关联 parent。
- child 召回 -> parent 回答上下文链路可用。
- 前端高级参数默认收起。
- 阶段 30 评分不降分，全量测试通过。
- 最终停在用户人工核验前，不提交、不打 `phase-31-complete` tag、不推送、不创建 PR。

## 面试表达

阶段 31 我先做检索底层升级，而不是继续堆 Agent 功能。向量检索上，我用 FAISS `IndexFlatIP` 替代 numpy 暴力矩阵扫描，因为归一化后的内积等价于余弦相似度，可以保持旧排序语义，又能把索引能力封装出来，为后续 HNSW 做准备。上下文上，我引入父子块：child chunk 用于精准召回和引用，parent chunk 用于给模型更完整的回答上下文。这样解决了“小 chunk 命中准但上下文不够”的 RAG 常见问题，同时通过 `parent_chunk_id` 可选字段兼容旧数据。
