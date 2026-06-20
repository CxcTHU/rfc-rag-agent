# 阶段 46 任务计划：图片质量修复与题注关联

## Goal

在阶段 45 完成全库图片提取（14,996 张图片，853 篇 PDF）和多模态 RAG 架构的基础上，完成两条主线：（A）针对 621 张问题图片进行分类诊断与定向修复，不重新提取 14,375 张正常图片；（B）为全部图片提取 PDF 原文中的图表题注（caption），增强图文关联，让检索和展示不再完全依赖视觉模型生成的描述文本。

## Current Phase

Phase 15：完成，停在用户人工核验前。

## 当前基线与工作区状态

- Git 基线：`main / origin/main -> e1ff05da Merge phase 45 data migration multimodal RAG`；`phase-45-complete -> 35127e44 Complete phase 45 data migration multimodal RAG`，且该 tag 是 `main` 的祖先。
- 当前分支：`codex/phase-46-image-quality-caption`。
- 本地 DB: SQLite, documents=1146, chunks=47,340, chunk_embeddings=68,857 (paratera=36,841 in FAISS)。
- 图片总量: 14,996 张（Phase 1 manifest 实测：14,243 normal + 753 问题）。
- 问题图片: 753 张（525 有 chunk+embedding，228 仅磁盘文件）。
- 受影响文档: 80 篇（Type B 碎片问题 42 篇）。
- Stage 30: 91.52 / A / pass（必须保持不退化）。
- 全量测试: 944 passed。

## 问题图片分类

| 类型 | 描述 | 数量 | 修复策略 |
|------|------|------|----------|
| Type A | 装饰图/模板图（重复页面模板、页眉页脚、logo 等低价值图） | 159 | 删除 chunk + embedding，保留磁盘文件 |
| Type B | 碎片图（完整图表被拆成坐标轴、数据区、图例等碎片） | 565 | 页面级重渲染 + bbox 合并，替换碎片为完整图 |
| Type C | 空/小文件（缺失、0 字节或 <5KB 且任一维度 <100px） | 29 | 清理 chunk + embedding，删除磁盘文件 |

## Phases

### Phase 0：启动校准与规划落盘

- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认阶段 45 已合并到 `origin/main`，不移动已有阶段 tag
- [x] 从 `origin/main` 创建 `codex/phase-46-image-quality-caption`
- [x] 校准 `task_plan.md`、`findings.md`、`progress.md`

### Phase 1：问题图片分类 manifest 生成

- [x] 新增 `scripts/classify_phase46_problem_images.py`
- [x] 扫描全部 14,996 张图片，分类为 normal / type_a / type_b / type_c
- [x] Type A 检测：同文档内相同尺寸（宽高完全相同）出现在 ≥3 个不同页面，并限定低文件量或低尺寸模板/装饰图，避免误伤正常大图
- [x] Type B 检测：同页面 ≥3 张图片且存在 aspect ratio >3:1 或 <1:3；低文件量碎片直接标记，单页 ≥20 张的密集碎片页整页标记
- [x] Type C 检测：文件缺失、文件大小 =0 或（<5KB 且任一维度 <100px）
- [x] 输出 `data/evaluation/phase46_image_quality_manifest.csv`
- [x] 抽检确认分类准确率（Type A 模板/页眉页脚、Type B 图表碎片、Type C 小装饰条均命中预期）

### Phase 2：Type A（装饰图）+ Type C（空/小文件）清理

- [x] 新增 `scripts/clean_phase46_decoration_empty.py`
- [x] Type A：删除对应 chunk（chunk_type=image_description）+ chunk_embedding，保留磁盘文件
- [x] Type C：删除对应 chunk + chunk_embedding + 磁盘文件
- [x] 记录清理数量到 `data/evaluation/phase46_cleanup_report.csv`
- [x] 验证数据库一致性（remaining image chunks=14,026，image embeddings=14,026，orphan embeddings=0）

### Phase 3：Type B（碎片图）页面级重渲染 — 试点 5 篇文档

- [x] 选取碎片最严重的 5 篇文档（doc 140, 431, 349, 144, 16）
- [x] 修改 `image_extractor.py`，新增 `extract_images_page_render` 方法：
  - 用 `page.get_image_info(xref=True)` 获取每张图在页面上的显示 bbox
  - 合并重叠/相邻的 bbox（IoU>0.3 或间距<20pt 合并为一个区域）
  - 用 `page.get_pixmap(clip=merged_rect, dpi=150)` 渲染合并区域
  - 过滤面积过小的区域（<50×50px）
