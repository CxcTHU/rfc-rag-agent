# Findings & Decisions

## Requirements
- 用户要求正式进入阶段 3 开发。
- 用户要求先修改当前线程名称，已完成，标题为 `阶段3-引用式问答`。
- 用户要求根据 `AGENT.MD` 和相关项目内容推进。
- 用户要求参考 Quivr 的架构，但不能机械复制。
- 用户要求使用 `planning-with-files` 撰写阶段 3 的流程规划。
- 用户强调规划要详细、可操作。

## Current Project Findings
- 当前分支已从 `main` 新建并切换到 `codex/phase-3-cited-chat`。
- 阶段 0、阶段 1、阶段 2 已完成；`main`、`origin/main` 和 `codex/phase-2-vector-search` 曾指向同一个 `phase-2-complete` 提交。
- 当前本地数据库状态：
  - `documents`: 136
  - `chunks`: 997
  - `chunk_embeddings`: 997
  - `source_type`: `local_file=10`、`open_access_pdf=10`、`institutional_access_pdf=1`、`metadata_record=115`
- 当前接口：
  - `GET /health`
  - `POST /documents/import`
  - `GET /documents`
  - `GET /documents/{document_id}/chunks`
  - `POST /search`
  - `POST /search/vector`
- 当前检索评测：
  - 关键词 baseline：15/15 通过。
  - 向量检索：11/15 通过。
  - 向量检索失败样例：`filling_capacity_en`、`mesoscopic_modeling`、`peridynamics`、`construction_management`。
- 当前全量测试：`python -m pytest -q` 为 63 passed。

## Quivr Research Findings
- Quivr 的 `Brain` 统一持有 storage、embedder、vector store、LLM 和 chat history。
- Quivr 的问答入口包括 `ask_streaming()`、`aask()`、`ask()`，最终返回 `ParsedRAGResponse`。
- Quivr 的 `LLMEndpoint` 封装模型供应商、模型名称、base URL、API key、上下文长度、输出长度和 function calling 能力。
- Quivr 默认 RAG workflow 是：
  - `START`
  - `filter_history`
  - `rewrite`
  - `retrieve`
  - `generate_rag`
  - `END`
- Quivr 的普通 RAG 实现 `QuivrQARAG` 把流程拆成：
  - 过滤聊天历史。
  - 生成 standalone question。
  - 从 vector store 检索 docs。
  - `combine_documents()` 格式化上下文并给每个 doc 加 index。
  - 使用 `RAG_ANSWER_PROMPT` 约束模型只基于 context 回答。
  - 使用 `parse_response()` 提取 answer、citations、followup_questions、sources。
- Quivr 的 `RAG_ANSWER_PROMPT` 重点规则：
  - 回答要使用 markdown。
  - 只使用提供的 context。
  - 如果无法基于 context 和引用来源回答，就说没有答案。
  - 如果 context 有冲突，要指出冲突。
- Quivr 的 `DEFAULT_DOCUMENT_PROMPT` 会给每个文档加入 `Source: {index}`，便于模型引用来源。
- Quivr 的 `cited_answer` 模型要求输出：
  - `answer`
  - `citations`
  - `followup_questions`
- Quivr 的 `RAGResponseMetadata` 包含：
  - `citations`
  - `followup_questions`
  - `sources`
  - `metadata_model`
  - `workflow_step`
  - `langchain_metadata`
