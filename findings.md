# 阶段 32 发现与关键决策

## 当前 Git 基线

当前工作区在 `main`，且与 `origin/main` 同步。阶段 31 已完成提交、tag 与合并。

```text
main -> 93ee058 Merge phase 31 faiss parent child retrieval
phase-31-complete -> b03bb47 Complete phase 31 faiss parent child retrieval
git merge-base --is-ancestor phase-31-complete main: passed
git status -sb: ## main...origin/main
```

决策：阶段 32 的正确起点是 `main -> 93ee058`，不是阶段 31 开发分支，也不是阶段 31 等待核验的旧文档状态。已从 `main` 创建并切换到 `codex/phase-32-react-agent-tool-observability`，后续阶段 32 开发均在该分支进行。

## 现有 Agent 架构观察

### 观察 1：default Agent 仍是规则意图路由

位置：`app/services/agent/service.py` 与 `app/services/agent/tools.py`。

当前行为：

- `detect_intent()` 根据规则判断 answer/search/source 意图。
- `AgentToolbox` 封装只读工具：`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- `AgentService.query()` 根据规则调用一个主要工具，然后返回 `AgentQueryResult`。

价值：这条链路稳定、可测、引用和拒答约束清晰。

限制：不是 LLM 自主选择下一步，也不会根据 observation 再决定是否改写 query 或再次检索。

关键决策：阶段 32 不删除 default Agent；保留它作为简单问题和回归基线。ReAct 应作为新的 agentic 能力接入，不能破坏 default。

### 观察 2：现有 agentic LangGraph 是固定状态图

位置：`app/services/agentic/graph.py` 与 `app/services/agentic/nodes.py`。

当前图：

```text
retrieve -> grade -> rewrite -> re_retrieve -> grade -> generate -> citation_check
```

关键函数：

```python
def grade_router(state: AgenticState) -> str:
    if state.get("evidence_sufficient", False):
        return "generate"
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return "generate"
    return "rewrite"
