# 阶段 28 任务计划：网页爬取 + 自动入库管线

## 目标

在阶段 27「Chainlit 前端 + Docker 容器化 + GitHub Actions CI」已完成并合并到 `main` 的基础上，完成阶段 28：构建网页爬取 + 自动入库管线（Web Crawl & Auto-Ingest Pipeline）。给定一个种子 URL 列表（CSV），自动抓取网页内容、提取正文（trafilatura）、清洗、切分、向量化、入库，扩充堆石混凝土领域语料至 600+ 文档。阶段完成后停在用户人工核验前，不提交、不打 tag、不推送。

## 硬约束

- 阶段 28 开发完成前后均不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。
- 不移动任何已有阶段 tag，尤其是 `phase-27-complete`。
- 保留用户或其他 session 的已有改动，不重置 Git，不覆盖无关文件。
- 爬虫必须遵守 robots.txt，默认请求间隔 ≥ 2 秒，不绕登录/验证码/付费墙。
- User-Agent 必须标识自身身份，不伪装浏览器。
- 不引入 `torch` / `sentence-transformers` / `selenium` / `playwright` 等重依赖。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 保证现有 API 端点不被破坏。
- 爬取的原始 HTML 不长期保存，只保存提取后的 markdown 正文。

## Phase 顺序

### Phase 0：启动校准与文件计划

**状态：已完成**

**解决的问题**：确认阶段 27 的最终状态、tag、main 起点和阶段 28 分支。

**RAG 链路位置**：阶段起点校准，不改运行链路。

**为什么现在做**：阶段 28 依赖阶段 27 的 Chainlit/Docker/CI 基础设施，必须先确认已合并到 `main`。

**任务**
- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读阶段 27 设计文档、phase review，以及根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 核对 `phase-27-complete` tag 指向阶段 27 最终功能提交，且已合并到 main。
- 从阶段 27 完成并合并后的 main 出发，创建或切换到 `codex/phase-28-web-crawl-auto-ingest`。
- 将根目录三份 Planning with Files 文件校准为阶段 28。

**验证方式**
- `git status -sb`
- `git log --oneline -5`
- `git merge-base --is-ancestor phase-27-complete main`

**完成标准**
- 当前分支为 `codex/phase-28-web-crawl-auto-ingest`。
- `phase-27-complete` 不移动，且已并入 `main`。
- `task_plan.md`、`findings.md`、`progress.md` 已切换为阶段 28。

**2026-06-12 校准记录**
- 已确认开工前当前 `main` 为 `800b39a Merge phase 27 chainlit docker ci`。
- 已确认 `phase-27-complete -> 79f612e Complete phase 27 chainlit docker ci`。
- 已确认 `phase-27-complete` 是 `main` 的 ancestor，阶段 27 已合并到 `main`。
- 已从 `main` 创建并切换到 `codex/phase-28-web-crawl-auto-ingest`。
- 未移动任何已有阶段 tag。
- 当前工作树启动前已有 `task_plan.md`、`findings.md`、`progress.md` 修改；本阶段继续维护这三份阶段 28 planning 文件，不重置、不覆盖无关改动。
- Phase 0 自检通过：当前分支为 `codex/phase-28-web-crawl-auto-ingest`，`git merge-base --is-ancestor phase-27-complete main` 返回通过。

**错误记录**
| 时间 | 错误 | 处理 |
| --- | --- | --- |
| 2026-06-12 | 按 planning-with-files 示例用 `& (Get-Command python).Source ...` 运行 catchup 脚本时，PowerShell 报 `The expression after '&' ... was not valid` | 改为直接执行 `python C:\Users\admin\.codex\skills\planning-with-files\scripts\session-catchup.py .`，脚本运行成功且无额外输出 |

### Phase 1：阶段 28 设计文档

**状态：已完成**

**解决的问题**：把网页爬取 + 自动入库管线的设计固化成可审查文档。

**RAG 链路位置**：数据采集层（Data Ingestion Pipeline 的前端扩展）。

**为什么现在做**：先明确爬虫架构、与现有 IngestionService 的集成方式、安全边界和种子 URL 管理方式。

