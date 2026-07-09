# Phase 60 Goal Prompt: Structured TableRAG Ingestion

阅读 AGENT.MD 和相关项目文件，了解项目开发进度。

现在正式进入阶段 60 的开发。请为本线程设置 goal：

按照当前项目的 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md，以及 Phase 58 之后默认 tool_calling_agent / 多通道检索 / evidence cache 的完成状态，持续推进本项目开发，直到阶段 60「结构化 TableRAG 入库旁路底座」的开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。

目标分支：

```text
codex/phase-60-structured-table-rag
```

重要：当前主工作区存在未提交的后端/前端链路优化改动。不要在该脏工作区开发 Phase 60。请从 origin/main 新建独立 worktree：

```text
G:\Codex\program\rfc-rag-agent-phase60-tablerag
```

执行要求：
- 首先修改当前对话线程名称为：阶段60-结构化TableRAG入库。
- 在新 worktree 中先阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、task_plan.md、findings.md、progress.md；若三份规划文件不存在，按 Planning with Files 创建 Phase 60 专属版本。
- 运行 git status -sb、git log --oneline -5、git worktree list，确认新 worktree 干净且分支正确。
- 保留其他线程已有改动，不重置 Git，不覆盖无关文件，不从脏 main 开发。
- 阶段完成后不要执行 git add、commit、tag、push 或 PR；等待用户人工核验。
- 本阶段只做旁路结构化 TableRAG 入库、检索单元和离线/只读验证；默认 Agent/Search 链路不切换。
- 不新增外部语料、爬虫、PDF、模型权重或写入型 Agent 工具。
- 不得写入真实 .env、.env.prod、数据库密码、JWT secret、Redis 密码、API key、Bearer token、provider raw response、raw_response、reasoning_content、hidden thought、完整 answer、完整 chunk、受限全文、私有日志或长期用户画像。

Phase 60 顺序：
- 60A 启动校准与基线审计：确认 worktree、当前表格 chunk、table_extractor、backfill、search_tables、table_text channel。
- 60B 结构化 schema 设计：新增 document_tables、document_table_columns、document_table_rows、document_table_cells、table_retrieval_units、table_extraction_runs；必要时新增 table_retrieval_unit_embeddings。保留 chunks.chunk_type="table" 作为兼容和 citation 回退。
- 60C 结构化抽取与 backfill：复用 PyMuPDF find_tables 的 rows/page/bbox/header_text，保存 raw/normalized rows、headers、units、quality_score、structure_hash；支持 dry-run、resume、document_id、limit；旧 Markdown 表格仅作 fallback 反解析。
- 60D 检索单元生成：为 table_summary、table_schema、row_pack、column_pack、cell_fact、caption_context 生成检索文本和 metadata；独立 BM25/embedding，不塞回普通 chunks。
- 60E 旁路 StructuredTableSearchService：实现 TableQueryPlanner、summary/schema/row/cell 多路召回、exact header/cell match、numeric/unit filter、RRF/加权融合、结构化 hydrate，返回 table_id、headers、rows、matched_units、citation。
- 60F 评测与安全：新增脱敏 table retrieval eval，覆盖找表、找列、找行、精确单元格、单位/数值、负例；输出只存 id/count/score/短标题/指标，不存完整表格正文或 provider payload。
- 60G 文档、Obsidian 与交班：更新 README、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/phase_reviews/phase-60.md、docs/stage60_structured_table_rag_goal_prompt.md 和本地 Obsidian 草稿。

完成标准：
- 结构化表格对象和检索单元可从现有 PDF/table chunks 重建。
- 旁路服务能返回结构化 headers/rows/cells/matched_units/citation。
- 默认 search_tables、hybrid_search、tool_calling_agent 行为不变或仅 feature flag 默认关闭。
- focused tests、schema/backfill dry-run、旁路检索评测通过。
- 文档说明 Text-to-SQL 不是第一入口；只允许候选 table_id 限定后的只读可选层。
- 最终汇报说明分支、worktree、主要改动、测试结果、未提交状态、合流风险和人工核验重点。
