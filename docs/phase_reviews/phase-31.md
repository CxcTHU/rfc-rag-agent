# 阶段 31 验收草稿：FAISS 向量索引与父子块检索

## 验收结论

当前结论：`PASS for human review`。阶段 31 的开发、测试、普通文档和 Obsidian 草稿已完成；最终状态必须停在用户人工核验前。当前不允许 `git add`、`git commit`、`git tag`、`git push` 或创建 PR，也不要创建 `phase-31-complete` tag。

## 范围对齐

- 已从阶段 30 完成并合并后的 `main -> e74ce78 Complete phase 30 rag evaluation scoring system` 出发。
- 已核对 `phase-30-complete -> e74ce78`，且与 `main` 指向同一提交。
- 当前分支：`codex/phase-31-faiss-parent-child-retrieval`。
- 未移动任何已有阶段 tag。
- 未引入 Qdrant、Chroma、PGVector、torch、sentence-transformers、新爬虫、写入型 Agent 工具、登录系统或部署优化。

## 功能证据

- 新增 `docs/stage31_faiss_parent_child_retrieval.md`，记录 FAISS 索引类型、父子块 schema、检索流程、安全边界和完成标准。
- 新增 `app/services/retrieval/faiss_index.py`，封装 FAISS `IndexFlatIP` 构建、保存、加载和搜索。
- 新增 `scripts/build_faiss_index.py`，可从现有 `chunk_embeddings` 构建本地 `.index` 文件。
- `data/faiss/` 已加入 `.gitignore`，FAISS 索引文件不进 Git。
- `VectorIndexCache` 优先使用完整 FAISS 索引；索引缺失、不完整、不匹配或加载失败时 fallback numpy。
- `chunks` 表新增 `parent_chunk_id` 可空自引用字段；新增 `scripts/migrate_parent_chunks.py` 并已在本地 SQLite 执行迁移。
- 新增 `app/services/ingestion/parent_chunker.py` 和 `app/services/retrieval/parent_child_search.py`，实现 parent/child 切分计划和 child 命中到 parent 上下文扩展。
- `BrainService` 在 prompt 组装前接入 parent context；引用仍指向检索命中的 child。
- 新增 `scripts/backfill_parent_chunks.py`，已将既有 12,716 个 child 非破坏性关联到 6,402 个新增 parent；parent 不生成 embedding，不进入 FAISS。
- `prompt_builder.py` 已强化引用密度、直接回答、对比类问题双边说明和错误前提纠正规则。
- 前端首页把 Agent 高级参数收入“高级设置”折叠区。

## 验证证据

```text
python scripts\build_faiss_index.py --provider jina --model-name jina-embeddings-v3 --dimension 1024
FAISS full index: vectors=12716
```

```text
python scripts\backfill_parent_chunks.py --dry-run
parent_reused=6402 child_updated=0

database check:
chunks=19118 parent_rows=6402 linked_children=12716 parent_embeddings=0 embeddings=25432
```

```text
python -m pytest tests\test_faiss_index.py tests\test_vector_cache_faiss.py tests\test_parent_child_retrieval.py tests\test_migrate_parent_chunks.py tests\test_frontend_app.py -q
24 passed
```

```text
python -m pytest tests\test_backfill_parent_chunks.py tests\test_faiss_index.py tests\test_vector_index_service.py -q
15 passed

python -m pytest tests\test_prompt_builder.py tests\test_backfill_parent_chunks.py -q
13 passed
```

```text
python scripts\score_stage30_quality.py
overall=83.17 grade=B release_decision=review_required
```

```text
python -m pytest -q
593 passed, 1 warning
```

接口与浏览器验证：

```text
GET /health 200
GET /quality-report 200
POST /search 200
POST /search/vector 200
POST /search/hybrid 200
POST /chat 200
POST /agent/query 200

Backfill 后 8000 复验：上述核心接口仍全部为 200。

Browser /: 高级设置默认收起，展开后可使用 top_k / max_tool_calls / source_id
Browser /quality-report: overall=83.17, grade=B, release_decision=review_required
console errors=0
```

## 安全合规

- FAISS 构建脚本不调用真实 API、不重建 embedding、不写数据库。
- 默认测试和全量测试仍不把真实 API 作为 CI 前提；阶段 31 额外完成了真实 provider 本地冒烟。
- FAISS `.index` 与 `_ids.json` 是可重建派生产物，不提交。
- 未写入 API key、Bearer token、Authorization header、供应商原始响应、raw_response 或受限全文。

## 人工核验清单

- 打开首页，确认 Agent 高级设置默认收起，展开后仍可填写 `top_k`、`max_tool_calls`、`source_id`。
- 打开 `/quality-report`，确认阶段 30 评分仍为 `overall=83.17`、`grade=B`、`release_decision=review_required`。
- 运行一次 deterministic provider 的 `/search/vector` 与 `/search/hybrid`，确认均返回 200。
- 抽查 `VectorIndexCache` 在有完整 FAISS 索引时使用 FAISS、无索引时 fallback numpy。
- 抽查带 `parent_chunk_id` 的 child 检索结果，确认 prompt context 来自 parent，但引用 chunk_id 仍指向 child。
- 复查真实 provider 配置：当前本地已将 `EMBEDDING_PROVIDER` 调整为 `jina`，并已验证真实 `/search/vector`、`/search/hybrid`、`/chat`、`/agent/query` 均为 200。

## 当前遗留

- 既有全量语料已完成非破坏性 parent backfill；后续人工核验重点是抽样检查 parent 上下文长度、位置匹配和回答引用是否仍指向 child。
- SQLite 对已有表通过 `ALTER TABLE` 添加字段，不能在该路径上补完整数据库级外键约束；当前通过 ORM relationship、应用层逻辑和测试控制风险。
- 阶段 30 质量门禁仍为 `review_required`，阶段 31 没有伪造成 pass。
- 真实 provider 500 已修复；后续如果换网络或代理，仍建议先用 provider 小请求确认 Jina embedding、Jina rerank 和 MIMO chat 可用。

## 面试表达

阶段 31 我先把 RAG 的底层检索能力补强，而不是继续叠功能。向量检索上，我用 FAISS `IndexFlatIP` 替代 numpy 全量扫描，归一化后内积等价于余弦相似度，所以能保持旧排序语义，也能为后续 HNSW 或更大规模索引留接口。上下文上，我引入父子块：child 负责 embedding、精准召回和引用，parent 负责提供完整回答上下文。这样解决了“小 chunk 命中准但上下文不够”的问题，同时通过 `parent_chunk_id` 可空字段兼容旧数据。
