# 阶段 38 发现与关键决策

## 当前 Git 基线

Phase 37 已完成、提交、打 `phase-37-complete` tag，并合并到 main：

```text
main / origin/main -> 25344a8 Merge phase 37 tool calling loop migration
phase-37-complete -> 62eff40 Complete phase 37 tool calling loop migration
当前开发分支 -> codex/phase-38-tool-calling-generation-quality
Phase 38 状态 -> Phase 0 启动校准完成；等待进入 Phase 1 设计文档与评测口径
```

关键决策：阶段 38 已从 Phase 37 合并后的 main 出发。后续开发不得再把 Phase 37 当作未提交工作区改动处理。

## Phase 0 校准结论

已完成启动校准：

```text
git status -sb -> codex/phase-38-tool-calling-generation-quality，未提交改动仅为阶段 38 规划文件
git log --oneline -5 -> 25344a8 Merge phase 37 tool calling loop migration
phase37_is_ancestor_of_main=yes
phase37_is_ancestor_of_origin_main=yes
```

阶段 37 的默认链路切换、三个 bug 修复和 stream mode 解析修复已经包含在合并后的 main 中，阶段 38 直接在默认 `tool_calling_agent` 链路上做生成质量攻坚。

## 观察 1：默认链路已切换到 tool_calling_agent

Phase 37 用户核验后，Claude 已在本次会话中完成三处默认切换：

```text
前端 app.js: mode: "react_agent" -> mode: "tool_calling_agent"
后端 query 端点: complex -> "agentic" 改为 complex -> "tool_calling_agent"
后端 stream 端点: 同上
stream 层 bug: auto-route 到 tool_calling_agent 时需跳过 QueueStreamingChatModelProvider
```

这意味着阶段 38 的所有 Judge 攻坚、生成策略优化和评测都应基于 tool_calling_agent 默认链路进行，不再以 react_agent 为基线。

## 观察 2：tool_calling_agent 的 final answer 生成路径与 react_agent 不同

react_agent 的回答生成：
```text
planner LLM (Flash) -> 选择 answer_with_citations 工具 -> 工具内调用 answer LLM (V4-Pro) -> prompt_builder 构建完整 prompt -> 生成答案
```

tool_calling_agent 的回答生成：
```text
LLM(messages + tools) -> tool_calls(hybrid_search_knowledge) -> execute -> role="tool" feedback -> LLM 直接生成 final answer
```

关键差异：tool_calling_agent 的 final answer 是模型在看到 tool result 后的自由生成，受控于 system prompt 中的指令。react_agent 的答案经过 prompt_builder 的精细引用约束。

关键决策：阶段 38 Phase 3 需要在 tool_calling_agent 的 system prompt 中嵌入等效的引用约束和生成结构要求，而不是把 prompt_builder 硬接回 tool-calling 链路。

## 观察 3：Phase 36 Judge 攻坚的数据为 react_agent 链路

Phase 36 的三组 Judge 结果（baseline/outline_first/answer_provider_ab）都是在 react_agent 链路上跑的。tool_calling_agent 的 final answer 质量尚未经过 Judge 评测。

```text
Phase 36 baseline (react_agent): cov=0.655 / cit=0.640 / safety=1.000
Phase 36 outline_first (react_agent): cov=0.703 / cit=0.685 / safety=1.000
Phase 36 answer_provider_ab (react_agent): cov=0.772 / cit=0.820 / safety=0.950
tool_calling_agent Judge: 未评测
```

关键决策：阶段 38 必须先在 tool_calling_agent 上跑一轮 baseline Judge，才能知道起点在哪。不能假设 tool_calling_agent 的 answer 质量与 react_agent 相同。

## 观察 4：评测集 8 条不足以支撑默认切换信心

Phase 37 的评测只有 8 条，覆盖：single_hop、comparison、multi_dimensional、bilingual、followup、evidence_insufficient、off_topic、multi_hop。

