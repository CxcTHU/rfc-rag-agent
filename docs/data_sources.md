# 数据来源登记

本文件用于记录后续采集的堆石混凝土相关资料来源。

## 登记模板

```text
source_id:
标题:
URL:
来源类型:
作者或机构:
发布时间:
访问时间:
是否允许全文保存:
可信度评级:
备注:
```

## 当前状态

阶段 29 完成真实 Embedding 重建与质量闭环后，外部资料来源数量不变，新增的是由现有 chunks 派生出的索引和评测产物：

```text
documents 635
chunks 12716
sources 673
chunk_embeddings 25432
jina_embeddings 12716
deterministic_embeddings 12716
orphan_embeddings 0
duplicate_provider_model_groups 0
```

阶段 29 新增评测与报告文件：

- `data/evaluation/stage29_new_corpus_queries.csv`：18 条评测问题，覆盖 Wikipedia、公开标准、网页语料和拒答边界。
- `data/evaluation/stage29_real_quality_results.csv`：真实 Jina embedding 检索 + deterministic 问答的逐题评测结果。
- `data/evaluation/stage29_real_quality_summary.csv`：precision@k、coverage_ratio、refusal_accuracy 和 source_type_distribution 汇总。
- `data/evaluation/stage29_quality_summary.csv`：`/quality-report` 使用的阶段 29 质量门禁摘要。
- `docs/stage29_quality_report.md`：人工核验用质量报告。

数据安全边界：

- `chunk_embeddings` 是从 `chunks` 派生出的可重建索引数据，不是新的外部资料来源。
- 阶段 29 的真实 Jina API 调用只用于本地 embedding 重建和质量评测；API key、Bearer token、Authorization header 和供应商原始敏感响应不得写入 Git、CSV、文档、测试或 Obsidian。
- 评测 CSV 只保存问题、指标、source type、文档/来源标识、延迟和脱敏摘要，不保存受限全文或供应商原始响应。
- 全量测试继续使用 deterministic provider，不让真实 API 成为 CI 前提。

阶段 28 续完成后，数据来源进入“清理后待人工核验”状态：

```text
documents 635
web_page_documents 136
wikipedia_documents 25
standard_documents 9
chunks 12716
sources 673
wikipedia_sources 19
standard_sources 9
chunk_embeddings 21634
```

新增来源类型：

- `web_page`：阶段 28 本地网页爬取保留语料。Phase 8 已删除 458 个低质量网页文档，清理后剩余 136 个网页文档，其中 91 个仍建议人工复核。
- `wikipedia`：Phase 9 通过 Wikipedia REST API 获取的中英文百科页面，作为概念背景知识，不作为工程规范强证据。
- `standard_document`：Phase 10 下载的公开免费 PDF 标准/指南类资料，保存于 `data/raw/standards/`，下载前检查文件大小，超过 20MB 或无法公开获取的文档跳过。

阶段 28 续相关数据文件：

- `data/crawl/wikipedia_articles.csv`：38 条 Wikipedia 候选。
- `data/crawl/standards_urls.csv`：15 条公开 PDF 候选。
- `data/evaluation/stage28_crawl_quality_*.csv`：清理后质量审查输出。
- `docs/stage28_crawl_quality_report.md`：清理后质量报告。

当前仍等待用户人工核验；人工核验前不提交、不打 tag、不推送。

已完成阶段 4 source registry 来源治理。

阶段 4 已新增数据库表 `sources`，作为本项目的 source registry。它统一承接：

- `docs/data_sources.md` 中的人读来源登记。
- `data/fulltext_manifest.csv` 中的 PDF manifest。
- `data/source_candidates.csv` 中的公开学术 API 候选。
- `data/metadata/rfc_papers_metadata.csv` 中的题录元数据。
- `data/imports/metadata_corpus/*.md` 中的题录卡片。

当前同步结果：

- 输入来源候选：283 条。
- 写入 `sources` 表：125 条。
- 更新已有来源：132 次。
- 合并重复来源：26 次。
- 状态分布：`candidate=8`、`collected=117`。
- 全文保存权限分布：`institutional_access=2`、`metadata_only=110`、`open_access=10`、`unknown=3`。
- 可信度分布：`high=125`。

阶段 21 新增评测数据产物（不含受限全文或 API 凭据）：

- `data/evaluation/stage21_agentic_comparison_results.csv`：agentic vs baseline 逐查询对照结果。
- `data/evaluation/stage21_agentic_comparison_summary.csv`：配置级汇总指标。
- `data/evaluation/stage21_agentic_decision.csv`：接入门槛决策。

阶段 22 不新增外部资料来源，也不新增爬虫、真实 API 依赖或受限全文文件。阶段 22 的改动集中在前端展示和 `/agent/query` 只读响应契约：

- 新增 `docs/stage22_frontend_agentic_observability.md` 设计文档。
- `/agent/query` 响应新增 `workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category` 等观测字段；这些字段来自本次请求的 agentic 运行状态，不写入新的数据源表。
- 前端展示 default / agentic 模式、迭代步骤、无效引用和拒答分类；不改变 `sources`、`documents`、`chunks`、`chunk_embeddings` 或 source registry 的数据边界。
- 新增/更新测试均使用 deterministic provider 与临时 SQLite，不要求真实 API，不写入 API key、Bearer token、供应商原始敏感响应或受限全文。

阶段 23 不新增外部资料来源，也不新增爬虫、真实 API 依赖或受限全文文件。阶段 23 的新增数据产物只用于 agentic vs default 对照评测和自动路由验收：

- `docs/stage23_agentic_eval_and_auto_routing.md`：阶段 23 设计文档，说明评测修复、路由规则、API 自动分流、前端只读指示器和安全边界。
- `scripts/evaluate_stage23_agentic_auto_routing.py`：deterministic 评测脚本，使用 in-memory SQLite 合成 fixture，不读取或调用真实 provider。
- `data/evaluation/stage23_agentic_auto_routing_results.csv`：逐问题对照结果，只保存问题 ID、类别、复杂度期望、错误标记、是否 answer-like、来源数量、迭代次数和 agentic gain 标记。
- `data/evaluation/stage23_agentic_auto_routing_summary.csv`：default/agentic 汇总指标，只保存总数、错误数、error_rate、answer_like_count、拒答匹配数和 agentic_gain_count。
- `data/evaluation/stage23_agentic_auto_routing_decision.csv`：阶段 23 决策摘要，记录 default/agentic error_rate、agentic_gain_count、decision 和 reason。

