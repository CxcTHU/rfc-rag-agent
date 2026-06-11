# 阶段 22 验收报告

- 验收人：Claude（独立验收方）
- 开发方：Codex
- 验收日期：2026-06-11
- 分支：`codex/phase-22-frontend-agentic-observability`
- 基线：`phase-21-complete -> 085bff4`

## 验收结论

**PASS**

阶段 22 的目标是把阶段 21 的 LangGraph agentic RAG 从"后端能跑"推到"前端能看懂"。这个目标已经达成，实现质量良好，边界把控干净。

---

## 一、阶段 22 解决了什么问题

阶段 21 实现了 LangGraph agentic RAG（retrieve → grade → rewrite → re_retrieve → generate → citation_check 六节点有向图），但前端只能看到最终答案和一组 `tool_calls`。用户无法知道：

- 系统走了几轮检索-改写循环
- 每个节点做了什么决策
- 拒答是因为"证据不足"还是"责任边界"还是"离题"
- 哪些引用编号其实没有对应到真实来源

阶段 22 把这些信息全部可读化。

## 二、实际做出的改进

### 2.1 后端响应契约升级

`AgentQueryResponse` 新增 5 个只读观测字段：

| 字段 | 作用 |
|---|---|
| `mode` | 标记本次响应走的是 default 还是 agentic 链路 |
| `workflow_steps` | agentic 每个节点的执行记录（名称、输入摘要、输出摘要、成功/失败） |
| `iteration_count` | 检索-评估-改写循环执行了几轮 |
| `invalid_citations` | 答案引用了但不在本次来源中的编号 |
| `refusal_category` | 拒答归类：责任边界 / 证据不足 / 离题 |

**做得好的地方：**

- Default 模式的新字段全部用零值/空值，旧客户端无需任何改动。这是正确的兼容策略。
- Agentic 模式同时保留旧 `tool_calls` 映射（从 workflow_steps 映射过来）和新 `workflow_steps`，渐进迁移思路清晰。
- `refusal_category_from_refusal()` 做成了纯函数，default 和 agentic 共用同一套判定逻辑，避免了两条链路各写一套分类的问题。
- `AgenticResult` 新增了 `responsibility_gate_triggered` 字段，从图状态中正确传递出来，不靠字符串猜测。

### 2.2 前端可观测展示

- Agent 面板新增了 default / agentic 下拉框，默认是 default，只有用户显式选 agentic 时才传 `mode="agentic"`。这是正确的 opt-in 设计——阶段 21 评测结论是 `inconclusive`，不应该把 agentic 设为默认。
- `renderAgentWorkflowSteps()` 把每个节点展示为带序号、节点名、状态 badge、输入/输出摘要的步骤卡片。agentic 响应优先用这个函数，default 响应 fallback 到旧的 `renderAgentToolCalls()`。
- `renderAgentAnswer()` 新增了 mode badge 和 iteration badge，用户一眼就知道走了哪条链路、循环了几次。
- 无效引用标记：如果 `invalid_citations` 命中了某个 citation badge，给它加红色 danger 样式和"无效"文字；如果无效引用编号不在 `citations` 里（孤立无效引用），单独展示。
- 拒答分类：`formatRefusalCategory()` 把英文枚举映射为中文（"责任边界"/"证据不足"/"离题"），同时显示原始枚举值便于调试。
- 所有动态 HTML 都经过 `escapeHtml()`，没有 XSS 风险。

**做得好的地方：**

- 没有引入任何前端框架、Node 构建链或复杂组件库，保持了原生 HTML/CSS/JS 的简洁性。对一个工程型 workbench 来说这是合理的。
- Mobile 视口下 agent-controls 网格正确折叠为单列，没有横向溢出。
- CSS 新增的类（`.workflow-step-item`、`.pill.danger`、`.pill.warning`、`.refusal-category`）是小范围新增，没有动旧样式。

### 2.3 Agentic 节点步骤记录

`nodes.py` 中每个节点（retrieve、grade、rewrite、re_retrieve、generate、citation_check）通过 `_append_step()` 累积 `workflow_steps`。步骤名与图节点名完全一致，前端不需要做名称翻译。

