# 阶段 29 进度日志：真实 Embedding 重建 + 端到端质量闭环

## 当前状态

- 当前阶段：阶段 29「真实 Embedding 重建 + 端到端质量闭环」。
- 当前分支：`codex/phase-29-real-embedding-quality-eval`。
- 前置条件：阶段 28 已完成提交、创建 `phase-28-complete` tag，并合并到本地 main。
- 阶段 29 状态：Phase 0-8 已完成，用户已明确授权提交合并。
- 提交状态：尚未执行 `git add`、尚未提交、尚未创建 `phase-29-complete` tag、尚未 push、未创建 PR。

## 阶段 29 目标概述

1. **Embedding 残留清理**：删除 chunk_embeddings 表全部 21,634 条混杂记录（旧 Jina + deterministic 混合），回到干净起点。
2. **真实 Jina v3 重建**：为全部 12,716 条 chunk 统一建真实语义向量，让阶段 28 新增的 170 篇文档在真实检索中可用。
3. **Deterministic 索引补建**：保留一套 deterministic embedding 供 CI/测试使用。
4. **评测数据集更新**：新增覆盖新语料（Wikipedia、标准 PDF、清理后网页）的评测查询。
5. **端到端质量评测**：用真实 Jina embedding 跑检索+问答评测，产出 precision@k、coverage_ratio、refusal accuracy 等可展示指标。
6. **质量报告**：整理成面试可展示的质量报告，更新 /quality-report 端点。

## 阶段 28 验收基线

- 阶段 28 验收结论：PASS。
- 阶段 28 merge commit：`07dadf0 Merge phase 28 web crawl auto ingest`。
- 阶段 28 final feature commit / `phase-28-complete`：`b345cd8 Complete phase 28 web crawl auto ingest`。
- 测试基线：544 passed, 1 warning。
- 数据基线：documents 635 / chunks 12,716 / chunk_embeddings 21,634 / sources 673。
- 关键交付：网页爬取管线、低质量清理、Wikipedia API fetcher、标准 PDF 入库。

## Phase 日志

### Phase 0：启动校准与文件计划

状态：已完成。

完成内容：
- 已阅读项目入口规则、README、进度、架构、数据源、阶段 28 验收草稿，以及根目录三份阶段 29 计划文件。
- 已运行 `git status -sb`、`git log --oneline -5`、`git show --no-patch --oneline phase-28-complete`、`git merge-base --is-ancestor phase-28-complete main`。
- 已确认 `phase-28-complete -> b345cd8`，并且该 tag 是本地 `main` 的祖先。
- 已从阶段 28 合并后的本地 `main` 创建并切换到 `codex/phase-29-real-embedding-quality-eval`。

注意事项：
- 本地 `main` 领先 `origin/main` 2 个提交；阶段 29 当前不执行 push。
- 当前仅做分支切换与计划文件更新，未执行 `git add`、`git commit`、`git tag`、`git push`。

### Phase 1：阶段 29 设计文档

状态：已完成。

完成内容：
- 新增 `docs/stage29_real_embedding_quality_eval.md`。
- 文档说明了为什么 `chunk_embeddings=21634` 需要清理、为什么选择全量重建、Jina v3 与 deterministic 双索引的执行顺序、评测指标和 `/quality-report` 更新边界。
- 预检发现 `--provider jina` 需要在 `create_embedding_provider()` 中补 alias；当前底层 OpenAI-compatible provider 已具备请求 Jina embeddings API 的能力。

提交边界：
- 用户已明确要求提交阶段 29 整体开发工作，并上传 merge 至 GitHub；进入提交、创建 `phase-29-complete` tag、合并 main 和推送流程。

### Phase 2：Embedding 残留清理

状态：已完成。

