# Findings & Decisions（阶段 19）

## Requirements

- 用户要求正式进入阶段 19：中文全文文献分析与检索/评测调优。
- 目标分支为 `claude/phase-19-chinese-analysis-retrieval-tuning`。
- 阶段 19 必须从阶段 18 完成、提交、合并到 `main` 并创建 `phase-18-complete` tag 的状态出发。
- 必须确认 `phase-18-complete` 指向阶段 18 最终功能提交 `c56fc62`（**非** merge），不移动已有阶段 tag。
- 阶段 19 开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。
- 阶段 19 不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不新增爬虫或外部资料来源。
- 不让真实 API 成为 CI 或本地全量测试前提；HyDE 仍只做离线实验。
- 默认链路是否切换必须由中文难评测集数据决定。
- 保留 deterministic baseline 与 real_config 边界，不用 deterministic 结果掩盖真实失败。
- 不得把 API key、Bearer token、供应商原始敏感响应、受限/受版权全文写入 Git、CSV、文档、测试或 Obsidian；中文全文与本地 DB 不入库。

## Git / Tag / Main 起点（已核实）

- `phase-18-complete -> c56fc62`（提交信息 `Complete phase 18 corpus expansion, evaluation and quality system`，是阶段 18 最终功能提交，**不是** merge commit）。
- `phase-18-complete` 是 `main` 祖先（已验证 `git merge-base --is-ancestor` 返回真）。
- `main` HEAD = `4db90c7 Merge phase 18 corpus expansion, evaluation and quality system`；其下含 `c56fc62 Complete phase 18 ...`、`d633b95 Merge phase 17 retrieval architecture upgrade`、`5b5ef02 Complete phase 17 ...`。
- 阶段 18 已完成人工核验、提交、打 `phase-18-complete` tag 并合并、推送到 GitHub。
- 已从 `main` 创建并切换到 `claude/phase-19-chinese-analysis-retrieval-tuning`，工作区保留 `M AGENT.MD`（用户在阶段 18 收尾时已写入阶段 19 路线建议，按规则保留不重置）。
- 所有已有阶段 tag（phase-0 ... phase-18-complete）保持不动。

## 当前语料构成（开发前用 DB 复核，2026-06-10）

`data/app.sqlite` 查询结果：

- documents 总数 = **465**：
  - `institutional_access_pdf` = **325**（用户合法下载的中文文献，本地私有，gitignore）
  - `metadata_record` = **115**（仅题录/摘要卡片，无深度全文）
  - `open_access_pdf` = **15**（开放获取全文）
  - `local_file` = **10**（阶段 1 早期 rfc_seed 资料卡）
- chunks 总数 = **8918**。
- 深度全文 ≈ **340 篇**（`institutional_access_pdf` + `open_access_pdf` = 325 + 15）。
- chunk_embeddings：
  - `deterministic / hash-token-v1 / dim=64` 共 8918（默认自动化测试用）
  - `openai-compatible / jina-embeddings-v3 / dim=1024` 共 8918（真实校准 / Phase 0 真实探索用）

## Git 跟踪边界（已核实）

- `data/app.sqlite`：**未跟踪**（gitignore `*.sqlite`）。语料 DB 是本地态。
- `data/fulltext/`、`data/raw/`：**gitignore**。用户合法下载的中文 PDF 与所有 PDF 全文永不提交。
- `data/imports/metadata_corpus/*.md`：**已跟踪**（题录卡片）。
- `obsidian-vault/`：**gitignore**，本地知识库不提交。
- 阶段 19 可提交物：阶段 19 设计文档、新增脚本/测试、评测 CSV（脱敏）、模块代码、入口文档增量。深度全文 DB 增长靠用户本地复跑 `scripts/import_papers_corpus.py` 复现。

## 阶段 18 复核结论（阶段 19 必须承接）

