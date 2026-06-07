# 阶段 13 设计：Decompose 与可解释证据合并

## 目标

阶段 13 聚焦 Decompose：把复杂问题拆成多个子 query，分别检索，再合并、去重和排序证据。阶段 13 的目标不是替换默认 RAG 链路，而是在 Brain 检索阶段增加一条可解释、可回归的证据增强路径。

本阶段继续保留：

- 阶段 11 `SYNONYM_RULES` 词表型 query expansion。
- 阶段 12 `rewrite_query` 最小上下文补全。
- Brain evidence confidence 低证据拒答。
- `default_hybrid`、`keyword_baseline` 和 `vector_only` 的可比较评测口径。

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

## 数据流

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

其中 `rule-based decompose` 是确定性规则，不调用真实模型；`sub_query provenance` 是证据来源记录，说明某条 chunk 是由哪个 sub query 召回的。

## 初始边界

- 子 query 最多 3 个。
- 先做规则式拆解，不接真实模型拆解。
- 只拆明显并列结构，例如“成本、工期和碳排放”“填充性和强度”“冻融和抗渗”。
- 不对 unsupported 问题强行拆解。
- 不绕过 Brain evidence confidence。
- 不替换阶段 11 的词表型 query expansion。
- 不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 的旧请求兼容性。
- 不把 HyDE 接入默认链路或 deterministic 自动回归。

## 拆解规则

阶段 13 先只拆“明显并列主题”。规则按保守顺序运行：

| 规则 | 示例 | 结果 |
|---|---|---|
| 中文顿号、逗号、和、与、以及连接的工程主题 | 成本、工期和碳排放 | 成本评估；工期评估；碳排放评估 |
| 英文 and / or 连接的材料或性能主题 | freeze-thaw and impermeability | freeze-thaw resistance；impermeability |
| 中英混合主题 | RFC dam construction 的成本工期和碳排放怎么评估 | RFC dam construction cost；RFC dam construction schedule；RFC dam construction emission |
| 领域固定短语 | 填充性和强度 | filling performance；strength |

不拆解以下情况：

- 乱字符串或 unsupported 问题，例如 `zqxjvblorptasticprotocol`。
- 只有一个明确主题的问题，例如“什么是堆石混凝土”。
- 指代追问本身；这类问题先由阶段 12 的 context rewrite 补全，再判断是否拆解。
- 拆解后无法形成任何领域主题词的问题。

## 数据结构建议

阶段 13 可以新增轻量 dataclass，避免破坏外部 API schema：

```text
DecomposedQuery
  original_question
  sub_queries
  decomposed: bool
  reason

SubQueryRetrievalResult
  sub_query
  retrieval_mode
  results

MergedEvidence
  result
  sub_queries
  keyword_score
  vector_score
  topic_score
  source_type_score
  both_match
  final_score
  explanation
```

这些结构用于 Brain 内部检索、评测 CSV 和调试说明。对外 `/chat` 和 `/agent/query` 仍返回现有 answer、citations、sources、refused 等字段。

## 证据合并规则建议

| 规则 | 目的 |
|---|---|
| 按 `chunk_id` 去重 | 避免同一片段被多个子 query 重复引用 |
| 保留 `sub_query` 来源 | 回答时能说明哪条证据支持哪个子问题 |
| source_type 排序 | 优先 local/open/institutional 全文，再考虑 metadata |
| 主题词命中加分 | 继续复用阶段 11 `SYNONYM_RULES` |
| both-match bonus | 复用 hybrid 同时命中 keyword/vector 的稳定信号 |

## 可解释 rerank

阶段 13 的 rerank 不使用黑盒模型，先用可解释分数：

```text
final_score =
  normalized_retrieval_score
  + topic_match_bonus
  + source_type_bonus
  + both_match_bonus
  + sub_query_coverage_bonus
```

解释字段至少记录：

- 命中的 sub query。
- 是否 keyword/vector 双路命中。
- 命中的主题词。
- source_type 排序原因。
- 原始 score 和最终 score。

source_type 排序继续复用已有 `source_type_rank()` 的思想：全文、本地资料、开放资料优先；metadata_record 仍可进入结果，但不应因为数量多而淹没更强证据。

## 评测指标

阶段 13 评测重点不只是“有没有回答”，还要记录证据质量：

| 指标 | 目的 |
|---|---|
| decompose_applied | 是否对复杂问题触发拆解 |
| sub_query_count | 子 query 数量，必须小于等于 3 |
| source_hit_matched | 合并后来源是否命中期望主题 |
| refusal_matched | unsupported 是否仍正确拒答 |
| deduplicated_count | 去重前后候选数量变化 |
| provenance_present | 是否记录 sub_query provenance |
| default_hybrid_regressed | 默认链路是否退化 |

## 优先测试问题

```text
user_mixed_cost_emission
user_cn_colloquial_compactness
user_cn_porosity_compression
user_en_freeze_thaw
user_cn_creep
```

这 5 个问题来自 `data/evaluation/user_questions.csv`，覆盖中英混合工程管理、中文口语质量控制、孔隙率抗压、英文冻融耐久和中文徐变长期变形。阶段 13 必须同时保留 `user_unsupported_random` 作为拒答保护样例。

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
- 阶段 13 相关测试覆盖拆解规则、去重、provenance、rerank 解释和拒答边界。
- 全量测试通过。

## 面试表达

阶段 13 我会优先做任务分解，而不是盲目换模型。原因是阶段 12 审阅发现默认 hybrid 能找到可靠来源，但复杂问题的覆盖度仍依赖检索证据是否完整。Decompose 的作用是把一个多意图问题拆成几个子 query，分别召回证据，再去重合并。这样做比直接让模型长回答更可控，也更符合引用式 RAG 的工程原则。