**任务**
- 新增 `docs/stage28_web_crawl_auto_ingest.md`。
- 说明爬虫架构：`seed_urls.csv` → `fetcher.py` → `extractor.py` → `pipeline.py` → `IngestionService.import_document()`。
- 说明与现有模块的集成：复用 IngestionService、split_text()、clean_text()、DocumentRepository、SourceRegistryService。
- 说明种子 URL 管理：CSV 格式、分类字段、可信度字段、状态跟踪。
- 说明 CLI 入口 `scripts/crawl_and_ingest.py`。
- 说明安全边界和完成标准。

**完成标准**
- 设计文档存在且覆盖爬虫架构、集成方式、URL 管理、安全边界与收尾标准。

**2026-06-12 完成记录**
- 已新增 `docs/stage28_web_crawl_auto_ingest.md`。
- 文档已覆盖：阶段起点、模块职责、CLI 参数、seed CSV、crawl results 状态、source registry 注册、索引重建、安全边界、测试方案和完成标准。
- 已明确本阶段爬虫只负责获取公开网页与正文提取，入库继续复用 `IngestionService.import_document()`，不重复实现清洗、切分和 documents/chunks 写入。

### Phase 2：爬虫核心模块

**状态：已完成**

**解决的问题**：项目目前只能手动导入本地文件，无法自动从网页获取内容。

**RAG 链路位置**：数据采集层，在 IngestionService 上游新增网页抓取能力。

**为什么现在做**：这是阶段 28 的核心工程模块，后续 CLI 脚本和批量入库都依赖它。

**任务**
- 新增 `app/services/crawling/` 模块：
  - `__init__.py`
  - `fetcher.py`：HTTP 抓取，User-Agent 标识，请求间隔，robots.txt 检查，超时/重试。
  - `extractor.py`：trafilatura 正文提取，输出 markdown 格式，提取元数据。
  - `url_manager.py`：读取 seed_urls.csv，URL 去重，状态跟踪，写入 crawl_results.csv。
  - `pipeline.py`：编排全链路：fetch → extract → 写入 markdown → IngestionService → 注册来源。
- `pyproject.toml` 新增 `trafilatura>=2.0.0`。
- 新增爬虫模块单元测试。

**完成标准**
- `app/services/crawling/` 4 个模块存在且可导入。
- 单元测试覆盖 HTTP 抓取、正文提取、URL 管理和管线编排。

**2026-06-12 完成记录**
- 已新增 `app/services/crawling/__init__.py`、`fetcher.py`、`extractor.py`、`url_manager.py`、`pipeline.py`。
- 已在 `pyproject.toml` 新增 `trafilatura>=2.0.0`。
- 已新增 `tests/test_crawling_fetcher.py`、`tests/test_crawling_extractor.py`、`tests/test_crawling_url_manager.py`、`tests/test_crawling_pipeline.py`。
- 验证通过：`.\.venv\Scripts\python.exe -m pytest tests\test_crawling_fetcher.py tests\test_crawling_extractor.py tests\test_crawling_url_manager.py tests\test_crawling_pipeline.py -q` -> 9 passed。

### Phase 3：CLI 脚本与种子 URL

**状态：已完成**

**解决的问题**：需要一个用户可用的入口来批量执行爬取 + 入库。

**RAG 链路位置**：CLI 入口层，连接爬虫模块和 IngestionService。

**为什么现在做**：核心模块就绪后，CLI 脚本是批量执行的入口。

**任务**
- 新增 `scripts/crawl_and_ingest.py`：接受 `--seed-csv`、`--output-dir`、`--delay`、`--max-urls` 参数。
- 新增 `data/crawl/seed_urls.csv`，80-120 个种子 URL，覆盖 5 个分类。
- CSV 格式：`url,category,trust_level,notes`。
- 新增 CLI 集成测试。

**完成标准**
- CLI 脚本可运行，参数解析正确。
- 种子 URL 文件包含 80-120 个分类标注的 URL。

**2026-06-12 完成记录**
- 已新增 `scripts/crawl_and_ingest.py`。
- 已新增 `data/crawl/seed_urls.csv`，共 100 条 URL，五类各 20 条。
- 已新增 `tests/test_crawl_and_ingest_cli.py`。
- 验证通过：爬虫 + CLI 聚焦测试 11 passed。
- 验证通过：seed CSV 100 行、无空 URL、无重复 URL、分类分布为百科词条/高校机构/工程案例/开放论文/行业标准各 20 条。
- 验证通过：CLI dry-run `--max-urls 1` 正常输出 `processed=1`，未触发真实网页抓取。

### Phase 4：批量爬取与入库

**状态：已完成**

