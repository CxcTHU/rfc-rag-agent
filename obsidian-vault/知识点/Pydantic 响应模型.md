---
stage: "阶段 0"
category: "API 设计"
location: "app/schemas/health.py"
purpose: "约束接口返回结构"
---

# Pydantic 响应模型

所属阶段：[[阶段 0 - FastAPI 工程底座]]
所属分类：[[API 设计]]
相关位置：`app/schemas/health.py`

## 它解决什么问题

接口如果直接返回随意字典，字段名、类型和结构很容易在迭代中变化。Pydantic 模型用于约束接口输出，让调用方得到稳定结构。

## 在本项目中怎么用

`HealthResponse` 定义了 `/health` 的返回结构：

- `status`
- `service`
- `environment`

`health_check()` 通过 `response_model=HealthResponse` 声明响应模型。

## 为什么这样设计

RAG 系统后续会返回更复杂的数据，例如文档列表、检索片段、引用来源和回答内容。提前建立 schema 层，可以让接口契约更清楚。

## 面试可能怎么问

Pydantic 在 FastAPI 里有什么作用？

## 你应该怎么回答

Pydantic 负责数据校验和序列化。在本项目中，schema 约束接口返回结构，比如 `/health` 必须返回状态、服务名和环境。后续搜索接口会用 schema 约束 query、top_k、chunk、source 等结构，减少前后端对接时的歧义。

## 相关双链

- [[健康检查接口]]
- [[API 路由分层]]
- [[阶段 0 - FastAPI 工程底座]]
