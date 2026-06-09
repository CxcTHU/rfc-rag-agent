# 阶段 18 质量门槛报告

本报告由 `scripts/build_stage18_quality_report.py` 生成，只读汇总阶段 18 语料扩充、难评测集多配置对比和质量门槛，不触发真实 API 调用。

| Section | Metric | Status | Value | Risk | Recommendation |
|---|---|---|---|---|---|
| corpus | deep_fulltext_depth | expanded | 16 -> 340 (open_access_pdf=15, chunks=8918) | low | RFC 窄领域开放获取全文有限，未达 40-60 目标；按用户决策诚实报数，未造假。可后续接入授权全文继续扩充。 |
| hard_set | discrimination | discriminating | rank@1 differs across configs (vector p@1=0.60 vs hybrid p@1=0.87) | low | hit@8 在 deterministic 下仍饱和(15/15)，但 rank@1/precision@1 提供区分度；后续可加入更难的跨段合成题进一步拉开差距。 |
| default_chain | decision | keep_existing_hybrid | deterministic: hybrid p@1=0.87, bm25_rrf p@1=0.87 | low | bm25_rrf 在难评测集上未优于 hybrid（同 hit@8、同 rank@1、mean_rank 略差），数据支持 keep_existing_hybrid；BM25+RRF/context expansion 继续作为候选/配置开关。 |
| real_config | ranking_under_real_embedding | validated | real Jina vector p@1=1.00 (vs deterministic 0.60) | low | 真实 Jina 提升 vector 排序到 p@1=1.00，说明 deterministic 仅作稳定回归；真实配置只作发布前校准，不进 CI。 |
| refusal_boundary | off_topic_refusal | pass | 5/5 off-topic queries refused (brain_default, evidence confidence) | low | 真实风险：明显 off-topic 查询（LLM/烹饪/金融/量子/随机串）多数未被拒答，因其与语料共享通用词使 evidence confidence(0.20) 偶然通过；deterministic 与真实 Jina 下均如此，非 deterministic 伪影。阶段 18 显式阻断并记录，不静默修改默认拒答逻辑（影响全链路，需独立校准 Phase）。建议下一阶段：为 evidence confidence 增加主题相关度下限或 off-topic 守卫。 |
| stage17_residual | mesoscopic_modeling_rank_softdrop | closed_with_decision | keep_existing_hybrid | low | 阶段 17 的排序软退化(rank 2->7)担忧已在难评测集上对照：bm25_rrf 未优于 hybrid，默认链路维持，遗留以数据结论闭环。 |
| stage16_residual | user_mixed_itz_strength_answer_coverage | closed_low | low | low | 阶段 16 的 ITZ/强度 Answer Coverage 已闭环为 low：语料新增专门 ITZ 全文，等价 ITZ 问题真实 MIMO+Jina 跑通且带引用溯源；逐字措辞重跑遇真实 API 瞬时超时(非覆盖缺口)。 |
| overall | stage18_quality_gate | pass | low | low | 阶段 18 质量门槛通过，可由用户人工核验后决定提交。 |

## 数据安全边界

- 报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- 阶段 18 只读取本地脱敏 CSV 质量产物，不调用真实模型或检索 API。
- deterministic baseline 可复跑；真实 Jina 仅作发布前校准，不进 CI。
- 阶段 18 收尾等待用户人工核验，当前不提交、不打 tag、不推送。
