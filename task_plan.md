# Task Plan: 阶段 7 - Agent 化

## Goal
在阶段 6 检索优化与评测已完成的基础上，进入阶段 7：Agent 化。本阶段目标不是引入复杂工作流框架，而是把已经稳定的 search、hybrid search、chat、sources 能力包装成受控、只读优先、可测试、可追踪的 Agent 工具调用链路。

阶段 7 不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不做联网爬虫扩展。重点是工具边界、工具选择、执行编排、引用和拒答约束、调用记录、评测回归和最小展示。

## Current Phase
Phase 7 complete。阶段 7 Agent 化已完成代码、评测、前端最小展示、普通文档、Obsidian 本地知识库、最终提交与 `phase-7-complete` tag 收尾口径。

## Phases

### Phase 0: 阶段 7 启动与规划文件校准
- [x] 将线程标题修改为 `阶段7-Agent化`。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其记录阶段 6 工作记忆。
- [x] 确认阶段 6 已完成，`phase-6-complete` 指向阶段 6 最终功能提交。
- [x] 从阶段 6 稳定提交创建并切换到 `codex/phase-7-agent-tools`。
- [x] 使用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md` 为阶段 7 工作记忆。
- [x] 运行阶段启动最小基线检查。
- **验证方式:** `git show phase-6-complete`、`git branch --show-current`、规划文件内容检查、必要的轻量测试。
- **Status:** complete

### Phase 1: Agent 化设计文档与工具边界
- [x] 新增 `docs/agent_design.md`，说明阶段 7 的 Agent 目标、工具边界、只读优先原则、失败处理、权限约束、日志字段和评测方式。
- [x] 明确最小工具集：`search_knowledge`、`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- [x] 明确阶段 7 暂不自动执行写入型动作；`source reindex` 暂不作为自动工具。
- [x] 增加文档断言测试，保证设计文档覆盖核心工具、只读约束和评测要求。
- **验证方式:** `tests/test_agent_design.py`。
- **Status:** complete

### Phase 2: Agent 工具抽象与只读工具实现
- [x] 新增 `app/services/agent/` 模块。
- [x] 实现工具输入、输出、工具调用记录的数据结构。
- [x] 实现只读工具：关键词搜索、混合检索、引用式问答、来源列表、来源详情。
- [x] 工具必须复用现有 service/repository，不直接绕过 `KeywordSearchService`、`HybridSearchService`、`CitationAnswerService`、`SourceRepository`。
- [x] 补充工具层单元测试。
- **验证方式:** `tests/test_agent_tools.py`。
- **Status:** complete

### Phase 3: Agent 编排服务
- [x] 新增 Agent 编排服务，负责根据用户意图选择工具。
- [x] 实现保守的规则式意图识别：问答类走 `answer_with_citations`，搜索类走 `hybrid_search_knowledge`，来源列表/详情类走 sources 工具。
- [x] 增加最大工具调用步数限制，默认只执行 1 到 2 步。
- [x] 返回结构化结果：answer、tool_calls、sources、citations、refused、reasoning_summary。
- [x] 补充编排服务测试，覆盖问答、搜索、来源查询和拒答。
- **验证方式:** `tests/test_agent_service.py`。
- **Status:** complete

### Phase 4: Agent API 与现有 API 回归
- [x] 新增 `app/schemas/agent.py` 和 `app/api/agent.py`。
- [x] 实现 `POST /agent/query`。
- [x] 在 `app/main.py` 注册 Agent API。
- [x] 确认 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`/sources` 既有 API 不被破坏。
- [x] 补充 API 测试。
- **验证方式:** `tests/test_agent_api.py` 以及相关旧 API 测试。
- **Status:** complete

### Phase 5: Agent 评测脚本与回归结果
- [x] 新增 `data/evaluation/agent_queries.csv` 或复用 chat/keyword queries 生成 Agent 评测输入。
- [x] 新增 `scripts/evaluate_agent.py`，输出 `data/evaluation/agent_results.csv`。
- [x] 验证 Agent 不降低阶段 6 的检索、引用和拒答质量。
- [x] 记录工具调用数量、使用工具、引用有效性、拒答匹配和期望来源命中。
- [x] 补充评测脚本测试。
- **验证方式:** `tests/test_evaluate_agent.py`、运行 `scripts/evaluate_agent.py`。
- **Status:** complete

### Phase 6: 前端最小展示与体验核验
- [x] 判断是否需要在现有工作台展示 Agent 问答入口。
- [x] 如需要，只做最小前端更新：Agent 问题输入、回答、工具调用记录和引用来源展示。
- [x] 不重构前端布局，不引入前端构建链。
- [x] 补充前端静态入口测试，必要时做浏览器 smoke check。
- **验证方式:** `tests/test_frontend_app.py` 和浏览器检查。
- **Status:** complete

### Phase 7: 阶段收尾文档、Obsidian、提交与 tag
- [x] 复跑 Agent 评测、阶段 6 评测和全量测试。
- [x] 更新 `README.md`，说明阶段 7 Agent 能力、API、启动方式、测试方式和下一阶段。
- [x] 更新 `docs/progress.md`，记录阶段 7 完成内容、验证方式、遗留问题和面试表达。
- [x] 更新 `docs/architecture.md`，补充 Agent 工具层、编排服务、API 和评测链路。
- [x] 更新 `docs/data_sources.md`，说明阶段 7 是否改变数据来源边界；如未改变，要明确 Agent 只读工具不新增外部来源。
- [x] 判断并更新 `AGENT.MD`，将后续默认起点校准到阶段 7 完成后的下一步。
- [x] 开发、测试和普通文档完成后，再统一更新 Obsidian 本地知识库：阶段 7 页、阶段索引、首页、分类页、知识点、Phase 0 到最终 Phase 汇报。
- [x] 创建阶段最终功能提交。
- [x] 创建 `phase-7-complete` tag，确保 tag 指向阶段 7 最终功能提交。
- **验证方式:** 全量测试、评测脚本、Obsidian 10 项模板检查、Git tag 检查。
- **Status:** complete