- [x] 对试点文档执行重渲染，输出新图片到 `data/images/{doc_id}/`
- [x] 删除试点文档的旧碎片图 chunk + embedding
- [x] 抽检对比试点文档修复前后效果（doc 140 `page7_render1.png` 已合并为完整多子图图表）

### Phase 4：Type B 全量修复（剩余 ~73 篇文档）

- [x] 对剩余碎片文档批量执行页面级重渲染
- [x] 输出修复统计：修复文档数、替换图片数、新生成图片数
- [x] 记录到 `data/evaluation/phase46_fragment_fix_report.csv`

### Phase 5：修复图片 GLM-4.6V 重描述 + chunk/embedding 更新

- [x] 对 Phase 3-4 新生成的图片调用 GLM-4.6V 生成描述（通过两个智谱官方 route + 一个 Paratera route，分 5 shard 执行，最终 1,995/1,995 described）
- [x] 采用阶段 45 的 5 路并发 staging pipeline（已复用 `process_multimodal_to_staging.py --image-manifest --workers 5` 路径，待配置后执行）
- [x] 创建新的 image_description chunk + paratera embedding
- [x] 合并到数据库（serial DB merge 避免 SQLite 锁）
- [x] 输出待描述图片 manifest：`data/evaluation/phase46_rendered_image_manifest.csv`（1,995 pending render images）
- [x] 输出脱敏 readiness 报告：`data/evaluation/phase46_redescribe_readiness.json`（status=blocked，pending_images=1,995；已区分统一 `VISION_MODEL_*` 与 Phase45/custom route env）
- [x] 输出描述统计到 `data/evaluation/phase46_redescribe_report.csv` 与 `data/evaluation/phase46_redescribe_summary.json`
- [x] 重建 FAISS：`paratera / GLM-Embedding-3 / dim2048` vectors=39,123；DB 校验 render_image_chunks=1,995，render_image_embeddings=1,995，orphan_embeddings=0

### Phase 5a：orientation residual audit/repair（Phase 5 后、Phase 6 前）

- [x] 基于 subagent worker 复核 Phase45 orientation repair 遗留：原始 review 85 条中 83 条 fixed，2 条失败均为 doc421 的 Type A 装饰/模板图，Phase46 Phase2 已删除其 chunk+embedding；doc1318 后续 3/3 fixed。
- [x] 输出 `data/evaluation/phase46_orientation_residual_candidates.csv` 和 `data/evaluation/phase46_orientation_residual_summary.json`：candidates_total=88，fixed=86，cleanup_resolved=2，still_candidate=0，failed=0。
- [x] 确认无需 `--apply` 页面级重渲染，不插队当前 Phase 5 重描述/DB merge/embedding，不重新处理已完成正常图片。

### Phase 6：题注提取模块开发

- [x] 新增 `app/services/ingestion/caption_extractor.py`
- [x] 用 PyMuPDF 获取每页文本块的空间位置（`page.get_text("dict")` → blocks）
- [x] 对每张图片的 bbox，在其下方 ~50pt 范围内搜索匹配题注模式的文本块：
  - 中文：`^图\s*[\d\.]+`、`^表\s*[\d\.]+`
  - 英文：`^Fig\.?\s*[\d\.]+`、`^Figure\s*[\d\.]+`、`^Table\s*[\d\.]+`
- [x] 处理边界情况：跨页题注、子图标签、无题注
- [x] 新增 `caption` 字段到 Chunk 模型（可空 Text 字段）
- [x] Alembic 迁移添加 `caption` 列
- [x] 新增测试覆盖题注提取逻辑

### Phase 7：全量题注关联

- [x] 新增 `scripts/backfill_phase46_captions.py`
- [x] 对全部 14,375+ 正常图片 + Phase 3-4 修复图片执行题注提取
- [x] 更新对应 image_description chunk 的 caption 字段
- [x] 输出 `data/evaluation/phase46_caption_coverage.csv` 与 summary：total_images=15,628，captioned=7,853，no_caption=7,741，failed=34；DB captioned_image_chunks=7,853

### Phase 8：前端题注展示 + FAISS 重建

