# Phase 64 官方智谱 Rerank 迁移设计

**状态：用户已批准（2026-07-13）**

## 目标

将本机 Phase 64 的真实 rerank 服务从并行智算云切换到智谱官方文本重排序 API，
并让冻结 A/B 契约明确验证 `zhipu / rerank` 身份。迁移不得关闭 rerank、放宽
pgvector、开启语义缓存，或使任意第三方 reranker 被误接受。

## 运行时配置

- 仅在被 `.gitignore` 排除的本机 `.env` 保存 API key。
- `RERANKING_PROVIDER=zhipu`、`RERANKING_MODEL_NAME=rerank`、
  `RERANKING_BASE_URL=https://open.bigmodel.cn/api/paas/v4`。
- 官方 rerank API 不使用本项目通用 `/health` 预检，因此本机设置
  `RERANKING_HEALTH_CHECK_ENABLED=false`；真实 `/rerank` 调用仍受原有超时、
  重试和 fail-soft 策略控制。
- 禁用原并行智算云 fallback，避免一次评测混入两个供应商。

## Phase 64 冻结合同

- A 与 B 均必须报告 `reranking_provider=zhipu` 和 `reranking_model_name=rerank`。
- 评测器继续要求两端语料指纹相同、严格 pgvector、四类冷缓存关闭，并分别验证
  Phase 63 A 与 Phase 64 B 的执行图开关。
- `zhipu / rerank` 不匹配、缺失或调用失败的行不可计入功能、延迟或盲评通过结果。

## 验证与限制

1. 单元测试覆盖冻结契约只接受 `zhipu / rerank` 并拒绝旧 `paratera / GLM-Rerank`。
2. 运行时安全 probe 仅输出成功布尔值、provider/model、HTTP 状态类别和耗时，
   不输出密钥、请求/响应正文、候选文本或原始载荷。
3. 最新固定输入小样本中，官方服务 5/5 成功，P50/P95 为 237.599/378.450 ms；
   旧云为 302.569/2141.696 ms。该证据仅说明本次小样本的服务波动，不构成质量或
   Phase 64 端到端门禁结论。

## 非目标

- 不改变 75 条候选池、最终 `top_k`、Flash/Pro 前端选择或最终生成模型。
- 不恢复 BGE，也不在 API 限流时静默关闭 rerank 或伪造通过结果。
