# 阶段 2 学习笔记：Embedding 与向量检索

本文件用于沉淀阶段 2 每个开发步骤的学习内容，方便复习和面试表达。对话里只保留简洁学习卡片，完整解释写在这里。

## 步骤 1：Embedding Provider 抽象

### 本步骤目标

建立一个统一的 embedding 调用入口，让后续检索逻辑不直接依赖某一家模型服务。

### 做了什么

- 新增 `app/services/retrieval/embedding.py`。
- 定义 `EmbeddingProvider` 协议，统一 `embed_texts()` 和 `embed_query()`。
- 实现 `DeterministicEmbeddingProvider`，用于本地测试和无 API key 开发。
- 新增 `tests/test_embedding_provider.py`。

### 新词解释

| 新词 | 是什么 | 在本项目哪里出现 | 有什么作用 | 面试怎么说 |
| --- | --- | --- | --- | --- |
| `EmbeddingProvider` | embedding 模型提供者，把文本转成向量 | `app/services/retrieval/embedding.py` | 隔离模型调用和业务检索逻辑 | 我把 embedding 模型封装成 provider，后续切换国产模型或本地模型不影响检索服务 |
| `Protocol` | Python 的接口约定 | `EmbeddingProvider` 定义 | 约束 provider 必须有 `embed_texts()` 和 `embed_query()` | 我用 Protocol 表达能力约束，而不是绑定具体实现 |
| deterministic embedding | 确定性 embedding，同样输入得到同样向量 | `DeterministicEmbeddingProvider` | 让测试不依赖网络、API key 或真实模型 | 测试阶段用确定性 embedding 保证结果稳定，真实运行时再替换模型 |
| API key | 调用云端模型服务的密钥 | `.env` 的 embedding 配置预留 | 后续接国产 OpenAI-compatible embedding 时使用 | 我没有把 key 写进代码，而是通过环境变量配置 |
| 归一化 | 把向量长度缩放到 1 | `normalize_vector()` | 方便后续用余弦相似度比较向量方向 | 向量归一化后，相似度计算更稳定 |

### 为什么这样设计

阶段 2 的目标是先跑通“文本 -> embedding -> 检索”的链路，而不是一开始绑定具体厂商。参考 Quivr 的 embedder 抽象，本项目先定义 provider 接口，再提供可测试的本地实现。

### 验证结果

```text
python -m pytest tests/test_embedding_provider.py -q
7 passed

python -m pytest -q
45 passed
```

### 面试表达

阶段 2 开始时，我先抽象了 EmbeddingProvider，而不是直接在检索代码里调用某个模型 API。这样可以把模型供应商、API key 和业务检索逻辑解耦。测试中我使用 deterministic embedding，保证没有外部服务时也能稳定验证向量链路。

### 我应该能说出的回答

我把 embedding 封装成 provider，因为 RAG 系统后续可能切换不同模型。如果业务代码直接调用某个厂商 API，后面迁移成本很高。Provider 抽象让检索服务只关心“给我文本，我要向量”，不关心向量来自哪里。

## 步骤 2：chunk embedding 保存结构

### 本步骤目标

建立 `chunk_embeddings` 表，让每个 chunk 的向量、模型信息和内容指纹都能被保存和复用。

### 做了什么

- 在 `app/db/models.py` 新增 `ChunkEmbedding` 模型。
- 在 `app/db/repositories.py` 新增 `ChunkEmbeddingRepository`。
- 支持保存、查询、列出、统计 chunk embeddings。
- `save_embedding()` 支持有记录就更新、没记录就插入。
- 新增数据库模型和 repository 测试。

### 新词解释

