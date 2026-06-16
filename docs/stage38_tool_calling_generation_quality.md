# 阶段 38 设计：默认 Tool Calling 链路生成质量攻坚与扩展评测闭环

## 目标与基线

阶段 38 从阶段 37 完成并合并后的主线出发：

```text
phase-37-complete -> 62eff40
main / origin/main -> 25344a8
Stage 30 = 91.52 / A / pass
default Agent mode = tool_calling_agent
```

阶段 37 已经完成 OpenAI-compatible `tools/tool_calls` 协议迁移，并把默认入口切到 `tool_calling_agent`。阶段 38 不再做新一轮架构迁移，而是围绕默认 tool-calling 链路补齐回答质量、引用质量和评测置信度。

核心问题：

```text
tool_calling_agent baseline Judge 起点是多少？
扩充到 20-30 条评测后，默认链路是否仍稳定？
tool-calling final synthesis 是否能通过结构化 prompt 提升 answer_coverage 和 citation_support？
structured_final_answer 是否值得进入默认链路？
```

## 四条主线

阶段 38 固定四条主线：

1. Judge 攻坚：先跑 `tool_calling_agent baseline Judge`，再做 `baseline vs structured_final_answer` A/B。
2. 专属生成策略：优化 tool-calling final answer 的 system prompt 和 evidence synthesis，不硬接旧 `answer_with_citations`。
3. 评测扩充：从 Phase 37 的 8 条扩充到 20-30 条，覆盖 11+ 类场景和 tool-calling edge case。
4. 默认链路回归：确认前端默认、`/agent/query` 默认和 `/agent/query/stream` 默认都走 `tool_calling_agent`，并保留显式 `mode="react_agent"` 回滚路径。

## Judge 评测口径

阶段 38 的 Judge 口径必须先确认 baseline，再做策略 A/B：

```text
baseline:
  当前默认 tool_calling_agent prompt
  LLM(messages, tools) -> tool_calls -> role="tool" feedback -> final content

structured_final_answer:
  同一 tool-calling loop
  在 system prompt / evidence synthesis prompt 中加入 outline-first 风格结构要求
  不调用 AgentToolbox.answer_with_citations 生成最终答案
```

评测目标：

```text
answer_coverage >= 0.80
citation_support >= 0.80
safety_leak_check >= 0.80
```

如果达标，裁定报告写明是否将 `structured_final_answer` 接入默认链路；如果未达标，必须诚实归因，不能把 `review_required` 包装成 pass。

## Tool Calling 专属 Final Answer 策略

`tool_calling_agent` 的最终答案路径不同于 `react_agent`。

```text
react_agent:
planner LLM -> answer_with_citations tool -> prompt_builder -> answer LLM

tool_calling_agent:
LLM(messages, tools) -> tool_calls -> role="tool" feedback -> LLM final content
```

因此阶段 38 只在 tool-calling 的 system prompt、`evidence_answer_messages()` 和 `citation_repair_messages()` 中增加结构化约束：

- 先覆盖问题中的主要要点，再组织自然语言答案。
- 每个事实性句子贴近对应 `[N]` 引用。
- 多要点问题必须逐点回答；缺少证据的要点必须明说证据不足。
- citation repair 只能补引用，不得新增事实。
- evidence convergence 后不得继续发散搜索；已有 evidence 不足时安全拒答。
- skip tool / duplicate tool_call 的 tool result 必须被模型理解为预算约束，而不是工具失败事实。

不允许把旧 `answer_with_citations` 工具硬接回 tool-calling 最终生成；否则会把 Phase 37 的协议迁移退回 ReAct/Brain 生成路径。

## 扩展评测集

阶段 38 评测集从 Phase 37 的 8 条扩充到 20-30 条，至少覆盖 11 类场景：

- single_hop
- comparison
- multi_dimensional
- multi_hop
- numeric_comparison
- bilingual
- long_question
- ambiguous_query
- followup
- evidence_insufficient
- off_topic
- responsibility_boundary
- citation_repair
- evidence_convergence
- skip_tool
- duplicate_tool_call

