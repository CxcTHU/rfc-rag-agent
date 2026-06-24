# RFC-DomainReranker Stage 3 任务计划

## 2026-06-23 Completion Audit

Stage 3 implementation and real validation are complete before user human verification.

Follow-up pool/top-k ablation audit:

- [x] Reused the existing Stage 3 queries and relevance/coverage labels.
- [x] Added `scripts/reranker/evaluate_rag_reranker_pool_ab.py` without changing the original Stage 3 A/B script.
- [x] Evaluated `remote-bge-lora` for `25/5`, `50/5`, `50/8`, `75/8`, and `100/10`.
- [x] Wrote sanitized outputs to `data/evaluation/stage3_reranker_pool_ab_results.csv` and `data/evaluation/stage3_reranker_pool_ab_summary.csv`.
- [x] Added @8/@10 metrics where relevant and `recall_at_candidate_pool`.
- [x] Confirmed strict independent candidate recall per pool; did not use top-100 prefix approximation for final results.
- [x] Recommended quality-first production default: `candidate_pool_size=75, top_k=8`.
- [x] Kept latency-sensitive fallback: `candidate_pool_size=50, top_k=8`.
- [x] No `git add`, commit, tag, push, or PR was performed.

Pool/top-k ablation summary:

```text
25/5:   MRR@5=0.639035 NDCG@5=0.609474 P@5=0.710526 coverage=0.639474 recall@pool=0.818182 p95_ms=279.185
50/8:   MRR@5=0.684211 NDCG@5=0.634920 P@5=0.736842 coverage=0.683333 recall@pool=0.878788 p95_ms=497.365
75/8:   MRR@5=0.697368 NDCG@5=0.645577 P@5=0.763158 coverage=0.705263 recall@pool=0.909091 p95_ms=687.263
100/10: MRR@5=0.692982 NDCG@5=0.632742 P@5=0.763158 coverage=0.705263 recall@pool=0.909091 p95_ms=894.848
```

Completed audit:

- [x] GPU server BGE LoRA service is running with CUDA at server-local `127.0.0.1:8091`.
- [x] Local machine calls the remote service through SSH tunnel `127.0.0.1:18091`.
- [x] Local RAG code uses HTTP reranking only; it does not load BGE, LoRA, torch, transformers, or CUDA locally.
- [x] OpenAI-compatible reranker supports tokenless localhost/private services and aliases `remote-bge-lora`, `bge-lora`, `rfc-bge-lora`.
- [x] Hybrid search records provider/model/fallback/error trace and keeps fail-open behavior.
- [x] Frozen-candidate A/B completed for `none`, `deterministic`, `glm-reranker`, and `remote-bge-lora`.
- [x] Real GLM call was explicitly enabled with `--execute-glm`; remote BGE call was explicitly configured with `--remote-bge-url`.
- [x] Final decision is `switch_default_to_remote_bge_lora`.
- [x] `/chat`, `/agent/query`, and `/agent/query/stream` smoke passed with remote BGE configured.
- [x] Stage 30 remains `91.52 / A / pass`.
- [x] Focused tests and py_compile passed.
- [x] Security boundary checked: no secrets, raw provider responses, full chunks, model weights, or service logs added.
- [x] No `git add`, commit, tag, push, or PR was performed.

Final A/B summary:

```text
remote-bge-lora: MRR@5=0.639035 NDCG@5=0.609474 P@1=0.605263 P@5=0.710526 avg_latency_ms=269.682 p95_latency_ms=315.543
glm-reranker:     MRR@5=0.563596 NDCG@5=0.545920 P@1=0.473684 P@5=0.684211 avg_latency_ms=939.337 p95_latency_ms=2985.302
decision=switch_default_to_remote_bge_lora
```

## Goal

在独立 worktree `G:\Codex\program\rfc-rag-agent-reranker` 中推进 RFC-DomainReranker Stage 3：将 Stage 2.5 训练出的 RFC-domain BGE LoRA reranker 作为 GPU 服务器远程推理服务接入正式 RAG 主链路，并在真实 RAG 测评集上与 `none`、`deterministic`、既有 GLM reranker 做同候选池对比，判断 BGE LoRA 是否具备替换、并行上线或仅作 fallback 的资格。

本机没有 GPU/CUDA，禁止在本地 Windows 主机加载 BGE 或运行真实 LoRA 推理。BGE 基座与 LoRA adapter 仅在 GPU 服务器上加载；本地只做 HTTP client、配置、测试替身、评测调度和文档。

建议目标分支：`feature/rfc-domain-reranker-stage3-rag-integration-eval`

建议起点：已合并 Stage 2/2.5 后的 `origin/main`，tag `rfc-domain-reranker-stage-2-5-complete`。

## Stage 3 范围

