# RFC-DomainReranker Stage 3 Findings

## 2026-06-23 pool/top-k ablation finding

The original Stage 3 `remote-bge-lora` score was partially limited by candidate-pool size. Increasing the first-stage pool from 25 to 50 improves all main @5 quality metrics, and 75 improves them further. Increasing to 100 does not improve quality over 75 and only adds latency.

Strict results:

```text
25/5:   MRR@5=0.639035 NDCG@5=0.609474 P@1=0.605263 P@5=0.710526 coverage=0.639474 recall@pool=0.818182 p95_ms=279.185
50/5:   MRR@5=0.684211 NDCG@5=0.634920 P@1=0.631579 P@5=0.736842 coverage=0.676754 recall@pool=0.878788 p95_ms=485.863
50/8:   MRR@5=0.684211 NDCG@5=0.634920 P@1=0.631579 P@5=0.736842 NDCG@8=0.643854 P@8=0.736842 coverage=0.683333 p95_ms=497.365
75/8:   MRR@5=0.697368 NDCG@5=0.645577 P@1=0.631579 P@5=0.763158 NDCG@8=0.647505 P@8=0.763158 coverage=0.705263 recall@pool=0.909091 p95_ms=687.263
100/10: MRR@5=0.692982 NDCG@5=0.632742 P@1=0.631579 P@5=0.763158 NDCG@10=0.638724 P@10=0.763158 coverage=0.705263 recall@pool=0.909091 p95_ms=894.848
```

Interpretation:

- `top_k=5` is enough for the @5 ranking metrics, but it is conservative for final evidence coverage.
- Moving to `top_k=8` mainly improves coverage/evidence breadth, not MRR@5, because the top-5 order is unchanged for a fixed candidate pool.
- The recall bottleneck is real: recall@candidate_pool improves from `0.818182` to `0.878788` to `0.909091` as the pool grows from 25 to 50 to 75.
- `candidate_pool_size=100` is not justified by this run; it has the same recall@pool and coverage as 75 with worse latency and slightly lower NDCG.

Recommendation: use `candidate_pool_size=75, top_k=8` as the production default after human verification because this system is a quality-first vertical RAG knowledge base. Keep `candidate_pool_size=50, top_k=8` as the latency-sensitive fallback. Do not default to 100 without recall-side optimization.

## 2026-06-23 final validation finding

The Stage 2.5 RFC-domain BGE LoRA reranker is viable as the preferred Stage 3 reranker candidate for the current RAG evaluation set.

Deployment finding:

- The BGE LoRA service is running on the GPU server at server-local `127.0.0.1:8091`.
- Local evaluation and route smoke use SSH tunnel `127.0.0.1:18091 -> 127.0.0.1:8091`.
- `/health` reports `model_loaded=true`, `cuda_available=true`, and `device=cuda`.
- The service is localhost-bound on the server; no public reranker port is exposed.

Quality and latency finding over 38 frozen-candidate RAG queries:

```text
remote-bge-lora: MRR@5=0.639035 NDCG@5=0.609474 P@1=0.605263 P@5=0.710526 coverage=0.639474 avg_latency_ms=269.682 p95_latency_ms=315.543
glm-reranker:     MRR@5=0.563596 NDCG@5=0.545920 P@1=0.473684 P@5=0.684211 coverage=0.610965 avg_latency_ms=939.337 p95_latency_ms=2985.302
deterministic:    MRR@5=0.592982 NDCG@5=0.560869 P@1=0.552632 P@5=0.657895 coverage=0.608772 avg_latency_ms=2.057
none:             MRR@5=0.432895 NDCG@5=0.385058 P@1=0.315789 P@5=0.605263 coverage=0.527632
```

Decision: `switch_default_to_remote_bge_lora`.

Route finding:

- `/chat` with hybrid retrieval and remote BGE reranking returned 200 with sources.
- `/agent/query` with `tool_calling_agent` and remote BGE reranking returned 200 with sources.
- `/agent/query/stream` returned SSE ending in `metadata` and `done`.

Regression finding:

- Stage 30 remains `overall=91.52 grade=A release_decision=pass`.
- Focused Stage 3 regression remains `37 passed`.

Safety finding:

- The real GLM key was loaded from the other local worktree `.env` only into process environment.
- The server password was not written to repository files.
- Stage 3 evaluation outputs are sanitized and do not include full chunks, raw provider responses, secrets, or model weights.

## 背景判断

- Stage 2/2.5 已完成 LoRA 训练、真实 synthetic query 替换、三组 GPU 实验与最终评测。
- Stage 2.5 最优模型为 expC：`BAAI/bge-reranker-base` + LoRA `r=32`、`alpha=64`、`epochs=5`。
- Stage 2.5 最终 GPU/cache 离线评测：

