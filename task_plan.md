# 阶段 32 任务计划：ReAct Agent 决策升级 + 工具调用实时可视化

## 目标

在阶段 31「FAISS 向量索引与父子块检索」已完成、提交、创建 `phase-31-complete` tag 并合并到 `main` 的基础上，进入阶段 32：把现有固定 agentic RAG 状态图升级为 LLM tool-calling 驱动的 ReAct 循环，并通过 SSE 在前端实时展示“正在判断、准备调用工具、工具返回结果、准备回答”等可审计步骤。

建议分支：`codex/phase-32-react-agent-tool-observability`

本阶段只做只读 RAG Agent 能力增强，不新增爬虫、不新增外部资料来源、不做写入型工具、不做登录系统、不改变 `/chat` 默认链路。阶段完成后停在用户人工核验前，不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。

## 背景

阶段 31 已补齐 FAISS 与父子块，底层检索和回答上下文更稳。当前 Agent 主要有两套路径：

1. default `AgentService`：由 `detect_intent()` 规则决定调用 `hybrid_search_knowledge`、`answer_with_citations`、`list_sources` 或 `get_source_detail`。
2. agentic LangGraph：固定 `retrieve -> grade -> rewrite -> re_retrieve -> grade -> generate -> citation_check`，其中 `grade_router()` 用硬编码规则决定下一步。

这说明系统已经有 Agent 工具、workflow steps、SSE token 流式输出和前端步骤展示基础，但还不是真正让 LLM 自主决定下一步。阶段 32 的核心是：让 LLM 在受控工具集合内选择 action，并把 action/observation 过程实时展示给用户。

## Phase 顺序

### Phase 0：启动校准与规划落盘

状态：已完成。

本 Phase 解决的问题：确认阶段 32 的正确起点，避免从阶段 31 未合并状态或旧文档描述继续开发。

RAG 链路位置：版本基线和协作边界，不改运行链路。

为什么现在做：ReAct 会改 Agent 编排和前端流式协议，必须先确认阶段 31 tag、main 合并关系和工作区状态。

- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读 `task_plan.md`、`findings.md`、`progress.md`。
- 运行 `git status -sb`、`git log --oneline -5`。
- 确认 `phase-31-complete` 存在，且是 `main` 的祖先。
- 从阶段 31 合并后的 `main` 创建或切换到 `codex/phase-32-react-agent-tool-observability`。
- 校准三份 planning 文件，记录分支、基线和提交边界。

完成记录：

- 已确认 `main -> 93ee058 Merge phase 31 faiss parent child retrieval`。
- 已确认 `phase-31-complete -> b03bb47 Complete phase 31 faiss parent child retrieval`。
- 已确认 `phase-31-complete` 是 `main` 的祖先，未移动任何已有阶段 tag。
- 已从 `main` 创建并切换到 `codex/phase-32-react-agent-tool-observability`。
- 已确认阶段 32 结束前不执行 `git add`、commit、tag、push 或 PR。

验证方式：

```text
git status -sb
git log --oneline -5
git tag --list "phase-31-complete"
git merge-base --is-ancestor phase-31-complete main
```

### Phase 1：阶段 32 设计文档

状态：已完成。

本 Phase 解决的问题：先固定 ReAct action 集合、工具权限、SSE 事件协议、前端展示边界和安全策略，避免实现时把 Agent 做成不可控黑盒。

RAG 链路位置：Agent 编排层与前端观测层设计。

为什么现在做：ReAct 会增加模型决策和循环，必须先把“模型能做什么、不能做什么、前端展示什么”写清楚。

- 新增 `docs/stage32_react_agent_observability.md`。
- 明确 ReAct 循环：Plan summary -> Action -> Observation -> Decide next action -> Final answer/refusal。
- 明确只读 action 集合：`search_knowledge`、`rewrite_query`、`answer_with_citations`、`refuse`。
- 明确不展示原始 hidden thought，只展示安全的 `reasoning_summary` / `step_summary`。
- 明确循环上限、工具调用上限、token 上限、重复 query 处理和错误收敛策略。
- 明确 `/agent/query/stream` 新增事件不破坏已有 `token` / `metadata` / `done` / `error`。

验证方式：

```text
python -m pytest tests\test_stage32_design.py -q
```

完成记录：

