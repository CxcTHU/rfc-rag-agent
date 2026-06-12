# 阶段 28 发现与关键决策

## 技术选型决策

### 为什么选 trafilatura 做网页正文提取

- **正文提取质量**：trafilatura 是目前最佳的网页正文提取库之一，在学术基准测试中优于 newspaper3k、readability-lxml、justext。它能准确识别正文区域，去除导航栏、广告、页脚、推荐链接。
- **元数据提取**：内置标题、作者、发布时间、描述的提取，不需要额外库。
- **Markdown 输出**：支持直接输出 Markdown 格式，保留标题层级，和现有 `split_text()` 的 heading_path 识别完美对接。
- **robots.txt 支持**：内置 robots.txt 检查，符合项目爬取规则。
- **多语言支持**：支持中英文混合内容，适合堆石混凝土领域中英文论文和百科。
- **轻量依赖**：不引入 torch/selenium/playwright 等重依赖。

### 为什么不用 Scrapy / Selenium / Playwright

- **Scrapy**：框架太重，适合大规模爬虫项目，本项目只需要批量抓取静态页面。
- **Selenium/Playwright**：用于 JS 渲染页面，但引入浏览器依赖会让 Docker 镜像体积暴增，CI 运行时间翻倍。目标页面的正文都在初始 HTML 中，不需要 JS 渲染。
- **requests + BeautifulSoup**：需要手写正文提取逻辑，每个网站结构不同，维护成本高。trafilatura 已经解决了这个问题。

### 为什么不新增数据库表来管理爬取状态

- 现有 `sources` 表已经有 URL 去重（`source_url`）、状态（`status`）和元数据。
- 爬取任务的临时状态（pending/retrying）用 CSV 文件 `data/crawl/crawl_results.csv` 跟踪，不污染生产数据库。
- 入库成功后在 `sources` 表注册来源，复用现有来源治理体系。

## 爬虫架构

```text
data/crawl/seed_urls.csv          <- 种子 URL 列表（人工维护）
        |
scripts/crawl_and_ingest.py       <- CLI 入口
        |
app/services/crawling/
  url_manager.py                  <- URL 去重 + 状态跟踪
  fetcher.py                      <- HTTP 抓取 + robots.txt + 限速
  extractor.py                    <- trafilatura 正文提取
  pipeline.py                     <- 编排全链路
    fetch HTML
    extract text + metadata
    write temp markdown
    call IngestionService.import_document()
    register in SourceRegistry
        |
data/crawl/crawl_results.csv      <- 爬取结果记录
data/raw/web_*.md                 <- 提取的正文（markdown）
documents / chunks                <- 入库
sources                           <- 来源注册
```

## 与现有模块的关系

| 现有模块 | 复用方式 |
|---------|---------|
| `IngestionService.import_document()` | 传入提取后的 markdown 文件，复用清洗、切分、去重、入库全链路 |
| `split_text()` | 爬取内容以 markdown 格式保存，heading_path 自然保留 |
| `clean_text()` | 去除多余空白、统一换行符 |
| `DocumentRepository` | content_hash 去重，避免同一页面内容重复入库 |
| `SourceRegistryService` | 入库后注册来源，记录 URL、标题、可信度、访问时间 |
| `VectorIndexService.build_index()` | 新内容入库后构建 embedding 索引 |

## 种子 URL 分类与可信度

| 分类 | 数量目标 | 可信度 | 说明 |
|------|---------|--------|------|
| 百科词条 | ~20 | 中高 | 百度百科、维基百科中文版，适合概念类问答 |
| 高校/机构 | ~20 | 高 | 清华、河海等高校公开研究介绍 |
| 工程案例 | ~20 | 中高 | 公开新闻报道、项目介绍 |
| 开放论文 | ~20 | 高 | MDPI、Engineering 等开放获取期刊 |
| 行业标准 | ~20 | 高 | 水利部/学会公开标准目录 |

## 安全与合规边界

- 爬虫必须设置 User-Agent 标识自身身份，不伪装浏览器。
- 默认请求间隔 2 秒，可通过参数调整。
- 检查 robots.txt，被禁止的 URL 标记为 skipped。
- 不绕登录、验证码、付费墙。
- 不保存 cookie、session token 或用户凭据。
- 爬取的原始 HTML 不长期保存，只保存提取后的 markdown 正文。
- `data/crawl/crawl_results.csv` 只保存 URL、状态、标题、时间、错误信息，不保存正文内容。
- 新增依赖 `trafilatura>=2.0.0` 不引入 torch/浏览器等重依赖。

