# RFC-RAG-Agent

面向水利工程堆石混凝土技术的文献检索与引用式问答 Agent。

本项目目标是从零搭建一个垂直领域 RAG 系统，逐步实现：

- 公开资料采集与来源管理
- 文档清洗、切分与元数据保存
- embedding 向量化与语义检索
- 基于检索资料的引用式问答
- 国产大模型接入
- 检索与回答质量评测
- 受控 Agent 工具调用与前端界面

## 当前阶段

阶段 18 之后增量（中文全文语料 + 拒答边界校准，待人工核验）：在 `claude/phase-18-corpus-evaluation-quality` 分支、阶段 18 主体之后，导入了用户合法下载的中文堆石混凝土全文,并校准了 off-topic 拒答边界。详见 `docs/stage18_followup_chinese_corpus.md`。要点：

- 中文全文入库 **298 篇**（`scripts/import_papers_corpus.py`，新增 `cryptography>=3.1` 解密知网 AES PDF）；语料 documents **465** / chunks **8918** / 深度全文 **约 340 篇**。
- 确定性 + 真实 Jina 索引全覆盖；建索引支持 `--sleep-seconds` 限速与 `--max-retries` 退避重试。
- off-topic 拒答闭环（主题门 `has_topic_anchor` + `CORE_DOMAIN_TERMS`）：off-topic 5/5 拒答、on-topic 8/8 不误拒；quality gate 由 `review_required/high` 降为 `review_required/medium`。
- 中文问答验收：真实 MIMO+Jina 下回答忠实、可引用溯源（`data/evaluation/cn_fulltext_*.csv`）。
- 全量测试 **382 passed**。当前未提交、未打 tag、未推送。

---

阶段 18：语料扩充与评测/质量体系增强，正在 `claude/phase-18-corpus-evaluation-quality` 分支开发，等待用户人工核验。阶段 17（检索架构升级）已完成人工核验、提交、创建 `phase-17-complete` tag 并合并到 `main`（合并提交 `d633b95`，tag 指向最终功能提交 `5b5ef02`）。阶段 18 从含阶段 17 合并的 `main` 出发，按要求尚未执行 `git add`、`git commit`、`git tag`、`git push` 或创建 PR。

阶段 18 已完成（待人工核验）：

- PDF 解析加固（`app/services/ingestion/pdf_text.py`）：标题层级、表格、断词合并、公式/页眉页脚去噪，让全文 chunk 带真实 `heading_path`。
- 语料深度扩充（诚实报数）：`scripts/expand_open_access_corpus.py` 用 OpenAlex 发现 + 许可允许开放获取过滤 + 加固解析导入，深度全文 **11 -> 16**（open_access_pdf 10 -> 15），chunks 997 -> 1332；RFC 窄领域开放全文有限，未达 40-60 目标，按用户决策诚实报数、不造假。
- 难评测集（`data/evaluation/stage18_hard_queries.csv`，20 题：跨段证据 / 易混淆术语 / 需拒答边界），独立 CSV，不覆盖旧 baseline。
- 多配置检索对比（`scripts/evaluate_stage18_hard_set.py`）：keyword / vector / hybrid / bm25_rrf / bm25_rrf_context；结论 `keep_existing_hybrid`（bm25_rrf 未优于 hybrid）。
- quality gate（`scripts/build_stage18_quality_report.py`）：overall `review_required/high`，高风险阻断原因=off-topic 拒答边界偏松（真实风险，显式记录）。
- `/quality-report` 增强：只读筛选 + 风险队列 + 导出（CSV/JSON），新增 `/quality-report/data.json`、`/quality-report/export.csv`。
- 全量测试 **377 passed**。

阶段 4 最终提交：`b044459b9b8c2153e9225daa55af5d82cdcdb282`。

阶段 4 tag：`phase-4-complete`，已推送到 GitHub，并指向上述提交。

阶段 5 最终功能提交：`8c885e6cc714cc985933438697a7eb2523b26722`。

阶段 5 tag：`phase-5-complete`，指向上述提交。

阶段 6 最终功能提交：由 `phase-6-complete` tag 指向的提交标识。

阶段 6 tag：`phase-6-complete`。

阶段 7 最终功能提交：由 `phase-7-complete` tag 指向的提交标识。

阶段 7 tag：`phase-7-complete`。

阶段 8 最终功能提交：由 `phase-8-complete` tag 指向的提交标识。

阶段 8 tag：`phase-8-complete`。

阶段 9 最终功能提交：由 `phase-9-complete` tag 指向的提交标识。

阶段 9 tag：`phase-9-complete`。

阶段 9.1 补充提交：由 `phase-9.1-complete` tag 指向的提交标识。

阶段 9.1 tag：`phase-9.1-complete`。

阶段 10 最终功能提交：由 `phase-10-complete` tag 指向的提交标识。

阶段 10 tag：`phase-10-complete`。

阶段 11 最终功能提交：由 `phase-11-complete` tag 指向的提交标识。

阶段 11 tag：`phase-11-complete`。

阶段 12 最终功能提交：由 `phase-12-complete` tag 指向的提交标识。

阶段 12 tag：`phase-12-complete`。

阶段 13 最终功能提交：由 `phase-13-complete` tag 指向的提交标识。

阶段 13 tag：`phase-13-complete`。

阶段 14 最终功能提交：由 `phase-14-complete` tag 指向的提交标识。

阶段 14 tag：`phase-14-complete`。

阶段 15 最终功能提交：由 `phase-15-complete` tag 指向的提交标识。

阶段 15 tag：`phase-15-complete`。

阶段 16 最终功能提交：由 `phase-16-complete` tag 指向的提交标识。

阶段 16 tag：`phase-16-complete`。

阶段 17 已完成人工核验、提交、创建 `phase-17-complete` tag（指向最终功能提交 `5b5ef02`）并合并到 `main`（合并提交 `d633b95`）。

下一步建议：人工核验阶段 18 的 PDF 解析加固（`app/services/ingestion/pdf_text.py`）、语料扩充管线（`scripts/expand_open_access_corpus.py`，真实导入 5 篇、深度全文 11 -> 16）、难评测集与多配置对比（`data/evaluation/stage18_hard_queries.csv`、`scripts/evaluate_stage18_hard_set.py`、`stage18_config_comparison.csv`）、quality gate（`scripts/build_stage18_quality_report.py`、`docs/stage18_quality_report.md`）和增强版 `/quality-report`。多配置结论是 `keep_existing_hybrid`（bm25_rrf 未优于 hybrid）；quality gate 为 `review_required/high`，高风险阻断来自 off-topic 拒答边界偏松（真实风险，显式记录，留待后续校准 Phase，不在阶段 18 静默改默认拒答逻辑）。HyDE 仍只做离线实验，不进入默认链路或自动回归。

当前已经实现：

