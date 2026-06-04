---
stage: "阶段 0"
category: "依赖管理"
location: "pyproject.toml"
purpose: "声明项目依赖、开发依赖和测试配置"
---

# pyproject.toml 项目依赖管理

所属阶段：[[阶段 0 - FastAPI 工程底座]]
所属分类：[[依赖管理]]
相关位置：`pyproject.toml`

## 它解决什么问题

一个 Python 项目需要明确依赖哪些库、支持哪些 Python 版本、测试从哪里发现文件。否则换机器或新线程接手时，很容易出现环境不一致。

## 在本项目中怎么用

`pyproject.toml` 声明了：

- Python 版本要求：`>=3.11`
- 运行依赖：FastAPI、Uvicorn、Pydantic Settings
- 开发依赖：pytest、httpx2
- pytest 配置：测试目录和 Python 路径

## 为什么这样设计

用 `pyproject.toml` 可以把项目元信息、依赖和工具配置放在一个标准文件里。相比只写 `requirements.txt`，它更适合长期维护。

## 面试可能怎么问

为什么使用 `pyproject.toml`，而不是只用 `requirements.txt`？

## 你应该怎么回答

`requirements.txt` 更像安装清单，适合简单脚本；`pyproject.toml` 可以描述项目名称、版本、Python 要求、运行依赖、开发依赖和工具配置。本项目会逐步扩展成完整工程，所以从阶段 0 就使用 `pyproject.toml`。

## 相关双链

- [[Pydantic Settings 配置读取]]
- [[pytest 与 TestClient]]
- [[阶段 0 - FastAPI 工程底座]]
