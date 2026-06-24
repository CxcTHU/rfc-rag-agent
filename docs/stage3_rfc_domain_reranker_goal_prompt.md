# RFC-DomainReranker Stage 3: RAG 主链路接入与 GLM/BGE 真实对比

## 背景

Stage 2 已完成 LoRA 微调脚本与离线评测脚本骨架。Stage 2.5 已在 GPU 服务器上用真实 synthetic query 重建数据集，并完成三组 BGE LoRA 训练实验。最优模型为：

```text
base_model=BAAI/bge-reranker-base
adapter=models/bge-reranker-base-rfc-lora
epochs=5
lora_r=32
lora_alpha=64
```

Stage 2.5 最终离线结果：

| Reranker | MRR@5 | NDCG@5 | P@1 | latency |
| --- | ---: | ---: | ---: | ---: |
| none | 0.626316 | 0.696061 | 0.350877 | 0.006 ms |
| deterministic | 0.964912 | 0.967571 | 0.929825 | 0.772 ms |
| local-lora expC GPU/cache | 0.969298 | 0.968684 | 0.947368 | 36.661 ms |

但上述评测来自 reranker 训练切分数据，不等于真实 RAG 主链路收益。Stage 3 需要正式把 BGE LoRA reranker 接入 RAG，并与既有 GLM reranker 在真实测评集上公平对比。

## 目标

将 Stage 2.5 训练出的 RFC-domain BGE LoRA reranker 作为远程 GPU 推理服务接入 RAG 主链路，并在真实 RAG 测评集上与 `none`、`deterministic`、既有 `glm-reranker` 做同候选池对比，判断是否具备替换 GLM、并行上线或仅作私有化 fallback 的资格。

## 工作环境

- 本地工作区：`G:\Codex\program\rfc-rag-agent-reranker`
- 不要在主工作区 `G:\Codex\program\rfc-rag-agent` 开发。
- 本地 Windows 没有 GPU/CUDA，不允许在本地加载 BGE 或运行真实 LoRA 推理。
- BGE LoRA 模型位于 GPU 服务器：
  - 服务器：GPU cloud host, public IP intentionally omitted from repo files
  - 服务器项目目录：`/home/ubuntu/rfc-rag-agent-reranker`
  - 模型目录：`models/bge-reranker-base-rfc-lora/`
- Stage 3 目标分支建议：`feature/rfc-domain-reranker-stage3-rag-integration-eval`
- 从已合并 Stage 2/2.5 后的最新 `origin/main` 开始，确认 tag `rfc-domain-reranker-stage-2-5-complete` 存在。

## 执行要求

1. 首先确认当前工作区必须是 `G:\Codex\program\rfc-rag-agent-reranker`；不要在 `G:\Codex\program\rfc-rag-agent` 主工作区开发。
2. 开工前阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
3. 阅读 RFC-DomainReranker Stage 1/2/2.5/3 专用规划文件：
   - `task_plan_rfc_domain_reranker.md`
   - `findings_rfc_domain_reranker.md`
   - `progress_rfc_domain_reranker.md`
   - `task_plan_rfc_domain_reranker_stage2.md`
   - `findings_rfc_domain_reranker_stage2.md`
   - `progress_rfc_domain_reranker_stage2.md`
   - `task_plan_rfc_domain_reranker_stage3.md`
   - `findings_rfc_domain_reranker_stage3.md`
   - `progress_rfc_domain_reranker_stage3.md`
4. 从最新 `origin/main` 创建/切换到 `feature/rfc-domain-reranker-stage3-rag-integration-eval`。
5. 保留用户已有改动，不重置 Git，不覆盖无关文件；无关未跟踪文件 `docs/redis_security_verification.html` 不属于本阶段产物，不要修改或纳入提交范围。
6. 不要占用根目录 `task_plan.md`、`findings.md`、`progress.md`；Stage 3 只更新 `task_plan_rfc_domain_reranker_stage3.md`、`findings_rfc_domain_reranker_stage3.md`、`progress_rfc_domain_reranker_stage3.md`。
7. 本阶段可以修改分支文件，但完成后不要 `git add`、commit、tag、push、创建 PR；必须等待用户人工核验。
8. 不让真实 GPU、Hugging Face 下载、GLM API、BGE 服务成为 CI 或本地全量测试前提；真实调用必须显式参数或本地配置。

## 核心链路

```text
真实 RAG query 集
-> 统一召回 top-N candidates
-> 冻结同候选池
-> none / deterministic / GLM reranker / remote BGE LoRA reranker
-> 排序指标对比
-> RAG sources/citations/coverage/latency 对比
-> Stage 30 quality gate
-> 形成上线决策
```

## 任务清单

### Phase 0：启动核验

- [ ] `pwd` 确认本地 worktree 是 `G:\Codex\program\rfc-rag-agent-reranker`。
- [ ] `git status -sb` 和 `git log --oneline -5` 确认状态。
- [ ] 确认 `origin/main` 包含 Stage 2.5 merge 和 tag `rfc-domain-reranker-stage-2-5-complete`。
- [ ] 创建/切换 Stage 3 分支。
- [ ] 不修改根目录三件套。

### Phase 1：GPU BGE reranker service

- [ ] SSH 登录 GPU 服务器。
- [ ] 检查：
  ```bash
  nvidia-smi
  python - <<'PY'
  import torch
  print(torch.__version__)
  print(torch.cuda.is_available())
  PY
  ```
- [ ] 确认模型目录：
  ```bash
  ls -lah models/bge-reranker-base-rfc-lora
  ```
