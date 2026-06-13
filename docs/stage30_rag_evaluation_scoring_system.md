# 阶段 30 设计：RAG 质量评分体系与诚实决策门禁

## 目标

阶段 29 已经把真实 Jina embedding 重建和端到端质量评测跑通，但输出仍是散指标：`precision@k`、`coverage_ratio`、`refusal_accuracy` 和人工复核队列。阶段 30 的目标是把这些散指标升级为轻量级评分体系：

```text
stage29_real_quality_results.csv / summary.csv
-> stage30_scoring_weights.yaml
-> stage30_engineering_health.json
-> score_stage30_quality.py
-> overall_score / grade / release_decision
-> deductions / recommended_actions / manual_review_queue
-> stage30 quality CSVs
-> docs/stage30_quality_score_report.md
-> /quality-report
```

本阶段不追求引入大型评测框架，而是参考主流 RAG 评测框架的指标思想，构建适合本项目的、默认离线可复现的评分与决策门禁。

## 新词解释

- RAG 质量评分：把检索命中、上下文覆盖、拒答边界、来源质量和工程健康等指标合成一个可解释总分。本项目里它用于判断当前阶段是否可以进入人工发布核验。
- 决策门禁：不是只给分，而是根据分数、扣分项和风险队列输出 `pass`、`review_required` 或 `blocked`。本项目里它保护“不能把中等风险伪装成通过”。
- LLM-as-Judge：用大模型作为评审员检查回答是否忠实、相关、 grounded。它更接近语义判断，但会引入模型成本、稳定性和隐私边界，所以本项目只放在手动可选模式。
- faithfulness：回答中的事实是否能被检索上下文支持。它需要理解回答中的 claim，不能用字符串覆盖率冒充。
- groundedness：回答是否扎根于给定证据。它和 faithfulness 接近，通常需要语义判断或人工审核。

## 参考框架与采纳点

### LlamaIndex

LlamaIndex 的 retrieval evaluation 用 `RetrieverEvaluator` 评估 retriever，并支持 hit-rate、MRR、precision、recall、AP、NDCG 等指标。参考文档：<https://developers.llamaindex.ai/python/examples/evaluation/retrieval/retriever_eval/>。

本项目采纳：

- 采纳“先评检索，再评回答”的分层思想。
- 在默认评分中使用 `precision_at_1`、`precision_at_3`、`precision_at_5` 等阶段 29 已产出的检索指标。
- 后续可扩展 MRR 或 NDCG，但阶段 30 不强行增加新检索运行。

本项目不采纳：

- 不引入 LlamaIndex 依赖。
- 不用 LlamaIndex 自动生成评测集，因为本项目当前更需要人工维护的水利工程领域题集。

### Ragas

Ragas 将 RAG 评测拆成 context precision、context recall、faithfulness、answer relevancy 等组件指标。参考文档：<https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/>、<https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/>。

本项目采纳：

- 采纳 context precision / recall 的思路：默认评分关注 top-k 是否召回预期来源，以及上下文是否覆盖期望要点。
- 采纳组件化汇总方式：检索质量、规则覆盖质量、安全拒答、来源质量、工程健康分别计分。

本项目不采纳：

- 不把阶段 29 的 `coverage_ratio` 命名为 faithfulness、answer relevancy 或 groundedness。
- 不在 CI 中调用真实 LLM 计算 Ragas 语义指标。

### DeepEval

DeepEval 提供 G-Eval 和 RAG 指标，强调 LLM-as-a-judge 和带理由的评分；其 contextual relevancy / faithfulness 等指标会输出解释理由。参考文档：<https://deepeval.com/docs/metrics-llm-evals>、<https://deepeval.com/docs/metrics-contextual-relevancy>、<https://deepeval.com/docs/metrics-faithfulness>。

本项目采纳：

- 每个扣分项必须输出 `deduction_reason` 和 `recommended_action`。
- `release_decision` 必须带可读解释，不能只输出裸分。

本项目不采纳：

- 不引入 DeepEval 依赖。
- 不让 G-Eval 风格 judge 成为默认测试或 CI 前提。

### TruLens

TruLens 的 RAG Triad 包含 context relevance、groundedness 和 answer relevance。参考文档：<https://www.trulens.org/getting_started/core_concepts/rag_triad/>。

本项目采纳：

- 把 RAG Triad 作为可选语义评审的概念边界。
- 在报告中明确“默认规则分”和“语义 judge 分”分开。

本项目不采纳：

- 不把当前规则覆盖率包装成 groundedness。
- 不引入 tracing/observability SDK。

### Phoenix

Phoenix 的思路是把 retrieval eval、response eval 和可观测性结合，帮助定位失败发生在检索、生成还是系统运行状态。参考文档：<https://phoenix.arize.com/> 与 Phoenix eval/observability 文档。

本项目采纳：

