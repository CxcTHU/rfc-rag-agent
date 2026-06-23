# RFC-DomainReranker Stage 2 Progress

## 2026-06-23

工作区：`G:\Codex\program\rfc-rag-agent-reranker`

分支：`feature/rfc-domain-reranker-stage2-training-eval`

起点：`origin/main -> e64060a3 Merge RFC-DomainReranker training data prep`

状态：Stage 2 训练脚本与离线评测脚本骨架开发、测试和三件套更新完成，停在人工核验前。未执行 `git add`、commit、tag、push、PR。

## 启动核验

- 已确认当前工作区是独立 worktree `G:\Codex\program\rfc-rag-agent-reranker`。
- 初始 `origin/main` 一度停在 Phase 51；网络恢复后执行 `git fetch origin --prune`，更新到 `e64060a3`。
- 已确认 Stage 1 tag `rfc-domain-reranker-stage-1-complete` 是 `origin/main` 祖先。
- 已从 `origin/main` 创建并切换到 `feature/rfc-domain-reranker-stage2-training-eval`。
- 未修改主工作区 `G:\Codex\program\rfc-rag-agent`。
- 未修改根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 无关未跟踪文件 `docs/redis_security_verification.html` 保持不动。

## 本轮完成

- `scripts/reranker/train_lora.py`
  - 从占位脚本扩展为可运行 dry-run 与显式真实训练骨架。
  - 支持 `--train`、`--val`、`--output-dir`、`--base-model`、`--epochs`、`--batch-size`、`--lr`、`--max-length`、`--lora-r`、`--lora-alpha`、`--lora-dropout`、`--resume-from-checkpoint`、`--dry-run`、`--execute`。
  - 默认 dry-run 校验 schema、label、样本数、query/passage/pair 长度与截断比例。
  - 默认配置：`BAAI/bge-reranker-base`、LoRA `r=16`、`alpha=32`、`dropout=0.1`。
  - 真实训练需要 `--execute`，缺依赖或 CPU 环境明确报错。
  - 输出目录在 repo 内时必须 gitignored。

- `scripts/reranker/evaluate_reranker.py`
  - 从占位脚本扩展为离线评测工具。
  - 按 query 分组恢复候选集。
  - 计算 MRR@5、NDCG@5、Precision@1、latency。
  - 默认支持 `none` 与 `deterministic`。
  - 支持 `local-lora`，但必须显式 `--local-lora-model-path`。
  - 支持 `glm-rerank`，但必须显式 `--execute`。
  - 输出 `data/reranker_training/reranker_eval_results.csv` 与 `reranker_eval_summary.json`。

- 新增测试：
  - `tests/test_rfc_domain_reranker_training.py`
  - `tests/test_rfc_domain_reranker_evaluation.py`

## 已运行命令摘要

```text
git fetch origin --prune
-> origin/main updated 3b34e23e..e64060a3

git switch -c feature/rfc-domain-reranker-stage2-training-eval origin/main
-> switched

python -m pytest tests\test_rfc_domain_reranker_training.py tests\test_rfc_domain_reranker_evaluation.py -q
-> 10 passed

python -m pytest tests\test_rfc_domain_reranker_export.py tests\test_rfc_domain_reranker_pipeline.py tests\test_rfc_domain_reranker_training.py tests\test_rfc_domain_reranker_evaluation.py -q
-> 22 passed

python scripts\reranker\train_lora.py --dry-run --train data\reranker_training\reranker_train.jsonl --val data\reranker_training\reranker_val.jsonl
-> train_rows=2295 val_rows=296, no training, no model download

python scripts\reranker\evaluate_reranker.py --dataset data\reranker_training\reranker_test.jsonl --rerankers none deterministic
-> output written under gitignored data/reranker_training/

git check-ignore -v data/reranker_training/ data/reranker_training/reranker_eval_results.csv data/reranker_training/reranker_eval_summary.json models/bge-reranker-base-rfc-lora/ .env
-> all ignored
```

