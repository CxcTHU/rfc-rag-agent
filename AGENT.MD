# 堆石混凝土问答 Agent 项目指南

## 每个新线程必须先读

以后任何关于本项目的新对话，先阅读本文件，再回答问题或改代码。

新线程启动时按顺序做：

1. 阅读 `G:\Codex\program\rfc-rag-agent\AGENT.MD`。
2. 如果项目目录已经创建，继续阅读项目内的 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
3. 检查当前目录结构和 Git 状态，确认用户已有改动，不要覆盖用户工作。
4. 根据本文件里的路线，判断当前处于哪个阶段，再继续推进。

本文件的作用不是一次性定死所有细节，而是给“从零搭建堆石混凝土问答 Agent”提供稳定方向。

## 协作与教学原则

本项目是用户的第一个完整工程项目。后续开发不能只“把代码写出来”，还要让用户真正理解项目为什么这样设计、代码怎样运行、面试时怎样讲清楚。

默认协作方式：

- 每推进一个功能，都先说明本步骤解决的业务问题、在 RAG 链路中的位置，以及为什么现在做它。
- 解释关键代码时，用清晰中文讲清楚输入、处理过程、输出和边界条件。
- 任何新名词第一次出现时，都要立刻用初学者能理解的方式解释，并结合本项目举例。不要假设用户已经知道 REST、HTTP、CI、ORM、向量库、embedding、chunk、schema、依赖注入等概念。
- 遇到专业概念时，必须结合本项目解释。例如用“堆石混凝土资料片段”解释 chunk，用“问题和资料的语义距离”解释 embedding。
- 如果连续出现多个新名词，先逐个短解释，再继续讲主线，避免概念堆叠。
- 新词解释优先采用“是什么 -> 在本项目哪里出现 -> 有什么作用 -> 面试怎么说”的顺序。
- 每次回复前必须做一次“新词自检”：如果本轮回答、代码、文件名、类名、数据库表、脚本或第三方库中出现了用户可能不熟悉的新词，必须补充“新词解释”小节或在正文中立即解释。
- 如果本轮新增 2 个及以上技术名词，最终回复必须包含“新词解释”小节；不能只说代码改了什么。
- 每个开发任务验收时必须明确说明：本步骤新增了哪些概念、是否已经解释、是否需要沉淀到 Obsidian。
- 不把复杂概念一次性堆给用户。优先按“能跑通 -> 能理解 -> 能优化 -> 能面试表达”的顺序推进。
- 每个阶段完成后，给出一段面试表达：这个阶段做了什么、为什么这么设计、可能被追问什么。
- 重要技术选择要说明取舍。例如为什么第一阶段用 SQLite 而不是 PostgreSQL，为什么先做关键词检索再做向量检索。
- 对高频面试点保持敏感，包括 FastAPI 分层、Pydantic 校验、数据库建模、文本切分、向量检索、召回与重排、引用溯源、拒答机制、评测指标和工程化部署。
- 如果发现当前实现只是 demo，要明确指出离真实工程还差什么，并给出下一步最小改进。

面试官视角的讲解模板：

```text
本步骤目标：
新词解释：
核心原理：
在本项目中的实现：
为什么不采用更复杂方案：
常见面试追问：
用户应该能说出的回答：
```

后续回答用户时，默认带有互联网大厂面试官视角：不仅关注功能是否可用，也关注模块边界、可维护性、可测试性、数据可信度、异常处理和可解释性。

## 阶段开发与线程策略

后续开发采用“一个大阶段一个主线程，一个大阶段一个分支”的方式推进。

建议阶段分支命名：

```text
codex/phase-0-health-api
codex/phase-1-document-ingestion
codex/phase-2-vector-search
codex/phase-3-cited-chat
codex/phase-4-source-management
codex/phase-5-frontend
codex/phase-6-evaluation
codex/phase-7-agent-tools
codex/phase-8-brain-workflow
codex/phase-9-real-model-evaluation
codex/phase-10-rag-quality-calibration
codex/phase-11-user-evaluation-query-expansion
codex/phase-12-quality-review-context-calibration
codex/phase-13-decompose-evidence-merge
codex/phase-14-real-quality-calibration
codex/phase-15-real-review-report
codex/phase-16-real-quality-risk-closure
codex/phase-17-retrieval-architecture-upgrade
claude/phase-18-corpus-evaluation-quality
claude/phase-19-chinese-analysis-retrieval-tuning
codex/phase-20-default-chain-and-eval-upgrade
claude/phase-21-langgraph-agentic-rag
codex/phase-22-frontend-agentic-observability
codex/phase-23-agentic-eval-and-auto-routing
```

协作规则：

