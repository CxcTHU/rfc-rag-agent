---
stage: 阶段 2
category: API 设计
location: app/services/retrieval/vector_search.py, app/api/search.py, app/schemas/search.py
purpose: 提供用户问题到相似 chunk 的向量检索入口
---

# 向量检索服务与 API

所属阶段：[[阶段 2 - Embedding 与向量检索]]
所属分类：[[API 设计]]
相关位置：`app/services/retrieval/vector_search.py`、`app/api/search.py`、`app/schemas/search.py`

## 它解决什么问题

关键词检索依赖字面匹配，遇到同义表达或中英文术语时容易漏掉资料。向量检索把问题和 chunk 都变成 embedding，再按相似度召回相关片段。

## 在本项目中怎么用

`VectorSearchService.search()` 负责检索逻辑，`POST /search/vector` 负责 HTTP 入口。响应会返回 `provider`、`model_name` 和每条结果的来源、标题、chunk 内容、heading_path 和 score。

## 新词解释

- query embedding：用户问题对应的向量。
- cosine similarity：余弦相似度，用两个向量方向的接近程度表示相关性。
- score：检索分数，阶段 2 中表示余弦相似度。
- top_k：返回最相关的前 K 条结果。
- source：来源信息，例如文档标题、文件名和来源路径。

## 为什么这样设计

本项目保留 `POST /search` 作为关键词 baseline，再新增 `POST /search/vector`，而不是替换旧接口。这样后续评测可以比较两个检索入口的效果，也能在向量检索效果不稳定时继续保留可解释的关键词检索。

## 面试可能怎么问

问：向量检索为什么要返回 provider 和 model_name？

答：因为不同模型生成的向量不能混用。响应里返回 provider 和 model_name，可以帮助排查当前检索用的是测试 provider 还是真实模型。

## 你应该怎么回答

我把向量检索放在 `VectorSearchService`，API 层只负责请求和响应。检索时先把用户问题转成 query embedding，再读取同一 provider/model/dimension 的 chunk embedding，计算余弦相似度并返回 top_k。为了保证结果可信，我还会跳过 stale embedding。

## 相关双链

- [[阶段 2 - Embedding 与向量检索]]
- [[API 设计]]
- [[RAG 链路]]