- [ ] 新增/完善 GPU 服务脚本：
  ```bash
  python scripts/reranker/serve_lora_reranker.py \
    --model-path models/bge-reranker-base-rfc-lora \
    --host 0.0.0.0 \
    --port <port> \
    --require-cuda
  ```
- [ ] 服务提供：
  - `GET /health`
  - `POST /rerank`
  - `POST /v1/rerank`
- [ ] 服务输出兼容 OpenAI-style rerank response，至少包含 `results[index,relevance_score]`。
- [ ] 没有 CUDA 时启动失败，不允许 CPU 静默跑生产推理。

### Phase 2：RAG 端 provider 接入

- [ ] 优先复用 `OpenAICompatibleReRankingProvider`。
- [ ] 如必须新增 provider，保持 `ReRankingProvider` 协议不变。
- [ ] `.env.example` 添加占位示例：
  ```text
  # Remote RFC-domain BGE LoRA reranker; fill real URL/token only in local .env.
  # RERANKING_PROVIDER=openai-compatible
  # RERANKING_MODEL_NAME=bge-reranker-base-rfc-lora
  # RERANKING_BASE_URL=http://<gpu-reranker-host>:<port>/v1
  # RERANKING_API_KEY=
  ```
- [ ] `HybridSearchService` 远程 rerank 失败时 fail-open 回退原排序。
- [ ] latency trace 记录 `rerank_latency_ms`、provider/model、fallback/error summary。
- [ ] 本地测试默认不访问 GPU 服务。

### Phase 3：GLM vs BGE 同候选池评测

- [ ] 新增评测脚本，例如：
  ```bash
  python scripts/reranker/evaluate_rag_reranker_ab.py
  ```
- [ ] 支持输入真实评测集：
  - `data/evaluation/stage29_new_corpus_queries.csv`
  - `data/evaluation/stage41_post_import_retrieval_queries.csv`
  - Phase 51 performance cases 或等价 Agent/Brain cases
- [ ] 支持 reranker 组合：
  ```text
  none deterministic glm-reranker remote-bge-lora
  ```
- [ ] GLM 真实调用必须显式：
  ```bash
  --execute-glm
  ```
- [ ] BGE 远程调用必须显式：
  ```bash
  --remote-bge-url http://<host>:<port>/v1
  ```
- [ ] 指标：
  - MRR@5
  - NDCG@5
  - Precision@1
  - Precision@3
  - Precision@5
  - coverage_ratio
  - refusal_accuracy
  - avg_latency_ms
  - p95_latency_ms
  - error_count
  - fallback_count
- [ ] 输出：
  ```text
  data/evaluation/stage3_reranker_ab_results.csv
  data/evaluation/stage3_reranker_ab_summary.csv
  data/evaluation/stage3_reranker_candidate_snapshot.jsonl
  ```
  candidate snapshot 不得保存完整 chunk；只保存 query_id、candidate_id/hash、rank、source_type、title 摘要、score。

### Phase 4：端到端 RAG 验证

- [ ] 配置 `none`、`deterministic`、`glm-reranker`、`remote-bge-lora` 四组 RAG。
- [ ] 跑 `/chat`、`/agent/query`、`/agent/query/stream` smoke。
- [ ] 跑 Stage 29/41/51 真实评测和 Stage 30 quality score。
- [ ] 记录每组：
  - sources/citations 是否稳定
  - refusal 是否退化
  - latency 是否可接受
  - GLM 与 BGE 的质量差异
- [ ] 给出上线决策：
  - `switch_default_to_remote_bge_lora`
  - `parallel_candidate`
  - `private_fallback_only`
  - `keep_glm_reranker`

### Phase 5：测试与收尾

- [ ] 新增测试覆盖 provider payload/parse。
- [ ] 新增测试覆盖同候选池冻结。
- [ ] 新增测试覆盖 GLM 默认不调用。
- [ ] 新增测试覆盖远程 BGE 缺服务/timeout/500 的 fail-open。
- [ ] 新增测试覆盖 RAG 主链路 source 顺序受 rerank 影响。
- [ ] 运行聚焦测试。
- [ ] 更新 Stage 3 三件套。
- [ ] 更新 docs 与 Obsidian 本地知识库。
- [ ] 停在人工核验前，不提交、不打 tag、不 push、不 PR。

## 完成标准

- 远程 GPU BGE LoRA reranker service 可 health check，CUDA=True。
- RAG 主链路可通过配置调用远程 BGE reranker，本机不加载模型。
- 真实 RAG 评测集上完成 GLM reranker 与 BGE LoRA 的同候选池对比。
- 给出明确默认链路建议：替换、并行、fallback 或保留 GLM。
- 新增测试覆盖核心逻辑并通过。
- 评测输出、服务日志、模型权重、训练数据保持 gitignored 或服务器本地，不进入 Git。
- Stage 3 三件套、docs、Obsidian 更新完成。
- 最终停在用户人工核验前。

## 安全边界

- 不提交 `.env`、`.env.prod`、数据库文件、API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、受限全文、完整 chunk、训练数据、评测原始敏感数据、模型权重或服务日志。
- GLM reranker 真实 API 必须显式授权。
- BGE reranker 服务必须显式配置 URL；缺服务时不得伪造通过。
- 本地 Windows 不加载 BGE、不跑 CUDA、不下载 Hugging Face 模型。
- 评测 CSV/JSON 只保存脱敏指标、query_id、candidate hash/id、标题摘要、latency 和错误摘要。
- 不修改无关未跟踪文件 `docs/redis_security_verification.html`。