| 新词 | 是什么 | 在本项目哪里出现 | 有什么作用 | 面试怎么说 |
| --- | --- | --- | --- | --- |
| `chunk_embeddings` | chunk 向量表 | SQLite 数据库，对应 `ChunkEmbedding` 模型 | 保存每个资料片段的向量和模型信息 | 我把向量单独成表，避免污染 chunks 主表，也方便后续重建或迁移索引 |
| `content_hash` | 内容指纹 | `ChunkEmbedding.content_hash` | 判断 chunk 内容变化后旧向量是否过期 | 我记录内容 hash，保证 chunk 内容变更后能识别并重建 embedding |
| `unique constraint` | 数据库唯一约束 | `chunk_id + provider + model_name` | 防止同一 chunk 同一模型重复保存多条向量 | 我用唯一约束保证索引构建可以重复运行而不产生重复数据 |
| `upsert` | 有就更新，没有就插入 | `ChunkEmbeddingRepository.save_embedding()` | 支持重复构建索引时更新旧记录 | 我的 save 方法具备 upsert 行为，方便断点式重复运行 |
| `embedding_json` | JSON 格式保存的向量数字列表 | `ChunkEmbedding.embedding_json` | 在 SQLite 中保存向量 | 第一版用 JSON 保存向量，便于调试；后续可迁移到 FAISS/Chroma/PGVector |

### 为什么这样设计

documents/chunks 是主数据，embedding 是可重建索引。把向量放到单独表里，可以清楚记录 provider、model_name、dimension 和 content_hash，后续迁移到向量库时不会影响原始资料和引用溯源。

### 验证结果

```text
python -m pytest tests/test_db_models.py tests/test_repositories.py -q
5 passed

python -m pytest -q
48 passed
```

### 面试表达

我没有只把文本丢进向量库，而是在 SQLite 中保留 documents/chunks 主数据，并新增 chunk_embeddings 表保存向量索引信息。每条向量都记录 chunk_id、模型、维度和内容 hash，因此可以判断是否需要重建，也方便未来迁移到 FAISS、Chroma 或 PGVector。

### 我应该能说出的回答

chunk_embeddings 是向量索引的持久化表。它不替代 chunks，而是补充 chunks。这样回答引用来源时仍回到 chunks/documents 查元数据，向量表只负责检索。

## 步骤 3：向量索引构建服务

### 本步骤目标

实现一个可重复运行的索引构建服务，把数据库中的 chunks 批量转成 embedding 并保存到 `chunk_embeddings`。

### 做了什么

- 新增 `app/services/retrieval/vector_index.py`。
- 实现 `VectorIndexService.build_index()`。
- 新增 `VectorIndexResult`，记录 total、indexed、updated、skipped 等统计。
- 新增 `calculate_text_hash()`，根据 chunk 内容计算内容指纹。
- 新增 `batched()`，按 batch size 分批处理 chunks。
- 新增 `scripts/build_vector_index.py`，作为命令行构建入口。
- 新增 `tests/test_vector_index_service.py`。

### 新词解释

| 新词 | 是什么 | 在本项目哪里出现 | 有什么作用 | 面试怎么说 |
| --- | --- | --- | --- | --- |
| `VectorIndexService` | 向量索引构建服务 | `app/services/retrieval/vector_index.py` | 扫描 chunks，生成 embedding，写入 `chunk_embeddings` | 我把索引构建独立成 service，避免 API、脚本和数据库逻辑混在一起 |
| batch | 批次 | `build_index(batch_size=32)` | 分批调用 embedding provider，避免一次处理过多文本 | 我支持批处理，后续接云端模型时可以控制请求规模和成本 |
| stale embedding | 过期向量 | `content_hash` 或 dimension 不一致时 | 识别需要重新生成的旧 embedding | 我通过内容 hash 和维度判断向量是否过期 |
| idempotent | 幂等，重复执行不会产生重复副作用 | `build_index()` 重复运行会 skip 未变化 chunks | 支持断点式和重复构建索引 | 索引构建脚本是幂等的，可以安全重复运行 |
| CLI script | 命令行脚本 | `scripts/build_vector_index.py` | 让开发者在终端一键构建向量索引 | 我提供脚本入口，方便本地和后续部署任务复用 |

### 为什么这样设计

参考 Quivr 的“处理后的文档 -> embedder -> vector_db”链路，本项目把“构建索引”单独成服务。API 不负责生成全库向量，脚本也不直接写数据库，而是调用 service。这样模块边界清楚，后续接真实 embedding 模型、后台任务或 FAISS/Chroma 时都更容易替换。

### 验证结果

```text
python -m pytest tests/test_vector_index_service.py -q
5 passed

python -m py_compile app/services/retrieval/vector_index.py scripts/build_vector_index.py tests/test_vector_index_service.py
pass

python -m pytest -q
53 passed
```

