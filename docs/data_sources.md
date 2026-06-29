# 数据来源登记

## Phase 57 Multi-Channel Retrieval Data Boundary

Phase 57 adds no external corpus, crawler, PDF download, source registry entry, model weight, embedding rebuild, or user-profile data. It reuses existing PostgreSQL chunks, existing GraphRAG derived graph data, table chunks, and image-description chunks as retrieval candidate channels.

New artifacts:

```text
docs/stage57_multichannel_hybrid_retrieval_goal_prompt.md
docs/stage57_multichannel_hybrid_retrieval_design.md
docs/phase_reviews/phase-57.md
scripts/evaluate_phase57_default_chain.py
data/evaluation/phase57_default_chain_eval.csv
obsidian-vault/阶段汇报/阶段 57 - 多通道混合检索与默认链路真实评测/Phase 57 - 多通道混合检索与默认链路真实评测.md
```

The Phase 57 evaluator is dry-run by default. With `--execute`, it calls the default `/agent/query` path and records sanitized metadata only: case id, category, config, status, latency, tool/workflow names, source/citation counts, channel counts, selected chunk ids, short source title/type previews, refusal/cache/reranker labels, and sanitized errors. It must not store full answers, full chunks, provider raw responses, API keys, bearer tokens, Authorization headers, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, private service logs, or raw uploaded images.

Latest real run:

```text
cases=30 rows=30 completed=30 errors=0 channel_rows=22 median_elapsed_ms=28734.723
```

The committed CSV is an evaluation metadata artifact, not a content source. It contains no full answer text, full chunk bodies, provider payloads, secrets, or restricted full text.

## Phase 56 Layered Cache Data Boundary

Phase 56 adds no external corpus, crawler, PDF download, source registry entry, model weight, embedding rebuild, or user-profile data. It adds derived runtime cache entries and sanitized evaluation output only.

Runtime Redis cache entries may contain:

```text
normalized query hash / cache identity hash
hashed stable user-question cache key
chunk ids
safe numeric scores
chunk/source labels
candidate id hash
reranker provider/model labels
retrieval candidate and selected chunk id previews
selected source title/source_type previews
cache hit/fallback booleans
TTL and created_at metadata
```

Runtime Redis cache entries must not contain:

```text
API keys
Bearer tokens
JWT or Redis passwords
provider raw responses
hidden reasoning
full final answers
full chunk text as the durable cache contract
restricted full text
long-term user profiles
raw uploaded image bytes
```

New Phase 56 artifacts:

```text
app/services/cache/layered_cache.py
app/frontend/static/app.js
scripts/evaluate_phase56_layered_cache.py
scripts/evaluate_phase56_real_chain_cache.py
tests/test_phase56_layered_cache.py
tests/test_hybrid_search.py
data/evaluation/phase56_layered_cache_eval.csv
data/evaluation/phase56_real_chain_cache_eval.csv
docs/phase_reviews/phase-56.md
```

The fixture and real-chain evaluation CSVs store scenario/case labels, cold/warm run labels, elapsed milliseconds, cache-hit booleans, backend labels, source/citation counts, tool/workflow names, top source type/title previews, evidence-chain field-presence booleans, selected counts, and dynamic-K status only. They do not store answer text, provider payloads, full chunks, source PDFs, image bytes, secrets, or restricted full text.

## Phase 55 Production Readiness Data Note

Phase 55 adds production readiness and operations artifacts only. It does not add a corpus source, crawler, PDF download, model weight, embedding rebuild, source registry entry, or new runtime content.

New Phase 55 artifacts:

```text
docs/phase55_production_readiness.md
docs/phase55_completion_audit.md
scripts/audit_phase55_production_readiness.py
scripts/check_phase55_runtime_readiness.py
data/evaluation/phase55_production_readiness_audit.csv
data/evaluation/phase55_runtime_readiness.csv
data/evaluation/phase55_production_smoke_dry_run.csv
updated scripts/run_production_smoke.py auth-enabled mode
```

The readiness audit, runtime readiness audit, and smoke dry-run record requirement ids, endpoint ids, statuses, counts, short evidence, and next actions. They do not print `.env`, `.env.prod`, production database passwords, JWT secrets, Redis passwords, API keys, bearer tokens, provider raw responses, full chunks, restricted full text, source PDFs, image bytes, FAISS files, or graph JSON contents.

Actual production smoke and server data checks must run on the CPU server with local-only `.env.prod`. Those runtime results should be recorded as sanitized pass/fail evidence only, never as secrets or response bodies.

## Phase 54 GraphRAG Derived Data Note

Phase 54 adds no external corpus, crawler, PDF download, source registry entry, model weight, or embedding rebuild. It derives GraphRAG extraction and evaluation artifacts from existing local chunks.

New derived artifacts include:

```text
docs/phase54_formal_judge_runbook.md
docs/phase54_completion_audit.md
scripts/evaluate_phase54_extraction_sample.py
scripts/review_phase54_extraction_sample.py
scripts/extract_phase54_graphrag_full.py
scripts/plan_phase54_llm_coverage.py
scripts/evaluate_phase54_graphrag_e2e.py
data/evaluation/phase54_* CSV/JSON summaries
data/evaluation/phase54_completion_audit.csv
data/knowledge_graph/extraction_regex.json
data/knowledge_graph/extraction_text_chunks.json
data/knowledge_graph/extraction_table_chunks.json
data/knowledge_graph/extraction_merged.json
data/knowledge_graph/domain_graph.json
```

`data/knowledge_graph/` is gitignored derived runtime data. The committed evaluation files contain chunk ids, document ids, short titles/headings, scores, counts, title hashes, answer lengths, statuses, and judge metrics only. They must not contain full chunk content, raw model answers, provider payloads, API keys, Bearer tokens, Authorization headers, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, or service logs.

Formal Phase 54D quality conclusions require explicit `--execute` with a configured judge provider. Dry-run, retrieval-only, and answer-only rows are operational evidence only.

## Phase 53 GraphRAG Data Note

Phase 53 adds no external corpus, crawler, PDF download, source registry entry, model weight, or embedding rebuild. It adds derived GraphRAG artifacts from existing local chunks and manually authored evaluation questions:

```text
scripts/extract_phase53_graphrag_triples.py
scripts/build_phase53_graphrag_graph.py
scripts/evaluate_phase53_graphrag_ablation.py
data/evaluation/phase53_graphrag_queries.csv
data/evaluation/phase53_graphrag_ablation_results.csv
data/evaluation/phase53_graphrag_ablation_summary.csv
data/evaluation/phase53_graphrag_ablation.csv
```

Expected optional derived graph artifacts, generated only when local extraction/build scripts are run:

```text
data/evaluation/phase53_graphrag_triples_sample.json
data/evaluation/phase53_graphrag_graph.json
data/evaluation/phase53_graphrag_graph_stats.json
```

The extraction and graph JSON files store chunk ids, document ids, short titles, entity labels, relation labels, graph node/edge metadata, counts, and sanitized status only. They must not store full chunk bodies, restricted full text, provider payloads, hidden reasoning, credentials, or service logs.

LLM extraction is disabled by default and requires explicit `execute_llm=True` or script `--execute`. The Phase 53 ablation runner is dry-run by default and writes strategy/count labels only.

## RFC-DomainReranker Stage 3 Data Note

Stage 3 adds no new corpus source, crawler, PDF download, training dataset, model weight, embedding rebuild, or provider raw-response artifact. It adds code and derived evaluation outputs for comparing rerankers on existing RAG evaluation queries.

New code paths:

```text
scripts/reranker/serve_lora_reranker.py
scripts/reranker/evaluate_rag_reranker_ab.py
tests/test_rfc_domain_reranker_stage3.py
```

Expected derived outputs, generated only when the Stage 3 evaluator is run:

```text
data/evaluation/stage3_reranker_ab_results.csv
data/evaluation/stage3_reranker_ab_summary.csv
data/evaluation/stage3_reranker_candidate_snapshot.jsonl
data/evaluation/stage3_reranker_pool_ab_results.csv
data/evaluation/stage3_reranker_pool_ab_summary.csv
```

The candidate snapshot stores only `query_id`, candidate hash/id, `chunk_id`, rank, source type, title summary, score, and relevance flag. It must not store full chunk content, full candidate text, API keys, Bearer tokens, Authorization headers, provider raw responses, `raw_response`, `reasoning_content`, hidden thoughts, restricted full text, training data, model weights, or service logs.

Real GLM reranking requires `--execute-glm`. Remote BGE LoRA reranking requires `--remote-bge-url` or local private configuration. The local Windows worktree must not load BGE, run CUDA, or download Hugging Face models.

Final Stage 3 validation used the existing local evaluation database and explicit runtime provider configuration only. The GLM reranker API key was loaded from the other local worktree `.env` into process environment and was not copied into this worktree. The BGE LoRA model and adapter remained on the GPU server at `models/bge-reranker-base-rfc-lora`; no model weight or adapter file was copied into Git.

The generated Stage 3 CSV/JSONL outputs contain metrics, ids/hashes, source type, title summary, ranks, scores, relevance flags, latency, and sanitized status only. They do not contain full chunk bodies, server passwords, API keys, Bearer tokens, Authorization headers, raw GLM responses, BGE logits, hidden reasoning, service logs, or model weights.

The pool/top-k ablation CSVs reuse the existing Stage 3 query labels and store candidate-pool/top-k settings, summary metrics, title summaries, ids, latency, and sanitized errors. They do not add a new evaluation corpus and do not store full candidate text.

## Phase 52 Real API Memory Evaluation Data Note

Phase 52 real API memory evaluation adds no external corpus, crawler, PDF download, source registry entry, production table, or embedding rebuild. It adds manually authored evaluation scenarios and derived real API result files only:

```text
data/evaluation/phase52_memory_real_api_cases.csv
data/evaluation/phase52_memory_real_api_results.csv
data/evaluation/phase52_memory_real_api_summary.csv
data/evaluation/phase52_memory_real_api_ablation.csv
scripts/evaluate_phase52_memory_real_api.py
docs/phase_reviews/phase-52-real-api-memory-eval.md
```

The case CSV contains synthetic conversation scenarios, expected labels, and short sanitized prior-answer summaries. It is not a new knowledge source and does not add document chunks. The formal run uses configured real chat, embedding, and judge APIs only when `--execute` is explicitly passed.

The result CSVs store case ids, categories, structured memory-policy labels, model/provider names, numeric scores, safe latency, and sanitized short judge reasons. They do not store API keys, bearer tokens, Authorization headers, provider raw responses, `raw_response`, `reasoning_content`, hidden thoughts, complete chunks, restricted full text, raw model answers, or long-term user profiles.

## Phase 52 Agent Memory Data Note

Phase 52 adds no external data source, crawler, PDF download, corpus row, embedding rebuild, or provider raw-response artifact. It derives short-lived memory context only from:

```text
current conversation history
latest LangGraph checkpoint prior sources/citations/answer summary
existing deterministic memory regression CSV
```

New derived artifacts:

```text
data/evaluation/phase52_memory_regression_cases.csv
data/evaluation/phase52_memory_regression_results.csv
data/evaluation/phase52_memory_regression_summary.csv
scripts/evaluate_phase52_memory.py
```

The CSVs store case ids, memory decision labels, policy routes, prior relevance scores/pass flags, safe memory usage flags, action labels, counts, pass/fail status, and disabled long-term memory flags. They do not store API keys, bearer tokens, Authorization headers, provider raw responses, `raw_response`, `reasoning_content`, hidden thoughts, complete chunks, restricted full text, or long-term user profiles.

The long-term memory governance interfaces added in Phase 52 are code contracts only. They do not create a production table, write user profile data, store deletion reasons, or add a persistence data source.

## Phase 51 Performance Evaluation Data Note

Phase 51 adds no external data source, crawler, PDF download, corpus row, embedding rebuild, or provider raw-response artifact. It adds derived evaluation artifacts only:

```text
scripts/evaluate_phase51_performance.py
tests/test_phase51_performance_eval.py
data/evaluation/phase51_performance_results.csv
data/evaluation/phase51_performance_summary.csv
docs/phase_reviews/phase-51.md
```

The real-provider evaluation reads the existing local database and provider configuration only when `--execute` is explicitly used. CSV outputs store configuration ids, latency metrics, backend labels, cache-hit flags, citation/source counts, and sanitized error summaries. They do not store API keys, Bearer tokens, Authorization headers, provider raw responses, `raw_response`, `reasoning_content`, hidden thoughts, restricted full text, or raw sensitive content.

## Phase 50 Planner Fast Model Data Note

Phase 16-17 adds no external data source, crawler, PDF download, corpus row, embedding rebuild, or provider raw-response artifact. It only adds an optional runtime planner model for LangGraph route selection.

Planner prompts contain action descriptions, the current user question, and short observation summaries. Tests use fake providers only. Docs, tests, CSVs, and Obsidian do not store API keys, bearer tokens, raw provider responses, `raw_response`, `reasoning_content`, hidden thoughts, or restricted full text.

## Phase 50 LangGraph Redis Data Note

Phase 50 adds no crawler, no external literature source, no new PDF download, and no new production corpus category. It adds runtime cache/checkpoint storage and deterministic evaluation artifacts only.

Runtime data introduced:

```text
Redis key emb:{provider}:{model}:{dimension}:{sha256(normalized_query)}
-> cached query embedding JSON
-> TTL controlled by existing query embedding cache settings
-> fallback to in-memory QueryEmbeddingCache when Redis is unavailable
```

```text
LangGraph checkpoint
-> RedisSaver when RedisJSON / RediSearch are available
-> MemorySaver fallback otherwise
-> keyed by configurable thread_id
```

New deterministic evaluation artifacts:

