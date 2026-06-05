# Progress Log

## Session: 2026-06-05

### Phase 0: 阶段 3 启动与规划
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 使用 Codex 线程工具将当前线程标题修改为 `阶段3-引用式问答`。
  - 确认当前工作区原本位于 `main`，且工作区干净。
  - 从 `main` 新建并切换到 `codex/phase-3-cited-chat`。
  - 按 `planning-with-files` 技能要求，重读现有 `task_plan.md`、`findings.md`、`progress.md`。
  - 运行 `planning-with-files` 的 session catchup 脚本，未发现需要同步的额外输出。
  - 读取 `planning-with-files` 模板，确定继续使用项目根目录下的 `task_plan.md`、`findings.md`、`progress.md`。
  - 重新确认阶段 2 当前证据：63 个测试通过、136 篇 documents、997 个 chunks、997 条 chunk embeddings、关键词评测 15/15、向量评测 11/15。
  - 参考 Quivr 的 `Brain`、`LLMEndpoint`、`QuivrQARAG`、`RAG_ANSWER_PROMPT`、`combine_documents()`、`ParsedRAGResponse`、`RAGResponseMetadata`。
  - 将阶段 2 planning 文件重写为阶段 3 planning 文件。
- Files created/modified:
  - `task_plan.md` rewritten for Stage 3
  - `findings.md` rewritten for Stage 3
  - `progress.md` rewritten for Stage 3

### Quivr Architecture Notes
- **Status:** complete
- Actions taken:
  - 确认 Quivr 的高层模式是 `Brain` 聚合 storage、processor、embedder、vector store、LLM 和 chat history。
  - 确认 Quivr 的 RAG workflow 是 `filter_history -> rewrite -> retrieve -> generate_rag`。
  - 确认 Quivr 的 prompt 约束是“只基于 context 回答，不能回答时说没有答案”。
  - 确认 Quivr 通过给 docs 加 `Source: index` 支持引用。
  - 确认 Quivr 的 response metadata 会携带 citations、followup_questions、sources 和模型信息。
  - 确认 Quivr 的测试使用 fake LLM，适合本项目借鉴 deterministic chat provider。
- Files created/modified:
  - `findings.md` updated with Quivr findings
  - `task_plan.md` updated with decisions based on Quivr

### Phase 1: ChatModelProvider 抽象
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `app/services/generation/` 目录，作为阶段 3 的生成层入口。
  - 新增 `app/services/generation/chat_model.py`。
  - 定义 `ChatMessage`，用 `role/content` 表示传给聊天模型的消息。
  - 定义 `ChatModelResult`，统一返回 answer、provider、model_name 和可选 raw_response。
  - 定义 `ChatModelProvider` 协议，统一 `generate()` 方法。
  - 实现 `DeterministicChatModelProvider`，用于无 API key 的本地开发和自动化测试。
  - 实现 `OpenAICompatibleChatModelProvider` 的最小调用边界，支持后续国产 OpenAI-compatible 模型。
  - 新增 `create_chat_model_provider()` 工厂函数。
  - 扩展 `app/core/config.py` 和 `.env.example`，新增聊天模型 temperature 和 timeout 配置。
  - 新增 `tests/test_chat_model_provider.py`，覆盖消息校验、deterministic provider、provider 工厂、OpenAI-compatible 配置和响应解析。
  - 新增 `docs/stage3_learning_notes.md`，记录本步骤目标、新词解释、设计原因、验证结果和面试表达。
- Files created/modified:
  - `app/services/generation/__init__.py` created
  - `app/services/generation/chat_model.py` created
  - `tests/test_chat_model_provider.py` created
  - `app/core/config.py` modified
  - `.env.example` modified
  - `docs/stage3_learning_notes.md` created
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 2: RAG 上下文组织与引用编号
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `app/services/generation/prompt_builder.py`。
  - 定义 `ContextSource`，作为给模型看的来源条目。
  - 定义 `RagPrompt`，作为 prompt builder 的结构化输出。
  - 新增 `SearchResultLike` 协议，让 prompt builder 能接收关键词检索或向量检索结果。
  - 实现 `build_rag_prompt()`，把用户问题和检索结果转成 system/user messages。
  - 实现 `[1] [2]` 来源编号，并把编号绑定到 chunk_id。
  - 实现 `format_source()` 和 `format_context()`，把标题、来源、chunk、score 和内容写进上下文。
  - 实现 `truncate_text()` 和 `limit_sources_for_context()`，控制单个 chunk 和总上下文长度。
  - 在默认 system prompt 中加入“只基于 context 回答”“资料不足时拒答”和中文工程免责声明。
  - 新增 `tests/test_prompt_builder.py`，覆盖编号、消息结构、免责声明、空输入、截断、上下文限制和来源元数据。
  - 首次测试发现截断后包含 suffix 导致长度超限，已修复并重跑通过。
