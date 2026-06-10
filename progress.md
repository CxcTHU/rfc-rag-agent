# Progress Log（阶段 19）

## Session: 2026-06-10

### 阶段启动状态

- 当前阶段：阶段 19，中文全文文献分析与检索/评测调优。
- 当前分支：`claude/phase-19-chinese-analysis-retrieval-tuning`（从含阶段 18 合并的 `main` 创建）。
- Git/tag/main 起点：
  - `phase-18-complete -> c56fc62`（阶段 18 最终功能提交，**非** merge），是 `main` 祖先。
  - `main` HEAD = `4db90c7 Merge phase 18 corpus expansion, evaluation and quality system`。
  - 阶段 18 已完成人工核验、提交、打 tag 并合并、推送到 GitHub。未移动任何已有阶段 tag。
- 语料构成（DB 复核）：documents=465（institutional_access_pdf=325、metadata_record=115、open_access_pdf=15、local_file=10）；chunks=8918；深度全文 ≈ 340。embeddings：deterministic(64) + jina(1024) 各 8918。
- 工作区状态：保留 `M AGENT.MD`（用户在阶段 18 收尾时已写入阶段 19 路线建议）。
- **状态：尚未提交，等待用户人工核验。** 未执行 git add/commit/tag/push 或 PR。

### Phase 0: 启动校准 + 第一轮中文文献分析探索

- Status: in_progress
- 解决的问题：从阶段 18 完成、合并到 `main` 之后起步，把当前线程、分支、规划文件切换到阶段 19；并用真实 MIMO+Jina 探索约 340 篇中文深度全文的回答覆盖度、排序短板和真实 API 行为，作为后续 Phase 的输入。
- 在 RAG 链路中的位置：阶段启动前置 + 真实评测探索层。
- 为什么现在做：阶段 18 已把中文全文入库、拒答边界校准、quality gate 收口；阶段 19 的目标是「真正用起来再调」，必须先用真实链路捕捉真实问题，避免凭直觉拍脑袋调检索。
- 已完成工作：
  - 阅读 AGENT.MD/README/docs/progress/architecture/data_sources、阶段 18 设计文档、阶段 18 增量、旧规划文件。
  - 核实 Git/tag/main 起点；确认 `phase-18-complete -> c56fc62` 是阶段 18 最终功能提交且为 main 祖先；未移动任何 tag。
  - 从 `main` 创建并切换到 `claude/phase-19-chinese-analysis-retrieval-tuning`，保留 `M AGENT.MD` 改动。
  - 用 DB 复核语料构成（465 docs / 8918 chunks / 深度全文 ≈ 340 / deterministic + jina 双索引）。
  - 确认 gitignore 边界（app.sqlite、data/fulltext/、data/raw/、obsidian-vault/ 均 gitignore）。
  - 用 Planning with Files 写阶段 19 task_plan.md / findings.md / progress.md。
- 已完成：
  - 新增 `scripts/explore_chinese_corpus.py`（默认 deterministic，可选 `--real`，带重试）。
  - 产出 `data/evaluation/stage19_exploration_results.csv`（10 题）。
  - findings.md 补 Phase 0 探索结论与排序短板根因。
- Phase 0 关键证据（deterministic）：
  - `total=10 refused=1 (expected=2) refusal_matched=9/10`。
  - `on_topic_answered=8 deep_top1=0 metadata_top1=5`。
  - 8 题 on-topic 全部 top-1 被 `metadata_record` 或 `local_file` 占据；最严重的 `cn_explore_scc_role` 在 top-8 内完全没有深度全文。
  - `errors=0`（deterministic 不依赖真实 API）。
  - 真实 Jina/MIMO 校验作为 Phase 2 可选项，**不依赖真实 API 才能得出 Phase 0 主结论**（排序短板已在 deterministic 下显形）。
- Phase 0 结论：**中文查询排序短板被 Phase 0 真实数据证实**——题录卡片在 hybrid 默认 0.7 keyword + 0.3 vector 权重下系统性压过中文深度全文。这是 Phase 2 的核心调优目标。

### Phase 1: 中文难评测集

- Status: complete
- 解决的问题：旧难评测集（`stage18_hard_queries.csv`）是英文 RFC 向，且 hit@8 已饱和；要量化中文查询的真实排序短板，需要独立的中文难评测集。
- 在 RAG 链路中的位置：评测层；为 Phase 2 检索调优提供量化对照集。
- 完成工作：
  - 新增设计文档 `docs/stage19_chinese_analysis_retrieval_tuning.md`（目标、输入、Phase 0 实证发现、四类难度设计、调优口径、决策门槛、安全边界、完成标准、面试表达）。
  - 新增中文难评测集 `data/evaluation/stage19_chinese_hard_queries.csv`（19 题：5 cross_passage + 5 confusable + 5 parameter_detail + 4 refusal，refusal 占比 21%）；锚定中文深度全文真实存在的主题（填充能力 / ITZ / 温控 / 抗冻 / 力学性能 / 配合比 / 工程案例 / 介观模型 等）。
  - 新增 `tests/test_stage19_chinese_hard_set.py`（CSV schema + 字段完整性 + 四类全覆盖 + refusal 占比 + 设计文档关键字断言）。
