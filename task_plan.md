# Task Plan: 阶段 12 - 质量审阅与上下文最小补全

## Goal

在阶段 11 已完成并合并到 `main` 的基础上，完成阶段 12：质量审阅与上下文最小补全。

本阶段不做登录系统、不做部署优化、不做复杂 LangGraph workflow、不做写入型 Agent 工具、不把 HyDE 接入默认链路、不做复杂长期记忆系统。重点是把阶段 11 的人工审阅抽样真正用于质量校准，并在 Brain workflow 的 `rewrite_query` 位置实现最小上下文补全。

核心链路：

```text
阶段 11 用户问题集与审阅样本
-> 人工/离线审阅 Faithfulness、Answer Coverage、Citation Quality
-> 质量风险归因
-> 最小上下文补全 rewrite_query
-> 基于历史问题补全代词或省略问法
-> 复跑 user_questions、chat、agent、Brain workflow 回归
-> 形成阶段 13 Decompose / rerank / HyDE 离线实验依据
```

## Current Phase

Phase 5 complete。阶段 12 已完成启动校准、质量审阅、Brain workflow 最小上下文补全、回归复测、阶段 13 Decompose 预研计划、普通文档、Obsidian、最终全量测试、提交和 tag 收尾。

## Phases

### Phase 0: 阶段启动与规划校准

- [x] 将线程标题修改为 `阶段12-质量审阅与上下文最小补全`。
- [x] 阅读 Planning with Files 技能说明。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage11_user_evaluation_plan.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其为阶段 11 工作记忆。
- [x] 确认阶段 11 已合并到 `main`，当前 `main` 最新提交为 `09926f5 merge phase 11 user evaluation query expansion`。
- [x] 确认 `phase-11-complete` 指向阶段 11 最终功能提交 `fcd174e`，不移动已有阶段 tag。
- [x] 从阶段 11 合并后的 `main` 创建并切换到 `codex/phase-12-quality-review-context-calibration`。
- [x] 使用 Planning with Files 校准阶段 12 的三份记忆文件。
- [x] 运行阶段 12 起点全量测试。
- 验证方式：线程标题、Git 分支/tag 检查、规划文件检查、起点全量测试。
- 文档收尾要求：记录阶段起点、已确认 tag、当前分支、阶段 11 遗留问题和基线测试。
- Status: complete

### Phase 1: 审阅样本与质量报告落地

- [x] 复核 `data/evaluation/user_question_review_samples.csv` 的样本覆盖和字段。
- [x] 新增或更新阶段 12 审阅结果表，记录 `faithfulness`、`answer_coverage`、`citation_quality` 和 reviewer notes。
- [x] 新增 `docs/stage12_quality_review.md`，说明审阅方法、rubric、样本、结果、风险和质量结论。
- [x] 复核 `data/evaluation/user_question_results.csv`，说明 `default_hybrid`、`keyword_baseline`、`vector_only` 的差异。
- [x] 明确 HyDE 仅作为后续离线评估建议，不进入默认链路或自动回归。
- [x] 新增文档/数据 schema 测试，确认审阅产物不保存真实 API key 或受限全文。
- 验证方式：审阅文档测试、CSV schema 测试、敏感信息检查。
- 文档收尾要求：在 `findings.md` 和 `progress.md` 记录质量风险、审阅结论和阶段 13 输入。
- Status: complete

### Phase 2: 最小上下文补全设计与实现

- [x] 复核 `BrainService._rewrite_query_step()`、`RetrievalConfig.max_history`、`CitationAnswerService`、`/chat` 和 Agent 调用路径。
- [x] 设计最小上下文补全规则，只基于最近历史问题处理代词或省略问法。
- [x] 在 Brain workflow 的 `rewrite_query` 位置实现补全，不改变旧请求兼容性。
- [x] 支持“它”“这个技术”“这类问题”等代词/省略表达的保守补全。
- [x] 保留原始问题用于最终回答展示，使用补全问题用于检索。
- [x] 不做复杂多轮记忆、不做长期用户画像、不引入真实模型改写。
- 验证方式：Brain workflow 单元测试覆盖有历史/无历史、代词补全、普通问题不改写。
- 文档收尾要求：记录上下文补全的边界、失败保护和面试表达。
- Status: complete

### Phase 3: Chat/Agent 回归与用户问题复测

- [x] 为 `/chat` 和 Agent 共享 Brain workflow 的上下文补全路径补充回归测试。
- [x] 复跑用户问题评测，确认阶段 11 默认链路不退化。
- [x] 复跑 chat、agent、Brain workflow deterministic 评测。
- [x] 复跑 search/vector/hybrid/chat/agent API 回归测试，确认旧请求兼容。
- [x] 记录上下文补全对现有评测的影响，特别是是否引入误改写。
- 验证方式：相关单元测试、评测脚本输出、API 回归。
- 文档收尾要求：在 `progress.md` 记录每项评测结果，在 `findings.md` 记录误改写风险。
- Status: complete

