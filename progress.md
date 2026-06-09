# Progress Log（阶段 18）

## Session: 2026-06-08

### 阶段启动状态

- 当前阶段：阶段 18，语料扩充与评测/质量体系增强。
- 当前分支：`claude/phase-18-corpus-evaluation-quality`（从含阶段 17 合并的 `main` 创建）。
- Git/tag/main 起点：
  - `phase-17-complete -> 5b5ef02`（阶段 17 最终功能提交，非 merge），是 `main` 祖先。
  - `main` HEAD = `d633b95 Merge phase 17 retrieval architecture upgrade`。
  - 阶段 17 已完成人工核验、提交、打 tag 并合并到 main。未移动任何已有阶段 tag。
- 语料构成（DB 复核）：documents=136（metadata_record=115、open_access_pdf=10、local_file=10、institutional_access_pdf=1）；chunks=997；深度全文≈11。
- 用户决策：语料扩充策略 = 尽力真实下载 + 诚实报数。
- **状态：尚未提交，等待用户人工核验。** 未执行 git add/commit/tag/push 或 PR。

### Phase 0: 阶段启动与规划校准

- Status: complete
- 解决的问题：从阶段 17 完成、提交、tag、合并后的 `main` 起步，把当前线程、分支和规划文件切换到阶段 18。
- 在 RAG 链路中的位置：阶段启动前置工作，确保语料扩充、解析加固、难评测、多配置对比和质量体系增强基于阶段 17 的稳定版本推进。
- 为什么现在做：阶段 17 已确认默认链路 keep_existing_hybrid 且评测集饱和缺区分度；下一步最有价值的是把语料和评测/质量体系做厚，让默认链路决策有真实依据。
- 已完成工作：
  - 阅读 AGENT.MD/README/docs/progress/architecture/data_sources、阶段 17 设计文档与报告、stage17 人工复核 CSV、旧规划文件。
  - 核实 Git/tag/main 起点；确认 `phase-17-complete -> 5b5ef02` 是阶段 17 最终功能提交且为 main 祖先；未移动任何 tag。
  - 从 `main` 创建并切换到 `claude/phase-18-corpus-evaluation-quality`。
  - 用 DB 复核语料构成（136 documents / 997 chunks / 深度全文≈11 / deterministic+jina 双索引）。
  - 确认 gitignore 边界（app.sqlite、fulltext gitignore；metadata_corpus、manifest 已跟踪）。
  - 确认本环境可联网下载真实开放获取 PDF。
  - 用 AskUserQuestion 确认语料扩充策略。
  - 用 Planning with Files 重写阶段 18 task_plan/findings/progress。

### Phase 1: 阶段 18 设计文档

- Status: complete
- 解决的问题：语料扩充、解析加固、难评测、多配置对比、quality gate、报告增强涉及多个模块，先固定设计边界，避免和核心 API 改动混在一起。
- 在 RAG 链路中的位置：开发前的架构设计层，定义语料/评测/质量增强如何进入既有链路且不破坏 API。
- 为什么现在做：阶段 17 已确认默认链路 keep_existing_hybrid 且评测集饱和；阶段 18 必须先说明“扩什么语料、加固什么解析、用什么难评测、怎么决定默认链路、怎么沉淀 quality gate”。
- 完成工作：
  - 新增 `docs/stage18_corpus_evaluation_quality.md`。
  - 明确五配置对比口径、quality gate 维度与状态、`/quality-report` 只读增强边界、数据安全边界和完成标准。
  - 新增 `tests/test_stage18_design.py`。
- 验证结果：`.venv\Scripts\python.exe -m pytest tests\test_stage18_design.py -q` -> `3 passed`。

### Phase 2: PDF 解析加固