- Quivr 测试中使用 fake LLM 和 deterministic fake embedding，说明本项目阶段 3 也应优先保证测试不依赖真实模型。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 阶段 3 新增 `app/services/generation/` | 阶段 1 是 ingestion，阶段 2 是 retrieval，阶段 3 需要 generation 层承接 prompt、模型调用和答案生成 |
| 定义 `ChatModelProvider` | 借鉴 Quivr `LLMEndpoint`，让问答业务不直接绑定某个国产模型或 OpenAI-compatible API |
| 先实现 deterministic chat provider | 自动化测试不能依赖真实 API key、网络和模型随机输出 |
| 预留 OpenAI-compatible provider | 用户当前主要使用国产模型 key，很多国产模型提供 OpenAI-compatible 接口 |
| 阶段 3 不引入 LangGraph | Quivr 的 LangGraph workflow 很强，但本项目现在先做单轮引用式问答，复杂 workflow 留到阶段 7 |
| 第一版不做聊天历史 | 阶段 3 最小目标是单轮“检索 -> 回答 -> 引用 -> 拒答”，多轮历史会增加复杂度 |
| 默认向量检索，必要时关键词回退 | 既复用阶段 2，又避免 deterministic 向量检索的 4 个失败样例导致问答链路不可用 |
| 引用编号采用 `[1] [2]` 文本格式 | 比 function calling 更通用，更适合不同国产模型；后续可升级为结构化输出 |
| 拒答判断放在 service 层 | 不能只靠 prompt 约束模型；工程层要在资料不足时主动阻止硬编 |
| `sources` 返回完整 chunk 元数据 | 回答引用必须能追溯到标题、来源路径、chunk_id 和 chunk_index |
| 阶段 3 新增 chat 评测集 | 问答质量不能只靠肉眼演示，需要固定问题集验证引用和拒答 |
| `ChatMessage` 只允许 `system/user/assistant` 三种 role | 对齐常见 chat completions 接口，避免后续 prompt 里混入未定义角色 |
| `OpenAICompatibleChatModelProvider` 使用标准库 `urllib` | 当前项目没有运行时 HTTP 客户端依赖，先避免额外依赖膨胀 |
| `ContextSource` 作为 prompt builder 的来源结构 | 把检索结果和给模型看的来源编号绑定起来，后续 citations 才能追溯 |
| Prompt 中同时包含英文规则和中文免责声明 | 模型接口通常能处理英文规则，中文免责声明贴近本项目用户和面试表达 |
| `CitationAnswerService` 返回结构化 dataclass | 比直接返回字符串更适合后续 API schema，能够同时携带 answer、citations、sources、refused 和模型信息 |
| `retrieval_mode` 支持 `auto/vector/keyword` | 第一版既能指定检索方式，也能在默认模式下自动从向量检索回退到关键词检索 |
| citations 在 service 层做白名单过滤 | 模型答案中的引用必须属于本次 prompt builder 生成的 sources，不能引用不存在的编号 |
| `POST /chat` 作为阶段 3 的外部问答入口 | 让前端或调用方不需要知道内部检索、prompt 和 provider 细节，只使用稳定 API |
| Chat schema 与 service result 分层 | `CitationAnswerResult` 是内部结构，`ChatResponse` 是对外协议，避免内部实现细节直接泄漏给 API 用户 |
| 空白问题在 `ChatRequest` 中校验为 422 | 输入格式问题属于请求校验错误，符合 FastAPI/Pydantic 的语义 |
| 本阶段落地 `qa_logs` 表 | 阶段 3 已有 `/chat`，问答结果需要可追踪，方便定位检索、引用、拒答和模型配置问题 |
| `qa_logs` 使用 JSON 字符串保存 id 列表 | 当前项目尚未引入复杂 JSON 列或迁移工具，用 Text 存储整数列表更轻量且易测试 |
| 不记录 `raw_response` | 原始模型响应可能包含敏感 provider trace，日志只保存 question、answer、source ids、citations 和模型元信息 |
| `scripts/evaluate_chat.py` 复用 `CitationAnswerService` | 评测真实问答链路，而不是绕过 service 直接测检索或 prompt |
| Chat 评测默认关闭 QA 日志 | 避免批量评测污染 `qa_logs`；需要时可通过 `--log-answers` 显式打开 |
| Chat 评测结果写入 CSV | 方便阶段收尾文档、Obsidian 和后续横向对比使用 |
| `AGENT.MD` 需要同步阶段 3 完成状态 | 新线程会优先读取 `AGENT.MD`，如果不更新会误判还需进入阶段 3 |
| Obsidian 知识点需要单独成文 | 阶段 3 新增 ChatModelProvider、RAG prompt、引用、拒答、Chat API、QA 日志和评测，都是后续面试可讲的独立点 |

