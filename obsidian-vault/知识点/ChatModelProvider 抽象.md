---
stage: 阶段 3
category: 后端工程
location: app/services/generation/chat_model.py
purpose: 解耦聊天模型调用与引用式问答业务逻辑
---

# ChatModelProvider 抽象

所属阶段：[[阶段 3 - 引用式问答]]
所属分类：[[后端工程]]
相关位置：`app/services/generation/chat_model.py`

## 它解决什么问题

引用式问答需要调用聊天模型，但业务代码不应该写死某一家模型 API。否则后续从 deterministic provider 换成国产 OpenAI-compatible 模型时，会影响 AnswerService、API 和测试。

## 在本项目中怎么用

`ChatModelProvider` 统一暴露 `generate(messages)`。当前有两个实现：

- `DeterministicChatModelProvider`：本地稳定测试用。
- `OpenAICompatibleChatModelProvider`：预留真实 `/chat/completions` 调用边界。

`CitationAnswerService` 只依赖 provider 接口，不关心底层模型来自哪里。

## 新词解释

- provider：提供某种能力的适配对象。本项目里 chat provider 提供聊天模型能力。
- deterministic provider：确定性模型实现，相同输入得到稳定输出，用于测试。
- OpenAI-compatible API：兼容 OpenAI 请求格式的模型接口，很多国产大模型也支持。
- temperature：控制模型随机性的参数，RAG 问答通常设低一些。
- timeout：请求超时时间，避免外部模型服务卡住。

## 为什么这样设计

这借鉴了 Quivr 的 `LLMEndpoint` 思路，但本项目第一版更轻量。阶段 3 先保证链路可测试、可替换，不把真实模型接入作为阻塞项。

## 面试可能怎么问

问：为什么不直接在 `/chat` 路由里调用大模型 API？

答：直接调用会让 API 层和模型供应商耦合，难测试、难替换。抽象成 `ChatModelProvider` 后，业务层只知道给 messages、拿 answer，测试可以用 deterministic provider，生产可以换成国产 OpenAI-compatible provider。

## 你应该怎么回答

我把聊天模型调用封装成 `ChatModelProvider`，让 `CitationAnswerService` 不依赖具体模型。这样没有 API key 时也能跑测试，后续接入真实国产模型时只需要替换 provider，不需要改问答链路。

## 相关双链

- [[阶段 3 - 引用式问答]]
- [[后端工程]]
- [[RAG 链路]]
