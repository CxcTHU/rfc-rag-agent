# Task Plan: 阶段 19 - 中文全文文献分析与检索/评测调优

## Goal

在阶段 18「语料扩充与评测/质量体系增强 + 中文全文语料与拒答边界校准」已完成、提交、打 `phase-18-complete` tag（指向最终功能提交 `c56fc62`）并合并到 `main`（合并提交 `4db90c7`）的基础上，完成阶段 19：

1. 用真实 MIMO+Jina agent 对约 340 篇深度全文（含约 298 篇用户合法下载的中文文献）做系统性文献分析探索，定位语料厚薄、回答覆盖度与排序短板。
2. 据此构建独立的中文难评测集（跨段证据 / 易混淆术语 / 参数细节 / 需拒答），不覆盖旧英文 baseline。
3. 在中文难评测集上对照「深度全文加权 / metadata 降权 / topic-anchor」方案，用数据决定是否调整默认链路。
4. （可选）把文献分析综述/研究问题清单沉淀为可复跑、带引用溯源的结构化产物。
5. 全量回归 + 普通文档与 Obsidian 收尾 + 停在用户人工核验前状态。

核心链路：

```text
阶段 18 中文全文语料 + quality gate
-> 真实 MIMO+Jina agent 对中文全文做系统性文献分析
-> 定位语料厚薄、回答覆盖度、中文查询排序短板
-> 中文难评测集（跨段证据、易混淆术语、参数细节、需拒答）
-> 检索排序调优（深度全文加权 / metadata 降权 / topic-anchor 对照）
-> 用数据决定是否调默认链路
-> （可选）文献分析产物结构化沉淀
-> 停在人工核验待提交状态
```

## 边界（不做）

- 不做写入型 Agent 工具。
- 不做复杂 LangGraph workflow。
- 不做登录系统、不做部署优化。
- 不新增爬虫或外部资料来源（已有语料够用）。
- 不让真实 API 成为 CI 或本地全量测试前提（默认 deterministic / mock）。
- HyDE 仍只做离线实验，不进入默认链路或自动回归。
- 默认链路是否切换必须由中文难评测集数据决定，不拍脑袋。
- 保留 deterministic baseline 与 real_config 边界，不用 deterministic 结果掩盖真实 API 失败。
- 不把 API key、Bearer token、供应商原始敏感响应、受限/受版权全文写入 Git、CSV、文档、测试或 Obsidian；中文全文与本地 DB 不入库。

阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。必须等待用户人工核验和明确确认后，才允许进入提交、tag 和 GitHub 推送流程。

## 用户决策（阶段 19 关键）

- 阶段 19 主要面向真实中文研究问题；评测/调优口径围绕「中文深度全文检索」展开。
- Phase 0 第一轮探索：用真实 MIMO+Jina 跑约 8–12 个真实中文研究问题，捕捉真实 API 偶发超时（带重试）、回答覆盖度、来源命中和排序模式，作为 Phase 1/2 的输入。
- Phase 2 调优方案对照三类轻量改动（深度全文加权 / metadata 降权 / topic-anchor），不引入新 reranker；若证据不充分则保持 `keep_existing_hybrid` 并写明阻断理由。

## Current Phase

All phases complete（Phase 0–4 已完成）；阶段 19 停在用户人工核验前，未执行 git add/commit/tag/push 或 PR。

## Phases

### Phase 0: 启动校准 + 第一轮中文文献分析探索

- [x] 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/stage18_corpus_evaluation_quality.md、docs/stage18_followup_chinese_corpus.md、旧 task_plan/findings/progress。
- [x] 确认 Git 起点：`phase-18-complete -> c56fc62`（阶段 18 最终功能提交，**非** merge），是 `main` 祖先；`main` 已含阶段 18 合并 `4db90c7`。不移动任何已有 tag。
- [x] 从含阶段 18 合并的 `main` 创建并切换到 `claude/phase-19-chinese-analysis-retrieval-tuning`。
- [x] 用脚本/DB 核对当前语料构成：documents=465（institutional_access_pdf=325、metadata_record=115、open_access_pdf=15、local_file=10）；chunks=8918；深度全文≈340 篇（institutional+open_access）。embeddings：deterministic(64) + jina(1024) 各 8918。
- [x] 确认 `data/app.sqlite`、`data/fulltext/` 被 gitignore；保留 AGENT.MD 未提交改动到新分支。
- [x] 用 Planning with Files 编写 task_plan.md、findings.md、progress.md。
- [x] 新增 `scripts/explore_chinese_corpus.py`：对若干真实中文研究问题（堆石混凝土自密实流动 / ITZ 强度 / 温控 / 抗冻 / 微观结构 / 综述 / 对比 / 需拒答）跑 hybrid 检索 + Brain answer，记录 top-K 来源 source_type 分布（深度全文 vs 题录）、命中 rank、回答覆盖度（基于期望关键词命中近似）、refused、耗时和真实 API 错误；默认 deterministic，可选 `--real` 走真实 MIMO+Jina；批量 agent 运行带重试。
- [x] 产出 `data/evaluation/stage19_exploration_results.csv`（10 题；deep_top1=0/8、metadata_top1=5/8；errors=0；refusal_matched=9/10）。
- [x] 在 findings.md 中记录探索结论与排序短板根因，作为 Phase 1/2 输入。
- 验证方式：Git 分支/tag 检查、DB 查询、规划文件检查、探索脚本能复跑（deterministic 必跑、真实可选）。
- 文档收尾要求：记录阶段 19 起点、tag/main 状态、语料构成、安全边界和「不提交、不打 tag、不推送」边界。
- Status: complete

