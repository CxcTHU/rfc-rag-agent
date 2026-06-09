# Task Plan: 阶段 18 - 语料扩充与评测/质量体系增强

## Goal

在阶段 17「检索架构升级」（含 Phase 9 人工复核）已完成、提交、打 `phase-17-complete` tag 并合并到 `main` 的基础上，完成阶段 18：语料深度扩充与评测/质量体系增强。阶段 18 的重点不是再加模型或 Agent，而是：

1. 把深度全文从约 11 篇尽力提升（真实下载开放获取全文，诚实报数，不为凑数造假）。
2. 加固 PDF 解析（标题层级、表格、公式、清洗）。
3. 构建更有区分度的难评测集（跨段证据、易混淆术语、需拒答边界）。
4. 在难评测集上做多配置检索对比（keyword / vector / hybrid / BM25+RRF / context expansion），给出是否调整默认链路的数据结论（含阶段 17 `mesoscopic_modeling` needs_tuning）。
5. 沉淀 quality gate，更新质量汇总/报告，给阶段 17 遗留与真实风险明确闭环状态。
6. 增强 `/quality-report` 只读筛选、风险详情/队列与导出。

核心链路：

```text
阶段17检索结论（keep_existing_hybrid）
-> 语料深度扩充（开放全文导入 + PDF 解析加固）
-> 难评测集构建（跨段证据、易混淆术语、需拒答边界）
-> 多配置检索对比（keyword / vector / hybrid / BM25+RRF / context expansion）
-> 质量门槛与 quality gate 沉淀
-> /quality-report 筛选、风险队列与导出增强
-> 发布前质量结论和下一阶段依据
-> 停在人工核验待提交状态
```

## 边界（不做）

- 不做写入型 Agent 工具。
- 不做复杂 LangGraph workflow。
- 不做登录系统、不做部署优化。
- 不让真实 API 成为 CI 或本地全量测试前提（默认 deterministic / mock）。
- HyDE 仍只做离线实验，不进入默认链路或自动回归。
- `/quality-report` 保持只读优先，不扩成复杂后台。
- 保留 deterministic baseline 与 real_config 边界，不用 deterministic 结果掩盖真实失败。
- 语料扩充只用开放获取或已授权全文，尊重 robots.txt 与网站条款，不绕付费墙/登录/验证码。
- 不把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。

阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。必须等待用户人工核验和明确确认后，才允许进入提交、tag 和 GitHub 推送流程。

## 用户决策（阶段 18 关键）

- 语料深度扩充策略：**尽力真实下载 + 诚实报数**。用 WebSearch/WebFetch 尽可能多地抓取真实开放获取 RFC 及邻近（SCC/坝工）全文，加固解析后导入本地 DB，扩充 manifest/题录/source registry；最终如实报告真实导入篇数（可能 20–40），不为凑 40–60 造假。

## Current Phase

Phase 0-10 全部完成。阶段 18 开发、测试、普通文档与 Obsidian 草稿收尾完毕，停在用户人工核验前（未 add/commit/tag/push）。

## Phases

### Phase 0: 阶段启动与规划校准

- [x] 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md。
- [x] 阅读 docs/stage17_retrieval_architecture_upgrade.md、docs/stage17_retrieval_upgrade_report.md、stage17 人工复核 CSV、旧 task_plan/findings/progress。
- [x] 确认 Git 起点：`phase-17-complete -> 5b5ef02`（阶段 17 最终功能提交，非 merge），是 `main` 祖先；`main` 已含阶段 17 合并 `d633b95`。不移动任何已有 tag。
- [x] 从 `main` 创建并切换到 `claude/phase-18-corpus-evaluation-quality`。
- [x] 用脚本/DB 核对当前语料构成：documents=136（metadata_record=115、open_access_pdf=10、local_file=10、institutional_access_pdf=1）；chunks=997；深度全文≈11。embeddings：deterministic(64) + jina(1024) 各 997。
- [x] 确认 data/app.sqlite、data/fulltext/ 被 gitignore；metadata_corpus（116）、fulltext_manifest.csv 已被 Git 跟踪。
- [x] 确认本环境可联网下载真实开放获取 PDF。
- [x] 用 AskUserQuestion 确认语料扩充策略 = 尽力真实下载 + 诚实报数。
- [x] 用 Planning with Files 编写 task_plan.md、findings.md、progress.md。
- 验证方式：Git 分支/tag 检查、DB 查询、规划文件检查。
- 文档收尾要求：记录阶段 18 起点、tag/main 状态、语料构成、安全边界和“不提交、不打 tag、不推送”边界。
- Status: complete

### Phase 1: 阶段 18 设计文档

