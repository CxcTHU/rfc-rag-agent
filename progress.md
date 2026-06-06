# Progress Log

## Session: 2026-06-05

### Phase 0: 阶段 6 启动与规划文件校准
- **Status:** complete
- **Started:** 2026-06-05
- Phase 目标：
  - 从阶段 5 已完成并合并到主线的状态出发，建立阶段 6 的正确工作起点。
  - 确认 tag、分支、文档、检索和评测现状。
  - 将 Planning with Files 三份文件重写为阶段 6 工作记忆。
- Actions taken:
  - 使用 Planning with Files 技能并阅读其规则。
  - 使用 Codex 线程工具将当前线程标题修改为 `阶段6-检索优化与评测`。
  - 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
  - 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认它们仍记录阶段 5 工作记忆。
  - 确认当前 `main` HEAD 为 `ae539f5 Revert "docs: add phase 1 phase reports"`。
  - 确认阶段 5 合并提交为 `9456a59 merge phase 5 frontend`。
  - 确认 `phase-5-complete` 指向 `8c885e6cc714cc985933438697a7eb2523b26722`。
  - 确认 `phase-5-complete` 是 `main` 的祖先，阶段 5 已合并。
  - 发现切换前存在一个 Obsidian 阶段汇报索引本地改动，已保留不回退。
  - 创建并切换到 `codex/phase-6-evaluation` 分支。
  - 阅读 `scripts/evaluate_keyword_search.py`、`scripts/evaluate_vector_search.py`、`scripts/evaluate_chat.py`。
  - 阅读 `KeywordSearchService`、`VectorSearchService`、`CitationAnswerService`、`app/api/search.py` 和 `app/schemas/search.py`。
  - 将 `task_plan.md`、`findings.md`、`progress.md` 重写为阶段 6 工作记忆。
  - 将 Phase 0 标记为 complete，下一步进入 Phase 1：评测计划与指标设计。
- Files created/modified:
  - `task_plan.md` rewritten for Stage 6
  - `findings.md` rewritten for Stage 6
  - `progress.md` rewritten for Stage 6

