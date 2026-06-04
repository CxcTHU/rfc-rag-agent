---
stage: "阶段 0"
category: "API 设计"
location: "app/api/health.py"
purpose: "让不同业务接口按模块组织"
---

# API 路由分层

所属阶段：[[阶段 0 - FastAPI 工程底座]]
所属分类：[[API 设计]]
相关位置：`app/api/health.py`

## 它解决什么问题

RAG 系统会逐步出现 `/documents`、`/search`、`/chat`、`/sources` 等接口。如果接口散落在一个文件里，后续难以维护、测试和定位问题。

## 在本项目中怎么用

阶段 0 先创建 `app/api/health.py`，只放健康检查接口。后续会按同样方式新增：

- `documents.py`
- `search.py`
- `chat.py`
- `sources.py`

## 为什么这样设计

路由分层让 API 层只负责 HTTP 请求和响应，不承担文档清洗、检索、模型调用等业务逻辑。后续业务逻辑会放到 service 层。

## 面试可能怎么问

FastAPI 项目里 router 的作用是什么？

## 你应该怎么回答

router 用来把一组相关接口组织在一起。比如本项目把健康检查放在 `health.py`，未来把资料导入放在 `documents.py`，搜索放在 `search.py`。这样 `main.py` 只负责注册路由，业务接口按模块维护，项目规模变大后仍然清楚。

## 相关双链

- [[FastAPI 应用入口与工厂函数]]
- [[健康检查接口]]
- [[阶段 0 - FastAPI 工程底座]]
