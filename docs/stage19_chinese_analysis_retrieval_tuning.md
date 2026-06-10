# 阶段 19 设计：中文全文文献分析与检索/评测调优

## 目标

阶段 18 已把约 340 篇深度全文（含 ~298 篇用户合法下载的中文文献 + 15 篇 OA + 1 篇 CNKI 机构授权）入库，拒答边界已校准（off-topic 主题门 `has_topic_anchor`），quality gate 收口。阶段 19 不再加模型/语料，而是把 RAG 系统**真正"用起来"**：用真实 MIMO+Jina 的 agent 对中文全文做系统性文献分析，把分析中暴露的检索短板，转成可量化的评测改进。

核心链路：

```text
阶段 18 中文全文语料 + quality gate
-> Phase 0 真实/确定性 agent 探索中文研究问题
-> 定位语料厚薄、回答覆盖度、中文查询排序短板
-> Phase 1 中文难评测集（跨段证据 / 易混淆术语 / 参数细节 / 需拒答）
-> Phase 2 检索排序调优（深度全文加权 / metadata 降权 / topic-anchor 对照）
-> 用数据决定是否调默认链路
-> (Phase 3 可选) 文献分析产物结构化沉淀
-> Phase 4 回归 + 文档/Obsidian 收尾 + 停在人工核验待提交状态
```

## 阶段输入

阶段 19 复用并承接以下产物：

```text
app/services/retrieval/{keyword_search,vector_search,hybrid_search}.py
app/services/retrieval/{bm25_search,rrf_fusion,context_expansion,decompose}.py
app/services/brain/{service,workflow,config}.py
app/services/generation/chat_model.py
app/services/ingestion/{parser,cleaner,splitter,pdf_text}.py
app/api/search.py / app/api/chat.py / app/api/agent.py
data/app.sqlite（gitignore；465 文档 / 8918 chunks / 深度全文 ≈ 340）
data/evaluation/stage18_hard_queries.csv（英文向旧难评测集，不覆盖）
docs/stage18_corpus_evaluation_quality.md
docs/stage18_followup_chinese_corpus.md
```

阶段 19 新增产物：

```text
docs/stage19_chinese_analysis_retrieval_tuning.md
scripts/explore_chinese_corpus.py
data/evaluation/stage19_exploration_results.csv
data/evaluation/stage19_chinese_hard_queries.csv
scripts/evaluate_stage19_retrieval_tuning.py
data/evaluation/stage19_retrieval_tuning_results.csv
data/evaluation/stage19_retrieval_tuning_summary.csv
app/services/retrieval/source_type_reweight.py
tests/test_stage19_chinese_hard_set.py
tests/test_stage19_retrieval_tuning.py
tests/test_stage19_design.py
```

可选（Phase 3）：

```text
scripts/build_stage19_literature_review.py
data/evaluation/stage19_literature_review.csv
docs/stage19_literature_review.md
```

## 第一轮文献分析方法（Phase 0）

`scripts/explore_chinese_corpus.py`：

- 准备 10 条真实中文研究问题（8 on-topic + 2 需拒答），覆盖：填充能力 / RFC vs RCC / SCC 作用 / ITZ 强度 / 温控 / 抗冻 / 工程案例 / 纤维改性 / 工程责任拒答 / off-topic 拒答。
- 对每条 query：跑 `HybridSearchService.search(top_k=8)` 拿 top-8 候选；用 `BrainService.answer` 拿到 `BrainAnswerResult`（含 refused、citations、retrieval_mode、model_provider）；记录 source_type 分布、深度全文/题录占比、首条深度全文/题录命中名次、回答摘要前 200 字、coverage 关键词命中数、耗时和真实 API 错误。
- 默认 deterministic，可用 `--real` 走 `.env` 配置的真实 MIMO+Jina；真实模式带轻量重试，真实失败显式写入 CSV `error` 字段，不静默掩盖。
- 输出 `data/evaluation/stage19_exploration_results.csv`。

**Phase 0 实证发现（deterministic）**：

| 指标 | 结果 |
|---|---|
| total | 10 |
| refused | 1 |
| refusal_matched | 9/10 |
| on_topic_answered | 8/8 |
| **deep_top1** | **0/8** |
| **metadata_top1** | **5/8** |
| errors | 0 |