- 同一阶段内尽量保持同一个线程，保证上下文连续。
- 进入下一个大阶段时，新开线程，先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md` 和 `docs/data_sources.md`。
- 阶段结束记录必须包含：完成内容、验证方式、遗留问题、下一阶段任务、面试表达、阶段提交号和阶段 tag。

阶段完成收尾清单：

每个阶段完成、合并或准备切换到下一阶段前，agent 必须主动完成以下文档同步；不要等用户指出文档债以后才补。这里的“主动”表示：阶段收尾时自动检查、自动更新、自动在最终回复中汇报结果。

- 自动更新 `README.md`：面向新读者，说明当前阶段、已实现功能、启动方式、测试方式和下一阶段。
- 自动更新 `docs/progress.md`：作为最权威进度记录，写清完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- 自动判断并更新 `docs/architecture.md`：如果阶段改变了模块边界、数据流、数据库表、API、检索链路或部署结构，必须同步更新；如果不需要改，也要说明原因。
- 自动判断并更新 `AGENT.MD`：如果阶段经验改变了后续 agent 的工作规则、阶段路线、教学要求、避坑规则或推荐下一步，必须同步更新；如果不需要改，也要说明原因。
- 自动更新 Obsidian 知识库：阶段页、阶段索引、首页、分类页和重要知识点笔记要与实际进度一致。
- 阶段完成并通过验证后，必须在阶段最终提交上创建阶段 tag，命名格式为 `phase-X-complete`，例如 `phase-3-complete`。tag 必须指向该阶段的最终功能提交；如果之后只是补充流程规则或文档修正，不要把阶段 tag 移到这些后续提交上。最终回复必须说明提交号和 tag 名称；如果暂时不能创建 tag，必须说明原因和补救动作。
- 必须落盘阶段验收报告：每个阶段通过验收时，验收方（在 Claude + Codex 闭环中通常是规划/验收方 Claude）必须把验收报告写入 `docs/phase_reviews/phase-X.md`，内容至少包含：验收结论（PASS 或整改清单）、逐项核对证据（范围对齐、测试、评测指标、安全合规、文档同步、提交边界）、以及带入后续阶段的遗留观察。验收报告是闭环的固定产物，每个阶段都不得省略；验收方必须直接核对工作区（读 diff、独立重跑测试、复现评测、扫描敏感信息），不能仅凭开发方的口头汇报判定通过。

阶段收尾回复必须明确说明这些检查结果，避免代码已进入新阶段而入口文档仍停留在旧阶段，也避免阶段已经提交但没有可追踪的版本标签。

## Claude + Codex 双 Agent 协作规则

本项目由 Claude Code 和 Codex **两个 AI Agent 轮流开发**，采用**时间分片**：同一时刻只有一个 Agent 在本工作目录干活，两个 Agent 不并行写同一个目录。阶段 0 到 16 由 Codex 完成，后续 Claude 与 Codex 交替推进。

### 入口文件与真相源

- `AGENT.MD` 是**唯一规则真相源**。
- `CLAUDE.md`（Claude Code 默认入口）、`AGENTS.md` 与 `AGENT.md`（Codex 默认入口）都只是**转发文件**，只写「先读 AGENT.MD」，不复制规则，避免多份规则不同步。
- 修改协作规则、阶段路线、教学要求时，只改 `AGENT.MD`，不要把规则正文写进转发文件。

### 交接协议（时间分片核心）

- **开工前**：先读 `AGENT.MD`、`README.md`、`docs/progress.md`，再运行 `git status -sb`、`git log --oneline -5`，确认上一个 Agent 留下的分支、未提交改动和当前阶段，绝不覆盖对方未提交的工作。
- **交班前**：把工作区留在可理解状态。要么是干净的（无零散半成品），要么在 `docs/progress.md` 或根目录 `progress.md` 写清「当前未提交的改动是什么、下一步该做什么」，方便另一个 Agent 接手。
- **根目录 `task_plan.md` / `findings.md` / `progress.md`** 是当前活跃阶段的工作记忆，由正在干活的 Agent 维护，交接时必须更新到最新。
- **`docs/progress.md`** 是最权威进度记录；**`AGENT.MD`** 是共享大脑。两者只在阶段收尾或明确节点更新，避免两个 Agent 反复抢改造成冲突。
- **阶段任务书 / goal prompt 模板**：规划方（在 Claude + Codex 闭环中通常是 Claude）为每个新阶段编写「阶段开发任务书」（即 Codex 新对话要设置的 goal）时，以本地模板 `obsidian-vault/模板/goal prompt.md` 为基准；同目录下还有配套的 `开启 prompt.md`、`提交 prompt.md`、`Phase 汇报模板.md`、`知识点模板.md`。注意 `obsidian-vault/` 是本地 only、已 `.gitignore`，这些模板不随仓库分发，仅供本机 Claude / Codex 取用；任务书生成的 goal prompt 正文不超过 4000 字符。

### 分支与提交边界

- 分支用工具名做命名空间区分负责人：Codex 用 `codex/...`，Claude 用 `claude/...`。一个阶段只交给一个 Agent，不让两个 Agent 同时改同一阶段分支。
- 提交边界对两个 Agent 同样适用：**未经用户人工核验并明确确认，不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR**。
- `.claude/`、`.codex/` 是本地工具配置，已加入 `.gitignore`，不提交。

### 阶段 23 之后的前端 Agentic 与自动路由规则

- 默认 `/chat` 仍不走 agentic；阶段 23 的自动路由只作用于 `/agent/query`。
- `/agent/query` 的 `mode` 为空时，先调用 `classify_query_complexity()`：`simple` 走 default `AgentService`，`complex` 走 agentic LangGraph。
- 显式 `mode="default"` 或 `mode="agentic"` 必须继续尊重，用作调试和人工核验能力。
- 不得修改 `detect_intent` 内部规则来实现阶段 23 自动路由；`detect_intent` 仍只在 default `AgentService` 内部判断 answer/search/list_sources/get_source_detail。
- 前端 Agent 面板不再让用户手动选择 default / agentic；使用只读状态指示器展示响应里的实际 `mode`。
- 前端继续使用原生 HTML/CSS/JS；阶段 22/23 已明确不引入 Node 构建链或前端框架，后续若要引入必须先单独论证收益与维护成本。
- `workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category` 属于只读可观测字段，用来解释 agentic RAG 的运行过程，不得被扩展成写入型 Agent 工具或外部副作用入口。
- 浏览器验证要覆盖 desktop 与移动断点，至少检查 Agent 只读模式指示器、步骤列表、横向溢出和 console error；真实 API 不能成为本地全量测试前提。
- 阶段 23 的 deterministic 评测只支持“复杂问题可自动尝试 agentic”的有限结论；不得把它表述为 agentic 全面优于 default。

### 阶段 24 之后的多轮会话与持久化规则

- 阶段 24 将多轮对话限定在 `/agent/query` + `conversation_id`；默认 `/chat` 仍保持单次引用式问答接口，不自动写入 Conversation/Message。
- `conversation_id` 是兼容开关：不传时保持阶段 23 行为；传入时必须校验会话存在、加载服务端 history、成功响应后保存 user/assistant 消息。
- 会话历史属于短期 conversation 上下文，不是跨会话长期记忆。不得把 summary 或 Message 表扩展成全局用户记忆，除非后续阶段单独设计权限、删除、隐私和评测边界。
- 长对话压缩使用 `role="summary"` 的 Message 表示；summary 只用于控制 prompt 长度，不能替代来源引用，也不能绕过 RAG 的 evidence confidence / responsibility_gate / citation 约束。
- agentic 路径只在 generate 节点利用 history 补全追问；retrieve、grade、rewrite 仍以当前问题为主，避免把会话短期上下文误当作资料库事实。
- 前端继续使用原生 HTML/CSS/JS。阶段 24 已明确不引入 React/Vue、Node 构建链、WebSocket/SSE 或 LangGraph Checkpointer；后续若要引入必须先写设计文档和回归计划。
- `Message.metadata_json` 只保存展示恢复所需的结构化元数据，例如 citations、workflow_steps、invalid_citations、refusal_category、mode、iteration_count；不得保存 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文。
- 会话 API 当前无登录和用户隔离，这是阶段 24 明确边界。后续如果做认证，必须给 Conversation 增加 owner/user 维度，并补列表过滤、删除权限和安全测试。
- 浏览器验证要覆盖 desktop 与移动断点，至少检查会话列表、聊天气泡、刷新恢复、横向溢出和 console error；真实 API 不能成为本地全量测试前提。

## Obsidian 知识库规则

本项目必须维护一个 Obsidian 知识库，用来沉淀每个阶段的工程知识、面试知识和项目决策。

知识库目录：

```text
obsidian-vault/
```

维护原则：

- 每个阶段结束时，必须自动更新 Obsidian 知识库，不需要用户单独提醒。
- 必须同步 `obsidian-vault/首页.md`，让“当前重点 / 已完成 / 下一阶段”与真实阶段一致。
- 必须同步 `obsidian-vault/阶段索引.md`，把已完成阶段、下一阶段和计划中阶段放在正确分组。
- 必须同步当前阶段页，例如 `obsidian-vault/阶段/阶段 1 - 本地资料导入与关键词检索.md`，包括 front matter 里的 `status`、阶段目标、完成内容、验证结果、知识点链接、面试表达、上一阶段和下一阶段。
- 必须维护 `obsidian-vault/阶段汇报/` 分支：
  - 每个大阶段建立一个目录，例如 `obsidian-vault/阶段汇报/阶段 5 - 前端界面/`。
  - 每个小 Phase 单独一篇笔记，标题格式建议为 `Phase N - 小阶段名称`。
  - 每篇小 Phase 笔记必须固定记录以下 10 项，不得省略、合并或只在大阶段最终收尾时统一补写：
    1. 本 Phase 目标
    2. 本 Phase 完成的主要任务
    3. 新增/修改了哪些内容
    4. 关键代码或模块说明
    5. 遇到的问题与解决方式
    6. 新词解释
    7. 验证结果
    8. 当前遗留问题
    9. 下一 Phase 要做什么
    10. 面试表达
  - `obsidian-vault/阶段汇报索引.md` 必须链接所有已记录的大阶段 Phase 汇报索引。
  - 每个大阶段页必须反向链接本阶段的 Phase 汇报索引，方便从阶段页进入小 Phase 复盘。
  - 如果是事后回填小 Phase 汇报，必须在对应索引中说明内容依据，例如来自 `docs/progress.md`、阶段页、测试结果或提交记录。
  - `obsidian-vault/` 是本地知识库，只做本地维护和复盘，不得提交到 Git，也不得上传到 GitHub。阶段收尾回复可以说明已更新本地知识库，但提交范围必须排除所有 Obsidian 文件。
- 每个重要知识点都要单独成文，不要只写在阶段总结里。
- 每个知识点必须标明：所属阶段、对应代码或文档位置、解决的问题、在项目中的作用、面试追问。
- 每个知识点必须使用 Obsidian 双链连接到阶段页和分类页，例如 `[[阶段 0 - FastAPI 工程底座]]`、`[[后端工程]]`。
- 阶段页要反向列出本阶段新增的知识点，方便复习。
- 分类页要按主题收集知识点，例如后端工程、API 设计、配置管理、测试与验证、RAG 链路、数据工程、评测体系。
- 如果某个知识点跨阶段复用，不要复制多份；更新原知识点，并在新阶段页中链接它。
- 知识点表达要面向“以后面试能讲清楚”，避免只记录命令或流水账。
- 如果阶段中出现新名词，要优先判断是否需要新增知识点笔记；至少要在相关知识点中解释它第一次出现时的含义和项目例子。

推荐知识点模板：

```text
---
stage:
category:
location:
purpose:
---

# 知识点标题

所属阶段：[[阶段 X - 阶段名称]]
所属分类：[[分类名称]]
相关位置：代码文件或文档路径

## 它解决什么问题

## 在本项目中怎么用

## 新词解释

## 为什么这样设计

## 面试可能怎么问

## 你应该怎么回答

## 相关双链
```

## 参考项目：Quivr

本项目整体工程框架参考本地 Quivr 项目：

```text
G:\Codex\program\quivr
```

Quivr 是一个成熟的 RAG core 项目，定位是把文件导入、解析、切分、向量化、检索、问答、引用来源、工作流配置等能力封装成可复用的“第二大脑”核心库。本项目不是复制 Quivr 代码，而是学习它的 RAG 工程拆分思路，并结合“水利工程堆石混凝土技术”这个垂直领域重新实现。

新线程如果涉及架构设计、文档导入、检索、问答、工具调用或评测，应优先参考 Quivr 的相关模块，再判断本项目是否需要采用、简化或调整。

### 从 Quivr 学到的核心框架

Quivr 的关键结构：

```text
Brain
  统一封装文件、storage、processor、vector store、embedder、LLM、chat history 和 RAG 问答

storage
  管理原始文件来源，例如本地文件、透明存储等

processor
  根据文件类型选择解析器，把 PDF/TXT/Markdown 等文件处理成 Document/chunk

splitter
  控制 chunk_size 和 chunk_overlap

vector store
  保存向量索引，默认可用 FAISS，也可以替换其他向量库

LLMEndpoint
  封装不同模型供应商和模型参数

RetrievalConfig / IngestionConfig / WorkflowConfig
  用配置控制导入、检索、rerank、历史过滤、问题重写、生成回答等流程

RAG pipeline
  典型流程是 filter_history -> rewrite -> retrieve -> generate_rag

response metadata
  回答不仅有 answer，还包含 citations、sources、followup_questions 等元数据
```

这些名词在本项目中的对应理解：

```text
Brain
  Quivr 中的知识库/中控对象。本项目阶段 8 已正式命名为 Brain，用来统一编排 RAG workflow，但不照搬 Quivr 代码。

storage
  原始资料存储。本项目会对应 data/raw、documents 表、source registry。

processor
  文件解析器。本项目会对应 ingestion/parser、cleaner、splitter。

splitter
  文本切分器。本项目会把堆石混凝土资料切成可检索、可引用的 chunk。

vector store
  向量库。本项目阶段 2 再接入 FAISS/Chroma 等。

LLMEndpoint
  模型调用封装。本项目会对应 ChatModelProvider 和 EmbeddingProvider，优先支持国产 OpenAI-compatible API。

workflow
  可配置流程。本项目早期先写清晰 service，等 RAG 稳定后再考虑复杂 workflow 或 Agent 工具编排。