- FastAPI 应用入口
- `GET /health` 健康检查接口
- 基础配置读取
- SQLAlchemy 数据库层，包含 `documents` 和 `chunks` 两张表
- Markdown、TXT、PDF 的文本读取、清洗和 chunk 切分
- 本地资料导入链路：读取文件 -> 清洗 -> 切分 -> 保存
- `POST /documents/import`
- `GET /documents`
- `GET /documents/{document_id}/chunks`
- `POST /search`
- 阶段 1 关键词检索，包含中文/英文同义词扩展、标题/路径加分、泛词降权和来源均衡
- 关键词检索评测集与自动评测脚本
- `EmbeddingProvider` 抽象和本地 deterministic embedding provider
- `chunk_embeddings` 向量保存表
- `VectorIndexService` 向量索引构建服务
- `scripts/build_vector_index.py` 向量索引构建脚本
- `POST /search/vector` 向量检索 API
- `scripts/evaluate_vector_search.py` 向量检索评测脚本
- `data/evaluation/vector_results.csv` 向量检索评测结果
- `HybridSearchService` 混合检索服务，合并关键词和向量召回并去重、归一化、重排
- `POST /search/hybrid` 混合检索 API
- `scripts/evaluate_hybrid_search.py` 混合检索评测脚本
- `data/evaluation/hybrid_results.csv` 混合检索评测结果
- `docs/evaluation_plan.md` 阶段 6 评测计划
- `scripts/analyze_retrieval_errors.py` 检索错误案例分析脚本
- `data/evaluation/retrieval_error_cases.csv` 检索错误案例表
- `docs/agent_design.md` 阶段 7 Agent 化设计文档
- `app/services/agent/` 受控 Agent 工具层和编排服务
- `POST /agent/query` Agent 查询 API
- `data/evaluation/agent_queries.csv` Agent 评测集
- `scripts/evaluate_agent.py` Agent 评测脚本
- `data/evaluation/agent_results.csv` Agent 评测结果
- `docs/brain_workflow_design.md` 阶段 8 Brain 中控层与 workflow 设计文档
- `app/services/brain/` Brain 中控层、配置模型、workflow step 记录和回答编排服务
- `RetrievalConfig`、`WorkflowConfig` 和默认 RAG workflow：`filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer`
- `CitationAnswerService` 作为兼容门面复用 Brain workflow，`POST /chat` 和 Agent `answer_with_citations` 共享同一条回答路径
- `scripts/evaluate_brain_workflow.py` Brain 配置化评测脚本
- `data/evaluation/brain_workflow_results.csv` Brain 配置化评测结果
- `docs/model_provider_evaluation.md` 阶段 9 真实模型接入与模型评测设计文档
- `OpenAICompatibleEmbeddingProvider`，支持兼容 `/embeddings` 的真实向量模型服务
- `.env.example` 真实 chat/embedding provider 配置字段
- `scripts/build_vector_index.py` provider/model/dimension/API 参数
- `scripts/evaluate_model_configs.py` 模型配置评测汇总脚本
- `data/evaluation/model_config_results.csv` 模型配置评测结果
- Jina `jina-embeddings-v3` 真实向量索引和评测结果
- MIMO Token Plan `mimo-v2.5-pro` 真实 chat provider 接入验证
- `data/evaluation/mimo_jina_chat_results.csv` 真实 MIMO chat + Jina embedding 问答评测结果
- `data/evaluation/mimo_jina_agent_results.csv` 真实 MIMO chat + Jina embedding Agent 评测结果
- `data/evaluation/mimo_jina_brain_workflow_results.csv` 真实 MIMO chat + Jina embedding Brain workflow 评测结果
- `scripts/analyze_real_rag_failures.py` 阶段 10 真实 RAG 失败案例分析脚本
- `data/evaluation/real_rag_failure_cases.csv` 阶段 10 失败案例分析表
- Brain evidence confidence 低证据拒答保护，在真实模型生成前判断检索证据是否足够支撑回答
- `VectorSearchService` topic anchor rerank，在 vector-only 候选内部用主题锚点降低误召回
- `data/evaluation/stage10_jina_vector_results.csv` 阶段 10 Jina vector 校准评测结果
- `data/evaluation/stage10_jina_hybrid_results.csv` 阶段 10 Jina hybrid 校准评测结果
- `data/evaluation/stage10_mimo_jina_chat_results.csv` 阶段 10 MIMO + Jina chat 校准评测结果
- `data/evaluation/stage10_mimo_jina_agent_results.csv` 阶段 10 MIMO + Jina Agent 校准评测结果
- `data/evaluation/stage10_mimo_jina_brain_workflow_results.csv` 阶段 10 MIMO + Jina Brain workflow 校准评测结果
- `data/evaluation/user_questions.csv` 阶段 11 真实用户问题评测集，覆盖中文口语、英文、中英混合、工程中文和 unsupported 问题
- `scripts/evaluate_user_questions.py` 阶段 11 用户问题评测脚本
- `data/evaluation/user_question_results.csv` 阶段 11 用户问题评测结果
- `docs/stage11_user_evaluation_plan.md` 阶段 11 人工审阅与 LLM-as-judge 离线设计
- `data/evaluation/user_question_review_samples.csv` 阶段 11 人工审阅抽样表
- `data/evaluation/stage12_quality_review_results.csv` 阶段 12 质量审阅结果表
- `docs/stage12_quality_review.md` 阶段 12 质量审阅报告，说明 Faithfulness、Answer Coverage、Citation Quality 的人工判定标准和风险结论
- `docs/stage13_decompose_plan.md` 阶段 13 Decompose 与可解释证据合并预研计划
- `app/services/retrieval/decompose.py` 阶段 13 规则式 Decompose、子 query 检索、证据合并、`chunk_id` 去重、sub query provenance 和可解释 rerank 服务
- `scripts/evaluate_decompose.py` 阶段 13 Decompose 评测脚本
- `data/evaluation/stage13_decompose_results.csv` 阶段 13 Decompose 评测结果
- `docs/stage14_real_quality_calibration.md` 阶段 14 真实 embedding 与回答覆盖校准设计文档
- `scripts/evaluate_stage14_embedding_comparison.py` 阶段 14 embedding 配置对比汇总脚本
- `data/evaluation/stage14_embedding_comparison.csv` 阶段 14 embedding 对比结果表
- `scripts/evaluate_stage14_answer_coverage.py` 阶段 14 Answer Coverage 校准脚本
- `data/evaluation/stage14_answer_coverage_review.csv` 阶段 14 回答覆盖校准表
- `scripts/evaluate_stage14_decompose_provenance.py` 阶段 14 Decompose provenance 可读化脚本
- `data/evaluation/stage14_decompose_provenance_review.csv` 阶段 14 证据级 provenance 审阅表
- `docs/stage15_real_review_report.md` 阶段 15 真实配置复跑与质量审阅设计文档
- `scripts/evaluate_stage15_real_config.py` 阶段 15 真实配置复跑脚本，输出到 `data/evaluation/stage14_real/`
- `data/evaluation/stage14_real/real_config_status.csv` 阶段 15 真实配置 completed/error/skipped 状态表
- `scripts/evaluate_stage15_answer_coverage_review.py` 阶段 15 Answer Coverage 复核脚本
- `data/evaluation/stage15_answer_coverage_review.csv` 阶段 15 回答覆盖复核结果表
- `scripts/build_stage15_quality_report.py` 阶段 15 质量汇总与只读报告生成脚本
- `data/evaluation/stage15_quality_summary.csv` 阶段 15 质量汇总表
- `docs/stage15_quality_report.md` 阶段 15 Markdown 质量审阅报告
- `GET /quality-report` 阶段 15/16 只读质量报告页
- `app/frontend/quality_report.html` 阶段 16 静态只读质量风险闭环报告
- `docs/stage16_quality_risk_closure.md` 阶段 16 真实质量风险闭环设计文档
- `scripts/analyze_stage16_decompose_diagnostics.py` 阶段 16 real decompose SSL EOF 诊断脚本
- `data/evaluation/stage16_decompose_diagnostics.csv` 阶段 16 decompose 诊断结果表
- `scripts/evaluate_stage16_answer_coverage_closure.py` 阶段 16 Answer Coverage high/medium 闭环脚本
- `data/evaluation/stage16_answer_coverage_closure.csv` 阶段 16 回答覆盖风险闭环表
- `scripts/build_stage16_quality_closure_report.py` 阶段 16 质量闭环汇总与报告生成脚本
- `data/evaluation/stage16_quality_closure_summary.csv` 阶段 16 质量闭环汇总表
- `docs/stage16_quality_closure_report.md` 阶段 16 Markdown 质量风险闭环报告
- `docs/stage17_retrieval_architecture_upgrade.md` 阶段 17 检索架构升级设计文档
- `app/services/retrieval/context_expansion.py` 阶段 17 邻近 chunk 上下文扩展服务
- `app/services/retrieval/bm25_search.py` 阶段 17 BM25 lexical retriever
- `app/services/retrieval/rrf_fusion.py` 阶段 17 BM25+vector RRF 融合服务
- `scripts/evaluate_stage17_retrieval_upgrade.py` 阶段 17 检索升级评测脚本
- `data/evaluation/stage17_retrieval_upgrade_results.csv` 阶段 17 检索升级评测表
- `data/evaluation/stage17_retrieval_upgrade_manual_review.csv` 阶段 17 Phase 9 人工复核结果表
- `docs/stage17_retrieval_upgrade_report.md` 阶段 17 检索架构升级评测报告（含 Phase 9 人工复核摘要）
- `docs/stage18_corpus_evaluation_quality.md` 阶段 18 设计文档（语料扩充、PDF 解析加固、难评测集、多配置对比、quality gate、报告增强、安全边界）
- `app/services/ingestion/pdf_text.py` 阶段 18 PDF 文本结构化加固（标题层级、表格、断词、公式/页眉页脚去噪）
- `scripts/expand_open_access_corpus.py` 阶段 18 开放获取全文语料扩充管线（OpenAlex 发现 + 许可允许过滤 + 加固解析导入 + manifest 标注，诚实报数）
- `data/metadata/stage18_oa_discovery.csv` 阶段 18 RFC 相关开放获取发现集（独立文件，不污染 curated 候选）
- `data/evaluation/stage18_hard_queries.csv` 阶段 18 难评测集（跨段证据 / 易混淆术语 / 需拒答边界，20 题）
- `scripts/evaluate_stage18_hard_set.py` 阶段 18 难评测集多配置检索对比脚本
- `data/evaluation/stage18_hard_results.csv`、`stage18_config_comparison.csv` 阶段 18 多配置对比结果（deterministic）
- `data/evaluation/stage18_config_comparison_real.csv` 阶段 18 真实 Jina 校验对照（可选）
- `data/evaluation/stage18_corpus_stats.csv` 阶段 18 语料构成统计
- `scripts/build_stage18_quality_report.py`、`data/evaluation/stage18_quality_summary.csv`、`docs/stage18_quality_report.md` 阶段 18 quality gate 汇总与只读报告
- `app/frontend/quality_report.html` 阶段 18 增强只读质量报告（筛选 + 风险队列 + 导出）
- `GET /quality-report/data.json`、`GET /quality-report/export.csv` 阶段 18 只读质量导出端点
- Brain `rewrite_query` 最小上下文补全，支持基于可选 `history` 的“它/这个技术/这类问题”等代词或省略问法补全
- `/chat` 和 `/agent/query` 可选 `history` 字段，旧请求保持兼容
- 跨语言 query expansion 增强，补充 ITZ/界面、creep/徐变、freeze-thaw/抗冻、porosity/孔隙率、emission/碳排放、steel fiber/钢纤维、rock shear key/剪力键等术语
- Brain evidence confidence 支持扩展后的中英文证据词，降低跨语言问题误拒答
- `ChatModelProvider` 聊天模型抽象，支持 deterministic provider 和 OpenAI-compatible provider
- RAG prompt/context builder，把检索结果组织成带 `[1]`、`[2]` 编号的上下文
- `CitationAnswerService` 最小引用式问答链路
- `POST /chat` 引用式问答 API
- `qa_logs` 问答日志表和最小可观测性
- `scripts/evaluate_chat.py` 问答评测脚本
- `data/evaluation/chat_queries.csv` 和 `data/evaluation/chat_results.csv`
- `sources` 来源登记表，统一管理公开资料候选、题录、PDF manifest 和 metadata cards
- `SourceRepository` 和 `SourceRegistryService`，支持来源保存、去重、合并、可信度、权限和状态治理
- `scripts/sync_sources.py` 来源同步脚本，可从 CSV、manifest、metadata corpus 同步来源记录
- `GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`
- `scripts/evaluate_sources.py` 来源登记库评测脚本
- `data/evaluation/source_registry_metrics.csv` 来源治理指标
- FastAPI 静态前端入口：`GET /`
- 前端工作台：来源管理、资料列表、chunk 查看、关键词/向量/混合检索、引用式问答、Agent 问答、工具调用记录、引用来源侧栏、source sync 和 source reindex 入口
- 堆石混凝土种子资料、题录元数据语料库和来源目录
- 377 个自动化测试
- 本地开发依赖配置

