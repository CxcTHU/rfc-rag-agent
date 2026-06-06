# Task Plan: 阶段 11 - 真实用户问题评测集与跨语言质量提升

## Goal

在阶段 10 已完成并合并到 `main` 的基础上，完成阶段 11：真实用户问题评测集与跨语言质量提升。

本阶段不做登录系统、不做部署优化、不做大规模前端重构、不做写入型 Agent 工具。重点是扩大真实用户问题评测集，记录语言类型、期望来源、拒答和回答覆盖点，并用可解释的跨语言 query expansion / 主题词增强继续提升检索与问答质量。

核心链路：

```text
已有 sources/documents/chunks/embeddings
-> 扩大真实用户问题评测集
-> 标注期望来源、拒答、覆盖点和语言类型
-> deterministic baseline 与真实 MIMO + Jina 校准结果分离
-> 跨语言 query expansion / 主题词增强
-> 人工审阅抽样或 LLM-as-judge 评测设计
-> 指标对比、质量结论和下一阶段依据
```

## Current Phase

Phase 6 complete。阶段 11 已新增用户问题集、用户问题评测脚本、跨语言 query expansion 增强、人工审阅计划和离线审阅抽样表，并完成 deterministic 回归验证、普通文档、Obsidian、最终测试、提交和 tag 收尾。

## Phases

### Phase 0: 阶段启动与规划校准

- [x] 将线程标题修改为 `阶段11-真实用户问题评测集与跨语言质量提升`。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/evaluation_plan.md`、`docs/agent_design.md`、`docs/brain_workflow_design.md`、`docs/model_provider_evaluation.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其为阶段 10 工作记忆。
- [x] 确认阶段 10 已合并到 `main`，当前 `main` 最新提交为 `c0bf8d6 merge phase 10 rag quality calibration`。
- [x] 确认 `phase-10-complete` 指向阶段 10 最终功能提交 `1454919`，不移动已有阶段 tag。
- [x] 从阶段 10 合并后的 `main` 创建并切换到 `codex/phase-11-user-evaluation-query-expansion`。
- [x] 使用 Planning with Files 校准阶段 11 的三份记忆文件。
- [x] 运行阶段 11 起点全量测试。
- 验证方式：线程标题、Git 分支/tag 检查、规划文件检查、起点全量测试。
- 文档收尾要求：记录阶段起点、已确认 tag、当前分支、文档口径差和基线测试。
- Status: complete

### Phase 1: 真实用户问题评测集设计与落地

- [x] 新增 `data/evaluation/user_questions.csv`。
- [x] 覆盖中文口语问法、英文问题、中英混合术语、工程应用场景和 unsupported 问题。
- [x] 每条问题记录 `query_id`、`question`、`language_type`、`expected_source_hit`、`expected_refused`、`expected_answer_points` 和 `notes`。
- [x] 同时记录自动评测所需的 `top_k`、`retrieval_mode`、期望标题词、期望正文词和禁止词。
- [x] 新增测试校验 CSV schema、语言类型覆盖和 unsupported 样例。
- 验证方式：CSV schema 测试通过；人工检查问题覆盖面。
- 文档收尾要求：在 `findings.md` 和 `progress.md` 记录问题集设计、字段含义和覆盖范围。
- Status: complete

### Phase 2: 用户问题评测脚本与指标输出

- [x] 新增 `scripts/evaluate_user_questions.py`，复用 Brain workflow、deterministic provider 和现有 source/citation 检查逻辑。
- [x] 输出 `data/evaluation/user_question_results.csv`。
- [x] 结果包含通过率、失败原因、拒答匹配、来源命中、引用有效性、语言类型和配置名。
- [x] 支持比较 `default_hybrid`、`keyword_baseline`、`vector_only`，但不让自动回归依赖真实 API key。
- [x] 新增脚本测试，覆盖读取、评测、失败原因和 CSV 字段。
- 验证方式：脚本测试通过；脚本可稳定输出用户问题评测结果。
- 文档收尾要求：记录用户问题评测流程、指标口径和与阶段 10 baseline 的关系。
- Status: complete

### Phase 3: 跨语言 Query Expansion 与主题词增强

- [x] 复核阶段 10 剩余 deterministic vector 失败和新增用户问题中的跨语言术语 gap。
- [x] 扩展 `keyword_search.SYNONYM_RULES`，覆盖 ITZ/界面、creep/徐变、freeze-thaw/抗冻、porosity/孔隙率、emission/碳排放、steel fiber/钢纤维、rock shear key/剪力键等工程术语。
- [x] 保持 query expansion 可解释，并继续被 keyword search 与 vector topic anchor 复用。
- [x] 增强 Brain evidence confidence，使中文问题也能利用扩展后的英文证据词判断是否有足够证据。
- [x] 不改变 `/search`、`/search/vector`、`/search/hybrid`、`/chat`、`/agent/query` 的 API schema。
- [x] 补充检索和 Brain workflow 相关测试。
- 验证方式：关键词/向量/混合检索相关测试通过；用户问题评测指标不退化。
- 文档收尾要求：解释 query expansion、跨语言术语 gap、主题词增强在本项目中的位置。
- Status: complete

### Phase 4: 人工审阅抽样与 LLM-as-judge 离线设计