- [ ] 新增 `docs/stage18_corpus_evaluation_quality.md`（或拆分多份 docs/stage18_*.md）。
- [ ] 说明目标、输入、语料扩充范围与边界、PDF 解析加固设计、难评测集设计、多配置对比口径、quality gate、报告增强、安全边界和完成标准。
- [x] 补设计文档断言测试。
- 验证方式：文档测试和字段检查。
- 文档收尾要求：在 findings.md 记录设计决策与新词。
- Status: complete（`docs/stage18_corpus_evaluation_quality.md` + `tests/test_stage18_design.py` 3 passed）

### Phase 2: PDF 解析加固

- [x] 复核现有 `app/services/ingestion/parser.py` PDF 解析能力（仅 `## Page N` + 扁平文本）。
- [x] 新增 `app/services/ingestion/pdf_text.py`：标题层级识别（编号/关键词/全大写）、表格行抽取、断词合并、公式/符号清洗、跨页页眉页脚去噪。
- [x] 在 `read_pdf_text` 接入 `structure_pdf_pages`，保持 `## Page N` 与向后兼容。
- [x] 收紧 heading 识别，去除公式假阳性（SCC/SCM、C_III、0 (1 )MKI gs）。
- [x] 补充 deterministic fixture 测试（heading_path 恢复、表格、断词、噪声、重复页眉）。
- 验证方式：parser/cleaner/splitter/ingestion + pdf_text 聚焦测试（26+14 passed）；真实 PDF 复核恢复出 Introduction/Methods/Results/Conclusions/References 等章节。
- 文档收尾要求：记录解析加固取舍与新词。
- Status: complete

### Phase 3: 语料深度扩充（开放/授权全文导入）

- [x] 新增 `scripts/expand_open_access_corpus.py`：OpenAlex 发现 -> RFC 相关性过滤 -> 许可允许 OA 过滤 -> 下载 -> 加固解析导入 -> manifest 标注，可复跑、诚实报数。
- [x] 真实下载并导入：OpenAlex 发现 866，RFC 相关 90，许可允许 OA 带 PDF 16；下载 11，content-hash 去重命中 6，**真实新导入 5 篇深度全文**（docs 137-141）。
- [x] 诚实结论：RFC 是窄领域，开放获取全文有限，达不到 40–60；深度全文 11 -> 16（open_access_pdf 10 -> 15），chunks 997 -> 1332。
- [x] manifest 追加 5 行（cc-by/cc-by-nc 标注），source_candidates.csv 保持不污染；发现集写入独立 `data/metadata/stage18_oa_discovery.csv`。
- [x] 重建 deterministic（64维）与 jina（1024维）向量索引，均覆盖 1332 chunks，deterministic baseline 可复跑。
- [x] 重置并重新同步 source registry：total=125、open_access 10 -> 15、metadata_only 110 -> 105、trust=high:125。
- 验证方式：脚本复跑、DB 复核、source registry 评测、helper 单测（4 passed）。
- 文档收尾要求：在 findings/progress 记录真实导入篇数、来源、权限标注和合规边界。
- Status: complete

### Phase 4: 难评测集构建

- [x] 新增 `data/evaluation/stage18_hard_queries.csv`：20 题（8 跨段 + 7 易混淆 + 5 需拒答），不覆盖旧 baseline。
- [x] 题目锚定真实语料（filling capacity、LBM-DEM、specimen size、temperature field、ITZ、iron ore tailings、seismic、elastic modulus、peridynamics、CFRD false friend 等）。
- [x] 补脚本结构与逻辑测试 `tests/test_stage18_hard_set.py`（6 passed）。
- 验证方式：评测脚本测试、CSV schema 检查。
- 文档收尾要求：记录难评测集设计口径与区分度目标。
- Status: complete

### Phase 5: 多配置检索对比

- [x] 新增 `scripts/evaluate_stage18_hard_set.py`：在难评测集上对比 keyword / vector / hybrid / bm25_rrf / bm25_rrf_context。
- [x] 输出 `stage18_hard_results.csv`（每 config×query 一行）+ `stage18_config_comparison.csv`（per-config 汇总，含 hit@8、rank1、precision@1、mean_rank、distinct_wins）。
- [x] 需拒答查询用默认 Brain（evidence confidence）判断，验证检索升级不绕过拒答。
- [x] 数据结论（deterministic）：hit@8 全部 15/15 饱和，但 rank@1 出现区分度——keyword 15、hybrid 14、bm25_rrf 14、vector 11；bm25_rrf 不优于 hybrid -> `keep_existing_hybrid`（用更有区分度的集证实阶段 17 结论，含 mesoscopic/ITZ 相关 cp_itz_uniaxial 样例）。
- [x] 诚实发现：deterministic 下 5 题需拒答仅 1 题被拒（off-topic 词偶然覆盖），留作 quality gate 风险，并在 Phase 6 用真实 Jina 校验是否为 deterministic 伪影。
- 验证方式：对比脚本测试、复跑、结果合理性检查。
- 文档收尾要求：记录各配置在难评测集上的命中/排序差异和默认链路结论。
- Status: complete