### Phase 4: 阶段 12 质量结论与后续阶段设计

- [x] 汇总阶段 12 质量审阅结论、上下文补全效果和残留风险。
- [x] 明确阶段 13 Decompose 的输入：复杂问题拆解、子 query 检索、证据合并、去重排序。
- [x] 明确 Semantic 方向：保留阶段 11 词表型 query expansion，HyDE 只做离线实验建议。
- [x] 明确 Context 方向：阶段 12 只做最小补全，不扩展成长期记忆系统。
- [x] 判断是否需要更新 `AGENT.MD` 的推荐下一步和阶段路线。
- 验证方式：质量报告、阶段路线文档、现有评测结果。
- 文档收尾要求：把阶段 12 结论写入普通文档准备材料。
- Status: complete

### Phase 5: 阶段收尾文档、Obsidian、提交与 tag

- [x] 更新 `README.md`，说明阶段 12 质量审阅、上下文补全、评测结果和下一阶段建议。
- [x] 更新 `docs/progress.md`，记录完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充阶段 12 审阅链路和 `rewrite_query` 最小上下文补全数据流。
- [x] 更新 `docs/data_sources.md`，说明阶段 12 审阅产物不新增资料来源、不保存真实模型密钥或受限全文。
- [x] 判断并更新 `AGENT.MD`，把后续起点校准到阶段 12 完成后的下一步。
- [x] 统一补齐 Obsidian 本地知识库：阶段 12 阶段页、阶段汇报目录、Phase 0-5 汇报、索引、分类页和知识点。
- [x] 确认 Obsidian 仍由 Git 忽略，不纳入提交。
- [x] 复跑最终全量测试和关键阶段评测。
- [x] 创建阶段最终功能提交。
- [x] 创建 `phase-12-complete` tag，确保 tag 指向阶段 12 最终功能提交。
- 验证方式：文档检查、Obsidian 10 项模板检查、全量测试、Git commit/tag 检查。
- 文档收尾要求：所有普通文档与 Obsidian 阶段知识库同步完成。
- Status: complete

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `codex/phase-12-quality-review-context-calibration` |
| Previous tags | `phase-11-complete` and older phase tags remain unmoved |
| Review results | Stage 12 review results table exists or `user_question_review_samples.csv` is updated |
| Quality report | `docs/stage12_quality_review.md` exists and documents rubric, samples, results, risks |
| Context rewrite | Brain `rewrite_query` performs conservative history-based补全 |
| API contract | search/vector/hybrid/chat/agent API tests pass without schema break |
| Deterministic regression | user_questions/chat/agent/Brain evaluations remain runnable |
| Full tests | `.venv\Scripts\python.exe -m pytest -q` passes |
| Docs | README, docs/progress, docs/architecture, docs/data_sources, AGENT.MD and Obsidian updated |
| Tag | `phase-12-complete` points to final phase 12 functionality commit |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支为 `codex/phase-12-quality-review-context-calibration` | 与阶段目标和用户要求一致 |
| 从阶段 11 合并后的 `main` 创建阶段 12 分支 | 阶段 11 是最新稳定起点 |
| 不移动既有阶段 tag | 阶段 tag 必须稳定指向各阶段最终提交 |
| 先做质量审阅，再做上下文补全 | 阶段 11 已暴露自动评测无法充分判断覆盖度和忠实度 |
| 上下文补全放在 Brain `rewrite_query` | 阶段 8 已把 `/chat` 与 Agent 问答收敛到 Brain workflow |
| HyDE 不进入默认链路 | 避免真实模型依赖和假想答案污染引用边界 |
| Decompose 只做阶段 13 输入 | 阶段 12 先校准质量和最小 context，不扩大复杂 workflow |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| Faithfulness | 回答是否忠实于检索来源，没有引入资料外事实 |
| Answer Coverage | 回答是否覆盖 `expected_answer_points` 中的核心技术点 |
| Citation Quality | 引用是否能支持回答中的关键说法 |
| Context Rewrite | 基于最近历史问题，把“它/这个技术”等省略问法补成更适合检索的问题 |
| HyDE | 先让模型生成假想答案再检索；本阶段只保留离线评估建议，不进默认链路 |
| Decompose | 把复杂问题拆成多个子 query 分别检索；本阶段只做后续设计输入 |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| None yet | - | - |

## Notes

- 本文件由 Planning with Files 维护，是阶段 12 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 12 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 5 统一补齐。
- 真实模型更适合最终质量校准，deterministic provider 更适合稳定回归。阶段 12 继续保持两者分离。