## Phase 0 启动校准发现

- `phase-27-complete` 当前指向 `79f612e Complete phase 27 chainlit docker ci`，与阶段 27 最终功能提交一致。
- `main` 当前指向 `800b39a Merge phase 27 chainlit docker ci`，不是阶段 26 合并点；阶段 27 已合并到 `main`。
- `git merge-base --is-ancestor phase-27-complete main` 通过，说明阶段 28 应从阶段 27 合并后的 `main` 出发。
- `phase-27-complete` 同时被 `main` 和 `codex/phase-27-chainlit-docker-ci` 包含；本阶段不得移动该 tag。
- 已创建并切换到 `codex/phase-28-web-crawl-auto-ingest`，阶段 28 的分支起点正确。
- 本轮启动前根目录 `task_plan.md`、`findings.md`、`progress.md` 已存在未提交修改，内容是阶段 28 预填计划；后续按用户要求在此基础上校准并推进。

## Phase 1 设计文档发现

- 当前 `IngestionService.import_document()` 已完整负责文件解析、raw 文件存储、content_hash 去重、`clean_text()`、`split_text()` 和 `DocumentRepository.create_with_chunks()`，阶段 28 不应重复实现这些逻辑。
- `SourceRegistryService.register_candidate()` 已有来源归一化、URL/标题/DOI 去重和 `document_id` 关联能力，爬虫入库后应通过它注册网页来源。
- `VectorIndexService.build_index()` 已是索引重建边界，CLI 可以用显式 `--rebuild-index` 触发，默认不让真实 API 成为测试前提。
- `pyproject.toml` 当前依赖中尚未包含 `trafilatura`；Phase 2 需要新增 `trafilatura>=2.0.0`。
- 阶段 28 设计文档已明确不新增数据库表管理 crawl 状态，批处理状态放在 `data/crawl/crawl_results.csv`，长期来源治理放在现有 `sources` 表。

## Phase 2 爬虫核心模块发现

- `WebFetcher` 使用 `urllib.request` 和 `urllib.robotparser`，避免新增 HTTP 客户端依赖；构造时强制 `delay_seconds >= 2.0`，并拒绝 `Mozilla/Chrome` 这类浏览器伪装 User-Agent。
- `WebFetcher` 在 robots.txt 禁止时返回 `skipped_robots`，不会继续发起页面请求。
- `WebContentExtractor` 将 `trafilatura` 放在运行时导入，便于测试用 fixture/mock 隔离真实依赖；实际环境仍通过 `pyproject.toml` 安装 `trafilatura>=2.0.0`。
- `CrawlUrlManager` 对 seed URL 去重，并把已 `imported`、`duplicate`、`skipped_robots`、`source_registered` 的记录视为不再 pending。
- `WebCrawlIngestionPipeline` 只编排 fetch/extract/write markdown/import/register；文档去重、clean、split 和 documents/chunks 写入仍由 `IngestionService.import_document()` 负责。
- Phase 2 测试均使用 fake HTTP、fake extractor、fake ingestion service 和本地 CSV，不依赖真实网络、真实网页或真实 API。

## Phase 3 CLI 与种子 URL 发现

- `scripts/crawl_and_ingest.py` 已提供 `--seed-csv`、`--output-dir`、`--results-csv`、`--delay`、`--max-urls`、`--rebuild-index`、`--dry-run` 参数。
- CLI 中 `--delay` 小于 2 秒会直接退出，避免绕过阶段 28 默认限速边界。
- CLI 的 `--rebuild-index` 显式使用 deterministic embedding provider，避免本地 `.env` 中真实 provider 影响普通批处理或测试。
- `data/crawl/seed_urls.csv` 当前共 100 条 URL，百科词条、高校机构、工程案例、开放论文、行业标准各 20 条，无重复 URL。
- 重要数量风险：当前核心设计是一条 seed URL 最多入库一个网页文档，因此 100 条 seed 最多新增 100 个文档；这与“新增 >=150 个文档”的目标存在天然张力。Phase 4 必须用合规、可解释的方式处理该差距，例如先跑实际成功率与当前 document 基线，再决定是否需要用户确认扩展 seed 规模或增加受控链接发现能力，不能为凑数拆分同一网页伪造多个文档。