### 面试表达

我实现了 VectorIndexService 来负责向量索引构建。它会扫描 chunks，判断已有 embedding 是否过期，对未索引或已过期的 chunk 批量生成向量，并写入 chunk_embeddings。这个过程是幂等的，所以脚本可以重复运行，不会生成重复向量。

### 我应该能说出的回答

向量索引构建不是用户每次搜索时才做的，而是提前批量完成。这样搜索时只需要把问题向量化，再和已有 chunk 向量比较，速度更快，也更符合 RAG 系统的工程流程。

## 步骤 4：向量检索服务与 API

### 本步骤目标

把“用户问题 -> query embedding -> 相似 chunk -> 返回来源”的链路正式接到服务和 API 上，同时保留阶段 1 的关键词检索作为对照基线。

### 做了什么

- 新增 `app/services/retrieval/vector_search.py`。
- 实现 `VectorSearchService.search()`，读取已构建的 `chunk_embeddings` 并计算相似度。
- 新增 `cosine_similarity()`，用于比较 query embedding 和 chunk embedding 的方向接近程度。
- 向量检索会过滤 provider、model_name、dimension，避免不同模型向量混用。
- 向量检索会跳过 stale embedding，避免 chunk 已变化但索引未重建时返回错误依据。
- 在 `app/api/search.py` 新增 `POST /search/vector`。
- 在 `app/schemas/search.py` 新增 `VectorSearchRequest` 和 `VectorSearchResponse`。
- 新增 `tests/test_vector_search.py` 和 `tests/test_vector_search_api.py`。

### 新词解释

| 新词 | 是什么 | 在本项目哪里出现 | 有什么作用 | 面试怎么说 |
| --- | --- | --- | --- | --- |
| `VectorSearchService` | 向量检索服务 | `app/services/retrieval/vector_search.py` | 把问题向量和 chunk 向量做相似度比较，返回最相关片段 | 我把检索逻辑放在 service 层，API 只负责接收请求和组织响应 |
| query embedding | 用户问题对应的向量 | `VectorSearchService.search()` 调用 `embed_query()` | 让问题可以和资料片段在同一个向量空间比较 | 用户问题先转成 embedding，再与资料 chunk 的 embedding 计算相似度 |
| cosine similarity | 余弦相似度 | `cosine_similarity()` | 衡量两个向量方向是否接近，越接近 1 越相似 | 向量检索不是比较字面词，而是比较 query 和 chunk 的向量方向 |
| dot product | 点积 | `cosine_similarity()` 内部 | 余弦相似度计算的一步，把两个向量逐项相乘再求和 | 点积配合向量长度可以得到余弦相似度 |
| `score` | 检索相关性分数 | `/search/vector` 响应结果 | 告诉调用方每个 chunk 和问题有多接近 | 我把相似度作为 score 返回，方便排序、调试和后续评测 |
| baseline | 对照基线 | 阶段 1 的 `POST /search` | 后续评估向量检索是否优于关键词检索 | 我保留关键词检索作为 baseline，避免只凭感觉判断新方案效果 |
| stale embedding | 过期向量 | `VectorSearchService` 校验 `content_hash` | 避免用旧向量匹配新文本 | 如果 chunk 内容变了但索引没重建，我会跳过这条向量，保证结果可解释 |

### 为什么这样设计

参考 Quivr 的 retriever 思路，本项目把“索引构建”和“检索查询”分开：索引构建阶段提前把 chunks 转成 embedding，检索阶段只把用户问题转成 embedding 并计算相似度。这样 API 不会在每次搜索时重建全库向量，职责更清楚。

本阶段没有替换 `/search`，而是新增 `/search/vector`。这样做的原因是阶段 1 的关键词检索仍然是可靠 baseline。下一步做评测时，可以对同一批问题分别运行关键词检索和向量检索，再比较命中率、失败案例和来源质量。

### 验证结果

```text
python -m py_compile app/services/retrieval/vector_search.py app/api/search.py app/schemas/search.py tests/test_vector_search.py tests/test_vector_search_api.py
pass

python -m pytest tests/test_vector_search.py tests/test_vector_search_api.py -q
7 passed

python -m pytest tests/test_search_api.py tests/test_keyword_search.py tests/test_vector_index_service.py -q
11 passed

python -m pytest -q
60 passed
```

