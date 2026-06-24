# RFC-DomainReranker Stage 3 Progress

## 2026-06-23: candidate-pool/top-k ablation follow-up complete

Scope: reused the existing Stage 3 query set and relevance/coverage labels. No new evaluation set was created.

Script:

```text
scripts/reranker/evaluate_rag_reranker_pool_ab.py
```

Outputs:

```text
data/evaluation/stage3_reranker_pool_ab_results.csv
data/evaluation/stage3_reranker_pool_ab_summary.csv
```

Method:

- Reranker: `remote-bge-lora` only.
- Candidate recall provider: `glm`, loaded from the other local worktree `.env` into process environment only.
- Remote BGE URL for validation: `http://127.0.0.1:18091/v1` through SSH tunnel to server-local `127.0.0.1:8091`.
- Each `candidate_pool_size` was evaluated with its own strict recall call. A faster top-100-prefix approximation was rejected because `HybridSearchService`/RRF-tail results may vary with requested `top_k`.
- CSV rows contain metrics, ids, title summaries, scores, and sanitized status only; no full chunks or raw provider responses.

Strict ablation results:

```text
pool25_top5:   MRR@5=0.639035 NDCG@5=0.609474 P@1=0.605263 P@5=0.710526 coverage=0.639474 recall@pool=0.818182 avg_ms=267.244 p95_ms=279.185
pool50_top5:   MRR@5=0.684211 NDCG@5=0.634920 P@1=0.631579 P@5=0.736842 coverage=0.676754 recall@pool=0.878788 avg_ms=467.360 p95_ms=485.863
pool50_top8:   MRR@5=0.684211 NDCG@5=0.634920 P@1=0.631579 P@5=0.736842 NDCG@8=0.643854 P@8=0.736842 coverage=0.683333 recall@pool=0.878788 avg_ms=471.843 p95_ms=497.365
pool75_top8:   MRR@5=0.697368 NDCG@5=0.645577 P@1=0.631579 P@5=0.763158 NDCG@8=0.647505 P@8=0.763158 coverage=0.705263 recall@pool=0.909091 avg_ms=665.227 p95_ms=687.263
pool100_top10: MRR@5=0.692982 NDCG@5=0.632742 P@1=0.631579 P@5=0.763158 NDCG@8=0.642432 P@8=0.763158 NDCG@10=0.638724 P@10=0.763158 coverage=0.705263 recall@pool=0.909091 avg_ms=866.641 p95_ms=894.848
```

Recommendation:

- `top_k=5` is serviceable but conservative; `top_k=8` improves coverage when the pool is at least 50, with almost no extra reranker latency because rerank scores are computed over the pool.
- Increasing `candidate_pool_size` from 25 to 50 gives a clear gain; increasing to 75 gives a smaller additional gain; 100 gives no quality gain over 75 and adds latency.
- The main bottleneck is first-stage recall/candidate coverage: recall@pool rises from `0.818182` at 25 to `0.878788` at 50 and `0.909091` at 75/100.
- Recommended production default after human verification: `candidate_pool_size=75, top_k=8` for this quality-first vertical RAG system. `candidate_pool_size=50, top_k=8` remains the latency-sensitive fallback if the extra p95 reranker latency is not acceptable.
- After validation, the local SSH tunnel was closed and the GPU server was shut down normally with `shutdown -h now`; no instance deletion, disk cleanup, data deletion, or model-file deletion was performed.

## 2026-06-23: Stage 3 real BGE/GLM validation complete

Workspace: `G:\Codex\program\rfc-rag-agent-reranker`

Branch: `feature/rfc-domain-reranker-stage3-rag-integration-eval`

GPU reranker service:

- Server: GPU cloud host, accessed by SSH during validation; public IP is intentionally not recorded in repo files.
- Server workdir: `/home/ubuntu/rfc-rag-agent-reranker`
- Server-local BGE LoRA service: `127.0.0.1:8091`
- Validation SSH tunnel used: `127.0.0.1:18091 -> 127.0.0.1:8091`
- Model path on server: `models/bge-reranker-base-rfc-lora`
- Health check: `model_loaded=true`, `cuda_available=true`, `device=cuda`, `model_name=BAAI/bge-reranker-base`
- Service is bound to server localhost only; no public reranker port is opened.

Real A/B command shape:

```text
python scripts\reranker\evaluate_rag_reranker_ab.py --provider glm --rerankers none deterministic glm-reranker remote-bge-lora --execute-glm --remote-bge-url http://127.0.0.1:18091/v1 --candidate-pool-size 25 --top-k 5
```

Real A/B result over 38 queries:

```text
remote-bge-lora: MRR@5=0.639035 NDCG@5=0.609474 P@1=0.605263 P@3=0.657895 P@5=0.710526 coverage=0.639474 avg_latency_ms=269.682053 p95_latency_ms=315.543
glm-reranker:     MRR@5=0.563596 NDCG@5=0.545920 P@1=0.473684 P@3=0.657895 P@5=0.684211 coverage=0.610965 avg_latency_ms=939.337395 p95_latency_ms=2985.302
deterministic:    MRR@5=0.592982 NDCG@5=0.560869 P@1=0.552632 P@3=0.631579 P@5=0.657895 coverage=0.608772 avg_latency_ms=2.057368 p95_latency_ms=4.569
none:             MRR@5=0.432895 NDCG@5=0.385058 P@1=0.315789 P@3=0.552632 P@5=0.605263 coverage=0.527632 avg_latency_ms=0.012211 p95_latency_ms=0.016
decision=switch_default_to_remote_bge_lora
```

End-to-end route smoke with remote BGE configured through `OpenAICompatibleReRankingProvider`:

```text
POST /chat -> 200, sources=1, retrieval_mode=hybrid
POST /agent/query -> 200, sources=2, mode=tool_calling_agent
POST /agent/query/stream -> 200, content-type=text/event-stream, tail=token/metadata/done
```

Stage 30:

```text
python scripts\score_stage30_quality.py
-> overall=91.52 grade=A release_decision=pass
```

Focused verification:

```text
python -m pytest tests\test_reranking.py tests\test_hybrid_search.py tests\test_rfc_domain_reranker_stage3.py tests\test_rfc_domain_reranker_evaluation.py -q
-> 37 passed

python -m py_compile scripts\reranker\serve_lora_reranker.py scripts\reranker\evaluate_rag_reranker_ab.py
-> passed
```

Safety:

- GLM API key was loaded only from the other local worktree `.env` into process environment; it was not copied to this worktree or docs.
- Server password was used only for interactive SSH login; it was not stored in repo files.
- Stage 3 output CSV/JSONL keeps ids, hashes, ranks, source type, title summary, scores, relevance labels, metrics, latency, and sanitized status only.
- No model weights, adapter files, full chunks, raw provider responses, API keys, bearer tokens, or service logs were added.
- `docs/redis_security_verification.html` remains unrelated and untouched.

## 2026-06-23：规划初始化

工作区：`G:\Codex\program\rfc-rag-agent-reranker`

当前分支：`feature/rfc-domain-reranker-stage2-training-eval`

建议 Stage 3 目标分支：`feature/rfc-domain-reranker-stage3-rag-integration-eval`

状态：Stage 3 规划文件与 goal prompt 草案已创建；尚未切换 Stage 3 分支，尚未实现代码，尚未运行测试，尚未提交。

## 用户新增要求

- Stage 3 需要正式把 RFC-domain reranker 模型嵌入 RAG。
- 需要进行真实测评集测试。
- 本机没有 GPU/CUDA。
- BGE LoRA 模型挂载在云端 GPU 服务器。
- 真实测评必须与之前的 GLM reranker 对比二者效果。

## 已形成规划

- Stage 3 不在本地 Windows 加载 BGE，不要求本地 CUDA。
- GPU 服务器负责运行 BGE LoRA HTTP reranker 服务。
- 本地 RAG App 通过 `ReRankingProvider` HTTP client 调用远端服务。
- 评测矩阵固定为：

```text
none
deterministic
glm-reranker
remote-bge-lora
```

- 评测必须使用同候选池，避免召回波动污染 reranker 对比。
- GLM reranker 调用必须显式授权，不进入 CI 或本地全量测试前提。
- remote BGE 服务缺失或失败时必须输出 skipped/error 或 fail-open，不得伪造通过。

## 当前文件状态

本轮新增规划文件：

```text
task_plan_rfc_domain_reranker_stage3.md
findings_rfc_domain_reranker_stage3.md
progress_rfc_domain_reranker_stage3.md
docs/stage3_rfc_domain_reranker_goal_prompt.md
```

保持不动：

```text
task_plan.md
findings.md
progress.md
docs/redis_security_verification.html
```

## 待开工事项

1. 用户确认 Stage 3 规划与 prompt。
2. 从最新 `origin/main` 创建 Stage 3 分支。
3. SSH 核验 GPU 服务器模型服务条件。
4. 实现 GPU reranker service 与 RAG 端 provider 接入。
5. 实现同候选池 GLM vs BGE 评测脚本。
6. 跑聚焦测试与真实测评。
7. 更新 Stage 3 三件套、docs 与 Obsidian，停在人工核验前。

## 未执行

- 未切换分支。
- 未修改业务代码。
- 未运行真实 GLM API。
- 未访问 GPU 服务器。
- 未运行测试。
- 未 `git add`。
- 未 commit、tag、push 或 PR。

## 安全说明

本规划未写入 API key、Bearer token、服务器密码、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk、受限全文、训练数据或模型权重。

## 2026-06-23：本地接入骨架开发

工作区：`G:\Codex\program\rfc-rag-agent-reranker`

当前分支：`feature/rfc-domain-reranker-stage3-rag-integration-eval`

起点：`origin/main -> 49cabbba Merge RFC-DomainReranker Stage 2/2.5`

tag：`rfc-domain-reranker-stage-2-5-complete -> 49cabbba`

### 已完成