## Phase 4 批量爬取与入库发现

- 批量开始前数据库基线为 documents 465、chunks 8918、sources 125、chunk_embeddings 17836；完成后为 documents 625、chunks 10543、sources 242、chunk_embeddings 17836。
- 文档净新增 160 个，总量 625，满足“新增 >=150”和“总文档数 600+”两个数量目标。
- 初始 100 条 seed 中 Wikipedia、部分开放论文站点和部分标准/政务页面大量返回 `skipped_robots`、`fetch_failed` 或 `extract_failed`；这验证了 robots.txt 和失败状态跟踪有效，也说明不能把爬虫成功率假设为 100%。
- `urllib` 页面读取会在慢站点出现 bare `TimeoutError` / `socket.timeout`，已扩展 `WebFetcher` 捕获范围并补充测试，避免长批次因单个慢站中断。
- 为解决 100 seed 与 150+ 新增文档目标之间的数量差距，已加入显式受控同站发现：默认关闭，仅 `--discover-links` 启用；只保留同 host HTTP(S) 链接，去 fragment，过滤 PDF/图片/压缩包/脚本样式等静态资源，并用 `--max-discovered-per-page` 限制扩展规模。
- 受控发现主要从已成功的清华、工程院、科研机构公开 HTML 页面补充相关页面；重复页面由 `content_hash` 标记为 `duplicate`，没有拆分网页伪造文档数量。
- `data/crawl/crawl_results_targeted_rfc.csv` 记录 44 条 targeted RFC URL，其中 imported 23、skipped_robots 2、fetch_failed 19。
- `data/crawl/crawl_results_targeted_rfc_discovery.csv` 记录 90 条，其中 imported 20、duplicate 39、skipped_robots 2、fetch_failed 21、extract_failed 8。
- `chunk_embeddings` 尚未随新增 chunks 自动增加，索引重建应在 Phase 5 显式执行并验证。

## Phase 5 端到端验证发现

- deterministic 向量索引重建只新增处理阶段 28 新 chunks：total=10543、indexed=1625、updated=0、skipped=8918；重建后 `chunk_embeddings` 达到 19461。
- API smoke 显示 `/health`、`/search`、`/search/hybrid` 均可用；检索 smoke 能返回 RFC 相关结果。
- 全量测试首次失败的主因不是爬虫改动，而是本地 `.env` 中真实 Jina reranking 配置进入 pytest，导致测试误触发外部 API。新增 `tests/conftest.py` 后，pytest 强制 deterministic reranking，受影响子集 64 passed，全量 533 passed。
- Docker build 已验证到 Docker Hub 访问层失败：BuildKit 拉 token 超时，legacy builder 拉 manifest EOF；本地无 `python:3.11-slim` 缓存，因此未进入项目 `pip install .` 步骤。该项记录为人工核验联网环境复测，不判定为项目代码失败。
- 本地虚拟环境已安装 `trafilatura 2.1.0`，说明阶段 28 Python 依赖在本地开发环境可解析。

## 用户追加 to1000 批量爬取发现

- 用户追加要求运行本地爬取程序将资料扩充到 1000 篇；已使用 `scripts/crawl_and_ingest.py --quiet` 分批执行，网页正文未进入大模型上下文。
- to1000 批次后数据库计数为 documents 1059、chunks 12103、sources 645；deterministic 索引重建后 chunk_embeddings 21021。
- `crawl_results_to1000_batch1.csv`：imported 38、duplicate 77、fetch_failed 28、skipped_robots 4、extract_failed 33。
- `crawl_results_to1000_batch2.csv`：imported 50、duplicate 121、fetch_failed 24、extract_failed 60。
- `crawl_results_to1000_batch3.csv`：imported 2、duplicate 164、fetch_failed 28、extract_failed 59，说明该发现链路基本耗尽。
- Engineering 文章 seed 批次全部 HTTP 405 fetch_failed；未尝试伪装浏览器或绕过站点限制，保留为失败记录。
- `tsinghua_news_article_seed_urls.csv` 批次 imported 344、extract_failed 6，是达到 1000 篇的主要增量来源；相关性比 targeted RFC seed 更宽，需用户人工核验时筛选保留范围。

