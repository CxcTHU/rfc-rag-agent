# Findings & Decisions

## Requirements

- 用户要求正式进入阶段 12：质量审阅与上下文最小补全。
- 线程标题已修改为 `阶段12-质量审阅与上下文最小补全`。
- 目标分支为 `codex/phase-12-quality-review-context-calibration`。
- 阶段 12 必须从阶段 11 已完成并合并到 `main` 的状态出发。
- 必须确认 `phase-11-complete` 指向阶段 11 最终功能提交，不移动已有阶段 tag。
- 阶段 12 不做登录系统、不做部署优化、不做复杂 LangGraph workflow、不做写入型 Agent 工具、不把 HyDE 接入默认链路、不做复杂长期记忆系统。
- 阶段 12 重点是人工审阅质量校准、真实用户问题质量报告、Brain workflow 中的最小上下文补全，以及为后续 Decompose 阶段提供依据。
- 开发阶段不写 Obsidian 小 Phase 汇报，收尾时统一补齐。

## Current Project Findings

- 当前工作区已切换到 `codex/phase-12-quality-review-context-calibration`。
- `main` 最新合并提交为 `09926f5b0d3066cfbe22b45158e0822c912dd30e`，提交信息为 `merge phase 11 user evaluation query expansion`。
- `phase-11-complete` 指向 `fcd174eed3bcf32077444aaff393c6f5e6cb0132`。
- 当前 `HEAD` 从阶段 11 合并后的 `main` 创建，阶段 12 起点干净。
- 阶段 11 记录的全量测试为 `230 passed`。
- README 和 `docs/progress.md` 最新状态仍写“当前分支为阶段 11 分支”，这是合并回 `main` 后的文档口径滞后；阶段 12 收尾需要校准。

## Architecture Findings

- 阶段 8 已把 `/chat` 与 Agent `answer_with_citations` 收敛到 `BrainService`，因此阶段 12 的上下文补全应优先放在 Brain workflow，而不是分别改 chat 和 Agent。
- Brain 默认 workflow 为 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer`。
- `BrainService._rewrite_query_step()` 当前只是返回原问题，正好是最小上下文补全的入口。
- `BrainService.answer()` 接受 `history`，但当前 `CitationAnswerService.answer()` 和 Agent `answer_with_citations()` 没有向 Brain 传递历史。
- `RetrievalConfig.max_history` 已存在，用于过滤历史数量；阶段 12 可以复用这个配置做最小上下文边界。
- 生成回答时仍使用原始问题作为 `BrainAnswerResult.question`，如果补全 query 只用于检索，可保持对外 API 不变。
- `BrainService._generate_answer_step()` 在生成前调用 evidence confidence，阶段 12 不应绕过这层拒答保护。

## Existing Code Findings

- `app/services/brain/service.py` 包含 workflow 编排和 `_rewrite_query_step()`。
- `app/services/brain/config.py` 定义 `RetrievalConfig`、`WorkflowConfig` 和默认 workflow steps。
- `app/services/generation/answer_service.py` 是 `/chat` 与 Agent 引用问答的兼容门面。
- `app/services/agent/tools.py` 的 `answer_with_citations()` 复用 `CitationAnswerService`。
- `app/services/retrieval/keyword_search.py` 的 `SYNONYM_RULES` 是阶段 11 词表型 query expansion 的来源；阶段 12 应保留，不引入 HyDE 默认链路。
- `scripts/evaluate_user_questions.py` 已比较 `default_hybrid`、`keyword_baseline`、`vector_only`，适合复跑阶段 12 回归。
- `data/evaluation/user_question_review_samples.csv` 是阶段 11 的审阅抽样表，阶段 12 可以更新它或新增独立结果表。

## API Contract Findings

- `POST /chat` 当前请求 schema 包含 question、top_k、retrieval_mode、min_score；阶段 12 目标要求不破坏现有 API，不新增必填字段。
- `POST /agent/query` 当前请求 schema 包含 question、top_k、max_tool_calls、source_id；阶段 12 不新增写入型 Agent 工具。
- 阶段 12 为 `/chat` 和 `/agent/query` 增加可选 `history` 字段；旧请求不传 history 仍保持兼容。
- `POST /search`、`POST /search/vector`、`POST /search/hybrid` 不应受上下文补全影响。
- 上下文补全的核心逻辑仍优先测试 `BrainService.answer(history=...)`，API 测试只验证可选 history 接入和旧请求兼容。

## Evaluation Findings

- 阶段 11 用户问题评测：`25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
- 用户问题分配置结果：`default_hybrid=10/10`、`keyword_baseline=10/10`、`vector_only=5/10`。
- deterministic 回归：keyword 15/15、vector 13/15、hybrid 15/15、chat 6/6、agent 5/5、Brain workflow 18/18。
- 剩余失败集中在 deterministic `vector_only` 的 source hit mismatch，属于主题漂移或领域术语召回不足。
- 自动脚本能稳定检查拒答、来源命中、引用有效性和禁止词，但 Faithfulness 与 Answer Coverage 仍需要人工审阅或离线裁判。
- 阶段 12 新增 `data/evaluation/stage12_quality_review_results.csv`，6 个抽样中 risk_level 为 low 1、medium 3、high 2。
- 阶段 12 审阅结论：default_hybrid 来源命中可靠，但 deterministic answer 不能证明真实语言表达覆盖度；vector_only 的失败应作为阶段 13 rerank/Decompose/真实 embedding 对比输入。
- 阶段 12 上下文补全后回归未退化：user_questions 25/30、chat 6/6、agent 5/5、Brain workflow 18/18，API/核心测试 47 passed。

