# 架构说明

## Phase 46 Architecture Delta: Image Repair And Caption Metadata

Phase 46 keeps the Phase 45 multimodal RAG shape but adds a targeted image-quality repair lane and a caption metadata lane.

Image repair lane:

```text
data/images + chunks.source_image_path
-> scripts/classify_phase46_problem_images.py
-> normal / type_a / type_b / type_c manifest
-> Type A/C cleanup
-> Type B page-level rendering
   page.get_image_info(xref=True)
   -> merge display bboxes
   -> page.get_pixmap(clip=merged_rect, dpi=150)
-> GLM-4.6V route staging
-> serial SQLite import
-> paratera embeddings + FAISS rebuild
```

Caption lane:

```text
PDF page text blocks via page.get_text("dict")
-> image display bbox from original xref or rendered-page merge
-> search below image bbox and top of next page
-> caption regex for Chinese 图/表 and English Fig/Figure/Table
-> chunks.caption nullable Text
-> retrieval result metadata
-> prompt ContextSource Caption line
-> AgentSearchItem / AgentSourceReference / API schemas
-> frontend figure evidence card title
```

Captions are metadata on `image_description` chunks. They do not replace the GLM visual description in `chunks.content`, and they do not change embedding vectors. FAISS remains derived from chunk embeddings; caption backfill does not require a vector rebuild unless content is changed.

The orientation residual audit was handled as Phase 5a by a subagent and reviewed by the main agent. It produced an audit report only: no remaining non-cleanup orientation candidate required additional page rendering or redescription.

Phase 46 extension decouples figure retrieval from text retrieval:

```text
ReAct planner
-> search_knowledge / hybrid_search_knowledge for text evidence
-> search_figures(query, top_k=4) only when visual evidence is useful
-> answer_with_citations
```

`search_figures` is a read-only Agent tool over `image_description` chunks. It embeds the visual query, searches the vector cache, filters to image chunks, enforces `MIN_IMAGE_RELEVANCE_SCORE=0.50`, verifies that the image file exists and is Pillow-readable with dimensions greater than 50px, deduplicates by `(document_id, page_number)`, and returns caption/page/document/image URL metadata. It does not depend on text-hit document ids.

Automatic `enrich_agent_response_with_figure_evidence()` is now gated by `ENABLE_AUTO_FIGURE_ENRICHMENT`, default `false`. `mode="react_agent"` never calls the automatic fallback, even if the flag is enabled; ReAct figure evidence must come from the `search_figures` tool. `/agent/query` and `/agent/query/stream` share the same helper. `/chat` remains unchanged.

The chunk metadata lane now includes nullable `chunks.page_number`, backfilled from `pageN_imgM.*` and `pageN_renderM.*` paths. Retrieval result objects, prompt context, Agent schemas, chat/document schemas, and frontend cards propagate this field. The frontend figure card source line is `图 X — 第 N 页 — 《文档标题》`.

Phase 46 image retrieval quality is measured by `data/evaluation/phase46_image_retrieval_questions.csv` and `scripts/evaluate_phase46_image_retrieval.py`. The script builds a temporary deterministic SQLite fixture and calls the real `AgentToolbox.search_figures()` without real API calls. The calibrated result is `image_precision=1.0000`, `image_recall=1.0000`, `image_suppression=1.0000`, with `threshold_decision=keep_current_threshold`.

Phase 16-21 adds a second, real-corpus image retrieval evaluation layer:

```text
local SQLite image_description chunks
+ caption / page_number / source_image_path / document title
-> scripts/build_phase46_real_image_retrieval_questions.py
-> 100-row real evaluation CSV
-> scripts/evaluate_phase46_real_image_retrieval.py
-> AgentToolbox.search_figures()
-> deterministic keyword/path/caption metrics
-> pass/fail gate for rerank or embedding readiness
```

The default evaluation mode is `stored_embedding_proxy`: it uses existing DB image embeddings as query-vector proxies for positive rows and zero vectors for suppression rows. This keeps the baseline offline and verifies the local FAISS/vector cache, threshold, image quality checks, deduplication, caption/page metadata, and deterministic relevance metrics without calling a real embedding API. The script also supports `--query-embedding-mode real` for later manually authorized natural-query embedding calibration; that mode is not a CI or full-test prerequisite.

The Phase 18 real-corpus offline baseline passed the requested gates:

```text
image_precision=0.9305
must_have_recall=1.0000
image_suppression=1.0000
topk_caption_match_rate=0.8800
wrong_generic_curve_rate=0.0000
threshold_decision=pass
```

Because the gate passed, Phase 19 did not change `search_figures` into caption-weighted soft rerank, and Phase 20 did not run embedding readiness. No text chunks, image descriptions, embeddings, DB rows, FAISS files, API handlers, or frontend code were changed by Phase 19-20.

## Phase 45 Additional Architecture Delta: Local Golden Corpus And Cloud Release Prep

The appended Phase 10-17 work keeps the same retrieval and Agent runtime, but adds a local-first corpus publication lane for the 2026-06-18 domestic paper batch.

```text
G:\Codex\program\papers_0618
-> scripts/build_phase45_literature_manifest.py
-> data/incoming/phase45_literature/manifest.csv/json
-> scripts/import_phase45_manifest_ready.py
-> local SQLite documents/chunks only
-> scripts/audit_phase45_import_quality.py
-> cloud_candidate / review_required split
-> scripts/index_phase45_cloud_candidates.py --chunk-type text
-> local GLM embeddings + FAISS rebuild
-> scripts/process_phase45_candidate_multimodal.py
-> image_description chunks
-> scripts/index_phase45_cloud_candidates.py --chunk-type image_description
-> local FAISS rebuild
-> scripts/prepare_phase45_cloud_migration.py
-> scripts/prepare_phase45_cloud_asset_sync.py
-> human verification before real PostgreSQL/file sync
```

Only `cloud_candidate` documents enter the candidate text/image indexing set. `review_required` documents stay in the local review queue until metadata, title/year extraction, scan quality, or text extraction issues are resolved.

Cloud release is intentionally split into PostgreSQL rows and filesystem assets. PostgreSQL stores paths and structured metadata; raw PDFs and extracted images must be synchronized separately. Cloud FAISS remains a derived runtime artifact and must be rebuilt from cloud PostgreSQL embeddings.

## Phase 45 Architecture Delta: Data Migration And Multimodal RAG

Phase 45 adds a database migration path and a multimodal ingestion path without changing the default Agent chain, Stage 30 scoring rules, provider topology, auth behavior, or data-source boundary.

Data migration:

```text
local SQLite
-> scripts/migrate_sqlite_to_postgres.py
-> target database from DATABASE_URL
-> documents / sources / chunks / chunk_embeddings / qa_logs
-> scripts/build_faiss_index.py --database-url
-> target FAISS index rebuilt from target DB embeddings
```

The migration is idempotent. Documents dedupe by `content_hash`, sources by `source_id`, chunks by mapped `document_id + chunk_index`, embeddings by mapped `chunk_id + provider + model_name`, and QA logs by question/answer/model/retrieval/created_at. Users, conversations, and messages are not migrated because they belong to authenticated cloud runtime state.

Multimodal RAG:

```text
PDF document.raw_path
-> PdfImageExtractor (PyMuPDF)
-> filter images with width or height < 100px
-> data/images/{document_id}/pageN_imgM.png
-> VisionModelProvider.describe_image()
-> Chunk(chunk_type="image_description", source_image_path=...)
-> VectorIndexService embedding
-> normal VectorSearchService / HybridSearchService retrieval
```

`image_description` chunks are text chunks generated from extracted images. They do not introduce a special retrieval route: the existing embedding, FAISS/numpy fallback, rerank, prompt assembly, citation, and refusal contracts continue to apply. The extra fields on `chunks` are `chunk_type` and `source_image_path`.

Vision models follow the existing provider pattern:

```text
VisionModelProvider
-> DeterministicVisionModelProvider (tests and local regression)
-> OpenAICompatibleVisionModelProvider (manual real-provider use)
```

Automated tests use deterministic vision only. Real vision API calls require explicit local configuration and must not become CI or local full-test prerequisites. Extracted images under `data/images/` are runtime artifacts and are gitignored like `data/raw/`, `data/fulltext/`, and `data/faiss/`.

## 阶段 43 架构增量：多轮对话质量与生产可观测性强化

阶段 43 不改变 Stage 30 评分规则、不替换 provider、不新增外部资料来源、不引入跨会话长期记忆或用户画像。架构增量集中在两个位置：多轮评测 + 会话内最小分层记忆，以及 request_id 全链路追踪 + 本地诊断端点。

多轮评测链路：

```text
data/evaluation/stage43_multi_turn_eval_cases.csv
-> scripts/evaluate_stage43_multi_turn.py
-> no_history / recent_only / summary_recent / layered_memory
-> deterministic lightweight corpus snapshot
-> stage43_multi_turn_baseline_results.csv
-> stage43_multi_turn_baseline_summary.csv
```

评测脚本默认 dry-run；`--no-dry-run` 使用本地 deterministic 轻量评分，不调用真实 provider。CSV 只保存 case id、scenario、history mode、命中/覆盖等指标和安全摘要，不保存 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、完整 chunk 或受限全文。

多轮 Judge 链路：

```text
data/evaluation/stage43_multi_turn_eval_cases.csv
-> scripts/judge_stage43_multi_turn_quality.py
-> dry-run plan or explicit --execute
-> AgentService answer generation with selected history mode
-> OpenAI-compatible Judge
-> stage43_multi_turn_judge_results.csv
-> stage43_multi_turn_judge_summary.csv
```

Judge 维度为 `answer_faithfulness`、`citation_accuracy`、`context_coherence`、`refusal_consistency`。脚本默认不调用真实 API；真实执行要求显式 `--execute` 和本地 provider 配置。由于真实 provider 运行较慢，单路执行支持逐行 checkpoint、重跑跳过 completed 行、按 `history_mode` 合并默认结果文件。Judge CSV 只保存分数、短理由、风险和 next_action，不保存完整答案、完整 chunk、raw provider response、`raw_response` 或 `reasoning_content`。

最小分层会话记忆：

```text
current conversation history
-> build_session_memory()
-> SessionMemory(entities, retrieval_anchors, constraints, stale_anchors)
-> augment_query_with_session_memory()
-> BrainService._rewrite_query_step()
-> retrieval query only
```

`SessionMemory` 位于 `app/services/conversation/session_memory.py`，只从当前 conversation 的 history 中提取 entities 与 retrieval_anchors，不写新表、不跨会话持久化、不形成用户画像。memory hint 明确标注“仅用于检索，不作为引用来源”。最终 answer generation 仍只使用 retrieval sources 构造可引用证据；summary 和 memory 都不能替代知识库证据。

Phase 16 增加纠错感知过滤：当当前问题包含“更正/我说错/想问”等纠错信号时，未在当前问题重申的旧 retrieval anchors 会进入 `stale_anchors`，不再写入 retrieval hint；当前问题中显式出现的领域词会补入新 retrieval anchors。`BrainService._rewrite_query_step()` 在这类问题上不再把上一轮完整原文前置到 query，避免已被纠正的旧目标污染检索。

request_id 追踪链路：

```text
FastAPI middleware
-> set_request_id()
-> start_request_trace()
-> log_event() structured logs
-> conversation / summary / memory / query rewrite / retrieval / provider / response events
-> finish_request_trace()
-> data/logs/request_traces.jsonl
```

`app/core/request_logger.py` 用 contextvars 聚合一次请求内的安全事件。`app/core/structured_logging.py::log_event()` best-effort 同步事件到当前 trace；失败不影响主请求。JSONL trace 存放在 `data/logs/`，该目录已 gitignore。trace 只保存 request_id、路径、状态、延迟、provider/model 名称、计数和短摘要等脱敏字段，不保存完整问题、完整 chunk、API key、Authorization、raw provider response、`reasoning_content` 或 hidden thought。

诊断端点：

```text
GET /health/details
-> SQLAlchemy SELECT 1 + documents/chunks count
-> data/faiss/*.index + *_ids.json metadata inspection
-> provider config booleans
-> no external provider ping
```

`GET /health` 保持轻量心跳不变。`GET /health/details` 只做本地 DB、FAISS 文件/metadata 和 provider 配置状态检查，不加载重型 FAISS 原生索引、不调用外部 chat/embedding/rerank provider，也不返回任何 key/header 字段。

HTTPS reverse proxy 模板：

```text
client
-> HTTPS Nginx/Caddy
-> HTTP uvicorn 127.0.0.1:8000
```

`deploy/nginx-https.example.conf` 与 `deploy/Caddyfile.example` 只是示例模板，不改变 Docker、CI 或运行时默认。模板传递 `X-Request-ID`，以便和 request trace 对齐；Nginx 模板对 `/agent/query/stream` 关闭 buffering，避免 SSE token streaming 被代理延迟。

## 阶段 42 架构增量：生成质量校准与生产体验完善

阶段 42 不修改 Stage 30 评分规则、不替换 provider、不改变数据源边界，也不引入 React/Vue/Node 构建链。架构增量集中在两个位置：离线 Judge 质量校准链路，以及原生前端会话/长回答体验。

```text
Stage 38 24 generation cases
+ Stage 41 12 post-import retrieval queries
-> scripts/judge_stage42_generation_quality.py
-> tool_calling_agent structured_final_answer
-> explicit --execute real Judge
-> sanitized CSV metrics / short reasons / risk levels
-> low-score analysis
-> tool-calling final-answer prompt calibration
```

阶段 42 的 Judge 脚本默认 dry-run，真实 Judge 必须显式 `--execute`。输出 CSV 只保存 case id、类别、分数、短理由、风险等级和 next_action，不保存 raw provider response、raw answer、`raw_response`、`reasoning_content`、hidden thought、API key 或 Bearer token。

prompt 校准落在 `app/services/agent/tool_calling_service.py::final_answer_strategy_instruction()`，而不是旧的普通 RAG prompt builder。原因是阶段 38 之后默认 Agent 链路是 tool-calling final synthesis：LLM 先通过工具召回证据，再由 tool-calling service 的最终答案策略生成引用式回答。阶段 42 只收紧 `structured_final_answer` 对比较题、多维题、质量控制题和新增语料题的覆盖要求，不改变 tool loop、provider 拓扑或 citation repair 规则。

前端长回答渲染仍保持原生 HTML/CSS/JS：

```text
finalizeAgentStreamingMessage()
-> renderSegmentedAnswerInto()
-> answerRenderSegments()
-> DocumentFragment
-> .answer-text--segmented > .answer-segment
```

流式阶段继续复用 Phase 40 的 token buffer 与 AbortController；最终回答落地时按段落和长度拆分为多个 segment，再批量 append 到 `.answer-text`。这样避免一次性大块 `innerHTML` 造成长回答 reflow 峰值，同时保留 sanitizer、citation button、invalid citation 标记和停止生成后的部分输出保留。

会话管理保持当前无认证前提下的简单 CRUD：

```text
PATCH /conversations/{conversation_id}
-> ConversationUpdateRequest(title)
-> ConversationRepository.rename_conversation()
-> ConversationItem

DELETE /conversations/{conversation_id}
-> hard delete
-> frontend fallback to remaining conversation / new conversation
```

重命名使用左侧会话列表的右键菜单触发，菜单靠近指针显示且不会切换当前会话；空标题归一化为“新对话”。删除同样从右键菜单触发并使用 hard delete，因为当前项目没有用户账号、归属权限、回收站或审计恢复模型。后续如果引入认证和多用户权限，再考虑 soft delete、删除审计和恢复。

## 阶段 40 架构增量：流式输出体验与输出安全

阶段 40 不修改默认 RAG / Agent 质量链路，不替换 provider，不改变 Stage 30 评分规则，也不新增外部数据源。架构增量集中在浏览器侧流式输出控制与最终渲染安全：

```text
POST /agent/query/stream
-> FastAPI StreamingResponse SSE
-> frontend fetch + response.body.getReader()
-> consumeSseBuffer()
-> createAgentTokenFlushScheduler()
-> sanitizeRenderedHtml()
-> citation-aware assistant message render
-> AbortController stop generation
```

`app/frontend/static/app.js` 新增 `sanitizeRenderedHtml()`，使用项目本地 allowlist 清洗回答 HTML。它删除危险标签、事件属性和 `javascript:` / `data:text/html` URL，同时保留项目需要的 `strong`、citation button、popover、状态 badge 和思考过程面板。当前没有引入运行时 CDN 或大型 Markdown 运行时依赖。

`streamAgentQuery()` 现在接受 `AbortController.signal` 并传给 `fetch`。`app/frontend/index.html` 增加 `data-agent-stop` 停止生成按钮；运行中按钮可见，点击后调用 `abortAgentStream()`。前端会中断浏览器侧 SSE 读取，保留已收到 token，给当前 assistant 气泡加 `chat-message--aborted` 和“已停止生成”状态，并恢复提交按钮，使用户可以继续发送新问题。

token 渲染从每个 token 立即写 DOM 改为 `createAgentTokenFlushScheduler()`：token 先进入 buffer，再用 `requestAnimationFrame` 和 32ms timeout 合并 flush。`metadata`、`done`、`error`、`abort` 到达时都会 `flushNow()`，避免最后一批 token 丢失。

后端边界需要诚实记录：`app/api/agent.py` 当前流式非闲聊路径使用 producer thread + queue。浏览器 abort 能停止前端读取和后续 UI 渲染，但如果 provider 调用已经在后台线程中执行，当前阶段不保证底层 provider 请求被立刻取消。阶段 40 不伪造成完全后端取消。

Current Phase 40 closeout calibration:

- The final UI does not use a separate stop button. While a request is running, the existing `data-agent-submit` button becomes the red stop-generation control (`command-button--stop`) and calls `abortAgentStream()`.
- `QueueStreamingChatModelProvider` now wraps the default tool-calling streaming path so final answers emit real `token` SSE events after tool execution.
- The corpus-import closeout added authorized local documents only: 106 Chinese `institutional_access_pdf` documents and 5 Zotero RFC-related `open_access_pdf` documents after dedupe. Runtime DB/PDF/index state stays local and gitignored.
- Verified closeout DB: `documents=753`, `chunks=25687`; full regression `821 passed`; Stage 30 remains `91.52 / A / pass`.

## 阶段 39 架构增量：生产部署与端到端体验

阶段 39 不修改默认 RAG / Agent 质量链路，不替换 provider，不改 Stage 30 评分规则，也不新增外部数据源。架构增量集中在运行时外壳和可观测体验：

```text
Docker / Compose
-> uvicorn app.main:app
-> FastAPI request middleware
-> structured JSON request logs
-> Agent safe event logs
-> frontend loading/error/citation UX
```

Dockerfile 已从旧 Chainlit CMD 切换为当前 FastAPI 入口：

