# 阶段 29 验收草稿：真实 Embedding 重建与质量闭环

## 验收结论

当前结论：`PASS`。阶段 29 的开发、测试、普通文档和 Obsidian 草稿已完成；真实质量门禁仍诚实保留 `review_required/medium` 的人工复核队列。用户已明确要求“提交阶段29的整体开发工作，并上传merge至github”，因此本验收草稿转为提交合并依据。

## 范围对齐

- 已从阶段 28 完成并合并后的 `main` 创建/切换到 `codex/phase-29-real-embedding-quality-eval`。
- 已核对 `phase-28-complete -> b345cd8 Complete phase 28 web crawl auto ingest`，且该 tag 是 `main -> 07dadf0 Merge phase 28 web crawl auto ingest` 的祖先。
- 未移动任何已有阶段 tag。
- 阶段 29 未引入写入型 Agent 工具、登录系统、部署优化、`torch` 或 `sentence-transformers`。

## 功能证据

- 新增 `scripts/cleanup_stale_embeddings.py`，支持 `--dry-run` 与 `--execute`。
- 历史 `chunk_embeddings` 已完成全量清理：`21634 -> 0`。
- 真实 Jina v3 embedding 已重建：`12716` 条 chunk 全部写入 `jina/jina-embeddings-v3/dim=1024`。
- deterministic embedding 已补建：`12716` 条 chunk 全部写入 `deterministic/hash-token-v1/dim=64`。
- 最终 `chunk_embeddings = 25432`，无孤立 embedding，无重复 provider/model/chunk 组合。
- 新增 `data/evaluation/stage29_new_corpus_queries.csv`，18 题覆盖 Wikipedia、公开标准、网页语料和拒答边界。
- 新增 `scripts/evaluate_stage29_real_quality.py`，输出真实评测逐题结果与汇总结果。
- 新增 `docs/stage29_quality_report.md`，并更新 `/quality-report`、`/quality-report/data.json`、`/quality-report/export.csv`。

## 评测指标

```text
precision_at_1 0.600
precision_at_3 0.867
precision_at_5 0.933
avg_coverage_ratio 0.664
refusal_accuracy 1.000
source_type_distribution institutional_access_pdf:17;metadata_record:6;open_access_pdf:5;standard_document:25;web_page:28;wikipedia:9
```

质量报告整体状态为 `review_required/medium`，主要因为仍有 1 条 Top-5 未命中和 2 条覆盖率偏低查询需要人工复核。

## 测试证据

阶段内已完成的聚焦测试：

```text
tests/test_cleanup_stale_embeddings.py: 4 passed
tests/test_embedding_provider.py + cleanup tests: 17 passed
tests/test_stage29_new_corpus_queries.py: 2 passed
tests/test_evaluate_stage29_real_quality.py: 3 passed
tests/test_build_stage29_quality_report.py + tests/test_frontend_app.py: 7 passed
```

阶段收尾最终全量测试：

```text
python -m pytest -q
556 passed, 1 warning
```

阶段收尾浏览器冒烟检查：

```text
GET /health 200
GET /quality-report 200
GET /quality-report/data.json 200
GET /quality-report/export.csv 200
/quality-report summary rows=7
risk queue rows=3
console errors=0
```

浏览器冒烟发现并修复了 `quality_report.html` 内联 JSON 被 HTML entity 转义后导致表格不渲染的问题；已补测试防回归。

## 安全合规

- 未把 API key、Bearer token、Authorization header、供应商原始敏感响应写入 Git、CSV、文档、测试或 Obsidian。
- 评测 CSV 只保存问题、指标、source type、文档/来源标识、延迟和脱敏摘要，不保存供应商原始响应。
- 全量测试默认 deterministic provider，不依赖真实 Jina API。

## 文档同步

- 已新增/更新：`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage29_real_embedding_quality_eval.md`、`docs/stage29_quality_report.md`、`docs/phase_reviews/phase-29.md`。
- 已更新本地 Obsidian 阶段页、阶段汇报索引和阶段 29 总汇报草稿。
- `task_plan.md`、`findings.md`、`progress.md` 按 Phase 0-8 进度持续更新。

## 人工核验清单

- 抽查 `docs/stage29_quality_report.md` 中列出的低覆盖查询是否符合语料现实。
- 打开 `/quality-report`，核对页面、JSON 和 CSV 导出是否反映阶段 29 指标。
- 复查 `data/evaluation/stage29_real_quality_results.csv` 中失败项和拒答项，不把拒答查询的检索命中失败误判为问答失败。
- 确认 `data/app.sqlite` 本地 embedding 计数符合 `12716 Jina + 12716 deterministic = 25432`。
- 用户已明确授权提交合并；提交时仍需保证不提交 `.env`、SQLite 数据库、`obsidian-vault/`、API key、Bearer token、供应商原始敏感响应或受限/原始全文。

## 面试表达

阶段 29 的重点不是再扩语料，而是把上一阶段新增语料真正纳入语义检索闭环。我先清空历史混合 embedding，避免旧索引污染评测；再分别构建真实 Jina v3 embedding 和 deterministic 测试 embedding，让生产质量评估和 CI 可复现测试各走自己的 provider。最后用覆盖 Wikipedia、标准、网页和拒答边界的新评测集跑端到端质量指标，并把结果公开到质量报告页面。这样能诚实说明当前系统的检索质量、失败样例和人工复核重点，而不是只给一个“测试通过”的工程结论。
