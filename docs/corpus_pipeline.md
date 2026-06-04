# 语料库扩容管道

本文件记录阶段 1 后续扩容资料库的自动化方式，目标是减少手动下载，形成可重复运行的来源管道。

## 管道总览

```text
学术 API / Zotero / 本地 PDF
-> 候选来源清单
-> 开放全文 PDF 下载
-> 来源登记与分类
-> PDF 文字抽取
-> chunk 切分
-> SQLite 入库
-> 关键词检索校准
```

## 新词解释

- `metadata-first`：先批量收集题名、作者、年份、DOI、摘要、来源链接和 PDF 链接，再决定哪些资料可以导入全文。
- `OA`：Open Access，开放获取。通常可以合法访问全文，但仍要记录许可条件。
- `connector`：连接器。把 Zotero、网盘、企业文档库或学术 API 接到本项目。
- `ETL`：Extract、Transform、Load，即提取资料、清洗转换、导入系统。
- `去重`：同一篇论文可能被 OpenAlex、Semantic Scholar、Crossref 同时发现，导入前要按 DOI 或题名合并。

## 脚本

### 1. 批量发现开放全文候选

```powershell
.\.venv\Scripts\python.exe scripts\collect_sources.py `
  --query "rock-filled concrete" `
  --query "rock-filled concrete dam" `
  --query "self-compacting concrete rock-filled concrete" `
  --limit 20 `
  --download `
  --max-downloads 30
```

输出：

```text
data/source_candidates.csv
data/fulltext/open_access_auto/
```

数据来源：

- OpenAlex
- Semantic Scholar
- Crossref
- Unpaywall（需要设置 `UNPAYWALL_EMAIL`）

可选环境变量：

```powershell
$env:OPENALEX_MAILTO="your_email@example.com"
$env:UNPAYWALL_EMAIL="your_email@example.com"
```

### 2. 导入本地 PDF / manifest PDF

```powershell
.\.venv\Scripts\python.exe scripts\import_fulltext.py `
  --manifest data\fulltext_manifest.csv `
  --manifest data\source_candidates.csv `
  --scan-dir data\fulltext\open_access_auto
```

作用：

- 读取 manifest 中已有 `local_path` 的 PDF。
- 扫描目录中的 PDF。
- 通过文件 hash 自动去重。
- 调用现有 ingestion service 入库。

### 3. 导入 Zotero 附件 PDF

```powershell
.\.venv\Scripts\python.exe scripts\import_zotero.py --query "rock-filled concrete"
```

前置条件：

- 已安装并启动 Zotero Desktop。
- Zotero 本地 API 可用：`http://127.0.0.1:23119`。
- 论文条目下有 PDF 附件。

当前状态：

- 本机尚未发现 Zotero 配置文件，脚本会提示先启动 Zotero。
- Zotero 可用后，该脚本只读取本地库和附件，不写入 Zotero。

## 当前运行反馈

### 2026-06-04 初次测试

```text
SSL: UNEXPECTED_EOF_WHILE_READING
```

判断：

- API 管道代码已落地，但当前网络环境到这些 API 的 HTTPS 连接被中断。
- 这不是某一个 API 不可用，而是本机网络或代理层问题。

处理方式：

- 配置系统代理或设置 `HTTPS_PROXY` / `HTTP_PROXY` 后重试。
- 换到能稳定访问这些学术 API 的网络。
- 先使用已有开放 PDF、CNKI 机构访问 PDF、Zotero 附件 PDF 扩容。

### 2026-06-04 后续测试

第二次运行 `collect_sources.py` 时，OpenAlex 和 Crossref 已成功返回候选，Semantic Scholar 返回 `HTTP 429`。

```text
候选记录：40
包含 PDF URL：4
成功下载：0
下载失败：4
```

下载失败原因：

- MDPI `/pdf` 链接返回 403；该类链接可改用出版方静态 `mdpi-res.com` PDF 地址。
- Springer 部分链接返回 HTML 页面，不是可直接下载 PDF，可能属于书籍或受限资源。
- EasyChair 预印本链接返回 404。

候选质量问题：

