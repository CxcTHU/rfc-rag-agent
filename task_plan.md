# Task Plan: 阶段 21 - LangGraph Agentic RAG

## Goal

在阶段 20「中文检索默认链路落地与评测判定增强」已完成、提交、创建 `phase-20-complete` tag（指向 `706047d`，非 merge）并合并到 `main`（合并提交 `8333d71`）的基础上，完成阶段 21「LangGraph Agentic RAG」：

1. 用 LangGraph 构建有状态 agentic RAG 图：retrieve → grade → rewrite/decompose → re-retrieve（硬迭代上界）→ generate（保留 citations/拒答/responsibility_gate）→ 引用自检。
2. 只用节点包裹现有 HybridSearchService / BrainService 核心能力，不重写检索内核。
3. 新能力以可配置 mode 接入，不改既有默认链路与 API 契约。
4. 用 stage19/20 中文难评测集对照 agentic vs keep_existing_hybrid baseline，按门槛诚实决策。
5. 更新文档、Obsidian，最终停在用户人工核验前：不 `git add`、不 commit、不 tag、不 push、不 PR。

核心链路：

```text
阶段 20 keep_existing_hybrid 与 p@1=0.133 瓶颈
-> LangGraph 状态图 retrieve（包裹 hybrid）
-> grade（evidence confidence 评估证据是否覆盖答案要点）
-> 不足则 rewrite/decompose 后 re-retrieve（硬迭代上界 MAX_ITERATIONS=3）
-> generate（保留 citations/拒答/responsibility_gate）
-> 引用自检
-> agentic vs baseline 评测与门槛驱动接入决策
-> 停在人工核验待提交状态
```

## Boundaries

- 用 LangGraph 重构 agentic 编排，但只用节点包裹现有检索/Brain 服务，不重写能跑通的检索内核。
- 新能力以可配置 mode 接入，不改既有默认链路与 API 契约。
- 迭代必须有硬上界防死循环。
- 不做写入型 Agent 工具、不做登录系统、不做部署优化、不新增爬虫。
- 不让真实 API 成为 CI 或本地全量测试前提（图须用 deterministic provider 跑通测试）。
- HyDE 仍只做离线实验。
- 不得把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。

## Current Phase

Phase 13: complete (human verification pending).

## Phases

### Phase 0: 启动校准

- [x] 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/stage20_default_chain_and_eval_upgrade.md、docs/phase_reviews/phase-20.md、task_plan.md、findings.md、progress.md。
- [x] 确认 phase-20-complete tag 和 main 状态正确。
- [x] 从 main 创建 `claude/phase-21-langgraph-agentic-rag` 分支。
- [x] 编写 task_plan.md、findings.md、progress.md。
- 验证：三文件就位，分支正确。
- Status: complete

### Phase 1: 设计文档

- [ ] 编写 `docs/stage21_langgraph_agentic_rag.md`。
- [ ] 内容：目标、状态 schema、节点图、迭代上界设计、确定性可测性、安全边界、接入门槛、完成标准。
- 验证：设计文档完整，覆盖所有完成标准中要求的内容。
- Status: complete

### Phase 2: 依赖引入与状态图骨架

- [ ] pyproject.toml 加 `langgraph` 依赖（含 `langchain-core` 最小依赖）。
- [ ] `pip install -e ".[dev]"` 验证安装。
- [ ] 新建 `app/services/agentic/` 模块（`__init__.py`, `state.py`, `graph.py`, `nodes.py`）。
- [ ] 实现 `AgenticState` TypedDict。
- [ ] 实现空节点函数骨架。
- [ ] 构建 `StateGraph` 并编译。
- 验证：依赖安装成功，骨架可导入，基础测试通过。
- Status: complete

### Phase 3: retrieve 节点

- [x] 实现 retrieve 节点，包裹 `HybridSearchService` + `decompose_query`。
- [x] 首次检索结果写入 `AgenticState`。
- [x] 补测试：deterministic provider 下 retrieve 节点单独跑通。
- 验证：测试通过。
- Status: complete

### Phase 4: grade 节点

- [x] 实现 grade 节点，复用 `evaluate_evidence_confidence()` + `has_topic_anchor()`。
- [x] 输出 evidence_sufficient (bool) + confidence_score 到 state。
- [x] 条件边：sufficient → generate，insufficient → rewrite。
- [x] 补测试：覆盖 sufficient/insufficient 两条路径。
- 验证：测试通过。
- Status: complete

### Phase 5: rewrite/decompose + re-retrieve 迭代（含硬上界）

- [x] 实现 rewrite 节点：query reformulation。
- [x] re-retrieve 节点：用改写后 query 重新检索，合并去重。
- [x] 硬上界 `MAX_ITERATIONS = 3`，超过直接走 generate。
- [x] 条件边完善：re-retrieve → grade → (sufficient → generate | insufficient → rewrite | max → generate)。
- [x] 补测试：强制验证硬上界——3 次迭代后必须终止。
- 验证：迭代上界测试通过。
- Status: complete

### Phase 6: generate 节点（保留 citations/拒答/responsibility_gate）

- [x] 实现 generate 节点，复用 `evaluate_responsibility_gate()`, `build_rag_prompt()`, chat model generate, `extract_citations()`。
- [x] responsibility_gate 在 generate 前执行。
- [x] 空结果拒答、低证据拒答保持不变。
- [x] 补测试：责任题拒答、off-topic 拒答、正常题生成+引用。
- 验证：测试通过。
- Status: complete

### Phase 7: citation_check 节点