- `/quality-report` 展示维度分、扣分项、风险队列和推荐动作，让失败位置更清楚。
- 引入 engineering health artifact，把测试、索引完整性和页面冒烟状态作为评分输入。

本项目不采纳：

- 不引入 Phoenix 依赖。
- 不做线上 tracing、监控平台或部署优化。

## 默认规则评分边界

默认评分模式命名为：

```text
deterministic_rule_based
```

它只能使用已经存在且可复现的输入：

- `data/evaluation/stage29_real_quality_results.csv`
- `data/evaluation/stage29_real_quality_summary.csv`
- `data/evaluation/stage30_scoring_weights.yaml`
- `data/evaluation/stage30_engineering_health.json`

默认评分允许输出：

- `retrieval_quality`
- `rule_based_context_answer_quality`
- `safety_refusal`
- `source_quality`
- `engineering_health`
- `overall_score`
- `grade`
- `release_decision`
- `deductions`
- `recommended_actions`

默认评分不得输出或冒充：

- `faithfulness`
- `answer_relevancy`
- `groundedness`
- `semantic_correctness`

如果报告需要提到阶段 29 的 `coverage_ratio`，必须称为 `rule_based_coverage_ratio` 或 `rule_based_context_answer_quality`，并说明它是规则/字符串层面的可复现指标，不是语义忠实度。

## 可选 LLM-as-Judge 边界

可选 judge 模式命名为：

```text
manual_llm_judge
```

它只在用户明确手动执行并传入 `--execute` 时运行。默认 `--dry-run` 不调用真实模型。

可选输出单独保存到：

```text
data/evaluation/stage30_llm_judge_results.csv
```

建议字段：

```text
query_id,judge_provider,judge_model,manual_run,
faithfulness_score,answer_relevancy_score,groundedness_score,
judge_reason,error_summary
```

安全边界：

- 不写 API key、Bearer token、Authorization header。
- 不写供应商原始响应、`raw_response` 或完整敏感错误。
- 不保存受限全文。
- 不进入 CI。
- 不覆盖默认 deterministic scoring 的结论。

## 评分维度

阶段 30 初始总分为 100 分，权重来自 `data/evaluation/stage30_scoring_weights.yaml`：

```text
retrieval_quality: 35
rule_based_context_answer_quality: 25
safety_refusal: 20
source_quality: 10
engineering_health: 10
```

这些权重是初始启发式，不是永久真理。后续阶段可以根据 `stage30_quality_scores.csv` 的历史趋势校准。

## 决策门禁

初始建议：

```text
A: >= 90
B: >= 80
C: >= 70
D: >= 60
F: < 60
```

发布建议：

```text
pass:
  overall_score >= 85
  no blocking deduction
  engineering_health >= configured pass threshold

review_required:
  overall_score >= 70
  no blocking deduction
  has medium-risk deductions or manual review queue

blocked:
  overall_score < 70
  or safety_refusal below threshold
  or engineering_health failed
  or scoring inputs missing
```

门禁结论必须可解释：每次输出都要包含主要扣分项、人工复核队列和下一步建议。

## 面试表达

阶段 30 我没有直接引入 Ragas 或 DeepEval 这类重框架，而是学习它们把 RAG 质量拆成检索、上下文、回答和安全边界的思路。默认评分只使用离线可复现的规则指标，比如 precision@k、规则覆盖率、拒答准确率、来源分布和工程健康；真正需要语义理解的 faithfulness、answer relevancy、groundedness 只放到手动 LLM-as-Judge 模式，避免用关键词匹配冒充语义评估。这样评分既能进入 CI，也能诚实保留人工复核和语义评审的边界。

## 追加记录：DeepSeek 手动 judge 适配器

`scripts/judge_stage30_semantic_quality.py` 已从纯 dry-run 骨架升级为 OpenAI-compatible 手动 judge runner。默认执行仍然是 dry-run，不调用任何真实模型；只有显式传入 `--execute`，并且本地环境变量里存在 `STAGE30_JUDGE_API_KEY` 时，才会调用 provider。

建议本地环境变量如下，严禁把实际 key 写入仓库、CSV、文档、测试或 Obsidian：

```text
STAGE30_JUDGE_PROVIDER=deepseek
STAGE30_JUDGE_MODEL=deepseek-chat
STAGE30_JUDGE_API_KEY=<local-secret-only>
STAGE30_JUDGE_BASE_URL=https://api.deepseek.com
```

该手动模式只读取阶段 29 评测 CSV 中的 query、source type、top titles、rule_based_coverage_ratio、covered_points 和 missing_points 等摘要字段；输出只保存 `faithfulness_score`、`answer_relevancy_score`、`groundedness_score`、`judge_reason` 与脱敏后的 `error_summary`。脚本不保存 API key、Authorization header、Bearer token、供应商原始响应、`raw_response` 或受限全文。语义 judge 结果仍不进入 CI，也不覆盖默认 deterministic scoring 的 `overall_score`、`grade` 或 `release_decision`。
