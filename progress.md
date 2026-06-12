# 阶段 28 进度日志：网页爬取 + 自动入库管线

## 当前状态

- 当前阶段：阶段 28「网页爬取 + 自动入库管线」。
- 目标分支：`codex/phase-28-web-crawl-auto-ingest`。
- 前置条件：阶段 27 已完成提交、创建 `phase-27-complete` tag，并合并到 main。
- 阶段 28 状态：Phase 0-7 已完成（爬虫管线 + 批量入库 + 质量审查），Phase 8-11（数据清理 + Wikipedia API + 标准 PDF + 最终验证）待执行。
- 提交状态：尚未执行 `git add`、尚未提交、尚未创建 `phase-28-complete` tag、尚未 push、未创建 PR。

## 阶段 28 目标概述

构建网页爬取 + 自动入库管线（Web Crawl & Auto-Ingest Pipeline）：

1. **爬虫核心模块**：`app/services/crawling/`，包含 HTTP 抓取（fetcher）、正文提取（extractor，基于 trafilatura）、URL 管理（url_manager）和管线编排（pipeline）。
2. **CLI 脚本**：`scripts/crawl_and_ingest.py`，接受种子 URL CSV，批量执行抓取 + 入库。
3. **种子 URL 列表**：`data/crawl/seed_urls.csv`，80-120 个 URL，覆盖百科、高校、工程案例、开放论文、行业标准 5 个分类。
4. **批量入库**：复用现有 `IngestionService.import_document()`，扩充语料至 600+ 文档。
5. **新增依赖**：`trafilatura>=2.0.0`（轻量，不引入 torch/浏览器）。

## 阶段 27 验收基线

- 阶段 27 验收结论：已提交、已打 `phase-27-complete` tag、已合并到 `main`。
- 测试基线：520 passed。
- 数据基线：465 文档 / 8918 chunks。
- 关键交付：Chainlit 前端、Docker 容器化、GitHub Actions CI、前端视觉升级。

## Phase 日志

### Phase 0：启动校准与文件计划

时间：2026-06-12

状态：已完成

任务：
- 阅读 AGENT.MD 等必读文件。
- 确认 `phase-27-complete` tag 已合并到 main。
- 创建 `codex/phase-28-web-crawl-auto-ingest` 分支。
- 校准 planning 文件为阶段 28。

已完成：
- 已阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage27_chainlit_docker_ci.md`、`docs/phase_reviews/phase-27.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 已运行 `git status -sb`，启动时位于 `main...origin/main`，且已有 `task_plan.md`、`findings.md`、`progress.md` 三个阶段 28 planning 文件修改。
- 已运行 `git log --oneline -5`，确认最近提交为 `800b39a Merge phase 27 chainlit docker ci`、`79f612e Complete phase 27 chainlit docker ci`、`74afce9 Merge phase 26 retrieval performance reranking`。
- 已确认 `phase-27-complete -> 79f612e Complete phase 27 chainlit docker ci`。
- 已确认 `phase-27-complete` 已合并到 `main`，当前 `main -> 800b39a Merge phase 27 chainlit docker ci`，不是阶段 26 合并点。
- 已从阶段 27 合并后的 `main` 创建并切换到 `codex/phase-28-web-crawl-auto-ingest`。
- 已运行 planning-with-files catchup 脚本，最终命令为 `python C:\Users\admin\.codex\skills\planning-with-files\scripts\session-catchup.py .`，无额外输出。
- Phase 0 自检：`git status -sb` 显示当前分支为 `codex/phase-28-web-crawl-auto-ingest`，仅三份 planning 文件有修改；`git merge-base --is-ancestor phase-27-complete main` 通过。

错误与处理：
- 两次使用 PowerShell `& (Get-Command python).Source ...` / `& $python ...` 运行 catchup 脚本失败，报 `The expression after '&' ... was not valid`；改用直接 `python ...` 成功。

### Phase 1：阶段 28 设计文档

时间：2026-06-12

状态：已完成

本 Phase 解决的问题：先固定网页爬取与现有入库服务的边界，避免后续在代码里重复造清洗、切分、来源注册和索引重建逻辑。

RAG 链路位置：数据采集层，位于 `seed_urls.csv` 与 `IngestionService.import_document()` 之间。