### Phase 6: 质量门槛与 quality gate 沉淀

- [x] 生成 `data/evaluation/stage18_corpus_stats.csv`（深度全文 11->16、chunks 1332）。
- [x] 新增 `scripts/build_stage18_quality_report.py`：8 维 gate（corpus / hard_set / default_chain / real_config / refusal_boundary / stage17_residual / stage16_residual / overall）。
- [x] 真实 Jina 校验：vector p@1 det 0.73 -> real 1.00（真实 embedding 改善排序），但 refusal 真实下仍 1/5 -> 确认拒答弱点非 deterministic 伪影。
- [x] gate 结论：阶段 17 mesoscopic 软退化以 keep_existing_hybrid 数据结论闭环（low）；off-topic 拒答边界=high（明确阻断原因，显式记录，不静默改默认拒答）；阶段 16 ITZ carry-forward（medium）。
- [x] overall quality gate = `review_required/high`，阻断原因写明。
- 验证方式：`scripts/build_stage18_quality_report.py` 复跑 + `tests/test_stage18_quality_report.py`（3 passed）。
- 文档收尾要求：记录 quality gate 口径与当前 gate 状态。
- Status: complete

### Phase 7: /quality-report 筛选、风险队列与导出增强

- [x] 重写 `app/frontend/quality_report.html` 为阶段 18 报告：客户端只读筛选（section/risk）+ 风险队列（high/medium）+ 导出（CSV/JSON Blob 下载）。
- [x] 新增只读导出端点 `GET /quality-report/data.json` 与 `GET /quality-report/export.csv`（FileResponse），不做登录、不写库、不触发真实 API。
- [x] 新增 `.filter-bar`/`risk-high`/`risk-medium` 样式。
- [x] 更新/新增前端测试：`/quality-report` 含筛选/队列/导出元素、data.json 只读且不泄露敏感字段、export.csv 下载。
- 验证方式：`tests/test_frontend_app.py`（6 passed）。
- 文档收尾要求：记录报告增强能力与只读边界。
- Status: complete

### Phase 8: 回归验证

- [x] 全量测试通过：**377 passed**（阶段 17 收尾为 349；阶段 18 新增约 28 个测试）。
- [x] 覆盖 documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend + 阶段 18 新增（pdf_text/expand_corpus/hard_set/quality_report/design）。
- [x] 默认 deterministic，无真实 API 依赖；POST /search、/search/vector、/search/hybrid、/chat、/agent/query、GET /quality-report 未被破坏。
- 验证方式：`.venv\Scripts\python.exe -m pytest -q` -> `377 passed in ~30s`。
- 文档收尾要求：记录测试结果、残余风险和人工核验重点。
- Status: complete

### Phase 9: 文档与 Obsidian 收尾

- [x] 更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD 判断。
- [x] 补齐 Obsidian：阶段 18 阶段页、Phase 汇报索引、Phase 0-10 小汇报（10 小节）、阶段汇报索引、阶段索引、首页、知识点（PDF 解析加固 / 难评测集与多配置对比 / Quality Gate）；并修正阶段 17 页状态为已完成。
- [x] 确认 obsidian-vault/ 仍被 Git 忽略（git check-ignore 通过）。
- 验证方式：文档检查、Obsidian 10 小节检查、Git 忽略检查。
- 文档收尾要求：所有普通文档与 Obsidian 同步完成，但停在人工核验前。
- Status: complete

### Phase 10: 人工核验待提交状态

- [x] 确认未执行 git add/commit/tag/push 或 PR；secret 扫描仅命中安全边界文案，无真实密钥；app.sqlite 与 data/fulltext/ 未被跟踪。
- [x] 最终汇报当前分支、主要改动、测试结果、未提交状态、人工核验重点和后续提交/tag 建议。
- 验证方式：Git 状态检查。
- 文档收尾要求：停在用户人工核验前。
- Status: complete

### Phase 11（增补）: CNKI 中文坝工全文本地扩充

用户在阶段 18 待核验期间手动下载约 121 篇中文全文（`G:/Codex/program/papers`，知网 `.caj`）。决策：扩域到坝工、分主题标注（rfc_core/dam_engineering）；CAJ 转 PDF 由 Claude 尝试。