## Planned File Changes
| Area | Planned Files |
|------|---------------|
| Chat model provider | `app/services/generation/chat_model.py`, `tests/test_chat_model_provider.py` |
| Prompt/context builder | `app/services/generation/prompt_builder.py`, `tests/test_prompt_builder.py` |
| Answer service | `app/services/generation/answer_service.py`, `tests/test_answer_service.py` |
| API/schema | `app/api/chat.py`, `app/schemas/chat.py`, `app/main.py`, `tests/test_chat_api.py` |
| Optional QA logging | `app/db/models.py`, `app/db/repositories.py`, `tests/test_chat_logging.py` |
| Evaluation | `data/evaluation/chat_queries.csv`, `scripts/evaluate_chat.py`, `data/evaluation/chat_results.csv`, `tests/test_evaluate_chat.py` |
| Documentation | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/stage3_learning_notes.md`, `AGENT.MD` if needed |
| Obsidian | `obsidian-vault/阶段/阶段 3 - 引用式问答.md`, related category pages and knowledge notes |

## Term Explanations
| Term | Explanation |
|------|-------------|
| `ChatModelProvider` | 聊天模型提供者，负责把 prompt 发给模型并拿回回答；类似阶段 2 的 `EmbeddingProvider` |
| `OpenAI-compatible API` | 兼容 OpenAI 请求格式的模型接口，很多国产模型也支持这种格式 |
| `prompt` | 给模型的指令和上下文组合；阶段 3 用它要求模型只基于资料回答 |
| `context` | 本次回答允许使用的资料片段集合，来自关键词或向量检索结果 |
| `citation` | 引用编号，表示答案中的某句话依据哪个资料片段 |
| `source` | 来源信息，包括文档标题、来源路径、chunk 编号和片段内容 |
| `refusal` | 拒答机制，资料不足时明确告诉用户“当前资料库没有足够依据” |
| `function calling` | 让模型按工具或结构化函数参数输出；Quivr 用它提取 `cited_answer`，本项目第一版先不依赖 |
| `metadata` | 回答正文之外的结构化信息，例如 citations、sources、model_name、refused |
| `workflow` | 多步骤流程编排；Quivr 用 LangGraph 表示，阶段 3 暂时用普通 service 串联 |
| `standalone question` | 脱离聊天历史也能理解的问题；Quivr 会改写问题，本项目第一版先不做 |
| `QA log` | 问答日志，记录问题、答案、召回片段和模型信息，方便后续排查 |
| `role` | 聊天消息角色，例如 system 表示系统规则，user 表示用户问题，assistant 表示模型回复 |
| `temperature` | 控制模型回答随机性的参数；阶段 3 默认较低，让回答更稳定 |
| `timeout` | 模型请求最长等待时间，避免外部 API 卡住整个服务 |
| `ContextSource` | 给模型看的上下文来源条目，包含 source_id、文档标题、chunk_id、片段内容和 score |
| `RagPrompt` | prompt builder 的输出，包含 messages、context_text 和 sources |
| 上下文截断 | 控制每个 chunk 和总上下文长度，避免 prompt 太长 |
| `CitationAnswerService` | 阶段 3 的问答编排服务，把检索、上下文组织、模型调用、引用提取和拒答串起来 |
| `retrieval_mode` | 检索模式，当前支持 `auto`、`vector`、`keyword`；`auto` 会先尝试向量检索，再关键词回退 |
| `min_score` | 最低相关性阈值，低于阈值的检索结果会被过滤，过滤后无结果则拒答 |
| `refused` | 问答结果里的布尔字段，表示本次是否因为资料不足而拒答 |
| `used_retrieval_mode` | 实际使用的检索模式，例如自动模式下最终可能是 `vector`、`keyword` 或 `none` |
| `ChatRequest` | `/chat` 的请求结构，包含 question、top_k、retrieval_mode 和 min_score |
| `ChatResponse` | `/chat` 的响应结构，包含 answer、citations、sources、refused 和模型信息 |
| `ChatSourceItem` | `/chat` 返回的单个来源结构，描述一个可追溯的 chunk 来源 |
| 依赖注入 | FastAPI 的 `Depends(...)` 机制，本项目用它把数据库、聊天模型 provider 和 embedding provider 交给路由函数 |
| 422 | 请求体验证错误，通常由 Pydantic schema 校验触发，例如空白 question 或非法 retrieval_mode |
| `qa_logs` | 问答日志表，记录每次问答的问题、答案、引用、召回 chunk、检索模式、模型信息和拒答状态 |
| `QuestionAnswerLog` | SQLAlchemy 模型，对应数据库中的 `qa_logs` 表 |
| `QuestionAnswerLogRepository` | 保存和读取问答日志的 repository，避免 service 直接拼数据库操作 |
| 可观测性 | 系统能被排查和复盘的能力；本阶段体现为保存 QA 日志，后续可用于评测和问题定位 |
| `raw_response` | 模型供应商返回的原始响应，可能含 trace 或敏感字段，本项目日志不保存它 |
| `chat_queries.csv` | 阶段 3 chat 评测问题集，定义问题、期望是否拒答、是否要求 sources/citations 和来源期望词 |
| `chat_results.csv` | chat 评测输出结果，记录每个问题是否通过、答案、sources 数量、citations 校验和模型信息 |
| `ExpectedChatQuery` | `evaluate_chat.py` 中的评测输入结构，对应 `chat_queries.csv` 的一行 |
| `EvaluatedChatResult` | `evaluate_chat.py` 中的评测输出结构，对应 `chat_results.csv` 的一行 |
| `citations_valid` | 评测指标，表示答案中的引用编号是否都能映射到本次返回的 sources |
| 阶段收尾 | 每个大阶段结束时同步 README、progress、architecture、AGENT 和 Obsidian，保证代码状态和文档入口一致 |
| Obsidian 双链 | Obsidian 的内部链接形式，例如 `[[阶段 3 - 引用式问答]]`，用于把阶段、分类和知识点互相连接 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| 当前 planning 文件还是阶段 2 记忆 | 已按 `planning-with-files` 重写为阶段 3 规划 |
| Quivr RAG 架构较复杂，直接照搬会过重 | 只借鉴 LLMEndpoint、prompt、source 编号和 response metadata，不引入 LangGraph |
| deterministic provider 初版回显完整 RAG prompt，误把上下文里的 `[2]` 当作答案引用 | 改为只提取用户问题本体，避免测试答案被 prompt 上下文污染 |

## Implementation Findings
- Phase 1 已新增 `app/services/generation/chat_model.py`，形成 generation 层入口。
- `DeterministicChatModelProvider` 可以在没有 API key 的情况下返回稳定答案，适合后续 AnswerService 和 Chat API 测试。
- `OpenAICompatibleChatModelProvider` 已具备最小真实调用边界：向 `{base_url}/chat/completions` 发送 `model/messages/temperature`。
- 当前不在测试中真实调用外部模型，只验证配置边界和 OpenAI-compatible 响应解析。
- `.env.example` 已补充 `CHAT_MODEL_TEMPERATURE` 和 `CHAT_MODEL_TIMEOUT_SECONDS`。
- Phase 2 已新增 `app/services/generation/prompt_builder.py`，可以把关键词或向量检索结果转成带 `[1]`、`[2]` 编号的 RAG prompt。
- Prompt builder 会保留每个来源的标题、来源类型、路径、文件名、chunk_id、chunk_index、heading_path、score 和内容。
- Prompt builder 会在 system prompt 中明确“不替代规范审查、工程设计和专家判断”。
- Phase 3 已新增 `app/services/generation/answer_service.py`，形成最小问答链路：检索 chunks -> 构造 RAG prompt -> 调用 ChatModelProvider -> 提取 citations -> 返回结构化结果。
- `CitationAnswerService.answer()` 会校验 `question`、`top_k`、`retrieval_mode` 和 `min_score`，避免无效输入进入检索和模型调用。
- `retrieval_mode="auto"` 会先调用 `VectorSearchService`，如果没有可用结果，再调用 `KeywordSearchService` 回退。
- 资料不足时返回统一拒答文案：`当前资料库中没有找到足够可靠的依据。`
- `extract_citations()` 只保留本次 sources 允许的编号，并去重保序；模型输出不存在的 `[99]` 会被过滤掉。
- `DeterministicChatModelProvider` 已新增问题提取逻辑，避免把完整上下文里的来源编号误带进答案。
- Phase 4 已新增 `app/schemas/chat.py` 和 `app/api/chat.py`，对外提供 `POST /chat`。
- `ChatRequest` 会把 question 去掉首尾空白，并在空白问题时返回 422。
- `/chat` 会通过依赖注入拿到数据库、`ChatModelProvider` 和 `EmbeddingProvider`，然后调用 `CitationAnswerService`。
- `ChatResponse` 会返回 answer、citations、sources、refused、refusal_reason、retrieval_mode、model_provider 和 model_name。
- `tests/test_chat_api.py` 覆盖了正常问答、auto 模式关键词回退、资料不足拒答、空白问题 422 和非法 retrieval_mode 422。
- Phase 5 已新增 `QuestionAnswerLog` 模型，对应 `qa_logs` 表。
- `QuestionAnswerLogRepository` 可以保存、查询和统计问答日志，并用 JSON 字符串保存 retrieved_chunk_ids 和 citations。
- `CitationAnswerService` 默认会在成功问答和拒答后写入一条 QA 日志。
- QA 日志记录 question、answer、retrieved_chunk_ids、citations、model_provider、model_name、retrieval_mode、refused、refusal_reason 和 created_at。
- QA 日志不保存 `ChatModelResult.raw_response`，测试已覆盖包含 `secret-api-key` 的 raw_response 不会进入日志字段。
- Phase 6 已新增 `scripts/evaluate_chat.py`、`data/evaluation/chat_queries.csv` 和 `data/evaluation/chat_results.csv`。
- Chat 评测覆盖 6 类问题：概念、施工/质量控制、温控、填充能力、工程案例和无依据问题。
- Chat 评测当前使用 deterministic chat provider 和 keyword retrieval，重点验证完整问答链路、sources、citations、拒答和明显硬编词检查。
- 当前真实数据库评测结果：chat 6/6 passed；关键词 15/15 passed；向量 11/15 passed。
- 调整无依据评测问题时发现，英文常见词问题容易被关键词检索误召回，因此第一版用合成单词稳定验证拒答机制。
- Phase 7 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md` 和 `AGENT.MD`。
- Phase 7 已更新 Obsidian 首页、阶段索引、阶段 3 页面、5 个分类页和 7 个知识点页面。
- 阶段 3 的文档收尾结论是：阶段 3 已完成，下一阶段应进入阶段 4 数据采集与来源管理。

## Resources
- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `task_plan.md`
- `progress.md`
- `G:\Codex\program\quivr\core\quivr_core\brain\brain.py`
- `G:\Codex\program\quivr\core\quivr_core\brain\brain_defaults.py`
- `G:\Codex\program\quivr\core\quivr_core\llm\llm_endpoint.py`
- `G:\Codex\program\quivr\core\quivr_core\rag\quivr_rag.py`
- `G:\Codex\program\quivr\core\quivr_core\rag\quivr_rag_langgraph.py`
- `G:\Codex\program\quivr\core\quivr_core\rag\prompts.py`
- `G:\Codex\program\quivr\core\quivr_core\rag\utils.py`
- `G:\Codex\program\quivr\core\quivr_core\rag\entities\models.py`
- `G:\Codex\program\quivr\core\quivr_core\rag\entities\config.py`
- `G:\Codex\program\quivr\core\tests\test_quivr_rag.py`
- `G:\Codex\program\quivr\core\tests\test_llm_endpoint.py`
- `G:\Codex\program\quivr\core\tests\conftest.py`

## Visual/Browser Findings
- 未使用浏览器或视觉检查。