这些 CSV 不包含 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文；合成 fixture 只使用可提交的短文本片段，用于隔离阶段 21 SSL/真实 provider 错误。阶段 23 前端只读 `data-agent-mode-status` 和 API 响应 `mode` 也不改变 `sources`、`documents`、`chunks`、`chunk_embeddings` 或 source registry 的数据边界。

阶段 24 不新增外部资料来源，也不新增爬虫、真实 API 依赖或受限全文文件。阶段 24 新增的是**本地会话运行数据**，用于让 Agent 面板支持多轮对话和刷新恢复：

- `docs/stage24_multi_turn_conversation.md`：阶段 24 设计文档，说明会话模型、API、摘要策略、前端 UI 和安全边界。
- `conversations` 表：保存会话标题、创建时间和更新时间。
- `messages` 表：保存 `user` / `assistant` / `summary` 消息正文、所属会话、回答 `mode` 和结构化 `metadata_json`。
- `app/services/conversation/history.py`：把消息装配为 LLM history，并在长对话超过阈值时生成 summary 消息。
- `/conversations` API：只管理本地会话和消息，不读取外部资料源，不触发爬虫。

阶段 24 的 `Message.metadata_json` 只保存前端恢复展示所需的结构化元数据，例如 `citations`、`workflow_steps`、`invalid_citations`、`refusal_category`、`mode` 和 `iteration_count`。它不得保存 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文。

阶段 24 的 summary 消息只用于当前 conversation 的短期上下文压缩，不是跨会话长期记忆，也不改变 `sources`、`documents`、`chunks`、`chunk_embeddings` 或 source registry 的资料来源边界。真实模型如果在实际长会话中被用于摘要，只能作为运行时模型服务，不是资料来源；自动测试继续使用 deterministic provider，不让真实 API 成为 CI 或本地全量测试前提。

阶段 25 不新增外部资料来源，也不新增爬虫、真实 API 依赖、CSV 评测数据或受限全文文件。阶段 25 新增的是**运行链路与展示协议**，用于让 Agent 面板支持闲聊短路和 SSE 流式输出：

- `docs/stage25_chitchat_and_sse_streaming.md`：阶段 25 设计文档，说明路由层闲聊短路、provider 流式协议、SSE 事件格式、前端消费方式和安全边界。
- `app/services/agent/chitchat.py`：本地规则和预设回复，只识别 greeting、thanks、goodbye、acknowledgment、help 五类社交意图，不读取外部资料源。
- `POST /agent/query/stream`：运行时流式响应端点，输出 `token`、`metadata`、`done`、`error` 事件，不改变 `sources`、`documents`、`chunks`、`chunk_embeddings` 或 source registry。
- 前端 `fetch()` + `ReadableStream` 消费 SSE：只改变回答展示时机，不创建新的资料来源。

阶段 25 的 SSE `token` 事件只包含面向用户展示的回答文本片段；`metadata` 事件复用 `AgentQueryResponse` 的结构化字段，例如 `citations`、`sources`、`workflow_steps`、`invalid_citations`、`refusal_category`、`mode` 和 `iteration_count`。它不得保存或暴露 API key、Bearer token、Authorization header、供应商原始敏感响应、raw_response 或受限全文。

阶段 25 的闲聊回复是预设文本，不是资料来源，也不参与检索证据；带 `conversation_id` 的闲聊可以保存为本地会话消息，但会跳过 summary 压缩，避免社交短句污染后续 RAG 上下文。真实模型流式输出只作为运行时服务能力，自动测试继续使用 deterministic provider，不让真实 API 成为 CI 或本地全量测试前提。

阶段 26 不新增外部资料来源，也不新增爬虫、真实 API 依赖或受限全文文件。阶段 26 新增的是**检索性能优化和重排序运行能力**：

- `docs/stage26_retrieval_performance_reranking.md`：阶段 26 设计文档，说明 profiling、numpy 向量化、缓存、并行召回、rerank provider 和安全边界。
- `scripts/benchmark_retrieval.py`：检索基准脚本，只读取现有本地数据库与索引，默认 deterministic provider，不触发真实 API。
- `app/services/retrieval/vector_cache.py`：进程内 `VectorIndexCache`，缓存来自 `chunk_embeddings` 的可重建向量矩阵。
- `app/services/retrieval/reranking.py`：`ReRankingProvider` 协议和 deterministic / OpenAI-compatible provider。

阶段 26 只读取现有：

```text
documents
chunks
chunk_embeddings
```

数据安全边界：

- `VectorIndexCache` 只在进程内缓存 embedding 矩阵，不写入 Git 或外部存储。
- `chunk_embeddings` 是由已有 chunks 派生出的可重建索引数据，不是新的文献资料来源。
- deterministic rerank 是本地规则式评分，不调用真实 API。
- OpenAI-compatible rerank provider 只是运行时可选能力；API key、Bearer token、Authorization header 和供应商原始敏感响应不得写入源码、文档、CSV、测试、Git 或 Obsidian。
- `scripts/benchmark_retrieval.py` 的输出只包含耗时、provider/model 名称和脱敏 query，不保存受限全文或供应商原始响应。
- 阶段 26 已停在用户人工核验前状态，尚未提交、尚未创建 `phase-26-complete` tag、尚未推送。

阶段 27 不新增外部资料来源，也不新增爬虫、真实 API 依赖、CSV 评测数据或受限全文文件。阶段 27 新增的是**运行入口、部署配置和 CI 配置**：

- `docs/stage27_chainlit_docker_ci.md`：阶段 27 设计文档，说明 Chainlit 双入口、service 层复用、Docker/CI、安全边界和完成标准。
- `chainlit_app.py`：Chainlit 对话界面入口，复用现有 `detect_chitchat`、Agent service、agentic workflow、ConversationRepository 和流式事件。
- `.chainlit/config.toml` 与 `chainlit.md`：Chainlit 运行配置和欢迎页，不包含外部资料、密钥或供应商响应。
- `Dockerfile`、`docker-compose.yml`、`.dockerignore`：容器运行配置和构建上下文排除规则。
- `.github/workflows/ci.yml`：deterministic provider 的 pytest CI 配置。

阶段 27 只读取既有运行数据边界：

```text
sources
documents
chunks
chunk_embeddings
conversations
messages
```

数据安全边界：

