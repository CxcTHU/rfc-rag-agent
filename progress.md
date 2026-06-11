# 阶段 26 进度日志：检索性能优化 + Cross-Encoder 重排序

## 当前状态

- 当前阶段：阶段 26「检索性能优化 + Cross-Encoder 重排序」。
- 当前分支：待创建 `codex/phase-26-retrieval-performance-reranking`。
- 前置条件：阶段 25 必须先完成提交、合并到 main 并创建 `phase-25-complete` tag。
- 阶段 26 状态：规划完成，等待 Phase 0 启动校准。
- 提交状态：尚未 `git add`、尚未提交、尚未创建 `phase-26-complete` tag、尚未推送。

## 阶段 26 目标概述

从阶段 25 完成后的 main 出发，实现检索性能优化 + Cross-Encoder 重排序：

1. **Profiling 与基线基准**：用 cProfile 和 perf_counter 量化当前检索管线每层耗时，建立优化前基线。
2. **numpy 向量化加速**：向量搜索从纯 Python 逐条余弦改为 numpy 矩阵运算，引入内存向量索引缓存。
3. **BM25 与向量检索并行**：hybrid search 中两路检索从串行改为 ThreadPoolExecutor 并行。
4. **Cross-Encoder 重排序**：新增 `ReRankingProvider` Protocol，hybrid search 召回 top-20~30 后 cross-encoder 精排取 top-5。
5. **端到端基准对比**：量化优化前后各层耗时和总响应时间改善。

## 阶段 25 验收基线

- 阶段 25 验收结论：待提交合并。
- 测试基线：497 passed。
- 关键交付：闲聊短路、SSE 流式输出、ChatModelProvider stream_generate、/agent/query/stream 端点。

## 已知性能瓶颈

来自 `docs/progress.md` 阶段 25 遗留风险：
- 真实本地大库上普通 RAG 问题 `What affects filling capacity in rock-filled concrete?` 在同步和流式端点都超过 20 秒。
- 初步判断瓶颈在 `VectorSearchService._list_indexed_chunks()`：每次查询从数据库加载全部 ChunkEmbedding 行到 Python 内存，然后用纯 Python 循环逐条计算 `cosine_similarity()`。
- keyword search（BM25）和 vector search 串行执行，hybrid search 总耗时为两者之和。
- 缺少重排序层，召回质量仅靠 BM25 + 余弦的简单加权。

## 遗留风险

- 阶段 25 尚未提交合并，阶段 26 不能从错误基线出发。
- numpy 引入后需要确认 deterministic embedding provider 的 64 维 hash 向量在 numpy 矩阵运算下结果一致。
- SQLAlchemy Session 在多线程并发中需要注意线程安全。
- 重排序 API 可能增加网络延迟，需要在总耗时预算内平衡。