## 新线程说明

任何新线程继续本项目时，先阅读：

1. `AGENT.MD`
2. `docs/progress.md`
3. `docs/architecture.md`
4. `docs/data_sources.md`

阶段 12 的开发记忆：

- `task_plan.md`
- `findings.md`
- `progress.md`

阶段 3 的学习笔记：

- `docs/stage3_learning_notes.md`

## 本地启动

建议使用 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

启动 API 服务：

```powershell
python -m uvicorn app.main:app --reload
```

访问健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

预期返回：

```json
{
  "status": "ok",
  "service": "RFC-RAG-Agent",
  "environment": "development"
}
```

如果 `8000` 端口已经被占用，可以换一个端口：

```powershell
python -m uvicorn app.main:app --reload --port 8001
```

## 运行测试

```powershell
python -m pytest
```

当前全量测试结果：

```text
382 passed
```

当前测试覆盖：

- FastAPI 应用能被导入
- `/health` 返回 HTTP 200
- `/health` 返回结构化 JSON
- SQLAlchemy 数据模型和 repository
- Markdown/TXT/PDF parser
- cleaner 和 splitter
- ingestion service
- documents API
- search API
- keyword search 评分与来源均衡
- embedding provider
- chunk embedding 数据库保存
- vector index service
- vector search service 和 API
- vector search evaluation script
- hybrid search service、API 和 evaluation script
- retrieval error case analysis script
- ChatModelProvider 和 OpenAI-compatible 响应解析
- RAG prompt/context builder
- CitationAnswerService
- Chat API
- QA logging
- Chat evaluation script
- source collection 资料发现与过滤
- source registry 数据模型与仓储
- 来源归一化、DOI/URL/标题三层去重、可信度和权限治理
- source sync 脚本、sources API、source reindex
- source registry 评测脚本
- 前端首页、静态资源挂载和工作台入口
- Agent 设计文档断言
- Agent 只读工具层
- Agent 编排服务
- Agent API
- Agent 评测脚本
- 前端 Agent 面板和工具调用展示入口
- 真实 RAG 失败案例分析脚本
- Brain evidence confidence 低证据拒答
- vector topic anchor rerank
- model config failed/pass_rate 汇总指标
- 阶段 11 用户问题评测集、评测脚本和审阅抽样表
- 阶段 11 跨语言 query expansion 与 Brain evidence confidence 回归

