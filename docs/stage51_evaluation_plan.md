# 阶段 51：Phase 50 性能评测与全周期架构演进对照

## 目标

对阶段 50 引入的 LangGraph Agent 编排、pgvector HNSW、Semantic Cache、Planner 快模型路由进行定量评测，补跑 Brain 直通路径作为"无 Agent 开销"基线，形成从 Phase 8 Brain 到 Phase 50 LangGraph 的**六代架构全周期性能演进对照表**，并完成 `route_query_node` → `planner_node` 重命名。

## 前置条件

- Phase 50 Phase 0-17 已完成并合并到 main（branch `codex/phase-50-langgraph-redis`）
- 基线：pytest 1106 passed / 1 skipped，Stage 30 91.52/A/pass
- 已有 Phase 37 真实评测数据（8 题，`data/evaluation/stage37_tool_calling_vs_react_real_results.csv`）
- 已有 Phase 50 deterministic 对照（`data/evaluation/phase50_langgraph_vs_react_results.csv`）
- 已有演进对照表：`G:\Codex\program\关键提升\agent_evolution_comparison.md`（P32/P34/P37 三列）

## Phase 规划

### Phase 0：启动校准 + 重命名 `route_query_node` → `planner_node`

**解决的问题**：代码命名与实际职责不匹配；LangGraph 路由节点的职责是"规划下一步 action"，应叫 planner_node。

**任务**：
- 确认 Phase 50 已合并到 main，创建 `codex/phase-51-performance-evaluation` 分支
- 重命名 `route_query_node` → `planner_node`（代码 + 测试 + 文档）
- 涉及文件：`graph_nodes.py`、`graph_builder.py`、`graph_state.py`（如有）、3 个测试文件、`docs/architecture.md`、`README.md`、`AGENT.MD`
- 全量 pytest 回归

### Phase 1：评测集设计与评测脚本

**解决的问题**：Phase 50 新增能力缺少定量对比数据，无法回答"改造后到底快了多少、质量有没有退化"。

**任务**：
- 新增 `scripts/evaluate_phase51_performance.py`
- 评测问题集：复用 Phase 37 的 8 题（single_hop_definition / comparison / multi_dimensional / bilingual_terms / followup / evidence_insufficient / off_topic_refusal / multi_hop_retrieval）
- 六种配置逐一评测：

| 配置 ID | 编排方式 | 路由 | 检索后端 | 生成模型 |
|---------|---------|------|---------|---------|
| brain_baseline | Brain 直通（/chat） | 无 Agent 循环 | pgvector HNSW | Pro |
| react_agent | ReAct Agent 循环 | DeterministicReActPlanner | pgvector HNSW | Pro |
| tool_calling_agent | 原生 tool_calls | 模型自选 | pgvector HNSW | V4-Flash |
| langgraph_deterministic | LangGraph 状态图 | 确定性规则 planner | pgvector HNSW | Pro |
| langgraph_flash_planner | LangGraph 状态图 | Flash LLM planner | pgvector HNSW | Flash 路由 + Pro 生成 |
| langgraph_faiss_fallback | LangGraph 状态图 | 确定性规则 planner | FAISS IndexFlatIP | Pro |

- 补充 Semantic Cache 命中场景：同一问题第二次请求的延迟

**记录字段**：
- `time_to_first_token_ms`、`time_to_final_ms`（端到端延迟）
- `planner_latency_ms`、`search_latency_ms`（子链路延迟）
- `vector_search_backend`（pgvector_hnsw / faiss）
- `planner_model`（deterministic / flash / native_tool_calls）
- `tool_call_count`、`iteration_count`
- `citation_count`、`source_count`
- `semantic_cache_hit`
- `refused`、`same_refusal`、`same_top_source`

**输出**：
- `data/evaluation/phase51_performance_results.csv`
- `data/evaluation/phase51_performance_summary.csv`
- 默认 dry-run（deterministic provider），`--execute` 调用真实 API

### Phase 2：真实 Provider 评测执行

**解决的问题**：dry-run 只验证脚本正确性；需要真实 API 数据填充对照表。

**任务**：
- `python scripts/evaluate_phase51_performance.py --execute`
- 确保 6 种配置 × 8 题 = 48 条记录（拒答题跳过部分配置）
- Semantic Cache 补充评测：每题跑两遍，记录第二遍命中延迟
- 记录向量检索子链路：pgvector HNSW vs FAISS 的 search_latency 和 recall@5
- 分析数据，输出 summary CSV

### Phase 3：全周期演进对照表更新

**解决的问题**：`agent_evolution_comparison.md` 只有 P32/P34/P37 三列，缺少 Brain 基线和 Phase 50 数据。

**任务**：
- 在 `G:\Codex\program\关键提升\agent_evolution_comparison.md` 追加为六代全周期表：

```
| | Brain 直通 (P8) | MIMO ReAct (P32) | Flash+Pro (P34) | Tool Calling (P37) | LG 规则路由 (P50) | LG+Planner (P50) | Cache 命中 |
```

- 新增维度行：
  - **路由架构类型**：无/LLM planner(慢)/LLM planner(快)/原生tool_calls/确定性规则/LLM planner(LangGraph)
  - **向量检索后端**：numpy → FAISS → pgvector HNSW
  - **Semantic Cache**：无 → 命中时 ~ms
  - **向量检索延迟**：子链路对比行
- 更新关键结论段落

### Phase 4：回归验证与文档收尾

**任务**：
- 全量 pytest，确认不退化
- Stage 30 评分，确认 91.52/A/pass
- 新增 `docs/phase_reviews/phase-51.md`
- 更新 `docs/progress.md`、`README.md`、`AGENT.MD`
- Obsidian：新增阶段 51 Phase 汇报
- 停在人工核验前状态

## 安全边界

- 不改变默认 provider、检索策略或外部数据源
- 不让真实 API 成为 CI 或本地全量测试前提
- 不把 API key、Bearer token、供应商原始响应写入 Git/CSV/文档/测试/Obsidian
- 评测 CSV 只保存延迟数值、配置标识和脱敏质量指标
- 未经用户人工核验，不 git add/commit/tag/push/PR
- 重命名 `route_query_node` 是纯重构，不改变运行时行为

## 完成标准

- `route_query_node` 已重命名为 `planner_node`，全量 pytest 通过
- 评测脚本 dry-run 通过，真实评测生成完整 CSV
- `agent_evolution_comparison.md` 扩展为六代全周期表（Brain → MIMO → Flash+Pro → Tool Calling → LG 规则 → LG+Planner + Cache 命中）
- 每代有延迟、可靠性、架构、质量四维对比
- 向量检索子链路（pgvector HNSW vs FAISS）有独立对比数据
- Semantic Cache 命中率和延迟收益有量化数据
- 全量 pytest 通过，Stage 30 不退化
- 文档和 Obsidian 同步完成
- 最终停在未提交、未 tag、未 push、未 PR 的人工核验前状态
