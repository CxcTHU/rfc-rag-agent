# Findings & Decisions（阶段 18）

## Requirements

- 用户要求正式进入阶段 18：语料扩充与评测/质量体系增强。
- 目标分支为 `claude/phase-18-corpus-evaluation-quality`。
- 阶段 18 必须从阶段 17 完成、提交、合并到 `main` 并创建 `phase-17-complete` tag 的状态出发。
- 必须确认 `phase-17-complete` 指向阶段 17 最终功能提交，不移动已有阶段 tag。
- 阶段 18 开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。
- 阶段 18 不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化。
- 不让真实 API 成为 CI 或本地全量测试前提；HyDE 仍只做离线实验。
- `/quality-report` 保持只读优先，不扩成复杂后台。
- 保留 deterministic baseline 与 real_config 边界，不用 deterministic 结果掩盖真实失败。
- 语料扩充只用开放获取或已授权全文，尊重 robots.txt 与网站条款，不绕付费墙/登录/验证码；复用 source registry 去重/可信度/全文权限/状态标注。
- 不得把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。

## Git / Tag / Main 起点（已核实）

- `phase-17-complete -> 5b5ef02`（提交信息 `Complete phase 17 retrieval architecture upgrade`，是阶段 17 最终功能提交，**不是** merge commit）。
- `phase-17-complete` 是 `main` 祖先（已验证 `git merge-base --is-ancestor` 返回真）。
- `main` HEAD = `d633b95 Merge phase 17 retrieval architecture upgrade`；其下有 `2f54b89 chore: add Claude and Codex dual-agent entry files`、`5b5ef02 Complete phase 17...`。
- 阶段 17 已完成人工核验、提交、打 tag 并合并到 main。**README/docs/progress 顶部仍残留“阶段 17 待人工核验”的旧文字，是过期表述，需要在阶段 18 收尾时修正。** Git 状态是事实真相源。
- 已从 `main` 创建并切换到 `claude/phase-18-corpus-evaluation-quality`，工作区干净。
- 所有已有阶段 tag（phase-0 ... phase-17-complete）保持不动。

## 当前语料构成（开发前用 DB 复核，2026-06-08）

`data/app.sqlite` 查询结果：

- documents 总数 = 136：
  - `metadata_record` = 115（仅题录/摘要卡片，无深度全文）
  - `open_access_pdf` = 10（开放获取全文）
  - `local_file` = 10（阶段 1 早期 rfc_seed 资料卡）
  - `institutional_access_pdf` = 1（CNKI 机构授权全文，本地私有）
- chunks 总数 = 997。
- 深度全文 ≈ 11（open_access_pdf 10 + institutional_access_pdf 1）。与任务估计一致。
- chunk_embeddings：
  - `deterministic / hash-token-v1 / dim=64` 共 997（默认自动化测试用）
  - `openai-compatible / jina-embeddings-v3 / dim=1024` 共 997（真实校准用）
- sources：status candidate=8、collected=117；fulltext_permission institutional_access=2、metadata_only=110、open_access=10、unknown=3。

本地实际 PDF 文件（`data/fulltext/`，gitignore）：

- `open_access/` 10 篇（TUGraz、MDPI×5、Engineering、ETASR、Nature、Springer）。
- `open_access_auto/` 1 篇（2019 Filling Capacity Evaluation）。
- `cnki_pending/` 1 篇（2005 金峰等创始论文，机构授权，本地私有）。

## Git 跟踪边界（已核实）

- `data/app.sqlite`：**未跟踪**（gitignore `*.sqlite`）。语料 DB 是本地态。
- `data/fulltext/`：**gitignore**。全文 PDF 永不提交。
- `data/imports/metadata_corpus/*.md`：**已跟踪**（116 个题录卡片）。
- `data/fulltext_manifest.csv`、`data/source_candidates.csv`、`data/metadata/rfc_papers_metadata.csv`：已跟踪。
- 因此阶段 18「语料深度扩充」的**可提交物**是：加固后的解析器代码、manifest/source registry 条目、题录卡片、可复跑导入管线；深度全文 DB 的增长靠用户本地复跑导入管线复现，不进 Git。

## 阶段 17 复核结论（阶段 18 必须承接）

