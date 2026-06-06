# Progress Log

## Session: 2026-06-06

### Phase 0: 阶段启动与规划校准

- Status: complete
- 解决的问题：从阶段 10 完成并合并后的 `main` 起步，把当前线程、分支、tag 和规划文件切换到阶段 11。
- 在 RAG 链路中的位置：阶段启动前置工作，确保开发起点干净、可追溯。
- 为什么现在做：阶段 11 必须基于阶段 10 的真实 RAG 质量校准成果继续推进。
- 完成工作：
  - 将线程标题修改为 `阶段11-真实用户问题评测集与跨语言质量提升`。
  - 阅读 Planning with Files 技能说明。
  - 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/evaluation_plan.md`、`docs/agent_design.md`、`docs/brain_workflow_design.md`、`docs/model_provider_evaluation.md`。
  - 阅读旧 `task_plan.md`、`findings.md`、`progress.md`。
  - 确认当前 `main` 最新提交为 `c0bf8d6 merge phase 10 rag quality calibration`。
  - 确认 `phase-10-complete -> 1454919`，不移动已有阶段 tag。
  - 创建并切换到 `codex/phase-11-user-evaluation-query-expansion`。
  - 用 Planning with Files 重写阶段 11 的 `task_plan.md`、`findings.md`、`progress.md`。
  - 运行阶段 11 起点全量测试。
- 验证结果：
  - 当前分支已切换到阶段 11 分支。
  - 阶段 10 tag 已确认。
  - 起点全量测试：`.venv\Scripts\python.exe -m pytest -q` -> `216 passed`。

### Phase 1: 真实用户问题评测集设计与落地

- Status: complete
- 解决的问题：现有 chat 评测只有 6 条，适合回归但不足以代表真实用户问法。
- 在 RAG 链路中的位置：用户问题集位于评测入口，驱动后续 Brain workflow、检索、拒答和审阅指标。
- 为什么现在做：阶段 10 已把低证据拒答和 topic anchor 稳定下来，下一步应扩大真实问法覆盖面。
- 完成工作：
  - 新增 `data/evaluation/user_questions.csv`，包含 10 条真实用户风格问题。
  - 覆盖中文口语、英文、中英混合、工程中文和 unsupported。
  - 每条问题记录语言类型、期望来源命中、期望拒答、期望回答要点和 notes。
  - 新增 `tests/test_user_questions.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_user_questions.py -q` -> `3 passed`。

### Phase 2: 用户问题评测脚本与指标输出

- Status: complete
- 解决的问题：用户问题集如果只能人工查看，就不能进入稳定回归。
- 在 RAG 链路中的位置：评测脚本位于 Brain workflow 之后，检查检索证据、引用、拒答和结果质量。
- 为什么现在做：问题集已落地，下一步要把它变成可重复执行的质量门槛。
- 完成工作：
  - 新增 `scripts/evaluate_user_questions.py`。
  - 新增 `tests/test_evaluate_user_questions.py`。
  - 评测脚本比较 `default_hybrid`、`keyword_baseline`、`vector_only`。
  - 结果 CSV 记录语言类型、失败原因、拒答匹配、来源命中、引用有效性和期望回答要点。
  - 修正 `expected_source_hit=no` 时的空期望判断。
  - 生成 `data/evaluation/user_question_results.csv`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_evaluate_user_questions.py tests\test_user_questions.py -q` -> `6 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_user_questions.py --chat-provider deterministic --embedding-provider deterministic --out data\evaluation\user_question_results.csv` -> `15/30 passed`。

### Phase 3: 跨语言 Query Expansion 与主题词增强