- 按 Stage 3 prompt 设置 Codex goal。
- 确认当前目录为 reranker worktree，不在主工作区开发。
- 执行 `git fetch origin --prune`。
- 从 `origin/main` 创建/切换到 `feature/rfc-domain-reranker-stage3-rag-integration-eval`。
- 保留无关未跟踪文件 `docs/redis_security_verification.html`，未修改、未纳入。
- 未修改根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 新增 `scripts/reranker/serve_lora_reranker.py`：
  - GPU 服务器 HTTP service；
  - `GET /health`；
  - `POST /rerank`；
  - `POST /v1/rerank`；
  - OpenAI-style `results[index,relevance_score]`；
  - `--require-cuda` 下无 CUDA 直接失败。
- 更新 `app/services/retrieval/reranking.py`：
  - OpenAI-compatible reranker 支持私有无 token 服务；
  - 保留 model/base_url 校验；
  - 增加 `remote-bge-lora` / `bge-lora` / `rfc-bge-lora` provider alias。
- 更新 `app/services/retrieval/hybrid_search.py`：
  - 保持 RuntimeError fail-open；
  - latency trace 记录 reranking provider/model/fallback/error。
- 更新 `.env.example` 远程 BGE LoRA placeholder。
- 新增 `scripts/reranker/evaluate_rag_reranker_ab.py`：
  - 冻结同候选池；
  - 支持 `none`、`deterministic`、`glm-reranker`、`remote-bge-lora`；
  - 默认使用 deterministic embedding 召回，避免默认命令触发真实 embedding；
  - 默认纳入 Stage 29、Stage 41 与 Phase 51 representative cases，可用 `--no-include-phase51-cases` 关闭；
  - 支持 `--limit` 做本地 smoke；
  - `glm-reranker` 必须 `--execute-glm`；
  - `remote-bge-lora` 必须 `--remote-bge-url`；
  - 输出 Stage 3 results/summary/candidate snapshot；
  - snapshot 不保存完整 chunk。
- 新增/补充测试：
  - `tests/test_rfc_domain_reranker_stage3.py`
  - `tests/test_reranking.py`
  - `tests/test_hybrid_search.py`
- 更新普通文档：
  - `docs/progress.md`
  - `docs/architecture.md`
  - `docs/data_sources.md`

### 已运行验证

```text
python -m pytest tests\test_reranking.py tests\test_hybrid_search.py tests\test_rfc_domain_reranker_stage3.py -q
-> 27 passed

python -m pytest tests\test_rfc_domain_reranker_export.py tests\test_rfc_domain_reranker_pipeline.py tests\test_rfc_domain_reranker_training.py tests\test_rfc_domain_reranker_evaluation.py tests\test_rfc_domain_reranker_stage3.py -q
-> 30 passed

python -m pytest tests\test_reranking.py tests\test_hybrid_search.py tests\test_rfc_domain_reranker_stage3.py tests\test_rfc_domain_reranker_evaluation.py -q
-> 37 passed

python -m py_compile scripts\reranker\serve_lora_reranker.py scripts\reranker\evaluate_rag_reranker_ab.py
-> passed

python scripts\reranker\evaluate_rag_reranker_ab.py --provider deterministic --rerankers none deterministic --candidate-pool-size 5 --top-k 5 --limit 1 --no-include-phase51-cases
-> completed=1/1 for none and deterministic, decision=remote_bge_not_evaluated

rg sensitive scan over Stage 3 source/docs/tests/output
-> only field names, placeholder/test keys, and safety-rule text matched; no real secret/raw response detected
```

### 未执行

- SSH 非交互探测失败：GPU server returned `Permission denied (publickey,password)` without an interactive credential.
- 未运行 `nvidia-smi` / CUDA server health。
- 未启动真实 `serve_lora_reranker.py`。
- 未调用真实 GLM reranker。
- 未调用远程 BGE reranker。
- 已生成本地 deterministic smoke `stage3_reranker_ab_results.csv` / summary / snapshot；尚未生成真实 GLM/BGE 对比输出。
- 未运行 Stage 30 quality score。
- 未运行 `/chat`、`/agent/query`、`/agent/query/stream` 端到端 smoke。
- 未 `git add`。
- 未 commit、tag、push 或 PR。

### 下一步建议

1. 在 GPU 服务器 `/home/ubuntu/rfc-rag-agent-reranker` 启动：

```bash
python scripts/reranker/serve_lora_reranker.py \
  --model-path models/bge-reranker-base-rfc-lora \
  --host 0.0.0.0 \
  --port <port> \
  --require-cuda
```

2. 核验 `GET /health`，确认 `cuda_available=true`。
3. 本地或服务器端显式运行同候选池真实对比：

```bash
python scripts/reranker/evaluate_rag_reranker_ab.py \
  --rerankers none deterministic glm-reranker remote-bge-lora \
  --execute-glm \
  --remote-bge-url http://<gpu-reranker-host>:<port>/v1
```

4. 再跑 Stage 30 与端到端 smoke，形成 `switch_default_to_remote_bge_lora` / `parallel_candidate` / `private_fallback_only` / `keep_glm_reranker` 结论。
