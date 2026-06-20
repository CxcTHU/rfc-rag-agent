# Subagent A — Goal Prompt：PDF 表格结构化提取与检索

请为本线程设置一个 goal：

按照当前项目的 AGENT.MD、README.md、docs/progress.md、docs/architecture.md，以及阶段 47 的 task_plan.md，在主 agent 完成 Phase 0-2 共享基础设施后的公共基线上，完成 **Track A：PDF 表格结构化提取与检索** 的开发与测试，并停在可交付状态。

目标分支建议为（从主 agent 的 phase-47 基线创建 worktree）：

codex/phase-47-track-a-table-extraction

## 执行要求

1. 首先修改当前对话线程名称为：阶段47-TrackA-表格提取。
2. 先阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、task_plan.md、findings.md、progress.md。
3. 确认当前基线已包含 Phase 1-2 的共享基础设施（Alembic 迁移 `0005`、models 中 `content_bbox_json`、schemas 中 `table_content` 预留字段、react_actions 中 `search_tables` action type）。
4. **不修改共享文件**：不得直接修改 `alembic/versions/`、`app/db/models.py`、`app/schemas/agent.py`、`app/frontend/static/app.js`、`app/api/agent.py`、`README.md`、`docs/progress.md`、`docs/architecture.md`。这些文件由主 agent 统一管理。
5. 可以创建分支和提交，但阶段完成后不要 git push；等待主 agent review 和 merge。

## 核心交付

### 1. 表格提取服务 `app/services/ingestion/table_extractor.py`

核心逻辑：
- `extract_tables(pdf_path: str, doc_id: int) -> list[TableChunk]`
- 使用 PyMuPDF `page.find_tables()` 提取所有表格（零外部依赖）
- 每个表格生成一个 `TableChunk` dataclass，包含：
  - `page_number: int`
  - `bbox: tuple[float, float, float, float]` — 表格在页面中的位置
  - `markdown_content: str` — 表格内容转 Markdown 格式
  - `header_text: str | None` — 表格标题（向上搜索最近的文本块）
  - `row_count: int`
  - `col_count: int`
- 过滤规则：行数 < `TABLE_EXTRACTION_MIN_ROWS`（默认 2）的跳过
- 对提取失败的页面（PDF 扫描件无文本层）记录日志但不抛异常

### 2. 存量表格回填脚本 `scripts/backfill_phase47_tables.py`

- 遍历 `documents` 表中 `file_extension='.pdf'` 的文档
- 对每个 PDF 调用 `extract_tables()`
- 将表格以 `chunk_type='table'` 写入 chunks 表，`content` 为 Markdown 表格文本
- 调用 GLM-Embedding-3 生成 embedding（使用现有 `EmbeddingProvider`）
- 支持 `--dry-run` 和 `--limit N` 参数
- 输出统计：processed_docs, extracted_tables, skipped_small, failed_pages

### 3. 检索工具 `search_tables()` — 追加到 `app/services/agent/tools.py`

在 `tools.py` 文件 **末尾追加** `search_tables()` 方法到 `AgentTools` 类：

```python
def search_tables(self, query: str) -> AgentToolResult:
    """搜索知识库中的结构化表格数据"""
```

逻辑：
- 向量检索 + `chunk_type='table'` 过滤
- MIN_TABLE_RELEVANCE_SCORE = 0.45（表格匹配度通常低于文本）
- 返回 Markdown 表格内容 + 所属文档标题 + 页码
- 结果格式与 `search_figures()` 类似

### 4. ReAct 集成

在 `app/services/agent/react_agent.py` 的 system prompt 中追加 `search_tables` 工具描述：

```
search_tables(query) — 搜索知识库中的结构化表格数据（配合比、试验结果、材料参数等）。当用户查询涉及数值数据、表格、配合比、试验参数时使用。
```

在 `_execute_react_action()` 中追加 `search_tables` 分支。

### 5. 评测数据

- `data/evaluation/phase47_table_retrieval_questions.csv`：10-15 条表格检索问题，覆盖：
  - 配合比查询（"水泥用量是多少"）
  - 试验结果查询（"28天抗压强度"）
  - 材料参数查询（"粉煤灰掺量"）
  - 对比查询（"不同配合比的强度对比"）
- `scripts/evaluate_phase47_table_retrieval.py`：精度/召回评测脚本

### 6. 测试覆盖

- `tests/test_table_extractor.py`：
  - 单元测试：解析带表格的 PDF → 验证 Markdown 输出格式
  - 空表格/无表格 PDF → 返回空列表
  - 行数过滤：1 行表格 → 被跳过
- `tests/test_search_tables.py`：
  - 集成测试：插入 table chunk → search_tables() 能召回
  - 无匹配 → 返回空结果

## 不做的事

- 不做前端展示（主 agent Phase 5 统一做）
- 不做 Camelot/Marker 高级表格提取（后续阶段可选扩展）
- 不新增 Alembic 迁移（chunk_type='table' 使用已有 chunk_type 字段）
- 不安装新的 Python 依赖（PyMuPDF 已在项目中）
- 不修改共享文件
- 不把 API key 写入代码/测试/CSV
- 不让真实 API 成为全量测试前提

## 完成标准

- `table_extractor.py` 能对项目中的 PDF 正确提取表格
- `search_tables()` 能在 ReAct 链路中被调用并返回格式化结果
- 回填脚本 dry-run 模式能输出统计
- 全量 pytest 通过且不退化
- 评测脚本能运行并输出基线指标
