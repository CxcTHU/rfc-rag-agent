# 阶段 32 设计：ReAct Agent 决策升级与工具调用实时可视化

## 目标

阶段 32 在阶段 31 的 FAISS 向量索引与父子块检索基线上，升级 Agent 编排方式：

```text
用户问题
-> ReAct action planner
-> 受控 action schema
-> AgentToolbox 只读工具
-> Brain / citation / refusal / responsibility_gate
-> SSE 实时步骤事件
-> 前端工具调用时间线
-> 最终 AgentQueryResponse metadata 校准展示
```

本阶段的核心不是增加更多资料，也不是开放写入能力，而是把当前由 `grade_router` 固定决策的 agentic RAG，升级为受控的 LLM action loop。模型可以选择检索、改写、回答或拒答，但工具权限、循环次数、引用约束和安全展示仍由后端控制。

## 背景

当前系统已有三条相关链路：

- default `AgentService`：规则式 `detect_intent()` 决定调用 `AgentToolbox` 的哪个只读工具，稳定、可测，是回归基线。
- old agentic LangGraph：固定执行 `retrieve -> grade -> rewrite -> re_retrieve -> grade -> generate -> citation_check`，下一步由 `grade_router()` 硬编码决定。
- `/agent/query/stream`：已有 `token`、`metadata`、`done`、`error` SSE 事件，前端可流式显示答案，但工具步骤只在最终 metadata 到达后展示。

阶段 32 保留 default 和 old agentic 作为对照或回退，新建 `react_agent` 路径，让模型在后端定义的 action schema 中选择下一步。

## 新词解释

- ReAct：让模型在“决策摘要 -> 动作 -> 观察结果 -> 下一步决策”的循环中工作。本项目只展示安全摘要，不展示模型原始 hidden thought。
- action schema：后端允许模型输出的结构化动作格式，例如 `{"action":"search_knowledge","query":"..."}`。它限制模型只能请求允许的只读操作。
- observation：工具执行后的结构化结果摘要，例如返回了多少条检索结果、是否触发拒答、是否有错误。
- tool calling：模型不直接访问数据库或网络，而是输出工具名和参数，由后端执行工具并把 observation 交回模型或流程。

## ReAct Action Schema

阶段 32 允许的 action 类型固定为：

| action | 作用 | 工具边界 |
| --- | --- | --- |
| `search_knowledge` | 基于当前 query 检索知识库 | 只能调用 `AgentToolbox.hybrid_search_knowledge` |
| `rewrite_query` | 在证据不足或 query 不清楚时改写问题 | 只生成新的检索 query，不写库、不联网 |
| `answer_with_citations` | 基于检索证据生成引用式回答 | 只能调用 `AgentToolbox.answer_with_citations`，继续复用 Brain |
| `refuse` | 证据不足、越界或责任边界命中时拒答 | 使用统一 refusal 结构 |
| `final_answer` | 收敛为最终回答 | 只能基于已产生的安全回答摘要，不绕过 citation |

建议结构：

```json
{
  "action": "search_knowledge",
  "query": "rock-filled concrete filling capacity",
  "reasoning_summary": "需要先检索资料库确认证据",
  "input_summary": "query=rock-filled concrete filling capacity"
}
```

约束：

- 不接受 schema 之外的 action。
- 不接受写入型 action。
- 不接受爬虫、外部网页访问、文件写入、数据库修改或任意 SQL。
- `reasoning_summary` 只能是面向用户和日志的安全摘要，不是 hidden thought。

## 工具权限

ReAct 工具必须复用 `AgentToolbox` 和 Brain 链路：

```text
search_knowledge
-> AgentToolbox.hybrid_search_knowledge

answer_with_citations
-> AgentToolbox.answer_with_citations
-> BrainService
-> parent-child context
-> evidence confidence
-> responsibility_gate
-> citation extraction
-> refusal handling
```

这样保证 ReAct 不能绕过：

- citation 和 source 追踪
- evidence confidence
- responsibility_gate
- refusal 约束
- qa_logs 和现有可观测字段