## Current Evidence
| Item | Evidence | Status |
|------|----------|--------|
| Thread title | `阶段6-检索优化与评测` | pass |
| Branch | `codex/phase-6-evaluation` | pass |
| Main status | `main -> ae539f5 Revert "docs: add phase 1 phase reports"` | pass |
| Phase 5 merge | `9456a59 merge phase 5 frontend` is in `main` history | pass |
| Phase 5 tag | `phase-5-complete -> 8c885e6cc714cc985933438697a7eb2523b26722` | pass |
| Phase 5 tag merged | `phase-5-complete` is ancestor of `main` | pass |
| Planning with Files | `task_plan.md`, `findings.md`, `progress.md` now describe Stage 6 | pass |

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| phase 5 tag check | `git show phase-5-complete` | points to phase 5 final functional commit | `8c885e6cc714cc985933438697a7eb2523b26722` | pass |
| phase 5 merge check | `git merge-base --is-ancestor phase-5-complete main` | phase 5 tag is merged into main | yes | pass |
| branch check | `git switch -c codex/phase-6-evaluation` | new phase 6 branch | switched successfully | pass |
| planning calibration | inspect rewritten files | reflect Stage 6 goal, phases, decisions and progress | files written | pass |
| phase 1 evaluation plan tests | `.venv\Scripts\python.exe -m pytest tests\test_evaluation_plan.py -q` | evaluation plan documents metrics and inputs | 2 passed | pass |
| phase 2 keyword baseline | `.venv\Scripts\python.exe scripts\evaluate_keyword_search.py` | keyword baseline reruns | 15/15 passed | pass |
| phase 2 vector baseline | `.venv\Scripts\python.exe scripts\evaluate_vector_search.py` | vector baseline reruns | 11/15 passed, 4 keyword_only_pass | pass |
| phase 2 chat baseline | `.venv\Scripts\python.exe scripts\evaluate_chat.py` | chat baseline reruns | 6/6 passed | pass |
| phase 2 error analysis tests | `.venv\Scripts\python.exe -m pytest tests\test_analyze_retrieval_errors.py tests\test_evaluation_plan.py -q` | error analysis and plan tests pass | 5 passed | pass |
| phase 2 error analysis script | `.venv\Scripts\python.exe scripts\analyze_retrieval_errors.py` | error cases generated | 4 vector cases | pass |
| phase 3 hybrid tests | `.venv\Scripts\python.exe -m pytest tests\test_hybrid_search.py tests\test_vector_search_api.py tests\test_answer_service.py tests\test_chat_api.py -q` | hybrid service/API/chat pass and old paths remain stable | 21 passed | pass |
| phase 4 hybrid evaluation tests | `.venv\Scripts\python.exe -m pytest tests\test_evaluate_hybrid_search.py tests\test_hybrid_search.py tests\test_vector_search_api.py tests\test_answer_service.py tests\test_chat_api.py -q` | hybrid evaluation and related paths pass | 24 passed | pass |
| phase 4 hybrid evaluation | `.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py` | hybrid results generated and compared with baselines | 15/15 passed, rescued_vector=4, regressed_keyword=0 | pass |
| phase 4 refreshed error cases | `.venv\Scripts\python.exe scripts\analyze_retrieval_errors.py` | vector failures updated with hybrid after_status | 4 fixed_by_hybrid | pass |
| phase 4 chat regression | `.venv\Scripts\python.exe scripts\evaluate_chat.py` | chat remains stable | 6/6 passed, citation_failures=0 | pass |
| phase 5 frontend/API tests | `.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_search_api.py -q` | frontend and existing API paths remain stable | 14 passed | pass |
| phase 5 browser smoke check | in-app browser at `http://127.0.0.1:8001/` | hybrid visible in search and chat mode selectors | search: keyword/vector/hybrid; chat: auto/hybrid/vector/keyword | pass |
| phase 5 hybrid route smoke check | `POST http://127.0.0.1:8001/search/hybrid` | current branch service returns hybrid results | 5 results, first title: filling capacity RFC paper | pass |
| phase 6 final keyword evaluation | `.venv\Scripts\python.exe scripts\evaluate_keyword_search.py` | keyword baseline remains stable | 15/15 passed | pass |
| phase 6 final vector evaluation | `.venv\Scripts\python.exe scripts\evaluate_vector_search.py` | vector baseline remains comparable | 11/15 passed, 4 keyword_only_pass | pass |
| phase 6 final hybrid evaluation | `.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py` | hybrid improves vector failures without keyword regression | 15/15 passed, rescued_vector=4, regressed_keyword=0 | pass |
| phase 6 final chat evaluation | `.venv\Scripts\python.exe scripts\evaluate_chat.py` | chat citations/refusal remain stable | 6/6 passed, citation_failures=0 | pass |
| phase 6 final error analysis | `.venv\Scripts\python.exe scripts\analyze_retrieval_errors.py` | vector failures retain optimized status | 4 cases, fixed_by_hybrid | pass |
| phase 6 final full tests | `.venv\Scripts\python.exe -m pytest -q` | entire suite passes | 141 passed | pass |
| phase 6 Obsidian template check | local section-count check | Phase 0-6 reports each keep 10 sections | 7 files, section_count=10 | pass |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-06-05 | 旧 planning 文件仍记录阶段 5 内容 | 1 | 重写为阶段 6 工作记忆 |
| 2026-06-05 | 切换前存在一个 Obsidian 阶段汇报索引本地改动 | 1 | 保留用户已有改动，不回退 |
| 2026-06-05 | 过早写入 Phase 0-2 Obsidian 汇报 | 1 | 按用户最新要求撤回提前写入，阶段 6 全部开发完成后统一补写 |
| 2026-06-05 | 8000 端口已有旧服务进程，未加载新的 `/search/hybrid` 路由 | 1 | 在 8001 端口启动当前分支服务做 smoke check，验证后停止临时服务 |

### User Direction Update: Obsidian 写入时机
- **Status:** recorded
- **Timestamp:** 2026-06-05
- 用户明确要求：所有开发工作做完之后，再填写进 Obsidian。
- 用户随后明确：对话中不需要输出完整 Phase 汇报，完整 10 项汇报只在最终 Obsidian 知识库中补齐。
- 已执行：
  - 删除提前新增的 `obsidian-vault/阶段汇报/阶段 6 - 检索优化与评测/` 下 Phase 0-2 汇报文件。
  - 移除提前加入 `obsidian-vault/阶段汇报索引.md` 的阶段 6 汇报索引链接。
  - 移除提前写入 `obsidian-vault/阶段/阶段 6 - 检索优化与评测.md` 的阶段进展内容。
  - 在 `task_plan.md`、`findings.md`、`progress.md` 记录新规则：开发过程中只维护 planning 文件和简短进度说明，阶段 6 完成后统一补齐 Obsidian 完整 Phase 汇报。

### Phase 1: 评测计划与指标设计
- **Status:** complete
- **Started:** 2026-06-05
- Phase 目标：
  - 为阶段 6 建立统一评测标准，避免后续检索优化只凭主观感觉。
  - 把现有 keyword/vector/chat baseline 数据集映射到清晰指标。
  - 明确哪些指标已经可以自动化，哪些暂时用规则近似或错误案例表承接。
