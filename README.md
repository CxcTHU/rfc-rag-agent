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

阶段 0：FastAPI 工程底座已建立。

当前已经实现：

- FastAPI 应用入口
- `GET /health` 健康检查接口
- 基础配置读取
- 最小自动化测试
- 本地开发依赖配置

## 新线程说明

任何新线程继续本项目时，先阅读：

1. `AGENT.MD`
2. `docs/progress.md`
3. `docs/architecture.md`
4. `docs/data_sources.md`

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

当前测试覆盖：

- FastAPI 应用能被导入
- `/health` 返回 HTTP 200
- `/health` 返回结构化 JSON

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
      health.py
    core/
      config.py
    schemas/
      health.py
  docs/
  tests/
    test_health.py
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