```text
none:          MRR@5=0.626316 NDCG@5=0.696061 P@1=0.350877 avg_latency_ms=0.006491
deterministic: MRR@5=0.964912 NDCG@5=0.967571 P@1=0.929825 avg_latency_ms=0.772000
local-lora:    MRR@5=0.969298 NDCG@5=0.968684 P@1=0.947368 avg_latency_ms=36.661228
```

- Stage 2.5 的评测集是 reranker 训练切分出的 `reranker_test.jsonl`，可证明模型在训练任务格式上的排序能力，但不能直接等价为线上 RAG 效果。
- Stage 3 必须进入真实 RAG 链路，以 Stage 29/30/41/51 等真实问答/检索评测集衡量最终收益。

## 当前代码接入点

- `app/services/retrieval/reranking.py` 定义 `ReRankingProvider`、`DeterministicReRankingProvider`、`OpenAICompatibleReRankingProvider` 和 `create_reranking_provider()`。
- `app/services/retrieval/hybrid_search.py` 已支持在候选融合后调用 `reranking_provider.rerank()`。
- `app/services/retrieval/hybrid_rrf_tail.py` 是当前 Brain 默认 hybrid 路径的重要包装：它保留 hybrid head，再用 RRF tail 补召回。
- `BrainService._retrieve_with_hybrid()` 默认非分解问题走 `HybridRrfTailSearchService`，所以 Stage 3 需要确认远程 BGE 在这个默认路径中实际生效。
- `tests/conftest.py` 强制测试环境 reranking provider 为 deterministic，符合 Stage 3 的 CI 边界：真实 GLM/BGE 不进入默认测试。

## 2026-06-23 本地实现发现

- 现有 `OpenAICompatibleReRankingProvider` 的 payload 已经匹配 Stage 3 需要：`model`、`query`、`documents`、`top_n`。唯一阻塞是原先强制 `api_key` 非空；私有 GPU 服务可能通过内网/SSH tunnel 暴露，不一定需要 token。本轮已改为有 token 才发送 `Authorization` / `api-key`，仍保留非空 `model_name` 与 `base_url` 校验。
- `HybridSearchService._rerank_results()` 原先只记录 `rerank_latency_ms`，且 RuntimeError fail-open 没有可观测标记。本轮补充 `reranking_provider`、`reranking_model`、`reranking_fallback`、`reranking_fallback_count`、`reranking_error`，便于端到端 smoke 和后续 Stage 30/Agent trace 复核。
- GPU 服务脚本 `scripts/reranker/serve_lora_reranker.py` 使用标准库 HTTP server，避免新增 FastAPI/Uvicorn 运行依赖；torch/transformers/peft 只在服务启动时导入，本地 Windows 测试 import helper 不会下载模型。
- 服务脚本提供 `/health`、`/rerank`、`/v1/rerank`。`--require-cuda` 下没有 CUDA 会启动失败，防止 CPU 静默承接生产推理。
- A/B 脚本 `scripts/reranker/evaluate_rag_reranker_ab.py` 先用 `HybridSearchService(..., reranking_enabled=False)` 冻结候选池，再分别套 reranker。这样能隔离召回波动，符合 Stage 3 的同候选池要求。
- A/B 脚本默认召回 provider 已设为 `deterministic`，避免裸命令触发真实 embedding；真实 GLM embedding 召回仍可显式 `--provider glm`。
- A/B 脚本默认纳入 Stage 29、Stage 41 和 Phase 51 representative cases。Phase 51 cases 来自 `scripts/evaluate_phase51_performance.py::EVAL_CASES`，用于覆盖 Agent/Brain 代表场景；本地 smoke 可用 `--limit` 控制条数。
- A/B 输出的 candidate snapshot 不包含完整 chunk，只保留 query_id、候选 hash/id、chunk_id、rank、source_type、title 摘要、score 和 relevance 标记。
- 非交互 SSH 探测 GPU 服务器失败：server returned `Permission denied (publickey,password)` without an interactive credential. 当前环境没有可用 SSH key/password，因此不能核验 CUDA、模型目录或启动服务。
- 本地 deterministic smoke 已生成 `data/evaluation/stage3_reranker_ab_results.csv`、`stage3_reranker_ab_summary.csv`、`stage3_reranker_candidate_snapshot.jsonl`，证明脚本写文件和脱敏 snapshot 形态可运行；它不是 GLM/BGE 真实对比。
- 本轮未启动真实 BGE 服务，未调用 GLM reranker，未生成真实 GLM/BGE Stage 3 对比 CSV。因此当前结论只能证明本地接入骨架、评测调度和测试替身成立，不能证明 BGE LoRA 相对 GLM 的质量收益。

## Stage 3 核心决策