评测 CSV 和脚本只能保存脱敏指标、状态、错误摘要、引用数量、来源数量、tool/LLM 调用计数、Judge 分数和短理由，不保存完整答案、raw provider response、reasoning_content、hidden thought、API key、Bearer token、Authorization header 或受限全文。

## 默认链路稳定性

阶段 38 必须回归三处默认入口：

```text
app/frontend/static/app.js -> default mode tool_calling_agent
POST /agent/query without explicit mode -> tool_calling_agent
POST /agent/query/stream without explicit mode -> tool_calling_agent
```

`scripts/run_production_smoke.py` 需要显式断言默认响应的 `mode` 为 `tool_calling_agent`。同时保留并验证：

- `mode="react_agent"` 显式可选，作为回滚路径。
- `mode="agentic"` 显式可选，不被删除。
- latency、tool_count、llm_call_count、citation_count、source_count 不相对 Phase 37 明显退步。
- Stage 30 仍为 `91.52 / A / pass`。

## 安全边界

阶段 38 不做以下事情：

- 不改 Stage 30 评分权重、等级阈值或 release_decision 规则。
- 不替换默认 embedding provider。
- 不替换默认 rerank provider。
- 不新增外部数据源、不爬新网页、不下载新 PDF、不重切 chunk。
- 不引入 LangGraph、checkpointing、人审工作流或写入型 Agent 工具。
- 不删除 `react_agent`，不删除 `agentic`。
- 不把 `citation_validator` 或其他 deterministic 后处理接进生产链路。
- 不让真实 API 成为 CI 或本地全量 pytest 前提。
- 不写 API key、Bearer token、Authorization header、raw provider response、reasoning_content、hidden thought、完整 chunk 全文或受限全文进 Git、CSV、文档、测试或 Obsidian。

## 新词解释

- `tool_calling_agent baseline Judge`：不加新生成策略，直接用当前默认 tool-calling 链路跑真实 Judge，得到 answer_coverage、citation_support 和 safety_leak_check 的起点。
- `structured_final_answer`：把 compact citation-first 生成约束写进 tool-calling final synthesis prompt，而不是改用旧 `answer_with_citations`。
- `final synthesis`：工具结果回灌后，模型把已有 evidence 组织成最终答案的阶段。
- `citation repair`：当已有证据支持但模型漏写 `[N]` 时，只允许补引用的一次修复调用，不允许新增事实。
- `evidence convergence`：模型反复要求工具时，runtime 基于已有脱敏 sources 收敛到最终回答或安全拒答。
- `skip tool`：runtime 因一轮只执行一个搜索工具或已有 evidence 可用而跳过额外 tool_call，并以安全 `role="tool"` 消息反馈。

## 验收口径

阶段 38 完成时必须输出：

```text
docs/stage38_tool_calling_quality_decision.md
data/evaluation/stage38_* baseline / structured_final_answer results
docs/phase_reviews/phase-38.md
README.md / docs/progress.md / docs/architecture.md / docs/data_sources.md 更新
Obsidian 阶段 38 汇报与索引
```

最终验证：

```text
python -m pytest -q
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute
browser smoke desktop + 390x844 mobile
```

## Six-Metric Judge Gate Addendum

After the user review note on Stage 38, the Judge gate is explicitly defined across all six metrics, not only coverage/citation/safety:

```text
faithfulness >= 0.80
answer_coverage >= 0.80
citation_support >= 0.80
refusal_correctness >= 0.80
conciseness >= 0.80
safety_leak_check >= 0.80
```

The final 24-case `structured_final_answer` average is:

```text
faithfulness=0.981
answer_coverage=0.808
citation_support=0.867
refusal_correctness=0.921
conciseness=0.925
safety_leak_check=1.000
judge_gate=pass
```

`refusal_correctness` is above the gate but still has two anomalous rows that should be checked during human verification.

阶段 38 收尾必须停在用户人工核验前状态，不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。
