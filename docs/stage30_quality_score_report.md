# 阶段 30 质量评分报告：RAG 质量评分体系与诚实决策门禁

本报告由 `scripts/build_stage30_quality_report.py` 生成，只读汇总阶段 30 的脱敏评分结果，不触发真实 API、不写数据库、不重建 embedding。

## 总览

- run_id：`stage30-clickable-human-review-validation`
- scoring_version：`stage30-v1`
- scoring_mode：`deterministic_rule_based`
- overall_score：83.17
- grade：B
- release_decision：review_required
- score_delta：-0.004

## 维度分

| Dimension | Weight | Score | Max | Normalized | Status | Evidence |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| retrieval_quality | 35.00 | 26.83 | 35.00 | 0.767 | review_required | precision_at_1/3/5 from stage29_real_quality_summary.csv |
| rule_based_context_answer_quality | 25.00 | 16.60 | 25.00 | 0.664 | weak | avg_coverage_ratio from stage29_real_quality_summary.csv |
| safety_refusal | 20.00 | 20.00 | 20.00 | 1.000 | strong | refusal_accuracy from stage29_real_quality_summary.csv |
| source_quality | 10.00 | 9.73 | 10.00 | 0.973 | strong | source_type_distribution and expected source misses |
| engineering_health | 10.00 | 10.00 | 10.00 | 1.000 | strong | stage30_engineering_health.json |
| overall | 100.00 | 83.17 | 100.00 | 0.832 | review_required | grade=B; scoring_mode=deterministic_rule_based |

## 扣分项

| Severity | Dimension | Query | Points | Reason | Recommended Action |
| --- | --- | --- | ---: | --- | --- |
| medium | retrieval_quality | stage29_wiki_dam_applications | 2.00 | Top-5 retrieval did not include the expected source type; this remains a manual review item from stage 29. | Review query design, expected source labeling, and top-k evidence before claiming release readiness. |
| medium | rule_based_context_answer_quality | stage29_wiki_dam_applications | 2.00 | Rule-based coverage_ratio=0.250 is below 0.500; this is not a semantic faithfulness score. | Inspect missing answer points and decide whether retrieval, corpus labeling, or the expected points need calibration. |
| medium | rule_based_context_answer_quality | stage29_web_rfc_advantages | 2.00 | Rule-based coverage_ratio=0.250 is below 0.500; this is not a semantic faithfulness score. | Inspect missing answer points and decide whether retrieval, corpus labeling, or the expected points need calibration. |

## 推荐动作

- Inspect missing answer points and decide whether retrieval, corpus labeling, or the expected points need calibration.
- Review query design, expected source labeling, and top-k evidence before claiming release readiness.

## Engineering Health

- full_tests_status：571 passed, 1 warning
- quality_report_smoke：passed: /health 200; /quality-report 200; /quality-review 200; review save click passed; data.json 200; review_data.json 200; export.csv 200; browser review_cases=15; needs_review=4; critical=3; console_errors=0
- chunk_count：12716
- embedding_count：25432
- jina_embedding_count：12716
- deterministic_embedding_count：12716
- orphan_embeddings：0
- duplicate_provider_model_groups：0

## Human Review Workbench

- `GET /quality-review` provides a read-only review UI for stage 30 human verification.
- `GET /quality-review/data.json` merges stage 29 quality rows, stage 30 deductions, and optional LLM judge rows by `query_id`.
- The page shows retrieval evidence, rule-based coverage, DeepSeek judge scores, judge reasons, deductions, and suggested human review labels.
- The review UI does not write the database or call a model. Human decisions are saved only to `data/evaluation/stage30_human_review.csv`.

## 边界

- 默认评分为 `deterministic_rule_based`，不调用真实模型。
- `rule_based_context_answer_quality` 不是 faithfulness、answer relevancy 或 groundedness。
- 可选 LLM-as-Judge 只在手动模式单独输出，不进入 CI 门禁。
- 报告不保存 API key、Bearer token、Authorization header、供应商原始响应、raw_response 或受限全文。
