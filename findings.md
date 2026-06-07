# Findings & Decisions

## Requirements

- 用户要求正式进入阶段 15：真实配置复跑与质量审阅报告。
- 线程标题已修改为 `阶段15-真实配置复跑与质量审阅报告`。
- 目标分支为 `codex/phase-15-real-review-report`。
- 阶段 15 必须从阶段 14 已完成并合并到 `main` 的状态出发。
- 必须确认 `phase-14-complete` 指向阶段 14 最终功能提交 `e5df149`，不移动已有阶段 tag。
- 阶段 15 不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不把 HyDE 接入默认链路或自动回归、不把真实 API 调用变成 CI 或本地全量测试前提。
- 阶段 15 重点是真实配置复跑、`stage14_real` 结果目录、Answer Coverage 复核、质量汇总、只读报告页或导出报告。
- 必须保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 旧 API 不被破坏。
- 开发阶段不写 Obsidian 小 Phase 汇报；阶段收尾统一补齐。

## Current Project Findings

- 当前工作区已切换到 `codex/phase-15-real-review-report`。
- `main` 当前提交为 `b9cb019ea0d7a7ebe366605f81758296f830d782`，提交信息为 `Merge phase 14 real quality calibration`。
- `phase-14-complete` 指向 `e5df149ea89a24db8e105f85e40c13eb812a1751`。
- 阶段 14 功能提交已被 `main` 合并；阶段 15 分支从合并后的 `main` 创建。
- 旧 `task_plan.md`、`findings.md`、`progress.md` 均为阶段 14 工作记忆，需要改写为阶段 15。
- Planning with Files 的 session-catchup 脚本在 `C:\Users\admin\.claude\skills\planning-with-files\scripts\session-catchup.py` 不存在；当前通过直接读取 Git、文档和旧记忆文件恢复上下文。

## Architecture Findings

