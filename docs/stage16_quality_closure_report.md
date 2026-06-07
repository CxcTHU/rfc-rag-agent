# 阶段 16 质量风险闭环报告

本报告由 `scripts/build_stage16_quality_closure_report.py` 生成，只读汇总阶段 16 风险闭环表，不触发真实 API 调用。

| Section | Metric | Status | Value | Baseline | Risk Before | Risk After | Recommendation |
|---|---|---|---|---|---|---|---|
| decompose | decompose | retry_completed | embedding_header_compatibility_and_chat_timeout | stage15 status=error | high | low | 保留阶段 16 显式真实 decompose 重试结果；后续真实复跑建议使用兼容 embedding 请求头和更长 chat timeout。 |
| answer_coverage | closure_rows | completed | 9 | before high=1, medium=8 | high | high | 阶段 16 已为 high/medium 样例补充 risk_after、root_cause、decision 和 next_action。 |
| answer_coverage | risk_after_high | completed | 1 | stage15 risk_before high/medium | high | high | 仍有 high 样例，通常是超时、无答案或证据不足；必须人工核验。 |
| answer_coverage | risk_after_medium | completed | 3 | stage15 risk_before high/medium | high | medium | medium 样例保留为人工审阅项，通常是来源细节不足。 |
| answer_coverage | risk_after_low | completed | 5 | stage15 risk_before high/medium | high | low | low 样例可作为阶段 16 闭环通过证据。 |
| overall | stage16_quality_gate | review_required | high | stage15 overall=review_required/high | high | high | real decompose 已完成阶段 16 显式重试；当前剩余 high 阻断来自 Answer Coverage 样例，需要人工核验或重跑真实回答。 |

## 数据安全边界

- 报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- 阶段 16 只读取本地脱敏 CSV 质量产物。
- 阶段 16 收尾等待用户人工核验，当前不提交、不打 tag、不推送。
