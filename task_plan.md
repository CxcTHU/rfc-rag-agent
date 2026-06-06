# Task Plan: 阶段 6 - 检索优化与评测

## Goal
在阶段 5 前端工作台已完成并合并到 `main` 的基础上，进入阶段 6：检索优化与评测。本阶段要把“系统能回答”推进到“系统质量可度量、可复现、可解释地优化”。

阶段 6 不做 Agent 工具调用、不做复杂 LangGraph workflow、不做登录系统、不做部署优化；重点是评测计划、错误案例分析、核心指标、检索优化方案和优化前后对比。

## Current Phase
Phase 6 complete。阶段 6 已完成检索优化与评测闭环、文档收尾、Obsidian 本地知识库回填、最终评测和全量测试。下一步创建阶段最终提交并确认 `phase-6-complete` tag 指向该提交。

## Phases

### Phase 0: 阶段 6 启动与规划文件校准
- [x] 将线程标题修改为 `阶段6-检索优化与评测`。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其仍记录阶段 5 工作记忆。
- [x] 确认阶段 5 已合并到 `main`。
- [x] 确认 `phase-5-complete` tag 指向阶段 5 最终功能提交，不移动该 tag。
- [x] 从 `main` 创建并切换到 `codex/phase-6-evaluation` 分支。
- [x] 使用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md` 为阶段 6 工作记忆。
- [x] 记录 Phase 0 完成状态。
- **Status:** complete

### Phase 1: 评测计划与指标设计
- [x] 新增 `docs/evaluation_plan.md`，说明阶段 6 的评测目标、数据集、流程和判定标准。
- [x] 明确核心指标：Recall@K、Citation Accuracy、Faithfulness、Answer Coverage、Refusal Quality。
- [x] 复核现有 `keyword_queries.csv`、`keyword_results.csv`、`vector_results.csv`、`chat_queries.csv`、`chat_results.csv`。
- [x] 明确哪些指标可以当前自动计算，哪些先用规则近似或人工审阅字段承接。
- [x] 补充必要测试或文档断言。
- **Status:** complete

### Phase 2: Baseline 复跑与错误案例分析
- [x] 复跑关键词、向量、chat 评测，确认阶段 6 起点指标。
- [x] 新增错误案例分析输出，例如 `data/evaluation/retrieval_error_cases.csv`。
- [x] 记录失败问题、失败原因、命中片段、期望依据、改进建议和优化前后状态。
- [x] 补充错误分析脚本及测试。
- **Status:** complete

### Phase 3: 可解释检索优化方案
- [x] 设计一种保守、可解释的优化方案，优先考虑混合检索或轻量 rerank。
- [x] 保留 `POST /search` 和 `POST /search/vector` 既有行为不破坏。
- [x] 新增 service 层优化能力，例如 hybrid search，把关键词与向量结果合并、归一化、去重、重排。
- [x] 必要时新增 API 或脚本入口，但不把阶段 6 变成前端重构。
- [x] 补充 service 和 API 测试。
- **Status:** complete

### Phase 4: 评测脚本升级与指标对比
- [x] 改进评测脚本，使优化前后可以同表对比。
- [x] 输出混合检索或 rerank 的结果 CSV。
- [x] 计算并记录 Recall@K、关键词 baseline、向量 baseline、优化方案的通过数和差异。
- [x] 复跑 chat 评测，确认引用和拒答链路没有破坏。
- **Status:** complete

### Phase 5: 前端最小展示与体验核验
- [x] 判断是否需要在前端展示新检索模式；只做最小必要更新。
- [x] 如果新增检索模式，保证界面能选择并展示结果，不做大重构。
- [x] 运行前端入口和相关 API 测试。
- [x] 必要时做浏览器 smoke check。
- **Status:** complete

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag
- [x] 更新 `README.md`，说明阶段 6 评测体系、检索优化方案、验证结果和下一阶段。
- [x] 更新 `docs/progress.md`，记录阶段 6 完成内容、指标对比、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充阶段 6 评测和优化链路。
- [x] 判断并更新 `docs/data_sources.md`，如数据来源关系未变则说明原因。
- [x] 判断并更新 `AGENT.MD`，将后续默认起点校准为阶段 7：Agent 化。
- [x] 开发、测试和常规文档收尾完成后，再统一更新 Obsidian 本地知识库：首页、阶段索引、阶段 6 页面、分类页、知识点和全部 Phase 汇报。
- [x] 运行全量测试。
- [x] 创建阶段最终功能提交。
- [x] 创建 `phase-6-complete` tag，确保 tag 指向阶段 6 最终功能提交。
- [x] 最终汇报阶段提交号和 tag 名称。
- **Status:** complete

## Key Questions
1. 阶段 6 先优化检索，还是先做评测？
   - 初步答案：先做评测计划和 baseline 复跑，再优化。否则无法证明改动是否真的改善质量。
2. 阶段 6 采用哪种优化方案最稳妥？
   - 初步答案：优先混合检索或轻量 rerank，因为它们能复用现有关键词和向量链路，容易解释，也不依赖真实模型 key。
3. 是否接入真实 embedding provider？
   - 初步答案：可以为真实 embedding 做配置和评测准备，但阶段 6 不能依赖外部 key 才能通过测试。
4. 是否改前端？
   - 初步答案：只有新增检索模式需要用户操作时才做最小更新；阶段 6 不是前端重构。

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 从 `main` 创建 `codex/phase-6-evaluation` | 阶段 5 已合并，阶段 6 应从主线继续 |
| 不移动 `phase-5-complete` tag | 阶段 tag 必须指向对应阶段最终功能提交 |
| 评测先行 | 阶段 6 的目标是质量可证明，不是凭感觉调参 |
| 优先混合检索或轻量 rerank | 可解释、低依赖、能复用现有关键词和向量结果 |
| 每个 Phase 后更新三份规划文件 | Planning with Files 是本阶段工作记忆和恢复依据 |

## Planned File Changes
| Area | Planned Files |
|------|---------------|
| 评测计划 | `docs/evaluation_plan.md` |
| 检索服务 | `app/services/retrieval/*.py` |
| 检索 API/schema | `app/api/search.py`, `app/schemas/search.py` |
| 评测脚本 | `scripts/evaluate_*.py`, possible `scripts/evaluate_hybrid_search.py`, possible `scripts/analyze_retrieval_errors.py` |
| 评测数据 | `data/evaluation/*.csv` |
| 测试 | `tests/test_*search*.py`, `tests/test_evaluate_*.py`, possible new tests |
| 前端最小更新 | `app/frontend/index.html`, `app/frontend/static/app.js`, `app/frontend/static/styles.css` |
| 阶段文档 | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | `obsidian-vault/首页.md`, `obsidian-vault/阶段索引.md`, `obsidian-vault/阶段/阶段 6 - 检索优化与评测.md`, `obsidian-vault/阶段汇报/阶段 6 - 检索优化与评测/*.md`, `obsidian-vault/知识点/*.md`, `obsidian-vault/分类/*.md` |

## Term Explanations
| Term | Explanation |
|------|-------------|
| baseline | 基线结果。优化前的关键词、向量、chat 评测成绩，用来和优化后对比 |
| Recall@K | 前 K 条结果里是否召回了期望资料。本项目可用命中期望标题/内容/source_type 近似计算 |
| Citation Accuracy | 引用准确性。回答中的 citation 是否能对应真实返回的 source，且来源是否符合期望 |
| Faithfulness | 忠实度。回答是否只基于检索到的资料，不编造资料外结论 |
| Answer Coverage | 覆盖度。回答是否覆盖问题需要的关键点 |
| Refusal Quality | 拒答质量。资料不足时是否拒答，资料足够时是否不误拒 |
| hybrid search | 混合检索。把关键词检索和向量检索结果合并，再去重、归一化、重排 |
| rerank | 重排。对初步召回结果重新排序，让更可靠、更相关的片段排在前面 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 旧 planning 文件仍记录阶段 5 | 1 | 进入阶段 6 后重写 `task_plan.md`、`findings.md`、`progress.md` |
| 切换阶段 6 前存在一个 Obsidian 索引本地改动 | 1 | 保留用户已有改动，不回退，随分支继续 |

## Notes
- 本文件由 Planning with Files 维护，是阶段 6 的工作记忆。
- 每个 Phase 完成后，必须先更新 `task_plan.md`、`findings.md`、`progress.md`；对话中只保留简短进度说明，不输出完整 10 项 Phase 汇报。
- 阶段 6 的重点是检索质量、问答质量和评测可复现，不是 Agent 化或前端重构。
- 阶段 6 开发过程中暂不写入 Obsidian 小 Phase 汇报；所有开发、测试和普通文档收尾完成后，再按 `obsidian-vault/模板/Phase 汇报模板.md` 统一补齐每个 Phase 的 Obsidian 笔记，并在每篇笔记中写完整 10 项汇报。
