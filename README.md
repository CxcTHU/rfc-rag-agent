# RFC-RAG-Agent

面向水利工程堆石混凝土技术的文献检索与引用式问答 Agent。

本项目目标是从零搭建一个垂直领域 RAG 系统，逐步实现：

- 公开资料采集与来源管理
- 文档清洗、切分与元数据保存
- embedding 向量化与语义检索
- 基于检索资料的引用式问答
- 国产大模型接入
- 检索与回答质量评测
- 后续 Agent 工具调用与前端界面

## 当前阶段

阶段 4：数据采集与来源管理已完成，当前分支为 `codex/phase-4-source-management`。

下一阶段准备进入：阶段 5，前端界面。

当前已经实现：

- FastAPI 应用入口
- `GET /health` 健康检查接口
- 基础配置读取
- SQLAlchemy 数据库层，包含 `documents` 和 `chunks` 两张表
- Markdown、TXT、PDF 的文本读取、清洗和 chunk 切分
- 本地资料导入链路：读取文件 -> 清洗 -> 切分 -> 保存
- `POST /documents/import`
- `GET /documents`
- `GET /documents/{document_id}/chunks`
- `POST /search`
- 阶段 1 关键词检索，包含中文/英文同义词扩展、标题/路径加分、泛词降权和来源均衡
- 关键词检索评测集与自动评测脚本
- `EmbeddingProvider` 抽象和本地 deterministic embedding provider
- `chunk_embeddings` 向量保存表
- `VectorIndexService` 向量索引构建服务
- `scripts/build_vector_index.py` 向量索引构建脚本
- `POST /search/vector` 向量检索 API
- `scripts/evaluate_vector_search.py` 向量检索评测脚本
- `data/evaluation/vector_results.csv` 向量检索评测结果
- `ChatModelProvider` 聊天模型抽象，支持 deterministic provider 和 OpenAI-compatible provider
- RAG prompt/context builder，把检索结果组织成带 `[1]`、`[2]` 编号的上下文
- `CitationAnswerService` 最小引用式问答链路
- `POST /chat` 引用式问答 API
- `qa_logs` 问答日志表和最小可观测性
- `scripts/evaluate_chat.py` 问答评测脚本
- `data/evaluation/chat_queries.csv` 和 `data/evaluation/chat_results.csv`
- `sources` 来源登记表，统一管理公开资料候选、题录、PDF manifest 和 metadata cards
- `SourceRepository` 和 `SourceRegistryService`，支持来源保存、去重、合并、可信度、权限和状态治理
- `scripts/sync_sources.py` 来源同步脚本，可从 CSV、manifest、metadata corpus 同步来源记录
- `GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`
- `scripts/evaluate_sources.py` 来源登记库评测脚本
- `data/evaluation/source_registry_metrics.csv` 来源治理指标
- 堆石混凝土种子资料、题录元数据语料库和来源目录
- 123 个自动化测试
- 本地开发依赖配置

## 新线程说明

任何新线程继续本项目时，先阅读：

1. `AGENT.MD`
2. `docs/progress.md`
3. `docs/architecture.md`
4. `docs/data_sources.md`

阶段 4 的开发记忆：

- `task_plan.md`
- `findings.md`
- `progress.md`

阶段 3 的学习笔记：

- `docs/stage3_learning_notes.md`

## 本地启动

建议使用 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

启动 API 服务：

```powershell
python -m uvicorn app.main:app --reload
```

访问健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期返回：

```json
{
  "status": "ok",
  "service": "RFC-RAG-Agent",
  "environment": "development"
}
```

如果 `8000` 端口已经被占用，可以换一个端口：

```powershell
python -m uvicorn app.main:app --reload --port 8001
```

## 运行测试

```powershell
python -m pytest
```

当前全量测试结果：

```text
123 passed
```

当前测试覆盖：

- FastAPI 应用能被导入
- `/health` 返回 HTTP 200
- `/health` 返回结构化 JSON
- SQLAlchemy 数据模型和 repository
- Markdown/TXT/PDF parser
- cleaner 和 splitter
- ingestion service
- documents API
- search API
- keyword search 评分与来源均衡
- embedding provider
- chunk embedding 数据库保存
- vector index service
- vector search service 和 API
- vector search evaluation script
- ChatModelProvider 和 OpenAI-compatible 响应解析
- RAG prompt/context builder
- CitationAnswerService
- Chat API
- QA logging
- Chat evaluation script
- source collection 资料发现与过滤
- source registry 数据模型与仓储
- 来源归一化、DOI/URL/标题三层去重、可信度和权限治理
- source sync 脚本、sources API、source reindex
- source registry 评测脚本

## 向量索引与检索

阶段 2 的最小链路是：