根因：题录卡片（`metadata_record`，约 115 条）chunks 短而集中，关键词密度高；hybrid 默认 0.7 keyword + 0.3 vector 权重，让题录卡片系统性压过中文深度全文。这是 Phase 2 的核心调优目标。

## 中文难评测集设计（Phase 1）

新增独立 `data/evaluation/stage19_chinese_hard_queries.csv`，**不覆盖**旧 `stage18_hard_queries.csv`（英文 RFC 向）。

四类难度（共 19 题，refusal 占比 ≥ 20%）：

| 难度类型 | 数量 | 说明 |
|---|---|---|
| cross_passage（跨段证据） | 5 | 答案要点分散多段，需要合并证据；锚定中文深度全文 |
| confusable（易混淆术语） | 5 | 区分相近概念（RFC vs RCC、绝热温升 vs 浇筑温度、劈裂 vs 直接抗拉…） |
| parameter_detail（参数细节） | 5 | 配合比、坍落扩展、强度、温升、抗渗系数等数值/范围 |
| refusal（需拒答） | 4 | off-topic（金融/烹饪/新闻） + 工程责任判断 |

字段：

```text
query_id
query
difficulty_type           # cross_passage|confusable|parameter_detail|refusal
language_type             # zh|zh_mixed
expected_source_hit       # 标题/正文关键词分号分隔
expected_source_type      # open_access_pdf|institutional_access_pdf|metadata_record|any
expected_refused          # true|false
expected_answer_points    # 期望回答覆盖的要点关键词分号分隔
distractor_topics         # 干扰主题词；用于检测排序是否被干扰文档骗走
notes
```

设计要求：

- 题目锚定中文深度全文真实存在的研究主题（基于 `data/app.sqlite` 中真实中文文献抽样：填充能力、ITZ、抗冻、温控、工程案例、力学性能、介观模型等）。
- `expected_source_type` 优先要求 `institutional_access_pdf` 或 `open_access_pdf`，用于暴露排序问题；少数概念题可允许 `any`。
- 需拒答题必须真实无依据或超工程责任范围；验证主题门 `has_topic_anchor` 与 evidence confidence 不被检索升级绕过。
- 输出独立 CSV，不动 keyword/vector/hybrid/chat/user_questions 旧结果。

## 检索排序调优口径（Phase 2）

新增 `scripts/evaluate_stage19_retrieval_tuning.py`，在中文难评测集上对比四种配置：

| 配置 | 实现 | 用意 |
|---|---|---|
| `hybrid_baseline` | 当前 `HybridSearchService`（0.7 keyword + 0.3 vector + 0.15 both_match） | 阶段 18 之后的默认链路 baseline |
| `hybrid_fulltext_boost` | 召回 fetch_k 后对 `source_type ∈ {open_access_pdf, institutional_access_pdf}` 的 chunk 加 `+δ` | 验证深度全文加权能否上分 |
| `hybrid_metadata_demote` | 召回 fetch_k 后对 `source_type ∈ {metadata_record, local_file}` 的 chunk 减 `−δ` | 验证题录降权能否上分 |
| `hybrid_topic_anchor_strict` | 在 hybrid 候选中按 `CORE_DOMAIN_TERMS` 命中数额外加权 | 验证主题锚点能否提升中文深度全文命中 |

调优实现保持轻量、可关闭：

- 新增 `app/services/retrieval/source_type_reweight.py`（纯函数）：对召回结果做 source_type 后处理重权；不改 `HybridSearchService` 默认参数；不改 API schema。
- 每种调优配置对应不同 `Stage19TuningWeights` dataclass；评测脚本只在脚本内组合，不切默认链路。
- Phase 2 默认 deterministic 跑得出主结论；真实 Jina 校验作为可选 `--real`，不让真实 API 成为必跑前提。

产出：

- `data/evaluation/stage19_retrieval_tuning_results.csv`（每 config × query 一行）：
  - `query_id, config, hit, rank_before, rank_after, deep_fulltext_in_top8, metadata_in_top8, source_match, refusal_matched, decision, next_action`
- `data/evaluation/stage19_retrieval_tuning_summary.csv`（每 config 一行汇总）：
  - `config, hits, precision_at_1, mean_rank, deep_fulltext_top1_rate, metadata_top1_rate, refusal_accuracy, distinct_wins`

默认链路决策：