- 已新增 `docs/stage32_react_agent_observability.md`。
- 已明确 ReAct action、工具权限、SSE 新事件、安全边界、循环控制、评测方式和完成标准。
- 已新增 `tests/test_stage32_design.py`，锁定 action 集合、工具边界、SSE 事件和敏感信息边界。
- 验证通过：`python -m pytest tests\test_stage32_design.py -q`，`2 passed`。

### Phase 2：ReAct 工具调用契约与模型 action schema

状态：已完成。

本 Phase 解决的问题：为 LLM 自主选择工具建立稳定的数据结构，让真实模型和 deterministic 测试都能走同一套 action contract。

RAG 链路位置：Agent 决策层与工具层之间。

为什么现在做：没有结构化 action schema，就只能解析自然语言，容易不稳定、难测试。

- 新增或扩展 `app/services/agent/react_actions.py`。
- 定义 `ReActAction`、`ReActObservation`、`ReActStepRecord`、`ReActRunResult`。
- 定义 action 类型：`search_knowledge`、`rewrite_query`、`answer_with_citations`、`refuse`、`final_answer`。
- 为真实 OpenAI-compatible provider 设计 tool-calling 或结构化 JSON action 入口。
- 为 deterministic provider 增加可测试的规则式 action planner，保证 CI 不依赖真实 API。
- 保留 `AgentToolbox` 作为唯一工具执行边界，不绕过 Brain、citation、refusal 和 source 约束。

验证方式：

```text
python -m pytest tests\test_react_actions.py tests\test_agent_tools.py -q
```

完成记录：

- 已新增 `app/services/agent/react_actions.py`。
- 已定义 `ReActAction`、`ReActObservation`、`ReActStepRecord`、`ReActRunResult`。
- 已固定 action 类型：`search_knowledge`、`rewrite_query`、`answer_with_citations`、`refuse`、`final_answer`。
- 已新增 `DeterministicReActPlanner`，覆盖检索、改写、回答和拒答收敛路径。
- 已新增 `tests/test_react_actions.py`。
- 验证通过：`python -m pytest tests\test_react_actions.py tests\test_agent_tools.py -q`，`12 passed`。

### Phase 3：ReAct Agent Service 实现

状态：已完成。

本 Phase 解决的问题：用 LLM action 决策替代固定 `grade_router` 主导的下一步选择，让模型在受控范围内决定是否检索、改写、回答或拒答。

RAG 链路位置：`/agent/query` 的 agentic 编排层。

为什么现在做：阶段 31 后检索和 prompt 地基已稳，可以把上层决策从硬编码状态图升级为可解释的 ReAct 循环。

- 新增 `app/services/agent/react_service.py`。
- 实现 `ReActAgentService.query()`：读取问题和 history，调用模型选择 action，执行工具，记录 observation，循环直到 final/refuse/上限。
- 默认最大迭代建议 3，最大工具调用建议沿用 request `max_tool_calls`。
- 对重复 query、工具异常、空结果、低证据结果做收敛处理。
- 将最终结果转换为现有 `AgentQueryResponse` 字段，保留 `tool_calls`、`workflow_steps`、`iteration_count`、`citations`、`sources`。
- 保留 default `AgentService` 和旧 agentic 路径作为回退或对照，不破坏显式 mode。

验证方式：

```text
python -m pytest tests\test_react_agent_service.py tests\test_agent_api.py -q
```

完成记录：

- 已新增 `app/services/agent/react_service.py`。
- 已实现 `ReActAgentService.query()`，支持受控 action loop、重复 query 防护、工具异常/空结果收敛、最大 3 轮硬上限。
- 已将 `react_agent` 作为显式 `/agent/query` mode 接入，保留 default 和旧 `agentic` 路径。
- 已扩展 `AgentQueryResult`，让 ReAct 路径返回 `workflow_steps`、`iteration_count` 和 `mode="react_agent"`。
- 已新增 `tests/test_react_agent_service.py`，并更新 `tests/test_agent_api.py` 覆盖显式 `react_agent`。
- 验证通过：`python -m pytest tests\test_react_agent_service.py tests\test_agent_api.py -q`，`24 passed`。

### Phase 4：SSE 实时步骤事件协议

状态：已完成。

本 Phase 解决的问题：让前端不再只显示“正在思考”，而是在模型准备调用工具和工具返回时实时显示当前步骤。

RAG 链路位置：API 流式输出层。

为什么现在做：ReAct 的价值不只在模型自主决策，也在过程可观测、可审计。

