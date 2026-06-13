# 阶段 30 进度日志：RAG 质量评分体系与诚实决策门禁

## 当前状态

- 当前阶段：阶段 30「RAG 质量评分体系与诚实决策门禁」规划已完成，等待开发线程开启。
- 当前本地分支：`main`。
- 当前远端同步状态：`main...origin/main` 干净。
- 阶段 29 已完成提交、创建 `phase-29-complete` tag，并合并到远端 `main`。
- 阶段 30 建议分支：`codex/phase-30-rag-evaluation-scoring-system`。
- 提交边界：阶段 30 开发完成后必须停在用户人工核验前；不要提交、不要创建 `phase-30-complete` tag、不要 push、不要创建 PR，直到用户明确确认。

## 阶段 29 验收基线

```text
main / origin/main -> cd32df6 Merge phase 29 real embedding quality eval
phase-29-complete -> b62b1a5 Complete phase 29 real embedding quality eval
```

阶段 29 最终验证：

```text
python -m pytest -q
556 passed, 1 warning

GET /health 200
GET /quality-report 200
GET /quality-report/data.json 200
GET /quality-report/export.csv 200

Browser smoke:
/quality-report summary rows=7
risk queue rows=3
console errors=0
```

阶段 29 真实质量结果：

```text
precision_at_1=0.600
precision_at_3=0.867
precision_at_5=0.933
avg_coverage_ratio=0.664
refusal_accuracy=1.000
quality_gate=review_required/medium
```

## 阶段 30 规划完成记录

已根据用户与 Claude 对阶段 30 的讨论，完成根目录三份 Planning with Files 文件改写：

- `task_plan.md`：阶段 30 Phase 0-8 任务计划。
- `findings.md`：开源 RAG 评测框架调研吸收、Claude 评审意见和关键决策。
- `progress.md`：阶段 30 启动状态、阶段 29 基线和后续开发边界。

## 阶段 30 目标概述

阶段 30 要把阶段 29 的散指标升级为评分体系：

```text
stage29_real_quality_results.csv
stage29_real_quality_summary.csv
stage30_scoring_weights.yaml
stage30_engineering_health.json
-> score_stage30_quality.py
-> stage30_quality_scores.csv
-> stage30_quality_summary.csv
-> stage30_quality_deductions.csv
-> docs/stage30_quality_score_report.md
-> /quality-report
```

## 关键执行边界

- 默认评分是 `deterministic_rule_based`，进入 CI。
- LLM-as-Judge 是手动可选模式，不进 CI。
- 默认评分不得输出伪造的 `faithfulness`、`answer_relevancy` 或 `groundedness`。
- 权重必须配置化，文件建议为 `data/evaluation/stage30_scoring_weights.yaml`。
- 评分脚本不得内部跑 pytest、不得重建 embedding、不得调用真实 API。
- Engineering Health 由独立 JSON 提供，评分器只读取。

## Phase 日志

### Phase 0：启动校准与计划落盘

状态：已完成。

完成内容：
- 已阅读项目入口文档、阶段 29 结果和根目录阶段 30 计划文件。
- 已核对 `phase-29-complete -> b62b1a5 Complete phase 29 real embedding quality eval`。
- 已核对 `main / origin/main -> cd32df6 Merge phase 29 real embedding quality eval`。
- `git merge-base --is-ancestor phase-29-complete main` 通过，阶段 29 已合并到 `main`。
- 已创建并切换到 `codex/phase-30-rag-evaluation-scoring-system`。
- 未移动任何已有阶段 tag；未提交、未打阶段 30 tag、未 push、未创建 PR。

### Phase 1：阶段 30 设计文档与开源评测框架映射

状态：已完成。

完成内容：
- 新增 `docs/stage30_rag_evaluation_scoring_system.md`。
- 说明 LlamaIndex、Ragas、DeepEval、TruLens、Phoenix 的可借鉴点。
- 明确默认规则评分只输出可复现指标，不把 `coverage_ratio` 冒充 `faithfulness`、`answer_relevancy` 或 `groundedness`。
- 明确可选 LLM-as-Judge 只能手动 `--execute`，不进 CI，不覆盖默认评分结论。

### Phase 2：评分 schema 与权重配置

状态：已完成。

完成内容：
- 新增 `data/evaluation/stage30_scoring_weights.yaml`。
- 定义 100 分维度：retrieval 35、rule-based context/answer 25、safety refusal 20、source quality 10、engineering health 10。
- 为每个维度写入 rationale，明确这些权重是初始启发式。
- 定义 A/B/C/D/F 等级边界和 `pass/review_required/blocked` 初始门禁规则。

### Phase 3：Engineering Health Artifact

状态：已完成。

完成内容：
- 新增 `scripts/collect_stage30_engineering_health.py`。
- 生成 `data/evaluation/stage30_engineering_health.json`。
- 当前统计：chunks 12716，embeddings 25432，Jina 12716，deterministic 12716，孤立 embedding 0，重复 provider/model/chunk 组合 0。
- health artifact 标注当前测试和冒烟为阶段 29 最终基线，阶段 30 收尾 Phase 7 需要复跑并刷新。

