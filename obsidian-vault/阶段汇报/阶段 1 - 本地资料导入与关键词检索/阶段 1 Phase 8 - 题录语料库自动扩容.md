---
stage: "阶段 1"
phase: "Phase 8"
status: "已完成"
---

# 阶段 1 Phase 8 - 题录语料库自动扩容

所属阶段：[[阶段 1 - 本地资料导入与关键词检索]]
所属汇报索引：[[阶段 1 Phase 汇报索引]]

## 1. 本 Phase 目标

避免手动下载论文太慢，改用学术 API、Zotero、本地 PDF 和题录导出文件扩充资料库。

## 2. 本 Phase 完成的主要任务

- 新增 `app/services/source_collection.py`。
- 新增 `scripts/collect_sources.py`。
- 新增 `scripts/import_fulltext.py`。
- 新增 `scripts/import_zotero.py`。
- 新增 `scripts/collect_metadata_corpus.py`。
- 支持 OpenAlex、Crossref、Semantic Scholar 发现论文候选。
- 支持 CNKI、Google Scholar 辅助工具、EndNote、Zotero 或 Publish or Perish 导出的文件合并。
- 生成 `data/metadata/rfc_papers_metadata.csv`、JSONL 和 Markdown 题录卡片。
- 将题录卡片以 `metadata_record` 类型导入 SQLite。

## 3. 新增/修改了哪些内容

- 新增 `tests/test_source_collection.py`。
- 新增 `docs/corpus_pipeline.md`。
- 新增 `data/source_candidates.csv`。
- 新增 `data/metadata/rfc_papers_metadata.csv`。
- 新增 `data/metadata/rfc_papers_metadata.jsonl`。
- 新增 `data/imports/metadata_corpus/*.md`。

## 4. 关键代码或模块说明

- `SourceCandidate` 表示一个论文候选，包含题名、作者、年份、摘要、关键词、DOI、URL、PDF URL 等。
- `collect_metadata_corpus.py` 负责批量采集、去重、过滤、生成题录卡片并可导入数据库。
- 相关性过滤用于排除 `concrete-faced rock-fill dam` 等相邻但不等同于堆石混凝土的主题。

## 5. 遇到的问题与解决方式

问题：Semantic Scholar 未配置 API key 时容易返回 `HTTP 429`，Google Scholar 不适合直接硬爬。

解决方式：支持 `--skip-semantic-scholar`，主链路转为 OpenAlex + Crossref，并支持用户从学术工具导出题录后导入。

## 6. 新词解释

- 题录：论文的标题、作者、期刊、年份、摘要、DOI 等元数据。
- OpenAlex/Crossref/Semantic Scholar：开放学术数据来源，用来批量发现论文。
- metadata_record：只保存题录和摘要的资料记录，不一定包含全文。
- Zotero：文献管理工具，可保存论文条目和 PDF 附件。

## 7. 验证结果

- OpenAlex + Crossref 返回 562 条原始候选。
- RFC 相关性过滤后保留 116 条题录。
- 生成 116 个 Markdown 题录卡片。
- 当前 SQLite：136 documents、997 chunks。
- `python -m pytest tests\test_source_collection.py -q`：9 个测试通过。
- `python -m pytest`：36 个测试通过。

## 8. 当前遗留问题

- Semantic Scholar 需要 API key 或退避重试。
- Zotero 本地 API 当时不可用，需要先启动 Zotero Desktop。
- `metadata_record` 作为 Markdown 卡片进入 `documents/chunks` 是阶段 1 最小实现，后续阶段 4 更适合独立建 `sources` 表。

## 9. 下一 Phase 要做什么

进入 Phase 9，建立关键词检索评测集，校准中英文、同义词、标题加分和 metadata_record 来源均衡。

## 10. 面试表达

“我没有继续靠手工下载扩大资料库，而是建设 metadata-first 的语料扩容管道。先用 OpenAlex、Crossref 等开放学术 API 批量发现题录，再把摘要和元数据生成 Markdown 卡片导入检索库。这样能快速扩大覆盖面，同时避开未经授权批量下载全文的问题。”
