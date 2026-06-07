# Progress Log

## Session: 2026-06-06

### Phase 0: 阶段启动与规划校准

- Status: complete
- 解决的问题：从阶段 11 完成并合并后的 `main` 起步，把当前线程、分支、tag 和规划文件切换到阶段 12。
- 在 RAG 链路中的位置：阶段启动前置工作，确保质量审阅和上下文补全基于最新稳定链路推进。
- 为什么现在做：阶段 11 已完成真实用户问题评测和离线审阅设计，阶段 12 需要把审阅真正落地，并在 Brain `rewrite_query` 中实现最小上下文补全。
- 完成工作：
  - 将线程标题修改为 `阶段12-质量审阅与上下文最小补全`。
  - 确认 goal 已处于 active 状态。
  - 阅读 Planning with Files 技能说明。
  - 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage11_user_evaluation_plan.md`。
  - 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其为阶段 11 工作记忆。
  - 确认当前 `main` 最新提交为 `09926f5 merge phase 11 user evaluation query expansion`。
  - 确认 `phase-11-complete -> fcd174e`，不移动已有阶段 tag。
  - 创建并切换到 `codex/phase-12-quality-review-context-calibration`。
  - 用 Planning with Files 重写阶段 12 的 `task_plan.md`、`findings.md`、`progress.md`。
  - 运行阶段 12 起点全量测试。
- 验证结果：
  - 当前分支已切换到阶段 12 分支。
  - 阶段 11 tag 已确认。
  - 起点全量测试：`.venv\Scripts\python.exe -m pytest -q` -> `230 passed`。

### Phase 1: 审阅样本与质量报告落地

- Status: complete
- 解决的问题：阶段 11 已有审阅样本表，但还没有真正把 Faithfulness、Answer Coverage 和 Citation Quality 用于质量结论。
- 在 RAG 链路中的位置：人工审阅位于自动评测之后，用来判断回答是否忠实、覆盖是否完整、引用是否能支持关键说法。
- 为什么现在做：阶段 11 的 default_hybrid 和 keyword_baseline 已稳定 10/10，但自动脚本仍无法证明答案质量足够可靠。
- 完成工作：
  - 复核 `data/evaluation/user_question_review_samples.csv` 与 `data/evaluation/user_question_results.csv`。
  - 新增 `data/evaluation/stage12_quality_review_results.csv`，记录 6 条抽样的人工/离线审阅结论。
  - 新增 `docs/stage12_quality_review.md`，说明审阅方法、rubric、结果、风险和阶段 13 输入。
  - 新增 `tests/test_stage12_quality_review.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage12_quality_review.py tests\test_stage11_user_evaluation_plan.py -q` -> `8 passed`。

### Phase 2: 最小上下文补全设计与实现

- Status: complete
- 解决的问题：当前 Brain workflow 的 `rewrite_query` 只是原样返回问题，无法处理“它”“这个技术”等依赖上一轮问题的省略问法。
- 在 RAG 链路中的位置：上下文补全位于检索前，让检索 query 更完整，但仍由后续 evidence confidence 和引用链路保护回答。
- 为什么现在做：阶段 8 已预留 `rewrite_query` step，阶段 12 只做最小补全，不扩大为复杂多轮记忆系统。
- 完成工作：
  - 在 `BrainService` 的 `filter_history` 和 `rewrite_query` 之间传递过滤后的最近历史问题。
  - 新增 `rewrite_contextual_question()`，只处理明确代词或省略表达。
  - 保留原始问题作为对外返回问题，补全后的 query 只用于检索和生成上下文。
  - 为 `CitationAnswerService.answer()` 增加可选 `history` 参数。
  - 为 `/chat` 和 `/agent/query` 增加可选 `history` 字段，旧请求保持兼容。
  - 补充 Brain、AnswerService、Chat API、Agent Service 和 Agent API 回归测试。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_brain_config.py tests\test_brain_service.py tests\test_answer_service.py tests\test_chat_api.py tests\test_agent_service.py tests\test_agent_api.py -q` -> `52 passed`。

### Phase 3: Chat/Agent 回归与用户问题复测

- Status: complete
- 解决的问题：阶段 12 修改了 Brain rewrite 和 chat/agent 可选 history，需要确认阶段 11 的检索、问答、Agent、API 和用户问题评测不退化。
- 在 RAG 链路中的位置：回归验证覆盖检索入口、Brain workflow、引用式问答和受控 Agent 工具链。
- 为什么现在做：上下文补全只有在不破坏默认链路时才适合进入阶段收尾。
- 完成工作：
  - 复跑阶段 11 用户问题评测。
  - 复跑 chat、agent、Brain workflow deterministic 评测。
  - 复跑 search/vector/chat/agent/API 和上下文补全相关测试。
