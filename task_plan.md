# Task Plan: 阶段 14 - 真实 Embedding 与回答覆盖校准

## Goal

在阶段 13 已完成并合并到 `main` 的基础上，完成阶段 14：真实 embedding 对比、真实模型或人工 Answer Coverage 校准、Decompose provenance / rerank explanation 可读化，以及阶段 14 文档、Obsidian、提交和 `phase-14-complete` tag 收尾。

本阶段不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不把 HyDE 接入默认链路或自动回归、不把真实 API 调用变成 CI 必跑前提。

核心链路：

```text
sources/documents/chunks/chunk_embeddings
-> deterministic baseline
-> 真实 embedding/provider 配置复核与索引重建
-> user/decompose/vector/hybrid/chat/brain/agent 评测对比
-> 真实模型或人工 Answer Coverage 校准
-> Decompose provenance / rerank explanation 评测可读化
-> 质量结论和下一阶段依据
```

## Current Phase

Phase 6 complete。阶段 14 已完成启动校准、设计文档、三类阶段 14 评测产物、聚焦测试、核心评测、API/服务/前端回归、普通文档、Obsidian 本地知识库和最终全量测试。下一步仅剩 Git 提交与 `phase-14-complete` tag 锚定。

## Phases

### Phase 0: 阶段启动与规划校准

- [x] 将线程标题修改为 `阶段14-真实Embedding与回答覆盖校准`。
- [x] 阅读 Planning with Files 规则。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/model_provider_evaluation.md`、`docs/stage12_quality_review.md`、`docs/stage13_decompose_plan.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其为阶段 13 工作记忆。
- [x] 确认阶段 13 已合并到 `main`：`main` 当前为 `27b25d3 Merge phase 13 decompose evidence merge`。
- [x] 确认 `phase-13-complete` 指向阶段 13 最终功能提交 `69a28cd`，不移动已有阶段 tag。
- [x] 从阶段 13 合并后的 `main` 创建并切换到 `codex/phase-14-real-quality-calibration`。
- [x] 使用 Planning with Files 校准阶段 14 的三份记忆文件。
- [x] 运行阶段 14 起点全量测试。
- 验证方式：线程标题、Git 分支/tag 检查、规划文件检查、起点全量测试。
- 文档收尾要求：记录阶段起点、tag 状态、当前分支、阶段 13 遗留问题和阶段 14 baseline。
- Status: complete

### Phase 1: 阶段 14 设计文档与评测口径固化

- [x] 新增 `docs/stage14_real_quality_calibration.md`。
- [x] 明确真实 embedding 对比、真实回答覆盖校准、数据集、流程、指标和判定标准。
- [x] 明确真实 API 缺失、限流、余额不足时必须 graceful skip，不伪造结果。
- [x] 明确 deterministic baseline 仍是自动回归主口径。
- [x] 明确 Decompose provenance / rerank explanation 只做评测可读化或只读最小展示。
- [x] 新增或更新设计测试，校验阶段 14 文档包含目标、边界、指标、skip 规则和产物。
- 验证方式：文档测试和字段检查。
- 文档收尾要求：在 `findings.md` 记录阶段 14 技术决策、新词和风险边界。
- Status: complete

### Phase 2: 真实 Embedding 对比脚本与结果表

- [x] 新增或扩展评测脚本，生成 `data/evaluation/stage14_embedding_comparison.csv`。
- [x] 复用 deterministic vector/hybrid/user/decompose 结果作为 baseline。
- [x] 显式记录 provider、model、dimension、config_name、suite、passed、total、pass_rate、failed_queries、status、skipped_reason。
- [x] 支持真实 embedding 配置完整时读取或生成真实评测结果；配置缺失或外部失败时写 skipped/error，不把真实 API 失败当成本地回归失败。
- [x] 保留 vector-only 失败边界，不用静默 fallback 掩盖。
- [x] 补充脚本测试，覆盖 completed、missing_results、skipped 和 failed query 汇总。
- 验证方式：脚本单测、deterministic 输出、真实配置缺失 skip 输出。
- 文档收尾要求：在 `progress.md` 记录 baseline 指标和 skip/完成状态。
- Status: complete

### Phase 3: Answer Coverage 校准结果表

- [x] 新增或扩展脚本，生成 `data/evaluation/stage14_answer_coverage_review.csv`。
- [x] 输入复用 `data/evaluation/user_questions.csv`、`stage13_decompose_results.csv`、用户问题评测结果和阶段 12 审阅口径。
- [x] 记录 query、expected_answer_points、evidence titles、answer、Faithfulness、Answer Coverage、Citation Quality、risk_level、recommendation。
- [x] 默认可用 deterministic/人工规则生成可审阅表；真实模型配置可选运行，缺失时 skipped。
- [x] 保证表格不保存 API key、原始供应商响应或受限全文。
- [x] 补充测试覆盖字段、评分口径和 unsupported 拒答样例。
- 验证方式：脚本单测、CSV schema 检查、样例内容检查。
- 文档收尾要求：在 `findings.md` 记录 Answer Coverage、Faithfulness、Citation Quality 的项目内含义和面试表达。
- Status: complete

### Phase 4: Decompose Provenance 与 Rerank Explanation 可读化