- Status: complete
- 解决的问题：PDF 全文 chunk 拿不到真实章节结构（旧解析只有 `## Page N`），跨段证据与章节定位差。
- 在 RAG 链路中的位置：ingestion 解析层，位于 parser 读取之后、cleaner/splitter 之前。
- 为什么现在做：阶段 18 要导入更多深度全文，先把解析做好，新导入的全文才能带上 `heading_path` 并被难评测集利用。
- 完成工作：新增 `app/services/ingestion/pdf_text.py`，接入 `parser.read_pdf_text`；标题层级/表格/断词/公式噪声/页眉页脚清洗；收紧 heading 去公式假阳性。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_pdf_text_structuring.py tests\test_ingestion_parser.py tests\test_ingestion_cleaner.py tests\test_ingestion_splitter.py tests\test_ingestion_service.py -q` -> `26 passed`。
  - 真实 PDF 复核恢复出 Introduction/Theoretical Model/Porous Boxes/Results/Conclusions/References 等章节。

### Phase 3: 语料深度扩充（开放/授权全文导入）

- Status: complete
- 解决的问题：深度全文只有 ~11 篇，115 篇只是题录；难以支撑跨段证据/参数细节问答。
- 在 RAG 链路中的位置：数据采集 + ingestion 层，喂给检索/评测。
- 为什么现在做：阶段 18 难评测集与多配置对比需要更厚的深度全文才有区分度。
- 完成工作：新增 `scripts/expand_open_access_corpus.py`；OpenAlex 发现 866、RFC 相关 90、许可允许 OA 16；真实新导入 5 篇深度全文（137-141）；manifest +5 行；重建双索引；重置并重新 sync source registry。
- 诚实结论：RFC 窄领域开放全文有限，深度全文 11 -> 16（达不到 40–60，按用户决策诚实报数，不造假）；chunks 997 -> 1332。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_expand_open_access_corpus.py -q` -> `4 passed`。
  - DB 复核：documents 141、deep fulltext 16、chunks 1332、deterministic+jina 索引各 1332。
  - source registry：total=125、open_access=15、metadata_only=105、trust=high:125。

### Phase 4 + 5: 难评测集与多配置检索对比

- Status: complete
- 解决的问题：阶段 17 评测集饱和无区分度，无法判断默认链路是否该切换。
- 在 RAG 链路中的位置：检索评测/对比层，喂给 quality gate 与默认链路决策。
- 为什么现在做：语料已扩充、解析已加固；需要更难、有区分度的评测集来量化各检索配置差异。
- 完成工作：新增难评测集 CSV（20 题）+ 多配置评测脚本 + 结构/逻辑测试（6 passed）；产出 hard_results + config_comparison CSV。
- 验证结果（deterministic）：
  - `keyword p@1=1.00(15)`、`hybrid 0.93(14)`、`bm25_rrf 0.93(14)`、`vector 0.73(11)`、`bm25_rrf_context 0.93(14)`；hit@8 全 15/15。
  - `default_chain_decision=keep_existing_hybrid`（bm25_rrf 不优于 hybrid）。
  - refusal 1/5（deterministic 伪影嫌疑，Phase 6 真实 Jina 校验）。
- `.venv\Scripts\python.exe -m pytest tests\test_stage18_hard_set.py -q` -> `6 passed`。

### Phase 6 + 7: quality gate 与 /quality-report 增强

- Status: complete
- 解决的问题：把语料/评测结果沉淀成发布前 quality gate，并让 /quality-report 可只读筛选/排队/导出。
- 在 RAG 链路中的位置：质量评测/报告层，发布前决策依据。
- 完成工作：生成 corpus_stats；新增 quality gate builder（8 维）；真实 Jina 校验；重写 quality_report.html（筛选/队列/导出）；新增只读导出端点 + 样式 + 测试。
- 验证结果：
  - `scripts/build_stage18_quality_report.py` -> `quality gate: review_required/high`（high=2, medium=1, low=5）。
  - `.venv\Scripts\python.exe -m pytest tests\test_stage18_quality_report.py tests\test_frontend_app.py -q` -> `9 passed`。
  - 真实 Jina：vector p@1 0.73 -> 1.00；refusal 仍 1/5（真实风险，已显式阻断）。

### Phase 8: 回归验证

- Status: complete
- 全量测试：`.venv\Scripts\python.exe -m pytest -q` -> **377 passed**（阶段 17 收尾 349；阶段 18 +约 28）。
- 覆盖既有 documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend + 阶段 18 新增测试；无真实 API 依赖。