## 向量索引、混合检索与评测

阶段 2 的向量检索最小链路是：

```text
chunks
-> EmbeddingProvider
-> chunk_embeddings
-> 用户问题向量化
-> 余弦相似度检索
-> 返回来源、标题、chunk 和 score
```

构建或刷新向量索引：

```powershell
python scripts/build_vector_index.py
```

运行向量检索评测：

```powershell
python scripts/evaluate_vector_search.py
```

运行混合检索评测：

```powershell
python scripts/evaluate_hybrid_search.py
```

分析检索错误案例：

```powershell
python scripts/analyze_retrieval_errors.py
```

当前评测结果：

```text
keyword baseline: 15/15 passed
vector search: 13/15 passed
hybrid search: 15/15 passed, rescued_vector=2, regressed_keyword=0
chat evaluation: 6/6 passed
agent evaluation: 5/5 passed
brain workflow evaluation: default_hybrid 6/6, keyword_baseline 6/6, vector_only 6/6
user question evaluation: 25/30 passed, default_hybrid 10/10, keyword_baseline 10/10, vector_only 5/10
```

说明：当前 deterministic embedding 主要用于稳定开发和自动化测试。阶段 10 在 vector-only 候选内部新增 topic anchor rerank，让主题更贴合问题的片段优先进入 top_k；hybrid search 仍保留 keyword 和 vector baseline，便于持续对比。

阶段 6 评测文件：

```text
docs/evaluation_plan.md
data/evaluation/keyword_results.csv
data/evaluation/vector_results.csv
data/evaluation/hybrid_results.csv
data/evaluation/chat_results.csv
data/evaluation/retrieval_error_cases.csv
```

阶段 10 新增评测文件：

```text
data/evaluation/real_rag_failure_cases.csv
data/evaluation/stage10_jina_vector_results.csv
data/evaluation/stage10_jina_hybrid_results.csv
data/evaluation/stage10_mimo_jina_chat_results.csv
data/evaluation/stage10_mimo_jina_agent_results.csv
data/evaluation/stage10_mimo_jina_brain_workflow_results.csv
```

阶段 11 新增评测文件：

```text
docs/stage11_user_evaluation_plan.md
data/evaluation/user_questions.csv
data/evaluation/user_question_results.csv
data/evaluation/user_question_review_samples.csv
```

阶段 6 结论：

- `Recall@K`：keyword 15/15，vector 11/15，hybrid 15/15。
- `Citation Accuracy`：chat 6/6，citation_failures=0。
- `Refusal Quality`：chat 评测中 1 条无依据问题正确拒答。
- `Error Cases`：4 个 vector-only 失败均被 hybrid 标记为 `fixed_by_hybrid`。

阶段 10 结论：

- `Refusal Quality`：Brain 生成前新增 evidence confidence；unsupported query 即使被真实向量召回到片段，也会因低证据拒答。
- `Vector Recall`：deterministic vector 从 11/15 提升到 13/15，Jina vector 阶段 10 校准为 15/15。
- `Brain Workflow`：deterministic 与真实 MIMO + Jina 都达到 18/18。
- `Model Config`：`model_config_results.csv` 新增 `failed` 和 `pass_rate`，方便直接比较配置质量。

阶段 11 结论：

- `User Question Evaluation`：新增 10 条真实用户风格问题，每条按 3 种配置评测，共 30 次 config-query run。
- `Cross-language Quality`：default_hybrid 与 keyword_baseline 在用户问题集上均为 10/10，说明中英术语增强对默认链路有效。
- `Refusal Quality`：用户问题评测 `refusal_matched=30/30`，unsupported 随机问题保持拒答。
- `Residual Risk`：deterministic vector_only 在用户问题集上为 5/10，剩余失败集中在来源命中不匹配，适合作为下一阶段 rerank 或真实 embedding 校准依据。

## Decompose 与证据合并

阶段 13 把阶段 12 的预研计划落成可运行能力。默认 hybrid 链路遇到明显多主题问题时，会先做规则式 Decompose，把问题拆成最多 3 个子 query；每个子 query 使用 hybrid 检索，随后合并候选证据、按 `chunk_id` 去重、保留 sub query provenance，并用可解释 rerank 排序。

当前 Decompose 数据流：

```text
original question
-> rule-based decompose
-> sub query retrieval
-> merge candidates
-> deduplicate by chunk_id
-> explainable rerank
-> Brain evidence confidence
-> generate answer with citations
```

阶段 13 不改变旧 API schema。`POST /chat` 和 Agent `answer_with_citations` 继续复用 Brain；`POST /search`、`POST /search/vector`、`POST /search/hybrid` 仍保持原响应结构。

运行阶段 13 评测：

```powershell
python scripts/evaluate_decompose.py
```

当前结果：

```text
decompose evaluation: 6/6 passed
all-user decompose evaluation: 10/10 passed
user question evaluation: 29/30 passed
chat evaluation: 6/6 passed
agent evaluation: 5/5 passed
brain workflow evaluation: 18/18 passed
deterministic hybrid evaluation: 15/15 passed
deterministic vector baseline: 13/15 passed
full tests: 257 passed
```

阶段 13 结论：Decompose 对复杂问题的来源命中有帮助，并且 unsupported 问题仍由 Brain evidence confidence 正确拒答。vector-only 的剩余失败边界继续保留，不用静默 fallback 掩盖。

## 真实 Embedding 与回答覆盖校准

阶段 14 把阶段 13 的“证据更完整”继续推进到“质量更可审阅”。本阶段新增三类结果表：

```text
data/evaluation/stage14_embedding_comparison.csv
data/evaluation/stage14_answer_coverage_review.csv
data/evaluation/stage14_decompose_provenance_review.csv
```

运行阶段 14 embedding 对比汇总：

```powershell
python scripts/evaluate_stage14_embedding_comparison.py --include-real-config
```

当前结果：

```text
deterministic vector: 13/15
deterministic hybrid: 15/15
deterministic user questions: 25/30
deterministic decompose: 10/10
deterministic chat: 6/6
deterministic agent: 5/5
deterministic brain_workflow: 18/18
real_config: missing_results，缺少 data/evaluation/stage14_real/*.csv
full tests: 275 passed
```