- 阶段 18 已完成：PDF 解析加固、开放获取语料扩充（诚实报数）、难评测集 + 多配置对比、quality gate、`/quality-report` 增强。结论 `default_chain_decision=keep_existing_hybrid`（bm25_rrf 未优于 hybrid）。
- 阶段 18 增量：用户合法下载的中文全文 **298 篇**入库，重建确定性 + 真实 Jina 双索引；off-topic 拒答边界校准闭环（`workflow.py` 主题门 `has_topic_anchor` + `CORE_DOMAIN_TERMS`，off-topic 5/5 拒答、on-topic 8/8 不误拒）。
- 阶段 18 quality gate 已由 high 降为 pass/low（AGENT.MD 阶段 18 段落写明）；全量 386 passed。
- 已知短板（阶段 19 输入）：
  - 中文查询排序：英文题录有时压过中文深度全文（Phase 2 重点）。
  - 真实 API 偶发读超时：批量 agent 运行需重试 / 调长 timeout（建索引已有重试，问答链路可借鉴）。
  - 8 篇扫描件未入库（需 OCR，低优先，已决定放弃）。
  - 旧难评测集（`stage18_hard_queries.csv`）是英文 RFC 向；阶段 19 需要独立的中文难评测集，**不覆盖**旧 baseline。

## Architecture Findings（承接阶段 18）

- 检索服务：
  - `KeywordSearchService`（规则关键词 + 同义词扩展 + 标题/heading/content 加权 + metadata 控制 + 来源均衡）。
  - `VectorSearchService`（余弦相似度 + topic anchor 轻量重排）。
  - `HybridSearchService`（keyword/vector 归一化加权 + both_match bonus，**默认链路**）。
  - 阶段 17 候选：`BM25SearchService`、`RRFHybridSearchService`、`ContextExpansionService`，未替换默认。
- `BrainService` hybrid 路径：判断是否 decompose（`DecomposeRetrievalService`），否则直接 `HybridSearchService`；`/chat` 与 Agent `answer_with_citations` 都复用 Brain。
- `EvidenceConfidence` + 阶段 18 增量主题门 `has_topic_anchor` + `CORE_DOMAIN_TERMS`：在 Brain 生成前判断「检索证据足够 + 同主题」，不足/越界则低证据拒答。阶段 19 调优不得绕过此拒答边界。
- `/quality-report` 是只读静态报告页 + 导出端点，不触发真实 API、不写库；阶段 19 暂不重构该报告。

## /quality-report Findings

- 阶段 19 不重构 `/quality-report`；只在阶段 19 收尾时（Phase 4）判断是否需要补充阶段 19 的 quality summary 行。如需要，新增独立 CSV，不动阶段 16/18 已沉淀汇总。
- 阶段 19 默认链路决策必须在 `docs/stage19_chinese_analysis_retrieval_tuning.md` 与 task_plan 中显式写明，不只藏在 CSV。

## 数据安全边界（阶段 19）

- 不新增爬虫或外部资料来源；现有约 340 篇深度全文足够支撑文献分析与调优。
- 用户合法下载的中文全文继续只留在本地（`data/app.sqlite` + `data/raw/` + `data/fulltext/`，均 gitignore），不公开分发、不进 Git。
- 真实 API key / Bearer token / 供应商原始敏感响应 / 受限全文不写入 Git、CSV、文档、测试或 Obsidian。
- 评测/探索 CSV 只保存脱敏的查询、命中、排名、风险判断和来源标题；回答摘要仅截取前若干字符，且不包含 API 原始响应。
- 真实 API 偶发失败必须显式写入 CSV `error` 字段；不静默重试到成功掩盖失败。

## Technical Decisions

| Decision | Reason |
|---|---|
| 阶段 19 入口先做真实文献分析探索 | 阶段 19 目标是「真正用起来再调」，必须先用真实链路捕捉真实问题 |
| 中文难评测集独立 CSV + 独立脚本 | 不覆盖旧英文 baseline，保留可对比性；旧难评测集是题录时代设计 |
| 调优用 source_type 轻量重权 + topic-anchor | 与阶段 17/18 边界一致，可解释、可关闭、不改检索算法本身 |
| 不引入新 reranker / 不引入复杂 workflow | 与阶段 19 边界一致，保持轻量；先证明排序问题确实存在再考虑重 reranker |
| 默认链路是否切换由中文难评测集对比决定 | 不拍脑袋，需可量化证据；precision@1 +≥0.10 且 deep_fulltext_top1_rate +≥0.20 且 refusal 不退化才切 |
| Phase 3 设为可选 | 文献分析快照是补充产物，不挡 Phase 4 收尾；不做也写明理由 |
| 不重构 /quality-report | 阶段 19 边界不含报告增强；如需更新 quality summary，新增独立行不动既有汇总 |

## Phase Findings

### Phase 0