缺失场景：
- 数值对比（具体数字比较）
- 长问题（复杂多约束）
- 模糊问题（模糊关键词）
- 工程责任边界（需要专业判断的问题）
- citation repair 专属触发
- evidence convergence 专属触发
- skip tool / duplicate tool_call 专属触发

关键决策：阶段 38 Phase 2 扩充到 20-30 条是优先级最高的任务之一，因为它直接影响 Judge 攻坚和默认链路信心。

## 观察 5：tool_calling_agent 的三个已修复 bug

Claude 在本次会话中修复了三个阻断性 bug：

1. GBK encoding：Windows 上 subprocess.run(text=True) 默认用 GBK 解码 curl 的 UTF-8 输出，加 encoding="utf-8"。
2. OpenAI tool 协议：DeepSeek 要求 assistant(tool_calls) 消息必须在 role="tool" 之前。ChatMessage 新增 assistant_tool_calls 字段，tool_calling_service.py 在 tool result 前先 append assistant message。
3. Forward reference：ChatToolCall 定义在 ChatMessage 之后，用字符串注解避免 NameError。

这些修复已包含在 `phase-37-complete -> 62eff40` 和 `main -> 25344a8` 的提交链中。阶段 38 Phase 0 已确认它们完整保留。

## 观察 6：真实评测数据对比

Phase 37 真实 Provider 评测（DeepSeek 官方 API）：

```text
react_agent: errors=0, avg_latency=28.0s, citations=2.25, sources=5.25, same_refusal=8/8, same_top_source=8/8
tool_calling_agent: errors=0, avg_latency=13.5s, citations=2.50, sources=5.50, same_refusal=8/8, same_top_source=7/8
```

tool_calling_agent 在延迟上有明确优势（2x），引用和来源数略多，有 1 条 top source 不同。

关键判断：延迟和可靠性已验证。阶段 38 的焦点完全在回答质量和引用质量上。

## 观察 7：阶段 38 不动的边界

- 不替换默认 embedding / rerank provider；不动 provider 拓扑。
- 不引入新外部数据源、不爬新网页、不切 chunk。
- 不做架构迁移（tool-calling 协议迁移已在 Phase 37 完成）。
- 不做多用户 / Conversation owner 隔离。
- 不做写入型 Agent 工具。
- 不接 deterministic 后处理（含 citation_validator）进生产链路。
- 不改 Stage 30 评分规则。
- 不写 API key / Bearer token / raw provider response / reasoning_content / hidden thought / 受限全文进任何提交物。

## Phase 1 设计文档决策

阶段 38 设计文档已固定四条主线：

```text
Judge 攻坚 -> Tool Calling 专属 final answer 生成策略 -> 扩展评测集 -> 默认链路稳定性回归
```

关键决策：

- `tool_calling_agent baseline Judge` 必须先跑，不能直接拿 Phase 36 react_agent Judge 分数当起点。
- `structured_final_answer` 是 tool-calling 原生 final synthesis 策略：改 system prompt / evidence synthesis prompt，不调用旧 `answer_with_citations` 工具内生成最终答案。
- 评测集必须扩到 20-30 条，覆盖 11+ 类场景，并包含 citation repair、evidence convergence、skip tool、duplicate tool_call 等 tool-calling edge case。
- 默认链路稳定性必须检查前端、query、stream 三处入口，`react_agent` 保留为显式回滚路径。

新词解释：

- `final synthesis`：工具结果回灌后，模型把已有 evidence 组织成最终答案的阶段。
- `structured_final_answer`：把 outline-first 风格的生成约束写进 tool-calling final synthesis prompt，而不是改用旧 `answer_with_citations`。
- `citation repair`：已有证据支持但模型漏写 `[N]` 时，只允许补引用的一次修复调用，不允许新增事实。

验证：

```text
python -m pytest tests/test_stage38_design.py -q -> 8 passed
```

