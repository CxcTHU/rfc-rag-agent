---
stage: 阶段 3
category: 工程化与可观测性
location: app/db/models.py, app/db/repositories.py, app/services/generation/answer_service.py
purpose: 保存问答链路的关键排查信息
---

# QA 日志与可观测性

所属阶段：[[阶段 3 - 引用式问答]]
所属分类：[[工程化与可观测性]]
相关位置：`app/db/models.py`、`app/db/repositories.py`、`app/services/generation/answer_service.py`

## 它解决什么问题

当用户觉得答案不对、引用奇怪或系统拒答时，需要知道当时召回了哪些 chunk、模型输出了什么、是否触发拒答。没有日志就很难复盘。

## 在本项目中怎么用

阶段 3 新增 `qa_logs` 表，对应 `QuestionAnswerLog`。日志保存：

- question
- answer
- retrieved_chunk_ids
- citations
- model_provider
- model_name
- retrieval_mode
- refused
- refusal_reason
- created_at

`CitationAnswerService` 默认写日志，评测脚本默认关闭日志，避免批量评测污染记录。

## 新词解释

- `qa_logs`：问答日志表。
- `QuestionAnswerLog`：SQLAlchemy 模型，对应 `qa_logs`。
- 可观测性：系统能被排查、复盘和监控的能力。
- raw_response：模型供应商原始响应，本项目不写入日志。

## 为什么这样设计

日志只保存排查需要的安全字段，不保存 API key，也不保存 `raw_response`，避免把供应商 trace 或敏感字段落库。

## 面试可能怎么问

问：你怎么排查 RAG 回答质量问题？

答：我会看 QA 日志，检查问题、答案、召回 chunk、引用编号、检索模式和模型信息，判断问题出在检索、prompt、模型输出还是拒答策略。

## 你应该怎么回答

QA 日志是 RAG 系统可观测性的基础。它不是为了多存数据，而是为了在答案质量异常时能复盘链路。

## 相关双链

- [[阶段 3 - 引用式问答]]
- [[工程化与可观测性]]
- [[拒答机制]]
