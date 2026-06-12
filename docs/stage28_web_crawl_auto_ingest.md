# 阶段 28：网页爬取 + 自动入库管线

## 目标

阶段 28 在阶段 27「Chainlit 前端 + Docker 容器化 + GitHub Actions CI」已经提交、打 `phase-27-complete` tag 并合并到 `main` 的基础上推进。目标是新增一条合规、可复跑、可测试的网页采集入口，把公开网页内容自动提取为 Markdown，再复用现有入库、清洗、切分、来源注册和索引重建能力，扩充堆石混凝土领域语料。

核心链路：

```text
data/crawl/seed_urls.csv
-> CrawlUrlManager
-> WebFetcher（HTTP + robots.txt + 限速）
-> WebContentExtractor（trafilatura 正文提取）
-> WebCrawlIngestionPipeline
-> data/raw/web_*.md
-> IngestionService.import_document()
-> SourceRegistryService.register_candidate()
-> VectorIndexService.build_index()
-> documents / chunks / sources / chunk_embeddings
```

阶段完成后停在用户人工核验前，不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。

## 阶段起点

阶段 27 已完成：

```text
phase-27-complete -> 79f612e Complete phase 27 chainlit docker ci
main merge commit -> 800b39a Merge phase 27 chainlit docker ci
baseline tests -> 520 passed
```

阶段 28 分支：

```text
codex/phase-28-web-crawl-auto-ingest
```

本阶段不移动任何已有阶段 tag。

## 模块设计

新增目录：

```text
app/services/crawling/
  __init__.py
  fetcher.py
  extractor.py
  url_manager.py
  pipeline.py
```

### fetcher.py

`WebFetcher` 只负责网页获取，不做正文提取、不写数据库。

职责：

- 使用明确的 User-Agent，例如 `RFC-RAG-Agent/0.1 (+research corpus builder; contact: local)`。
- 读取并遵守 robots.txt；robots.txt 禁止的 URL 标记为 skipped。
- 默认请求间隔不小于 2 秒。
- 设置合理 timeout 和有限重试。
- 只发送普通 HTTP GET，不保存 cookie，不绕登录、验证码、付费墙，不伪装浏览器。
- 返回结构化结果：`url`、`status_code`、`content_type`、`html`、`fetched_at`、`error`。

### extractor.py

`WebContentExtractor` 只负责把 HTML 提取为 Markdown 正文。

职责：

- 使用 `trafilatura>=2.0.0` 提取正文。
- 输出 Markdown，尽量保留标题层级，方便现有 `split_text()` 继续识别 `heading_path`。
- 提取标题、作者、发布时间、站点描述等可用元数据。
- 对正文长度做最小门槛检查，过短内容标记为 extraction_failed。
- 不长期保存原始 HTML。

### url_manager.py

`CrawlUrlManager` 负责种子 URL 和结果状态文件。

种子文件：

```text
data/crawl/seed_urls.csv
```

最小字段：

```text
url,category,trust_level,notes
```

结果文件：

```text
data/crawl/crawl_results.csv
```

建议字段：

```text
url,category,trust_level,status,http_status,title,document_id,source_id,content_hash,fetched_at,error
```

状态枚举：

```text
pending
fetched
imported
duplicate
skipped_robots
fetch_failed
extract_failed
ingest_failed
source_registered
```

URL 管理只维护批处理状态，不新增数据库表。入库成功后的长期来源治理继续交给 `sources` 表。

### pipeline.py

`WebCrawlIngestionPipeline` 编排完整流程，但不复制已有入库逻辑。

流程：

```text
read seed urls
-> skip duplicate URL / already imported result
-> fetch HTML
-> extract Markdown + metadata
-> write temporary Markdown file
-> IngestionService.import_document(
     file_path=markdown_path,
     title=metadata.title,
     source_path=url,
     file_name=generated_name,
     source_type="web_page",
   )
-> SourceRegistryService.register_candidate(candidate, document_id=...)
-> update crawl_results.csv
```