- **切默认链路的门槛**：候选配置在中文难评测集上 **precision@1 +≥0.10** 且 **deep_fulltext_top1_rate +≥0.20**，且 refusal_accuracy 不退化（≥ baseline）。
- 若没有任何配置达到门槛，结论 `keep_existing_hybrid`，把建议留作可关闭的工程开关（不改默认）。
- **不静默 fallback 掩盖差异**：配置失败/无索引要显式记录。

## API 与兼容边界

阶段 19 必须保证以下入口不被破坏：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
GET /quality-report
```

默认 Brain hybrid 链路是否切换，**只能由中文难评测集多配置对比的数据结论决定**；无充分证据时保持 `keep_existing_hybrid`。`source_type_reweight` 模块只作为评测脚本可调的纯函数候选，不进默认链路。

## 数据安全边界

- 阶段 19 不新增爬虫或外部资料来源；现有约 340 篇深度全文已足够。
- 用户合法下载的中文全文继续只留在本地（`data/app.sqlite` + `data/raw/` + `data/fulltext/`，均 gitignore），不公开分发、不进 Git。
- 真实 API key / Bearer token / 供应商原始敏感响应 / 受限/受版权全文不写入 Git、CSV、文档、测试或 Obsidian。
- 探索/调优 CSV 只保存脱敏查询、命中、排名、风险判断、来源标题（截取）、回答摘要（≤200 字）；不含 API 原始响应。
- 真实 API 偶发失败必须显式写入 CSV `error` 字段；不静默重试到成功掩盖失败。

## 阶段边界

阶段 19 不做：

- 不做写入型 Agent 工具、不做复杂 LangGraph workflow。
- 不做登录系统、不做部署优化。
- 不新增爬虫或外部资料来源。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 HyDE 接入默认链路或自动回归。
- 不重构 `/quality-report` 报告页（只在收尾时视情判断是否补阶段 19 一行）。

阶段 19 要做：

- 固化阶段 19 设计。
- Phase 0 用真实/确定性 agent 探索中文全文回答覆盖度与排序短板。
- Phase 1 构建中文难评测集。
- Phase 2 在中文难评测集上做 source_type 重权 + topic-anchor 对照，给默认链路数据结论。
- Phase 3（可选）沉淀文献分析快照。
- Phase 4 全量回归 + 文档/Obsidian 收尾，停在用户人工核验前。

## 完成标准

- `docs/stage19_chinese_analysis_retrieval_tuning.md` 存在并覆盖目标、输入、第一轮文献分析方法、中文难评测集设计、调优口径、安全边界和完成标准。
- Phase 0 探索脚本与结果 CSV 存在，真实失败显式记录。
- 中文难评测集独立 CSV + 测试，不覆盖旧 baseline。
- 多配置调优脚本与结果 CSV 存在；source_type_reweight 是纯函数 + 测试。
- 默认链路决策有数据证据；切换或保持都写明理由。
- POST /search、/search/vector、/search/hybrid、/chat、/agent/query、GET /quality-report 不被破坏。
- 阶段 19 测试 + 既有相关测试 + 全量测试通过。
- README、docs/progress、docs/architecture、docs/data_sources、AGENT.MD 判断和 Obsidian 本地知识库完成阶段收尾。
- 最终停在未提交状态，等待用户人工核验。

## 面试表达

阶段 19 我没有继续堆模型或语料，而是把已经入库的约 340 篇中文深度全文**真正用起来**。先用真实/确定性 agent 跑一批真实中文研究问题做文献分析探索，结果直接暴露了一个之前没量化过的真实短板：8 道 on-topic 中没有一题的 top-1 是深度全文，5 题的 top-1 是题录卡片。根因是题录 chunks 短而关键词密度高，hybrid 默认 0.7 keyword + 0.3 vector 让题录系统性压过中文深度全文。

我没有凭直觉调，而是用三步收口：第一，独立构建中文难评测集（跨段证据 / 易混淆术语 / 参数细节 / 需拒答 19 题，不覆盖英文旧 baseline）；第二，把 source_type 重权和 topic-anchor 加权做成纯函数，在评测脚本里对照 baseline；第三，定明确门槛 precision@1 +≥0.10 且 deep_fulltext_top1_rate +≥0.20 且 refusal 不退化才切默认链路。结论由数据决定——切就有证据，不切就 keep_existing_hybrid 写明理由。这种"先用起来 → 暴露真实问题 → 用难评测集量化 → 用纯函数对照 → 用门槛决策"的闭环，是阶段 19 想传达的工程方法。
