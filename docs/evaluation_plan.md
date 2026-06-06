# 阶段 6 评测计划

## 目标

阶段 6 的目标不是简单让某个查询结果看起来更好，而是建立一套可复现的检索与问答质量评测流程。后续每次调整关键词规则、向量检索、混合检索、rerank 或模型配置，都必须能和同一批 baseline 对比。

核心问题：

```text
同一批问题
-> keyword baseline
-> vector baseline
-> hybrid / rerank 优化结果
-> chat 引用式回答结果
-> 指标对比和错误案例分析
```

## 当前数据集

| 数据集 | 路径 | 用途 |
|--------|------|------|
| 关键词/向量查询集 | `data/evaluation/keyword_queries.csv` | 检索评测主数据集，包含 query、top_k、期望标题词、期望正文词和期望 source_type |
| 关键词结果 | `data/evaluation/keyword_results.csv` | 阶段 1 keyword baseline |
| 向量结果 | `data/evaluation/vector_results.csv` | 阶段 2 vector baseline |
| 聊天查询集 | `data/evaluation/chat_queries.csv` | 引用式问答评测主数据集 |
| 聊天结果 | `data/evaluation/chat_results.csv` | 阶段 3 chat baseline |
| 来源指标 | `data/evaluation/source_registry_metrics.csv` | source registry 规模、权限、状态和可信度指标 |

## 核心指标

### Recall@K

是什么：前 K 条检索结果中是否召回了期望资料。

在本项目中怎么计算：如果某条结果同时满足 query 中配置的期望标题词、正文词和 source_type 约束，就记为命中。`hit_rank <= K` 视为该 query 通过。

当前自动化程度：已在 keyword/vector 评测脚本中用 `passed`、`hit_rank`、`result_count` 近似覆盖；阶段 6 后续可把它显式命名为 `recall_at_k`。

面试表达：Recall@K 衡量“资料有没有被召回”，它比只看最终回答更底层，因为回答质量首先取决于检索结果。

### Citation Accuracy

是什么：回答里的引用编号是否能映射到真实返回的来源，并且来源是否符合问题期望。

在本项目中怎么计算：

- `citations_valid=yes`：回答中的 `[1]`、`[2]` 等编号都能对应 `sources`。
- `expected_source_hit=yes`：返回来源里存在期望标题词或正文词。
- 两者都满足时，Citation Accuracy 通过。

当前自动化程度：`scripts/evaluate_chat.py` 已计算 `citations_valid` 和 `expected_source_hit`。

面试表达：Citation Accuracy 不是看回答有没有随便写引用，而是看引用能不能追溯到系统实际检索到的资料片段。

### Faithfulness

是什么：回答是否忠实于检索上下文，不编造资料外事实。

在本项目中怎么计算：当前先用规则近似：

- `forbidden_terms_absent=yes` 表示回答没有出现禁止词。
- deterministic provider 默认回答来源于 source，因此适合作为稳定回归。
- 使用真实模型时，需要增加人工审阅或更严格的事实核查字段。

当前自动化程度：部分自动化。阶段 6 先保持规则指标，同时在错误案例表中记录需要人工判断的忠实度问题。

面试表达：Faithfulness 关注“回答有没有胡说”，是 RAG 项目区别于普通聊天机器人的关键质量指标。

### Answer Coverage

是什么：回答是否覆盖问题需要的关键点。

在本项目中怎么计算：当前先用 query 的期望来源命中和回答返回状态近似：

- `returned_answer=yes`
- `expected_source_hit=yes`
- 对非拒答问题，`source_count > 0`

当前自动化程度：部分自动化。后续可以在 `chat_queries.csv` 中增加 expected_answer_terms 字段。

面试表达：Answer Coverage 不是要求回答越长越好，而是要覆盖问题真正需要的技术点。

### Refusal Quality

是什么：资料不足时是否拒答，资料足够时是否不误拒。

在本项目中怎么计算：

- `expected_refused` 与实际 `refused` 一致。
- out-of-corpus 问题应拒答。
- 有足够资料的问题不应拒答。

当前自动化程度：已在 `scripts/evaluate_chat.py` 中用 `refusal_matched` 覆盖。

面试表达：Refusal Quality 衡量系统是否知道“不知道”，这对工程风险、规范适用和参数建议类问题很重要。

## 评测流程

阶段 6 每次优化都按以下顺序执行：

```text
1. 运行 keyword baseline
2. 运行 vector baseline
3. 生成或更新错误案例分析
4. 实现 hybrid search / rerank 等优化
5. 运行优化后检索评测
6. 运行 chat 评测
7. 汇总优化前后指标
8. 更新 README、docs/progress.md 和 Obsidian
```

建议命令：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_keyword_search.py
.\.venv\Scripts\python.exe scripts\evaluate_vector_search.py
.\.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py
.\.venv\Scripts\python.exe scripts\evaluate_chat.py
.\.venv\Scripts\python.exe scripts\analyze_retrieval_errors.py
```

## 错误案例分析字段

阶段 6 需要新增错误案例分析表，建议路径：

```text
data/evaluation/retrieval_error_cases.csv
```

建议字段：

| 字段 | 含义 |
|------|------|
| query_id | 查询编号 |
| query | 实际检索 query |
| evaluator | keyword、vector、hybrid 或 chat |
| failure_type | 失败类型，例如 no_hit、wrong_topic、low_rank、citation_miss、over_refusal |
| expected_terms | 期望命中的标题或正文词 |
| actual_top_titles | 实际 top results 标题 |
| likely_reason | 失败原因分析 |
| suggested_fix | 建议修复方式 |
| before_status | 优化前状态 |
| after_status | 优化后状态 |

## 阶段 6 完成标准

- `docs/evaluation_plan.md` 已记录指标、数据集、流程和判定标准。
- keyword、vector、chat baseline 已复跑并记录。
- 错误案例分析表已生成。
- 至少实现一种可解释优化方案，例如 hybrid search 或轻量 rerank。
- 优化方案有独立评测结果，并能和 keyword/vector baseline 对比。
- `POST /search`、`POST /search/vector`、`POST /chat` 既有行为不破坏。
- 全量测试通过。
- 阶段 6 文档和 Obsidian 知识库完成收尾。
