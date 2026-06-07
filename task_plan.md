# Task Plan: 阶段 13 - Decompose 与证据合并

## Goal

在阶段 12 已完成并合并到 `main` 的基础上，完成阶段 13：规则式 Decompose、子 query 检索、证据合并、按 `chunk_id` 去重和可解释 rerank。

本阶段不做登录系统、不做部署优化、不做写入型 Agent 工具、不把 HyDE 接入默认链路、不引入复杂长期记忆系统。重点是把阶段 12 的质量审阅结论转化为可运行、可评测、可解释的检索增强能力。

核心链路：

```text
原始问题
-> 规则式 Decompose
-> 最多 3 个子 query
-> 每个子 query 使用 keyword/vector/hybrid 检索
-> 合并候选证据
-> 按 chunk_id 去重
-> 保留 sub_query provenance
-> 基于来源标题、主题词、source_type、分数和 both-match 信号 rerank
-> Brain generate_answer
-> 引用和来源继续可追溯
```

## Current Phase

Phase 6 complete。阶段 13 已完成启动校准、Decompose 设计固化、服务实现、Brain 集成、阶段 13 评测、更广回归、普通文档、Obsidian 本地知识库、最终全量验证、最终提交与 `phase-13-complete` tag 收尾。

## Phases

### Phase 0: 阶段启动与规划校准

- [x] 将线程标题修改为 `阶段13-Decompose与证据合并`。
- [x] 阅读 Planning with Files 技能说明。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage12_quality_review.md`、`docs/stage13_decompose_plan.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其为阶段 12 工作记忆。
- [x] 确认阶段 12 已合并到 `main`，当前 `main` 最新提交为 `5c7bb58 merge phase 12 quality review context calibration`。
- [x] 确认 `phase-12-complete` 指向阶段 12 最终功能提交 `d7b5bff`，不移动已有阶段 tag。
- [x] 从阶段 12 合并后的 `main` 创建并切换到 `codex/phase-13-decompose-evidence-merge`。
- [x] 使用 Planning with Files 校准阶段 13 的三份记忆文件。
- [x] 运行阶段 13 起点全量测试。
- 验证方式：线程标题、Git 分支/tag 检查、规划文件检查、起点全量测试。
- 文档收尾要求：记录阶段起点、已确认 tag、当前分支、阶段 12 遗留问题和基线测试。
- Status: complete

### Phase 1: Decompose 设计固化与测试输入校准

- [x] 更新 `docs/stage13_decompose_plan.md`，从预研计划升级为阶段 13 设计文档。
- [x] 明确规则式拆解的触发条件、最多 3 个子 query、unsupported 保护和不拆解边界。
- [x] 明确 sub_query provenance、候选合并、`chunk_id` 去重和可解释 rerank 的数据结构。
- [x] 复核 `data/evaluation/user_questions.csv` 中 5 个优先问题和 unsupported 样例。
- [x] 新增或更新阶段 13 设计测试，校验文档包含规则、边界、指标和 HyDE 限制。
- 验证方式：文档/CSV schema 测试。
- 文档收尾要求：在 `findings.md` 记录设计决策、风险和新词解释。
- Status: complete

### Phase 2: 规则式 Decompose 与证据合并服务

- [x] 新增 Decompose/merge 相关 service，或在 retrieval/brain 层按现有边界实现。
- [x] 实现明显并列结构拆解，例如“成本、工期和碳排放”“填充性和强度”“冻融和抗渗”。
- [x] 限制子 query 最多 3 个，并避免对乱字符串或 unsupported 问题强行拆解。
- [x] 为每个子 query 运行指定 retrieval mode 的检索。
- [x] 合并候选、按 `chunk_id` 去重并记录命中该 chunk 的 sub queries。
- [x] 实现可解释 rerank，考虑主题词命中、source_type、原始分数和 hybrid both-match 信号。
- [x] 补充 service 单元测试，覆盖拆解、去重、provenance、rerank 和 unsupported 边界。
- 验证方式：阶段 13 service 测试和既有 retrieval 单元测试。
- 文档收尾要求：在 `findings.md` 记录核心类名、数据流和失败保护。
- Status: complete

### Phase 3: Brain 集成与 API 兼容回归