- Chainlit 是展示与交互入口，不是新的资料来源。它显示的回答、citations 和 workflow 来自当前请求运行结果。
- Chainlit 会话保存复用 `ConversationRepository`，只写入本地 `conversations` 与 `messages` 表；不得保存 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文。
- Docker 镜像不得包含 `.env`、API key、SQLite 数据库、`data/raw`、`data/fulltext` 或 Obsidian 知识库；运行时数据通过 `./data:/app/data` volume 挂载。
- GitHub Actions CI 使用 deterministic provider，不读取真实 `.env`，不要求真实模型 API，也不保存真实供应商响应。
- 当前阶段停在用户人工核验前状态，尚未提交、尚未创建 `phase-27-complete` tag、尚未推送。

阶段 28 新增外部网页资料来源，但限定为**公开 HTML 页面**的本地合规采集和自动入库：

- `docs/stage28_web_crawl_auto_ingest.md`：阶段 28 设计文档，说明 crawling 模块、CLI、本地运行方式、安全边界和完成标准。
- `app/services/crawling/`：网页采集服务层，包含 seed URL 管理、robots.txt 检查、限速 HTTP 抓取、trafilatura 正文提取和入库编排。
- `scripts/crawl_and_ingest.py`：本地批量爬取与自动入库 CLI。
- `data/crawl/seed_urls.csv`：100 条人工维护种子 URL，覆盖百科词条、高校机构、工程案例、开放论文、行业标准 5 类。
- `data/crawl/crawl_results*.csv`：本地批处理状态记录，只保存 URL、分类、状态、标题、document/source 标识和错误摘要，不保存网页正文。
- `data/raw/web_crawl/*.md`：公开网页经 trafilatura 提取后的 Markdown 正文，用于复用现有 `IngestionService.import_document()` 入库。

阶段 28 读取和写入边界：

```text
公开 seed URL
-> robots.txt / 限速 / User-Agent
-> trafilatura 提取正文
-> data/raw/web_crawl/*.md
-> documents/chunks
-> sources
-> chunk_embeddings
```

数据安全边界：

- 只抓取公开可访问页面；不绕登录、验证码、付费墙、机构授权墙或 robots.txt 禁止。
- User-Agent 标识 RFC-RAG-Agent，不伪装浏览器，不使用 Selenium/Playwright。
- 不长期保存原始 HTML，不保存 cookie、session、Authorization header、Bearer token 或用户凭据。
- `crawl_results*.csv` 不保存网页正文或供应商原始响应，只保存状态和错误摘要。
- 已入库网页来源统一注册到 `sources` 表，继续复用 DOI/URL/标题去重和 `document_id` 关联。
- 批量执行后数据库从 documents 465 / chunks 8918 / sources 125 增至 documents 1059 / chunks 12103 / sources 645；新增内容为本地运行数据，阶段 28 停在人工核验前，不提交 SQLite 数据库。
- 新增索引通过 deterministic provider 重建，`chunk_embeddings` 增至 21021；真实 API 不作为本地全量测试或 CI 前提。

阶段 1 第一批试导入资料登记仍保留在下方，作为早期人工来源记录和历史审计依据。

本批资料采用“资料卡”形式导入：保存题录、公开摘要的转述、检索关键词和来源链接，不保存受版权限制的论文全文。

## 已登记来源（阶段 1 试导入）

| source_id | 标题 | 来源类型 | 作者或机构 | 发布时间 | URL | 是否允许全文保存 | 可信度评级 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rfc_seed_001 | 堆石混凝土及堆石混凝土大坝 / Study on rock-fill concrete dam | CNKI 摘要页、论文题录与公开摘要整理 | 金峰, 安雪晖, 石建军, 张楚汉 | 2005 | https://kns.cnki.net/kcms2/article/abstract?v=7jvqSXIa2LXUBdK4dw0XCLkKcRO8rkZ6LMUUPnH8IpFJ2iR8zuGHA1e5WffpBNepiDh_rfta6rS4U4LuO-qJaLhUnh5c-5CkPCagNMPVSAWdW7j2g4YjWYemqq7ziqRMfVTwwnFVvAbh46kqvSqjJUorkuOpi55gjpt5EPsoavCGJgU1GTvfUw==&uniplatform=NZKPT&language=CHS | 否，仅保存转述整理 | 高 | 用户补充确认的堆石混凝土开篇之作；ResearchGate 与行业页面作为辅助线索 |
| rfc_seed_002 | 堆石混凝土大坝施工方法 | 专利题录与公开资料整理 | 金峰, 安雪晖 | 2003 | https://www.civil.tsinghua.edu.cn/heen/info/1159/1950.htm | 否，仅保存转述整理 | 高 | 金峰教授主页列出的 RFC 施工方法专利 |
| rfc_seed_003 | 自密实混凝土充填堆石体试验研究 | 论文题录与引用线索整理 | 安雪晖, 金峰, 石建军 | 2005 | https://cjxy.usc.edu.cn/info/2369/1623.htm | 否，仅保存转述整理 | 中高 | 通过作者主页论文列表和相关引用页确认 |
| rfc_seed_004 | 自密实堆石混凝土力学性能的试验研究 | 公开摘要整理 | 石建军, 张志恒, 金峰, 张楚汉 | 2007 | https://rockmech.whrsm.ac.cn/CN/abstract/abstract25492.shtml | 否，仅保存转述整理 | 高 | 期刊官网摘要页 |
| rfc_seed_005 | Rock-filled concrete, the new norm of SCC in hydraulic engineering in China | 论文题录与摘要整理 | Xuehui An, Qiong Wu, Feng Jin 等 | 2014 | https://www.sciencedirect.com/science/article/pii/S0958946514001413 | 否，仅保存转述整理 | 高 | Cement and Concrete Composites 论文页 |
| rfc_seed_006 | Experimental study of filling capacity of self-compacting concrete and its influence on the properties of rock-filled concrete | 论文题录与摘要整理 | Yuetao Xie, David J. Corr, Mohend Chaouche, Feng Jin, Surendra P. Shah | 2014 | https://www.scholars.northwestern.edu/en/publications/experimental-study-of-filling-capacity-of-self-compacting-concret | 否，仅保存转述整理 | 高 | Northwestern Scholars 题录页 |
| rfc_seed_007 | Lattice Boltzmann-Discrete Element Modeling Simulation of SCC Flowing Process for Rock-Filled Concrete | 开放获取论文整理 | Song-Gui Chen, Chuan-Hu Zhang, Feng Jin 等 | 2019 | https://www.mdpi.com/1996-1944/12/19/3128 | 可开放访问，本项目仍只保存转述整理 | 高 | MDPI Materials 开放论文 |
| rfc_seed_008 | A Brief Review of Rock-Filled Concrete Dams and Prospects for Next-Generation Concrete Dam Construction Technology | 开放获取综述整理 | Feng Jin, Duruo Huang, Michel Lino, Hu Zhou | 2023 | https://www.engineering.org.cn/engi/CN/PDF/10.1016/j.eng.2023.09.020 | 可开放访问，本项目仍只保存转述整理 | 高 | Engineering 开放综述 |
| rfc_seed_009 | Filling the gaps in large concrete dams | 高校公开网页整理 | Tsinghua University | 2021 | https://www.tsinghua.edu.cn/en/info/1418/10419.htm | 否，仅保存转述整理 | 中高 | 清华大学英文新闻/特写 |
| rfc_seed_010 | 堆石混凝土绝热温升性能初步研究 | 论文题录与公开摘要整理 | 金峰, 李乐, 周虎, 安雪晖 | 2008 | https://sjwj.cbpt.cnki.net/portal/journal/portal/client/paper/65e4dbdb69e5e0bc75cdedaf22704c3e | 否，仅保存转述整理 | 高 | 覆盖水化热、温控和抗裂主题 |

