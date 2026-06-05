# Progress Log

## Session: 2026-06-05

### Phase 1: Embedding Provider 抽象
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 使用 `planning-with-files` 技能创建阶段 2 规划文件。
  - 参考 Quivr 的 embedder/vector_db/retriever 分层方式，确定本项目阶段 2 的任务边界。
  - 新增 `EmbeddingProvider` 协议与 deterministic embedding provider。
  - 新增 embedding provider 单元测试。
  - 根据用户提醒，将“新词解释”从背景规则加强为 `AGENT.MD` 最终回复自检和 `task_plan.md` Phase 验收项。
- Files created/modified:
  - `task_plan.md` created
  - `findings.md` created
  - `progress.md` created
  - `app/services/retrieval/embedding.py` created
  - `tests/test_embedding_provider.py` created
  - `AGENT.MD` modified

### Phase 2: chunk embedding 保存结构
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `ChunkEmbedding` SQLAlchemy 模型，对应 `chunk_embeddings` 表。
  - 在 `Chunk` 和 `ChunkEmbedding` 之间建立一对多关系，支持删除 chunk 时级联删除向量。
  - 新增 `ChunkEmbeddingCreate` 数据结构。
  - 新增 `ChunkEmbeddingRepository`，支持保存、查询、列出和统计 chunk embeddings。
  - `save_embedding()` 支持同一 chunk/provider/model 的更新行为，避免重复索引。
  - 新增 `serialize_embedding()` 和 `deserialize_embedding()`，用于 SQLite 中的 JSON 向量存取。
  - 补充数据库模型和 repository 测试。
- Files created/modified:
  - `app/db/models.py` modified
  - `app/db/repositories.py` modified
  - `tests/test_db_models.py` modified
  - `tests/test_repositories.py` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 3: 向量索引构建服务
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `VectorIndexService`，负责扫描 chunks、判断是否需要生成或更新 embedding、批量写入 `chunk_embeddings`。
  - 新增 `VectorIndexResult`，返回 total/indexed/updated/skipped 等索引构建统计。
  - 新增 `calculate_text_hash()`，用 chunk 内容计算内容指纹。
  - 新增 `batched()`，按 batch_size 把待处理 chunks 分批。
  - 新增 `scripts/build_vector_index.py`，提供命令行索引构建入口。
  - 补充 `tests/test_vector_index_service.py`，覆盖首次构建、重复跳过、内容变化更新、limit 和参数校验。
  - 创建 `docs/stage2_learning_notes.md`，沉淀阶段 2 每步学习卡片和面试表达。
- Files created/modified:
  - `app/services/retrieval/vector_index.py` created
  - `scripts/build_vector_index.py` created
  - `tests/test_vector_index_service.py` created
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified
  - `docs/stage2_learning_notes.md` created

### Phase 4: 向量检索服务与 API
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `VectorSearchService`，负责把用户问题转成 query embedding，并与 `chunk_embeddings` 中的 chunk embedding 计算余弦相似度。
  - 新增 `VectorSearchResult`，复用阶段 1 的来源、标题、片段、heading_path 和 score 返回结构。
  - 新增 `cosine_similarity()` 和 `is_zero_vector()`，把相似度计算从 API 层拆到检索服务层。
  - 向量检索只读取同一 provider/model/dimension 的索引，避免不同模型生成的向量混用。
  - 向量检索会跳过 stale embedding，避免 chunk 内容变更但索引未重建时返回错误依据。
  - 在 `app/api/search.py` 新增 `POST /search/vector`，同时保留原 `POST /search` 关键词检索。
  - 在 `app/schemas/search.py` 新增 `VectorSearchRequest` 和 `VectorSearchResponse`，响应中返回 provider 与 model_name，方便后续排查。
  - 新增 `tests/test_vector_search.py` 和 `tests/test_vector_search_api.py`，覆盖服务层、API 层、缺失索引、过期索引和参数校验。
- Files created/modified:
  - `app/services/retrieval/vector_search.py` created
  - `app/api/search.py` modified
  - `app/schemas/search.py` modified
  - `tests/test_vector_search.py` created
  - `tests/test_vector_search_api.py` created
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified
  - `docs/stage2_learning_notes.md` modified