为什么现在做：爬虫会引入网络访问、robots.txt、限速、正文提取和批量入库，先写设计文档可以把安全边界和复用关系讲清楚。

已完成：
- 新增 `docs/stage28_web_crawl_auto_ingest.md`。
- 固定阶段 28 核心链路：`seed_urls.csv -> CrawlUrlManager -> WebFetcher -> WebContentExtractor -> WebCrawlIngestionPipeline -> IngestionService.import_document() -> SourceRegistryService -> VectorIndexService`。
- 明确 `fetcher.py`、`extractor.py`、`url_manager.py`、`pipeline.py` 职责边界。
- 明确 CLI 参数、seed CSV 格式、crawl_results.csv 状态字段、来源注册字段、安全合规边界和测试方案。
- 明确开发过程中暂不写 Obsidian 小 Phase 汇报，阶段 28 全部开发完成后统一补齐。

### Phase 2：爬虫核心模块

时间：2026-06-12

状态：已完成

本 Phase 解决的问题：新增网页抓取、正文提取、URL 状态管理和管线编排模块，让公开网页可以进入已有 RAG 入库链路。

RAG 链路位置：数据采集层到入库层之间，负责把 URL 变成可交给 `IngestionService.import_document()` 的 Markdown 文件。

为什么现在做：设计边界已经固定，后续 CLI、seed URL 和批量入库都依赖这四个核心模块。

已完成：
- 新增 `app/services/crawling/` 模块：
  - `fetcher.py`：HTTP GET、robots.txt、限速、User-Agent、timeout/retry。
  - `extractor.py`：trafilatura 正文提取、Markdown 输出、元数据提取、短正文拒绝。
  - `url_manager.py`：seed CSV 读取去重、crawl_results.csv upsert、pending 过滤。
  - `pipeline.py`：fetch -> extract -> Markdown -> `IngestionService.import_document()` -> `SourceRegistryService.register_candidate()`。
- `pyproject.toml` 新增 `trafilatura>=2.0.0`。
- 新增 4 个聚焦测试文件，覆盖抓取、提取、URL 管理和管线编排。

验证：
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_crawling_fetcher.py tests\test_crawling_extractor.py tests\test_crawling_url_manager.py tests\test_crawling_pipeline.py -q
```

结果：
```text
9 passed in 0.56s
```

### Phase 3：CLI 脚本与种子 URL

时间：2026-06-12

状态：已完成

本 Phase 解决的问题：提供用户可运行的批量入口，并准备覆盖百科、高校/机构、工程案例、开放论文、行业标准的种子 URL。

RAG 链路位置：命令行入口层，负责把人工维护的 URL 列表交给 Phase 2 的爬虫核心模块。

为什么现在做：核心模块已完成并通过测试，只有补上 CLI 和种子 URL，才能进入实际批量爬取与入库验证。

已完成：
- 新增 `scripts/crawl_and_ingest.py`，支持 `--seed-csv`、`--output-dir`、`--results-csv`、`--delay`、`--max-urls`、`--rebuild-index`、`--dry-run`。
- 新增 `tests/test_crawl_and_ingest_cli.py`。
- 新增 `data/crawl/seed_urls.csv`，共 100 条 URL，五类各 20 条。

验证：
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_crawl_and_ingest_cli.py tests\test_crawling_fetcher.py tests\test_crawling_extractor.py tests\test_crawling_url_manager.py tests\test_crawling_pipeline.py -q
```

结果：
```text
11 passed in 0.44s
```

CSV 校验：
```text
rows 100
categories {'百科词条': 20, '高校机构': 20, '工程案例': 20, '开放论文': 20, '行业标准': 20}
missing_url 0
duplicate_url 0
```

CLI dry-run：
```powershell
.\.venv\Scripts\python.exe scripts\crawl_and_ingest.py --seed-csv data\crawl\seed_urls.csv --results-csv $env:TEMP\stage28_crawl_results_dry_run.csv --output-dir $env:TEMP\stage28_crawl_output --dry-run --max-urls 1
```

结果：
```text
dry_run: https://en.wikipedia.org/wiki/Concrete
processed=1
```