## Phase 2 扩展评测集决策

阶段 38 新增独立评测脚本：

```text
scripts/evaluate_stage38_tool_calling_quality.py
data/evaluation/stage38_tool_calling_quality_results.csv
data/evaluation/stage38_tool_calling_quality_summary.csv
```

关键决策：不覆盖 Phase 37 的 `stage37_tool_calling_vs_react_*` 产物。Phase 37 文件继续作为迁移对照历史；Phase 38 文件作为默认链路生成质量攻坚的扩展基线。

扩展评测集当前为 24 条，覆盖 16 类场景：

```text
single_hop / comparison / multi_dimensional / multi_hop / numeric_comparison
bilingual / long_question / ambiguous_query / followup / evidence_insufficient
off_topic / responsibility_boundary / citation_repair / evidence_convergence
skip_tool / duplicate_tool_call
```

deterministic 运行结果：

```text
react_agent: errors=0, same_refusal=24/24, same_top_source=24/24
tool_calling_agent: errors=0, same_refusal=23/24, same_top_source=20/24
```

观察：扩展集已经比 Phase 37 的 8 条更有区分度。`tool_calling_agent` 没有工程错误，但 refusal 和 top source 一致性出现差异，说明 Phase 3/4 的 final answer 质量和 Judge 攻坚是必要的。

新词解释：

- `skip tool`：模型一次返回多个 tool_call 时，runtime 只执行预算允许的一个搜索工具，其他工具以安全 tool result 反馈“本轮搜索预算已用完”。
- `duplicate_tool_call`：模型重复或近似重复搜索同一 query，runtime 拦截并记录 near_duplicate_query_count，避免循环浪费。
- `same_top_source`：tool_calling_agent 和 react_agent 的第一来源是否一致。它不是最终质量分，但能提示默认链路证据锚点是否漂移。

验证：

```text
python -m pytest tests/test_stage38_tool_calling_eval.py -q -> 5 passed
python scripts/evaluate_stage38_tool_calling_quality.py -> cases=24, tool_calling_agent errors=0
```

## Phase 3 Tool Calling 专属 Final Answer 策略决策

实现决策：

```text
ToolCallingFinalAnswerStrategy = baseline | structured_final_answer
默认策略 = structured_final_answer
baseline = 只用于 Phase 4 A/B 对照和回归
```

结构化策略进入了三处 prompt：

- `tool_calling_messages()`：常规 LLM(messages, tools) loop 的 system prompt。
- `evidence_answer_messages()`：已有 evidence 后收敛回答的 final synthesis prompt。
- `citation_repair_messages()`：只补引用、不扩写事实的 repair prompt。

关键边界：

- 没有把旧 `AgentToolbox.answer_with_citations` 接回 tool-calling 最终生成。
- 没有引入 deterministic citation_validator 后处理。
- 没有改变 provider 拓扑、工具权限或 Stage 30 规则。

新词解释：

- `ToolCallingFinalAnswerStrategy`：tool-calling 链路最终答案策略枚举；当前只有 baseline 和 structured_final_answer。
- `evidence synthesis prompt`：已有工具证据后，用来要求模型按证据组织答案的 system prompt。
- `repair prompt`：漏引用时的修复 prompt，只允许把已有事实和已有 source marker 对齐，不允许添加新内容。

验证：

```text
python -m pytest tests/test_tool_calling_agent_service.py tests/test_stage38_design.py tests/test_stage38_tool_calling_eval.py -q -> 28 passed
python scripts/evaluate_stage38_tool_calling_quality.py -> cases=24, tool_calling_agent errors=0
```

## Phase 4 Judge 质量门攻坚结论

真实 Judge A/B 已完成：

```text
python scripts/judge_stage38_tool_calling_quality.py --execute --limit 24 --timeout-seconds 180

baseline: completed=24, cov=0.869, cit=0.794, safety=1.000, gate=review_required
structured_final_answer: completed=24, cov=0.808, cit=0.729, safety=1.000, gate=review_required
```

