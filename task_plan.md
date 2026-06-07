# Task Plan: 阶段 15 - 真实配置复跑与质量审阅报告

## Goal

在阶段 14 已完成并合并到 `main` 的基础上，完成阶段 15：真实配置复跑、真实/人工回答质量复核、阶段 14/15 质量表汇总，以及只读报告页或导出报告入口。阶段最终必须完成普通文档、Obsidian 本地知识库、全量测试、最终提交和 `phase-15-complete` tag。

本阶段不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不把 HyDE 接入默认链路或自动回归、不把真实 API 调用变成 CI 或本地全量测试前提。真实 API key、供应商原始敏感响应、受限全文不得写入 Git、CSV、文档、测试或 Obsidian。

核心链路：

```text
stage14 quality tables
-> 真实配置可用性检查
-> vector/hybrid/user/decompose/chat/agent/brain workflow 真实结果复跑或 graceful skip
-> stage14_answer_coverage_review.csv 中 medium/review 样例复核
-> 质量审阅汇总
-> 只读报告页或导出报告
-> 发布前质量结论和下一阶段依据
```

## Current Phase

Phase 6 complete。阶段 15 普通文档、Obsidian、本地安全检查、最终全量测试、提交准备和 tag 收尾均已完成；最终提交号和 `phase-15-complete` tag 由 Git 结果确认。

## Phases

### Phase 0: 阶段启动与规划校准

- [x] 将线程标题修改为 `阶段15-真实配置复跑与质量审阅报告`。
- [x] 阅读 Planning with Files 规则。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage14_real_quality_calibration.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其为阶段 14 工作记忆。
- [x] 确认阶段 14 已合并到 `main`：`main` 当前为 `b9cb019 Merge phase 14 real quality calibration`。
- [x] 确认 `phase-14-complete` 指向阶段 14 最终功能提交 `e5df149`，不移动已有阶段 tag。
- [x] 从阶段 14 合并后的 `main` 创建并切换到 `codex/phase-15-real-review-report`。
- [x] 使用 Planning with Files 校准阶段 15 的三份记忆文件。
- [x] 运行阶段 15 起点全量测试。
- 验证方式：线程标题、Git 分支/tag 检查、规划文件检查、起点全量测试。
- 文档收尾要求：记录阶段起点、tag 状态、当前分支、阶段 14 遗留问题和阶段 15 baseline。
- Status: complete

### Phase 1: 阶段 15 设计文档与质量报告口径

- [x] 新增 `docs/stage15_real_review_report.md`。
- [x] 明确真实配置复跑、graceful skip、人工/真实回答审阅、质量汇总和只读报告的目标、输入、输出、指标和边界。
- [x] 明确 `data/evaluation/stage14_real/` 只保存脱敏评测结果，不保存 API key、供应商原始敏感响应或受限全文。
- [x] 明确 deterministic baseline、real_config completed/skipped/error 和人工复核之间的比较口径。
- [x] 明确只读报告页或导出报告不改变核心 RAG API，不重构前端工作台。
- [x] 新增或更新设计测试，校验阶段 15 文档包含目标、边界、产物、skip 规则、报告入口和完成标准。
- 验证方式：文档测试和字段检查。
- 文档收尾要求：在 `findings.md` 记录阶段 15 技术决策、新词和风险边界。
- Status: complete

### Phase 2: 真实配置复跑脚本与 stage14_real 结果目录

- [x] 新增或改进真实配置复跑脚本，统一输出到 `data/evaluation/stage14_real/`。
- [x] 覆盖 vector、hybrid、user_questions、decompose、chat、agent、brain_workflow 的真实配置复跑或 skipped/error 记录。
- [x] 真实配置完整时可显式运行真实评测；配置缺失、结果缺失、外部失败时写 skipped/error，不伪造成成功。
- [x] 保留 deterministic baseline，并让 `stage14_embedding_comparison.csv` 能清楚对比 baseline、真实结果和缺失状态。
- [x] 脚本输出不得包含 API key、Bearer token、供应商原始敏感响应或受限全文。
- [x] 补充测试覆盖 completed、skipped、error、missing_results、输出目录和脱敏字段。
- 验证方式：脚本单测、无真实配置下 graceful skip、必要时 deterministic/mock 结果生成。
- 文档收尾要求：在 `progress.md` 记录真实配置当前状态和复跑结果。
- Status: complete

### Phase 3: Answer Coverage 复核表

- [x] 针对 `stage14_answer_coverage_review.csv` 中 `medium/review` 样例建立阶段 15 复核结果表。
- [x] 输出至少包含 query_id、question、expected_answer_points、answer_summary、evidence_titles、faithfulness、answer_coverage、citation_quality、risk_level、review_method、review_note、next_action。
- [x] 支持人工规则复核；真实模型结果存在时可读取脱敏结果辅助复核，缺失时记录 skipped/review。
- [x] 明确 unsupported 拒答样例和 medium/review 样例的风险处理差异。
- [x] 补充测试覆盖字段、风险等级、review/pass/fail 判定和 skipped 行。
- 验证方式：脚本单测、CSV schema 检查、样例内容检查。
- 文档收尾要求：在 `findings.md` 记录 Faithfulness、Answer Coverage、Citation Quality 在阶段 15 的复核含义和面试表达。
- Status: complete

### Phase 4: 质量汇总与只读报告入口