- [x] 前端图片 evidence card 展示 caption 作为图片标题
- [x] `AgentSearchItem` / `AgentSourceReference` 增加 caption 传递
- [x] 重建 FAISS 索引（只含 paratera embedding）
- [x] 验证检索链路端到端正常

### Phase 9：回归验证 + 文档与 Obsidian 收尾

- [x] 全量 pytest 通过
- [x] Stage 30 评分保持 91.52/A/pass 或不退化
- [x] API smoke：/health, /search/hybrid, /chat, /agent/query, /agent/query/stream 均 200
- [x] 浏览器验证：图片 evidence card 显示题注、desktop + mobile 无溢出
- [x] 同步 README.md、docs/progress.md、docs/architecture.md
- [x] 新增 docs/phase_reviews/phase-46.md 验收草稿
- [x] 更新 Obsidian 本地知识库
- [x] 停在用户人工核验前状态，不执行 git add/commit/tag/push/PR

### Phase 10：search_figures 工具开发

- [x] 在 `app/services/agent/tools.py` 新增 `search_figures(query, top_k=4)`，只检索 `chunk_type='image_description'` 的全库图片通道
- [x] 应用 `MIN_IMAGE_RELEVANCE_SCORE` 阈值，初始值 0.35，后续由评测标定
- [x] 增加运行时图片质量检查：文件存在、非零字节、尺寸大于 50x50px
- [x] 对同文档同页相似图片去重，只保留最佳结果
- [x] 返回 `FigureSearchResult`：`image_url`、`caption`、`page_number`、`document_title`、`relevance_score`、`description_snippet`
- [x] 在 `app/services/agent/react_actions.py` 注册 `search_figures` action，与 `search_knowledge` 同级
- [x] 在 `app/schemas/agent.py` 增加 FigureSearchResult schema
- [x] 更新 ReAct planner prompt，说明何时调用 `search_figures`，何时不调用
- [x] 新增 deterministic 测试覆盖 `search_figures` 工具逻辑

### Phase 11：图片 chunk 元数据增强（page_number 回填）

- [x] 检查现有 image_description chunk 是否已有 page number 信息
- [x] 新增 `scripts/backfill_phase46_image_page_numbers.py`，从 `source_image_path` 的 `pageN_imgM.png` / `pageN_renderM.png` 解析页码并写入独立字段或可传递元数据
- [x] 确保 `search_figures` 返回 `page_number`
- [x] 前端 evidence card 展示格式：`图 X — 第 N 页 — 《文档标题》`

### Phase 12：降级 enrich_agent_response_with_figure_evidence（完成解耦）

- [x] ReAct 路径（`mode="react_agent"`）使用 `search_figures` 工具，不再调用自动 enrich
- [x] default AgentService 路径保留 enrich fallback，但新增 `ENABLE_AUTO_FIGURE_ENRICHMENT` 且默认关闭
- [x] 确保 `/agent/query` 和 `/agent/query/stream` 行为一致
- [x] 确保 `/chat` 端点不受影响

### Phase 13：图片召回评测集构建

- [x] 新增 `data/evaluation/phase46_image_retrieval_questions.csv`，至少 30 条问题
- [x] 覆盖四类：`must_have_image`、`image_helpful`、`text_only`、`no_image`
- [x] 列包含：`query_id`、`question`、`category`、`expected_has_image`、`expected_image_keywords`、`notes`
- [x] 评测集覆盖真实语料图片类型：工程照片、试验曲线、施工流程图、微观结构图等

### Phase 14：图片检索质量评测脚本

- [x] 新增 `scripts/evaluate_phase46_image_retrieval.py`
- [x] 对每条评测问题调用 `search_figures`，不依赖真实 API
- [x] 计算 `image_precision`、`image_recall`、`image_suppression`、`image_quality_rate`、`caption_coverage`、`page_number_coverage`
- [x] 输出 `data/evaluation/phase46_image_retrieval_results.csv` 和 `data/evaluation/phase46_image_retrieval_summary.csv`
- [x] 根据评测结果标定 `MIN_IMAGE_RELEVANCE_SCORE`
- [ ] 可选对比旧 enrich 模式与新 `search_figures` 模式的 precision/recall

### Phase 15：追加回归验证 + 文档收尾