- [x] 扩展阶段 13 Decompose 评测输出或新增阶段 14 可读化输出。
- [x] 将 sub query provenance、命中来源、去重、both_match、topic_terms、final_score 组织成更易审阅的字段。
- [x] 判断前端是否需要最小只读展示；若需要，只展示说明或评测结果入口，不重构前端。
- [x] 保证外部 API schema 不破坏：`POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 兼容。
- [x] 补充 Decompose/前端/API 回归测试。
- 验证方式：Decompose 脚本测试、API 测试、必要时前端 smoke 测试。
- 文档收尾要求：记录 provenance 可读化对 RAG 引用链路的价值。
- Status: complete

### Phase 5: 阶段 14 回归验证与质量结论

- [x] 复跑 deterministic vector、hybrid、chat、agent、brain workflow、user questions、decompose 评测。
- [x] 运行阶段 14 新增脚本和聚焦测试。
- [x] 运行 documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend 相关回归测试。
- [x] 记录真实配置是否 completed、skipped 或 error，并说明原因。
- [x] 汇总指标对比、失败案例、风险和下一阶段依据。
- 验证方式：评测脚本输出、聚焦测试、全量测试前检查。
- 文档收尾要求：`progress.md` 记录所有测试命令和结果。
- Status: complete

### Phase 6: 普通文档、Obsidian、最终测试、提交与 tag

- [x] 更新 `README.md`，说明阶段 14 能力、评测结果、使用边界和下一阶段建议。
- [x] 更新 `docs/progress.md`，记录完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充真实 embedding 对比、Answer Coverage 校准和 provenance 可读化数据流。
- [x] 更新 `docs/data_sources.md`，说明阶段 14 只新增评测/审阅产物，不新增文献来源、不保存受限全文或 API key。
- [x] 判断并更新 `AGENT.MD`，把后续起点校准到阶段 14 完成后的下一步。
- [x] 统一补齐 Obsidian 本地知识库：阶段 14 阶段页、阶段汇报目录、Phase 0 到最终 Phase 汇报、索引、分类页和知识点。
- [x] 确认每篇 Obsidian Phase 汇报包含 10 个固定小节。
- [x] 确认 `obsidian-vault/` 仍被 Git 忽略，不纳入提交。
- [x] 运行最终全量测试。
- [ ] 创建阶段 14 最终功能提交。
- [ ] 创建 `phase-14-complete` tag，确保 tag 指向阶段 14 最终功能提交。
- 验证方式：文档检查、Obsidian 小节检查、全量测试、Git commit/tag 检查。
- 文档收尾要求：所有普通文档与 Obsidian 阶段知识库同步完成。
- Status: complete, pending final commit and tag

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `codex/phase-14-real-quality-calibration` |
| Previous tags | `phase-13-complete` and older phase tags remain unmoved |
| Design doc | `docs/stage14_real_quality_calibration.md` exists and documents metrics, flow, skip rules and boundaries |
| Embedding comparison | `data/evaluation/stage14_embedding_comparison.csv` records deterministic and real/skipped config rows |
| Answer coverage review | `data/evaluation/stage14_answer_coverage_review.csv` records Faithfulness, Answer Coverage, Citation Quality, risk and recommendation |
| Graceful skip | Missing or failed real API config becomes skipped/error row, not fake success or CI failure |
| Provenance readability | Decompose provenance and rerank explanation are reviewable in CSV or minimal read-only UI |
| API contract | search/vector/hybrid/chat/agent API tests pass without schema break |
| Full tests | `.venv\Scripts\python.exe -m pytest -q` passes |
| Docs | README, docs/progress, docs/architecture, docs/data_sources, AGENT.MD and Obsidian updated |
| Tag | `phase-14-complete` points to final phase 14 functionality commit |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支为 `codex/phase-14-real-quality-calibration` | 与阶段 14 目标和用户要求一致 |
| 从阶段 13 合并后的 `main` 创建阶段 14 分支 | 阶段 13 是最新稳定起点 |
| 不移动已有阶段 tag | 阶段 tag 必须稳定指向各阶段最终功能提交 |
| 保留 deterministic baseline | 自动回归必须不依赖真实 API、网络、余额和限流 |
| 真实 API 缺失时 graceful skip | 阶段 14 要评估真实能力，但不能伪造结果或阻塞本地回归 |
| Answer Coverage 先做校准表 | deterministic 回答不能证明真实语言覆盖度，需要可审阅证据 |
| provenance 先做评测可读化 | 保持 API 兼容，避免把阶段 14 变成前端重构 |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| 真实 embedding | 由 OpenAI-compatible 外部模型生成的语义向量，用于和 deterministic 向量对比 |
| deterministic baseline | 本地确定性模型结果，用于稳定回归，不代表真实模型语言质量 |
| Answer Coverage | 回答是否覆盖用户问题期望的核心技术点 |
| Faithfulness | 回答是否忠于检索资料，不引入来源外事实 |
| Citation Quality | 引用编号是否能追溯并支撑关键说法 |
| Graceful skip | 真实 API 未配置或失败时记录 skipped/error，不伪造成功、不让自动回归失败 |
| Provenance | 证据来源记录，说明某个 chunk 是由哪个 sub query 或检索路径召回的 |
| Rerank explanation | 排序原因说明，例如 topic_terms、both_match、source_type 和 final_score |

## Notes

- 本文件由 Planning with Files 维护，是阶段 14 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 14 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 6 统一补齐。
- 真实模型更适合质量校准，deterministic provider 继续负责稳定回归。
