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

阶段 2：Embedding 与向量检索已完成，当前分支为 `codex/phase-2-vector-search`。

下一阶段准备进入：阶段 3，引用式问答。

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
- 堆石混凝土种子资料、题录元数据语料库和来源目录
- 63 个自动化测试
- 本地开发依赖配置

## 新线程说明

任何新线程继续本项目时，先阅读：

1. `AGENT.MD`
2. `docs/progress.md`
3. `docs/architecture.md`
4. `docs/data_sources.md`

阶段 2 的开发记忆和学习笔记：

- `task_plan.md`
- `findings.md`
- `progress.md`
- `docs/stage2_learning_notes.md`

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
63 passed
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
- source collection 资料发现与过滤

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
```

说明：当前向量检索使用 deterministic embedding，主要用于稳定开发和自动化测试，不代表真实语义 embedding 的最终效果。后续接入真实 embedding 模型或混合检索后，应继续复用同一评测集对比。

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
      documents.py
      health.py
      search.py
    core/
      config.py
    db/
      models.py
      repositories.py
      session.py
    schemas/
      document.py
      health.py
      search.py
    services/
      ingestion/
      retrieval/
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
