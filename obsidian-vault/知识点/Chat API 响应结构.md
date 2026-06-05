---
stage: 阶段 3
category: API 设计
location: app/api/chat.py, app/schemas/chat.py
purpose: 提供引用式问答的稳定外部接口
---

# Chat API 响应结构

所属阶段：[[阶段 3 - 引用式问答]]
所属分类：[[API 设计]]
相关位置：`app/api/chat.py`、`app/schemas/chat.py`

## 它解决什么问题

内部 AnswerService 跑通后，需要一个外部入口给前端或调用方使用。`POST /chat` 把内部问答结果映射成稳定的 API 响应。

## 在本项目中怎么用

请求结构 `ChatRequest`：

- `question`
- `top_k`
- `retrieval_mode`
- `min_score`

响应结构 `ChatResponse`：

- `answer`
- `citations`
- `sources`
- `refused`
- `refusal_reason`
- `retrieval_mode`
- `model_provider`
- `model_name`

## 新词解释

- schema：请求或响应的数据结构。
- `ChatSourceItem`：单个来源条目，包含文档、chunk、content 和 score。
- 依赖注入：FastAPI 用 `Depends(...)` 把数据库和 provider 传给路由函数。
- 422：请求校验失败，例如空白问题或非法检索模式。

## 为什么这样设计

API 层保持薄封装，不写检索、prompt 或模型调用细节。这样内部逻辑变化时，对外协议可以保持稳定。

## 面试可能怎么问

问：为什么 chat 接口要返回 sources 和 model 信息？

答：RAG 回答必须可追溯。sources 让用户能核验依据，model_provider 和 model_name 方便排查当前使用的是测试模型还是真实模型。

## 你应该怎么回答

`POST /chat` 不只是返回一段回答，而是返回答案、引用、来源、拒答状态、实际检索模式和模型信息。这样接口对前端友好，也方便后续排查和评测。

## 相关双链

- [[阶段 3 - 引用式问答]]
- [[API 设计]]
- [[后端工程]]