- 默认链路接入建议 = `keep_existing_hybrid`：`RRFHybridSearchService`、`BM25SearchService`、`ContextExpansionService` 保持候选/配置开关，不替换默认 `HybridSearchService`、Brain、`/chat`、`/agent`。
- 阻断理由：阶段 17 评测集 hit 已饱和（15/15）缺乏区分度 -> 升级零增益；且 `mesoscopic_modeling` 存在排序软退化（rank 2 -> 7，vector_rank=29，被泛主题综述文档挤占），是 hit 指标掩盖的软退化。
- 5 条 `source_match=no` 中 4 条为等价主题文献换位（多为中文 query 下中文母语文献上浮），仍 top-1 命中，判 acceptable。
- 阶段 18 依据：需构建更有区分度的难评测集，并对综述类文档加权或 topic-anchor rerank 做对照，再决定 RRF 是否进入默认链路。

## Architecture Findings（承接阶段 17）

- `documents` 保存资料整体信息，`chunks` 保存可检索片段，`chunk_embeddings` 保存每个 chunk 的 embedding（按 provider/model/dimension 区分）。
- 检索服务：`KeywordSearchService`（规则关键词 + 同义词扩展 + 标题/heading/content 加权 + metadata 控制 + 来源均衡）、`VectorSearchService`（余弦相似度 + topic anchor 轻量重排）、`HybridSearchService`（keyword/vector 归一化加权 + both_match bonus，默认链路）。
- 阶段 17 新增候选：`BM25SearchService`、`RRFHybridSearchService`（BM25+vector RRF）、`ContextExpansionService`（同 document 相邻 chunk 扩展）。
- `DecomposeRetrievalService` 在复杂问题拆解后调用 `HybridSearchService`，再去重 + rerank。
- `BrainService` hybrid 路径：先判断是否 decompose，否则直接 `HybridSearchService`；`/chat` 与 Agent `answer_with_citations` 都复用 Brain，阶段 18 不能破坏 Brain 输入输出。
- `EvidenceConfidence`：Brain 生成前判断检索证据是否足够，不足则低证据拒答。

## /quality-report Findings

- `GET /quality-report` 是只读质量报告入口（阶段 15/16），由 `app/frontend/quality_report.html` + 质量汇总 CSV 驱动，不触发真实 API、不写库。
- 阶段 16 quality gate = `review_required/high`，high 阻断来自 Answer Coverage 样例 `user_mixed_itz_strength`（真实回答超时），不再来自 decompose。
- 阶段 18 要增强只读筛选、风险详情/队列与导出，并把阶段 17 检索遗留与真实风险纳入 gate 闭环。

## 数据安全边界（阶段 18）

- 语料扩充只用开放获取或已授权全文；受限全文只留在本地授权环境（gitignore），不公开分发。
- 不绕付费墙、登录、验证码；尊重 robots.txt 与网站条款。
- 真实 API key / Bearer token / 供应商原始敏感响应 / 受限全文不写入 Git、CSV、文档、测试或 Obsidian。
- 评测 CSV 只保存脱敏的查询、命中、排名、风险判断和来源标题。

## Technical Decisions

| Decision | Reason |
|---|---|
| 阶段 18 先写设计文档 | 语料扩充、解析加固、难评测、多配置对比、quality gate、报告增强涉及多个模块，先固定边界 |
| 语料扩充真实下载 + 诚实报数 | 用户明确选择；数据完整性优先，RFC 领域开放全文有限，不为凑 40–60 造假 |
| PDF 解析加固用 deterministic fixture 测试 | 不依赖真实 PDF 下载即可回归 heading/表格/公式/清洗 |
| 难评测集独立 CSV + 独立脚本 | 不覆盖旧 baseline，保留可对比性 |
| 默认链路是否切换由难评测集对比决定 | 阶段 17 已证明旧评测集饱和无区分度，需难样例才有决策依据 |
| /quality-report 保持只读 | 不做登录、不重构核心 API，符合阶段边界 |

## Phase Findings

### Phase 0

- 已读 AGENT.MD/README/docs/progress/architecture/data_sources、阶段 17 设计文档与报告、stage17 人工复核 CSV、旧 task_plan/findings/progress。
- 已核实 Git/tag/main 起点（见上）。
- 已从 main 创建阶段 18 分支。
- 已用 DB 复核语料构成（见上）。
- 已确认 gitignore 边界与可提交物。
- 已确认本环境可联网下载真实开放获取 PDF（用 urllib 拉取 MDPI materials-13-00108 返回 `%PDF-1.5`）。
- 已用 AskUserQuestion 确认语料扩充策略 = 尽力真实下载 + 诚实报数。
- 已用 Planning with Files 编写阶段 18 task_plan/findings/progress。

