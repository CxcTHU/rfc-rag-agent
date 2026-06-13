# Phase 32 Review: ReAct Agent 决策升级与工具调用可视化

## 状态

阶段 32 开发、测试、文档和 Obsidian 草稿已完成，当前停在用户人工核验前状态。尚未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR，未创建 `phase-32-complete` tag。

分支：`codex/phase-32-react-agent-tool-observability`

基线：

```text
main -> 93ee058 Merge phase 31 faiss parent child retrieval
phase-31-complete -> b03bb47 Complete phase 31 faiss parent child retrieval
```

## 范围

- 新增受控 ReAct action schema：`search_knowledge`、`rewrite_query`、`answer_with_citations`、`refuse`、`final_answer`。
- 新增 `ReActAgentService`，让 `react_agent` 在最多 3 轮内选择检索、改写、回答或拒答。
- 保留 default `AgentService`、旧 `agentic` LangGraph 路径和 `/chat` 默认链路。
- 扩展 `/agent/query/stream`：新增 `agent_step`、`tool_call_start`、`tool_call_result`，保留旧 `token`、`metadata`、`done`、`error`。
- 前端 Agent 面板默认走 `react_agent`，运行中显示简洁中文状态，最终由 metadata 的 `workflow_steps` 校准可折叠“查看思考过程”面板。
- 新增 deterministic 三路评测脚本和结果 CSV。

## 验证

```text
python scripts\evaluate_stage32_react_agent.py
default / agentic_langgraph / react_agent: errors=0, decision=pass

python -m pytest tests\test_stage32_design.py tests\test_react_actions.py tests\test_react_agent_service.py tests\test_react_stream_events.py tests\test_stage32_react_eval.py tests\test_agent_api.py tests\test_agent_stream_api.py tests\test_frontend_app.py -q
106 passed

python -m pytest -q
629 passed, 1 warning

python scripts\score_stage30_quality.py
stage30 quality score overall=83.17 grade=B release_decision=review_required
```

Browser smoke 使用显式 deterministic 服务实例：

```text
desktop: collapsible thought panel present, live tool cards hidden, final answer present, horizontal overflow=false, console errors=0
mobile 390x844: collapsible thought panel present, live tool cards hidden, final answer present, horizontal overflow=false, console errors=0
```

API smoke：

```text
/health 200
/quality-report 200
/chat 200
/agent/query 200
/agent/query/stream 200, includes agent_step and tool_call_result
/search/hybrid 200
```

## 人工核验重点

1. 打开 Agent 面板，确认运行中只显示简洁中文状态，不再铺满 function call 卡片。
2. 答案结束后展开“查看思考过程”，确认其中由 `workflow_steps` 回填，能看到 `search_knowledge` 和 `answer_with_citations` 等步骤。
3. 确认 `/chat` 仍保持默认 RAG 链路，不被 ReAct 默认策略影响。
4. 用 API 显式调用 `mode="default"`、`mode="agentic"`、`mode="react_agent"`，确认三路仍可对照。
5. 抽查 `data/evaluation/stage32_react_agent_results.csv` 和前端展示，确认没有敏感凭据、授权头、供应商原始响应或受限全文。
6. 复核产品默认策略：前端 Agent 面板现在默认提交 `mode: "react_agent"`，而不是让自动复杂度路由决定 default/agentic。

## 联调修复：网络封锁诊断、网络韧性与 Provider 迁移

阶段 32 功能开发完成后，用户联调 `react_agent` 时发现 ReAct 第一步 `search_knowledge` 稳定失败，前端报 `Embedding model request failed: [SSL: UNEXPECTED_EOF_WHILE_READING]`，随后整条 query 被拒答。排查结论与修复如下。

### 根因：api.jina.ai 被 TLS 定向封锁

- 故障链：`search_knowledge` -> `HybridSearchService` -> Jina embedding HTTP 请求 -> SSL 握手被中途重置 -> `RuntimeError` -> 工具失败 -> ReAct 立即拒答，且被误分类为 `evidence_insufficient`。
- 连通性实测（Python urllib + curl 两套 TLS 栈、直连 + 本地代理四种组合）：

```text
google.com / baidu.com / MIMO .cn      -> 可达
api.jina.ai (embedding + reranking)    -> 四种组合全部 TLS 握手重置
```

- 判定：`api.jina.ai` 在该网络环境被 SNI 级 TLS 阻断，属持续性故障，非代码问题，本地重试无法治愈。

### 网络韧性加固（治本，防止同类问题复发）

项目仅有的三个对外 HTTP 出口现在都有重试与降级：

- `OpenAICompatibleEmbeddingProvider`、`OpenAICompatibleChatModelProvider`、`OpenAICompatibleReRankingProvider` 新增有限次重试（`max_attempts=3`，指数退避）：对 `URLError`/SSL、`TimeoutError`、HTTP 429/5xx 重试；4xx 客户端错误不重试。
- chat 流式只在首个 token 前重试连接，已开始流式后不重试，避免重复 token。
- `HybridSearchService` 的 rerank 改为 fail-open：rerank 异常时降级回融合排序，不再让整条 query 崩溃。
- `refusal_category_from_refusal` 新增 `service_error` 分类，工具/网络错误不再误标 `evidence_insufficient`；前端补“检索服务异常”标签。

### Provider 迁移：Jina -> 清华 Paratera

- embedding：`GLM-Embedding-3`（2048 维），`https://llmapi.paratera.com/v1`。
- reranking：`GLM-Rerank`，真实交叉编码器，端点在 `/v1/p002/rerank`（base_url 配 `https://llmapi.paratera.com/v1/p002`，provider 自动追加 `/rerank`）。
- `create_embedding_provider` / `create_reranking_provider` 新增 `paratera`（及 `zhipu`、`siliconflow`）别名；均为 OpenAI/Jina 兼容格式，provider 代码零改动。
- 数据迁移：对 12,731 个叶子块重新生成 embedding（旧 Jina 1024 维向量留库不动，新增 `provider=paratera` 2048 维一组），重建 FAISS 索引 `data/faiss/paratera_GLM-Embedding-3_dim2048.index`。
- 安全：API key 仅写入已 gitignore 的 `.env` 与 FAISS 派生文件（`data/faiss/` 亦 gitignore），未进入 git、文档、CSV 或测试。

### 联调修复验证

```text
ReAct 端到端（真实 Paratera embedding + GLM-Rerank + MIMO chat）：
refused=False; tool_calls=[hybrid_search_knowledge ✓, answer_with_citations ✓]
sources=9; citations=[1,2,4,3]; 返回真实带引用答案，SSL 错误消失

python -m pytest -q -> 629 passed
python scripts\score_stage30_quality.py -> overall=83.17 grade=B（评分管线不退步）
```

注：阶段 30 评分读取阶段 29 的缓存 CSV（基于旧 Jina 检索），`83.17` 仅说明评分管线完好，尚未反映 Paratera 新 embedding 的真实检索质量；如需量化 GLM-Embedding-3 vs Jina，需另行用真实 API 重跑阶段 29 评测。

## 提交建议

人工核验通过后再提交，并建议创建 `phase-32-complete` tag 指向阶段 32 最终功能提交。提交前再次确认工作区无意外敏感信息（尤其 `.env` 不得入库），并重跑至少阶段 32 聚焦测试。