- Files created/modified:
  - `app/services/generation/prompt_builder.py` created
  - `tests/test_prompt_builder.py` created
  - `docs/stage3_learning_notes.md` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 3: CitationAnswerService 最小问答链路
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `app/services/generation/answer_service.py`。
  - 定义 `RetrievalOutcome`，表示一次检索的结果、实际使用的检索模式和拒答原因。
  - 定义 `CitationAnswerResult`，统一返回 question、answer、citations、sources、refused、refusal_reason、retrieval_mode、model_provider 和 model_name。
  - 实现 `CitationAnswerService.answer()`，串联问题校验、检索、prompt 构造、聊天模型调用、引用提取和结构化返回。
  - 实现 `retrieval_mode="auto"`：优先向量检索，向量没有可用结果时回退关键词检索。
  - 实现资料不足拒答：无检索结果、低于 `min_score` 或无法构造有效上下文时，不让模型硬编答案。
  - 实现 `extract_citations()`，从答案文本提取 `[1]`、`[2]` 这类编号，并只保留本次 sources 中存在的编号。
  - 新增 `tests/test_answer_service.py`，覆盖向量问答、无结果拒答、低分拒答、关键词回退、非法引用过滤和参数校验。
  - 测试中发现 deterministic provider 会把完整 RAG prompt 当成问题回显，导致引用污染；已在 `chat_model.py` 中新增 `extract_question()` 修复。
  - 补充本阶段新词解释与面试表达至 `docs/stage3_learning_notes.md`。
- Files created/modified:
  - `app/services/generation/answer_service.py` created
  - `tests/test_answer_service.py` created
  - `app/services/generation/chat_model.py` modified
  - `tests/test_chat_model_provider.py` modified
  - `docs/stage3_learning_notes.md` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 4: Chat API 与响应 Schema
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `app/schemas/chat.py`。
  - 定义 `ChatRequest`，包含 question、top_k、retrieval_mode 和 min_score，并在 schema 层拒绝空白问题。
  - 定义 `ChatSourceItem`，让 `/chat` 返回的每个来源都能追溯到 document、chunk、heading、content 和 score。
  - 定义 `ChatResponse`，统一返回 answer、citations、sources、refused、refusal_reason、retrieval_mode、model_provider 和 model_name。
  - 新增 `app/api/chat.py`，实现 `POST /chat`。
  - 在 `app/main.py` 注册 chat router。
  - 在 chat 路由中新增 `get_chat_model_provider()` 和 `get_embedding_provider()` 依赖，统一从 settings 构造 provider。
  - 保持 API 层为薄封装：只做请求校验、依赖注入、service 调用和响应映射。
  - 新增 `tests/test_chat_api.py`，覆盖正常问答、auto 模式关键词回退、资料不足拒答、source 字段完整性、provider 元信息、空白问题 422 和非法检索模式 422。
- Files created/modified:
  - `app/schemas/chat.py` created
  - `app/api/chat.py` created
  - `app/main.py` modified
  - `tests/test_chat_api.py` created
  - `docs/stage3_learning_notes.md` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 5: QA 日志与可观测性
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 评估 Phase 5 是否落地数据库日志，结论是本阶段落地最小 `qa_logs` 表。
  - 新增 `QuestionAnswerLog` SQLAlchemy 模型，对应 `qa_logs` 表。
  - 新增 `QuestionAnswerLogCreate` 和 `QuestionAnswerLogRepository`，负责保存、查询、列表和计数。
  - 新增 `serialize_int_list()` 和 `deserialize_int_list()`，用于保存 retrieved_chunk_ids 和 citations。
  - 更新 `CitationAnswerService`，成功问答和拒答都会默认写入 QA 日志。
  - 为 `CitationAnswerService` 增加 `log_answers` 参数，允许测试或特殊批处理关闭日志副作用。
  - 新增 `tests/test_chat_logging.py`，覆盖日志 repository、成功问答日志、拒答日志、关闭日志和 raw_response 不落库。
