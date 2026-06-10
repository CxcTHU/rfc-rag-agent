# 阶段 19 中文全文文献分析快照

> 本快照基于阶段 19 Phase 0 真实/确定性 agent 探索结果（`data/evaluation/stage19_exploration_results.csv`，10 题）与 Phase 2 中文难评测集调优结果（`data/evaluation/stage19_retrieval_tuning_results.csv`、`stage19_retrieval_tuning_summary.csv`，19 题 × 4 配置）。
> 不依赖真实 API 即可复现：所有数据均可通过 `python scripts/explore_chinese_corpus.py` 与 `python scripts/evaluate_stage19_retrieval_tuning.py` 重生成。

## 一、语料概况

| 维度 | 数值 |
|---|---|
| 文档总数 | 465 |
| chunk 总数 | 8918 |
| 深度全文（institutional_access_pdf + open_access_pdf） | ≈ 340 |
| 题录卡片（metadata_record） | 115 |
| 早期资料卡（local_file） | 10 |
| deterministic embedding（dim 64） | 8918 |
| 真实 Jina embedding（jina-embeddings-v3, dim 1024） | 8918 |

中文深度全文覆盖：填充能力、自密实流动、堆石粒径与级配、ITZ、力学性能（抗压/抗拉/弹性模量）、抗冻抗渗、绝热温升、温控防裂、施工技术、工程案例（高拱坝/超高面板坝/水库除险加固）、介观/细观建模、纤维与铁尾矿改性等。

## 二、Phase 0 第一轮探索结论

对 10 道真实中文研究问题（8 on-topic + 2 需拒答）做 RAG agent 系统性探索：

| 指标 | 结果 |
|---|---|
| total | 10 |
| refused | 1 |
| refusal_matched | 9/10 |
| on_topic_answered | 8/8 |
| **deep_top1（top-1 是深度全文的占比）** | **0/8** |
| **metadata_top1（top-1 是题录卡片的占比）** | **5/8** |
| 真实 API errors | 0（deterministic 模式） |

关键发现：

- **题录卡片系统性压过中文深度全文**：8 道 on-topic 中，无一题 top-1 是深度全文；最严重的 `cn_explore_scc_role` top-8 完全没有深度全文。
- 根因：题录 chunks 短而关键词密度高，`KeywordSearchService` 评分天然占优；hybrid 默认 0.7 keyword + 0.3 vector 让题录系统性压过深度全文。
- off-topic 拒答边界（主题门 `has_topic_anchor` + `CORE_DOMAIN_TERMS`）按预期工作：`cn_explore_refusal_weather` 正确拒答。
- 例外：`cn_explore_refusal_mix_design`（"本工程配合比是否符合规范"）命中域词后未被默认拒答门挡住，属 **prompt 层议题**（区分"学习参考" vs "工程责任判断"），**不在阶段 19 检索调优范围内**，记入遗留风险。

## 三、Phase 2 中文难评测集调优结论

19 题中文难评测集（5 cross_passage + 5 confusable + 5 parameter_detail + 4 refusal）对照四种检索后处理配置：

| 配置 | precision@1 | deep_fulltext_top1_rate | metadata_top1_rate | refusal_accuracy | 决策 |
|---|---|---|---|---|---|
| hybrid_baseline | 0.400 | **0.000** | **1.000** | 0.750 | baseline |
| hybrid_fulltext_boost | 0.333 | 0.533 | 0.467 | 0.750 | keep_existing_hybrid |
| hybrid_metadata_demote | 0.333 | 0.533 | 0.467 | 0.750 | keep_existing_hybrid |
| hybrid_topic_anchor_strict | 0.200 | **0.733** | **0.267** | 0.750 | keep_existing_hybrid |

数据观察：

1. **baseline 强力印证 Phase 0 发现**：15 题非拒答题中 deep_top1=0.0，meta_top1=1.0（**100%** top-1 都是题录卡片）。
2. **三候选都显著拉升深度全文 top-1**：`topic_anchor_strict` 把 deep_top1 从 0.000 推到 0.733。
3. **但 precision@1 不升反降**：根因是 `expected_source_hit` 用关键词列表判 hit，题录卡片标题/摘要本就高密度包含主题关键词，baseline 选题录就近似 hit；切深度全文后语义更精准但精确字面命中下降。
4. **严格门槛（Δp@1 ≥ 0.10 且 Δdeep_top1 ≥ 0.20 且 refusal 不退化）下 → keep_existing_hybrid**：三候选都达 Δdeep_top1 ≥ 0.20，refusal 不退化，但 Δp@1 都为负。诚实结论：不切默认链路。
5. **可被采用的工程结论**：三候选作为可配置开关保留在 `app/services/retrieval/source_type_reweight.py`；未来若优化 hit 判定（基于答案级 ratio 或真实 Jina embedding 重跑），让 Δp@1 通过门槛，可再次审视切换。

