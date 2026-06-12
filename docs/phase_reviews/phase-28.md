# 阶段 28 验收草稿：网页爬取 + 自动入库管线

## 验收结论

状态：PASS，已获用户授权提交合并。

阶段 28 的 Phase 0-11 已完成开发、测试、普通文档和 Obsidian 草稿收尾。用户已明确要求提交阶段 28 整体开发工作并上传 merge 至 GitHub；本报告作为阶段最终功能提交、`phase-28-complete` tag 和合并到 `main` 前的验收记录。

## 范围核对

| 要求 | 证据 | 结论 |
| --- | --- | --- |
| 从阶段 27 合并后的 main 出发 | `main -> 800b39a Merge phase 27 chainlit docker ci`；`phase-27-complete -> 79f612e`；阶段 27 已合并到 main | 已满足 |
| 不移动已有阶段 tag | 本阶段未执行 tag 移动命令 | 已满足 |
| Phase 0-7 网页爬取管线 | `app/services/crawling/`、`scripts/crawl_and_ingest.py`、`data/crawl/seed_urls.csv`、`docs/stage28_web_crawl_auto_ingest.md` | 已满足 |
| Phase 8 低质量清理 | `scripts/cleanup_drop_candidates.py` 清理 458 个低质量 web_page 文档，documents 1059 -> 601 | 已满足 |
| Phase 9 Wikipedia 补充 | `app/services/crawling/wikipedia_fetcher.py`、`scripts/ingest_wikipedia.py`、`data/crawl/wikipedia_articles.csv`；入库 25 个 wikipedia 文档 | 已满足 |
| Phase 10 公开标准 PDF 补充 | `scripts/ingest_standards.py`、`data/crawl/standards_urls.csv`；入库 9 个 standard_document 文档 | 已满足 |
| Phase 11 最终验证与文档同步 | 质量报告、阶段 review、README、docs、AGENT、Obsidian 已同步 | 已满足 |
| 不让真实 API 成为测试前提 | 测试均使用 mock 或 deterministic provider；CI 不依赖外部 API | 已满足 |
| 安全边界 | 不写入 API key、Bearer token、供应商原始敏感响应或受限全文；爬取不绕登录/验证码/付费墙 | 已满足 |

## 最终数据计数

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

说明：`chunk_embeddings` 数量高于 `chunks` 是因为历史阶段保留了不同索引批次/配置下的 embedding 记录；本阶段已用 deterministic provider 完成当前索引重建。

## 关键验证命令

低质量清理：

```powershell
.\.venv\Scripts\python.exe scripts\cleanup_drop_candidates.py --dry-run
.\.venv\Scripts\python.exe scripts\cleanup_drop_candidates.py
```

索引重建：

```powershell
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider deterministic --batch-size 64
```

Wikipedia 离线测试与入库：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_wikipedia_fetcher.py -q
.\.venv\Scripts\python.exe scripts\ingest_wikipedia.py --quiet --rebuild-index
```

公开标准 PDF 离线测试与入库：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ingest_standards.py -q
.\.venv\Scripts\python.exe scripts\ingest_standards.py --quiet --rebuild-index
```

质量复核：

```powershell
.\.venv\Scripts\python.exe scripts\review_stage28_crawl_quality.py --sample-size 80
```

全量测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

最近一次结果：`544 passed, 1 warning`。

## 质量结论

- Phase 8 删除了 458 个低质量网页文档，清理后 `suggested_drop_candidate=0`。
- Phase 9 补充 Wikipedia 背景知识，用于解释概念、术语和工程类型，不作为规范性强证据。
- Phase 10 补充 FEMA 公开 dam safety PDF，作为比普通网页更稳定的公开标准/指南类语料；USACE/USBR 部分公开 PDF 在当前网络环境下被拒绝或超过 20MB，已按边界跳过。
- 清理后仍有 91 个 `review_candidate`，建议用户人工核验后再决定是否二次清理。

## 人工核验清单

- 检查 `data/evaluation/stage28_crawl_quality_manual_review_candidates.csv` 的 review 候选。
- 抽查 `data/raw/wikipedia/` 的百科正文是否只作背景知识。
- 抽查 `data/raw/standards/` 的公开 PDF 标题、URL、下载权限与文件大小。
- 确认 `scripts/cleanup_drop_candidates.py` 的删除范围只作用于 `web_page` 类型低质量语料。
- 当前用户已明确授权提交、创建阶段 tag、合并到 `main` 并推送 GitHub；合并完成后以 `phase-28-complete` 指向的提交作为阶段 28 最终功能提交。