运行回答覆盖校准：

```powershell
python scripts/evaluate_stage14_answer_coverage.py --include-real-config
```

当前结果：

```text
stage14_answer_coverage_review.csv: 20 rows
risk counts: low=1, medium=9, skipped=10
```

运行 Decompose provenance 可读化：

```powershell
python scripts/evaluate_stage14_decompose_provenance.py
```

当前结果：

```text
stage14_decompose_provenance_review.csv: 50 evidence rows
decomposed_rows=15
both_match_rows=37
```

阶段 14 结论：deterministic baseline 继续适合自动回归，但显式 deterministic 用户问题集为 25/30，说明真实 embedding 或更强 rerank 仍有价值。真实配置没有伪造成成功结果，而是记录为 missing/skipped，等待 `data/evaluation/stage14_real/` 中的真实评测文件。Answer Coverage 校准表把默认链路多数样例标为 review，因为 deterministic 回答只能证明链路稳定，不能证明真实语言覆盖度。

## 真实配置复跑与质量审阅报告

阶段 15 把阶段 14 的“质量表可审阅”继续推进到“真实配置状态和质量结论可报告”。本阶段不改变核心 RAG API，不把真实 API 调用变成自动测试前提，而是把真实结果、错误状态和人工复核风险都显式写入质量产物。

阶段 15 核心产物：

```text
data/evaluation/stage14_real/
data/evaluation/stage15_answer_coverage_review.csv
data/evaluation/stage15_quality_summary.csv
docs/stage15_quality_report.md
app/frontend/quality_report.html
```

运行真实配置复跑状态脚本：

```powershell
python scripts/evaluate_stage15_real_config.py --run-real
```

不传 `--run-real` 时脚本只记录 skipped，不会偷偷调用真实模型。真实 API key 仍只允许放在本地 `.env`，不得写入 CSV、文档、测试或 Obsidian。

阶段 15 当前真实配置结果：

```text
real vector: 15/15
real hybrid: 15/15
real user_questions: 27/30
real decompose: error，真实 embedding 请求 SSL EOF
real chat: 6/6
real agent: 5/5
real brain_workflow: 18/18
```

运行阶段 15 Answer Coverage 复核：

```powershell
python scripts/evaluate_stage15_answer_coverage_review.py
```

当前结果：

```text
stage15_answer_coverage_review.csv: 9 rows
risk counts: high=1, medium=8
```

运行阶段 15 质量报告：

```powershell
python scripts/build_stage15_quality_report.py
```

报告入口：

```text
GET /quality-report
```

当前质量汇总结论：

```text
stage15_quality_summary.csv: 14 rows
risk counts: high=4, low=7, medium=3
overall quality gate: review_required/high
```

阶段 15 结论：真实配置已经能支撑 vector、hybrid、chat、agent 和 Brain workflow 的发布前校准，但真实 decompose error 和 1 条 Answer Coverage high 风险不能被掩盖。deterministic baseline 继续负责稳定回归，真实配置结果只作为发布前质量审阅依据；只读报告页只展示本地质量产物，不触发真实 API 调用，也不重构核心前端工作台。

## 真实质量风险闭环

阶段 16 把阶段 15 报告中的 high/medium 风险推进到可解释闭环：真实 decompose SSL EOF 被分类为 provider/network 层风险，Answer Coverage high/medium 样例被逐条复核，并生成新的质量门禁报告。本阶段仍不改变核心 RAG API，不让真实 API 成为全量测试前提，也不新增爬虫或外部资料来源。

阶段 16 核心产物：

```text
docs/stage16_quality_risk_closure.md
data/evaluation/stage16_decompose_diagnostics.csv
data/evaluation/stage16_answer_coverage_closure.csv
data/evaluation/stage16_quality_closure_summary.csv
docs/stage16_quality_closure_report.md
app/frontend/quality_report.html
```

运行阶段 16 闭环脚本：

```powershell
python scripts/analyze_stage16_decompose_diagnostics.py
python scripts/evaluate_stage16_answer_coverage_closure.py
python scripts/build_stage16_quality_closure_report.py
```

当前质量闭环结果：

```text
real decompose: retry_completed, root_cause=embedding_header_compatibility_and_chat_timeout, blocking_status=not_blocking
stage16 answer coverage closure: 9 rows, risk_after high=1, medium=3, low=5
stage16 quality gate: review_required/high
stage16 real decompose retry: 10/10 passed with compatible embedding header and longer chat timeout
focused regression: 80 passed
full tests: 322 passed
```

阶段 16 结论：本阶段没有把 deterministic baseline 当成真实成功，也没有伪造 real decompose 通过。追加重试后，真实 decompose 已在兼容 embedding 请求头和更长 chat timeout 下跑通 10/10；当前剩余发布前 high 阻断来自 Answer Coverage，`user_mixed_itz_strength` 仍需人工核验或重跑真实回答。阶段 16 当前停在用户人工核验前状态，尚未提交、尚未打 `phase-16-complete` tag、尚未推送 GitHub。

## Agent 化

阶段 7 的最小 Agent 链路是：

```text
用户任务
-> AgentService 意图路由
-> 只读 Agent 工具
-> search / hybrid search / citation chat / sources
-> 结构化返回 answer、tool_calls、sources、citations、refused、reasoning_summary
-> 前端展示工具调用和引用
```

当前 Agent 工具：

- `search_knowledge`：关键词检索工具，保留阶段 1 baseline。
- `hybrid_search_knowledge`：混合检索工具，默认用于搜索类任务。
- `answer_with_citations`：引用式问答工具，复用 `CitationAnswerService`。
- `list_sources`：来源列表工具。
- `get_source_detail`：来源详情工具。

调用 `/agent/query` 示例：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/agent/query `
  -ContentType "application/json" `
  -Body '{"question":"检索 filling capacity 相关资料","top_k":5,"max_tool_calls":2}'
