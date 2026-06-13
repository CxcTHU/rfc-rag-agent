# 阶段 30 任务计划：RAG 质量评分体系与诚实决策门禁

## 目标

在阶段 29「真实 Embedding 重建 + 端到端质量闭环」已完成、提交、打 `phase-29-complete` tag 并合并到 `main` 的基础上，完成阶段 30：参考 LlamaIndex、Ragas、DeepEval、TruLens、Phoenix 等主流 RAG 评测框架，构建本项目自己的轻量级质量评分与决策门禁系统。阶段 30 必须输出可解释、不夸大的总分、等级、扣分项、人工复核队列和下一步建议；语义级指标只能作为可选 LLM-as-Judge 模式，绝不用字符串匹配冒充。

建议分支：`codex/phase-30-rag-evaluation-scoring-system`

## 背景

阶段 29 已产出真实 Jina 评测指标：

```text
precision_at_1=0.600
precision_at_3=0.867
precision_at_5=0.933
avg_coverage_ratio=0.664
refusal_accuracy=1.000
source_type_distribution=institutional_access_pdf:17;metadata_record:6;open_access_pdf:5;standard_document:25;web_page:28;wikipedia:9
quality_gate=review_required/medium
```

这些指标可以说明质量现状，但仍是散指标。阶段 30 要把它们升级为可复用的评分体系：

```text
stage29 metrics + engineering health
-> scoring weights
-> dimension scores
-> overall_score / grade / release_decision
-> deductions / recommended_actions
-> quality report / export / trend history
```

## 硬约束

- 阶段 30 开发完成前后均不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR；等待用户人工核验和明确确认。
- 不移动任何已有阶段 tag，尤其是 `phase-29-complete`。
- 从阶段 29 完成并合并后的远端 `main` 出发；先确认 `phase-29-complete` 指向阶段 29 最终功能提交并已合并到 `main`。
- 不引入 LlamaIndex、Ragas、DeepEval、TruLens、Phoenix 等重依赖，只借鉴指标思想。
- 不引入 `torch` / `sentence-transformers`。
- 默认评分链路必须 deterministic、离线、可单测，不依赖真实 Jina/MIMO API。
- 可选 LLM-as-Judge 只能手动触发，不进 CI，不作为默认评分前提。
- 不把 API key、Bearer token、Authorization header、供应商原始敏感响应、raw_response、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 评分脚本保持纯读取：不内部跑 pytest、不重建 embedding、不主动改数据库、不调用真实 API。
- 保证 `/search`、`/search/vector`、`/search/hybrid`、`/chat`、`/agent/query`、`/agent/query/stream`、`/quality-report` 不被破坏。

## 核心设计原则

1. 诚实命名：默认 CI 模式只叫 `rule_based_coverage`、`retrieval_hit`、`source_quality` 等可复现指标；不得把字符串覆盖率命名为 `faithfulness` 或 `answer_relevancy`。
2. 双模式评分：默认 deterministic scoring 进入 CI；可选 LLM-as-Judge scoring 单独输出 judge 文件，并明确 `judge_provider`、`judge_model`、`manual_run=true`。
3. 权重配置化：新增 `data/evaluation/stage30_scoring_weights.yaml`，权重不硬编码在业务逻辑中。
4. 历史可追踪：`stage30_quality_scores.csv` 设计成可追加趋势表，每次评测一行，支持和上次结果比较。
5. 评分器纯函数化：`scripts/score_stage30_quality.py` 只读取 CSV/YAML/JSON，输出评分 CSV/summary，不负责跑测试和采集健康信号。

## Phase 顺序

### Phase 0：启动校准与计划落盘

**状态：已完成**

**解决的问题**：确认阶段 29 已完成、tag/main 状态正确，创建阶段 30 分支，并校准三份规划文件。

**RAG 链路位置**：阶段启动与版本基线，不改运行链路。

**任务**
- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读 `docs/stage29_quality_report.md`、`docs/stage29_real_embedding_quality_eval.md`、`docs/phase_reviews/phase-29.md`。
- 阅读根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 运行 `git status -sb`、`git log --oneline -5`。
- 核对 `phase-29-complete` 指向阶段 29 最终功能提交，且已并入 `main`。
- 从阶段 29 合并后的 `main` 创建/切换 `codex/phase-30-rag-evaluation-scoring-system`。

**验证方式**
- `git merge-base --is-ancestor phase-29-complete main`
- 当前分支正确，工作区无无关改动。