- [x] 实地检查：121 个 `.caj`；34 个是改名 PDF（有中文文字层），87 个是真 CAJ（HN/KDH/CAJ 头）。
- [x] 诚实结论：本沙箱无 CAJViewer/mutool/PyMuPDF/caj2pdf，**87 个真 CAJ 无法自动转换**，需用户用 CAJViewer 批量导出 PDF；清单写入 `data/fulltext/cnki_caj_pending.txt`（gitignore）。
- [x] 中文解析适配 `pdf_text.py`：加中文章节词（摘要/关键词/引言/结论/参考文献…）、中文数字标题（一、引言）、收紧编号标题（拒测量值/表格行）与全大写碎片（D A M/DO I）；补测试（pdf_text 12 passed）。
- [x] 本地全文批量导入：统一导入器 `scripts/import_papers_corpus.py`（原 `import_cnki_papers.py` 已并入并删除）。只导入真 PDF，可选复制到 gitignore 目录、按标题去重 `(1)`、分主题标注、真 CAJ 列待转换清单；source_type=`institutional_access_pdf`（本地、合规、不提交）。
- [x] 导入 26 篇（8 rfc_core + 18 dam_engineering，34 含 8 重复）；深度全文 16 -> 42（institutional 1 -> 27、open_access 15），docs 141 -> 167、chunks 1332 -> 1814；重建 deterministic 索引覆盖 1814。
- [x] 全量测试 379 passed；data/fulltext、app.sqlite、pending 清单均 gitignore，无全文/PDF 泄露。
- [ ] 待用户用 CAJViewer 把 87 个 CAJ 转 PDF 后，做一次统一导入 + 重跑难评测/quality gate + 文档/Obsidian 收尾（建议作为阶段 19 或阶段 18 收尾的统一闭环，避免半套语料重复评测）。

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `claude/phase-18-corpus-evaluation-quality` |
| Previous tags | `phase-17-complete` 及更早 tag 不移动 |
| Baseline | 从含阶段 17 合并的 `main` 出发 |
| No submit actions | no add/commit/tag/push/PR |
| Design doc | `docs/stage18_*.md` 覆盖目标/语料/解析/难评测/多配置/quality gate/报告/安全/完成标准 |
| PDF parsing | heading 层级、表格、公式、清洗加固 + 测试 |
| Corpus | 深度全文尽力提升，真实导入篇数如实记录；source registry 去重/权限标注；deterministic baseline 可复跑 |
| Hard eval set | 独立难评测集 + 脚本 + 独立 CSV，不覆盖旧 baseline |
| Multi-config | keyword/vector/hybrid/BM25+RRF/context expansion 对比 + 默认链路数据结论 |
| Quality gate | gate 口径沉淀；阶段 17 遗留与真实风险闭环状态明确 |
| Quality report | 只读筛选/风险队列/导出增强，不做登录 |
| API contract | search/vector/hybrid/chat/agent + /quality-report 兼容 |
| Tests | 阶段 18 测试 + 全量测试通过 |
| Docs | README/docs/progress/architecture/data_sources/AGENT 同步 |
| Obsidian | 阶段 18 本地知识库更新且仍被 Git 忽略 |
| Final state | 停在用户人工核验前 |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支 `claude/phase-18-corpus-evaluation-quality` | 与阶段 18 目标和用户要求一致；Claude 用 `claude/` 命名空间 |
| 从含阶段 17 合并的 `main` 创建分支 | `main` 已含 `d633b95 Merge phase 17`，是正确起点 |
| 不移动已有阶段 tag | tag 必须稳定指向各阶段最终功能提交 |
| 语料扩充用真实下载 + 诚实报数 | 用户明确选择；数据完整性优先，不为凑数造假 |
| 全文/DB 不提交，靠可复跑导入管线 | full-text 与 *.sqlite 已 gitignore，受版权与数据安全约束 |
| 默认链路是否切换取决于难评测集对比 | 阶段 17 评测集 hit 饱和无区分度，需难评测集才能决策 |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| heading hierarchy（标题层级） | PDF/文档中“一级标题 -> 二级标题”的结构；解析时保留进 `heading_path`，让 chunk 知道自己属于哪一节 |
| table extraction（表格抽取） | 把 PDF 里以空格/列对齐的表格行识别成结构化文本，避免被切碎 |
| hard eval set（难评测集） | 比旧 baseline 更难、有区分度的评测题，覆盖跨段证据、易混淆术语、需拒答边界 |
| quality gate（质量门槛） | 阶段质量闸口，规定何时可进下一阶段、何时必须人工复核或阻断 |
| risk queue（风险队列） | 把高/中风险样例集中排队展示，方便人工逐条复核 |
| RRF | Reciprocal Rank Fusion，倒数排名融合；用排名而非原始分数融合 BM25 与 vector |
| context expansion（上下文扩展） | 命中核心 chunk 后拉取相邻 chunk 帮助回答，引用仍指向核心 chunk |

## Notes

- 本文件由 Planning with Files 维护，是阶段 18 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 task_plan.md、findings.md、progress.md。
- 阶段 18 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 9 统一补齐。
- 阶段 18 收尾后必须停在用户人工核验前，不提交、不打 tag、不推送。