```text
scripts/evaluate_phase50_langgraph_vs_react.py
data/evaluation/phase50_langgraph_vs_react_results.csv
data/evaluation/phase50_langgraph_vs_react_summary.csv
tests/test_phase50_langgraph_eval.py
```

The evaluation script uses an in-memory SQLite fixture and deterministic providers by default. CSV rows contain mode, status, refusal summary, tool/iteration counts, safe latency metrics, citation/source counts, top source id, cache/checkpointer backend, and short safe error summaries. They must not contain API keys, bearer tokens, Authorization headers, provider raw responses, `raw_response`, `reasoning_content`, hidden reasoning, full restricted text, or user-uploaded sensitive bytes.

## Phase 49 Local PostgreSQL And Cloud Sync Data Note

Phase 49 adds no crawler, no external literature source, no new PDF download, no new provider topology, and no new production corpus category. It moves existing local project data from SQLite into local PostgreSQL, then synchronizes that PostgreSQL state plus image assets to the cloud deployment.

Data movement:

```text
data/app.sqlite
-> local PostgreSQL 16 dev database on localhost:5433
-> documents / sources / chunks / chunk_embeddings / qa_logs
-> users / conversations / messages / qa_feedback
-> FAISS rebuilt from PostgreSQL embeddings
```

The SQLite database remains a local backup/golden source and is not deleted. PostgreSQL is the active local runtime database after `.env` points `DATABASE_URL` to PostgreSQL. The migration is idempotent: a second run inserts no duplicate rows.

Local migrated counts:

```text
documents=1146
sources=1073
chunks=50250
chunk_embeddings=72579
users=3
conversations=7
messages=117
image_description chunks=15628
table chunks=1440
GLM vectors for FAISS=40563
```

Image assets:

```text
data/images/ files=16978
data/images/ directories=854
PostgreSQL image chunks with paths=15628
```

`data/images/` is still a gitignored runtime asset directory. It must be synchronized to the cloud separately from PostgreSQL rows so `/assets/images/...` can serve figure evidence. Phase 49 synchronized 16978 image files to the cloud server; a public check against `http://36.103.199.132:8044/assets/images/1059/page10_img1.png` returned 200 after sync.

Safety boundary: Phase 49 docs and tests store only counts, local paths, command templates, and placeholder variables. They must not store database passwords, JWT secrets, SSH passwords, API keys, bearer tokens, Authorization headers, provider raw responses, `raw_response`, `reasoning_content`, hidden reasoning, full restricted text, or sensitive uploaded-image bytes.

## Phase 48 Real Multimodal Evaluation Data Note

Phase 48 adds no new literature corpus, crawler, restricted full text, or production source registry. It operates on the existing local corpus plus a local-only public-image evaluation set for uploaded-image analysis.

New derived artifacts include:

- `data/evaluation/phase48_summary.json`
- `data/evaluation/phase48_table_backfill_summary.json`
- `data/evaluation/phase48_image_edge_questions.csv`
- `data/evaluation/phase48_user_image_questions.csv`
- `data/evaluation/phase48_table_retrieval_questions.csv`
- `data/evaluation/phase48_*_results.csv`
- `data/evaluation/phase48_*_summary.csv`
- `scripts/evaluate_phase48_image_edge.py`
- `scripts/evaluate_phase48_user_image.py`
- `scripts/evaluate_phase48_table_retrieval.py`
- `docs/phase48_evaluation_report.md`
- `docs/phase_reviews/phase-48.md`

`data/evaluation/phase48_user_images/` contains local downloaded public evaluation images and is gitignored. Repository files intentionally do not record original image download URLs. The set is for evaluation only and does not enter the production knowledge base.

Real GLM-4.6V and GLM-Embedding-3 were used for Phase 48 evaluation runs and local derived embeddings. CSVs and docs store only local filenames, ids, counts, metrics, and keyword-hit summaries. They do not store API keys, bearer tokens, Authorization headers, vendor raw responses, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, or original public image URLs.

## Phase 46 Image Repair And Caption Data Note

Phase 46 adds no new external literature source, crawler, PDF download, or restricted full text. It operates on the existing Phase 45 local PDF corpus, extracted images, SQLite rows, and derived embeddings.

New derived artifacts include:

- `data/evaluation/phase46_image_quality_manifest.csv`
- `data/evaluation/phase46_cleanup_report.csv`
- `data/evaluation/phase46_fragment_fix_report.csv`
- `data/evaluation/phase46_rendered_image_manifest.csv`
- `data/evaluation/phase46_redescribe_*`
- `data/evaluation/phase46_orientation_residual_*`
- `data/evaluation/phase46_caption_coverage.csv`
- `data/evaluation/phase46_caption_coverage_summary.json`
- `data/evaluation/phase46_db_stats.json`
- `data/evaluation/phase46_image_page_number_summary.json`
- `data/evaluation/phase46_image_retrieval_questions.csv`
- `data/evaluation/phase46_image_retrieval_results.csv`
- `data/evaluation/phase46_image_retrieval_summary.csv`
- `data/evaluation/phase46_real_image_retrieval_questions.csv`
- `data/evaluation/phase46_real_image_retrieval_results.csv`
- `data/evaluation/phase46_real_image_retrieval_summary.csv`
- deterministic evaluation fixture images generated under `data/images/phase46_eval_fixture/`
- page-rendered image files under `data/images/{document_id}/pageN_renderM.png`
- nullable `chunks.caption` values derived from source PDF text blocks
- nullable `chunks.page_number` values parsed from local image paths

Real GLM-4.6V was used only for local redescription of the 1,995 repaired render images through explicit route staging. CSVs and docs store only local paths, ids, statuses, counts, captions, and sanitized summaries; they must not store API keys, bearer tokens, Authorization headers, vendor raw responses, `raw_response`, `reasoning_content`, hidden reasoning, or full restricted text.

Caption extraction reads PDF text block geometry from local PDFs via PyMuPDF. Captions are derived metadata for existing image chunks and are not a new source corpus. Caption association does not change source ownership, license status, or external data boundaries.

The first Phase 46 image retrieval evaluation set and fixture images are derived local test artifacts. The fixture evaluation script uses deterministic embeddings and a temporary SQLite database, then calls the real `search_figures` tool without real provider APIs. These artifacts calibrate retrieval precision/suppression only; they do not add external literature or production corpus rows.

Phase 16-21 adds a true-corpus evaluation set derived from existing local image chunks, captions, page numbers, document titles, and image paths. It is not a new source corpus and does not add external literature. `scripts/evaluate_phase46_real_image_retrieval.py` defaults to `stored_embedding_proxy`, which uses already stored image embeddings and does not call real provider APIs. The optional `--query-embedding-mode real` path may call the configured embedding provider only when manually authorized. Results store ids, local paths, page numbers, captions/short titles, counts, and metrics; they do not store API keys, bearer tokens, vendor raw responses, `raw_response`, `reasoning_content`, hidden reasoning, or restricted full text.

## Phase 45 Additional Literature Batch Data Note

Source directory: `G:\Codex\program\papers_0618`.

This batch is user-provided local literature for domestic rock-filled concrete coverage. It was not crawled or downloaded by the system. The batch was first registered in `data/incoming/phase45_literature/manifest.csv/json`, then only `ready` rows were imported into local SQLite.

Derived artifacts include the Phase 10 manifest, Phase 11 import summaries, Phase 12 quality audit/review queue, Phase 13/14 embedding summaries, Phase 14 multimodal summaries, Phase 16 migration readiness, and Phase 17 asset sync manifest.

Safety boundary: raw PDFs, extracted images, SQLite DB state, FAISS indexes, full chunk bodies, API keys, bearer tokens, JWT secrets, plaintext passwords, provider raw responses, `raw_response`, `reasoning_content`, hidden reasoning, and restricted full text remain out of Git, docs, tests, public CSVs, and Obsidian. Real GLM-4.6V was used only for local batch processing; automated tests continue to use `DeterministicVisionModelProvider`.

## Phase 45 Data Migration And Multimodal RAG Data Note

Phase 45 adds no crawler, no new external source registry category, no new PDF download, and no restricted full text to Git. It operates on existing local corpus rows and local PDF files already represented by `documents.raw_path`.

New derived runtime artifacts:

- `data/images/{document_id}/pageN_imgM.png`: extracted PDF images, gitignored runtime files.
- `chunk_type="image_description"` rows in `chunks`: text descriptions generated from extracted images.
- chunk embeddings for those image-description rows, generated through the existing embedding provider.
- optional FAISS indexes rebuilt from target DB embeddings through `scripts/build_faiss_index.py --database-url`.

Data migration artifacts:

- `scripts/migrate_sqlite_to_postgres.py` copies existing local rows into a target database.
- Migrated tables: documents, sources, chunks, chunk_embeddings, qa_logs.
- Non-migrated runtime identity tables: users, conversations, messages.

Safety boundary:

- Extracted images are local runtime artifacts and remain out of Git.
- Vision provider tests use `DeterministicVisionModelProvider`.
- Real vision API calls require explicit local configuration and are not CI or full-test prerequisites.
- API keys, bearer tokens, JWT secrets, plaintext passwords, provider raw responses, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, and full vendor responses must not be written to Git, CSV, docs, tests, or Obsidian.

本文件用于记录后续采集的堆石混凝土相关资料来源。

## 阶段 43 多轮对话质量与生产可观测性说明

阶段 43 不新增外部资料来源，不爬新网页，不下载新 PDF，不导入受限全文，不重切 chunk，也不重建 embedding。新增内容均为多轮质量评测、会话内检索辅助记忆、request_id 追踪、健康诊断、测试、普通文档和本地 Obsidian 草稿。

新增或更新的工程/文档产物：

- `docs/stage43_multi_turn_quality_and_observability.md`
- `docs/stage43_multi_turn_judge.md`
- `docs/deployment_https_reverse_proxy.md`
- `docs/phase_reviews/phase-43.md`
- `data/evaluation/stage43_multi_turn_eval_cases.csv`
- `data/evaluation/stage43_multi_turn_baseline_results.csv`
- `data/evaluation/stage43_multi_turn_baseline_summary.csv`
- `data/evaluation/stage43_multi_turn_judge_results.csv`
- `data/evaluation/stage43_multi_turn_judge_summary.csv`
- `scripts/evaluate_stage43_multi_turn.py`
- `scripts/judge_stage43_multi_turn_quality.py`
- `deploy/nginx-https.example.conf`
- `deploy/Caddyfile.example`
- `app/services/conversation/session_memory.py`
- `app/core/request_logger.py`
- `app/core/structured_logging.py`
- `app/main.py`
- `app/api/agent.py`
- `app/api/health.py`
- `app/schemas/health.py`
- `app/services/brain/service.py`
- `tests/test_stage43_design.py`
- `tests/test_stage43_multi_turn_eval.py`
- `tests/test_session_memory.py`
- `tests/test_request_logger.py`
- `tests/test_health_details.py`
- `tests/test_stage43_multi_turn_judge.py`
- `tests/test_stage43_https_templates.py`
- `obsidian-vault/阶段/阶段 43 - 多轮对话质量与生产可观测性强化.md`
- `obsidian-vault/阶段汇报/阶段 43 - 多轮对话质量与生产可观测性强化/`

数据与日志边界：

- Stage 43 多轮评测集是人工编写的对话场景与期望指标，不是新的外部资料来源。
- Stage 43 多轮 Judge CSV 是由现有评测集、现有 RAG 链路和真实 Judge 派生的脱敏评测结果，不是新的资料来源；真实 API 只在显式 `--execute` 中调用。
- `SessionMemory(entities, retrieval_anchors)` 只来自当前 conversation history，只辅助 query rewrite / retrieval，不作为引用来源，不跨会话持久化，不形成用户画像。
- JSONL request trace 写入 `data/logs/request_traces.jsonl`，目录已 gitignore；trace 只保存脱敏摘要。
- `/health/details` 只做本地 DB、FAISS 文件/metadata、provider 配置状态检查，不做外部 provider ping。
- HTTPS reverse proxy 文件只是配置模板，不包含真实域名证书、密钥或部署 secret，不改变数据源边界。
- 不把 API key、Bearer token、Authorization header、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk 全文或受限全文写入 Git、CSV、文档、测试或 Obsidian。

## 阶段 42 生成质量校准与生产体验说明

阶段 42 不新增外部资料来源，不爬新网页，不下载新 PDF，不导入受限全文，不重切 chunk，也不重建 embedding。新增内容均为生成质量评测派生产物、prompt 校准、前端体验、会话管理、测试、普通文档和本地 Obsidian 草稿。

新增或更新的工程/文档产物：

- `docs/stage42_generation_quality_and_experience.md`
- `docs/phase_reviews/phase-42.md`
- `scripts/judge_stage42_generation_quality.py`
- `data/evaluation/stage42_generation_judge_results.csv`
- `data/evaluation/stage42_generation_judge_summary.csv`
- `data/evaluation/stage42_generation_low_score_analysis.csv`
- `app/services/agent/tool_calling_service.py`
- `app/api/conversations.py`
- `app/db/repositories.py`
- `app/schemas/conversation.py`
- `app/frontend/index.html`
- `app/frontend/static/app.js`
- `app/frontend/static/styles.css`
- `tests/test_stage42_design.py`
- `tests/test_stage42_generation_judge.py`
- `obsidian-vault/阶段/阶段 42 - 生成质量校准与生产体验完善.md`
- `obsidian-vault/阶段汇报/阶段 42 - 生成质量校准与生产体验完善/`

Judge 语料边界：

- Stage 42 Judge 评测集由既有 Stage 38 24 条 generation-quality cases 与 Stage 41 12 条 post-import retrieval queries 组合而成。
- Stage 41 queries 只引用已有评测问题、期望来源和目标类别，不写入新增全文。
- 真实 Judge 需要显式 `--execute`，默认 dry-run 不调用真实 provider。
- CSV 只保存脱敏分数、短理由、风险等级、next_action 和错误摘要，不保存 raw provider response、raw answer、`raw_response`、`reasoning_content`、hidden thought、API key、Bearer token 或受限全文。

