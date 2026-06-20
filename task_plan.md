# 阶段 48 任务计划：多模态能力真实评测与质量闭环

## Goal

在阶段 47 完成表格提取、用户图片分析、引用定位、反馈闭环四条功能线之后，用**真实模型**对三类新增能力做系统性评测：
（1）知识库图片检索质量（复跑 + 边缘扩展）；
（2）用户上传图片分析效果（以图搜图 + 领域门控）；
（3）表格检索准确性。

采用**两轮评测**策略：第一轮建立基线，第二轮根据基线指标自动决定是否扩展到 50 条。全程使用真实 API（GLM-4.6V / GLM-Embedding-3 / GLM-Rerank），不使用 deterministic mock。

## Current Phase

Phase 0：启动校准。

## 自动扩展决策门（Decision Gate）

本阶段设计为**无人值守自主推进**。以下是各评测集的扩展判定规则：

### Gate 1：知识库图片检索

| 指标 | 门槛 | 判定 |
|---|---|---|
| precision | >= 0.88 | PASS |
| must_have_recall | >= 0.95 | PASS |
| image_suppression | >= 0.95 | PASS |

- 全部 PASS → 基线达标，不扩展，记录结论
- 任一 FAIL → 扩展边缘集到 50 条，分析失败模式，尝试修复后重跑

### Gate 2：用户图片分析

| 指标 | 门槛 | 判定 |
|---|---|---|
| description_accuracy | >= 0.75 | 视觉描述准确率 |
| text_retrieval_relevance | >= 0.70 | 文本检索相关性 |
| image_to_image_hit_rate | >= 0.60 | 以图搜图命中率 |
| refusal_correctness | >= 0.90 | 领域门控拒答正确率 |

- 全部 PASS → 基线达标，不扩展
- 任一 FAIL → 扩展到 50 条（补充对应弱项类别），分析根因，尝试调参修复后重跑

### Gate 3：表格检索

| 指标 | 门槛 | 判定 |
|---|---|---|
| precision | >= 0.75 | 返回表格相关性 |
| recall | >= 0.65 | 应返回表格的覆盖率 |
| format_correctness | >= 0.85 | Markdown 格式可读性 |

- 全部 PASS → 基线达标，不扩展
- 任一 FAIL → 扩展到 50 条，分析提取/检索失败模式，尝试修复后重跑

### 扩展后二次评测

扩展后重跑仍然 FAIL → 记录为**已知限制**，写入 findings.md 和 phase review，不无限循环。最多执行两轮。

## 当前基线

- Git: 阶段 47 合并后的 `main`（需先完成阶段 47 合并）
- Stage 30: 91.52 / A / pass（必须保持不退化）
- 全量测试: 1029 passed
- Alembic head: `20260621_0005`
- 图片检索基线: precision=0.9305, must_have_recall=1.0000（Phase 46 的 100 条）
- 表格 chunk 数量: 待 Phase 1 回填后确认
- 用户图片分析: 无基线

## Phases

### Phase 0：启动校准（主 agent）

- [ ] 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md
- [ ] 运行 `git status -sb` 与 `git log --oneline -5`
- [ ] 确认阶段 47 已合并到 `origin/main`，phase-47-complete tag 存在
- [ ] 从 `main` 创建 `codex/phase-48-multimodal-evaluation`
- [ ] 校准 task_plan.md、findings.md、progress.md

### Phase 1：表格回填与统计（主 agent）

- [ ] 运行 `python scripts/backfill_phase47_tables.py --dry-run`，统计表格数量和分布
- [ ] 根据 dry-run 结果决定实际回填策略
- [ ] 运行 `python scripts/backfill_phase47_tables.py`（正式回填）
- [ ] 运行 embedding 生成（使用真实 GLM-Embedding-3）
- [ ] 记录统计：total_docs, extracted_tables, by_category, by_doc 分布
- [ ] 决定表格评测集规模：
  - 表格 < 100 → 评测 20 条
  - 表格 100-500 → 评测 30 条
  - 表格 > 500 → 评测 50 条

### Phase 2：知识库图片检索回归评测（主 agent）

- [ ] 复跑已有 100 条评测集 `data/evaluation/phase46_real_image_retrieval_questions.csv`
  - 使用 `scripts/evaluate_phase46_real_image_retrieval.py --mode real`
  - 对比 Phase 46 基线：precision=0.9305, must_have_recall=1.0000
  - 验证 Phase 47 新增功能未导致图片检索退化
