# 阶段 34 决策报告：RAG 性能瓶颈诊断、Embedding 迁移决策与真实 Judge 质量复核

## 结论

- Embedding decision: `keep_glm`
- Latency primary bottleneck: `tool_iteration_overhead`
- Chat provider next action: `keep_flash_planner_pro_answer_and_tune_answer_prompt_length_or_top_k`
- Judge quality gate: `review_required`
- Phase 35 recommendation: `phase35_should_keep_glm_default_and_use_jina_only_as_rollback_reference_and_evaluate_tool_calling_protocol_migration_to_merge_planner_and_answer_into_one_llm_call_and_tune_answer_prompt_length_or_top_k_or_streaming_first_token_and_review_judge_medium_risk_answers`
- Submit state: `uncommitted_waiting_for_user_manual_review`

## 证据

- Embedding evidence: glm_candidate:p1=0.667,p3=0.867,p5=0.867,coverage=0.637,latency=1491.38ms,status=completed | jina_baseline:p1=0.667,p3=0.800,p5=0.933,coverage=0.670,latency=1489.29ms,status=completed
- Latency evidence: p50=17739.698ms,p90=52216.255ms,max=56451.032ms,top_stage=tool_latency_ms,share=0.738
- Judge evidence: completed=4,faithfulness=0.925,coverage=0.675,citation=0.613,high=0,medium=4
- Stage 30 score: 83.17 / review_required

## 工程判断

- 当前不删除旧 Jina 索引，不直接切默认 embedding，也不移动任何阶段 tag。
- 阶段 34 最终建议保留 GLM-Embedding-3 作为默认 embedding provider；Jina 在 precision@5 和 coverage 上的小幅优势不足以抵消额度可持续性风险，不继续推进 Jina 分流。Jina 结果仅作为历史同环境对照和必要时的回滚参考。
- 阶段 34 已完成 chat provider 分层路由：answer 路径切到 Paratera DeepSeek-V4-Pro（替换 MIMO），planner 路径独立配置为 Paratera DeepSeek-V4-Flash 这一轻量模型。原 MIMO 配置在 .env 中注释保留，可做回滚参考。
- LLM-driven planner 实验在 MIMO 上反向退化（p90 +135%、出现 timeout），根因是 MIMO 作为 reasoning 模型单次 planner 调用就 30–70s；本项目当前 ReAct 协议把每轮拆成 planner 决策与 answer 生成两次 LLM 往返，慢/重模型当 planner 会被放大。
- 引入轻量 Flash planner 后，react_agent p50 从 87.9s 降到约 39s（-55% vs MIMO 基线），p90 与 max 同步下降，10/10 样例完成；refusal_boundary 边界问题第 1 轮即由 LLM 自主 refuse（~3.5s），相对 elif 短路 + MIMO 的 17s 是一个净改进。
- 协议层的根本问题没有改变：每轮 1 次 LLM 调用 + answer 工具内部又 1 次 LLM 调用，总比主流 tool-calling 协议多 1 次 LLM 调用。后续阶段可评估迁移到 OpenAI 函数调用/tool_calls 协议，让 planner 决策和 answer 生成在同一次 LLM forward 内完成。
- 当前真实 Judge 不是 pass，medium 风险样例应在阶段 35 前人工复核，尤其 citation_support 与 answer_coverage 较低的样例。
- 阶段 35 候选方向：tool-calling 协议迁移合并 planner 与 answer、answer 端 prompt 长度/top_k/流式首 token 调优、Judge medium 风险复核；不再推荐直接放开真 LLM 自主 ReAct 之外的更大改动。

## 安全边界

本报告只引用脱敏指标、状态和短证据，不包含 API key、Bearer token、raw provider response、reasoning_content、hidden thought 或受限全文。
