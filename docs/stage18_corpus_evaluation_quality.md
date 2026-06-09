# 阶段 18 设计：语料扩充与评测/质量体系增强

## 目标

阶段 18 不再新增模型 provider 或 Agent 框架，而是把 RAG 系统的两个真实瓶颈做厚：

1. **语料深度不足**：当前 136 篇文档里有 115 篇只是题录/摘要（`metadata_record`），真正的深度全文只有约 11 篇（`open_access_pdf` 10 + `institutional_access_pdf` 1）。题录只能回答“有哪些研究”，不能支撑跨段证据、参数细节和易混淆术语的引用式问答。
2. **评测集饱和缺区分度**：阶段 17 已用人工复核证明旧 baseline 评测集 hit 已饱和（15/15），导致 BM25+vector RRF 升级“零增益”，并掩盖了 `mesoscopic_modeling` 的排序软退化（rank 2 -> 7）。没有更难、更有区分度的评测集，就无法判断默认链路该不该切换。

因此阶段 18 的核心链路是：

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

## 阶段输入

阶段 18 复用并承接以下产物：

```text
app/services/ingestion/parser.py / cleaner.py / splitter.py / service.py
app/services/retrieval/keyword_search.py / vector_search.py / hybrid_search.py
app/services/retrieval/bm25_search.py / rrf_fusion.py / context_expansion.py / decompose.py
app/services/brain/service.py
app/api/search.py / app/api/frontend.py
app/frontend/quality_report.html
data/fulltext_manifest.csv
data/metadata/rfc_papers_metadata.csv
data/imports/metadata_corpus/*.md
data/evaluation/stage17_retrieval_upgrade_results.csv
data/evaluation/stage17_retrieval_upgrade_manual_review.csv
docs/stage17_retrieval_architecture_upgrade.md
docs/stage17_retrieval_upgrade_report.md
docs/stage16_quality_closure_report.md
```

阶段 18 新增产物（建议）：

```text
docs/stage18_corpus_evaluation_quality.md
app/services/ingestion/pdf_text.py            # PDF 文本结构化与解析加固
scripts/expand_open_access_corpus.py          # 开放获取全文调研/下载/导入管线
data/evaluation/stage18_hard_queries.csv      # 难评测集（输入）
scripts/evaluate_stage18_hard_set.py          # 难评测集多配置对比脚本
data/evaluation/stage18_hard_results.csv      # 难评测集多配置对比结果
data/evaluation/stage18_config_comparison.csv # 各配置命中/排序汇总
scripts/build_stage18_quality_report.py       # quality gate 汇总与报告生成
data/evaluation/stage18_quality_summary.csv   # quality gate 汇总
docs/stage18_quality_report.md                # Markdown 质量报告
app/frontend/quality_report.html              # 增强只读筛选/风险队列/导出
app/api/quality_report.py（如需要）            # 只读导出端点
```

## 语料扩充范围与边界

### 范围

- 优先抓取**真实开放获取**（CC BY / CC BY-NC 等）RFC 全文，以及邻近主题（自密实混凝土 SCC 充填、堆石混凝土坝、大体积混凝土温控）的开放全文。
- 来源优先级：MDPI、Engineering（中国工程院）、Nature/Scientific Reports、Springer 开放卷、ETASR、arXiv、开放会议论文集、高校开放仓储。
- 用 source registry 做 DOI/URL/标题三层去重，标注 `trust_level`、`fulltext_permission`、`status`。
- 同步扩充 `fulltext_manifest.csv`、`rfc_papers_metadata.csv`、题录卡片。

### 边界（合规与数据安全）

- 只用开放获取或已授权全文；**不绕付费墙、登录、验证码**；尊重 robots.txt 与网站条款。
- 受限全文（如 CNKI 机构授权）只留在本地授权环境（`data/fulltext/` 已 gitignore），不公开分发、不进 Git。
- `data/app.sqlite`（`*.sqlite` gitignore）与 `data/fulltext/` 不提交；阶段 18「深度全文 DB 增长」靠**可复跑导入管线**复现，可提交物是解析器、manifest/registry 条目、题录卡片和管线脚本。
- **诚实报数**：RFC 是窄领域，开放全文有限；真实导入篇数（预期 20–40）如实记录，不为凑 40–60 造假。
- 不把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。

## PDF 解析加固设计

当前 `read_pdf_text` 只把每页文本拼成 `## Page N` 块，导致：

- PDF 没有 Markdown 标题，`splitter.find_heading_path` 几乎只能拿到 `Page N`，丢失真实章节结构。
- 跨行连字符（`concre-\nte`）、栏内换行、页眉页脚和参考文献噪声混进正文。
- 表格按列对齐的行被当普通文本，容易被切碎。