- [ ] 设计 20 条边缘场景补充评测集 `data/evaluation/phase48_image_edge_questions.csv`
  - 5 条跨页图片查询（图片标题在上一页，内容在下一页）
  - 5 条表格内嵌图表查询（配合 Phase 47 表格提取的交叉验证）
  - 5 条多图同页竞争查询（同一页有 3+ 张图，验证选择准确性）
  - 5 条模糊查询（用口语化描述而非精确术语，验证语义理解）
- [ ] 编写 `scripts/evaluate_phase48_image_edge.py` 复用已有评测框架
- [ ] 运行边缘评测，记录指标
- [ ] **Gate 1 判定**：检查 precision/must_have_recall/suppression 是否达标
  - PASS → 记录结论，进入 Phase 3
  - FAIL → 扩展边缘集到 50 条，分析失败模式，调参后重跑一次

### Phase 3：用户图片分析评测（主 agent）

#### 3a：收集真实工程图片

- [ ] 从公开渠道下载 20 张真实工程图片到 `data/evaluation/phase48_user_images/`
  - 搜索来源：学术论文配图（知网/万方/Google Scholar 公开预览）、公开工程报告/技术标准配图、GitHub 上的开源混凝土缺陷检测数据集（如 SDNET2018、Concrete Crack Dataset）、公开新闻/工程项目展示页面
  - 裂缝类 5 张：横向裂缝、纵向裂缝、网状裂缝、表面龟裂、深层贯穿裂缝
  - 骨料/表面类 3 张：混凝土骨料粒径、表面气泡、蜂窝麻面
  - 试验/设备类 3 张：抗压试验机、试件破坏现场、混凝土搅拌设备
  - 工程现场类 3 张：坝体浇筑、仓面施工、模板支护
  - 图表类 3 张：手机拍摄的纸质数据表格、屏幕截图曲线、手绘草图
  - **负样本** 3 张：自然风景、动物、无关电子产品
- [ ] 图片来源必须是公开可用的（不使用付费数据集、不下载受版权保护的商业图片）
- [ ] 在 `data/evaluation/phase48_user_images/README.md` 记录每张图片的来源描述（不记录原始 URL）
- [ ] `data/evaluation/phase48_user_images/` 加入 `.gitignore`

#### 3b：编写评测集

- [ ] 创建 `data/evaluation/phase48_user_image_questions.csv`：

```csv
eval_id,image_filename,question,category,expected_domain,expected_description_keywords,expected_text_keywords,expected_similar_figure_topic,notes
```

- 每张图片 1 条问题（共 20 条）
- `category`：crack / aggregate / test_equipment / construction / chart / negative
- `expected_domain`：in_scope / out_of_scope
- `expected_description_keywords`：视觉模型应识别的关键词（"|" 分隔）
- `expected_text_keywords`：文本检索应匹配的关键词（"|" 分隔）
- `expected_similar_figure_topic`：以图搜图应命中的主题

#### 3c：编写评测脚本

- [ ] 创建 `scripts/evaluate_phase48_user_image.py`
- 对每条评测记录：
  1. 调用 `UserImageAnalyzer.analyze(image_path, question)` — 使用真实 GLM-4.6V
  2. 评分维度：
     - `description_accuracy`：视觉描述是否命中 expected_description_keywords
     - `text_retrieval_relevance`：text_chunks 是否命中 expected_text_keywords
     - `image_to_image_hit_rate`：similar_figures 主题是否匹配 expected_similar_figure_topic
     - `refusal_correctness`：负样本是否被正确拒答，正样本是否未被误拒
  3. 输出详细结果 `data/evaluation/phase48_user_image_results.csv`
  4. 输出汇总 `data/evaluation/phase48_user_image_summary.csv`
- [ ] 支持 `--dry-run`（只检查图片和 CSV 格式，不调真实 API）

#### 3d：运行评测并判定

- [ ] 运行评测脚本（真实 GLM-4.6V + GLM-Embedding-3）
- [ ] **Gate 2 判定**：
  - 全部达标 → 记录基线，进入 Phase 4
  - 任一不达标 → 分析弱项类别，从网上补充该类别图片，扩展到 50 条，调参后重跑

### Phase 4：表格检索评测（主 agent）

#### 4a：设计评测集

- [ ] 根据 Phase 1 的回填统计，确定评测规模（20/30/50 条）
- [ ] 创建 `data/evaluation/phase48_table_retrieval_questions.csv`：

```csv
eval_id,question,category,expected_has_table,expected_table_keywords,expected_doc_keywords,expected_values,notes
```

- 覆盖类别：
  - 配合比查询 — "XX 工程的水泥用量是多少"
  - 强度参数 — "28 天抗压强度试验结果"
  - 材料掺量 — "粉煤灰掺量对比"
  - 对比类 — "不同配合比的强度对比表格"
  - 工程参数 — "大坝分区的混凝土方量"
  - **负样本** — 答案在文本段落中而非表格中的查询