- Status: complete
- 解决的问题：用户问题 baseline 暴露出中英术语 gap，尤其是 freeze-thaw、creep、porosity、emission、rock shear key 等真实工程词。
- 在 RAG 链路中的位置：query expansion 位于检索入口，影响 keyword search，也通过 topic anchor 影响 vector 候选排序。
- 为什么现在做：评测脚本已经能稳定暴露失败项，现在可以针对失败项做可解释的词表增强。
- 完成工作：
  - 扩展 `app/services/retrieval/keyword_search.py` 的 `SYNONYM_RULES`。
  - 在 `app/services/brain/workflow.py` 中让 evidence confidence 支持扩展后的中英文证据词。
  - 新增 Brain evidence confidence 跨语言测试。
  - 新增 keyword search 阶段 11 术语测试。
  - 复跑用户问题评测与标准回归评测。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_brain_workflow.py tests\test_brain_service.py tests\test_answer_service.py tests\test_chat_api.py tests\test_agent_service.py tests\test_keyword_search.py tests\test_vector_search.py tests\test_evaluate_user_questions.py -q` -> `48 passed`。
  - 用户问题评测：`25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
  - `scripts\evaluate_vector_search.py --provider deterministic --skip-index-build --out data\evaluation\vector_results.csv` -> `13/15 passed`。
  - `scripts\evaluate_hybrid_search.py --provider deterministic --vector-results data\evaluation\vector_results.csv --out data\evaluation\hybrid_results.csv` -> `15/15 passed`。
  - `scripts\evaluate_chat.py --chat-provider deterministic --embedding-provider deterministic --out data\evaluation\chat_results.csv` -> `6/6 passed`。
  - `scripts\evaluate_brain_workflow.py --chat-provider deterministic --embedding-provider deterministic --out data\evaluation\brain_workflow_results.csv` -> `18/18 passed`。

### Phase 4: 人工审阅抽样与 LLM-as-judge 离线设计

- Status: complete
- 解决的问题：自动脚本能判断来源和拒答，但无法充分判断回答是否覆盖所有技术点。
- 在 RAG 链路中的位置：人工审阅位于自动评测之后，用于检查 Faithfulness、Answer Coverage 和 Citation Quality。
- 为什么现在做：用户问题评测已经跑通并提升，下一步要给真实模型或人工审阅留下结构化质量表。
- 完成工作：
  - 新增 `docs/stage11_user_evaluation_plan.md`。
  - 新增 `data/evaluation/user_question_review_samples.csv`。
  - 审阅表记录 expected answer points、faithfulness、answer coverage、citation quality、reviewer notes 和 judge prompt。
  - 新增 `tests/test_stage11_user_evaluation_plan.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage11_user_evaluation_plan.py tests\test_evaluate_user_questions.py tests\test_user_questions.py -q` -> `10 passed`。

### Phase 5: 回归验证与阶段 11 质量结论

- Status: complete
- 解决的问题：阶段 11 的评测集、脚本、query expansion 和审阅设计已经完成，需要确认不破坏既有检索、问答、Agent 与 API 链路。
- 在 RAG 链路中的位置：回归验证覆盖 keyword/vector/hybrid/chat/agent/Brain workflow 和新增用户问题评测。
- 为什么现在做：只有在阶段 11 质量结果稳定后，才能进入普通文档、Obsidian、提交和 tag 收尾。
- 完成工作：
  - 复跑 keyword、vector、hybrid、chat、agent、Brain workflow deterministic 评测。
  - 复跑阶段 11 用户问题评测。
  - 运行 model config 对比脚本，确认 deterministic baseline 与 real_config 缺失结果边界。
  - 复跑 API 回归测试。
  - 运行全量测试。
- 验证结果：
  - keyword evaluation -> `15/15 passed`。
  - vector evaluation -> `13/15 passed`。
  - hybrid evaluation -> `15/15 passed`，`rescued_vector=2`，`regressed_keyword=0`。
  - chat evaluation -> `6/6 passed`。
  - agent evaluation -> `5/5 passed`。
  - Brain workflow evaluation -> `18/18 passed`。
  - 用户问题评测 -> `25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
  - model config evaluation -> deterministic baseline 全部可读；real_config 因缺少本地真实结果文件为 `missing_results`。
  - API 回归：`.venv\Scripts\python.exe -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py -q` -> `16 passed`。
  - 全量测试：`.venv\Scripts\python.exe -m pytest -q` -> `230 passed`。

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag

- Status: complete
- 解决的问题：把阶段 11 的实现、指标、限制和下一阶段建议同步到普通文档与 Obsidian，并创建最终提交和 `phase-11-complete` tag。
- 在 RAG 链路中的位置：阶段知识沉淀和可追溯发布点，保证后续阶段能从清晰状态继续。
- 为什么现在做：功能与回归验证已完成，需要收尾文档、知识库、最终验证和 Git 标记。
- 完成工作：
  - 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD`。
  - 新增 `docs/stage11_user_evaluation_plan.md`。
  - 补齐 Obsidian 阶段 11 阶段页、Phase 汇报索引、Phase 0-6 汇报、首页、阶段索引、阶段汇报索引、分类页和知识点。
  - 确认 7 篇 Phase 汇报均包含 10 个固定小节。
  - 确认 `obsidian-vault/` 仍被 Git 忽略。
  - 复跑最终全量测试。
  - 准备阶段最终功能提交和 `phase-11-complete` tag。