```

响应字段要点：

- `answer`：Agent 汇总后的回答或检索说明。
- `tool_calls`：工具调用记录，包含工具名、输入摘要、输出摘要、成功状态和错误信息。
- `sources` / `citations`：来源和引用信息。
- `search_results`：搜索类任务返回的片段结果。
- `refused` / `refusal_reason`：资料或参数不足时的拒答状态与原因。
- `reasoning_summary`：面向审计的工具选择摘要，不暴露内部敏感推理。

运行 Agent 评测：

```powershell
python scripts/evaluate_agent.py
```

当前结果：

```text
agent evaluation: 5/5 passed
refused=1
tool_failures=0
citation_failures=0
```

阶段 7 只做只读工具优先，不自动执行 source reindex 等写入型动作；后续如接入写入工具，必须有显式请求字段、权限约束和测试。

## Brain 中控层与 Workflow 配置化

阶段 8 将中控层正式命名为 Brain。Brain 不是新的数据库层，也不是爬虫层，而是位于 `/chat`、Agent 和现有检索/生成服务之间的轻量编排层。

默认 RAG workflow 是：

```text
filter_history
-> rewrite_query
-> retrieve
-> optional_rerank
-> generate_answer
```

当前实现要点：

- `RetrievalConfig` 统一控制 `retrieval_mode`、`top_k`、`min_score`、`max_history`、`rerank_top_n`、`prompt_profile` 和 `model_provider`。
- `WorkflowConfig` 描述 workflow step 顺序，默认保持五步 RAG 链路。
- `BrainService` 复用现有 keyword、vector、hybrid、prompt、chat model、citation 和 qa_logs 能力，不直接写 SQL。
- `CitationAnswerService` 保留原有对外入口，内部改为调用 Brain，因此 `POST /chat` 和 Agent `answer_with_citations` 共享同一条回答路径。
- 本阶段不引入复杂 LangGraph workflow，不联网爬取新资料，不自动执行 source reindex，也不做前端大重构。

运行 Brain 配置化评测：

```powershell
python scripts/evaluate_brain_workflow.py
```

当前配置化评测结果：

```text
default_hybrid: 6/6 passed
keyword_baseline: 6/6 passed
vector_only: 6/6 passed
```

说明：阶段 10 之后 Brain workflow 在 deterministic 配置下已经稳定到 18/18；阶段 11 在此基础上新增真实用户问题评测，用更接近实际提问的方式继续暴露质量边界。

## 真实模型接入与模型评测

阶段 9 补齐真实模型接入边界。默认仍使用 deterministic provider，保证本地开发和自动化测试不依赖真实 API key；需要真实模型效果时，再通过本地 `.env` 或命令行显式配置 OpenAI-compatible chat/embedding provider。

新增真实 embedding 配置字段：

```powershell
EMBEDDING_PROVIDER=openai-compatible
EMBEDDING_MODEL_NAME=your-embedding-model
EMBEDDING_API_KEY=your-local-secret
EMBEDDING_BASE_URL=https://your-provider.example/v1
EMBEDDING_DIMENSION=1024
EMBEDDING_TIMEOUT_SECONDS=30
```

使用真实 embedding 前必须按相同 provider/model/dimension 重建向量索引：

```powershell
python scripts/build_vector_index.py `
  --provider openai-compatible `
  --model-name your-embedding-model `
  --base-url https://your-provider.example/v1 `
  --api-key your-local-secret `
  --dimension 1024
```

运行模型配置汇总评测：

```powershell
python scripts/evaluate_model_configs.py --include-real-config
```

当前阶段 9 结果：

```text
deterministic_baseline:
  keyword 15/15
  vector 11/15
  hybrid 15/15
  chat 6/6
  agent 5/5
  brain_workflow 12/18

real_config:
  skipped，本地未配置真实 chat/embedding API key、base URL、model 和 embedding dimension

phase_9_1_real_mimo_jina:
  Jina vector 14/15
  Jina hybrid 15/15
  MIMO + Jina chat 6/6
  MIMO + Jina agent 5/5
  MIMO + Jina brain_workflow 15/18
  full tests 208 passed

phase_10_rag_quality_calibration:
  deterministic vector 13/15
  deterministic hybrid 15/15
  deterministic chat 6/6
  deterministic agent 5/5
  deterministic brain_workflow 18/18
  Jina vector 15/15
  Jina hybrid 15/15
  MIMO + Jina chat 6/6
  MIMO + Jina agent 5/5
  MIMO + Jina brain_workflow 18/18
  full tests 216 passed
```

设计结论：真实模型接入已经具备工程边界和评测入口，但默认配置仍不切到真实模型。阶段 10 的推荐做法是：deterministic provider 用于稳定回归，真实 MIMO + Jina 用于发布前质量校准；真实模型更贴近用户体验，但不适合作为自动测试唯一依据。

## 真实 RAG 质量校准与拒答边界

阶段 10 处理阶段 9.1 暴露的 3 类问题：vector-only 误召回、unsupported 问题未拒答、真实模型与 deterministic baseline 的指标不可直接读懂。

新增质量保护：

- `scripts/analyze_real_rag_failures.py`：把真实 RAG 失败拆成可诊断案例。
- `EvidenceConfidence`：在 Brain 生成答案前检查问题有效词是否被召回证据覆盖。
- 低证据拒答：有检索结果但证据不足时，直接返回“当前资料库中没有找到足够可靠的依据”，不调用真实模型硬生成。
- `topic anchor rerank`：vector-only 候选内部用主题锚点轻量重排，降低语义相近但主题不对的误召回。
- `failed` / `pass_rate`：模型配置汇总结果直接显示失败数和通过率。

阶段 10 结果：

```text
deterministic:
  vector 13/15
  hybrid 15/15
  chat 6/6
  agent 5/5
  brain_workflow 18/18

real MIMO + Jina:
  Jina vector 15/15
  Jina hybrid 15/15
  chat 6/6
  agent 5/5
  brain_workflow 18/18
```

面试表达：阶段 10 不是继续堆模型，而是把真实模型暴露出的失败转成可复现的工程保护。系统先判断检索证据是否足够，再决定是否生成；同时保留 deterministic 和真实模型两套评测口径，既能稳定回归，也能验证真实体验。

## 真实用户问题评测集与跨语言质量提升

阶段 11 处理阶段 10 后的下一类质量问题：旧评测集能证明主链路稳定，但还不足以覆盖真实用户会怎么问，尤其是中文口语、英文问题、中英混合术语和工程场景问法。

新增链路：

```text
data/evaluation/user_questions.csv
-> scripts/evaluate_user_questions.py
-> data/evaluation/user_question_results.csv
-> 跨语言 query expansion / Brain evidence confidence
-> docs/stage11_user_evaluation_plan.md
-> data/evaluation/user_question_review_samples.csv
```

阶段 11 的 query expansion 继续复用 `SYNONYM_RULES`，因此同一套术语增强会同时服务关键词检索和向量检索的 topic anchor。Brain evidence confidence 也会使用扩展后的中英文证据词，避免中文问题被英文证据片段误判为低证据。

当前结果：

```text
keyword evaluation: 15/15
vector evaluation: 13/15
hybrid evaluation: 15/15
chat evaluation: 6/6
agent evaluation: 5/5
brain workflow evaluation: 18/18
user question evaluation: 25/30
full tests: 230 passed
```

面试表达：阶段 11 我把 RAG 质量评测从“标准测试题”扩展到“真实用户怎么问”。新增问题集显式记录语言类型、期望来源、期望拒答和回答要点；自动脚本稳定检查拒答、来源命中和引用有效性；人工审阅表再检查 Faithfulness、Answer Coverage 和 Citation Quality。跨语言增强不是黑盒调参，而是把中文工程词和英文论文术语做可解释映射，并复用到 keyword、vector topic anchor 和 Brain 证据置信度中。

## 质量审阅与上下文最小补全

阶段 12 把阶段 11 的人工审阅设计真正落地，并在 Brain workflow 的 `rewrite_query` 位置实现最小上下文补全。

新增链路：

```text
data/evaluation/user_question_review_samples.csv
-> data/evaluation/stage12_quality_review_results.csv
-> docs/stage12_quality_review.md
-> Brain filter_history / rewrite_query
-> 可选 history 补全代词或省略问法
-> chat / agent / user question / Brain workflow 回归
-> docs/stage13_decompose_plan.md
```

