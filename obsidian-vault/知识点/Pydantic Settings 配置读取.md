---
stage: "阶段 0"
category: "配置管理"
location: "app/core/config.py"
purpose: "集中读取环境变量和本地配置"
---

# Pydantic Settings 配置读取

所属阶段：[[阶段 0 - FastAPI 工程底座]]
所属分类：[[配置管理]]
相关位置：`app/core/config.py`

## 它解决什么问题

项目会使用数据库地址、模型供应商、API Key、模型名称等配置。如果这些配置散落在业务代码里，会导致修改困难，也容易误提交密钥。

## 在本项目中怎么用

`Settings` 负责读取：

- `APP_ENV`
- `DATABASE_URL`
- `CHAT_MODEL_PROVIDER`
- `CHAT_MODEL_API_KEY`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_API_KEY`

真实密钥只放在本地 `.env`，仓库只保留 `.env.example`。

## 为什么这样设计

集中配置可以让开发、测试、生产环境使用不同配置。`get_settings()` 使用缓存，避免每次请求都重复读取 `.env`。

## 面试可能怎么问

为什么不用代码里写死数据库地址和模型 Key？

## 你应该怎么回答

写死配置会导致安全风险和环境切换困难。本项目把配置集中在 `app/core/config.py`，真实密钥只放本地 `.env`，代码只依赖配置对象。这样后续从 SQLite 换 PostgreSQL，或从一个国产模型换到另一个模型时，业务代码不用大改。

## 相关双链

- [[pyproject.toml 项目依赖管理]]
- [[阶段 0 - FastAPI 工程底座]]
- [[配置管理]]
