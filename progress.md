# 阶段 32 进度日志：ReAct Agent 决策升级 + 工具调用实时可视化

## 最终状态：阶段 32 开发、测试、文档和 Obsidian 草稿已完成

- 当前本地分支：`codex/phase-32-react-agent-tool-observability`。
- 当前停在用户人工核验前：未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR，未创建 `phase-32-complete` tag。
- 核心功能：`react_agent` 受控 ReAct loop、实时 `agent_step` / `tool_call_start` / `tool_call_result` SSE、前端中文状态 + 可折叠“查看思考过程”、deterministic 三路评测。
- 最终验证：阶段 32 聚焦测试 `106 passed`；全量 `python -m pytest -q` -> `629 passed, 1 warning`；阶段 30 评分 `overall=83.17`；桌面和移动端浏览器 smoke 均通过。

## 最终验收补充（2026-06-13）

- 前端 Agent 运行中展示从“逐条工具卡片”调整为简洁中文状态；答案完成后提供可折叠“查看思考过程”面板，按需展示 `workflow_steps` 和工具摘要。
- 已撤回 keyword fallback：Jina embedding / reranking 失败时不静默降级，`tool_call_result` 显示真实工具失败，ReAct 安全收敛为拒答。
- 浏览器验证：桌面与 390px 移动端均确认折叠面板存在、实时工具卡片不可见、无横向溢出、console errors=0。

## 当前状态

- 当前阶段：阶段 32 规划已准备，尚未开始代码实现。
- 当前本地分支：`codex/phase-32-react-agent-tool-observability`。
- 当前 Git 状态：已从 `main -> 93ee058` 创建并切换到 `codex/phase-32-react-agent-tool-observability`；本次仅改写根目录三份 planning 文件，尚未进入功能代码实现。
- 阶段 31 已完成开发、验证、提交、创建 `phase-31-complete` tag 并合并到 `main`。
- 阶段 32 建议分支：`codex/phase-32-react-agent-tool-observability`。
- 提交边界：阶段 32 正式开发完成后必须停在用户人工核验前；不要提交、不要创建 `phase-32-complete` tag、不要 push、不要创建 PR，直到用户明确确认。

## 阶段 31 验收基线

```text
main / origin/main -> 93ee058 Merge phase 31 faiss parent child retrieval
phase-31-complete -> b03bb47 Complete phase 31 faiss parent child retrieval
git merge-base --is-ancestor phase-31-complete main -> passed
```
阶段 31 关键结果：

```text
FAISS full index: vectors=12716
parent backfill: parent_rows=6402, linked_children=12716, parent_embeddings=0
stage30 quality score: overall=83.17, grade=B, release_decision=review_required
full tests: 593 passed, 1 warning
real provider API smoke: /health、/quality-report、/search、/search/vector、/search/hybrid、/chat、/agent/query 均 200
```

系统规模：

```text
documents: 635
chunks: 19,118 (12,716 child + 6,402 parent)
chunk_embeddings: 25,432 (child only, Jina v3 1024d + deterministic 64d)
```

## 阶段 32 规划完成记录

已完成根目录三份 Planning with Files 文件改写：

- `task_plan.md`：阶段 32 Phase 0-8 任务计划，覆盖启动校准、设计文档、ReAct action schema、ReAct service、SSE 步骤事件、前端实时展示、评测回归、文档与 Obsidian 收尾。
- `findings.md`：记录当前 fixed graph、default Agent、SSE 流式协议、工具边界、ReAct 设计决策、风险防线和面试表达。
- `progress.md`：记录阶段 32 启动状态、阶段 31 Git/tag/main 基线、后续执行边界和 Phase 日志框架。

## 阶段 32 目标概述

阶段 32 要完成三个核心任务：

1. **ReAct Agent 决策升级**：把当前由 `grade_router` 硬编码控制的 agentic 路径升级为 LLM action loop，让模型在受控工具集合内选择检索、改写、回答或拒答。
2. **工具调用过程可观测**：所有 action 和 observation 记录为结构化 `workflow_steps` / `tool_calls`，保留引用、来源、拒答和迭代次数。
3. **前端实时步骤显示**：扩展 `/agent/query/stream`，在答案 token 前实时推送 `agent_step`、`tool_call_start`、`tool_call_result`，让用户看到 Agent 当前正在哪一步。

