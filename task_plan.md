# Task Plan: 阶段 8 - Brain 中控层与 RAG Workflow 配置化

## Goal
在阶段 7 Agent 化已完成并合并到 `main` 的基础上，进入阶段 8：Brain 中控层与 RAG Workflow 配置化。

本阶段参照 Quivr 的 Brain / RetrievalConfig / WorkflowConfig 架构思想，但不照搬 Quivr 代码，不引入复杂 LangGraph workflow。目标是把现有 search、vector、hybrid、chat、agent、sources 能力收拢到一个轻量 Brain 中控层，用配置描述 RAG 问答流程，让 `/chat` 和 Agent 的 `answer_with_citations` 工具复用同一套 workflow。

阶段 8 不做登录系统、不做部署优化、不做大规模前端重构、不自动接入写入型 Agent 工具。重点是配置化、复用、可测试、可评测、可解释。

## Current Phase
Phase 7 complete。阶段 8 普通文档、Obsidian 本地知识库、最终验证准备、提交与 `phase-8-complete` tag 收尾已完成。

## Phases

### Phase 0: 阶段 8 启动与规划校准
- [x] 将线程标题修改为 `阶段8-Brain中控层与Workflow配置化`。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/agent_design.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其记录阶段 7 工作记忆。
- [x] 确认阶段 7 已完成并合并到 `main`。
- [x] 确认 `phase-7-complete` 指向阶段 7 最终功能提交，且不移动已有 tag。
- [x] 从阶段 7 合并后的 `main` 创建并切换到 `codex/phase-8-brain-workflow`。
- [x] 参照 Quivr 的 Brain、RetrievalConfig、WorkflowConfig，校准阶段 8 规划文件。
- [x] 运行阶段 8 起点基线测试。
- **验证方式:** `git log --oneline --decorate -n 12`、`git show phase-7-complete`、`git branch --show-current`、规划文件内容检查、全量或轻量基线测试。
- **Status:** complete

### Phase 1: Brain Workflow 设计文档
- [x] 新增 `docs/brain_workflow_design.md`。
- [x] 说明 Brain 中控层目标、模块边界、与现有 RAG/Agent 的关系。
- [x] 说明 `RetrievalConfig`、`WorkflowConfig`、workflow steps、配置化评测。
- [x] 明确与 Quivr 的对应关系和取舍：借鉴 Brain/配置/workflow 思路，不照搬 LangGraph 和外部依赖。
- [x] 增加文档断言测试，确保设计文档覆盖 Brain、RetrievalConfig、WorkflowConfig、filter_history、rewrite_query、retrieve、optional_rerank、generate_answer、chat/agent 复用。
- **验证方式:** `tests/test_brain_workflow_design.py`。
- **Status:** complete

### Phase 2: Brain 配置模型
- [x] 新增 `app/services/brain/` 模块。
- [x] 实现配置模型：`RetrievalConfig`、`WorkflowConfig`、`WorkflowStepConfig` 或等价结构。
- [x] 配置至少覆盖 `retrieval_mode`、`top_k`、`min_score`、`max_history`、`rerank_top_n`、`prompt_profile`、`model_provider`。
- [x] 提供默认 workflow：`filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer`。
- [x] 增加配置校验测试，覆盖默认值、非法参数、非法步骤、从 chat 参数构造配置。
- **验证方式:** `tests/test_brain_config.py`。
- **Status:** complete

### Phase 3: 轻量 RAG Workflow 与 BrainService
- [x] 实现 `BrainService` 或等价中控服务。
- [x] 实现 workflow steps：`filter_history`、`rewrite_query`、`retrieve`、`optional_rerank`、`generate_answer`。
- [x] `filter_history` 和 `rewrite_query` 第一版允许 no-op，但必须返回结构化 step 记录。
- [x] `retrieve` 复用现有 keyword/vector/hybrid service。
- [x] `generate_answer` 复用 `build_rag_prompt`、`ChatModelProvider`、citation 提取和 qa_logs 记录。
- [x] 返回兼容 `CitationAnswerResult` 的结果，并额外保留 workflow step 记录供内部评测使用。
- [x] 增加 Brain/workflow 单元测试。
- **验证方式:** `tests/test_brain_service.py`、`tests/test_brain_workflow.py`。
- **Status:** complete