#### 4b：编写评测脚本

- [ ] 创建 `scripts/evaluate_phase48_table_retrieval.py`
- 对每条评测记录：
  1. 调用 `AgentToolbox.search_tables(query)` — 使用真实 GLM-Embedding-3
  2. 评分维度：
     - `precision`：返回的表格是否与查询相关
     - `recall`：应召回的表格是否被召回
     - `format_correctness`：Markdown 表格是否可读（列数一致、无乱码、header 正确）
     - `value_accuracy`：表格中的数值是否与 PDF 原文一致（抽样 5 条人工标注后自动对比）
  3. 输出详细结果 `data/evaluation/phase48_table_results.csv`
  4. 输出汇总 `data/evaluation/phase48_table_summary.csv`

#### 4c：运行评测并判定

- [ ] 运行评测脚本（真实 GLM-Embedding-3）
- [ ] **Gate 3 判定**：
  - 全部达标 → 记录基线，进入 Phase 5
  - 任一不达标 → 扩展到 50 条，分析提取/检索失败模式，尝试修复后重跑

### Phase 5：扩展评测执行（条件触发）

本 Phase 仅在 Gate 1/2/3 中有任一 FAIL 时执行。若全部 PASS 则跳过。

- [ ] 对每个 FAIL 的 Gate：
  1. 分析失败模式（聚类错误类型，列出 top-3 失败原因）
  2. 尝试参数调整或代码修复（记录修改内容和理由）
  3. 扩展评测集到 50 条（补充弱项类别）
  4. 重跑评测
  5. 记录二轮结果，对比一轮基线
- [ ] 二轮仍 FAIL → 记录为**已知限制**，不继续循环
- [ ] 所有扩展评测完成后进入 Phase 6

### Phase 6：质量问题修复（条件触发）

本 Phase 仅在评测发现可修复的质量问题时执行。若无需修复则跳过。

- [ ] 图片检索退化修复（如有）
- [ ] 用户图片分析参数调优（如有）：
  - IMAGE_TO_IMAGE_MIN_SCORE 调整
  - DOMAIN_ANCHORS 扩充
  - USER_IMAGE_ANALYSIS_PROMPT 优化
- [ ] 表格提取改进（如有）：
  - TABLE_EXTRACTION_MIN_ROWS 调整
  - 表格标题搜索范围扩大
  - Markdown 格式优化
- [ ] 修复后回归测试：全量 pytest + Stage 30 不退化
- [ ] 修复后重跑受影响的评测集，确认指标提升

### Phase 7：文档 + Obsidian 收尾（主 agent）

- [ ] 汇总所有评测结果到 `data/evaluation/phase48_summary.json`
- [ ] 新增 `docs/phase48_evaluation_report.md`：
  - 三组评测的基线指标
  - 各 Gate 判定结果
  - 扩展评测结果（如有）
  - 质量修复记录（如有）
  - 已知限制和后续建议
- [ ] 同步 README.md、docs/progress.md、docs/architecture.md
- [ ] 新增 docs/phase_reviews/phase-48.md 验收草稿
- [ ] Obsidian 本地知识库收尾：
  - 新建 `obsidian-vault/阶段/阶段 48 - 多模态能力真实评测与质量闭环.md`
  - 新建 `obsidian-vault/阶段汇报/阶段 48 - 多模态能力真实评测与质量闭环/` 目录
  - 阶段 48 Phase 汇报索引 + 每个 Phase 的 10 项小汇报（按 Phase 汇报模板）
  - 更新 `obsidian-vault/阶段汇报索引.md` 追加阶段 48
  - 每篇小 Phase 汇报包含：目标、完成任务、新增/修改内容、关键代码或模块、问题与解决方式、新词解释、验证结果、遗留问题、下一 Phase、面试表达
- [ ] 全量 pytest 通过，Stage 30 不退化
- [ ] 停在用户人工核验前状态

## 安全边界

- Stage 30 必须保持 91.52/A/pass 或不退化
- 真实 API 调用使用 Paratera 供应商（GLM-4.6V 5 路分片、GLM-Embedding-3、GLM-Rerank）
- 不把 API key、Bearer token、供应商原始响应写入 Git/CSV/文档/测试/Obsidian
- 评测用用户图片存储在 `data/evaluation/phase48_user_images/`（gitignored），不提交到 Git
- 下载工程图片仅使用公开可用来源，不使用付费/受版权保护的商业图片
- 未经用户人工核验，不 git add/commit/tag/push/建 PR
- 最多执行两轮评测，不无限循环
