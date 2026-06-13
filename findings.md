# 阶段 30 发现与关键决策

## 阶段 29 基线

阶段 29 已完成、提交、打 tag 并合并到远端 `main`。

```text
main / origin/main -> cd32df6 Merge phase 29 real embedding quality eval
phase-29-complete -> b62b1a5 Complete phase 29 real embedding quality eval
```

阶段 29 质量产物：

- `data/evaluation/stage29_new_corpus_queries.csv`
- `data/evaluation/stage29_real_quality_results.csv`
- `data/evaluation/stage29_real_quality_summary.csv`
- `data/evaluation/stage29_quality_summary.csv`
- `docs/stage29_quality_report.md`

核心指标：

```text
precision_at_1=0.600
precision_at_3=0.867
precision_at_5=0.933
avg_coverage_ratio=0.664
refusal_accuracy=1.000
quality_gate=review_required/medium
```

人工复核重点：

- `stage29_wiki_dam_applications`：Top-5 未命中预期 source type。
- `stage29_web_rfc_advantages`：命中 web_page，但 coverage_ratio 低。

## Phase 0 启动核对

- 当前阶段 30 分支：`codex/phase-30-rag-evaluation-scoring-system`。
- `phase-29-complete` 指向 `b62b1a5 Complete phase 29 real embedding quality eval`。
- `main` 指向 `cd32df6 Merge phase 29 real embedding quality eval`。
- `git merge-base --is-ancestor phase-29-complete main` 已通过，阶段 29 已合并进 `main`。
- 阶段 30 启动时未移动任何阶段 tag，未执行提交、打 tag、push 或 PR 操作。

## 开源评测框架调研结论

### LlamaIndex

可借鉴点：

- 把 RAG 评测拆成 retrieval evaluation 与 response evaluation。
- RetrieverEvaluator 常见指标包括 hit-rate、MRR。
- Response evaluators 包括 faithfulness、relevancy、correctness、semantic similarity。

本项目采纳：

- 采纳分层评测思想。
- 在默认评分中加入 hit-rate/MRR 或等价排序指标。
- 不直接引入 LlamaIndex 依赖。

### Ragas

可借鉴点：

- context precision / context recall 用于评价检索上下文。
- faithfulness / answer relevancy 用于语义级回答评价。

本项目采纳：

- 默认模式只实现可复现的 context 命中、coverage 和 source_type 指标。
- faithfulness / answer relevancy 只能进入可选 LLM-as-Judge，不用规则匹配冒充。

### DeepEval

可借鉴点：

- G-Eval 类指标强调带理由的评分。
- RAG 指标不只是给数字，还要输出评估理由。

本项目采纳：

- 每个扣分项都输出 `deduction_reason` 和 `recommended_action`。
- 对 release decision 给出解释，而不是只给裸分。

### TruLens

可借鉴点：

- RAG Triad：context relevance、groundedness、answer relevance。

本项目采纳：

- 将 triad 作为文档和可选 judge 模式的概念参考。
- 默认 CI 不声称自己完成了 semantic groundedness。

### Phoenix

可借鉴点：

- Retrieval eval 与 response eval 分层。
- 质量结果和 observability 结合，便于看失败发生在哪一步。

本项目采纳：

- `/quality-report` 从指标表升级为评分 + 决策 + 风险队列。
- 保留失败样例队列和推荐动作。

## Phase 1 落地结论

- 已将参考框架映射写入 `docs/stage30_rag_evaluation_scoring_system.md`。
- 默认评分模式固定命名为 `deterministic_rule_based`，只允许使用阶段 29 CSV、阶段 30 权重 YAML 和 engineering health JSON。
- 阶段 29 的 `coverage_ratio` 在阶段 30 中只能称为 `rule_based_coverage_ratio` 或 `rule_based_context_answer_quality`，不能改名为 faithfulness。
- 可选语义评审模式固定命名为 `manual_llm_judge`，默认 dry-run；没有显式 `--execute` 不调用真实模型。

## Claude 评审意见吸收

Claude 对阶段 30 目标提出的四个坑全部采纳：

1. **faithfulness / answer relevancy 不能伪造**：阶段 29 的 coverage_ratio 是字符串覆盖，不是语义判断。默认评分不得把它命名成 faithfulness。
2. **权重必须可配置且有依据**：新增 `stage30_scoring_weights.yaml`，不在代码里写死 35/25/20/10/10。
3. **等级门槛缺校准数据**：`stage30_quality_scores.csv` 设计成历史趋势表，当前 A/B/C 阈值只是初始启发式。
4. **评分脚本不能跑 pytest**：engineering health 先产出 JSON，评分脚本只读取。

## 阶段 30 核心决策

### 决策 1：双模式评分

默认模式：

```text
mode=deterministic_rule_based
CI 可运行
不调用真实 API
只读取已有 CSV/YAML/JSON
```

可选模式：

```text
mode=manual_llm_judge
手动触发
可调用真实 MIMO judge
输出单独 CSV
不进入 CI
```

理由：既学习 Ragas/DeepEval 的语义评估思想，又不破坏项目离线约束。

Phase 5 已新增 `scripts/judge_stage30_semantic_quality.py`，默认 dry-run 只生成 `stage30_llm_judge_results.csv` 计划表，不调用真实模型。当前手动模式支持 OpenAI-compatible/DeepSeek provider，但必须显式 `--execute` 且本地存在 `STAGE30_JUDGE_API_KEY`；语义 judge 结果不会混入默认评分。

### 决策 2：默认 100 分维度

初始建议：

```text
retrieval_quality: 35
rule_based_context_answer_quality: 25
safety_refusal: 20
source_quality: 10
engineering_health: 10
```

