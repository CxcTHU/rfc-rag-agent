# 阶段 22：前端 Agentic 可视化与可观测增强

## 目标

阶段 21 已经完成 LangGraph Agentic RAG，并通过 `/agent/query` 的 `mode="agentic"` 作为可选链路接入。本阶段不改变默认 RAG 问答逻辑，而是把 agentic 链路从“后端能跑”推进到“前端能看懂、能核验、能排查”：

```text
/agent/query mode="agentic"
-> 返回 answer / sources / citations
-> 返回 workflow_steps / iteration_count / invalid_citations / refusal_category
-> 前端 Agent 面板展示 default / agentic 模式切换
-> 前端展示迭代过程、引用有效性和拒答分类
```

阶段 22 的核心产物是只读可观测能力，不做写入型 Agent 工具、不做登录系统、不做部署优化、不新增爬虫，也不让真实 API 成为测试前提。

## 背景

阶段 21 的 agentic 图包含：

```text
retrieve -> grade -> rewrite -> re_retrieve -> generate -> citation_check
```

现有前端 Agent 面板只能提交普通 Agent 任务，并展示回答、引用 badge、来源 badge 与工具调用记录。后端已经支持 `AgentQueryRequest.mode`，但 `AgentQueryResponse` 还没有把 agentic 特有的 `iteration_count`、`invalid_citations`、`workflow_steps` 暴露为独立响应字段，前端也没有模式切换控件。

本阶段解决的问题是：用户不仅要知道“答案是什么”，还要能看到系统经历了几轮检索、哪些节点执行过、为什么拒答、哪些引用不可信。

## 范围

本阶段做：

- 扩展 `/agent/query` 响应契约，向前端暴露 agentic 可观测字段。
- 前端 Agent 面板新增 `default` / `agentic` 模式切换。
- `submitAgent()` 在 agentic 模式下传递 `mode="agentic"`。
- 前端显示 `workflow_steps` 时间线或步骤列表。
- 前端显示 `iteration_count`。
- 前端在 `invalid_citations` 非空时标记无效引用。
- 前端在拒答时展示拒答分类。
- 补充 API 与前端相关测试。
- 同步 README、progress、architecture、data_sources、AGENT.MD、Obsidian 与阶段验收报告。

本阶段不做：

- 不改默认 `/chat` 或 default Agent 行为。
- 不把 agentic 设为默认链路。
- 不新增外部数据源、爬虫、登录、部署优化或写入型 Agent 工具。
- 不引入 React/Vue/Vite/Node 构建链。
- 不把真实 API key、Bearer token、供应商原始敏感响应或受限全文写入任何可提交产物。

## 响应契约

`POST /agent/query` 保持现有字段：

```text
question
answer
tool_calls
search_results
sources
citations
refused
refusal_reason
reasoning_summary
```

阶段 22 新增只读观测字段：

| 字段 | 类型 | default 模式 | agentic 模式 |
|---|---|---|---|
| `mode` | string | `default` | `agentic` |
| `workflow_steps` | list | `[]` | LangGraph 节点步骤 |
| `iteration_count` | int | `0` | 实际 rewrite/re-retrieve 迭代次数 |
| `invalid_citations` | list[int] | `[]` | 引用自检发现的无效编号 |
| `refusal_category` | string/null | 按普通拒答原因映射 | 按 agentic 状态/拒答原因映射 |

`workflow_steps` 中每个元素使用前端友好的结构：

```text
name
input_summary
output_summary
succeeded
error
```

为了兼容阶段 21，后端可以继续把 agentic `workflow_steps` 映射到现有 `tool_calls`；阶段 22 的前端优先读取新的 `workflow_steps`，没有时回退到 `tool_calls`。

## 拒答分类

阶段 22 前端展示的拒答分类包括：

| 分类 | 含义 | 判定来源 |
|---|---|---|
| `responsibility_gate_triggered` | 用户要求系统替代规范审查、工程判定、验收或专家签字 | `responsibility_gate` 命中，或 `refusal_reason` 含 responsibility 信号 |
| `evidence_insufficient` | 检索到的资料不足以支撑回答 | 空结果、低证据置信度、迭代上界后仍不足 |
| `off_topic` | 问题离开堆石混凝土 / 水利工程资料范围 | topic anchor 不命中或拒答原因含 off-topic |

分类是解释字段，不替代现有 `refused` 和 `refusal_reason`。前端仍展示原始拒答原因，分类只帮助用户快速理解。

## 前端交互

Agent 面板新增模式控件：

```text
模式：default | agentic
```

交互规则：

