---
stage: "阶段 2"
status: "已完成"
---

# 阶段 2 - Embedding 与向量检索

所属索引：[[阶段索引]]

上一阶段：[[阶段 1 - 本地资料导入与关键词检索]]
下一阶段：[[阶段 3 - 引用式问答]]

## 阶段目标

在阶段 1 的 documents/chunks 和关键词检索 baseline 基础上，实现可测试、可替换、可评测的 embedding 与向量检索链路。

核心链路：

```text
用户问题
-> query embedding
-> chunk_embeddings
-> 余弦相似度
-> top_k 相似 chunk
-> 返回来源、标题、片段和 score
```

## 完成内容

- 新增 [[EmbeddingProvider 抽象]]，隔离模型调用和检索业务逻辑。
- 新增 [[chunk embedding 保存结构]]，用 `chunk_embeddings` 保存 chunk 向量。
- 新增 [[向量索引构建服务]]，可重复构建和更新 chunk embeddings。
- 新增 [[向量检索服务与 API]]，提供 `POST /search/vector`。
- 新增 [[向量检索评测对比]]，复用关键词评测集和 baseline。
- 保留阶段 1 的 `POST /search` 关键词检索作为对照基线。
- 创建 `docs/stage2_learning_notes.md`，沉淀每一步学习笔记和面试表达。

## 关键代码位置

- `app/services/retrieval/embedding.py`
- `app/db/models.py`
- `app/db/repositories.py`
- `app/services/retrieval/vector_index.py`
- `app/services/retrieval/vector_search.py`
- `app/api/search.py`
- `app/schemas/search.py`
- `scripts/build_vector_index.py`
- `scripts/evaluate_vector_search.py`
- `data/evaluation/vector_results.csv`

## 验证结果

```text
python scripts/evaluate_vector_search.py
vector evaluation: 11/15 passed
keyword baseline: 15/15 passed

python -m pytest -q
63 passed
```

失败样例：

- `filling_capacity_en`
- `mesoscopic_modeling`
- `peridynamics`
- `construction_management`

这些失败样例用于后续接入真实 embedding、混合检索或 query expansion 后做回归测试。

## 新词解释

- embedding：文本向量，把问题或资料片段变成一组数字。
- query embedding：用户问题对应的向量。
- chunk embedding：资料片段对应的向量。
- cosine similarity：余弦相似度，用来比较两个向量方向是否接近。
- baseline：对照基线，本项目里阶段 1 的关键词检索就是 baseline。
- stale embedding：过期向量，表示 chunk 内容变了但向量还没重建。
- Recall@K：前 K 条结果是否召回期望资料。

## 阶段设计取舍

本阶段没有直接接入 FAISS、Chroma 或云端 embedding 模型，而是先用 SQLite 和 deterministic embedding 跑通最小链路。

这样做的好处是：

- 不依赖 API key。
- 不被向量库安装问题阻塞。
- 能写稳定自动化测试。
- 后续迁移向量库时可以从 `documents/chunks` 主数据重建索引。

当前 deterministic embedding 只用于稳定开发，不代表真实语义模型效果。阶段 2 的评测结果 11/15 说明链路可运行，但还需要后续用真实 embedding 或混合检索提升召回。

## 知识点链接

- [[EmbeddingProvider 抽象]]
- [[chunk embedding 保存结构]]
- [[向量索引构建服务]]
- [[向量检索服务与 API]]
- [[向量检索评测对比]]
- [[检索评测基线]]

## 面试表达

阶段 2 我先抽象了 `EmbeddingProvider`，避免检索逻辑直接绑定某个模型供应商。然后新增 `chunk_embeddings` 表保存每个 chunk 的向量、模型信息、维度和内容 hash。索引构建由 `VectorIndexService` 负责，向量检索由 `VectorSearchService` 负责，API 层只暴露 `POST /search/vector`。

为了证明不是只做了演示，我复用阶段 1 的关键词评测集，对同一批问题分别运行关键词检索和向量检索。当前 deterministic embedding 下，向量检索 11/15，关键词 baseline 15/15。这个结果说明工程链路已经跑通，但真实语义效果还需要接入更好的 embedding 模型或混合检索继续优化。

## 相关双链

- [[阶段索引]]
- [[RAG 链路]]
- [[数据工程]]
- [[API 设计]]
- [[测试与验证]]