- 验证结果：
  - 用户问题评测 -> `25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
  - chat evaluation -> `6/6 passed`。
  - agent evaluation -> `5/5 passed`。
  - Brain workflow evaluation -> `18/18 passed`。
  - API/核心回归：`.venv\Scripts\python.exe -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py tests\test_agent_service.py tests\test_brain_service.py tests\test_answer_service.py tests\test_evaluate_user_questions.py -q` -> `47 passed`。

### Phase 4: 阶段 12 质量结论与后续阶段设计

- Status: complete
- 解决的问题：阶段 12 已完成质量审阅和最小上下文补全，需要把结论转成后续阶段清晰输入。
- 在 RAG 链路中的位置：阶段结论位于质量校准之后，指导后续 Decompose、rerank、真实 embedding 对比和 HyDE 离线实验。
- 为什么现在做：只有把边界写清楚，阶段 13 才不会盲目扩展复杂 workflow 或引入默认 HyDE。
- 完成工作：
  - 新增 `docs/stage13_decompose_plan.md`。
  - 明确阶段 13 推荐数据流：original question -> rule-based decompose -> sub query retrieval -> merge -> deduplicate by chunk_id -> rerank -> Brain answer。
  - 明确 HyDE 只做离线实验建议，不进入默认链路或自动回归。
  - 明确 Context 继续保持最近历史问题的最小补全，不做长期记忆。
  - 新增 `tests/test_stage13_decompose_plan.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage12_quality_review.py tests\test_stage13_decompose_plan.py -q` -> `6 passed`。

### Phase 5: 阶段收尾文档、Obsidian、提交与 tag

- Status: complete
- 解决的问题：把阶段 12 的代码、质量结论、验证结果和下一阶段路线同步到入口文档、本地知识库和 Git 标记。
- 在 RAG 链路中的位置：阶段知识沉淀和可追溯发布点，保证后续阶段能从清晰状态继续。
- 为什么现在做：功能与回归验证已完成，需要收尾文档、知识库、最终验证、提交和 tag。
- 完成工作：
  - 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD`。
  - 新增 `docs/stage12_quality_review.md` 和 `docs/stage13_decompose_plan.md`。
  - 补齐 Obsidian 阶段 12 阶段页、Phase 汇报索引、Phase 0-5 汇报、阶段索引、阶段汇报索引、首页、分类页和知识点。
  - 确认 6 篇 Phase 汇报均包含 10 个固定小节。
  - 确认 `obsidian-vault/` 仍被 Git 忽略。
  - 复跑最终全量测试。
  - 准备阶段最终功能提交和 `phase-12-complete` tag。
- 验证结果：
  - Obsidian Phase 汇报小节检查：Phase 0-5 均为 10 个小节。
  - `git status --short --ignored obsidian-vault` -> `!! obsidian-vault/`，确认 Obsidian 不进入提交。
  - 最终全量测试：`.venv\Scripts\python.exe -m pytest -q` -> `244 passed`。

## Current Evidence

| Evidence | Result | Status |
|---|---|---|
| Thread title | `阶段12-质量审阅与上下文最小补全` | pass |
| Current branch | `codex/phase-12-quality-review-context-calibration` | pass |
| Main merge | `09926f5 merge phase 11 user evaluation query expansion` | pass |
| Phase 11 tag | `phase-11-complete -> fcd174e` | pass |
| Planning files | Rewritten for stage 12 | pass |
| Baseline tests | 230 passed | pass |

## Test Results

| Test | Expected | Actual | Status |
|---|---|---|---|
| Phase 0 baseline tests | Full suite passes | 230 passed | pass |
| Phase 1 quality review tests | Stage 12 report and review schema pass | 8 passed | pass |
| Phase 2 context rewrite tests | Brain/chat/agent context rewrite and compatibility pass | 52 passed | pass |
| Phase 3 user questions | Stage 11 user question regression remains stable | 25/30 | pass |
| Phase 3 chat eval | Chat regression remains stable | 6/6 | pass |
| Phase 3 agent eval | Agent regression remains stable | 5/5 | pass |
| Phase 3 Brain eval | Brain workflow remains stable | 18/18 | pass |
| Phase 3 API/core tests | API compatibility and context tests pass | 47 passed | pass |
| Phase 4 decompose plan tests | Stage 13 plan boundaries pass | 6 passed | pass |
| Phase 5 Obsidian reports | Each Phase report has 10 sections | Phase 0-5 all 10 | pass |
| Phase 5 final full suite | Full suite passes after docs | 244 passed | pass |

## Error Log

| Error | Attempt | Resolution |
|---|---|---|
| None yet | - | - |

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | Phase 0 of stage 12: startup, planning, baseline verification |
| Where am I going? | Toward quality review report, minimal Brain context rewrite, regression validation, docs/Obsidian, commit and `phase-12-complete` |
| What's the goal? | Complete stage 12: quality review and minimal context completion |
| What have I learned? | Stage 11 automatic evaluation is stable but Faithfulness/Answer Coverage need review; Brain `rewrite_query` is the right context补全入口 |
| What have I done? | Renamed thread, confirmed main/tag, created branch, rewrote planning files |