- [x] 新增 `docs/stage11_user_evaluation_plan.md`，说明人工审阅和 LLM-as-judge 的边界。
- [x] 新增最小离线审阅表 `data/evaluation/user_question_review_samples.csv`。
- [x] 记录 `expected_answer_points`、`faithfulness`、`answer_coverage`、`citation_quality` 和 `reviewer_notes` 字段。
- [x] 明确真实模型评测可用于发布前校准，但不能成为 CI 或自动回归前提。
- [x] 新增文档和数据 schema 测试，确认不保存真实 API key 或受限全文。
- 验证方式：文档测试和数据 schema 测试通过。
- 文档收尾要求：记录人工审阅与自动评测的分工。
- Status: complete

### Phase 5: 回归验证与阶段 11 质量结论

- [x] 复跑 keyword、vector、hybrid、chat、agent、Brain workflow deterministic 评测。
- [x] 运行新增用户问题评测。
- [x] 复跑 API 回归测试，确认 search/vector/hybrid/chat/agent API 不被破坏。
- [x] 运行全量测试。
- [x] 记录阶段 11 指标、失败项、残留风险和下一阶段建议。
- 验证方式：评测脚本输出、API 测试、全量测试。
- 文档收尾要求：把指标对比和质量结论写入普通文档和 Obsidian 准备材料。
- Status: complete

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag

- [x] 更新 `README.md`，说明阶段 11 新增用户问题评测集、跨语言增强、评测结果和下一阶段建议。
- [x] 更新 `docs/progress.md`，记录完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充用户问题评测和 query expansion 数据流。
- [x] 更新 `docs/data_sources.md`，说明阶段 11 评测产物不新增资料来源、不保存真实模型密钥或受限全文。
- [x] 判断并更新 `AGENT.MD`，把后续起点校准到阶段 11 完成后的下一步。
- [x] 统一补齐 Obsidian 本地知识库：阶段 11 阶段页、阶段汇报目录、Phase 0-6 汇报、索引、分类页和知识点。
- [x] 确认 Obsidian 仍由 Git 忽略，不纳入提交。
- [x] 复跑最终全量测试和关键阶段评测。
- [x] 创建阶段最终功能提交。
- [x] 创建 `phase-11-complete` tag，确保 tag 指向阶段 11 最终功能提交。
- 验证方式：文档检查、Obsidian 10 项模板检查、全量测试、Git commit/tag 检查。
- 文档收尾要求：所有普通文档与 Obsidian 阶段知识库同步完成。
- Status: complete

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `codex/phase-11-user-evaluation-query-expansion` |
| Previous tags | `phase-10-complete` and older phase tags remain unmoved |
| User question set | `data/evaluation/user_questions.csv` exists and covers required language/scenario types |
| User evaluation | `scripts/evaluate_user_questions.py` writes `data/evaluation/user_question_results.csv` |
| Query expansion | Cross-language terms are explainable and tested |
| Review design | Manual/LLM-as-judge offline review doc and sample table exist |
| Deterministic baseline | Existing keyword/vector/hybrid/chat/agent/Brain evaluations remain runnable |
| API contract | search/vector/hybrid/chat/agent API tests pass |
| Full tests | `.venv\Scripts\python.exe -m pytest -q` passes |
| Docs | README, docs/progress, docs/architecture, docs/data_sources, AGENT.MD and Obsidian updated |
| Tag | `phase-11-complete` points to final phase 11 functionality commit |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支为 `codex/phase-11-user-evaluation-query-expansion` | 与阶段目标和用户要求一致 |
| 从阶段 10 合并后的 `main` 创建阶段 11 分支 | 阶段 10 是最新稳定起点 |
| 不移动既有阶段 tag | 阶段 tag 必须稳定指向各阶段最终提交 |
| 新增独立用户问题评测集 | 不污染阶段 10 baseline，同时扩大真实使用场景 |
| 继续使用 deterministic 自动回归 | 避免真实 API key、网络、限流和余额成为测试前提 |
| 跨语言增强复用 `SYNONYM_RULES` | keyword search 和 vector topic anchor 已共用该词表，最小改动即可覆盖两条链路 |
| 人工审阅与 LLM-as-judge 先做离线设计 | 先建立质量字段和抽样表，不让自动测试依赖真实模型裁判 |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| 真实用户问题评测集 | 更接近真实提问方式的一组问题，用来检验系统能否处理口语、英文、中英混合和工程场景 |
| language_type | 记录问题语言形态，例如中文口语、英文、中英混合、工程中文、unsupported |
| expected_answer_points | 期望回答覆盖的关键点，用于人工审阅或 LLM-as-judge |
| Query Expansion | 把用户问题中的术语扩展成中英文同义词，提高召回概率 |
| 跨语言术语 gap | 用户用中文问、资料用英文写，或反过来时产生的召回缺口 |
| LLM-as-judge | 用模型做质量裁判；本阶段只做离线设计，不作为自动回归前提 |
| Faithfulness | 回答是否忠实于检索来源，没有引入资料外事实 |
| Answer Coverage | 回答是否覆盖期望技术要点 |
| Citation Quality | 引用是否能支持回答中的关键说法 |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| expected_source_hit=no 时空期望被误判为命中 | 初次用户问题评测暴露 unsupported 边界问题 | 已修正脚本，只在存在期望标题词或正文词时计算实际来源命中 |

## Notes

- 本文件由 Planning with Files 维护，是阶段 11 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 11 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 6 统一补齐。
- 真实模型更适合最终质量校准，deterministic provider 更适合稳定回归。阶段 11 继续保持两者分离。