```text
chunks
-> EmbeddingProvider
-> chunk_embeddings
-> 用户问题向量化
-> 余弦相似度检索
-> 返回来源、标题、chunk 和 score
```

构建或刷新向量索引：

```powershell
python scripts/build_vector_index.py
```

运行向量检索评测：

```powershell
python scripts/evaluate_vector_search.py
```

当前评测结果：

```text
keyword baseline: 15/15 passed
vector search: 11/15 passed
chat evaluation: 6/6 passed
```

说明：当前向量检索使用 deterministic embedding，主要用于稳定开发和自动化测试，不代表真实语义 embedding 的最终效果。后续接入真实 embedding 模型或混合检索后，应继续复用同一评测集对比。

## 引用式问答

阶段 3 的最小问答链路是：

```text
用户问题
-> 检索 chunks
-> 组织 RAG 上下文和来源编号
-> 调用 ChatModelProvider
-> 返回 answer、citations、sources、refused 和 model 信息
-> 写入 qa_logs
```

调用 `/chat` 示例：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body '{"question":"What affects filling capacity in rock-filled concrete?","top_k":5,"retrieval_mode":"auto"}'
```

响应字段要点：

- `answer`：回答正文。
- `citations`：答案中使用的来源编号，例如 `[1]`。
- `sources`：每个来源编号对应的文档、chunk、片段内容和 score。
- `refused`：资料不足时为 `true`。
- `refusal_reason`：拒答原因。
- `retrieval_mode`：实际使用的检索模式，可能是 `vector`、`keyword` 或 `none`。
- `model_provider` / `model_name`：本次回答使用的聊天模型信息。

资料不足时，系统会返回：

```text
当前资料库中没有找到足够可靠的依据。
```

运行问答评测：

```powershell
python scripts/evaluate_chat.py
```

当前结果：

```text
chat evaluation: 6/6 passed
```

阶段 3 仍然不做 Agent 工具调用，也不引入复杂 LangGraph workflow。当前目标是先把“基于资料回答、可引用、可拒答、可评测”的最小链路稳定跑通。

## 来源管理

阶段 4 的最小来源治理链路是：

```text
公开资料候选 / 题录 / PDF manifest
-> source registry
-> DOI / URL / 标题归一化去重
-> 可信度与全文保存权限标记
-> 来源状态管理
-> 原文或题录入库
-> 支持重新索引
```

同步现有来源到 `sources` 表：

```powershell
python scripts/sync_sources.py
```

查看来源治理指标：

```powershell
python scripts/evaluate_sources.py
```

当前来源评测结果：

```text
total_sources: 125
linked_documents: 0
merged_duplicates: 14
status: candidate=8, collected=117
fulltext_permission: institutional_access=2, metadata_only=110, open_access=10, unknown=3
trust_level: high=125
```

来源管理 API：

```text
GET /sources
GET /sources/{source_id}
POST /sources/sync
POST /sources/{source_id}/reindex
```

字段要点：

- `trust_level`：来源可信度，例如高校、期刊、DOI、开放论文等高可信来源。
- `fulltext_permission`：全文保存权限，例如 `open_access`、`institutional_access`、`metadata_only`、`unknown`。
- `status`：来源生命周期状态，例如 `candidate`、`collected`、`imported`、`duplicate`、`rejected`。
- `document_id`：来源重新导入后关联到 `documents` 表的文档编号。

阶段 4 不做 Agent 工具调用、不做复杂 LangGraph workflow、不做前端界面。当前重点是让资料来源可靠、可去重、可追溯、可重新导入，为阶段 5 前端和后续 Agent 工具调用打基础。

## Obsidian 知识库

本项目维护了一个可直接用 Obsidian 打开的知识库：

```text
obsidian-vault/
```

打开方式：

1. 打开 Obsidian。
2. 选择“打开本地文件夹作为库”。
3. 选择本仓库下的 `obsidian-vault`。
4. 从 `首页.md` 开始阅读。

知识库用途：

- 按阶段沉淀开发知识。
- 按分类整理面试高频点。
- 用 `[[双链]]` 连接阶段、分类和知识点。
- 记录每个知识点对应的代码位置、作用和面试表达。

## 当前目录

```text
rfc-rag-agent/
  app/
    main.py
    api/
      chat.py
      documents.py
      health.py
      search.py
      sources.py
    core/
      config.py
    db/
      models.py
      repositories.py
      session.py
    schemas/
      chat.py
      document.py
      health.py
      search.py
      source.py
    services/
      generation/
      ingestion/
      retrieval/
      source_registry.py
      source_collection.py
  data/
    evaluation/
    imports/
    metadata/
  docs/
  scripts/
  tests/
  obsidian-vault/
    首页.md
    阶段索引.md
    分类索引.md
    阶段/
    分类/
    知识点/
    模板/
  AGENT.MD
  README.md
  .env.example
  .gitignore
  pyproject.toml