### Phase 5: 检索评测对比
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `scripts/evaluate_vector_search.py`，复用 `data/evaluation/keyword_queries.csv` 作为阶段 2 向量检索评测集。
  - 评测脚本默认检查并补齐 `chunk_embeddings`，避免因为没有构建索引而误判向量检索失败。
  - 新增 `data/evaluation/vector_results.csv`，记录每条问题的 passed、hit_rank、top_titles、top_scores、provider、model_name 和 baseline 对比。
  - 向量评测会读取 `data/evaluation/keyword_results.csv`，生成 `same_pass`、`keyword_only_pass` 等对比标记。
  - 新增 `tests/test_evaluate_vector_search.py`，覆盖评测命中判断、top_k 覆盖、关键词 baseline 读取和结果写出。
  - 首次运行评测脚本时遇到超时，定位为首次索引写入时逐条 commit 成本过高。
  - 将 `ChunkEmbeddingRepository.save_embedding()` 增加 `commit` 参数，并让 `VectorIndexService` 按 batch 提交，显著减少首次索引构建的磁盘写入次数。
  - 真实评测结果：向量检索 11/15 通过，关键词 baseline 15/15 通过；4 条 `keyword_only_pass` 作为后续优化样例。
- Failure cases recorded:
  - `filling_capacity_en`: 英文 `filling capacity rock-filled concrete` 未命中期望填充能力资料。
  - `mesoscopic_modeling`: 中文细观/数值/模拟未召回期望 mesoscopic/simulation 资料。
  - `peridynamics`: 专有方法 Peridynamics 未命中对应全文。
  - `construction_management`: `CIM4R construction information management` 未命中施工信息管理题录。
- Files created/modified:
  - `scripts/evaluate_vector_search.py` created
  - `data/evaluation/vector_results.csv` created
  - `tests/test_evaluate_vector_search.py` created
  - `app/db/repositories.py` modified
  - `app/services/retrieval/vector_index.py` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified
  - `docs/stage2_learning_notes.md` modified

### Phase 6: 阶段收尾文档
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 更新 `README.md`，同步阶段 2 已完成、当前功能、向量索引命令、向量评测命令、测试数量和阶段 2 面试表达。
  - 更新 `docs/progress.md`，作为权威进度记录补充阶段 2 完成内容、验证结果、遗留问题和阶段 3 下一步。
  - 更新 `docs/architecture.md`，补充阶段 2 的 embedding provider、chunk_embeddings、向量索引构建、向量检索 API 和评测链路。
  - 更新 `AGENT.MD`，将“当前推荐的第一步”从阶段 2 启动校准为阶段 3 引用式问答。
  - 更新 Obsidian 首页、阶段索引、分类索引、阶段 2 页面、分类页和阶段 2 知识点。
  - 新增 Obsidian 分类 `RAG 链路`。
  - 新增 Obsidian 知识点：`EmbeddingProvider 抽象`、`chunk embedding 保存结构`、`向量索引构建服务`、`向量检索服务与 API`、`向量检索评测对比`。
  - 更新 `docs/stage2_learning_notes.md`，新增步骤 6：阶段收尾文档。
  - 将 `task_plan.md` 当前阶段更新为 `Stage 2 complete`，并将 Phase 6 标记为完成。
