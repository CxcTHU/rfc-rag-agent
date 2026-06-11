# 阶段 25 验收报告

- 验收人：用户人工核验 + Codex 提交前复核
- 开发方：Claude + Codex 双 Agent 协作
- 验收日期：2026-06-11
- 分支：`codex/phase-25-chitchat-and-sse-streaming`
- 基线：`main -> c4eda98 Merge phase 24 multi-turn conversation`

## 验收结论

**PASS**

阶段 25 的目标是把 Agent 主入口补齐两类交互体验：闲聊类问题在路由层短路返回，避免无意义检索和模型调用；正式问答通过 SSE 逐 token 输出，让用户在长链路 RAG 生成阶段看到持续反馈。用户已完成真实浏览器体验核验，并确认 Claude 修复后已经是真正流式输出。本报告用于阶段 25 最终功能提交、`phase-25-complete` tag 和合并到 `main` 前的正式记录。

## 核对范围

- 新增 `app/services/agent/chitchat.py`，在 `/agent/query` 和 `/agent/query/stream` 路由层、`classify_query_complexity()` 之前统一识别 `greeting`、`thanks`、`goodbye`、`acknowledgment`、`help` 五类社交意图。
- 命中闲聊短路时直接返回预设友好回复，不调用 LLM、检索、重写或评分链路；带 `conversation_id` 时仍持久化 user/assistant 消息，并跳过摘要触发。
- 从 `AgentService.detect_intent()` 移除已提升到 API 层的 greeting 分支，保留 RFC/source lookup 等业务意图检测。
- `ChatModelProvider` 新增 `stream_generate(messages)` 协议，OpenAI-compatible provider 使用 `stream=true` 解析 SSE delta，deterministic provider 按 chunk yield，便于本地和 CI 测试。
- 新增 `POST /agent/query/stream`，使用 `StreamingResponse(media_type="text/event-stream")` 输出 `token`、`metadata`、`done`、`error` 四类事件。
- Agentic 路径保持 retrieve/grade/rewrite 同步执行，仅 generate 节点切换为流式输出；流完成后再持久化 assistant 消息并触发会话摘要。
- 前端 `submitAgent()` 改为 `fetch` + `ReadableStream` 消费 SSE，逐 token 追加到同一助手气泡；`metadata` 事件回填 citations、mode、workflow、refusal 信息。
- 修复用户反馈的“看起来不是流式”问题：deterministic provider 增加 token 间隔，前端 metadata 不再整体重建气泡 DOM，并使用双层 `requestAnimationFrame` 保证逐 token paint。
- 保留 `POST /agent/query` 同步 JSON 契约，未破坏 `/search`、`/search/vector`、`/search/hybrid`、`/chat`、`GET /quality-report`。
- 新增 `docs/stage25_chitchat_and_sse_streaming.md`，同步 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`、`task_plan.md`、`findings.md`、`progress.md` 和本地 Obsidian 草稿。
- 明确未引入 WebSocket、登录认证、前端框架/Node 构建链、写入型 Agent 工具、跨会话长期记忆，也未让真实 API 成为本地全量测试或 CI 前提。

## 验证结果

```text
.\.venv\Scripts\python.exe -m pytest -q
497 passed in 66.18s
```

阶段开发过程中的聚焦验证还覆盖：

- `tests/test_agent_chitchat.py tests/test_agent_api.py tests/test_agent_service.py -q`：闲聊短路、同步 Agent API 和业务意图回归。
- `tests/test_agent_stream_api.py tests/test_chat_model_provider.py tests/test_agent_api.py -q`：SSE 事件契约、流式 provider、同步 API 兼容性。
- `tests/test_frontend_app.py -q`：前端静态结构、SSE 消费入口和 Agent 面板回归。
- 阶段 25 组合测试：53 项通过。
- 浏览器桌面/移动核验：`thanks` 闲聊回复在助手气泡中分段增长，最终 `data-agent-status="answered"`，console error 为 0；普通 source_id 问答可返回 token、metadata、done 事件。

## 安全与合规

- 未写入 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文。
- 测试全部使用 deterministic provider、mock provider 或本地合成数据，真实模型 API 不作为测试前提。
- SSE metadata 仅携带前端展示所需的结构化结果，不额外暴露供应商响应细节。
- 本阶段没有新增外部数据源，也没有修改 RFC XML 导入、chunk、embedding、ranking 或质量报告的数据语义。
- Obsidian 汇报保留在本地 gitignored 目录，不随 Git 提交。

## 遗留观察

- 大库真实检索问答仍可能超过 20 秒；阶段 25 已让生成阶段可见，但 retrieve/grade/rewrite 仍是同步前置步骤。
- 会话能力仍无登录和用户隔离，延续阶段 24 的明确边界。
- SSE 是单向输出通道；取消生成、双向工具调用或实时协作需要后续阶段另行设计。
- 前端仍使用原生 HTML/CSS/JS，无框架构建链；这符合阶段边界，但后续复杂交互增加时可能需要重新评估。