## Data Source Findings

- 阶段 12 不新增外部文献来源，不改变 source registry 合规边界。
- `data/evaluation/user_questions.csv`、`data/evaluation/user_question_results.csv`、`data/evaluation/user_question_review_samples.csv` 都是评测产物，不是资料来源。
- 阶段 12 新增的审阅结果表和质量报告仍是评测产物，不应保存受限全文。
- Jina、MIMO 或其他真实模型仍是模型服务，不是文献资料来源。
- 真实 API key 只允许存在本地 `.env`，不能写入文档、CSV、测试或 Obsidian。

## Technical Decisions

| Decision | Reason |
|---|---|
| 阶段 12 新增质量报告而不是只更新阶段 11 文档 | 阶段 12 要形成独立的发布前质量校准结论 |
| 上下文补全优先实现于 BrainService | 保持 chat/agent 共享核心链路，避免两处重复编排 |
| 为 chat/agent 增加可选 history 字段 | 让上下文补全可被外部调用，同时不破坏旧请求 |
| 补全只基于最近历史问题 | 满足“最小版本”，避免复杂长期记忆系统 |
| 补全只处理明确代词/省略问法 | 降低普通问题被误改写的风险 |
| 保留原始 question，补全 query 只用于检索 | 对外展示不变，检索质量可提升 |
| HyDE 只写入离线建议 | 避免真实模型依赖和假想答案污染引用边界 |
| Decompose 只做阶段 13 输入 | 阶段 12 先完成质量校准和最小 context，不扩大复杂 workflow |

## Phase Findings

### Phase 0

- 线程标题已修改为阶段 12。
- 已阅读 Planning with Files 技能说明。
- 已阅读阶段启动所需普通文档、阶段 11 离线审阅计划、旧规划文件和关键进度记录。
- `main` 与 `phase-11-complete` 已确认。
- 已创建并切换阶段 12 分支。
- 三份 Planning with Files 文件已校准为阶段 12。
- 起点全量测试为 `230 passed`。

### Phase 1

- Phase 1 目标是把阶段 11 的审阅样本真正用于质量校准。
- 已新增 `data/evaluation/stage12_quality_review_results.csv`，记录 6 条抽样的 faithfulness、answer_coverage、citation_quality、risk_level、reviewer_notes 和 next_action。
- 已新增 `docs/stage12_quality_review.md`，说明审阅方法、rubric、结果、风险和阶段 13 输入。
- 审阅结论保留一个诚实边界：deterministic provider 适合稳定回归，但不能单独证明真实回答覆盖度。
- 已新增 `tests/test_stage12_quality_review.py`，覆盖报告路径、CSV schema、语言/配置覆盖、敏感信息边界和 HyDE 不进默认回归。
- Phase 1 测试结果：`8 passed`。

