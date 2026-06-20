# 阶段 47 Findings

## 阶段 46 基线确认

- 全量测试: 996 passed
- Stage 30: 91.52 / A / pass
- 数据库: documents=1146, chunks=48810, chunk_embeddings=71139, image_chunks=15628, captioned=7853
- Alembic head: `20260620_0004_chunk_page_number`
- page_number 覆盖率: 100%
- image_description 覆盖率: 15628/15628 (100%)

## Phase 0-2 启动与共享基础设施结果

- 线程名已更新为：阶段47-主agent-多模态交互增强。
- 本地 `main` 已对齐 `origin/main`；`phase-46-complete -> ba44a68a` 是 `origin/main` 的祖先，tag 未移动。
- 已从 `main` 创建 `codex/phase-47-multimodal-interaction-upgrade`。
- Alembic 已升级到 `20260621_0005 (head)`。
- Phase 1 全量回归：`python -m pytest -q -> 999 passed`。
- Phase 2 全量回归：`python -m pytest -q -> 1002 passed`。
- Stage 30 校验：`python scripts/score_stage30_quality.py -> 91.52 / A / pass`。
- 当前未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR；Phase 2 公共基线提交等待用户确认。

## Phase 1-2 新增共享文件

- `alembic/versions/20260621_0005_phase47_shared_schema.py`：新增 `chunks.content_bbox_json` 与 `qa_feedback`。
- `app/db/models.py`：新增 `Chunk.content_bbox_json` 与 `QAFeedback`。
- `app/db/repositories.py`：`ChunkCreate` 支持 `content_bbox_json`。
- `app/db/feedback_repository.py`：新增 `FeedbackRepository`。
- `app/schemas/feedback.py`：新增反馈请求、响应与统计 schema。
- `app/schemas/agent.py`：预留 `table_content`、`image_analysis`、`content_bbox` 字段。
- `app/api/feedback.py`：新增 `POST /feedback` 与 `GET /feedback/stats`。
- `app/core/config.py`：预留表格提取、用户图片上传与大小/行数配置。
- `app/services/agent/react_actions.py`：预留 `search_tables` 与 `analyze_user_image` action type。
- `tests/test_phase47_shared_schema.py`、`tests/test_feedback_api.py`：覆盖共享 schema、反馈 API、ReAct action 预留。

## 当前阻塞点

- 四个 subagent worktree 应从 Phase 2 公共基线提交点创建。
- 由于项目安全边界写明“未经用户确认不 commit/tag/push”，当前停在未提交状态，等待用户确认是否允许提交 Phase 2 公共基线。

## 四 Track 独立性分析

### 共享文件冲突点

| 共享文件 | 涉及 Track | 决策 |
|---|---|---|
| `alembic/versions/` | A(无) + C(bbox) + D(feedback) | 主 agent Phase 1 一次性完成 |
| `app/db/models.py` | C(bbox) + D(feedback) | 主 agent Phase 1 一次性完成 |
| `app/schemas/agent.py` | A + B + C | 主 agent Phase 1 预留字段 |
| `app/services/agent/tools.py` | A + B + C | 各 subagent 追加独立函数，主 agent 合并 |
| `app/services/agent/react_actions.py` | A + B | 主 agent Phase 2 预留 action type |
| `app/frontend/static/app.js` | 全部 | 主 agent Phase 5 统一集成 |

### Subagent 可独立修改的文件

- Track A: `table_extractor.py`(新), `backfill_tables.py`(新), 评测脚本(新), 测试(新)
- Track B: `image_analysis.py`(新), `image_storage.py`(新), `image_upload.py`(新), 测试(新)
- Track C: `backfill_chunk_bbox.py`(新), `citation_locator.py`(新), 测试(新)
- Track D: `feedback_service.py`(新), `keyword_extractor.py`(新), 导出脚本(新), 测试(新)

结论：冲突集中在 models/schemas/migrations/frontend，由主 agent 独占后，四 Track 完全并行安全。

## 技术决策

### 表格提取策略

- 选用 PyMuPDF `find_tables()`（零依赖，已在项目中）
- 不引入 Camelot/Marker/LayoutLMv3（避免 PyTorch/GPU 依赖）
- 扫描件 PDF（无文本层）暂不处理，记录日志

### 以图搜图方案

- 用户上传图片 → GLM-4.6V 描述 → embedding → 在 image_description chunks 中向量检索
- 复用已有 search_figures() 的检索逻辑，只是输入从用户查询变为视觉描述
- 阈值 `IMAGE_TO_IMAGE_MIN_SCORE = 0.55`（略高于一般检索的 0.50）

### Bbox 回填策略

- 使用 PyMuPDF `page.search_for()` 做文本定位
- 三级退化：精确匹配（80字符）→ 部分匹配（40字符）→ 仅页面定位
- 图片 chunk 跳过（已有 source_image_path）

### 反馈闭环策略

- 正面反馈自动导入评测集
- 关键词提取用正则分词（不引入 jieba）
- 评测集 query_id 前缀 `feedback_` 区分来源
- 敏感信息正则过滤

## 供应商与 API 约束

- 视觉模型: GLM-4.6V via Paratera（5 路分片）
- Embedding: GLM-Embedding-3 via Paratera
- Rerank: GLM-Rerank via Paratera `/v1/p002/rerank`
- api.jina.ai 仍然 TLS 不可用
- 所有测试 mock API 调用，不依赖真实供应商