- `EmbeddingProvider` 是向量模型适配层，当前有 `DeterministicEmbeddingProvider` 和 `OpenAICompatibleEmbeddingProvider`。
- `ChatModelProvider` 是回答模型适配层，当前有 deterministic provider 和 OpenAI-compatible provider。
- `chunk_embeddings` 记录 provider、model_name、dimension、content_hash 和 embedding_json；真实 embedding 切换后必须按 provider/model/dimension 重建索引。
- `VectorSearchService` 按当前 embedding provider 查询匹配索引；如果 provider/model/dimension 不匹配，vector 检索不会误用旧索引。
- `HybridSearchService` 组合 keyword/vector 召回，保留 both-match 信号和可解释合并基础。
- `BrainService` 默认 workflow 是 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer`。
- 阶段 13 已在 Brain hybrid 路径中接入 Decompose；阶段 14 已把 Decompose provenance 和 rerank explanation 结构化为审阅 CSV。
- `evaluate_evidence_confidence()` 位于 Brain 生成前，阶段 15 不能绕过低证据拒答。
- 只读报告如果接入前端，应位于 evaluation/reporting 层，不改变核心 RAG API schema。

## Existing Code Findings

- `scripts/evaluate_stage14_embedding_comparison.py` 已能汇总 deterministic baseline 与 real_config 结果文件状态。
- `data/evaluation/stage14_embedding_comparison.csv` 已记录 deterministic baseline 和 real_config missing_results/skipped 状态。
- `scripts/evaluate_stage14_answer_coverage.py` 已生成 `data/evaluation/stage14_answer_coverage_review.csv`。
- `data/evaluation/stage14_answer_coverage_review.csv` 当前 20 行，包含 default_hybrid deterministic 审阅行和 real_config skipped 行。
- `scripts/evaluate_stage14_decompose_provenance.py` 已生成 `data/evaluation/stage14_decompose_provenance_review.csv`，把 Decompose 证据解释拆成证据级字段。
- `scripts/evaluate_vector_search.py`、`scripts/evaluate_hybrid_search.py`、`scripts/evaluate_user_questions.py`、`scripts/evaluate_decompose.py`、`scripts/evaluate_chat.py`、`scripts/evaluate_agent.py`、`scripts/evaluate_brain_workflow.py` 是阶段 15 真实配置复跑的核心入口。
- `docs/stage12_quality_review.md` 已定义 Faithfulness、Answer Coverage、Citation Quality 的人工审阅 rubric。

## Evaluation Findings

- 阶段 14 显式 deterministic baseline：vector 13/15、hybrid 15/15、user_questions 25/30、decompose 10/10、chat 6/6、agent 5/5、brain_workflow 18/18。
- `data/evaluation/stage14_real/` 当前缺少阶段 14 真实结果 CSV，因此 real_config 记录为 `missing_results` 或 `skipped`。
- `stage14_answer_coverage_review.csv` 当前风险统计为 `low=1`、`medium=9`、`skipped=10`。
- deterministic answer 多数只能标为 Answer Coverage `review`，不能证明真实语言覆盖度。
- 阶段 14 provenance review 输出 50 行证据级记录，能支撑只读报告中的证据解释。

## Data Source Findings

- 阶段 15 不新增外部文献来源，不新增爬虫链路，不保存受限全文。
- 阶段 15 新增的设计文档、真实配置复跑结果、复核表、质量汇总表和报告文件都是工程/评测产物，不是资料来源。
- 真实 API key 只允许存在本地 `.env`，不能写入文档、CSV、测试或 Obsidian。
- 真实模型输出如果进入 CSV，必须是脱敏后的答案摘要、指标、状态和错误摘要，不能保存供应商原始敏感响应。
- 报告页只读展示质量表和结论，不应暴露本地文件路径中的敏感信息或受限全文。

## Technical Decisions

| Decision | Reason |
|---|---|
| 阶段 15 先写设计文档 | 真实复跑、人工复核和报告入口需要先固定边界 |
| 保留 deterministic baseline | 保障本地回归稳定，避免网络和限流影响 CI |
| 真实配置缺失时写 skipped/error | 满足可复现，不伪造真实模型结果 |
| `stage14_real` 目录保存脱敏结果 | 与阶段 14 comparison 脚本衔接，并隔离真实配置产物 |
| Answer Coverage 复核表独立于 stage14 原表 | 保留阶段 14 原始校准表，同时记录阶段 15 的人工/真实复核结论 |
| 报告入口只读 | 阶段 15 是质量审阅，不改变核心业务链路 |
| HyDE 不进默认链路 | 避免假想答案污染引用和自动回归 |

## Phase Findings

### Phase 0

- 线程标题已修改为阶段 15。
- 已阅读 Planning with Files 技能说明。
- 已确认 `main` 是阶段 14 合并后的状态。
- 已确认 `phase-14-complete -> e5df149`，不移动既有 tag。
- 已创建并切换阶段 15 分支。
- 三份 Planning with Files 文件已校准为阶段 15。
- 起点全量测试通过：`.venv\Scripts\python.exe -m pytest -q` -> `275 passed`。

### Phase 1

- Phase 1 目标是把阶段 15 的真实配置复跑、Answer Coverage 复核、质量汇总和只读报告边界固化成可测试设计。
- 新增 `docs/stage15_real_review_report.md`。
- 文档明确 `data/evaluation/stage14_real/` 是真实配置脱敏结果目录，真实 API 不可用时必须写 skipped/error。
- 文档定义 `data/evaluation/stage15_answer_coverage_review.csv` 和 `data/evaluation/stage15_quality_summary.csv` 两个阶段 15 核心产物。
- 文档明确只读报告不触发真实 API 调用，不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`。
- 新增 `tests/test_stage15_real_review_report.py`，覆盖核心产物、质量 rubric、skip 规则、报告只读边界和 API 兼容。
- Phase 1 测试结果：`3 passed`。

### Phase 2

- Phase 2 目标是把真实配置状态从阶段 14 的 `missing_results/skipped` 推进为可审计的 completed/error/skipped 状态。
- 新增 `scripts/evaluate_stage15_real_config.py`。
- 新增 `tests/test_evaluate_stage15_real_config.py`。
- 新增 `data/evaluation/stage14_real/real_config_status.csv`。
- 真实复跑已写出：
  - `data/evaluation/stage14_real/vector_results.csv`：15/15。
  - `data/evaluation/stage14_real/hybrid_results.csv`：15/15。
  - `data/evaluation/stage14_real/user_question_results.csv`：27/30。
  - `data/evaluation/stage14_real/chat_results.csv`：6/6。
  - `data/evaluation/stage14_real/agent_results.csv`：5/5。
  - `data/evaluation/stage14_real/brain_workflow_results.csv`：18/18。