```text
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

构建采用 builder/runtime 两阶段：builder 通过 `pyproject.toml` 构建 wheel，runtime 安装 wheel 并复制 `app/`。`docker-compose.yml` 负责注入 `APP_ENV=production`、挂载 `./data:/app/data`，并通过 Python 标准库访问 `GET /health` 做 healthcheck。

结构化日志位于 `app/core/structured_logging.py`。请求日志由 `app/main.py` middleware 写入 `request_completed` / `request_failed`，Agent 日志由 `app/api/agent.py` 和 `app/services/agent/tool_calling_service.py` 写入 `query_received`、`tool_call_executed`、`answer_generated`、`refusal_triggered`。日志只记录 request_id、method、path、status_code、latency、mode、计数和截断摘要，不记录 API key、Bearer token、Authorization header、raw provider response、`reasoning_content`、完整问题或完整 chunk。

前端仍是原生静态资源，不引入新框架。`app/frontend/static/app.js` 新增会话标题生成、中文友好错误、`[N]` 引用按钮和 hover 来源卡片；`styles.css` 新增加载 spinner 和引用浮层样式。它只改变展示体验，不改变 `tool_calling_agent` 默认链路、prompt、检索或评分。

## 阶段 38 架构增量：默认 Tool Calling 链路生成质量攻坚

阶段 38 不引入新外部数据源、不替换 provider 拓扑、不修改 Stage 30 评分规则，也不把 deterministic citation-validator 接入生产链路。增量集中在默认 `tool_calling_agent` 的最终答案生成约束、扩展评测、真实 Judge A/B 和默认入口稳定性回归。

```text
POST /agent/query or /agent/query/stream
-> omitted mode defaults to tool_calling_agent
-> ToolCallingAgentService(final_answer_strategy="structured_final_answer")
-> LLM(messages + tools)
-> hybrid_search_knowledge / search_knowledge tool calls
-> sanitized role="tool" evidence feedback
-> native tool-calling final synthesis
-> citation extraction / repair / refusal if unsupported
```

`ToolCallingFinalAnswerStrategy` 当前支持 `baseline` 和 `structured_final_answer`。`structured_final_answer` 已从 outline-first 改成 compact citation-first：先给 1-2 句带引用的直接回答，再按需输出最多 3-5 个短事实点，每个事实句或事实 bullet 都必须带最近的 `[N]` source marker；证据缺口用 evidence gap 明说，不推断补全。它不调用旧 `AgentToolbox.answer_with_citations` 作为最终生成器，因此不回退到 ReAct/Brain 的旧 answer tool 路径。

默认入口在阶段 38 被收紧：前端默认、`/agent/query` 省略 `mode`、`/agent/query/stream` 省略 `mode` 均进入 `tool_calling_agent`。显式 `mode="react_agent"` 继续作为回滚路径；显式 `mode="default"` 继续保留，用于旧 RAG 链路、source detail 和 follow-up transform 等能力。`ToolCallingAgentService` 还增加 provider capability 护栏：如果注入的 provider 不支持 `generate_with_tools`，API 返回受控 503，而不是暴露内部 AttributeError。

评测层新增两个 Stage 38 脚本：`evaluate_stage38_tool_calling_quality.py` 用 24 条、16 类场景做 deterministic 对照；`judge_stage38_tool_calling_quality.py` 用同一题集做 `baseline` vs `structured_final_answer` 真实 Judge A/B，默认 dry-run，显式 `--execute` 才调用真实 provider/Judge。CSV 只保存指标、风险、短理由和安全摘要，不保存答案全文、raw provider response、`reasoning_content`、hidden thought、API key 或 Bearer token。

真实 Judge 最终结论：baseline `answer_coverage=0.775 / citation_support=0.731 / safety=1.000 / review_required`，compact citation-first `structured_final_answer` 为 `0.808 / 0.867 / 1.000 / pass`。因此阶段 38 的架构决策是“保持默认 tool-calling，并保留 compact citation-first structured final answer”，而不是调权、接 deterministic 后处理或把旧 answer tool 硬接回生产。

## 阶段 37 架构增量：Tool Calling Loop 并行迁移

阶段 37 新增并行 `tool_calling_agent`，把 ReAct 自定义 JSON action loop 的一部分能力迁移到 OpenAI-compatible `tools/tool_calls` 协议上。关键点是：tool-calling 只是模型表达工具请求的协议，真正的 Agent 能力来自外层 loop。

```text
/agent/query mode="tool_calling_agent"
-> ToolCallingAgentService
-> chat_model.generate_with_tools(messages, tools)
-> tool_calls: 执行只读 search_knowledge / hybrid_search_knowledge
-> role="tool" 脱敏回灌 messages
-> 继续 loop，直到 content / 拒答 / max_iterations
```

新增 provider 协议结构位于 `app/services/generation/chat_model.py`：`ChatToolFunction`、`ChatToolDefinition`、`ChatToolCall`、`ToolCallingChatModelResult` 与 `generate_with_tools()`。旧 `generate()` / `stream_generate()` 行为保持兼容，现有 `/chat`、默认 Agent 与 `react_agent` 不被替换。

`app/services/agent/tool_calling_service.py` 是新并行 service。它只暴露只读检索工具，进入 loop 前执行责任边界与主题门，loop 内执行重复 query 防护、工具错误收敛、tool result 脱敏截断、引用校验和 latency trace 记录。tool result 回灌只包含 source title、source_type、chunk_id、chunk_index、score 和短 snippet，不回灌完整 chunk 全文、raw provider response、`reasoning_content` 或 hidden thought。

该架构与阶段 34 的 tiered provider 设计存在取舍：`react_agent` 可以使用 Flash planner + V4-Pro answer，而 `tool_calling_agent` 的 `LLM(messages, tools)` 同时承担工具决策和最终回答，因此第一版只能选择一个 tools-capable chat provider。选择 Flash 可能降低最终回答质量；选择 V4-Pro 可能让每次工具迭代都变慢，削弱 latency 收益。

引用边界也更严格：`tool_calling_agent` 要求最终 content 带有来自 tool result / sources 的有效 `[N]` 引用；如果真实模型给出有价值内容但漏写 citation marker，会安全拒答。阶段 37 评估脚本用 `refusal_reason_summary=missing_tool_backed_citations` 跟踪这种风险。

API 层在 `app/api/agent.py` 中为 `/agent/query` 和 `/agent/query/stream` 新增 `mode="tool_calling_agent"` 分支。SSE 事件通道泛化为安全 runtime event，可转发 `agent_step`、`tool_call_start` 和 `tool_call_result`，不暴露模型隐藏推理。

阶段 37 不引入 LangGraph，不做 checkpoint、human-in-the-loop 或复杂状态机编排；这些留到后续阶段根据评估结果再决定。

## 阶段 36 架构增量：生成可靠性与多轮体验稳定化

阶段 36 不改变默认 RAG 生产主链路，不替换 chat / embedding / rerank provider，不新增外部数据源，也不把 `citation_validator` 或其他 deterministic 后处理接回生产 Brain。增量集中在输出解释、生产 smoke、离线 Judge 实验和意图路由模块化。

```text
/agent/query
-> intent_router（meta / followup / refusal explanation / normal RAG）
-> AgentService / ReActAgentService / Agentic RAG
-> refusal_explainer（仅 refused=True 时追加安全解释到 reasoning_summary）
-> AgentQueryResponse（schema 不变）
```

`app/services/agent/refusal_explainer.py` 是输出层解释器：`off_topic` 给安全改写建议；`evidence_insufficient` 使用真实 source title / source_type / 短内容摘要生成检索摘要。它不调用 LLM、不读取内部规则原文、不输出完整 chunk。

`scripts/run_production_smoke.py` 是生产端点 smoke 脚本：默认 dry-run，显式 `--execute` 才访问 `/health`、`/quality-report`、`/quality-report/data.json`、`/agent/query` 和 `/agent/query/stream`。CSV 只记录安全字段，不保存 response body。

`app/services/generation/outline_first_strategy.py` 与 `scripts/judge_stage36_strategy_ab.py` 是离线 Judge A/B 基础设施。三组策略是 `baseline`、`outline_first`、`answer_provider_ab`。当前真实执行已完成 20 题 x 3 策略，结果分别为 baseline `0.655/0.640/1.000`、outline_first `0.703/0.685/1.000`、answer_provider_ab `0.772/0.820/0.950`，三组均为 `review_required`，因此不允许接生产或声明通过。

`app/services/agent/intent_router.py` 抽取多轮意图纯函数，覆盖上一轮翻译、追问、问来源、问模型、拒答原因、闲聊、off-topic 和正常领域问答回归。API 层继续负责会话读写和响应组装。

## 阶段 35 架构增量：检索质量校准与 Stage 30 评分破局

阶段 35 不替换默认 chat / embedding / rerank provider，不改变 `/chat`、`/agent/query`、`/agent/query/stream`、`/search/*` 或 `/quality-report` 的外部契约，而是在 evaluation -> retrieval -> generation -> quality gate 链路上做最小质量校准。

```text
stage34 decision report / stage30 deductions / real Judge
-> stage35 deduction root-cause analysis
-> leakage removal from keyword query expansion
-> HybridRrfTailSearchService for clean tail recall
-> provider-specific Stage 29 evaluation factory
-> prompt citation and coverage constraints
-> real Judge rerun with question + sanitized evidence snippets
-> Stage 30 score rerun and honest release_decision
```

新增 `scripts/analyze_stage35_deduction_causes.py` 作为评分归因层：它读取 `stage30_quality_deductions.csv`、`stage29_real_quality_results.csv` 与 `stage29_new_corpus_queries.csv`，把每条扣分映射到 `retrieval_miss`、`context_expansion_miss`、`prompt_citation_gap`、`answer_coverage_gap` 或 `rule_too_strict`。这层不参与线上请求，只把质量门失败转换为可执行修复任务。

检索层只做可解释 query expansion：阶段 35 已撤回把 `Alpe Gera Dam`、`road paving`、`vibratory rollers` 等评测答案词写入 `SYNONYM_RULES` 的泄漏规则；当前保留的是 RCC / roller-compacted concrete 等通用领域缩写与机制级排序修正，不重建索引、不新增外部数据、不替换 embedding。`evaluate_stage29_real_quality.py` 新增 provider 专用工厂，保证 Jina 使用 `jina-embeddings-v3 / dim=1024`，GLM 使用 `GLM-Embedding-3 / dim=2048`，避免评测污染。

生成层只强化 prompt 约束：`prompt_builder.py` 要求事实句逐句引用、引用贴近对应句子、不得引用不支持该句的 source、多要点问题覆盖上下文支持的各方面，缺失证据必须明说。既有 `extract_citations()` 与 `citation_check_node()` 继续过滤 / 检查无效 `[N]`，不改变 response schema。

Judge 层补齐评审输入完整性：`judge_stage34_generation_quality.py` 在 Stage 35 复用时加入 question 与每个 source 的脱敏短 `evidence_snippet`。输出仍只保存分数、短理由、风险等级、next_action 和安全摘要，不保存 API key、Bearer token、raw provider response、reasoning_content、hidden thought 或受限全文。

阶段 35 的 Stage 30 门禁已干净通过：在默认 GLM provider 与 `hybrid_rrf_tail` 检索链路上得到 `91.52 / A / pass`，且不改变评分权重、等级阈值、release decision 规则、provider 拓扑或外部数据源。真实 Judge 生成质量门仍诚实保留 FAIL：GLM 重跑在 validator 前为 `answer_coverage=0.525`、`citation_support=0.750`、`safety_leak_check=0.700`；validator drop 实验虽把 safety 修到 `1.000`，但 coverage/citation 降到 `0.410/0.635`，因此已从生产 Brain 路径解耦，仅保留为离线评测工具。

## 阶段 34 架构增量：RAG 性能瓶颈诊断、Embedding 决策与真实 Judge 复核

阶段 34 不替换默认 `/chat`、`/agent/query`、`/agent/query/stream` 或任何 provider，而是在 evaluation/reporting 层补齐三条决策链路：同环境 embedding 对照、真实 latency trace 归因和真实 LLM Judge 复核。

```text
stage33 latency trace / embedding migration results
-> stage34 GLM-Embedding-3 vs Jina same-environment comparison
-> stage34 real RAG/ReAct latency traces
-> stage34 bottleneck summary and report
-> stage34 optional real LLM Judge
-> stage34 decision summary and decision report
-> user manual review before commit/tag/push
```

阶段 34 对 `AgentService` default 路径补齐请求级 `LatencyTrace`。这是向后兼容增强：`AgentQueryResponse` 原本已有 `latency_trace` 字段，阶段 34 只是让 default Agent 与 `react_agent` 一样输出安全耗时数值。`/chat` schema 不新增 trace 字段，采集脚本只记录端到端耗时并标为 `endpoint_total_latency`，避免伪造内部瓶颈。

阶段 34 新增脚本均位于 evaluation/reporting 层：

- `scripts/collect_stage34_latency_traces.py`：默认 dry-run，显式 `--execute-real` 才使用真实 provider，输出脱敏 trace CSV。
- `scripts/analyze_stage34_latency_bottlenecks.py`：读取 trace CSV，输出 p50/p90、最大值、阶段占比和主要瓶颈。
- `scripts/judge_stage34_generation_quality.py`：默认 dry-run，显式 `--execute` 才调用真实 Judge，只保存分数、短理由、风险等级和 next_action。
- `scripts/build_stage34_decision_report.py`：汇总 embedding、latency、Judge 和阶段 30 分数，生成阶段 34 决策。

架构结论：阶段 34 的证据显示，当前慢点主要在 `tool_iteration_overhead`/answer/tool 链路，不在 FAISS/vector search；embedding 对照呈现 Jina top-5/coverage 更强、GLM top-3 更强的混合信号；Judge 分支为 `review_required`。

阶段 34 内追加的 chat provider 分层路由架构：

- 新增 `Settings.planner_chat_*` 配置组（与 `chat_model_*` 解耦），新增 `get_agent_planner_chat_model_provider()` 工厂依赖。
- `ReActAgentService.__init__(planner_chat_provider=None)`：缺省 None 时保持原 elif 短路 + chat_model_provider 兼容路径（deterministic 测试、agentic、default 不受影响）；不为 None 时禁用 elif 短路，让 LLM 每轮自主决策。
- 默认生产拓扑：`planner=Paratera DeepSeek-V4-Flash`、`answer=Paratera DeepSeek-V4-Pro`；MIMO 配置在 `.env` 中注释保留作回滚参考。
- 真实 trace 实测：react_agent p50 从 MIMO 基线 87.9s 降到 39.1s（-55%），p90 95.2s → 55.0s（-42%），10/10 完成；refusal_boundary 由 LLM 第 1 轮即 refuse（3.5s）。
- 协议层差距未消除：本项目 ReAct 协议「planner 决策 + answer 工具内 LLM 生成」每 run 仍比主流 tool-calling 多 1 次 LLM 调用。阶段 35 候选方向为 tool-calling 协议迁移，把 planner 决策和 answer 生成合并到同一次 LLM forward。

## 阶段 33 架构增量：RAG 链路性能优化与 Embedding 迁移验证

阶段 33 不替换默认 `/chat`、`/agent/query` 或 `/agent/query/stream` 的外部契约，而是在检索执行层、query embedding 层和可观测层补齐性能与迁移验证能力。核心目标是让真实 RAG/ReAct 链路更快、更可诊断，并诚实验证 GLM-Embedding-3（2048 维）迁移后是否存在静默退化。

```text
用户问题
-> VectorSearchService
   -> QueryEmbeddingCache(provider, model, dimension, normalized_query)
   -> embedding provider embed_query（cache miss 时）
-> VectorIndexCache
   -> complete FAISS index + complete ids + metadata match: faiss_only
   -> otherwise: SQLite embeddings -> numpy_fallback
-> HybridSearchService / rerank
-> BrainService or ReActAgentService
-> latency_trace metadata
-> JSON response or SSE metadata
```

`VectorIndexCache` 新增 `load_mode`。当本地 `data/faiss/{provider}_{model}_dim{dimension}.index` 与 `_ids.json` metadata 可加载、`complete=true`、provider/model/dimension 匹配、ids 无重复且完整覆盖当前有效 chunk metadata 时，缓存只加载 chunk/document metadata 和 FAISS index，不再反序列化 SQLite 中每条 embedding JSON，也不再构建 `_normalized_matrix`。任何文件缺失、损坏、维度不一致、provider/model 不一致、ids 不完整或 ids 与当前 metadata 不一致都会回退到旧的 SQLite/numpy 路径。

Query embedding cache 位于 `VectorSearchService` 内部，只缓存“问题 -> query 向量”的结果，不缓存文档写入型 embedding，也不修改 `chunk_embeddings` 或 FAISS 文件。cache key 包含 provider、model、dimension 和归一化后的 query text，并带 TTL 与 max size，避免同一请求或短时间重复查询反复调用真实 embedding provider。

Latency trace 是请求级安全观测对象。`app/services/observability/latency_trace.py` 使用 request-local context 记录 query_embedding、vector_search、faiss_search、numpy_search、rerank、planner、answer、tool、time_to_first_token、time_to_final、iteration_count 和 tool_call_count 等字段。它只记录数值、计数和阶段名，不记录 hidden thought、reasoning_content、raw provider response、API key、Bearer token、Authorization header 或受限全文。

阶段 33 的验证脚本保持“默认可离线、真实需显式”的边界：

- `scripts/benchmark_stage33_rag_latency.py`：默认 deterministic，可显式切真实 provider，输出脱敏延迟 CSV。
- `scripts/evaluate_stage33_embedding_migration.py`：对比 Jina 1024 维与 GLM-Embedding-3 2048 维；真实配置缺失时写 skipped，不伪造成成功。
- `scripts/benchmark_stage33_chat_providers.py`：MIMO 是 baseline，DeepSeek 只是 candidate；缺少 DeepSeek 配置时写 skipped，不切默认 provider。

阶段 33 保留旧 Jina FAISS 索引作为回滚保险和质量对照，也保留 GLM-Embedding-3 2048 维索引作为新链路验证目标；不删除旧向量、不直接切默认 MIMO/DeepSeek、不新增外部资料源、不做写入型 Agent 工具，也不让真实 API 成为 CI 或本地全量测试前提。

## 阶段 32 架构增量：ReAct Agent 决策升级与工具调用实时可视化

阶段 32 改动的是 `/agent/query` 的 Agent 编排层和 `/agent/query/stream` 的可观测输出层，不改变 `/chat` 默认 RAG 问答链路。新的 `react_agent` 路径让模型在受控 action schema 中选择下一步，但真正的工具执行仍由后端 `AgentToolbox` 负责。

```text
POST /agent/query or /agent/query/stream
-> chitchat short-circuit
-> mode == react_agent
-> ReActAgentService
   -> ReActAction schema validation
   -> action: search_knowledge
      -> AgentToolbox.hybrid_search_knowledge
      -> HybridSearchService / VectorIndexCache / FAISS or numpy fallback
      -> ParentChildSearchService / Brain context
   -> action: rewrite_query
      -> controlled query rewrite summary
   -> action: answer_with_citations
      -> AgentToolbox.answer_with_citations
      -> BrainService / CitationAnswerService
      -> citations, sources, evidence confidence, responsibility gate
   -> action: refuse or final_answer
-> AgentQueryResponse
-> token / metadata / done plus agent_step / tool_call_start / tool_call_result
```

`app/services/agent/react_actions.py` 定义阶段 32 的 action contract：只允许 `search_knowledge`、`rewrite_query`、`answer_with_citations`、`refuse`、`final_answer`。它同时提供 deterministic planner、重复 query 标准化、防护函数和 observation 摘要结构。非法 action、缺失字段或循环异常不会直接执行工具，而是收敛到可记录的失败 observation 或 refusal。

`app/services/agent/react_service.py` 实现 ReAct loop。硬上限为 3 轮；请求级 `max_tool_calls` 继续生效；重复 query 会被拦截；工具异常会记录为 observation，并在超过边界时收敛到拒答或已有证据答案。真实 provider 可通过结构化 JSON action 决策；自动测试默认使用 deterministic planner，不依赖真实 API。

SSE 协议保持向后兼容：

```text
旧事件：token, metadata, done, error
新增事件：agent_step, tool_call_start, tool_call_result
```

新增事件只包含安全摘要，例如 `step_summary`、`action`、`input_summary`、`observation_summary`、`decision_summary`，不展示模型 hidden thought、供应商原始响应、敏感凭据、授权头或受限全文。最终 `metadata` 仍携带 `workflow_steps`、`tool_calls`、`iteration_count`、`sources`、`citations`、`refusal_category` 等可追踪字段。

前端仍使用原生 HTML/CSS/JS。Agent 面板默认提交 `mode: "react_agent"`，pending assistant 气泡中只显示简洁中文状态，避免把每个 function call 事件刷成卡片；最终 metadata 到达后，助手气泡内用可折叠“查看思考过程”面板展示由正式 `workflow_steps` 校准的步骤和工具摘要。显式 API mode `default` 和 `agentic` 保留，便于对照、回退和人工核验。

阶段 32 评测新增 `scripts/evaluate_stage32_react_agent.py`。它使用 in-memory SQLite fixture、deterministic embedding/chat，并显式关闭 reranking provider，对照 `default`、`agentic_langgraph`、`react_agent`，输出 `stage32_react_agent_results.csv` 和 `stage32_react_agent_summary.csv`。该脚本不读取真实 API key，不调用真实 provider，不写业务数据库。

## 阶段 31 架构增量：FAISS 向量索引与父子块检索

阶段 31 改动默认 RAG 检索链路的底层执行方式，但保持外部 API schema 不变。核心思想是：child chunk 仍负责精确召回和引用，parent chunk 负责给生成模型提供更完整上下文；向量检索优先使用本地 FAISS `IndexFlatIP`，索引不可用时继续 fallback 到阶段 26 的 numpy 矩阵搜索。

```text
chunk_embeddings
-> scripts/build_faiss_index.py
-> data/faiss/{provider}_{model}_dim{dimension}.index
-> data/faiss/{provider}_{model}_dim{dimension}_ids.json
-> VectorIndexCache.search()
   -> complete FAISS index available: FAISS top-k
   -> otherwise: numpy fallback
-> VectorSearchService / HybridSearchService
-> ParentChildSearchService
   -> child.parent_chunk_id exists: parent.content as prompt context
   -> parent_chunk_id is NULL: ContextExpansionService fallback
-> BrainService prompt assembly
-> /chat and /agent/query
```

`app/services/retrieval/faiss_index.py` 封装 FAISS `IndexFlatIP` 的构建、保存、加载和搜索。所有 embedding 会先转为 `float32` 并做 L2 归一化，因此内积排序等价于旧链路的余弦相似度排序。阶段 31 暂不使用 `IndexHNSWFlat`，因为当前约 12K 条向量更需要精确可解释和 numpy 一致性；以后语料扩大到十万级时，可以在该封装层切换近似索引。

`scripts/build_faiss_index.py` 是只读构建脚本：它读取 SQLite 中 `chunk_embeddings` 与 `chunks.content_hash` 匹配的有效 embedding，不调用真实 API，不重建 embedding，不写数据库。生成的 `data/faiss/` 是可重建索引派生物，已加入 `.gitignore`。

`VectorIndexCache` 新增运行时索引选择逻辑。只有 metadata 中 provider、model、dimension 匹配，`complete=true`，并且 FAISS metadata 中的 chunk_id 都能映射回当前缓存 entries 时，才会启用 FAISS。任何缺失、不完整、维度不一致或加载失败都会回退 numpy，保证 deterministic provider 和 CI 不依赖本地 `.index` 文件。

`chunks.parent_chunk_id` 是阶段 31 的 schema 增量。它是 `chunks` 表的可空自引用字段：child chunk 指向 parent chunk，旧 chunk 保持 NULL。`scripts/migrate_parent_chunks.py` 负责幂等添加字段和索引；SQLite 对已有表无法在 `ALTER TABLE` 中补完整外键约束，因此当前阶段依赖 ORM relationship、应用层校验和测试覆盖。

阶段 31 追加完成了历史数据非破坏性回填。`scripts/backfill_parent_chunks.py` 按每个 document 的既有 child `chunk_index` 顺序拼接文本，切出约 1,800 字符的 parent chunk，再用字符区间重叠把既有 child 的 `parent_chunk_id` 指向对应 parent。脚本支持 `--dry-run` 和幂等重跑；本地结果为 12,716 个既有 child 全部关联 parent，新增 6,402 个 parent，parent 不生成 embedding。

父子块检索新增两层服务：

- `app/services/ingestion/parent_chunker.py`：把文档文本先切成较大的 parent，再在 parent 内切较小的 child；设计上只对 child 生成 embedding，parent 不进入 FAISS。
- `app/services/retrieval/parent_child_search.py`：把检索命中的 child 扩展为 parent 上下文；引用仍保留 child `chunk_id`，便于精确溯源。

前端架构只做显示优先级调整。`app/frontend/index.html` 保留原有 Agent 请求字段，但把 `top_k`、`max_tool_calls`、`source_id` 放入 `<details>` 高级设置；后端接口没有删除这些参数，因此 `POST /agent/query` 的能力不变。

阶段 31 验证基线：

```text
FAISS full index: vectors=12716
stage30 score: overall=83.17 grade=B release_decision=review_required
focused tests: 24 passed
full tests: 589 passed
real provider smoke: /health, /quality-report, /search, /search/vector, /search/hybrid, /chat, /agent/query all 200
```

阶段 31 同时修复了真实 provider HTTP 路径的本机卡顿问题。`OpenAICompatibleEmbeddingProvider`、`OpenAICompatibleReRankingProvider` 和 `OpenAICompatibleChatModelProvider` 现在通过 `ProxyHandler({})` 显式禁用系统代理探测；这不是降级，仍然调用真实供应商，只是避免 Python `urllib` 在当前 Windows 环境里卡在系统代理/TLS 路径。本地 `.env` 的 `EMBEDDING_PROVIDER` 已改为 `jina`，与数据库中的 `jina/jina-embeddings-v3/dim=1024` 和 FAISS 索引 metadata 对齐。

## 阶段 30 架构增量：RAG 质量评分体系与诚实决策门禁

阶段 30 不改默认 RAG 检索、问答、Agent 或 SSE 运行链路，而是在 evaluation/reporting 层新增一条只读评分链路。它把阶段 29 的真实评测产物、阶段 30 权重配置和工程健康 artifact 合成为可解释总分、等级、发布建议、扣分项和推荐动作。

```text
stage29_real_quality_results.csv
stage29_real_quality_summary.csv
-> stage30_scoring_weights.yaml
-> stage30_engineering_health.json
-> score_stage30_quality.py
-> stage30_quality_scores.csv
-> stage30_quality_summary.csv
-> stage30_quality_deductions.csv
-> build_stage30_quality_report.py
-> docs/stage30_quality_score_report.md
-> app/frontend/quality_report.html
-> GET /quality-report
```

`scripts/score_stage30_quality.py` 是纯读取评分器：不运行 pytest、不重建 embedding、不写数据库、不调用真实 API。它读取 `data/evaluation/stage30_scoring_weights.yaml`，因此 retrieval_quality、rule_based_context_answer_quality、safety_refusal、source_quality 和 engineering_health 的权重不硬编码在业务逻辑中。

`scripts/collect_stage30_engineering_health.py` 独立生成 `data/evaluation/stage30_engineering_health.json`，记录全量测试状态、chunk/embedding 计数、Jina/deterministic embedding 覆盖、孤立 embedding、重复 provider/model/chunk 组合和 `/quality-report` 冒烟结果。评分器只读取该 JSON，不自己采集重任务。

`scripts/judge_stage30_semantic_quality.py` 是可选 LLM-as-Judge 手动支路，默认 dry-run，不调用真实模型；只有用户显式传入 `--execute`，并在本地环境变量提供 `STAGE30_JUDGE_API_KEY` 时，才会调用 DeepSeek/OpenAI-compatible provider。真正的 `faithfulness`、`answer_relevancy`、`groundedness` 只能从这类手动语义评审支路产生，不能由默认规则评分冒充。

`GET /quality-report` 继续是静态只读报告入口。阶段 30 后 `/quality-report/data.json` 和 `/quality-report/export.csv` 读取 `stage30_quality_summary.csv`；页面内联展示最新评分、维度分、扣分项和推荐动作，不触发真实模型、不写库、不暴露密钥或供应商原始响应。

## 阶段 29 架构增量：真实 Embedding 重建与端到端质量闭环

阶段 29 不新增外部资料采集入口，而是把阶段 28 已入库的新语料纳入真实语义检索质量闭环。核心变化在 Embedding 构建、评测脚本和质量报告展示三处：

```text
chunk_embeddings 历史数据
-> cleanup_stale_embeddings.py --execute
-> chunk_embeddings 21634 -> 0

chunks 12716
-> build_vector_index.py --provider jina
-> chunk_embeddings: jina/jina-embeddings-v3/dim=1024 12716

chunks 12716
-> build_vector_index.py --provider deterministic
-> chunk_embeddings: deterministic/hash-token-v1/dim=64 12716

stage29_new_corpus_queries.csv
-> evaluate_stage29_real_quality.py
-> stage29_real_quality_results.csv
-> stage29_real_quality_summary.csv
-> build_stage29_quality_report.py
-> docs/stage29_quality_report.md
-> app/frontend/quality_report.html
-> GET /quality-report
```

`create_embedding_provider()` 在阶段 29 支持 `provider="jina"` 作为 OpenAI-compatible embedding provider 的显式别名。这样数据库中的 provider 名称能区分真实 Jina embedding 与其他 OpenAI-compatible 供应商，同时继续复用既有 HTTP 适配、批处理、重试和向量写入逻辑。

阶段 29 的质量闭环故意把“真实检索质量”和“CI 可复现测试”分开：真实评测使用 Jina v3 embedding；pytest 和 deterministic embedding 仍保持离线、可重复、不依赖 API key。`/quality-report` 展示的是评测与数据质量摘要，不调用真实供应商，也不暴露供应商原始响应。

## 阶段 28 续架构增量

阶段 28 续在原有 Crawling 层之后补齐三类数据治理能力：低质量语料删除、Wikipedia 百科补充、公开标准 PDF 补充。它们都复用既有 `IngestionService.import_document()`、文本清洗、切分、Source Registry 和 deterministic 索引重建链路，不引入第二套入库系统。

```text
drop_candidates.csv
-> cleanup_drop_candidates.py
-> documents/chunks/chunk_embeddings 级联清理
-> sources.document_id SET NULL
-> 删除 data/raw/web_crawl/*.md
-> deterministic 索引重建

wikipedia_articles.csv
-> Wikipedia REST API HTML
-> WebContentExtractor
-> data/raw/wikipedia/*.md
-> IngestionService.import_document(source_type="wikipedia")
-> SourceRegistryService
-> deterministic 索引重建

standards_urls.csv
-> 公开 PDF 下载（<= 20MB，限速 >= 2 秒）
-> data/raw/standards/*.pdf
-> IngestionService.import_document(source_type="standard_document")
-> SourceRegistryService
-> deterministic 索引重建
```

安全边界：Wikipedia 和公开 PDF 入库脚本都不需要 API key，不绕登录、验证码或付费墙，不伪装浏览器；测试使用 mock 或 deterministic provider，不让真实网络或真实 API 成为 CI 前提。

## 总体流程

```text
资料来源
-> source registry 登记与治理
-> 本地文件导入或阶段 28 网页爬取
-> robots.txt / 限速 / User-Agent 安全边界
-> trafilatura 正文提取为 Markdown
-> 文本抽取
-> 清洗
-> 切分 chunk
-> embedding 向量化
-> 向量索引
-> 用户提问
-> Brain 中控层
-> 检索召回
-> 组织上下文
-> 大模型回答
-> 返回答案和引用来源
-> Agent 工具编排
-> Agentic 可观测响应契约
-> Agent 自动模式路由
-> 会话历史装配与摘要压缩
-> 路由层闲聊短路
-> ChatModelProvider 流式生成
-> /agent/query/stream SSE 输出
-> VectorIndexCache numpy 向量矩阵缓存
-> hybrid search 并行召回
-> ReRankingProvider Cross-Encoder 重排序
-> 前端工作台展示、聊天气泡、会话管理、只读模式指示、步骤可视化和打字机式流式输出
-> Chainlit 对话界面复用同一 Agent service 层，展示流式回答、workflow steps 和 citations
-> Docker Compose 本地容器运行
-> GitHub Actions deterministic pytest CI
```

## 初始分层

```text
API 层：FastAPI 路由，含同步 JSON 端点和阶段 25 `/agent/query/stream` SSE 端点
Schema 层：Pydantic 请求和响应模型
Service 层：导入、切分、检索、问答业务逻辑；阶段 26 后向量检索使用 `VectorIndexCache` + numpy 矩阵运算，hybrid search 默认并行召回并执行可配置 rerank
Crawling 层：阶段 28 新增的公开网页采集入口，负责 seed URL 状态管理、robots.txt 检查、限速 HTTP 抓取、trafilatura 正文提取、Markdown 落盘和复用 IngestionService 入库
Agent 层：受控工具封装、意图路由、工具调用记录和拒答约束；阶段 25 后社交闲聊短路位于 API 路由层，不再由 AgentService 承担
Agentic 层：LangGraph 状态图编排，迭代式 retrieve-grade-rewrite-generate 循环（阶段 21），向前端暴露只读可观测字段（阶段 22），在阶段 23 通过规则式复杂度路由接入 `/agent/query` 自动分流，并在阶段 24 的 generate 节点利用会话 history 补全追问
Brain 层：RAG workflow 中控、RetrievalConfig、WorkflowConfig、step 记录和 chat/agent 复用
Conversation 层：会话历史装配、Conversation/Message 持久化、长对话 summary 压缩和 `/conversations` API；闲聊消息可持久化但跳过 summary
DB 层：文档、chunk、问答日志元数据、会话和消息
Source Registry 层：来源登记、去重、可信度、全文权限和重新索引
Model Provider 层：聊天模型、embedding 模型和 reranking 模型适配；阶段 25 后聊天模型 Provider 同时支持 `generate()` 和 `stream_generate()`，阶段 26 后 reranking Provider 支持 deterministic 与 OpenAI-compatible 两类实现
Frontend 层：来源、资料、检索、问答、引用来源展示，以及 Agent 聊天气泡、会话管理、自动模式结果指示、workflow 步骤可视化和 SSE token 追加；阶段 27 后新增 Chainlit 对话界面入口，并在 Phase 7 将原生 FastAPI 首页升级为深色科技风产品首页
Deployment 层：阶段 27 后提供 Dockerfile、docker-compose 和 GitHub Actions CI；容器运行默认启动 Chainlit，CI 只运行 deterministic pytest
```

## 阶段 28 网页爬取与自动入库架构

阶段 28 在现有 IngestionService 上游新增 Crawling 层，不改变 FastAPI API、Chainlit 入口或默认问答链路。核心目标是让用户在本机运行爬取程序，由程序自行联网抓取公开 HTML 页面，再进入既有 RAG 入库链路：

```text
data/crawl/seed_urls.csv
-> scripts/crawl_and_ingest.py
-> CrawlUrlManager
   -> seed 去重
   -> crawl_results.csv 状态跟踪
-> WebFetcher
   -> robots.txt 检查
   -> 默认 delay >= 2 秒
   -> RFC-RAG-Agent User-Agent
   -> urllib 普通 HTTP GET
-> WebContentExtractor
   -> trafilatura.extract(output_format="markdown")
   -> 标题/作者/时间等元数据
-> WebCrawlIngestionPipeline
   -> 写入 data/raw/web_crawl/*.md
   -> IngestionService.import_document()
   -> SourceRegistryService.register_candidate()
-> documents / chunks / sources
-> scripts/build_vector_index.py --provider deterministic
-> chunk_embeddings
```

`WebCrawlIngestionPipeline` 只做编排，不复制清洗、切分、去重或数据库写入逻辑。正文清洗仍由 `clean_text()` 负责，chunk 切分仍由 `split_text()` 负责，document/chunk 写入仍由 `DocumentRepository` 负责，来源治理仍通过 `SourceRegistryService` 写入 `sources`。

受控同站发现通过 `--discover-links` 显式启用，默认关闭。启用后只保留同 host 的 HTTP(S) 链接，去除 fragment，过滤 PDF、图片、压缩包、脚本、样式等常见二进制/静态资源，并通过 `--max-discovered-per-page` 限制扩展规模。它用于补充公开站内页面，不用于绕过 robots.txt、登录、验证码、付费墙或浏览器渲染限制。

阶段 28 的 CLI 支持 `--quiet`，用于用户自行长时间本地运行时只输出汇总，避免逐 URL 日志刷屏。真实批量爬取不依赖大模型上下文；大模型只负责开发程序、解释用法、审查聚合结果。

测试边界：

- fetcher/extractor/url_manager/pipeline/CLI 单元测试使用 fake HTTP、fixture 或 mock，不依赖真实网页。
- `tests/conftest.py` 在 pytest 进程中强制 reranking provider 为 deterministic，避免本地 `.env` 的真实 reranker 配置影响全量测试。
- CI 仍不要求真实 API key、真实网页或 Docker daemon。

## 阶段 27 Chainlit 前端、Docker 与 CI 架构

阶段 27 不替换 FastAPI API，也不删除 `app/frontend/` 原生工作台。新增的是一个并列入口：

```text
浏览器
-> Chainlit server
-> chainlit_app.py
-> @cl.on_message
-> stream_agent_query_events()
   -> detect_chitchat()
   -> default AgentService 或 agentic LangGraph
   -> ChatModelProvider.stream_generate()
-> msg.stream_token()
-> cl.Text citations / workflow summary
-> cl.Step workflow steps
-> ConversationRepository 保存会话消息
```

`chainlit_app.py` 复用阶段 25 `/agent/query/stream` 背后的 service 层函数，而不是对本机 FastAPI 发 HTTP 请求。这样可以避免容器内“服务调用自己”的端口和启动顺序问题，也能让 Chainlit 与 FastAPI API 共享同一套请求校验、闲聊短路、自动模式路由、引用契约和会话持久化逻辑。

Phase 7 继续保留双入口策略：Docker Compose 默认入口仍是 Chainlit，原生 FastAPI 前端作为 `GET /` 调试和作品展示入口单独运行。`app/frontend/index.html` 使用深色科技风 hero、能力卡片、真实 Agent demo 面板和资料库工作台；用户反馈页面杂乱后，进一步拆成“开始问答”和“资料库”两个原生视图，通过 `data-view-target` / `data-view` 切换。所有交互仍复用原有 data hook 与 `app/frontend/static/app.js`，不引入 Node/React/Vue，也不改变 RAG 后端契约。

Chainlit 展示映射：

- `token` 事件：追加到同一个 assistant message，通过 `msg.stream_token()` 形成流式回答。
- `metadata` 事件：解析为 `AgentQueryResponse`，用于组装 citations、sources、mode、workflow、iteration_count、invalid_citations 和 refusal 信息。
- `workflow_steps`：以 `cl.Step` 展示步骤名称、状态、输入摘要、输出摘要和错误摘要。
- `sources` / `citations`：以 `cl.Text` 展示引用编号、标题、chunk/document/source 标识和分数。

容器化边界：

```text
Dockerfile
-> python:3.11-slim
-> pip install .
-> chainlit run chainlit_app.py --host 0.0.0.0 --port 8000 --headless

docker-compose.yml
-> env_file: .env
-> DATABASE_URL=sqlite:////app/data/app.sqlite
-> ./data:/app/data
```

`.dockerignore` 排除 `.env`、SQLite 数据文件、`data/raw`、`data/fulltext`、Obsidian 知识库、虚拟环境、缓存和构建产物。镜像只包含可重建代码、配置模板和静态资产；本地运行数据通过 volume 注入。

CI 边界：

```text
.github/workflows/ci.yml
-> push main/codex/**/claude/** 或 PR main
-> Python 3.11
-> python -m pip install -e ".[dev]"
-> deterministic chat / embedding / reranking provider
-> python -m pytest -q
```

CI 不需要真实 API key，不读取 `.env`，不依赖 Docker daemon，也不访问受限全文。

## 阶段 26 检索性能优化与重排序架构

阶段 26 不改变外部 API 路径，而是在检索服务内部优化性能并加入可配置精排层：

```text
用户问题
-> embedding_provider.embed_query()
-> VectorIndexCache.search()
   -> numpy normalized_matrix @ query_vector
-> KeywordSearchService.search()
-> HybridSearchService ThreadPoolExecutor 并行等待两路召回
-> merge / normalize / both_match_bonus
-> ReRankingProvider.rerank(query, top-20~30 candidates)
-> top-k HybridSearchResult
-> Brain / Chat / Agent / SSE 复用结果
```

`VectorIndexCache` 位于 `app/services/retrieval/vector_cache.py`。它将 `chunk_embeddings` 表中同一 provider/model/dimension 的向量加载为 numpy `float64` 矩阵，并保存每一行对应的 chunk/document 元数据。缓存内容来自已有数据库索引，是可重建数据，不新增资料来源。

`VectorSearchService` 仍负责 query 校验、query embedding、零向量处理和 topic anchor 排序。区别是它不再每次调用 `_list_indexed_chunks()` 全表加载 ORM 对象，而是向 `VectorIndexCache` 请求矩阵相似度结果。纯 Python `cosine_similarity()` 保留为测试对照，确保 numpy 分数误差 `< 1e-6`。

`HybridSearchService` 默认使用 `ThreadPoolExecutor(max_workers=2)` 并行执行 keyword/BM25 与 vector search。由于 SQLAlchemy `Session` 不是跨线程共享对象，每个 worker 都基于同一个 engine 创建独立 Session，主线程只合并普通 Python 结果对象。

`ReRankingProvider` 位于 `app/services/retrieval/reranking.py`。阶段 26 提供：

```text
DeterministicReRankingProvider
  本地规则式 keyword overlap 打分，用于 CI 和离线测试。

OpenAICompatibleReRankingProvider
  运行时可选 HTTP rerank API，解析 /rerank 响应，不进入全量测试前提。
```

默认配置启用 deterministic rerank。hybrid search 先召回 `max(top_k * 5, reranking_recall_k)` 个候选，再精排返回 top-k。当前 `HybridSearchResult.score` 仍保留原 hybrid score，rerank 只改变顺序；如果后续要展示 rerank score，需要单独扩展 schema。

阶段 26 基准脚本：

```text
scripts/benchmark_retrieval.py
```

默认使用 deterministic embedding provider，避免普通基准运行触发真实 API。它记录 query embedding、keyword、vector、hybrid、rerank-only 和 agent_query 端到端耗时。

## 阶段 25 闲聊短路与 SSE 流式输出架构

阶段 25 不改变默认 `/chat`，也不改变同步 `/agent/query` 的 JSON 契约。新增边界集中在 `/agent/query` 路由入口、`ChatModelProvider` 协议、并行流式端点 `/agent/query/stream` 和前端 Agent 面板：

```text
前端 Agent 面板
-> submitAgent()
-> POST /agent/query/stream { question, source_id?, conversation_id? }
-> 后端校验 conversation_id 并加载 history
-> detect_chitchat(question)
   -> 命中：token/metadata/done，保存消息但跳过 summary
   -> 未命中：classify_query_complexity()
-> default AgentService 或 agentic graph
-> QueueStreamingChatModelProvider 将 stream_generate() token 放入队列
-> event: token ... event: metadata ... event: done
-> 前端逐 token 追加助手气泡
-> metadata 回填 citations/mode/workflow/refusal
```

闲聊短路规则：

- `app/services/agent/chitchat.py` 只负责识别社交意图和返回预设回复，不读取资料库，不调用 LLM。
- `/agent/query` 与 `/agent/query/stream` 都在 `classify_query_complexity()` 之前调用 `detect_chitchat()`，保证 default 和 agentic 路径都不会收到闲聊问题。
- 当前覆盖五类意图：`greeting`、`thanks`、`goodbye`、`acknowledgment`、`help`。
- 闲聊命中并带 `conversation_id` 时，仍保存 user/assistant 消息，方便前端刷新恢复；但 `summarize=False`，避免大量“你好/谢谢/好的”污染长对话 summary。
- `AgentService.detect_intent()` 不再包含 greeting 分支，继续只处理 RAG/资料查询相关意图。

流式 Provider 协议：

```text
ChatModelProvider.generate(messages) -> ChatModelResult
ChatModelProvider.stream_generate(messages) -> Iterator[str]
```

- `DeterministicChatModelProvider.stream_generate()` 先得到确定性完整答案，再按稳定文本片段 yield，用于本地和 CI 测试。
- `OpenAICompatibleChatModelProvider.stream_generate()` 发送 `stream=true`，读取 OpenAI-compatible SSE 行，只把 `choices[].delta.content` 暴露为业务 token。
- Provider 层不把 API key、Authorization header、供应商原始敏感响应或 raw_response 写入 SSE metadata。

SSE 端点事件格式：

```text
event: token
data: {"text":"..."}

event: metadata
data: {完整 AgentQueryResponse JSON}

event: done
data: {}

event: error
data: {"message":"..."}
```

- default 和 agentic 路径的 retrieve、grade、rewrite、citation_check 仍同步执行；阶段 25 只让 generate 阶段流式输出。
- `QueueStreamingChatModelProvider` 用于兼容现有 `AgentService` / agentic 图：业务代码仍调用 `generate()`，wrapper 内部优先消费底层 `stream_generate()`，每得到一个 token 就放入线程安全队列；SSE generator 从队列取出后立即 yield `event: token`。
- 非闲聊路径在后台生产者线程中执行现有 Agent/RAG 链路，主 generator 负责持续读取 token 队列，因此不会等完整 `AgentQueryResponse` 构造完才开始输出。
- 流完成后才持久化完整 assistant 消息并触发 summary；中途错误不保存半成品助手消息。
- metadata 事件复用 `AgentQueryResponse.model_dump(mode="json")`，前端可以沿用同步端点的 citations、sources、workflow_steps、invalid_citations、refusal_category、mode 和 iteration_count 展示逻辑。

前端消费方式：

- 因为 Agent 请求需要 POST JSON body，前端使用 `fetch()` + `response.body.getReader()` + `TextDecoder` 手动解析 SSE，不使用只适合 GET 的 `EventSource`。
- `token` 事件通过 `textContent` 追加到当前助手气泡的 `.answer-text`，第一个 token 到达时替换“正在思考...”。
- `metadata` 事件到达后，复用 `agentAnswerHtml()` 重绘同一个助手气泡底部的引用、来源、模式、workflow 和拒答信息。
- 如果流式请求在收到任何 token 前失败，前端 fallback 到同步 `/agent/query`；如果已经开始输出 token 后失败，则显示错误气泡，避免同一轮出现两条助手回答。

## 阶段 24 多轮对话 UI 与会话持久化架构

阶段 24 不改变默认 `/chat`，也不把会话系统扩展成跨会话长期记忆。新增边界集中在 `/conversations` 与 `/agent/query`：

```text
前端 Agent 面板
-> loadAgentConversations()
-> GET /conversations
-> 选择或创建 currentConversationId
-> submitAgent()
-> POST /agent/query { question, source_id?, conversation_id }
-> 后端加载 conversation messages
-> history_from_messages()
-> default AgentService.query(history=...) 或 run_agentic_rag(history=...)
-> 成功后保存 user / assistant Message
-> summarize_conversation_if_needed()
-> 前端追加 user / assistant 气泡并刷新会话列表
```

新增数据库模型：

```text
Conversation
  id
  title
  created_at
  updated_at

Message
  id
  conversation_id -> conversations.id
  role: user / assistant / summary
  content
  mode
  metadata_json
  created_at
```

`ConversationRepository` 是会话读写边界，负责创建会话、列出最近会话、读取消息、追加消息、删除会话、默认标题生成和 metadata JSON 序列化。删除会话时通过 ORM cascade 删除对应消息。

会话 API：

```text
POST /conversations
GET /conversations
GET /conversations/{conversation_id}/messages
DELETE /conversations/{conversation_id}
```

`/agent/query` 的兼容规则：

- `conversation_id` 不传：保持阶段 23 单次 Agent 行为，不写会话，不加载服务端历史。
- `conversation_id` 传入：先校验会话存在，读取消息并装配 history；响应成功后再保存 user 和 assistant 消息，避免失败请求留下半条会话记录。
- `request.history` 仍保留为兼容字段，但服务端 conversation history 优先，减少前端伪造或重复历史带来的混乱。

摘要压缩策略：

```text
messages after latest summary
-> 非 summary 消息数 > 16
-> 旧消息 + 既有 summary 交给 ChatModelProvider 生成摘要
-> 追加 role="summary" Message
-> 下一轮 history = 最新 summary + summary 之后的消息
```

agentic 集成：

- `run_agentic_rag()` 新增 `history` 参数。
- `AgenticState` 新增 `history` 字段。
- generate 节点用 `rewrite_contextual_question(question, history)` 生成更完整的生成问题。
- retrieve / grade / rewrite / re_retrieve 仍以当前问题为主，避免把短期会话历史误当作长期资料库。

前端架构：

- Agent 结果区从单个覆盖式 answer box 改为 `chat-messages` 列表。
- 每条消息渲染为 user / assistant / summary 气泡。
- 助手气泡复用阶段 22/23 的 mode、iteration、citations、invalid citations、refusal_category 和 workflow 元数据展示。
- 会话管理栏使用原生 HTML/CSS/JS：会话列表、新建、刷新、删除。
- 所有动态 HTML 继续经 `escapeHtml()` 处理，不引入前端框架或 Node 构建链。

## 阶段 23 Agentic 自动模式路由架构

阶段 23 没有改变默认 `/chat`，也没有修改 default `AgentService` 内部的 `detect_intent`。新增边界只在 `/agent/query` 入口：

```text
POST /agent/query
-> request.mode 显式存在？
   yes: 尊重 mode=default / mode=agentic
   no: classify_query_complexity(question)
       simple  -> default AgentService.query()
       complex -> run_agentic_rag()
-> AgentQueryResponse.mode 标记本次实际链路
-> 前端 data-agent-mode-status 只读展示 default / agentic
```

新增模块：

```text
app/services/agent/routing.py
  classify_query_complexity(question)
  -> QueryComplexityResult(complexity, score, reasons, signals)
```

规则只读取问题文本，不调用 LLM。主要信号包括问题长度、子句数、对比/流程/多方面关键词、跨证据/改写倾向，以及 `search + compare/explain/analyze` 组合。直接 source/list/source detail 请求保持 `simple`，继续交给 default `AgentService` 内部 `detect_intent` 处理。

评测闭环：

```text
scripts/evaluate_stage23_agentic_auto_routing.py
-> deterministic provider + in-memory SQLite fixture
-> default AgentService vs agentic LangGraph
-> data/evaluation/stage23_agentic_auto_routing_*.csv
```

阶段 23 对照结果为 default/agentic `error_rate=0.000`，`agentic_gain_count=1`，决策 `reliable_auto_route_candidate`。结论只支持“复杂问题可自动尝试 agentic”，不支持声称 agentic 全面优于 default。

## 阶段 22 Agentic 前端可观测架构

阶段 22 没有改变默认 `/chat` 或 default Agent 链路，而是在 `/agent/query` 上保留显式 opt-in。阶段 23 已将前端手动选择升级为自动路由后的只读模式指示器：

```text
前端 Agent 面板
-> 阶段 22：default / agentic 模式选择
-> 阶段 23：data-agent-mode-status 只读显示系统实际选择
-> submitAgent()
-> POST /agent/query
   default: 旧 AgentService 工具调用链路
   agentic: 阶段 21 LangGraph Agentic RAG
-> AgentQueryResponse
-> 前端结果区与步骤列表
```

新增响应字段属于“只读观测契约”，用于解释系统如何运行，不作为写库或外部副作用入口：

```text
mode
  本次回答使用 default 还是 agentic。

workflow_steps
  agentic 图节点记录，前端按顺序展示 retrieve、grade、rewrite、re_retrieve、generate、citation_check。

iteration_count
  agentic 检索-评估-改写循环执行次数。

invalid_citations
  citation_check 发现的无效引用编号，前端用风险 badge 标记。

refusal_category
  拒答分类：responsibility_gate_triggered / evidence_insufficient / off_topic。
```

兼容策略：

- default 模式继续返回旧的 `answer`、`tool_calls`、`sources`、`citations`、`refused`、`refusal_reason`、`reasoning_summary` 字段。
- 新增字段在 default 模式使用兼容默认值：`mode="default"`、`workflow_steps=[]`、`iteration_count=0`、`invalid_citations=[]`、`refusal_category=None`。
- agentic 模式同时填充 `workflow_steps` 和旧 `tool_calls` 映射，让旧前端/旧客户端仍可读取工具调用列表。
- 前端使用原生 HTML/CSS/JS，不引入 Node 构建链或前端框架。

## 第一阶段原则

- 先做工程底座，再做复杂 Agent。
- 先做本地资料导入，再做爬虫。
- 先做检索，再做回答。
- 回答必须能追溯来源。

## 当前实现

阶段 0 已落地最小后端骨架：

```text
app/main.py
  创建 FastAPI 应用，注册路由

app/api/health.py
  提供 GET /health

app/core/config.py
  集中读取应用配置和模型配置占位字段

app/schemas/health.py
  定义健康检查响应结构

tests/test_health.py
  验证 /health 的 HTTP 状态码和 JSON 返回
```

这种结构的目的，是让后续阶段可以自然扩展：

```text
health.py -> documents.py -> search.py -> chat.py
config.py -> database config -> model provider config
health schema -> document/search/chat schemas
```

## 阶段 1 总体框架

阶段 1 的目标是打通第一条最小资料链路：

```text
本地 Markdown/TXT/PDF 文件
-> 保存原始文件
-> 解析正文
-> 清洗文本
-> 切分 chunk
-> 保存 documents 和 chunks
-> 关键词检索
-> 返回标题、来源和片段
```

本阶段参考 Quivr 的 `storage / processor / splitter` 思路，但只保留当前需要的最小版本：

```text
Quivr storage      -> 本项目保存原始文件到 data/raw/
Quivr processor    -> 本项目 parser 读取 Markdown/TXT 正文
Quivr splitter     -> 本项目 splitter 把堆石混凝土资料切成 chunk
Quivr vector store -> 阶段 2 再做，本阶段不接 embedding 和向量库
Quivr RAG workflow -> 阶段 3 以后再做，本阶段不接大模型
```

### 新词解释

```text
ingestion
  资料导入链路。把用户上传或指定的本地文件变成系统可检索的数据。

processor / parser
  文件处理器。负责按文件类型读取内容，例如 .md 按 Markdown 文本读，.txt 按普通文本读，.pdf 用 pypdf 抽取文字层。

chunk
  可检索资料片段。例如一篇堆石混凝土施工文章会被切成多个 500 到 900 字左右的小段。

metadata
  元数据。不是正文内容，而是标题、来源路径、文件类型、导入时间、chunk 序号等说明信息。

repository
  数据库读写层。API 和 service 不直接写 SQL，而是通过 repository 保存和查询 documents/chunks。

top_k
  返回最相关的前 K 条结果。例如 top_k=5 表示关键词检索返回 5 个最相关片段。
```

### 目录规划

阶段 1 先增加以下模块：

```text
app/
  api/
    documents.py        POST /documents/import, GET /documents, GET /documents/{document_id}/chunks
    search.py           POST /search
  db/
    session.py          创建 SQLite 连接
    models.py           documents 和 chunks 表模型
    repositories.py     文档和 chunk 的保存、查询
  schemas/
    document.py         导入和文档列表响应结构
    search.py           搜索请求和响应结构
  services/
    ingestion/
      loader.py         保存上传文件，计算 hash
    parser.py         解析 Markdown/TXT/PDF
      cleaner.py        清洗文本
      splitter.py       切分 chunk
      service.py        串起导入全流程
    retrieval/
      keyword_search.py 关键词检索
```

### 数据库设计

阶段 1 只落地 `documents` 和 `chunks` 两张核心表：

```text
documents
  id
  title
  source_type
  source_path
  file_name
  file_extension
  content_hash
  raw_path
  status
  created_at
  updated_at

chunks
  id
  document_id
  chunk_index
  content
  char_count
  heading_path
  start_char
  end_char
  created_at
```

为什么这样设计：

- `documents` 保存一篇资料的整体信息，后续可以展示“资料库里有哪些资料”。
- `chunks` 保存可检索片段，后续问答引用时能追溯到具体片段。
- `content_hash` 用于识别重复文件，避免同一篇资料被重复导入。
- `heading_path` 预留标题层级，后续处理论文、报告、规范类资料时能保留上下文。
- `start_char` 和 `end_char` 记录片段在原文中的大致位置，方便排查和引用。

### API 设计

```text
POST /documents/import
  输入：Markdown/TXT/PDF 文件，可选 title
  处理：保存原文件 -> 解析 -> 清洗 -> 切分 -> 入库
  输出：document_id、title、chunk_count、status

GET /documents
  输入：无
  处理：查询已导入资料
  输出：文档列表、每篇资料的 chunk 数量和导入状态

GET /documents/{document_id}/chunks
  输入：URL 路径中的 document_id
  处理：查询某篇资料下的全部 chunk
  输出：资料标题、来源路径、chunk 总数、每个 chunk 的内容、序号、字符数和位置

POST /search
  输入：query、top_k
  处理：用关键词在 chunks 中检索
  输出：命中的片段、所属文档标题、chunk 序号、简单相关性分数
```

### 关键词检索策略

阶段 1 先做确定性关键词检索，不接 embedding。

```text
query
-> 清洗查询词
-> 在 chunk content 和 document title 中匹配
-> 按命中次数、标题命中、片段长度做简单评分
-> 返回 top_k
```

为什么先这样做：

- 不需要模型 API，也不需要向量库，能最快验证“资料能导入、能被搜到”。
- 关键词检索结果容易解释，适合第一阶段调试。
- 后续阶段 2 接入 embedding 后，可以把关键词结果作为对照基线。

### 真实资料切分微调

第一批资料卡导入后，splitter 采用以下补充规则：

- 跳过 Markdown 资料卡开头的 `source_id`、`url`、`copyright_note` 等元信息块，避免把来源登记字段当作知识正文。
- 新 chunk 起点优先贴近段落、换行、句号等自然边界，避免从 URL、英文单词或中文句子中间开始。
- `heading_path` 按 chunk 开始位置计算，用来表示该片段所属标题层级。
- 摘要型资料卡如果正文少于 `chunk_size`，保留为一个完整 chunk；长论文或长报告仍按长度和自然边界切成多个 chunk。

### PDF 原文导入

阶段 1 已增加最小 PDF 支持：

- 使用 `pypdf` 抽取 PDF 文字层。
- 每页文本前增加 `## Page N`，方便后续检查 chunk 所在页。
- 仅支持有文字层的 PDF；扫描版 PDF 暂不做 OCR。
- 开放全文 PDF 保存在 `data/fulltext/open_access/`，该目录不提交到 Git。
- 来源、许可、分类和本地文件名记录在 `data/fulltext_manifest.csv` 与 `docs/source_catalog.md`。

为什么这样设计：

- 阶段 1 先解决“能导入论文原文并检索”，不把 OCR、版面还原和表格识别一次性引入。
- PDF 全文可能受版权或机构访问限制，因此全文文件留在本地，仓库只保存来源清单和分类。
- 先用开放全文建立基线，再用 CNKI 机构授权下载补齐中文早期核心论文。

### 题录元数据语料库

阶段 1 现在增加一条轻量资料链路：

```text
OpenAlex / Crossref / Semantic Scholar / CNKI导出 / Google Scholar辅助导出
-> 题录候选
-> RFC 相关性过滤
-> DOI 或题名去重
-> CSV / JSONL 保存
-> Markdown 题录卡片
-> ingestion service
-> documents/chunks
-> 关键词检索
```

这样设计的原因：
- 论文全文获取慢且受版权、机构授权和网站限制影响；题录和摘要通常更容易批量获取。
- 阶段 1 的目标是先扩大可检索范围，不急着把所有全文都放进库里。
- 题录卡片复用现有 Markdown parser、cleaner、splitter、repository 和 search，不需要提前新增复杂表结构。
- 对 Google Scholar 和 CNKI，优先支持导出文件导入，不把验证码、登录态和页面结构变化放进主链路。

对应实现：
- `app/services/source_collection.py`：来源候选结构、分类、去重、摘要清洗、OpenAlex 摘要还原、Markdown 卡片生成。
- `scripts/collect_sources.py`：学术 API 发现，仍支持开放 PDF 可选下载。
- `scripts/collect_metadata_corpus.py`：题录优先采集、导出文件合并、CSV/JSONL 输出、Markdown 卡片入库。
- `data/metadata/rfc_papers_metadata.csv`：当前题录语料清单。
- `data/imports/metadata_corpus/`：生成的题录 Markdown 卡片。

### 测试顺序

```text
test_parser.py
  Markdown/TXT 能被解析成文本

test_cleaner.py
  多余空白、空字符能被清理

test_splitter.py
  长文本能切成多个 chunk，且保留 overlap

test_documents_api.py
  POST /documents/import 能导入示例文件
  GET /documents 能看到导入结果
  GET /documents/{document_id}/chunks 能查看某篇资料的 chunk

test_search.py
  POST /search 能搜到包含关键词的 chunk
```

阶段 1 完成标准：

```text
能导入 5 到 10 篇本地 Markdown/TXT 资料
SQLite 中能看到 documents 和 chunks
搜索“堆石混凝土”“自密实混凝土”“施工质量”等关键词能返回相关片段
返回结果包含 document title、chunk content、chunk_index 和 score
```

## 阶段 2 总体框架

阶段 2 的目标是打通第一条最小向量检索链路：

```text
documents/chunks
-> EmbeddingProvider
-> chunk_embeddings
-> VectorIndexService
-> 用户问题
-> query embedding
-> VectorSearchService
-> 返回 top_k 相似 chunks 和来源
```

本阶段参考 Quivr 的 `embedder / vector store / retriever` 模块边界，但先保留轻量实现：

```text
Quivr embedder      -> 本项目 EmbeddingProvider
Quivr vector store  -> 本项目先用 SQLite chunk_embeddings 表保存向量
Quivr retriever     -> 本项目 VectorSearchService
Quivr eval/tests    -> 本项目 keyword_queries.csv + evaluate_vector_search.py
```

阶段 2 不做：

- 引用式回答生成。
- 大模型聊天接口。
- Agent 工具调用。
- 复杂 workflow 编排。

这些内容放到阶段 3 或更后续阶段。

### 新词解释

```text
embedding
  文本向量。把用户问题或堆石混凝土资料片段变成一组数字，便于计算相似度。

EmbeddingProvider
  embedding 模型提供者。检索服务只依赖这个接口，不直接绑定某一家模型 API。

deterministic embedding
  确定性 embedding。同样输入永远得到同样向量，用于无 API key 的开发和自动化测试。

chunk_embeddings
  chunk 向量表。保存每个 chunk 的 embedding、provider、model_name、dimension 和 content_hash。

VectorIndexService
  向量索引构建服务。扫描 chunks，生成或更新 embedding，并写入 chunk_embeddings。

VectorSearchService
  向量检索服务。把用户问题向量化，再和 chunk_embeddings 中的向量计算相似度。

cosine similarity
  余弦相似度。用两个向量方向的接近程度表示问题和资料片段的相关性。

baseline
  对照基线。阶段 1 的关键词检索就是阶段 2 向量检索的 baseline。
```

### 目录规划

阶段 2 新增和扩展以下模块：

```text
app/
  api/
    search.py                 POST /search, POST /search/vector
  db/
    models.py                 ChunkEmbedding 模型
    repositories.py           ChunkEmbeddingRepository
  schemas/
    search.py                 VectorSearchRequest, VectorSearchResponse
  services/
    retrieval/
      embedding.py            EmbeddingProvider, DeterministicEmbeddingProvider
      vector_index.py         VectorIndexService
      vector_search.py        VectorSearchService
scripts/
  build_vector_index.py       构建 chunk_embeddings
  evaluate_vector_search.py   评测向量检索
data/
  evaluation/
    keyword_queries.csv
    keyword_results.csv
    vector_results.csv
```

### 数据库设计

阶段 2 在阶段 1 的 `documents` 和 `chunks` 基础上新增 `chunk_embeddings`：

```text
chunk_embeddings
  id
  chunk_id
  provider
  model_name
  dimension
  embedding_json
  content_hash
  created_at
  updated_at
```

为什么这样设计：

- `documents/chunks` 仍保存可引用的主数据。
- `chunk_embeddings` 只保存可重建的向量索引数据。
- `chunk_id` 用来从向量结果回到原始 chunk 和 document。
- `provider/model_name/dimension` 防止不同模型生成的向量混用。
- `content_hash` 用来判断向量是否过期。
- `embedding_json` 让 SQLite 阶段可以直接保存向量列表，后续迁移到 FAISS、Chroma 或 PGVector 时可以重建索引。

### API 设计

```text
POST /search
  阶段 1 关键词检索，继续作为 baseline。

POST /search/vector
  输入：query、top_k
  处理：query -> embedding -> 和 chunk embedding 计算余弦相似度
  输出：query、top_k、provider、model_name、results
  results：document_id、document_title、source_type、source_path、file_name、chunk_id、chunk_index、content、heading_path、score
```

### 向量索引构建策略

```text
chunks
-> 计算 content_hash
-> 查询同 provider/model 的已有 embedding
-> 未索引：生成 embedding 并插入
-> 已过期：重新生成 embedding 并更新
-> 未变化：跳过
```

索引构建由 `VectorIndexService` 负责，命令行入口是：

```powershell
python scripts/build_vector_index.py
```

### 向量检索策略

```text
query
-> EmbeddingProvider.embed_query()
-> 查询同 provider/model/dimension 的 chunk_embeddings
-> 跳过 stale embedding
-> cosine similarity
-> score 降序
-> 返回 top_k
```

当前使用 deterministic embedding，因此它主要证明工程链路可运行。真实语义效果需要后续接入真实 embedding 模型后继续评测。

### 评测策略

阶段 2 复用阶段 1 的评测集：

```text
data/evaluation/keyword_queries.csv
```

关键词检索评测输出：

```text
data/evaluation/keyword_results.csv
```

向量检索评测输出：

```text
data/evaluation/vector_results.csv
```

阶段 8 完成时结果：

```text
keyword baseline: 15/15 passed
vector search: 11/15 passed
```

这说明：

- 阶段 2 的向量检索链路已经跑通。
- deterministic embedding 不足以证明真实语义效果优于关键词检索。
- 后续优化应复用这些 failure cases 做回归测试。

阶段 2 完成标准：

```text
能为已有 chunks 构建 embedding
能保存 chunk_embeddings
能通过 POST /search/vector 返回来源、标题、片段和 score
能复用关键词评测集输出向量检索评测结果
关键词 baseline 仍可用
全量自动化测试通过
```

## 阶段 3 总体框架

阶段 3 的目标是打通第一条最小引用式问答链路：

```text
用户问题
-> CitationAnswerService
-> VectorSearchService 或 KeywordSearchService
-> prompt_builder 组织上下文和来源编号
-> ChatModelProvider 生成回答
-> extract_citations 过滤引用
-> ChatResponse 返回答案、来源和拒答状态
-> qa_logs 保存问答记录
```

本阶段参考 Quivr 的 `LLMEndpoint`、RAG prompt、source index 和 response metadata 思路，但继续保持轻量 service 分层，不引入 LangGraph 或复杂 Agent workflow。

```text
Quivr LLMEndpoint          -> 本项目 ChatModelProvider
Quivr combine_documents    -> 本项目 prompt_builder / ContextSource
Quivr ParsedRAGResponse    -> 本项目 CitationAnswerResult / ChatResponse
Quivr RAGResponseMetadata  -> 本项目 citations / sources / model_provider / model_name / refused
```

阶段 3 不做：

- Agent 工具调用。
- 多轮聊天历史。
- 复杂 LangGraph workflow。
- 真实模型质量优化。
- rerank 或混合检索优化。

这些内容放到阶段 4 以后逐步处理。

### Generation 层

阶段 3 新增 `app/services/generation/`：

```text
app/services/generation/
  chat_model.py       ChatModelProvider、deterministic provider、OpenAI-compatible provider
  prompt_builder.py   ContextSource、RagPrompt、build_rag_prompt()
  answer_service.py   CitationAnswerService、引用提取、拒答和日志写入
```

为什么新增 generation 层：

- 阶段 1/2 已经有 ingestion 和 retrieval。
- 阶段 3 需要独立承接 prompt、模型调用和答案生成。
- API 层不应该直接写检索、prompt 和模型调用细节。

### ChatModelProvider

`ChatModelProvider` 是聊天模型适配接口：

```text
messages -> ChatModelResult(answer, provider, model_name, raw_response)
```

当前实现：

- `DeterministicChatModelProvider`：用于本地开发和自动化测试。
- `OpenAICompatibleChatModelProvider`：预留国产大模型或兼容 OpenAI `/chat/completions` 的真实调用边界。

配置项：

```text
CHAT_MODEL_PROVIDER
CHAT_MODEL_NAME
CHAT_MODEL_API_KEY
CHAT_MODEL_BASE_URL
CHAT_MODEL_TEMPERATURE
CHAT_MODEL_TIMEOUT_SECONDS
```

### RAG prompt/context builder

`prompt_builder.py` 把检索结果转成模型可读上下文：

```text
SearchResultLike
-> ContextSource(source_id, chunk_id, document_title, content, score, ...)
-> RagPrompt(messages, context_text, sources)
```

来源编号规则：

- 每次回答内部从 `[1]` 开始编号。
- `source_id` 是本次回答的局部编号，不等于数据库 `chunk_id`。
- API 返回的 `sources` 保存 `source_id -> chunk_id` 的映射。

prompt 约束：

- 只基于给定资料回答。
- 回答中引用来源编号。
- 资料不足时拒答。
- 区分事实、推断和工程风险。
- 明确系统不替代规范审查、工程设计和专家判断。

### CitationAnswerService

`CitationAnswerService` 是阶段 3 的核心编排层：

```text
answer(question, top_k, retrieval_mode, min_score)
```

职责：

- 校验问题和参数。
- 根据 `retrieval_mode` 检索 chunks。
- `auto` 模式先向量检索，失败后关键词回退。
- 资料为空或低于 `min_score` 时拒答。
- 调用 `build_rag_prompt()`。
- 调用 `ChatModelProvider.generate()`。
- 从答案中提取 `[1]`、`[2]` 这类 citations。
- 只保留本次 sources 中存在的 citations。
- 返回 `CitationAnswerResult`。
- 默认保存 `qa_logs`。

返回结构：

```text
question
answer
citations
sources
refused
refusal_reason
retrieval_mode
model_provider
model_name
```

### Chat API

阶段 3 新增：

```text
POST /chat
```

请求结构 `ChatRequest`：

```text
question
top_k
retrieval_mode: auto | vector | keyword
min_score
```

响应结构 `ChatResponse`：

```text
question
answer
citations
sources
refused
refusal_reason
retrieval_mode
model_provider
model_name
```

`ChatSourceItem` 包含：

```text
source_id
document_id
document_title
source_type
source_path
file_name
chunk_id
chunk_index
heading_path
content
score
```

API 层保持薄封装：

- 用 Pydantic 校验请求。
- 用 `Depends(...)` 注入数据库、chat provider、embedding provider。
- 调用 `CitationAnswerService`。
- 把内部结果映射成对外响应。

### QA 日志

阶段 3 新增 `qa_logs` 表，对应 `QuestionAnswerLog`：

```text
qa_logs
  id
  question
  answer
  retrieved_chunk_ids
  citations
  model_provider
  model_name
  retrieval_mode
  refused
  refusal_reason
  created_at
```

设计原则：

- 记录排查需要的信息。
- 不保存 API key。
- 不保存 `ChatModelResult.raw_response`。
- `retrieved_chunk_ids` 和 `citations` 当前用 Text 保存 JSON 整数列表，后续迁移 PostgreSQL 时可升级为 JSON 字段。
- `CitationAnswerService` 默认写日志，测试或批处理可以用 `log_answers=False` 关闭。

### 评测策略

阶段 3 新增：

```text
data/evaluation/chat_queries.csv
scripts/evaluate_chat.py
data/evaluation/chat_results.csv
```

评测指标：

- 是否返回答案。
- 是否按预期拒答。
- 是否返回 sources。
- citations 是否能映射到 sources。
- 期望来源是否命中。
- 答案是否包含明显不在资料中的禁止词。

当前结果：

```text
chat evaluation: 6/6 passed
keyword baseline: 15/15 passed
vector evaluation: 11/15 passed
full tests: 106 passed
```

### 阶段 3 完成标准

```text
ChatModelProvider 可替换
RAG prompt 可构造
AnswerService 可返回 answer/citations/sources/refused/model 信息
POST /chat 可调用
资料不足时拒答
问答日志可追踪
chat 评测脚本可运行
旧关键词和向量评测仍可运行
全量自动化测试通过
```

## 阶段 4 总体框架

阶段 4 的目标是补齐资料来源治理层，让“有哪些资料来源、是否可信、能否保存全文、是否已经入库”这些问题有统一答案。

```text
公开资料候选 / PDF manifest / metadata CSV / metadata cards
-> SourceRegistryService
-> DOI / URL / 标题归一化
-> SourceRepository
-> sources 表
-> sync_sources.py 或 sources API
-> reindex_source()
-> IngestionService
-> documents/chunks
-> 后续向量索引刷新
```

阶段 4 不做：

- Agent 工具调用。
- 复杂 LangGraph workflow。
- 前端界面。
- 大规模爬虫。
- 检索召回质量优化。

这些内容放到阶段 5 以后逐步处理。

### Source Registry 层

阶段 4 新增 `app/services/source_registry.py`：

```text
SourceCandidate
-> candidate_to_source_create()
-> normalize_doi / normalize_url / normalize_title
-> derive_trust_level()
-> derive_fulltext_permission()
-> derive_status()
-> SourceRepository
-> sources
```

这个 service 位于“采集候选”和“数据库来源表”之间。它的作用不是下载更多论文，而是把已有来源变成可治理、可查询、可去重、可重新导入的结构化记录。

### sources 表

阶段 4 新增 `sources` 表：

```text
sources
  id
  source_id
  title
  normalized_title
  authors
  year
  venue
  category
  discovered_via
  doi
  normalized_doi
  url
  normalized_url
  pdf_url
  abstract
  keywords
  language
  citation_count
  source_type
  trust_level
  access_rights
  fulltext_permission
  license_or_terms
  local_path
  status
  notes
  document_id
  created_at
  updated_at
```

`sources.document_id` 可为空。这样一条来源可以先被登记为 `candidate` 或 `collected`，等用户确认或前端触发后，再通过 reindex 导入到 `documents/chunks`。

`sources` 和 `documents/chunks` 的关系：

```text
sources
  管来源、权限、状态、可信度、重复合并和 reindex 入口

documents/chunks
  管已经入库、可检索、可引用的正文或题录卡片
```

### 去重策略

阶段 4 使用三层去重：

```text
DOI -> URL -> 标题
```

设计原因：

- DOI 是论文最稳定标识，优先级最高。
- URL 可以识别网页、期刊页面、PDF 链接和题录页面。
- 标题归一化用于没有 DOI/URL 的题录或历史资料卡。

重复来源不会简单丢弃。当前策略是把更完整的字段合并到已有来源，并在 `notes` 中记录 `merged_duplicate_source_id=...`，方便后续审计。

### 可信度与权限

阶段 4 将可信度和全文保存权限分开：

```text
trust_level
  来源可靠程度，例如 high / medium / low。

fulltext_permission
  本项目能否保存全文，例如 open_access / institutional_access / metadata_only / unknown。
```

这样设计是为了避免把两个问题混在一起：一篇期刊论文可能很可信，但项目只能保存题录；一份开放 PDF 可以保存全文，但仍需要记录来源和许可。

### 来源状态

阶段 4 使用固定字符串表达来源生命周期：

```text
candidate
collected
imported
duplicate
rejected
```

含义：

- `candidate`：已发现但未收集原文。
- `collected`：已有本地路径、题录卡片或可用来源信息。
- `imported`：已经通过 reindex 进入 `documents/chunks`。
- `duplicate`：被识别为重复来源。
- `rejected`：因不相关、质量低或权限不合适而拒绝。

### 来源同步脚本

阶段 4 新增：

```text
scripts/sync_sources.py
```

默认读取：

```text
data/source_candidates.csv
data/fulltext_manifest.csv
data/metadata/rfc_papers_metadata.csv
data/imports/metadata_corpus/*.md
```

真实同步结果：

```text
total=283
created=125
updated=132
duplicates=26
```

脚本是幂等的：重复运行不会重复创建同一来源，而是更新已有来源或合并重复来源。

### 来源管理 API

阶段 4 新增：

```text
GET /sources
GET /sources/{source_id}
POST /sources/sync
POST /sources/{source_id}/reindex
```

API 层保持薄封装：

- 用 Pydantic schema 校验和组织响应。
- 用 repository 查询来源。
- 用 `SourceRegistryService` 执行 reindex。
- 把找不到来源映射成 404，把无法导入映射成可理解的 400。

### 重新索引

`reindex_source()` 的最小流程：

```text
source_id
-> 查询 sources
-> 如果 local_path 存在，导入原文件
-> 如果是 metadata-only，生成 metadata card 后导入
-> IngestionService.import_document()
-> 更新 sources.document_id
-> 更新 sources.status=imported
```

阶段 4 先提供入口，不做后台任务队列。后续前端可以把 reindex 做成按钮，Agent 工具阶段也可以把它包装成受控工具。

### 来源评测

阶段 4 新增：

```text
scripts/evaluate_sources.py
data/evaluation/source_registry_metrics.csv
```

当前指标：

```text
total_sources=125
linked_documents=0
merged_duplicates=14
status=candidate:8;collected:117
fulltext_permission=institutional_access:2;metadata_only:110;open_access:10;unknown:3
trust_level=high:125
```

`linked_documents=0` 表示当前 source registry 已登记来源，但尚未对真实库逐条执行 reindex。这个状态是可接受的，因为阶段 4 的目标是提供登记、治理和入口；批量导入或前端触发可在后续阶段继续推进。

### 阶段 4 完成标准

```text
sources 表可创建
来源可以从现有 CSV / manifest / metadata corpus 同步
来源可按 DOI / URL / 标题去重
可信度、全文权限和状态字段可用
sources API 可查询、同步和 reindex
来源评测脚本可运行
documents/search/vector/chat 测试不被破坏
全量自动化测试通过
```

## 阶段 5 总体框架

阶段 5 的目标是把阶段 1-4 的后端能力变成非技术用户可操作的浏览器工作台：

```text
FastAPI
-> GET /
-> app/frontend/index.html
-> app/frontend/static/app.js
-> 调用 sources/documents/search/chat API
-> 浏览器展示来源、资料、片段、检索结果、回答和引用
```

阶段 5 不做：

- Agent 工具调用。
- 复杂 LangGraph workflow。
- 登录系统。
- 部署平台优化。
- 检索质量优化。

这些内容放到阶段 6 和阶段 7。

### 前端目录

```text
app/
  api/
    frontend.py
  frontend/
    index.html
    static/
      app.js
      styles.css
```

`app/api/frontend.py` 提供：

```text
GET /
GET /favicon.ico
```

`app/main.py` 使用 `StaticFiles` 挂载：

```text
/static -> app/frontend/static
```

### 前端数据流

```text
页面加载
-> GET /health
-> GET /sources
-> GET /documents
-> 渲染概览指标、来源表、资料表
```

来源管理：

```text
GET /sources
-> 浏览器端关键词 / 状态 / 全文权限筛选
-> sources 表格
```

资料管理：

```text
GET /documents
-> documents 表格
-> 点击 chunks
-> GET /documents/{document_id}/chunks
-> chunks 面板
```

检索：

```text
POST /search 或 POST /search/vector
-> result cards
```

问答：

```text
POST /chat
-> answer
-> citations
-> sources sidebar
```

来源操作：

```text
POST /sources/sync
POST /sources/{source_id}/reindex
```

### 前端设计边界

- 前端只负责展示、筛选、发起 API 请求和反馈状态。
- 来源去重、可信度、权限、reindex、检索和问答仍由后端 service 负责。
- 第一版使用原生 HTML/CSS/JS，避免阶段 5 过早引入 Node 构建链。
- 首页就是工作台，不做 landing page。
- 桌面和移动视口都要保持可读，不出现横向溢出。

### 阶段 5 完成标准

```text
GET / 可访问
静态 CSS/JS 可访问
sources 和 documents 可展示
document chunks 可查看
keyword/vector search 可触发
chat 可触发并展示引用来源
source sync/reindex 有操作入口和反馈
浏览器桌面与移动视口验证通过
全量自动化测试通过
```

## 阶段 6 总体框架

阶段 6 的目标是把“能检索、能回答”推进到“质量可度量、优化可解释、结果可复现”。

```text
documents/chunks/sources/chunk_embeddings
-> keyword/vector/chat baseline
-> evaluation plan
-> retrieval error cases
-> HybridSearchService
-> POST /search/hybrid
-> hybrid evaluation
-> metrics comparison
-> frontend minimal mode selector
```

阶段 6 不做：

- Agent 工具调用。
- 复杂 LangGraph workflow。
- 登录系统。
- 部署优化。
- 大规模前端重构。

这些内容放到阶段 7 以后逐步处理。

### 评测计划

阶段 6 新增：

```text
docs/evaluation_plan.md
```

核心指标：

```text
Recall@K
Citation Accuracy
Faithfulness
Answer Coverage
Refusal Quality
```

当前自动化口径：

- `Recall@K` 由 keyword/vector/hybrid 评测脚本按期望标题、正文片段和 source_type 近似判断。
- `Citation Accuracy` 由 chat 评测脚本检查 citations 是否能映射到本次 sources，并检查期望来源是否命中。
- `Faithfulness` 当前用禁止词和拒答规则做轻量自动检查，后续接真实模型后可加入人工审阅或 LLM-as-judge。
- `Answer Coverage` 当前由期望词和来源命中近似承接。
- `Refusal Quality` 由 chat 评测集中的无依据问题验证。

### 混合检索服务

阶段 6 新增：

```text
app/services/retrieval/hybrid_search.py
```

`HybridSearchService` 复用已有两条召回链路：

```text
query
-> KeywordSearchService.search(fetch_k)
-> VectorSearchService.search(fetch_k)
-> 按 chunk_id 去重
-> keyword/vector 分数分别按最大分归一化
-> keyword_weight + vector_weight + both_match_bonus
-> source_type_rank 和稳定字段兜底排序
-> top_k results
```

默认权重：

```text
keyword_weight = 0.7
vector_weight = 0.3
both_match_bonus = 0.15
```

这样设计的原因：

- keyword baseline 当前 15/15，适合救回 deterministic vector 的弱召回。
- vector 仍保留语义召回能力，后续接真实 embedding provider 后可以继续受益。
- 不改写 `/search` 或 `/search/vector`，避免破坏 baseline。
- 权重和 bonus 可解释，适合写入错误案例和面试表达。

### API 与 Chat 集成

阶段 6 新增：

```text
POST /search/hybrid
```

请求字段与现有检索入口保持一致：

```text
query
top_k
```

响应结构与向量检索类似：

```text
query
top_k
provider
model_name
results
```

`POST /chat` 新增显式检索模式：

```text
retrieval_mode = "hybrid"
```

但 `auto` 模式仍保留阶段 3 的旧行为：先尝试 vector，有结果则使用 vector，只在无结果时 fallback 到 keyword。这样可以避免阶段 6 中途改变 chat baseline 的含义。

### 评测脚本与结果

阶段 6 新增和复用：

```text
scripts/evaluate_keyword_search.py
scripts/evaluate_vector_search.py
scripts/evaluate_hybrid_search.py
scripts/evaluate_chat.py
scripts/analyze_retrieval_errors.py

data/evaluation/keyword_results.csv
data/evaluation/vector_results.csv
data/evaluation/hybrid_results.csv
data/evaluation/chat_results.csv
data/evaluation/retrieval_error_cases.csv
```

当前结果：

```text
keyword baseline: 15/15 passed
vector search: 11/15 passed
hybrid search: 15/15 passed
chat evaluation: 6/6 passed
rescued_vector: 4
regressed_keyword: 0
retrieval error cases: 4 fixed_by_hybrid
full tests: 141 passed
```

### 前端最小展示

阶段 6 只在现有工作台中增加 hybrid 选项：

```text
app/frontend/index.html
app/frontend/static/app.js
```

搜索模式：

```text
keyword
vector
hybrid
```

聊天检索模式：

```text
auto
hybrid
vector
keyword
```

前端仍只负责选择模式和调用 API；混合检索排序、去重和评分逻辑都在后端 service 中。

### 阶段 6 完成标准

```text
docs/evaluation_plan.md 已建立
keyword/vector/chat baseline 已复跑
retrieval_error_cases.csv 已生成
hybrid search service/API/chat mode 已实现
hybrid_results.csv 可对比优化前后指标
旧 search/vector/chat/sources/frontend 测试不被破坏
前端能最小展示 hybrid 检索模式
全量自动化测试通过
```

## 阶段 7 总体框架

阶段 7 的目标是把阶段 6 稳定的 RAG 能力包装成受控、只读优先、可测试、可追踪的 Agent 工具调用链路。

```text
用户任务
-> POST /agent/query
-> AgentService
-> AgentToolbox
-> search / hybrid search / citation chat / sources
-> AgentQueryResult
-> answer + tool_calls + sources + citations + refused + reasoning_summary
-> 前端 Agent 面板展示
```

阶段 7 不做：

- 复杂 LangGraph workflow。
- 登录系统。
- 部署优化。
- 联网爬虫扩展。
- 自动执行写入型 source reindex。

### Agent 目录

阶段 7 新增：

```text
app/
  api/
    agent.py
  schemas/
    agent.py
  services/
    agent/
      __init__.py
      tools.py
      service.py
scripts/
  evaluate_agent.py
data/
  evaluation/
    agent_queries.csv
    agent_results.csv
docs/
  agent_design.md
```

### 工具层

`AgentToolbox` 是 Agent 的工具封装层。

当前只读工具：

```text
search_knowledge
  复用 KeywordSearchService，保留关键词 baseline。

hybrid_search_knowledge
  复用 HybridSearchService，作为搜索类任务默认工具。

answer_with_citations
  复用 CitationAnswerService，返回 answer、citations、sources 和 refused。

list_sources
  复用 SourceRepository，列出已登记来源。

get_source_detail
  复用 SourceRepository，查询单条来源详情。
```

工具返回统一结构：

```text
AgentToolResult
  answer
  search_results
  sources
  citations
  refused
  refusal_reason
  tool_call
```

工具调用记录：

```text
AgentToolCallRecord
  tool_name
  input_summary
  output_summary
  succeeded
  error
```

这样设计的原因：

- API 和前端可以直接展示工具调用过程。
- 评测脚本可以检查工具是否选对。
- 失败时可以返回可理解的失败记录，而不是让异常逃逸。

### 编排层

`AgentService` 是阶段 7 的轻量编排服务。

职责：

- 校验 `question`、`top_k` 和 `max_tool_calls`。
- 用规则式意图路由判断任务类型。
- 控制最多工具调用步数。
- 调用 `AgentToolbox`。
- 汇总 `answer`、`tool_calls`、`sources`、`search_results`、`citations`、`refused` 和 `reasoning_summary`。

当前意图路由：

```text
搜索 / 检索 / 查找
-> hybrid_search_knowledge

来源列表
-> list_sources

来源详情 + source_id
-> get_source_detail

来源详情但缺少 source_id
-> 拒答，提示需要 source_id

其他问答
-> answer_with_citations
```

第一版不用 LLM 做规划，是为了保证阶段 7 的行为稳定、可解释、可自动测试。后续如果接入 LLM 规划，也必须保留只读优先、最大步数、权限字段、工具调用记录和评测回归。

### Agent API

阶段 7 新增：

```text
POST /agent/query
```

请求字段：

```text
question
top_k
max_tool_calls
source_id
```

响应字段：

```text
question
answer
tool_calls
search_results
sources
citations
refused
refusal_reason
reasoning_summary
```

API 层保持薄封装：只做请求校验、依赖注入和响应映射，不直接写检索、问答或来源查询逻辑。

### 评测策略

阶段 7 新增：

```text
data/evaluation/agent_queries.csv
scripts/evaluate_agent.py
data/evaluation/agent_results.csv
```

Agent 评测检查：

- 期望工具是否被调用。
- 拒答是否符合预期。
- 需要来源的任务是否返回 sources。
- 需要引用的任务 citations 是否能映射到 sources。
- 期望来源标题或内容词是否命中。
- 工具调用次数是否受控。

当前结果：

```text
agent evaluation: 5/5 passed
refused=1
tool_failures=0
citation_failures=0
full tests=163 passed
```

## 阶段 8 总体框架

阶段 8 的目标是把阶段 3-7 已经跑通的 RAG 问答、检索和 Agent 回答能力收拢到一个轻量 Brain 中控层。

核心数据流：

```text
POST /chat 或 AgentToolbox.answer_with_citations
-> CitationAnswerService 兼容门面
-> RetrievalConfig / WorkflowConfig
-> BrainService.answer()
-> filter_history
-> rewrite_query
-> retrieve
-> optional_rerank
-> generate_answer
-> answer / citations / sources / qa_logs
```

阶段 8 不改变外部 API 响应结构：

```text
POST /chat
  仍然返回 question、answer、citations、sources、refused、retrieval_mode、model_provider、model_name

POST /agent/query
  仍然返回 answer、tool_calls、search_results、sources、citations、refused、reasoning_summary
```

### Brain 模块

阶段 8 新增：

```text
app/services/brain/__init__.py
app/services/brain/config.py
app/services/brain/workflow.py
app/services/brain/service.py
```

`BrainService` 的职责：

- 接收用户问题和 `RetrievalConfig`。
- 按 `WorkflowConfig` 执行 RAG workflow。
- 复用 `KeywordSearchService`、`VectorSearchService`、`HybridSearchService`。
- 复用 `build_rag_prompt`、`ChatModelProvider`、citation 提取和 `QuestionAnswerLogRepository`。
- 返回 `BrainAnswerResult`，其中包含 answer、citations、sources、refused、retrieval_mode、model 信息和 workflow step 记录。

Brain 不负责：

- 不直接写 SQL。
- 不联网爬取新资料。
- 不自动执行 source reindex。
- 不替代 source registry、documents/chunks 或 retrieval service。
- 不引入复杂 LangGraph workflow。

### 配置模型

`RetrievalConfig` 控制一次问答的检索和生成参数：

```text
retrieval_mode: auto / keyword / vector / hybrid
top_k
min_score
max_history
rerank_top_n
prompt_profile
model_provider
workflow_config
```

`WorkflowConfig` 默认步骤：

```text
filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer
```

第一版实现中：

- `filter_history` 是历史过滤占位，用于后续多轮问答。
- `rewrite_query` 是问题改写占位，用于后续 query expansion。
- `retrieve` 复用现有检索服务。
- `optional_rerank` 使用可解释截断，为后续真实 reranker 预留位置。
- `generate_answer` 复用现有引用式问答链路。

### 与 Quivr 的取舍

本阶段借鉴 Quivr 的三个思想：

- Brain 作为中控对象。
- RetrievalConfig 作为检索与生成参数包。
- WorkflowConfig 作为 RAG 步骤描述。

但本项目不照搬 Quivr 代码，也不引入 LangGraph。阶段 8 的选择是先用普通 Python service 固定边界，让 `/chat` 和 Agent 共用一条可测试、可评测的工作流。

### 配置化评测

阶段 8 新增：

```text
scripts/evaluate_brain_workflow.py
data/evaluation/brain_workflow_results.csv
tests/test_evaluate_brain_workflow.py
```

评测比较三种配置：

```text
default_hybrid
keyword_baseline
vector_only
```

CSV 记录：

- config 名称
- configured / actual retrieval mode
- top_k、min_score、rerank_top_n
- workflow steps
- workflow_succeeded
- citations_valid
- expected_source_hit
- refusal_matched

当前结果：

```text
default_hybrid: 4/6 passed
keyword_baseline: 6/6 passed
vector_only: 2/6 passed
```

这个结果说明阶段 8 已经能对不同 Brain 配置做可复现比较；阶段 10 和阶段 11 已在此基础上进一步提升 Brain workflow 和真实用户问题评测质量。

### 阶段 8 完成标准

```text
docs/brain_workflow_design.md 已建立
app/services/brain/ 已建立
RetrievalConfig / WorkflowConfig 已实现
BrainService 五步 workflow 已实现
CitationAnswerService 已复用 Brain
Agent answer_with_citations 已复用同一路径
Brain 配置化评测脚本和结果 CSV 已生成
search/vector/hybrid/chat/agent/sources/frontend 回归通过
全量自动化测试通过：189 passed
```

## 阶段 9 总体框架

阶段 9 的目标是补齐真实模型接入与模型评测闭环。

阶段 9 不改变外部 API 响应结构，而是增强 Model Provider 层：

```text
POST /search/vector 或 POST /search/hybrid
-> API dependency 创建 EmbeddingProvider
-> VectorSearchService / HybridSearchService
-> chunk_embeddings 按 provider/model/dimension 查询
-> 返回检索结果

POST /chat 或 AgentToolbox.answer_with_citations
-> CitationAnswerService
-> BrainService
-> ChatModelProvider + EmbeddingProvider
-> 返回 answer/citations/sources
```

阶段 9 新增：

```text
docs/model_provider_evaluation.md
OpenAICompatibleEmbeddingProvider
EMBEDDING_DIMENSION
EMBEDDING_TIMEOUT_SECONDS
scripts/build_vector_index.py provider/model/dimension 参数
scripts/evaluate_model_configs.py
data/evaluation/model_config_results.csv
```

### Provider 边界

`ChatModelProvider` 管“怎么生成回答”。

`EmbeddingProvider` 管“怎么把问题或资料片段变成向量”。

业务 service 不直接知道具体模型厂商，只调用统一方法：

```text
chat_model_provider.generate(messages)
embedding_provider.embed_texts(texts)
embedding_provider.embed_query(query)
```

这样后续替换国产兼容模型、OpenAI-compatible 模型或本地模型时，不需要重写 retrieval、Brain、Agent 或 API schema。

### 真实 embedding 索引

`chunk_embeddings` 的唯一约束包含：

```text
chunk_id
provider
model_name
```

同时保存：

```text
dimension
content_hash
embedding_json
```

阶段 9 之后，同一份 chunk 可以同时存在 deterministic 索引和真实模型索引。切换真实 embedding provider 后必须重建向量索引，检索时才会命中当前 provider/model/dimension 对应的 embedding。

阶段 9.1 已使用 Jina `jina-embeddings-v3` 重建真实向量索引：997 个 chunk 中 995 个新写入，2 个已存在跳过。Jina provider 使用 1024 维向量，因此检索时必须继续按 provider=`openai-compatible`、model=`jina-embeddings-v3`、dimension=`1024` 查询，不能混用 deterministic 索引。

### 模型配置评测

阶段 9 新增模型配置汇总评测：

```text
scripts/evaluate_model_configs.py
data/evaluation/model_config_results.csv
```

它汇总：

```text
keyword
vector
hybrid
chat
agent
brain_workflow
```

当前结果：

```text
deterministic_baseline:
  keyword 15/15
  vector 11/15
  hybrid 15/15
  chat 6/6
  agent 5/5
  brain_workflow 12/18

real_config:
  skipped because local real model configuration is incomplete
```

这说明阶段 9 已具备真实模型接入和可对比评测入口，但默认仍保留 deterministic，避免本地测试依赖 API key、网络、限流和模型供应商状态。

### 阶段 9.1 真实 Jina 与 MIMO 补充验证

阶段 9.1 没有改变外部 API contract，而是验证真实 provider 能被现有 RAG 链路消费：

```text
Jina embeddings
-> chunk_embeddings(provider/model/dimension/content_hash)
-> vector / hybrid retrieval
-> Brain workflow
-> MIMO chat answer
-> citations / sources / refusal evaluation
```

实现上的关键点：

```text
OpenAICompatibleEmbeddingProvider
  增加 Accept 和 User-Agent 请求头，兼容 Jina API 行为

OpenAICompatibleChatModelProvider
  同时发送标准授权头和供应商兼容 key header
  保留 Accept、Content-Type 和 User-Agent
  兼容常规 OpenAI-compatible 服务和 MIMO Token Plan
```

真实组合评测结果：

```text
Jina vector: 14/15
Jina hybrid: 15/15
MIMO + Jina chat: 6/6
MIMO + Jina agent: 5/5
MIMO + Jina brain_workflow: 15/18
full tests: 208 passed
```

架构结论：真实 MIMO + Jina 组合证明 provider 边界有效，业务层无需知道具体供应商差异。剩余 3 个 brain workflow 失败项集中在 `vector_only` 和 `unsupported` 边界，说明下一阶段不应继续扩 provider，而应优化检索置信度、拒答判断和 hybrid/rerank 策略。

## 阶段 10 真实 RAG 质量校准与拒答边界优化

阶段 10 的目标不是新增模型 provider，而是在真实模型已经能运行的基础上，校准 RAG 的质量边界。

本阶段处理的失败链路是：

```text
真实 Jina / MIMO 评测结果
-> 失败案例分析
-> Brain 生成前证据置信度检查
-> vector-only 候选主题锚点重排
-> deterministic 与真实模型结果对比
```

### 失败案例分析

阶段 10 新增：

```text
scripts/analyze_real_rag_failures.py
data/evaluation/real_rag_failure_cases.csv
tests/test_analyze_real_rag_failures.py
```

失败案例表记录：

- 失败问题。
- 失败配置。
- 失败原因。
- 召回片段标题。
- 期望依据。
- 改进建议。

它把阶段 9.1 的失败拆成三类：

```text
unsupported_low_evidence
vector_topic_drift
cross_language_topic_gap
```

### Evidence Confidence

阶段 10 在 Brain workflow 中新增 `EvidenceConfidence`。

它解决的问题是：检索有结果，不代表证据足够回答。

数据流：

```text
BrainService.retrieve()
-> BrainRetrievalOutcome(results)
-> evaluate_evidence_confidence(question, results)
-> confidence.sufficient?
   -> yes: build prompt and call ChatModelProvider
   -> no: return DEFAULT_REFUSAL_ANSWER without model generation
```

当前规则使用轻量 query-token coverage：

```text
question
-> normalize and extract evidence terms
-> compare with result title / heading / content
-> matched_terms / query_terms
-> coverage >= 0.20 means sufficient
```

设计取舍：

- 不依赖真实模型自评，保证 deterministic 测试可复现。
- 不改变基础 search API schema。
- 不把低证据片段交给真实模型硬生成。
- 先覆盖乱字符串式 unsupported query，避免过度拒答正常工程问题。

### 低证据拒答

低证据拒答发生在 Brain 的 `generate_answer` 步骤之前。

当证据不足时，系统返回：

```text
answer = DEFAULT_REFUSAL_ANSWER
sources = []
citations = []
refused = true
refusal_reason = evidence confidence insufficient
```

因为 `/chat` 和 Agent `answer_with_citations` 都复用 Brain，因此这条保护同时覆盖：

```text
POST /chat
POST /agent/query -> answer_with_citations
```

### Topic Anchor Rerank

阶段 10 在 `VectorSearchService` 中新增 topic anchor rerank。

原向量检索：

```text
query embedding
-> cosine similarity
-> top_k
```

阶段 10 后：

```text
query embedding
-> cosine similarity candidates
-> topic anchor score from query terms and document text
-> combined internal rank score
-> top_k
```

实现要点：

- 复用 `keyword_search.expand_query_terms()` 的领域词扩展。
- `TOPIC_ANCHOR_BOOST = 0.20`。
- 返回给 API 和 CSV 的 `score` 仍是 cosine score。
- topic anchor 只参与内部排序，不改变 `POST /search/vector` 响应结构。
- 不把 vector-only 静默 fallback 到 hybrid，保留 baseline 可解释性。

### 阶段 10 评测结果

deterministic 结果：

```text
vector: 13/15
hybrid: 15/15
chat: 6/6
agent: 5/5
brain_workflow:
  default_hybrid 6/6
  keyword_baseline 6/6
  vector_only 6/6
full tests: 216 passed
```

真实 MIMO + Jina 校准结果：

```text
Jina vector: 15/15
Jina hybrid: 15/15
MIMO + Jina chat: 6/6
MIMO + Jina agent: 5/5
MIMO + Jina brain_workflow:
  default_hybrid 6/6
  keyword_baseline 6/6
  vector_only 6/6
```

架构结论：阶段 10 后，真实模型更适合做最终体验校准，deterministic provider 更适合做稳定回归。RAG 质量保护应优先放在 Brain 生成前，而不是只靠 prompt 要求模型“不要胡编”。

## 阶段 11 真实用户问题评测集与跨语言质量提升

阶段 11 不改变外部 API schema，而是在评测层、检索词表和 Brain 证据判断层补强真实用户问法覆盖。

核心数据流：

```text
data/evaluation/user_questions.csv
-> scripts/evaluate_user_questions.py
-> BrainService.answer()
-> keyword / vector / hybrid retrieval
-> query expansion / topic anchor
-> Brain evidence confidence
-> answer / refusal / sources / citations
-> data/evaluation/user_question_results.csv
-> data/evaluation/user_question_review_samples.csv
```

### 用户问题评测集

阶段 11 新增：

```text
data/evaluation/user_questions.csv
scripts/evaluate_user_questions.py
data/evaluation/user_question_results.csv
tests/test_user_questions.py
tests/test_evaluate_user_questions.py
```

`user_questions.csv` 与阶段 10 的 `chat_queries.csv` 分开维护，原因是两者用途不同：

- `chat_queries.csv` 保留旧问答 baseline，适合长期稳定回归。
- `user_questions.csv` 覆盖更接近真实提问的语言形态，例如中文口语、英文问题、中英混合术语、工程中文和 unsupported。

新增字段中，`language_type` 用来标记问题语言形态，`expected_answer_points` 用来给人工审阅或 LLM-as-judge 判断回答覆盖度。

### 跨语言 Query Expansion

阶段 11 继续复用 `app/services/retrieval/keyword_search.py` 中的 `SYNONYM_RULES`：

```text
中文工程词
-> 英文论文术语
-> keyword search term expansion
-> vector topic anchor
-> evidence confidence expanded terms
```

这样做的好处是同一套可解释词表能服务三处能力：

- `KeywordSearchService`：提高中文、英文、中英混合问法的关键词召回。
- `VectorSearchService`：topic anchor 在向量候选内部做轻量主题重排。
- `BrainService`：evidence confidence 使用扩展后的中英文证据词，避免中文问题与英文证据之间的误拒答。

阶段 11 增强的术语包括：

```text
ITZ / 界面 / interfacial transition zone
creep / 徐变 / 长期变形
freeze-thaw / 冻融 / 抗冻
porosity / void / 孔隙率 / 孔洞
emission / cost / schedule / 碳排放 / 成本 / 工期
steel fiber / 钢纤维
rock shear keys / 剪力键
compactness / compaction detection / 灌满 / 密实度
```

### 离线审阅设计

阶段 11 新增：

```text
docs/stage11_user_evaluation_plan.md
data/evaluation/user_question_review_samples.csv
tests/test_stage11_user_evaluation_plan.py
```

自动评测适合稳定检查：

```text
Refusal Quality
Source Hit
Citation Quality
Forbidden Terms
```

人工审阅或 LLM-as-judge 离线校准适合检查：

```text
Faithfulness
Answer Coverage
Citation Quality
```

LLM-as-judge 在本项目中只作为离线质量裁判设计，不进入 CI，不作为自动回归前提，也不要求真实 API key。

### 阶段 11 评测结果

```text
keyword: 15/15
vector: 13/15
hybrid: 15/15
chat: 6/6
agent: 5/5
brain_workflow: 18/18
user_question_evaluation: 25/30
  default_hybrid: 10/10
  keyword_baseline: 10/10
  vector_only: 5/10
full tests: 230 passed
```

架构结论：阶段 11 把质量提升放在“评测输入更真实”和“术语增强更可解释”上，而不是改变 API 或引入黑盒 workflow。剩余的 vector-only 用户问题失败项保留为下一阶段真实 embedding、rerank 或人工审阅校准依据。

## 阶段 12 质量审阅与上下文最小补全

阶段 12 不改变核心 RAG 架构，而是在质量审阅层和 Brain `rewrite_query` step 做最小增强。

核心数据流：

```text
data/evaluation/user_question_review_samples.csv
-> data/evaluation/stage12_quality_review_results.csv
-> docs/stage12_quality_review.md
-> BrainService.answer(history=...)
-> filter_history
-> rewrite_query
-> retrieve
-> evidence confidence
-> generate_answer
```

### 质量审阅链路

阶段 12 新增：

```text
data/evaluation/stage12_quality_review_results.csv
docs/stage12_quality_review.md
tests/test_stage12_quality_review.py
```

质量审阅补足自动评测的不足：

- 自动评测负责检查拒答匹配、来源命中、引用编号和禁止词。
- 人工或离线审阅负责检查 Faithfulness、Answer Coverage 和 Citation Quality。

阶段 12 审阅结论：

```text
default_hybrid 来源命中可靠
keyword_baseline 仍是稳定可解释 baseline
vector_only 仍有主题漂移
deterministic answer 不能单独证明真实回答覆盖度
```

### Context Rewrite

阶段 12 在 `app/services/brain/service.py` 中实现最小上下文补全：

```text
history + current question
-> filter_history
-> rewrite_contextual_question()
-> retrieval question
```

触发条件保持保守：

- 当前问题含有“它”“这个技术”“这类问题”“上面”“刚才”等明确上下文指代。
- 存在最近历史问题。
- 只拼接最近历史问题，不做长期记忆、不做用户画像、不调用真实模型改写。

示例：

```text
history: 堆石混凝土徐变有什么研究？
question: 它有哪些研究？
rewritten query: 堆石混凝土徐变有什么研究？；追问：它有哪些研究？
```

对外响应仍保留原始 `question`，补全后的 query 只用于检索、prompt 和 evidence confidence。这样既改善省略问法召回，又不改变用户看到的问题。

### Chat 与 Agent 接入

阶段 12 为 `/chat` 和 `/agent/query` 增加可选 `history` 字段：

```text
{
  "question": "它有哪些研究？",
  "history": ["堆石混凝土徐变有什么研究？"]
}
```

旧请求不传 `history` 仍保持兼容。Agent 不新增写入型工具，只把可选 history 传入已有 `answer_with_citations` 工具。

### 阶段 13 输入

阶段 12 新增：

```text
docs/stage13_decompose_plan.md
tests/test_stage13_decompose_plan.py
```

后续建议：

```text
original question
-> rule-based decompose
-> sub query retrieval
-> merge candidates
-> deduplicate by chunk_id
-> rerank by topic/source/score
-> Brain answer with citations
```

HyDE 只作为离线实验建议，不进入默认链路或 deterministic 自动回归。

阶段 12 评测结果：

```text
quality review tests: 8 passed
context rewrite focused tests: 52 passed
user questions: 25/30
chat: 6/6
agent: 5/5
Brain workflow: 18/18
API/core tests: 47 passed
full tests: 244 passed
```

架构结论：阶段 12 把质量校准和上下文补全都放在已有 Brain / evaluation 边界内，没有绕开引用、拒答和来源治理。后续阶段应优先做 Decompose 与可解释证据合并，而不是默认引入 HyDE 或复杂多轮记忆。

## 阶段 13 Decompose 与可解释证据合并

阶段 13 的目标是在 Brain 检索阶段增强复杂问题的证据覆盖，而不是替换 RAG 架构或改变外部 API。

核心数据流：

```text
BrainService._retrieve_with_hybrid()
-> decompose_query()
-> DecomposeRetrievalService.retrieve()
-> sub query hybrid retrieval
-> merge_sub_query_results()
-> MergedEvidence
-> build_retrieval_outcome()
-> evaluate_evidence_confidence()
-> build_rag_prompt()
-> ChatModelProvider
```

### 规则式 Decompose

阶段 13 新增：

```text
app/services/retrieval/decompose.py
tests/test_decompose_retrieval.py
```

核心结构：

```text
DecomposedQuery
  original_question
  sub_queries
  decomposed
  reason

SubQueryRetrievalResult
  sub_query
  retrieval_mode
  results

MergedEvidence
  普通 SearchResultLike 字段
  sub_queries
  keyword_score
  vector_score
  topic_score
  source_type_score
  both_match
  final_score
  explanation
```

规则边界：

- 子 query 最多 3 个。
- 只拆明显并列结构，例如“成本、工期和碳排放”“灌满以及密实度”“孔隙率和抗压表现”。
- 单主题问题继续使用原始 query。
- unsupported 乱字符串不强行拆解。
- 不调用真实模型拆解，避免自动回归依赖 API。

### Brain 集成

阶段 13 只在 hybrid 路径中接入 Decompose：

```text
question
-> decompose_query(question)
-> if decomposed: run sub query hybrid retrieval and merge evidence
-> else: keep original HybridSearchService
```

这样做有两个目的：

- 复杂问题能获得更完整证据。
- 单主题问题不多跑额外检索，避免 default_hybrid 退化。

阶段 13 初次接入时曾因“先执行 Decompose 服务再判断是否拆解”导致 Brain workflow `default_hybrid` 从 6/6 退到 5/6。修复后改为先运行轻量 `decompose_query()`，只有真正拆解时才执行子 query 检索，Brain workflow 恢复 18/18。

### 可解释 Rerank

`MergedEvidence` 的排序综合：

```text
normalized_retrieval_score
topic_match_bonus
source_type_bonus
both_match_bonus
sub_query_coverage_bonus
```

`explanation` 字段记录：

- 命中的 sub query 数量。
- 命中的主题词。
- 是否 keyword/vector 双路命中。
- source_type。
- raw_score 和 final_score。

这些信息目前用于评测 CSV 和调试，不改变 `/chat` 或 `/agent/query` 的响应 schema。

### 阶段 13 评测

阶段 13 新增：

```text
scripts/evaluate_decompose.py
data/evaluation/stage13_decompose_results.csv
tests/test_evaluate_decompose.py
```

评测字段包括：

- decompose_applied
- sub_query_count
- raw_result_count
- merged_result_count
- deduplicated_count
- provenance_present
- source_hit_matched
- answer_coverage_proxy
- rerank_explanations

阶段 13 结果：

```text
decompose evaluation: 6/6
all-user decompose evaluation: 10/10
user question evaluation: 29/30
Brain workflow: 18/18
chat: 6/6
agent: 5/5
hybrid: 15/15
vector baseline: 13/15
full tests: 257 passed
```

架构结论：阶段 13 把复杂问题处理放在检索证据层，而不是让模型自行长回答。系统继续保留引用、拒答、来源治理和 API 兼容边界。

## 阶段 14 真实 Embedding 与回答覆盖校准

阶段 14 的目标是在阶段 13 证据合并稳定后，把质量判断从“检索是否命中”推进到“真实配置状态和回答覆盖是否可审阅”。

核心数据流：

```text
sources/documents/chunks/chunk_embeddings
-> deterministic baseline
-> stage14 embedding comparison
-> stage14 answer coverage review
-> stage14 decompose provenance review
-> docs/progress / README / Obsidian quality conclusion
```

阶段 14 新增：

```text
docs/stage14_real_quality_calibration.md
scripts/evaluate_stage14_embedding_comparison.py
data/evaluation/stage14_embedding_comparison.csv
scripts/evaluate_stage14_answer_coverage.py
data/evaluation/stage14_answer_coverage_review.csv
scripts/evaluate_stage14_decompose_provenance.py
data/evaluation/stage14_decompose_provenance_review.csv
```

### Embedding Comparison

`stage14_embedding_comparison.csv` 汇总多套 suite：

```text
vector
hybrid
user_questions
decompose
chat
agent
brain_workflow
```

每行记录：

```text
config_name
suite
status
passed / total / failed / pass_rate
embedding_provider / embedding_model_name / embedding_dimension
chat_provider / chat_model_name
failed_queries
skipped_reason
```

阶段 14 的关键边界是：真实配置没有结果文件时，记录为 `missing_results` 或 `skipped`，而不是伪造成 passed。当前 deterministic baseline 结果为：

```text
vector: 13/15
hybrid: 15/15
user_questions: 25/30
decompose: 10/10
chat: 6/6
agent: 5/5
brain_workflow: 18/18
```

### Answer Coverage Review

`stage14_answer_coverage_review.csv` 把回答质量拆成三个维度：

```text
Faithfulness
Answer Coverage
Citation Quality
```

这张表不会把 deterministic answer 直接当作真实回答质量证明。当前默认链路多数样例标为 `answer_coverage=review`，意思是：检索来源和引用链路稳定，但仍需要真实模型回答或人工摘要确认是否覆盖核心技术点。

unsupported 随机问题被标为低风险，因为它正确拒答且不返回来源。

### Decompose Provenance Review

`stage14_decompose_provenance_review.csv` 把阶段 13 的长字符串 `rerank_explanations` 拆成证据级字段：

```text
evidence_rank
evidence_title
evidence_sub_query_count
topic_terms
both_match
source_type
raw_score
final_score
review_note
```

这样能直接审阅“某条证据为什么进入上下文”，而不需要人工从长字符串中拆解。当前输出为 50 条证据级记录，其中 15 条来自真正 decomposed 的问题，37 条具有 keyword/vector both-match 信号。

### API 与前端边界

阶段 14 不改变外部 API schema：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
```

前端暂不修改。原因是阶段 14 的只读审阅需求已经通过 CSV 产物满足；如果后续要做展示，应优先做报告页或只读表格，不重构核心工作台。

架构结论：阶段 14 把质量校准放在 evaluation/reporting 层，而不是把真实模型调用塞进默认链路。deterministic baseline 继续负责稳定回归，真实配置结果必须显式生成并与 baseline 分开记录。

## 阶段 15 真实配置复跑与质量审阅报告

阶段 15 的目标是在阶段 14 质量表基础上，把真实配置状态、回答覆盖复核和只读报告入口落地为可重复生成的发布前质量证据。

核心数据流：

```text
stage14 quality tables
-> evaluate_stage15_real_config.py
-> data/evaluation/stage14_real/
-> stage14_embedding_comparison.csv
-> evaluate_stage15_answer_coverage_review.py
-> data/evaluation/stage15_answer_coverage_review.csv
-> build_stage15_quality_report.py
-> data/evaluation/stage15_quality_summary.csv
-> docs/stage15_quality_report.md
-> app/frontend/quality_report.html
-> GET /quality-report
```

阶段 15 新增：

```text
docs/stage15_real_review_report.md
scripts/evaluate_stage15_real_config.py
data/evaluation/stage14_real/real_config_status.csv
scripts/evaluate_stage15_answer_coverage_review.py
data/evaluation/stage15_answer_coverage_review.csv
scripts/build_stage15_quality_report.py
data/evaluation/stage15_quality_summary.csv
docs/stage15_quality_report.md
app/frontend/quality_report.html
GET /quality-report
```

### 真实配置复跑

`evaluate_stage15_real_config.py` 统一调度阶段 14/15 相关评测入口：

```text
vector
hybrid
user_questions
decompose
chat
agent
brain_workflow
```

脚本只有显式传入 `--run-real` 才运行真实配置；否则只记录 skipped，避免把真实 API 调用变成默认回归前提。真实结果统一输出到 `data/evaluation/stage14_real/`，并写入 `real_config_status.csv`。外部服务失败时记录 `error` 和脱敏错误摘要，不伪造成成功。

当前真实配置状态：

```text
vector: completed 15/15
hybrid: completed 15/15
user_questions: completed 27/30
decompose: error, SSL EOF during embedding request
chat: completed 6/6
agent: completed 5/5
brain_workflow: completed 18/18
```

### Answer Coverage 复核

`evaluate_stage15_answer_coverage_review.py` 读取阶段 14 的 medium/review 样例，并结合 `stage14_real/user_question_results.csv` 中的真实回答摘要和来源命中状态，输出：

```text
query_id
question
expected_answer_points
answer_summary
evidence_titles
faithfulness
answer_coverage
citation_quality
risk_level
review_method
review_note
next_action
```

这张表继续把 Faithfulness、Answer Coverage 和 Citation Quality 分开审阅。来源命中不等于回答覆盖；真实回答超时、无答案或缺少引用会被提升为高风险。

当前结果：

```text
9 review rows
high=1
medium=8
```

### 质量汇总与只读报告

`build_stage15_quality_report.py` 汇总四类证据：

```text
stage14_embedding_comparison.csv
stage14_real/real_config_status.csv
stage15_answer_coverage_review.csv
stage14_decompose_provenance_review.csv
```

输出：

```text
data/evaluation/stage15_quality_summary.csv
docs/stage15_quality_report.md
app/frontend/quality_report.html
```

只读报告通过 FastAPI 前端路由暴露：

```text
GET /quality-report
```

这个入口只返回静态 HTML，不调用真实模型，不写数据库，不触发 source reindex，也不改变现有核心 API schema。

当前质量门槛：

```text
stage15_quality_summary.csv: 14 rows
risk counts: high=4, low=7, medium=3
overall: review_required/high
```

### API 与前端边界

阶段 15 不改变以下 API schema：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
```

前端只新增静态报告路由 `/quality-report`，没有重构工作台。核心工作台仍负责来源、文档、检索、问答和 Agent 展示；质量报告页只负责展示阶段 14/15 的评测结论。

架构结论：阶段 15 把真实配置复跑和回答质量复核放在 evaluation/reporting 层，继续保持 deterministic baseline 与真实配置结果分离。系统现在能说明“哪些链路真实配置已通过、哪些失败是外部服务错误、哪些回答仍需人工审阅”，而不是只给一个笼统的通过率。

## 阶段 16 真实质量风险闭环

阶段 16 的目标不是增加新的检索或 Agent 功能，而是把阶段 15 报告中的发布前风险变成可解释、可复核、可人工放行或阻断的质量闭环。

核心数据流：

```text
stage15 quality report
-> stage14_real/real_config_status.csv
-> analyze_stage16_decompose_diagnostics.py
-> data/evaluation/stage16_decompose_diagnostics.csv
-> stage15_answer_coverage_review.csv
-> evaluate_stage16_answer_coverage_closure.py
-> data/evaluation/stage16_answer_coverage_closure.csv
-> build_stage16_quality_closure_report.py
-> data/evaluation/stage16_quality_closure_summary.csv
-> docs/stage16_quality_closure_report.md
-> app/frontend/quality_report.html
-> GET /quality-report
```

阶段 16 新增：

```text
docs/stage16_quality_risk_closure.md
scripts/analyze_stage16_decompose_diagnostics.py
data/evaluation/stage16_decompose_diagnostics.csv
scripts/evaluate_stage16_answer_coverage_closure.py
data/evaluation/stage16_answer_coverage_closure.csv
scripts/build_stage16_quality_closure_report.py
data/evaluation/stage16_quality_closure_summary.csv
docs/stage16_quality_closure_report.md
```

### Decompose 真实错误诊断

阶段 16 没有默认重跑真实 API，而是读取阶段 15 已保存的脱敏状态和进度证据，把 real decompose error 分类为：

```text
status_after=retry_completed
error_type=none_after_retry
root_cause=embedding_header_compatibility_and_chat_timeout
blocking_status=not_blocking
```

这表示阶段 15 的真实 provider/network 层失败没有被伪造成通过，而是在阶段 16 追加显式重试后得到真实结果。修复点包括 embedding provider 补齐 `api-key` 兼容请求头，以及将真实 chat 读取 timeout 临时提高到 120 秒。

### Answer Coverage 闭环

阶段 16 读取 `stage15_answer_coverage_review.csv` 中 high/medium 样例，输出：

```text
query_id
risk_before
risk_after
faithfulness
answer_coverage
citation_quality
root_cause
evidence
decision
next_action
```

当前结果：

```text
high=1
medium=3
low=5
```

`user_mixed_itz_strength` 仍保持 high/blocking，因为真实回答超时，不能证明回答覆盖 ITZ 与强度的期望要点。3 条 medium 是 `source_detail_limited`，适合作为人工审阅项。

### Quality Gate 与 API 边界

阶段 16 的 quality gate 为：

```text
review_required/high
```

这是一种诚实阻断状态：decompose 已完成真实重试并降为 low，但 Answer Coverage 仍有 high 样例，需要用户人工核验。阶段 16 继续保持以下 API schema 不变：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
GET /quality-report
```

`GET /quality-report` 仍只返回静态只读报告，不调用真实模型，不写数据库，不触发 source reindex，也不改变核心工作台交互。

架构结论：阶段 16 把质量风险闭环放在 evaluation/reporting 层，通过诊断表、闭环表和质量汇总报告连接阶段 15 的真实风险与人工核验流程。核心 RAG 检索、Brain、chat 和 Agent 编排保持稳定，deterministic baseline 与真实配置状态继续分离。

### 阶段 9 完成标准

```text
OpenAICompatibleEmbeddingProvider implemented
.env.example documents real chat/embedding settings
build_vector_index supports provider/model/dimension/API parameters
model config evaluation output exists
search/vector/hybrid/chat/agent APIs remain stable
full tests: 208 passed
```

### 阶段 7 完成标准

```text
docs/agent_design.md 已建立
只读 Agent 工具层已实现
Agent 编排服务已实现
POST /agent/query 已实现
旧 search/vector/hybrid/chat/sources API 不被破坏
Agent 评测脚本和结果文件已生成
前端能最小展示 Agent 回答和工具调用记录
keyword/vector/hybrid/chat/agent 评测通过
全量自动化测试通过
```

## 阶段 17 检索架构升级

阶段 17 在 retrieval 层新增三类能力，但不立即替换默认 `HybridSearchService`：

```text
app/services/retrieval/context_expansion.py
app/services/retrieval/bm25_search.py
app/services/retrieval/rrf_fusion.py
scripts/evaluate_stage17_retrieval_upgrade.py
```

新的候选检索流水线为：

```text
query normalize
-> query expansion
-> BM25 lexical retrieval
-> vector retrieval
-> merge candidates
-> deduplicate by chunk_id
-> RRF ranking
-> optional context expansion
-> context assembly
```

`BM25SearchService` 是新的词法检索通道。它复用现有中英文术语归一化和 `SYNONYM_RULES`，并为中文无空格 query 保留“孔隙率”“抗压”等领域触发词。它输出 `matched_terms`、`title_score`、`heading_score` 和 `content_score`，便于解释为什么命中。

`RRFHybridSearchService` 是新的 BM25+vector 融合通道。它不把 BM25 分数和向量余弦分数硬加权，而是记录 `bm25_rank`、`vector_rank` 和 `rrf_score`，按排名融合。每条结果保留 `matched_channels` 和 `provenance`，用于评测和人工核验。

`ContextExpansionService` 是 parent-like 上下文扩展能力。当前不新增 parent chunk 表，而是按同一个 `document_id` 下的 `chunk_index` 拉取前后相邻 chunk。扩展文本可用于 prompt context assembly，但引用仍指向核心 `chunk_id`，避免引用漂移。

阶段 17 评测结果：

```text
data/evaluation/stage17_retrieval_upgrade_results.csv
docs/stage17_retrieval_upgrade_report.md
upgraded=15/15
baseline=15/15
improved=0
regression=0
```

架构结论：阶段 17 证明 BM25+vector RRF 在当前 baseline 查询集上没有 regression，但尚未证明明显优于旧 hybrid。因此默认 `POST /search/hybrid`、Brain hybrid、`POST /chat` 和 `POST /agent/query` 暂不自动切换到新检索服务。新能力先作为评测和人工核验候选保留。

阶段 17 Phase 9 在 `data/evaluation/stage17_retrieval_upgrade_manual_review.csv` 对每条查询做人工复核：14 acceptable、1 needs_tuning（`mesoscopic_modeling` 排序 2 -> 7，被泛主题综述文档挤占）、0 regression。复核确认 hit 级「regression=0」掩盖了排序软退化，并把默认链路接入建议固定为 `keep_existing_hybrid`：`RRFHybridSearchService`、`BM25SearchService`、`ContextExpansionService` 保持候选/配置开关，等阶段 18 用更有区分度的难评测集和综述降权/topic-anchor rerank 对照证明更优后，再考虑默认接入。

## 阶段 18 语料扩充与评测/质量体系增强

阶段 18 不改外部 API contract，而是把语料深度和评测/质量体系做厚。核心数据流：

```text
OpenAlex 发现 -> RFC 相关性过滤 -> 许可允许开放获取过滤
-> 礼貌下载（data/fulltext/open_access_auto，gitignore）
-> 加固 PDF 解析（pdf_text.structure_pdf_pages）
-> cleaner / splitter（带真实 heading_path）
-> documents/chunks（source_type=open_access_pdf）
-> deterministic + jina 双向量索引
-> source registry 去重/权限标注
难评测集（跨段/易混淆/需拒答）
-> keyword / vector / hybrid / bm25_rrf / bm25_rrf_context 多配置对比
-> 默认链路数据结论
-> quality gate 汇总
-> 只读 /quality-report（筛选/风险队列/导出）
```

### PDF 解析加固层

阶段 18 新增 `app/services/ingestion/pdf_text.py`，位于 `parser.read_pdf_text` 内、`cleaner`/`splitter` 之前：

- `structure_pdf_pages(pages)`：跨页去重页眉页脚 -> 逐页结构化 -> 保留 `## Page N`。
- `structure_page_text`：unicode 归一 -> 断词合并 -> heading 识别（编号/关键词/多词全大写）-> 表格行成块 -> 噪声行丢弃。
- 目的：让全文 chunk 带上真实 `heading_path`（splitter 依赖 Markdown `#` 标题），改善跨段证据定位。
- 纯函数、deterministic，可用合成文本 fixture 测试，不依赖真实 PDF。

### 语料扩充管线

`scripts/expand_open_access_corpus.py` 复用 `app/services/source_collection.py`（`SourceCandidate`、相关性过滤、dedupe、`download_pdf`）和 `scripts/collect_sources.collect_openalex`：

- 只下载许可允许（cc-by/cc-by-nc/cc0/明确 OA）的开放获取全文；尊重条款，不绕付费墙/登录/验证码。
- 发现集写入独立 `data/metadata/stage18_oa_discovery.csv`，不污染 curated `data/source_candidates.csv`。
- 仅为真正新导入（非 content-hash 重复）论文写 `fulltext_manifest.csv`（按 local_path + 归一化标题去重）。
- `data/app.sqlite` 与 `data/fulltext/` 均 gitignore；可提交物是解析器、manifest/registry 条目、题录卡片和管线脚本；深度全文 DB 增长靠可复跑导入管线复现。

### 评测与质量体系

- 难评测集 `data/evaluation/stage18_hard_queries.csv`（跨段证据 / 易混淆术语 / 需拒答边界），独立 CSV，不覆盖旧 baseline。
- `scripts/evaluate_stage18_hard_set.py` 对比 5 种检索配置，输出 hit@8 / rank@1 / precision@1 / mean_rank / distinct_wins，并用默认 Brain（evidence confidence）判定需拒答查询；不静默 fallback 掩盖配置差异。
- `scripts/build_stage18_quality_report.py` 汇总 quality gate（corpus / hard_set / default_chain / real_config / refusal_boundary / stage17_residual / stage16_residual / overall），状态口径 pass / review_required / blocked。

### Quality Report 增强（只读边界）

- `GET /quality-report` 仍是静态只读页（`app/frontend/quality_report.html`），阶段 18 增强客户端筛选（section/risk）+ 风险队列（high/medium）+ 导出（CSV/JSON Blob）。
- 新增只读端点 `GET /quality-report/data.json`、`GET /quality-report/export.csv`，只读取本地脱敏汇总 CSV，不触发真实 API、不写库、不做登录。

### API 与默认链路边界

阶段 18 保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 不被破坏。多配置对比结论为 `keep_existing_hybrid`（bm25_rrf 未优于 hybrid），默认 Brain hybrid 链路不切换；BM25+RRF / context expansion 继续作为候选/配置开关。

### 架构结论

阶段 18 用更有区分度的难评测集证实了阶段 17 的 `keep_existing_hybrid` 结论（hit@8 仍饱和，但 rank@1 出现区分度，bm25_rrf 未赢过 hybrid），并以数据闭环了阶段 17 `mesoscopic_modeling` 排序软退化担忧。同时难评测集暴露出真实的 off-topic 拒答边界偏松问题（deterministic 与真实 Jina 下均 1/5），阶段 18 在 quality gate 显式标为 high 阻断并写明原因，不静默修改默认拒答逻辑，留待后续独立校准 Phase。


## 阶段 19 中文全文文献分析与检索/评测调优

阶段 19 不再加模型/语料，而是把约 340 篇中文深度全文真正用起来：第一轮真实/确定性 agent 文献分析 → 量化中文查询排序短板 → 中文难评测集 → 候选重权对照 → 数据驱动决策。

核心数据流：

```text
POST /chat 或 AgentToolbox.answer_with_citations
-> BrainService.answer()
-> HybridSearchService (默认 0.7 keyword + 0.3 vector + 0.15 both_match)
-> (评测脚本) source_type_reweight 后处理重权（可关闭）
-> top-K 候选
-> evidence confidence + has_topic_anchor 拒答门
-> generate_answer
```

### 阶段 19 候选重权模块

阶段 19 新增 `app/services/retrieval/source_type_reweight.py`（纯函数）：

```text
Stage19TuningWeights
  name
  fulltext_boost           # 命中 open_access_pdf / institutional_access_pdf 的加分
  metadata_demote          # 命中 metadata_record / local_file 的减分（传正值）
  topic_anchor_bonus_per_term  # 命中 CORE_DOMAIN_TERMS 时的每词加分（仅对深度全文生效）
  topic_anchor_cap         # 主题锚点加分上限

默认 4 套：
  BASELINE_WEIGHTS              # 全 0 偏移，与默认 HybridSearchService 等价
  FULLTEXT_BOOST_WEIGHTS        # fulltext_boost=0.30
  METADATA_DEMOTE_WEIGHTS       # metadata_demote=0.30
  TOPIC_ANCHOR_STRICT_WEIGHTS   # topic_anchor 0.06/词 + cap 0.30 + fulltext_boost 0.10
```

- 纯函数 `reweight_results(results, weights, query)`，不修改输入，稳定重排键：`(-score, source_type_rank, document_id, chunk_index)`。
- `CORE_DOMAIN_TERMS` 与 Brain `workflow.py` 含义对齐但在该模块内独立维护，避免与默认拒答门耦合。
- **不改 `HybridSearchService` 默认参数；不改 API schema；只在 `scripts/evaluate_stage19_retrieval_tuning.py` 内组合使用**。

### 第一轮文献分析探索 + 中文难评测集

- `scripts/explore_chinese_corpus.py`：10 题真实中文研究问题，默认 deterministic，可选 `--real` 走 MIMO+Jina（带轻量重试，真实失败显式写 CSV `error`）；输出 `data/evaluation/stage19_exploration_results.csv`（含 top-8 source_type 分布、深度全文/题录命中名次、refused、回答摘要、耗时、错误）。
- `data/evaluation/stage19_chinese_hard_queries.csv`：19 题独立中文难评测集（5 跨段证据 + 5 易混淆术语 + 5 参数细节 + 4 需拒答），锚定中文深度全文真实主题，不覆盖旧 `stage18_hard_queries.csv`。
- `scripts/evaluate_stage19_retrieval_tuning.py`：对照 4 配置；非拒答题用 hybrid `fetch_k=24` 召回 + 重权 + top-K=8 评测；拒答题用 `BrainService.answer` 验证。输出 `stage19_retrieval_tuning_results.csv` + `stage19_retrieval_tuning_summary.csv`，含决策门槛回写。

### 数据结论

- Phase 0 探索：deep_top1=0/8、metadata_top1=5/8（题录系统性压过深度全文）。
- Phase 2 调优：三候选都把 `deep_fulltext_top1_rate` 从 0.000 拉升到 0.533–0.733；但 precision@1 不升反降（关键词 hit 判定偏向题录）。
- 决策门槛（Δp@1 ≥ 0.10 且 Δdeep_top1 ≥ 0.20 且 refusal 不退化）下 → **`keep_existing_hybrid`**：三候选作为可配置开关保留在 `source_type_reweight.py`。

### API 与默认链路边界

阶段 19 保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 不被破坏。默认 Brain hybrid 链路**不切换**；`source_type_reweight` 仅在阶段 19 评测脚本中组合使用，作为候选/可配置开关。

### 架构结论

阶段 19 用真实数据**首次量化**了中文查询的 metadata vs deep_fulltext 排序短板，并以纯函数对照 + 严格门槛得出诚实的 `keep_existing_hybrid` 决策；同时把三种调优作为可配置开关纳入候选模块，为后续阶段（优化 hit 判定 / 用真实 Jina 重跑 / 答案级 ratio 评测）的默认链路切换留出数据驱动入口。


## 阶段 20 中文检索默认链路落地与评测判定增强

阶段 20 不新增语料、不新增爬虫、不重做 chunk embedding，而是把阶段 19 的候选调优结论放到更严格的答案级评测与真实 Jina query 端校验里复核，再决定默认链路是否切换。同时补上阶段 19 暴露的工程责任边界拒答门。

核心数据流：

```text
stage19_chinese_hard_queries.csv
-> evaluate_stage20_eval_upgrade.py
   -> deterministic coverage_ratio
   -> optional real Jina query-only coverage_ratio
-> build_stage20_default_chain_decision.py
-> keep_existing_hybrid 或 switch_default_candidate
-> build_stage20_quality_report.py
-> data/evaluation/stage20_quality_summary.csv
-> docs/stage20_quality_report.md + GET /quality-report
```

默认问答链路保持：

```text
POST /chat 或 AgentToolbox.answer_with_citations
-> BrainService.answer()
-> HybridSearchService (默认 0.7 keyword + 0.3 vector + 0.15 both_match)
-> evidence confidence + has_topic_anchor
-> responsibility_gate（生成前工程责任边界拒答）
-> generate_answer 或责任边界拒答
```

### 答案级 coverage ratio

阶段 20 新增 `scripts/evaluate_stage20_eval_upgrade.py`，复用阶段 19 中文难评测集，但把主 hit 口径从 `expected_source_hit` 关键词命中升级为 `expected_answer_points` 覆盖率：

- 非拒答题：检查 top-1 证据的 `heading_path + content` 是否覆盖期望回答要点，刻意不把 `document_title` 作为 top-1 coverage 证据，降低题录标题关键词密度带来的偏置。
- 拒答题：继续用 Brain 是否 refused 与 `expected_refused` 对齐计算 `refusal_accuracy`。
- 输出 `data/evaluation/stage20_eval_upgrade_results.csv` 与 `stage20_eval_upgrade_summary.csv`，schema 包含 `query_id`、`config`、`judge_mode`、`hit`、`coverage_ratio`、`deep_fulltext_top1`、`refusal_matched`、`decision`、`next_action`。

真实 Jina 校验通过同一脚本的 `--real-query` 模式完成，只调用真实 provider 生成 query embedding，复用已有 `jina-embeddings-v3 / dim=1024` chunk embeddings；不调用 `VectorIndexService`，不重建 8918 条 chunk 向量。缺少配置或调用失败时写 `real_config_status=skipped/error`，不把 deterministic 结果伪造成真实成功。

### 默认链路决策

阶段 20 新增 `scripts/build_stage20_default_chain_decision.py`，同时要求 deterministic 与真实 Jina query-only 结果满足切换门槛：

```text
delta_precision_at_1 >= 0.10
and delta_deep_fulltext_top1_rate >= 0.20
and refusal_accuracy >= baseline_refusal_accuracy
```

实际结果：

- `hybrid_fulltext_boost`、`hybrid_metadata_demote`、`hybrid_topic_anchor_strict` 的 `delta_precision_at_1` 均为 `+0.000<0.10`。
- 候选 deep_fulltext top-1 明显提升，但答案级 p@1 没有提升。
- 最终决策为 `keep_existing_hybrid`，不把 `source_type_reweight` 接入默认 `HybridSearchService` / Brain hybrid 链路。

这个决策避免了“只因深度全文排上来就切默认链路”的风险：默认链路必须同时改善答案覆盖、深度全文排序和拒答边界。

### responsibility_gate 责任边界拒答门

阶段 20 在 `app/services/brain/workflow.py` 与 `app/services/brain/service.py` 新增责任边界门：

- `evaluate_responsibility_gate(query)`：纯函数判断查询是否要求系统替代工程责任判断。
- `RESPONSIBILITY_REFUSAL_ANSWER`：统一提示系统不替代规范审查、工程设计、第三方检测或专家签字。
- `BrainService._generate_answer_step()`：在证据置信度与模型生成前调用责任门；命中后直接返回责任边界拒答。

它与阶段 18 的 `has_topic_anchor` 分工不同：`has_topic_anchor` 解决 off-topic 问题，`responsibility_gate` 解决“同主题但不应替代审查/签字”的问题。正例包括“请判定本工程配合比是否符合规范要求”，反例包括“堆石混凝土配合比通常关注哪些指标”。

### Quality gate 与只读报告

阶段 20 新增 `scripts/build_stage20_quality_report.py`，生成：

- `data/evaluation/stage20_quality_summary.csv`
- `docs/stage20_quality_report.md`
- `app/frontend/quality_report.html`

`GET /quality-report` 继续是静态只读质量报告页，只读取本地脱敏 CSV/HTML，不触发真实 API、不写数据库、不重新索引、不改变登录或权限体系。全量测试通过后，阶段 20 quality gate 为 `pass/low`。

### API 与默认链路边界

阶段 20 保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 不被破坏。聚焦回归 61 passed + 67 passed，全量测试 424 passed。

架构结论：阶段 20 把阶段 19 的“候选重权可能有用”升级为“经过答案级判定与真实 query 端校验后仍不足以切默认链路”的可复核结论。真正进入默认运行链路的是 `responsibility_gate`，因为它闭环的是安全责任边界，而不是检索排序偏好；`source_type_reweight` 继续保持候选/评测开关。
## Phase 35 Clean Architecture Update

Phase 35's accepted architecture change is retrieval-strategy isolation, not score tuning. The clean final chain is:

```text
Stage 30 deductions / Stage 34 Judge evidence
-> leakage removal
-> score density analysis
-> HybridRrfTailSearchService
-> Stage 29 clean retrieval rerun
-> Stage 30 score rerun
-> human verification
```

`HybridRrfTailSearchService` lives in `app/services/retrieval/hybrid_rrf_tail.py`. It keeps the existing hybrid top 3 as the trusted head and uses BM25+vector Reciprocal Rank Fusion only to fill tail recall slots. This keeps retrieval strategy separate from scoring and policy.

No Stage 30 scoring weights, grade thresholds, release rules, default providers, provider topology, or external data sources were changed. The clean final Stage 30 result under the default GLM embedding provider is `91.52 / A / pass`. Real Judge remains a separate generation-quality review risk: production GLM before validator was `answer_coverage=0.525`, `citation_support=0.750`, `safety_leak_check=0.700`; the final documented conclusion is Judge gate FAIL with no production validator regression retained.

## Stage 37 tool runtime refinement

`ToolCallingAgentService` now behaves as a lightweight tool runtime, not only a provider wrapper. It enforces one executed read-only RAG search per model turn, returns safe skipped `role="tool"` messages for skipped `tool_call_id`s, blocks near-duplicate search queries, converges from existing sanitized sources when the model keeps asking for tools, and performs one bounded citation repair turn when a source-backed draft misses `[N]` markers.

This keeps Phase 37 inside the existing provider topology: no LangGraph, no checkpointing framework, no write tools, no default provider replacement, and no default routing switch. The tiered-provider tradeoff remains: `react_agent` can use Flash planner + V4-Pro answer, while the first `tool_calling_agent` path uses one tools-capable model for planning and final answering unless a later phase explicitly designs a tiered tool-calling variant.

## Phase 41 Architecture Delta: Post-Import Retrieval Optimization

Phase 41 does not change the default Agent chain, prompt strategy, Stage 30 scoring rules, provider topology, frontend code, or data-source boundaries. The architecture delta is limited to rebuilding the retrieval substrate after the Phase 40 corpus import.

The chunk table now contains both child chunks and Stage 31 parent rows:

```text
documents=753
chunks table rows=25687
indexable child chunks=19300
parent rows=6387
```

`VectorIndexService._list_chunks()` intentionally indexes only child chunks that are not parent containers. Parent rows provide context expansion and are not embedded or stored in FAISS. This keeps the retrieval vector set aligned with answerable evidence chunks while preserving parent context for synthesis.

The production retrieval substrate is:

```text
query
-> GLM-Embedding-3 query embedding
-> FAISS paratera_GLM-Embedding-3_dim2048
-> hybrid_rrf_tail retrieval/rerank path
-> parent context expansion
-> default tool_calling_agent answer path
```

The CI/offline baseline substrate mirrors the same child chunk set with `deterministic / hash-token-v1 / dim64` embeddings and a deterministic FAISS index. CI and full local pytest do not require real provider API calls.

Phase 41 also adds safe post-import retrieval evaluation. The evaluation CSVs store query ids, categories, source types, top titles, numeric metrics, and sanitized errors only. They do not store API keys, Bearer tokens, raw provider responses, `raw_response`, `reasoning_content`, hidden reasoning, restricted full text, or full chunk content.

## Phase 44 Architecture Delta: Production Deployment, PostgreSQL, And Auth Isolation

Phase 44 expands the local SQLite-only shape into a production-deployable shape while keeping SQLite as the default local development and full-test path. `app/db/session.py::create_database_engine()` selects the engine from `DATABASE_URL`: SQLite keeps `check_same_thread=False`, while PostgreSQL uses `pool_pre_ping=True`. Alembic is now the schema migration entry point; the initial migration explicitly creates `documents`, `sources`, `chunks`, `chunk_embeddings`, `conversations`, `messages`, `qa_logs`, `users`, and nullable `conversations.user_id`.

Auth adds `User`, `app/core/security.py`, `app/api/auth.py`, and `app/schemas/auth.py`:

```text
POST /auth/register -> bcrypt password_hash -> users
POST /auth/login -> verify_password -> HS256 JWT
GET /auth/me -> Authorization: Bearer <token> -> current user
```

When `AUTH_ENABLED=false`, local development remains backward compatible. When `AUTH_ENABLED=true`, `/agent/query`, `/agent/query/stream`, and `/conversations/*` are guarded by `get_current_user()`. `/health`, `/health/details`, `/auth/register`, and `/auth/login` remain public. Conversation isolation is enforced in the repository layer: list, read, messages, delete, rename, and Agent append paths all filter by `user_id`; cross-user conversation access returns 404.

Production deployment shape:

```text
docker-compose.prod.yml
-> db: postgres:16-alpine + postgres_data volume + pg_isready healthcheck
-> app: build Dockerfile
-> env: AUTH_ENABLED=true, DATABASE_URL=postgresql+psycopg2://..., JWT_SECRET_KEY
-> command: alembic upgrade head && uvicorn app.main:app
```

The native frontend remains static HTML/CSS/JS with no Node/React/Vue build chain. Phase 44 adds a standalone Chinese authentication gate with login and account creation tabs, then reveals the Agent workspace only after sign-in. After login, the JWT is stored in browser `localStorage`; `fetchJson()` and `streamAgentQuery()` inject the `Authorization` header. The frontend must not display or log the full token.

Security boundary: JWT secrets, database passwords, SSH passwords, bearer tokens, API keys, provider raw responses, `raw_response`, `reasoning_content`, and restricted full text must not enter Git, CSV, docs, tests, or Obsidian. The cloud server is a deployment smoke and human-verification target, not a CI or local full-test prerequisite.

## Phase 45 Quality Repair Delta

Phase 18-20 adds a quality repair layer before cloud publication:

```text
image_description chunks
-> scripts/clean_phase45_low_value_images.py
-> remove QR / publisher logo / deterministic template / very short low-information chunks
-> keep orientation-review chunks for human inspection

phase12 quality audit
-> stronger title weakness detection
-> year recovery from early text chunks
-> expanded cloud_candidate set
-> candidate-only embeddings and FAISS rebuild
```

This keeps the architecture local-first. The repair layer changes release eligibility and derived indexes; it does not alter the default Agent chain, auth, provider topology, or cloud runtime contract.

## Phase 47 Architecture Delta: Multimodal Interaction Layer

Phase 47 adds an interaction layer above the existing multimodal retrieval substrate without changing Stage 30 scoring, provider defaults, auth isolation, or the cloud migration boundary.

```text
PDF text/table/image chunks
-> search_knowledge / search_tables / search_figures
-> ReAct or tool-calling agent
-> AgentQueryResponse sources with table_content, image_analysis, content_bbox
-> native frontend evidence cards and citation drawer
```

The new schema surface is:

- `chunks.content_bbox_json`: optional JSON payload for page number, bbox list, and confidence.
- `qa_feedback`: answer-level user feedback with rating, optional reason/comment, and optional links to conversation/message/QA log ids.
- `AgentSearchResultItem` and `AgentSourceItem`: optional `table_content`, `image_analysis`, and `content_bbox`.

Table extraction uses PyMuPDF `page.find_tables()` and stores extracted Markdown as `chunk_type="table"`. User uploads are validated with Pillow and saved under `data/user_uploads/`; the ReAct path calls the configured vision provider through the existing provider abstraction, with deterministic provider support for tests. Citation location is best-effort: exact bbox, partial bbox, page-only, or none. Feedback export is local and sanitized before writing `data/evaluation/phase47_user_feedback_eval.csv`.

The frontend remains a static FastAPI-served HTML/CSS/JS app. It does not introduce a Node build chain. New controls are thin API clients for upload, feedback, and evidence rendering.