**解决的问题**：需要实际执行爬取，将语料库从 ~465 文档扩充到 600+ 文档。

**RAG 链路位置**：数据采集层实际执行。

**为什么现在做**：CLI 和种子 URL 就绪后，实际执行来验证管线和扩充语料。

**任务**
- 执行批量爬取。
- 监控成功/失败/跳过统计。
- 检查入库结果和来源注册。
- 处理失败 URL。
- 目标：新增 ≥ 150 个文档，总文档数达到 600+。

**完成标准**
- 入库文档 ≥ 600。
- crawl_results.csv 记录完整。
- 新增文档质量抽查通过。

**2026-06-12 完成记录**
- 阶段 28 批量爬取前基线：documents 465、chunks 8918、sources 125、chunk_embeddings 17836。
- 已执行主 seed、受控同站发现、元数据补充 seed、targeted RFC seed 多批次爬取；所有批次均保持 robots.txt 检查、默认限速、短超时和自标识 User-Agent。
- 已新增受控同站发现能力，仅在显式 `--discover-links` 下启用，同 host、过滤 fragment 和常见二进制/静态资源，并限制每页发现数量。
- 第一轮完成后数据库计数：documents 625、chunks 10543、sources 242、chunk_embeddings 17836。
- 用户追加要求爬取到 1000 篇后，继续本地批量爬取并达到：documents 1059、chunks 12103、sources 645、chunk_embeddings 21021。
- 本阶段净新增文档 594 个，总文档数已超过 1000，满足阶段 28 批量扩充目标和用户追加目标。
- 主要结果文件：`data/crawl/crawl_results.csv`、`data/crawl/crawl_results_discovery2.csv`、`data/crawl/crawl_results_extra_metadata.csv`、`data/crawl/crawl_results_targeted_rfc.csv`、`data/crawl/crawl_results_targeted_rfc_discovery.csv`。
- 质量抽查：导入内容来自公开 HTML 页面，原始 HTML 未长期保存；重复内容由 `IngestionService.import_document()` content_hash 去重并在 results CSV 标记为 `duplicate`。

### Phase 5：端到端验证与回归

**状态：已完成**

**解决的问题**：确认新增语料不破坏现有检索质量。

**RAG 链路位置**：全链路验证。

**任务**
- 全量测试。
- API 端点冒烟。
- 新入库内容检索测试。
- Docker 镜像更新验证（新增 trafilatura 依赖）。

**完成标准**
- 全量测试 ≥ 520 passed。
- 新旧内容检索正常。

**2026-06-12 完成记录**
- 第一轮 deterministic 索引重建：total=10543、indexed=1625、updated=0、skipped=8918。
- 用户追加 to1000 后再次重建：total=12103、indexed=1560、updated=0、skipped=10543。
- 重建后数据库计数：documents 1059、chunks 12103、sources 645、chunk_embeddings 21021。
- API smoke 通过：`GET /health` 200，`POST /search` 200，`POST /search/hybrid` 200。
- 检索 smoke 通过：`HybridSearchService(deterministic, reranking_enabled=False)` 返回 5 条结果。
- 受影响 agent/hybrid/search/CLI 子集回归通过：64 passed。
- 全量测试通过：533 passed, 1 warning。
- Docker build 已尝试两次，但当前环境无法从 Docker Hub 拉取 `python:3.11-slim`：BuildKit token 请求超时、legacy builder manifest 请求 EOF。该失败发生在项目构建步骤前，记录为用户人工核验项；本地 Python 依赖中 `trafilatura 2.1.0` 已安装并通过测试。

### Phase 6：文档同步、Obsidian 收尾与人工核验待提交状态

**状态：已完成**

**解决的问题**：阶段 28 收尾。

**任务**
- 更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD。
- 新增 docs/phase_reviews/phase-28.md。
- 新增 Obsidian 阶段 28 知识条目。

**完成标准**
- 所有文档同步完成。
- 不提交、不打 tag、不推送，等待用户人工核验。

**2026-06-12 完成记录**
- 已同步 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 已新增 `docs/phase_reviews/phase-28.md`。
- 已新增 Obsidian 阶段页、统一 Phase 汇报、知识点，并更新首页、阶段索引、阶段汇报索引和分类页。
- 当前仍未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR，停在用户人工核验前状态。

### Phase 8：低质量语料清理

**状态：已完成**