- `decompose` 真实复跑因真实 embedding 请求出现 `SSL: UNEXPECTED_EOF_WHILE_READING`，已在 status 和 comparison 中记录为 `error`，没有伪造成功结果。
- `scripts/evaluate_stage15_real_config.py` 支持增量写入 status，避免长时间真实复跑被外层超时打断时丢失已完成 suite 的证据。
- `stage14_embedding_comparison.csv` 已同步 real_config completed/error 状态：real vector/hybrid/chat/agent/brain workflow 全通过，user_questions 27/30，decompose error。
- Phase 2 测试结果：`12 passed`。

### Phase 3

- Phase 3 目标是对阶段 14 的 `medium/review` 样例做真实结果辅助复核。
- 新增 `scripts/evaluate_stage15_answer_coverage_review.py`。
- 新增 `tests/test_evaluate_stage15_answer_coverage_review.py`。
- 新增 `data/evaluation/stage15_answer_coverage_review.csv`。
- 复核表读取 `stage14_answer_coverage_review.csv` 的 default_hybrid medium/review 行，并用 `stage14_real/user_question_results.csv` 的真实 default_hybrid 回答补充判断。
- 输出 9 行复核结果：`high=1`、`medium=8`。
- 高风险项为 `user_mixed_itz_strength`，真实 default_hybrid 结果出现 `The read operation timed out`，因此 Faithfulness/Answer Coverage 标为 fail，Citation Quality 标为 review。
- 其余 8 行真实回答来源命中和引用有效，但 rule-based term check 仍认为 Answer Coverage 需要人工复核，因此保留 `medium` 风险。
- Phase 3 测试结果：`7 passed`。

### Phase 4

