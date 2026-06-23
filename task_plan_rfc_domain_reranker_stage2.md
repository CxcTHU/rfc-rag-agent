# RFC-DomainReranker Stage 2 任务计划

## Goal

在独立 worktree `G:\Codex\program\rfc-rag-agent-reranker` 中完成 RFC-DomainReranker Stage 2：LoRA 微调脚本与离线评测脚本骨架开发、测试和规划文件更新。主工作区 `G:\Codex\program\rfc-rag-agent` 留给主干阶段开发，不使用根目录 `task_plan.md`、`findings.md`、`progress.md`。

当前分支：`feature/rfc-domain-reranker-stage2-training-eval`

起点：`origin/main -> e64060a3 Merge RFC-DomainReranker training data prep`，已确认包含 Stage 1 tag `rfc-domain-reranker-stage-1-complete -> 2c19d999`。

## Stage 2 范围

本阶段聚焦总规划 Step 3 与 Step 4 的可复现工程骨架：

- 完善 `scripts/reranker/train_lora.py`，支持默认 dry-run 校验和显式 `--execute` 真实训练路径。
- 完善 `scripts/reranker/evaluate_reranker.py`，支持离线比较 `none`、`deterministic`、可选 `local-lora`、可选 `glm-rerank`。
- 固定训练配置、输入输出、resume/checkpoint、安全边界和测试替身。
- 默认不触发真实 API、不要求 GPU、不要求 Hugging Face 下载作为 CI 或本地测试前提。
- 本阶段允许未来显式训练生成本地模型权重到 `models/bge-reranker-base-rfc-lora/`，但该目录保持 gitignored，不提交。

## Phase 顺序

### Phase 0：启动核验

- [x] 确认当前目录是 `G:\Codex\program\rfc-rag-agent-reranker`。
- [x] `git fetch origin --prune` 成功后，确认 `origin/main` 包含 Stage 1 merge commit `e64060a3bffbfcce1857d4c5e0cdd45ec829fd5d`。
- [x] 从 `origin/main` 创建/切换到 `feature/rfc-domain-reranker-stage2-training-eval`。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- [x] 阅读 Stage 1 三件套与 Stage 2 三件套。
- [x] 确认不修改根目录 `task_plan.md`、`findings.md`、`progress.md`。
- [x] 确认 `docs/redis_security_verification.html` 仍为无关未跟踪文件，本阶段不修改。

### Phase 1：训练脚本设计与配置

- [x] `train_lora.py` 支持 CLI：`--train`、`--val`、`--output-dir`、`--base-model`、`--epochs`、`--batch-size`、`--lr`、`--max-length`、`--lora-r`、`--lora-alpha`、`--lora-dropout`、`--resume-from-checkpoint`、`--dry-run`、`--execute`。
- [x] 默认 dry-run 只校验数据 schema、样本数、label 分布、长度分布和训练配置，不下载模型、不训练。
- [x] 显式 `--execute` 才允许真实训练。
- [x] 默认基座模型为 `BAAI/bge-reranker-base`。
- [x] LoRA 默认值为 `r=16`、`alpha=32`、`dropout=0.1`。
- [x] 训练输出只允许写入 gitignored 目录，如 `models/bge-reranker-base-rfc-lora/`。

### Phase 2：训练数据读取与校验

- [x] 读取 `reranker_train.jsonl` / `reranker_val.jsonl`。
- [x] 校验每行只包含 `query`、`passage`、`label`。
- [x] 校验 label 只允许 0/1，query/passage 非空。
- [x] 输出安全 summary：行数、正负例比例、query/passage/pair 长度分布、超过 `max_length` 的比例。
- [x] 不把完整 passage 或完整训练样本写入文档、测试或 Git。

### Phase 3：LoRA 训练实现

- [x] `--execute` 路径以 `transformers` / `peft` / `datasets` / `torch` 实现 cross-encoder reranker LoRA 训练骨架。
- [x] 缺依赖时给出明确错误。
- [x] 当前真实训练要求 CUDA GPU；CPU 环境明确报错，dry-run 仍可运行。
- [x] 保存 adapter、tokenizer 和 `training_config_summary.json` 到输出目录。
- [x] 支持 `--resume-from-checkpoint` 传给 Trainer。

### Phase 4：离线评测脚本

- [x] 完善 `evaluate_reranker.py`。
- [x] 支持从 `reranker_test.jsonl` 按 query 分组恢复候选列表。
- [x] 指标：MRR@5、NDCG@5、Precision@1、平均 latency。
- [x] 支持默认离线配置 `none` 与 `deterministic`。
- [x] `local-lora` 需显式 `--local-lora-model-path`，缺路径或缺依赖时明确报错。
- [x] `glm-rerank` 需显式 `--execute`，不得作为 CI 或默认本地测试前提。
- [x] 输出 `data/reranker_training/reranker_eval_results.csv` 与 `reranker_eval_summary.json`，保持 gitignored。

### Phase 5：测试与安全扫描

- [x] 新增测试覆盖训练 dry-run 不训练、不下载模型。
- [x] 新增测试覆盖数据 schema 校验、label 校验、长度/截断统计。
- [x] 新增测试覆盖 evaluate 指标计算、query 分组候选恢复。
- [x] 新增测试覆盖默认真实 provider/API 不调用。
- [x] 新增测试覆盖 `glm-rerank` 未 `--execute` 报错、`local-lora` 缺模型路径报错。
- [x] 聚焦测试通过。
- [x] 扫描新增源码/测试/文档，确认无密钥、供应商原始响应或完整训练语料落盘；命中项仅为安全规则文本。

