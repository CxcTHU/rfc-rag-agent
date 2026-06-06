# Task Plan: 阶段 10 - 真实 RAG 质量校准与拒答边界优化

## Goal

在阶段 9.1 已完成并合并到 `main` 的基础上，完成阶段 10：真实 RAG 质量校准与拒答边界优化。

本阶段不新增模型 provider、不做复杂 Agent 工具调用、不做登录系统、不做部署优化、不做大规模前端重构。重点是复核真实模型暴露的失败案例，并用可解释、可复现的方式提升检索质量、问答质量和拒答边界。

核心链路：

```text
已有 documents/chunks/sources/embeddings
-> 真实 RAG 失败案例分析
-> 检索证据置信度与低证据拒答
-> vector-only 误召回优化
-> deterministic 与真实模型指标对比
-> 文档、Obsidian、提交和阶段 tag 收尾
```

## Current Phase

Phase 6 complete。阶段 10 的代码开发、失败分析、确定性回归、真实 MIMO + Jina 校准验证、普通文档、Obsidian、最终全量测试、提交准备和 `phase-10-complete` tag 收尾均已完成。

## Phases

### Phase 0: 阶段启动与规划校准

- [x] 将线程标题修改为 `阶段10-真实RAG质量校准与拒答边界优化`。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/evaluation_plan.md`、`docs/agent_design.md`、`docs/brain_workflow_design.md`、`docs/model_provider_evaluation.md`。
- [x] 接管旧 `task_plan.md`、`findings.md`、`progress.md`，确认其为阶段 9 工作记忆。
- [x] 确认阶段 9 与阶段 9.1 已完成并合并到 `main`。
- [x] 确认 `phase-9-complete` 与 `phase-9.1-complete` 指向对应阶段最终提交，不移动已有 tag。
- [x] 从阶段 9.1 合并后的 `main` 创建并切换到 `codex/phase-10-rag-quality-calibration`。
- [x] 使用 Planning with Files 校准三份阶段记忆文件。
- [x] 运行阶段 10 起点全量测试。
- 验证方式：线程标题工具结果、Git 分支与 tag 检查、规划文件检查、起点全量测试。
- 文档收尾要求：记录阶段起点、已确认 tag、当前分支和基线测试。
- Status: complete

### Phase 1: 真实 RAG 失败案例复核与质量诊断

- [x] 复核阶段 9.1 的 `mimo_jina_brain_workflow_results.csv` 失败项。
- [x] 复核 Jina vector 的历史失败项 `mesoscopic_modeling`。
- [x] 新增失败案例分析脚本与 CSV。
- [x] 区分 unsupported 低证据拒答问题、vector-only topic drift 问题、跨语言术语 gap 问题。
- 验证方式：`scripts/analyze_real_rag_failures.py` 可稳定生成 `data/evaluation/real_rag_failure_cases.csv`；对应测试通过。
- 文档收尾要求：把失败根因、改进方向和关键结论写入 `findings.md`、`progress.md`。
- Status: complete

### Phase 2: 检索证据置信度与低证据拒答

- [x] 设计可解释的 evidence confidence 规则。
- [x] 在 Brain 生成答案前加入 query-token coverage 检查。
- [x] 对完全无有效词重叠的 unsupported query 直接拒答。
- [x] 保持 `/search`、`/search/vector`、`/search/hybrid` schema 不变。
- [x] 覆盖正常问题不误拒、低证据问题拒答、Brain 共享链路生效的测试。
- 验证方式：Brain workflow/service/chat/agent 相关测试通过，确定性 Brain workflow unsupported 项被修复。
- 文档收尾要求：解释 Evidence Confidence、低证据拒答、query-token 覆盖率。
- Status: complete

### Phase 3: vector-only 误召回优化

- [x] 针对 filling capacity 与 mesoscopic modeling 诊断结果选择最小可解释优化。
- [x] 在 vector search 候选内部新增 topic anchor rerank。
- [x] 复用现有 keyword expansion 领域词表，不把 vector-only 静默改成 hybrid。
- [x] 保留向量 cosine score 作为响应字段，topic anchor 只参与排序。
- [x] 通过测试与评测确认 hybrid/keyword baseline 不退化。
- 验证方式：vector/hybrid/Brain workflow 评测、vector rerank 单元测试。
- 文档收尾要求：说明 topic anchor rerank 在 RAG 链路的位置、作用和限制。
- Status: complete

### Phase 4: 评测脚本与指标对比增强

- [x] 增强 `scripts/evaluate_model_configs.py`，输出 `failed` 与 `pass_rate`。
- [x] 更新 model config 相关测试。
- [x] 保留 deterministic baseline、Jina vector/hybrid baseline 和真实 MIMO + Jina 单独评测入口。
- [x] 确认真实配置缺失或结果目录缺失时不会破坏 deterministic 测试。
- 验证方式：model config 测试通过，汇总 CSV 能直接展示 passed/failed/pass_rate。
- 文档收尾要求：记录 deterministic 与真实配置的对比方式。
- Status: complete

### Phase 5: 回归验证与阶段 10 质量结论

- [x] 复跑 deterministic chat、agent、Brain workflow、model config 评测。
- [x] 复跑 deterministic vector 与 hybrid 评测。
- [x] 运行 API 回归测试，确认 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 不被破坏。
- [x] 运行全量测试。
- [x] 根据用户关于真实模型的判断，单独复跑阶段 10 真实 Jina / MIMO + Jina 校准评测。
- [x] 记录阶段 10 质量结论、残留风险和下一阶段建议。
- 验证方式：评测脚本输出、API 测试、全量测试、真实模型单独 CSV。
- 文档收尾要求：把确定性回归与真实模型校准结论写入普通文档和 Obsidian。
- Status: complete

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag

- [x] 更新 `README.md`，说明阶段 10 的质量保护、拒答边界、评测结果和默认建议。
- [x] 更新 `docs/progress.md`，记录完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充 evidence confidence、low-evidence refusal、topic anchor rerank 数据流。
- [x] 更新 `docs/data_sources.md`，说明阶段 10 评测产物不新增资料来源、不保存真实模型密钥。
- [x] 判断并更新 `AGENT.MD`，把后续起点校准到阶段 10 完成后的下一步。
- [x] 统一补齐 Obsidian 本地知识库：阶段页、阶段汇报目录、Phase 0-6 汇报、索引、分类页和知识点。
- [x] 复跑最终全量测试和关键阶段评测。
- [x] 创建阶段最终功能提交。
- [x] 创建 `phase-10-complete` tag，确保 tag 指向阶段 10 最终功能提交。
- 验证方式：文档检查、Obsidian 10 项模板检查、全量测试、Git commit/tag 检查。
- 文档收尾要求：所有普通文档与 Obsidian 阶段知识库同步完成。
- Status: complete

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `codex/phase-10-rag-quality-calibration` |
| Previous tags | `phase-9-complete` and `phase-9.1-complete` remain unmoved |
| Failure analysis | `data/evaluation/real_rag_failure_cases.csv` records real RAG failure modes |
| Unsupported refusal | Brain refuses low-evidence unsupported questions before model generation |
| Vector-only quality | Topic anchor rerank improves vector-only without changing API schema |
| Deterministic evaluation | vector 13/15, hybrid 15/15, chat 6/6, agent 5/5, Brain workflow 18/18 |
| Real model calibration | Jina vector 15/15, Jina hybrid 15/15, MIMO + Jina chat 6/6, agent 5/5, Brain workflow 18/18 |
| API contract | search/vector/hybrid/chat/agent API tests pass |
| Full tests | `.venv\Scripts\python.exe -m pytest -q` passes |
| Docs | README, docs/progress, docs/architecture, docs/data_sources, AGENT.MD and Obsidian updated |
| Tag | `phase-10-complete` points to final phase 10 functionality commit |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支为 `codex/phase-10-rag-quality-calibration` | 与阶段目标和用户要求一致 |
| 从阶段 9.1 合并后的 `main` 创建阶段 10 分支 | 阶段 9.1 是最新稳定起点 |
| 不移动既有阶段 tag | 阶段 tag 必须稳定指向各阶段最终提交 |
| 低证据拒答放在 Brain 生成前 | `/chat` 与 Agent 引用问答共享 Brain workflow，一处修复覆盖多个入口 |
| 不把 vector-only 静默 fallback 到 hybrid | vector-only 是评测语义和 baseline，必须可解释、可比较 |
| 自动测试默认继续使用 deterministic provider | 避免 CI/本地回归依赖真实 API key、网络、限流和余额 |
| 真实 MIMO + Jina 作为阶段 10 质量校准补充评测 | 真实模型能更贴近用户体验，但只作为单独质量结论，不替代稳定回归 |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| Evidence Confidence | 在模型生成前判断检索证据是否足够支撑回答的可解释规则 |
| Query-token 覆盖率 | 用户问题中的有效词在召回标题、heading 或片段内容中出现的比例 |
| 低证据拒答 | 检索有结果但结果与问题缺少足够关联时拒绝生成答案 |
| Topic Anchor Rerank | 在 vector 候选内部用主题关键词锚点轻量重排，降低语义漂移 |
| vector-only | 只使用向量检索的配置，用来观察语义召回能力，不能被静默替换为 hybrid |
| deterministic provider | 本项目的可复现本地模型替身，用于稳定测试与指标回归 |
| 真实模型校准 | 使用真实 ChatModel 和 EmbeddingModel 复核最终体验，但不让自动测试依赖密钥 |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| `evaluate_vector_search.py` rejected `--embedding-provider` | 使用了 chat/Brain 脚本参数 | 改用 `--provider deterministic` |
| `evaluate_hybrid_search.py` rejected `--embedding-provider` | 使用了 chat/Brain 脚本参数 | 改用 `--provider deterministic` |
| `TOPIC_ANCHOR_BOOST=0.25` regressed Brain thermal_control | 主题锚点权重过高影响 hybrid 候选排序 | 降到 `0.20`，Brain workflow 恢复 18/18 |
| PowerShell rg quoting error | 用双引号包了含引号的复杂正则 | 改用单引号和更简单的检索表达式 |

## Notes

- 本文件由 Planning with Files 维护，是阶段 10 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 10 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 6 统一补齐。
- 真实模型更适合最终质量校准，deterministic provider 更适合稳定回归。两者在阶段 10 并列使用。
