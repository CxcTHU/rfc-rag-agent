# 项目进度

## 2026-06-04

当前阶段：阶段 0，FastAPI 工程底座已完成。

已完成：

- 明确项目主题：面向水利工程堆石混凝土技术的 RAG 问答 Agent。
- 编写项目指南 `AGENT.MD`。
- 创建初始项目目录。
- 准备连接 GitHub 仓库。
- 创建阶段 0 开发分支 `codex/phase-0-health-api`。
- 建立 FastAPI 应用入口 `app/main.py`。
- 实现健康检查接口 `GET /health`。
- 建立基础配置读取 `app/core/config.py`。
- 增加健康检查响应模型 `app/schemas/health.py`。
- 增加最小接口测试 `tests/test_health.py`。
- 增加项目依赖与测试配置 `pyproject.toml`。
- 在 `AGENT.MD` 中补充 Obsidian 知识库维护规则。
- 创建 Obsidian 知识库 `obsidian-vault/`。
- 为阶段 0 沉淀知识点笔记，并用双链连接阶段页与分类页。

验证结果：

- `python -m pytest`：1 个测试通过。
- 本地服务验证：`GET http://127.0.0.1:8000/health` 返回 `{"status":"ok","service":"RFC-RAG-Agent","environment":"development"}`。

阶段 0 知识点：

- FastAPI 用来声明 API 应用和路由。
- Pydantic schema 用来约束接口返回结构，避免返回格式随意变化。
- 配置读取集中放在 `app/core/config.py`，避免把环境变量散落在业务代码里。
- 测试使用 `TestClient` 模拟 HTTP 请求，能在不启动真实端口的情况下验证接口行为。
- 健康检查接口是服务可观测性的起点，后续可扩展为数据库、向量库和模型服务状态检查。

Obsidian 知识库已记录：

- `obsidian-vault/阶段/阶段 0 - FastAPI 工程底座.md`
- `obsidian-vault/知识点/FastAPI 应用入口与工厂函数.md`
- `obsidian-vault/知识点/API 路由分层.md`
- `obsidian-vault/知识点/健康检查接口.md`
- `obsidian-vault/知识点/Pydantic 响应模型.md`
- `obsidian-vault/知识点/Pydantic Settings 配置读取.md`
- `obsidian-vault/知识点/pytest 与 TestClient.md`
- `obsidian-vault/知识点/pyproject.toml 项目依赖管理.md`
- `obsidian-vault/知识点/uvicorn 与 ASGI 服务.md`
- `obsidian-vault/知识点/阶段分支开发.md`
- `obsidian-vault/知识点/Obsidian 双链知识库.md`

面试表达：

```text
阶段 0 我没有直接接入大模型，而是先搭建 FastAPI 工程底座。
我把应用入口、路由、配置和响应模型分开，保证后续 documents、search、chat 等模块可以按同样结构扩展。
我实现了 /health 接口，并用自动化测试验证 HTTP 状态码和 JSON 返回结构。
这样可以证明服务可启动、接口可访问，也为后续 CI、部署和监控打基础。
```

下一步：

- 进入阶段 1：本地资料导入与关键词检索。
- 设计 `documents` 与 `chunks` 的 SQLite 表结构。
- 支持导入 Markdown/TXT。
- 完成文本清洗、chunk 切分和关键词检索。