风险：
- 当前一条 seed URL 最多新增一个文档，100 条 seed 无法单独满足“新增 >=150 文档”；Phase 4 需要先核对当前 documents 基线和实际成功率，再用合规方式决定是否扩展 seed 或补充受控链接发现能力。

### Phase 4：批量爬取与入库

时间：2026-06-12

状态：已完成

本 Phase 解决的问题：真实执行网页抓取、正文提取、入库和来源注册，验证阶段 28 管线是否能扩充语料库。

RAG 链路位置：数据采集层实际执行，从公开 URL 进入 `documents/chunks/sources`。

为什么现在做：CLI 和种子 URL 已就绪，需要用真实小批量 smoke 先验证依赖、robots、提取和入库，再决定是否扩大批量。

批量前基线：
```text
documents 465
chunks 8918
sources 125
chunk_embeddings 17836
```

关键执行：
- 安装阶段 28 新依赖：`.\.venv\Scripts\python.exe -m pip install -e .`，成功安装 `trafilatura>=2.0.0`。
- 主 seed smoke：前 3 条 Wikipedia 页面均按 robots.txt 标记为 `skipped_robots`。
- 主 seed 批量与受控发现：写入 `data/crawl/crawl_results.csv`、`data/crawl/crawl_results_discovery.csv`、`data/crawl/crawl_results_discovery2.csv`。
- 元数据补充 seed：写入 `data/crawl/extra_metadata_seed_urls.csv` 与 `data/crawl/crawl_results_extra_metadata.csv`。
- targeted RFC seed：写入 `data/crawl/targeted_rfc_seed_urls.csv`、`data/crawl/crawl_results_targeted_rfc.csv`、`data/crawl/crawl_results_targeted_rfc_discovery.csv`。

最终计数：
```text
documents 625
chunks 10543
sources 242
chunk_embeddings 17836
```

- 第一轮结果：从 465 文档增加到 625 文档，净新增 160 个文档。
- 用户追加 to1000 后结果：documents 1059、chunks 12103、sources 645。
- 总文档数达到 1000+，满足用户追加目标。
- 相对阶段 28 起点新增 chunks 3185 个，sources 从 125 增至 645。
- `chunk_embeddings` 尚未更新，Phase 5 需要显式重建向量索引。

主要问题与处理：
- 多个站点被 robots.txt 禁止或无法稳定提取，按 `skipped_robots`、`fetch_failed`、`extract_failed` 记录，没有绕过限制。
- 慢站点触发 `TimeoutError` 导致一次长批次中断；已扩展 fetcher 异常捕获并补充测试。
- 100 条 seed 无法单独满足新增 150+ 的数量目标；已通过显式受控同站发现和 targeted RFC seed 补齐，没有拆分同一网页伪造文档。

### Phase 5：端到端验证与回归

时间：2026-06-12

状态：已完成

本 Phase 解决的问题：确认新增网页语料、索引重建、CLI 与既有 API/测试套件可以协同工作。

RAG 链路位置：从 documents/chunks/sources 到 vector index，再到检索/API 的端到端验证层。

为什么现在做：Phase 4 已真实扩充语料库，但 embedding 索引仍停留在旧计数；必须先重建索引并跑回归，才能进入文档和 Obsidian 收尾。

索引重建：

```powershell
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider deterministic --batch-size 64
```

结果：

```text
vector index built provider=deterministic model=hash-token-v1 dimension=64 content_hash=tracked total=10543 indexed=1625 updated=0 skipped=8918
```

用户追加 to1000 后再次重建，结果：

```text
vector index built provider=deterministic model=hash-token-v1 dimension=64 content_hash=tracked total=12103 indexed=1560 updated=0 skipped=10543
```

重建后计数：

```text
documents 1059
chunks 12103
sources 645
chunk_embeddings 21021
```

API / 检索 smoke：

```text
GET /health -> 200
POST /search -> 200
POST /search/hybrid -> 200
HybridSearchService deterministic smoke -> 5 results
```

