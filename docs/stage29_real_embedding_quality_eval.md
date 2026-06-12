# 阶段 29 设计：真实 Embedding 重建与端到端质量闭环

## 目标

阶段 29 的目标是在阶段 28 已合并到 `main` 的基础上，把当前混杂的 `chunk_embeddings` 表清理到干净起点，再为全部 12,716 条 chunk 建立两套可审计索引：

- 真实 Jina v3 embedding：用于真实语义检索和阶段 29 质量评测。
- deterministic embedding：用于 CI 和本地全量回归测试。

完成后运行端到端质量评测，输出 precision@k、coverage_ratio、refusal_accuracy 和 source_type_distribution，并更新只读质量报告与 `/quality-report`。

## 新词解释

- Embedding：把一段文字转换成一串数字向量，用来计算“问题”和“资料片段”的语义距离。本项目里每个 chunk 都需要一条 embedding，向量检索才能工作。
- chunk：资料被切分后的片段。本项目里一篇论文、网页或标准 PDF 会被切成多个 chunk，检索时先找 chunk，再组织回答。
- provider：模型服务来源或本地实现。例如 `jina` 表示真实 Jina embedding 服务，`deterministic` 表示本地稳定测试用假向量。
- precision@k：检索评测指标，表示前 k 条结果里命中预期证据的比例。比如 precision@5 关注前 5 条里是否找到正确资料。
- coverage_ratio：答案要点覆盖率，用来衡量召回证据是否覆盖评测题期待的关键回答点。

## 起点状态

阶段 28 合并后，本地基线为：

```text
documents 635
chunks 12716
sources 673
chunk_embeddings 21634
phase-28-complete -> b345cd8 Complete phase 28 web crawl auto ingest
main -> 07dadf0 Merge phase 28 web crawl auto ingest
```

`phase-28-complete` 已确认是 `main` 的祖先，阶段 29 从 `codex/phase-29-real-embedding-quality-eval` 分支继续。

## 为什么要全量清理

当前 `chunk_embeddings=21,634`，但 `chunks=12,716`。这说明向量表中混有多个阶段、多种 provider 和不同语料范围下的索引记录。

阶段 28 新增了网页、Wikipedia 和标准 PDF 语料，并用 deterministic provider 重建过索引；但旧 Jina 索引只覆盖阶段 18/20 之前的旧 chunk。这样会产生两个问题：

- 新增语料在真实 Jina 语义检索中不可用或覆盖不完整。
- 旧索引与新 chunk 范围混杂，评测时很难解释结果来自哪套索引。

本阶段选择“全部删除后重建”，而不是增量修补。原因是全量重建更简单、更可审计：清理后每个 chunk 应恰好有一条 Jina embedding 和一条 deterministic embedding。

## 清理策略

新增 `scripts/cleanup_stale_embeddings.py`：

- 默认 `--dry-run` 只统计，不写数据库。
- `--execute` 才实际删除。
- 输出 provider/model/dimension 分布。
- 输出孤立 embedding 数量，即 embedding 的 `chunk_id` 找不到对应 chunk。
- 支持删除全部 embedding，也支持按 provider 删除，便于后续排查。

阶段 29 主流程采用全部删除：

```text
chunk_embeddings 21634 -> 0
chunks 12716 -> 12716
```

清理脚本不得删除 `chunks`、`documents` 或 `sources`。

## 真实 Jina 重建方案

重建命令：

```powershell
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider jina --batch-size 64 --sleep-seconds 1 --max-retries 3
```

实现注意：

- 当前 `create_embedding_provider()` 已支持 OpenAI-compatible embedding 协议，但还需要把 `jina` 作为别名映射到同一实现。
- Jina 默认配置从本地 `.env` 读取，不把 API key 写入命令、文档、CSV 或测试。
- batch size 使用 64，降低单次请求体积。
- batch 间 sleep 1 秒，避免触发限速。
- max retries 为 3，遇到临时网络错误或限速时重试。
- 如果脚本中断，重新运行同一命令；已有且 content_hash 未变化的 embedding 会被跳过。

完成后应满足：

```text
COUNT(chunk_embeddings WHERE provider='jina') = 12716
COUNT(DISTINCT chunk_id WHERE provider='jina') = 12716
```

## Deterministic 补建方案

真实 Jina 索引完成后，运行：

```powershell
.\.venv\Scripts\python.exe scripts\build_vector_index.py --provider deterministic --batch-size 64
```

这套索引用于 CI 和本地全量测试。真实 Jina 不得成为自动测试前提。

最终目标：

```text
jina embeddings = 12716
deterministic embeddings = 12716
total chunk_embeddings = 25432
```

## 评测方案

阶段 29 评测分三层：

1. 复用历史难题：读取 `stage19_chinese_hard_queries.csv` 和 `cn_fulltext_queries.csv`，保证旧语料与旧边界不退化。
2. 新增新语料题：创建 `stage29_new_corpus_queries.csv`，覆盖 Wikipedia、标准 PDF、网页和拒答边界。
3. 端到端真实评测：新增 `evaluate_stage29_real_quality.py`，用真实 Jina query embedding 运行检索和回答评测。

新增评测集字段建议：

```text
query_id,question,category,expected_source_type,expected_answer_points,expected_refused,notes
```

指标：

- precision@1 / precision@3 / precision@5
- coverage_ratio
- refusal_accuracy
- source_type_distribution
- latency_ms

评测结果必须诚实记录。若真实 provider 调用失败，写入 `error` 或 `skipped` 状态，不用 deterministic 结果伪装成功。

## 质量报告方案

新增 `docs/stage29_quality_report.md`，包含：

- 语料规模与 source_type 分布。
- embedding 重建结果：Jina、deterministic、重复、孤立。
- 真实 Jina 检索质量：precision@k、coverage_ratio、refusal_accuracy。
- 新语料覆盖情况：Wikipedia、标准 PDF、网页是否被召回。
- 检索性能：benchmark 耗时。
- 风险与下一步：例如真实 API 失败、个别 source_type 召回不足、拒答误判。

`GET /quality-report` 继续是只读静态报告入口：

- 不调用真实 API。
- 不写数据库。
- 不暴露 API key、Bearer token、Authorization header 或供应商原始响应。
- 不改变 `/search`、`/search/vector`、`/search/hybrid`、`/chat`、`/agent/query`、`/agent/query/stream` 的契约。

## 测试与回归边界

必须补充：

- `tests/test_cleanup_stale_embeddings.py`
- Jina provider alias 测试
- stage29 评测脚本单元测试，使用 fake provider 或 fixture，不调用真实 API

全量回归必须使用 deterministic provider：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

真实 Jina 重建和真实质量评测只作为显式本地步骤运行，不进入 CI 必跑。

## 完成标准

- `chunk_embeddings` 表最终为 25,432 条：12,716 Jina + 12,716 deterministic。
- 无孤立 embedding，无同 provider/model 下重复 chunk embedding。
- `stage29_new_corpus_queries.csv` 覆盖 Wikipedia、标准 PDF、网页和拒答边界。
- `stage29_real_quality_results.csv` 与 `stage29_real_quality_summary.csv` 已生成。
- `docs/stage29_quality_report.md` 和 `/quality-report` 已更新。
- 全量测试通过。
- 文档、阶段 review 和 Obsidian 草稿完成。
- 停在用户人工核验前：不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。