### Phase 6：文档与人工核验前收尾

- [x] 更新 Stage 2 三件套。
- [x] 记录训练/评测命令、真实执行状态、输出路径和遗留风险。
- [x] 不提交训练数据、评测输出、模型权重。
- [x] 停在人工核验前：不 `git add`、不 commit、不 tag、不 push、不 PR。

## 验证结果

```text
python -m pytest tests\test_rfc_domain_reranker_export.py tests\test_rfc_domain_reranker_pipeline.py tests\test_rfc_domain_reranker_training.py tests\test_rfc_domain_reranker_evaluation.py -q
-> 22 passed

python scripts\reranker\train_lora.py --dry-run --train data\reranker_training\reranker_train.jsonl --val data\reranker_training\reranker_val.jsonl
-> train_rows=2295 val_rows=296, no training, no model download

python scripts\reranker\evaluate_reranker.py --dataset data\reranker_training\reranker_test.jsonl --rerankers none deterministic
-> none: queries=38 mrr_at_5=1.000000 ndcg_at_5=0.858902 precision_at_1=1.000000
-> deterministic: queries=38 mrr_at_5=0.692982 ndcg_at_5=0.705747 precision_at_1=0.473684

git check-ignore -v data/reranker_training/ data/reranker_training/reranker_eval_results.csv data/reranker_training/reranker_eval_summary.json models/bge-reranker-base-rfc-lora/ .env
-> all ignored
```

## 完成标准

- [x] `train_lora.py` 不再是占位脚本，具备 dry-run 校验与显式真实训练路径。
- [x] `evaluate_reranker.py` 不再是占位脚本，具备离线指标计算和多 reranker 对比骨架。
- [x] 新增测试覆盖核心逻辑并通过。
- [x] `models/bge-reranker-base-rfc-lora/`、`data/reranker_training/` 继续 gitignored。
- [x] Stage 2 三件套更新到最新状态。
- [x] 最终停在用户人工核验前。

## Stage 2.5 附加计划：数据增强与重训练

目标：在 GPU 服务器 `36.103.236.99` 上用真实 synthetic query 替换 dry-run 模板 query，并通过多组 LoRA 超参实验让 `local-lora` 的 MRR@5 超过 deterministic baseline。

### Stage 2.5 Phase 0：启动核验

- [x] 确认服务器目录为 `/home/ubuntu/rfc-rag-agent-reranker`。
- [x] 确认 RTX 3090、CUDA、PyTorch CUDA 可用。
- [x] 确认分支 `feature/rfc-domain-reranker-stage2-training-eval` 与 commit `06c811f96e389f302465346d582066b9d77ee62c`。
- [x] 读取 `AGENT.MD`、Stage 2 findings/progress。
- [x] 上传服务器本地 `.env` 并保持 exclude，不写入 Git。

### Stage 2.5 Phase 1：真实 synthetic query 生成

- [x] 运行 `generate_synthetic_queries.py --execute --limit 500`。
- [x] 完成 provider smoke；Linux 上通过 venv 本地 `curl.exe -> /usr/bin/curl` 兼容 DeepSeek curl fallback。
- [x] 生成 500 条真实 synthetic query，最终可用 499 条。
- [x] 保留 raw 状态备份，记录 filtered 误杀与人工抽样判断。

### Stage 2.5 Phase 2：重建数据集

- [x] 运行 `build_dataset.py`。
- [x] 新数据：`train_rows=2267`、`val_rows=330`、`test_rows=245`、`total_rows=2842`。
- [x] 运行 `train_lora.py --dry-run`，schema、label、长度统计通过。

### Stage 2.5 Phase 3：三组 GPU 训练

- [x] 备份首次训练模型为 `models/bge-reranker-base-rfc-lora-run1-baseline`。
- [x] 实验 A：3 epoch，LoRA r=16/alpha=32。
- [x] 实验 B：5 epoch，LoRA r=16/alpha=32。
- [x] 实验 C：5 epoch，LoRA r=32/alpha=64。
- [x] 每组训练后立即评测并保存独立 summary/results。

### Stage 2.5 Phase 4：最优模型与最终评测

- [x] 选择 expC，复制回标准路径 `models/bge-reranker-base-rfc-lora/`。
- [x] 修复 `local-lora` 评测：初始化缓存模型、优先 CUDA、batch tensor 移动到同一 device。
- [x] 最终 GPU/cache 评测：local-lora MRR@5 `0.969298`，deterministic MRR@5 `0.964912`。

### Stage 2.5 Phase 5：收尾

- [x] 更新 Stage 2 三件套。
- [x] 运行聚焦测试：`23 passed`。
- [x] 停在人工核验前：不 `git add`、不 commit、不 tag、不 push、不 PR。

## 安全边界

- 不提交 `.env`、`.env.prod`、数据库文件、API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、受限全文、完整 chunk 或模型权重。
- 真实 API 调用必须显式 `--execute`。
- 真实训练必须显式 `--execute`。
- CI/本地默认测试不得依赖真实 API、GPU 或 Hugging Face 下载。