### 面试表达

我实现了独立的 VectorSearchService 和 `/search/vector` API。检索时，系统先把用户问题转成 query embedding，再从 `chunk_embeddings` 中取出同一 provider/model/dimension 的 chunk embedding，计算余弦相似度并按 score 排序返回。为了保持结果可信，我会跳过内容 hash 不一致的 stale embedding，并保留原来的关键词 `/search` 作为 baseline。

### 我应该能说出的回答

向量检索解决的是“字面不同但语义接近”的召回问题。我的实现不是直接上复杂向量库，而是先用 SQLite 保存 embedding，用线性扫描和余弦相似度跑通主链路。这样更容易测试，也方便后面迁移到 FAISS、Chroma 或 PGVector。

## 步骤 5：检索评测对比

### 本步骤目标

复用阶段 1 的关键词评测集，对向量检索运行同一批问题，并把向量检索结果和关键词 baseline 做对比。

### 做了什么

- 新增 `scripts/evaluate_vector_search.py`。
- 复用 `data/evaluation/keyword_queries.csv` 作为评测输入。
- 生成 `data/evaluation/vector_results.csv`，记录向量检索每条问题的命中情况。
- 读取 `data/evaluation/keyword_results.csv`，在向量结果里标记 `same_pass`、`keyword_only_pass` 等对比状态。
- 新增 `tests/test_evaluate_vector_search.py`。
- 将 `VectorIndexService` 的数据库写入优化为 batch commit，避免首次索引大量 chunk 时过慢。

### 新词解释

| 新词 | 是什么 | 在本项目哪里出现 | 有什么作用 | 面试怎么说 |
| --- | --- | --- | --- | --- |
| evaluation script | 评测脚本 | `scripts/evaluate_vector_search.py` | 自动运行固定问题集并输出检索结果 | 我用脚本让检索评测可重复，而不是手动看几个样例 |
| Recall@K | 前 K 条结果里是否召回期望资料 | `top_k`、`hit_rank` 字段 | 衡量检索是否把正确资料排进前 K 条 | 我用 hit_rank 记录期望资料是否进入 top_k，近似做 Recall@K 检查 |
| failure case | 失败样例 | `vector_results.csv` 中 `passed=no` 的行 | 帮助定位向量检索哪里弱 | 我会保留失败样例，后续优化 embedding 或混合检索时回归验证 |
| `keyword_only_pass` | 关键词命中但向量未命中 | `vector_results.csv` 的 `comparison` 字段 | 暴露向量检索弱于 baseline 的问题 | 这说明新方案并非天然更好，需要用评测证明和迭代 |
| batch commit | 批量提交数据库写入 | `VectorIndexService` 调用 `save_embedding(commit=False)` | 减少大量 chunk 写入时的磁盘提交次数 | 我把索引构建改为按批提交，避免首次构建索引时过慢 |
| regression test | 回归测试 | `python -m pytest` | 确认新改动没有破坏旧功能 | 我每次修改检索链路后跑相关测试和全量测试，保证系统持续可运行 |

### 为什么这样设计

阶段 2 不能只说“向量检索已经能跑”，还要能回答“它比关键词检索好在哪里、差在哪里”。所以本步骤复用同一批 `keyword_queries.csv`，让关键词和向量使用完全相同的问题、期望标题、期望内容词和期望来源类型。

当前 deterministic embedding 是为了稳定开发，不是真实语义模型。因此评测结果不能被包装成“语义检索已优于关键词”。这次真实结果是向量检索 11/15，通过但弱于关键词 baseline 的 15/15。这个结果很有价值，因为它说明下一步需要真实 embedding 模型、混合检索或更好的 query expansion，而不是盲目相信向量检索。

### 验证结果

```text
python -m py_compile scripts/evaluate_vector_search.py tests/test_evaluate_vector_search.py
pass

python -m pytest tests/test_evaluate_vector_search.py -q
3 passed

python scripts/evaluate_vector_search.py
vector evaluation: 11/15 passed
keyword baseline: 15/15 passed

python -m pytest -q
63 passed
```

失败样例：

```text
filling_capacity_en
mesoscopic_modeling
peridynamics
construction_management
```