`IngestionService.import_document()` 已负责：

- 读取 Markdown/TXT/PDF 等本地文件。
- `store_raw_file()` 保存可复跑 raw 文件。
- content_hash 去重。
- `clean_text()` 文本清洗。
- `split_text()` 切分 chunk。
- `DocumentRepository.create_with_chunks()` 写入 `documents` 和 `chunks`。

因此阶段 28 不重复实现清洗、切分、文档去重和数据库写入。

## CLI 入口

新增：

```text
scripts/crawl_and_ingest.py
```

参数：

```text
--seed-csv data/crawl/seed_urls.csv
--output-dir data/raw/web_crawl
--results-csv data/crawl/crawl_results.csv
--delay 2.0
--max-urls 20
--rebuild-index
--dry-run
```

默认行为：

- 使用 deterministic provider 配置，不要求真实 API。
- 不自动绕过 robots.txt。
- 默认限速 2 秒。
- 默认保存提取后的 Markdown，不保存原始 HTML。
- `--rebuild-index` 显式触发 `VectorIndexService.build_index()`。

### 本地自行爬取操作

阶段 28 的爬取工作应由本地程序自行联网执行，不需要把网页正文交给大模型阅读。推荐用户在 PowerShell 中分批运行：

```powershell
cd G:\Codex\program\rfc-rag-agent
.\.venv\Scripts\python.exe -m pip install -e .
```

先 dry-run 检查 pending URL：

```powershell
.\.venv\Scripts\python.exe scripts\crawl_and_ingest.py `
  --seed-csv data\crawl\seed_urls.csv `
  --results-csv data\crawl\crawl_results.csv `
  --output-dir data\raw\web_crawl `
  --dry-run `
  --max-urls 5
```

再小批量正式爬取：

```powershell
.\.venv\Scripts\python.exe scripts\crawl_and_ingest.py `
  --seed-csv data\crawl\seed_urls.csv `
  --results-csv data\crawl\crawl_results.csv `
  --output-dir data\raw\web_crawl `
  --max-urls 50 `
  --timeout 8 `
  --quiet
```

如果需要从成功页面补充同站公开链接，可显式开启受控发现：

```powershell
.\.venv\Scripts\python.exe scripts\crawl_and_ingest.py `
  --seed-csv data\crawl\seed_urls.csv `
  --results-csv data\crawl\crawl_results_discovery.csv `
  --output-dir data\raw\web_crawl `
  --max-urls 150 `
  --timeout 8 `
  --discover-links `
  --max-discovered-per-page 3 `
  --quiet
