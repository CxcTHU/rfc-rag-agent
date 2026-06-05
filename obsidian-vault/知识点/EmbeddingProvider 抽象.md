---
stage: 阶段 2
category: RAG 链路
location: app/services/retrieval/embedding.py
purpose: 隔离 embedding 模型调用和检索业务逻辑
---

# EmbeddingProvider 抽象

所属阶段：[[阶段 2 - Embedding 与向量检索]]
所属分类：[[RAG 链路]]
相关位置：`app/services/retrieval/embedding.py`

## 它解决什么问题

RAG 系统后续可能切换不同 embedding 模型。如果检索代码直接调用某个模型 API，后续换模型会牵动很多业务逻辑。`EmbeddingProvider` 把模型调用封装成统一接口，让检索服务只关心“给我文本，我要向量”。

## 在本项目中怎么用

`EmbeddingProvider` 定义 `embed_texts()` 和 `embed_query()`。阶段 2 先实现 `DeterministicEmbeddingProvider`，用于无 API key 的本地开发和稳定测试。`VectorIndexService` 调用 `embed_texts()`，`VectorSearchService` 调用 `embed_query()`。

## 新词解释

- embedding：文本向量，把问题或资料片段变成数字列表。
- provider：提供者，本项目中指负责生成 embedding 的对象。
- deterministic embedding：确定性 embedding，同样输入永远生成同样向量。
- API key：调用云端模型服务的密钥，本阶段暂不依赖它。

## 为什么这样设计

本项目参考 Quivr 的 embedder 抽象思想，但没有复制 Quivr 代码。先做 provider 抽象，可以让模型服务、测试实现和检索逻辑解耦。后续接国产 OpenAI-compatible embedding、本地开源 embedding 或云端 embedding 时，只需要新增 provider。

## 面试可能怎么问

问：为什么不直接在检索服务里调用模型 API？

答：因为模型供应商和模型参数会变化。如果直接写死，后续迁移成本高。我把 embedding 调用封装成 provider，检索服务只依赖接口，不依赖具体厂商。

## 你应该怎么回答

我在阶段 2 先定义了 `EmbeddingProvider`，把 embedding 生成能力抽象出来。这样 `VectorIndexService` 和 `VectorSearchService` 都不需要知道向量来自真实云端模型还是本地测试实现。测试中用 deterministic provider 保证稳定，生产环境后续可以换成真实 embedding provider。

## 相关双链

- [[阶段 2 - Embedding 与向量检索]]
- [[RAG 链路]]
