# 阶段 35 设计：检索质量校准与 Stage 30 评分破局

## 目标

阶段 35 的目标是正面处理阶段 30 以来持续存在的 `overall_score=83.17`、`grade=B`、`release_decision=review_required`。本阶段不继续做架构扩张，而是沿着已经暴露的扣分项做闭环：

```text
阶段 34 决策报告 / 阶段 30 评分 / 真实 Judge 结果
-> Stage 30 扣分根因分类
-> 检索召回与父子块上下文最小修复
-> prompt 引用约束与 invalid_citations 处理强化
-> 真实 Judge 复跑
-> Stage 30 评分重跑
-> 阶段 35 验收草稿与人工核验
```

目标结果是 `overall_score >= 88`、`grade >= A-`、`release_decision=pass`。如果没有达到目标，阶段 35 必须在报告中诚实说明剩余根因，不能通过调权、放松规则或隐藏失败样例伪造通过。

## 输入基线

阶段 35 从阶段 34 已合并后的 `main` 出发：

```text
main / origin/main -> d9053a6 Merge phase 34 rag diagnosis embedding judge
phase-34-complete -> 8028acb Complete phase 34 rag diagnosis embedding judge
phase-34-complete 已合并到 main
目标分支 -> codex/phase-35-retrieval-quality-calibration
```

阶段 34 已确认的质量观察：

```text
stage30_overall_score=83.17
stage30_grade=B
stage30_release_decision=review_required
stage30 主要扣分项=stage29_wiki_dam_applications Top-5 未命中；stage29_wiki_dam_applications 和 stage29_web_rfc_advantages 覆盖率低
stage34 Judge=high 0, medium 4, avg citation_support 0.613, avg answer_coverage 0.675
```

## 归因方法

阶段 35 必须先归因再修复。`scripts/analyze_stage35_deduction_causes.py` 读取 `data/evaluation/stage30_quality_deductions.csv`、`data/evaluation/stage29_real_quality_results.csv` 和阶段 30 评分结果，输出 `data/evaluation/stage35_deduction_root_causes.csv`。

扣分项必须归到以下五类之一：

- `retrieval_miss`：检索 Top-K 没召回预期来源或包含答案的 chunk。
- `context_expansion_miss`：child 命中后，父子块或相邻上下文没有带入足够证据。
- `prompt_citation_gap`：模型回答中有事实陈述，但缺少对应 `[N]` 引用或引用不稳定。
- `answer_coverage_gap`：答案没有覆盖 `expected_answer_points` 中的关键点。
- `rule_too_strict`：规则评分关键词过窄，低估了同义表达或合理换说法。

`rule_too_strict` 可以成为结论，但不能直接成为放水理由。如果需要修改规则关键词，必须在 Phase 6 决策报告中说明规则修订原因、影响范围和对历史基线的含义。

## 修复范围

阶段 35 允许的最小修复范围：

- 检索召回：同义词扩展、keyword/BM25/vector 权重的局部校准、Top-K 或 recall_k 的保守调整。
- 父子块上下文：检查 `parent_chunk_id` 与上下文扩展边界，确保答案邻近证据进入 prompt。
- prompt 引用约束：强化 `app/services/generation/prompt_builder.py` 中事实陈述必须带 `[N]` 的规则。
- 引用校验：复核 `invalid_citations` 的提取与处理，不让无效引用静默进入质量报告。
- 评分对比：保留 Stage 30 权重，不通过改权重制造 pass。

阶段 35 不做：

- 不替换默认 chat provider，不动 Paratera DeepSeek-V4-Flash planner + DeepSeek-V4-Pro answer 拓扑。
- 不替换默认 embedding provider，不把 Jina 重新设为默认，不删除旧 Jina 或 GLM 索引。
- 不替换 rerank provider。
- 不新增外部数据源、不爬新网页、不下载新 PDF、不重切 chunk。
- 不做写入型 Agent 工具。
- 不做 tool-calling 协议迁移。
- 不改 `/chat`、`/agent/query`、`/agent/query/stream`、`/search/*`、`/quality-report` 的兼容 contract。

## 双门验证

阶段 35 的质量结论必须同时看两个门：

1. Stage 30 deterministic scoring：重跑 `python scripts/score_stage30_quality.py`，目标 `overall_score >= 88`、`grade >= A-`、`release_decision=pass`。
2. 真实 LLM Judge：显式手动复跑不少于 10 条，输出 `data/evaluation/stage35_llm_judge_results.csv` 与 summary，目标 `citation_support >= 0.80`、`answer_coverage >= 0.80`、`high=0`。

真实 Judge 不进入 CI，不作为本地全量 pytest 前提。缺少真实 provider 配置时必须写 `skipped` 或 `error`，不能用 deterministic 结果冒充真实通过。

## 安全边界

阶段 35 新增 CSV、测试、文档和 Obsidian 草稿不得写入：

- API key
- Bearer token
- Authorization header
- raw provider response
- `reasoning_content`
- hidden thought
- 受限全文

CSV 只保存脱敏指标、query_id、根因分类、短证据摘要、修复建议、状态和必要的 provider/model 名称。错误只保存可公开的短摘要。

## 面试表达

阶段 35 我没有继续堆新 Agent 功能，而是把阶段 30 以来一直挂着的 `review_required` 当成质量债来处理。做法是先把每个扣分项归因到检索、上下文、prompt、答案覆盖或规则过严，再做最小修复，最后用 Stage 30 规则评分和真实 LLM Judge 双门复核。这样既避免了靠调权刷分，也能清楚说明如果仍然没有 pass，瓶颈到底是在召回、上下文、引用、答案覆盖还是评估规则本身。
