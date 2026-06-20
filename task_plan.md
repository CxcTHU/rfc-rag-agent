# 阶段 47 任务计划：多模态交互增强与用户体验升级

## Goal

在阶段 46 完成图片质量修复、题注关联和精确图片检索的基础上，完成四条并行主线：
（A）PDF 表格结构化提取与检索；
（B）用户图片上传与多模态分析（以图搜图 + RAG 融合）；
（C）精确引用定位（PDF 页面跳转与高亮）；
（D）用户反馈闭环（评测集自增长）。

四条主线代码路径独立，采用**主 agent 基础设施 + 四 subagent 并行开发 + 主 agent 集成**的协作模式。

## Current Phase

Phase 3：四个 subagent 已从 Phase 2 公共基线并行启动，等待 Track A/B/C/D 完成后主 agent review + merge。

## 当前基线与工作区状态

- Git 基线：`main / origin/main` 应为阶段 46 合并后状态；`phase-46-complete` tag 是 `main` 的祖先。
- 当前分支：`codex/phase-47-multimodal-interaction-upgrade`。
- 本地 DB: SQLite, documents≈1146, chunks≈48810, chunk_embeddings≈71139, image_chunks=15628。
- Stage 30: 91.52 / A / pass（必须保持不退化）。
- 全量测试: Phase 2 baseline `1002 passed`。
- Alembic head: `20260621_0005_phase47_shared_schema`。

## 协作模式：主 agent + 四 subagent 并行

```text
Phase 0-2   主 agent：启动校准 + 共享基础设施（Alembic 迁移、models、schemas 预留）
Phase 3     四 subagent 并行开发（各自 worktree，只改自己的新文件和工具函数）
Phase 4-5   主 agent：逐个 review + merge subagent 成果
Phase 6     主 agent：前端统一集成
Phase 7     主 agent：全量回归验证 + 文档 + Obsidian 收尾
```

### 共享文件由主 agent 独占

以下文件只有主 agent 可以修改，subagent 不得直接改动：

- `alembic/versions/` — 迁移链必须线性
- `app/db/models.py` — 数据模型统一
- `app/schemas/agent.py` — Agent API schema 统一
- `app/frontend/static/app.js` — 前端统一集成
- `app/api/agent.py` — Agent API 路由统一
- `README.md`、`docs/progress.md`、`docs/architecture.md` — 文档统一

## Phases

### Phase 0：启动校准与规划落盘（主 agent）

- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认阶段 46 已合并到 `origin/main`，不移动已有阶段 tag
- [x] 从 `main` 创建 `codex/phase-47-multimodal-interaction-upgrade`
- [x] 校准 `task_plan.md`、`findings.md`、`progress.md`

### Phase 1：共享基础设施 — 数据模型与迁移（主 agent）

- [x] 新增 Alembic 迁移 `20260621_0005_phase47_shared_schema.py`，一次性包含：
  - `chunks` 表新增 `content_bbox_json` 可空 Text 字段（存储 chunk 在 PDF 页面中的空间位置）
  - 新增 `qa_feedback` 表（id, question_answer_log_id FK nullable, conversation_id FK nullable, message_id FK nullable, question TEXT, answer TEXT, rating VARCHAR(10) NOT NULL, reason VARCHAR(50) nullable, comment TEXT nullable, created_at DATETIME）
- [x] 更新 `app/db/models.py`：新增 `QAFeedback` 模型、`Chunk.content_bbox_json` 字段
- [x] 更新 `app/schemas/agent.py`：预留 `table_content`、`image_analysis`、`content_bbox` 字段
- [x] 新增 `app/schemas/feedback.py`：`FeedbackCreateRequest`、`FeedbackResponse`
- [x] 新增 `app/db/feedback_repository.py`：`FeedbackRepository` CRUD
- [x] 运行 `alembic upgrade head`，确认迁移成功
- [x] 运行全量 pytest 确认不退化

### Phase 2：共享基础设施 — API 路由与配置预留（主 agent）

- [x] 新增 `app/api/feedback.py`：`POST /feedback`、`GET /feedback/stats`
- [x] 在 `app/main.py` 注册 feedback router
- [x] `app/core/config.py` 新增配置项：
  - `ENABLE_TABLE_EXTRACTION: bool = True`
  - `ENABLE_USER_IMAGE_UPLOAD: bool = True`
  - `TABLE_EXTRACTION_MIN_ROWS: int = 2`
  - `USER_IMAGE_MAX_SIZE_MB: float = 10.0`
- [x] 在 `app/services/agent/react_actions.py` 预留 `search_tables` 和 `analyze_user_image` action type
- [x] 运行全量 pytest 确认不退化
- [x] 提交共享基础设施到 phase-47 分支，作为四个 subagent 的公共基线（local commit `25674308`，未 push/tag/PR）