- [x] 实现 citation_check 节点：验证引用对应有效 source。
- [x] 无效引用标记到 state，不阻断。
- [x] 补测试。
- 验证：测试通过。
- Status: complete

### Phase 8: 端到端整合与 API 接入

- [ ] 完整状态图端到端跑通（deterministic provider）。
- [ ] 新增 `agentic` retrieval mode 或独立 endpoint。
- [ ] 确保既有 API 不受影响。
- [ ] 端到端测试 + 全部既有 API 测试通过。
- 验证：聚焦回归通过。
- Status: complete

### Phase 9: Agentic vs Baseline 评测

- [ ] 用 stage19_chinese_hard_queries.csv 对照评测。
- [ ] baseline: keep_existing_hybrid (BrainService 默认链路)。
- [ ] agentic: LangGraph 状态图。
- [ ] 指标：coverage_ratio, p@1, deep_top1。
- [ ] 门槛判断（Δp@1≥0.10 AND Δdeep_top1≥0.20 AND refusal not degraded）。
- [ ] 诚实决策：达标接入新 mode，未达标保留候选并写明阻断原因。
- 验证：评测脚本产出对比 CSV，决策清晰。
- Status: complete (eval ran; decision=inconclusive_high_error_rate due to SSL errors; eval script fixed to exclude errored rows)

### Phase 10: 回归验证 + quality gate

- [ ] 全量 `pytest -q` 通过（>= 424 existing + new tests）。
- [ ] 既有测试文件无破坏。
- [ ] quality gate 检查。
- 验证：全量测试通过。
- Status: complete (449 passed in 32s, >= 424 baseline + 25 new)

### Phase 11: 文档同步

- [ ] 更新 README.md。
- [ ] 更新 docs/progress.md。
- [ ] 更新 docs/architecture.md。
- [ ] 更新 docs/data_sources.md。
- [ ] 更新 AGENT.MD。
- 验证：文档反映阶段 21 完成状态。
- Status: complete (README, docs/progress, docs/architecture, docs/data_sources, AGENT.MD all updated)

### Phase 12: Obsidian 收尾

- [ ] 建立 obsidian-vault/阶段汇报/阶段 21 - LangGraph Agentic RAG/。
- [ ] Phase 0 到最终 Phase 小汇报（10 项模板）。
- [ ] 阶段 21 Phase 汇报索引。
- [ ] 更新 obsidian-vault/阶段汇报索引.md、阶段索引.md、首页.md。
- [ ] 建立 obsidian-vault/阶段/阶段 21 - LangGraph Agentic RAG.md。
- 验证：Obsidian 完整，gitignored。
- Status: complete (14 phase reports + index + stage page + global indexes updated)

### Phase 13: 人工核验待提交状态

- [ ] 确认未执行 git add / commit / tag / push。
- [ ] 最终汇报。
- 验证：git status 确认无 staged 变更。
- Status: complete (git status clean, no add/commit/tag/push)

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `claude/phase-21-langgraph-agentic-rag` |
| Previous tag | `phase-20-complete -> 706047d` unchanged |
| Baseline | `main` contains `8333d71 Merge phase 20` |
| No submit actions | no add/commit/tag/push/PR |
| Design doc | `docs/stage21_langgraph_agentic_rag.md` |
| LangGraph dep | `langgraph` in pyproject.toml |
| Agentic graph | `app/services/agentic/` with state, nodes, graph |
| Deterministic test | graph runnable with deterministic providers |
| Hard iteration cap | MAX_ITERATIONS=3 with test enforcement |
| Citations/refusal/gate | preserved behavior with test coverage |
| Eval comparison | agentic vs baseline CSV with honest decision |
| API contract | search/vector/hybrid/chat/agent + /quality-report compatible |
| Tests | full suite passes (>= 424 + new) |
| Docs | README/progress/architecture/data_sources/AGENT synced |
| Obsidian | local phase 21 reports completed and gitignored |
| Final state | waiting for user manual verification |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| LangGraph | 基于 langchain-core 的状态图编排框架，用 TypedDict 定义状态，节点读/写状态，条件边决定分支 |
| Agentic RAG | 带自纠正循环的 RAG：检索 → 评估证据 → 不足则改写查询重检索 → 生成 → 自检，迭代直到满意或达上界 |
| AgenticState | LangGraph 状态图的 TypedDict，记录 question、results、iteration_count、evidence_sufficient 等 |
| StateGraph | LangGraph 的有向图类型，节点是函数，边是条件分支 |
| CompiledGraph | StateGraph 编译后的可执行对象，可 `.invoke()` 或 `.stream()` |
| 硬迭代上界 | MAX_ITERATIONS=3，防止检索-评估-改写循环无限执行 |
| coverage_ratio | 答案要点覆盖率，用 expected_answer_points 衡量 top-1 证据覆盖多少期望要点 |
| p@1 | precision@1，top-1 结果是否覆盖答案要点（coverage_ratio >= 阈值则 hit=1） |
| deep_top1 | deep_fulltext_top1_rate，top-1 结果来自深度全文来源（非题录卡片）的比率 |
| responsibility_gate | 工程责任边界拒答门，阻止系统替代规范审查、工程判定、专家签字 |
| evidence_confidence | 证据置信度评估，查询词与检索证据的覆盖率 + 主题锚点判断 |

## Notes

- 本文件由 Planning with Files 维护，是阶段 21 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 task_plan.md、findings.md、progress.md。
- 开发过程中暂不写入 Obsidian 小 Phase 汇报；全部开发、测试、普通文档完成后 Phase 12 统一补齐。
- 阶段 21 收尾后必须停在用户人工核验前，不提交、不打 tag、不推送。
