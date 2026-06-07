# 阶段 12 质量审阅报告：人工审阅与上下文最小补全前校准

## 目标

阶段 12 在阶段 11 的真实用户问题评测集之上，把人工审阅从“设计好的表”推进到“可用于质量校准的结论”。本报告复核 `data/evaluation/user_question_results.csv` 和 `data/evaluation/user_question_review_samples.csv`，并新增阶段 12 审阅结果：

```text
data/evaluation/stage12_quality_review_results.csv
```

本报告只评估阶段 11 已有评测产物，不新增资料来源，不保存真实 API key，不保存受限全文。

## 审阅对象

阶段 12 抽样覆盖 6 条样例：

| 样例类型 | 目的 |
|---|---|
| default_hybrid 通过样例 | 检查默认链路是否能命中可靠来源 |
| vector_only 失败样例 | 分析 deterministic 向量 baseline 的主题漂移 |
| unsupported 拒答样例 | 确认低证据问题是否正确拒答 |
| 中文口语/工程中文/中英混合 | 检查阶段 11 跨语言 query expansion 是否覆盖真实问法 |

## Rubric

| 维度 | pass | review | fail |
|---|---|---|---|
| Faithfulness | 回答或拒答没有引入来源外事实 | 自动链路看起来可信，但仍需真实回答文本复核 | 出现资料外断言或与来源冲突 |
| Answer Coverage | 覆盖 `expected_answer_points` 的核心技术点 | 命中来源但回答文本未充分展开，需要人工或真实模型复核 | 缺少关键技术点或检索证据明显不足 |
| Citation Quality | 引用编号能映射到支持关键说法的来源 | 有引用但支持关系偏弱或来源主题不完全匹配 | 引用缺失、无法追溯或不支持回答 |

## 审阅结果

阶段 12 审阅结果表显示：

```text
total_samples: 6
faithfulness:
  pass: 4
  review: 2
answer_coverage:
  pass: 1
  review: 3
  fail: 2
citation_quality:
  pass: 4
  review: 2
risk_level:
  low: 1
  medium: 3
  high: 2
```

解释：

- `default_hybrid` 样例的来源命中稳定，适合作为默认线上链路继续保留。
- `keyword_baseline` 在用户问题集上同样是 10/10，说明阶段 11 的词表型 query expansion 对真实问法有效。
- `vector_only` 仍有明显主题漂移，尤其是 freeze-thaw、porosity、compactness、creep、cost/emission 等问题。
- deterministic provider 的回答主要用于稳定回归，不适合证明真实语言表达质量；它能证明引用链路、拒答边界和来源返回稳定，但不能单独证明 Answer Coverage。

## 与阶段 11 自动评测的关系

阶段 11 自动评测结果：

```text
user_question_evaluation: 25/30
  default_hybrid: 10/10
  keyword_baseline: 10/10
  vector_only: 5/10
refusal_matched: 30/30
source_hit_matched: 25/30
```

阶段 12 的审阅结论不是推翻自动评测，而是补足自动评测无法覆盖的质量层：

- 自动评测能判断是否拒答、是否有来源、引用编号是否有效。
- 人工审阅能判断答案是否忠实、是否覆盖核心技术点、引用是否支撑关键说法。

## 风险结论

| 风险 | 证据 | 下一步 |
|---|---|---|
| deterministic answer 覆盖度不足 | 多数回答只是稳定回显问题和来源编号 | 发布前用真实模型或人工答案复核 Answer Coverage |
| vector_only 主题漂移 | 用户问题集中 vector_only 仅 5/10 | 阶段 13 优先做 Decompose、rerank 或真实 embedding 对比 |
| 默认链路依赖 keyword/hybrid 救回 | default_hybrid 和 keyword_baseline 均 10/10 | 保留词表型 query expansion，不隐藏 vector baseline 失败 |
| HyDE 可能污染引用边界 | HyDE 依赖假想答案和真实模型 | 只作为离线实验建议，不进入默认链路或自动回归 |

## 阶段 13 输入

阶段 13 更适合聚焦 Decompose 和可解释 rerank：

```text
复杂问题
-> 拆成 2-3 个子 query
-> 分别检索
-> 合并证据
-> 按 chunk_id 去重
-> 用来源标题、主题词、source_type 和分数重新排序
```

优先失败案例：

- `user_en_freeze_thaw`
- `user_cn_porosity_compression`
- `user_cn_colloquial_compactness`
- `user_cn_creep`
- `user_mixed_cost_emission`

## 边界

- 不新增文献来源。
- 不保存受限全文。
- 不保存 API key。
- 不把 LLM-as-judge 或 HyDE 接入自动回归。
- 继续使用 deterministic provider 做稳定测试。

## 面试表达

阶段 12 我没有只看自动评测通过率，而是把阶段 11 的人工审阅表真正用于质量校准。自动评测能稳定检查拒答、来源命中和引用有效性，但不能充分判断回答是否覆盖技术要点。因此我新增阶段 12 质量审阅结果表和报告，把 Faithfulness、Answer Coverage、Citation Quality 分开评估。结论是默认 hybrid 链路来源命中可靠，但 deterministic 回答不能证明真实表达覆盖度，vector-only 仍有主题漂移，这为后续 Decompose、rerank 和真实 embedding 对比提供了明确输入。