完成内容：
- 新增 `scripts/cleanup_stale_embeddings.py`，支持 `--dry-run`、`--execute`、`--provider`。
- 新增 `tests/test_cleanup_stale_embeddings.py`。
- dry-run 确认真实数据库清理前状态：
  - `chunks=12716`
  - `chunk_embeddings=21634`
  - `orphan_embeddings=0`
  - `deterministic/hash-token-v1/dim=64 = 12716`
  - `openai-compatible/jina-embeddings-v3/dim=1024 = 8918`
- 已执行清理，删除 21634 条 embedding。
- 清理后验证：`chunks=12716`，`chunk_embeddings=0`。

验证：
```text
.\.venv\Scripts\python.exe -m pytest tests\test_cleanup_stale_embeddings.py -q
4 passed
```

提交边界：
- 仍未执行 `git add`、`git commit`、`git tag`、`git push`。

### Phase 3：真实 Jina Embedding 重建

状态：已完成。

完成内容：
- 为 `create_embedding_provider()` 增加 `jina` alias，并补单元测试。
- 确认本地 Jina embedding 配置完整，未打印 API key。
- 运行真实 Jina v3 全量重建：

```text
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider jina --batch-size 64 --sleep-seconds 1 --max-retries 3
vector index built provider=jina model=jina-embeddings-v3 dimension=1024 total=12716 indexed=12716 updated=0 skipped=0
```

验证：
```text
chunks 12716
chunk_embeddings 12716
jina_embeddings 12716
distinct_jina_chunk_ids 12716
orphan_embeddings 0
duplicate_provider_model_groups 0
```

性能基准：
```text
scripts\benchmark_retrieval.py --provider jina --runs 1
query_embedding: 940.29-1011.31 ms
vector_search: 1040.35-3040.30 ms
hybrid_search: 2601.00-2778.45 ms
agent_query: 2658.63-2950.80 ms
```

提交边界：
- 仍未执行 `git add`、`git commit`、`git tag`、`git push`。

### Phase 4：Deterministic 索引补建（CI 保障）

状态：已完成。

完成内容：
- 运行 deterministic 索引补建：

```text
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider deterministic --batch-size 64
vector index built provider=deterministic model=hash-token-v1 dimension=64 total=12716 indexed=12716 updated=0 skipped=0
```

最终索引状态：
```text
chunks 12716
chunk_embeddings 25432
deterministic/hash-token-v1/dim=64 12716
jina/jina-embeddings-v3/dim=1024 12716
distinct deterministic chunk ids 12716
distinct jina chunk ids 12716
orphan_embeddings 0
duplicate_provider_model_groups 0
```

验证：
```text
.\.venv\Scripts\python.exe -m pytest -q
549 passed, 1 warning
```

提交边界：
- 仍未执行 `git add`、`git commit`、`git tag`、`git push`。

### Phase 5：评测数据集更新

状态：已完成。

完成内容：
- 新增 `data/evaluation/stage29_new_corpus_queries.csv`，共 18 题：
  - Wikipedia：5 题。
  - 标准/指南 `standard_document`：5 题。
  - 清理后保留网页 `web_page`：5 题。
  - 拒答边界：3 题。
- 新增 `tests/test_stage29_new_corpus_queries.py`。

验证：
```text
.\.venv\Scripts\python.exe -m pytest tests\test_stage29_new_corpus_queries.py -q
2 passed
```

提交边界：
- 仍未执行 `git add`、`git commit`、`git tag`、`git push`。

### Phase 6：端到端质量评测

状态：已完成。

完成内容：
- 新增 `scripts/evaluate_stage29_real_quality.py`。
- 新增 `tests/test_evaluate_stage29_real_quality.py`。
- 生成：
  - `data/evaluation/stage29_real_quality_results.csv`
  - `data/evaluation/stage29_real_quality_summary.csv`

验证：
```text
.\.venv\Scripts\python.exe -m pytest tests\test_evaluate_stage29_real_quality.py -q
3 passed

.\.venv\Scripts\python.exe scripts\evaluate_stage29_real_quality.py --provider jina --top-k 5
stage29 real quality provider=jina model=jina-embeddings-v3 p@1=0.600 p@3=0.867 p@5=0.933 coverage=0.664 refusal_accuracy=1.000
```