- Files created/modified:
  - `README.md` modified
  - `docs/progress.md` modified
  - `docs/architecture.md` modified
  - `AGENT.MD` modified
  - `task_plan.md` modified
  - `progress.md` modified
  - `docs/stage2_learning_notes.md` modified
  - `obsidian-vault/首页.md` modified
  - `obsidian-vault/阶段索引.md` modified
  - `obsidian-vault/分类索引.md` modified
  - `obsidian-vault/阶段/阶段 2 - Embedding 与向量检索.md` replaced
  - `obsidian-vault/分类/RAG 链路.md` created
  - `obsidian-vault/分类/API 设计.md` modified
  - `obsidian-vault/分类/数据工程.md` modified
  - `obsidian-vault/分类/测试与验证.md` modified
  - `obsidian-vault/分类/后端工程.md` modified
  - `obsidian-vault/知识点/EmbeddingProvider 抽象.md` created
  - `obsidian-vault/知识点/chunk embedding 保存结构.md` created
  - `obsidian-vault/知识点/向量索引构建服务.md` created
  - `obsidian-vault/知识点/向量检索服务与 API.md` created
  - `obsidian-vault/知识点/向量检索评测对比.md` created

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| embedding provider unit tests | `python -m pytest tests/test_embedding_provider.py -q` | pass | 7 passed | pass |
| compile embedding files | `python -m py_compile app/services/retrieval/embedding.py tests/test_embedding_provider.py` | pass | pass | pass |
| chunk embedding repository tests | `python -m pytest tests/test_db_models.py tests/test_repositories.py -q` | pass | 5 passed | pass |
| compile db files | `python -m py_compile app/db/models.py app/db/repositories.py tests/test_db_models.py tests/test_repositories.py` | pass | pass | pass |
| vector index service tests | `python -m pytest tests/test_vector_index_service.py -q` | pass | 5 passed | pass |
| compile vector index files | `python -m py_compile app/services/retrieval/vector_index.py scripts/build_vector_index.py tests/test_vector_index_service.py` | pass | pass | pass |
| vector search compile | `python -m py_compile app/services/retrieval/vector_search.py app/api/search.py app/schemas/search.py tests/test_vector_search.py tests/test_vector_search_api.py` | pass | pass | pass |
| vector search service and API tests | `python -m pytest tests/test_vector_search.py tests/test_vector_search_api.py -q` | pass | 7 passed | pass |
| keyword/vector regression tests | `python -m pytest tests/test_search_api.py tests/test_keyword_search.py tests/test_vector_index_service.py -q` | pass | 11 passed | pass |
| chunk embedding regression tests | `python -m pytest tests/test_db_models.py tests/test_repositories.py -q` | pass | 5 passed | pass |
| vector evaluation compile | `python -m py_compile scripts/evaluate_vector_search.py tests/test_evaluate_vector_search.py` | pass | pass | pass |
| vector evaluation tests | `python -m pytest tests/test_evaluate_vector_search.py -q` | pass | 3 passed | pass |
| vector evaluation run | `python scripts/evaluate_vector_search.py` | write vector results | vector 11/15, keyword baseline 15/15 | pass |
| vector evaluation regression tests | `python -m pytest tests/test_vector_search.py tests/test_vector_search_api.py tests/test_evaluate_vector_search.py -q` | pass | 10 passed | pass |
| stage 2 documentation sync | README/docs/architecture/docs/progress/AGENT/Obsidian updated | docs reflect Stage 2 complete | complete | pass |
| full test suite after Phase 1 | `python -m pytest -q` | pass | 45 passed | pass |
| full test suite after Phase 2 | `python -m pytest -q` | pass | 48 passed | pass |
| full test suite after Phase 3 | `python -m pytest -q` | pass | 53 passed | pass |
| full test suite after Phase 4 | `python -m pytest -q` | pass | 60 passed | pass |
| full test suite after Phase 5 | `python -m pytest -q` | pass | 63 passed | pass |
| full test suite after Phase 6 | `python -m pytest -q` | pass | 63 passed | pass |
| final vector evaluation after Phase 6 | `python scripts/evaluate_vector_search.py` | write vector results | vector 11/15, keyword baseline 15/15 | pass |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-06-05 | `Sequence` duplicated import in repository edit | 1 | Removed `typing.Sequence` and kept `collections.abc.Sequence` |
| 2026-06-05 | Used Python 3.12-only `def batched[T]` syntax while project supports Python 3.11 | 1 | Replaced with `TypeVar`-based generic helper |
| 2026-06-05 | First `scripts/evaluate_vector_search.py` run timed out before printing summary | 1 | Confirmed 997 embeddings were written, optimized `VectorIndexService` to batch commit, then reran evaluation successfully |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Stage 2 complete，准备进入阶段 3: 引用式问答 |
| Where am I going? | 阶段 3 -> ChatModelProvider、上下文组织、POST /chat、引用来源和拒答 |
| What's the goal? | 完成可测试、可替换、可评测的 embedding 与向量检索链路 |
| What have I learned? | 见 `findings.md` |
| What have I done? | 创建阶段 2 规划，完成 Embedding Provider 抽象、chunk embedding 保存结构、向量索引构建服务、向量检索 API、向量检索评测对比和阶段收尾文档同步 |
