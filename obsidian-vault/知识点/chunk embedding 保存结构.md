---
stage: 阶段 2
category: 数据工程
location: app/db/models.py, app/db/repositories.py
purpose: 保存 chunk 向量、模型信息和内容指纹
---

# chunk embedding 保存结构

所属阶段：[[阶段 2 - Embedding 与向量检索]]
所属分类：[[数据工程]]
相关位置：`app/db/models.py`、`app/db/repositories.py`

## 它解决什么问题

向量检索需要保存每个 chunk 的 embedding。如果只把向量放进外部向量库，后续引用来源、排查错误和迁移索引都会变困难。本项目先在 SQLite 中新增 `chunk_embeddings` 表，把向量和 chunk 主数据关联起来。

## 在本项目中怎么用

`ChunkEmbedding` 保存 `chunk_id`、`provider`、`model_name`、`dimension`、`embedding_json` 和 `content_hash`。`ChunkEmbeddingRepository` 负责保存、查询、列出和统计向量。`VectorIndexService` 通过 repository 写入索引，`VectorSearchService` 再读取这些向量进行相似度计算。

## 新词解释

- `chunk_embeddings`：chunk 向量表。
- `embedding_json`：用 JSON 文本保存的向量数字列表。
- `content_hash`：内容指纹，用来判断 chunk 内容是否变化。
- unique constraint：唯一约束，防止同一个 chunk/provider/model 保存重复向量。
- upsert：有记录就更新，没记录就插入。

## 为什么这样设计

`documents` 和 `chunks` 是主数据，`chunk_embeddings` 是可重建索引。这样后续迁移到 FAISS、Chroma 或 PGVector 时，不会影响原始资料和引用来源，只需要重新构建向量索引。

## 面试可能怎么问

问：为什么不直接把原文和向量都交给向量库？

答：因为 RAG 系统需要可解释和可追溯。主数据必须保留在结构化数据库中，向量库或向量表只负责检索索引。这样返回结果时可以通过 `chunk_id` 找回标题、来源、文件名和片段内容。

## 你应该怎么回答

我新增了 `chunk_embeddings` 表，但没有替代原来的 `chunks` 表。`chunks` 继续保存可引用文本，`chunk_embeddings` 保存可重建的向量索引。每条向量记录 provider、model、dimension 和 content_hash，方便判断是否过期，也方便后续迁移向量库。

## 相关双链

- [[阶段 2 - Embedding 与向量检索]]
- [[数据工程]]
- [[RAG 链路]]