- [x] 建立阶段 15 质量汇总表或报告数据，汇总 deterministic baseline、real_config 状态、Answer Coverage 复核和 Decompose provenance 风险。
- [x] 实现只读报告页或导出报告入口，用于展示阶段 14/15 质量表；不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`。
- [x] 如果改前端，只做最小只读展示，不重构核心工作台。
- [x] 补充报告/前端测试，验证页面或导出内容包含关键指标、风险和下一步建议。
- 验证方式：报告数据生成、前端或导出测试、API 兼容测试。
- 文档收尾要求：记录报告入口的使用方式、边界和不保存敏感信息的原因。
- Status: complete

### Phase 5: 阶段 15 回归验证与质量结论

- [x] 复跑 deterministic vector、hybrid、user_questions、decompose、chat、agent、brain_workflow 评测。
- [x] 运行阶段 15 新增脚本和聚焦测试。
- [x] 运行 documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend 相关回归测试。
- [x] 汇总真实配置 completed/skipped/error 状态、Answer Coverage 复核结果、质量风险和下一阶段依据。
- 验证方式：评测脚本输出、聚焦测试、全量测试前检查。
- 文档收尾要求：`progress.md` 记录所有测试命令和结果。
- Status: complete

### Phase 6: 普通文档、Obsidian、最终测试、提交与 tag

- [x] 更新 `README.md`，说明阶段 15 能力、评测/报告结果、使用边界和下一阶段建议。
- [x] 更新 `docs/progress.md`，记录完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充真实配置复跑、质量复核和只读报告数据流。
- [x] 更新 `docs/data_sources.md`，说明阶段 15 只新增评测/报告产物，不新增文献来源、不保存受限全文或 API key。
- [x] 判断并更新 `AGENT.MD`；阶段 15 经验改变了后续工作规则和下一步建议，已同步更新。
- [x] 统一补齐 Obsidian 本地知识库：阶段 15 阶段页、阶段汇报目录、Phase 0 到最终 Phase 汇报、索引、分类页和知识点。
- [x] 确认每篇 Obsidian Phase 汇报包含 10 个固定小节。
- [x] 确认 `obsidian-vault/` 仍被 Git 忽略，不纳入提交。
- [x] 运行最终全量测试。
- [x] 创建阶段 15 最终功能提交。
- [x] 创建 `phase-15-complete` tag，确保 tag 指向阶段 15 最终功能提交。
- 验证方式：文档检查、Obsidian 小节检查、全量测试、Git commit/tag 检查。
- 文档收尾要求：所有普通文档与 Obsidian 阶段知识库同步完成。
- Status: complete

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `codex/phase-15-real-review-report` |
| Previous tags | `phase-14-complete` and older phase tags remain unmoved |
| Design doc | `docs/stage15_real_review_report.md` exists and documents metrics, flow, skip rules, review rubric and report boundaries |
| Real rerun outputs | `data/evaluation/stage14_real/` contains real completed rows or explicit skipped/error status files |
| Comparison | deterministic baseline and real_config status can be compared without fake success |
| Coverage review | Stage 15 review table covers Faithfulness, Answer Coverage, Citation Quality, risk and next action |
| Quality summary/report | Stage 15 quality summary or read-only report shows key metrics, risk and next-stage basis |
| API contract | search/vector/hybrid/chat/agent API tests pass without schema break |
| Full tests | `.venv\Scripts\python.exe -m pytest -q` passes |
| Docs | README, docs/progress, docs/architecture, docs/data_sources and AGENT.MD judgment updated |
| Obsidian | Stage 15 local knowledge base updated and remains ignored by Git |
| Tag | `phase-15-complete` points to final phase 15 functionality commit |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支为 `codex/phase-15-real-review-report` | 与阶段 15 目标和用户要求一致 |
| 从阶段 14 合并后的 `main` 创建阶段 15 分支 | 阶段 14 是最新稳定起点 |
| 不移动已有阶段 tag | 阶段 tag 必须稳定指向各阶段最终功能提交 |
| 保留 deterministic baseline | 自动回归必须不依赖真实 API、网络、余额和限流 |
| 真实 API 缺失时 graceful skip | 阶段 15 要证明真实配置状态，不能伪造结果 |
| 报告优先只读 | 阶段 15 是质量审阅，不是核心前端重构 |
| HyDE 不进默认链路 | 避免假想答案污染引用和自动回归 |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| 真实配置复跑 | 使用本地 `.env` 中真实 embedding/chat provider 配置显式复跑评测，并输出脱敏结果 |
| stage14_real | `data/evaluation/stage14_real/`，保存真实配置复跑结果或 skipped/error 状态的目录 |
| deterministic baseline | 本地确定性模型结果，用于稳定回归，不代表真实模型语言质量 |
| Answer Coverage | 回答是否覆盖用户问题期望的核心技术点 |
| Faithfulness | 回答是否忠于检索资料，不引入来源外事实 |
| Citation Quality | 引用编号是否能追溯并支撑关键说法 |
| Graceful skip | 真实 API 未配置或失败时记录 skipped/error，不伪造成功、不让自动回归失败 |
| 只读报告 | 展示质量表和结论的报告入口，不触发写入、不改变核心 RAG API |

## Notes

- 本文件由 Planning with Files 维护，是阶段 15 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 15 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 6 统一补齐。
- 真实模型更适合质量校准，deterministic provider 继续负责稳定回归。
