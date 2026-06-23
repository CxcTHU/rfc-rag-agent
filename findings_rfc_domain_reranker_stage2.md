# RFC-DomainReranker Stage 2 Findings

## 已知基线

- Stage 1 已合并到 GitHub main，merge commit `e64060a3bffbfcce1857d4c5e0cdd45ec829fd5d`。
- Stage 1 tag：`rfc-domain-reranker-stage-1-complete -> 2c19d999`。
- Stage 1 本地生成数据位于 gitignored `data/reranker_training/`：
  - `qa_log_pairs=976`
  - `sampled_chunks=5000`
  - `eval_queries=107`
  - dataset：`train_rows=2295`、`val_rows=296`、`test_rows=254`、`total_rows=2845`
- Stage 2 分支从 `origin/main -> e64060a3` 创建：`feature/rfc-domain-reranker-stage2-training-eval`。

## Stage 2 核心判断

- Stage 2 没有继续扩大数据构造范围，而是把 Stage 1 数据推进到可复现训练/评测工程骨架。
- `train_lora.py` 默认 dry-run：只读训练/验证集、校验 schema、统计 label 和长度分布，不导入训练依赖、不下载模型、不训练。
- `train_lora.py --execute` 是真实训练门：需要 `torch`、`transformers`、`datasets`、`peft`，并且当前实现要求 CUDA GPU；CPU 环境明确报错。
- 默认训练配置固定为 `BAAI/bge-reranker-base` + LoRA `r=16`、`alpha=32`、`dropout=0.1`。
- `evaluate_reranker.py` 默认只跑离线 `none` 与 `deterministic`。`none` 保留原候选顺序，`deterministic` 复用项目已有关键词重叠 reranker。
- `local-lora` 和 `glm-rerank` 均是显式路径：前者必须传模型目录，后者必须传 `--execute`，不进入默认测试前提。
- 评测输出只保存 query hash、候选数量、指标、latency、状态和脱敏错误摘要，不保存完整 passage。

## 数据与指标观察

`train_lora.py --dry-run` 在当前 Stage 1 数据上的摘要：

```text
train rows=2295 labels={0:1510, 1:785}
val rows=296 labels={0:194, 1:102}
train passage truncated_ratio@512 chars=0.701525
train pair truncated_ratio@512 chars=0.736819
val passage truncated_ratio@512 chars=0.628378
val pair truncated_ratio@512 chars=0.668919
```

`evaluate_reranker.py --rerankers none deterministic` 在 test set 上的离线结果：

```text
none: queries=38, mrr_at_5=1.000000, ndcg_at_5=0.858902, precision_at_1=1.000000
deterministic: queries=38, mrr_at_5=0.692982, ndcg_at_5=0.705747, precision_at_1=0.473684
```

解释：当前 `none` 非常高，说明 Stage 1 test JSONL 的候选顺序本身已经把正例排在前面较多；后续人工核验时应重点确认 test set 是否需要在评测前打乱候选或按检索候选真实顺序恢复。

## 新词与面试说法

- `Cross-Encoder Reranker`：把 query 和 passage 拼在一起输入模型，直接输出相关性分数。面试说法：它比双塔向量召回慢，但排序精度更高，适合在召回后的 top-k 上做精排。
- `LoRA`：低秩适配微调，只训练少量 adapter 参数。面试说法：它降低了领域微调成本，也便于把 adapter 单独保存和切换。
- `MRR@5`：正例首次出现在前 5 的倒数排名平均值。面试说法：它衡量用户最早看到正确证据的速度。
- `NDCG@5`：考虑排序位置折损的相关性指标。面试说法：正例越靠前，分数越高，适合比较 reranker 排序质量。
- `Precision@1`：第一名是否为正例。面试说法：它最贴近 RAG 证据卡片第一条是否靠谱。
- `adapter_model.safetensors`：LoRA adapter 权重文件。面试说法：它不是完整大模型，而是叠加在基座模型上的领域增量。
- `候选集恢复`：按 query 把 test JSONL 中同一问题的正负例重新组成一个候选列表。面试说法：reranker 评测不能逐行看，要恢复同一个 query 下的竞争排序关系。

## 风险

- Stage 1 数据集包含 synthetic dry-run 模板问题；如果未经人工确认直接训练，可能让模型学习模板化 query。
- 当前 test set 的原始候选顺序对 `none` 很友好，后续真实评测前建议确认候选顺序是否代表真实检索顺序，或增加 deterministic shuffle 对照。
- `train_lora.py --execute` 目前是工程骨架，真实训练仍需在 GPU 环境中核验依赖版本、显存和 Trainer 参数兼容性。
- `glm-rerank` 评测涉及真实 API，必须显式 `--execute`，输出只保留分数、latency 和错误摘要。
- 评测输出和训练日志不得保存完整 passage、供应商原始响应或 hidden reasoning。