数据安全边界：

- 不改变资料来源归属、source_type、数据库 schema 或 embedding 边界。
- 不把 API key、Bearer token、Authorization header、供应商原始响应、`reasoning_content`、hidden thought、完整 chunk 全文或受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 浏览器 smoke 只记录 UI 状态、控制台错误和横向溢出结论，不保存回答全文或供应商响应。

## 阶段 40 流式输出体验与输出安全说明

阶段 40 的流式输出体验与输出安全开发不新增外部资料来源，不爬新网页，不下载新 PDF，不导入受限全文，不重切 chunk，也不重建 embedding。新增内容是前端安全渲染、停止生成、token 渲染节流、测试、普通文档和 Obsidian 草稿。

新增或更新的工程/文档产物：

- `docs/stage40_streaming_output_safety.md`
- `docs/phase_reviews/phase-40.md`
- `app/frontend/index.html`
- `app/frontend/static/app.js`
- `app/frontend/static/styles.css`
- `tests/test_stage40_streaming_output_safety.py`
- `tests/test_frontend_app.py`
- `obsidian-vault/阶段汇报/阶段 40 - 流式输出体验与输出安全/`
- `obsidian-vault/阶段/阶段 40 - 流式输出体验与输出安全.md`

数据安全边界：

- 不把 API key、Bearer token、Authorization header、供应商原始响应、`reasoning_content`、hidden thought、完整 chunk 全文或受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 前端 sanitizer 只处理最终渲染 HTML，不改变资料来源归属，也不生成新语料。
- 浏览器 smoke 只记录安全状态、控制台错误和横向溢出结论，不保存 response body 或受限全文。

## 阶段 40 数据说明

阶段 40 开始补齐中文行业标准/规程语料。新增内容只包含公开题录、范围级摘要、纠错说明和检索关键词；没有下载或提交受版权、购买或机构访问限制的标准全文。

新增数据产物：

- `scripts/seed_chinese_standards_metadata.py`
- `data/imports/chinese_standards_metadata/`
- `data/corpus_expansion/chinese_standards_metadata.csv`
- `data/evaluation/stage40_chinese_standards_results.csv`
- `docs/stage40_corpus_expansion.md`

新增中文标准题录：

- `NB/T 10077-2018`《堆石混凝土筑坝技术导则》
- `DL/T 5806-2020`《水电水利工程堆石混凝土施工规范》
- `GB 50496-2018`《大体积混凝土施工标准》
- `SL/T 352-2020`《水工混凝土试验规程》
- `DL/T 5330-2015`《水工混凝土配合比设计规程》
- `SL 314-2018`《碾压混凝土坝设计规范》，作为用户原标准号纠错和 RCC 对照标准，不标为 RFC 专门标准。
- `DB52/T 1545-2020`《堆石混凝土拱坝技术规范》，作为已废止历史地方标准记录。

当前语料计数核验：

```text
standard_document: 9 -> 16
open_access_pdf: 15 -> 15
metadata_record: 115
institutional_access_pdf: 325
wikipedia: 25
```

OpenAlex 二次筛选结果：

```text
queries: rock-filled concrete durability; RFC dam seismic; self-compacting concrete large aggregate
license_policy: cc-by-or-cc0
discovered=238 relevant=91
permissive_oa_with_pdf=10
downloaded_this_run=9
imported=0 duplicate=9
```

数据安全边界：

- 标准卡片只保存公开题录和范围级信息，不保存标准正文条文。
- `data/fulltext/` 和本地 SQLite 仍由 `.gitignore` 排除。
- `CC-BY-NC`、`CC-BY-NC-ND` 等非严格 `CC-BY/CC0` 论文不进入本轮自动下载。
- 如用户后续提供购买或机构授权的标准全文，应以 `institutional_access` 本地保存，并继续避免进入 Git。

## 阶段 39 数据说明

阶段 39 不新增外部资料来源、不爬新网页、不下载新 PDF、不写入新的受限全文，也不重切语料或重建 chunk embedding。新增内容均为部署、日志、前端体验、配置模板、测试和文档派生产物。

新增或更新的主要工程/文档产物：

- `docs/stage39_production_deployment.md`
- `docs/deployment_guide.md`
- `docs/phase_reviews/phase-39.md`
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `.env.example`
- `app/core/structured_logging.py`
- `app/main.py`
- `app/api/agent.py`
- `app/services/agent/tool_calling_service.py`
- `app/frontend/index.html`
- `app/frontend/static/app.js`
- `app/frontend/static/styles.css`
- `tests/test_stage39_design.py`
- `tests/test_stage39_docker.py`
- `tests/test_stage39_logging.py`
- `tests/test_stage39_deployment_docs.py`

数据安全边界：

- 结构化日志只记录安全字段和截断摘要，不记录 API key、Bearer token、Authorization header、raw provider response、`reasoning_content`、hidden thought、完整用户问题、完整 chunk 或受限全文。
- production smoke CSV 仍只记录 endpoint、状态、耗时、mode 校验、citation_count、refused 和错误摘要，不保存 response body。
- `.env.example` 只列变量名和安全默认值，不包含真实 key。
- Docker 构建上下文通过 `.dockerignore` 排除 `.env`、测试、`data/evaluation`、本地数据库、原始全文、Obsidian 和日志。

## 阶段 38 数据说明

阶段 38 不新增外部资料来源、不爬新网页、不下载新 PDF、不写入新的受限全文，也不重切语料。新增内容均为默认 tool-calling 链路生成质量攻坚、扩展评测、真实 Judge A/B、production smoke 和文档/Obsidian 草稿的派生产物。

阶段 38 新增派生产物：

- `docs/stage38_tool_calling_generation_quality.md`
- `docs/stage38_tool_calling_quality_decision.md`
- `docs/phase_reviews/phase-38.md`
- `scripts/evaluate_stage38_tool_calling_quality.py`
- `scripts/judge_stage38_tool_calling_quality.py`
- `data/evaluation/stage38_tool_calling_quality_results.csv`
- `data/evaluation/stage38_tool_calling_quality_summary.csv`
- `data/evaluation/stage38_tool_calling_judge_results.csv`
- `data/evaluation/stage38_tool_calling_judge_summary.csv`
- `data/evaluation/stage38_citation_gap_analysis.csv`
- `data/evaluation/stage36_production_smoke_results.csv`（扩展为 11 个 smoke case，增加 `expected_mode` / `actual_mode` / `mode_matched`）
- `obsidian-vault/阶段汇报/阶段 38 - Tool Calling 生成质量攻坚/`

数据安全边界：

- Stage 38 CSV 与文档不得保存 API key、Bearer token、Authorization header、供应商原始响应、raw provider response、`reasoning_content`、hidden thought、完整 chunk 全文或受限全文。
- Judge CSV 只保存分数、风险等级、短理由、next_action、计数和安全摘要，不保存答案全文或 provider 原始 JSON。
- production smoke CSV 不保存 response body，只保存 endpoint、状态、耗时、关键字段、mode 校验字段、refused、citation_count、validator_marker、sensitive_field_detected 和 error_summary。
- 真实 API 调用只在显式 `--execute` 命令中发生，不进入 CI 或本地全量 pytest 前提。

## 阶段 37 数据说明

阶段 37 不新增外部资料来源、不爬新网页、不下载新 PDF、不写入新的受限全文，也不重切语料。新增内容均为协议迁移、Agent loop、API/SSE 接入、deterministic 本地评估 fixture、production smoke 和文档草稿。

阶段 37 新增派生产物：

- `docs/stage37_tool_calling_loop_migration.md`
- `app/services/agent/tool_calling_service.py`
- `scripts/evaluate_stage37_tool_calling_vs_react.py`
- `data/evaluation/stage37_tool_calling_vs_react_results.csv`
- `data/evaluation/stage37_tool_calling_vs_react_summary.csv`
- `data/evaluation/stage37_tool_calling_vs_react_real_results.csv`
- `data/evaluation/stage37_tool_calling_vs_react_real_summary.csv`
- `data/evaluation/stage36_production_smoke_results.csv`（扩展为 9 个 smoke case，含 `tool_calling_agent`）
- `docs/stage37_tool_calling_vs_react_decision.md`
- `docs/phase_reviews/phase-37.md`

数据安全边界：

- tool result 回灌只保存脱敏、截断后的短摘要，不保存完整 chunk 全文。
- 对照评估 CSV 只保存指标、状态、错误摘要和裁定候选，不保存答案全文、raw provider response、`reasoning_content`、hidden thought、API key、Bearer token 或 Authorization header。
- real-provider 对照 CSV 当前记录 `provider_rate_limit` 等安全错误标签，不保存 provider 原始 JSON 错误体。
- production smoke CSV 不保存 response body，只保存 endpoint、状态、耗时、关键字段、refused、citation_count、validator_marker、sensitive_field_detected 和 error_summary。

## 阶段 36 数据说明

阶段 36 不新增外部资料来源、不爬新网页、不下载新 PDF、不写入新的受限全文。新增内容均为现有代码、现有问题集、现有检索结果和真实/离线评测流程派生的工程与评测产物。

阶段 36 新增派生产物：

- `docs/stage36_generation_reliability_and_conversation_stability.md`
- `app/services/agent/refusal_explainer.py`
- `scripts/run_production_smoke.py`
- `data/evaluation/stage36_production_smoke_results.csv`
- `app/services/generation/outline_first_strategy.py`
- `scripts/judge_stage36_strategy_ab.py`
- `data/evaluation/stage36_judge_strategy_ab_results.csv`
- `data/evaluation/stage36_judge_strategy_ab_summary.csv`
- `docs/stage36_judge_strategy_decision.md`
- `app/services/agent/intent_router.py`
- `docs/phase_reviews/phase-36.md`

数据安全边界：

- 任何阶段 36 CSV、文档、测试和 Obsidian 草稿不得保存 API key、Bearer token、Authorization header、raw provider response、`reasoning_content`、hidden thought、完整 chunk 全文或受限全文。
- 拒答解释中的检索摘要只允许使用 source title、source_type 和短内容片段，单条摘要不超过 200 字符。
- production smoke CSV 不保存 response body，只保存状态、耗时、关键字段、refused、citation_count、validator_marker、sensitive_field_detected 和 error_summary。
- Judge A/B 当前真实执行受 provider timeout 阻断，completed rows 为 0；不得把 dry-run 或 skipped 结果冒充真实 Judge 通过。

## 登记模板

```text
source_id:
标题:
URL:
来源类型:
作者或机构:
发布时间:
访问时间:
是否允许全文保存:
可信度评级:
备注:
```

## 当前状态

阶段 35 不新增外部资料来源、不新增爬虫、不写入新的受限全文；新增的是由现有 Stage 29/30 评测集、现有 chunks、现有 provider 配置和真实 Judge 复跑派生出的扣分归因、质量校准和评分对比产物。

阶段 35 新增派生产物：

- `docs/stage35_retrieval_quality_calibration.md`：阶段 35 设计、五类根因、修复边界、双门验证和安全边界。
- `scripts/analyze_stage35_deduction_causes.py`：Stage 30 deductions 根因归因脚本。
- `data/evaluation/stage35_deduction_root_causes.csv`：每条扣分的根因分类、证据摘要和修复建议。
- `data/evaluation/stage35_llm_judge_results.csv`、`stage35_llm_judge_summary.csv`：真实 Judge 10 条脱敏复跑结果。
- `data/evaluation/stage35_quality_summary.csv`：阶段 34/35 Stage 30 分数、目标样例和 Judge 指标对比。
- `docs/phase_reviews/phase-35.md`：阶段 35 人工核验前验收草稿。

数据安全边界：

- Stage 35 CSV 与文档不得保存 API key、Bearer token、Authorization header、供应商原始响应、raw provider response、`reasoning_content`、hidden thought 或受限全文。
- Judge payload 的 `evidence_snippet` 仅为脱敏短片段，用于判断 citation_support；不保存大段全文，不作为新语料来源。
- 真实 API 只在显式命令中调用，不进入 CI；本地全量 pytest 不依赖真实 provider。

阶段 34 不新增外部资料来源、不新增爬虫、不写入新的受限全文；新增的是由现有问题集、现有 chunks、现有 embedding 索引、真实运行 trace 和真实 Judge 复核派生出的评测/报告产物。

阶段 34 新增派生产物：

- `docs/stage34_rag_diagnosis_embedding_judge.md`：阶段 34 设计、指标、真实调用边界和安全边界。
- `data/evaluation/stage34_embedding_comparison_results.csv`、`stage34_embedding_comparison_summary.csv`：Jina 1024 维与 GLM-Embedding-3 2048 维同环境检索对照。
- `data/evaluation/stage34_latency_traces.csv`、`stage34_latency_traces_dry_run.csv`：脱敏 latency trace，不保存完整答案、raw response 或受限全文。
- `data/evaluation/stage34_latency_bottleneck_summary.csv`、`docs/stage34_latency_bottleneck_report.md`：性能瓶颈分析产物。
- `data/evaluation/stage34_llm_judge_results.csv`、`stage34_llm_judge_summary.csv`：真实 Judge 脱敏分数、短理由、风险等级和 next_action。
- `data/evaluation/stage34_decision_summary.csv`、`docs/stage34_rag_diagnosis_decision_report.md`：阶段 34 决策摘要和报告。

数据安全边界：

- 真实 API key、Bearer token、Authorization header、供应商原始响应、raw_response、`reasoning_content`、hidden thought 和受限全文不得写入 Git、CSV、文档、测试或 Obsidian。
- 真实调用必须显式执行；dry-run 不伪造成成功，真实失败必须写 `skipped` 或 `error`。
- 旧 Jina FAISS 与 GLM-Embedding-3 FAISS 均继续作为可重建索引派生产物保留，`data/faiss/` 不进入 Git。