**完成记录**
- 已读取入口规则、项目 README、进度、架构、数据源、阶段 29 质量报告、阶段 29 设计和阶段 29 验收草稿。
- 已核对 `phase-29-complete -> b62b1a5 Complete phase 29 real embedding quality eval`。
- 已核对 `main -> cd32df6 Merge phase 29 real embedding quality eval`，且 `phase-29-complete` 是 `main` 的祖先。
- 已从 `main` 创建并切换到 `codex/phase-30-rag-evaluation-scoring-system`。
- 未移动任何已有阶段 tag；未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR 操作。

### Phase 1：阶段 30 设计文档与开源评测框架映射

**状态：已完成**

**解决的问题**：把 LlamaIndex/Ragas/DeepEval/TruLens/Phoenix 的可借鉴思想翻译成本项目可落地的轻量方案。

**任务**
- 新增 `docs/stage30_rag_evaluation_scoring_system.md`。
- 写清参考框架：
  - LlamaIndex：RetrieverEvaluator、hit-rate、MRR、faithfulness/relevancy evaluator。
  - Ragas：context precision/recall、faithfulness、answer relevancy。
  - DeepEval：G-Eval、RAG metrics、带理由的评测。
  - TruLens：RAG Triad，context relevance / groundedness / answer relevance。
  - Phoenix：retrieval eval + response eval + observability。
- 写清本项目采纳和不采纳的部分。
- 明确默认规则评分与可选 LLM-as-Judge 的边界。

**完成标准**
- 文档明确说明“不用规则匹配冒充语义评分”。

**完成记录**
- 已新增 `docs/stage30_rag_evaluation_scoring_system.md`。
- 已记录 LlamaIndex、Ragas、DeepEval、TruLens、Phoenix 的参考点、采纳点和不采纳点。
- 已明确默认 `deterministic_rule_based` 只使用可复现规则指标。
- 已明确 `faithfulness`、`answer_relevancy`、`groundedness` 只能出现在可选 `manual_llm_judge` 模式，不进入 CI。

### Phase 2：评分 schema 与权重配置

**状态：已完成**

**解决的问题**：定义可解释总分、子分、等级、发布建议和扣分项的数据结构。

**任务**
- 新增 `data/evaluation/stage30_scoring_weights.yaml`。
- 定义默认维度：
  - `retrieval_quality` 35 分。
  - `rule_based_context_answer_quality` 25 分。
  - `safety_refusal` 20 分。
  - `source_quality` 10 分。
  - `engineering_health` 10 分。
- 在 YAML 中写每个权重的 rationale。
- 定义等级边界：A/B/C/D/F 与 `pass/review_required/blocked`，并明确这些边界是初始启发式，后续可用历史趋势校准。
- 新增/设计输出字段：`overall_score`、`grade`、`release_decision`、`dimension_scores`、`deductions`、`recommended_actions`、`scoring_mode`、`scoring_version`。

**完成标准**
- 权重不硬编码；测试能读取并校验权重总和为 100。

**完成记录**
- 已新增 `data/evaluation/stage30_scoring_weights.yaml`。
- 已配置五个默认维度：`retrieval_quality=35`、`rule_based_context_answer_quality=25`、`safety_refusal=20`、`source_quality=10`、`engineering_health=10`。
- 已写入每个维度的 machine-readable `rationale`。
- 已定义 A/B/C/D/F 等级边界和 `pass/review_required/blocked` 初始决策规则。
- 权重读取与总和校验将在 Phase 4 评分脚本和 Phase 7 测试中覆盖。

### Phase 3：Engineering Health Artifact

**状态：已完成**

**解决的问题**：让评分脚本读取工程健康信号，而不是自己跑 pytest 或扫数据库。

**任务**
- 新增 `scripts/collect_stage30_engineering_health.py`。
- 输出 `data/evaluation/stage30_engineering_health.json`。
- health artifact 至少包含：
  - `full_tests_status`
  - `chunk_count`
  - `embedding_count`
  - `jina_embedding_count`
  - `deterministic_embedding_count`
  - `orphan_embeddings`
  - `duplicate_provider_model_groups`
  - `quality_report_smoke`
  - `generated_at`
- 脚本可读取数据库和已有验证输入，但不得运行 pytest。

**完成标准**
- health JSON 脱敏、可提交、可单测。

**完成记录**
- 已新增 `scripts/collect_stage30_engineering_health.py`。
- 已生成 `data/evaluation/stage30_engineering_health.json`。
- 当前 health artifact 记录：`chunk_count=12716`、`embedding_count=25432`、`jina_embedding_count=12716`、`deterministic_embedding_count=12716`、`orphan_embeddings=0`、`duplicate_provider_model_groups=0`。
- 脚本只读数据库统计和外部传入状态；不运行 pytest、不重建 embedding、不写数据库、不调用真实 API。

