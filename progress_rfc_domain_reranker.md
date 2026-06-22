# RFC-DomainReranker Progress

## 2026-06-22

工作区：`G:\Codex\program\rfc-rag-agent-reranker`

分支：`feature/rfc-domain-reranker`

状态：阶段 A/B/C 开发与本地验证完成，停在人工核验前。未执行 `git add`、commit、tag、push、PR。

## 本轮完成

- 读取并遵守项目入口规则：本分支只使用 RFC-DomainReranker 专用三件套，不占用根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 完成 `scripts/reranker/export_training_pairs.py` 的空库容错。
- 完成 `scripts/reranker/collect_real_agent_cases.py`：
  - 默认 dry-run；
  - `--execute` 才调用真实 provider；
  - `--log-answers` 才写入 `qa_logs`；
  - 支持 `--limit 50`、`--resume`、`--mode`；
  - balanced selection 覆盖 7 个目标类别。
- 完成 `scripts/reranker/generate_synthetic_queries.py`：
  - 读取 `sampled_chunks.jsonl`；
  - 默认 dry-run；
  - `--execute` 才调用当前 chat provider；
  - 支持 `--limit`、`--resume` 和基本过滤。
- 完成 `scripts/reranker/build_dataset.py`：
  - 合并真实 QA pairs 与 synthetic positives；
  - 为每个正例构造 hard/easy negative；
  - 按 query/group 切分 train/val/test；
  - 输出 manual review CSV 和 summary。
- 新增测试：
  - `tests/test_rfc_domain_reranker_export.py`
  - `tests/test_rfc_domain_reranker_pipeline.py`

## 已运行命令摘要

```text
python scripts\reranker\collect_real_agent_cases.py --limit 50 --output data\reranker_training\real_agent_cases_preview.jsonl
-> dry-run rows=50

python scripts\reranker\collect_real_agent_cases.py --limit 50 --execute --log-answers --output data\reranker_training\real_agent_cases_execute_v2.jsonl
-> rows=50

python scripts\reranker\export_training_pairs.py --sample-size 5000
-> qa_log_pairs=976 sampled_chunks=5000 eval_queries=107

python scripts\reranker\generate_synthetic_queries.py --limit 500
-> rows=500

python scripts\reranker\build_dataset.py
-> train_rows=2295 val_rows=296 test_rows=254 total_rows=2845

python -m pytest tests\test_rfc_domain_reranker_export.py tests\test_rfc_domain_reranker_pipeline.py -q
-> 12 passed
```

## 输出文件

以下均在 gitignored `data/reranker_training/` 下：

- `real_agent_cases_preview.jsonl`
- `real_agent_cases_execute.jsonl`
- `real_agent_cases_execute_v2.jsonl`
- `qa_log_pairs.jsonl`
- `sampled_chunks.jsonl`
- `eval_queries.jsonl`
- `synthetic_queries.jsonl`
- `reranker_train.jsonl`
- `reranker_val.jsonl`
- `reranker_test.jsonl`
- `manual_review_sample.csv`
- `summary.json`
- `dataset_summary.json`

## 下一步建议

1. 人工抽查 `real_agent_cases_execute_v2.jsonl`。
2. 人工抽查 `manual_review_sample.csv`。
3. 如果质量可接受，再决定是否真实执行 Stage B：`generate_synthetic_queries.py --execute --limit 300`。
4. 人工确认后再进入 git stage/commit/push/PR。
