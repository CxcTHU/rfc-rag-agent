# 阶段 30 质量评分报告：RAG 质量评分体系与诚实决策门禁

本报告由 `scripts/build_stage30_quality_report.py` 生成，只读汇总阶段 30 的脱敏评分结果，不触发真实 API、不写数据库、不重建 embedding。

## 总览

- run_id：`stage30-63b8d169d1e2`
- scoring_version：`stage30-v1`
- scoring_mode：`deterministic_rule_based`
- overall_score：91.52
- grade：A
- release_decision：pass
- score_delta：0.002

## 维度分

| Dimension | Weight | Score | Max | Normalized | Status | Evidence |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| retrieval_quality | 35.00 | 33.36 | 35.00 | 0.953 | strong | precision_at_1/3/5 from stage29_real_quality_summary.csv |
| rule_based_context_answer_quality | 25.00 | 18.27 | 25.00 | 0.731 | review_required | avg_coverage_ratio from stage29_real_quality_summary.csv |
| safety_refusal | 20.00 | 20.00 | 20.00 | 1.000 | strong | refusal_accuracy from stage29_real_quality_summary.csv |
| source_quality | 10.00 | 9.89 | 10.00 | 0.989 | strong | source_type_distribution and expected source misses |
| engineering_health | 10.00 | 10.00 | 10.00 | 1.000 | strong | stage30_engineering_health.json |
| overall | 100.00 | 91.52 | 100.00 | 0.915 | pass | grade=A; scoring_mode=deterministic_rule_based |

## 扣分项

- 当前无扣分项。

## 推荐动作

- Continue human review of the stage 30 score report before commit/tag/push.

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