阶段 33 不新增外部资料来源、不新增爬虫、不写入新的受限全文；新增的是由现有 chunks、embedding 索引和评测集派生出的性能/迁移验证产物。阶段 33 同时明确保留旧 Jina 索引作为回滚保险和质量对照，保留 GLM-Embedding-3 2048 维索引作为新链路验证目标。

```text
documents 635
chunks 19118
sources 673
legacy_jina_faiss data/faiss/jina_jina-embeddings-v3_dim1024.index
legacy_jina_ids data/faiss/jina_jina-embeddings-v3_dim1024_ids.json
glm_embedding_dimension 2048
stage30_quality_overall 83.17
```

阶段 33 新增派生产物与脚本：

- `docs/stage33_rag_performance_embedding_validation.md`：阶段 33 性能优化、迁移验证和安全边界设计文档。
- `scripts/benchmark_stage33_rag_latency.py`：RAG 延迟基准脚本，默认 deterministic，不要求真实 API。
- `scripts/evaluate_stage33_embedding_migration.py`：GLM-Embedding-3 2048 维与 Jina 1024 维检索质量对照脚本；真实配置缺失时显式 skipped。
- `scripts/benchmark_stage33_chat_providers.py`：MIMO baseline 与 DeepSeek candidate 聊天 provider benchmark；DeepSeek 只作候选，不替换默认 MIMO。
- `data/evaluation/stage33_rag_latency_benchmark.csv`：脱敏延迟指标，不保存供应商原始响应或受限全文。
- `data/evaluation/stage33_embedding_migration_results.csv`、`stage33_embedding_migration_summary.csv`：precision@k、hit@k、source/citation coverage、unsupported/refusal 边界和耗时结果。
- `data/evaluation/stage33_chat_provider_benchmark.csv`：time_to_first_token、time_to_final、token_count、tokens_per_second、citation/refusal 一致性和 reasoning_content 泄露风险标记。

数据安全边界：

- 阶段 33 的 CSV 只保存脱敏指标、provider/model 名称、维度、状态、错误摘要和延迟，不保存 API key、Bearer token、Authorization header、raw provider response、reasoning_content 或受限全文。
- Query embedding cache 是进程内缓存，不写入 Git，不写数据库，不改变知识库索引。
- Latency trace 只记录安全耗时和计数字段；SSE metadata 继续保持向后兼容。
- 旧 Jina FAISS 与 GLM-Embedding-3 FAISS 均是可重建索引派生产物，`data/faiss/` 不进入 Git。

阶段 32 不新增外部资料来源、不新增爬虫、不写入新的受限全文；新增的是 ReAct Agent 编排代码、SSE 运行事件协议、前端可视化，以及 deterministic 评测派生产物。

```text
documents 635
chunks 19118
sources 673
chunk_embeddings 25432
stage30_quality_overall 83.17
stage32_eval_modes default / agentic_langgraph / react_agent
```

阶段 32 新增派生产物与脚本：

- `docs/stage32_react_agent_observability.md`：阶段 32 ReAct action、工具权限、SSE 事件、安全边界和完成标准设计文档。
- `scripts/evaluate_stage32_react_agent.py`：deterministic 三路对照评测脚本，使用 in-memory SQLite fixture，不读取真实 API key，不调用真实 provider，不写业务数据库。
- `data/evaluation/stage32_react_agent_results.csv`：逐问题、逐模式评测结果，只保存 query_id、category、mode、错误、是否 answer-like、拒答匹配、来源数量、引用有效性、工具调用数、迭代数和 workflow step 数。
- `data/evaluation/stage32_react_agent_summary.csv`：`default`、`agentic_langgraph`、`react_agent` 汇总指标，只保存错误率、回答数、拒答匹配、平均工具调用、平均迭代和 decision。
- `/agent/query/stream` 新增运行事件 `agent_step`、`tool_call_start`、`tool_call_result`，这些事件是请求内即时传输的安全摘要，不是新的持久数据源。

数据安全边界：

- ReAct 工具仍只读，只能走 `search_knowledge`、`rewrite_query`、`answer_with_citations`、`refuse`、`final_answer`；不新增写入型工具。
- ReAct 检索和回答必须复用 `AgentToolbox`、Brain、citation、sources、evidence confidence、responsibility_gate 和 refusal 链路。
- SSE 和前端只展示 `step_summary`、`input_summary`、`observation_summary`、`decision_summary` 等安全摘要，不展示 hidden thought。
- `stage32_react_agent_results.csv` 和 `stage32_react_agent_summary.csv` 不得包含敏感凭据、授权头、供应商原始响应或受限全文。

阶段 31 不新增外部资料来源、不新增爬虫、不写入新的受限全文；新增的是由现有 `chunk_embeddings` 派生的本地 FAISS 索引能力，以及 `chunks.parent_chunk_id` 父子块关系字段。

```text
documents 635
chunks 12716
sources 673
chunk_embeddings 25432
jina_embeddings 12716
deterministic_embeddings 12716
faiss_index_vectors 12716
stage30_quality_overall 83.17
```

阶段 31 新增派生产物与脚本：

- `data/faiss/`：本地 FAISS `.index` 与 `_ids.json` metadata 输出目录，已加入 `.gitignore`，不提交到 Git。
- `scripts/build_faiss_index.py`：只读读取当前 SQLite 的有效 `chunk_embeddings`，构建 FAISS `IndexFlatIP` 索引；不调用真实 API、不重建 embedding、不写数据库。
- `scripts/migrate_parent_chunks.py`：幂等添加 `chunks.parent_chunk_id` 字段和索引；本地 SQLite 已执行迁移。
- `docs/stage31_faiss_parent_child_retrieval.md`：阶段 31 设计、边界和完成标准文档。

数据安全边界：

- FAISS `.index` 和 `_ids.json` 是可重建索引派生物，不是新的外部资料来源，不进入 Git。
- 父子块 parent 只用于回答上下文，设计上不生成 embedding；child 负责 embedding、FAISS 召回和引用溯源。
- 阶段 31 不新增 Qdrant、Chroma、PGVector、torch、sentence-transformers，也不让真实 API 成为 CI 或本地全量测试前提。
- API key、Bearer token、Authorization header、供应商原始响应、raw_response 和受限全文不得写入 Git、CSV、文档、测试或 Obsidian。

阶段 30 不新增外部资料来源、不新增爬虫、不写入新的受限全文；新增的是 evaluation/reporting 层的评分配置、评分结果和报告产物：

```text
documents 635
chunks 12716
sources 673
chunk_embeddings 25432
jina_embeddings 12716
deterministic_embeddings 12716
orphan_embeddings 0
duplicate_provider_model_groups 0
```

阶段 30 新增评测与报告文件：

- `data/evaluation/stage30_scoring_weights.yaml`：评分权重与 rationale，权重合计 100。
- `data/evaluation/stage30_engineering_health.json`：工程健康只读 artifact，记录测试、索引完整性和报告冒烟状态。
- `data/evaluation/stage30_quality_scores.csv`：可追加历史趋势表，记录 run_id、run_at、overall_score、grade、release_decision、dimension_scores、score_delta、deductions 和 recommended_actions。
- `data/evaluation/stage30_quality_summary.csv`：`/quality-report/data.json` 和 `/quality-report/export.csv` 使用的阶段 30 维度分汇总。
- `data/evaluation/stage30_quality_deductions.csv`：扣分项、原因和推荐动作。
- `data/evaluation/stage30_llm_judge_results.csv`：可选 LLM-as-Judge 输出；默认 dry-run 不含真实语义分数、不调用真实模型，只有人工显式 `--execute` 且本地设置 key 时才会调用 DeepSeek/OpenAI-compatible provider。
- `docs/stage30_quality_score_report.md`：阶段 30 人工核验用评分报告。

数据安全边界：

- 阶段 30 的评分 CSV 和报告不是文献资料来源，只是阶段 29 评测结果的派生质量产物。
- 默认评分只使用 deterministic/rule-based 指标，不把 `coverage_ratio` 冒充为 `faithfulness`、`answer_relevancy` 或 `groundedness`。
- `scripts/score_stage30_quality.py` 不运行 pytest、不重建 embedding、不写数据库、不调用真实 API。
- 可选 LLM-as-Judge 当前支持 DeepSeek/OpenAI-compatible 手动模式；默认 dry-run 不调用真实模型，真实执行必须显式 `--execute` 并使用本地环境变量注入 key。API key、Bearer token、Authorization header、供应商原始响应、raw_response 和受限全文不得写入 Git、CSV、文档、测试或 Obsidian。

阶段 29 完成真实 Embedding 重建与质量闭环后，外部资料来源数量不变，新增的是由现有 chunks 派生出的索引和评测产物：

```text
documents 635
chunks 12716
sources 673
chunk_embeddings 25432
jina_embeddings 12716
deterministic_embeddings 12716
orphan_embeddings 0
duplicate_provider_model_groups 0
```

阶段 29 新增评测与报告文件：

- `data/evaluation/stage29_new_corpus_queries.csv`：18 条评测问题，覆盖 Wikipedia、公开标准、网页语料和拒答边界。
- `data/evaluation/stage29_real_quality_results.csv`：真实 Jina embedding 检索 + deterministic 问答的逐题评测结果。
- `data/evaluation/stage29_real_quality_summary.csv`：precision@k、coverage_ratio、refusal_accuracy 和 source_type_distribution 汇总。
- `data/evaluation/stage29_quality_summary.csv`：`/quality-report` 使用的阶段 29 质量门禁摘要。
- `docs/stage29_quality_report.md`：人工核验用质量报告。

数据安全边界：

- `chunk_embeddings` 是从 `chunks` 派生出的可重建索引数据，不是新的外部资料来源。
- 阶段 29 的真实 Jina API 调用只用于本地 embedding 重建和质量评测；API key、Bearer token、Authorization header 和供应商原始敏感响应不得写入 Git、CSV、文档、测试或 Obsidian。
- 评测 CSV 只保存问题、指标、source type、文档/来源标识、延迟和脱敏摘要，不保存受限全文或供应商原始响应。
- 全量测试继续使用 deterministic provider，不让真实 API 成为 CI 前提。

阶段 28 续完成后，数据来源进入“清理后待人工核验”状态：

```text
documents 635
web_page_documents 136
wikipedia_documents 25
standard_documents 9
chunks 12716
sources 673
wikipedia_sources 19
standard_sources 9
chunk_embeddings 21634
```

新增来源类型：

- `web_page`：阶段 28 本地网页爬取保留语料。Phase 8 已删除 458 个低质量网页文档，清理后剩余 136 个网页文档，其中 91 个仍建议人工复核。
- `wikipedia`：Phase 9 通过 Wikipedia REST API 获取的中英文百科页面，作为概念背景知识，不作为工程规范强证据。
- `standard_document`：Phase 10 下载的公开免费 PDF 标准/指南类资料，保存于 `data/raw/standards/`，下载前检查文件大小，超过 20MB 或无法公开获取的文档跳过。

阶段 28 续相关数据文件：

- `data/crawl/wikipedia_articles.csv`：38 条 Wikipedia 候选。
- `data/crawl/standards_urls.csv`：15 条公开 PDF 候选。
- `data/evaluation/stage28_crawl_quality_*.csv`：清理后质量审查输出。
- `docs/stage28_crawl_quality_report.md`：清理后质量报告。

当前仍等待用户人工核验；人工核验前不提交、不打 tag、不推送。

已完成阶段 4 source registry 来源治理。

阶段 4 已新增数据库表 `sources`，作为本项目的 source registry。它统一承接：

- `docs/data_sources.md` 中的人读来源登记。
- `data/fulltext_manifest.csv` 中的 PDF manifest。
- `data/source_candidates.csv` 中的公开学术 API 候选。
- `data/metadata/rfc_papers_metadata.csv` 中的题录元数据。
- `data/imports/metadata_corpus/*.md` 中的题录卡片。

当前同步结果：

- 输入来源候选：283 条。
- 写入 `sources` 表：125 条。
- 更新已有来源：132 次。
- 合并重复来源：26 次。
- 状态分布：`candidate=8`、`collected=117`。
- 全文保存权限分布：`institutional_access=2`、`metadata_only=110`、`open_access=10`、`unknown=3`。
- 可信度分布：`high=125`。

阶段 21 新增评测数据产物（不含受限全文或 API 凭据）：

- `data/evaluation/stage21_agentic_comparison_results.csv`：agentic vs baseline 逐查询对照结果。
- `data/evaluation/stage21_agentic_comparison_summary.csv`：配置级汇总指标。
- `data/evaluation/stage21_agentic_decision.csv`：接入门槛决策。

阶段 22 不新增外部资料来源，也不新增爬虫、真实 API 依赖或受限全文文件。阶段 22 的改动集中在前端展示和 `/agent/query` 只读响应契约：

- 新增 `docs/stage22_frontend_agentic_observability.md` 设计文档。
- `/agent/query` 响应新增 `workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category` 等观测字段；这些字段来自本次请求的 agentic 运行状态，不写入新的数据源表。
- 前端展示 default / agentic 模式、迭代步骤、无效引用和拒答分类；不改变 `sources`、`documents`、`chunks`、`chunk_embeddings` 或 source registry 的数据边界。
- 新增/更新测试均使用 deterministic provider 与临时 SQLite，不要求真实 API，不写入 API key、Bearer token、供应商原始敏感响应或受限全文。

阶段 23 不新增外部资料来源，也不新增爬虫、真实 API 依赖或受限全文文件。阶段 23 的新增数据产物只用于 agentic vs default 对照评测和自动路由验收：