## 循环控制

默认策略：

- 最大 ReAct 迭代次数：3。
- 最大工具调用次数：沿用请求中的 `max_tool_calls`，并受后端硬上限保护。
- 重复 query 防护：同一规范化 query 不重复检索；重复时记录 observation，并要求改写或收敛。
- 工具异常收敛：工具失败后记录安全错误摘要；连续失败或达到上限时拒答。
- 空结果收敛：空结果可触发一次 `rewrite_query`，再次为空则拒答。
- 最终必须进入 `answer_with_citations`、`refuse` 或 `final_answer`，不能无限循环。

## SSE 事件协议

保留阶段 25 已有事件：

```text
token
metadata
done
error
```

新增阶段 32 事件：

```text
agent_step
tool_call_start
tool_call_result
```

示例：

```text
event: agent_step
data: {"step_summary":"正在判断是否需要检索","action":"search_knowledge","iteration":1}

event: tool_call_start
data: {"tool_name":"search_knowledge","input_summary":"query=rock-filled concrete filling capacity","iteration":1}

event: tool_call_result
data: {"tool_name":"search_knowledge","observation_summary":"returned 5 results","succeeded":true,"iteration":1}
```

兼容性要求：

- 旧前端只消费 `token` 和 `metadata` 时仍能得到最终答案。
- 新前端实时消费新增事件，并在最终 `metadata.workflow_steps` 到达后校准展示。
- `error` 事件不包含敏感凭据、授权头、供应商原始响应或受限全文。

## 前端展示

阶段 32 将“正在思考”升级为可审计但不刷屏的运行状态：

- `agent_step`：运行中只更新简洁中文状态，最终折叠面板中展示当前决策阶段。
- `tool_call_start`：运行中显示“正在调用：某工具”，最终折叠面板中展示工具名和脱敏输入摘要。
- `tool_call_result`：运行中显示工具已返回或失败，最终折叠面板中展示结果数量、拒答状态或错误摘要。
- `metadata`：最终校准正式 `workflow_steps`、`tool_calls`、`sources`、`citations`、`iteration_count` 和 `refusal_category`。

前端不展示：

- 原始 hidden thought
- 供应商原始响应
- 敏感凭据或授权头
- 受限全文

## 评测方式

阶段 32 评测分三层：

1. action schema 单元测试：非法 action、重复 query、工具调用上限、拒答收敛。
2. ReAct service 测试：deterministic planner 覆盖检索、改写、回答、拒答。
3. 端到端对照评测：default、old agentic、react_agent 三路对照，记录 `tool_calls`、`workflow_steps`、`iteration_count`、`sources`、`citations`、`refusal_category`。

默认测试必须使用 deterministic provider 或 fixture。真实 MIMO/Jina provider 只做显式 smoke，不进入 CI 或本地全量测试前提。

## 安全边界

- 不新增爬虫。
- 不新增外部资料来源。
- 不新增写入型 Agent 工具。
- 不改变 `/chat` 默认链路。
- 不删除 default Agent。
- 不删除 old agentic 路径。
- 不保存供应商原始响应。
- 不把敏感凭据、授权头、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 不展示模型原始 hidden thought，只展示 `step_summary`、`input_summary`、`observation_summary` 和 `decision_summary`。

## 完成标准

- ReAct Agent 能通过受控 action schema 自主选择检索、改写、回答或拒答。
- `/agent/query/stream` 能实时推送 `agent_step`、`tool_call_start`、`tool_call_result`、`token`、`metadata`、`done`。
- 前端能显示 Agent 当前步骤和工具调用摘要，不只显示“正在思考”。
- `tool_calls`、`workflow_steps`、`iteration_count`、`sources`、`citations`、`refusal_category` 继续可追踪。
- default、old agentic、react_agent 有评测对照。
- 全量测试、阶段 30 评分和浏览器冒烟通过。
- 阶段结束停在用户人工核验前，不执行 git add、commit、tag、push 或 PR。
