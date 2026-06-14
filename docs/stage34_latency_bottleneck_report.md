# 阶段 34 latency bottleneck report

本报告读取 `data/evaluation/stage34_latency_traces.csv`，只分析脱敏耗时字段、状态和计数，不保存完整问题、完整答案、供应商原始响应或受限全文。

## 总体结论

- completed: 10
- error: 0
- p50 time_to_final: 17739.698 ms
- p90 time_to_final: 52216.255 ms
- max time_to_final: 56451.032 ms
- dominant bottleneck: tool_iteration_overhead
- top stage by average share: tool_latency_ms (0.738)

## 分组摘要

| group | completed | p50_ms | p90_ms | dominant_bottleneck | top_stage_by_share | top_stage_share |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| all | 10 | 17739.698 | 52216.255 | tool_iteration_overhead | tool_latency_ms | 0.738 |
| default | 5 | 13387.752 | 23879.721 | tool_iteration_overhead | tool_latency_ms | 1.000 |
| react_agent | 4 | 39097.537 | 55039.440 | tool_iteration_overhead | tool_latency_ms | 0.595 |
| chat | 1 | 20035.427 | 20035.427 | endpoint_total_latency |  | 0.000 |

## 样本状态

| query_id | endpoint | mode | status | primary_bottleneck | time_to_final_ms |
| --- | --- | --- | --- | --- | ---: |
| stage34_simple_filling_default | agent_query | default | completed | tool_iteration_overhead | 13387.752 |
| stage34_simple_filling_react | agent_query | react_agent | completed | tool_iteration_overhead | 26449.350 |
| stage34_thermal_default | agent_query | default | completed | tool_iteration_overhead | 29503.556 |
| stage34_thermal_react | agent_query | react_agent | completed | tool_iteration_overhead | 56451.032 |
| stage34_refusal_boundary_default | agent_query | default | completed | tool_iteration_overhead | 3907.780 |
| stage34_refusal_boundary_react | agent_query | react_agent | completed | planner_latency | 3509.320 |
| stage34_mixed_language_default | agent_query | default | completed | tool_iteration_overhead | 15443.968 |
| stage34_mixed_language_react | agent_query | react_agent | completed | tool_iteration_overhead | 51745.724 |
| stage34_search_default | agent_query | default | completed | tool_iteration_overhead | 4177.776 |
| stage34_chat_filling | chat | chat | completed | endpoint_total_latency | 20035.427 |

## 初步建议

- 如果 `answer_latency_ms` 或 `tool_latency_ms` 占比最高，优先评估 prompt 长度、chat provider 延迟和 ReAct 工具轮数。
- 如果 `planner_latency_ms` 在 `react_agent` 中占比高，阶段 35 前应先考虑 planner prompt 压缩或减少规划调用。
- 如果 `query_embedding_latency_ms` 高，优先检查 query embedding cache 命中率和 provider 延迟。
- 如果 `rerank_latency_ms` 高，优先对比 rerank provider、recall_k 和是否需要按 query 类型启用。