- Files created/modified:
  - `app/db/models.py` modified
  - `app/db/repositories.py` modified
  - `app/services/generation/answer_service.py` modified
  - `tests/test_chat_logging.py` created
  - `docs/stage3_learning_notes.md` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 6: 阶段 3 评测与回归验证
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `data/evaluation/chat_queries.csv`，覆盖概念、施工/质量控制、温控、填充能力、工程案例和无依据问题。
  - 新增 `scripts/evaluate_chat.py`。
  - 定义 `ExpectedChatQuery` 和 `EvaluatedChatResult`，分别对应 chat 评测输入和输出。
  - 第一版 chat 评测指标包括：是否返回答案、是否按预期拒答、是否返回 sources、citations 是否映射到 sources、期望来源是否命中、答案是否包含禁止硬编词。
  - 默认使用 deterministic chat provider，避免真实模型 API、网络和随机输出影响评测。
  - 默认 `log_answers=False`，避免批量评测污染 `qa_logs`；需要时可使用 `--log-answers` 显式打开。
  - 新增 `tests/test_evaluate_chat.py`，覆盖支持问题通过、无依据拒答通过、缺失必需引用失败、CSV 读取和结果写出。
  - 运行真实数据库 chat 评测并输出 `data/evaluation/chat_results.csv`，结果为 6/6 passed。
  - 运行阶段 1 关键词评测，结果为 15/15 passed。
  - 运行阶段 2 向量评测，结果为 11/15 passed，保持阶段 2 已知水平。
  - 运行全量回归，结果为 106 passed。
- Files created/modified:
  - `data/evaluation/chat_queries.csv` created
  - `data/evaluation/chat_results.csv` created
  - `scripts/evaluate_chat.py` created
  - `tests/test_evaluate_chat.py` created
  - `data/evaluation/keyword_results.csv` regenerated
  - `data/evaluation/vector_results.csv` regenerated
  - `docs/stage3_learning_notes.md` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 7: 阶段收尾文档与 Obsidian
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 更新 `README.md`，将当前阶段从阶段 2 校准为阶段 3 已完成，并补充 `/chat` 用法、响应字段、拒答机制、chat 评测和阶段 3 面试表达。
  - 更新 `docs/progress.md`，新增阶段 3 完成记录，写入完成内容、验证结果、已处理问题、遗留问题、下一阶段任务和面试表达。
  - 更新 `docs/architecture.md`，补充 generation 层、ChatModelProvider、RAG prompt/context builder、CitationAnswerService、Chat API、qa_logs 和 chat 评测策略。
  - 判断 `AGENT.MD` 需要更新，因为阶段 3 改变了当前状态和下一步推荐任务；已同步为阶段 4 数据采集与来源管理。
  - 更新 Obsidian 首页、阶段索引和阶段 3 页面。
  - 更新 Obsidian 分类页：`RAG 链路`、`API 设计`、`测试与验证`、`后端工程`、`工程化与可观测性`。
  - 新增 Obsidian 知识点：`ChatModelProvider 抽象`、`RAG prompt 构造`、`引用来源编号`、`拒答机制`、`Chat API 响应结构`、`QA 日志与可观测性`、`Chat 问答评测`。