阶段 12 的上下文补全只处理明确依赖最近历史的问题，例如“它有哪些研究？”、“这个技术对长期变形有什么影响？”。系统会把最近历史问题拼入检索 query，但返回结果中的 `question` 仍保留用户原始问题。`/chat` 和 `/agent/query` 新增可选 `history` 字段，旧请求不传该字段仍保持兼容。

当前结果：

```text
quality review tests: 8 passed
context rewrite focused tests: 52 passed
user question evaluation: 25/30
chat evaluation: 6/6
agent evaluation: 5/5
brain workflow evaluation: 18/18
API/core regression: 47 passed
full tests: 244 passed
```

阶段 12 结论：默认 hybrid 链路来源命中可靠，deterministic provider 适合稳定回归但不能单独证明真实回答覆盖度；vector-only 仍有主题漂移。下一阶段优先做规则式 Decompose、子 query 检索、证据合并、按 `chunk_id` 去重和可解释 rerank；HyDE 只做离线实验建议。

面试表达：阶段 12 我把自动评测和人工审阅分开。自动评测继续保证拒答、来源命中和引用链路稳定，人工审阅结果表则检查 Faithfulness、Answer Coverage 和 Citation Quality。同时我没有做复杂长期记忆，而是在 Brain 的 `rewrite_query` step 做最小上下文补全，让“它”“这个技术”等追问能带上最近历史问题进入检索，并通过回归测试证明默认链路不退化。

## 引用式问答

阶段 3 的最小问答链路是：

```text
用户问题
-> 检索 chunks
-> 组织 RAG 上下文和来源编号
-> 调用 ChatModelProvider
-> 返回 answer、citations、sources、refused 和 model 信息
-> 写入 qa_logs
```

调用 `/chat` 示例：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body '{"question":"What affects filling capacity in rock-filled concrete?","top_k":5,"retrieval_mode":"auto"}'
```

响应字段要点：

- `answer`：回答正文。
- `citations`：答案中使用的来源编号，例如 `[1]`。
- `sources`：每个来源编号对应的文档、chunk、片段内容和 score。
- `refused`：资料不足时为 `true`。
- `refusal_reason`：拒答原因。
- `retrieval_mode`：实际使用的检索模式，可能是 `vector`、`keyword`、`hybrid` 或 `none`。
- `model_provider` / `model_name`：本次回答使用的聊天模型信息。

资料不足时，系统会返回：

```text
当前资料库中没有找到足够可靠的依据。
```

运行问答评测：

```powershell
python scripts/evaluate_chat.py
```

当前结果：

```text
chat evaluation: 6/6 passed
```

阶段 3 仍然不做 Agent 工具调用，也不引入复杂 LangGraph workflow。当前目标是先把“基于资料回答、可引用、可拒答、可评测”的最小链路稳定跑通。

## 来源管理

阶段 4 的最小来源治理链路是：

```text
公开资料候选 / 题录 / PDF manifest
-> source registry
-> DOI / URL / 标题归一化去重
-> 可信度与全文保存权限标记
-> 来源状态管理
-> 原文或题录入库
-> 支持重新索引
```

同步现有来源到 `sources` 表：

```powershell
python scripts/sync_sources.py
```

查看来源治理指标：

```powershell
python scripts/evaluate_sources.py
```

当前来源评测结果：

```text
total_sources: 125
linked_documents: 0
merged_duplicates: 14
status: candidate=8, collected=117
fulltext_permission: institutional_access=2, metadata_only=110, open_access=10, unknown=3
trust_level: high=125
```

来源管理 API：

```text
GET /sources
GET /sources/{source_id}
POST /sources/sync
POST /sources/{source_id}/reindex
```

字段要点：

- `trust_level`：来源可信度，例如高校、期刊、DOI、开放论文等高可信来源。
- `fulltext_permission`：全文保存权限，例如 `open_access`、`institutional_access`、`metadata_only`、`unknown`。
- `status`：来源生命周期状态，例如 `candidate`、`collected`、`imported`、`duplicate`、`rejected`。
- `document_id`：来源重新导入后关联到 `documents` 表的文档编号。

阶段 4 不做 Agent 工具调用、不做复杂 LangGraph workflow、不做前端界面。当前重点是让资料来源可靠、可去重、可追溯、可重新导入，为阶段 5 前端和后续 Agent 工具调用打基础。

## 前端工作台

阶段 5 新增浏览器界面：

```text
GET /
```

前端入口由 FastAPI 直接提供，静态文件位于：

```text
app/frontend/
```

当前工作台支持：

- 查看来源总数、已收集来源、已入库来源、资料数和 chunk 总数。
- 查看 sources 列表，并按关键词、状态、全文权限筛选。
- 查看 documents 列表和每篇资料的 chunk 数量。
- 查看指定 document 的 chunks。
- 使用关键词检索、向量检索或混合检索查看召回片段。
- 调用 `/chat` 提问，展示回答、引用编号、模型信息和引用来源侧栏。
- 调用 `/agent/query` 提交 Agent 任务，展示回答、引用编号、工具调用记录和来源。
- 触发 source sync。
- 触发单条 source reindex，并在失败时展示可理解错误。

启动服务后访问：

```powershell
python -m uvicorn app.main:app --reload
```

```text
http://127.0.0.1:8000
```

## Obsidian 知识库

本项目维护了一个可直接用 Obsidian 打开的知识库：

```text
obsidian-vault/
```

打开方式：

1. 打开 Obsidian。
2. 选择“打开本地文件夹作为库”。
3. 选择本仓库下的 `obsidian-vault`。
4. 从 `首页.md` 开始阅读。

知识库用途：

- 按阶段沉淀开发知识。
- 用 `阶段汇报/` 分支记录每个大阶段的小 Phase 复盘。
- 按分类整理面试高频点。
- 用 `[[双链]]` 连接阶段、分类和知识点。
- 记录每个知识点对应的代码位置、作用和面试表达。

## 当前目录

```text
rfc-rag-agent/
  app/
    main.py
    api/
      chat.py
      documents.py
      agent.py
      frontend.py
      health.py
      search.py
      sources.py
    core/
      config.py
    db/
      models.py
      repositories.py
      session.py
    schemas/
      chat.py
      document.py
      agent.py
      health.py
      search.py
      source.py
    services/
      agent/
      generation/
      ingestion/
      retrieval/
      source_registry.py
      source_collection.py
    frontend/
      index.html
      static/
        app.js
        styles.css
  data/
    evaluation/
    imports/
    metadata/
  docs/
  scripts/
  tests/
  obsidian-vault/
    首页.md
    阶段索引.md
    分类索引.md
    阶段汇报索引.md
    阶段/
    阶段汇报/
    分类/
    知识点/
    模板/
  AGENT.MD
  README.md
  .env.example
  .gitignore
  pyproject.toml
