# RFC-DomainReranker 任务计划

## Goal

在独立 worktree `G:\Codex\program\rfc-rag-agent-reranker` 的 `feature/rfc-domain-reranker` 分支推进 RFC-DomainReranker。主工作区 `G:\Codex\program\rfc-rag-agent` 保留给阶段 52，不在本分支占用根目录 `task_plan.md`、`findings.md`、`progress.md`。

当前阶段目标：完成阶段 A 真实 Agent 样本补强 50 条，并完成 Stage B/C 脚本骨架、测试和本地数据链路验证；停在人工核验前，不提交、不推送。

## 已完成

- [x] 创建并使用独立 worktree `G:\Codex\program\rfc-rag-agent-reranker`。
- [x] 确认目标分支为 `feature/rfc-domain-reranker`。
- [x] 新增 `.gitignore` 规则：`data/reranker_training/` 与 `models/bge-reranker-base-rfc-lora/`。
- [x] 完成 Step 1 脚本 `scripts/reranker/export_training_pairs.py`。
- [x] 支持空库温和导出，避免未初始化 SQLite 阻断 eval query 导出。
- [x] 从本地 PostgreSQL dev 库导出：`qa_log_pairs=976`、`sampled_chunks=5000`、`eval_queries=107`。
- [x] 完成 Stage A 脚本 `scripts/reranker/collect_real_agent_cases.py`。
- [x] Stage A 默认 dry-run；只有显式 `--execute --log-answers` 才调用真实 provider 并写入 `qa_logs`。
- [x] Stage A 支持 `--limit`、`--resume`、`--mode`、`--top-k`、`--max-tool-calls`。
- [x] Stage A 问题选择覆盖施工、填充性能、水化热、力学、裂缝、工程案例和拒答边界。
- [x] 使用当前项目 provider：`openai-compatible/deepseek-v4-pro` 与 `paratera/GLM-Embedding-3`。
- [x] 真实采集第二版 `real_agent_cases_execute_v2.jsonl`：50 条 completed，0 error，50 条写入 `qa_logs`，1 条 refused。
- [x] 完成 Stage B 脚本 `scripts/reranker/generate_synthetic_queries.py`。
- [x] Stage B 默认 dry-run；显式 `--execute` 才调用真实 chat provider；支持 `--limit`、`--resume`、基本质量过滤。
- [x] 生成 synthetic dry-run 抽查集 500 条。
- [x] 完成 Stage C 脚本 `scripts/reranker/build_dataset.py`。
- [x] Stage C 合并 QA positives 与 synthetic positives；每个正例构造 1 个 hard negative 和 1 个 easy negative。
- [x] Stage C 按 query/group 切分 train/val/test，并输出 `manual_review_sample.csv` 与 `dataset_summary.json`。
- [x] 当前 dataset：`train_rows=2295`、`val_rows=296`、`test_rows=254`、`total_rows=2845`。
- [x] 新增测试覆盖 dry-run 不调用 provider、`--execute`/`--log-answers` 边界、qa_logs 写入、synthetic 过滤、dataset group split 不泄漏。

## 当前验证

```text
python -m pytest tests\test_rfc_domain_reranker_export.py tests\test_rfc_domain_reranker_pipeline.py -q
-> 12 passed

python scripts\reranker\collect_real_agent_cases.py --limit 50 --execute --log-answers --output data\reranker_training\real_agent_cases_execute_v2.jsonl
-> rows=50

python scripts\reranker\export_training_pairs.py --sample-size 5000
-> qa_log_pairs=976 sampled_chunks=5000 eval_queries=107

python scripts\reranker\generate_synthetic_queries.py --limit 500
-> rows=500 dry-run

python scripts\reranker\build_dataset.py
-> train_rows=2295 val_rows=296 test_rows=254 total_rows=2845
```

## 人工核验前待办

- [ ] 抽查 `data/reranker_training/real_agent_cases_execute_v2.jsonl` 的 50 条真实 Agent 问答质量。
- [ ] 抽查 `data/reranker_training/manual_review_sample.csv` 的正负例标签质量。
- [ ] 决定是否将 Stage B 从 dry-run 改为真实 `--execute` 生成 300-500 条 synthetic queries。
- [ ] 人工确认后再允许 `git add` / commit / push / PR。

## 边界

- 不提交 `.env`、`.env.prod`、数据库文件、API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、受限全文或完整 chunk 训练语料。
- 不提交 `data/reranker_training/`、`models/bge-reranker-base-rfc-lora/`。
- 不修改根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 不修改无关未跟踪文件 `docs/redis_security_verification.html`。