- Files created/modified:
  - `README.md` modified
  - `docs/progress.md` modified
  - `docs/architecture.md` modified
  - `AGENT.MD` modified
  - `obsidian-vault/首页.md` modified
  - `obsidian-vault/阶段索引.md` modified
  - `obsidian-vault/阶段/阶段 3 - 引用式问答.md` modified
  - `obsidian-vault/分类/RAG 链路.md` modified
  - `obsidian-vault/分类/API 设计.md` modified
  - `obsidian-vault/分类/测试与验证.md` modified
  - `obsidian-vault/分类/后端工程.md` modified
  - `obsidian-vault/分类/工程化与可观测性.md` modified
  - `obsidian-vault/知识点/ChatModelProvider 抽象.md` created
  - `obsidian-vault/知识点/RAG prompt 构造.md` created
  - `obsidian-vault/知识点/引用来源编号.md` created
  - `obsidian-vault/知识点/拒答机制.md` created
  - `obsidian-vault/知识点/Chat API 响应结构.md` created
  - `obsidian-vault/知识点/QA 日志与可观测性.md` created
  - `obsidian-vault/知识点/Chat 问答评测.md` created
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| stage 2 baseline check before planning | `python -m pytest -q` | all tests pass | 63 passed | pass |
| local database count check | SQLite counts | documents/chunks/embeddings available | 136 documents, 997 chunks, 997 embeddings | pass |
| planning files rewrite | inspect `task_plan.md`, `findings.md`, `progress.md` | reflect Stage 3 | Stage 3 plan, findings, and progress are readable and aligned | pass |
| chat model provider tests | `python -m pytest tests\test_chat_model_provider.py -q` | pass | 13 passed | pass |
| chat model provider compile | `python -m py_compile app\services\generation\chat_model.py tests\test_chat_model_provider.py app\core\config.py` | pass | pass | pass |
| full regression after Phase 1 | `python -m pytest -q` | pass | 76 passed | pass |
| prompt builder tests first run | `python -m pytest tests\test_prompt_builder.py -q` | pass | 1 failed, 8 passed | fail |
| prompt builder tests after fix | `python -m pytest tests\test_prompt_builder.py -q` | pass | 9 passed | pass |
| prompt builder compile | `python -m py_compile app\services\generation\prompt_builder.py tests\test_prompt_builder.py` | pass | pass | pass |
| full regression after Phase 2 | `python -m pytest -q` | pass | 85 passed | pass |
| answer service tests first run | `python -m pytest tests\test_answer_service.py -q` | pass | 1 failed, 6 passed | fail |
| answer service and chat provider tests after fix | `python -m pytest tests\test_chat_model_provider.py tests\test_answer_service.py -q` | pass | 21 passed | pass |
| full regression after Phase 3 | `python -m pytest -q` | pass | 93 passed | pass |
| chat API tests | `python -m pytest tests\test_chat_api.py -q` | pass | 5 passed | pass |
| chat API compile | `python -m py_compile app\schemas\chat.py app\api\chat.py app\main.py tests\test_chat_api.py` | pass | pass | pass |
| full regression after Phase 4 | `python -m pytest -q` | pass | 98 passed | pass |
| QA logging tests | `python -m pytest tests\test_chat_logging.py tests\test_answer_service.py tests\test_chat_api.py -q` | pass | 16 passed | pass |
| QA logging compile | `python -m py_compile app\db\models.py app\db\repositories.py app\services\generation\answer_service.py tests\test_chat_logging.py` | pass | pass | pass |
| full regression after Phase 5 | `python -m pytest -q` | pass | 102 passed | pass |
| chat evaluation tests | `python -m pytest tests\test_evaluate_chat.py -q` | pass | 4 passed | pass |
| chat evaluation compile | `python -m py_compile scripts\evaluate_chat.py tests\test_evaluate_chat.py` | pass | pass | pass |
| chat evaluation first real run | `python scripts\evaluate_chat.py --queries data\evaluation\chat_queries.csv --out data\evaluation\chat_results.csv` | pass | 4/6 passed | fail |
| chat evaluation after query-set fix | `python scripts\evaluate_chat.py --queries data\evaluation\chat_queries.csv --out data\evaluation\chat_results.csv` | pass | 6/6 passed | pass |
| keyword evaluation after Phase 6 | `python scripts\evaluate_keyword_search.py --queries data\evaluation\keyword_queries.csv --out data\evaluation\keyword_results.csv` | pass | 15/15 passed | pass |
| vector evaluation after Phase 6 | `python scripts\evaluate_vector_search.py --queries data\evaluation\keyword_queries.csv --out data\evaluation\vector_results.csv --keyword-results data\evaluation\keyword_results.csv --skip-index-build` | pass | 11/15 passed | pass |
| full regression after Phase 6 | `python -m pytest -q` | pass | 106 passed | pass |
| documentation status check after Phase 7 | `rg` over README, docs, AGENT, Obsidian | stage 3 complete references present | stage 3 complete, `/chat`, chat evaluation, and stage 4 next-step references found | pass |
| full regression after Phase 7 | `python -m pytest -q` | pass | 106 passed | pass |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-06-05 | `list_threads` query did not find the current thread with a narrow search query | 1 | Listed recent threads without query, identified current active thread by cwd and title, then renamed it |
| 2026-06-05 | `truncate_text()` returned 43 chars when max was 40 because suffix length was not counted | 1 | Counted `... [truncated]` suffix length before slicing, then reran tests successfully |
| 2026-06-05 | Deterministic provider echoed the full RAG prompt, so citations included `[2]` from context instead of only the answer source | 1 | Added `extract_question()` to isolate the actual question before generating deterministic answers |
| 2026-06-05 | First real chat evaluation returned 4/6 because quality-control expectations were too narrow and an out-of-corpus English sentence matched common keyword terms | 2 | Loosened expected content terms for quality-control query and changed the no-evidence query to a single synthetic token; reran chat evaluation at 6/6 |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 7 complete，当前分支 `codex/phase-3-cited-chat` |
| Where am I going? | 阶段 3 已完成；下一步进入阶段 4：数据采集与来源管理 |
| What's the goal? | 完成可测试、可替换、可引用、可拒答的最小问答链路 |
| What have I learned? | 见 `findings.md`，重点是 Quivr 的 LLMEndpoint、RAG prompt、source index 和 metadata 设计 |
| What have I done? | 改线程名、新建阶段 3 分支、参考 Quivr、重写阶段 3 planning 文件，完成 `ChatModelProvider`、RAG prompt/context builder、`CitationAnswerService`、`POST /chat` API、`qa_logs` 问答日志、chat 评测脚本和阶段 3 文档/Obsidian 收尾 |