- 本机没有 GPU/CUDA，因此不在 Windows 本地加载 BGE、LoRA、torch、transformers。
- BGE LoRA 应部署为 GPU 服务器 HTTP reranker 服务；RAG App 只通过 HTTP provider 调用它。
- 若 BGE 服务实现兼容 OpenAI-style `/rerank` 响应，则可直接复用现有 `OpenAICompatibleReRankingProvider`，减少业务层变更。
- 如果服务契约不能完全兼容，新增 provider 也应只实现 `ReRankingProvider` Protocol，不把模型加载逻辑侵入 `HybridSearchService` 或 Brain。
- Stage 3 评测必须使用同候选池：先冻结召回候选，再分别交给 `none`、`deterministic`、`glm-reranker`、`remote-bge-lora` 排序。
- GLM reranker 是关键对照组；BGE LoRA 的目标不是只超过 deterministic，而是证明相对 GLM reranker 的质量、延迟、成本、可运维性是否值得上线。

## 真实测评集口径

建议 Stage 3 使用三层评测：

1. **候选排序层**：同 query、同候选池，计算 MRR@5、NDCG@5、Precision@1/3/5、latency、fallback/error。
2. **检索结果层**：复用 Stage 29/41 的 `precision@k`、`coverage_ratio`、source_type 命中与 top title 评估。
3. **端到端 RAG 层**：复用 Phase 51/Agent/Brain 场景，检查 citation/source 顺序、拒答一致性、Stage 30 score 和 latency trace。

不建议只用 `data/reranker_training/reranker_test.jsonl` 作验收，因为它来自训练构造任务，不覆盖真实 RAG 召回噪声、source_type 差异、multi-hop 问题、拒答问题和端到端 citation 影响。

## 新词与面试说法

- `远程 reranker service`：把 GPU 上的 BGE LoRA 模型包装成 HTTP 服务。本项目中它会被 `ReRankingProvider` 调用。面试说法：本地 RAG 不持有大模型，只通过服务边界拿排序分数，便于 GPU 隔离和弹性部署。
- `同候选池评测`：先固定每个 query 的召回候选，再让不同 reranker 排同一批候选。面试说法：这样能排除召回波动，公平比较重排器本身。
- `GLM reranker`：既有真实 API reranker 对照组。本项目中必须显式授权调用，不进入 CI。面试说法：自训练 BGE 不是和规则 baseline 比就够了，还要和商业/通用 reranker 对齐，才能判断上线价值。
- `fail-open`：增强服务失败时回退原排序，而不是让问答失败。面试说法：reranker 是质量增强，不是可用性单点，生产链路需要回退。
- `shadow evaluation`：先在同一批真实请求/评测集上旁路比较新旧策略，不立刻替换默认链路。面试说法：先用数据证明无退化，再决定是否切换默认。
- `p95 latency`：95% 请求的耗时上界。本项目用于评估远程 BGE 服务是否会拖慢 RAG 体验。
- `adapter_model.safetensors`：LoRA adapter 权重文件，不是完整基座模型。Stage 3 中它只留在 GPU 服务器，不能提交到 Git。

## 风险

- BGE LoRA 在训练切分上略优于 deterministic，但真实 RAG 测评中可能不优于 GLM reranker。
- BGE 服务如果部署在公网裸端口，存在滥用风险；应考虑内网、防火墙、token 或 SSH tunnel。
- 同候选池若保存完整候选文本，会形成完整 chunk 泄露风险；评测 CSV 只能保存候选 id/hash、标题摘要和指标。
- `HybridRrfTailSearchService` 保留 stable head 的策略可能限制全候选 rerank 的收益；若评测目标是全局重排，需要显式设计候选池与排序插入点。
- 远程 BGE 服务不可用时，RAG 不能中断；必须有 fail-open、错误脱敏和 fallback 计数。
- GLM reranker 的真实 API latency/cost 可能波动，必须记录错误/超时，不允许重试到好看结果后覆盖失败。

## 人工核验重点

1. 确认 GPU 服务器 BGE 服务 `GET /health` 显示 CUDA=True、模型已加载、路径对应 Stage 2.5 最优 adapter。
2. 抽查同候选池评测输出，确认 GLM 与 BGE 看到的是同一批候选。
3. 对比 `glm-reranker` 与 `remote-bge-lora` 的 MRR/NDCG/P@1/coverage/latency，不只看单一指标。
4. 抽查端到端 RAG 回答的 sources/citations，确认排序变化没有引入错误引用。
5. 确认评测输出无完整 chunk、原始 API 响应、API key、Bearer token、模型权重或隐藏推理内容。

## 当前建议结论模板

Stage 3 结束时应给出四选一结论：

- `switch_default_to_remote_bge_lora`：BGE LoRA 在质量不低于 GLM、latency/cost/可控性更优时才允许。
- `parallel_candidate`：BGE LoRA 接近 GLM，但仍需更大真实流量或人工复核。
- `private_fallback_only`：BGE LoRA 质量低于 GLM，但私有化、断网或成本场景有价值。
- `keep_glm_reranker`：GLM 明显优于 BGE，Stage 3 不切默认。