## 后续补充方向

- 增加更多工程应用案例资料，覆盖不同坝型和施工场景。
- 增加规范、规程或行业标准的公开目录信息，但不保存受版权限制全文。
- 对每条资料补充主题标签，例如概念、施工、质量控制、温控、力学性能、工程应用。

## 全文来源目录

阶段 1 已开始从资料卡扩展到论文原文导入。全文 PDF 的来源分类、访问权限和本地文件名见：

- `docs/source_catalog.md`
- `data/fulltext_manifest.csv`

全文 PDF 保存在 `data/fulltext/`，该目录已加入 `.gitignore`，用于本地私有资料库，不提交到 GitHub。

## 题录元数据来源目录

阶段 1 已新增题录优先语料库，用于在不下载更多全文的情况下扩大检索覆盖面。

当前题录文件：
- `data/metadata/rfc_papers_metadata.csv`
- `data/metadata/rfc_papers_metadata.jsonl`
- `data/imports/metadata_corpus/*.md`

当前来源：
- OpenAlex
- Crossref
- 后续可合并 Semantic Scholar、CNKI 导出、Google Scholar 辅助工具导出、Zotero/EndNote/RIS 导出

当前规模：
- 116 条题录记录。
- 69 条包含公开摘要。
- 115 条已作为 `metadata_record` 文档进入 SQLite 检索库。

合规说明：
- 题录语料只保存公开元数据和摘要，不保存未授权全文。
- Google Scholar 不作为直接网页爬取主链路；如需使用，优先通过可导出的题录文件进入本项目。
- CNKI 机构账号获取的内容优先走题录导出或本地私有导入，不公开再分发全文。

## Source Registry 关系说明

阶段 4 之后，来源治理以 `sources` 表为准，文档关系如下：

```text
docs/data_sources.md
  人读来源说明和合规边界

data/fulltext_manifest.csv
  PDF 全文清单，包含本地路径和访问权限

data/source_candidates.csv
  学术 API 发现的候选来源

data/metadata/rfc_papers_metadata.csv
  题录 CSV，适合批量导入和评测

data/imports/metadata_corpus/*.md
  题录 Markdown 卡片，可进入 documents/chunks

sources
  数据库来源登记库，统一保存来源元数据、去重键、权限、可信度、状态和 document 关联

documents/chunks
  已导入并可检索、可引用的内容库
```

同步入口：

```powershell
python scripts/sync_sources.py
```

来源评测入口：

```powershell
python scripts/evaluate_sources.py
```

重新索引入口：

```text
POST /sources/{source_id}/reindex
```

设计原则：

- `sources` 管“这条资料来源是什么、是否可信、能否保存、是否已导入”。
- `documents/chunks` 管“这条资料实际进入 RAG 检索后的正文和片段”。
- `fulltext_permission` 与 `trust_level` 分开记录，避免把版权/授权问题和来源质量混在一起。
- 对受限全文，保留题录、摘要、合法来源链接和本地授权路径，不公开分发全文。

## 前端展示入口

阶段 5 已新增前端工作台：

```text
GET /
```

来源相关界面能力：

- 查看 `sources` 列表。
- 按关键词、状态、全文保存权限筛选来源。
- 查看来源可信度、全文权限、年份、分类、URL/DOI 和 `document_id`。
- 触发 `POST /sources/sync` 同步现有来源文件。
- 触发 `POST /sources/{source_id}/reindex` 重新导入单条来源。

资料相关界面能力：

- 查看 `documents` 列表。
- 查看每篇资料的 chunk 数量。
- 点击资料查看 `documents/{document_id}/chunks`。
- 在聊天引用侧栏中核验回答依据的具体 chunk。

阶段 5 的界面不改变数据来源合规边界：受限全文仍不公开分发，前端只展示本地系统已登记或已导入的来源和片段。

## 阶段 6 评测与数据来源边界

阶段 6 进入检索优化与评测，没有新增外部资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 6 使用的评测数据来自现有本地项目文件：

```text
data/evaluation/keyword_queries.csv
data/evaluation/chat_queries.csv
data/evaluation/keyword_results.csv
data/evaluation/vector_results.csv
data/evaluation/chat_results.csv
```

阶段 6 新增的评测输出是对现有资料库和现有评测集的分析结果：

```text
data/evaluation/hybrid_results.csv
data/evaluation/retrieval_error_cases.csv
```

它们不包含新的受限全文，只记录查询、期望命中、命中结果、通过状态、失败原因、改进建议和 hybrid 优化后的状态。

阶段 6 的核心关系是：

```text
sources
-> documents/chunks
-> chunk_embeddings
-> keyword/vector/hybrid retrieval
-> evaluation results
-> error cases
```

合规结论：

- `sources` 仍然负责来源可信度、全文权限和状态。
- `documents/chunks` 仍然只保存已导入的本地资料或题录卡片。
- `chunk_embeddings` 是由 chunks 派生出的可重建索引数据。
- `hybrid_results.csv` 和 `retrieval_error_cases.csv` 是评测产物，不是新的资料来源。
- 阶段 6 没有公开分发受限全文，也没有引入新的爬虫链路。

## 阶段 7 Agent 化与数据来源边界

阶段 7 进入 Agent 化，没有新增外部资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

Agent 工具只读取现有数据：

```text
sources
documents/chunks
chunk_embeddings
qa_logs
data/evaluation/*.csv
```

阶段 7 新增的 Agent 工具：

