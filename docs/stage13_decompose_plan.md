# 阶段 13 预研计划：Decompose 与可解释证据合并

## 目标

阶段 13 建议聚焦 Decompose：把复杂问题拆成多个子 query，分别检索，再合并、去重和排序证据。阶段 12 不实现该能力，只根据质量审阅和回归结果给出后续输入。

## 为什么阶段 13 做 Decompose

阶段 12 质量审阅显示：

- `default_hybrid` 与 `keyword_baseline` 在用户问题集上均为 10/10，说明默认检索链路稳定。
- `vector_only` 仍为 5/10，失败集中在多主题或跨语言术语问题。
- deterministic answer 不能证明真实 Answer Coverage，需要后续在检索证据更完整的基础上做真实模型校准。

复杂问题往往同时包含多个意图，例如：

```text
RFC dam construction 的成本工期和碳排放怎么评估？
```

适合拆成：

```text
成本评估
工期评估
碳排放评估
```

## 建议数据流

```text
original question
-> rule-based decompose
-> sub query 1 / sub query 2 / sub query 3
-> keyword / vector / hybrid retrieval per sub query
-> merge candidates
-> deduplicate by chunk_id
-> rerank by source title, topic terms, source_type, score
-> Brain generate_answer
-> citations and sources keep sub_query provenance
```

## 初始边界

- 子 query 最多 3 个。
- 先做规则式拆解，不接真实模型拆解。
- 只拆明显并列结构，例如“成本、工期和碳排放”“填充性和强度”“冻融和抗渗”。
- 不对 unsupported 问题强行拆解。
- 不绕过 Brain evidence confidence。
- 不替换阶段 11 的词表型 query expansion。

## 证据合并规则建议

| 规则 | 目的 |
|---|---|
| 按 `chunk_id` 去重 | 避免同一片段被多个子 query 重复引用 |
| 保留 `sub_query` 来源 | 回答时能说明哪条证据支持哪个子问题 |
| source_type 排序 | 优先 local/open/institutional 全文，再考虑 metadata |
| 主题词命中加分 | 继续复用阶段 11 `SYNONYM_RULES` |
| both-match bonus | 复用 hybrid 同时命中 keyword/vector 的稳定信号 |

## 优先测试问题

```text
user_mixed_cost_emission
user_cn_colloquial_compactness
user_cn_porosity_compression
user_en_freeze_thaw
user_cn_creep
```

## HyDE 边界

HyDE 可以作为阶段 13 或阶段 14 的离线实验，但不建议进入默认链路：

- HyDE 依赖真实模型，不能作为 deterministic 自动回归前提。
- HyDE 生成的是假想答案，可能引入资料库中不存在的词或事实。
- 本项目强调引用溯源，默认链路应优先使用真实检索证据。

## Context 边界

阶段 12 已完成最小上下文补全：

```text
最近历史问题 + 明确指代词
-> 补全检索 query
```

阶段 13 不应把它扩成长期记忆系统。若需要更多多轮能力，只保留最近 1-3 条问题，并继续把补全后的 query 记录在 workflow step 中。

## 完成标准建议

- Decompose 评测脚本能输出每个子 query 的召回结果。
- 复杂问题的 Answer Coverage 有提升证据。
- `default_hybrid` 不退化。
- `unsupported` 不被误拆解成可回答问题。
- API 旧请求保持兼容。

## 面试表达

阶段 13 我会优先做任务分解，而不是盲目换模型。原因是阶段 12 审阅发现默认 hybrid 能找到可靠来源，但复杂问题的覆盖度仍依赖检索证据是否完整。Decompose 的作用是把一个多意图问题拆成几个子 query，分别召回证据，再去重合并。这样做比直接让模型长回答更可控，也更符合引用式 RAG 的工程原则。