**解决的问题**：Phase 4 批量爬取中 `--discover-links` 在 `www.tsinghua.edu.cn` 上失控扩展，导致 594 个新增 web_page 文档中 458 个（77%）是导航页、泛新闻、机构首页等无关内容（drop_candidate），严重稀释 RAG 检索质量。

**RAG 链路位置**：数据质量治理层，位于入库之后、提交之前。

**为什么现在做**：在提交阶段 28 之前必须清理，否则这些垃圾数据会进入 Git 历史和生产索引。

**任务**
- 新增 `scripts/cleanup_drop_candidates.py` 清理脚本：
  - 读取 `data/evaluation/stage28_crawl_quality_drop_candidates.csv`，提取 458 个 document_id。
  - 删除对应的 `documents` 记录（SQLAlchemy cascade 会自动删除关联的 `chunks` 和 `chunk_embeddings`）。
  - 对应的 `sources` 记录的 `document_id` 会被 `SET NULL`（保留来源记录但断开文档关联）。
  - 删除对应的 `data/raw/web_crawl/*.md` 文件。
  - 支持 `--dry-run` 模式，先预览要删除的数量。
  - 输出清理前后的 documents/chunks/chunk_embeddings 计数对比。
- 执行清理（非 dry-run）。
- 重建 deterministic 向量索引：`python scripts/build_vector_index.py --provider deterministic --batch-size 64`。
- 运行全量测试确认无回归。

**验证方式**
- 清理前：documents ~1059, chunks ~12103, chunk_embeddings ~21021。
- 清理后：documents ~601, chunks 减少（减去 drop_candidate 的 chunks），chunk_embeddings 相应减少。
- 全量测试 ≥ 530 passed。
- 随机抽查 5 个保留文档，确认是 strong/medium/weak 相关内容。

**完成标准**
- 458 个 drop_candidate 文档及关联 chunks/embeddings 已删除。
- 向量索引已重建。
- 全量测试通过。
- 清理脚本可复用（后续如需清理 review_candidate 可直接改 CSV 路径）。

**2026-06-12 完成记录**
- 新增 `scripts/cleanup_drop_candidates.py`，支持 `--dry-run`，读取 `data/evaluation/stage28_crawl_quality_drop_candidates.csv` 中的 458 个 `document_id`。
- 新增 `tests/test_cleanup_drop_candidates.py`，覆盖候选 CSV 去重、dry-run 不改数据、正式清理会删除 web_page 文档并把 `sources.document_id` 置空。
- dry-run 结果：candidate_ids=458，existing_web_page_documents=458，chunks_to_delete=1471，embeddings_to_delete=1471，sources_to_unlink=421，raw_files_to_delete=879，unsafe_raw_paths=0。
- 清理脚本发现阶段 28 入库后 `documents.raw_path` 指向 `data/raw/<content_hash>.md`，而 `sources.local_path` 指向 `data/raw/web_crawl/web_*.md`；脚本已改为同时删除这两类项目内 Markdown 文件，安全根目录限定为 `data/raw`，且只允许 `.md` 文件。
- 正式清理结果：documents 1059 -> 601，chunks 12103 -> 10632，chunk_embeddings 21021 -> 19550，sources 保持 645；458 个 drop_candidate 文档删除，879 个 Markdown 文件删除，421 条 source 断开 document 关联。
- 已重建 deterministic 索引：`python scripts/build_vector_index.py --provider deterministic --batch-size 64` -> total=10632, indexed=0, updated=0, skipped=10632。
- 全量测试通过：`python -m pytest -q` -> 536 passed, 1 warning。

### Phase 9：Wikipedia API 百科知识补充

**状态：已完成**

**解决的问题**：原 seed_urls.csv 中 40 条 Wikipedia URL 全部被 robots.txt 拦截（`skipped_robots`），百科类知识完全缺失。Wikipedia 禁止通用爬虫但提供官方 REST API（合规渠道）。

**RAG 链路位置**：数据采集层，新增 Wikipedia API 数据源，补充概念类百科知识。

**为什么现在做**：百科知识对"堆石混凝土是什么""自密实混凝土原理"等概念类问答至关重要，是检索覆盖面的关键补充。