## Phase 6 文档与 Obsidian 收尾发现

- `README.md` 顶部已切到阶段 28，新增“网页爬取与自动入库”本地运行命令，强调真实批量爬取由本地程序自行执行，不需要大模型逐页读取网页内容。
- `docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD` 已同步阶段 28 状态、架构、安全边界、数据边界和后续 Agent 协作规则。
- `docs/phase_reviews/phase-28.md` 是待人工核验草稿，不冒充最终 PASS；提交/tag/push 仍需用户明确授权。
- Obsidian 已新增阶段页、统一汇报页和知识点页；按用户要求未在开发过程中逐小 Phase 写入，阶段收尾时统一补齐。

## Phase 7 人工核验与质量筛选发现

- `web_page` 文档共 594 条，其中 source linked 540、unlinked 54。
- 关键词启发式相关性分布：strong 45、medium 4、weak 87、low 458。
- 自动筛选建议：keep_candidate 45、review_candidate 91、drop_candidate 458。
- 最大来源域名是 `www.tsinghua.edu.cn`，共 392 条，其中 low 365；这是冲到 1000 篇的主要来源，也是不相关风险最大的来源。
- 当前只生成质量审查报告和候选 CSV，不删除数据库内容；删除前需要用户人工确认，删除后必须重建 deterministic 索引。

## Phase 8-11 规划决策

### 为什么必须先清理再提交

- 458 个 drop_candidate 会严重稀释检索质量：用户搜"堆石混凝土"时，大量不相关的清华泛新闻和导航页会挤进 top-k 结果。
- SQLAlchemy cascade 设计支持安全删除：删除 Document 会自动级联删除 Chunks 和 ChunkEmbeddings，Sources 的 document_id 会 SET NULL。
- 清理后数据库约 601 文档，全部是有实际内容的相关文档。

### 为什么用 Wikipedia REST API 替代直接爬取

- Wikipedia robots.txt 禁止通用爬虫，原 seed 中 40 条 Wikipedia URL 全部 skipped_robots。
- Wikipedia 提供官方 REST API（`/api/rest_v1/page/html/{title}`），无需 API key，合规使用。
- 中英文 Wikipedia 分别用 `en.wikipedia.org` 和 `zh.wikipedia.org` 的 API。
- 百科知识补充对概念类问答（"堆石混凝土是什么""自密实混凝土原理"）至关重要。

### 为什么不爬百度百科

- 百度百科 JavaScript 渲染重，trafilatura 提取质量差（导航栏、推荐列表混入正文）。
- 百度有 IP 频率限制和验证码，反爬严格。
- 投入产出比不如 Wikipedia API + 公开标准 PDF。

### 标准文档入库策略

- 标准文档（GB/T、SL）大部分是 PDF 格式，不走网页爬虫管线。
- 项目已有 PDF 入库管线（`parser.py` 支持 `.pdf`，`IngestionService.import_document()` 可接受 PDF）。
- 只获取公开免费文档，不绕付费墙。
- 来源类型标记为 `standard_document`，与 `web_page` 区分。
## Phase 8 低质量语料清理发现

- `stage28_crawl_quality_drop_candidates.csv` 中 458 个候选全部仍存在于数据库，且全部为 `source_type="web_page"`，没有误包含本地 PDF、题录或深度全文文档。
- 458 个 drop_candidate 对应 1471 个 chunks 和 1471 条 deterministic chunk_embeddings；清理后 documents 从 1059 降到 601，符合预期。
- `sources` 表中只有 421 条记录关联到这 458 个文档，说明 Phase 4/7 中仍存在一部分 `web_page` document 没有关联 source 的情况；清理脚本按实际关联数断开 `document_id`，不伪造 source。
- Stage 28 的实际落盘路径有两层：`pipeline.py` 先写 `data/raw/web_crawl/web_*.md`，`IngestionService.import_document()` 再复制到统一 `data/raw/<content_hash>.md` 并把后者写入 `documents.raw_path`。因此安全清理必须同时处理 `Document.raw_path` 和 `Source.local_path`。
- 清理脚本把删除边界限制在 `data/raw` 下的 `.md` 文件，拒绝删除 raw root 之外路径或非 Markdown 文件；这比直接按字符串删除 `data/raw/web_crawl/*.md` 更贴合当前数据库事实。
- SQLAlchemy ORM 删除 `Document` 能按 relationship cascade 删除 chunks 和 chunk_embeddings；为了不依赖 SQLite `ON DELETE SET NULL` 是否启用，脚本显式把关联 `Source.document_id` 置空后再删除文档。
- 清理后 deterministic 索引重建显示 total=10632, indexed=0, updated=0, skipped=10632，说明剩余 chunk 均已有当前 deterministic embedding，无漏索引。
## Phase 9 Wikipedia API 百科补充发现