测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_agent_tools.py tests/test_agentic_graph.py tests/test_hybrid_search.py tests/test_vector_search_api.py tests/test_crawl_and_ingest_cli.py -q
```

结果：

```text
64 passed
```

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

结果：

```text
533 passed, 1 warning
```

问题与处理：
- 全量测试首次失败时，原因是本地 `.env` 中真实 Jina reranking 配置进入 pytest，导致测试误触发真实 API。已新增 `tests/conftest.py`，强制测试进程使用 deterministic reranking。
- Docker build 尝试两次均未能拉取 `python:3.11-slim` 基础镜像：BuildKit token 请求超时，legacy builder manifest 请求 EOF。本地无该基础镜像缓存，失败发生在项目构建步骤前；记录为人工核验联网环境复测项。
- 本地 Python 环境已确认 `trafilatura 2.1.0` 安装可用。

### Phase 6：文档同步、Obsidian 收尾与人工核验待提交状态

时间：2026-06-12

状态：已完成

本 Phase 解决的问题：把阶段 28 的工程结果、使用方式、安全边界和人工核验项同步到普通文档与 Obsidian，并停在未提交状态。

RAG 链路位置：阶段收尾与项目知识管理，不改变运行链路。

为什么现在做：阶段 28 工程链路和测试已完成，需要把“如何本地自行爬取”和“哪些内容等待人工核验”写清楚，方便用户核验与后续接手。

已完成：
- 更新 `README.md`：当前阶段切到阶段 28，新增本地网页爬取与自动入库命令。
- 更新 `docs/progress.md`：顶部新增阶段 28 最新状态、验证结果、人工核验重点和面试表达。
- 更新 `docs/architecture.md`：新增 Crawling 层和阶段 28 架构说明。
- 更新 `docs/data_sources.md`：新增阶段 28 网页来源、运行数据和安全边界说明。
- 更新 `AGENT.MD`：新增阶段 28 之后的网页爬取与自动入库规则。
- 新增 `docs/phase_reviews/phase-28.md`：待人工核验草稿。
- 新增 Obsidian：
  - `obsidian-vault/阶段/阶段 28 - 网页爬取与自动入库管线.md`
  - `obsidian-vault/阶段汇报/阶段 28 - 网页爬取与自动入库管线/阶段 28 Phase 汇报索引.md`
  - `obsidian-vault/阶段汇报/阶段 28 - 网页爬取与自动入库管线/阶段 28 汇总 - 网页爬取与自动入库管线.md`
  - `obsidian-vault/知识点/网页爬取与自动入库管线.md`
- 更新 Obsidian 首页、阶段索引、阶段汇报索引、数据工程/RAG 链路/测试与验证分类页。

当前提交边界：
- 未执行 `git add`。
- 未执行 `git commit`。
- 未创建 `phase-28-complete` tag。
- 未执行 `git push`。
- 未创建 PR。
- 当前状态等待用户人工核验和明确授权。

### Phase 7：人工核验 + 语料质量筛选

时间：2026-06-12

状态：已完成（只读审查，不删除数据）

本 Phase 解决的问题：用户要求对爬取到 1000 篇后的语料做人工核验和质量筛选。当前先生成可审查报告和候选清单，不直接删除数据库内容。

RAG 链路位置：数据质量治理层，位于网页入库之后、提交/发布之前。

为什么现在做：数量达标后必须检查相关性，否则泛新闻、导航页和机构主页会稀释 RAG 检索质量。

已完成：
- 新增 `scripts/review_stage28_crawl_quality.py`。
- 生成 `docs/stage28_crawl_quality_report.md`。
- 生成质量审查 CSV：
  - `data/evaluation/stage28_crawl_quality_summary.csv`
  - `data/evaluation/stage28_crawl_quality_documents.csv`
  - `data/evaluation/stage28_crawl_quality_review_sample.csv`
  - `data/evaluation/stage28_crawl_quality_domains.csv`
  - `data/evaluation/stage28_crawl_quality_keep_candidates.csv`
  - `data/evaluation/stage28_crawl_quality_manual_review_candidates.csv`
  - `data/evaluation/stage28_crawl_quality_drop_candidates.csv`

审查结果：
```text
web_page documents 594
source linked 540
unlinked 54
strong 45
medium 4
weak 87
low 458
keep_candidate 45
review_candidate 91
drop_candidate 458
```

验证：
```powershell
.\.venv\Scripts\python.exe scripts\review_stage28_crawl_quality.py --sample-size 80
.\.venv\Scripts\python.exe -m py_compile scripts\review_stage28_crawl_quality.py
```

结论：
- 建议保留 strong 45 条。
- 建议人工复核 review 91 条。
- 建议重点审查 drop 458 条，尤其是 `www.tsinghua.edu.cn` 泛新闻扩展批次。
- 当前没有删除数据库内容；如用户确认删除候选，后续应写安全删除脚本、备份清单并重建 deterministic 索引。

## 架构决策

### 爬虫集成方式

- 爬虫作为 `app/services/crawling/` 模块，与现有 `app/services/ingestion/` 对接。
- 不新增数据库表，爬取状态用 CSV 跟踪，入库后注册到已有 `sources` 表。
- CLI 脚本在 `scripts/` 目录，不改 FastAPI 路由。

### 正文提取策略

- trafilatura 输出 markdown 格式，保留标题层级。
- 复用现有 `split_text()` 的 heading_path 识别。
- content_hash 去重防止同一页面重复入库。

## 遗留风险

- 部分目标网站有 robots.txt、网络超时或正文提取失败，后续用户自行扩 seed 时需要继续按 results CSV 观察成功率。
- 中文网页的 trafilatura 提取质量仍需用户人工抽查，尤其是导航、列表页和机构首页类页面。
- 大批量入库后 embedding 索引构建时间会随 chunks 增长；建议分批爬取、分批重建或记录运行耗时。
- Docker build 当前受 Docker Hub 网络/registry 访问失败影响，尚需用户在联网正常环境人工复验。
- 阶段 28 已完成开发、测试、普通文档和 Obsidian 草稿收尾；当前未提交、未 tag、未 push，等待用户人工核验。
- Phase 8-11 待执行：低质量语料清理（458 条 drop_candidate）、Wikipedia API 百科补充、公开标准 PDF 补充、最终验证。

### Phase 8：低质量语料清理

时间：待执行

状态：未开始

任务：
- 新增 `scripts/cleanup_drop_candidates.py`，读取 drop_candidates CSV 并删除对应文档/chunks/embeddings。
- 执行清理，重建 deterministic 索引。
- 清理前基线：documents 1059, chunks 12103, chunk_embeddings 21021。
- 预期清理后：documents ~601, chunks 和 embeddings 相应减少。

### Phase 9：Wikipedia API 百科知识补充

时间：待执行

状态：未开始

任务：
- 新增 `app/services/crawling/wikipedia_fetcher.py`。
- 新增 `data/crawl/wikipedia_articles.csv`（30-40 篇精选中英文百科文章）。
- 入库 Wikipedia 文章，来源类型 `wikipedia`。

### Phase 10：公开标准文档 PDF 补充

时间：待执行

状态：未开始

任务：
- 新增 `data/crawl/standards_urls.csv` 和 `scripts/ingest_standards.py`。
- 下载并入库公开标准 PDF，来源类型 `standard_document`。

### Phase 11：清理后验证 + 文档同步

时间：待执行

状态：未开始

任务：
- 全量测试。
- 更新质量报告、phase review 和所有文档。
- 停在人工核验待提交状态。
### Phase 8：低质量语料清理

时间：2026-06-12

状态：已完成

本 Phase 解决的问题：清理 Phase 4/7 识别出的 458 个低质量 `web_page` 文档，避免导航页、泛新闻和机构首页稀释 RAG 检索质量。

RAG 链路位置：数据质量治理层，位于网页入库之后、百科/标准补充与最终提交之前。

为什么现在做：在继续补充 Wikipedia 和公开标准 PDF 前，必须先把已知低质量网页文档从 documents/chunks/embeddings 中移除，避免后续索引与质量报告建立在脏数据上。

已完成：
- 新增 `scripts/cleanup_drop_candidates.py`，支持 `--dry-run`，读取 `data/evaluation/stage28_crawl_quality_drop_candidates.csv`。
- 新增 `tests/test_cleanup_drop_candidates.py`，覆盖 CSV 读取、dry-run 和正式删除路径。
- dry-run 结果：candidate_ids=458，existing_web_page_documents=458，chunks_to_delete=1471，embeddings_to_delete=1471，sources_to_unlink=421，raw_files_to_delete=879，unsafe_raw_paths=0。
- 正式清理结果：documents 1059 -> 601，chunks 12103 -> 10632，chunk_embeddings 21021 -> 19550，sources 645 保持不变；421 条 sources 的 `document_id` 已置空。
- 删除 879 个对应 Markdown 文件，覆盖 `documents.raw_path` 指向的 `data/raw/<hash>.md` 和 `sources.local_path` 指向的 `data/raw/web_crawl/web_*.md`。
- 重建 deterministic 索引：`total=10632 indexed=0 updated=0 skipped=10632`。

验证：
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cleanup_drop_candidates.py -q
.\.venv\Scripts\python.exe scripts\cleanup_drop_candidates.py --dry-run
.\.venv\Scripts\python.exe scripts\cleanup_drop_candidates.py
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider deterministic --batch-size 64
.\.venv\Scripts\python.exe -m pytest -q
```

