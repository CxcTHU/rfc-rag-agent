# 阶段 11 真实用户问题评测与离线审阅计划

## 目标

阶段 11 在阶段 10 的稳定 RAG 链路之上，新增真实用户问题评测集，并用跨语言 query expansion 提升中文、英文和中英混合问法的检索质量。本计划说明自动评测、人工审阅抽样和 LLM-as-judge 离线校准之间的分工。

核心链路：

```text
data/evaluation/user_questions.csv
-> scripts/evaluate_user_questions.py
-> data/evaluation/user_question_results.csv
-> data/evaluation/user_question_review_samples.csv
-> 人工审阅或离线 LLM-as-judge 校准
```

## 自动评测范围

`scripts/evaluate_user_questions.py` 默认使用 deterministic provider，不依赖真实 API key，不依赖外部网络，不作为真实模型质量的唯一结论。它用于稳定回归以下内容：

| 指标 | 自动判断方式 | 说明 |
|---|---|---|
| Refusal Quality | `expected_refused` 与 `refused` 是否一致 | 检查该拒答时是否拒答、该回答时是否误拒 |
| Source Hit | 来源标题或正文是否命中期望词 | 近似检查检索是否找到了正确资料 |
| Citation Quality | 引用编号是否能映射到返回来源 | 检查引用是否可追溯 |
| Forbidden Terms | 回答中是否出现禁止词 | 用于 unsupported 问题和低证据拒答边界 |

自动评测输出 `data/evaluation/user_question_results.csv`。该文件可以比较 `default_hybrid`、`keyword_baseline` 和 `vector_only`，用于观察阶段 11 的 query expansion 是否改善真实问法下的检索表现。

## 人工审阅范围

自动规则不能充分判断回答是否覆盖所有技术点，也不能完整判断回答是否忠实于证据。因此阶段 11 新增最小审阅表：

```text
data/evaluation/user_question_review_samples.csv
```

审阅表记录以下质量字段：

| 字段 | 含义 |
|---|---|
| `faithfulness` | 回答是否忠实于检索来源，没有引入资料外事实 |
| `answer_coverage` | 回答是否覆盖 `expected_answer_points` 中的关键点 |
| `citation_quality` | 引用是否能支持回答中的关键说法 |
| `reviewer_notes` | 审阅人记录问题、证据缺口或改进建议 |

人工审阅优先抽样：

- `default_hybrid` 的通过样例，用来确认线上默认链路质量。
- `vector_only` 的失败样例，用来分析 deterministic 向量 baseline 的主题漂移。
- `unsupported` 样例，用来确认低证据拒答边界。
- 中英混合和中文口语样例，用来确认跨语言 query expansion 是否解决真实表达差异。

## LLM-as-judge 离线设计

LLM-as-judge 是指让模型扮演质量裁判，按固定评分说明检查 Faithfulness、Answer Coverage 和 Citation Quality。在本项目中它只用于离线校准或发布前抽检，不进入 CI，不成为自动回归前提。

裁判输入应限制为：

- 用户问题。
- `expected_answer_points`。
- 回答摘要或回答原文。
- 来源标题、引用编号和必要片段摘要。
- 审阅 rubric。

裁判输出应写入审阅表字段，而不是覆盖自动评测结果。真实模型调用需要本地 `.env` 中的模型配置，但文档、CSV、测试和 Obsidian 都不能写入真实 API key。

## Rubric

| 维度 | pass | review | fail |
|---|---|---|---|
| Faithfulness | 回答只基于返回来源 | 有轻微概括，需要人工确认 | 出现资料外断言或错误事实 |
| Answer Coverage | 覆盖核心 expected_answer_points | 覆盖部分要点但不完整 | 缺少关键技术点 |
| Citation Quality | 关键说法能对应引用来源 | 引用存在但支持关系偏弱 | 引用缺失或无法支持回答 |

`review` 表示不能只靠规则判断，建议人工复核或用真实模型离线裁判再次校准。

## 边界

- 不新增资料来源，不修改 `sources/documents/chunks/embeddings` 的语料边界。
- 不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 的 API schema。
- 不让自动测试依赖真实 API key。
- 不把 LLM-as-judge 结果当作 deterministic baseline。
- 不在 CSV 中保存受限全文，只保存问题、来源标题、答案摘要、审阅字段和必要备注。

## 面试表达

阶段 11 把“系统能不能答”推进到“真实用户怎么问时系统答得是否可靠”。我把自动评测和人工审阅分开：自动脚本稳定检查拒答、来源命中和引用有效性，人工或 LLM-as-judge 离线抽样检查 Faithfulness、Answer Coverage 和 Citation Quality。这样既能持续回归，又不会让测试依赖真实模型 API key。
