---
stage: "阶段 0"
status: "已完成"
branch: "codex/phase-0-health-api"
---

# 阶段 0 - FastAPI 工程底座

所属索引：[[阶段索引]]

## 阶段目标

阶段 0 的目标不是做完整 RAG，而是先搭建可持续扩展的后端工程底座：

- FastAPI 应用能启动。
- `GET /health` 能返回稳定 JSON。
- 配置读取集中管理。
- 有最小自动化测试。
- 文档能说明启动、测试和设计原因。

## 相关代码位置

- `app/main.py`
- `app/api/health.py`
- `app/core/config.py`
- `app/schemas/health.py`
- `tests/test_health.py`
- `pyproject.toml`

## 本阶段知识点

- [[FastAPI 应用入口与工厂函数]]
- [[API 路由分层]]
- [[健康检查接口]]
- [[Pydantic 响应模型]]
- [[Pydantic Settings 配置读取]]
- [[pytest 与 TestClient]]
- [[pyproject.toml 项目依赖管理]]
- [[uvicorn 与 ASGI 服务]]
- [[阶段分支开发]]
- [[Obsidian 双链知识库]]
- [[新词解释机制]]

## 面试表达

阶段 0 我没有直接接入大模型，而是先搭建 FastAPI 工程底座。我把应用入口、路由、配置和响应模型分开，保证后续 `documents`、`search`、`chat` 等模块可以按同样结构扩展。我实现了 `/health` 接口，并用自动化测试验证 HTTP 状态码和 JSON 返回结构。这样可以证明服务可启动、接口可访问，也为后续 CI、部署和监控打基础。

## 下一阶段连接

下一步进入 [[阶段 1 - 本地资料导入与关键词检索]]，会开始设计 `documents` 和 `chunks`，并打通资料导入、清洗、切分、保存、搜索这条最小数据链路。