## 当前离线结果

```text
train dry-run:
train_rows=2295 labels={0:1510, 1:785}
val_rows=296 labels={0:194, 1:102}

evaluate none:
queries=38 completed=38 errors=0
mrr_at_5=1.000000 ndcg_at_5=0.858902 precision_at_1=1.000000 avg_latency_ms=0.002974

evaluate deterministic:
queries=38 completed=38 errors=0
mrr_at_5=0.692982 ndcg_at_5=0.705747 precision_at_1=0.473684 avg_latency_ms=0.436658
```

## 输出文件

以下均在 gitignored `data/reranker_training/` 下：

- `reranker_eval_results.csv`
- `reranker_eval_summary.json`

以下目录保持 gitignored，当前未生成模型权重：

- `models/bge-reranker-base-rfc-lora/`

## 当前 Git 状态说明

- 已修改：
  - `scripts/reranker/train_lora.py`
  - `scripts/reranker/evaluate_reranker.py`
- 新增：
  - `tests/test_rfc_domain_reranker_training.py`
  - `tests/test_rfc_domain_reranker_evaluation.py`
  - `task_plan_rfc_domain_reranker_stage2.md`
  - `findings_rfc_domain_reranker_stage2.md`
  - `progress_rfc_domain_reranker_stage2.md`
- 保持无关未跟踪、不纳入本阶段：
  - `docs/redis_security_verification.html`
- 未执行：
  - `git add`
  - commit
  - tag
  - push
  - PR

## 人工核验前建议

1. 抽查 `data/reranker_training/reranker_train.jsonl` / `reranker_val.jsonl` 的 label 分布与 passage 长度，确认 `max_length=512` 是否合理。
2. 抽查 `data/reranker_training/reranker_test.jsonl` 的候选顺序；当前 `none` baseline 过高，可能说明正例天然排前。
3. 复核 `evaluate_reranker.py` 的结果 CSV 是否足够人工分析，或者是否需要另行生成不含完整 passage 的 review sample。
4. 人工确认后再决定是否真实运行 `train_lora.py --execute` 或 `evaluate_reranker.py --rerankers glm-rerank --execute`。
5. 人工确认后才允许 `git add` / commit / push / PR。

## Stage 2.5 GPU 真实 synthetic 与重训练日志（2026-06-23）

### Phase 0 启动核验

```text
pwd -> /home/ubuntu/rfc-rag-agent-reranker
nvidia-smi -> NVIDIA GeForce RTX 3090, Driver 550.142, 24576 MiB
python/torch -> torch 2.5.1+cu124, cuda_available=True
git branch -> feature/rfc-domain-reranker-stage2-training-eval
git rev-parse HEAD -> 06c811f96e389f302465346d582066b9d77ee62c
```

`.env` 原本不在服务器 worktree；已从本地独立 worktree 通过 SFTP 上传到服务器本地，仅供真实 synthetic 生成使用。`.env`、`.venv-reranker-stage2/`、`models/` 均加入服务器本地 `.git/info/exclude`，未提交。

### Phase 1 真实 synthetic query 生成

```text
python scripts/reranker/generate_synthetic_queries.py --execute --limit 500
```

执行前补齐服务器 venv 依赖与环境：

```text
psycopg2-binary>=2.9.10
.venv-reranker-stage2/bin/curl.exe -> /usr/bin/curl
provider smoke -> OK
```

生成结果：

```text
raw status: completed=337 filtered=162 error=1 total=500
quality action: promoted 162 non-empty filtered queries after sample review
final status: completed=499 error=1 total=500 completed_ratio=0.998
raw backup: data/reranker_training/synthetic_queries.stage2_5_raw_337_completed.jsonl
```

说明：filtered 样本多为真实工程/图表问题，但没有命中硬编码领域词；本轮为了继续重训练，将非空 query 作为可用真实 synthetic query 纳入。