### Phase 9 + 10: 文档/Obsidian 收尾与人工核验待提交状态

- Status: complete
- 更新入口文档：README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD（修正阶段 17 已合并、阶段 18 在分支开发的滞后状态）。
- Obsidian：新增阶段 18 阶段页、Phase 汇报索引、Phase 0-10 小汇报（各 10 小节）、知识点（PDF 解析加固 / 难评测集与多配置对比 / Quality Gate）；更新阶段汇报索引、阶段索引、首页；修正阶段 17 页状态。obsidian-vault/ 仍被 Git 忽略。
- Git 状态：仅预期的代码/文档/评测 CSV 改动；app.sqlite、data/fulltext/、obsidian-vault/ 均未跟踪；secret 扫描仅命中安全边界文案，无真实密钥。
- **未执行 git add/commit/tag/push 或 PR；等待用户人工核验。**

### Phase 11 增补: CNKI 中文坝工全文本地扩充（待用户转换 CAJ 后统一收尾）

- Status: 部分完成（34 真 PDF 已导入；87 真 CAJ 待用户 CAJViewer 转换）。
- 用户在阶段 18 待核验期间手动下载约 121 篇中文全文（知网 .caj）。
- 做了：中文解析适配（pdf_text.py + 测试）、本地全文批量导入（`scripts/import_papers_corpus.py` 统一导入器，原 `import_cnki_papers.py` 已合并并删除）、导入真 PDF（institutional_access，本地）、重建 deterministic 索引、真 CAJ 列待转换清单。后续用户提供 `papers_NEW` 合法下载全文，入库 298 篇。
- 语料：深度全文 16 -> 42（institutional 1 -> 27、open_access 15）、docs 141 -> 167、chunks 1332 -> 1814。
- 合规：CNKI 全文只存本地 gitignore，不提交/推送；全量 379 passed；无泄露。
- 待办：用户用 CAJViewer 把 87 个 CAJ 转 PDF -> 统一导入 + 重跑难评测/quality gate + 文档/Obsidian 闭环。

## Current Evidence

| Evidence | Result | Status |
|---|---|---|
| Branch | `claude/phase-18-corpus-evaluation-quality` | pass |
| Baseline | from `main` containing `d633b95 Merge phase 17` | pass |
| Phase 17 tag | `phase-17-complete -> 5b5ef02` (functional commit) | pass |
| Phase 17 tag ancestry | ancestor of `main` | pass |
| Tags unmoved | all existing phase tags unchanged | pass |
| Corpus baseline | 136 docs / 997 chunks / deep fulltext ≈ 11 | pass |
| Network for OA PDF | reachable (urllib %PDF-1.5) | pass |
| Planning files | rewritten for stage 18 | pass |
| Submit boundary | no add/commit/tag/push/PR until user approval | pass |

## Test Results

| Test | Expected | Actual | Status |
|---|---|---|---|
| (Phase 0) Git/DB baseline checks | Stage 17 merged & tagged; corpus verified | pass | pass |

## Error Log

| Error | Attempt | Resolution |
|---|---|---|
| README/docs/progress 顶部仍写阶段 17 待核验 | Phase 0 阅读发现过期 | 记为阶段 18 文档校准项，收尾时修正 |

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | Phase 0 complete; planning files written; on stage 18 branch from merged main |
| Where am I going? | 设计文档 -> PDF 解析加固 -> 语料扩充 -> 难评测集 -> 多配置对比 -> quality gate -> /quality-report 增强 -> 回归 -> 文档/Obsidian -> 停在人工核验前 |
| What's the goal? | 完成阶段 18 开发/测试/普通文档/Obsidian 草稿，停在用户人工核验前 |
| What have I learned? | 阶段 17 已合并；评测集饱和无区分度，需难评测集；full-text/DB gitignore，可提交物是管线+manifest+题录+解析器 |
| What have I done? | Git/DB 核对、建分支、确认网络与策略、写 Planning with Files |