阶段 18 新增 `app/services/ingestion/pdf_text.py`，对 pypdf 抽取的原始文本做结构化后处理：

```text
raw page text
-> de-hyphenate（合并行尾连字符断词）
-> 软换行合并（把同段落内的硬换行并成句子）
-> heading 识别（编号章节如 "1. Introduction"、"2.1 Methods"、短全大写行 -> Markdown # 标题）
-> table 行识别（>=2 个 2+ 空格分隔列 -> 标注/规整为可检索文本）
-> 公式/符号清洗（控制字符、孤立行号、坐标噪声）
-> page header/footer 去噪（重复出现的短行）
-> 输出带 Markdown heading 的结构化文本，喂给现有 cleaner/splitter
```

设计要求：

- 纯函数、deterministic，可用合成文本 fixture 测试，**不依赖真实 PDF 下载**即可回归。
- 向后兼容：Markdown/TXT 链路不变；旧 PDF 仍可导入，只是 heading/清洗更好。
- 不破坏 `ParsedDocument` 结构和 `IngestionService` 接口。
- heading 识别保守：只升级高置信度的章节标题，避免把普通句子误判成标题。

## 难评测集设计

新增独立难评测集 `data/evaluation/stage18_hard_queries.csv`，**不覆盖旧 baseline**，覆盖三类更难、有区分度的题：

| 难度类型 | 说明 | 例子方向 |
|---|---|---|
| 跨段证据（cross-passage） | 答案要点分散在多段/多文档，需要合并证据 | “填充能力如何同时受 SCC 流动度和堆石空隙率影响” |
| 易混淆术语（confusable） | 区分相近概念，避免召回错主题 | “堆石混凝土 vs 碾压混凝土 vs 自密实混凝土的区别”、“弹性模量 vs 抗压强度” |
| 需拒答边界（refusal） | 资料库无依据或超工程责任范围，应拒答 | 与 RFC 无关的随机问题、需要规范定量判定的问题 |

每条记录字段：`query_id, query, difficulty_type, language_type, expected_source_hit, expected_refused, expected_answer_points, distractor_topics, notes`。

设计要求：

- 题目要能在“饱和评测集”之外制造区分度：不同配置应出现可观察的命中/排序差异。
- 拒答题必须真实无依据或超范围，验证 Brain evidence confidence 不被检索升级绕过。
- 输出独立 CSV，不动 keyword/vector/hybrid/chat/user_questions 旧结果。

## 多配置对比口径

新增 `scripts/evaluate_stage18_hard_set.py`，在难评测集上对比五种检索配置：

```text
keyword            -> KeywordSearchService
vector             -> VectorSearchService
hybrid             -> HybridSearchService（当前默认）
bm25_rrf           -> RRFHybridSearchService（阶段 17 候选）
bm25_rrf_context   -> RRFHybridSearchService + context expansion（context_window>0）
```

对比口径：

- 每个 config × query 记录：`hit`（期望来源是否在 top_k）、`rank`（命中名次）、`refusal_matched`、`top_titles`、`evidence`。
- 汇总每个 config 的 `hits/total`、`mean_rank`（命中样例平均名次）、`refusal_accuracy`、`distinct_wins`（仅该配置命中的题数）。
- 给出**是否调整默认链路**的数据结论：
  - 若某配置在难评测集上**显著且无回归地**优于默认 hybrid，建议作为默认链路候选并说明证据。
  - 若仍无区分度或存在排序软退化（含阶段 17 `mesoscopic_modeling`），明确建议 `keep_existing_hybrid` 并写明阻断原因。
- **不用静默 fallback 掩盖差异**：配置失败/无索引要显式记录，不偷偷换配置。
- 默认用 deterministic provider，保证可复跑；真实 embedding 只作为可选发布前校准。

## Quality Gate 设计

新增 `scripts/build_stage18_quality_report.py` 汇总 quality gate：

```text
gate 维度：
- corpus_depth          # 深度全文篇数与目标差距
- hard_set_discrimination # 难评测集是否产生区分度
- default_chain_decision  # 默认链路是否调整及证据
- stage17_residual        # mesoscopic_modeling 排序软退化闭环状态
- stage16_residual        # user_mixed_itz_strength Answer Coverage high 状态
- real_config_boundary    # 真实配置 vs deterministic 边界

gate 状态口径：
- pass            # 可进入下一阶段
- review_required # 需人工复核但不阻断后续设计
- blocked         # 高风险，必须人工处理后才放行，写明阻断原因
```

要求：

