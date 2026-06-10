# 阶段 20 质量门槛报告

本报告由 `scripts/build_stage20_quality_report.py` 生成，只读汇总阶段 20 评测判定升级、真实 Jina query 校验、默认链路决策和责任边界拒答，不触发真实 API 调用。

| Section | Metric | Status | Value | Risk | Recommendation |
|---|---|---|---|---|---|
| eval_judge_upgrade | coverage_ratio | completed | baseline p@1=0.133, best_deep=hybrid_topic_anchor_strict deep_top1=0.733 | low | 已用 expected_answer_points 的 coverage_ratio 替代题录关键词命中主判定；结果显示 deep top-1 上浮但答案覆盖 p@1 未提升。 |
| real_jina_query_validation | query_only | completed | completed, baseline p@1=0.133 | low | 真实 Jina 只在 query 端校验，复用已有 chunk embeddings；本轮无真实错误。 |
| default_chain_decision | source_type_reweight | keep_existing_hybrid | no candidate passed delta_precision_at_1 threshold | low | 不接入默认链路；保留 source_type_reweight 为候选/评测开关。 Blockers: delta_precision_at_1=+0.000<0.10; real:delta_precision_at_1=+0.000<0.10 | delta_precision_at_1=+0.000<0.10; real:delta_precision_at_1=+0.000<0.10 | delta_precision_at_1=+0.000<0.10; real:delta_precision_at_1=+0.000<0.10 |
| responsibility_gate | engineering_responsibility_refusal | closed | 4/4 matched | low | responsibility_gate 已闭环工程责任拒答遗留，且正反例测试覆盖学习题不误拒。 |
| api_regression | core_routes_and_tests | passed | full regression passed | low | 核心 API 与全量测试通过。 |
| overall | stage20_quality_gate | pass | low | low | 阶段 20 核心质量闭环完成；等待用户人工核验。 |

## 数据安全边界

- 报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- 报告只读取本地脱敏 CSV，不触发真实 API、不写数据库。
- 阶段 20 收尾等待用户人工核验，当前不提交、不打 tag、不推送。