```

### 本项目如何参考 Quivr

参考方向：

- 学习 Quivr 的“导入 -> 解析 -> 切分 -> 向量化 -> 检索 -> 生成回答 -> 返回来源”主链路。
- 学习 Quivr 把 storage、processor、vector store、LLM endpoint 分开的模块边界。
- 学习 Quivr 通过配置对象控制 ingestion 和 retrieval，而不是把参数散落在业务代码中。
- 学习 Quivr 对多文件格式的 processor registry 思路，后续支持 Markdown/TXT/PDF/HTML 时可以借鉴。
- 学习 Quivr 的 response metadata 思路，让回答天然携带 citations、sources、followup_questions 等结构。
- 学习 Quivr 的 examples 和 tests 组织方式：核心能力要有最小示例和自动化测试。
- 学习 Quivr 的工具扩展方向，例如 web search、tools、workflow，但本项目要等 RAG 稳定后再做 Agent 化。

本项目不直接照搬：

- 不直接复制 Quivr 代码。
- 不一开始引入 LangGraph、复杂 workflow 或多工具调用。
- 不默认绑定 OpenAI；本项目要优先支持国产大模型和 OpenAI-compatible API。
- 不做通用 second brain，而是聚焦堆石混凝土和水利工程资料。
- 不只依赖向量库保存内容；本项目必须同时保存 SQLite 元数据，方便引用溯源、质量检查和错误排查。

### 当前对齐情况

阶段 0 到阶段 11 当前已逐步对齐 Quivr 的工程思想：

- 有清晰入口：`app/main.py`。
- 有 API 分层：`app/api/health.py`、`app/api/documents.py`、`app/api/search.py`、`app/api/chat.py`、`app/api/sources.py`、`app/api/agent.py`。
- 有 schema 分层：`app/schemas/health.py`、`app/schemas/document.py`、`app/schemas/search.py`、`app/schemas/chat.py`、`app/schemas/source.py`、`app/schemas/agent.py`。
- 有集中配置：`app/core/config.py`。
- 有导入、检索、生成和评测 service 分层。
- 有 `EmbeddingProvider` 和 `ChatModelProvider` 两类 provider 抽象。
- 有 response metadata：`citations`、`sources`、`refused`、`model_provider`、`model_name`。
- 有 source registry：`sources` 表、`SourceRegistryService`、来源同步脚本、sources API 和 reindex 入口。
- 有受控 Agent 工具层：`AgentToolbox`、`AgentService`、`POST /agent/query`、`tool_calls` 和 `reasoning_summary`。
- 有 Brain 中控层：`app/services/brain/`、`RetrievalConfig`、`WorkflowConfig`、`BrainService` 和可记录的 workflow steps。
- 有真实模型接入边界：`OpenAICompatibleChatModelProvider`、`OpenAICompatibleEmbeddingProvider`、模型配置评测和 provider/model/dimension 可追踪索引。
- 有真实用户问题评测集和跨语言质量增强：`data/evaluation/user_questions.csv`、`scripts/evaluate_user_questions.py`、`docs/stage11_user_evaluation_plan.md`、跨语言 `SYNONYM_RULES` 和人工审阅抽样表。
- 有质量审阅和上下文最小补全：`data/evaluation/stage12_quality_review_results.csv`、`docs/stage12_quality_review.md`、Brain `rewrite_query`、可选 `history` 字段和 `docs/stage13_decompose_plan.md`。
- 有自动化测试和评测脚本。
- 有文档和知识库沉淀：`README.md`、`docs/progress.md`、`obsidian-vault/`。

阶段 4 已实现来源治理层。后续阶段按以下方式继续对齐：

```text
阶段 1
  对齐 Quivr storage / processor / splitter 的思想
  实现本地 Markdown/TXT 导入、清洗、chunk 切分、SQLite 元数据保存和关键词检索

阶段 2
  对齐 Quivr vector store / embedder 的思想
  接入 embedding provider 和向量检索

阶段 3
  已对齐 Quivr RAG pipeline / LLMEndpoint / response metadata 的思想
  已实现引用式问答、来源返回和拒答机制

阶段 4
  已对齐 Quivr storage 扩展和 source 管理思想
  已建立 source registry、来源去重、可信度、全文权限、状态、同步脚本、sources API 和 reindex 入口

阶段 6
  借鉴 Quivr 的测试组织，补充检索与问答评测集

阶段 7
  已借鉴 Quivr workflow/tools 思路，但采用更轻量的只读工具封装和规则式编排
  已实现 search_knowledge、hybrid_search_knowledge、answer_with_citations、list_sources、get_source_detail

阶段 8
  已借鉴 Quivr Brain / RetrievalConfig / WorkflowConfig 思路，但采用普通 Python service
  已实现 BrainService、RetrievalConfig、WorkflowConfig、filter_history、rewrite_query、retrieve、optional_rerank、generate_answer

阶段 9
  已补齐真实模型接入与模型评测
  已实现 OpenAICompatibleEmbeddingProvider、真实 embedding 配置、provider/model/dimension 可追踪索引和 model_config_results 评测汇总
```

### 使用 Quivr 作为参考时的规则

- 先理解 Quivr 的设计意图，再决定本项目是否需要采用。
- 优先学习模块边界、数据流、配置方式和测试思路，不机械复制代码。
- 每次借鉴 Quivr 的设计，都要说明本项目为什么采用、为什么简化、为什么调整。
- 如果 Quivr 的实现与本项目垂直领域目标冲突，以本项目目标为准。
- 如果新增架构明显参考 Quivr，必须在 `docs/architecture.md` 或 Obsidian 对应知识点中记录。
- 面试表达时可以说“参考成熟 RAG 项目的工程拆分思路”，但要能讲清楚本项目自己的领域改造：国产模型、堆石混凝土资料、引用溯源、拒答机制和评测体系。

## 项目定位

暂定项目名：

```text
RFC-RAG-Agent
```

## GitHub 仓库信息

本项目已经连接到 GitHub。

```text
GitHub 仓库: https://github.com/CxcTHU/rfc-rag-agent
仓库名: CxcTHU/rfc-rag-agent
可见性: private
默认分支: main
本地路径: G:\Codex\program\rfc-rag-agent
远程名称: origin
远程地址: https://github.com/CxcTHU/rfc-rag-agent.git
```

新线程如果需要确认连接状态，进入项目目录后检查：

```powershell
git status -sb
git remote -v
```

正常状态应显示：

```text
main...origin/main
origin https://github.com/CxcTHU/rfc-rag-agent.git
```

以后新增功能时，优先从 `main` 新建功能分支，例如：

```text
feature/health-api
feature/document-ingestion
feature/vector-search
feature/cited-chat
```

如果用户需要同时推进多个功能，可以把新分支派生到新的 Git worktree。新的 worktree 应放在项目目录外，例如：

```text
G:\Codex\program\rfc-rag-agent-health
G:\Codex\program\rfc-rag-agent-ingestion
```

不要把 worktree 创建在 `G:\Codex\program\rfc-rag-agent` 内部，避免目录嵌套混乱。

中文定位：

```text
面向水利工程堆石混凝土技术的文献检索与引用式问答 Agent
```

英文关键词：

```text
Rock-filled Concrete
RFC
Self-compacting Concrete
Dam Engineering
Hydraulic Engineering
Retrieval-Augmented Generation
RAG Agent
```

项目目标：

```text
从零搭建一个垂直领域 RAG 问答系统。
系统能够采集、清洗、管理堆石混凝土相关资料，
建立检索索引，
根据用户问题召回可靠资料片段，
再调用大模型生成带引用来源的回答。
```

这个项目不是单纯的“PDF 聊天机器人”，而是一个可逐步扩展的水利工程知识库系统。后续可以从堆石混凝土扩展到混凝土坝、碾压混凝土、面板堆石坝、大体积混凝土温控、水工施工规范等方向。

## 为什么选堆石混凝土

不要一开始做“全水利知识库”。水利知识范围太大，容易变成资料堆砌：

```text
水文学
水力学
水工结构
岩土工程
施工组织
材料性能
大坝安全
运行调度
规范体系
```

第一个大项目需要范围足够聚焦。堆石混凝土适合做第一阶段主题，因为它具备：

- 专业性强，能体现用户水利背景。
- 资料量适中，有论文、综述、工程案例、施工技术、试验研究和质量控制资料。
- 非常适合做“引用式问答”，因为回答必须基于来源。
- 后续可以自然扩展到相邻水工材料与坝工技术。

核心边界：

```text
以堆石混凝土为核心，
以相关筑坝材料、施工工艺、质量控制和工程应用为扩展。
```

## 领域范围

### 第一阶段核心范围

优先收集和支持问答：

- 堆石混凝土基本概念。
- 堆石混凝土与常规混凝土、碾压混凝土、自密实混凝土的区别。
- 堆石混凝土材料组成。
- 堆石料粒径、级配、空隙率、填充性等基本问题。
- 自密实混凝土或高性能自密实混凝土在堆石混凝土中的作用。
- 堆石混凝土施工流程。
- 浇筑、填充、密实性与质量控制。
- 力学性能、变形性能、耐久性。
- 温控、水化热、裂缝控制等工程问题。
- 堆石混凝土坝或相关水利工程案例。
- 公开论文、公开网页、公开报告中的技术结论。

### 第二阶段扩展范围

资料不够或系统需要扩展时，可以加入：

- 大体积混凝土温控。
- 碾压混凝土坝。
- 常态混凝土坝。
- 混凝土面板堆石坝。
- 自密实混凝土技术。
- 水工混凝土施工与检测。
- 水利工程质量验收相关公开资料。

### 暂不纳入

第一阶段不要做：

- 全水利学科问答。
- 大坝结构安全定量计算。
- 工程设计责任判断。
- 隐私资料、内部资料、付费资料的非授权抓取。
- 绕过网站登录、验证码、反爬或版权限制。

如果用户问需要专业工程责任的问题，系统应明确说明：

```text
本系统仅提供资料检索和学习参考，不能替代规范审查、工程设计和专家判断。
```

## 项目总架构

推荐总体流程：

```text
资料来源
-> 爬取或导入
-> 原文保存
-> 文本抽取
-> 清洗
-> 切分 chunk
-> 生成 embedding
-> 存储向量索引
-> 用户提问
-> 检索召回
-> 可选 rerank
-> 组织上下文
-> 大模型生成回答
-> 返回答案、来源、置信提示
```

系统模块：

```text
API 层
  FastAPI 路由，请求和响应

