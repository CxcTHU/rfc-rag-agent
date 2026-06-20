# Subagent C — Goal Prompt：精确引用定位

请为本线程设置一个 goal：

按照当前项目的 AGENT.MD、README.md、docs/progress.md、docs/architecture.md，以及阶段 47 的 task_plan.md，在主 agent 完成 Phase 0-2 共享基础设施后的公共基线上，完成 **Track C：精确引用定位（chunk bbox 回填 + 定位服务 + API 传递）** 的开发与测试，并停在可交付状态。

目标分支建议为（从主 agent 的 phase-47 基线创建 worktree）：

codex/phase-47-track-c-citation-location

## 执行要求

1. 首先修改当前对话线程名称为：阶段47-TrackC-引用定位。
2. 先阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、task_plan.md、findings.md、progress.md。
3. 确认当前基线已包含 Phase 1-2 的共享基础设施（Alembic 迁移 `0005` 中 `content_bbox_json` 字段、schemas 中 `content_bbox` 预留字段）。
4. **不修改共享文件**：不得直接修改 `alembic/versions/`、`app/db/models.py`、`app/schemas/agent.py`、`app/frontend/static/app.js`、`app/api/agent.py`、`README.md`、`docs/progress.md`、`docs/architecture.md`。这些文件由主 agent 统一管理。
5. 可以创建分支和提交，但阶段完成后不要 git push；等待主 agent review 和 merge。

## 背景

当前系统的引用功能仅提供文档标题和 chunk 内容，用户看到引用后无法快速定位到原文 PDF 中的具体位置。Phase 46 已为每个 chunk 添加了 `page_number` 字段（覆盖率 100%），Phase 47 Phase 1 新增了 `content_bbox_json` 字段。本 Track 的目标是：回填 bbox 数据 → 提供定位服务 → API 透传 → 前端可跳转到具体页面和高亮区域。

## 核心交付

### 1. Chunk Bbox 回填脚本 `scripts/backfill_phase47_chunk_bbox.py`

核心逻辑：
- 遍历 chunks 表中 `chunk_type='text'` 且 `content_bbox_json IS NULL` 的记录
- 对每个 chunk，根据 `document.raw_path` 打开对应 PDF
- 使用 PyMuPDF `page.search_for(chunk_content_snippet)` 定位 chunk 在 PDF 页面中的空间位置
- 将匹配到的 bbox 写入 `content_bbox_json` 字段，格式为：

```json
{
  "page": 5,
  "bboxes": [
    {"x0": 72.0, "y0": 120.5, "x1": 540.0, "y1": 185.3},
    {"x0": 72.0, "y0": 185.3, "x1": 540.0, "y1": 250.1}
  ],
  "confidence": "exact"
}
```

匹配策略：
- 优先使用 chunk content 的前 80 个字符做精确搜索
- 如果精确搜索无结果，退化为前 40 个字符
- 如果仍无结果，使用 `page_number` 字段定位到页面，标记 `confidence: "page_only"`
- 对图片 chunk（`chunk_type` 含 image）跳过（已有 source_image_path 定位）

参数：
- `--dry-run`：只统计不写入
- `--limit N`：处理前 N 个 chunk
- `--doc-id D`：只处理特定文档

输出统计：
- total_chunks, exact_match, partial_match, page_only, failed, skipped_image

### 2. 引用定位服务 `app/services/retrieval/citation_locator.py`

```python
class CitationLocator:
    """根据 chunk 的 bbox 数据生成前端可用的定位信息"""

    def locate(self, chunk_id: int, db: Session) -> CitationLocation | None:
        """
        查询 chunk 的 content_bbox_json + page_number，
        生成前端跳转所需的定位信息
        """

    def locate_batch(self, chunk_ids: list[int], db: Session) -> dict[int, CitationLocation]:
        """批量定位，减少 DB 查询次数"""
```

`CitationLocation` dataclass：

```python
@dataclass
class CitationLocation:
    chunk_id: int
    document_id: int
    document_title: str
    file_name: str
    page_number: int | None
    bboxes: list[dict] | None       # [{"x0":..., "y0":..., "x1":..., "y1":...}]
    confidence: str                  # "exact" | "partial" | "page_only" | "none"
    pdf_url: str | None              # 相对路径，供前端打开 PDF
```

### 3. 检索结果增强 — 追加定位信息

在 `app/services/agent/tools.py` 的 `search_knowledge()` 和 `search_figures()` 方法返回结果中，追加 `content_bbox` 信息。具体做法：

在 `tools.py` **末尾追加** 一个辅助函数：

```python
def _enrich_results_with_citation_location(
    results: list[AgentSearchResultItem],
    db: Session,
) -> list[AgentSearchResultItem]:
    """为检索结果批量追加定位信息"""
```

该函数在 `search_knowledge` 和 `search_figures` 的返回路径上被调用。不修改原有函数签名，只在结果返回前做一次批量查询和字段填充。

### 4. 测试覆盖

- `tests/test_citation_locator.py`：
  - 单元测试：给定有 bbox 的 chunk → 返回 CitationLocation
  - 无 bbox 的 chunk → confidence="none"
  - 批量定位：3 个 chunk → 返回 3 个结果
- `tests/test_backfill_chunk_bbox.py`：
  - Mock PDF：PyMuPDF page.search_for() → 验证 bbox JSON 格式
  - 无文本层 PDF → confidence="page_only"
  - dry-run 模式 → 不写入数据库

## 不做的事

- 不做前端 PDF 查看器集成（主 agent Phase 5 统一做 pdf.js 集成）
- 不新增 Alembic 迁移（`content_bbox_json` 已在 Phase 1 迁移中添加）
- 不处理图片 chunk 的 bbox（图片有 source_image_path，不需要文本定位）
- 不修改共享文件
- 不让真实 API 成为全量测试前提

## 完成标准

- 回填脚本能对项目 PDF 正确提取 chunk bbox
- dry-run 模式能输出覆盖率统计
- CitationLocator 能根据 bbox 数据生成定位信息
- 检索结果中包含 content_bbox 字段
- 全量 pytest 通过且不退化