### 面试表达

我没有只实现向量检索 API，还复用了阶段 1 的关键词评测集做检索回归。评测脚本会对同一批问题运行向量检索，输出命中排名、top titles、向量分数和与关键词 baseline 的对比。当前 deterministic embedding 下向量检索是 11/15，关键词 baseline 是 15/15，这说明第一版本地向量链路可运行，但还不能证明语义效果优于关键词检索。

### 我应该能说出的回答

检索系统必须做评测，否则很容易只凭几个演示样例误判效果。我用同一批问题对关键词和向量检索做对比，记录成功和失败样例。失败样例后续会用于验证真实 embedding 模型、混合检索或 query expansion 是否真的带来提升。

## 步骤 6：阶段收尾文档

### 本步骤目标

把阶段 2 的代码、测试、评测结果、架构说明和 Obsidian 知识库统一更新到“阶段 2 已完成、下一步进入阶段 3”的状态。

### 做了什么

- 更新 `README.md`，说明阶段 2 已完成、当前功能、向量索引命令、评测命令和阶段 2 面试表达。
- 更新 `docs/progress.md`，作为权威进度记录写入阶段 2 完成内容、验证结果、遗留问题和下一阶段。
- 更新 `docs/architecture.md`，补充阶段 2 的 embedding、chunk_embeddings、向量索引、向量检索 API 和评测链路。
- 更新 `AGENT.MD`，把“当前推荐的第一步”从阶段 2 启动改为阶段 3 引用式问答。
- 更新 Obsidian 首页、阶段索引、阶段 2 页、分类页和阶段 2 知识点。
- 更新 `task_plan.md`，将阶段 6 标记为完成。

### 新词解释

| 新词 | 是什么 | 在本项目哪里出现 | 有什么作用 | 面试怎么说 |
| --- | --- | --- | --- | --- |
| 阶段收尾 | 阶段结束时同步代码、测试、文档和知识库 | `task_plan.md` Phase 6 | 避免代码完成但入口文档仍停留在旧阶段 | 我每个阶段结束都会同步 README、progress、architecture 和知识库 |
| 完成审计 | 用当前证据逐项确认目标是否完成 | 阶段 2 收尾检查 | 防止凭印象宣布完成 | 我会用规划文件、测试结果、评测输出和文档状态证明阶段完成 |
| 权威进度 | 最可信的项目进度记录 | `docs/progress.md` | 新线程和复盘时先看它 | 我把阶段完成记录写进 docs/progress，避免上下文丢失 |
| Obsidian 双链 | Obsidian 中用 `[[页面名]]` 连接笔记 | `obsidian-vault/` | 方便按阶段和分类复习 | 我把阶段页、分类页、知识点互相链接，形成可复习知识库 |
| 文档债 | 代码已经变了但文档没同步造成的欠账 | README、architecture、progress 校准 | 避免后来的人误判项目状态 | 我在阶段收尾主动清理文档债 |

### 为什么这样设计

阶段 2 不是只写完代码就结束。对一个工程项目来说，新线程接手、面试复盘、后续开发和用户理解都依赖文档。如果 README 还写“阶段 2 下一阶段”，但代码已经有向量检索，后续就会出现方向混乱。

因此阶段收尾必须把三个层次同步：

- 新读者入口：`README.md`
- 权威进度和架构：`docs/progress.md`、`docs/architecture.md`
- 复习知识库：`obsidian-vault/`

### 验证结果

```text
python -m pytest -q
63 passed

python scripts/evaluate_vector_search.py
vector evaluation: 11/15 passed
keyword baseline: 15/15 passed
```

### 面试表达

阶段 2 收尾时，我不仅验证了代码和测试，还同步了 README、进度文档、架构文档和 Obsidian 知识库。这样做能保证后续新线程或面试复盘时，项目状态、模块边界、评测结果和下一步计划是一致的。这体现的是工程项目的可维护性，而不只是功能实现。

### 我应该能说出的回答

阶段完成不等于代码写完。一个可维护项目需要让 README、progress、architecture、测试结果和知识库都能证明当前阶段已经完成。阶段 2 我用 63 个自动化测试、向量检索评测结果和文档同步来证明链路已经稳定跑通。
