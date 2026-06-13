# 阶段 30 验收草稿：RAG 质量评分体系与诚实决策门禁

## 验收结论

当前结论：`PASS for human review`。阶段 30 的开发、测试、普通文档和 Obsidian 草稿已完成；最终状态必须停在用户人工核验前。当前不允许 `git add`、`git commit`、`git tag`、`git push` 或创建 PR。

## 范围对齐

- 已从阶段 29 完成并合并后的 `main` 创建/切换到 `codex/phase-30-rag-evaluation-scoring-system`。
- 已核对 `phase-29-complete -> b62b1a5 Complete phase 29 real embedding quality eval`。
- 已核对 `main -> cd32df6 Merge phase 29 real embedding quality eval`，且 `phase-29-complete` 是 `main` 的祖先。
- 未移动任何已有阶段 tag。
- 未引入 LlamaIndex、Ragas、DeepEval、TruLens、Phoenix 等重依赖。
- 未引入 `torch`、`sentence-transformers`、写入型 Agent 工具、登录系统、部署优化、新爬虫或外部资料来源。

## 功能证据

- 新增 `docs/stage30_rag_evaluation_scoring_system.md`，说明参考框架、采纳点、不采纳点、默认规则评分和可选 LLM-as-Judge 边界。
- 新增 `data/evaluation/stage30_scoring_weights.yaml`，五个维度合计 100，并写入 rationale。
- 新增 `scripts/collect_stage30_engineering_health.py` 和 `data/evaluation/stage30_engineering_health.json`。
- 新增 `scripts/score_stage30_quality.py`，输出：
  - `data/evaluation/stage30_quality_scores.csv`
  - `data/evaluation/stage30_quality_summary.csv`
  - `data/evaluation/stage30_quality_deductions.csv`
- 新增 `scripts/judge_stage30_semantic_quality.py` 和 dry-run 输出 `data/evaluation/stage30_llm_judge_results.csv`。
- 新增 `scripts/build_stage30_quality_report.py` 和 `docs/stage30_quality_score_report.md`。
- `/quality-report` 已升级为阶段 30 评分报告，JSON/CSV 导出读取 `stage30_quality_summary.csv`。

## 当前评分

```text
overall_score 83.17
grade B
release_decision review_required
retrieval_quality 26.83 / 35
rule_based_context_answer_quality 16.60 / 25
safety_refusal 20.00 / 20
source_quality 9.73 / 10
engineering_health 10.00 / 10
```

主要扣分项：

- `stage29_wiki_dam_applications`：Top-5 未命中预期 source type。
- `stage29_wiki_dam_applications`：rule-based coverage_ratio 0.250，低于 0.500。
- `stage29_web_rfc_advantages`：rule-based coverage_ratio 0.250，低于 0.500。

当前 `review_required` 是诚实门禁结论，不是失败，也不是伪造 pass。

## 测试证据

阶段 30 聚焦测试：

```text
python -m pytest tests/test_stage30_scoring.py tests/test_stage30_engineering_health.py tests/test_stage30_semantic_judge.py tests/test_build_stage30_quality_report.py tests/test_frontend_app.py -q
21 passed
```

阶段收尾全量测试：

```text
python -m pytest -q
571 passed, 1 warning
```

接口冒烟：

```text
GET /health 200
GET /quality-report 200
GET /quality-report/data.json 200
GET /quality-report/export.csv 200
```

浏览器冒烟：

```text
/quality-report overall=83.17
grade=B
release_decision=review_required
summary rows=6
deduction rows=3
recommended actions=2
console errors=0
```

## 安全合规

- 默认评分模式为 `deterministic_rule_based`，不调用真实模型。
- `rule_based_context_answer_quality` 明确不是 `faithfulness`、`answer_relevancy` 或 `groundedness`。
- 可选 `manual_llm_judge` 默认是 dry-run；显式 `--execute` 且本地存在 `STAGE30_JUDGE_API_KEY` 时可调用 DeepSeek/OpenAI-compatible provider，但不进入 CI，也不覆盖默认评分。
- 评分脚本不内部跑 pytest、不重建 embedding、不主动写数据库、不调用真实 API。
- 未把 API key、Bearer token、Authorization header、供应商原始响应、raw_response 或受限全文写入 Git、CSV、文档、测试或 Obsidian。

## 人工核验清单

- 打开 `/quality-report`，确认总分、等级、发布建议、维度分、扣分项和推荐动作可读。
- 抽查 `stage30_quality_deductions.csv` 中的三条扣分项是否符合阶段 29 真实结果。
- 确认 `stage30_scoring_weights.yaml` 的权重和 rationale 是否符合用户预期。
- 确认 `stage30_llm_judge_results.csv` 只是 dry-run，不含真实模型输出。
- 人工核验通过前不要提交、不要创建 `phase-30-complete` tag、不要 push。

## 面试表达

阶段 30 我把阶段 29 的散指标升级成一个可解释的质量门禁系统。设计上我参考了 LlamaIndex、Ragas、DeepEval、TruLens 和 Phoenix 的分层评测思想，但没有引入这些重依赖。默认评分只读已有评测 CSV、权重 YAML 和工程健康 JSON，输出总分、等级、发布建议、维度分、扣分项和推荐动作；真正需要语义判断的 faithfulness、answer relevancy、groundedness 只留在手动 LLM-as-Judge 支路，避免用关键词覆盖率冒充语义质量。当前得分 83.17，结论是 review_required，因为检索和规则覆盖仍有人工复核项，但安全拒答和工程健康是满分。

## 追加验收记录：DeepSeek 手动 judge 适配器

- `manual_llm_judge` 已从 dry-run 骨架升级为 OpenAI-compatible 手动 runner，可使用 DeepSeek 作为 judge provider。
- 默认 dry-run 仍为离线模式，当前 `data/evaluation/stage30_llm_judge_results.csv` 由默认命令生成，`real_model_calls=0`。
- 真实调用必须显式使用 `--execute`，并在本地环境变量设置 `STAGE30_JUDGE_API_KEY`；仓库中未写入任何实际 key。
- 输出只保存语义分数、简短理由和脱敏错误，不保存 API key、Bearer token、Authorization header、供应商原始响应、`raw_response` 或受限全文。
- 该手动 judge 结果不进入 CI、不参与默认门禁、不改变 `overall_score=83.17`、`grade=B`、`release_decision=review_required`。