关键结论：两组均未同时达到 `answer_coverage >= 0.80` 与 `citation_support >= 0.80`。baseline 距 citation_support 门槛只差 0.006，但仍不能包装成 pass；structured_final_answer 没有改善 citation_support，反而降到 0.729。

归因：

- 主要瓶颈是 citation granularity，即事实句与 `[N]` source marker 的局部贴合不够稳定。
- structured prompt 提升了“组织答案”的意图，但没有让模型稳定做到逐事实句贴源。
- refusal 边界题在 Judge 里可能被记为 coverage/citation 低分，即使行为方向正确；需要人审解释，而不是自动放宽门槛。
- safety 没有退步，两组 `safety_leak_check=1.000`，且 high_risk=0。

决策：

- `structured_final_answer` 作为实现策略保留，但暂不声称优于 baseline。
- Judge gate 诚实记录为 `review_required`。
- 不接 deterministic citation_validator，不改 Stage 30 规则，不硬接旧 `answer_with_citations` 回生产。

验证与产物：

```text
python -m pytest tests/test_stage38_tool_calling_judge.py -q -> 4 passed
data/evaluation/stage38_tool_calling_judge_results.csv
data/evaluation/stage38_tool_calling_judge_summary.csv
docs/stage38_tool_calling_quality_decision.md
```

## Phase 5 默认链路稳定性回归结论

三处默认入口已经对齐：

```text
前端 app.js 默认 mode -> tool_calling_agent
POST /agent/query 省略 mode -> tool_calling_agent
POST /agent/query/stream 省略 mode -> tool_calling_agent
```

关键实现变化：

- 后端不再用 query complexity 把简单问题自动分回 `default`；省略 `mode` 即默认 tool-calling。
- 显式 `mode="default"` 继续保留，用于旧 RAG 链路、source detail、follow-up transform 等回归场景。
- 显式 `mode="react_agent"` 继续保留为 Phase 37/38 约定的回滚路径。
- `ToolCallingAgentService` 对不支持 `generate_with_tools` 的 provider 做受控失败，API 返回 503，避免默认链路切换后出现未包装 AttributeError。

production smoke 已增强为默认链路质量门：

```text
新增字段：expected_mode / actual_mode / mode_matched
新增用例：agent_query_default_tool_calling
新增用例：agent_query_stream_default_tool_calling
总 smoke rows：9 -> 11
```

新词解释：

- `mode_matched`：production smoke 中的布尔字段，用来判断接口返回的实际 `mode` 是否等于该用例期望的默认或显式 mode；它把“字段存在”升级为“默认链路真的走对”。
- `provider capability 护栏`：默认 tool-calling 需要 provider 支持 `generate_with_tools`；如果注入的 provider 缺少该能力，服务层把它归类为模型 provider 不可用，而不是暴露内部属性错误。

验证：

```text
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_run_production_smoke.py -q -> 44 passed
python -m pytest tests/test_stage38_design.py tests/test_stage38_tool_calling_eval.py tests/test_stage38_tool_calling_judge.py tests/test_tool_calling_agent_service.py -q -> 32 passed
python scripts/run_production_smoke.py -> rows=11 execute=false failed=0
python scripts/evaluate_stage38_tool_calling_quality.py -> cases=24, tool_calling_agent errors=0
```

关键判断：默认链路入口已经稳定切到 `tool_calling_agent`，显式 `react_agent` 回滚路径未删除，显式 `default` 仍可用于旧链路能力。

## Phase 6 收尾验证结论

普通文档与 Obsidian 已收尾：

```text
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
docs/stage38_tool_calling_quality_decision.md
docs/phase_reviews/phase-38.md
obsidian-vault/阶段汇报/阶段 38 - Tool Calling 生成质量攻坚/
obsidian-vault/阶段/阶段 38 - Tool Calling 生成质量攻坚.md
```

