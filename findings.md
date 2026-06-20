# 阶段 48 Findings

## 阶段 47 基线确认

- 全量测试: 1029 passed
- Stage 30: 91.52 / A / pass
- Alembic head: `20260621_0005`
- 图片检索 Phase 46 基线: precision=0.9305, must_have_recall=1.0000, suppression=1.0000
- 表格提取: Phase 47 已实现 `table_extractor.py` + `backfill_phase47_tables.py`，待回填统计
- 用户图片分析: Phase 47 已实现 `UserImageAnalyzer` + 领域门控，无评测基线
- image_description chunks: 15628 条（以图搜图的检索目标）

## 评测策略决策

### 两轮评测 + Decision Gate

- 第一轮：小规模建立基线（20-30 条），用真实 API 验证功能有效性
- Decision Gate：机器可判定的指标门槛，无人值守自动决策
- 第二轮（条件触发）：扩展到 50 条，聚焦弱项类别
- 最多两轮，不无限循环

### 真实工程图片来源

- 优先使用公开学术论文配图（知网/万方预览页、Google Scholar）
- 公开混凝土缺陷检测数据集（SDNET2018、GitHub 上的 Concrete Crack Dataset）
- 公开工程报告和技术标准文档中的配图
- 不使用付费数据集、不下载受版权保护的商业图片
- 图片存储在 gitignored 目录，只在本地评测使用

### 评测集规模逻辑

| 评测组 | 初始规模 | 扩展条件 | 扩展规模 |
|---|---|---|---|
| 图片检索 | 复跑 100 + 新增 20 边缘 | Gate 1 任一 FAIL | 边缘集扩到 50 |
| 用户图片分析 | 20 | Gate 2 任一 FAIL | 扩到 50 |
| 表格检索 | 20-30（视回填量） | Gate 3 任一 FAIL | 扩到 50 |

## 供应商与 API 约束

- 视觉模型: GLM-4.6V via Paratera（5 路分片 `/v1/p001` ~ `/v1/p005`）
- Embedding: GLM-Embedding-3 via Paratera
- Rerank: GLM-Rerank via Paratera `/v1/p002/rerank`
- api.jina.ai 仍然 TLS 不可用
- 本阶段所有评测使用真实 API，不使用 deterministic mock
