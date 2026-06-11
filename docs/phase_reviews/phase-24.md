# 阶段 24 验收报告

- 验收人：用户人工核验 + Codex 提交前复核
- 开发方：Codex
- 验收日期：2026-06-11
- 分支：`codex/phase-24-multi-turn-conversation`
- 基线：`main -> 8fc1cfa Merge phase 23 agentic eval and auto routing`

## 验收结论

**PASS**

阶段 24 的目标是把 Agent 从单次问答升级为可持久化的多轮会话入口：新增 Conversation/Message 模型、会话 CRUD API、`/agent/query` 的 `conversation_id` 集成、长对话摘要压缩、前端聊天气泡和会话管理，并在人工反馈后收敛首页主入口到 Agent。用户已完成手工体验核验并明确要求提交、打阶段 tag、合并并推送到 GitHub。

## 核对范围

- 后端新增 `Conversation`、`Message`、`ConversationRepository`，支持会话分组、消息持久化、默认标题、更新时间和级联删除。
- 新增 `/conversations` CRUD API：创建会话、列出会话、读取消息、删除会话。
- `/agent/query` 新增可选 `conversation_id`：不传保持阶段 23 行为，传入时加载历史、持久化 user/assistant 消息，并触发摘要压缩。
- agentic 路径新增 `history` 参数，只在 generate 节点利用会话历史，不改变 retrieve/grade/rewrite 的当前问题驱动边界。
- 长对话超过阈值后生成 `role="summary"` 消息，保留近期原文消息，summary 仅用于 prompt 压缩，不替代来源引用。
- 前端 Agent 面板改为聊天气泡流，支持会话列表、新建、切换、删除、刷新恢复，保留 mode、workflow、citations、refusal_category 展示。
- 人工反馈修复：增加“正在思考”提示、错误气泡、provider 失败兜底、寒暄 greeting 引导、隐藏普通首页的“问答”和“检索”调试入口。
- 保留后端 `/chat`、`/search`、`/search/vector`、`/search/hybrid` 和 `/quality-report` 兼容性。
- 未引入 WebSocket/SSE、登录系统、跨会话长期记忆、LangGraph Checkpointer、React/Vue/Node 构建链或新外部资料来源。

## 验证结果

```text
.\.venv\Scripts\python.exe -m pytest -q
483 passed in 46.23s
```

阶段开发过程中的聚焦验证还覆盖了会话 API、摘要压缩、Agent API、agentic history、前端静态结构、搜索/问答/Agent 组合回归以及浏览器 DOM/CSS 检查。最终浏览器检查确认普通首页只展示 Agent 主入口，`operations-grid` 与 `answer-grid` 均隐藏，Agent 区域可见且无横向溢出。

## 安全与合规

- 未写入 API key、Bearer token、Authorization header、供应商原始敏感响应或受限全文。
- `Message.metadata_json` 仅保存前端恢复展示所需的结构化元数据。
- 真正模型 provider 不作为 CI 或本地全量测试前提。
- 会话 API 当前无登录和用户隔离，这是阶段 24 明确边界；后续若引入认证，需要补 owner/user 维度、列表过滤、删除权限和安全测试。

## 遗留观察

- 首页调试入口已隐藏但对应 JS 和后端 API 保留，便于后续开发调试和回归。
- 摘要压缩是短期 conversation 上下文管理，不是跨会话长期记忆。
- Agent 主入口已满足普通用户体验，但后续可继续优化加载态、会话标题生成和更细粒度的路由解释。

