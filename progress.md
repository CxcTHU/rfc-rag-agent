# Progress Log

## Session: 2026-06-07

### Phase 0: 阶段启动与规划校准

- Status: complete
- 解决的问题：从阶段 12 完成并合并后的 `main` 起步，把当前线程、分支、tag 和规划文件切换到阶段 13。
- 在 RAG 链路中的位置：阶段启动前置工作，确保 Decompose 与证据合并基于最新 Brain、评测和质量审阅边界推进。
- 为什么现在做：阶段 12 已明确 default_hybrid 稳定但复杂问题 Answer Coverage 仍需要更完整证据，阶段 13 要把这个结论落实为规则式拆解、子 query 检索和可解释证据合并。
- 已完成工作：
  - 将线程标题修改为 `阶段13-Decompose与证据合并`。
  - 确认 goal 已处于 active 状态。
  - 阅读 Planning with Files 技能说明。
  - 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage12_quality_review.md`、`docs/stage13_decompose_plan.md`。
  - 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其为阶段 12 工作记忆。
  - 确认当前 `main` 最新提交为 `5c7bb58 merge phase 12 quality review context calibration`。
  - 确认 `phase-12-complete -> d7b5bff`，不移动已有阶段 tag。
  - 创建并切换到 `codex/phase-13-decompose-evidence-merge`。
-  - 用 Planning with Files 重写阶段 13 的 `task_plan.md`、`findings.md`、`progress.md`。
-  - 运行阶段 13 起点全量测试。
- 验证结果：
-  - 当前分支已切换到阶段 13 分支。
-  - 阶段 12 tag 已确认。
-  - 起点全量测试：`.venv\Scripts\python.exe -m pytest -q` -> `244 passed`。

## Current Evidence

| Evidence | Result | Status |
|---|---|---|
| Thread title | `阶段13-Decompose与证据合并` | pass |
| Starting branch | `main` clean, tracking `origin/main` | pass |
| Main merge | `5c7bb58 merge phase 12 quality review context calibration` | pass |
| Phase 12 tag | `phase-12-complete -> d7b5bff` | pass |
| Stage 13 branch | `codex/phase-13-decompose-evidence-merge` created | pass |
| Planning files | Rewritten for stage 13 | pass |
| Baseline tests | `.venv\Scripts\python.exe -m pytest -q` -> `244 passed` | pass |

## Test Results

| Test | Expected | Actual | Status |
|---|---|---|---|
| Phase 0 baseline tests | Full suite passes | 244 passed | pass |
| Phase 1 design tests | Stage 13 design and quality review docs pass | 7 passed | pass |
| Phase 2 decompose service tests | Decompose service and retrieval regressions pass | 16 passed | pass |
| Phase 3 Brain/API tests | Brain, chat, agent and API compatibility pass | 45 passed, then focused 17 passed, API 18 passed | pass |
| Phase 3 user questions | Stage 13 Decompose does not regress default path | 29/30 | pass |
| Phase 3 chat eval | Chat regression remains stable | 6/6 | pass |
| Phase 3 agent eval | Agent regression remains stable | 5/5 | pass |
| Phase 3 Brain eval | Brain workflow remains stable after fix | 18/18 | pass |
| Phase 4 decompose script tests | Stage 13 evaluation script tests pass | 5 passed | pass |
| Phase 4 decompose evaluation | Priority Decompose evaluation passes | 6/6 | pass |
| Phase 5 focused regression tests | Stage 13, Brain, eval and frontend focused tests pass | 31 passed | pass |
| Phase 5 deterministic hybrid eval | Hybrid remains stable | 15/15 | pass |
| Phase 5 deterministic vector baseline | Vector baseline remains honest | 13/15 | pass |
| Phase 5 all user Decompose eval | Stage 13 Decompose all-user run passes | 10/10 | pass |
| Phase 6 Obsidian section check | Phase 0-6 reports each contain 10 fixed sections | 7/7 files passed | pass |
| Phase 6 Obsidian git ignore check | Obsidian remains local-only | `!! obsidian-vault/` | pass |
| Phase 6 final full tests | Full suite passes | 257 passed | pass |

## Error Log

| Error | Attempt | Resolution |
|---|---|---|
| Brain `default_hybrid` 一度退化 | 初次接入后 `scripts\evaluate_brain_workflow.py` 显示 default_hybrid 5/6，rfc_concept 被拒答 | 改为先用 `decompose_query()` 判断是否拆解，只有复杂问题才执行 Decompose 服务；复跑 Brain workflow 为 18/18 |
| Stage 13 Decompose 评测 unsupported 初次失败 | `scripts\evaluate_decompose.py` 初次为 5/6，unsupported 已拒答但 actual_source_hit 被算成 yes | 新增 `actual_source_hit_for_expected_question()`，expected_source_hit=no 时按是否返回 sources 判断；复跑为 6/6 |
| 并行回归触发真实 embedding 限流 | `scripts\evaluate_hybrid_search.py` 默认读取 `.env`，真实 provider 返回 HTTP 429 concurrency limit | 显式用 `--provider deterministic` 复跑 hybrid/vector，自动回归不依赖真实 API |

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | Phase 0 of stage 13: startup, planning, baseline verification |
| Where am I going? | Toward rule-based Decompose, sub-query retrieval, evidence merge, deduplication, explainable rerank, evaluation, docs, Obsidian, commit and `phase-13-complete` |
| What's the goal? | Complete stage 13: Decompose and evidence merge |
| What have I learned? | Stage 12 proved default hybrid source hits are stable, but complex questions need fuller evidence and vector-only failures remain honest baseline inputs |
| What have I done? | Renamed thread, confirmed main/tag, created branch, rewrote planning files for stage 13 |

### Phase 1: Decompose 设计固化与测试输入校准

- Status: complete
- 解决的问题：阶段 12 只给出 Decompose 预研计划，还没有明确实现规则、数据结构、评测指标和不拆解边界。
- 在 RAG 链路中的位置：Decompose 位于 Brain 检索增强层，在生成回答前为复杂问题准备更完整证据。
- 为什么现在做：阶段 13 后续要实现子 query 检索和证据合并，如果不先固化规则，容易误拆 unsupported 问题或破坏 API 兼容。
- 完成工作：
  - 更新 `docs/stage13_decompose_plan.md`，从预研计划升级为阶段 13 设计文档。
  - 明确规则式拆解触发条件、最多 3 个子 query、unsupported 保护和 HyDE 边界。
  - 明确内部数据结构建议：`DecomposedQuery`、`SubQueryRetrievalResult`、`MergedEvidence`。
  - 明确可解释 rerank 分数和解释字段。
  - 明确阶段 13 评测指标和优先验证问题。
  - 更新 `tests/test_stage13_decompose_plan.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage13_decompose_plan.py tests\test_stage12_quality_review.py -q` -> `7 passed`。

### Phase 2: 规则式 Decompose 与证据合并服务

- Status: complete
- 解决的问题：阶段 13 需要一个可复用的服务来完成问题拆解、子 query 检索、候选合并、去重和可解释排序。
- 在 RAG 链路中的位置：位于 Brain retrieve step 之前或内部，负责把复杂问题转成更完整的证据池，再交给生成前证据置信度和引用式回答。
- 为什么现在做：只有先把服务层单独跑稳，后续接入 Brain 时才不会同时承担拆解规则、检索合并和 API 回归三类风险。
- 完成工作：
  - 新增 `app/services/retrieval/decompose.py`。
  - 实现 `decompose_query()`，支持明显多主题拆解并限制最多 3 个 sub query。
  - 实现 `DecomposeRetrievalService.retrieve()`，支持按 keyword/vector/hybrid 检索每个 sub query。
  - 实现 `merge_sub_query_results()`，按 `chunk_id` 去重并保留 sub query provenance。
  - 实现可解释 rerank，综合原始 score、主题词命中、source_type、both-match 和 sub query 覆盖度。
  - 新增 `tests/test_decompose_retrieval.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_decompose_retrieval.py tests\test_hybrid_search.py tests\test_vector_search.py -q` -> `16 passed`。

### Phase 3: Brain 集成与 API 兼容回归

- Status: complete
- 解决的问题：Decompose 服务只有接入 Brain 后，才能真正服务 `/chat` 和 Agent 引用式回答。
- 在 RAG 链路中的位置：Brain retrieve step 的 hybrid 路径中，复杂问题使用 Decompose 合并证据；单主题问题继续使用原 hybrid 检索。
- 为什么现在做：阶段 8 已经把 chat/agent 收敛到 Brain，阶段 13 必须在这个共享入口接入，而不是只停留在独立服务。
- 完成工作：
  - 在 `BrainService._retrieve_with_hybrid()` 接入 Decompose。
  - 为多主题 hybrid 问题补充 Brain 测试。
  - 初次回归发现 default_hybrid 一度退化为 5/6。
  - 修复接入条件：先用 `decompose_query()` 判断，只有复杂问题才执行子 query 检索。
  - 复跑用户问题、chat、agent、Brain workflow 和 API 回归。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_brain_service.py tests\test_answer_service.py tests\test_chat_api.py tests\test_agent_service.py tests\test_agent_api.py tests\test_search_api.py tests\test_vector_search_api.py -q` -> `45 passed`。
  - `.venv\Scripts\python.exe -m pytest tests\test_brain_service.py tests\test_decompose_retrieval.py -q` -> `17 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py` -> `18/18 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_user_questions.py` -> `29/30 passed`，`refusal_matched=30/30`，`source_hit_matched=29/30`。
  - `.venv\Scripts\python.exe scripts\evaluate_chat.py` -> `6/6 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_agent.py` -> `5/5 passed`。
  - `.venv\Scripts\python.exe -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py -q` -> `18 passed`。