- [x] 在 Brain workflow 中接入 Decompose 检索路径，保持旧请求默认兼容。
- [x] 保留 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer` 的外部语义。
- [x] 继续复用阶段 11 `SYNONYM_RULES` 和 Brain evidence confidence。
- [x] 确认 `/chat` 与 Agent `answer_with_citations` 共享新路径或兼容配置。
- [x] 确认 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 不被破坏。
- [x] 补充 Brain/chat/agent/API 回归测试。
- 验证方式：Brain、chat、agent、search API 相关测试。
- 文档收尾要求：记录 API 兼容性和不做 schema 破坏的原因。
- Status: complete

### Phase 4: 阶段 13 评测脚本与质量校准

- [x] 新增阶段 13 评测脚本或扩展现有 user question / brain workflow 评测。
- [x] 输出每个复杂问题的子 query、召回来源、去重结果、rerank 解释和通过状态。
- [x] 优先验证 `user_mixed_cost_emission`、`user_cn_colloquial_compactness`、`user_cn_porosity_compression`、`user_en_freeze_thaw`、`user_cn_creep`。
- [x] 检查 default_hybrid 不退化，unsupported 不被误拆解成可回答问题。
- [x] 保留 vector-only 失败边界，不用静默 fallback 掩盖。
- [x] 生成 `data/evaluation/stage13_decompose_results.csv` 或等价评测产物。
- 验证方式：评测脚本运行、评测脚本测试、关键回归脚本。
- 文档收尾要求：在 `progress.md` 记录指标、失败项和质量结论。
- Status: complete

### Phase 5: 回归验证与前端最小可见性判断

- [x] 复跑用户问题、chat、agent、Brain workflow deterministic 评测。
- [x] 复跑 search/vector/hybrid/chat/agent API 回归测试。
- [x] 判断前端是否需要最小展示 Decompose/检索说明；如需要，只做小范围展示，不做前端重构。
- [x] 运行阶段 13 相关聚焦测试和较大范围回归。
- 验证方式：评测脚本输出、API/核心测试、必要时前端 smoke 测试。
- 文档收尾要求：记录是否改前端、为什么，以及验证结果。
- Status: complete

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag

- [x] 更新 `README.md`，说明阶段 13 能力、评测结果、使用边界和下一阶段建议。
- [x] 更新 `docs/progress.md`，记录完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充 Decompose、子 query 检索、证据合并和 provenance 数据流。
- [x] 更新 `docs/data_sources.md`，说明阶段 13 只新增评测/设计产物，不新增文献来源、不保存受限全文或 API key。
- [x] 判断并更新 `AGENT.MD`，把后续起点校准到阶段 13 完成后的下一步。
- [x] 统一补齐 Obsidian 本地知识库：阶段 13 阶段页、阶段汇报目录、Phase 0 到最终 Phase 汇报、索引、分类页和知识点。
- [x] 确认每篇 Obsidian Phase 汇报包含 10 个固定小节。
- [x] 确认 `obsidian-vault/` 仍被 Git 忽略，不纳入提交。
- [x] 复跑最终全量测试和关键阶段评测。
- [x] 创建阶段最终功能提交。
- [x] 创建 `phase-13-complete` tag，确保 tag 指向阶段 13 最终功能提交。
- 验证方式：文档检查、Obsidian 小节检查、全量测试、Git commit/tag 检查。
- 文档收尾要求：所有普通文档与 Obsidian 阶段知识库同步完成。
- Status: complete

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `codex/phase-13-decompose-evidence-merge` |
| Previous tags | `phase-12-complete` and older phase tags remain unmoved |
| Design doc | Decompose design documents rules, boundaries, data flow, metrics, failure protection |
| Decompose | Rule-based decomposition generates at most 3 sub queries |
| Unsupported | Unsupported/random questions are not forced into answerable sub queries |
| Merge | Sub query retrieval results merge, deduplicate by `chunk_id`, and preserve provenance |
| Rerank | Rerank is explainable and considers topic terms, source_type, score, both-match signal |
| Brain | Brain answer path can consume merged evidence without bypassing evidence confidence |
| API contract | search/vector/hybrid/chat/agent API tests pass without schema break |
| Evaluation | Stage 13 evaluation records complex question coverage, source hit, refusal quality, no regression |
| Full tests | `.venv\Scripts\python.exe -m pytest -q` passes |
| Docs | README, docs/progress, docs/architecture, docs/data_sources, AGENT.MD and Obsidian updated |
| Tag | `phase-13-complete` points to final phase 13 functionality commit |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支为 `codex/phase-13-decompose-evidence-merge` | 与阶段目标和用户要求一致 |
| 从阶段 12 合并后的 `main` 创建阶段 13 分支 | 阶段 12 是最新稳定起点 |
| 不移动既有阶段 tag | 阶段 tag 必须稳定指向各阶段最终功能提交 |
| 先固化设计，再实现服务 | Decompose 会影响 Brain 检索证据，需要先明确边界 |
| 子 query 最多 3 个 | 控制检索成本和证据噪声，符合阶段 13 初始边界 |
| 规则式拆解优先 | 不依赖真实模型，便于 deterministic 自动回归 |
| HyDE 不进入默认链路 | 避免假想答案污染引用边界 |
| 保留 vector-only 失败边界 | 不用静默 fallback 掩盖 baseline 问题，保持评测诚实 |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| Decompose | 把一个复杂问题拆成多个子 query 分别检索 |
| Sub query | 从原始问题拆出的子问题，例如“成本评估”“工期评估”“碳排放评估” |
| Evidence merge | 把多个子 query 的召回片段合并成一组回答证据 |
| Deduplicate by chunk_id | 用 chunk 的数据库编号去重，避免同一片段重复进入上下文 |
| Provenance | 证据来源记录，说明某个 chunk 是由哪个 sub query 召回的 |
| Rerank | 对初步召回证据重新排序，让更贴题、更可信的片段排前面 |
| Both-match signal | hybrid 中同一 chunk 同时被关键词和向量命中的稳定信号 |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| Brain `default_hybrid` 一度从 6/6 退到 5/6 | Phase 3 初次接入时先执行 Decompose 服务再判断是否拆解，单主题问题多跑了一轮不必要检索 | 改为先调用轻量 `decompose_query()` 判断，只有真正 decomposed 时才执行子 query 检索；Brain workflow 恢复 18/18 |

## Notes

- 本文件由 Planning with Files 维护，是阶段 13 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 13 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 6 统一补齐。
- 真实模型更适合最终质量校准，deterministic provider 继续负责稳定回归。