- `docs/stage23_agentic_eval_and_auto_routing.md`：阶段 23 设计文档，说明评测修复、路由规则、API 自动分流、前端只读指示器和安全边界。
- `scripts/evaluate_stage23_agentic_auto_routing.py`：deterministic 评测脚本，使用 in-memory SQLite 合成 fixture，不读取或调用真实 provider。
- `data/evaluation/stage23_agentic_auto_routing_results.csv`：逐问题对照结果，只保存问题 ID、类别、复杂度期望、错误标记、是否 answer-like、来源数量、迭代次数和 agentic gain 标记。
- `data/evaluation/stage23_agentic_auto_routing_summary.csv`：default/agentic 汇总指标，只保存总数、错误数、error_rate、answer_like_count、拒答匹配数和 agentic_gain_count。
- `data/evaluation/stage23_agentic_auto_routing_decision.csv`：阶段 23 决策摘要，记录 default/agentic error_rate、agentic_gain_count、decision 和 reason。

这些 CSV 不包含 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文；合成 fixture 只使用可提交的短文本片段，用于隔离阶段 21 SSL/真实 provider 错误。阶段 23 前端只读 `data-agent-mode-status` 和 API 响应 `mode` 也不改变 `sources`、`documents`、`chunks`、`chunk_embeddings` 或 source registry 的数据边界。

阶段 24 不新增外部资料来源，也不新增爬虫、真实 API 依赖或受限全文文件。阶段 24 新增的是**本地会话运行数据**，用于让 Agent 面板支持多轮对话和刷新恢复：

- `docs/stage24_multi_turn_conversation.md`：阶段 24 设计文档，说明会话模型、API、摘要策略、前端 UI 和安全边界。
- `conversations` 表：保存会话标题、创建时间和更新时间。
- `messages` 表：保存 `user` / `assistant` / `summary` 消息正文、所属会话、回答 `mode` 和结构化 `metadata_json`。
- `app/services/conversation/history.py`：把消息装配为 LLM history，并在长对话超过阈值时生成 summary 消息。
- `/conversations` API：只管理本地会话和消息，不读取外部资料源，不触发爬虫。

阶段 24 的 `Message.metadata_json` 只保存前端恢复展示所需的结构化元数据，例如 `citations`、`workflow_steps`、`invalid_citations`、`refusal_category`、`mode` 和 `iteration_count`。它不得保存 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文。

阶段 24 的 summary 消息只用于当前 conversation 的短期上下文压缩，不是跨会话长期记忆，也不改变 `sources`、`documents`、`chunks`、`chunk_embeddings` 或 source registry 的资料来源边界。真实模型如果在实际长会话中被用于摘要，只能作为运行时模型服务，不是资料来源；自动测试继续使用 deterministic provider，不让真实 API 成为 CI 或本地全量测试前提。

阶段 25 不新增外部资料来源，也不新增爬虫、真实 API 依赖、CSV 评测数据或受限全文文件。阶段 25 新增的是**运行链路与展示协议**，用于让 Agent 面板支持闲聊短路和 SSE 流式输出：

- `docs/stage25_chitchat_and_sse_streaming.md`：阶段 25 设计文档，说明路由层闲聊短路、provider 流式协议、SSE 事件格式、前端消费方式和安全边界。
- `app/services/agent/chitchat.py`：本地规则和预设回复，只识别 greeting、thanks、goodbye、acknowledgment、help 五类社交意图，不读取外部资料源。
- `POST /agent/query/stream`：运行时流式响应端点，输出 `token`、`metadata`、`done`、`error` 事件，不改变 `sources`、`documents`、`chunks`、`chunk_embeddings` 或 source registry。
- 前端 `fetch()` + `ReadableStream` 消费 SSE：只改变回答展示时机，不创建新的资料来源。

阶段 25 的 SSE `token` 事件只包含面向用户展示的回答文本片段；`metadata` 事件复用 `AgentQueryResponse` 的结构化字段，例如 `citations`、`sources`、`workflow_steps`、`invalid_citations`、`refusal_category`、`mode` 和 `iteration_count`。它不得保存或暴露 API key、Bearer token、Authorization header、供应商原始敏感响应、raw_response 或受限全文。

阶段 25 的闲聊回复是预设文本，不是资料来源，也不参与检索证据；带 `conversation_id` 的闲聊可以保存为本地会话消息，但会跳过 summary 压缩，避免社交短句污染后续 RAG 上下文。真实模型流式输出只作为运行时服务能力，自动测试继续使用 deterministic provider，不让真实 API 成为 CI 或本地全量测试前提。

阶段 26 不新增外部资料来源，也不新增爬虫、真实 API 依赖或受限全文文件。阶段 26 新增的是**检索性能优化和重排序运行能力**：

- `docs/stage26_retrieval_performance_reranking.md`：阶段 26 设计文档，说明 profiling、numpy 向量化、缓存、并行召回、rerank provider 和安全边界。
- `scripts/benchmark_retrieval.py`：检索基准脚本，只读取现有本地数据库与索引，默认 deterministic provider，不触发真实 API。
- `app/services/retrieval/vector_cache.py`：进程内 `VectorIndexCache`，缓存来自 `chunk_embeddings` 的可重建向量矩阵。
- `app/services/retrieval/reranking.py`：`ReRankingProvider` 协议和 deterministic / OpenAI-compatible provider。

阶段 26 只读取现有：

```text
documents
chunks
chunk_embeddings
```

数据安全边界：

- `VectorIndexCache` 只在进程内缓存 embedding 矩阵，不写入 Git 或外部存储。
- `chunk_embeddings` 是由已有 chunks 派生出的可重建索引数据，不是新的文献资料来源。
- deterministic rerank 是本地规则式评分，不调用真实 API。
- OpenAI-compatible rerank provider 只是运行时可选能力；API key、Bearer token、Authorization header 和供应商原始敏感响应不得写入源码、文档、CSV、测试、Git 或 Obsidian。
- `scripts/benchmark_retrieval.py` 的输出只包含耗时、provider/model 名称和脱敏 query，不保存受限全文或供应商原始响应。
- 阶段 26 已停在用户人工核验前状态，尚未提交、尚未创建 `phase-26-complete` tag、尚未推送。

阶段 27 不新增外部资料来源，也不新增爬虫、真实 API 依赖、CSV 评测数据或受限全文文件。阶段 27 新增的是**运行入口、部署配置和 CI 配置**：

- `docs/stage27_chainlit_docker_ci.md`：阶段 27 设计文档，说明 Chainlit 双入口、service 层复用、Docker/CI、安全边界和完成标准。
- `chainlit_app.py`：Chainlit 对话界面入口，复用现有 `detect_chitchat`、Agent service、agentic workflow、ConversationRepository 和流式事件。
- `.chainlit/config.toml` 与 `chainlit.md`：Chainlit 运行配置和欢迎页，不包含外部资料、密钥或供应商响应。
- `Dockerfile`、`docker-compose.yml`、`.dockerignore`：容器运行配置和构建上下文排除规则。
- `.github/workflows/ci.yml`：deterministic provider 的 pytest CI 配置。

阶段 27 只读取既有运行数据边界：

```text
sources
documents
chunks
chunk_embeddings
conversations
messages
```

数据安全边界：

- Chainlit 是展示与交互入口，不是新的资料来源。它显示的回答、citations 和 workflow 来自当前请求运行结果。
- Chainlit 会话保存复用 `ConversationRepository`，只写入本地 `conversations` 与 `messages` 表；不得保存 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文。
- Docker 镜像不得包含 `.env`、API key、SQLite 数据库、`data/raw`、`data/fulltext` 或 Obsidian 知识库；运行时数据通过 `./data:/app/data` volume 挂载。
- GitHub Actions CI 使用 deterministic provider，不读取真实 `.env`，不要求真实模型 API，也不保存真实供应商响应。
- 当前阶段停在用户人工核验前状态，尚未提交、尚未创建 `phase-27-complete` tag、尚未推送。

阶段 28 新增外部网页资料来源，但限定为**公开 HTML 页面**的本地合规采集和自动入库：

- `docs/stage28_web_crawl_auto_ingest.md`：阶段 28 设计文档，说明 crawling 模块、CLI、本地运行方式、安全边界和完成标准。
- `app/services/crawling/`：网页采集服务层，包含 seed URL 管理、robots.txt 检查、限速 HTTP 抓取、trafilatura 正文提取和入库编排。
- `scripts/crawl_and_ingest.py`：本地批量爬取与自动入库 CLI。
- `data/crawl/seed_urls.csv`：100 条人工维护种子 URL，覆盖百科词条、高校机构、工程案例、开放论文、行业标准 5 类。
- `data/crawl/crawl_results*.csv`：本地批处理状态记录，只保存 URL、分类、状态、标题、document/source 标识和错误摘要，不保存网页正文。
- `data/raw/web_crawl/*.md`：公开网页经 trafilatura 提取后的 Markdown 正文，用于复用现有 `IngestionService.import_document()` 入库。

阶段 28 读取和写入边界：

```text
公开 seed URL
-> robots.txt / 限速 / User-Agent
-> trafilatura 提取正文
-> data/raw/web_crawl/*.md
-> documents/chunks
-> sources
-> chunk_embeddings
```

数据安全边界：

- 只抓取公开可访问页面；不绕登录、验证码、付费墙、机构授权墙或 robots.txt 禁止。
- User-Agent 标识 RFC-RAG-Agent，不伪装浏览器，不使用 Selenium/Playwright。
- 不长期保存原始 HTML，不保存 cookie、session、Authorization header、Bearer token 或用户凭据。
- `crawl_results*.csv` 不保存网页正文或供应商原始响应，只保存状态和错误摘要。
- 已入库网页来源统一注册到 `sources` 表，继续复用 DOI/URL/标题去重和 `document_id` 关联。
- 批量执行后数据库从 documents 465 / chunks 8918 / sources 125 增至 documents 1059 / chunks 12103 / sources 645；新增内容为本地运行数据，阶段 28 停在人工核验前，不提交 SQLite 数据库。
- 新增索引通过 deterministic provider 重建，`chunk_embeddings` 增至 21021；真实 API 不作为本地全量测试或 CI 前提。

阶段 1 第一批试导入资料登记仍保留在下方，作为早期人工来源记录和历史审计依据。

本批资料采用“资料卡”形式导入：保存题录、公开摘要的转述、检索关键词和来源链接，不保存受版权限制的论文全文。

## 已登记来源（阶段 1 试导入）

| source_id | 标题 | 来源类型 | 作者或机构 | 发布时间 | URL | 是否允许全文保存 | 可信度评级 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rfc_seed_001 | 堆石混凝土及堆石混凝土大坝 / Study on rock-fill concrete dam | CNKI 摘要页、论文题录与公开摘要整理 | 金峰, 安雪晖, 石建军, 张楚汉 | 2005 | https://kns.cnki.net/kcms2/article/abstract?v=7jvqSXIa2LXUBdK4dw0XCLkKcRO8rkZ6LMUUPnH8IpFJ2iR8zuGHA1e5WffpBNepiDh_rfta6rS4U4LuO-qJaLhUnh5c-5CkPCagNMPVSAWdW7j2g4YjWYemqq7ziqRMfVTwwnFVvAbh46kqvSqjJUorkuOpi55gjpt5EPsoavCGJgU1GTvfUw==&uniplatform=NZKPT&language=CHS | 否，仅保存转述整理 | 高 | 用户补充确认的堆石混凝土开篇之作；ResearchGate 与行业页面作为辅助线索 |
| rfc_seed_002 | 堆石混凝土大坝施工方法 | 专利题录与公开资料整理 | 金峰, 安雪晖 | 2003 | https://www.civil.tsinghua.edu.cn/heen/info/1159/1950.htm | 否，仅保存转述整理 | 高 | 金峰教授主页列出的 RFC 施工方法专利 |
| rfc_seed_003 | 自密实混凝土充填堆石体试验研究 | 论文题录与引用线索整理 | 安雪晖, 金峰, 石建军 | 2005 | https://cjxy.usc.edu.cn/info/2369/1623.htm | 否，仅保存转述整理 | 中高 | 通过作者主页论文列表和相关引用页确认 |
| rfc_seed_004 | 自密实堆石混凝土力学性能的试验研究 | 公开摘要整理 | 石建军, 张志恒, 金峰, 张楚汉 | 2007 | https://rockmech.whrsm.ac.cn/CN/abstract/abstract25492.shtml | 否，仅保存转述整理 | 高 | 期刊官网摘要页 |
| rfc_seed_005 | Rock-filled concrete, the new norm of SCC in hydraulic engineering in China | 论文题录与摘要整理 | Xuehui An, Qiong Wu, Feng Jin 等 | 2014 | https://www.sciencedirect.com/science/article/pii/S0958946514001413 | 否，仅保存转述整理 | 高 | Cement and Concrete Composites 论文页 |
| rfc_seed_006 | Experimental study of filling capacity of self-compacting concrete and its influence on the properties of rock-filled concrete | 论文题录与摘要整理 | Yuetao Xie, David J. Corr, Mohend Chaouche, Feng Jin, Surendra P. Shah | 2014 | https://www.scholars.northwestern.edu/en/publications/experimental-study-of-filling-capacity-of-self-compacting-concret | 否，仅保存转述整理 | 高 | Northwestern Scholars 题录页 |
| rfc_seed_007 | Lattice Boltzmann-Discrete Element Modeling Simulation of SCC Flowing Process for Rock-Filled Concrete | 开放获取论文整理 | Song-Gui Chen, Chuan-Hu Zhang, Feng Jin 等 | 2019 | https://www.mdpi.com/1996-1944/12/19/3128 | 可开放访问，本项目仍只保存转述整理 | 高 | MDPI Materials 开放论文 |
| rfc_seed_008 | A Brief Review of Rock-Filled Concrete Dams and Prospects for Next-Generation Concrete Dam Construction Technology | 开放获取综述整理 | Feng Jin, Duruo Huang, Michel Lino, Hu Zhou | 2023 | https://www.engineering.org.cn/engi/CN/PDF/10.1016/j.eng.2023.09.020 | 可开放访问，本项目仍只保存转述整理 | 高 | Engineering 开放综述 |
| rfc_seed_009 | Filling the gaps in large concrete dams | 高校公开网页整理 | Tsinghua University | 2021 | https://www.tsinghua.edu.cn/en/info/1418/10419.htm | 否，仅保存转述整理 | 中高 | 清华大学英文新闻/特写 |
| rfc_seed_010 | 堆石混凝土绝热温升性能初步研究 | 论文题录与公开摘要整理 | 金峰, 李乐, 周虎, 安雪晖 | 2008 | https://sjwj.cbpt.cnki.net/portal/journal/portal/client/paper/65e4dbdb69e5e0bc75cdedaf22704c3e | 否，仅保存转述整理 | 高 | 覆盖水化热、温控和抗裂主题 |

