# Phase 64 已验证事实

更新时间：2026-07-13

## 性能归因与效果

- 关系型图检索的本地 profile 从约 12.6 秒降至约 0.31 秒：有界双向遍历避免了
  全图复制，且只为入选候选构造 provenance。
- 已检查的 BM25 warm profile 从约 4.3 秒降至约 1.9 秒；评分和排序语义保持。
  进程就绪后的首个 B 请求 BM25 span 为 1107.175 ms。
- 官方智谱 rerank 的 5 次/12 candidates 交替小样本为 P50/P95
  237.599/378.450 ms；旧并行云为 302.569/2141.696 ms。结论仅限短样本服务
  稳定性，不能外推为 75 candidates 或质量门禁。
- 三对方向性 A/B 中，B Flash 首 token P50/P95 为 17.480/18.683 秒，A Pro 为
  38.974/39.831 秒；B 更快但未达到 15 秒 P95 目标。完整 30×3 与盲评未跑。

## 功能与安全

- 75 是 rerank candidate pool；最终来源仍由 Dynamic-K 决定（4–12），不是固定
  8 条，未以关闭 rerank 或语义缓存来压延迟。
- 默认实际 reranker 为官方 `zhipu/rerank`；旧并行云与历史 BGE 都不是运行时
  fallback。
- 同会话第二次流式请求能覆盖终态 run，修复了 UI 长期显示“已思考 <1 秒”。
- 图片资源回答会在正文下方展示最多 4 张去重的图片证据卡片；无正文引用的卡片
  明确标为仅检索。

## 可复跑证据

- 后端：`python -m pytest -q` → `1479 passed, 1 skipped`。
- 前端：`npm run test:unit` → `31 passed`；lint 与 build 通过。
- Stage 30：`python scripts/score_stage30_quality.py` → `91.52 / A / pass`。
- 指标与配置：`data/evaluation/phase64_*`；冻结评审：
  `docs/phase_reviews/phase-64.md`。