- 已读 AGENT.MD/README/docs/progress/architecture/data_sources、阶段 18 设计文档 (`docs/stage18_corpus_evaluation_quality.md`)、阶段 18 增量 (`docs/stage18_followup_chinese_corpus.md`)、旧 task_plan/findings/progress。
- 已核实 Git/tag/main 起点（见上）。
- 已从 main 创建阶段 19 分支；保留 AGENT.MD 未提交改动到新分支。
- 已用 DB 复核语料构成（465 文档 / 8918 chunks / 深度全文 ≈ 340 / deterministic + jina 双索引各 8918）。
- 已确认 gitignore 边界与可提交物。
- 已用 Planning with Files 编写阶段 19 task_plan/findings/progress。
- 已新增 `scripts/explore_chinese_corpus.py`（默认 deterministic，可 `--real` 走真实 MIMO+Jina，带重试）。
- 已产出 `data/evaluation/stage19_exploration_results.csv`（10 题：8 on-topic + 2 需拒答）。

**Phase 0 关键发现（deterministic）**：

| 指标 | 结果 | 解读 |
|---|---|---|
| total | 10 | 8 on-topic + 2 refusal_expected |
| refused | 1 | 仅 off-topic 天气题被拒；refusal_mix_design 未拒（命中域词，属 prompt 层议题） |
| refusal_matched | 9/10 | refusal_mix_design 未拒（真实风险，见下） |
| on_topic_answered | 8 | 全部回答（无 evidence confidence 拦截） |
| **deep_top1** | **0/8** | **8 题 on-topic 中无一 top-1 是深度全文** |
| **metadata_top1** | **5/8** | **5 题 top-1 是 metadata_record（题录卡片）** |
| errors | 0 | deterministic 不依赖真实 API |

每题排序细节（rank_first_deep_fulltext / rank_first_metadata）：

| query_id | deep_first | meta_first | 备注 |
|---|---|---|---|
| filling_capacity | 3 | 2 | local_file 抢 top-1，metadata 抢 top-2 |
| rfc_vs_rcc | 7 | 2 | local_file top-1，深度全文被压到第 7 |
| **scc_role** | **0** | **3** | **top-8 无任何深度全文**（最严重） |
| itz_strength | 6 | 1 | 题录抢 top-1 |
| temperature_control | 3 | 1 | 题录抢 top-1 |
| freeze_thaw | 4 | 1 | 题录抢 top-1 |
| engineering_cases | 6 | 1 | 题录抢 top-1 |
| fiber_tailings | 4 | 1 | 题录抢 top-1 |
| refusal_mix_design | 2 | 1 | 命中域词，未拒；属 prompt 层议题 |
| refusal_weather | 1 | 0 | 正确拒答（主题门生效） |

**根因分析**：
- 题录卡片（`metadata_record`，~115 条）chunks 短而集中，标题/摘要关键词密度高，`KeywordSearchService` 评分天然占优；而 hybrid 默认 0.7 keyword + 0.3 vector，所以题录卡片轻易夺 top-1。
- 深度全文 chunk 短篇且分散，单 chunk 的关键词密度通常不如题录；vector 这条通道虽然能召回深度全文，但 0.3 权重压不过 0.7 keyword 通道的题录优势。
- `local_file`（阶段 1 早期 rfc_seed 资料卡，10 篇）也有同样问题：短摘要、关键词密度高。
- `scc_role` 是最严重的样例：top-8 完全没有深度全文，意味着 hybrid fetch_k=24 召回阶段就被题录/local_file 完全占据；这条 query 在阶段 19 后续应当作为 Phase 2 标志性回归样例。
- `refusal_mix_design` 未拒答属于 prompt/responsibility 层议题，**不在阶段 19 检索调优范围内**；记入 findings 作为遗留风险，不强行修复。

**Phase 1/2 输入结论**：

1. 中文难评测集应当显式锚定中文深度全文真实存在的题目（阶段 18 已导入约 298 篇用户合法下载中文文献 + 15 篇 OA），并用 `expected_source_type` 字段要求 top-1 应是深度全文，以此暴露排序问题。
2. Phase 2 调优应当对 `source_type ∈ {open_access_pdf, institutional_access_pdf}` 加权（或对 `metadata_record/local_file` 减权），并对照 topic-anchor 重排；若数据显示能把 `deep_top1` 从 0/8 提到 ≥6/8 且不退化 refusal，就有切默认链路的证据。
3. 真实 Jina embedding 维度更高（1024 vs deterministic 64），可能对中文语义更敏感，把深度全文向量分数提上来；但 Phase 0 在 deterministic 下已暴露根因；真实 Jina 校验留给 Phase 2 在调优配置上跑（可选），不依赖真实 API 才能得出主结论。