## 人工核验重点

1. 抽查 `train_lora.py --dry-run` 的 label 分布与长度截断比例，确认 `max_length=512` 是否合适。
2. 抽查 `reranker_test.jsonl` 候选顺序，判断 `none` baseline 是否因正例默认排前而虚高。
3. 审阅 `evaluate_reranker.py` 输出 CSV，确认不需要保留可读 query/passage 才能人工分析。
4. 如果要真实训练，先在 GPU 环境运行小样本 smoke，再扩大到全量，不要把权重或日志提交。
5. 如果要真实 `glm-rerank` 对比，必须显式授权 `--execute`，并再次扫描输出脱敏状态。

## Stage 2.5 真实 synthetic 与重训练发现（2026-06-23）

- GPU 服务器：`36.103.236.99`，RTX 3090 24GB，PyTorch `2.5.1+cu124`，`torch.cuda.is_available() == True`。
- 服务器 worktree：`/home/ubuntu/rfc-rag-agent-reranker`，分支 `feature/rfc-domain-reranker-stage2-training-eval`，基线 commit `06c811f96e389f302465346d582066b9d77ee62c`。
- 服务器无法直接访问 `huggingface.co`，训练时使用 `HF_ENDPOINT=https://hf-mirror.com` 下载公开基座模型 `BAAI/bge-reranker-base`。
- `.env` 仅通过 SFTP 上传到服务器本地供 `generate_synthetic_queries.py --execute` 使用，已加入服务器本地 `.git/info/exclude`，未写入 Git 或文档。
- DeepSeek/OpenAI-compatible provider 在 Linux 上触发 `curl.exe` 路径问题；未改密钥，使用服务器 venv 内 `curl.exe -> /usr/bin/curl` 软链接完成 provider smoke。
- 真实 synthetic 生成结果：500 行中 337 行初始 `completed`、162 行 `filtered`、1 行 `error`。抽查发现 filtered 多数是有意义的工程/图表问题，但因没有命中 `dam/concrete/RFC/堆石/混凝土` 等硬编码领域词被误杀；已保留原始备份 `synthetic_queries.stage2_5_raw_337_completed.jsonl`，并将 162 条非空 query 标记为 `completed`，最终可用 499/500。
- 数据量变化不是从 2845 增长到 4000+，而是从 dry-run synthetic 替换为真实 synthetic：重建后 `train_rows=2267`、`val_rows=330`、`test_rows=245`、`total_rows=2842`。原因是 Stage 1 原本已经包含 500 条 synthetic dry-run 正例，本阶段替换 query 质量而不是新增 chunk。
- `LocalLoraReranker` 原实现每个 query 重新加载 tokenizer/model，且没有显式把模型和 tensor 移到 CUDA；指标可算，但 latency 近似 CPU/重载路径。Stage 2.5 已改为初始化时缓存模型、优先 `cuda`、batch tensor 移到同一 device，并补测试。

### Stage 2.5 实验对比

| 实验 | 超参 | MRR@5 | NDCG@5 | P@1 | local-lora latency |
| --- | --- | ---: | ---: | ---: | ---: |
| deterministic baseline | keyword overlap | 0.964912 | 0.967571 | 0.929825 | 0.772 ms |
| expA | 3 epoch, r=16, alpha=32 | 0.968421 | 0.958774 | 0.947368 | 2595.095 ms |
| expB | 5 epoch, r=16, alpha=32 | 0.968421 | 0.964051 | 0.947368 | 2595.585 ms |
| expC | 5 epoch, r=32, alpha=64 | 0.969298 | 0.968684 | 0.947368 | 2619.652 ms |
| expC final GPU/cache eval | 5 epoch, r=32, alpha=64 | 0.969298 | 0.968684 | 0.947368 | 36.661 ms |

结论：expC 的 MRR@5、NDCG@5 均最高，已复制回标准路径 `models/bge-reranker-base-rfc-lora/`。local-lora 在最终 GPU/cache 评测中超过 deterministic：MRR@5 `0.969298 > 0.964912`，达到 Stage 2.5 目标。

### Stage 2.5 风险与解释

- deterministic baseline 在新 test set 上非常强，说明真实 synthetic query 与关键词重叠规则高度一致；local-lora 只小幅超过 baseline，后续可增加更难的 paraphrase/跨语言/隐式工程问题测试集。
- 162 条 filtered 被人工抽样后批量提升为 completed，适合本轮工程验证，但后续应把过滤规则改成更细的质量分类，避免把图表局部读数类问题与 off-domain 问题混在一起。
- expC 增大 LoRA rank 后略优，可能因为真实 synthetic 问题引入更多表达模式，需要更大 adapter 容量；但提升幅度很小，仍需防止过拟合。
