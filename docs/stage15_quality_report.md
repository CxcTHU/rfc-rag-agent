# 阶段 15 质量审阅报告

本报告由 `scripts/build_stage15_quality_report.py` 生成，只读汇总阶段 14/15 质量表，不触发真实 API 调用。

| Section | Metric | Status | Value | Baseline | Risk | Recommendation |
|---|---|---|---|---|---|---|
| real_config | agent | completed | 5/5 (1.000) | 5/5 (1.000) | low | agent 真实配置结果可作为发布前校准证据。 |
| real_config | brain_workflow | completed | 18/18 (1.000) | 18/18 (1.000) | low | brain_workflow 真实配置结果可作为发布前校准证据。 |
| real_config | chat | completed | 6/6 (1.000) | 6/6 (1.000) | low | chat 真实配置结果可作为发布前校准证据。 |
| real_config | decompose | error | 0/0 | 10/10 (1.000) | high | 优先排查 decompose 真实配置错误；不要用 deterministic 结果伪造成真实通过。 |
| real_config | hybrid | completed | 15/15 (1.000) | 15/15 (1.000) | low | hybrid 真实配置结果可作为发布前校准证据。 |
| real_config | user_questions | completed | 27/30 (0.900) | 25/30 (0.833) | medium | user_questions 真实结果与 deterministic baseline 不同，保留差异用于人工审阅。 |
| real_config | vector | completed | 15/15 (1.000) | 13/15 (0.867) | medium | vector 真实结果与 deterministic baseline 不同，保留差异用于人工审阅。 |
| answer_coverage | review_rows | completed | 9 | stage14 medium/review rows | high | 将 high 样例作为发布前阻断风险，将 medium 样例保留为人工审阅样例。 |
| answer_coverage | risk_high | completed | 1 |  | high | 发布前优先处理 high 风险回答，通常是超时、无答案或来源不匹配。 |
| answer_coverage | risk_medium | completed | 8 |  | medium | 保留 medium 样例进入人工审阅，检查回答是否真正覆盖期望要点。 |
| provenance | evidence_rows | completed | 50 | 50 stage14 evidence rows | low | 保留证据级 provenance 作为人工审阅和报告依据。 |
| provenance | both_match_rows | completed | 37 | 37 stage14 both-match rows | low | both_match 越多，说明 keyword/vector 双路证据更一致。 |
| provenance | decomposed_evidence_rows | completed | 15 | 15 stage14 decomposed rows | low | 保留 decomposed evidence rows 解释复杂问题证据来源。 |
| overall | stage15_quality_gate | review_required | high | stage14 quality tables | high | 阶段 15 已形成真实配置和回答复核报告；发布前优先处理 high 风险和真实 decompose error。 |

## 数据安全边界

- 报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- 真实回答只以脱敏摘要和指标进入审阅表。
- `obsidian-vault/` 仍作为本地知识库，不纳入 Git 提交。