## 关键执行边界

- 不展示模型原始 hidden thought，只展示安全摘要。
- 不新增写入型工具，所有工具继续只读。
- 不新增爬虫、不新增外部资料来源、不保存受限全文。
- 不改变 `/chat` 默认链路。
- 不删除 default Agent，不破坏旧 agentic 作为对照或回退。
- 真实 provider 可以支持 tool calling，但自动测试必须走 deterministic。
- ReAct 循环必须有最大迭代和最大工具调用限制。
- SSE 新事件必须兼容既有 `token` / `metadata` / `done` / `error`。
- 阶段 30 评分 overall_score 必须保持 `>= 83.17`。
- 不把 API key、Bearer token、供应商原始响应写入 Git、CSV、文档、测试或 Obsidian。
- 未经用户人工核验，不 git add / commit / tag / push / 建 PR。

## Phase 日志

### Phase 0：启动校准与规划落盘

状态：已完成。

本 Phase 解决的问题：确认阶段 32 的正确起点，并建立本阶段的任务书、发现记录和进度日志。

RAG 链路位置：版本基线和协作边界，不改运行链路。

为什么现在做：ReAct 会改 Agent 编排和前端流式协议，必须先确认阶段 31 已完整合并并固定回归基线。

已完成：

- 已读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 已读取根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 已读取 `obsidian-vault/模板/goal prompt.md` 和 `obsidian-vault/模板/开启 prompt.md`。
- 已运行 `git status -sb`、`git log --oneline -5`。
- 已确认 `phase-31-complete` 存在并且是 `main` 的祖先。
- 已将三份 planning 文件改写为阶段 32 规划。
- 已从 `main` 创建并切换到 `codex/phase-32-react-agent-tool-observability`。

未执行：

- 未开始代码实现。
- 未执行 `git add`、commit、tag、push 或 PR。

### Phase 1：阶段 32 设计文档

状态：已完成。

计划产物：

```text
docs/stage32_react_agent_observability.md
tests/test_stage32_design.py
```

完成记录：

- 已新增 `docs/stage32_react_agent_observability.md`，覆盖 ReAct action、工具权限、SSE 事件、安全边界、循环控制、评测方式和完成标准。
- 已新增 `tests/test_stage32_design.py`。
- 聚焦测试：`python -m pytest tests\test_stage32_design.py -q` -> `2 passed`。

### Phase 2：ReAct 工具调用契约与模型 action schema

状态：已完成。

计划产物：

```text
app/services/agent/react_actions.py
tests/test_react_actions.py
```

完成记录：

- 已新增 `app/services/agent/react_actions.py`，包含受控 action schema、observation、step record、run result、JSON action parser、重复 query 防护和 deterministic planner。
- 已新增 `tests/test_react_actions.py`。
- 聚焦测试：`python -m pytest tests\test_react_actions.py tests\test_agent_tools.py -q` -> `12 passed`。

### Phase 3：ReAct Agent Service 实现

状态：已完成。

计划产物：

```text
app/services/agent/react_service.py
tests/test_react_agent_service.py
```

完成记录：

- 已新增 `app/services/agent/react_service.py`，实现受控 ReAct loop。
- 已扩展 `AgentQueryRequest.mode` 支持 `react_agent`。
- 已接入 `/agent/query` 和流式共用的 response 构建路径，旧 `default` / `agentic` 保持可用。
- 已新增 `tests/test_react_agent_service.py`，并补充 `tests/test_agent_api.py` 的 `react_agent` 显式 mode 测试。
- 聚焦测试：`python -m pytest tests\test_react_agent_service.py tests\test_agent_api.py -q` -> `24 passed`。

### Phase 4：SSE 实时步骤事件协议

状态：已完成。

计划产物：

```text
app/api/agent.py
tests/test_react_stream_events.py
```

