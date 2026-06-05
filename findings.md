# Findings & Decisions

## Requirements
- 用户要求正式进入阶段 2 开发。
- 用户要求先尝试修改当前线程名称，已完成，标题为 `阶段2-Embedding 与向量检索`。
- 用户要求参照 Quivr 项目拆分阶段 2 开发任务。
- 用户要求使用 `planning-with-files` 生成阶段 2 规划文件。
- 用户要求完成第一个开发任务。

## Research Findings
- 本项目阶段 1 已完成并合并到 `main`，当前分支为 `codex/phase-2-vector-search`。
- 阶段 1 已有 `documents` 和 `chunks` 两张主表，已有 ingestion service 与关键词检索 `/search`。
- 本地数据库当前记录过 136 篇 documents 和 997 个 chunks，适合先用 SQLite 保存向量并进行线性相似度检索。
- Quivr 的 `Brain` 将文件处理、embedder、vector_db、retriever 分离。
- Quivr 默认使用 FAISS 构建本地向量库；序列化结构中也预留 PGVector 配置。
- 本地 Quivr core 未发现 Chroma 的实际默认使用。
- Quivr 测试使用 `InMemoryVectorStore` 和 deterministic fake embedding，说明测试不应依赖真实模型 API。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 第一开发任务是 Embedding Provider 抽象 | 这是向量索引和语义检索的上游依赖，且能单独测试 |
| 增加 deterministic embedding provider | 保证无 API key、无网络、无外部向量库时仍可稳定测试 |
| 暂不直接引入 FAISS/Chroma | 阶段 2 初期重点是跑通 embedding -> 保存 -> 相似度检索主链路 |
| 保留 SQLite documents/chunks 为主数据源 | 后续迁移到 FAISS/Chroma/PGVector 时只需重建索引 |
| 新词解释加入每个 Phase 验收项 | 仅写在 AGENT.MD 里仍可能执行遗漏，放进任务清单能在每次阶段收尾时强制检查 |
| `chunk_embeddings` 用唯一约束避免重复索引 | 同一个 chunk 使用同一个 provider/model 只保留一条向量，重复构建时更新旧记录 |
| 向量检索新增独立入口 `POST /search/vector` | 保留阶段 1 `/search` 关键词检索 baseline，后续可以直接对比两条检索链路 |
| `VectorSearchService` 跳过 stale embedding | 避免 chunk 文本已经变化但向量还没重建时返回解释不一致的检索结果 |
| 向量检索评测复用 `keyword_queries.csv` | 保证关键词 baseline 和向量检索使用同一批问题，比较口径一致 |
| `scripts/evaluate_vector_search.py` 默认检查并补齐向量索引 | 避免因为忘记构建 `chunk_embeddings` 而把空结果误判为检索失败 |
| `VectorIndexService` 改为按 batch 提交数据库写入 | 减少大量 chunk 首次索引时的磁盘提交次数，避免评测脚本长时间卡住 |

## Term Explanations
| Term | Explanation |
|------|-------------|
| `EmbeddingProvider` | embedding 模型提供者，负责把问题或 chunk 文本转成向量；本项目放在 `app/services/retrieval/embedding.py` |
| `Protocol` | Python 的接口约定，用来表达“只要对象有这些方法，就能当作这个类型使用” |
| deterministic embedding | 确定性 embedding，同样输入永远生成同样向量，适合测试和无 API key 开发 |
| `hash` | 内容指纹，把文本算成固定字符串；本项目用它判断 chunk 内容是否变化 |
| API key | 调用云端模型服务的密钥；阶段 2 初期不用真实 key，避免开发被外部服务卡住 |
| 归一化 | 把向量长度缩放到 1，方便后续用余弦相似度比较语义距离 |
| `chunk_embeddings` | chunk 向量表，保存每个资料片段对应的 embedding、模型信息和内容指纹 |
| `unique constraint` | 数据库唯一约束，保证同一个 chunk/provider/model 组合不会保存重复向量 |
| `upsert` | 有记录就更新、没记录就插入；本项目 repository 的 `save_embedding()` 采用这个行为 |
| `embedding_json` | 用 JSON 文本保存向量数字列表，便于 SQLite 早期开发和后续迁移 |
| `VectorIndexService` | 向量索引构建服务，扫描 chunks、调用 embedding provider、写入 `chunk_embeddings` |
| batch | 批次，把多个 chunk 分组处理，避免一次调用处理过多文本 |
| stale embedding | 过期向量，表示 chunk 内容或向量维度变了，需要重新生成 embedding |
| idempotent | 幂等，重复运行同一操作不会产生重复或错误结果；本项目索引脚本重复运行会跳过未变化 chunks |
| CLI script | 命令行脚本，例如 `scripts/build_vector_index.py`，用于在终端触发索引构建 |
| `VectorSearchService` | 向量检索服务，把用户问题转成 query embedding，再和 `chunk_embeddings` 中保存的 chunk embedding 比较相似度 |
| query embedding | 用户问题对应的向量；本项目在 `VectorSearchService.search()` 中调用 `embed_query()` 生成 |
| cosine similarity | 余弦相似度，用两个向量夹角衡量接近程度；越接近 1 表示方向越像，越适合排在前面 |
| dot product | 点积，余弦相似度计算中的基础步骤，可以理解为两个向量逐项相乘再求和 |
| `score` | 检索相关性分数；向量检索中表示 query embedding 与 chunk embedding 的余弦相似度 |
| baseline | 对照基线；本项目里阶段 1 的 `/search` 关键词检索是后续评估向量检索是否变好的对照组 |
| evaluation script | 评测脚本，用固定问题集自动运行检索并输出结果；本项目新增 `scripts/evaluate_vector_search.py` |
| Recall@K | 检索评测指标，表示前 K 条结果中是否召回了期望资料；本项目用 `top_k` 和 `hit_rank` 近似记录 |
| failure case | 失败样例，表示某条评测问题没有命中期望资料；本轮向量检索有 4 条 `keyword_only_pass` |
| keyword_only_pass | 关键词检索命中但向量检索未命中；说明当前 deterministic 向量检索在这类问题上弱于 baseline |
| batch commit | 批量提交，把一批数据库写入一起确认保存；本项目用于加速 `VectorIndexService` 写入 `chunk_embeddings` |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| `Sequence` 重复导入 | 删除 `typing.Sequence`，统一使用 `collections.abc.Sequence` |
| `def batched[T]` 是 Python 3.12 才支持的泛型语法 | 改成 Python 3.11 可用的 `TypeVar` 写法，符合项目 `requires-python >=3.11` |
| 首次运行 `scripts/evaluate_vector_search.py` 超时 | 发现索引写入已完成但脚本未及时输出；将索引构建保存逻辑改为 batch commit 后重跑成功 |

## Resources
- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `data/evaluation/keyword_queries.csv`
- `G:\Codex\program\quivr\core\quivr_core\brain\brain.py`
- `G:\Codex\program\quivr\core\quivr_core\brain\brain_defaults.py`
- `G:\Codex\program\quivr\core\quivr_core\rag\entities\config.py`
- `G:\Codex\program\quivr\core\tests\test_brain.py`

## Visual/Browser Findings
- 未使用浏览器或视觉检查。