### Phase 4：默认 deterministic 评分脚本

**状态：已完成**

**解决的问题**：基于阶段 29 评测结果和 health artifact 生成可解释评分。

**任务**
- 新增 `scripts/score_stage30_quality.py`。
- 输入：
  - `data/evaluation/stage29_real_quality_results.csv`
  - `data/evaluation/stage29_real_quality_summary.csv`
  - `data/evaluation/stage30_scoring_weights.yaml`
  - `data/evaluation/stage30_engineering_health.json`
- 输出：
  - `data/evaluation/stage30_quality_scores.csv`
  - `data/evaluation/stage30_quality_summary.csv`
  - `data/evaluation/stage30_quality_deductions.csv`
- 计算 retrieval / rule_based_context_answer / safety / source / engineering 子分。
- 对 `stage29_wiki_dam_applications`、`stage29_web_rfc_advantages` 等低分项生成扣分原因和 recommended_actions。

**完成标准**
- 评分可复现、无真实 API、测试覆盖关键公式和边界。

**完成记录**
- 已新增 `scripts/score_stage30_quality.py`。
- 已读取阶段 29 results/summary、阶段 30 weights YAML 和 engineering health JSON。
- 已生成：
  - `data/evaluation/stage30_quality_scores.csv`
  - `data/evaluation/stage30_quality_summary.csv`
  - `data/evaluation/stage30_quality_deductions.csv`
- 初版结果：`overall_score=83.17`、`grade=B`、`release_decision=review_required`。
- 扣分项覆盖 `stage29_wiki_dam_applications` Top-5 未命中与两个低 `rule_based coverage_ratio` 样例；未使用或伪造 `faithfulness`、`answer_relevancy`、`groundedness`。

### Phase 5：可选 LLM-as-Judge 设计与手动模式

**状态：已完成**

**解决的问题**：为真正的 faithfulness / answer relevancy 留出诚实入口，但不让它进入 CI。

**任务**
- 新增可选脚本或文档化 CLI：`scripts/judge_stage30_semantic_quality.py`。
- 默认 `--dry-run` 或 `--disabled`，没有显式 `--execute` 不调用真实模型。
- 输出单独文件，如 `data/evaluation/stage30_llm_judge_results.csv`。
- 字段必须包含：`judge_provider`、`judge_model`、`manual_run`、`faithfulness_score`、`answer_relevancy_score`、`groundedness_score`、`judge_reason`。
- 任何真实模型错误必须脱敏。

**完成标准**
- 默认测试不调用真实 API；文档明确该模式不参与 CI 门禁。

**完成记录**
- 已新增 `scripts/judge_stage30_semantic_quality.py`。
- 默认 dry-run 不调用真实模型，已生成 `data/evaluation/stage30_llm_judge_results.csv` 示例输出。
- 输出字段包含 `judge_provider`、`judge_model`、`manual_run`、`faithfulness_score`、`answer_relevancy_score`、`groundedness_score`、`judge_reason`。
- 当前手动模式支持 OpenAI-compatible/DeepSeek provider；只有显式 `--execute` 且本地存在 `STAGE30_JUDGE_API_KEY` 时才会调用真实 provider，输出继续脱敏。

### Phase 6：质量报告与 `/quality-report` 升级

**状态：已完成**

**解决的问题**：把阶段 29 的指标报告升级为评分与决策报告。

**任务**
- 新增 `docs/stage30_quality_score_report.md`。
- 更新或新增 report builder，把总分、等级、子分、扣分项、推荐动作、历史趋势写入 HTML/CSV/JSON。
- 更新 `/quality-report`、`/quality-report/data.json`、`/quality-report/export.csv`。
- 保留只读、安全、可导出能力。

**完成标准**
- 页面清楚展示总分、等级、release decision、dimension scores 和人工复核队列。

**完成记录**
- 已新增 `scripts/build_stage30_quality_report.py`。
- 已新增 `docs/stage30_quality_score_report.md`。
- 已更新 `app/frontend/quality_report.html` 为阶段 30 评分报告。
- 已将 `/quality-report/data.json` 和 `/quality-report/export.csv` 的只读数据源切换为 `data/evaluation/stage30_quality_summary.csv`。
- 页面展示 `overall_score=83.17`、`grade=B`、`release_decision=review_required`、维度分、扣分项、推荐动作和人工复核队列。