- 让阶段 17 遗留（mesoscopic_modeling、评测集饱和）和阶段 16 遗留（ITZ/强度 Answer Coverage）有明确闭环状态。
- 如仍高风险，必须明确阻断原因，不用 deterministic 结果掩盖。

## /quality-report 增强

`GET /quality-report` 保持**只读优先**，本阶段增强：

- 只读筛选：按 stage、risk_level、gate_status 过滤。
- 风险详情/队列：把高/中风险样例集中排队展示，附根因和 next_action。
- 导出：提供 CSV/JSON 下载（基于本地质量汇总产物，不触发真实 API）。

边界：

- 不做登录、不做写库、不重构核心前端工作台。
- 不触发真实 API 调用、不重新索引来源。

## API 与兼容边界

阶段 18 必须保证以下入口不被破坏：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
GET /quality-report
```

默认 Brain hybrid 链路是否切换，**只能由难评测集多配置对比的数据结论决定**；无充分证据时保持 `keep_existing_hybrid`。

## 数据安全边界

- 阶段 18 不新增爬虫框架，只做受控、尊重条款的开放获取下载。
- 不保存 API key、Bearer token、供应商原始敏感响应或受限全文到 Git/CSV/文档/测试/Obsidian。
- 真实 provider 只能通过显式本地命令运行；默认测试使用 deterministic 或 mock。
- 不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR，等待用户人工核验。

## 阶段边界

阶段 18 不做：

- 不做写入型 Agent 工具、不做复杂 LangGraph workflow。
- 不做登录系统、不做部署优化。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 HyDE 接入默认链路或自动回归。
- 不把 `/quality-report` 扩成复杂后台。

阶段 18 要做：

- 固化阶段 18 设计。
- 加固 PDF 解析（标题层级、表格、公式、清洗）。
- 尽力真实下载开放获取全文并导入，诚实报数；source registry 去重/权限标注；保留 deterministic baseline 可复跑。
- 构建难评测集与多配置对比，给默认链路数据结论。
- 沉淀 quality gate，闭环阶段 17/16 遗留与真实风险。
- 增强 `/quality-report` 只读筛选/风险队列/导出。
- 保证旧 API、Brain、chat、agent 和 `/quality-report` 不被破坏。
- 完成测试、普通文档、Obsidian 草稿，并停在用户人工核验前状态。

## 完成标准

- `docs/stage18_*.md` 存在并覆盖目标、输入、语料扩充范围与边界、PDF 解析加固、难评测集设计、多配置对比口径、quality gate、报告增强、安全边界和完成标准。
- PDF 解析加固存在并有 deterministic fixture 测试（heading 层级、表格、公式、清洗）。
- 语料深度全文尽力提升，真实导入篇数如实记录；source registry 去重与全文权限标注；deterministic baseline 可复跑。
- 难评测集独立 CSV + 独立脚本，不覆盖旧 baseline。
- 多配置对比给出是否调整默认链路（含 `mesoscopic_modeling` needs_tuning）的数据结论，不用静默 fallback 掩盖差异。
- quality gate 沉淀，阶段 17/16 遗留与真实风险有明确闭环状态；如仍高风险写明阻断原因。
- `/quality-report` 增强只读筛选/风险详情/队列/导出，不做登录、不重构核心 API。
- POST /search、/search/vector、/search/hybrid、/chat、/agent/query、GET /quality-report 不被破坏。
- 阶段 18 测试 + 既有相关测试 + 全量测试通过。
- README、docs/progress、docs/architecture、docs/data_sources、AGENT.MD 判断和 Obsidian 本地知识库完成阶段收尾。
- 最终停在未提交状态，等待用户人工核验。

## 面试表达

阶段 18 我没有再堆模型，而是补 RAG 系统真正的短板：语料深度和评测区分度。原来的库里 115 篇只是题录，深度全文只有 11 篇；旧评测集又已经饱和到 15/15，所以阶段 17 的 BM25+RRF 升级看起来“零增益”，其实是评测题太容易看不出差别。

我做了三件事：第一，加固 PDF 解析，把章节标题、表格行、公式噪声和跨行断词处理好，让全文 chunk 带上真实的 `heading_path`；第二，尽力下载真实开放获取全文导入（诚实报数，不为凑数造假），并用 source registry 做去重和权限标注；第三，专门构建一个难评测集，覆盖跨段证据、易混淆术语和需拒答边界，再在上面对比 keyword/vector/hybrid/BM25+RRF/context expansion 五种配置。只有当某个配置在难题上真正且无回归地更好时，我才会建议切默认链路；否则就保持 keep_existing_hybrid 并写明阻断原因。最后我把这些结论沉淀成 quality gate，并增强了 /quality-report 的只读筛选、风险队列和导出，让发布前质量风险可见、可追踪、可复查。
