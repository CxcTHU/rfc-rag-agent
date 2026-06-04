---
stage: "阶段 0"
category: "后端工程"
location: "README.md"
purpose: "用 ASGI 服务器运行 FastAPI 应用"
---

# uvicorn 与 ASGI 服务

所属阶段：[[阶段 0 - FastAPI 工程底座]]
所属分类：[[后端工程]]
相关位置：`README.md`

## 它解决什么问题

FastAPI 应用本身只是一个 ASGI 应用对象，需要服务器负责监听端口、接收 HTTP 请求、调用应用并返回响应。

## 在本项目中怎么用

启动命令：

```powershell
python -m uvicorn app.main:app --reload
```

其中：

- `app.main` 表示 Python 模块。
- `app` 表示模块中暴露的 FastAPI 应用对象。
- `--reload` 表示开发时自动重载。

## 为什么这样设计

开发阶段用 Uvicorn 足够轻量。后续部署时，可以继续用 Uvicorn，也可以放到容器、进程管理器或云平台中运行。

## 面试可能怎么问

`uvicorn app.main:app` 里的两个 `app` 分别是什么意思？

## 你应该怎么回答

前面的 `app.main` 是模块路径，表示加载 `app/main.py`；后面的 `app` 是这个模块里创建的 FastAPI 应用对象。Uvicorn 根据这个路径找到 ASGI 应用，然后监听端口处理请求。

## 相关双链

- [[FastAPI 应用入口与工厂函数]]
- [[健康检查接口]]
- [[工程化与可观测性]]