- Phase 4 目标是把阶段 14/15 的质量表变成可读、可审计、可展示的质量结论。
- 新增 `scripts/build_stage15_quality_report.py`。
- 新增 `tests/test_build_stage15_quality_report.py`。
- 新增 `data/evaluation/stage15_quality_summary.csv`、`docs/stage15_quality_report.md`、`app/frontend/quality_report.html`。
- `stage15_quality_summary.csv` 汇总 14 行：real_config、answer_coverage、provenance 和 overall quality gate。
- 当前质量闸口为 `review_required/high`，原因是真实 `decompose` 复跑 error、Answer Coverage 有 1 条 high 风险，以及 overall 继承最高风险。
- `app/api/frontend.py` 新增只读 `/quality-report` 路由，直接返回静态报告文件，不触发真实 API 调用。
- 只读报告使用已有 FastAPI 静态前端边界，没有重构核心工作台，也没有改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`。
- Phase 4 测试结果：报告脚本测试 `2 passed`，报告入口测试 `1 passed`。

### Phase 5

- Phase 5 目标是确认阶段 15 的报告和复核产物没有破坏既有 RAG 主链路。
- deterministic vector 仍为 13/15，失败项为 `mesoscopic_modeling` 和 `construction_management`，keyword baseline 仍为 15/15。
- deterministic hybrid 仍为 15/15，`rescued_vector=2`，`regressed_keyword=0`。
- deterministic user_questions 仍为 25/30，`refusal_matched=30/30`，说明拒答边界稳定。
- deterministic decompose 仍为 10/10，说明真实 decompose error 来自外部真实 embedding 请求，不是本地规则式 Decompose 代码退化。
- deterministic chat 仍为 6/6，Agent 仍为 5/5，Brain workflow 仍为 18/18。
- 阶段 15 Answer Coverage 复核脚本可重复生成 9 行结果：`high=1`、`medium=8`。
- 阶段 15 质量报告脚本可重复生成 14 行汇总：`high=4`、`low=7`、`medium=3`。
- 聚焦回归测试覆盖阶段 15 新脚本、前端、search/vector/hybrid/decompose/chat/brain/agent/sources/documents，结果为 `112 passed`。
- Phase 5 结论：阶段 15 的新增报告能力处在 evaluation/reporting 层，没有破坏核心 RAG API、Brain workflow 或 Agent 只读工具链路。

### Phase 6

- Phase 6 目标是完成普通文档、Obsidian、本地安全检查、最终测试和版本标记。
- `README.md` 已更新阶段 15 当前状态、产物列表、真实配置结果、只读报告入口和下一阶段建议。
- `docs/progress.md` 已新增阶段 15 完成记录，包含关键证据、遗留问题、下一阶段任务和面试表达。
- `docs/architecture.md` 已补充阶段 15 evaluation/reporting 数据流，明确 `/quality-report` 只读边界。
- `docs/data_sources.md` 已说明阶段 15 只新增评测/报告产物，不新增文献来源、不保存受限全文或 API key。
- `AGENT.MD` 已更新阶段 15 完成状态、`phase-15-complete` tag 规则、阶段 15 结果和阶段 16 建议。
- Obsidian 已新增阶段 15 阶段页、Phase 汇报索引、Phase 0-6 汇报和知识点 `真实配置复跑`、`只读质量报告与质量闸口`。
- Obsidian 结构检查确认 7 篇 Phase 汇报均包含 10 个固定小节。
- `obsidian-vault/` 仍被 `.gitignore` 忽略，不进入 Git 提交。
- 安全扫描确认本地 `.env` 中加载到的 2 个密钥值未出现在评测、文档、前端、Obsidian 或阶段记忆文件中，常见 secret/token 正则命中 0。
- 最终全量测试结果：`300 passed`。

## Term Explanations

| Term | Explanation |
|---|---|
| 真实配置复跑 | 使用本地 `.env` 中真实 embedding/chat provider 配置显式复跑评测，并输出脱敏结果 |
| `stage14_real` | `data/evaluation/stage14_real/`，保存真实配置复跑结果或 skipped/error 状态的目录 |
| provider/model/dimension | 向量索引的身份三元组，用来避免不同模型的 embedding 混用 |
| Answer Coverage | 回答是否覆盖 `expected_answer_points` 中的关键技术点 |
| Faithfulness | 回答是否严格来自检索证据，没有资料外断言 |
| Citation Quality | 引用是否能追溯并支撑回答中的关键说法 |
| Graceful skip | 外部真实模型不可用时，把结果记录为 skipped 或 error，而不是伪造成功或让本地测试失败 |
| 只读报告 | 展示质量表和结论的报告入口，不触发写入、不改变核心 RAG API |
| Quality Gate | 阶段质量闸口；在本项目里用 `stage15_quality_summary.csv` 的 overall 行记录当前是否可以放行或仍需审阅 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| Planning catchup 脚本不存在 | `session-catchup script not found` | 直接读取 Git、文档和旧 planning 文件恢复上下文，并记录在 Phase 0 |
| real_config 缺少阶段 14 真实结果文件 | `stage14_embedding_comparison.csv` 中 real_config 为 `missing_results` | 阶段 15 要显式复跑或写出 skipped/error 状态 |
| deterministic answer 不能证明覆盖度 | `stage14_answer_coverage_review.csv` 中默认链路多数为 answer_coverage=`review` | 阶段 15 要建立复核表和质量汇总 |
| 真实复跑外层命令超时 | 首次 `evaluate_stage15_real_config.py --run-real` 被外层 904s timeout 打断 | 补充增量 status 写入；等待残留真实复跑自然收尾后读取状态 |
| Decompose 真实复跑 SSL 中断 | `evaluate_decompose.py` 调用真实 embedding 时出现 `SSL: UNEXPECTED_EOF_WHILE_READING` | status 和 comparison 记录为 `error`，作为质量汇总风险项 |

## Resources

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage14_real_quality_calibration.md`
- `docs/stage12_quality_review.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `app/services/retrieval/embedding.py`
- `app/services/retrieval/vector_search.py`
- `app/services/retrieval/hybrid_search.py`
- `app/services/retrieval/decompose.py`
- `app/services/brain/service.py`
- `scripts/evaluate_stage14_embedding_comparison.py`
- `scripts/evaluate_stage14_answer_coverage.py`
- `scripts/evaluate_stage14_decompose_provenance.py`
- `scripts/evaluate_vector_search.py`
- `scripts/evaluate_hybrid_search.py`
- `scripts/evaluate_user_questions.py`
- `scripts/evaluate_decompose.py`
- `scripts/evaluate_chat.py`
- `scripts/evaluate_agent.py`
- `scripts/evaluate_brain_workflow.py`
- `data/evaluation/user_questions.csv`
- `data/evaluation/stage14_answer_coverage_review.csv`
- `data/evaluation/stage14_decompose_provenance_review.csv`