数据采集层
  手动导入、网页爬取、PDF/HTML/Markdown/TXT 解析

文档处理层
  清洗、去重、切分、元数据保存

Embedding 层
  调用国产或本地 embedding 模型，把文本转成向量

向量检索层
  FAISS / Chroma / Qdrant / Milvus / pgvector

问答生成层
  调用国产大模型，根据检索资料生成回答

引用与溯源层
  显示来源标题、URL、发布时间、片段位置

评测层
  检索命中率、回答忠实度、引用准确性、不知道问题测试

前端层
  后续可做聊天界面、知识库管理界面、来源侧栏
```

## 推荐技术栈

第一阶段以容易跑通和可维护为主。

### 后端

```text
Python 3.11+
FastAPI
Pydantic
SQLAlchemy
SQLite
```

FastAPI 用来做接口，Pydantic 用来定义请求响应，SQLite 用来保存文档元数据和 chunk 信息。

后续升级：

```text
SQLite -> PostgreSQL
本地任务 -> 后台任务队列
单进程 -> Docker 部署
```

### 检索

第一阶段可选：

```text
FAISS
Chroma
```

建议初期优先选一个容易本地跑通的向量库。不要一开始就上复杂集群。

后续可升级：

```text
Qdrant
Milvus
pgvector
Elasticsearch / OpenSearch 混合检索
```

### 模型

用户目前没有 GPT Key，只有国产大模型 Key。因此要优先支持：

```text
OpenAI-compatible 国产模型 API
国产 embedding 模型
本地 embedding 模型
```

实现时要把模型调用封装成接口：

```text
EmbeddingProvider
ChatModelProvider
```

不要在业务代码里写死某一家模型。这样以后可以换模型。

候选方向：

- 云端国产聊天模型，用于生成回答。
- 云端国产 embedding，用于向量化。
- 本地开源 embedding，用于降低成本和保护资料。

具体模型名称和 API 参数可能变化，实际编码前要查看对应厂商当前文档。

### 前端

第一阶段可以没有前端，只做 API 和简单命令行测试。

第二阶段可选：

```text
Streamlit
Chainlit
React / Next.js
```

如果目标是简历大项目，后续建议做正式前端：

```text
知识库列表
资料导入
问答聊天
引用来源侧栏
检索片段查看
```

## 建议目录结构

正式项目建议创建在：

```text
G:\Codex\program\rfc-rag-agent
```

推荐结构：

```text
rfc-rag-agent/
  app/
    main.py
    api/
      health.py
      documents.py
      search.py
      chat.py
      sources.py
    core/
      config.py
      logging.py
    db/
      session.py
      models.py
      repositories.py
    schemas/
      document.py
      search.py
      chat.py
      source.py
    services/
      ingestion/
        loader.py
        parser.py
        cleaner.py
        splitter.py
      retrieval/
        embedding.py
        vector_store.py
        retriever.py
        reranker.py
      generation/
        prompt_builder.py
        chat_model.py
        answer_service.py
      crawling/
        crawler.py
        source_registry.py
        deduplicator.py
      evaluation/
        testset.py
        metrics.py
  data/
    raw/
    processed/
    indexes/
    exports/
  docs/
    architecture.md
    progress.md
    data_sources.md
    evaluation_plan.md
    interview_notes.md
  tests/
    test_splitter.py
    test_search.py
    test_chat.py
  .env.example
  .gitignore
  README.md
  requirements.txt
```

不要把所有代码写进一个 `main.py`。从第一天就保持模块边界清楚。

## 数据来源策略

本项目后续会从网上爬取资料，但第一阶段必须克制。

### 资料类型优先级

优先：

1. 官方或高校公开网页。
2. 公开论文页面、摘要页、DOI 页面。
3. 公开工程案例介绍。
4. 公开会议、新闻稿、项目介绍。
5. 可合法访问的 PDF 或开放文档。

谨慎：

- 论坛帖子。
- 无来源转载。
- 质量不明的营销文。
- 不完整或明显机翻资料。

禁止：

- 绕过登录、验证码、付费墙。
- 批量下载明显受版权保护且未授权的全文资料。
- 把密钥、Cookie、个人账号信息写进代码或提交到 Git。

### 爬取规则

任何爬虫代码都必须遵守：

- 小规模开始。
- 尊重 `robots.txt` 和网站条款。
- 设置请求间隔和最大页数。
- 保存原始 URL、标题、作者、发布时间、访问时间。
- 对来源质量打标签。
- 支持增量更新，不重复爬同一 URL。
- 对重复内容做去重。
- 不要隐藏或伪造来源。

### 数据源登记表

后续应维护：

```text
docs/data_sources.md
```

每个来源至少记录：

```text
source_id
标题
URL
来源类型
作者或机构
发布时间
访问时间
是否允许全文保存
可信度评级
备注
```

## 数据库设计建议

第一阶段可以用 SQLite。

核心表：

```text
documents
  id
  title
  source_type
  source_url
  author
  published_at
  fetched_at
  raw_path
  status
  hash

chunks
  id
  document_id
  chunk_index
  content
  token_count
  heading_path
  page_number
  source_url
  embedding_id

qa_logs
  id
  question
  answer
  retrieved_chunk_ids
  model_name
  created_at

crawl_tasks
  id
  seed_url
  status
  error_message
  created_at
  finished_at
```

不要只把文本丢进向量库。必须同时保存元数据，否则后面无法展示引用来源，也无法排查召回错误。

## 文本切分策略

中文专业资料切分要注意：

- 不要把公式、表格说明、施工步骤切得太碎。
- 保留标题层级。
- 保留来源 URL 和文档标题。
- 每个 chunk 应能独立表达一个局部知识点。

初始建议：

```text
chunk_size: 500 到 900 个中文字符
overlap: 80 到 150 个中文字符
```

如果是论文或报告：

```text
按标题层级优先切分
再按段落长度补切
```

如果是网页：

```text
去除导航栏、页脚、广告、推荐链接
保留正文、标题、发布时间、来源机构
```

## 检索策略

第一阶段先做：

```text
关键词检索 top_k
```

第二阶段加入：

```text
embedding 向量检索 top_k
向量检索与关键词检索结果对比
必要时加入简单的向量 + 关键词混合检索
保留来源可信度、时间过滤、分类过滤的扩展空间
```

后续阶段再逐步加入：

```text
rerank
引用式问答
来源可信度加权
更细的时间过滤和分类过滤
```

返回给大模型前，要整理上下文：

```text
[来源 1]
标题：
URL：
片段：

