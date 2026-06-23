# RFC-DomainReranker Stage 2.5: 数据增强与重训练

## 背景

Stage 2 已完成 LoRA 训练与离线评测骨架。首次 GPU 训练结果显示 local-lora 未超过 deterministic 关键词基线：

| Reranker | MRR@5 | NDCG@5 | P@1 |
|----------|-------|--------|-----|
| none (随机) | 0.568 | 0.584 | 0.316 |
| deterministic | **0.693** | **0.706** | **0.474** |
| local-lora (3 epoch) | 0.683 | 0.693 | 0.474 |

根因：785 条真实正例太少，500 条 synthetic 全是 dry-run 模板无语义价值。

## 目标

通过真实 synthetic 数据扩充 + 超参调优，使 local-lora 在 MRR@5 上超过 deterministic（目标 ≥ 0.72）。

## 工作环境

- 你已经在 GPU 云服务器上（`36.103.236.99`，RTX 3090 24GB）
- 项目目录：`/home/ubuntu/rfc-rag-agent-reranker`
- 分支：`feature/rfc-domain-reranker-stage2-training-eval`
- 首次训练产物在 `/home/ubuntu/rfc-rag-agent-reranker/models/bge-reranker-base-rfc-lora/`
- 不修改根目录 `task_plan.md`、`findings.md`、`progress.md`

## 任务清单

### Phase 0：启动核验

- [ ] 确认 `pwd` 是 `/home/ubuntu/rfc-rag-agent-reranker`
- [ ] `nvidia-smi` 确认 GPU 可用
- [ ] `git status -sb` 确认分支
- [ ] 阅读 `AGENT.MD`、`findings_rfc_domain_reranker_stage2.md`、`progress_rfc_domain_reranker_stage2.md`
- [ ] 确认 `.env` 存在且包含 chat_model 配置（用于 synthetic 生成）

### Phase 1：真实 Synthetic Query 生成

- [ ] 执行：
  ```bash
  python scripts/reranker/generate_synthetic_queries.py --execute --limit 500
  ```
  - 这会调用 .env 中配置的 chat_model_provider（Paratera GLM-4）为每个 sampled chunk 生成一个真实工程问题
  - 当前 500 条全是 dry_run 模板，需要用 --execute 替换为真实 LLM 生成的问题
  - 如果 API 出错或中断，用 `--resume` 断点续跑
- [ ] 验证：`data/reranker_training/synthetic_queries.jsonl` 中 status=completed 的比例应 ≥ 90%
- [ ] 抽查 3-5 条 synthetic query 的质量（应该是有意义的中文/英文工程问题，不是模板）

### Phase 2：重建数据集

- [ ] 执行：
  ```bash
  python scripts/reranker/build_dataset.py
  ```
  - 真实 synthetic 正例会纳入训练集，每个正例配 hard+easy negative
  - 预期 total_rows 从 2845 增长到 ~4000+
- [ ] 记录新的 train/val/test 行数和 label 分布
- [ ] dry-run 校验：
  ```bash
  python scripts/reranker/train_lora.py --dry-run \
    --train data/reranker_training/reranker_train.jsonl \
    --val data/reranker_training/reranker_val.jsonl
  ```

### Phase 3：GPU 训练（3 组实验）

首次训练的模型在 `models/bge-reranker-base-rfc-lora/`，先备份再开始新实验：

```bash
mv models/bge-reranker-base-rfc-lora models/bge-reranker-base-rfc-lora-run1-baseline
```

按顺序跑以下 3 组实验，每组训完立刻评测，选最优：

**实验 A：更多数据 + 默认超参 (3 epoch)**
```bash
python scripts/reranker/train_lora.py --execute \
  --train data/reranker_training/reranker_train.jsonl \
  --val data/reranker_training/reranker_val.jsonl \
  --output-dir models/bge-reranker-base-rfc-lora

python scripts/reranker/evaluate_reranker.py \
  --dataset data/reranker_training/reranker_test.jsonl \
  --rerankers none deterministic local-lora \
  --local-lora-model-path models/bge-reranker-base-rfc-lora

# 记录结果到 progress，然后备份
mv models/bge-reranker-base-rfc-lora models/bge-reranker-base-rfc-lora-expA
```

**实验 B：5 epoch**
```bash
python scripts/reranker/train_lora.py --execute --epochs 5 \
  --train data/reranker_training/reranker_train.jsonl \
  --val data/reranker_training/reranker_val.jsonl \
  --output-dir models/bge-reranker-base-rfc-lora

python scripts/reranker/evaluate_reranker.py \
  --dataset data/reranker_training/reranker_test.jsonl \
  --rerankers none deterministic local-lora \
  --local-lora-model-path models/bge-reranker-base-rfc-lora

mv models/bge-reranker-base-rfc-lora models/bge-reranker-base-rfc-lora-expB
```

**实验 C：5 epoch + LoRA r=32**
```bash
python scripts/reranker/train_lora.py --execute --epochs 5 \
  --lora-r 32 --lora-alpha 64 \
  --train data/reranker_training/reranker_train.jsonl \
  --val data/reranker_training/reranker_val.jsonl \
  --output-dir models/bge-reranker-base-rfc-lora

python scripts/reranker/evaluate_reranker.py \
  --dataset data/reranker_training/reranker_test.jsonl \
  --rerankers none deterministic local-lora \
  --local-lora-model-path models/bge-reranker-base-rfc-lora

mv models/bge-reranker-base-rfc-lora models/bge-reranker-base-rfc-lora-expC
```

### Phase 4：选最优模型

- [ ] 对比 3 组实验的 MRR@5 / NDCG@5 / P@1
- [ ] 选 MRR@5 最高的实验，把其模型复制回标准路径：
  ```bash
  cp -r models/bge-reranker-base-rfc-lora-expX models/bge-reranker-base-rfc-lora
  ```
- [ ] 最终评测确认：
  ```bash
  python scripts/reranker/evaluate_reranker.py \
    --dataset data/reranker_training/reranker_test.jsonl \
    --rerankers none deterministic local-lora \
    --local-lora-model-path models/bge-reranker-base-rfc-lora
  ```
- [ ] 保存最终的 `reranker_eval_summary.json` 和 `reranker_eval_results.csv`

### Phase 5：收尾

- [ ] 更新 `findings_rfc_domain_reranker_stage2.md`：
  - 记录 synthetic 生成质量和数量
  - 记录 3 组实验的对比表
  - 记录最优模型的超参和指标
  - 分析为什么某组效果最好
- [ ] 更新 `progress_rfc_domain_reranker_stage2.md`：
  - 记录所有命令和输出摘要
  - 记录数据量变化（old vs new）
- [ ] 运行测试确认无回归：
  ```bash
  python -m pytest tests/test_rfc_domain_reranker_export.py \
    tests/test_rfc_domain_reranker_pipeline.py \
    tests/test_rfc_domain_reranker_training.py \
    tests/test_rfc_domain_reranker_evaluation.py -q
  ```
- [ ] 停在人工核验前：不 git add / commit / tag / push / PR

## 安全边界

- 不提交 `.env`、API key、供应商原始响应、完整 chunk 或模型权重
- `data/reranker_training/` 和 `models/` 下所有目录保持 gitignored
- 真实 API / 训练调用必须显式 `--execute`
- 不修改主工作区的任何文件
- 评测输出只保留 query hash + 指标，不保存完整 passage