### Phase 4: 阶段 13 评测脚本与质量校准

- Status: complete
- 解决的问题：阶段 13 需要一个专属评测产物来证明 Decompose 不是黑盒效果，而是有子 query、去重、provenance 和 rerank 解释。
- 在 RAG 链路中的位置：评测位于检索增强之后、阶段收尾之前，用来判断复杂问题来源命中、拒答边界和默认链路是否稳定。
- 为什么现在做：服务和 Brain 已经接入，如果没有阶段 13 专属评测，无法证明复杂问题证据覆盖确实改善。
- 完成工作：
  - 新增 `scripts/evaluate_decompose.py`。
  - 默认选取阶段 13 的 5 个优先问题和 `user_unsupported_random`。
  - 输出 `data/evaluation/stage13_decompose_results.csv`。
  - 新增 `tests/test_evaluate_decompose.py`。
  - 修正 unsupported source_hit 口径，保证拒答问题按“无 sources”判断。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_evaluate_decompose.py -q` -> `5 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_decompose.py` -> `6/6 passed`，`decomposed=3`，`refused=1`，`source_hit_matched=6/6`。

### Phase 5: 回归验证与前端最小可见性判断

- Status: complete
- 解决的问题：确认阶段 13 的内部检索增强不会破坏既有 search/vector/hybrid/chat/agent/front-end 入口。
- 在 RAG 链路中的位置：大范围回归位于核心实现和文档收尾之间，用来证明新检索路径可安全进入阶段收尾。
- 为什么现在做：Decompose 已接入 Brain，如果没有复跑旧评测和 API 测试，无法确认默认链路不退化。
- 完成工作：
  - 复跑阶段 13、Brain、评测和前端聚焦测试。
  - 复跑 deterministic hybrid 和 vector baseline。
  - 复跑阶段 13 Decompose 全用户问题评测。
  - 判断前端无需改动，因为 API schema 不变，Decompose 细节通过评测 CSV 与内部解释字段保留。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_decompose_retrieval.py tests\test_evaluate_decompose.py tests\test_brain_service.py tests\test_evaluate_user_questions.py tests\test_evaluate_brain_workflow.py tests\test_frontend_app.py -q` -> `31 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py --provider deterministic` -> `15/15 passed`，`regressed_keyword=0`。
  - `.venv\Scripts\python.exe scripts\evaluate_vector_search.py --provider deterministic --skip-index-build` -> `13/15 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_decompose.py --include-all` -> `10/10 passed`，`decomposed=3`，`refused=1`，`source_hit_matched=10/10`。
  - 并行回归中真实 embedding provider 返回 HTTP 429，已记录为外部限流并使用 deterministic 复跑。

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag

- Status: complete
- 解决的问题：把阶段 13 的代码、评测、文档、Obsidian 本地知识库和 Git 阶段锚点统一收口，避免实现完成但项目记忆仍停留在阶段 12。
- 在 RAG 链路中的位置：这是 Decompose 检索增强进入下一阶段前的验收层，负责把检索链路、评测链路和知识库说明对齐。
- 为什么现在做：阶段 13 的服务、Brain 集成和评测已经通过回归，必须在创建阶段 tag 前完成普通文档、Obsidian 和最终全量测试。
- 完成工作：
  - 更新 `README.md`，补充阶段 13 能力、评测结果、使用边界和下一阶段建议。
  - 更新 `docs/progress.md`，记录阶段 13 完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
  - 更新 `docs/architecture.md`，补充规则式 Decompose、子 query 检索、证据合并、`MergedEvidence` 和可解释 rerank 数据流。
  - 更新 `docs/data_sources.md`，说明阶段 13 只新增工程评测产物，不新增文献来源、不保存受限全文或 API key。
  - 更新 `AGENT.MD`，把后续起点校准到阶段 13 完成后的下一步。
  - 补齐 Obsidian 阶段 13 阶段页、阶段汇报目录、Phase 0-6 小 Phase 汇报、索引、分类页和知识点页。
  - 校验每篇 Obsidian 小 Phase 汇报均包含 10 个固定小节。
  - 确认 `obsidian-vault/` 仍被 Git 忽略，不纳入提交。
  - 复跑最终全量测试。
- 验证结果：
  - Obsidian Phase 0-6 汇报 10 小节检查：`7/7` 通过。
  - `git status --short --ignored obsidian-vault` -> `!! obsidian-vault/`，确认 Obsidian 仍是本地忽略目录。
  - `.venv\Scripts\python.exe -m pytest -q` -> `257 passed`。