### Phase 4：默认 deterministic 评分脚本

状态：已完成。

完成内容：
- 新增 `scripts/score_stage30_quality.py`。
- 生成 `data/evaluation/stage30_quality_scores.csv`、`data/evaluation/stage30_quality_summary.csv`、`data/evaluation/stage30_quality_deductions.csv`。
- 初版评分：`overall_score=83.17`、`grade=B`、`release_decision=review_required`。
- 主要扣分：`stage29_wiki_dam_applications` Top-5 未命中，以及 `stage29_wiki_dam_applications` / `stage29_web_rfc_advantages` 的低规则覆盖率。
- 默认评分未输出伪造的 semantic faithfulness、answer relevancy 或 groundedness。

### Phase 5：可选 LLM-as-Judge 设计与手动模式

状态：已完成。

完成内容：
- 新增 `scripts/judge_stage30_semantic_quality.py`。
- 默认 dry-run 生成 `data/evaluation/stage30_llm_judge_results.csv`，不调用真实 API。
- 输出中保留 semantic judge 字段，但 dry-run 不填分数，避免伪造 faithfulness、answer relevancy 或 groundedness。
- 当前 `--execute` 已支持 OpenAI-compatible/DeepSeek provider；只有本地存在 `STAGE30_JUDGE_API_KEY` 时才会调用真实 provider，输出继续脱敏且不进入 CI。

### Phase 6：质量报告与 `/quality-report` 升级

状态：已完成。

完成内容：
- 新增 `scripts/build_stage30_quality_report.py`。
- 新增 `docs/stage30_quality_score_report.md`。
- 更新 `app/frontend/quality_report.html`，展示阶段 30 总分、等级、release decision、维度分、扣分项、推荐动作和人工复核队列。
- 更新 `/quality-report/data.json` 与 `/quality-report/export.csv` 的只读数据源为 `stage30_quality_summary.csv`。

### Phase 7：测试与回归

状态：已完成。

完成内容：
- 新增阶段 30 聚焦测试并更新 `/quality-report` 前端测试。
- 聚焦测试：`21 passed`。
- 全量测试：`571 passed, 1 warning`。
- 接口冒烟：`/health`、`/quality-report`、`/quality-report/data.json`、`/quality-report/export.csv` 均返回 200。
- 浏览器冒烟：summary rows 6、deduction rows 3、recommended actions 2、console errors 0。
- 已刷新 `stage30_engineering_health.json` 和 `stage30_quality_scores.csv` 的 `stage30-final-validation` run。

### Phase 8：普通文档与 Obsidian 收尾

状态：已完成。

完成内容：
- 同步 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 新增 `docs/phase_reviews/phase-30.md`。
- 补 Obsidian 阶段页、阶段汇报汇总、知识点和索引链接。
- 更新根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 当前停在用户人工核验前；未提交、未打 tag、未 push、未创建 PR。

## 下一步

用新的 goal prompt 开启阶段 30 开发线程。开发线程必须从 Phase 0 开始，不跳步；每完成任意 Phase 后更新 `task_plan.md`、`findings.md`、`progress.md`。

## 追加记录：DeepSeek 手动 judge 适配器

- 已将 `scripts/judge_stage30_semantic_quality.py` 从安全骨架升级为 OpenAI-compatible 手动 judge runner。
- 默认 dry-run 仍不调用真实模型，并已重新生成 `data/evaluation/stage30_llm_judge_results.csv`，输出 `real_model_calls=0`。
- `--execute` 只有在本地设置 `STAGE30_JUDGE_API_KEY` 后才会调用 provider；默认 provider/model/base URL 为 `deepseek`、`deepseek-chat`、`https://api.deepseek.com`，也可通过环境变量或 CLI 覆盖。
- 输出继续脱敏，不保存 API key、Bearer token、Authorization header、供应商原始响应、`raw_response` 或受限全文。
- 该手动语义 judge 仍不进入 CI，也不改变阶段 30 默认 `overall_score=83.17`、`grade=B`、`release_decision=review_required`。

## 追加记录：人工复核工作台

- 已新增 `/quality-review` 和 `/quality-review/data.json`。
- 页面聚合 `stage29_real_quality_results.csv`、`stage30_quality_deductions.csv`、`stage30_llm_judge_results.csv`，避免人工直接横向阅读 CSV。
- 浏览器冒烟：15 cases、4 needs_review、3 critical、首条 `stage29_web_aci_318_scope`，console errors 0。
- 搜索 `rfc` 返回 3 条，严重低分筛选返回 3 条。
- 页面不写库、不调用真实模型；点击人工结论按钮会写入 `data/evaluation/stage30_human_review.csv`。浏览器 smoke 后已删除测试写入，正式人工复核从空表开始。