关键结果：
```text
total_queries=18
non_refusal_total=15
precision_at_1=0.600
precision_at_3=0.867
precision_at_5=0.933
avg_coverage_ratio=0.664
refusal_total=3
refusal_accuracy=1.000
source_type_distribution=institutional_access_pdf:17;metadata_record:6;open_access_pdf:5;standard_document:25;web_page:28;wikipedia:9
```

主要观察：
- `stage29_wiki_dam_applications` 未命中预期 Wikipedia source_type。
- `stage29_web_rfc_advantages` top1 命中正确 web_page，但 coverage_ratio 仅 0.250。
- 3 条拒答边界均正确拒答。

提交边界：
- 仍未执行 `git add`、`git commit`、`git tag`、`git push`。

### Phase 7：质量报告与 /quality-report 更新

状态：已完成。

完成内容：
- 新增 `scripts/build_stage29_quality_report.py`。
- 新增 `docs/stage29_quality_report.md`。
- 新增 `data/evaluation/stage29_quality_summary.csv`。
- 更新 `app/frontend/quality_report.html` 为阶段 29 只读报告。
- 更新 `app/api/frontend.py`，让 `/quality-report/data.json` 和 `/quality-report/export.csv` 读取/导出阶段 29 summary。
- 新增 `tests/test_build_stage29_quality_report.py`，更新 `tests/test_frontend_app.py`。

验证：
```text
.\.venv\Scripts\python.exe scripts\build_stage29_quality_report.py
stage29 quality report built rows=7

.\.venv\Scripts\python.exe -m pytest tests\test_build_stage29_quality_report.py tests\test_frontend_app.py -q
7 passed
```

报告结论：
- `embedding_rebuild=completed/low`
- `real_jina_quality=completed/medium`
- `refusal_boundary=closed/low`
- `overall=review_required/medium`
- 人工复核重点：`stage29_wiki_dam_applications`、`stage29_web_rfc_advantages`

提交边界：
- 仍未执行 `git add`、`git commit`、`git tag`、`git push`。

### Phase 8：回归验证 + 文档与 Obsidian 收尾

状态：已完成。

完成内容：
- 已更新 `README.md`，把当前阶段切换为阶段 29 人工核验前状态。
- 已更新 `docs/progress.md`，记录阶段 29 起点校准、完成内容、真实评测指标和人工核验重点。
- 已更新 `docs/architecture.md`，补充真实 Jina / deterministic 双索引和质量报告数据流。
- 已更新 `docs/data_sources.md`，补充阶段 29 派生索引与评测产物的数据安全边界。
- 已更新 `AGENT.MD` 最新交接状态。
- 已新增 `docs/phase_reviews/phase-29.md` 验收草稿。
- 已补 Obsidian 阶段 29 阶段页、阶段汇报索引和阶段总汇报。

待完成验证：
- 无。当前停在用户人工核验前。

最终验证：
```text
.\.venv\Scripts\python.exe -m pytest -q
556 passed, 1 warning

DB:
chunks=12716
chunk_embeddings=25432
deterministic/hash-token-v1/dim=64 12716
jina/jina-embeddings-v3/dim=1024 12716
orphan_embeddings=0
duplicate_provider_model_groups=0

HTTP smoke:
GET /health 200
GET /quality-report 200
GET /quality-report/data.json 200
GET /quality-report/export.csv 200

Browser smoke:
/quality-report summary rows=7
risk queue rows=3
console errors=0
```

修复记录：
- 浏览器冒烟发现 `quality_report.html` 内联 JSON 被实体转义后导致表格为空。
- 已修复 `scripts/build_stage29_quality_report.py` 的 JSON 嵌入方式，并补 `tests/test_build_stage29_quality_report.py` 防回归。

提交边界：
- 仍未执行 `git add`、`git commit`、`git tag`、`git push`。