完成记录：

- 已扩展 `/agent/query/stream` 队列事件，实时转发 ReAct runtime events。
- 新增 SSE 事件：`agent_step`、`tool_call_start`、`tool_call_result`。
- 旧事件 `token`、`metadata`、`done`、`error` 保持兼容。
- 已新增 `tests/test_react_stream_events.py`。
- 聚焦测试：`python -m pytest tests\test_agent_stream_api.py tests\test_react_stream_events.py -q` -> `8 passed`。

### Phase 5：前端实时步骤可视化

状态：已完成。

计划产物：

```text
app/frontend/static/app.js
app/frontend/static/styles.css
tests/test_frontend_app.py
```

完成记录：
- 已在 pending Agent 消息中新增 live step timeline 容器。
- 已消费 `agent_step`、`tool_call_start`、`tool_call_result`，运行时实时追加安全步骤摘要。
- 已保留最终 `metadata` 校准 `workflow_steps` / `tool_calls` 的旧展示链路。
- 已新增紧凑 live step 样式和长文本溢出防护。
- 聚焦测试：`python -m pytest tests\test_frontend_app.py -q` -> `10 passed`。

### Phase 6：ReAct 评测与回归对照

状态：已完成。

计划产物：

```text
scripts/evaluate_stage32_react_agent.py
data/evaluation/stage32_react_agent_results.csv
data/evaluation/stage32_react_agent_summary.csv
tests/test_stage32_react_eval.py
```

完成记录：
- 已新增 deterministic 三路对照脚本，不依赖真实 provider，并显式关闭 reranking。
- 已生成 `data/evaluation/stage32_react_agent_results.csv` 和 `data/evaluation/stage32_react_agent_summary.csv`。
- 已记录 `default`、`agentic_langgraph`、`react_agent` 的错误率、拒答匹配、工具调用、迭代次数、来源和引用有效性。
- 聚焦测试：`python -m pytest tests\test_stage32_react_eval.py -q` -> `4 passed`。
- 正式脚本：`python scripts\evaluate_stage32_react_agent.py` -> 三模式 `errors=0`，decision 均为 `pass`。

### Phase 7：全量验证、浏览器冒烟与真实 provider smoke

状态：已完成。

验证目标：

```text
阶段 32 聚焦测试通过
python -m pytest -q 通过
python scripts\score_stage30_quality.py -> overall >= 83.17
Browser / 显示实时步骤、工具调用、最终答案，console errors=0
核心 API smoke 均 200
```

完成记录：
- 阶段 32 聚焦测试：`106 passed`。
- 全量测试：`python -m pytest -q` -> `629 passed, 1 warning`。
- 阶段 30 评分：`overall=83.17 grade=B release_decision=review_required`。
- API smoke：`/health 200`、`/quality-report 200`、`/chat 200`、`/agent/query 200`、`/agent/query/stream 200`、`/search/hybrid 200`。
- 浏览器桌面 smoke：折叠“查看思考过程”存在、实时工具卡片不可见、最终答案存在、横向溢出=false、console errors=0。
- 浏览器移动端 390x844 smoke：折叠“查看思考过程”存在、实时工具卡片不可见、最终答案存在、横向溢出=false、console errors=0。
- 自动验证使用 deterministic 服务实例，未把真实 provider 作为前提。

### Phase 8：文档、Obsidian 与人工核验收尾

状态：已完成。

计划产物：

```text
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
AGENT.MD（按需）
docs/phase_reviews/phase-32.md
obsidian-vault/阶段/阶段 32 - ReAct Agent 决策升级与工具调用可视化.md
obsidian-vault/阶段汇报/阶段 32 - ReAct Agent 决策升级与工具调用可视化/
```

完成记录：
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 已新增 `docs/phase_reviews/phase-32.md`。
- 已新增 Obsidian 阶段页、阶段汇报索引、阶段汇总和 `ReAct Agent 可观测性` 知识点。
- 已更新 Obsidian 阶段索引、阶段汇报索引和 Agent 工具调用分类页。
- 当前仍停在人工核验前，未执行提交、tag、push 或 PR。