## 后续补充方向

- 增加更多工程应用案例资料，覆盖不同坝型和施工场景。
- 增加规范、规程或行业标准的公开目录信息，但不保存受版权限制全文。
- 对每条资料补充主题标签，例如概念、施工、质量控制、温控、力学性能、工程应用。

## 全文来源目录

阶段 1 已开始从资料卡扩展到论文原文导入。全文 PDF 的来源分类、访问权限和本地文件名见：

- `docs/source_catalog.md`
- `data/fulltext_manifest.csv`

全文 PDF 保存在 `data/fulltext/`，该目录已加入 `.gitignore`，用于本地私有资料库，不提交到 GitHub。

## 题录元数据来源目录

阶段 1 已新增题录优先语料库，用于在不下载更多全文的情况下扩大检索覆盖面。

当前题录文件：
- `data/metadata/rfc_papers_metadata.csv`
- `data/metadata/rfc_papers_metadata.jsonl`
- `data/imports/metadata_corpus/*.md`

当前来源：
- OpenAlex
- Crossref
- 后续可合并 Semantic Scholar、CNKI 导出、Google Scholar 辅助工具导出、Zotero/EndNote/RIS 导出

当前规模：
- 116 条题录记录。
- 69 条包含公开摘要。
- 115 条已作为 `metadata_record` 文档进入 SQLite 检索库。

合规说明：
- 题录语料只保存公开元数据和摘要，不保存未授权全文。
- Google Scholar 不作为直接网页爬取主链路；如需使用，优先通过可导出的题录文件进入本项目。
- CNKI 机构账号获取的内容优先走题录导出或本地私有导入，不公开再分发全文。

## Source Registry 关系说明

阶段 4 之后，来源治理以 `sources` 表为准，文档关系如下：

```text
docs/data_sources.md
  人读来源说明和合规边界

data/fulltext_manifest.csv
  PDF 全文清单，包含本地路径和访问权限

data/source_candidates.csv
  学术 API 发现的候选来源

data/metadata/rfc_papers_metadata.csv
  题录 CSV，适合批量导入和评测

data/imports/metadata_corpus/*.md
  题录 Markdown 卡片，可进入 documents/chunks

sources
  数据库来源登记库，统一保存来源元数据、去重键、权限、可信度、状态和 document 关联

documents/chunks
  已导入并可检索、可引用的内容库
```

同步入口：

```powershell
python scripts/sync_sources.py
```

来源评测入口：

```powershell
python scripts/evaluate_sources.py
```

重新索引入口：

```text
POST /sources/{source_id}/reindex
```

设计原则：

- `sources` 管“这条资料来源是什么、是否可信、能否保存、是否已导入”。
- `documents/chunks` 管“这条资料实际进入 RAG 检索后的正文和片段”。
- `fulltext_permission` 与 `trust_level` 分开记录，避免把版权/授权问题和来源质量混在一起。
- 对受限全文，保留题录、摘要、合法来源链接和本地授权路径，不公开分发全文。

## 前端展示入口

阶段 5 已新增前端工作台：

```text
GET /
```

来源相关界面能力：

- 查看 `sources` 列表。
- 按关键词、状态、全文保存权限筛选来源。
- 查看来源可信度、全文权限、年份、分类、URL/DOI 和 `document_id`。
- 触发 `POST /sources/sync` 同步现有来源文件。
- 触发 `POST /sources/{source_id}/reindex` 重新导入单条来源。

资料相关界面能力：

- 查看 `documents` 列表。
- 查看每篇资料的 chunk 数量。
- 点击资料查看 `documents/{document_id}/chunks`。
- 在聊天引用侧栏中核验回答依据的具体 chunk。

阶段 5 的界面不改变数据来源合规边界：受限全文仍不公开分发，前端只展示本地系统已登记或已导入的来源和片段。

## 阶段 6 评测与数据来源边界

阶段 6 进入检索优化与评测，没有新增外部资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 6 使用的评测数据来自现有本地项目文件：

```text
data/evaluation/keyword_queries.csv
data/evaluation/chat_queries.csv
data/evaluation/keyword_results.csv
data/evaluation/vector_results.csv
data/evaluation/chat_results.csv
```

阶段 6 新增的评测输出是对现有资料库和现有评测集的分析结果：

```text
data/evaluation/hybrid_results.csv
data/evaluation/retrieval_error_cases.csv
```

它们不包含新的受限全文，只记录查询、期望命中、命中结果、通过状态、失败原因、改进建议和 hybrid 优化后的状态。

阶段 6 的核心关系是：

```text
sources
-> documents/chunks
-> chunk_embeddings
-> keyword/vector/hybrid retrieval
-> evaluation results
-> error cases
```

合规结论：

- `sources` 仍然负责来源可信度、全文权限和状态。
- `documents/chunks` 仍然只保存已导入的本地资料或题录卡片。
- `chunk_embeddings` 是由 chunks 派生出的可重建索引数据。
- `hybrid_results.csv` 和 `retrieval_error_cases.csv` 是评测产物，不是新的资料来源。
- 阶段 6 没有公开分发受限全文，也没有引入新的爬虫链路。

## 阶段 7 Agent 化与数据来源边界

阶段 7 进入 Agent 化，没有新增外部资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

Agent 工具只读取现有数据：

```text
sources
documents/chunks
chunk_embeddings
qa_logs
data/evaluation/*.csv
```

阶段 7 新增的 Agent 工具：

```text
search_knowledge
hybrid_search_knowledge
answer_with_citations
list_sources
get_source_detail
```

这些工具复用现有 service 和 repository：

```text
KeywordSearchService
HybridSearchService
CitationAnswerService
SourceRepository
```

阶段 7 新增的评测输入和输出：

```text
data/evaluation/agent_queries.csv
data/evaluation/agent_results.csv
```

它们不包含新的受限全文，只记录 Agent 任务、期望工具、期望拒答、来源命中、引用有效性和工具调用结果。

阶段 7 的核心关系是：

```text
sources
-> documents/chunks
-> keyword/vector/hybrid retrieval
-> citation chat
-> Agent read-only tools
-> agent evaluation results
-> frontend tool call display
```

合规结论：

- Agent 不新增联网爬虫链路。
- Agent 不绕过 `sources` 的可信度、全文权限和状态记录。
- Agent 不自动执行 `POST /sources/{source_id}/reindex` 等写入型动作。
- `agent_results.csv` 是评测产物，不是新的资料来源。
- 受限全文仍只保存在本地授权环境中，不公开分发。

## 阶段 8 Brain Workflow 与数据来源边界

阶段 8 进入 Brain 中控层与 RAG Workflow 配置化，没有新增外部资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

Brain workflow 只读取或复用现有数据：

```text
sources
documents/chunks
chunk_embeddings
qa_logs
data/evaluation/*.csv
```

阶段 8 新增的评测输出：

```text
data/evaluation/brain_workflow_results.csv
```

它不是新的资料来源，而是对现有 chat 评测集和现有资料库的配置化评测产物。该 CSV 记录不同 Brain 配置下的：

- config 名称
- 实际检索模式
- workflow steps
- 来源命中
- citation 有效性
- 拒答匹配
- 模型提供方和模型名称

阶段 8 的核心关系是：

```text
sources
-> documents/chunks
-> chunk_embeddings
-> keyword/vector/hybrid retrieval
-> Brain workflow
-> chat/agent answer
-> brain workflow evaluation results
```

合规结论：

- Brain 不联网爬取新资料。
- Brain 不绕过 `sources` 的可信度、全文权限和状态记录。
- Brain 不自动执行 `source reindex` 等写入型动作。
- `brain_workflow_results.csv` 是评测产物，不是新的资料来源。
- 受限全文仍只保存在本地授权环境中，不公开分发。

## 阶段 9 真实模型接入与数据来源边界

阶段 9 进入真实模型接入与模型评测，没有新增外部文献资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 9 新增的是模型服务配置和评测产物：

```text
docs/model_provider_evaluation.md
scripts/evaluate_model_configs.py
data/evaluation/model_config_results.csv
data/evaluation/mimo_jina_chat_results.csv
data/evaluation/mimo_jina_agent_results.csv
data/evaluation/mimo_jina_brain_workflow_results.csv
```

真实模型 API 不是资料来源。它只用于：

```text
chunks -> embedding vectors
prompt/context -> chat answer
evaluation results -> quality comparison
```

阶段 9 不保存真实模型服务返回的受限文献全文；`model_config_results.csv` 只保存配置名、评测项、通过数、总数、provider/model 名称和 skipped reason。

阶段 9.1 使用 Jina embedding 和 MIMO chat 做真实模型补充评测。Jina 和 MIMO 都是模型服务，不是文献资料来源；新增的 `mimo_jina_*_results.csv` 只保存问题、通过状态、来源标题、引用数量、provider/model 名称和错误摘要，不保存 API key，也不新增受限全文。

合规结论：

- `sources` 仍然负责资料来源、可信度、权限和状态。
- `documents/chunks` 仍然只保存已导入的本地资料或题录卡片。
- `chunk_embeddings` 是由 chunks 派生出的可重建索引数据。
- 真实 API key 只允许放在本地 `.env`，不得提交到 Git。
- MIMO Token Plan key、Jina API key 和任何真实模型凭证不得写入源码、文档或评测 CSV。
- 阶段 9 没有公开分发受限全文，也没有引入新的爬虫链路。

## 阶段 10 真实 RAG 质量校准与数据来源边界