```

这说明“下一步怎么走”仍由硬编码函数决定，不是 LLM 自主基于 action/observation 决策。

关键决策：阶段 32 的技术主线应从固定 `grade_router` 升级为 ReAct action loop。模型可以选择工具，但工具集合、次数、参数和最终引用约束仍由后端控制。

### 观察 3：SSE 已有 token 流，但步骤不是实时推送

位置：`app/api/agent.py` 与 `app/frontend/static/app.js`。

当前 `/agent/query/stream` 事件：

```text
token
metadata
done
error
```

当前前端行为：

- `appendAgentThinkingMessage()` 先展示“正在思考...”
- token 到达后替换为答案文本。
- `metadata` 到达后才渲染 `workflow_steps` 或 `tool_calls`。

限制：检索、改写、工具调用、证据判断都发生在后端内部，前端只有最后才知道过程。用户在等待时仍看不到“当前正在哪一步”。

关键决策：阶段 32 应新增 SSE 事件：`agent_step`、`tool_call_start`、`tool_call_result`。这些事件先于最终 `metadata` 到达，前端实时更新状态线。

## ReAct 设计关键决策

### Phase 1 落盘结论

`docs/stage32_react_agent_observability.md` 已固定阶段 32 的核心边界：ReAct 只能输出受控 action，工具执行必须复用 `AgentToolbox` 与 Brain，SSE 在保留 `token` / `metadata` / `done` / `error` 的基础上新增 `agent_step` / `tool_call_start` / `tool_call_result`，前端和日志只展示安全摘要，不展示 hidden thought 或 provider raw response。

验证：`python -m pytest tests\test_stage32_design.py -q` -> `2 passed`。

### Phase 2 Action Schema 结论

`app/services/agent/react_actions.py` 已建立阶段 32 的代码级契约：只允许 `search_knowledge`、`rewrite_query`、`answer_with_citations`、`refuse`、`final_answer` 五类 action；`search_knowledge` 映射到 `AgentToolbox.hybrid_search_knowledge`，`answer_with_citations` 映射到 `AgentToolbox.answer_with_citations`，没有任何写入型 action。`DeterministicReActPlanner` 先覆盖稳定测试路径，真实 provider 的 tool-calling 能力后续只作为运行时能力和显式 smoke。

验证：`python -m pytest tests\test_react_actions.py tests\test_agent_tools.py -q` -> `12 passed`。

### Phase 3 ReAct Service 结论

`app/services/agent/react_service.py` 已把 action schema 串成可运行的 ReAct loop：默认 deterministic planner 先检索，再根据 observation 回答、改写或拒答；真实 provider 可通过结构化 JSON action 规划下一步。`react_agent` 已作为显式 API mode 接入，但 default 和旧 `agentic` LangGraph 路径没有删除，便于后续评测对照和回退。

关键边界：ReAct 的检索仍调用 `AgentToolbox.hybrid_search_knowledge`，回答仍调用 `AgentToolbox.answer_with_citations`，因此继续复用 Brain、parent-child context、citation、evidence confidence、responsibility_gate 和 refusal 约束。

验证：`python -m pytest tests\test_react_agent_service.py tests\test_agent_api.py -q` -> `24 passed`。

### Phase 4 SSE 事件结论

`/agent/query/stream` 已能在 `react_agent` 路径中实时转发 `agent_step`、`tool_call_start`、`tool_call_result`，并继续保留 `token`、`metadata`、`done`、`error`。这些事件来自 `ReActAgentService` 的安全摘要，不包含 hidden thought、provider raw response、API key 或 Bearer token。

验证：`python -m pytest tests\test_agent_stream_api.py tests\test_react_stream_events.py -q` -> `8 passed`。

### Phase 5 前端实时步骤结论

前端已把新增 SSE 事件接入同一条 Agent assistant 消息。最终验收时，展示策略从“运行中铺开 live step timeline”调整为更克制的中文状态：运行中只显示“正在思考”“正在调用：检索知识库”等状态，不把每个 function call 事件刷成卡片；最终 `metadata` 到达后，由正式 `workflow_steps` / `tool_calls` 校准可折叠“查看思考过程”面板。展示字段只使用 `step_summary`、`input_summary`、`observation_summary`、`tool_name`、`action` 等白名单摘要，不展示 hidden thought 或 provider raw response。

样式上，折叠思考面板使用紧凑布局、`overflow-wrap: anywhere` 和 8px border radius，防止长 query、工具名或摘要在桌面与移动端横向溢出。

验证：`python -m pytest tests\test_frontend_app.py -q` -> `10 passed`。

### Phase 6 评测对照结论

`scripts/evaluate_stage32_react_agent.py` 已建立阶段 32 的 deterministic 三路对照：`default`、旧 `agentic_langgraph`、新 `react_agent`。脚本使用内存 SQLite fixture、`DeterministicEmbeddingProvider`、`DeterministicChatModelProvider`，并显式设置 `RERANKING_ENABLED=false` 后清理 settings cache，避免真实 MIMO/Jina/reranking provider 进入自动测试或默认评测。

正式输出写入 `data/evaluation/stage32_react_agent_results.csv` 和 `data/evaluation/stage32_react_agent_summary.csv`。当前结果：三模式 `errors=0`、`refusal_matches=1/1`、decision 均为 `pass`；`react_agent` 平均 tool_count 为 `2.00`，可追踪 `workflow_step_count` 与 `iteration_count`。CSV 不包含 `api_key`、`bearer`、`authorization`、`raw_response`。

验证：`python -m pytest tests\test_stage32_react_eval.py -q` -> `4 passed`；`python scripts\evaluate_stage32_react_agent.py` -> 三模式通过。

### Phase 7 验证结论

最新代码已完成阶段 32 聚焦测试、全量 pytest、阶段 30 评分、核心 API smoke 和浏览器桌面/移动端 smoke。阶段 32 聚焦测试为 `106 passed`；全量 `python -m pytest -q` 为 `629 passed, 1 warning`；`scripts/score_stage30_quality.py` 仍为 `overall=83.17 grade=B release_decision=review_required`。

浏览器验证确认：桌面端与 390x844 移动端均有折叠“查看思考过程”面板，实时工具卡片不可见，最终答案存在，横向溢出=false，console errors=0。核心 API smoke：`/health`、`/quality-report`、`/chat`、`/agent/query`、`/agent/query/stream`、`/search/hybrid` 均返回 200，且 stream 包含 `agent_step` 与 `tool_call_result`。

### 决策 1：展示安全摘要，不展示原始 hidden thought

ReAct 在面试表达中可以讲 Thought -> Action -> Observation，但产品和日志里不应展示模型完整内部推理。原因：

- 原始推理可能包含不稳定、自相矛盾或过长内容。
- 原始推理可能泄露 prompt 细节或 provider 行为。
- 对用户真正有价值的是“准备做什么”和“做完结果是什么”。

阶段 32 展示：

```text
step_summary: 正在判断是否需要检索
action: search_knowledge
input_summary: query=...
observation_summary: returned 5 results
decision_summary: 证据不足，准备改写查询
```

不展示：

```text
raw hidden thought
provider raw response
API key / Bearer token
完整受限全文
```

### 决策 2：工具调用必须复用 `AgentToolbox`

ReAct 不应该绕过现有工具边界。所有动作都应经过当前稳定工具：

- 检索：`AgentToolbox.hybrid_search_knowledge`
- 回答：`AgentToolbox.answer_with_citations`
- 来源查询：如本阶段需要，复用 `list_sources` / `get_source_detail`
- 拒答：后端统一生成 refusal result

这样能继续复用 Brain、citation、parent-child context、EvidenceConfidence、responsibility_gate 和 qa_logs。

### 决策 3：真实 provider 和 deterministic provider 分层

阶段 32 需要“LLM tool calling”，但自动测试不能依赖真实 MIMO/Jina。

建议：

- 真实 OpenAI-compatible provider：支持 tool calling 或结构化 JSON action。
- deterministic provider：用规则式 planner 生成固定 action，覆盖检索、改写、拒答、最终回答路径。
- 评测脚本默认 deterministic，真实 provider 只做人工 smoke。

这能保证“工程可测”和“真实能力演示”两者分开。

### 决策 4：不用优先做 embedding 额度缓存，但必须做循环控制

用户已明确不需要优先控制额度，因此阶段 32 不把 query embedding 缓存作为主任务。

但必须做：

- 最大 ReAct 迭代次数，建议 3。
- 最大工具调用数，尊重 request `max_tool_calls`。
- 重复 query 去重或标记，避免同一 query 反复检索。
- 工具异常后收敛到拒答或基于已有证据回答。
- 最终必须进入 `final_answer` 或 `refuse`，不能无限循环。

### 决策 5：SSE 协议保持向后兼容

新增事件不能破坏阶段 25 的流式输出契约。

保留：

```text
token
metadata
done
error
```

新增：

```text
agent_step
tool_call_start
tool_call_result
```

前端如果不识别新事件，也应仍能靠 `token` 和 `metadata` 得到最终答案。

## 风险与防线

- 风险：模型输出非法 action。
  - 防线：Pydantic schema 校验；非法 action 记为失败 observation，并要求模型重选；超过次数则拒答。
- 风险：ReAct 循环成本过高。
  - 防线：最大迭代、最大工具调用、重复 query 检测。
- 风险：模型绕过引用或直接编造。
  - 防线：最终回答优先通过 `answer_with_citations`，继续使用 Brain 和 citation extraction。
- 风险：前端实时步骤泄露敏感信息。
  - 防线：只发送脱敏摘要，不发送 provider raw response、API key、受限全文。
- 风险：ReAct 相比旧 agentic 退化。
  - 防线：评测对照 default / old agentic / react_agent，保留旧路径作回退。
- 风险：SSE 新事件破坏旧浏览器逻辑。
  - 防线：保持 `metadata` 终态契约；前端 parser 对未知事件可忽略。

## 新词解释

- ReAct：是什么 -> 让模型按“思考摘要、选择动作、观察结果、再决定”的循环工作；在本项目哪里出现 -> 阶段 32 的新 Agent 编排；作用 -> 替代固定 `grade_router`，让模型自主决定是否检索、改写、回答或拒答；面试怎么说 -> “我把硬编码状态图升级成受控 ReAct 循环，模型能选工具，但工具权限、次数和引用约束仍由后端控制”。
- tool calling：是什么 -> 模型输出要调用的工具名和参数，由后端执行工具后把结果交回模型；在本项目哪里出现 -> 阶段 32 的 action schema；作用 -> 让 LLM 决策和真实工具执行解耦；面试怎么说 -> “我没有让模型直接访问数据库，而是通过受控 tool schema 调用只读 RAG 工具”。
- SSE：是什么 -> 服务端持续向浏览器推送事件的 HTTP 流式协议；在本项目哪里出现 -> `/agent/query/stream`；作用 -> 已用于 token 流式输出，阶段 32 会扩展为步骤事件；面试怎么说 -> “我用 SSE 把 Agent 的工具调用过程实时推给前端，提升可观测性”。
- Observation：是什么 -> 工具执行后的结构化结果摘要；在本项目哪里出现 -> ReAct loop 每次 action 后；作用 -> 让模型根据检索结果、错误或拒答状态决定下一步；面试怎么说 -> “每次工具调用都会形成 observation，既给模型继续决策，也给前端审计展示”。

## 面试表达准备

阶段 32 可以这样讲：

> 阶段 32 我把原来固定的 agentic RAG 状态图升级成 ReAct Agent。旧版本由 `grade_router` 硬编码决定检索后是生成还是改写，新版本让 LLM 在受控 action schema 里选择检索、改写、回答或拒答。所有工具仍复用 `AgentToolbox` 和 Brain 链路，所以不会绕过引用、来源追踪和拒答约束。同时我扩展了 `/agent/query/stream` 的 SSE 协议，不只流式输出答案 token，还实时推送 agent_step、tool_call_start、tool_call_result，让前端能显示 Agent 当前正在哪一步、准备调用什么工具、工具返回了多少结果。这样既提升了 Agent 自主性，也提升了可观测性和面试表达价值。
