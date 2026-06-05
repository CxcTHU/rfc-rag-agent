---
stage: 阶段 3
category: 测试与验证
location: data/evaluation/chat_queries.csv, scripts/evaluate_chat.py, data/evaluation/chat_results.csv
purpose: 用固定问题集验证引用式问答链路
---

# Chat 问答评测

所属阶段：[[阶段 3 - 引用式问答]]
所属分类：[[测试与验证]]
相关位置：`data/evaluation/chat_queries.csv`、`scripts/evaluate_chat.py`、`data/evaluation/chat_results.csv`

## 它解决什么问题

RAG 问答不能只靠手动提问判断效果。需要固定问题集，每次修改后都能重复验证答案、来源、引用和拒答。

## 在本项目中怎么用

`chat_queries.csv` 定义问题和期望：

- 是否应该拒答。
- 是否要求 sources。
- 是否要求 citations。
- 期望来源标题或内容词。
- 禁止出现在答案里的硬编词。

`evaluate_chat.py` 调用完整 `CitationAnswerService` 链路，输出 `chat_results.csv`。

## 新词解释

- 评测集：固定的一组测试问题。
- `citations_valid`：引用编号是否能映射到 sources。
- 回归测试：修改代码后重新跑旧测试，确认没有破坏已有能力。
- forbidden_answer_terms：答案里不应该出现的词，用于捕捉明显硬编。

## 为什么这样设计

脚本默认使用 deterministic chat provider，保证评测不依赖真实 API key、网络和模型随机输出。这样阶段 3 的问答链路可以稳定回归。

## 面试可能怎么问

问：你怎么证明问答系统不是 demo？

答：我建立了 chat 评测集和自动评测脚本。指标包括是否返回答案、是否按预期拒答、是否返回 sources、citations 是否有效、期望来源是否命中，以及答案是否包含明显硬编词。

## 你应该怎么回答

我用 `chat_queries.csv` 固定问题，用 `evaluate_chat.py` 执行完整 AnswerService 链路，再输出 `chat_results.csv`。当前 chat evaluation 是 6/6 passed，并且同时回归关键词 15/15、向量 11/15 和全量测试 106 passed。

## 相关双链

- [[阶段 3 - 引用式问答]]
- [[测试与验证]]
- [[检索评测基线]]