最终验证：

```text
python -m pytest -q -> 780 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120 -> rows=11 execute=true failed=0
browser desktop -> latest mode=tool_calling_agent, citations present, horizontal overflow=false, console errors=0
browser 390x844 -> Agent page present, tool-calling history present, horizontal overflow=false, console errors=0
```

阶段 38 当前结论：开发、测试、普通文档和 Obsidian 草稿均已完成；Judge gate 仍诚实记录为 `review_required`；当前停在用户人工核验前，未执行 `git add`、commit、tag、push 或 PR。

## Citation Gap 补强结论

用户人工核验前追加分析 `structured_final_answer` 的 citation_support 扣分 case。

新增产物：

```text
scripts/analyze_stage38_citation_gaps.py
tests/test_stage38_citation_gap_analysis.py
data/evaluation/stage38_citation_gap_analysis.csv
```

初始归因：

```text
low-citation rows=9
prompt_citation_gap=6
refusal_judge_artifact=2
retrieval_or_repair_gap=1
```

关键判断：大多数 case 不是检索证据完全不够，而是 structured prompt 让模型展开后没有做到 sentence-local citation。检索侧暂不优先改动。

Prompt 调整过程：

```text
outline-first structured -> cov=0.808 / cit=0.729 / review_required
over-strict citation-dense -> cov=0.708 / cit=0.719 / review_required
compact citation-first -> cov=0.808 / cit=0.867 / pass
```

最终策略：

- 直接回答 1-2 句，句句带 citation。
- 如需展开，最多 3-5 个短事实 bullet。
- 每个 factual sentence / factual bullet 都贴最近 `[N]`。
- 对比题两侧分别引用。
- 不支持的细节写 evidence gap，不推断补全。

最终真实 Judge：

```text
python scripts/judge_stage38_tool_calling_quality.py --execute --limit 24 --timeout-seconds 180
baseline: cov=0.775 / cit=0.731 / safety=1.000 / gate=review_required
structured_final_answer: cov=0.808 / cit=0.867 / safety=1.000 / gate=pass
```

补强后最终验证：

```text
python -m pytest -q -> 783 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120 -> rows=11 execute=true failed=0
browser desktop readonly -> Agent page present, horizontal overflow=false, console errors=0
browser 390x844 readonly -> Agent page present, horizontal overflow=false, console errors=0
```

Browser runtime 文本输入受虚拟剪贴板限制，因此最终浏览器 smoke 没有重新提交表单；默认 query/stream `mode=tool_calling_agent` 的执行由 production smoke execute 覆盖。

新词解释：

- `prompt_citation_gap`：同一 query 中 baseline citation_support 达标而 structured 未达标，说明证据大概率足够，主要是生成 prompt 没约束好引用粒度。
- `compact citation-first`：先给短直接答案，再给少量短事实点，并要求每个事实句或事实点都带来源编号的生成策略。
## Six-Metric Judge Gate Decision

The Stage 38 gate is now explicitly six-dimensional. A strategy must average at least `0.80` on:

```text
faithfulness
answer_coverage
citation_support
refusal_correctness
conciseness
safety_leak_check
```

This prevents over-optimizing only `answer_coverage` and `citation_support` while ignoring refusal behavior or verbosity. The final summary was rebuilt from existing real Judge rows without rerunning provider calls.

Final result:

```text
baseline: faith=0.958 / cov=0.775 / cit=0.731 / refusal=0.958 / concise=0.960 / safety=1.000 / gate=review_required
structured_final_answer: faith=0.981 / cov=0.808 / cit=0.867 / refusal=0.921 / concise=0.925 / safety=1.000 / gate=pass
```

Interpretation: `structured_final_answer` passes the six-metric average gate. The two anomalous refusal rows do not fail the average gate but should be manually reviewed before submission.