### Phase 1

- 新增 `docs/stage18_corpus_evaluation_quality.md`，覆盖目标、输入、语料扩充范围与边界、PDF 解析加固设计、难评测集设计、多配置对比口径、quality gate、`/quality-report` 增强、API 兼容、数据安全和完成标准。
- 明确五种检索配置对比口径：keyword / vector / hybrid / bm25_rrf / bm25_rrf_context。
- 明确 quality gate 维度（corpus_depth、hard_set_discrimination、default_chain_decision、stage17_residual、stage16_residual、real_config_boundary）与状态口径（pass/review_required/blocked）。
- 新增 `tests/test_stage18_design.py`（3 passed）。

### Phase 2

- 现状：`read_pdf_text` 只把每页拼成 `## Page N` + pypdf 扁平文本，PDF chunk 几乎拿不到真实 `heading_path`。
- 新增 `app/services/ingestion/pdf_text.py`（纯函数）：`structure_pdf_pages`、`structure_page_text`、`dehyphenate`、`detect_heading`、`is_table_row`/`render_table_block`、`is_noise_line`、`detect_repeated_header_footer`、`normalize_unicode`。
- heading 识别策略保守：编号章节（点分段数定级）+ 已知关键词（Abstract/Introduction/.../References）+ 多词全大写行；收紧后排除公式片段（含 `()=_[]{}|/\\`、单词缩写）。
- 表格行：被 2+ 空格分隔出 >=3 列且至少一列含数字 -> 渲染成 `[表格]` + 管线分隔，避免被切碎。
- 断词合并 `concre-\nte -> concrete`；unicode NFKC + 各种 dash 归一 ASCII `-`；去控制符；孤立页码/纯符号行丢弃；跨 >=3 页重复短行作页眉页脚删除。
- 接入 `parser.read_pdf_text`，保留 `## Page N` 与向后兼容（旧单句 PDF 测试仍 pass）。
- 真实 PDF 复核（2020 Liu filling capacity）：恢复出 1 Introduction / 2 Theoretical Model / 2.1 Porous Boxes / 3 Results and Discussions / 4 Conclusions / References 等真实章节。
- 测试：`tests/test_pdf_text_structuring.py`（含 heading_path 端到端）+ 既有 ingestion 测试，26+14 passed。

### Phase 3（语料深度扩充，诚实报数）

- 新增 `scripts/expand_open_access_corpus.py`（可复跑管线，默认 dry-run，需 `--download --import-to-db` 才执行）。
- OpenAlex 发现 866 -> RFC 相关 90 -> 许可允许 OA 带 PDF **16**（这是窄领域的真实上限，远达不到 40–60）。
- 下载 11，其中 6 篇 content-hash 命中已有论文（dedup 生效），**真实新导入 5 篇深度全文**：
  - 137 Pilot Study on Vibrated Rock-filled Concrete（jstage，60 chunks）
  - 138 Application of Iron Ore Tailings and Phosphogypsum...（MDPI buildings，cc-by，75 chunks）
  - 139 Study on Influence of Specimen Size and Aggregate Size on Compressive Strength...（MDPI applsci，cc-by，102 chunks）
  - 140 The Influence of Construction Parameters on the Temperature Field...（MDPI buildings，cc-by，88 chunks）
  - 141 探析水利混凝土工程的施工要点及其裂缝控制（中文，cc-by-nc，10 chunks；控制台 GBK 显示乱码但 DB 存的是正确 UTF-8）
- 语料：documents 136 -> 141，深度全文 11 -> 16（open_access_pdf 10 -> 15），chunks 997 -> 1332。
- 索引：deterministic(64) 与 jina(1024) 均重建到 1332，deterministic baseline 可复跑（jina 由 .env 真实 provider 重建，仅作可选校准）。
- 关键修正（避免污染跟踪文件）：
  - 发现集写入独立 `data/metadata/stage18_oa_discovery.csv`（90 行），不覆盖 curated `data/source_candidates.csv`。
  - manifest 只为真正新导入论文加行（按 local_path + 归一化标题去重），追加 5 行。
  - 重置 `sources` 表后从干净输入重新 sync：total=125、open_access 10 -> 15、metadata_only 110 -> 105、trust=high:125。