阶段 10 进入真实 RAG 质量校准与拒答边界优化，没有新增外部文献资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 10 复用现有数据：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/*.csv
```

阶段 10 新增或更新的评测产物：

```text
data/evaluation/real_rag_failure_cases.csv
data/evaluation/vector_results.csv
data/evaluation/hybrid_results.csv
data/evaluation/brain_workflow_results.csv
data/evaluation/model_config_results.csv
data/evaluation/stage10_jina_vector_results.csv
data/evaluation/stage10_jina_hybrid_results.csv
data/evaluation/stage10_mimo_jina_chat_results.csv
data/evaluation/stage10_mimo_jina_agent_results.csv
data/evaluation/stage10_mimo_jina_brain_workflow_results.csv
```

这些文件不是新的资料来源。它们只记录：

- 评测问题。
- 期望命中条件。
- 通过或失败状态。
- 命中标题和来源类型。
- 引用数量和拒答状态。
- provider/model 名称。
- 失败原因和改进建议。

阶段 10 的核心关系是：

```text
已有 sources / documents / chunks
-> deterministic or Jina chunk_embeddings
-> keyword / vector / hybrid retrieval
-> Brain evidence confidence
-> chat / agent / brain workflow evaluation
-> stage 10 quality conclusion
```

合规结论：

- 阶段 10 不新增爬虫链路。
- 阶段 10 不新增外部文献或受限全文。
- Jina 和 MIMO 仍然是模型服务，不是资料来源。
- `stage10_*_results.csv` 是质量校准结果，不是资料库。
- `real_rag_failure_cases.csv` 是失败分析表，不包含受限全文，只保存可追溯标题、简短证据摘要和诊断。
- 真实 API key 只允许放在本地 `.env`，不得写入源码、文档、CSV 或 Obsidian。
- 自动回归继续优先使用 deterministic provider，避免把真实模型密钥、网络和余额变成测试前提。

## 阶段 11 真实用户问题评测与数据来源边界

阶段 11 进入真实用户问题评测集与跨语言质量提升，没有新增外部文献资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 11 复用现有数据：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/keyword_queries.csv
data/evaluation/chat_queries.csv
data/evaluation/agent_queries.csv
```

阶段 11 新增或更新的评测产物：

```text
data/evaluation/user_questions.csv
data/evaluation/user_question_results.csv
data/evaluation/user_question_review_samples.csv
docs/stage11_user_evaluation_plan.md
```

这些文件不是新的资料来源。它们只记录：

- 用户问题。
- 语言类型。
- 期望来源命中。
- 期望拒答状态。
- 期望回答要点。
- 自动评测通过或失败状态。
- 来源标题、答案摘要、审阅字段和 judge prompt。

阶段 11 的核心关系是：

```text
已有 sources / documents / chunks
-> keyword / vector / hybrid retrieval
-> user question evaluation
-> cross-language query expansion
-> manual review samples
-> stage 11 quality conclusion
```

合规结论：

- 阶段 11 不新增爬虫链路。
- 阶段 11 不新增外部文献或受限全文。
- `user_questions.csv` 是评测输入，不是资料库。
- `user_question_results.csv` 和 `user_question_review_samples.csv` 是质量评测产物，不保存受限全文。
- 审阅抽样表只保存来源标题、答案摘要、审阅字段和必要备注，不保存完整论文正文。
- Jina、MIMO 或其他真实模型仍然是模型服务，不是资料来源。
- 真实 API key 只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- 自动回归继续使用 deterministic provider；真实模型只适合发布前质量校准或离线审阅。

## 阶段 12 质量审阅与上下文最小补全产物

阶段 12 新增或更新的评测与设计产物：

```text
data/evaluation/stage12_quality_review_results.csv
docs/stage12_quality_review.md
docs/stage13_decompose_plan.md
```

这些文件不是新的文献资料来源。它们只记录：

- 审阅样本 ID 和用户问题 ID。
- 语言类型和评测配置。
- 期望回答要点。
- Faithfulness、Answer Coverage、Citation Quality 的人工或离线审阅结论。
- 风险等级、审阅备注和下一步建议。
- 阶段 13 Decompose 的后续设计边界。

阶段 12 的上下文补全也不新增资料来源。它只在检索前使用调用方传入的可选 `history`，把“它”“这个技术”等省略问法补成更完整的检索 query。补全后的 query 不会写入 `sources`、`documents`、`chunks` 或 `chunk_embeddings`。

合规结论：

- 阶段 12 不新增爬虫链路。
- 阶段 12 不新增外部文献或受限全文。
- `stage12_quality_review_results.csv` 是质量审阅产物，不是资料库。
- `docs/stage13_decompose_plan.md` 是后续设计文档，不是资料来源。
- 质量审阅只保存来源标题、答案摘要、审阅字段和必要备注，不保存完整论文正文。
- HyDE 只保留为离线实验建议，不进入默认链路或自动回归。
- 真实 API key 仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。

## 阶段 13 Decompose 与证据合并产物

阶段 13 新增或更新的工程与评测产物：

```text
app/services/retrieval/decompose.py
scripts/evaluate_decompose.py
data/evaluation/stage13_decompose_results.csv
docs/stage13_decompose_plan.md
```

这些文件不是新的文献资料来源。它们只记录：

- 规则式拆解后的 sub query。
- 每个问题的检索、合并、去重和 rerank 解释。
- 来源命中、拒答匹配、provenance 和 answer coverage proxy 等评测字段。
- 阶段 13 的设计边界和质量结论。

阶段 13 不新增外部资料来源，不新增爬虫链路，不保存受限全文。Decompose 只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/user_questions.csv
```

合规结论：

- `stage13_decompose_results.csv` 是质量评测产物，不是资料库。
- sub query provenance 只说明证据由哪个子问题召回，不改变资料来源归属。
- 真实 API key 仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 14 真实 Embedding 与回答覆盖校准产物

阶段 14 新增或更新的工程与评测产物：

```text
docs/stage14_real_quality_calibration.md
scripts/evaluate_stage14_embedding_comparison.py
data/evaluation/stage14_embedding_comparison.csv
scripts/evaluate_stage14_answer_coverage.py
data/evaluation/stage14_answer_coverage_review.csv
scripts/evaluate_stage14_decompose_provenance.py
data/evaluation/stage14_decompose_provenance_review.csv
```

这些文件不是新的文献资料来源。它们只记录：

- deterministic baseline 与 real_config 的评测状态、指标和失败 query。
- Answer Coverage、Faithfulness、Citation Quality、risk_level 和 recommendation。
- Decompose provenance、topic_terms、both_match、source_type、raw_score、final_score 等证据级审阅字段。
- 真实配置缺失或真实结果文件缺失时的 `skipped` / `missing_results` 原因。

阶段 14 不新增外部资料来源，不新增爬虫链路，不保存受限全文。它只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/user_questions.csv
data/evaluation/user_question_results.csv
data/evaluation/stage13_decompose_results.csv
```

合规结论：

- `stage14_embedding_comparison.csv` 是评测汇总表，不是资料库。
- `stage14_answer_coverage_review.csv` 是质量审阅表，不保存受限论文全文或供应商原始敏感响应。
- `stage14_decompose_provenance_review.csv` 是证据解释表，不改变来源归属。
- 真实 API key 仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 15 真实配置复跑与质量审阅报告产物

阶段 15 新增或更新的工程与评测产物：

```text
docs/stage15_real_review_report.md
scripts/evaluate_stage15_real_config.py
data/evaluation/stage14_real/real_config_status.csv
data/evaluation/stage14_real/vector_results.csv
data/evaluation/stage14_real/hybrid_results.csv
data/evaluation/stage14_real/user_question_results.csv
data/evaluation/stage14_real/chat_results.csv
data/evaluation/stage14_real/agent_results.csv
data/evaluation/stage14_real/brain_workflow_results.csv
scripts/evaluate_stage15_answer_coverage_review.py
data/evaluation/stage15_answer_coverage_review.csv
scripts/build_stage15_quality_report.py
data/evaluation/stage15_quality_summary.csv
docs/stage15_quality_report.md
app/frontend/quality_report.html
```

这些文件不是新的文献资料来源。它们只记录：

- 真实配置复跑的 completed、skipped 或 error 状态。
- 脱敏后的评测通过数、失败数、provider/model 名称和错误摘要。
- Answer Coverage、Faithfulness、Citation Quality、risk_level、review_note 和 next_action。
- 质量汇总、报告建议和只读展示所需的指标。

阶段 15 不新增外部资料来源，不新增爬虫链路，不保存受限全文。它只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/stage14_embedding_comparison.csv
data/evaluation/stage14_answer_coverage_review.csv
data/evaluation/stage14_decompose_provenance_review.csv
data/evaluation/stage14_real/*.csv
```

合规结论：

- `data/evaluation/stage14_real/` 是真实配置评测结果目录，不是资料库。
- `stage15_answer_coverage_review.csv` 是质量复核表，不保存受限论文全文或供应商原始敏感响应。
- `stage15_quality_summary.csv` 和 `docs/stage15_quality_report.md` 是报告产物，不改变来源归属。
- `app/frontend/quality_report.html` 是只读静态报告页，不触发真实 API 调用，不写数据库，不重新索引来源。
- 真实 API key、Bearer token 和供应商原始敏感响应仍只允许存在本地 `.env` 或内存调用中，不得写入源码、文档、CSV、测试、Git 或 Obsidian。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 16 真实质量风险闭环产物

阶段 16 新增或更新的工程与评测产物：

```text
docs/stage16_quality_risk_closure.md
scripts/analyze_stage16_decompose_diagnostics.py
data/evaluation/stage16_decompose_diagnostics.csv
scripts/evaluate_stage16_answer_coverage_closure.py
data/evaluation/stage16_answer_coverage_closure.csv
scripts/build_stage16_quality_closure_report.py
data/evaluation/stage16_quality_closure_summary.csv
docs/stage16_quality_closure_report.md
app/frontend/quality_report.html
```

这些文件不是新的文献资料来源。它们只记录：

- real decompose SSL EOF 的脱敏错误分类、根因、可重试状态和阻断状态。
- 阶段 15 high/medium Answer Coverage 样例的 `risk_before`、`risk_after`、Faithfulness、Answer Coverage、Citation Quality、根因、证据摘要、决策和 next action。
- 阶段 16 quality gate、报告建议和人工核验边界。
- 脱敏来源标题、回答摘要和必要指标，不保存供应商原始敏感响应。

阶段 16 不新增外部资料来源，不新增爬虫链路，不保存受限全文。它只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/stage14_real/real_config_status.csv
data/evaluation/stage14_embedding_comparison.csv
data/evaluation/stage15_answer_coverage_review.csv
docs/progress.md
```

合规结论：

- `stage16_decompose_diagnostics.csv` 是真实错误诊断表，不是资料库，也不保存 API key 或完整供应商响应。
- `stage16_answer_coverage_closure.csv` 是质量复核闭环表，不保存受限论文全文。
- `stage16_quality_closure_summary.csv` 和 `docs/stage16_quality_closure_report.md` 是报告产物，不改变来源归属。
- `app/frontend/quality_report.html` 仍是只读静态报告页，不触发真实 API 调用，不写数据库，不重新索引来源。
- 真实 API key、Bearer token、供应商原始敏感响应和受限全文仍不得写入源码、文档、CSV、测试、Git 或 Obsidian。
- 阶段 16 已完成人工核验、提交、创建 `phase-16-complete` tag 并合并到 `main`。

## 阶段 17 检索架构升级产物

阶段 17 新增或更新的工程与评测产物：

```text
docs/stage17_retrieval_architecture_upgrade.md
app/services/retrieval/context_expansion.py
app/services/retrieval/bm25_search.py
app/services/retrieval/rrf_fusion.py
scripts/evaluate_stage17_retrieval_upgrade.py
data/evaluation/stage17_retrieval_upgrade_results.csv
data/evaluation/stage17_retrieval_upgrade_manual_review.csv
docs/stage17_retrieval_upgrade_report.md
tests/test_stage17_manual_review.py
```

阶段 17 不新增外部资料来源，不新增爬虫链路，不新增受限全文保存。它只读取现有：

```text
documents
chunks
chunk_embeddings
data/evaluation/keyword_queries.csv
data/evaluation/hybrid_results.csv
```

数据安全边界：

- `stage17_retrieval_upgrade_results.csv` 是检索评测表，不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- `stage17_retrieval_upgrade_manual_review.csv` 是 Phase 9 人工复核结果表，只记录脱敏的复核判断（review_decision、retrieval_risk、evidence、tuning_suggestion 等），不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- `docs/stage17_retrieval_upgrade_report.md` 是只读报告（含 Phase 9 人工复核摘要），不触发真实 API；报告由已有结果 CSV 重生成，不跑检索、不访问数据库、不调用真实 provider。
- 阶段 17 使用 deterministic provider 运行默认评测，不让真实 API 成为 CI 或本地全量测试前提。
- 阶段 17 当前停在用户人工核验前状态，尚未提交、尚未打 `phase-17-complete` tag、尚未推送。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 18 语料扩充与评测/质量体系增强产物

阶段 18 新增或更新的工程与评测产物：

```text
docs/stage18_corpus_evaluation_quality.md
app/services/ingestion/pdf_text.py
scripts/expand_open_access_corpus.py
data/metadata/stage18_oa_discovery.csv
data/fulltext_manifest.csv（新增 5 行开放获取全文标注）
data/evaluation/stage18_hard_queries.csv
scripts/evaluate_stage18_hard_set.py
data/evaluation/stage18_hard_results.csv
data/evaluation/stage18_config_comparison.csv
data/evaluation/stage18_config_comparison_real.csv
data/evaluation/stage18_corpus_stats.csv
scripts/build_stage18_quality_report.py
data/evaluation/stage18_quality_summary.csv
docs/stage18_quality_report.md
app/frontend/quality_report.html
```

阶段 18 是本项目**首次新增外部资料来源**（开放获取全文），但严格限定在合规边界内：

- 只下载**许可允许的开放获取**全文（cc-by / cc-by-nc / cc0 / 明确 OA），来源经 OpenAlex 元数据 API 发现。
- 尊重 robots.txt 与网站条款；**不绕付费墙、登录、验证码**；下载有请求间隔。
- 受限全文（如 CNKI 机构授权）只留在本地授权环境（`data/fulltext/` gitignore），不公开分发、不进 Git。
- `data/app.sqlite`（`*.sqlite` gitignore）与 `data/fulltext/` 不提交；可提交物是解析器、manifest/source registry 条目、题录卡片和可复跑导入管线脚本。
- 真实导入篇数诚实记录：深度全文 11 -> 16（open_access_pdf 10 -> 15），未为凑 40-60 目标造假。
- 经 source registry 三层去重（DOI/URL/标题）与全文权限标注；`fulltext_manifest.csv` 只为真正新导入论文加行。

数据安全边界：

- `stage18_*` 评测/报告 CSV 与 HTML 只保存脱敏的查询、命中、排名、风险判断、来源标题和 quality gate 状态。
- 不保存 API key、Bearer token、供应商原始敏感响应或受限全文到 Git、CSV、文档、测试或 Obsidian。
- deterministic baseline 可复跑；真实 Jina 仅作发布前校准，不进 CI 或本地全量测试前提。
- `/quality-report` 及其导出端点只读取本地脱敏汇总 CSV，不触发真实 API、不写库、不做登录。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 18 之后增量：用户合法下载的中文全文语料

阶段 18 主体之后，用户提供了合法下载的中文堆石混凝土全文（约 324 篇，本地 `papers_NEW`），
通过 `scripts/import_papers_corpus.py` 入库 **298 篇**（24 篇扫描/损坏按用户决定放弃）。

合规与数据安全：

- 这批中文全文是用户**合法下载**的文献，仅保存到本地 DB（`data/app.sqlite`，gitignore）与
  `data/raw`（gitignore）；原始 PDF 与 DB **不进 Git、不公开分发**。
- 新增依赖 `cryptography>=3.1` 仅用于让 pypdf 读取用户**已合法获取**的 AES 加密 PDF，
  不绕任何 DRM、登录或授权。
- `source_type=institutional_access_pdf` 标注其为本地私有全文。
- 评测产物 `data/evaluation/cn_fulltext_queries.csv` / `cn_fulltext_results.csv` 只保存问题、
  脱敏的回答摘要、来源标题与拒答判断，不含 API key 或供应商原始响应。
- 真实 Jina/MIMO 仅用于本地真实检索/分析；deterministic 索引仍负责离线回归。

## 阶段 19 中文全文文献分析与检索/评测调优产物

阶段 19 新增或更新的工程与评测产物：

```text
docs/stage19_chinese_analysis_retrieval_tuning.md
docs/stage19_literature_review.md
scripts/explore_chinese_corpus.py
scripts/evaluate_stage19_retrieval_tuning.py
app/services/retrieval/source_type_reweight.py
data/evaluation/stage19_exploration_results.csv
data/evaluation/stage19_chinese_hard_queries.csv
data/evaluation/stage19_retrieval_tuning_results.csv
data/evaluation/stage19_retrieval_tuning_summary.csv
tests/test_stage19_chinese_hard_set.py
tests/test_stage19_retrieval_tuning.py
```

阶段 19 **不新增外部资料来源**，不新增爬虫链路，不保存受版权/受限全文。它只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/stage18_hard_queries.csv（仅引用对比，不修改）
```

这些文件不是新的文献资料来源。它们只记录：

- 中文研究问题、期望命中、期望来源类型、期望拒答、期望要点关键词、干扰主题。
- 探索/调优配置名、source_type 分布、深度全文/题录命中名次与占比、precision@1、mean_rank、refusal_accuracy、distinct_wins、decision/next_action。
- 真实 API 偶发失败显式写入 `error` 字段；不静默重试到成功掩盖失败。
- 回答摘要仅截取前 200 字，且不包含 API 原始响应、API key、Bearer token。

阶段 19 的核心关系是：

```text
已有 sources / documents / chunks（含约 340 篇中文深度全文）
-> hybrid retrieval（默认 0.7 keyword + 0.3 vector + 0.15 both_match）
-> Phase 0 真实/确定性 agent 探索（脱敏结果）
-> Phase 1 中文难评测集（19 题，独立 CSV）
-> Phase 2 source_type_reweight 4 配置对照（纯函数后处理）
-> Phase 3 文献分析快照（Markdown 引用现有 CSV）
```

合规结论：

- 阶段 19 不新增爬虫链路。
- 阶段 19 不新增外部文献或受限全文。
- 用户合法下载的中文全文继续只留在本地 `data/raw/` 与 `data/app.sqlite`（均 gitignore），不公开分发、不进 Git。
- 真实 MIMO+Jina 仍是模型服务，不是资料来源；真实 API key / Bearer token / 供应商原始响应仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- 自动回归继续使用 deterministic provider；真实模型只适合发布前质量校准或离线审阅。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。
- 阶段 19 已提交、创建 `phase-19-complete` tag 并合并到 `main`，成为阶段 20 的正确基线。

## 阶段 20 中文检索默认链路落地与评测判定增强产物

阶段 20 **不新增外部资料来源**，不新增爬虫链路，不保存受版权/受限全文，不重做 chunk embedding。它只读取现有阶段 18/19 语料、索引和评测集，并新增评测/报告产物：

```text
docs/stage20_default_chain_and_eval_upgrade.md
docs/stage20_quality_report.md
scripts/evaluate_stage20_eval_upgrade.py
scripts/build_stage20_default_chain_decision.py
scripts/build_stage20_quality_report.py
data/evaluation/stage20_eval_upgrade_results.csv
data/evaluation/stage20_eval_upgrade_summary.csv
data/evaluation/stage20_eval_upgrade_real_jina_results.csv
data/evaluation/stage20_eval_upgrade_real_jina_summary.csv
data/evaluation/stage20_default_chain_decision.csv
data/evaluation/stage20_quality_summary.csv
tests/test_stage20_default_chain_and_eval_upgrade.py
tests/test_stage20_eval_upgrade.py
tests/test_stage20_default_chain_decision.py
tests/test_stage20_quality_report.py
```

阶段 20 读取边界：

```text
data/evaluation/stage19_chinese_hard_queries.csv
data/evaluation/stage19_retrieval_tuning_summary.csv（只作历史对照）
sources
documents/chunks
chunk_embeddings（deterministic 与已有 Jina 索引）
```

这些文件不是新的文献资料来源。它们只记录：

- 查询编号、配置名、judge 模式、答案级 `coverage_ratio`、deep_fulltext top-1、拒答匹配、默认链路决策和下一步动作。
- 真实 Jina query-only 校验状态：`completed` / `skipped` / `error`，以及脱敏错误摘要。
- quality gate section、status、risk_level、evidence、decision、next_action。

合规结论：

- 阶段 20 不新增论文、PDF、CAJ、网页抓取或外部资料库。
- 中文全文继续只留在本地 `data/raw/`、`data/fulltext/`、`data/app.sqlite` 和已有 chunk/index 中，均不进入 Git。
- 真实 Jina 只在 query 端按需调用，不重做 8918 条 chunk embedding；真实 API key / Bearer token / 供应商原始响应不得写入 CSV、文档、测试或 Obsidian。
- `stage20_eval_upgrade_real_jina_*` 只保存脱敏评测指标和状态，不保存供应商原始响应或受限全文。
- `/quality-report` 当前读取阶段 20 脱敏 summary 与静态 HTML，不触发真实 API、不写库、不重新索引。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。
- 阶段 20 当前停在用户人工核验前状态，尚未提交、尚未创建 `phase-20-complete` tag、尚未推送。

## Stage 37 refinement data note

No new external data source was added for the Phase 37 runtime refinement. The new tool-calling controls operate only on existing local RAG search results from `search_knowledge` and `hybrid_search_knowledge`. Evaluation outputs were refreshed under `data/evaluation/`, including real-provider CSVs, but no source corpus expansion, recrawling, PDF download, or rechunking was performed.

## Phase 40 Corpus Import Closeout

Phase 40 added the authorized local paper expansion after the streaming output safety work. The import used existing ingestion boundaries: full-text PDFs and SQLite runtime state remain local and gitignored, while only scripts, metadata, evaluation summaries, tests, and documentation are committed.

Chinese institutional-access papers:

- Source directory: `G:\Codex\program\papers_0616`.
- Command: `python scripts/import_papers_corpus.py --dir "G:\Codex\program\papers_0616" --source-type institutional_access_pdf`.
- Dry-run found `150` real PDFs, not the originally estimated `155`: `rfc_core=109`, `dam_engineering=41`.
- Cumulative import result after fixing surrogate cleanup and per-file rollback: `imported=106`, `duplicate=55`, `empty=2`, `failed=0`, `new_chunks=6183`.
- Source type: `institutional_access_pdf`.

Zotero RFC-related English papers:

- Source directory: `C:\Users\admin\Zotero\storage`.
- Script: `scripts/import_stage40_zotero_rfc.py`.
- Filter: filename-only RFC context matching for `rock-filled`, `rock filled`, `rock-fill/rockfill` with dam/concrete context, `SCC` with concrete/rock/aggregate context, `stone-concrete` with dam/rockfill context, and `堆石`.
- Dry-run: `scanned_pdfs=66`, `matched_pdfs=9`.
- Formal import: `scanned_pdfs=67`, `matched_pdfs=9`, `imported=5`, `duplicate=4`, `empty=0`, `failed=0`, `new_chunks=372`.
- Source type: `open_access_pdf`.

Verified local corpus after Phase 40 import:

```text
documents: 753
chunks: 25687
institutional_access_pdf: 431
web_page: 136
metadata_record: 115
wikipedia: 25
open_access_pdf: 20
standard_document: 16
local_file: 10
```

Safety boundary:

- `data/app.sqlite`, `data/raw/`, `data/fulltext/`, and `data/faiss/` are gitignored and must not be staged.
- Imported full text stays local; no restricted PDF, API key, Bearer token, raw provider response, `reasoning_content`, hidden thought, or restricted full text is written into Git, CSV, docs, tests, or Obsidian.
- The Zotero filter intentionally excluded non-RFC rock support, mining, tunnel, foundation, and generic concrete papers to avoid corpus noise.

## Phase 41 Data Source Note

Phase 41 adds no external source, crawler, download, imported PDF, restricted full text, or new data-source category. It works only on the local corpus created by Phase 40.

The post-import retrieval refresh builds derived local artifacts:

- GLM-Embedding-3 embeddings for all 19300 indexable child chunks.
- deterministic embeddings for the same 19300 child chunks.
- parent chunk links for all ordinary child chunks.
- GLM and deterministic FAISS indexes under `data/faiss/`.
- post-import retrieval evaluation CSVs under `data/evaluation/`.

The local database still reports `documents=753` and `chunks=25687`. The chunk count includes Stage 31 parent rows; parent rows are context containers and intentionally do not receive embeddings or enter FAISS.

Data safety boundary:

- No API key, Bearer token, Authorization header, vendor raw response, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, or full chunk body is written to Git, CSV, tests, docs, or Obsidian.
- Runtime corpus and index state remains local and gitignored: `data/app.sqlite`, `data/raw/`, `data/fulltext/`, and `data/faiss/`.
- Evaluation CSVs contain only ids, categories, source types, metric numbers, top titles, and sanitized error summaries.

## Phase 45 Quality Repair Data Note

Phase 18-20 does not add a new external source. It cleans and reclassifies the same user-provided `papers_0618` batch. New artifacts are local quality-review derivatives:

- `phase18_image_quality_review.csv`
- `phase18_image_quality_summary.json`
- `phase19_embedding_summary.json`
- `phase19_image_embedding_summary.json`
- `phase20_image_embedding_summary.json`
- `phase20_migration_readiness.json`
- `phase20_asset_sync_manifest.json`

The repair removed deterministic template image descriptions from the real candidate corpus because those descriptions are test-provider artifacts, not genuine visual understanding. Real vision API responses and secrets are still not stored in docs, tests, Git, public CSVs, or Obsidian.

## Phase 47 Multimodal Interaction Data Note

Phase 47 does not add an external literature corpus, crawler, PDF download, or restricted full-text source. It adds interaction metadata and local runtime artifacts derived from existing documents and user actions.

New local/runtime data surfaces:

- `chunks.content_bbox_json`: optional page/bbox metadata derived from local PDFs for citation navigation.
- `qa_feedback`: local answer feedback rows with rating and optional sanitized reason/comment.
- `data/user_uploads/`: gitignored user-uploaded images used only for runtime image analysis.
- `data/evaluation/phase47_user_feedback_eval.csv`: sanitized positive-feedback export for future evaluation-set growth.
- `data/evaluation/phase47_orientation_*/` and `data/evaluation/phase47_doc1193_orientation_fix/`: local-only orientation repair reports and backups generated while re-rendering existing image assets from PDF display rectangles.

User-uploaded image analysis first creates a vision description, applies a domain-relevance gate, and only runs knowledge or similar-figure retrieval for in-scope RFC/hydraulic concrete/dam/concrete defect/table/curve/engineering-diagram images. Out-of-scope, uncertain, or deterministic test-vision cases return a refusal and do not recall corpus images.

Data safety boundary: no API key, Bearer token, Authorization header, vendor raw response, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, raw uploaded image bytes, or full feedback-sensitive material is written to Git, docs, tests, public CSVs, or Obsidian. Automated tests use deterministic/local providers only; real vision/model APIs are not a test prerequisite.

The orientation repair does not add a new source corpus. It rewrites derived local files under gitignored `data/images/` from the existing local PDFs and records local audit artifacts under ignored Phase 47 orientation directories.
## Phase 50 Phase 10-14 Redis Runtime Data Note

Phase 50 Phase 10-14 adds no external data source, crawler, PDF download, or production corpus category. It adds Redis runtime data only:

```text
semcache:{sha256(normalized_query)}
-> Redis Hash with query, mode, created_at, FLOAT32 embedding, payload JSON
-> payload contains answer, sources, citations, mode
-> no API keys, bearer tokens, provider raw responses, hidden reasoning, or restricted full text
```

```text
ratelimit:{client_ip}:{endpoint}
-> Redis ZSET of request timestamps
-> applies only to /agent/query and /agent/query/stream when enabled
-> Redis unavailable means fail-open; no request body is stored
```

Redis Stack indexes (`idx:semcache`, LangGraph checkpoint indexes) are derived runtime structures and are not committed. Phase 50 evaluation artifacts remain deterministic and safe for Git.
## Phase 50 pgvector Data Boundary Update

pgvector does not add any external data source. It stores a second database representation of embeddings already present in `chunk_embeddings.embedding_json`.

- Source of truth for corpus text/image/table chunks remains the existing PostgreSQL/SQLite tables.
- `embedding_vector Vector(2048)` is derived from GLM-Embedding-3 vectors and can be rebuilt from `embedding_json`.
- HNSW indexes are database indexes, not new content.
- Existing FAISS files under `data/faiss/` remain gitignored, rebuildable runtime artifacts and are kept as fallback.
- No API key, Bearer token, provider raw response, or restricted full text is written to docs, tests, CSV, Git, or Obsidian.

## Phase 54D Standards Batch Data Note

Phase 54D uses a user-provided local standards batch under `standards_0625`. The source standard files, rendered images, table assets, local SQLite database, FAISS indexes, and rebuilt knowledge graph JSON files remain local runtime data and are not committed.

Committed Phase 54D artifacts are derived evaluation outputs only: ids, labels, counts, short titles/headings, metric values, status fields, and reranking trace labels. They do not contain full chunk text, raw answers, provider raw responses, hidden reasoning, credentials, service logs, restricted full text, or source PDFs.

The standards batch was used to produce full LLM semantic supplementation for new standard text/table chunks, then rebuild the domain graph for the D experiment. The resulting production-risk conclusion is captured in `docs/phase_reviews/phase-54.md`: graph-intent answers improve strongly, while ordinary in-domain query routing still needs tuning before enabling the chain by default.

## Phase 55 Runtime Sync Data Boundary

Phase 55 adds no new external source corpus, crawler, PDF download, restricted full text, or user-profile data. It synchronizes the already-developed Phase 54 runtime state to the cloud readiness environment:

- PostgreSQL/pgvector tables and derived embedding rows.
- `data/images` runtime image assets.
- `data/faiss` derived FAISS files for the GLM-Embedding-3 2048-dimensional index.
- `data/knowledge_graph/domain_graph.json` derived GraphRAG asset.
- Sanitized quality report summary CSV used by `/quality-report/data.json`.

The synced cloud baseline is operational evidence, not a new data-source category. No API key, Bearer token, Authorization header, provider raw response, hidden reasoning, full answer text, full chunk body, restricted full text, source PDF, or private BGE service log is added to Git, docs, tests, public CSVs, or Obsidian.