```text
search_knowledge
hybrid_search_knowledge
answer_with_citations
list_sources
get_source_detail
```

这些工具复用现有 service 和 repository：

```text
KeywordSearchService
HybridSearchService
CitationAnswerService
SourceRepository
```

阶段 7 新增的评测输入和输出：

```text
data/evaluation/agent_queries.csv
data/evaluation/agent_results.csv
```

它们不包含新的受限全文，只记录 Agent 任务、期望工具、期望拒答、来源命中、引用有效性和工具调用结果。

阶段 7 的核心关系是：

```text
sources
-> documents/chunks
-> keyword/vector/hybrid retrieval
-> citation chat
-> Agent read-only tools
-> agent evaluation results
-> frontend tool call display
```

合规结论：

- Agent 不新增联网爬虫链路。
- Agent 不绕过 `sources` 的可信度、全文权限和状态记录。
- Agent 不自动执行 `POST /sources/{source_id}/reindex` 等写入型动作。
- `agent_results.csv` 是评测产物，不是新的资料来源。
- 受限全文仍只保存在本地授权环境中，不公开分发。

## 阶段 8 Brain Workflow 与数据来源边界

阶段 8 进入 Brain 中控层与 RAG Workflow 配置化，没有新增外部资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

Brain workflow 只读取或复用现有数据：

```text
sources
documents/chunks
chunk_embeddings
qa_logs
data/evaluation/*.csv
```

阶段 8 新增的评测输出：

```text
data/evaluation/brain_workflow_results.csv
```

它不是新的资料来源，而是对现有 chat 评测集和现有资料库的配置化评测产物。该 CSV 记录不同 Brain 配置下的：

- config 名称
- 实际检索模式
- workflow steps
- 来源命中
- citation 有效性
- 拒答匹配
- 模型提供方和模型名称

阶段 8 的核心关系是：

```text
sources
-> documents/chunks
-> chunk_embeddings
-> keyword/vector/hybrid retrieval
-> Brain workflow
-> chat/agent answer
-> brain workflow evaluation results
```

合规结论：

- Brain 不联网爬取新资料。
- Brain 不绕过 `sources` 的可信度、全文权限和状态记录。
- Brain 不自动执行 `source reindex` 等写入型动作。
- `brain_workflow_results.csv` 是评测产物，不是新的资料来源。
- 受限全文仍只保存在本地授权环境中，不公开分发。

## 阶段 9 真实模型接入与数据来源边界

阶段 9 进入真实模型接入与模型评测，没有新增外部文献资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 9 新增的是模型服务配置和评测产物：

```text
docs/model_provider_evaluation.md
scripts/evaluate_model_configs.py
data/evaluation/model_config_results.csv
data/evaluation/mimo_jina_chat_results.csv
data/evaluation/mimo_jina_agent_results.csv
data/evaluation/mimo_jina_brain_workflow_results.csv
```

真实模型 API 不是资料来源。它只用于：

```text
chunks -> embedding vectors
prompt/context -> chat answer
evaluation results -> quality comparison
```

阶段 9 不保存真实模型服务返回的受限文献全文；`model_config_results.csv` 只保存配置名、评测项、通过数、总数、provider/model 名称和 skipped reason。

阶段 9.1 使用 Jina embedding 和 MIMO chat 做真实模型补充评测。Jina 和 MIMO 都是模型服务，不是文献资料来源；新增的 `mimo_jina_*_results.csv` 只保存问题、通过状态、来源标题、引用数量、provider/model 名称和错误摘要，不保存 API key，也不新增受限全文。

合规结论：

- `sources` 仍然负责资料来源、可信度、权限和状态。
- `documents/chunks` 仍然只保存已导入的本地资料或题录卡片。
- `chunk_embeddings` 是由 chunks 派生出的可重建索引数据。
- 真实 API key 只允许放在本地 `.env`，不得提交到 Git。
- MIMO Token Plan key、Jina API key 和任何真实模型凭证不得写入源码、文档或评测 CSV。
- 阶段 9 没有公开分发受限全文，也没有引入新的爬虫链路。

## 阶段 10 真实 RAG 质量校准与数据来源边界

