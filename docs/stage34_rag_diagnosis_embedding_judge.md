# 阶段 34：RAG 性能瓶颈诊断、Embedding 迁移决策与真实 Judge 质量复核

## 目标

阶段 34 从阶段 33 已完成并合并后的 `main` 出发，使用阶段 33 新增的 latency trace、FAISS-only 加载、query embedding cache 和 embedding 迁移评测脚本，完成三条证据闭环：

- GLM-Embedding-3 2048 维与 Jina 1024 维同环境检索对照。
- 真实 RAG/ReAct latency trace 采集与瓶颈归因。
- 可选真实 LLM Judge 对最终生成答案做语义质量复核。

本阶段的输出是决策报告，而不是直接替换默认模型、删除旧索引或扩大 Agent 能力。阶段 34 必须最终停在用户人工核验前状态：不 `git add`、不 commit、不创建 `phase-34-complete` tag、不 push、不创建 PR。

## 输入

阶段 34 主要读取以下已有资产：

```text
data/evaluation/stage29_new_corpus_queries.csv
data/evaluation/stage33_embedding_migration_results.csv
data/evaluation/stage33_embedding_migration_summary.csv
data/evaluation/stage33_chat_provider_benchmark.csv
data/faiss/jina_jina-embeddings-v3_dim1024.index
data/faiss/jina_jina-embeddings-v3_dim1024_ids.json
data/faiss/paratera_GLM-Embedding-3_dim2048.index
data/faiss/paratera_GLM-Embedding-3_dim2048_ids.json
```

真实 provider 配置只允许来自本地 `.env` 或命令行参数。配置存在与否只能写成 `completed`、`skipped` 或 `error` 状态，不能把 dry-run 结果伪造成真实成功。

## 同环境 Embedding 对照

阶段 33 的 GLM 真实 query 侧已完成，但 Jina baseline 因缺少本机真实配置被标记为 `skipped_missing_real_config`。阶段 34 必须补齐同环境对照：

```text
同一题集
-> 同一 SQLite 数据库
-> 同一 top_k / rerank / source 判定口径
-> 只替换 query embedding provider
-> Jina 1024 维 vs GLM-Embedding-3 2048 维
-> 检索质量、来源覆盖和延迟指标对比
```

必备指标：

- `precision@1`
- `precision@3`
- `precision@5`
- `hit@5`
- `coverage`
- `source_type_distribution`
- `citation/source 覆盖`
- `refusal boundary`
- `latency_ms`

输出建议：

```text
data/evaluation/stage34_embedding_comparison_results.csv
data/evaluation/stage34_embedding_comparison_summary.csv
```

决策候选：

- `keep_glm`
- `rollback_jina`
- `route_by_query_type`
- `review_required`

阶段 34 最终采用 `keep_glm`：Jina 在 precision@5 与 coverage 上略优，但优势不足以抵消额度即将耗尽带来的可持续性风险；保留 GLM-Embedding-3 作为默认 embedding provider，不继续推进 Jina 分流，Jina 结果仅作为历史对照和回滚参考。

阶段 34 不直接切默认 GLM/Jina provider，不删除旧 Jina 索引，也不把任何 API key 或供应商原始响应写入 CSV、文档、测试或 Obsidian。

## Latency Trace 采集与瓶颈归因

阶段 33 已经把 latency trace 接入 RAG/ReAct 链路。阶段 34 要采集 10-20 条真实请求，把 trace 从“可记录字段”变成“可执行诊断结论”。

覆盖链路：

```text
/chat
/agent/query
/agent/query/stream
mode=default
mode=agentic
mode=react_agent
SSE metadata
```

必备字段：

- `query_embedding_latency_ms`
- `faiss_search_latency_ms`
- `vector_search_latency_ms`
- `numpy_search_latency_ms`
- `rerank_latency_ms`
- `planner_latency_ms`
- `tool_latency_ms`
- `answer_latency_ms`
- `time_to_first_token_ms`
- `time_to_final_ms`
- `iteration_count`
- `tool_call_count`
- `load_mode`
- `cache_hit`

分析指标：

- `p50`
- `p90`
- `mean`
- `max`
- `stage_share`

瓶颈分类：

- `embedding_provider_latency`
- `faiss_or_vector_search_latency`
- `rerank_latency`
- `planner_latency`
- `tool_iteration_overhead`
- `answer_generation_latency`
- `time_to_first_token_latency`
- `cold_start_or_cache_miss`

输出建议：