结果：
```text
tests/test_cleanup_drop_candidates.py -> 3 passed
full test suite -> 536 passed, 1 warning
```

问题与处理：
- 首次 dry-run 发现 `documents.raw_path` 实际指向 `data/raw/<content_hash>.md`，不是预期的 `data/raw/web_crawl/*.md`；原因是 `IngestionService.import_document()` 会把 pipeline 生成的 Markdown 复制到统一 raw 仓库。脚本已改为同时读取 `Document.raw_path` 和 `Source.local_path`，并把删除边界限制在 `data/raw` 下的 `.md` 文件。
### Phase 9：Wikipedia API 百科知识补充

时间：2026-06-12

状态：已完成

本 Phase 解决的问题：原始 `seed_urls.csv` 中 Wikipedia 普通网页被 robots.txt 拦截，百科概念类知识缺口较大；本 Phase 通过 Wikipedia 官方 REST API 合规补充中英文百科正文。

RAG 链路位置：数据采集层，位于 crawling 普通网页入口旁路，但下游仍复用 Markdown -> `IngestionService.import_document()` -> sources -> vector index。

为什么现在做：Phase 8 已清掉低质量网页语料，当前库重新回到 601 篇较干净文档；此时补充百科概念能提高“混凝土坝是什么”“重力坝/拱坝区别”“自密实混凝土原理”等概念问答覆盖面。