[来源 2]
标题：
URL：
片段：
```

最终回答必须附来源。

如果召回片段质量很差，回答应该是：

```text
当前资料库中没有找到足够可靠的依据。
```

不要让模型硬编。

## 问答生成原则

Prompt 应强调：

- 只基于给定资料回答。
- 不知道就说不知道。
- 引用来源编号。
- 区分事实、推断和建议。
- 面向水利工程学习和资料检索，不替代工程设计。

回答格式建议：

```text
简要结论
依据说明
相关来源
不确定性或需要补充资料
```

对于工程风险、规范适用、设计参数类问题，要更谨慎。

## 评测体系

这个项目要想写进简历，必须有评测，不然只是普通聊天 demo。

后续建立：

```text
docs/evaluation_plan.md
```

测试问题分类：

- 概念类：什么是堆石混凝土。
- 对比类：堆石混凝土和碾压混凝土有什么区别。
- 施工类：堆石混凝土施工流程是什么。
- 质量控制类：如何判断填充密实性。
- 工程案例类：哪些工程应用了相关技术。
- 不知道类：资料库没有依据的问题。

评测指标：

```text
Recall@K：正确资料是否被召回
Citation Accuracy：引用是否真实对应回答
Faithfulness：回答是否忠于资料
Answer Coverage：是否覆盖问题要点
Refusal Quality：无依据时是否拒答
```

每次升级检索或模型后，要用同一批问题回归测试。

## 开发里程碑

### 阶段 0：项目初始化

目标：

```text
创建 rfc-rag-agent 项目
建立 FastAPI 基础服务
建立 Git 仓库
写 README 和 .env.example
```

接口：

```text
GET /health
```

完成标准：

```text
服务能启动
/health 返回 ok
README 能说明项目目标和启动方式
```

### 阶段 1：本地资料导入与关键词检索

先不接大模型，先打通资料链路。

目标：

```text
导入 Markdown/TXT
清洗文本
切分 chunk
保存到 SQLite
用关键词搜索返回相关 chunk
```

接口：

```text
POST /documents/import
GET /documents
POST /search
```

完成标准：

```text
能导入 5 到 10 篇资料
能搜索并返回来源、标题和片段
```

### 阶段 2：Embedding 与向量检索

目标：

```text
接入 embedding 模型
建立向量索引
问题向量化
返回 top_k 相似片段
```

完成标准：

```text
语义相近但字面不同的问题也能召回正确资料
```

### 阶段 3：引用式问答

目标：

```text
接入国产聊天模型
把召回片段作为上下文
生成回答
附来源
无依据时拒答
```

接口：

```text
POST /chat
```

完成标准：

```text
能回答堆石混凝土基础问题
能显示引用来源
能处理资料库无答案问题
```

### 阶段 4：数据采集与来源管理

目标：

```text
建立 source registry
同步现有公开资料候选、PDF manifest 和题录语料
去重
保存来源元数据、可信度、全文权限和状态
支持重新索引
```

完成标准：

```text
sources 表可管理至少 30 到 80 条高质量公开资料来源
每条资料都有来源记录、可信度、全文权限和状态
支持从现有 CSV / manifest / metadata corpus 同步
支持按 DOI / URL / 标题去重
支持来源重新索引到 documents/chunks
```

### 阶段 5：前端界面

目标：

```text
资料管理界面
聊天界面
引用来源侧栏
检索片段查看
```

完成标准：

```text
非技术用户能上传资料、提问、查看来源
```

### 阶段 6：检索优化与评测

目标：

```text
混合检索
rerank
评测集
指标记录
错误案例分析
```

完成标准：

```text
README 中能展示评测结果和改进前后对比
```

### 阶段 7：Agent 化

在 RAG 稳定后再做 Agent。

已加入第一批只读工具：

```text
search_knowledge
hybrid_search_knowledge
answer_with_citations
list_sources
get_source_detail
```

限制：

- 最大工具调用步数。
- 只读工具优先。
- 高风险动作人工确认。
- 工具调用日志脱敏。
- 不自动执行 source reindex 等写入型动作。
- 继续复用阶段 6/7 评测集做回归。

## 简历化目标

最终简历描述可以向这个方向靠拢：

```text
基于 FastAPI 和向量检索构建面向水利工程堆石混凝土技术的 RAG Agent 系统，
实现公开资料采集、文本清洗切分、embedding 向量化、语义检索、引用式问答和来源追踪。
系统支持国产大模型 OpenAI-compatible API 接入，
设计文档元数据与 chunk 存储结构，
并通过自建评测集评估检索命中率和回答忠实度。
```

可展示亮点：

- 垂直领域，而不是通用聊天 demo。
- 有数据采集和来源管理。
- 有 RAG 全链路。
- 有引用和拒答机制。
- 支持国产模型。
- 有评测集和指标。
- 能逐步扩展成真实系统。

## 编码与协作规则

后续实现时遵守：

- 保持代码模块化，不把所有逻辑写进 `main.py`。
- API、schema、service、database 分层。
- 密钥放 `.env`，永远不要提交真实 key。
- 提供 `.env.example`。
- 每个阶段结束时，执行上文“阶段完成收尾清单”，不要只更新代码。
- 每次新增重要模块，补充最小测试。
- 保留用户已有改动，不随意重置 Git。
- 解释时使用清晰的中文，适合初学者理解。
- 遇到复杂概念，要结合当前项目例子讲。

## 新线程默认工作方式

如果用户说“继续这个项目”，新线程应该：

1. 读本文件。
2. 检查 `rfc-rag-agent` 是否已创建。
3. 阅读项目 README 和 progress。
4. 判断当前阶段。
5. 给出下一步最小可执行任务。
6. 如果用户要求实现，就直接动手，不只停留在建议。

如果用户问概念，要结合本项目解释。例如：

```text
embedding = 把堆石混凝土资料片段和用户问题变成向量，用于语义召回
chunk = 一段可被检索和引用的资料片段
rerank = 对初步召回的片段重新排序
source = 回答依据，必须能追溯到标题和 URL
```

## 当前推荐的第一步

阶段 24「多轮对话 UI 与会话持久化」当前已完成开发、测试、普通文档和 Obsidian 草稿收尾，停在用户人工核验前状态。当前分支为 `codex/phase-24-multi-turn-conversation`；阶段 23 已合并到 `main`，`phase-23-complete -> dd7d953`，合并提交为 `8fc1cfa`。

下一步最适合先完成人工核验。人工核验通过并且用户明确确认后，才允许执行 `git add`、`git commit`、创建 `phase-24-complete` tag、推送 GitHub或创建 PR；tag 必须指向阶段 24 最终功能提交，不要移动任何已有阶段 tag。

阶段 24 核验重点：

```text
检查 Conversation / Message 模型和级联删除是否符合会话持久化预期
检查 /conversations 四个端点的正常与异常路径
检查 /agent/query 不传 conversation_id 时是否保持阶段 23 兼容行为
检查传 conversation_id 时是否正确加载历史、保存 user/assistant 消息并触发摘要压缩
检查 agentic generate 节点是否只利用 history 做追问补全，不改变 retrieve/grade/rewrite 主链路
检查前端聊天气泡、会话列表、新建、切换、删除和刷新恢复
检查动态 HTML 是否继续使用 escapeHtml()
检查全量测试 479 passed 和浏览器 desktop/mobile 验证记录
确认尚未提交、尚未创建 phase-24-complete tag、尚未推送
```

阶段 0 到阶段 23 已完成并已有阶段 tag（含 `phase-21-complete`、`phase-22-complete`、`phase-23-complete`）。阶段 23 tag 指向最终功能提交 `dd7d953`、合并提交 `8fc1cfa`。

阶段 18（语料扩充与评测/质量体系增强 + 中文全文语料与拒答边界校准）已完成人工核验、提交、创建 `phase-18-complete` tag（指向最终功能提交 `c56fc62`，**非** merge）并合并到 `main`（合并提交 `4db90c7`），已 push 到 GitHub。阶段 18 关键结论与经验：

- 语料：开放获取深度扩充（诚实报数）+ 用户合法下载的中文全文 **298 篇**入库；现为 465 文档 / 8918 chunk / 深度全文约 340 篇。中文全文与 `data/app.sqlite`、`data/fulltext/` 均 gitignore，靠 `scripts/import_papers_corpus.py`（统一导入器）可复跑导入；新增依赖 `cryptography` 解密用户已合法获取的 AES PDF。
- PDF 解析加固 `app/services/ingestion/pdf_text.py`（含中文章节识别）让全文 chunk 带真实 `heading_path`。
- 难评测集多配置对比结论 `keep_existing_hybrid`（bm25_rrf 未优于 hybrid）。
- off-topic 拒答边界已校准闭环：`workflow.py` 主题门 `has_topic_anchor` + `CORE_DOMAIN_TERMS`（off-topic 5/5 拒答、on-topic 8/8 不误拒）；阶段 16 ITZ Answer Coverage 闭环为 low。quality gate 由 high → **pass/low**；全量 386 passed。
- 真实索引重建：`build_vector_index.py --provider openai-compatible --batch-size 16 --sleep-seconds 10 --max-retries 5`（限速 + 退避重试，遵守 Jina 速率限额、容忍瞬断）。
- 经验：阶段 17/18 都遇到「README/docs 顶部状态滞后于 Git 真相」，新线程务必以 `git tag`/`git log` 为准，文档收尾时同步修正入口文档。

阶段 19（中文全文文献分析与检索/评测调优）已完成人工核验、提交、创建 `phase-19-complete` tag（指向最终功能提交 `ffb4756`，**非** merge）并合并到 `main`（合并提交 `12184d7`）。阶段 19 关键结论与经验：

- **Phase 0 第一轮文献分析探索**（`scripts/explore_chinese_corpus.py`，10 题：8 on-topic + 2 拒答）：deterministic 下 `deep_top1=0/8`、`metadata_top1=5/8` 强力暴露中文查询排序短板（题录 chunks 短而关键词密度高，hybrid 默认 0.7 keyword + 0.3 vector 让题录系统性压过中文深度全文）；off-topic 拒答门按预期工作，唯独"工程责任判断"命中域词后未被默认拒答门挡住（prompt 层议题，记入遗留风险）。
- **Phase 1 中文难评测集**（`data/evaluation/stage19_chinese_hard_queries.csv`，19 题：5 跨段证据 + 5 易混淆术语 + 5 参数细节 + 4 需拒答）：独立 CSV，不覆盖旧英文 `stage18_hard_queries.csv`。
- **Phase 2 检索排序调优**：新增纯函数 `app/services/retrieval/source_type_reweight.py`（`Stage19TuningWeights` + 4 套默认配置 + `CORE_DOMAIN_TERMS` 与 Brain 解耦），新增 `scripts/evaluate_stage19_retrieval_tuning.py`；三候选都把 `deep_fulltext_top1_rate` 从 0.000 拉升到 0.533–0.733（`topic_anchor_strict` 最高），但 `precision@1` 因关键词判定偏向题录卡片而下降；按严格门槛（Δp@1 ≥ 0.10 且 Δdeep_top1 ≥ 0.20 且 refusal 不退化）保持 **`keep_existing_hybrid`**——三候选作为可配置开关保留在 `source_type_reweight.py`。
- **Phase 3 文献分析快照**（`docs/stage19_literature_review.md`）：面向人读，整合 Phase 0/2 数据 + 主题速览 + 面试表达；未新增 build 脚本（阶段边界裁剪）。
- 全量测试 **408 passed**；POST /search、/search/vector、/search/hybrid、/chat、/agent/query、GET /quality-report 均未被破坏。
- 经验：`expected_source_hit` 关键词判定对题录卡片偏向；阶段 20 已用答案级 coverage ratio 与真实 Jina query-only 复核。

阶段 19 经验继续沿用：不让真实 API 成为 CI/全量测试前提（deterministic 仍负责离线回归）；受版权/授权全文与本地 DB 不入库；默认链路是否切换由中文难评测集数据决定；`phase-19-complete` 已指向阶段 19 最终功能提交 `ffb4756`。

### 阶段 20 — 中文检索默认链路落地与评测判定增强（已完成并合并）

阶段 20 已完成人工核验、提交、创建 `phase-20-complete` tag（指向 `706047d`，**非** merge）并合并到 `main`（合并提交 `8333d71`）。

阶段 20 关键结论与经验：

- 评测判定升级：`scripts/evaluate_stage20_eval_upgrade.py` 用答案级 `coverage_ratio` 复用阶段 19 中文难评测集，避免题录标题/摘要关键词偏置。
- 真实 Jina 校验：只做 query 端真实 embedding，复用已有 8918 条 chunk embeddings，不重做索引；真实失败必须写 `skipped/error`，不伪造成成功。
- 默认链路决策：`scripts/build_stage20_default_chain_decision.py` 同时看 deterministic 与真实 Jina。当前候选 `source_type_reweight` 虽提高 deep_fulltext top-1，但 `Δp@1=+0.000<0.10`，因此保持 **`keep_existing_hybrid`**，不改默认 `HybridSearchService` / Brain hybrid 链路。
- 责任边界：新增 Brain 生成前 `responsibility_gate`，拦截“判定/评定/是否合格/是否符合规范/能否用于工程”等责任判断题；系统不替代规范审查、工程设计、第三方检测或专家签字。
- 质量门槛：`scripts/build_stage20_quality_report.py` 汇总阶段 20 quality gate；全量回归通过后为 `pass/low`。
- 面试表达：阶段 20 的重点不是盲目把重权策略焊进默认链路，而是先把评测口径修正确，再用真实 query 端校验和门槛做数据驱动决策；真正进入默认运行链路的是安全责任门，而不是排序偏好。

阶段 20 经验继续沿用：答案级 coverage_ratio 替代旧的关键词精度口径；responsibility_gate 已进入默认生成链路；不让真实 API 成为 CI/全量测试前提。

### 阶段 21 — LangGraph Agentic RAG（历史记录，已完成并合并）

阶段 21 已完成、提交、创建 `phase-21-complete` tag，并合并到 `main`。以下保留阶段 21 的关键结论与经验，供后续阶段理解 agentic RAG 架构。

阶段 21 关键结论与经验：

- LangGraph 状态图编排：`app/services/agentic/`（state.py, nodes.py, graph.py）实现 retrieve → grade → rewrite/decompose → re-retrieve → generate → citation_check 六节点有向图，TypedDict AgenticState 驱动。
- 硬迭代上界 `MAX_ITERATIONS = 3`：防止 retrieve-grade-rewrite 循环无限执行；超上界后 generate 节点重新评估证据，不足则拒答而非硬凑。
- 节点包裹现有服务：retrieve 包裹 HybridSearchService，generate 复用 BrainService 的 responsibility_gate + build_rag_prompt + extract_citations，不重写检索内核。
- 可配置 mode 接入：`AgentQueryRequest.mode = "agentic"` 走 LangGraph 图，默认 mode 走既有 BrainService 链路，API 契约不变。
- 确定性可测：`DeterministicChatModelProvider` 让全部 19 个 agentic 测试不依赖真实 LLM API。
- 评测决策（诚实）：agentic vs baseline 对照评测因 SSL 错误（`[SSL: UNEXPECTED_EOF_WHILE_READING]`）导致 14/19 查询出错，评测脚本已修复（排除出错行、报告 error_rate、高错误率返回 `inconclusive_high_error_rate`），不伪造达标结论。
- 全量测试 **449 passed**（>= 424 基线 + 25 新增）；POST /search、/search/vector、/search/hybrid、/chat、/agent/query、GET /quality-report 均未被破坏。
- 面试表达：阶段 21 重点是用 LangGraph 实现带自纠正循环的 agentic RAG，但诚实面对评测结果——SSL 错误导致对照不可靠，系统选择 `inconclusive` 而非伪装达标；工程上硬迭代上界 + 证据再评估双保险防止幻觉和死循环。

阶段 4 最终提交和 tag：

```text
commit: b044459b9b8c2153e9225daa55af5d82cdcdb282
tag: phase-4-complete
remote branch: origin/codex/phase-4-source-management
```

阶段 5 最终功能提交和 tag：

```text
commit: 8c885e6cc714cc985933438697a7eb2523b26722
tag: phase-5-complete
```

阶段 6 由以下 tag 标识：

```text
tag: phase-6-complete
```

阶段 7 由以下 tag 标识：

```text
tag: phase-7-complete
```

阶段 8 由以下 tag 标识：

```text
tag: phase-8-complete
```

阶段 9 由以下 tag 标识：

```text
tag: phase-9-complete
```

阶段 9.1 真实 Jina + MIMO 补充验证由以下 tag 标识：

```text
tag: phase-9.1-complete
```

阶段 10 真实 RAG 质量校准与拒答边界优化由以下 tag 标识：

```text
tag: phase-10-complete
```

阶段 11 真实用户问题评测集与跨语言质量提升由以下 tag 标识：

```text
tag: phase-11-complete
```

阶段 12 质量审阅与上下文最小补全由以下 tag 标识：

```text
tag: phase-12-complete
```

阶段 13 Decompose 与可解释证据合并由以下 tag 标识：

```text
tag: phase-13-complete
```

阶段 14 真实 Embedding 与回答覆盖校准由以下 tag 标识：

```text
tag: phase-14-complete
```

阶段 15 真实配置复跑与质量审阅报告由以下 tag 标识：

```text
tag: phase-15-complete
```

不要移动 `phase-4-complete` 到 `phase-18-complete` 中的任何已有阶段 tag。如果后续只是补文档或流程规则，应该新建普通文档提交，不要把阶段完成 tag 挪到后续提交。

阶段 18 已创建 `phase-18-complete` tag（指向最终功能提交 `c56fc62`）并合并、推送到 GitHub。阶段 19 已创建 `phase-19-complete` tag（指向最终功能提交 `ffb4756`）并合并到 `main`（合并提交 `12184d7`）。阶段 20 当前不得提交、不得创建 `phase-20-complete` tag、不得推送 GitHub；只有用户人工核验并明确确认后，才允许提交、创建阶段 20 tag 和推送，tag 必须指向阶段 20 最终功能提交。

阶段 6 已实现检索优化与评测闭环：

```text
docs/evaluation_plan.md
scripts/analyze_retrieval_errors.py
scripts/evaluate_hybrid_search.py
app/services/retrieval/hybrid_search.py
POST /search/hybrid
POST /chat retrieval_mode="hybrid"
data/evaluation/hybrid_results.csv
data/evaluation/retrieval_error_cases.csv
```

阶段 6 评测结果：

```text
keyword baseline: 15/15 passed
vector search: 11/15 passed
hybrid search: 15/15 passed
chat evaluation: 6/6 passed
rescued_vector: 4
regressed_keyword: 0
full tests: 141 passed
```

阶段 7 已实现受控 Agent 工具调用链路：

```text
docs/agent_design.md
app/services/agent/tools.py
app/services/agent/service.py
app/api/agent.py
POST /agent/query
scripts/evaluate_agent.py
data/evaluation/agent_queries.csv
data/evaluation/agent_results.csv
frontend Agent panel
```

阶段 7 评测结果：

```text
agent evaluation: 5/5 passed
tool_failures: 0
citation_failures: 0
full tests: 163 passed
```

阶段 8 已实现 Brain 中控层与 RAG Workflow 配置化：

```text
docs/brain_workflow_design.md
app/services/brain/config.py
app/services/brain/workflow.py
app/services/brain/service.py
CitationAnswerService -> BrainService
Agent answer_with_citations -> CitationAnswerService -> BrainService
scripts/evaluate_brain_workflow.py
data/evaluation/brain_workflow_results.csv
```

阶段 8 评测结果：

```text
brain workflow: default_hybrid 4/6, keyword_baseline 6/6, vector_only 2/6
keyword evaluation: 15/15 passed
vector evaluation: 11/15 passed
hybrid evaluation: 15/15 passed
chat evaluation: 6/6 passed
agent evaluation: 5/5 passed
full tests: 189 passed
```

阶段 9 已实现真实模型接入与模型评测：

```text
docs/model_provider_evaluation.md
OpenAICompatibleEmbeddingProvider
.env.example embedding provider/model/key/base_url/dimension/timeout
scripts/build_vector_index.py provider/model/dimension/API 参数
scripts/evaluate_model_configs.py
data/evaluation/model_config_results.csv
```

阶段 9 评测结果：

```text
deterministic model config:
  keyword 15/15
  vector 11/15
  hybrid 15/15
  chat 6/6
  agent 5/5
  brain_workflow 12/18