- 合规：只下载许可允许（cc-by/cc-by-nc 等）OA；全文存 `data/fulltext/open_access_auto`（gitignore）；DB gitignore；不绕付费墙/登录/验证码；无 API key 入库。

### Phase 4 + 5（难评测集 + 多配置对比）

- 新增 `data/evaluation/stage18_hard_queries.csv`（20 题：8 cross_passage + 7 confusable + 5 refusal），锚定真实语料。
- 新增 `scripts/evaluate_stage18_hard_set.py`：5 配置 keyword/vector/hybrid/bm25_rrf/bm25_rrf_context；需拒答用默认 Brain evidence confidence 判断。
- 产物：`stage18_hard_results.csv`、`stage18_config_comparison.csv`。
- deterministic 多配置结论：
  - hit@8 全部 15/15（recall 饱和），但 **rank@1/precision@1 出现真实区分度**：keyword 15(1.00)、hybrid 14(0.93)、bm25_rrf 14(0.93)、vector 11(0.73)、bm25_rrf_context 14(0.93)。
  - bm25_rrf 与 hybrid 同 hit@8、同 rank@1、mean_rank 略差（1.13 vs 1.07）-> `default_chain_decision=keep_existing_hybrid`，用更有区分度的集证实阶段 17 结论。
  - 区分样例 `cp_itz_uniaxial`（content=ITZ，无标题词锚点）：vector rank4、hybrid/bm25_rrf rank2-3，对应阶段 17 mesoscopic/综述上浮关切。
  - keyword 在“词面显式”查询上 p@1=1.00，但这类查询不考验语义/跨语言，不代表 keyword 通用更优；hybrid 更稳健（承接前阶段）。
- **真实风险（诚实记录，不掩盖）**：deterministic 下 5 题 refusal 仅 1 题被拒（rf_unrelated_finance）。off-topic 词（models/mechanism、中文常用字、random）偶然覆盖证据，evidence confidence 0.20 阈值放过。判断：很可能是 deterministic 哈希 embedding 的语义噪声伪影，Phase 6 用真实 Jina 校验；作为 quality gate 风险条目，不静默改默认拒答逻辑（与阶段 17 把 mesoscopic 留作 tuning_suggestion 同一原则）。

### Phase 6 + 7（quality gate + /quality-report 增强）

- 真实 Jina 校验（`stage18_config_comparison_real.csv`）：vector p@1 0.73(det) -> 1.00(real)，hybrid/bm25_rrf 仍 0.93；**refusal 真实下仍 1/5** -> 拒答弱点是真实风险，非 deterministic 伪影。
- 新增 `scripts/build_stage18_quality_report.py`，产出 `stage18_quality_summary.csv` / `docs/stage18_quality_report.md` / 增强版 `quality_report.html`。
- quality gate 8 行，overall=`review_required/high`：
  - corpus（low）、hard_set 区分度（low）、default_chain=keep_existing_hybrid（low）、real_config（low）、stage17 mesoscopic 闭环（low）、stage16 ITZ carry-forward（medium）、refusal_boundary（high）、overall（high）。
  - 高风险阻断原因明确写出：off-topic 拒答边界偏松；阶段 18 显式记录、不静默改默认拒答逻辑（需独立校准 Phase）。
- `/quality-report` 增强：客户端只读筛选 + 风险队列 + 导出（CSV/JSON）；新增只读端点 `/quality-report/data.json`、`/quality-report/export.csv`；保持只读、无登录、不触发真实 API。
- 关键决策：把“拒答边界弱”作为质量门槛的 high 风险显式暴露，体现质量体系“能发现真实风险”，而非用 deterministic 结果掩盖；具体修复留待后续校准 Phase。

### Phase 11 增补（CNKI 中文坝工全文本地扩充）

