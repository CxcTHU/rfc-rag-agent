# Phase 64 Flash 用户显式选择延迟设计

**状态：已批准（2026-07-13）**

## 目标

在不改变前端用户模型选择权、检索语义、GLM-Rerank 或 Phase 63 冻结 A
链路的前提下，建立可复跑的 `deepseek-v4-pro`（A）与
`deepseek-v4-flash`（B）端到端延迟对照。Flash 只由评测请求显式选择，
不是对生产用户或默认模型的静默替换。

## 已有边界

- 前端已向 `/agent/query` 与 `/agent/query/stream` 发送受 schema 限制的
  `chat_model`；可选值为 Flash 和 Pro。
- 后端在请求边界用相同 provider、base URL、凭据、温度和超时创建选定模型的
  provider，且 SSE `metadata` 安全回传 `chat_provider` 与 `chat_model`。
- Phase 64 B 保持 route-first、short-loop、complex-only fan-out、非思考最终生成、
  BM25/pgvector、真实 `paratera / GLM-Rerank` 与语义缓存关闭。不得使用或恢复 BGE。
- A 保持 Phase 63 冻结行为和 `deepseek-v4-pro`；B 的 Flash 改动只用于本评测
  lane，未通过质量和延迟门禁前不改变默认配置。

## 对照合同

| 项目 | A（基线） | B（候选） |
| --- | --- | --- |
| 请求 `chat_model` | `deepseek-v4-pro` | `deepseek-v4-flash` |
| 执行图 | Phase 63 冻结 | Phase 64 short-loop / route-first |
| 检索与证据 | 相同语料、严格 pgvector、冷 cache | 相同语料、严格 pgvector、冷 cache |
| Reranker | `paratera / GLM-Rerank` | `paratera / GLM-Rerank` |
| 成功条件 | 功能、引文、盲评、延迟均过门禁 | 功能、引文、盲评、延迟均过门禁 |

评测器必须把模型名随每个 SSE 请求发送，并从最终 `metadata.chat_model`
读取实际观察值。观察值缺失或与请求不一致时，该行标为
`selected_chat_model_mismatch`，不可计入成功、P50/P95 或质量门禁。
结果只保存安全指标、路由、模型标识和计时；不得写入回答正文、完整证据、供应商
原始载荷、隐藏推理或任何凭据。

## 非目标

- 不新增前端模式，不修改用户已选择的模式，也不把 Flash 设为默认。
- 不改变 planner 的独立配置，亦不以伪造进度 token 代替真实首回答 token。
- 不因 Flash 测试关闭 GLM-Rerank、降低 pgvector 要求或开启最终答案语义缓存。

## 验收

1. 单个 Phase 63 E2E case 可显式传递模型并从 SSE 元数据记录安全的请求/观察模型。
2. Phase 64 配对评测固定 A=Pro、B=Flash，任何模型不匹配均失败。
3. Flash 仍经过全量功能、引文和盲评门禁；只有在这些门禁不回退且延迟门禁通过时，
   才能作为用户可选低延迟 lane 的候选结论。