已完成：
- 新增 `app/services/crawling/wikipedia_fetcher.py`。
- 新增 `data/crawl/wikipedia_articles.csv`，38 条中英文 Wikipedia 候选。
- 新增 `scripts/ingest_wikipedia.py`，支持 `--dry-run`、`--quiet`、`--delay`、`--timeout`、`--max-articles`、`--rebuild-index`。
- 新增 `tests/test_wikipedia_fetcher.py`，mock API 响应，不让真实 Wikipedia 成为测试前提。
- 第一轮真实 API 入库：imported 11、fetch_failed 27。
- 加入网络错误有限重试后第二轮入库：imported 14、duplicate 11、fetch_failed 11、extract_failed 2。
- 累计 Wikipedia 入库文档 25 篇；数据库计数为 documents 626、wikipedia_documents 25、chunks 11121、sources 664、wikipedia_sources 19。
- 重建 deterministic 索引：total=11121、indexed=489、updated=0、skipped=10632。

验证：
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_wikipedia_fetcher.py -q
.\.venv\Scripts\python.exe scripts\ingest_wikipedia.py --dry-run --quiet --results-csv data\crawl\wikipedia_results_dry_run.csv
.\.venv\Scripts\python.exe scripts\ingest_wikipedia.py --quiet --results-csv data\crawl\wikipedia_results.csv
.\.venv\Scripts\python.exe scripts\ingest_wikipedia.py --quiet --results-csv data\crawl\wikipedia_results_retry.csv
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider deterministic --batch-size 64
.\.venv\Scripts\python.exe -m pytest -q
```

结果：
```text
tests/test_wikipedia_fetcher.py -> 5 passed
full test suite -> 541 passed, 1 warning
```

问题与处理：
- Wikipedia API 在当前网络下多次出现远端连接重置；已加入有限重试，仍失败的条目保留在 `wikipedia_results_retry.csv`。
- 部分条目 HTTP 404 或正文过短，未强行入库；后续若要继续扩充，可人工替换为更准确的 Wikipedia title。
### Phase 10：公开标准文档 PDF 补充

时间：2026-06-12

状态：已完成

本 Phase 解决的问题：在网页与百科语料之外补充高可信公开标准/指南 PDF，增强大坝安全、混凝土结构、地震分析、应急预案和洪水风险等问题的证据来源。

RAG 链路位置：数据采集层，绕过普通网页爬虫，直接进入 PDF -> `IngestionService.import_document()` -> sources -> vector index。

为什么现在做：Phase 9 已补概念型百科知识，Phase 10 需要补“规范/指南/手册”型资料，让回答不仅知道概念，也能引用更工程化的设计与安全管理资料。

已完成：
- 新增 `data/crawl/standards_urls.csv`，15 条公开 PDF URL 候选。
- 新增 `scripts/ingest_standards.py`，支持下载间隔、20MB 上限、dry-run、quiet、有限重试和 deterministic 索引重建。
- 新增 `tests/test_ingest_standards.py`，mock 下载，不依赖真实网络。
- 第一轮真实入库：imported 2、download_failed 10、skipped_too_large 1。
- 调整清单并加入网络错误有限重试后第二轮入库：imported 7、duplicate 2、download_failed 4、skipped_too_large 2。
- 累计标准 PDF 入库 9 篇；数据库计数为 documents 635、standard_documents 9、chunks 12716、sources 673、standard_sources 9。
- 重建 deterministic 索引：total=12716、indexed=1595、updated=0、skipped=11121。

验证：
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ingest_standards.py -q
.\.venv\Scripts\python.exe scripts\ingest_standards.py --dry-run --quiet --results-csv data\crawl\standards_results_dry_run.csv
.\.venv\Scripts\python.exe scripts\ingest_standards.py --quiet --results-csv data\crawl\standards_results.csv
.\.venv\Scripts\python.exe scripts\ingest_standards.py --quiet --results-csv data\crawl\standards_results_retry.csv
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider deterministic --batch-size 64
.\.venv\Scripts\python.exe -m pytest -q
```