```

## 项目边界

第一阶段聚焦堆石混凝土，不做全水利知识库。

核心范围：

- 堆石混凝土基本概念
- 材料组成与自密实混凝土
- 施工工艺与质量控制
- 力学性能与耐久性
- 工程案例
- 公开文献和网页资料的引用式问答

## 安全说明

真实 API Key 只允许写入本地 `.env`，不得提交到 GitHub。

## 阶段 0 面试表达

本阶段先搭建 FastAPI 后端工程底座，而不是直接做爬虫或大模型调用。原因是 RAG 系统后续会包含资料导入、检索、问答、评测等多个模块，如果一开始没有清晰的应用入口、路由分层、配置读取和测试方式，后续功能会很容易堆在一起，难以维护。

`/health` 是服务健康检查接口，用来证明 API 服务可以被正常启动和访问。真实部署时，健康检查还可以扩展为数据库连接、向量库状态、模型服务状态等检查。

## 阶段 1 面试表达

阶段 1 我先完成了 RAG 系统的数据入口和关键词检索 baseline，而不是直接接大模型。

我把资料导入拆成 parser、cleaner、splitter、repository 和 ingestion service：parser 负责把 Markdown/TXT/PDF 读成文本，cleaner 负责去掉多余空白，splitter 负责切成可检索的 chunk，repository 负责数据库读写，ingestion service 负责串起完整导入流程。这样做的好处是每一步都能单独测试，后续接 embedding 或更换数据库时不需要重写整条链路。

关键词检索用于在没有向量库之前建立第一版可解释检索能力。我建立了 `data/evaluation/keyword_queries.csv` 作为评测集，并用脚本自动检查命中结果。最终 15 个代表性查询全部通过，形成了阶段 2 向量检索的对照基线。

## 阶段 2 面试表达

阶段 2 我完成了从 chunk 到 embedding，再到向量检索 API 的最小可运行链路。

我先抽象 `EmbeddingProvider`，让业务检索逻辑不依赖某一家模型服务；再新增 `chunk_embeddings` 表保存每个 chunk 的向量、模型信息、维度和内容指纹。索引构建由 `VectorIndexService` 负责，可以重复运行，未变化的 chunk 会被跳过，内容变化后会更新 embedding。

检索时，`POST /search/vector` 会把用户问题转成 query embedding，再和数据库中的 chunk embedding 计算余弦相似度，返回来源、标题、片段和 score。为了验证效果，我复用了阶段 1 的关键词评测集，当前 deterministic embedding 下向量检索为 11/15，关键词 baseline 为 15/15。这个结果说明链路已经跑通，但真实语义效果还需要后续接入更好的 embedding 模型或混合检索来提升。

## 阶段 3 面试表达

阶段 3 我完成了引用式问答的最小稳定链路，而不是直接做一个普通聊天接口。

我先抽象 `ChatModelProvider`，让业务逻辑不绑定某一家模型服务；再用 prompt builder 把检索结果组织成带 `[1]`、`[2]` 编号的上下文，并保存编号到 chunk 的映射。`CitationAnswerService` 负责串联检索、prompt 构造、模型调用、引用提取和拒答判断。最后通过 `POST /chat` 返回 answer、citations、sources、refused、retrieval_mode 和 model 信息。

为了保证可排查性，我新增了 `qa_logs` 记录每次问答的问题、答案、召回 chunk、引用、模型和拒答状态；为了保证不是只靠演示，我新增了 chat 评测集和 `scripts/evaluate_chat.py`。当前 chat 评测 6/6 通过，全量测试 106 个通过。阶段 3 暂不做 Agent 工具调用和复杂 workflow，先保证 RAG 问答链路忠实、可引用、可拒答、可评测。

## 阶段 4 面试表达

阶段 4 我完成了资料来源治理，而不是继续堆更多问答功能。

我新增 `sources` 表作为 source registry，把公开资料候选、PDF manifest、题录 CSV 和 metadata cards 统一登记起来。`SourceRegistryService` 负责把采集候选转换成数据库记录，并按 DOI、URL、标题归一化做三层去重；同时维护 `trust_level`、`fulltext_permission` 和 `status`，区分来源是否可信、能否保存全文、处于候选还是已收集状态。

为了让来源能重新进入 RAG 链路，我新增了 source reindex 入口：已有本地文件的来源可以重新导入原文，metadata-only 来源可以重新生成题录卡片后导入 `documents/chunks`。同时提供 `scripts/sync_sources.py`、`/sources` API 和 `scripts/evaluate_sources.py`，保证来源治理既能批量同步，也能被后续前端或 Agent 工具调用复用。阶段 4 全量测试 123 个通过，关键词、向量和 chat 评测保持阶段 3 基线。

## 阶段 5 面试表达

阶段 5 我补齐了 RAG 系统的前端工作台，而不是只做一个聊天框。

我采用 FastAPI 静态文件提供第一版前端，避免在当前 Python 项目里过早引入复杂前端构建链。页面直接接入已有 sources、documents、search、vector search 和 chat API，展示来源治理状态、资料列表、chunk 片段、检索结果、问答回答和引用来源侧栏。

这样设计的重点是让非技术用户能看见 RAG 链路：source 是资料来源治理，documents/chunks 是已入库内容，chat 的 citations 可以追溯到具体 chunk。阶段 5 还提供 source sync 和 reindex 操作入口，并通过浏览器验证桌面和移动视口，最终全量测试 126 个通过。

## 阶段 6 面试表达

阶段 6 我没有继续盲目加功能，而是先把 RAG 的检索和问答质量变成可量化、可复现、可解释的评测闭环。

我新增了 `docs/evaluation_plan.md`，把 Recall@K、Citation Accuracy、Faithfulness、Answer Coverage 和 Refusal Quality 映射到当前 keyword、vector、chat 评测脚本和 CSV 结果。然后复跑 baseline：关键词检索 15/15，向量检索 11/15，chat 6/6，并用 `retrieval_error_cases.csv` 记录 4 个向量检索失败案例。

优化上我选择混合检索，而不是直接接更复杂的外部模型或 Agent。`HybridSearchService` 同时调用关键词和向量检索，按 chunk 去重，对两路分数归一化，再用权重和双路命中奖励重排。最终 hybrid search 达到 15/15，救回 4 个 vector-only 失败，且没有相对关键词 baseline 的退化。这样阶段 6 能清楚说明：优化不是凭感觉，而是有 baseline、有错误案例、有指标对比和回归测试。

## 阶段 7 面试表达

阶段 7 我把已经稳定的 RAG 能力包装成受控 Agent 工具调用链路，而不是直接引入复杂 LangGraph workflow。

我先写 `docs/agent_design.md` 固定工具边界和权限约束，然后新增 `AgentToolbox`，把关键词检索、混合检索、引用式问答和来源查询封装成只读工具。`AgentService` 使用保守规则做意图路由：搜索类任务调用 `hybrid_search_knowledge`，问答类任务调用 `answer_with_citations`，来源类任务调用 sources 工具。API 通过 `POST /agent/query` 返回 answer、tool_calls、sources、citations、refused 和 reasoning_summary，前端也能展示工具调用记录。

这个阶段的重点不是让 Agent “自由发挥”，而是让它不能绕过 sources、documents/chunks、hybrid search、引用和拒答链路。验证上我新增 Agent 评测集和脚本，结果 5/5 通过，同时复跑 keyword 15/15、vector 11/15、hybrid 15/15、chat 6/6 和全量 163 个测试。面试里可以强调：这是一个可审计、可回归、只读优先的 RAG Agent，而不是不可控的多工具 demo。