- 在 GPU 服务器上托管 `BAAI/bge-reranker-base` + Stage 2.5 最优 LoRA adapter。
- 提供兼容现有 OpenAI-style rerank client 的 HTTP `/rerank` 推理服务。
- 本地 RAG App 通过现有 `ReRankingProvider` 边界调用远端 BGE，不直接依赖 CUDA、torch、transformers 或 Hugging Face 下载。
- 将远端 BGE 接入 `HybridSearchService` / `HybridRrfTailSearchService` / Brain / Agent 主链路，并验证 `/chat`、`/agent/query`、`/agent/query/stream` 的实际排序影响。
- 构建真实 RAG reranker A/B 评测：冻结同一候选池，对比 `none`、`deterministic`、`glm-reranker`、`remote-bge-lora`。
- 保留 GLM reranker 作为质量对照，真实 GLM API 调用必须显式授权，不进入 CI 或本地全量测试前提。
- 不提交模型权重、训练数据、评测原始敏感数据、API key、Bearer token、供应商原始响应、完整 chunk 或受限全文。

## Phase 顺序

### Phase 0：启动核验与分支基线

- [x] 确认当前工作区是 `G:\Codex\program\rfc-rag-agent-reranker`，不是主工作区 `G:\Codex\program\rfc-rag-agent`。
- [x] 读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- [x] 读取 RFC-DomainReranker Stage 1/2/2.5 三件套与本 Stage 3 三件套。
- [x] 运行 `git status -sb`、`git log --oneline -5`，确认用户已有改动；保留无关未跟踪文件 `docs/redis_security_verification.html`。
- [x] 从最新 `origin/main` 创建/切换到 `feature/rfc-domain-reranker-stage3-rag-integration-eval`。
- [x] 确认 `origin/main` 包含 tag `rfc-domain-reranker-stage-2-5-complete` 指向的 Stage 2.5 merge commit。
- [x] 不修改根目录 `task_plan.md`、`findings.md`、`progress.md`。

### Phase 1：GPU 服务器 BGE reranker 服务化

- [ ] SSH 登录 GPU 服务器，确认 `/home/ubuntu/rfc-rag-agent-reranker`、CUDA、PyTorch、模型目录可用。
- [ ] 确认 Stage 2.5 最优模型在 `models/bge-reranker-base-rfc-lora/`，且包含 adapter/tokenizer/config 必要文件。
- [x] 新增或完善 `scripts/reranker/serve_lora_reranker.py`，提供本地 GPU HTTP 服务。
- [x] `GET /health` 返回安全状态：model_loaded、cuda_available、device、model_name、model_path、max_length，不返回 key 或原始权重路径以外的敏感信息。
- [x] `POST /rerank` 或 `/v1/rerank` 接收 `model`、`query`、`documents`、`top_n`，返回 `results[index,relevance_score,document?]`。
- [x] 服务启动时要求 CUDA 可用；如果没有 CUDA，明确报错，不允许 CPU 静默跑生产推理。
- [x] 服务日志只记录计数、耗时、错误摘要，不记录完整候选文本、完整 query、供应商响应或 hidden thought。

### Phase 2：本地 RAG 端远程 reranker client 接入

- [x] 优先复用 `OpenAICompatibleReRankingProvider`；如服务契约需要扩展，新增独立 provider，例如 `RemoteBgeReRankingProvider`，保持 `ReRankingProvider` Protocol 不破坏。
- [x] `.env.example` 增加远程 BGE reranker 示例配置，不写真实 IP、token 或密码。
- [x] 在 `HybridSearchService._rerank_results()` 保持 fail-open：远程 reranker 失败时回退融合排序，不使 `/chat` 或 `/agent/query` 失败。
- [x] 在 latency trace 或安全输出中记录 reranker provider/model、`rerank_latency_ms`、fallback/error summary。
- [x] 确认默认测试仍强制 deterministic/disabled，不访问远程 GPU 服务。
- [x] 明确 `HybridRrfTailSearchService` 的 stable head 与 tail 填充策略下，远程 reranker 影响的是 hybrid head 排序；如需全候选 rerank，必须通过评测证明收益。

### Phase 3：同候选池 RAG reranker 对比评测

- [x] 新增 `scripts/reranker/evaluate_rag_reranker_ab.py` 或等价脚本。
- [x] 从真实 RAG query 集构造评测输入，至少覆盖：
  - `data/evaluation/stage29_new_corpus_queries.csv`
  - `data/evaluation/stage41_post_import_retrieval_queries.csv`
  - Phase 51 performance cases 或等价 Agent/Brain 查询集
- [x] 先统一召回 top-N candidates，并冻结候选池；同一 query 的同一组 candidates 分别送入四类 reranker：
  - `none`
  - `deterministic`
  - `glm-reranker`
  - `remote-bge-lora`