```

## 项目边界

第一阶段聚焦堆石混凝土，不做全水利知识库。

核心范围：

- 堆石混凝土基本概念
- 材料组成与自密实混凝土
- 施工工艺与质量控制
- 力学性能与耐久性
- 工程案例
- 公开文献和网页资料的引用式问答

## 安全说明

真实 API Key 只允许写入本地 `.env`，不得提交到 GitHub。

## 阶段 0 面试表达

本阶段先搭建 FastAPI 后端工程底座，而不是直接做爬虫或大模型调用。原因是 RAG 系统后续会包含资料导入、检索、问答、评测等多个模块，如果一开始没有清晰的应用入口、路由分层、配置读取和测试方式，后续功能会很容易堆在一起，难以维护。

`/health` 是服务健康检查接口，用来证明 API 服务可以被正常启动和访问。真实部署时，健康检查还可以扩展为数据库连接、向量库状态、模型服务状态等检查。

## 阶段 1 面试表达

阶段 1 我先完成了 RAG 系统的数据入口和关键词检索 baseline，而不是直接接大模型。

我把资料导入拆成 parser、cleaner、splitter、repository 和 ingestion service：parser 负责把 Markdown/TXT/PDF 读成文本，cleaner 负责去掉多余空白，splitter 负责切成可检索的 chunk，repository 负责数据库读写，ingestion service 负责串起完整导入流程。这样做的好处是每一步都能单独测试，后续接 embedding 或更换数据库时不需要重写整条链路。

关键词检索用于在没有向量库之前建立第一版可解释检索能力。我建立了 `data/evaluation/keyword_queries.csv` 作为评测集，并用脚本自动检查命中结果。最终 15 个代表性查询全部通过，形成了阶段 2 向量检索的对照基线。

## 阶段 2 面试表达

阶段 2 我完成了从 chunk 到 embedding，再到向量检索 API 的最小可运行链路。

我先抽象 `EmbeddingProvider`，让业务检索逻辑不依赖某一家模型服务；再新增 `chunk_embeddings` 表保存每个 chunk 的向量、模型信息、维度和内容指纹。索引构建由 `VectorIndexService` 负责，可以重复运行，未变化的 chunk 会被跳过，内容变化后会更新 embedding。

检索时，`POST /search/vector` 会把用户问题转成 query embedding，再和数据库中的 chunk embedding 计算余弦相似度，返回来源、标题、片段和 score。为了验证效果，我复用了阶段 1 的关键词评测集，当前 deterministic embedding 下向量检索为 11/15，关键词 baseline 为 15/15。这个结果说明链路已经跑通，但真实语义效果还需要后续接入更好的 embedding 模型或混合检索来提升。

## 阶段 3 面试表达

阶段 3 我完成了引用式问答的最小稳定链路，而不是直接做一个普通聊天接口。

我先抽象 `ChatModelProvider`，让业务逻辑不绑定某一家模型服务；再用 prompt builder 把检索结果组织成带 `[1]`、`[2]` 编号的上下文，并保存编号到 chunk 的映射。`CitationAnswerService` 负责串联检索、prompt 构造、模型调用、引用提取和拒答判断。最后通过 `POST /chat` 返回 answer、citations、sources、refused、retrieval_mode 和 model 信息。

为了保证可排查性，我新增了 `qa_logs` 记录每次问答的问题、答案、召回 chunk、引用、模型和拒答状态；为了保证不是只靠演示，我新增了 chat 评测集和 `scripts/evaluate_chat.py`。当前 chat 评测 6/6 通过，全量测试 106 个通过。阶段 3 暂不做 Agent 工具调用和复杂 workflow，先保证 RAG 问答链路忠实、可引用、可拒答、可评测。

## 阶段 4 面试表达

阶段 4 我完成了资料来源治理，而不是继续堆更多问答功能。

我新增 `sources` 表作为 source registry，把公开资料候选、PDF manifest、题录 CSV 和 metadata cards 统一登记起来。`SourceRegistryService` 负责把采集候选转换成数据库记录，并按 DOI、URL、标题归一化做三层去重；同时维护 `trust_level`、`fulltext_permission` 和 `status`，区分来源是否可信、能否保存全文、处于候选还是已收集状态。

为了让来源能重新进入 RAG 链路，我新增了 source reindex 入口：已有本地文件的来源可以重新导入原文，metadata-only 来源可以重新生成题录卡片后导入 `documents/chunks`。同时提供 `scripts/sync_sources.py`、`/sources` API 和 `scripts/evaluate_sources.py`，保证来源治理既能批量同步，也能被后续前端或 Agent 工具调用复用。阶段 4 全量测试 123 个通过，关键词、向量和 chat 评测保持阶段 3 基线。
