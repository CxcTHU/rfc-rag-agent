# Progress Log

## Session: 2026-06-06

### Phase 0: 阶段 8 启动与规划校准
- **Status:** complete
- **Started:** 2026-06-06
- Phase 目标：
  - 从阶段 7 已完成并合并到 `main` 的稳定状态出发。
  - 建立阶段 8 Brain 中控层与 RAG Workflow 配置化开发的正确分支、文档和工作记忆。
  - 将 Planning with Files 三份文件重写为阶段 8 工作记忆。
- Actions taken:
  - 使用 `get_goal` 确认当前线程 goal 已激活，目标为阶段 8 完整完成。
  - 使用 Planning with Files 技能并阅读其规则。
  - 使用 Codex 线程工具将当前线程标题修改为 `阶段8-Brain中控层与Workflow配置化`。
  - 检查 Git 工作区，当前为 `main` 且无未提交改动。
  - 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/agent_design.md`。
  - 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认它们记录阶段 7 工作记忆。
  - 运行 Planning with Files session catchup 检查，未发现需要恢复的额外输出。
  - 确认 `main` 最新提交为 `1ab9d5b merge phase 7 agent tools`。
  - 确认 `phase-7-complete` 指向 `3a1ad943abe24b2ce9a10e1ee5b2c09225760474`，提交信息为 `feat: complete phase 7 agent tools`。
  - 确认目标分支 `codex/phase-8-brain-workflow` 此前不存在。
  - 从 `main` 创建并切换到 `codex/phase-8-brain-workflow`。
  - 阅读现有 `CitationAnswerService`、Agent tools、Agent service、chat schema、chat evaluation 脚本。
  - 阅读 Quivr 的 Brain、RetrievalConfig、WorkflowConfig 和 basic RAG workflow 示例，确认阶段 8 借鉴方向。
  - 将 `task_plan.md`、`findings.md`、`progress.md` 重写为阶段 8 工作记忆。
  - 运行阶段 8 起点全量测试，结果为 163 passed。
  - 将 Phase 0 标记为 complete，下一步进入 Phase 1：Brain Workflow 设计文档。
- Files created/modified:
  - `task_plan.md` rewritten for Stage 8
  - `findings.md` rewritten for Stage 8
  - `progress.md` rewritten for Stage 8

### Phase 1: Brain Workflow 设计文档
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 先用文档固定 Brain 中控层、配置模型、workflow steps、与 Quivr 的取舍关系。
  - 明确本阶段不引入复杂 LangGraph workflow、不照搬 Quivr、不联网爬取新资料、不自动执行 source reindex。
  - 为后续配置模型和 BrainService 实现提供可测试边界。
- Actions taken:
  - 新增 `docs/brain_workflow_design.md`，说明 Brain 在 RAG 链路中的位置、模块边界和复用路线。
  - 新增 `tests/test_brain_workflow_design.py`，断言设计文档覆盖 Brain、RetrievalConfig、WorkflowConfig、五个 workflow steps、chat/agent 复用和配置化评测。
  - 通过 4 次小的边界措辞修正，让文档用语与测试要求完全对齐。
- Files created/modified:
  - `docs/brain_workflow_design.md`
  - `tests/test_brain_workflow_design.py`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 2: Brain 配置模型
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 为 Brain workflow 提供一个可校验的配置入口。
  - 用配置统一描述检索模式、召回数量、历史限制、可选重排、prompt 方案和模型提供方。
  - 先完成配置模型，后续 BrainService 只消费配置，不在各处散落参数判断。
- Actions taken:
  - 新增 `app/services/brain/` 包。
  - 新增 `RetrievalConfig`、`WorkflowConfig`、`WorkflowStepConfig`。
  - 固定默认 workflow 顺序为 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer`。
  - 增加配置模型测试，覆盖默认值、非法参数、非法 workflow step、必需 step 和 chat 参数构造。
- Files created/modified:
  - `app/services/brain/__init__.py`
  - `app/services/brain/config.py`
  - `tests/test_brain_config.py`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 3: 轻量 RAG Workflow 与 BrainService
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 把原本隐式串在回答服务里的检索、重排占位、prompt、模型调用、citation 和日志记录显式放入 Brain workflow。
  - 保留现有检索和生成 service，不改变 keyword/vector/hybrid 的实现。
  - 让每次回答都带有 workflow step 记录，供后续配置化评测使用。