```text
data/evaluation/stage34_latency_traces.csv
data/evaluation/stage34_latency_bottleneck_summary.csv
docs/stage34_latency_bottleneck_report.md
```

latency trace 只允许保存安全耗时、计数、状态、query id 和脱敏错误摘要。不保存完整 prompt、完整 answer、hidden thought、`reasoning_content`、raw provider response、API key、Bearer token、Authorization header 或受限全文。

## 真实 LLM Judge 质量复核

阶段 30 的 `overall_score=83.17` 来自规则评分，不等于真实语义质量通过。阶段 34 增加可选真实 LLM Judge 支路，用于少量代表样本的生成答案复核。

运行边界：

- 默认 dry-run，不调用真实 judge。
- 只有显式 `--execute` 且本地存在 judge provider 配置时才调用真实模型。
- 真实失败必须写 `skipped` 或 `error` 和脱敏原因。
- Judge 结果不进入 CI 或本地全量测试前提。

Judge 指标：

- `faithfulness`
- `answer_coverage`
- `citation_support`
- `refusal_correctness`
- `conciseness`
- `safety_leak_check`

输出建议：

```text
data/evaluation/stage34_llm_judge_results.csv
data/evaluation/stage34_llm_judge_summary.csv
```

只保存：

- 分数。
- 短理由。
- 风险等级。
- `next_action`。
- 脱敏状态。

禁止保存：

- raw judge response。
- `reasoning_content`。
- hidden thought。
- 完整受限全文。
- API key。
- Bearer token。
- Authorization header。
- 完整 prompt。

## 决策报告

阶段 34 的最终决策报告汇总 embedding 对照、latency 归因、真实 Judge 复核和阶段 30 评分状态。

输出：

```text
data/evaluation/stage34_decision_summary.csv
docs/stage34_rag_diagnosis_decision_report.md
```

必备决策项：

- `embedding_decision`
- `latency_primary_bottleneck`
- `chat_provider_next_action`
- `judge_quality_gate`
- `phase35_recommendation`

报告必须说明：

- 是否保留 GLM-Embedding-3。
- 是否回滚 Jina 或按 query 类型分流。
- 主要性能瓶颈来自 embedding、FAISS/vector search、rerank、planner、tool、answer generation、TTFT、final latency、冷启动或 cache miss 中哪一类。
- MIMO/DeepSeek 后续动作，但不在阶段 34 直接替换默认 provider。
- 阶段 35 是否适合进入真 LLM 自主 ReAct，或应先做 prompt/provider/rerank 小优化。

## 兼容性要求

阶段 34 不改变以下外部契约：

```text
default mode
agentic mode
react_agent mode
POST /chat
POST /agent/query
POST /agent/query/stream
SSE token / metadata / done / error
SSE agent_step / tool_call_start / tool_call_result
```

新增脚本和报告必须在 evaluation/reporting 层完成，不把真实 API 变成默认运行、CI 或全量 pytest 的前提。

## 不做事项

- 不删除旧 Jina 索引。
- 不直接替换默认 GLM/Jina/MIMO/DeepSeek。
- 不新增外部数据源。
- 不新增写入型 Agent 工具。
- 不做部署或运维。
- 不上真 LLM 自主 ReAct。
- 不把真实 API 调用伪造成 dry-run 成功。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始响应、raw_response、`reasoning_content`、hidden thought 或受限全文写入 Git、CSV、文档、测试或 Obsidian。

## 完成标准

- 阶段 34 从 `main -> c06d0a3` 与 `phase-33-complete -> 0bad9e1` 的正确基线出发。
- Jina 与 GLM 完成同环境检索对照，或写明可复现的 `skipped` / `error` 原因。
- 采集 10-20 条真实 RAG/ReAct latency trace，并输出 p50/p90、均值、最大值和阶段占比。
- 明确性能瓶颈主因。
- LLM Judge 支路默认 dry-run，显式 `--execute` 才调用真实 judge。
- Judge 结果只保存脱敏分数、短理由、风险等级和 next_action。
- 形成 `docs/stage34_rag_diagnosis_decision_report.md` 与 `data/evaluation/stage34_decision_summary.csv`。
- 阶段 34 聚焦测试、全量 pytest 和 `scripts/score_stage30_quality.py` 通过；阶段 30 overall score 保持 `>= 83.17`。
- 浏览器桌面与移动端验证 Agent 查询、折叠思考过程、最终答案、无横向溢出、console errors=0。
- 普通文档和 Obsidian 草稿完成。
- 最终停在用户人工核验前，不提交、不 tag、不 push、不建 PR。