### Phase 1: 中文难评测集

- [x] 新增 `docs/stage19_chinese_analysis_retrieval_tuning.md`（设计文档）：目标、输入、Phase 0 实证发现、第一轮文献分析方法、中文难评测集设计、排序调优口径与决策门槛、安全边界和完成标准。
- [x] 新增 `data/evaluation/stage19_chinese_hard_queries.csv`（19 题：5 cross_passage + 5 confusable + 5 parameter_detail + 4 refusal）：包含 query_id、query、difficulty_type、language_type、expected_source_hit、expected_source_type、expected_refused、expected_answer_points、distractor_topics、notes。
- [x] 题目锚定中文深度全文真实存在的研究主题：填充能力、温控、ITZ、抗冻抗渗、工程案例、RFC vs RCC、RFC vs 埋石混凝土、弹性模量 vs 抗压、绝热温升 vs 浇筑温度、劈裂 vs 直接抗拉、SCC 流动度、粒径级配、抗压强度尺寸效应、渗透系数、绝热温升曲线；refusal 含金融/烹饪/新闻 off-topic + 工程责任判断。
- [x] 新增 `tests/test_stage19_chinese_hard_set.py`：CSV schema + 字段完整性 + 四类难度全覆盖 + refusal 占比 ≥ 20% + 设计文档关键字断言。
- 验证方式：设计文档断言测试 + 难评测集结构测试通过。
- 文档收尾要求：在 findings.md 记录设计决策与中文术语词；在 progress.md 记录测试结果。
- Status: complete（11 passed）

### Phase 2: 检索排序调优

- [x] 新增 `scripts/evaluate_stage19_retrieval_tuning.py`：在中文难评测集上对比基线 hybrid 与三种调优配置。
- [x] 调优实现保持轻量、可关闭：`app/services/retrieval/source_type_reweight.py`（纯函数 + `Stage19TuningWeights`，不改 HybridSearchService 默认参数，不改 API schema）。
- [x] 产出 `data/evaluation/stage19_retrieval_tuning_results.csv`（每 config × query 一行，含 decision/next_action）。
- [x] 产出 `data/evaluation/stage19_retrieval_tuning_summary.csv`（每 config 一行汇总，含 distinct_wins_vs_baseline）。
- [x] 默认链路决策：候选三组都满足 Δdeep_top1 ≥ 0.20 且 refusal 不退化，但都未达 Δp@1 ≥ 0.10 门槛 → 结论 `keep_existing_hybrid`，不静默 fallback。
- [x] 补测试 `tests/test_stage19_retrieval_tuning.py`（11 passed）：纯函数 + dataclass 校验 + 不修改输入 + 与设计文档引用一致。
- 验证方式：评测脚本可复跑；CSV 结构 + 决策口径正确；POST /search/hybrid 等 API 不变。
- 文档收尾要求：findings.md 记录三候选数据、根因和遗留风险；progress.md 记录测试结果与决策。
- Status: complete（overall=`keep_existing_hybrid`）

### Phase 3（可选）: 文献分析产物结构化沉淀

- [x] 新增 `docs/stage19_literature_review.md`（面向人读的文献分析快照），整合 Phase 0 探索 + Phase 2 调优数据，按主题速览中文深度全文覆盖度，并给出面试表达与数据安全边界。
- [x] 未新增 `scripts/build_stage19_literature_review.py`：阶段边界裁剪——Phase 0 探索脚本与 Phase 2 调优脚本已经把数据沉淀到 CSV，可被脚本/前端任意复用；再加一个 build 脚本会引入需要 CI 维护的额外代码而无显著新增价值。该决策已写入 findings/progress。
- 验证方式：Markdown 引用的所有 CSV/脚本/测试在仓库中实际存在；阶段 19 现有测试通过。
- 文档收尾要求：作为面向人读的发布前文献快照；与 Phase 0/2 数据一致。
- Status: complete（轻量做法）

### Phase 4: 回归验证 + 文档/Obsidian 收尾 + 停在人工核验前