- Actions taken:
  - 新增 `app/services/brain/workflow.py`，定义 Brain 结果、检索结果、step 记录、拒答文本、引用提取和检索结果过滤。
  - 新增 `app/services/brain/service.py`，实现 `BrainService.answer()` 和 `BrainService.retrieve()`。
  - 实现 `filter_history`、`rewrite_query`、`retrieve`、`optional_rerank`、`generate_answer` 五个步骤。
  - 保持 `auto` 检索的 vector 优先、keyword fallback 行为。
  - 增加 Brain workflow 和 BrainService 测试。
- Files created/modified:
  - `app/services/brain/__init__.py`
  - `app/services/brain/workflow.py`
  - `app/services/brain/service.py`
  - `tests/test_brain_workflow.py`
  - `tests/test_brain_service.py`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 4: Chat 与 Agent 复用 Brain Workflow
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 让 `/chat` 和 Agent 的 `answer_with_citations` 共享 Phase 3 新增的 Brain workflow。
  - 保持 `CitationAnswerService`、`CitationAnswerResult`、API 响应和 Agent 工具输出结构不变。
  - 用回归测试确认迁移没有破坏问答、引用、拒答、日志和 Agent 编排。
- Actions taken:
  - 将 `app/services/generation/answer_service.py` 改造为兼容门面。
  - `CitationAnswerService.answer()` 现在通过 `RetrievalConfig.from_chat_request()` 构造配置，并调用 `BrainService.answer()`。
  - `CitationAnswerService.retrieve()` 现在委托 `BrainService.retrieve()`，保留旧入口。
  - `AgentToolbox.answer_with_citations()` 继续调用 `CitationAnswerService`，因此自然复用 Brain workflow，无需新增 Agent 工具。
  - 运行回答服务、聊天日志、聊天 API、Agent 工具、Agent service、Agent API 回归测试。
- Files created/modified:
  - `app/services/generation/answer_service.py`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 5: 配置化评测
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 让同一批 chat 评测问题可以用多套 Brain 配置重复运行。
  - 至少比较 `default_hybrid`、`keyword_baseline`、`vector_only`。
  - 输出可复查 CSV，记录配置名、实际检索模式、workflow steps、引用有效性、来源命中和拒答匹配。
- Actions taken:
  - 新增 `scripts/evaluate_brain_workflow.py`。
  - 新增 `tests/test_evaluate_brain_workflow.py`。
  - 运行配置化评测脚本，生成 `data/evaluation/brain_workflow_results.csv`。
  - 记录配置对比结果：`keyword_baseline` 6/6 passed，`default_hybrid` 4/6 passed，`vector_only` 2/6 passed。
- Files created/modified:
  - `scripts/evaluate_brain_workflow.py`
  - `tests/test_evaluate_brain_workflow.py`
  - `data/evaluation/brain_workflow_results.csv`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 6: 回归验证与前端/API 边界检查
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 确认 Brain 中控层没有破坏现有 search、vector、hybrid、chat、agent、source 和 frontend 能力。
  - 复跑阶段评测，确认新增配置化评测和既有评测都能稳定输出。
  - 保持阶段 8 前端边界：不新增复杂配置面板，不做大规模前端重构。
- Actions taken:
  - 运行全量测试，结果为 189 passed。
  - 复跑 keyword、vector、hybrid、chat、agent、source 和 Brain workflow 评测脚本。
  - 确认本阶段没有新增前端配置面板；前端静态测试包含在全量测试中通过。
- Files created/modified:
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 7: 阶段收尾文档、Obsidian、提交与 tag
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 将阶段 8 的代码、评测、架构和边界同步到普通文档。
  - 统一补齐 Obsidian 本地知识库的小 Phase 汇报和阶段页。
  - 为最终提交和 `phase-8-complete` tag 做准备。