权重理由：

- 检索质量最高，因为 RAG 的回答质量首先受 top-k 召回影响。
- 上下文/答案覆盖第二，因为阶段 29 已暴露“命中但覆盖不足”的问题。
- 安全拒答 20 分，因为工程签字、密钥、付费墙边界必须稳定。
- 来源质量 10 分，用于避免过度依赖 metadata 或单一来源。
- 工程健康 10 分，保证评分建立在可复现系统状态上。

这些权重是初始启发式，必须配置化，并允许后续根据历史趋势调整。

Phase 2 已将这些权重落盘到 `data/evaluation/stage30_scoring_weights.yaml`，并为每个维度保留机器可读 rationale。后续评分脚本只能读取该文件，不得把权重常量写死在评分公式里。

### 决策 3：趋势表而不是一次性分数

`stage30_quality_scores.csv` 应支持多次追加：

```text
run_id,run_at,scoring_version,overall_score,grade,release_decision,
retrieval_score,context_answer_score,safety_score,source_score,engineering_score,
baseline_run_id,score_delta,main_deductions,recommended_actions
```

这样阶段 31 以后可以回答：“这次比上次提升/下降了多少，主要原因是什么。”

Phase 4 已生成初版趋势表 `data/evaluation/stage30_quality_scores.csv`，当前 `overall_score=83.17`、`grade=B`、`release_decision=review_required`。该分数的主要拉低因素是 retrieval top-1 较弱和两个低规则覆盖率样例，不是工程健康或拒答边界。

Phase 6 已将 `/quality-report` 升级为阶段 30 评分报告。JSON/CSV 导出当前读取 `stage30_quality_summary.csv`，静态 HTML 内联展示评分总览、维度分、deductions 和 recommended actions；阶段 29 原始 CSV 与报告保持可追溯，不被覆盖。

## Phase 7 验证结论

- 聚焦测试：`17 passed`。
- 全量测试：`567 passed, 1 warning`。
- 接口冒烟：`/health`、`/quality-report`、`/quality-report/data.json`、`/quality-report/export.csv` 均为 200。
- 浏览器冒烟：`overall=83.17`、`grade=B`、`release_decision=review_required`、summary rows 6、deduction rows 3、recommended actions 2、console errors 0。
- `stage30_engineering_health.json` 已刷新为阶段 30 验证结果，评分趋势表追加 `stage30-final-validation`。

## Phase 8 收尾结论

- 普通文档已同步：`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 阶段验收草稿已新增：`docs/phase_reviews/phase-30.md`。
- Obsidian 已补：阶段页、阶段汇报汇总、知识点和索引链接。
- 当前必须停在人工核验前，不提交、不打 tag、不 push、不创建 PR。

### 决策 4：Engineering Health 作为输入

评分脚本不直接跑测试，而是读取：

```text
data/evaluation/stage30_engineering_health.json
```

建议结构：

```json
{
  "full_tests_status": "556 passed, 1 warning",
  "chunk_count": 12716,
  "embedding_count": 25432,
  "jina_embedding_count": 12716,
  "deterministic_embedding_count": 12716,
  "orphan_embeddings": 0,
  "duplicate_provider_model_groups": 0,
  "quality_report_smoke": "passed"
}
```

Phase 3 已落地 `scripts/collect_stage30_engineering_health.py` 和 `data/evaluation/stage30_engineering_health.json`。采集器仅做只读统计，不跑 pytest、不重建 embedding、不写数据库、不调用真实 API；评分器后续只能读取该 JSON。

## 风险与防线

- 风险：总分好看但指标不真实。
  - 防线：默认模式不使用 faithfulness / answer relevancy 命名。
- 风险：权重被质疑主观。
  - 防线：YAML 配置 + rationale + 历史趋势。
- 风险：评分脚本变重。
  - 防线：评分脚本只读输入，不跑 pytest、不调 API、不改 DB。
- 风险：LLM-as-Judge 泄露供应商响应。
  - 防线：可选模式单独输出脱敏结果，不保存 raw_response。
- 风险：阶段 29 的质量报告被覆盖后失去溯源。
  - 防线：保留 stage29 artifacts，stage30 输出新文件，不改写 stage29 原始结果。

## 面试表达准备

阶段 30 可以这样讲：

> 阶段 29 已经能跑真实检索评测，但只有散指标。阶段 30 我参考 LlamaIndex、Ragas、DeepEval、TruLens 和 Phoenix，把评测拆成检索质量、规则覆盖质量、安全拒答、来源质量和工程健康五个维度，输出总分、等级、扣分原因和推荐动作。同时我明确区分规则评分和语义评分：CI 默认只跑 deterministic 的可复现指标，faithfulness 和 answer relevancy 只能通过手动 LLM-as-Judge 模式产生，避免用关键词匹配冒充语义判断。

## 追加发现：DeepSeek 手动 judge 接入边界

- `scripts/judge_stage30_semantic_quality.py` 已支持 OpenAI-compatible `/chat/completions` 调用，可用于 DeepSeek 手动 LLM-as-Judge。
- 默认模式仍为 dry-run；缺少 `--execute` 时不会读取 key、不会联网、不会生成语义分数。
- 即使传入 `--execute`，缺少 `STAGE30_JUDGE_API_KEY` 时也只写入 `missing_env:STAGE30_JUDGE_API_KEY`，不调用 provider。
- judge prompt 只使用阶段 29 CSV 中的摘要字段和规则指标提示，不把 `coverage_ratio` 包装成 faithfulness。
- 输出脱敏且不保存供应商原始响应或 `raw_response`，避免把手动 judge 支路变成敏感数据落盘点。