```

爬取完成后重建 deterministic 向量索引：

```powershell
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider deterministic --batch-size 64
```

`--quiet` 用于本地长批量运行，只输出最终汇总，避免逐 URL 日志刷屏。真实批量爬取不应依赖大模型上下文；大模型只负责写程序、解释用法、审查结果摘要。

## 种子 URL 范围

`data/crawl/seed_urls.csv` 包含 80-120 条 URL，覆盖 5 类：

| 分类 | 目标数量 | 可信度 | 示例来源 |
| --- | --- | --- | --- |
| 百科词条 | 15-25 | medium/high | Wikipedia、百度百科、工程百科公开词条 |
| 高校/机构 | 15-25 | high | 清华、河海、科研院所公开页面 |
| 工程案例 | 15-25 | medium/high | 水利工程公开报道、项目介绍 |
| 开放论文 | 15-25 | high | MDPI、Engineering、DOAJ、期刊开放页面 |
| 行业标准 | 15-25 | high | 水利部、行业协会、标准目录公开页 |

种子 URL 只记录公开可访问页面，不记录登录后页面、付费全文页、验证码页或机构受限页面。

## 来源注册

网页入库后注册到现有 `sources` 表。候选来源字段建议：

```text
source_id: crawl_<hash>
title: extractor metadata title or URL fallback
url: original URL
source_type: web_page
trust_level: seed trust_level
fulltext_permission: open_access 或 unknown
status: imported / duplicate / rejected
local_path: extracted Markdown path
document_id: import result document_id
notes: seed notes + crawl metadata
```

`SourceRegistryService.register_candidate()` 会继续复用 DOI、URL、标题归一化去重边界，避免爬虫绕开已有来源治理。

## 索引重建

阶段 28 新增文档后，向量索引通过现有能力重建：

```text
VectorIndexService(db, embedding_provider).build_index()
```

默认使用 deterministic embedding provider，保证本地测试和 CI 不依赖真实 API。真实 Jina/MIMO 只能作为人工发布前校准，不能成为全量测试前提。

## 安全与合规边界

- 遵守 robots.txt。
- 默认请求间隔 ≥ 2 秒。
- User-Agent 标识项目身份，不伪装浏览器。
- 不绕登录、验证码、付费墙、机构授权墙。
- 不抓取或保存受限全文。
- 不保存 cookie、session、Authorization header、Bearer token 或任何用户凭据。
- 不把 API key、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 不长期保存原始 HTML；只保存正文提取后的 Markdown。
- `crawl_results.csv` 只保存状态、标题、URL、错误摘要和 document/source 标识，不保存网页正文。
- CI 和本地全量测试使用 mock/fake HTTP 或本地 fixture，不依赖真实网络。

## 测试方案

新增测试建议：

```text
tests/test_crawling_fetcher.py
tests/test_crawling_extractor.py
tests/test_crawling_url_manager.py
tests/test_crawling_pipeline.py
tests/test_crawl_and_ingest_cli.py
```

重点覆盖：

- robots.txt allow/disallow 判定。
- 默认限速配置不小于 2 秒。
- User-Agent 不为空且不伪装浏览器。
- HTML fixture 可以提取出 Markdown 正文和标题。
- 短正文或空正文会被标记为 extract_failed。
- seed CSV 读取、去重、状态写回稳定。
- pipeline 调用 `IngestionService.import_document()`，而不是重复写 documents/chunks。
- duplicate 文档不会重复入库。
- CLI 参数解析和 dry-run 不触发真实 HTTP。

## 批量执行验收

阶段目标：

```text
新增 >= 150 个文档
总 documents >= 600
crawl_results.csv 有完整成功/失败/跳过记录
新增网页内容可被 keyword / hybrid / agent 问答链路检索
```

批量执行后抽查：

- 每个分类至少抽查 3 条成功入库文档。
- 检查标题、source_path、source_type、chunk_count。
- 检查 `sources` 表中 URL 与 document_id 关联。
- 针对新增网页内容运行检索 smoke。

## 文档收尾

阶段完成时同步：

```text
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
AGENT.MD
docs/phase_reviews/phase-28.md
obsidian-vault/
```

本阶段开发过程中暂不写 Obsidian 小 Phase 汇报；全部开发完成后统一补齐。

## 新词解释与面试表达

- **robots.txt**：网站放在根路径的爬虫访问规则文件。本项目用它判断某个 URL 是否允许抓取，避免越界访问。
- **User-Agent**：HTTP 请求头里标识访问者身份的字符串。本项目必须写明自己是 RFC-RAG-Agent，而不是伪装成浏览器。
- **trafilatura**：网页正文提取库，用来从 HTML 中去掉导航、广告、页脚，只保留正文和标题等元数据。
- **CLI**：命令行入口。本阶段的 `scripts/crawl_and_ingest.py` 让用户不用写代码也能执行批量爬取和入库。

面试表达：

```text
阶段 28 我没有把爬虫做成一个绕过网站限制的大规模抓取系统，而是把它设计成 RAG 数据采集层的受控入口。它从人工维护的种子 URL 出发，先遵守 robots.txt 和限速规则抓取公开页面，再用 trafilatura 提取正文，最后复用已有 IngestionService 完成清洗、切分、去重和入库。这样做的好处是新增采集能力不会破坏原有 RAG 主链路，来源仍进入 source registry 治理，测试也可以用本地 fixture 隔离真实网络和真实 API。
```