- Actions taken:
  - 复核 `data/evaluation/keyword_queries.csv`、`keyword_results.csv`、`vector_results.csv`、`chat_results.csv` 的字段和历史结果。
  - 新增 `docs/evaluation_plan.md`。
  - 在评测计划中定义 Recall@K、Citation Accuracy、Faithfulness、Answer Coverage、Refusal Quality。
  - 记录当前数据集、评测流程、错误案例分析字段和阶段 6 完成标准。
  - 新增 `tests/test_evaluation_plan.py`，验证评测计划覆盖核心指标、关键输入输出文件、baseline 和 hybrid search。
  - 运行 `tests/test_evaluation_plan.py`，结果为 2 passed。
- Files created/modified:
  - `docs/evaluation_plan.md` created
  - `tests/test_evaluation_plan.py` created
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 2: Baseline 复跑与错误案例分析
- **Status:** complete
- **Started:** 2026-06-05
- Phase 目标：
  - 复跑阶段 6 起点 baseline，确认当前真实指标。
  - 把失败样例落成可追踪错误案例表。
  - 为 Phase 3 的检索优化提供明确目标。
- Actions taken:
  - 运行 `scripts/evaluate_keyword_search.py`，结果 keyword 15/15 passed。
  - 运行 `scripts/evaluate_vector_search.py`，结果 vector 11/15 passed，keyword baseline 15/15，4 个 keyword_only_pass。
  - 运行 `scripts/evaluate_chat.py`，结果 chat 6/6 passed，refused=1，citation_failures=0。
  - 新增 `scripts/analyze_retrieval_errors.py`，自动读取 keyword/vector/chat 结果并输出错误案例。
  - 新增 `tests/test_analyze_retrieval_errors.py`，覆盖 vector keyword gap、chat failure type 和稳定输出 schema。
  - 更新 `docs/evaluation_plan.md`，补充错误分析脚本运行命令。
  - 生成 `data/evaluation/retrieval_error_cases.csv`，记录 4 个 vector 失败案例。
- Files created/modified:
  - `scripts/analyze_retrieval_errors.py` created
  - `tests/test_analyze_retrieval_errors.py` created
  - `data/evaluation/keyword_results.csv` updated
  - `data/evaluation/vector_results.csv` updated
  - `data/evaluation/chat_results.csv` updated
  - `data/evaluation/retrieval_error_cases.csv` created
  - `docs/evaluation_plan.md` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 3: 可解释检索优化方案
- **Status:** complete
- **Started:** 2026-06-05
- Phase 目标：
  - 实现一个保守、可解释的检索优化方案。
  - 用 keyword evidence 补救 deterministic vector 的弱召回。
  - 保持既有 keyword/vector/chat API 不被破坏。
- Actions taken:
  - 新增 `app/services/retrieval/hybrid_search.py`。
  - 新增 `HybridSearchService`，合并 keyword/vector 候选，按 chunk 去重，归一化两路分数并加权排序。
  - 新增 `HybridSearchRequest` 和 `HybridSearchResponse`。
  - 新增 `POST /search/hybrid`。
  - 将 chat `retrieval_mode` 扩展为支持 `hybrid`。
  - `CitationAnswerService` 新增 hybrid 检索路径，但保留 `auto` 旧行为。
  - 新增 `tests/test_hybrid_search.py`。
  - 更新 search API、answer service、chat API 相关测试。
  - 运行 hybrid 相关测试，结果 21 passed。
- Files created/modified:
  - `app/services/retrieval/hybrid_search.py` created
  - `app/schemas/search.py` modified
  - `app/api/search.py` modified
  - `app/schemas/chat.py` modified
  - `app/services/generation/answer_service.py` modified
  - `tests/test_hybrid_search.py` created
  - `tests/test_vector_search_api.py` modified
  - `tests/test_answer_service.py` modified
  - `tests/test_chat_api.py` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 4: 评测脚本升级与指标对比
- **Status:** complete
- **Started:** 2026-06-05
- Phase 目标：
  - 让 hybrid search 能和 keyword/vector baseline 同表对比。
  - 生成优化后检索结果 CSV。
  - 用错误案例表记录优化前后状态。
- Actions taken:
  - 新增 `scripts/evaluate_hybrid_search.py`。
  - 新增 `tests/test_evaluate_hybrid_search.py`。
  - 更新 `docs/evaluation_plan.md`，补充 hybrid 评测命令。
  - 运行 hybrid 评测，生成 `data/evaluation/hybrid_results.csv`。
  - 更新 `scripts/analyze_retrieval_errors.py`，让错误案例读取 hybrid 结果并写入 `after_status`。
  - 刷新 `data/evaluation/retrieval_error_cases.csv`，4 个 vector 失败均为 `fixed_by_hybrid`。
  - 复跑 chat 评测，确认引用和拒答链路不破坏。