- [x] GLM reranker 调用必须显式 `--execute-glm` 或 `--execute`，不得成为默认本地/CI 前提。
- [x] remote BGE 调用必须显式传 `--remote-bge-url` 或通过本地 `.env` 配置，缺服务时输出 `skipped/error`，不得伪造成 pass。
- [x] 评测指标至少包含：MRR@5、NDCG@5、Precision@1、Precision@3、Precision@5、coverage_ratio、refusal_accuracy、avg/p95 latency、error_count、fallback_count。
- [x] 输出只写 `data/evaluation/` 或 `data/reranker_training/` 下的脱敏 CSV/JSON，不保存完整 chunk、完整候选正文、GLM 原始响应或 BGE logits 明细。
- [x] 新增 `--limit` 和 deterministic 默认召回，支持本地轻量 smoke 且默认不触发真实 provider。
- [x] 本地 smoke 生成 `stage3_reranker_ab_results.csv` / summary / candidate snapshot，验证输出链路；该 smoke 不是真实 GLM/BGE 对比。

### Phase 4：端到端 RAG 真实链路核验

- [ ] 在本地或云端 RAG App 配置 `remote-bge-lora`，运行 `/chat`、`/agent/query`、`/agent/query/stream` smoke。
- [ ] 对比 `reranking=off`、`deterministic`、`glm-reranker`、`remote-bge-lora` 的端到端结果。
- [ ] 跑 `scripts/score_stage30_quality.py`，确认 Stage 30 总分不退化，目标保持 `91.52 / A / pass` 或说明差异。
- [ ] 跑 Stage 29/41/51 相关评测脚本或新增 Stage 3 汇总脚本，形成统一决策表。
- [ ] 若 BGE LoRA 质量低于 GLM reranker，不默认替换；记录为私有化/成本/离线候选。
- [ ] 若 BGE LoRA 与 GLM 接近或超过 GLM，结合 latency、成本、稳定性和可运维性给出上线建议。

### Phase 5：测试与安全扫描

- [x] 新增测试覆盖远程 BGE HTTP payload、响应解析、排序恢复、top_n 截断。
- [x] 新增测试覆盖 GLM provider 默认不调用，必须显式 `--execute`。
- [x] 新增测试覆盖远程 BGE 缺 URL、服务 500、timeout、格式错误时的清晰报错或 fail-open。
- [x] 新增测试覆盖同候选池冻结逻辑，确保四个 reranker 对同一候选集评测。
- [x] 新增测试覆盖 RAG 主链路中 rerank 排序确实影响最终 sources 顺序。
- [x] 聚焦测试通过；必要时运行相关全量或阶段回归。
- [x] 扫描新增源码/文档/测试，确认无 `.env`、API key、Bearer token、供应商 raw response、`raw_response`、`reasoning_content`、完整 chunk、模型权重。

### Phase 6：文档、Obsidian 与人工核验前收尾

- [x] 更新 `task_plan_rfc_domain_reranker_stage3.md`、`findings_rfc_domain_reranker_stage3.md`、`progress_rfc_domain_reranker_stage3.md`。
- [x] 更新 `docs/architecture.md`、`docs/data_sources.md`、`docs/progress.md` 的 Stage 3 摘要；不写入敏感内容。
- [x] 按 Obsidian 阶段汇报格式更新本地 `obsidian-vault/`，但不提交该 gitignored 目录。
- [x] 明确模型/评测/日志文件是否仍在 gitignored 目录。
- [x] 停在用户人工核验前：不 `git add`、不 commit、不 tag、不 push、不创建 PR。

## 完成标准

- [ ] GPU 服务器提供可用的 BGE LoRA reranker HTTP 服务，CUDA=True，health 可核验。
- [ ] 本地 RAG 主链路可以通过配置调用远程 BGE reranker，本机不加载 BGE 模型。
- [ ] 同一真实候选池上完成 `none`、`deterministic`、`glm-reranker`、`remote-bge-lora` 对比。
- [ ] 端到端 RAG 评测证明 BGE LoRA 相对 GLM 的质量、延迟、成本和可运维结论。
- [ ] GLM reranker 和远程 BGE 调用均不成为 CI 或本地全量测试前提。
- [ ] 新增测试覆盖核心契约并通过。
- [ ] 安全边界扫描通过，无敏感内容、完整 chunk、模型权重入 Git。
- [ ] Stage 3 三件套与 goal prompt 更新完成，停在人工核验前。

## 安全边界

- 不提交 `.env`、`.env.prod`、数据库文件、API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、受限全文、完整 chunk、训练数据、评测原始敏感数据、模型权重或服务日志。
- 真实 GLM API 调用必须显式授权。
- 远程 BGE 服务调用必须显式配置 URL；缺服务时输出 skipped/error，不伪造结果。
- 本地 Windows 不做 CUDA 推理，不下载 BGE 基座，不加载 LoRA 权重。
- 评测输出只保留 query id、候选 id/hash、标题摘要、指标、latency、状态和脱敏错误。
- 不修改或纳入无关文件 `docs/redis_security_verification.html`。