- 普通网页爬虫被 Wikipedia robots.txt 拦截后，官方 REST API 是更合规的入口；实现使用用户指定的 `/api/rest_v1/page/html/{title}`，不需要 API key，也不伪装浏览器。
- Wikipedia API 在当前本地网络环境下存在连接重置，单次运行只导入 11/38；加入网络错误有限重试后，第二轮额外导入 14 篇，累计 `wikipedia` documents 达到 25。
- HTTP 404 不重试，因为这通常表示条目标题在对应语言站点不存在或 REST title 不匹配；结果 CSV 如实保留失败条目，方便后续人工替换标题。
- `extract_failed=2` 表示 API 返回了 HTML 但 trafilatura 提取正文过短；这类条目不强行入库，避免百科导航页或消歧义页污染语料。
- `SourceRegistryService` 可能因为 URL/title 归一化把部分 Wikipedia source 合并，因此 `wikipedia_documents=25` 而 `wikipedia_sources=19`；文档自身 `source_type="wikipedia"` 已满足检索侧来源标记。
- Wikipedia 批次同样只保存提取后的 Markdown 和结果 CSV，不保存原始 HTML；CSV 只记录 title、status、URL、document/source id 和错误摘要。
- 新增 489 个 Wikipedia chunks 后 deterministic 索引重建成功，`chunk_embeddings` 与清理后的旧 chunk 加新 chunk 保持一致。
## Phase 10 公开标准 PDF 补充发现

- USACE/USBR/FEMA 等官方公开 PDF URL 即使公开，也可能在当前本地网络环境下返回 403、TLS EOF 或连接重置；脚本必须把这些作为可审计失败记录，而不是伪装浏览器或绕过限制。
- `--max-mb 20` 边界生效：USBR Design of Small Dams 和 FEMA P-679 因超过 20MB 被跳过，没有下载完整大文件。
- FEMA 官方站点的中小型 dam safety 指南最稳定，最终累计导入 9 篇 `standard_document`，覆盖 emergency action planning、earthquake analysis、inflow design flood、dam incident planning、dam awareness、inundation mapping 等主题。
- PDF 入库继续复用 `IngestionService.import_document()` 和现有 pypdf 解析/结构化逻辑；标准脚本只负责下载、大小限制、结果记录和来源注册。
- 标准文档下载脚本对网络错误做有限重试，但对 HTTP 403 和超限大文件不重试；这符合“不绕登录/付费墙/站点限制”的边界。
- 标准 PDF 结果 CSV 只保存 URL、状态、字节数、local_path、document/source id 和错误摘要，不保存供应商敏感响应或受限全文。

## Phase 11 最终验证与文档同步发现

- 清理后质量复核显示 `suggested_drop_candidate=0`，说明 Phase 8 的 458 个 drop_candidate 已从数据库和 raw Markdown 中移除。
- 清理后仍有 91 个 `review_candidate`，这些不是自动删除对象，而是用户人工核验入口；主要风险仍集中在高校新闻、机构介绍、目录页和 DOI 跳转页。
- 最终语料组成从 to1000 的 1059 个 documents 收敛为 635 个 documents：136 个 `web_page`、25 个 `wikipedia`、9 个 `standard_document`，其余为历史阶段的本地 PDF/题录/元数据语料。
- `chunk_embeddings=21634` 高于 `chunks=12716`，这是历史阶段保留多批 embedding/provider 记录造成的现象；本阶段已用 deterministic provider 完成当前索引重建。
- `standards_urls.csv` 中 FEMA Inflow Design Floods URL 文件名为 P-94，标题已从 P-93 修正为 P-94，避免后续人工核验误判。
- 普通文档与 Obsidian 已同步到“阶段 28 Phase 0-11 完成，等待人工核验”状态；仍不得提交、打 tag、push 或创建 PR。