## 四、按主题的文献覆盖度速览

基于 Phase 0 探索结果（top-8 中真实命中的文档标题摘要），中文深度全文对以下主题有可被引用的覆盖：

| 主题 | 主要中文/英文证据来源类别 |
|---|---|
| 填充能力 / 自密实 | institutional_access_pdf + 1 open_access_pdf（Filling Capacity Evaluation）|
| RFC vs RCC 对比 | institutional_access_pdf 多篇（如 "堆石混凝土与埋石混凝土方案典型对比研究"）|
| ITZ / 界面过渡区 | open_access_pdf（3D mesoscopic、Peridynamics 等）+ institutional_access_pdf（介观/细观）|
| 温控 / 绝热温升 | institutional_access_pdf 多篇（"绝热温升曲线特征"、"温度场"、"分层填充非均质温度"）|
| 抗冻 / 抗渗 | institutional_access_pdf（"抗冻抗渗性能试验"、"渗透系数浅析"）|
| 工程案例 / 坝工 | institutional_access_pdf 大量（围滩、石河、东庄二道坝、湾子寨水库等）|
| 力学性能 | institutional_access_pdf + open_access_pdf（弹性模量、抗压、抗拉、劈裂）|
| 钢纤维 / 铁尾矿改性 | open_access_pdf（Iron Ore Tailings）+ institutional_access_pdf |

## 五、面试表达

阶段 19 我没有继续堆模型或语料，而是把已经入库的约 340 篇中文深度全文真正用起来。第一轮真实/确定性 agent 探索就暴露了一个之前没被量化过的真实排序短板：8 道 on-topic 中文问题里没有一题 top-1 是深度全文，5 题被题录卡片占据。中文难评测集进一步在 15 道非拒答题上把 deep_top1 量化到 0.000，这是阶段 18 之后的真实瓶颈。

调优我没有引入新 reranker，而是用纯函数的 `source_type_reweight` 在 hybrid 候选之后做后处理，对照三种配置（深度全文加权 / metadata 降权 / topic-anchor 加权）。结果是三组都能把 deep_top1 从 0.000 推到 0.53–0.73，但 precision@1 因关键词判定偏向题录而下降，按严格门槛（Δp@1 ≥ 0.10 且 Δdeep_top1 ≥ 0.20 且 refusal 不退化）保持 `keep_existing_hybrid`，并把三候选作为可配置开关留作后续切换依据。这种"先用起来 → 暴露真实问题 → 用难评测集量化 → 用纯函数对照 → 用门槛诚实决策"的闭环是阶段 19 想传达的工程方法。

## 六、相关产物索引

| 类型 | 路径 |
|---|---|
| 设计文档 | `docs/stage19_chinese_analysis_retrieval_tuning.md` |
| 探索脚本 | `scripts/explore_chinese_corpus.py` |
| 探索结果 | `data/evaluation/stage19_exploration_results.csv` |
| 中文难评测集 | `data/evaluation/stage19_chinese_hard_queries.csv` |
| 重权纯函数 | `app/services/retrieval/source_type_reweight.py` |
| 调优评测脚本 | `scripts/evaluate_stage19_retrieval_tuning.py` |
| 调优结果 | `data/evaluation/stage19_retrieval_tuning_results.csv` |
| 调优汇总 | `data/evaluation/stage19_retrieval_tuning_summary.csv` |
| 测试 | `tests/test_stage19_chinese_hard_set.py`、`tests/test_stage19_retrieval_tuning.py` |

## 七、阶段 19 数据安全边界

- 用户合法下载的中文全文只留在本地 `data/raw/` 与 `data/app.sqlite`（均 gitignore），不公开分发、不进 Git。
- 探索/调优 CSV 只保存脱敏查询、命中、排名、风险判断、来源标题（截取）、回答摘要（≤200 字）；不含 API key、Bearer token、供应商原始响应。
- 真实 API 偶发失败必须显式写入 `error` 字段；不静默重试到成功掩盖失败。
- 阶段 19 完成后仍停在用户人工核验前状态，未执行 `git add` / `commit` / `tag` / `push`，不创建 PR。