### Phase 4: Chat 与 Agent 复用 Brain Workflow
- [x] 改造 `CitationAnswerService`，让 `answer()` 通过 Brain/workflow 执行，而不是在自身内部直接串联所有步骤。
- [x] 保持 `CitationAnswerResult`、`POST /chat` 响应结构和既有行为不破坏。
- [x] 改造 Agent 的 `answer_with_citations` 工具，让它通过改造后的 `CitationAnswerService` 复用 Brain/workflow。
- [x] 保持 Agent 工具调用记录、引用、拒答和 `reasoning_summary` 不退化。
- [x] 补充 chat/agent 回归测试。
- **验证方式:** `tests/test_answer_service.py`、`tests/test_chat_api.py`、`tests/test_agent_tools.py`、`tests/test_agent_api.py`。
- **Status:** complete

### Phase 5: 配置化评测
- [x] 新增配置化评测输入或配置定义，至少比较 `default_hybrid`、`keyword_baseline`、`vector_only`。
- [x] 新增 `scripts/evaluate_brain_workflow.py` 或扩展现有评测脚本。
- [x] 输出 `data/evaluation/brain_workflow_results.csv`。
- [x] 评测字段记录 config 名称、workflow steps、实际检索模式、来源命中、citation 有效性、拒答匹配。
- [x] 补充评测脚本测试。
- **验证方式:** `tests/test_evaluate_brain_workflow.py`、运行 `scripts/evaluate_brain_workflow.py`。
- **Status:** complete

### Phase 6: 回归验证与前端/API 边界检查
- [x] 确认阶段 8 不破坏 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`/sources`。
- [x] 复跑 keyword、vector、hybrid、chat、agent、source 评测。
- [x] 运行前端静态测试；本阶段不做大规模前端重构。
- [x] 如需要，只在 README/docs 中说明 Brain workflow，不强行新增前端配置面板。
- **验证方式:** 相关 API 测试、评测脚本、`tests/test_frontend_app.py`。
- **Status:** complete

### Phase 7: 阶段收尾文档、Obsidian、提交与 tag
- [x] 更新 `README.md`，说明阶段 8 Brain/workflow 能力、评测方式、启动和测试方式。
- [x] 更新 `docs/progress.md`，记录阶段 8 完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充 Brain 层、配置模型、workflow 数据流和 chat/agent 复用关系。
- [x] 更新 `docs/data_sources.md`，说明阶段 8 不新增外部资料来源，新增评测 CSV 只是评测产物。
- [x] 判断并更新 `AGENT.MD`，将后续默认起点校准到阶段 8 完成后的下一步。
- [x] 统一更新 Obsidian 本地知识库：阶段 8 页、阶段汇报索引、Phase 0 到最终 Phase 汇报、分类页和知识点。
- [x] 复跑全量测试和阶段评测。
- [x] 创建阶段最终功能提交。
- [x] 创建 `phase-8-complete` tag，确保 tag 指向阶段 8 最终功能提交。
- **验证方式:** 全量测试、评测脚本、Obsidian 10 项模板检查、Git tag 检查。
- **Status:** complete

## Final Verification Targets

| Check | Expected |
|-------|----------|
| Design doc | `docs/brain_workflow_design.md` exists and covers Brain/config/workflow/Quivr tradeoffs |
| Brain module | `app/services/brain/` exists with config and service/workflow |
| Config coverage | retrieval_mode/top_k/min_score/max_history/rerank_top_n/prompt_profile/model_provider |
| Workflow steps | filter_history/rewrite_query/retrieve/optional_rerank/generate_answer |
| Chat reuse | `/chat` still works and goes through Brain/workflow via `CitationAnswerService` |
| Agent reuse | `answer_with_citations` still works and uses the shared answer path |
| Evaluation | config comparison output exists for default_hybrid/keyword_baseline/vector_only |
| Regression | keyword/vector/hybrid/chat/agent/source/frontend tests and evaluations remain green |
| Full tests | `python -m pytest -q` passes |
| Tag | `phase-8-complete` points to final phase 8 functionality commit |