- 用户手动下载约 121 篇中文全文到 `G:/Codex/program/papers`（知网 `.caj`）。
- 格式真相：34 个是改名 PDF（`%PDF` 头，有中文文字层，可解析）；87 个是真 CAJ（`CAJ`/`HN`/`KDH` 头），pypdf 读不了。
- 合规：知网全文=受版权机构授权，`institutional_access_pdf`，只存本地 `data/fulltext/cnki_pdf/`（gitignore），chunk 进本地 DB，绝不提交/推送/再分发。
- 自动转换不可行：本沙箱无 mutool/PyMuPDF/caj2pdf；87 个真 CAJ 需用户用 CAJViewer 批量导出 PDF；清单 `data/fulltext/cnki_caj_pending.txt`（gitignore）。
- 中文解析适配 `pdf_text.py`：CHINESE_SECTION_KEYWORDS（摘要/关键词/引言/前言/结论/结语/参考文献/致谢…，支持被抽取拆开的"结 论"）；CHINESE_NUM_HEADING_RE（一、引言 / （三）结论，要求顿号或括号，拒"一是/一方面/一旦…"）；编号标题加 num<=40、标题无数字、必须含真正词（>=2 中文或 >=3 字母），拒"150 m/17 km/9 DA M 0 + 251/表格行"；全大写标题要求每词 >=2 字母，拒"D A M/DO I"。
- 决策：扩域到坝工，分主题标注 rfc_core / dam_engineering（importer 用堆石混凝土/自密实/rock-filled 等词粗分）。
- 导入结果：26 篇（8 rfc_core + 18 dam_engineering）；深度全文 16 -> 42（institutional 1 -> 27、open_access 15），docs 141 -> 167、chunks 1332 -> 1814；deterministic 索引重建覆盖 1814；jina 未重建（需真实 API，可选）。
- 验证：pdf_text 12 passed；全量 379 passed；无全文/PDF/sqlite 泄露到 Git。
- 遗留：87 个 CAJ 待用户转换；转换后做一次统一导入 + 重跑难评测/quality gate + 文档/Obsidian 闭环（建议作为阶段 19 或阶段 18 统一收尾）。难评测集目前是英文 RFC 向，后续可补中文坝工难题。

## Term Explanations

| Term | Meaning in this project |
|---|---|
| metadata_record | 仅题录/摘要的文档类型；只有标题、作者、摘要等元数据，没有深度全文正文 |
| open_access_pdf | 开放获取全文 PDF 文档类型；可在本地保存正文并切 chunk |
| heading hierarchy | 标题层级；解析 PDF 时保留章节结构进 `heading_path` |
| table extraction | 表格抽取；把 PDF 里列对齐的表格识别成可检索文本 |
| hard eval set | 难评测集；跨段证据、易混淆术语、需拒答边界，比旧 baseline 更有区分度 |
| quality gate | 质量门槛；规定何时可进下一阶段、何时必须人工复核或阻断 |
| risk queue | 风险队列；把高/中风险样例集中排队，便于人工逐条复核 |
| RRF | Reciprocal Rank Fusion，倒数排名融合 |
| context expansion | 上下文扩展；命中核心 chunk 后拉取相邻 chunk 帮助回答 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| README/docs/progress 顶部仍写阶段 17 待核验 | Git 已有 `phase-17-complete` 和 `Merge phase 17` | 阶段 18 收尾时同步修正入口文档 |
| RFC 领域开放全文数量可能不足 40–60 | 现有 10 篇 open_access 已覆盖主流 MDPI/Engineering/Nature/Springer | 尽力真实下载，诚实报数，不造假 |

## Resources

- `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`
- `docs/stage17_retrieval_architecture_upgrade.md`、`docs/stage17_retrieval_upgrade_report.md`
- `data/evaluation/stage17_retrieval_upgrade_manual_review.csv`
- `app/services/ingestion/parser.py`、`cleaner.py`、`splitter.py`、`service.py`
- `app/services/retrieval/{keyword_search,vector_search,hybrid_search,bm25_search,rrf_fusion,context_expansion,decompose}.py`
- `app/services/brain/service.py`、`app/api/search.py`、`app/schemas/search.py`
- `scripts/import_fulltext.py`、`scripts/build_vector_index.py`、`scripts/sync_sources.py`、`scripts/evaluate_*.py`
- `app/frontend/quality_report.html`、`scripts/build_stage16_quality_closure_report.py`
- `data/fulltext_manifest.csv`、`data/metadata/rfc_papers_metadata.csv`、`data/imports/metadata_corpus/`