### Phase 1

- 新增设计文档 `docs/stage19_chinese_analysis_retrieval_tuning.md`，覆盖目标、Phase 0 实证、中文难评测集设计、四类难度、调优口径、决策门槛、安全边界、完成标准、面试表达。
- 新增独立中文难评测集 `data/evaluation/stage19_chinese_hard_queries.csv`（19 题：5 cross_passage + 5 confusable + 5 parameter_detail + 4 refusal）。题目锚定真实中文深度全文研究主题：填充能力、温控、ITZ、抗冻抗渗、工程案例、RFC vs RCC、RFC vs 埋石、弹性模量 vs 抗压、绝热温升 vs 浇筑温度、劈裂 vs 直接抗拉、SCC 流动度、粒径级配、抗压强度尺寸效应、渗透系数、绝热温升曲线；refusal 含 off-topic（金融/烹饪/新闻）+ 工程责任判断。
- 新增 `tests/test_stage19_chinese_hard_set.py`（11 passed）：CSV schema + 字段完整性 + 四类难度全覆盖 + refusal 占比 ≥ 20% + 设计文档关键字断言。
- 不覆盖旧 `stage18_hard_queries.csv` baseline。

### Phase 2

- 新增 `app/services/retrieval/source_type_reweight.py` 纯函数模块：`Stage19TuningWeights` dataclass + `reweight_results` 后处理重权；4 套默认配置（baseline / fulltext_boost / metadata_demote / topic_anchor_strict）；带 `CORE_DOMAIN_TERMS` 中英文锚点词表（与 Brain workflow 含义对齐但独立维护，避免耦合默认拒答门）。
- 新增 `scripts/evaluate_stage19_retrieval_tuning.py`：在中文难评测集上对照四种配置，非拒答题用 `HybridSearchService(fetch_k=24)` 召回 + 重权 + top-K=8 评测，拒答题用 `BrainService.answer` 验证拒答；输出 `stage19_retrieval_tuning_results.csv`（每 config × query 一行）+ `stage19_retrieval_tuning_summary.csv`（每 config 一行汇总）。
- 新增 `tests/test_stage19_retrieval_tuning.py`（11 passed）：rejecting 负权重、dedup 锚点命中、不修改输入、上限 cap、ankor 不会无关引入加分、设计文档引用一致。

**Phase 2 关键证据（deterministic）**：

| config | precision@1 | deep_fulltext_top1_rate | metadata_top1_rate | refusal_accuracy | distinct_wins_vs_baseline | decision |
|---|---|---|---|---|---|---|
| hybrid_baseline | 0.400 | **0.000** | **1.000** | 0.750 | 0 | baseline |
| hybrid_fulltext_boost | 0.333 | 0.533 | 0.467 | 0.750 | 5 | keep_existing_hybrid |
| hybrid_metadata_demote | 0.333 | 0.533 | 0.467 | 0.750 | 5 | keep_existing_hybrid |
| **hybrid_topic_anchor_strict** | 0.200 | **0.733** | **0.267** | 0.750 | 5 | keep_existing_hybrid |

**Phase 2 数据观察与诚实结论**：

