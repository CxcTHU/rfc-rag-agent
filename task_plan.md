# Task Plan: 阶段 2 - Embedding 与向量检索

## Goal
在阶段 1 的 documents/chunks 与关键词检索 baseline 基础上，完成可测试、可替换、可评测的 embedding 与向量检索链路。

## Current Phase
Stage 2 complete

## Phases

### Phase 1: Embedding Provider 抽象
- [x] 参考 Quivr 的 embedder 抽象方式，确定本项目不把模型调用写死在检索逻辑里。
- [x] 新增 `EmbeddingProvider` 接口，统一 `embed_texts()` 和 `embed_query()`。
- [x] 新增本地 deterministic embedding provider，用于测试和无 API key 开发。
- [x] 补充最小自动化测试，验证维度、归一化、稳定性和空输入处理。
- [x] 补充本阶段新词解释与面试表达。
- **Status:** complete

### Phase 2: chunk embedding 保存结构
- [x] 设计并实现 `chunk_embeddings` 表。
- [x] Repository 支持按 chunk_id、provider、model_name 查询和保存向量。
- [x] 记录 dimension、content_hash、created_at，支持后续重建索引。
- [x] 补充本阶段新词解释与面试表达。
- **Status:** complete

### Phase 3: 向量索引构建服务
- [x] 新增 `VectorIndexService`，扫描未向量化 chunks。
- [x] 批量调用 embedding provider 并写入 `chunk_embeddings`。
- [x] 新增 `scripts/build_vector_index.py`，支持断点式重复运行。
- [x] 补充本阶段新词解释与面试表达。
- **Status:** complete

### Phase 4: 向量检索服务与 API
- [x] 新增 `VectorSearchService`，计算 query embedding 与 chunk embedding 的余弦相似度。
- [x] 新增 `POST /search/vector`，提供向量检索入口并返回来源、标题、片段和 score。
- [x] 保持阶段 1 `/search` 关键词检索可用，避免破坏 baseline。
- [x] 补充本阶段新词解释与面试表达。
- **Status:** complete

### Phase 5: 检索评测对比
- [x] 复用 `data/evaluation/keyword_queries.csv`。
- [x] 新增 `scripts/evaluate_vector_search.py` 和 `data/evaluation/vector_results.csv`。
- [x] 对比关键词检索和向量检索的召回表现，记录失败案例。
- [x] 补充本阶段新词解释与面试表达。
- **Status:** complete

### Phase 6: 阶段收尾文档
- [x] 更新 `README.md`。
- [x] 更新 `docs/progress.md`。
- [x] 更新 `docs/architecture.md`。
- [x] 判断是否需要更新 `AGENT.MD`，并将下一步校准为阶段 3。
- [x] 更新 Obsidian 阶段 2 页面与知识点。
- **Status:** complete

## Key Questions
1. 第一版向量索引是否直接使用 FAISS/Chroma？答：否，先用 SQLite 保存 embedding，降低阶段 2 初期调试复杂度。
2. 如何避免后续迁移困难？答：SQLite 的 documents/chunks 作为主数据，向量库只作为可重建索引；所有向量通过 chunk_id 回关联原文。
3. 如何保证测试不依赖真实模型 API？答：提供 deterministic embedding provider，用稳定算法生成固定维度向量。
4. 如何借鉴 Quivr？答：学习其 embedder/vector_db/retriever 的模块边界，不复制复杂 workflow。

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 第一版先实现 provider 抽象与 deterministic provider | 不依赖 API key，不被 FAISS/Chroma 安装问题阻塞，方便写稳定测试 |
| documents/chunks 继续作为主数据 | 后续向量库迁移时只重建索引，不影响引用溯源 |
| 向量检索先独立于关键词检索实现 | 保留阶段 1 baseline，方便对比与回归 |
| 参考 Quivr 的 VectorStore 抽象边界 | embedding、向量存储、检索服务解耦，后续可替换 FAISS/Chroma/PGVector |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `def batched[T]` is Python 3.12-only syntax | 1 | 改为 Python 3.11 可用的 `TypeVar` 写法 |
| 向量评测首次运行超时 | 1 | 将索引构建从逐条提交优化为按 batch 提交，重跑后 997 个 chunk 全部跳过未变更索引并完成评测 |

## Notes
- 本文件由 `planning-with-files` 技能创建，作为阶段 2 开发工作记忆。
- Quivr 默认使用 FAISS，并通过 LangChain VectorStore 抽象保留替换能力；本项目阶段 2 先实现更轻量的本地链路。
- 阶段 2 不做引用式问答和 Agent 工具调用，那是阶段 3/7 的任务。