**任务**
- 新增 `app/services/crawling/wikipedia_fetcher.py`：
  - 使用 Wikipedia REST API：`https://en.wikipedia.org/api/rest_v1/page/html/{title}`（英文）和 `https://zh.wikipedia.org/api/rest_v1/page/html/{title}`（中文）。
  - 不需要 API key，不违反 robots.txt（官方 API 渠道）。
  - 请求间隔仍保持 ≥ 2 秒。
  - User-Agent 标识 RFC-RAG-Agent。
  - 返回 HTML 后交给 `WebContentExtractor` 提取 markdown。
- 新增 `data/crawl/wikipedia_articles.csv`：精选 30-40 篇与堆石混凝土/大坝/混凝土直接相关的 Wikipedia 文章：
  - 中文：堆石混凝土、自密实混凝土、碾压混凝土、混凝土坝、重力坝、拱坝、面板堆石坝、水泥、骨料、坍落度、抗压强度、水化反应、大体积混凝土、温控措施 等
  - 英文：Rock-filled concrete、Self-consolidating concrete、Roller-compacted concrete、Concrete dam、Gravity dam、Arch dam、Aggregate (composite)、Portland cement、Compressive strength、Mass concrete 等
- CLI 入口：扩展 `scripts/crawl_and_ingest.py` 添加 `--source wikipedia` 选项，或新增独立脚本 `scripts/ingest_wikipedia.py`。
- 新增 `tests/test_wikipedia_fetcher.py`：mock API 响应，验证 HTML 提取和入库流程。

**验证方式**
- Wikipedia API 请求成功率 ≥ 90%。
- 新增 25-35 个 Wikipedia 文档。
- 全量测试通过。

**完成标准**
- `wikipedia_fetcher.py` 存在且可导入。
- Wikipedia 文章已入库，来源类型标记为 `wikipedia`。
- 单元测试覆盖 API 请求和提取流程。

**2026-06-12 完成记录**
- 新增 `app/services/crawling/wikipedia_fetcher.py`，使用 Wikipedia REST API `https://{lang}.wikipedia.org/api/rest_v1/page/html/{title}`，支持 `en`/`zh`、项目 User-Agent、默认 2 秒限速、网络错误有限重试，不需要 API key。
- 新增 `data/crawl/wikipedia_articles.csv`，共 38 条中英文百科候选，覆盖混凝土、混凝土坝、重力坝、拱坝、水泥、骨料、坍落度、抗压强度、碾压混凝土、自密实混凝土、大体积混凝土等主题。
- 新增 `scripts/ingest_wikipedia.py`，将 Wikipedia HTML 交给 `WebContentExtractor` 提取 Markdown，再复用 `IngestionService.import_document()` 入库，并通过 `SourceRegistryService` 注册 `source_type="wikipedia"`。
- 新增 `tests/test_wikipedia_fetcher.py`，mock Wikipedia API 响应，覆盖 URL 编码、User-Agent 边界、HTML 获取、正文提取和网络错误重试；测试不依赖真实 Wikipedia。
- dry-run 结果：`scripts/ingest_wikipedia.py --dry-run --quiet` -> processed=38。
- 第一轮真实 API 入库：imported=11，fetch_failed=27；失败主要来自远端连接重置和少量 404。
- 加入网络错误有限重试后第二轮入库：imported=14，duplicate=11，fetch_failed=11，extract_failed=2；累计 `wikipedia` documents=25。
- 入库后数据库计数：documents=626，wikipedia_documents=25，chunks=11121，sources=664，wikipedia_sources=19，chunk_embeddings 在重建前为 19550。
- 已重建 deterministic 索引：`python scripts/build_vector_index.py --provider deterministic --batch-size 64` -> total=11121, indexed=489, updated=0, skipped=10632。
- 全量测试通过：`python -m pytest -q` -> 541 passed, 1 warning。

### Phase 10：公开标准文档 PDF 补充

**状态：已完成**

**解决的问题**：当前语料缺少设计规范和行业标准类文档。堆石混凝土相关的国标（GB/T）、水利行业标准（SL）和国际标准有部分公开可获取。

**RAG 链路位置**：数据采集层，利用已有 PDF 入库管线补充标准类文档。

**为什么现在做**：标准文档是高可信度来源，对"配合比设计""施工质量控制""验收规范"等问题的回答质量至关重要。

**任务**
- 新增 `data/crawl/standards_urls.csv`，列出 10-15 个可公开获取的标准文档 URL（PDF 或 HTML）：
  - 国家标准全文公开系统（openstd.samr.gov.cn）上的公开标准
  - 水利部公开的 SL 标准文件
  - USBR Concrete Manual、Design of Small Dams 等公开 PDF（部分已在 seed_urls.csv 中）
  - FEMA Dam Safety 指南（公开 PDF）
  - 其他可公开获取的混凝土/大坝标准摘要