- API 查询会混入相邻主题，例如 `concrete-faced rock-fill dam` 属于混凝土面板堆石坝，不等同于本项目的 `rock-filled concrete / 堆石混凝土`。
- 后续需要增加 RFC 相关性过滤，避免语料库变大但主题变脏。

Zotero 状态：

- 当前本机未发现 Zotero 配置文件，本地 API `http://127.0.0.1:23119` 不可用。
- 启动 Zotero Desktop 并启用本地 API 后，可重新运行 `scripts/import_zotero.py`。

## 设计原则

- 自动下载只针对开放获取或明确可访问的 PDF。
- CNKI、ScienceDirect 等机构访问资料只做本地私有导入，不公开再分发全文。
- 不绕过验证码、登录限制、付费墙或网站反爬。
- 不把 `data/fulltext/` 提交到 GitHub。
- 所有来源都要记录标题、作者、年份、URL、PDF URL、访问权限、许可和分类。

## 后续优化

- 增加代理配置检测。
- 将 source candidates 导入 `sources` 表，而不只保存 CSV。
- 增加批量 DOI -> Unpaywall 开放全文查找。
- 增加 Zotero collection 筛选。
- 增加 PDF 清洗规则，处理特殊符号、页眉页脚、参考文献噪声。

## 2026-06-04 题录优先语料库管道

用户调整方向：当前不再优先下载论文全文，而是先批量获取题名、作者、年份、期刊、摘要、关键词、DOI 和来源链接等公开题录信息，形成更大的可检索语料库。

新词解释：
- `题录`：一篇论文的基本登记信息，例如题名、作者、期刊、年份、摘要、关键词和 DOI。它不是论文全文，但足以用于早期检索、综述线索发现和来源筛选。
- `metadata corpus`：元数据语料库。这里指由论文题录和摘要组成的轻量知识库，每条记录会生成一个 Markdown 卡片并导入 `documents/chunks`。
- `JSONL`：一行一个 JSON 对象的文本格式，适合存放大量题录记录，后续可以逐行读取、追加和排查。

新增脚本：

```powershell
.\.venv\Scripts\python.exe scripts\collect_metadata_corpus.py `
  --skip-semantic-scholar `
  --query "rock-filled concrete" `
  --query "rock filled concrete" `
  --query "rock-fill concrete dam" `
  --query "self-compacting rock-filled concrete" `
  --query "self-compacting concrete prepacked rock" `
  --query "堆石混凝土" `
  --query "自密实堆石混凝土" `
  --query "金峰 堆石混凝土" `
  --limit 100 `
  --max-records 300 `
  --import-to-db
```

输出文件：
- `data/metadata/rfc_papers_metadata.csv`
- `data/metadata/rfc_papers_metadata.jsonl`
- `data/imports/metadata_corpus/*.md`

本轮结果：
- OpenAlex + Crossref 共返回 562 条原始候选。
- RFC 相关性过滤后保留 116 条题录。
- 其中 69 条包含公开摘要。
- 生成 116 个 Markdown 题录卡片。
- SQLite 当前包含 136 篇 documents、997 个 chunks。
- 其中 `metadata_record` 类型文档 115 篇；有 1 个题名对应两个 DOI，本轮按题名避免重复刷屏，因此数据库中只保留一个可检索题录文档。

Google Scholar / CNKI 处理原则：
- Google Scholar 没有官方公开批量 API，直接网页爬取容易触发验证码，也不稳定；当前不作为自动主链路。
- CNKI 有机构账号访问权限，但全文和批量页面抓取仍应遵守授权边界；当前优先支持 CNKI 导出的 CSV/RIS/EndNote 题录文件导入。
- `scripts/collect_metadata_corpus.py --import-export path` 可把 CNKI、Google Scholar 辅助工具、Zotero、EndNote 或 Publish or Perish 导出的题录文件合并到同一套语料库。

面试表达：

```text
我没有把学术网站页面抓取作为第一选择，而是先建立 metadata-first 管道。原因是题录和摘要的公开元数据更容易批量获取、去重、分类和追踪来源，也能快速扩大检索覆盖面。对 Google Scholar 和 CNKI 这类有登录、验证码或授权边界的网站，我把它们作为导出文件入口，而不是在系统里硬爬页面。这样系统更稳定，也更容易解释数据来源和合规边界。
```