- [x] 全量测试通过：**408 passed**（阶段 18 收尾为 386，阶段 19 新增 22 个）；无回归。
- [x] 默认 deterministic，无真实 API 依赖；POST /search、/search/vector、/search/hybrid、/chat、/agent/query、GET /quality-report 未被破坏。
- [x] 更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD。
- [x] 补齐 Obsidian：`obsidian-vault/阶段汇报/阶段 19 - 中文全文文献分析与检索调优/`、Phase 汇报索引、Phase 0–4 小汇报（10 项模板）；更新 `阶段汇报索引.md`、`阶段索引.md`、`首页.md`、`obsidian-vault/阶段/阶段 19 - 中文全文文献分析与检索调优.md`。
- [x] 确认 obsidian-vault/ 仍被 Git 忽略；未执行 git add/commit/tag/push/PR。
- [x] 最终汇报：当前分支、主要改动、测试结果、未提交状态、人工核验重点、后续提交/tag/推送建议。
- [x] 密钥/敏感字段扫描：阶段 19 全部产物未泄露 API key / Bearer token / 受版权全文。
- 验证方式：`.venv\Scripts\python.exe -m pytest -q` → 408 passed；Git 状态检查通过；Obsidian 文件已建立且仍 gitignore；阶段 tag 未移动。
- 文档收尾要求：所有普通文档与 Obsidian 同步完成，停在用户人工核验前。
- Status: complete

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `claude/phase-19-chinese-analysis-retrieval-tuning` |
| Previous tags | `phase-18-complete` 及更早 tag 不移动 |
| Baseline | 从含阶段 18 合并的 `main`（含 `4db90c7`）出发 |
| No submit actions | no add/commit/tag/push/PR |
| Design doc | `docs/stage19_chinese_analysis_retrieval_tuning.md` 覆盖目标/输入/方法/难评测/调优/安全/完成标准 |
| Exploration | `scripts/explore_chinese_corpus.py` + `stage19_exploration_results.csv` 真实失败显式记录 |
| Hard eval set | `stage19_chinese_hard_queries.csv` 独立 CSV + 测试，不覆盖旧 baseline |
| Retrieval tuning | source_type_reweight + 多配置对比 + 默认链路数据结论 |
| Tuning results | `stage19_retrieval_tuning_results.csv` + `stage19_retrieval_tuning_summary.csv` |
| API contract | search/vector/hybrid/chat/agent + /quality-report 兼容 |
| Tests | 阶段 19 测试 + 全量测试通过 |
| Docs | README/docs/progress/architecture/data_sources/AGENT 同步 |
| Obsidian | 阶段 19 本地知识库更新且仍被 Git 忽略 |
| Final state | 停在用户人工核验前 |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支 `claude/phase-19-chinese-analysis-retrieval-tuning` | 与阶段 19 目标和 AGENT.MD 路线一致；Claude 用 `claude/` 命名空间 |
| 从含阶段 18 合并的 `main` 创建分支 | `main` 已含 `4db90c7 Merge phase 18`，是正确起点；`phase-18-complete -> c56fc62` 是其祖先 |
| 不移动已有阶段 tag | tag 必须稳定指向各阶段最终功能提交 |
| 真实 agent 探索作为 Phase 0 入口 | 阶段 19 的目标是「真正用起来再调」，必须先用真实链路捕捉真实问题 |
| 调优用 source_type 轻量重权 + topic-anchor，不引入新 reranker | 与阶段 17/18 边界一致，可解释、可关闭 |
| 默认链路是否切换取决于中文难评测集对比 | 不拍脑袋，需可量化证据 |
| Phase 3 设为可选 | 在 Phase 0/2 时间允许时做；不做也写明理由 |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| 深度全文（deep fulltext） | `source_type in (open_access_pdf, institutional_access_pdf)` 的文档；含真实正文与章节结构 |
| 题录（metadata_record） | 仅标题/摘要/元数据的轻量卡片；阶段 19 重点之一是确认这类卡片是否在中文查询下不当压过深度全文 |
| topic-anchor | 主题锚点；中英文术语词表（堆石混凝土/ITZ/freeze-thaw 等），用于轻量重排 |
| source_type 重权 | 召回后按文档类型加权或减权；纯后处理，不改检索算法本身 |
| 中文难评测集 | 跨段证据 / 易混淆术语 / 参数细节 / 需拒答；锚定真实中文全文，让 deep_fulltext_top1_rate 与 metadata_top1_rate 等指标可观察 |
| deep_fulltext_top1_rate | top-1 命中是深度全文的比率；阶段 19 关键调优指标 |
| metadata_top1_rate | top-1 命中是题录卡片的比率；高了说明深度全文被压过，是阶段 19 想下降的指标 |
| literature review snapshot | 文献分析快照；Phase 3 可选产物，作为面向人读的发布前结构化综述 |

## Notes

- 本文件由 Planning with Files 维护，是阶段 19 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 task_plan.md、findings.md、progress.md。
- 阶段 19 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 4 统一补齐。
- 阶段 19 收尾后必须停在用户人工核验前，不提交、不打 tag、不推送。