real_config: skipped because local real model configuration is incomplete
full tests: 205 passed
```

阶段 9.1 已完成真实 Jina + MIMO 补充验证：

```text
Jina vector: 14/15
Jina hybrid: 15/15
MIMO + Jina chat: 6/6
MIMO + Jina agent: 5/5
MIMO + Jina brain_workflow: 15/18
full tests: 208 passed
```

阶段 10 已完成真实 RAG 质量校准与拒答边界优化：

```text
scripts/analyze_real_rag_failures.py
data/evaluation/real_rag_failure_cases.csv
Brain EvidenceConfidence
low-evidence refusal before model generation
VectorSearchService topic anchor rerank
scripts/evaluate_model_configs.py failed/pass_rate
stage10_jina_* results
stage10_mimo_jina_* results
```

阶段 10 评测结果：

```text
deterministic:
  vector 13/15
  hybrid 15/15
  chat 6/6
  agent 5/5
  brain_workflow 18/18

real MIMO + Jina:
  Jina vector 15/15
  Jina hybrid 15/15
  chat 6/6
  agent 5/5
  brain_workflow 18/18

full tests: 216 passed
```

阶段 11 已完成真实用户问题评测集与跨语言质量提升：

```text
data/evaluation/user_questions.csv
scripts/evaluate_user_questions.py
data/evaluation/user_question_results.csv
docs/stage11_user_evaluation_plan.md
data/evaluation/user_question_review_samples.csv
expanded SYNONYM_RULES for cross-language engineering terms
Brain evidence confidence expanded evidence terms
```

阶段 11 评测结果：

```text
keyword evaluation: 15/15
vector evaluation: 13/15
hybrid evaluation: 15/15
chat evaluation: 6/6
agent evaluation: 5/5
brain workflow evaluation: 18/18
user question evaluation: 25/30
  default_hybrid: 10/10
  keyword_baseline: 10/10
  vector_only: 5/10