阶段 10 进入真实 RAG 质量校准与拒答边界优化，没有新增外部文献资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 10 复用现有数据：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/*.csv
```

阶段 10 新增或更新的评测产物：

```text
data/evaluation/real_rag_failure_cases.csv
data/evaluation/vector_results.csv
data/evaluation/hybrid_results.csv
data/evaluation/brain_workflow_results.csv
data/evaluation/model_config_results.csv
data/evaluation/stage10_jina_vector_results.csv
data/evaluation/stage10_jina_hybrid_results.csv
data/evaluation/stage10_mimo_jina_chat_results.csv
data/evaluation/stage10_mimo_jina_agent_results.csv
data/evaluation/stage10_mimo_jina_brain_workflow_results.csv
```

这些文件不是新的资料来源。它们只记录：

- 评测问题。
- 期望命中条件。
- 通过或失败状态。
- 命中标题和来源类型。
- 引用数量和拒答状态。
- provider/model 名称。
- 失败原因和改进建议。

阶段 10 的核心关系是：

```text
已有 sources / documents / chunks
-> deterministic or Jina chunk_embeddings
-> keyword / vector / hybrid retrieval
-> Brain evidence confidence
-> chat / agent / brain workflow evaluation
-> stage 10 quality conclusion
```

合规结论：

- 阶段 10 不新增爬虫链路。
- 阶段 10 不新增外部文献或受限全文。
- Jina 和 MIMO 仍然是模型服务，不是资料来源。
- `stage10_*_results.csv` 是质量校准结果，不是资料库。
- `real_rag_failure_cases.csv` 是失败分析表，不包含受限全文，只保存可追溯标题、简短证据摘要和诊断。
- 真实 API key 只允许放在本地 `.env`，不得写入源码、文档、CSV 或 Obsidian。
- 自动回归继续优先使用 deterministic provider，避免把真实模型密钥、网络和余额变成测试前提。

## 阶段 11 真实用户问题评测与数据来源边界

阶段 11 进入真实用户问题评测集与跨语言质量提升，没有新增外部文献资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 11 复用现有数据：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/keyword_queries.csv
data/evaluation/chat_queries.csv
data/evaluation/agent_queries.csv
```

阶段 11 新增或更新的评测产物：

```text
data/evaluation/user_questions.csv
data/evaluation/user_question_results.csv
data/evaluation/user_question_review_samples.csv
docs/stage11_user_evaluation_plan.md
```

这些文件不是新的资料来源。它们只记录：

- 用户问题。
- 语言类型。
- 期望来源命中。
- 期望拒答状态。
- 期望回答要点。
- 自动评测通过或失败状态。
- 来源标题、答案摘要、审阅字段和 judge prompt。

阶段 11 的核心关系是：

```text
已有 sources / documents / chunks
-> keyword / vector / hybrid retrieval
-> user question evaluation
-> cross-language query expansion
-> manual review samples
-> stage 11 quality conclusion
```

合规结论：

- 阶段 11 不新增爬虫链路。
- 阶段 11 不新增外部文献或受限全文。
- `user_questions.csv` 是评测输入，不是资料库。
- `user_question_results.csv` 和 `user_question_review_samples.csv` 是质量评测产物，不保存受限全文。
- 审阅抽样表只保存来源标题、答案摘要、审阅字段和必要备注，不保存完整论文正文。
- Jina、MIMO 或其他真实模型仍然是模型服务，不是资料来源。
- 真实 API key 只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- 自动回归继续使用 deterministic provider；真实模型只适合发布前质量校准或离线审阅。

## 阶段 12 质量审阅与上下文最小补全产物

阶段 12 新增或更新的评测与设计产物：

```text
data/evaluation/stage12_quality_review_results.csv
docs/stage12_quality_review.md
docs/stage13_decompose_plan.md
```

这些文件不是新的文献资料来源。它们只记录：

- 审阅样本 ID 和用户问题 ID。
- 语言类型和评测配置。
- 期望回答要点。
- Faithfulness、Answer Coverage、Citation Quality 的人工或离线审阅结论。
- 风险等级、审阅备注和下一步建议。
- 阶段 13 Decompose 的后续设计边界。

阶段 12 的上下文补全也不新增资料来源。它只在检索前使用调用方传入的可选 `history`，把“它”“这个技术”等省略问法补成更完整的检索 query。补全后的 query 不会写入 `sources`、`documents`、`chunks` 或 `chunk_embeddings`。

合规结论：

- 阶段 12 不新增爬虫链路。
- 阶段 12 不新增外部文献或受限全文。
- `stage12_quality_review_results.csv` 是质量审阅产物，不是资料库。
- `docs/stage13_decompose_plan.md` 是后续设计文档，不是资料来源。
- 质量审阅只保存来源标题、答案摘要、审阅字段和必要备注，不保存完整论文正文。
- HyDE 只保留为离线实验建议，不进入默认链路或自动回归。
- 真实 API key 仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。

## 阶段 13 Decompose 与证据合并产物

阶段 13 新增或更新的工程与评测产物：

```text
app/services/retrieval/decompose.py
scripts/evaluate_decompose.py
data/evaluation/stage13_decompose_results.csv
docs/stage13_decompose_plan.md
```

这些文件不是新的文献资料来源。它们只记录：

- 规则式拆解后的 sub query。
- 每个问题的检索、合并、去重和 rerank 解释。
- 来源命中、拒答匹配、provenance 和 answer coverage proxy 等评测字段。
- 阶段 13 的设计边界和质量结论。

阶段 13 不新增外部资料来源，不新增爬虫链路，不保存受限全文。Decompose 只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/user_questions.csv
```

合规结论：

- `stage13_decompose_results.csv` 是质量评测产物，不是资料库。
- sub query provenance 只说明证据由哪个子问题召回，不改变资料来源归属。
- 真实 API key 仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 14 真实 Embedding 与回答覆盖校准产物

阶段 14 新增或更新的工程与评测产物：

```text
docs/stage14_real_quality_calibration.md
scripts/evaluate_stage14_embedding_comparison.py
data/evaluation/stage14_embedding_comparison.csv
scripts/evaluate_stage14_answer_coverage.py
data/evaluation/stage14_answer_coverage_review.csv
scripts/evaluate_stage14_decompose_provenance.py
data/evaluation/stage14_decompose_provenance_review.csv
```

这些文件不是新的文献资料来源。它们只记录：

- deterministic baseline 与 real_config 的评测状态、指标和失败 query。
- Answer Coverage、Faithfulness、Citation Quality、risk_level 和 recommendation。
- Decompose provenance、topic_terms、both_match、source_type、raw_score、final_score 等证据级审阅字段。
- 真实配置缺失或真实结果文件缺失时的 `skipped` / `missing_results` 原因。

阶段 14 不新增外部资料来源，不新增爬虫链路，不保存受限全文。它只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/user_questions.csv
data/evaluation/user_question_results.csv
data/evaluation/stage13_decompose_results.csv
```

合规结论：

- `stage14_embedding_comparison.csv` 是评测汇总表，不是资料库。
- `stage14_answer_coverage_review.csv` 是质量审阅表，不保存受限论文全文或供应商原始敏感响应。
- `stage14_decompose_provenance_review.csv` 是证据解释表，不改变来源归属。
- 真实 API key 仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 15 真实配置复跑与质量审阅报告产物

阶段 15 新增或更新的工程与评测产物：

```text
docs/stage15_real_review_report.md
scripts/evaluate_stage15_real_config.py
data/evaluation/stage14_real/real_config_status.csv
data/evaluation/stage14_real/vector_results.csv
data/evaluation/stage14_real/hybrid_results.csv
data/evaluation/stage14_real/user_question_results.csv
data/evaluation/stage14_real/chat_results.csv
data/evaluation/stage14_real/agent_results.csv
data/evaluation/stage14_real/brain_workflow_results.csv
scripts/evaluate_stage15_answer_coverage_review.py
data/evaluation/stage15_answer_coverage_review.csv
scripts/build_stage15_quality_report.py
data/evaluation/stage15_quality_summary.csv
docs/stage15_quality_report.md
app/frontend/quality_report.html
```

这些文件不是新的文献资料来源。它们只记录：

- 真实配置复跑的 completed、skipped 或 error 状态。
- 脱敏后的评测通过数、失败数、provider/model 名称和错误摘要。
- Answer Coverage、Faithfulness、Citation Quality、risk_level、review_note 和 next_action。
- 质量汇总、报告建议和只读展示所需的指标。

阶段 15 不新增外部资料来源，不新增爬虫链路，不保存受限全文。它只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/stage14_embedding_comparison.csv
data/evaluation/stage14_answer_coverage_review.csv
data/evaluation/stage14_decompose_provenance_review.csv
data/evaluation/stage14_real/*.csv
```

合规结论：

- `data/evaluation/stage14_real/` 是真实配置评测结果目录，不是资料库。
- `stage15_answer_coverage_review.csv` 是质量复核表，不保存受限论文全文或供应商原始敏感响应。
- `stage15_quality_summary.csv` 和 `docs/stage15_quality_report.md` 是报告产物，不改变来源归属。
- `app/frontend/quality_report.html` 是只读静态报告页，不触发真实 API 调用，不写数据库，不重新索引来源。
- 真实 API key、Bearer token 和供应商原始敏感响应仍只允许存在本地 `.env` 或内存调用中，不得写入源码、文档、CSV、测试、Git 或 Obsidian。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 16 真实质量风险闭环产物

阶段 16 新增或更新的工程与评测产物：

```text
docs/stage16_quality_risk_closure.md
scripts/analyze_stage16_decompose_diagnostics.py
data/evaluation/stage16_decompose_diagnostics.csv
scripts/evaluate_stage16_answer_coverage_closure.py
data/evaluation/stage16_answer_coverage_closure.csv
scripts/build_stage16_quality_closure_report.py
data/evaluation/stage16_quality_closure_summary.csv
docs/stage16_quality_closure_report.md
app/frontend/quality_report.html
```

这些文件不是新的文献资料来源。它们只记录：

- real decompose SSL EOF 的脱敏错误分类、根因、可重试状态和阻断状态。
- 阶段 15 high/medium Answer Coverage 样例的 `risk_before`、`risk_after`、Faithfulness、Answer Coverage、Citation Quality、根因、证据摘要、决策和 next action。
- 阶段 16 quality gate、报告建议和人工核验边界。
- 脱敏来源标题、回答摘要和必要指标，不保存供应商原始敏感响应。

阶段 16 不新增外部资料来源，不新增爬虫链路，不保存受限全文。它只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/stage14_real/real_config_status.csv
data/evaluation/stage14_embedding_comparison.csv
data/evaluation/stage15_answer_coverage_review.csv
docs/progress.md
```

合规结论：

- `stage16_decompose_diagnostics.csv` 是真实错误诊断表，不是资料库，也不保存 API key 或完整供应商响应。
- `stage16_answer_coverage_closure.csv` 是质量复核闭环表，不保存受限论文全文。
- `stage16_quality_closure_summary.csv` 和 `docs/stage16_quality_closure_report.md` 是报告产物，不改变来源归属。
- `app/frontend/quality_report.html` 仍是只读静态报告页，不触发真实 API 调用，不写数据库，不重新索引来源。
- 真实 API key、Bearer token、供应商原始敏感响应和受限全文仍不得写入源码、文档、CSV、测试、Git 或 Obsidian。
- 阶段 16 已完成人工核验、提交、创建 `phase-16-complete` tag 并合并到 `main`。

## 阶段 17 检索架构升级产物

阶段 17 新增或更新的工程与评测产物：

```text
docs/stage17_retrieval_architecture_upgrade.md
app/services/retrieval/context_expansion.py
app/services/retrieval/bm25_search.py
app/services/retrieval/rrf_fusion.py
scripts/evaluate_stage17_retrieval_upgrade.py
data/evaluation/stage17_retrieval_upgrade_results.csv
data/evaluation/stage17_retrieval_upgrade_manual_review.csv
docs/stage17_retrieval_upgrade_report.md
tests/test_stage17_manual_review.py
```

阶段 17 不新增外部资料来源，不新增爬虫链路，不新增受限全文保存。它只读取现有：

```text
documents
chunks
chunk_embeddings
data/evaluation/keyword_queries.csv
data/evaluation/hybrid_results.csv
```

数据安全边界：

- `stage17_retrieval_upgrade_results.csv` 是检索评测表，不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- `stage17_retrieval_upgrade_manual_review.csv` 是 Phase 9 人工复核结果表，只记录脱敏的复核判断（review_decision、retrieval_risk、evidence、tuning_suggestion 等），不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- `docs/stage17_retrieval_upgrade_report.md` 是只读报告（含 Phase 9 人工复核摘要），不触发真实 API；报告由已有结果 CSV 重生成，不跑检索、不访问数据库、不调用真实 provider。
- 阶段 17 使用 deterministic provider 运行默认评测，不让真实 API 成为 CI 或本地全量测试前提。
- 阶段 17 当前停在用户人工核验前状态，尚未提交、尚未打 `phase-17-complete` tag、尚未推送。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 18 语料扩充与评测/质量体系增强产物

阶段 18 新增或更新的工程与评测产物：

```text
docs/stage18_corpus_evaluation_quality.md
app/services/ingestion/pdf_text.py
scripts/expand_open_access_corpus.py
data/metadata/stage18_oa_discovery.csv
data/fulltext_manifest.csv（新增 5 行开放获取全文标注）
data/evaluation/stage18_hard_queries.csv
scripts/evaluate_stage18_hard_set.py
data/evaluation/stage18_hard_results.csv
data/evaluation/stage18_config_comparison.csv
data/evaluation/stage18_config_comparison_real.csv
data/evaluation/stage18_corpus_stats.csv
scripts/build_stage18_quality_report.py
data/evaluation/stage18_quality_summary.csv
docs/stage18_quality_report.md
app/frontend/quality_report.html
```

阶段 18 是本项目**首次新增外部资料来源**（开放获取全文），但严格限定在合规边界内：

- 只下载**许可允许的开放获取**全文（cc-by / cc-by-nc / cc0 / 明确 OA），来源经 OpenAlex 元数据 API 发现。
- 尊重 robots.txt 与网站条款；**不绕付费墙、登录、验证码**；下载有请求间隔。
- 受限全文（如 CNKI 机构授权）只留在本地授权环境（`data/fulltext/` gitignore），不公开分发、不进 Git。
- `data/app.sqlite`（`*.sqlite` gitignore）与 `data/fulltext/` 不提交；可提交物是解析器、manifest/source registry 条目、题录卡片和可复跑导入管线脚本。
- 真实导入篇数诚实记录：深度全文 11 -> 16（open_access_pdf 10 -> 15），未为凑 40-60 目标造假。
- 经 source registry 三层去重（DOI/URL/标题）与全文权限标注；`fulltext_manifest.csv` 只为真正新导入论文加行。

数据安全边界：

- `stage18_*` 评测/报告 CSV 与 HTML 只保存脱敏的查询、命中、排名、风险判断、来源标题和 quality gate 状态。
- 不保存 API key、Bearer token、供应商原始敏感响应或受限全文到 Git、CSV、文档、测试或 Obsidian。
- deterministic baseline 可复跑；真实 Jina 仅作发布前校准，不进 CI 或本地全量测试前提。
- `/quality-report` 及其导出端点只读取本地脱敏汇总 CSV，不触发真实 API、不写库、不做登录。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。

## 阶段 18 之后增量：用户合法下载的中文全文语料

阶段 18 主体之后，用户提供了合法下载的中文堆石混凝土全文（约 324 篇，本地 `papers_NEW`），
通过 `scripts/import_papers_corpus.py` 入库 **298 篇**（24 篇扫描/损坏按用户决定放弃）。

合规与数据安全：

- 这批中文全文是用户**合法下载**的文献，仅保存到本地 DB（`data/app.sqlite`，gitignore）与
  `data/raw`（gitignore）；原始 PDF 与 DB **不进 Git、不公开分发**。
- 新增依赖 `cryptography>=3.1` 仅用于让 pypdf 读取用户**已合法获取**的 AES 加密 PDF，
  不绕任何 DRM、登录或授权。
- `source_type=institutional_access_pdf` 标注其为本地私有全文。
- 评测产物 `data/evaluation/cn_fulltext_queries.csv` / `cn_fulltext_results.csv` 只保存问题、
  脱敏的回答摘要、来源标题与拒答判断，不含 API key 或供应商原始响应。
- 真实 Jina/MIMO 仅用于本地真实检索/分析；deterministic 索引仍负责离线回归。

## 阶段 19 中文全文文献分析与检索/评测调优产物

阶段 19 新增或更新的工程与评测产物：

```text
docs/stage19_chinese_analysis_retrieval_tuning.md
docs/stage19_literature_review.md
scripts/explore_chinese_corpus.py
scripts/evaluate_stage19_retrieval_tuning.py
app/services/retrieval/source_type_reweight.py
data/evaluation/stage19_exploration_results.csv
data/evaluation/stage19_chinese_hard_queries.csv
data/evaluation/stage19_retrieval_tuning_results.csv
data/evaluation/stage19_retrieval_tuning_summary.csv
tests/test_stage19_chinese_hard_set.py
tests/test_stage19_retrieval_tuning.py
```

阶段 19 **不新增外部资料来源**，不新增爬虫链路，不保存受版权/受限全文。它只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/stage18_hard_queries.csv（仅引用对比，不修改）
```

这些文件不是新的文献资料来源。它们只记录：

- 中文研究问题、期望命中、期望来源类型、期望拒答、期望要点关键词、干扰主题。
- 探索/调优配置名、source_type 分布、深度全文/题录命中名次与占比、precision@1、mean_rank、refusal_accuracy、distinct_wins、decision/next_action。
- 真实 API 偶发失败显式写入 `error` 字段；不静默重试到成功掩盖失败。
- 回答摘要仅截取前 200 字，且不包含 API 原始响应、API key、Bearer token。

阶段 19 的核心关系是：

```text
已有 sources / documents / chunks（含约 340 篇中文深度全文）
-> hybrid retrieval（默认 0.7 keyword + 0.3 vector + 0.15 both_match）
-> Phase 0 真实/确定性 agent 探索（脱敏结果）
-> Phase 1 中文难评测集（19 题，独立 CSV）
-> Phase 2 source_type_reweight 4 配置对照（纯函数后处理）
-> Phase 3 文献分析快照（Markdown 引用现有 CSV）
```

合规结论：

- 阶段 19 不新增爬虫链路。
- 阶段 19 不新增外部文献或受限全文。
- 用户合法下载的中文全文继续只留在本地 `data/raw/` 与 `data/app.sqlite`（均 gitignore），不公开分发、不进 Git。
- 真实 MIMO+Jina 仍是模型服务，不是资料来源；真实 API key / Bearer token / 供应商原始响应仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- 自动回归继续使用 deterministic provider；真实模型只适合发布前质量校准或离线审阅。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。
- 阶段 19 已提交、创建 `phase-19-complete` tag 并合并到 `main`，成为阶段 20 的正确基线。

## 阶段 20 中文检索默认链路落地与评测判定增强产物

阶段 20 **不新增外部资料来源**，不新增爬虫链路，不保存受版权/受限全文，不重做 chunk embedding。它只读取现有阶段 18/19 语料、索引和评测集，并新增评测/报告产物：

```text
docs/stage20_default_chain_and_eval_upgrade.md
docs/stage20_quality_report.md
scripts/evaluate_stage20_eval_upgrade.py
scripts/build_stage20_default_chain_decision.py
scripts/build_stage20_quality_report.py
data/evaluation/stage20_eval_upgrade_results.csv
data/evaluation/stage20_eval_upgrade_summary.csv
data/evaluation/stage20_eval_upgrade_real_jina_results.csv
data/evaluation/stage20_eval_upgrade_real_jina_summary.csv
data/evaluation/stage20_default_chain_decision.csv
data/evaluation/stage20_quality_summary.csv
tests/test_stage20_default_chain_and_eval_upgrade.py
tests/test_stage20_eval_upgrade.py
tests/test_stage20_default_chain_decision.py
tests/test_stage20_quality_report.py
```

阶段 20 读取边界：

```text
data/evaluation/stage19_chinese_hard_queries.csv
data/evaluation/stage19_retrieval_tuning_summary.csv（只作历史对照）
sources
documents/chunks
chunk_embeddings（deterministic 与已有 Jina 索引）
```

这些文件不是新的文献资料来源。它们只记录：

- 查询编号、配置名、judge 模式、答案级 `coverage_ratio`、deep_fulltext top-1、拒答匹配、默认链路决策和下一步动作。
- 真实 Jina query-only 校验状态：`completed` / `skipped` / `error`，以及脱敏错误摘要。
- quality gate section、status、risk_level、evidence、decision、next_action。

合规结论：

- 阶段 20 不新增论文、PDF、CAJ、网页抓取或外部资料库。
- 中文全文继续只留在本地 `data/raw/`、`data/fulltext/`、`data/app.sqlite` 和已有 chunk/index 中，均不进入 Git。
- 真实 Jina 只在 query 端按需调用，不重做 8918 条 chunk embedding；真实 API key / Bearer token / 供应商原始响应不得写入 CSV、文档、测试或 Obsidian。
- `stage20_eval_upgrade_real_jina_*` 只保存脱敏评测指标和状态，不保存供应商原始响应或受限全文。
- `/quality-report` 当前读取阶段 20 脱敏 summary 与静态 HTML，不触发真实 API、不写库、不重新索引。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。
- 阶段 20 当前停在用户人工核验前状态，尚未提交、尚未创建 `phase-20-complete` tag、尚未推送。