- Files created/modified:
  - `scripts/evaluate_hybrid_search.py` created
  - `tests/test_evaluate_hybrid_search.py` created
  - `data/evaluation/hybrid_results.csv` created
  - `scripts/analyze_retrieval_errors.py` modified
  - `tests/test_analyze_retrieval_errors.py` modified
  - `data/evaluation/retrieval_error_cases.csv` modified
  - `data/evaluation/chat_results.csv` updated
  - `docs/evaluation_plan.md` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 5: 前端最小展示与体验核验
- **Status:** complete
- **Started:** 2026-06-05
- Phase 目标：
  - 判断 hybrid search 是否需要最小前端展示。
  - 让工作台能选择新检索模式，同时保持阶段 6 不变成前端重构。
  - 用测试和浏览器 smoke check 验证入口可用。
- Actions taken:
  - 在 `app/frontend/index.html` 搜索模式下拉框中新增 `hybrid`。
  - 在聊天检索模式下拉框中新增 `hybrid`。
  - 在 `app/frontend/static/app.js` 中新增 `/search/hybrid` endpoint，并让 `submitSearch()` 按模式选择 endpoint。
  - 更新 `tests/test_frontend_app.py`，断言页面和 JS 静态资源包含 hybrid 入口。
  - 运行前端入口和相关 API 测试，结果 14 passed。
  - 发现 8000 端口旧服务未加载新 hybrid 路由后，在 8001 端口启动当前分支服务完成验证。
  - 浏览器 smoke check 确认页面标题、搜索表单、聊天表单和 hybrid 下拉选项均存在。
  - 通过当前分支服务验证 `/search/hybrid` 对 `filling capacity rock-filled concrete` 返回 5 条结果。
- Files created/modified:
  - `app/frontend/index.html` modified
  - `app/frontend/static/app.js` modified
  - `tests/test_frontend_app.py` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag
- **Status:** complete
- **Started:** 2026-06-05
- Phase 目标：
  - 将阶段 6 的评测闭环、代码变化和验证结果写入普通项目文档。
  - 在开发、测试和普通文档完成后，统一回填 Obsidian 小 Phase 汇报。
  - 完成最终测试、提交和 `phase-6-complete` tag。
- Actions taken:
  - 更新 `README.md`，记录阶段 6 当前状态、hybrid search、评测结果和阶段 6 面试表达。
  - 更新 `docs/progress.md`，新增阶段 6 完成记录、指标对比、遗留问题、下一阶段和面试表达。
  - 更新 `docs/architecture.md`，补充阶段 6 评测计划、混合检索服务、API/chat 集成、评测脚本和前端最小展示。
  - 更新 `docs/data_sources.md`，说明阶段 6 评测产物不改变数据来源边界。
  - 更新 `AGENT.MD`，将新线程默认起点校准为阶段 7：Agent 化。
  - 复跑 keyword/vector/hybrid/chat 评测和错误案例分析。
  - 复跑全量测试，结果 141 passed。
  - 在开发、测试和普通文档完成后，统一更新 Obsidian 首页、阶段索引、阶段页、阶段汇报索引、分类页、知识点和 Phase 0-6 汇报。
  - 确认 `obsidian-vault/` 仍被 `.gitignore` 排除，不进入 Git 提交。
- Files created/modified:
  - `README.md` modified
  - `docs/progress.md` modified
  - `docs/architecture.md` modified
  - `docs/data_sources.md` modified
  - `AGENT.MD` modified
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified
  - `obsidian-vault/` local-only files updated

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 6 complete，当前分支 `codex/phase-6-evaluation` |
| Where am I going? | 阶段 6：检索优化与评测 |
| What's the goal? | 建立评测计划和指标，复跑 baseline，分析错误案例，实现可解释检索优化并做优化前后对比 |
| What have I learned? | hybrid search 把 vector 从 11/15 提升到 15/15，救回 4 个 keyword_only_pass，且没有 keyword regression；前端只需最小入口即可展示新模式；阶段 6 评测闭环能支撑阶段 7 Agent 化 |
| What have I done? | 完成线程改名、阶段 5 tag/merge 校验、阶段 6 分支创建、三份规划文件校准、新增评测计划、复跑 baseline、新增错误案例分析脚本和 CSV、实现 hybrid search service/API/chat mode、新增 hybrid 评测脚本和结果对比、完成 hybrid 前端最小展示和 smoke check、完成普通文档和 Obsidian 收尾、最终全量测试 141 passed |