API regression: 16 passed
full tests: 230 passed
```

阶段 12 已完成质量审阅与上下文最小补全：

```text
data/evaluation/stage12_quality_review_results.csv
docs/stage12_quality_review.md
Brain rewrite_contextual_question
ChatRequest optional history
AgentQueryRequest optional history
docs/stage13_decompose_plan.md
```

阶段 12 评测结果：

```text
quality review tests: 8 passed
context rewrite focused tests: 52 passed
user question evaluation: 25/30
chat evaluation: 6/6
agent evaluation: 5/5
brain workflow evaluation: 18/18
API/core regression: 47 passed
full tests: 244 passed
```

阶段 13 已完成 Decompose 与可解释证据合并：

```text
docs/stage13_decompose_plan.md
app/services/retrieval/decompose.py
scripts/evaluate_decompose.py
data/evaluation/stage13_decompose_results.csv
Brain hybrid path -> decompose_query -> DecomposeRetrievalService -> MergedEvidence
```

阶段 13 评测结果：

```text
decompose evaluation: 6/6
all-user decompose evaluation: 10/10
user question evaluation: 29/30
chat evaluation: 6/6
agent evaluation: 5/5
brain workflow evaluation: 18/18
deterministic hybrid evaluation: 15/15
deterministic vector baseline: 13/15
full tests: 257 passed
```

阶段 14 已完成真实 Embedding 与回答覆盖校准：

```text
docs/stage14_real_quality_calibration.md
scripts/evaluate_stage14_embedding_comparison.py
data/evaluation/stage14_embedding_comparison.csv
scripts/evaluate_stage14_answer_coverage.py
data/evaluation/stage14_answer_coverage_review.csv
scripts/evaluate_stage14_decompose_provenance.py
data/evaluation/stage14_decompose_provenance_review.csv
```

阶段 14 评测结果：

```text
deterministic vector: 13/15
deterministic hybrid: 15/15
deterministic user_questions: 25/30
deterministic decompose: 10/10
deterministic chat: 6/6
deterministic agent: 5/5
deterministic brain_workflow: 18/18
answer coverage review: low=1, medium=9, skipped=10
decompose provenance review: 50 evidence rows
real_config: missing_results/skipped because stage14_real result files are absent
focused tests: 49 passed
API/frontend tests: 28 passed
core service tests: 75 passed
full tests: 275 passed
```

阶段 15 已完成真实配置复跑与质量审阅报告：

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

阶段 15 评测结果：

```text
real vector: 15/15
real hybrid: 15/15
real user_questions: 27/30
real decompose: error, SSL EOF during embedding request
real chat: 6/6
real agent: 5/5
real brain_workflow: 18/18
stage15 answer coverage review: high=1, medium=8
stage15 quality summary: high=4, low=7, medium=3
overall quality gate: review_required/high
deterministic vector: 13/15
deterministic hybrid: 15/15
deterministic user_questions: 25/30
deterministic decompose: 10/10
deterministic chat: 6/6
deterministic agent: 5/5
deterministic brain_workflow: 18/18
focused regression tests: 112 passed
full tests: 300 passed
```

阶段 16 已完成真实质量风险闭环开发与验证，当前等待用户人工核验：

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
GET /quality-report
```

阶段 16 评测结果：

```text
real decompose diagnostic: root_cause=embedding_header_compatibility_and_chat_timeout, blocking_status=not_blocking
stage16 answer coverage closure: 9 rows, risk_after high=1, medium=3, low=5
stage16 quality gate: review_required/high
stage16 real decompose retry: 10/10 passed
focused regression tests: 80 passed
full tests: 322 passed
submit state: no git add, no commit, no tag, no push, no PR
```

阶段 9.1 关键经验：

```text
Token Plan 的 MIMO key 是 tp- 前缀，必须配 token-plan-cn / token-plan-sgp / token-plan-ams 这类 Token Plan base URL。
普通 sk- 前缀 key 应配普通 API base URL，两者不能混用。
MIMO OpenAI-compatible 调用需要 api-key 请求头；项目同时保留 Authorization: Bearer 以兼容其他 provider。
真实模型评测要输出独立 CSV，不覆盖 deterministic baseline。
```

阶段 10 关键经验：

```text
真实 ChatModel 和 EmbeddingModel 更适合做最终体验校准，但不适合作为自动回归的唯一依据。
deterministic provider 继续负责稳定回归，真实 MIMO + Jina 负责发布前质量校准。
低证据拒答应放在 Brain 生成前，不能只靠 prompt 要求模型不要胡编。
vector-only 不能静默 fallback 到 hybrid；如果要优化，应使用可解释 rerank 或显式配置，保持 baseline 可比较。
```

阶段 11 关键经验：

```text
真实用户问题评测集应与旧 chat baseline 分开，既保留历史可比性，又能覆盖中文口语、英文、中英混合和工程场景。
expected_answer_points 更适合服务人工审阅或 LLM-as-judge，不要强行让 deterministic 回答逐词覆盖。
跨语言 query expansion 优先复用 SYNONYM_RULES，因为 keyword search、vector topic anchor 和 Brain evidence confidence 都能共享这套可解释词表。
LLM-as-judge 适合离线质量校准，不适合做 CI 或本地自动回归前提；真实 API key 不能写入文档、CSV、测试或 Obsidian。
deterministic vector-only 在真实用户问题上剩余的 source_hit_mismatch 应保留为 honest baseline，不要用静默 fallback 掩盖。
```

阶段 12 关键经验：

```text
自动评测能证明拒答、来源命中和引用链路稳定，但不能单独证明 Faithfulness 和 Answer Coverage。
deterministic provider 适合稳定回归，不适合证明真实语言表达质量；发布前仍需要真实模型或人工审阅校准。
上下文补全应放在 Brain rewrite_query step，补全后的 query 只用于检索，对外仍保留用户原始 question。
history 必须是可选输入，旧 /chat 和 /agent/query 请求不能被破坏。
Context 只做最近历史问题的最小补全，不扩展成长期记忆系统；HyDE 只做离线实验建议。
```

阶段 13 关键经验：

```text
Decompose 应优先放在 Brain/retrieval 边界，而不是让 chat 或 Agent 各自复制拆解逻辑。
规则式拆解比真实模型拆解更适合 deterministic 自动回归；子 query 最多 3 个，避免召回噪声和上下文膨胀。
接入 Brain 时必须先判断是否真的 decomposed，再执行子 query 检索；否则单主题问题会多跑检索并可能造成 default_hybrid 退化。
MergedEvidence 要像普通 SearchResultLike 一样能进入 Brain，同时保留 sub_query provenance、both_match、topic_score 和 explanation 供评测使用。
unsupported 问题不能因为 Decompose 而被强行回答，最终仍要经过 Brain evidence confidence。
阶段 13 后续最值得做的是真实 embedding 对比、真实模型 Answer Coverage 校准，以及把 provenance/rerank explanation 做成只读可视化。
```

阶段 14 关键经验：

```text
deterministic baseline 继续负责稳定回归，但不能证明真实回答覆盖度。
真实 embedding 或真实 chat 没有阶段 14 结果文件时，必须记录 missing_results/skipped，不能伪造成成功。
Answer Coverage、Faithfulness 和 Citation Quality 应分开审阅；来源命中不等于回答覆盖。
Decompose provenance 和 rerank explanation 可以先在 CSV 中证据级可读化，不必为了展示破坏 API schema 或重构前端。
显式 deterministic user_questions 为 25/30，说明真实 embedding、真实模型回答或更强 rerank 仍有后续价值。
```

阶段 15 关键经验：

```text
真实配置复跑必须显式运行，默认不能偷偷调用真实 API，也不能让真实 API 成为 CI 或本地全量测试前提。
stage14_real 目录保存脱敏评测结果和状态，不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
completed、skipped 和 error 都是有效质量状态；真实 decompose error 必须进入质量报告，而不是被 deterministic baseline 掩盖。
Answer Coverage、Faithfulness 和 Citation Quality 仍要分开复核；真实回答来源命中不等于回答覆盖。
只读质量报告应放在 evaluation/reporting 层，不改变 search/vector/hybrid/chat/agent API schema，不重构核心工作台。
```

阶段 16 关键经验：

```text
质量闭环不是把 high 风险改成通过，而是给每个风险补 root_cause、risk_after、decision 和 next_action。
real decompose SSL EOF 不能被 deterministic decompose 10/10 掩盖；阶段 16 追加重试证明，embedding 请求头兼容性和 chat timeout 都会影响真实 decompose 运行。
Answer Coverage 复核不能只看来源命中，必须检查回答摘要是否覆盖 expected_answer_points；真实回答超时应保持 high/blocking。
阶段 16 的 /quality-report 仍然是 evaluation/reporting 层的只读页面，不调用真实 API、不写数据库、不改变核心 RAG API。
用户要求人工核验前不得 git add、commit、tag、push 或 PR；后续线程必须先确认这个边界。
```

当前最权威的进度依据是：

```text
docs/progress.md
```

下一步最适合先完成人工核验。人工核验通过后再提交阶段 16 并创建 `phase-16-complete` tag；若用户要求继续加功能，则追加阶段 16 小 Phase。核验重点：

