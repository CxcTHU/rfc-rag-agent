# Subagent B — Goal Prompt：用户图片上传与多模态分析

请为本线程设置一个 goal：

按照当前项目的 AGENT.MD、README.md、docs/progress.md、docs/architecture.md，以及阶段 47 的 task_plan.md，在主 agent 完成 Phase 0-2 共享基础设施后的公共基线上，完成 **Track B：用户图片上传与多模态分析（含以图搜图）** 的开发与测试，并停在可交付状态。

目标分支建议为（从主 agent 的 phase-47 基线创建 worktree）：

codex/phase-47-track-b-user-image-upload

## 执行要求

1. 首先修改当前对话线程名称为：阶段47-TrackB-图片上传分析。
2. 先阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、task_plan.md、findings.md、progress.md。
3. 确认当前基线已包含 Phase 1-2 的共享基础设施（schemas 中 `image_analysis` 预留字段、react_actions 中 `analyze_user_image` action type、config 中 `ENABLE_USER_IMAGE_UPLOAD` / `USER_IMAGE_MAX_SIZE_MB`）。
4. **不修改共享文件**：不得直接修改 `alembic/versions/`、`app/db/models.py`、`app/schemas/agent.py`、`app/frontend/static/app.js`、`app/api/agent.py`、`README.md`、`docs/progress.md`、`docs/architecture.md`。这些文件由主 agent 统一管理。
5. 可以创建分支和提交，但阶段完成后不要 git push；等待主 agent review 和 merge。

## 核心交付

### 1. 图片分析服务 `app/services/agent/image_analysis.py`

核心逻辑：

```python
class UserImageAnalyzer:
    """处理用户上传图片的分析服务"""

    async def analyze(self, image_path: str, user_question: str) -> ImageAnalysisResult:
        """
        1. 调用 GLM-4.6V 视觉模型识别图像内容，生成结构化描述
        2. 将描述文本作为查询，调用 EmbeddingProvider 生成 embedding
        3. 执行双路检索：
           a. search_knowledge：文本检索，找到相关理论/规范段落
           b. search_figures：以图搜图，在知识库 15628 条 image_description chunks 中
              找到视觉相似的文献图片
        4. 融合检索结果 + 视觉描述 → 返回 ImageAnalysisResult
        """
```

`ImageAnalysisResult` dataclass：

```python
@dataclass
class ImageAnalysisResult:
    image_description: str          # 视觉模型对上传图片的描述
    related_text_chunks: list       # 文本检索结果
    similar_figures: list           # 以图搜图结果
    fused_context: str              # 融合后的上下文（供 answer_with_citations 使用）
```

### 2. 图片上传临时存储 `app/services/agent/image_storage.py`

- 用户上传的图片存储到 `data/user_uploads/{date}/{uuid}.{ext}`
- 目录已在 `.gitignore` 中排除
- 文件大小校验：超过 `USER_IMAGE_MAX_SIZE_MB` 拒绝
- 格式校验：只接受 PNG/JPG/JPEG/WEBP/BMP
- 自动清理：提供 `cleanup_old_uploads(days=7)` 函数

### 3. 视觉模型调用封装

复用项目已有的 GLM-4.6V 调用逻辑（参考 `app/services/ingestion/image_describer.py`）：
- 使用 Paratera 供应商的 `open.bigmodel.cn/api/paas/v4/chat/completions`
- 5 路分片轮转（`/v1/p001` ~ `/v1/p005`）
- Prompt 针对用户场景优化："请分析这张工程现场照片，描述你看到的混凝土结构特征、可能的缺陷类型、严重程度，以及与相关工程规范的关联。"

### 4. Agent 工具 `analyze_user_image()` — 追加到 `app/services/agent/tools.py`

在 `tools.py` 文件 **末尾追加** `analyze_user_image()` 方法到 `AgentTools` 类：

```python
def analyze_user_image(self, image_path: str, question: str) -> AgentToolResult:
    """分析用户上传的图片，结合知识库生成回答"""
```

逻辑：
- 调用 `UserImageAnalyzer.analyze()` 获取分析结果
- 将 `fused_context` 格式化为 AgentToolResult
- 包含视觉描述 + 文本引用 + 相似图片引用

### 5. 以图搜图核心流程

这是本 Track 的关键创新点：

```text
用户上传图片
  → GLM-4.6V 生成描述文本（如"混凝土表面出现竖向贯穿裂缝，宽度约0.5mm"）
  → 描述文本 embedding（GLM-Embedding-3）
  → 在 chunk_type='image_description' 的 15628 条向量中做余弦相似度检索
  → 返回知识库中视觉相似的文献图片（带 source_image_path 和原文描述）
  → 用户可看到："在《XX规范》第X页发现类似裂缝图片"
```

关键参数：
- `IMAGE_TO_IMAGE_MIN_SCORE = 0.55`（以图搜图阈值，略高于一般检索）
- `IMAGE_TO_IMAGE_TOP_K = 5`（最多返回 5 张相似图片）
- 复用已有的 `search_figures()` 中的向量检索逻辑，但输入从用户查询文本变为视觉描述文本

### 6. ReAct 集成

在 `app/services/agent/react_agent.py` 的 system prompt 中追加 `analyze_user_image` 工具描述：

```
analyze_user_image(image_path, question) — 分析用户上传的图片。自动识别图片内容，在知识库中搜索相关文本资料和相似图片，生成带引用的综合分析。当用户上传了图片并提问时使用。
```

在 `_execute_react_action()` 中追加 `analyze_user_image` 分支。

### 7. API 层图片接收

新增 `app/api/image_upload.py`：

```python
@router.post("/agent/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """接收用户上传的图片，返回临时存储路径"""
```

- 校验文件类型和大小
- 存储到 `data/user_uploads/`
- 返回 `{"image_id": "uuid", "path": "...", "filename": "..."}`

注意：这是一个独立的新 router 文件，不修改 `app/api/agent.py`。主 agent 后续会在 `app/main.py` 注册。

### 8. 测试覆盖

- `tests/test_image_analysis.py`：
  - 单元测试（mock 视觉模型）：给定图片描述 → 验证双路检索被触发
  - 以图搜图逻辑：给定描述 embedding → 验证在 image_description chunks 中检索
  - 大小校验：10MB+ 文件 → 拒绝
  - 格式校验：.txt 文件 → 拒绝
- `tests/test_image_upload_api.py`：
  - FastAPI TestClient：上传合法图片 → 200 + 返回 image_id
  - 上传超大文件 → 413
  - 上传非图片文件 → 400

## 不做的事

- 不做前端上传 UI（主 agent Phase 5 统一做）
- 不做图片持久化到知识库（用户上传图片是临时的，不入库）
- 不新增 Alembic 迁移（不需要新字段）
- 不修改共享文件
- 不把视觉模型的 raw_response 写入 Git/CSV/测试
- 不让真实 API 成为全量测试前提（测试中 mock 视觉模型）

## 完成标准

- `UserImageAnalyzer` 能对给定图片生成描述并执行双路检索
- `analyze_user_image()` 能在 ReAct 链路中被调用
- 图片上传 API 能正确接收和存储图片
- 以图搜图能在 15628 条 image_description 中找到相似图片
- 全量 pytest 通过且不退化