- 新增 `scripts/ingest_standards.py`：
  - 读取 standards_urls.csv。
  - 下载 PDF/HTML 到 `data/raw/standards/`。
  - 调用 `IngestionService.import_document()` 入库。
  - 注册来源类型 `standard_document`。
- 下载和入库过程中：
  - 不绕付费墙，只获取公开免费文档。
  - 大于 20MB 的 PDF 跳过（避免超大文件）。
  - 下载间隔 ≥ 2 秒。
- 新增相关测试。

**验证方式**
- 新增 5-10 个标准类文档。
- 全量测试通过。

**完成标准**
- 标准类文档已入库，来源类型标记为 `standard_document`。
- standards_urls.csv 记录完整。
- 不包含付费/受限文档。

**2026-06-12 完成记录**
- 新增 `data/crawl/standards_urls.csv`，15 条公开 PDF 候选，来源覆盖 USACE、USBR、FEMA/FERC/ASDSO；脚本按 20MB 上限自动跳过大 PDF。
- 新增 `scripts/ingest_standards.py`，支持 `--dry-run`、`--quiet`、`--delay`、`--timeout`、`--max-mb`、`--max-retries`、`--rebuild-index`，下载 PDF 到 `data/raw/standards/` 后复用 `IngestionService.import_document()`，并注册 `source_type="standard_document"`。
- 新增 `tests/test_ingest_standards.py`，mock PDF 下载、Content-Length 超限跳过和项目 User-Agent；测试不依赖真实网络。
- 第一轮标准 PDF 入库：imported=2，download_failed=10，skipped_too_large=1。
- 调整清单并加入网络错误有限重试后第二轮入库：imported=7，duplicate=2，download_failed=4，skipped_too_large=2；累计 `standard_document` documents=9。
- 入库后数据库计数：documents=635，standard_documents=9，chunks=12716，sources=673，standard_sources=9，chunk_embeddings 在重建前为 20039。
- 已重建 deterministic 索引：`python scripts/build_vector_index.py --provider deterministic --batch-size 64` -> total=12716, indexed=1595, updated=0, skipped=11121。
- 全量测试通过：`python -m pytest -q` -> 544 passed, 1 warning。

### Phase 11：清理后验证 + 文档同步 + 人工核验待提交

**状态：已完成，等待用户人工核验**

**解决的问题**：Phase 8-10 完成后的最终验证和文档同步。

**RAG 链路位置**：全链路验证 + 文档层。

**任务**
- 运行全量测试。
- 统计最终 documents/chunks/sources/chunk_embeddings 计数。
- 用新增的百科和标准文档相关问题测试检索效果。
- 更新 `docs/stage28_crawl_quality_report.md` 反映清理后的质量分布。
- 更新 `docs/phase_reviews/phase-28.md`。
- 更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md。
- 更新 Obsidian 知识条目。

**完成标准**
- 全量测试通过。
- 文档全部同步。
- 不提交、不打 tag、不推送，等待用户人工核验。

**2026-06-12 完成记录**
- 重新运行 `scripts/review_stage28_crawl_quality.py --sample-size 80`，更新 `data/evaluation/stage28_crawl_quality_*.csv` 和 `docs/stage28_crawl_quality_report.md`；清理后 `suggested_drop_candidate=0`，剩余 `review_candidate=91`。
- 统计最终数据库计数：documents=635，web_page_documents=136，wikipedia_documents=25，standard_documents=9，chunks=12716，sources=673，wikipedia_sources=19，standard_sources=9，chunk_embeddings=21634。
- 更新 `docs/phase_reviews/phase-28.md`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 更新 Obsidian 阶段页、阶段汇报索引、阶段 28 续汇总和知识点：`低质量语料清理`、`Wikipedia API 百科补充`、`公开标准 PDF 自动入库`。
- 修正 `data/crawl/standards_urls.csv` 中 FEMA P-94 标题。
- 当前仍停在人工核验前：未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

**最终验证**
- 最终全量测试：`python -m pytest -q` -> 544 passed, 1 warning。
- 最终质量复核：`suggested_drop_candidate=0`。
- 最终索引状态：deterministic provider 已重建，`chunk_embeddings=21634`。
