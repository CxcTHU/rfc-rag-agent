---
stage: "阶段 3"
phase: "Phase 1"
status: "已完成"
---

# 阶段 3 Phase 1 - 模型抽象与 Prompt 构造

所属阶段：[[阶段 3 - 引用式问答]]
所属汇报索引：[[阶段 3 Phase 汇报索引]]

## 1. 本 Phase 目标

建立聊天模型调用抽象，并把检索结果整理成大模型可以理解、可引用、可拒答的上下文。

## 2. 本 Phase 完成的主要任务

- 新增 `app/services/generation/chat_model.py`。
- 新增 deterministic provider，用于无外部 key 时稳定测试。
- 新增 OpenAI-compatible provider，为国产大模型 API 预留接入方式。
- 新增 `app/services/generation/prompt_builder.py`。
- 定义带 `[1]`、`[2]` 编号的 context source 和 RAG prompt。
- 在配置中补充聊天模型温度、超时等参数。

## 3. 新增/修改了哪些内容

- 新增 `app/services/generation/__init__.py`。
- 新增 `ChatModelProvider`、`DeterministicChatModelProvider`、`OpenAICompatibleChatModelProvider`。
- 新增 `ContextSource`、`RagPrompt` 和 `build_rag_prompt()`。
- 修改 `.env.example` 和 `app/core/config.py`，加入 chat model 配置。

## 4. 关键代码或模块说明

`ChatModelProvider` 是模型调用入口，业务代码只依赖这个抽象，不直接写死某一家模型厂商。`prompt_builder` 把召回的 chunk 转成编号来源，让回答可以引用 `[1]` 这样的来源编号。

## 5. 遇到的问题与解决方式

问题是当前不一定有可用的大模型 key，如果直接依赖真实模型，测试会不稳定。解决方式是先提供 deterministic provider，让测试和评测可以在本地稳定运行；真实模型通过 OpenAI-compatible provider 后续接入。

## 6. 新词解释

- Provider：提供某种能力的封装层。本项目里 `ChatModelProvider` 负责提供“生成回答”的能力。
- Prompt：发给大模型的指令和上下文。本项目的 prompt 会明确要求“只能基于资料回答，并使用来源编号”。
- Deterministic：确定性的意思。同一个输入会得到稳定输出，适合自动化测试。
- OpenAI-compatible：接口格式兼容 OpenAI 风格，很多国产模型也提供这种调用方式。

## 7. 验证结果

- `tests/test_chat_model_provider.py` 通过。
- `tests/test_prompt_builder.py` 通过。
- 模型抽象和 prompt 构造可以在无真实模型 key 的情况下测试。

## 8. 当前遗留问题

真实模型调用还没有接入生产 key，也没有做流式输出和多轮上下文。

## 9. 下一 Phase 要做什么

进入 Phase 2，把检索、prompt、模型调用、引用提取和拒答判断串成完整回答服务。

## 10. 面试表达

“我把模型调用封装成 provider，是为了避免业务逻辑绑定某一家大模型。prompt builder 则负责把检索片段转成带编号的上下文，让模型回答时可以引用来源，也方便后端校验引用是否合法。”
