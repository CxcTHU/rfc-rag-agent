# 阶段 28 爬取质量审查报告

## 结论

阶段 28 Phase 8 已按人工筛选候选清理低质量网页语料，随后 Phase 9-10 补充 Wikipedia 百科条目和公开标准 PDF。清理后重新抽样显示，原 `drop_candidate` 已归零；仍保留的 `weak` 与 `review_candidate` 主要来自高校新闻、机构介绍页、标准目录页和 DOI 跳转页，需要用户人工核验后再决定是否继续收紧。

当前状态：等待用户人工核验，尚未提交、打 tag、push 或创建 PR。

## 清理后统计

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

## 网页质量分布

```text
web_page_documents 136
source_linked_documents 119
unlinked_documents 17
relevance_strong 45
relevance_medium 4
relevance_weak 87
relevance_low 0
suggested_keep_candidate 45
suggested_review_candidate 91
suggested_drop_candidate 0
```

## 清理动作

- 输入候选：`data/evaluation/stage28_crawl_quality_drop_candidates.csv` 中 458 个 `document_id`。
- 删除范围：仅删除 `source_type="web_page"` 的低质量 documents。
- 级联影响：SQLAlchemy cascade 删除关联 chunks 与 chunk_embeddings；关联 sources 的 `document_id` 置空。
- 原文清理：同步删除 `data/raw/web_crawl/` 下由 `Document.raw_path` 或 `Source.local_path` 指向的 `.md` 文件。
- 清理后索引：已执行 `python scripts/build_vector_index.py --provider deterministic --batch-size 64`。

清理前后：

```text
before:
  documents 1059
  chunks 12103
  chunk_embeddings 21021
  sources 645

after cleanup:
  documents 601
  chunks 10632
  chunk_embeddings 19550
  sources 645
```

## 补充语料

- Wikipedia：`data/crawl/wikipedia_articles.csv` 38 条候选，成功入库 25 个 `source_type="wikipedia"` 文档。
- 公开标准 PDF：`data/crawl/standards_urls.csv` 15 条候选，成功入库 9 个 `source_type="standard_document"` 文档；超过 20MB 或远端拒绝下载的文档跳过。

## 人工核验建议

- 优先核验 `stage28_crawl_quality_manual_review_candidates.csv` 中的 91 个 review 候选。
- 对 `www.tsinghua.edu.cn`、`www.civil.tsinghua.edu.cn`、`doi.org` 相关页面重点判断：保留学术/工程技术页，删除泛新闻、组织简介、目录页。
- 对 Wikipedia 文档只作为百科背景使用，不作为工程设计规范的强证据。
- 对公开标准 PDF 优先核验标题、URL、下载权限和是否确为公开资料。
- 人工核验通过前不要提交、打 tag 或推送。

## 输出文件

- `data/evaluation/stage28_crawl_quality_review_sample.csv`
- `data/evaluation/stage28_crawl_quality_documents.csv`
- `data/evaluation/stage28_crawl_quality_keep_candidates.csv`
- `data/evaluation/stage28_crawl_quality_manual_review_candidates.csv`
- `data/evaluation/stage28_crawl_quality_drop_candidates.csv`
- `data/evaluation/stage28_crawl_quality_domains.csv`
- `data/evaluation/stage28_crawl_quality_summary.csv`

## 验证

```text
python scripts/review_stage28_crawl_quality.py --sample-size 80
python scripts/build_vector_index.py --provider deterministic --batch-size 64
python -m pytest -q
```

最近一次全量测试结果：`544 passed, 1 warning`。