- [x] 全量 pytest 通过
- [x] Stage 30 保持 91.52/A/pass 或不退化
- [x] 图片检索评测指标达标：`image_precision >= 0.7`，`image_suppression >= 0.8`
- [x] API smoke：`agent/query` 返回图片时包含 `caption` + `page_number`
- [x] 浏览器验证：图片 evidence card 展示 `图 X — 第 N 页 — 《文档标题》`
- [x] 更新 `task_plan.md`、`findings.md`、`progress.md`、`docs/phase_reviews/phase-46.md`
- [x] 在 `findings.md` 记录解耦前后的架构对比和评测数据
- [x] 停在用户人工核验前状态，不执行 git add/commit/tag/push/PR

### Phase 16：真实语料图片召回评测集

- [x] 新增 `data/evaluation/phase46_real_image_retrieval_questions.csv`，至少 100 条真实 DB/image chunk/caption/page_number 驱动问题
- [x] 四类大致均衡：`must_have_image`、`image_helpful`、`text_only`、`no_image`
- [x] 正例覆盖应力应变、强度、温控/水化热、粉煤灰、微观结构、破坏裂缝、施工浇筑、级配孔隙填充、试验装置
- [x] 负例覆盖定义概念、明确不要图片、系统问题、离题问题
- [x] CSV 字段包含 `query_id,question,category,expected_has_image,expected_image_keywords,expected_caption_keywords,expected_doc_keywords,expected_source_image_path,expected_page_number,notes`
- [x] 不使用合成 fixture 作为主评测集

### Phase 17：真实图片召回评测脚本

- [x] 新增 `scripts/evaluate_phase46_real_image_retrieval.py`
- [x] 默认使用本地 DB、已有 image embeddings/FAISS/vector cache，不调用真实 API
- [x] 逐条调用 `AgentToolbox.search_figures()` 或等价生产路径
- [x] 输出 results/summary CSV
- [x] 指标至少包含 `image_precision,image_recall,must_have_recall,image_helpful_hit_rate,image_suppression,top1_caption_match_rate,topk_caption_match_rate,expected_path_hit_rate,caption_coverage_in_results,page_number_coverage_in_results,wrong_generic_curve_rate`
- [x] 支持 `--questions-csv --results-csv --summary-csv --top-k --min-score`
- [x] 使用 expected keywords/caption/path deterministic 判定，不调用 LLM Judge
- [x] 增加小型 fixture 测试覆盖脚本逻辑

### Phase 18：基线真实评测

- [x] 运行真实评测脚本记录 baseline
- [x] 建议门槛：precision>=0.75，must_have_recall>=0.75，suppression>=0.85，topk_caption_match_rate>=0.70，wrong_generic_curve_rate<=0.10
- [x] 达标则不优化；不达标进入 Phase 19
- [x] 将 baseline 指标与判定写入 `findings.md`、`progress.md`

### Phase 19：caption-weighted soft rerank

- [x] Phase 18 baseline 已达标，按“达标则不优化”规则不触发 rerank 实施
- [x] 记录后续若真实 query embedding 评测暴露误召，应优先将当前 specific-term hard requirement 改为 caption-weighted soft rerank
- [x] 当前不调整 `search_figures` 排序代码，不新增 near-miss 行为变更测试，避免在达标 baseline 上继续调参
- [x] 记录暂不重做 embedding

### Phase 20：caption-enhanced image embedding readiness（仅当 Phase 19 不达标）

- [x] Phase 19 未触发，Phase 20 readiness 不需要执行
- [x] 不调用真实 embedding API，不更新 DB/FAISS
- [x] 明确普通 text chunks 不动，等待用户明确授权

### Phase 21：收口验证与文档

- [x] 运行 focused tests、全量 pytest、Stage 30
- [x] 运行最终真实图片召回评测
- [x] 如有 API/前端行为变化，跑 8000 smoke：本轮 Phase 16-21 未改 API/前端行为，因此未新增 8000 smoke
- [x] 更新 `task_plan.md`、`findings.md`、`progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-46.md`
- [x] 记录 100 条覆盖、baseline、rerank 后指标、是否需要 embedding 重建
- [x] 停在人工核验前，不执行 git add/commit/tag/push/PR

## 安全边界

- 14,375 张正常图片不得重新提取，只做题注关联
- 只对 Type B 碎片文档重新提取图片
- Stage 30 必须保持 91.52/A/pass 或不退化
- 不让真实 API 成为 CI 或本地全量测试前提
- 不把 API key、Bearer token、供应商原始响应写入 Git/CSV/文档/测试/Obsidian
- 未经用户人工核验，不 git add/commit/tag/push/建 PR