## 联调修复：网络封锁诊断、网络韧性与 Provider 迁移

状态：已完成（仍未提交，停在人工核验前）。

阶段 32 功能开发完后，用户联调 `react_agent` 发现 `search_knowledge` 稳定失败、报 `[SSL: UNEXPECTED_EOF_WHILE_READING]`。排查与修复：

- 根因：`api.jina.ai`（旧 embedding + reranking 端点）在该网络被 SNI 级 TLS 阻断。Python urllib + curl、直连 + 本地代理四种组合全部握手重置，而 google/baidu/MIMO `.cn` 均可达。属持续性网络故障，非代码问题。
- 网络韧性（治本）：三个对外 HTTP 出口（embedding/chat/reranker provider）新增有限次重试（`max_attempts=3` + 退避，URLError/SSL、超时、429/5xx 重试，4xx 不重试）；chat 流式仅在首 token 前重试连接；hybrid search 的 rerank 改为 fail-open；拒答新增 `service_error` 分类，前端补“检索服务异常”标签。
- Provider 迁移：Jina -> 清华 Paratera。embedding=`GLM-Embedding-3`（2048 维，`https://llmapi.paratera.com/v1`）；reranking=`GLM-Rerank`（真实交叉编码器，端点 `/v1/p002/rerank`）。`create_embedding_provider` / `create_reranking_provider` 新增 `paratera`/`zhipu`/`siliconflow` 别名；均 OpenAI/Jina 兼容，provider 代码零改动。
- 数据迁移：重 embed 12,731 个叶子块（旧 Jina 向量留库），重建 FAISS `data/faiss/paratera_GLM-Embedding-3_dim2048.index`。
- 验证：ReAct 端到端用真实 Paratera embedding + GLM-Rerank + MIMO chat 跑通，`refused=False`，两个工具均成功，返回带 `[1][2][3][4]` 引用的真实答案，SSL 错误消失；`python -m pytest -q` -> `629 passed`；阶段 30 评分 `overall=83.17`（管线不退步，注：评分基于阶段 29 旧 Jina 缓存，未反映新 embedding 检索质量）。
- 安全：API key 仅写入已 gitignore 的 `.env`；FAISS 派生文件在 gitignore 的 `data/faiss/`；未进 git、文档、CSV、测试。

详见 `docs/phase_reviews/phase-32.md` 的「联调修复」一节。

## 当前遗留风险与人工核验重点

- 前端 Agent 面板现在默认提交 `mode: "react_agent"`；人工核验时应确认这个产品默认策略符合阶段 32 预期。API 仍保留显式 `mode="default"` 和 `mode="agentic"` 作为对照/回退。
- ReAct 真实 provider 路径依赖模型按结构化 JSON action 返回；自动测试和默认评测已经使用 deterministic planner，真实 provider 只建议人工显式 smoke。
- 前端和 SSE 只展示安全摘要；人工核验时继续抽查 CSV、文档、测试和 Obsidian，确认没有 hidden thought、provider raw response、API key、Bearer token、Authorization header、`raw_response` 或受限全文。
- 阶段 32 尚未提交、未 tag、未 push；用户确认前不要进入 Git 提交流程。

## 面试表达草稿

阶段 32 可以这样讲：

```text
阶段 32 我把原来固定状态图式的 Agent 升级成 ReAct Agent。旧版本中 retrieve、grade、rewrite、generate 的顺序由代码里的 grade_router 决定；新版本让模型在受控 action schema 中自主选择检索、改写、回答或拒答。工具执行仍通过 AgentToolbox 和 Brain 链路，所以不会绕过引用、来源追踪和拒答机制。

同时我扩展了 SSE 流式协议。以前前端只能显示“正在思考”，最后 metadata 到了才看到 workflow steps；现在后端会实时推送 agent_step、tool_call_start、tool_call_result，用户能看到 Agent 当前准备调用哪个工具、用什么 query、返回了多少结果。这样既体现 Agent 自主决策能力，也提升了可观测性和可审计性。
```
