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
```

协作规则：

- 同一阶段内尽量保持同一个线程，保证上下文连续。
- 进入下一个大阶段时，新开线程，先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md` 和 `docs/data_sources.md`。
- 每个阶段结束时，必须更新 `README.md` 和 `docs/progress.md`。
- 如果阶段改变了系统结构，也要更新 `docs/architecture.md`。
- 阶段结束记录必须包含：完成内容、验证方式、遗留问题、下一阶段任务、面试表达。

## Obsidian 知识库规则

本项目必须维护一个 Obsidian 知识库，用来沉淀每个阶段的工程知识、面试知识和项目决策。

知识库目录：

```text
obsidian-vault/
```

维护原则：

- 每个阶段结束时，必须在 Obsidian 知识库中新增或更新对应阶段笔记。
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
  Quivr 中的知识库对象。本项目后续可以对应为 KnowledgeBase 或 Corpus，不一定直接命名为 Brain。

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

阶段 0 当前已对齐 Quivr 的工程思想：

- 有清晰入口：`app/main.py`。
- 有 API 分层：`app/api/health.py`。
- 有 schema 分层：`app/schemas/health.py`。
- 有集中配置：`app/core/config.py`。
- 有自动化测试：`tests/test_health.py`。
- 有文档和知识库沉淀：`README.md`、`docs/progress.md`、`obsidian-vault/`。

阶段 0 尚未实现 Quivr 的 RAG 核心链路，这是正常的。后续阶段按以下方式逐步对齐：

```text
阶段 1
  对齐 Quivr storage / processor / splitter 的思想
  实现本地 Markdown/TXT 导入、清洗、chunk 切分、SQLite 元数据保存和关键词检索

阶段 2
  对齐 Quivr vector store / embedder 的思想
  接入 embedding provider 和向量检索

阶段 3
  对齐 Quivr RAG pipeline / LLMEndpoint / response metadata 的思想
  实现引用式问答、来源返回和拒答机制

阶段 4
  对齐 Quivr storage 扩展和 source 管理思想
  建立公开资料采集、source registry、原文保存和去重机制

阶段 6
  借鉴 Quivr 的测试组织，补充检索与问答评测集

阶段 7
  借鉴 Quivr workflow/tools 思路，再做 Agent 工具调用
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
小规模爬取公开网页
去重
保存原文和元数据
支持重新索引
```

完成标准：

```text
至少收集 30 到 80 条高质量公开资料
每条资料都有来源记录
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

可加入工具：

```text
search_knowledge_base
summarize_document
compare_sources
generate_review_questions
extract_engineering_terms
```

限制：

- 最大工具调用步数。
- 只读工具优先。
- 高风险动作人工确认。
- 工具调用日志脱敏。

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
- 每个阶段都更新 `README.md` 和 `docs/progress.md`。
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

阶段 0 和阶段 1 已完成，阶段 1 已合并到 `main`。

当前最权威的进度依据是：

```text
docs/progress.md
```

下一步最适合进入阶段 2：Embedding 与向量检索。

建议先创建或切换到阶段 2 分支：

```text
codex/phase-2-vector-search
```

阶段 2 的第一批最小任务：

```text
阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md 和 docs/data_sources.md
确认阶段 1 的 documents/chunks 表、ingestion service 和 POST /search 已可用
选择阶段 2 的 embedding 模型和向量索引方案
设计 chunk embedding 的保存结构
实现最小向量检索链路：问题 -> embedding -> 召回 chunks -> 返回来源
补充向量检索测试，并与阶段 1 keyword baseline 对比
```

阶段 2 不要急着做引用式问答和 Agent 工具调用。

先把“资料片段能被语义召回”这件事稳定跑通，再进入阶段 3。