## Final Verification Summary

| Check | Result |
|-------|--------|
| Agent evaluation | 5/5 passed, refused=1, tool_failures=0, citation_failures=0 |
| Keyword baseline | 15/15 passed |
| Vector baseline | 11/15 passed |
| Hybrid search | 15/15 passed, rescued_vector=4, regressed_keyword=0 |
| Chat evaluation | 6/6 passed |
| Source metrics | total_sources=125, merged_duplicates=14 |
| Frontend static tests | 3 passed |
| Browser smoke check | Agent panel answered with `hybrid_search_knowledge`, returned 5 hybrid results |
| Full tests | 163 passed |
| Obsidian Phase reports | Phase 0 through Phase 7 each contain 10 required sections |

## Key Questions
1. 阶段 7 是否引入 LangGraph？
   - 初步答案：不引入。当前目标是受控工具调用链路，先用轻量规则式编排保证可测试和可解释。
2. Agent 工具是否允许写入？
   - 初步答案：阶段 7 只读优先。source reindex 属于写入型动作，除非有明确请求字段和测试约束，否则不自动执行。
3. Agent 默认调用哪个检索？
   - 初步答案：优先 hybrid search，因为阶段 6 已证明 hybrid 在当前评测集上优于 deterministic vector 且不退化 keyword baseline。
4. Agent 评测如何证明不退化？
   - 初步答案：复用阶段 6 的检索与 chat 评测思想，记录工具调用、来源命中、citation 有效性和拒答匹配。

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 从 `phase-6-complete` 创建 `codex/phase-7-agent-tools` | 阶段 6 已完成并 tag 标识，阶段 7 应从稳定 RAG 质量基线出发 |
| 不移动 `phase-6-complete` | 阶段 tag 必须指向对应阶段最终功能提交 |
| 阶段 7 采用只读工具优先 | 降低风险，避免 Agent 自动执行 reindex 等写入动作 |
| 不引入复杂 workflow 框架 | 当前项目更需要可解释、可测试的最小 Agent 工具链 |
| Agent 工具复用既有 service | 保证不绕过 sources、documents/chunks、hybrid search、chat citation 和日志约束 |
| 每个 Phase 后更新三份规划文件 | Planning with Files 是本阶段工作记忆和恢复依据 |

## Planned File Changes
| Area | Planned Files |
|------|---------------|
| Agent 设计 | `docs/agent_design.md`, `tests/test_agent_design.py` |
| Agent service | `app/services/agent/*.py` |
| Agent API/schema | `app/api/agent.py`, `app/schemas/agent.py`, `app/main.py` |
| Agent 评测 | `scripts/evaluate_agent.py`, `data/evaluation/agent_queries.csv`, `data/evaluation/agent_results.csv` |
| 测试 | `tests/test_agent_tools.py`, `tests/test_agent_service.py`, `tests/test_agent_api.py`, `tests/test_evaluate_agent.py` |
| 前端最小展示 | `app/frontend/index.html`, `app/frontend/static/app.js`, `app/frontend/static/styles.css`, `tests/test_frontend_app.py` |
| 阶段文档 | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | `obsidian-vault/首页.md`, `obsidian-vault/阶段索引.md`, `obsidian-vault/阶段/阶段 7 - Agent 化.md`, `obsidian-vault/阶段汇报/阶段 7 - Agent 化/*.md`, `obsidian-vault/知识点/*.md`, `obsidian-vault/分类/*.md` |

## Term Explanations
| Term | Explanation |
|------|-------------|
| Agent | 能根据用户意图选择工具并组织结果的编排层。本项目阶段 7 先做轻量、受控、只读优先的 Agent |
| Tool | Agent 可调用的能力包装，例如混合检索、引用式问答、来源查询 |
| Orchestration | 编排。决定调用哪个工具、调用几步、如何汇总结果 |
| Tool call log | 工具调用记录。保存工具名、输入摘要、输出摘要、成功状态和错误信息，便于排查 |
| Read-only tool | 只读工具。只查询资料和来源，不修改数据库或文件 |
| reasoning_summary | 可审计摘要。给用户说明本次为什么调用这些工具，但不暴露内部推理细节 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 无 | 0 | 暂无 |

## Notes
- 本文件由 Planning with Files 维护，是阶段 7 的工作记忆。
- 每个 Phase 完成后，必须先更新 `task_plan.md`、`findings.md`、`progress.md`；对话中只保留简短进度说明，不输出完整 10 项 Phase 汇报。
- 阶段 7 开发过程中暂不写入 Obsidian 小 Phase 汇报；所有开发、测试和普通文档收尾完成后，再按 `obsidian-vault/模板/Phase 汇报模板.md` 统一补齐每个 Phase 的 Obsidian 笔记。
- 阶段 7 的重点是让 Agent 调用 RAG 系统，但不能绕过来源、权限、引用、拒答和评测约束。