### Phase 7：测试与回归

**状态：已完成**

**解决的问题**：确保评分体系不破坏现有 API 和 deterministic 测试。

**任务**
- 为权重读取、health artifact、评分计算、deductions、report builder、frontend API 补测试。
- 运行聚焦测试。
- 运行全量测试。
- 浏览器检查 `/quality-report` 渲染、导出和 console errors。

**完成标准**
- 全量测试通过。
- `/quality-report` 冒烟通过。

**完成记录**
- 已新增阶段 30 聚焦测试：
  - `tests/test_stage30_scoring.py`
  - `tests/test_stage30_engineering_health.py`
  - `tests/test_stage30_semantic_judge.py`
  - `tests/test_build_stage30_quality_report.py`
- 已更新 `tests/test_frontend_app.py` 的阶段 30 `/quality-report` 断言。
- 聚焦测试：`21 passed`。
- 全量测试：`571 passed, 1 warning`。
- 接口冒烟：`/health`、`/quality-report`、`/quality-report/data.json`、`/quality-report/export.csv` 均返回 200。
- 浏览器冒烟：`overall=83.17`、`grade=B`、`release_decision=review_required`、summary rows 6、deduction rows 3、recommended actions 2、console errors 0。
- 已刷新 `stage30_engineering_health.json`、追加 `stage30-final-validation` 评分记录并重建阶段 30 质量报告。

### Phase 8：普通文档与 Obsidian 收尾

**状态：已完成**

**解决的问题**：把阶段 30 的设计、结果、边界、面试表达沉淀到项目入口文档和本地知识库。

**任务**
- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 新增 `docs/phase_reviews/phase-30.md`。
- 补 Obsidian 阶段 30 阶段页、阶段汇报索引和总汇报；开发过程中不写小 Phase 汇报，收尾统一补齐。
- 更新根目录 `task_plan.md`、`findings.md`、`progress.md`。

**完成标准**
- 阶段 30 开发、测试、普通文档和 Obsidian 草稿完成。
- 停在用户人工核验前：不提交、不打 tag、不 push。

**完成记录**
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 已新增 `docs/phase_reviews/phase-30.md`。
- 已补 Obsidian 阶段页、阶段汇报汇总、知识点和索引链接。
- 已更新根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 当前停在人工核验前：未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

## 阶段 30 完成标准

- `docs/stage30_rag_evaluation_scoring_system.md` 已生成。
- `data/evaluation/stage30_scoring_weights.yaml` 已生成，权重合计 100，且有 rationale。
- `data/evaluation/stage30_engineering_health.json` 已生成，评分脚本不内部跑 pytest。
- `scripts/score_stage30_quality.py` 能生成总分、等级、决策、子分、扣分项和 recommended_actions。
- `stage30_quality_scores.csv` 支持历史趋势追加。
- 语义级指标只在可选 LLM-as-Judge 模式出现；默认报告不得把规则覆盖率叫做 faithfulness/answer relevancy。
- `/quality-report` 展示阶段 30 评分报告。
- 全量测试通过。
- 不泄露 API key、Bearer token、供应商原始响应或受限全文。
- 最终停在人工核验前，不提交、不创建 `phase-30-complete` tag、不推送。

## 追加完成记录：DeepSeek 手动 judge 适配器

- `scripts/judge_stage30_semantic_quality.py` 已支持 OpenAI-compatible 手动执行路径，默认 provider/model/base URL 为 `deepseek`、`deepseek-chat`、`https://api.deepseek.com`。
- 默认 dry-run 不联网、不造语义分数；`--execute` 缺少 `STAGE30_JUDGE_API_KEY` 时只输出脱敏错误。
- 新增测试覆盖 dry-run、缺 key 不调用客户端、假客户端执行、judge JSON 解析与敏感字段脱敏。
- 已重新生成 `data/evaluation/stage30_llm_judge_results.csv`，当前默认输出仍为 `real_model_calls=0`。
- 手动 judge 结果不进入 CI，不改变阶段 30 默认评分和发布建议。

## 追加完成记录：人工复核工作台

- 新增 `/quality-review` 人工复核小 UI 和 `/quality-review/data.json` 聚合接口。
- UI 按风险排序展示 query、来源命中、规则覆盖、covered/missing points、DeepSeek judge 分数、judge reason、stage30 deductions 和建议人工结论标签。
- 新增前端测试覆盖页面与 JSON 聚合接口。
- 页面不写数据库、不触发真实 API；人工复核点击会落盘到 `data/evaluation/stage30_human_review.csv`，同一 query 可更新。