每个步骤的 `input_summary` 和 `output_summary` 是简洁的诊断信息（例如 `query=xxx results=5`、`evidence_sufficient=True score=0.85`），既够用又不暴露敏感内容。

### 2.4 测试

- 新增了 agentic observability 字段测试（`test_agent_api_agentic_mode_exposes_observability_fields`）和 responsibility gate 拒答分类测试（`test_agent_api_agentic_refusal_category_marks_responsibility_gate`）。
- 已有的 default 模式测试加入了新字段的兼容性断言（`mode=="default"`, `workflow_steps==[]` 等）。
- 前端静态测试覆盖了 mode 控件、JS 传参逻辑和新增渲染函数的存在性。
- 全量 451 passed，超过阶段 21 基线 449。

## 三、边界把控

以下"不做"的边界全部守住了：

- **没有把 agentic 切为默认模式**——这是正确的。阶段 21 的 agentic vs baseline 对照评测因 SSL 错误不可靠，目前没有数据支撑切换默认。
- **没有引入 Node/React/Vue**——继续原生 HTML/CSS/JS，符合项目当前阶段的维护成本。
- **没有新增写入型 Agent 工具**——新增字段全部是只读观测。
- **没有让真实 API 成为测试前提**——所有测试用 DeterministicChatModelProvider 和临时 SQLite。
- **提交边界已获用户确认进入发布流程**——阶段 22 开发完成时曾停在人工核验前；2026-06-11 用户已明确要求提交阶段 22 整体开发工作、创建 `phase-22-complete` tag，并合并推送到 GitHub。

## 四、不足与遗留

1. **`_append_step` 的 type: ignore**：`nodes.py:293` 有 `# type: ignore[arg-type]`，因为 `BrainWorkflowStepRecord.name` 字段类型比 `str` 更具体。不影响运行，但说明 workflow_steps 的类型体系在 Brain 和 Agentic 之间有轻微不一致。不阻断。

2. **前端测试是静态断言而非行为测试**：`test_frontend_app.py` 只检查 HTML/JS 字符串是否包含关键标识符（如 `data-agent-mode`、`renderAgentWorkflowSteps`），没有真正渲染 DOM 或模拟用户交互。这在没有前端构建链的项目中是合理折中，但意味着 JS 逻辑错误（如 `escapeHtml` 被跳过、条件判断写反）不会被测试捕获。用户应在人工核验时实际在浏览器中操作一遍。

3. **workflow_steps 的输入/输出摘要是开发者友好的而非用户友好的**：例如 `query=xxx results=5`、`evidence_sufficient=True score=0.85` 这样的格式，开发者或面试官能看懂，但普通用户可能需要更友好的中文描述。考虑到本项目当前定位是工程学习型 workbench 而非面向终端用户的产品，这不是问题。

4. **浏览器截图捕获超时**：浏览器 desktop/mobile 的 DOM、布局、交互和 console error 检查已完成并通过，但截图命令超时。这个问题不影响功能结论，后续如果需要更强的视觉回归，可以补专门的截图流程。

## 五、对阶段目标的总体评价

阶段 22 的定位是"可观测增强"，不是"功能升级"。它没有改变任何检索或生成逻辑，只是把阶段 21 已有的 agentic 内部状态变成前端可读的信息。这个定位精准，实现干净，没有越界。

从简历/面试角度看，阶段 22 补上了一个重要的产品能力：可解释性。用户不仅能得到答案，还能看到系统"为什么这样回答"——经过几轮检索、在哪一步拒答、哪些引用不可信。这对垂直领域 RAG 的可信度非常关键。

## 六、人工核验建议

用户在确认前建议：

1. 启动本地服务（`uvicorn app.main:app`），打开 Agent 面板，确认 default / agentic 下拉框可用。
2. 用 agentic 模式提交一个问题，在 DevTools Network 面板确认请求体有 `mode: "agentic"`。
3. 看看 workflow 步骤列表、iteration badge、引用 badge 和拒答分类展示是否符合预期。
4. 切回 default 模式，确认行为和阶段 21 一致。

用户已确认通过并要求提交；下一步执行 commit、创建 `phase-22-complete` tag、合并到 `main` 并推送 GitHub。