1. **baseline 强力印证排序短板**：15 题非拒答题里 deep_top1=0.0、meta_top1=1.0（100% top-1 都是题录卡片）；这是阶段 18 之后未被量化的真实缺陷。
2. **三候选都显著拉升深度全文 top-1 占比**：`topic_anchor_strict` 最高（0.000 → 0.733，+0.733），`fulltext_boost` / `metadata_demote` 0.000 → 0.533（+0.533）。所有候选都符合 Δdeep_top1 ≥ 0.20 门槛。
3. **但 precision@1 不升反降**：baseline 0.40 → 候选 0.20–0.33；门槛 Δp@1 ≥ 0.10 不满足。
4. **根因分析（不掩盖）**：`expected_source_hit` 用关键词列表判 hit，而题录卡片标题/摘要正好高密度包含这些主题关键词（卡片本身就是按主题组织的），baseline 把题录推 top-1 就近似 "hit"；切深度全文后语义更精准，但深度全文 chunk 的标题/局部文本不一定包含期望关键词的精确字面。这暴露了 hit 判定规则对这种语料的偏向，未来可考虑用 `expected_answer_points` 在答案级别 ratio 判定，或用真实 Jina 重跑校验。
5. **refusal 没退化**：四配置 refusal_accuracy 一致 0.75，4 题里 3 正确拒答；剩 1 题 `cn_hq_refusal_engineering_responsibility` 命中域词后未被默认拒答门挡住（属 prompt 层议题，不在阶段 19 检索调优范围内，记入遗留风险）。
6. **默认链路决策（数据驱动）**：严格门槛（Δp@1 ≥ 0.10 且 Δdeep_top1 ≥ 0.20 且 refusal 不退化）下，**`keep_existing_hybrid`**——Δdeep_top1 都达标但 Δp@1 都不达标，按口径**不切换**默认链路。
7. **可被采用的工程结论**：三候选作为**可配置开关**保留在 `source_type_reweight.py`，已经能让深度全文 top-1 占比从 0.00 提到 0.73（topic_anchor_strict）。后续若优化 hit 判定（基于答案级 ratio 或真实 Jina）能让 Δp@1 通过门槛，可再次审视切换。
8. **真实 Jina 校验（可选）**：评测脚本支持 `--real`；deterministic 已足以暴露排序短板与候选效果，主结论不依赖真实 API。

### Phase 2 决策表

| 候选配置 | 是否达 Δp@1 ≥ 0.10 | 是否达 Δdeep_top1 ≥ 0.20 | refusal 不退化 | 最终决策 |
|---|---|---|---|---|
| hybrid_fulltext_boost | 否 (−0.067) | 是 (+0.533) | 是 | keep_existing_hybrid |
| hybrid_metadata_demote | 否 (−0.067) | 是 (+0.533) | 是 | keep_existing_hybrid |
| hybrid_topic_anchor_strict | 否 (−0.200) | 是 (+0.733) | 是 | keep_existing_hybrid |

整体结论 `overall=keep_existing_hybrid`，与阶段 17/18 保持一致；阶段 19 的贡献是**首次用真实数据量化中文查询 metadata vs deep_fulltext 的排序短板**，并把三个候选作为可配置开关纳入 `source_type_reweight` 模块，留作后续阶段切换的依据。

## Term Explanations

| Term | Meaning in this project |
|---|---|
| institutional_access_pdf | 受机构授权或用户合法下载的本地私有全文；只存本地 gitignore 目录，绝不公开分发 |
| open_access_pdf | 许可允许的开放获取全文；可正常入 DB 和评测 |
| metadata_record | 仅题录/摘要的文档类型；只有标题、作者、摘要等元数据 |
| 主题门 has_topic_anchor | 阶段 18 增量在 `workflow.py` 新增的拒答闸口；查询必须命中 `CORE_DOMAIN_TERMS` 才认为同主题 |
| deep_fulltext_top1_rate | top-1 命中是深度全文的比率；阶段 19 中文查询期望该指标上升 |
| metadata_top1_rate | top-1 命中是题录卡片的比率；阶段 19 中文查询期望该指标下降 |
| source_type reweight | 召回结果按 source_type 加权或减权的纯后处理函数；可解释、可关闭 |
| topic-anchor strict | 在 hybrid 候选中根据 CORE_DOMAIN_TERMS 命中数额外加分的可解释重排 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| `M AGENT.MD` 未提交改动随分支跟随 | 用户在阶段 18 收尾时已写入阶段 19 路线 | 按 AGENT.MD 规则保留；阶段 19 收尾时再视情况一并更新 |
| 真实 API 偶发读超时 | 阶段 18 增量记录在 `docs/stage18_followup_chinese_corpus.md` | 探索脚本必须带重试与显式 error 字段，不静默掩盖 |

## Resources

- `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`
- `docs/stage18_corpus_evaluation_quality.md`、`docs/stage18_followup_chinese_corpus.md`
- `data/evaluation/stage18_hard_queries.csv`、`stage18_config_comparison.csv`
- `app/services/ingestion/pdf_text.py`、`parser.py`、`cleaner.py`、`splitter.py`
- `app/services/retrieval/{keyword_search,vector_search,hybrid_search,bm25_search,rrf_fusion,context_expansion,decompose}.py`
- `app/services/brain/service.py`、`app/services/brain/workflow.py`、`app/api/search.py`、`app/schemas/search.py`
- `scripts/import_papers_corpus.py`、`scripts/build_vector_index.py`、`scripts/evaluate_*.py`