## Key Questions

1. 阶段 8 是否引入 LangGraph？
   - 初步答案：不引入。先用轻量 Python service 表达 workflow，保留后续扩展点。
2. 中控层为什么叫 Brain？
   - 初步答案：用户已确认使用 Brain，更简洁，也与 Quivr 的核心抽象对齐。
3. Brain 是否替代现有 service？
   - 初步答案：不替代。Brain 作为中控层组合既有 retrieval、generation、logging、agent 能力，降低重复编排。
4. `filter_history` 和 `rewrite_query` 第一版是否必须真的智能化？
   - 初步答案：不必须。第一版 no-op，但要有清晰 step 输出和测试，证明扩展点存在。
5. 阶段 8 是否接真实模型？
   - 初步答案：不作为主目标。阶段 8 先把配置和 workflow 稳住，为阶段 9 真实模型接入铺路。

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 目标分支为 `codex/phase-8-brain-workflow` | 与阶段命名和用户要求一致 |
| 从 `main` 创建阶段 8 分支 | 阶段 7 已合并到 main，符合阶段切换规则 |
| 不移动 `phase-7-complete` | 阶段 tag 必须稳定指向阶段最终功能提交 |
| 中控层命名为 Brain | 用户明确要求，且与 Quivr 架构概念一致 |
| 第一版 workflow 不引入 LangGraph | 保持依赖和行为简单可测，先沉淀边界 |
| 配置模型放在 `app/services/brain/` | Brain 是 service 层中控，不应该放在 API 或 DB 层 |
| Chat/Agent 共享 `CitationAnswerService` 入口 | 保持外部 API 不变，同时把内部编排迁移到 Brain/workflow |

## Planned File Changes

| Area | Planned Files |
|------|---------------|
| Brain 设计 | `docs/brain_workflow_design.md`, `tests/test_brain_workflow_design.py` |
| Brain service | `app/services/brain/__init__.py`, `app/services/brain/config.py`, `app/services/brain/workflow.py`, `app/services/brain/service.py` |
| Generation integration | `app/services/generation/answer_service.py` |
| Agent integration | `app/services/agent/tools.py` |
| Evaluation | `scripts/evaluate_brain_workflow.py`, `data/evaluation/brain_workflow_results.csv`, optional config/query CSV |
| Tests | `tests/test_brain_config.py`, `tests/test_brain_service.py`, `tests/test_brain_workflow.py`, `tests/test_evaluate_brain_workflow.py`, existing chat/agent regression tests |
| Stage docs | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | `obsidian-vault/阶段/阶段 8 - Brain 中控层与 Workflow 配置化.md`, phase reports, categories, knowledge notes |

## Term Explanations

| Term | Explanation |
|------|-------------|
| Brain | 本项目阶段 8 的中控层，统一组织资料库检索、配置、问答、日志和 Agent 复用链路 |
| RetrievalConfig | 检索与问答配置，控制检索模式、召回数量、分数阈值、历史数量、重排数量和 prompt 方案 |
| WorkflowConfig | 工作流配置，描述 RAG 每一步的顺序 |
| workflow step | RAG 流程中的单个步骤，例如过滤历史、改写问题、检索、重排、生成回答 |
| no-op | 空操作。第一版保留步骤位置但不改变输入，用于稳定扩展点 |
| rerank | 重排。先召回候选资料，再重新排序，提高最终上下文质量 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| 无 | 0 | 暂无 |

## Notes
- 本文件由 Planning with Files 维护，是阶段 8 的工作记忆。
- 每个 Phase 完成后，必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 8 开发过程中暂不写入 Obsidian 小 Phase 汇报；全部开发、测试和普通文档收尾完成后，再统一补齐每个 Phase 的 Obsidian 笔记。
- 阶段 8 的重点是让 RAG 编排从 service 内部隐式流程变成 Brain/workflow 的显式可配置流程。