### Phase 2

- Phase 2 目标是在 Brain workflow 的 `rewrite_query` 位置实现最小上下文补全。
- 已新增 `rewrite_contextual_question()`，只在问题包含“它/这个技术/这类问题/上面/刚才”等明确上下文指代时，用最近历史问题拼接检索 query。
- `BrainService.answer()` 现在会先过滤最近 history，再把过滤结果传给 `rewrite_query` step。
- 原始 `question` 保留在返回结果中；补全后的 query 只用于检索、prompt 和 evidence confidence。
- `CitationAnswerService.answer()` 支持可选 `history`，并根据非空历史自动设置 `max_history`。
- `/chat` 与 `/agent/query` 支持可选 `history` 字段；旧请求不传该字段仍保持兼容。
- 已补充 Brain、AnswerService、Chat API 和 Agent API 回归测试。
- Phase 2 测试结果：`52 passed`。

### Phase 3

- Phase 3 目标是确认最小上下文补全和可选 history 字段不破坏阶段 11 默认链路。
- 复跑用户问题评测：`25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
- 复跑 chat 评测：`6/6 passed`。
- 复跑 agent 评测：`5/5 passed`。
- 复跑 Brain workflow：`18/18 passed`。
- API/核心回归测试：`47 passed`。
- 结论：上下文补全只有在传入 history 且问题含明显指代词时生效，默认无 history 链路不退化。

### Phase 4

- Phase 4 目标是把阶段 12 结论转成阶段 13 的开发输入。
- 已新增 `docs/stage13_decompose_plan.md`。
- 阶段 13 建议优先做规则式 Decompose、子 query 检索、按 `chunk_id` 去重、保留 sub_query provenance 和可解释 rerank。
- HyDE 只保留离线实验建议，不进入默认链路或 deterministic 自动回归。
- Context 继续停留在最近 1-3 条问题的最小补全，不扩展成长期记忆系统。
- 新增 `tests/test_stage13_decompose_plan.py`。
- Phase 4 文档测试结果：`6 passed`。

### Phase 5

- Phase 5 目标是完成普通文档、Obsidian、本地过程文件、最终测试、提交和 tag 收尾。
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD`。
- 已新增 Obsidian 阶段 12 阶段页、阶段 12 Phase 汇报索引、Phase 0-5 小 Phase 汇报和 3 个知识点。
- Obsidian 每篇 Phase 汇报均有 10 个固定小节；Git 状态确认 `obsidian-vault/` 仍被忽略。
- 最终全量测试通过：`244 passed`。
- 阶段最终提交和 `phase-12-complete` tag 将作为本阶段完成标识；tag 必须指向阶段 12 最终功能提交。

## Term Explanations

| Term | Explanation |
|---|---|
| Faithfulness | 回答是否忠实于检索来源，没有编造资料外事实 |
| Answer Coverage | 回答是否覆盖问题期望的核心技术点 |
| Citation Quality | 引用编号和来源是否能支持回答中的关键说法 |
| Context Rewrite | 根据最近历史问题，把“它/这个技术”之类省略表达补成可检索问题 |
| HyDE | 先让模型生成假想答案再检索；本阶段只保留离线评估建议 |
| Decompose | 把复杂问题拆成多个子 query 分别检索；本阶段只做后续阶段输入 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| README/docs 当前分支口径仍写阶段 11 分支 | README 与 docs/progress 最新状态段落 | 阶段 12 收尾统一校准为阶段 12 完成状态 |
| Faithfulness/Answer Coverage 尚未真实审阅 | 阶段 11 只设计了审阅表 | Phase 1 将落地质量报告和审阅结果 |
| Brain rewrite_query 仍为 no-op | `BrainService._rewrite_query_step()` 返回原问题 | Phase 2 实现最小上下文补全 |

## Resources

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage11_user_evaluation_plan.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `app/services/brain/service.py`
- `app/services/brain/config.py`
- `app/services/generation/answer_service.py`
- `app/services/agent/tools.py`
- `scripts/evaluate_user_questions.py`
- `data/evaluation/user_questions.csv`
- `data/evaluation/user_question_results.csv`
- `data/evaluation/user_question_review_samples.csv`