- 扩展 `/agent/query/stream`：新增 `agent_step`、`tool_call_start`、`tool_call_result` 事件。
- 保留现有 `token`、`metadata`、`done`、`error` 事件兼容。
- `tool_call_start` 展示工具名和脱敏输入摘要。
- `tool_call_result` 展示结果数量、是否拒答、错误摘要，不展示 provider raw response。
- 让非流式 `/agent/query` 仍返回完整 `workflow_steps`。

验证方式：

```text
python -m pytest tests\test_agent_stream_api.py tests\test_react_stream_events.py -q
```

完成记录：

- 已把 `ReActAgentService` 的运行时事件接入 `/agent/query/stream`。
- 已新增 `agent_step`、`tool_call_start`、`tool_call_result` SSE 事件。
- 已保持 `token`、`metadata`、`done`、`error` 兼容。
- 已新增 `tests/test_react_stream_events.py`。
- 验证通过：`python -m pytest tests\test_agent_stream_api.py tests\test_react_stream_events.py -q`，`8 passed`。

### Phase 5：前端实时步骤可视化

状态：已完成。

本 Phase 解决的问题：把“正在思考”升级为实时步骤时间线，让用户看到 Agent 当前正在哪一步、准备调用什么工具、工具返回了什么摘要。

RAG 链路位置：前端交互和可观测展示层。

为什么现在做：后端已经能流式发送步骤事件后，前端必须把这些事件变成可理解界面，而不是只在最后展示 workflow steps。

- 修改 `app/frontend/static/app.js`：消费 `agent_step`、`tool_call_start`、`tool_call_result`。
- 修改 `appendAgentThinkingMessage()`，把静态“正在思考”改成动态状态行。
- 新增 live step timeline，运行中逐条追加。
- 最终 `metadata` 到达后，用正式 `workflow_steps` 校准展示。
- 修改 `app/frontend/static/styles.css`，保证桌面和移动端不溢出、不遮挡答案。
- 更新 `tests/test_frontend_app.py` 和必要的 JS/HTML 断言。

验证方式：

```text
python -m pytest tests\test_frontend_app.py -q
```

完成记录：
- 已扩展 `app/frontend/static/app.js`，消费 `agent_step`、`tool_call_start`、`tool_call_result` SSE 事件。
- 已新增 live step timeline，运行中在同一条 Agent assistant 消息里展示步骤、工具准备和工具返回摘要。
- 已扩展 `app/frontend/static/styles.css`，让 live steps 在桌面和移动端不横向溢出。
- 已更新 `tests/test_frontend_app.py`，锁定前端实时事件消费、DOM 容器和样式。
- 验证通过：`python -m pytest tests\test_frontend_app.py -q`，`10 passed`。

### Phase 6：ReAct 评测与回归对照

状态：已完成。

本 Phase 解决的问题：证明 ReAct 不只是“会跑”，还要证明它没有破坏引用、拒答、来源追踪和默认链路。

RAG 链路位置：评测与质量门禁层。

为什么现在做：LLM 自主决策会增加不确定性，必须用 deterministic fixture 和真实 provider smoke 分开验证。

- 新增 `scripts/evaluate_stage32_react_agent.py`。
- 复用阶段 29/30 关键问答样例，增加需要改写、需要再次检索、需要拒答的 ReAct 样例。
- 输出 `data/evaluation/stage32_react_agent_results.csv` 与 summary。
- 对照 default / old agentic / react_agent 三类模式。
- 记录 tool_count、iteration_count、refusal_match、citation_valid、source_count、decision。
- 默认 deterministic，不让真实 API 进入 CI。

验证方式：

```text
python scripts\evaluate_stage32_react_agent.py
python -m pytest tests\test_stage32_react_eval.py -q
```

完成记录：
- 已新增 `scripts/evaluate_stage32_react_agent.py`，使用内存 SQLite、deterministic embedding/chat，并强制关闭真实 reranking provider。
- 已输出 `data/evaluation/stage32_react_agent_results.csv` 和 `data/evaluation/stage32_react_agent_summary.csv`。
- 已对照 `default`、`agentic_langgraph`、`react_agent` 三种模式，记录 tool_count、iteration_count、workflow_step_count、source_count、citation_valid 和 refusal_match。
- 已新增 `tests/test_stage32_react_eval.py`，覆盖 fixture 类别、三模式输出、ReAct 工具/迭代追踪和敏感词边界。
- 验证通过：`python -m pytest tests\test_stage32_react_eval.py -q`，`4 passed`。
- 正式评测通过：`python scripts\evaluate_stage32_react_agent.py`，三模式 `errors=0`，`react_agent` refusal match `1/1`，decision `pass`。