- Actions taken:
  - 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
  - 新增 Obsidian 阶段 8 阶段页、Phase 汇报索引、Phase 0-7 小 Phase 汇报和知识点。
  - 检查 Obsidian 阶段 8 小 Phase 汇报数量和固定 10 项模板。
  - 将 `task_plan.md`、`findings.md`、`progress.md` 更新到阶段 8 收尾完成状态。
- Files created/modified:
  - `README.md`
  - `docs/progress.md`
  - `docs/architecture.md`
  - `docs/data_sources.md`
  - `AGENT.MD`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
  - `obsidian-vault/阶段/阶段 8 - Brain 中控层与 RAG Workflow 配置化.md`
  - `obsidian-vault/阶段汇报/阶段 8 - Brain 中控层与 RAG Workflow 配置化/*.md`
  - `obsidian-vault/知识点/Brain 中控层.md`
  - `obsidian-vault/知识点/RetrievalConfig 与 WorkflowConfig.md`
  - `obsidian-vault/知识点/RAG Workflow 配置化评测.md`

## Current Evidence

| Item | Evidence | Status |
|------|----------|--------|
| Goal | `get_goal` returned active stage 8 objective | pass |
| Thread title | `阶段8-Brain中控层与Workflow配置化` | pass |
| Starting branch | `main` before switch | pass |
| Clean worktree before switch | `git status --short --branch` showed no changes | pass |
| Phase 7 merge | `1ab9d5b merge phase 7 agent tools` on `main` | pass |
| Phase 7 tag | `phase-7-complete -> 3a1ad943abe24b2ce9a10e1ee5b2c09225760474` | pass |
| Phase 8 branch | `codex/phase-8-brain-workflow` created | pass |
| Planning with Files | `task_plan.md`, `findings.md`, `progress.md` now describe Stage 8 | pass |
| Phase 1 design | `docs/brain_workflow_design.md` covers Brain/config/workflow/Quivr tradeoffs | pass |
| Phase 2 config | `app/services/brain/config.py` defines RetrievalConfig and WorkflowConfig | pass |
| Phase 3 Brain | `app/services/brain/service.py` runs configurable workflow steps | pass |
| Phase 4 reuse | `CitationAnswerService.answer()` delegates to BrainService | pass |
| Phase 5 evaluation | `data/evaluation/brain_workflow_results.csv` compares three Brain configs | pass |
| Phase 6 regression | full tests and evaluation scripts passed or produced expected baseline output | pass |
| Phase 7 docs | README/docs/AGENT and Obsidian local knowledge base updated | pass |

## Test Results

| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| goal check | `get_goal` | active stage 8 goal | active | pass |
| thread rename | Codex thread title | `阶段8-Brain中控层与Workflow配置化` | renamed | pass |
| clean worktree check | `git status --short --branch` | no changes before branch switch | no changes | pass |
| phase 7 tag check | `git show phase-7-complete` | points to final phase 7 commit | `3a1ad943abe24b2ce9a10e1ee5b2c09225760474` | pass |
| phase 8 branch check | `git switch -c codex/phase-8-brain-workflow` | new phase 8 branch | switched successfully | pass |
| planning calibration | inspect rewritten files | reflect Stage 8 goal, phases, decisions and progress | files written | pass |
| phase 8 startup full tests | `.venv\Scripts\python.exe -m pytest -q` | existing suite remains green | 163 passed | pass |
| phase 1 design doc test | `.venv\Scripts\python.exe -m pytest tests\test_brain_workflow_design.py -q` | design doc assertions pass | 2 passed | pass |
| phase 2 config test | `.venv\Scripts\python.exe -m pytest tests\test_brain_config.py -q` | config model assertions pass | 13 passed | pass |
| phase 3 brain tests | `.venv\Scripts\python.exe -m pytest tests\test_brain_workflow.py tests\test_brain_service.py -q` | Brain workflow assertions pass | 8 passed | pass |
| phase 4 chat/agent regression | `.venv\Scripts\python.exe -m pytest tests\test_answer_service.py tests\test_chat_logging.py tests\test_chat_api.py tests\test_agent_tools.py -q` | answer/chat/agent behavior remains stable | 24 passed | pass |
| phase 4 agent API regression | `.venv\Scripts\python.exe -m pytest tests\test_agent_api.py tests\test_agent_service.py -q` | agent API behavior remains stable | 11 passed | pass |
| phase 5 evaluation test | `.venv\Scripts\python.exe -m pytest tests\test_evaluate_brain_workflow.py -q` | config evaluation assertions pass | 3 passed | pass |
| phase 5 evaluation run | `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py --queries data\evaluation\chat_queries.csv --out data\evaluation\brain_workflow_results.csv --chat-provider deterministic` | brain workflow results CSV generated | 18 runs; keyword 6/6, hybrid 4/6, vector 2/6 | pass |
| phase 6 full tests | `.venv\Scripts\python.exe -m pytest -q` | all tests pass | 189 passed | pass |
| phase 6 keyword evaluation | `.venv\Scripts\python.exe scripts\evaluate_keyword_search.py` | keyword evaluation remains green | 15/15 passed | pass |
| phase 6 vector evaluation | `.venv\Scripts\python.exe scripts\evaluate_vector_search.py` | vector baseline remains reproducible | 11/15 passed | pass |
| phase 6 hybrid evaluation | `.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py` | hybrid evaluation remains green | 15/15 passed | pass |
| phase 6 chat evaluation | `.venv\Scripts\python.exe scripts\evaluate_chat.py` | chat evaluation remains green | 6/6 passed | pass |
| phase 6 agent evaluation | `.venv\Scripts\python.exe scripts\evaluate_agent.py` | agent evaluation remains green | 5/5 passed | pass |
| phase 6 source evaluation | `.venv\Scripts\python.exe scripts\evaluate_sources.py` | source metrics produced | total_sources=125 | pass |
| phase 6 brain workflow evaluation | `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py --queries data\evaluation\chat_queries.csv --out data\evaluation\brain_workflow_results.csv --chat-provider deterministic` | brain workflow comparison remains stable | 18 runs; keyword 6/6, hybrid 4/6, vector 2/6 | pass |
| phase 7 Obsidian report check | inspect `obsidian-vault\阶段汇报\阶段 8 - Brain 中控层与 RAG Workflow 配置化` | Phase 0-7 reports each include 10 fixed sections | 8 reports; each count=10 | pass |

## Error Log

| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-06-06 | `tests/test_brain_workflow_design.py` 首次运行 1 failed，文档缺少测试要求的完整短语 `不引入复杂 LangGraph workflow` | 1 | 修正文档表述后复跑设计文档测试 |
| 2026-06-06 | `tests/test_brain_workflow_design.py` 第二次运行仍 1 failed，文档边界写成 `直接写 SQL` 而非 `不直接写 SQL` | 2 | 统一文档边界措辞后复跑设计文档测试 |
| 2026-06-06 | `tests/test_brain_workflow_design.py` 第三次运行仍 1 failed，文档边界写成 `自动执行 source reindex` 而非 `不自动执行 source reindex` | 3 | 统一 source reindex 边界措辞后复跑设计文档测试 |
| 2026-06-06 | `tests/test_brain_workflow_design.py` 第四次运行仍 1 failed，文档边界写成 `联网爬取新资料` 而非 `不联网爬取新资料` | 4 | 统一外部资料采集边界措辞后复跑设计文档测试 |

## 5-Question Reboot Check

| Question | Answer |
|----------|--------|
| Where am I? | Phase 0 complete，当前分支 `codex/phase-8-brain-workflow` |
| Where am I going? | 阶段 8：Brain 中控层与 RAG Workflow 配置化 |
| What's the goal? | 把阶段 7 已稳定的 RAG/Agent 能力收拢进 Brain 中控层，用 RetrievalConfig/WorkflowConfig 显式描述 RAG 流程，并让 chat 与 agent 复用同一 workflow |
| What have I learned? | Quivr 的核心启发是 Brain + RetrievalConfig + WorkflowConfig；本项目当前 CitationAnswerService 隐式串联检索、prompt、模型、引用和日志，阶段 8 应把这些步骤显式化；Brain 不替代既有 service，而是组合它们 |
| What have I done? | 确认 goal、改线程名、确认阶段 7 tag 与 main 合并、创建阶段 8 分支、阅读入口文档/阶段记忆/现有代码/Quivr 参考，重写 Planning with Files 三份文件，并完成起点全量测试 163 passed |