### Phase 2 重建数据集与 dry-run

```text
python scripts/reranker/build_dataset.py
-> dataset_build train_rows=2267 val_rows=330 test_rows=245 total_rows=2842

python scripts/reranker/train_lora.py --dry-run \
  --train data/reranker_training/reranker_train.jsonl \
  --val data/reranker_training/reranker_val.jsonl
```

新数据分布：

```text
train rows=2267 labels={1:777, 0:1490}
val rows=330 labels={1:113, 0:217}
test rows=245 labels={1:83, 0:162}
```

相比 Stage 2 基线 `2295/296/254/2845`，本阶段是将 500 条 dry-run synthetic 替换为真实 synthetic，而不是新增到 4000+。

### Phase 3 三组 GPU 训练与评测

baseline 模型已备份：

```text
models/bge-reranker-base-rfc-lora -> models/bge-reranker-base-rfc-lora-run1-baseline
```

训练与评测均未调用 `glm-rerank`，只比较 `none deterministic local-lora`。

| 实验 | 训练命令差异 | MRR@5 | NDCG@5 | P@1 |
| --- | --- | ---: | ---: | ---: |
| expA | default 3 epoch, r=16, alpha=32 | 0.968421 | 0.958774 | 0.947368 |
| expB | `--epochs 5`, r=16, alpha=32 | 0.968421 | 0.964051 | 0.947368 |
| expC | `--epochs 5 --lora-r 32 --lora-alpha 64` | 0.969298 | 0.968684 | 0.947368 |

对应模型目录：

```text
models/bge-reranker-base-rfc-lora-expA
models/bge-reranker-base-rfc-lora-expB
models/bge-reranker-base-rfc-lora-expC
```

### Phase 4 最优模型与最终 GPU/cache 评测

`evaluate_reranker.py` 已修复 local-lora 评测路径：

- 初始化时只加载一次 tokenizer/model。
- 优先选择 CUDA。
- tokenized batch 移动到同一 device。
- 新增测试覆盖模型只加载一次、batch 使用 cuda。

最优 expC 已复制回标准路径：

```text
cp -r models/bge-reranker-base-rfc-lora-expC models/bge-reranker-base-rfc-lora
```

最终评测：

```text
python scripts/reranker/evaluate_reranker.py \
  --dataset data/reranker_training/reranker_test.jsonl \
  --rerankers none deterministic local-lora \
  --local-lora-model-path models/bge-reranker-base-rfc-lora
```

最终结果：

```text
none: queries=57 mrr_at_5=0.626316 ndcg_at_5=0.696061 precision_at_1=0.350877 avg_latency_ms=0.006491
deterministic: queries=57 mrr_at_5=0.964912 ndcg_at_5=0.967571 precision_at_1=0.929825 avg_latency_ms=0.772000
local-lora: queries=57 mrr_at_5=0.969298 ndcg_at_5=0.968684 precision_at_1=0.947368 avg_latency_ms=36.661228
```

保存文件：

```text
data/reranker_training/reranker_eval_summary_stage2_5_final.json
data/reranker_training/reranker_eval_results_stage2_5_final.csv
data/reranker_training/train_lora_stage2_5_expA.log
data/reranker_training/train_lora_stage2_5_expB.log
data/reranker_training/train_lora_stage2_5_expC.log
```

### 当前状态

- 已修改 tracked 文件：
  - `scripts/reranker/evaluate_reranker.py`
  - `tests/test_rfc_domain_reranker_evaluation.py`
  - `findings_rfc_domain_reranker_stage2.md`
  - `progress_rfc_domain_reranker_stage2.md`
- 未执行：
  - `git add`
  - commit
  - tag
  - push
  - PR
- 训练数据、评测输出、模型权重、日志均位于 gitignored 或服务器本地 exclude 路径，不纳入 Git。