### Phase 7：全量验证、浏览器冒烟与真实 provider smoke

状态：已完成。

本 Phase 解决的问题：确认阶段 32 没有破坏核心 API、前端、SSE、质量报告和现有检索链路。

RAG 链路位置：发布前质量门禁。

为什么现在做：Agent 编排和 SSE 前端都属于用户可见主链路，必须跑全量验证。

- 运行阶段 32 聚焦测试。
- 运行全量 `python -m pytest -q`。
- 重跑阶段 30 评分，确保 `overall >= 83.17`。
- 浏览器检查 `/`：ReAct 流式步骤显示、工具调用卡片、最终答案、移动端布局、console errors。
- API 冒烟：`/health`、`/quality-report`、`/agent/query`、`/agent/query/stream`、`/chat`、`/search/hybrid`。
- 真实 provider 只做人工显式 smoke，不作为 CI 前提。

完成记录：
- 阶段 32 聚焦测试通过：`106 passed`。
- 全量测试通过：`python -m pytest -q` -> `629 passed, 1 warning`。
- 阶段 30 评分保持：`overall=83.17 grade=B release_decision=review_required`。
- API smoke 通过：`/health 200`、`/quality-report 200`、`/chat 200`、`/agent/query 200`、`/agent/query/stream 200`、`/search/hybrid 200`。
- 浏览器桌面 smoke 通过：折叠“查看思考过程”存在、实时工具卡片不可见、最终答案存在、横向溢出=false、console errors=0。
- 浏览器移动端 390x844 smoke 通过：折叠“查看思考过程”存在、实时工具卡片不可见、最终答案存在、横向溢出=false、console errors=0。
- 自动验证未依赖真实 provider；浏览器 smoke 使用 8012 deterministic 服务实例。

### Phase 8：文档、Obsidian 与人工核验收尾

状态：已完成。

本 Phase 解决的问题：把阶段 32 的设计、验证、风险和面试表达沉淀到普通文档与本地 Obsidian。

RAG 链路位置：项目交接与知识沉淀层。

为什么现在做：ReAct、tool calling、SSE 可视化都是面试高价值能力，必须写清楚为什么这样设计和如何防失控。

- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 判断是否需要更新 `AGENT.MD`，若阶段 32 改变后续协作规则或下一步路线则更新。
- 新增 `docs/phase_reviews/phase-32.md` 人工核验草稿。
- 更新 Obsidian 阶段页、阶段汇报索引、Phase 0 到最终 Phase 小汇报。
- 最终保持未提交状态，等待用户人工核验。

完成记录：
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD`。
- 已新增 `docs/phase_reviews/phase-32.md`。
- 已新增 Obsidian 阶段页、阶段汇报索引、阶段汇总和 `ReAct Agent 可观测性` 知识点。
- 已更新 Obsidian `阶段索引.md`、`阶段汇报索引.md` 和 `分类/Agent 工具调用.md`。
- 仍保持人工核验前状态：未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

## 完成标准

- 新增阶段 32 设计文档，明确 ReAct action、工具权限、循环上限、SSE 事件和安全边界。
- LLM 可通过 tool-calling 或结构化 action schema 自主选择检索、改写、回答、拒答。
- deterministic provider 有稳定测试路径，不依赖真实 API。
- ReAct 循环最多 3 轮或受 `max_tool_calls` 限制，不会无限循环。
- 前端运行中能实时展示当前步骤、准备调用工具、工具结果摘要，不只显示“正在思考”。
- `/agent/query/stream` 保持现有 token/metadata/done/error 兼容。
- `tool_calls`、`workflow_steps`、`iteration_count`、`citations`、`sources` 继续可追踪。
- 不展示原始 hidden thought，不写入 provider raw response。
- 不新增写入型工具，不新增爬虫，不新增外部资料来源。
- 核心 API 不破坏：`POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`POST /agent/query/stream`、`GET /quality-report`。
- 阶段 30 评分不低于 83.17。
- 全量测试通过，浏览器冒烟通过。
- 文档和 Obsidian 草稿完成。
- 未经用户人工核验，不 git add / commit / tag / push / PR。