```text
检查 stage16_decompose_diagnostics.csv 对 SSL EOF 的分类是否符合真实网络/provider 现象
检查 stage16_answer_coverage_closure.csv 中 user_mixed_itz_strength 是否仍应 high/blocking
检查 3 条 medium 样例是否需要追加人工证据或后续资料补充
确认 /quality-report 是否足够支撑阶段 16 人工审阅
确认后才允许提交、创建 phase-16-complete tag 和推送
```

## 阶段 16 之后的开发计划

阶段 16 已完成人工核验、提交、创建 `phase-16-complete` tag 并合并到 `main`。阶段 17 当前已完成开发与验证，等待用户人工核验。后续优先顺序是：

```text
阶段 17：人工核验、提交与 phase-17-complete tag
阶段 18：质量报告与评测体系增强
阶段 19：产品化、Agent 增强与框架评估
```

### 阶段 16：真实质量风险闭环

当前状态是开发与验证完成，等待人工核验。阶段 16 的目标是处理阶段 15 质量报告已经暴露的问题，而不是继续加新功能。

已完成任务：

```text
排查 real decompose 的 SSL EOF 错误，先分类为 provider_network_ssl_eof，随后通过兼容 embedding 请求头和更长 chat timeout 完成真实重试
复核 stage15_answer_coverage_review.csv 中 1 条 high 风险样例
审阅 8 条 medium 样例，形成 high=1、medium=3、low=5 的 risk_after
生成阶段 16 质量闭环汇总、Markdown 报告和 /quality-report 页面
运行聚焦回归 80 passed 与全量测试 322 passed
```

阶段 16 仍然不做写入型 Agent 工具，不做复杂 LangGraph workflow，不做部署优化，不让真实 API 成为 CI 或本地全量测试前提。当前质量门禁仍是 `review_required/high`，但 decompose 已完成真实重试；剩余 high 阻断来自 `user_mixed_itz_strength` 的 Answer Coverage high/blocking。

### 阶段 17：检索架构升级

阶段 17 比 LangChain / LangGraph 更优先。当前项目最值得增强的是检索工程本身。

推荐能力：

```text
父子块切片策略：child chunk 负责精准召回，parent chunk 负责回答上下文扩展
检索流水线：query normalize -> query expansion -> 多路召回 -> merge -> deduplicate -> rerank -> evidence confidence -> context assembly
BM25 lexical retriever：替代或增强当前简单 keyword baseline
BM25 + vector 双通道召回：保留关键词可解释性，同时保留语义召回
RRF 融合：用排名融合 BM25 和 vector 结果，避免直接硬拼不同尺度分数
与现有 hybrid baseline 对比：必须保留旧结果，证明升级没有 regression
```

HNSW 暂时不是第一优先级。只有当资料量扩大、SQLite 向量全量扫描明显变慢，或需要接入 FAISS/Qdrant/PGVector 这类向量索引时，再把 HNSW 作为阶段 17 后半段或后续小 Phase。不要为了简历关键词过早引入复杂索引。

阶段 17 的面试表达重点：

```text
我先升级检索架构，而不是先套 Agent 框架。父子块解决“召回精准但上下文不足”的问题；BM25 + vector 双通道解决“术语精确匹配和语义召回互补”的问题；RRF 解决“两路分数尺度不同、直接加权不稳定”的问题。
```

阶段 17 当前已完成 Phase 0-8 开发与验证，并追加完成 Phase 9 人工复核与接入建议，等待用户人工核验：

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

阶段 17 评测结果：

```text
stage17 retrieval upgrade: upgraded=15/15
old hybrid baseline: baseline=15/15
improved=0
regression=0
phase9 manual review: acceptable=14, needs_tuning=1, regression=0, defer=0
phase9 default chain recommendation: keep_existing_hybrid（候选/配置开关，不替换默认 HybridSearchService）
phase9 rank soft-degradation: mesoscopic_modeling rank 2 -> 7
focused regression: 97 passed
full test suite: 343 passed
```

阶段 17 关键经验：

```text
BM25 适合补强术语精确匹配，但中文无空格 query 必须显式保留领域触发词，例如“孔隙率”“抗压”。
BM25 与 vector 的原始分数尺度不同，不能直接硬加权；阶段 17 使用 RRF 按排名融合。
context expansion 可以先用同 document 相邻 chunk 近似 parent chunk，不必过早迁移数据库 schema。
如果评测只证明无 regression，而没有证明明显优于旧 hybrid，默认 Brain/chat/agent 链路应保持不变。
Phase 9：hit 级「regression=0」会掩盖排序层退化；人工复核必须逐条看 rank_before/rank_after，例如 mesoscopic_modeling 从 rank 2 退化到 7。
Phase 9：source_match=no 不等于失败；中文 query 下中文母语文献换位仍 top-1 命中应判 acceptable，不能伪造成 regression，也不能当作通过糊弄过去。
Phase 9：评测集 hit 饱和（15/15）缺乏区分度，是 RRF 看不出增益的根因；这把「下一阶段做更难评测集」的依据交给阶段 18，而不是继续盲目调检索。
Phase 9：报告纳入人工复核摘要时，让脚本 write_report 从复核 CSV 读取并重生成，保持可复现；用已有结果 CSV 重生成，不重跑检索、不碰 DB、不触发真实 API（.env 可能是真实 provider）。
Phase 9：人工复核 Phase 不做即时检索重排调优；mesoscopic 软退化记为 tuning_suggestion 留给阶段 18，避免在复核阶段做影响全部查询的调参。
```

阶段 17 当前没有阶段 tag。只有用户人工核验并明确确认后，才允许提交、创建 `phase-17-complete` tag 和推送 GitHub；tag 必须指向阶段 17 最终功能提交。

### 阶段 18：质量报告与评测体系增强

阶段 18 的目标是把阶段 15 的静态报告升级成长期可用的质量评估体系。

推荐任务：

```text
增强 /quality-report 的只读筛选、风险详情和导出能力
把 high/medium/low 风险样例变成可持续审阅队列
补充更结构化的人工审阅 rubric
可选引入 LLM-as-judge 离线评测，但不能进入 CI 必跑
对比 keyword、vector、hybrid、BM25+vector、RRF 等多套检索配置
沉淀质量门槛：什么情况下可以继续下一阶段，什么情况必须人工复核
```

阶段 18 仍然保持报告只读优先，不做登录系统，不把报告页扩展成复杂后台。

### 阶段 19：产品化、Agent 增强与框架评估

阶段 19 再考虑产品体验、Agent 能力和外部框架。

推荐任务：

```text
前端体验优化和质量报告体验优化
更多只读 Agent 工具，例如质量报告查询、来源质量查询、评测结果查询
Agent 多步查询规划，但仍保留工具权限、最大步数、调用记录和引用约束
来源库扩展和 source registry 质量治理
部署、日志、观测、配置分环境等工程化能力
评估 LangChain / LangGraph 是否值得接入
```

LangChain / LangGraph 不建议早于阶段 19 引入。引入条件是：

```text
Brain workflow 已经难以表达复杂条件分支
Agent 工具数量明显增多，手写编排开始难维护
需要多步计划、重试、checkpoint、human-in-the-loop 或可视化 workflow
已有测试能证明迁移不会破坏引用、拒答、来源追踪和评测回归
```

如果当前链路仍主要是：

```text
检索 -> 组织上下文 -> 生成回答
```

则继续使用本项目已有 `BrainService`、`RetrievalConfig` 和 `WorkflowConfig`。不要为了框架名提前引入 LangChain 或 LangGraph。更好的面试表达是：先把 RAG 底层链路、检索质量、引用溯源和评测闭环做清楚，等系统进入多工具、多步骤、状态机编排时，再评估 LangGraph 承接 Brain workflow。

阶段 7 已经把稳定 RAG 能力包装成受控工具，让 Agent 能调用 RAG 系统，但不能绕过来源、权限、引用和评测约束。后续如果加入 LLM 规划、写入工具或部署能力，必须继续保留只读优先、最大步数、显式权限、工具调用记录、引用溯源和评测回归。

阶段 8 已经把 `/chat` 和 Agent `answer_with_citations` 收拢到 Brain workflow。后续如果加入真实模型、query rewrite、rerank 或更复杂 workflow，应优先扩展 `RetrievalConfig`、`WorkflowConfig` 和 `BrainService`，而不是重新在 chat 或 Agent 工具里复制编排逻辑。

阶段 9 已经补齐真实模型 provider 边界。后续如果切换真实 chat 或 embedding 模型，必须保留 deterministic baseline，先按 provider/model/dimension 重建向量索引，再复跑 model config、vector、hybrid、chat、agent 和 brain workflow 评测，不能只凭单次回答效果判断质量。

阶段 9.1 已证明真实 MIMO + Jina 可以运行，但失败项集中在 `vector_only/filling_capacity`、`default_hybrid/unsupported`、`vector_only/unsupported`。阶段 10 已通过 EvidenceConfidence 和 topic anchor rerank 修复主要边界。阶段 11 已扩大真实用户问题集、补充跨语言 query expansion 和人工审阅设计。阶段 12 已落地质量审阅并实现最小上下文补全。阶段 13 已实现规则式 Decompose、子 query 检索、证据合并、`chunk_id` 去重和可解释 rerank。阶段 14 已建立真实 embedding 对比、Answer Coverage 校准和 Decompose provenance 可读化表。阶段 15 已补齐真实配置复跑、Answer Coverage 复核表和只读质量报告。后续阶段如果继续提升质量，应优先处理报告暴露的 high/medium 风险和真实 decompose 稳定性，而不是继续盲目扩展模型 provider 或默认引入 HyDE。