### Phase 3：四 subagent 并行开发

四个 subagent 从 Phase 2 完成后的公共基线分别创建 worktree，并行开发。每个 subagent 只改自己的新文件和指定的工具函数（在 tools.py 中追加函数），不修改共享文件。

当前调度状态：

- [x] Track A 分支 `codex/phase-47-track-a-table-extraction`，worktree `C:\Users\admin\.codex\worktrees\2ff9\rfc-rag-agent`，worker Zeno。
- [x] Track B 分支 `codex/phase-47-track-b-user-image-upload`，worktree `C:\Users\admin\.codex\worktrees\5e65\rfc-rag-agent`，worker Hume。
- [x] Track C 分支 `codex/phase-47-track-c-citation-location`，worktree `C:\Users\admin\.codex\worktrees\cafa\rfc-rag-agent`，worker Singer。
- [x] Track D 分支 `codex/phase-47-track-d-feedback-loop`，worktree `C:\Users\admin\.codex\worktrees\faf2\rfc-rag-agent`，worker Poincare。

#### Subagent A：PDF 表格结构化提取与检索

详见 subagent_a_goal.md。

核心交付：
- `app/services/ingestion/table_extractor.py`
- `scripts/backfill_phase47_tables.py`
- `search_tables()` 工具函数（追加到 `tools.py`）
- `data/evaluation/phase47_table_retrieval_questions.csv`
- `scripts/evaluate_phase47_table_retrieval.py`
- 测试覆盖

#### Subagent B：用户图片上传与多模态分析

详见 subagent_b_goal.md。

核心交付：
- `app/services/agent/image_analysis.py`
- `analyze_user_image()` 工具函数（追加到 `tools.py`）
- 用户上传图片的临时存储与清理逻辑
- 以图搜图：描述文本 → search_figures 联动
- 测试覆盖

#### Subagent C：精确引用定位

详见 subagent_c_goal.md。

核心交付：
- `scripts/backfill_phase47_chunk_bbox.py`
- `app/services/retrieval/citation_locator.py`
- API response 中传递 `content_bbox` + `page_number`
- 测试覆盖

#### Subagent D：用户反馈闭环

详见 subagent_d_goal.md。

核心交付：
- `app/services/feedback/feedback_service.py`
- `scripts/export_phase47_feedback_to_eval.py`
- 反馈 → 评测集自增长管道
- 测试覆盖

### Phase 4：主 agent 逐个 review + merge（主 agent）

- [ ] Review subagent A 成果，merge 表格提取到主分支
- [ ] Review subagent B 成果，merge 图片上传到主分支
- [ ] Review subagent C 成果，merge 引用定位到主分支
- [ ] Review subagent D 成果，merge 反馈闭环到主分支
- [ ] 解决 `tools.py`、`react_actions.py` 的函数级合并冲突
- [ ] 运行全量 pytest 确认合并后不退化

### Phase 5：前端统一集成（主 agent）

- [ ] 表格 evidence card：Markdown 表格渲染，`search_tables` 结果展示
- [ ] 图片上传：聊天输入框旁 📎 按钮，支持拖拽/粘贴图片，预览缩略图
- [ ] 引用定位：点击引用来源时打开 PDF 并跳转到对应页面（pdf.js 或新窗口 URL 带页码参数）
- [ ] 反馈按钮：每条回答下方 👍/👎，负反馈弹出原因选择
- [ ] 统一交互风格、布局和移动端适配
- [ ] 运行 `node --check app/frontend/static/app.js`

### Phase 6：回归验证 + 文档 + Obsidian 收尾（主 agent）

- [ ] 全量 pytest 通过
- [ ] Stage 30 评分保持 91.52/A/pass 或不退化
- [ ] API smoke：所有既有端点 + 新增 `/feedback` 均 200
- [ ] 浏览器验证：四个新功能 desktop + mobile 无溢出
- [ ] 同步 README.md、docs/progress.md、docs/architecture.md
- [ ] 新增 docs/phase_reviews/phase-47.md 验收草稿
- [ ] 更新 Obsidian 本地知识库
- [ ] 停在用户人工核验前状态

## 安全边界

- Stage 30 必须保持 91.52/A/pass 或不退化
- 不让真实 API 成为 CI 或本地全量测试前提
- 不把 API key、Bearer token、供应商原始响应写入 Git/CSV/文档/测试/Obsidian
- 用户上传图片存储在 `data/user_uploads/`（gitignored），定期清理
- 反馈数据不保存 API key 或供应商敏感响应
- 未经用户人工核验，不 git add/commit/tag/push/建 PR
- 共享文件（models、schemas、migrations、frontend）只由主 agent 修改