- 默认值为 `default`。
- `default` 模式不传 `mode="agentic"`，保持现有行为。
- `agentic` 模式向 `/agent/query` 请求体加入 `mode: "agentic"`。
- 结果区域显示当前模式、迭代次数和拒答分类。
- 工具调用侧栏在 agentic 模式下展示 workflow steps；每步显示节点名、输入摘要、输出摘要、成功/失败和错误摘要。
- 引用区域或 Agent 回答 meta 区在 `invalid_citations` 非空时显示“无效引用 [n]”标记。

## 节点展示

阶段 22 实现后，后端写入 `workflow_steps` 的名称已与 LangGraph 图节点对齐：

| 节点名 | 展示含义 |
|---|---|
| `retrieve` | 初始混合检索 |
| `grade` | 证据充分性与 topic anchor 评估 |
| `rewrite` | 证据不足时改写/拆解查询 |
| `re_retrieve` | 用改写后的查询重新检索并合并结果 |
| `generate` | 生成答案或触发责任/证据拒答 |
| `citation_check` | 检查答案引用编号是否在本次来源中有效 |

前端直接展示 `workflow_steps[].name`，不再需要猜测 `rewrite_query` 或 `generate_answer` 等旧内部名。

## 测试方案

聚焦测试：

```text
tests/test_frontend_app.py
tests/test_agent_api.py
tests/test_agentic_graph.py
tests/test_stage21_agentic_eval.py
```

必须覆盖：

- 前端 HTML 有 agentic/default 模式控件。
- 静态 JS 包含 `data-agent-mode`、`mode: "agentic"` 传参逻辑。
- 前端包含 workflow、iteration、invalid citation、refusal category 渲染入口。
- `/agent/query` default 模式响应字段兼容。
- `/agent/query mode="agentic"` 返回 `mode="agentic"`、`iteration_count`、`invalid_citations`、`workflow_steps`。
- 既有 search/vector/hybrid/chat/agent/quality-report API 不破坏。

全量验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

验收目标：至少 `449 existing + new` 测试通过。

前端浏览器验证：

- 启动 FastAPI 本地服务。
- 打开 `http://127.0.0.1:8000`。
- 桌面和移动视口检查 Agent 面板。
- 验证控制台无明显错误。
- 验证 agentic 模式控件、步骤列表和文本布局不重叠。

## 安全边界

- 新字段只暴露脱敏步骤摘要、计数、引用编号和拒答分类。
- 不暴露 API key、Bearer token、provider 原始响应、受限全文。
- `workflow_steps` 只展示阶段 21 已生成的 `input_summary` / `output_summary`，不新增外部调用。
- 测试使用 deterministic provider 和本地临时 SQLite。
- Obsidian 只做本地知识库，不进入 Git。

## 完成标准

- 新增本设计文档。
- Agent 面板新增 default / agentic 模式切换。
- `submitAgent()` 根据模式向 `/agent/query` 传递 `mode`。
- agentic 返回结果中 `workflow_steps` 可视化展示，每步显示节点名、输入摘要、输出摘要。
- `iteration_count` 展示在 Agent 结果区域。
- `invalid_citations` 非空时标记无效引用。
- 拒答时展示 `responsibility_gate_triggered`、`evidence_insufficient` 或 `off_topic`。
- default 模式行为不变。
- 核心 API 不破坏：`POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report`。
- 补充前端/API 测试。
- 全量测试通过。
- README、docs/progress、docs/architecture、docs/data_sources、AGENT.MD、Obsidian 与 `docs/phase_reviews/phase-22.md` 同步。
- 开发完成后先停在用户人工核验前；用户明确确认后，提交、创建 `phase-22-complete` tag，并合并推送到 GitHub。

## 实现与验证状态

截至阶段 22 收尾：

- 后端响应契约已完成，default 模式新增字段使用兼容默认值。
- 前端 Agent 面板已支持 default / agentic 模式切换。
- agentic 模式下 `workflow_steps` 优先展示为步骤列表；default 模式继续展示旧 `tool_calls`。
- `iteration_count`、`invalid_citations` 和 `refusal_category` 已进入 Agent 结果区。
- 聚焦测试通过：`39 passed in 4.42s`。
- 全量测试通过：`451 passed in 44.61s`。
- 浏览器 desktop 与 390x844 mobile 检查通过，console error 为空。
- 用户已在 2026-06-11 明确要求提交阶段 22 整体开发工作，并上传 merge 至 GitHub。

## 面试表达

阶段 22 的重点不是再造一个前端框架，而是把 agentic RAG 的内部决策过程变成可解释的产品能力。默认 RAG 链路继续保持稳定，用户只有选择 agentic 模式时才进入 LangGraph 图。前端展示每轮检索、证据评估、改写、重检索、生成和引用检查，让系统从“黑盒回答”变成“可追踪回答”。这对工程型 RAG 很重要：用户需要知道答案为什么可信，拒答为什么发生，引用是否有效，而不仅是看到一段模型输出。