- 验证结果：
  - Obsidian Phase 汇报小节检查：Phase 0-6 均为 10 个小节。
  - `git status --short --ignored obsidian-vault` -> `!! obsidian-vault/`，确认 Obsidian 不进入提交。
  - 最终全量测试：`.venv\Scripts\python.exe -m pytest -q` -> `230 passed`。

## Current Evidence

| Evidence | Result | Status |
|---|---|---|
| Thread title | `阶段11-真实用户问题评测集与跨语言质量提升` | pass |
| Current branch | `codex/phase-11-user-evaluation-query-expansion` | pass |
| Main merge | `c0bf8d6 merge phase 10 rag quality calibration` | pass |
| Phase 10 tag | `phase-10-complete -> 1454919` | pass |
| Planning files | Rewritten for stage 11 | pass |
| Baseline tests | 216 passed | pass |

## Test Results

| Test | Expected | Actual | Status |
|---|---|---|---|
| Phase 0 baseline tests | Full suite passes | 216 passed | pass |
| Phase 1 user question schema | CSV schema and coverage pass | 3 passed | pass |
| Phase 2 user question evaluator tests | Parser/evaluator/result schema pass | 6 passed | pass |
| Phase 2 user question baseline | Deterministic user questions evaluated | 15/30 | pass |
| Phase 3 focused tests | Retrieval/Brain/user evaluator pass | 48 passed | pass |
| Phase 3 user question eval | Cross-language enhancement improves results | 25/30 | pass |
| Phase 3 vector eval | Existing vector baseline stable | 13/15 | pass |
| Phase 3 hybrid eval | Existing hybrid baseline stable | 15/15 | pass |
| Phase 3 chat eval | Existing chat baseline stable | 6/6 | pass |
| Phase 3 Brain eval | Existing Brain baseline stable | 18/18 | pass |
| Phase 4 review plan tests | Review doc and sample schema pass | 10 passed | pass |
| Phase 5 keyword eval | Existing keyword baseline stable | 15/15 | pass |
| Phase 5 vector eval | Existing vector baseline stable | 13/15 | pass |
| Phase 5 hybrid eval | Hybrid rescues vector without regression | 15/15 | pass |
| Phase 5 chat eval | Existing chat baseline stable | 6/6 | pass |
| Phase 5 agent eval | Existing agent baseline stable | 5/5 | pass |
| Phase 5 Brain eval | Existing Brain workflow stable | 18/18 | pass |
| Phase 5 user questions | Stage 11 user question eval stable | 25/30 | pass |
| Phase 5 API regression | Public API tests pass | 16 passed | pass |
| Phase 5 full suite | Full suite passes | 230 passed | pass |
| Phase 6 Obsidian reports | Each Phase report has 10 sections | Phase 0-6 all 10 | pass |
| Phase 6 final full suite | Full suite passes after docs | 230 passed | pass |

## Error Log

| Error | Attempt | Resolution |
|---|---|---|
| `expected_source_hit=no` 时空期望被误判为来源命中 | 初次用户问题评测发现 unsupported 边界不清 | 已修正 `evaluate_user_questions.py`，只有存在期望词时才计算实际来源命中 |

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | Phase 6 of stage 11: docs, Obsidian, final commit and tag |
| Where am I going? | Toward docs, Obsidian, final full tests, commit and `phase-11-complete` |
| What's the goal? | Complete stage 11: real user question evaluation set and cross-language quality improvement |
| What have I learned? | Expanded evidence terms are needed because source text can be English while user questions are Chinese |
| What have I done? | Renamed thread, confirmed tags, created branch, planned, tested baseline, added user questions/evaluator, improved query expansion, added review design |