结果：
```text
tests/test_ingest_standards.py -> 3 passed
full test suite -> 544 passed, 1 warning
```

问题与处理：
- USACE/USBR 部分公开 PDF 在当前环境返回 403、TLS EOF 或连接重置；脚本不绕过限制，只记录失败。
- 超过 20MB 的 PDF 按规则跳过，避免把大体量文档作为默认入库前提。

### Phase 11：清理后验证 + 文档同步

时间：2026-06-12

状态：已完成，等待用户人工核验

本 Phase 解决的问题：把 Phase 8-10 的清理、百科补充和标准 PDF 补充统一收口到最终质量报告、阶段验收草稿、普通文档、Obsidian 和最终验证结果中。

RAG 链路位置：全链路验证与文档层，位于语料清理、数据补充和索引重建之后，提交/tag/push 之前。

为什么现在做：Phase 8-10 已改变语料库规模、来源类型和索引状态，必须在人工核验前把事实、命令、风险和后续检查点完整留档。

已完成：
- 重跑 `scripts/review_stage28_crawl_quality.py --sample-size 80`，更新清理后质量报告。
- 更新 `docs/stage28_crawl_quality_report.md`，记录最终质量分布、清理动作、补充语料和人工核验建议。
- 更新 `docs/phase_reviews/phase-28.md`，形成 Phase 0-11 验收草稿。
- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 更新 Obsidian 阶段页、阶段汇报索引、阶段 28 续汇总和知识点卡片。
- 修正 `data/crawl/standards_urls.csv` 中 FEMA P-94 标题。

最终计数：
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

验证：
```powershell
.\.venv\Scripts\python.exe scripts\review_stage28_crawl_quality.py --sample-size 80
.\.venv\Scripts\python.exe -m pytest -q
```

结果：
```text
quality review -> suggested_drop_candidate=0, review_candidate=91
full test suite -> 544 passed, 1 warning
```

当前状态：
- 未执行 `git add`。
- 未执行 `git commit`。
- 未创建 `phase-28-complete` tag。
- 未执行 `git push`。
- 未创建 PR。
- 等待用户人工核验。