- 验证结果：`.venv\Scripts\python.exe -m pytest tests\test_stage19_chinese_hard_set.py -q` → **11 passed**。

### Phase 2: 检索排序调优

- Status: complete
- 解决的问题：Phase 0 已暴露中文查询排序短板（题录卡片系统性压过深度全文）；需要在中文难评测集上对照「深度全文加权 / metadata 降权 / topic-anchor」量化候选效果，用数据决定是否切默认链路。
- 在 RAG 链路中的位置：检索后处理层（reweight 是 hybrid 候选之后的纯函数；不改默认 `HybridSearchService`、Brain、`/chat`、`/agent`）。
- 完成工作：
  - 新增 `app/services/retrieval/source_type_reweight.py`（纯函数 + `Stage19TuningWeights` + 4 套默认配置 + 与 Brain 解耦的 `CORE_DOMAIN_TERMS`）。
  - 新增 `scripts/evaluate_stage19_retrieval_tuning.py`（非拒答题 hybrid+重权评测 + 拒答题 Brain 验证 + 结果/汇总双 CSV + 决策门槛回写）。
  - 新增 `tests/test_stage19_retrieval_tuning.py`（11 passed）：纯函数 + dataclass 校验 + 不修改输入 + 设计文档引用一致。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage19_retrieval_tuning.py -q` → **11 passed**。
  - `.venv\Scripts\python.exe scripts\evaluate_stage19_retrieval_tuning.py` → **overall=keep_existing_hybrid**。
  - 三个候选都把 `deep_fulltext_top1_rate` 从 0.000 拉升到 0.533–0.733，**但 precision@1 不升反降**（baseline 0.40 → 候选 0.20–0.33），未达 Δp@1 ≥ 0.10 门槛。
  - refusal_accuracy 四配置一致 0.75；不退化。
- Phase 2 结论：**`keep_existing_hybrid`**。三候选作为可配置开关保留在 `source_type_reweight.py`，未来若优化 hit 判定（基于答案级 ratio 或真实 Jina）能让 Δp@1 通过门槛，可再次审视切换。详见 findings.md。

### Phase 3（可选）: 文献分析产物结构化沉淀

- Status: complete（轻量做法）
- 解决的问题：让阶段 19 "用起来"的真实分析数据有面向人读的发布前文献快照。
- 在 RAG 链路中的位置：文档/产物收尾层。
- 完成工作：
  - 新增 `docs/stage19_literature_review.md`，按主题速览中文深度全文覆盖度，整合 Phase 0 探索 + Phase 2 调优数据，给出面试表达和数据安全边界。
  - **未新增 build 脚本**：阶段边界裁剪——Phase 0/2 脚本已经把数据沉淀到 CSV，可被任意复用；再加 build 脚本只增加 CI 维护成本而无显著新价值。
- 验证结果：Markdown 引用的所有 CSV/脚本/测试在仓库中实际存在；阶段 19 现有测试通过。

### Phase 4: 回归验证 + 文档/Obsidian 收尾 + 停在人工核验前

- Status: complete
- 解决的问题：把阶段 19 开发结论同步到所有入口文档与 Obsidian 知识库；跑全量测试确认无回归；停在用户人工核验前。
- 在 RAG 链路中的位置：阶段收尾层。
- 完成工作：
  - 全量测试 **408 passed**（阶段 18 收尾 386 → 阶段 19 收尾 408，新增 22 个：11 chinese_hard_set + 11 retrieval_tuning），无回归。
  - 更新 README.md 顶部状态 + 产物清单 + 测试总数 → 408；更新 docs/progress.md 顶部加入"最新状态：2026-06-10 阶段 19"段落；新增 docs/architecture.md "阶段 19" 段落；新增 docs/data_sources.md "阶段 19 产物" 段落；更新 AGENT.MD "下一阶段建议：阶段 19" 为"在分支开发，待人工核验"。
  - 补 Obsidian 阶段 19：`obsidian-vault/阶段汇报/阶段 19 - 中文全文文献分析与检索调优/` 含 Phase 汇报索引 + Phase 0–4 小汇报（10 项模板）；`obsidian-vault/阶段/阶段 19 - 中文全文文献分析与检索调优.md`；更新 `阶段汇报索引.md`、`阶段索引.md`、`首页.md`。
  - 密钥扫描：阶段 19 全部产物无 API key / Bearer token / 受版权全文泄露。
  - `obsidian-vault/`、`data/app.sqlite`、`data/fulltext/`、`data/raw/` 均确认未被 Git 跟踪。
  - 阶段 19 当前**未执行 git add / commit / tag / push 或 PR**；所有已有阶段 tag（phase-0 … phase-18-complete）保持不动。

## 阶段 19 最终汇报（待人工核验）

- **当前分支**：`claude/phase-19-chinese-analysis-retrieval-tuning`（从含阶段 18 合并的 `main` 创建，HEAD = `4db90c7 Merge phase 18`）。
- **主要改动**：
  - 修改：AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、findings.md、progress.md、task_plan.md。
  - 新增：docs/stage19_chinese_analysis_retrieval_tuning.md、docs/stage19_literature_review.md、scripts/explore_chinese_corpus.py、scripts/evaluate_stage19_retrieval_tuning.py、app/services/retrieval/source_type_reweight.py、data/evaluation/stage19_exploration_results.csv、data/evaluation/stage19_chinese_hard_queries.csv、data/evaluation/stage19_retrieval_tuning_results.csv、data/evaluation/stage19_retrieval_tuning_summary.csv、tests/test_stage19_chinese_hard_set.py、tests/test_stage19_retrieval_tuning.py。
  - 本地知识库（不提交 Git）：obsidian-vault 下阶段 19 阶段页 + Phase 0–4 小汇报 + Phase 汇报索引；并更新阶段汇报索引/阶段索引/首页。
- **测试结果**：`.venv\Scripts\python.exe -m pytest -q` → **408 passed in ~32s**。
- **未提交状态**：阶段 19 当前**未执行 git add / commit / tag / push、未创建 PR**；`phase-19-complete` tag 尚未创建。
- **建议人工核验重点**：
  1. 阶段 19 设计文档 `docs/stage19_chinese_analysis_retrieval_tuning.md` 与 Phase 0–2 数据一致。
  2. 探索脚本 `scripts/explore_chinese_corpus.py` 与结果 `stage19_exploration_results.csv`（10 题，deep_top1=0/8、metadata_top1=5/8）。
  3. 中文难评测集 `data/evaluation/stage19_chinese_hard_queries.csv`（19 题，refusal 占比 21%）与对应测试。
  4. 候选重权纯函数 `app/services/retrieval/source_type_reweight.py` 与对应测试。
  5. 调优评测脚本 `scripts/evaluate_stage19_retrieval_tuning.py` 与两份 CSV：`stage19_retrieval_tuning_results.csv` + `stage19_retrieval_tuning_summary.csv`，整体决策 `overall=keep_existing_hybrid`。
  6. 文献分析快照 `docs/stage19_literature_review.md` 与 Phase 0/2 数据一致。
  7. 入口文档同步（README / docs/progress / docs/architecture / docs/data_sources / AGENT.MD）。
  8. Obsidian 阶段 19（仍 gitignore）。
- **后续提交/tag/推送建议**（仅供用户确认后执行）：
  1. `git add` 仅范围内的阶段 19 改动（不要 `-A`/`.`，避免误带本地 DB 与外部文件）。
  2. 创建 `phase-19-complete` tag，指向阶段 19 **最终功能提交**（建议是包含阶段 19 全部代码/脚本/CSV 的最后一个非 merge 提交，沿用阶段 17/18 惯例：tag 不指向 merge）。
  3. 推送分支与 tag 到 GitHub，然后开 PR 合并到 main；合并提交将作为 main 的阶段 19 锚点。
  4. 合并后再更新 README / docs/progress 顶部把"待人工核验"切为"已合并"，与阶段 17/18 收尾经验一致。

## Current Evidence

| Evidence | Result | Status |
|---|---|---|
| Branch | `claude/phase-19-chinese-analysis-retrieval-tuning` | pass |
| Baseline | from `main` containing `4db90c7 Merge phase 18` | pass |
| Phase 18 tag | `phase-18-complete -> c56fc62` (functional commit, not merge) | pass |
| Phase 18 tag ancestry | ancestor of `main` | pass |
| Tags unmoved | all existing phase tags unchanged | pass |
| Corpus baseline | 465 docs / 8918 chunks / deep fulltext ≈ 340 | pass |
| Embeddings | deterministic(64) 8918 + jina-v3(1024) 8918 | pass |
| Planning files | written for stage 19 | pass |
| Submit boundary | no add/commit/tag/push/PR until user approval | pass |

## Test Results

| Test | Expected | Actual | Status |
|---|---|---|---|
| (Phase 0) Git/DB baseline checks | Stage 18 merged & tagged; corpus verified | pass | pass |

## Error Log

| Error | Attempt | Resolution |
|---|---|---|
| (none) | — | — |

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | Phase 0 in progress; planning files written; on stage 19 branch from merged main with phase 18 |
| Where am I going? | Phase 0 文献分析探索 -> Phase 1 中文难评测集 -> Phase 2 检索排序调优 -> Phase 3（可选）文献分析产物 -> Phase 4 回归 + 文档/Obsidian 收尾 + 停人工核验 |
| What's the goal? | 完成阶段 19 开发/测试/普通文档/Obsidian 草稿，停在用户人工核验前 |
| What have I learned? | 阶段 18 已合并；语料已有约 340 深度全文；旧难评测集是英文向，阶段 19 需要独立中文集；中文查询排序可能被 metadata 压过；真实 API 偶发超时需重试 |
| What have I done? | Git/DB 核对、建分支、确认网络与策略、写 Planning with Files |
