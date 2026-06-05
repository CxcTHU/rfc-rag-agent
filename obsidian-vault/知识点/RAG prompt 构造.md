---
stage: 阶段 3
category: RAG 链路
location: app/services/generation/prompt_builder.py
purpose: 把检索结果转换成模型可阅读、可引用、可拒答的上下文
---

# RAG prompt 构造

所属阶段：[[阶段 3 - 引用式问答]]
所属分类：[[RAG 链路]]
相关位置：`app/services/generation/prompt_builder.py`

## 它解决什么问题

检索服务返回的是 chunk 列表，但聊天模型需要看到清晰的上下文和回答规则。RAG prompt 构造负责把检索结果变成模型能理解的 system/user messages。

## 在本项目中怎么用

`build_rag_prompt()` 接收用户问题和检索结果，返回 `RagPrompt`：

- `messages`：发给聊天模型的消息。
- `context_text`：格式化后的上下文。
- `sources`：本次回答可引用的来源列表。

默认 prompt 要求模型只基于 context 回答，资料不足时拒答，并提示本系统不能替代工程设计和专家判断。

## 新词解释

- prompt：给模型的指令和资料组合。
- context：本次回答允许使用的资料片段。
- system message：告诉模型整体规则的消息。
- user message：包含用户问题和上下文的消息。
- 上下文截断：限制 chunk 和总上下文长度，避免 prompt 太长。

## 为什么这样设计

如果只是把 chunk 拼成一大段文本，模型很难稳定引用来源，也不方便 API 返回来源映射。用结构化 prompt builder，可以统一编号、统一格式、统一免责声明。

## 面试可能怎么问

问：RAG prompt 里为什么要包含来源编号？

答：来源编号让模型回答时可以引用 `[1]`、`[2]`。系统再用这些编号映射回真实 chunk，保证答案可追溯。

## 你应该怎么回答

我没有直接把检索结果拼给模型，而是用 prompt builder 把每个 chunk 转成带编号的 `ContextSource`。这样模型知道有哪些资料可以用，API 也能把答案里的 `[1]` 映射回真实文档和 chunk。

## 相关双链

- [[阶段 3 - 引用式问答]]
- [[RAG 链路]]
- [[引用来源编号]]
