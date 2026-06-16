# 阶段 38 任务计划：默认 Tool Calling 链路生成质量攻坚与扩展评测闭环

## 目标

在阶段 37 tool_calling_agent 已成为默认链路（前端、后端 query/stream 三处已切换）的基础上，把默认链路的回答质量、引用质量和评测置信度补齐。

主线不是"再迁移架构"，而是承认默认链路已切到 tool_calling_agent，接下来攻坚 Judge 质量门、设计 tool-calling 专属生成策略、扩充评测集并做默认链路稳定性回归。

目标分支建议：`codex/phase-38-tool-calling-generation-quality`

核心原则：
- Judge 质量门目标：answer_coverage >= 0.80，citation_support >= 0.80，safety_leak_check 不降。
- 不为了覆盖率放松安全边界；不把 citation_validator 硬塞进生产链路。
- 不动 Stage 30 评分权重、等级阈值、release_decision 规则；Stage 30 维持 91.52 / A / pass。
- 不替换默认 embedding / rerank provider；不新增外部数据源。
- mode="react_agent" 继续作为显式回滚路径，不删除。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不写 API key / Bearer token / raw provider response / reasoning_content / hidden thought / 受限全文进 Git、CSV、文档、测试或 Obsidian。

## 当前基线

```text
main / origin/main -> 25344a8 Merge phase 37 tool calling loop migration
phase-37-complete -> 62eff40 Complete phase 37 tool calling loop migration
当前开发分支 -> codex/phase-38-tool-calling-generation-quality
```

Phase 37 关键改动（已提交并合并到 main）：
- tool_calling_agent 成为默认：前端 app.js、后端 agent.py query/stream 两个入口
- 三个 bug 修复：GBK encoding、assistant tool_calls protocol、ChatToolCall forward reference
- stream 层 mode 解析修复：auto-route 到 tool_calling_agent 时跳过 QueueStreamingChatModelProvider
- 真实评测：tool_calling 13.5s avg / react 28.0s avg，0 errors，8/8 refusal match

Phase 36 Judge 攻坚留下的基线：
- baseline: cov=0.655 / cit=0.640 / safety=1.000
- outline_first: cov=0.703 / cit=0.685 / safety=1.000
- answer_provider_ab: cov=0.772 / cit=0.820 / safety=0.950
- 三组均 review_required，未接生产

## Phase 顺序

### Phase 0：启动校准与阶段 38 规划落盘

任务：
- 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/phase_reviews/phase-37.md、docs/stage37_tool_calling_vs_react_decision.md。
- 阅读 task_plan.md、findings.md、progress.md。
- 运行 git status -sb、git log --oneline -5 --decorate。
- 确认 Phase 37 改动状态（默认链路切换 + bug 修复已在工作区但未提交）。
- 从当前状态创建或切换到 codex/phase-38-tool-calling-generation-quality 分支。

完成记录：
- 已阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/phase_reviews/phase-37.md、docs/stage37_tool_calling_vs_react_decision.md。
- 已阅读 task_plan.md、findings.md、progress.md。
- 已运行 `git status -sb` 与 `git log --oneline -5 --decorate`。
- 已确认 `phase-37-complete -> 62eff40` 是 `main / origin/main -> 25344a8` 的祖先，Phase 37 已完成并合并到 main。
- 已从 `main` 创建并切换到 `codex/phase-38-tool-calling-generation-quality`。

### Phase 1：阶段 38 设计文档与评测口径

任务：
- 新增 docs/stage38_tool_calling_generation_quality.md：固定四条主线（Judge 攻坚 / 专属生成策略 / 评测扩充 / 默认链路回归）和安全边界。
- 新增 tests/test_stage38_design.py，断言设计文档涵盖核心范围。
- 明确 Judge 评测口径：tool_calling_agent 的 final answer 走原生 tool_calls 协议最后一次 LLM 回复，不再走 answer_with_citations 工具内生成。

完成记录：
- 已新增 `docs/stage38_tool_calling_generation_quality.md`，固定 baseline Judge、structured_final_answer A/B、20-30 条扩展评测、默认链路三入口回归、安全边界和收尾产物。
- 已新增 `tests/test_stage38_design.py`，锁定 Phase 38 基线、四条主线、Judge 门槛、tool-calling 原生 final synthesis、扩展评测类别、默认回归与安全边界。
- 已明确 `structured_final_answer` 只能适配到 tool-calling system prompt / evidence synthesis prompt，不硬接旧 `AgentToolbox.answer_with_citations` 作为最终生成器。
- 已运行 `python -m pytest tests/test_stage38_design.py -q`，结果 `8 passed`。

### Phase 2：评测集扩充到 20-30 条

任务：
- 在 Phase 37 的 8 条基础上扩充评测集。
- 新增覆盖：多跳推理、数值对比、中英混合、长问题、模糊问题、证据不足、off-topic、工程责任边界。
- 新增 tool-calling 专属 edge case：citation repair 触发、evidence convergence 触发、skip tool 场景、duplicate tool_call 场景。
- 更新评测脚本支持扩充后的题集。
- deterministic 全量跑通。

完成记录：
- 已新增 `scripts/evaluate_stage38_tool_calling_quality.py`，复用 Phase 37 安全指标结构但输出独立 `stage38_*` CSV，不污染 Stage 37 历史产物。
- 已新增 `tests/test_stage38_tool_calling_eval.py`。
- 已将评测集扩展到 24 条，覆盖 16 类场景：single_hop、comparison、multi_dimensional、multi_hop、numeric_comparison、bilingual、long_question、ambiguous_query、followup、evidence_insufficient、off_topic、responsibility_boundary、citation_repair、evidence_convergence、skip_tool、duplicate_tool_call。
- 已运行 `python -m pytest tests/test_stage38_tool_calling_eval.py -q`，结果 `5 passed`。
- 已运行 `python scripts/evaluate_stage38_tool_calling_quality.py`，生成 `data/evaluation/stage38_tool_calling_quality_results.csv` 与 `data/evaluation/stage38_tool_calling_quality_summary.csv`。
- deterministic 结果：`react_agent errors=0 same_refusal=24/24 same_top_source=24/24`；`tool_calling_agent errors=0 same_refusal=23/24 same_top_source=20/24`。

### Phase 3：Tool Calling 专属 Final Answer 生成策略

任务：
- 分析 tool_calling_agent 当前 final answer 的 prompt 路径：tool result 反馈后模型自由生成 vs 有结构化指令。
- 设计 tool result 后的 final answer 指令模板：要求逐条引用、覆盖多要点、缺失证据说明。
- 把 Phase 36 的 outline_first 思路适配到 tool-calling final synthesis：不是接回旧 answer_with_citations，而是在 tool-calling 系统 prompt 中嵌入 outline-first 结构化生成要求。
- 处理已知 edge case：citation repair 失败后的安全拒答、evidence convergence 后回答发散、skip tool 后模型误解工具结果。
- 明确哪些策略进入默认链路，哪些只做 A/B 候选。

完成记录：
- 已在 `app/services/agent/tool_calling_service.py` 增加 `ToolCallingFinalAnswerStrategy`，支持 `baseline` 与 `structured_final_answer`。
- 默认 `ToolCallingAgentService` 使用 `structured_final_answer`；`baseline` 继续可显式传入，用于 Phase 4 A/B 对照。
- 已把结构化生成要求接入 `tool_calling_messages()`、`evidence_answer_messages()`、`citation_repair_messages()`：覆盖主要要点、事实句贴近 `[N]` 引用、证据缺失明说、citation repair 不新增事实、evidence convergence 不继续发散。
- 未把旧 `AgentToolbox.answer_with_citations` 硬接回 tool-calling 最终生成。
- 已补充 `tests/test_tool_calling_agent_service.py`，验证默认 structured prompt、baseline prompt、evidence/repair prompt 和非法 strategy 校验。
- 已运行 `python -m pytest tests/test_tool_calling_agent_service.py tests/test_stage38_design.py tests/test_stage38_tool_calling_eval.py -q`，结果 `28 passed`。
- 已重跑 `python scripts/evaluate_stage38_tool_calling_quality.py`，结果仍为 `tool_calling_agent errors=0 same_refusal=23/24 same_top_source=20/24`。

### Phase 4：Judge 质量门真实攻坚

任务：
- 用扩充后的 20-30 条评测集，在默认 tool_calling_agent 链路上跑真实 Judge。
- 对照组：baseline（当前默认 prompt）vs structured_final_answer（Phase 3 新策略）。
- 目标：answer_coverage >= 0.80，citation_support >= 0.80，safety_leak_check >= 0.80。
- 若达标 → 写决策报告，建议将新策略接入默认链路。
- 若未达标 → 诚实写归因（是 Judge 评分体系瓶颈、模型能力上限、还是 prompt 仍有空间），不强行包装。

完成记录：
- 已新增 `scripts/judge_stage38_tool_calling_quality.py`，支持 `baseline` vs `structured_final_answer` 两组 tool_calling_agent 原生链路 Judge A/B；默认 dry-run，显式 `--execute` 才调用真实 provider/Judge。
- 已新增 `tests/test_stage38_tool_calling_judge.py`，覆盖 dry-run 行数、summary gate、expected_refused 映射和敏感字段不入 CSV。
- 已运行 `python -m pytest tests/test_stage38_tool_calling_judge.py -q`，结果 `4 passed`。
- 已运行 dry-run：`python scripts/judge_stage38_tool_calling_quality.py --limit 24`，生成 48 行计划结果。
- 已运行真实 Judge：`python scripts/judge_stage38_tool_calling_quality.py --execute --limit 24 --timeout-seconds 180`，生成 48 行真实结果。
- 真实结果：baseline `cov=0.869 / cit=0.794 / safety=1.000 / gate=review_required`；structured_final_answer `cov=0.808 / cit=0.729 / safety=1.000 / gate=review_required`。
- 已新增 `docs/stage38_tool_calling_quality_decision.md` 草稿，诚实记录两组均未达标，不强行包装。
- 用户人工核验前追加 citation gap 补强：已新增 `scripts/analyze_stage38_citation_gaps.py` 和 `tests/test_stage38_citation_gap_analysis.py`。
- 分析结论：原 structured 低 cit 的 9 条中，6 条为 `prompt_citation_gap`，2 条为 `refusal_judge_artifact`，1 条为 `retrieval_or_repair_gap`；因此优先优化 prompt，不先动检索。
- 已将 `structured_final_answer` 从 outline-first 改为 compact citation-first：直接回答 1-2 句带引用，最多 3-5 个短事实 bullet，每个事实句/事实点必须贴最近 `[N]`。
- 第三轮真实 Judge 结果：baseline `cov=0.775 / cit=0.731 / safety=1.000 / gate=review_required`；structured_final_answer `cov=0.808 / cit=0.867 / safety=1.000 / gate=pass`。

### Phase 5：默认链路稳定性回归

任务：
- 锁定前端默认、query 端点默认、stream 端点默认都走 tool_calling_agent。
- production smoke 增加"默认 mode 实际为 tool_calling_agent"的断言。
- 保留并验证 latency、tool_count、llm_call_count、citation_count、source_count 等 Phase 37 指标不退步。
- mode="react_agent" 和 mode="agentic" 继续作为显式可选路径，回归测试确认不破坏。

完成记录：
- 已确认前端默认仍为 `tool_calling_agent`。
- 已将 `/agent/query` 与 `/agent/query/stream` 的省略 `mode` 默认行为从复杂度分流改为直接进入 `tool_calling_agent`。
- 显式 `mode="default"`、`mode="react_agent"`、`mode="agentic"`、`mode="tool_calling_agent"` 均保留，测试覆盖显式回滚路径。
- 已给 `ToolCallingAgentService` 补充 provider capability 护栏：默认链路遇到不支持 `generate_with_tools` 的 provider 时返回受控 503，不泄漏内部 AttributeError。
- 已增强 `scripts/run_production_smoke.py`：新增默认 query/stream smoke case，输出 `expected_mode`、`actual_mode`、`mode_matched` 并在 mode 不匹配时失败。
- 已运行 `python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_run_production_smoke.py -q`，结果 `44 passed`。
- 已运行 `python -m pytest tests/test_stage38_design.py tests/test_stage38_tool_calling_eval.py tests/test_stage38_tool_calling_judge.py tests/test_tool_calling_agent_service.py -q`，结果 `32 passed`。
- 已运行 `python scripts/run_production_smoke.py`，结果 `rows=11 execute=false failed=0`。
- 已重跑 `python scripts/evaluate_stage38_tool_calling_quality.py`，结果仍为 `tool_calling_agent errors=0 same_refusal=23/24 same_top_source=20/24`。

### Phase 6：裁定报告、文档与阶段收尾

任务：
- 输出 docs/stage38_tool_calling_quality_decision.md：Judge 质量门是否达标、是否继续保持 tool_calling 默认、哪些生成策略进入默认链路。
- 更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、按需 AGENT.MD。
- 新增 docs/phase_reviews/phase-38.md 验收草稿。
- Obsidian 阶段 38 收尾。
- 全量 pytest、Stage 30 score、production smoke、浏览器 smoke。
- 停在用户人工核验前状态。

完成记录：
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage38_tool_calling_quality_decision.md`。
- 已新增 `docs/phase_reviews/phase-38.md`。
- 已建立 `obsidian-vault/阶段汇报/阶段 38 - Tool Calling 生成质量攻坚/`，补齐阶段 38 Phase 汇报索引与 Phase 0-6 小汇报。
- 已新增 `obsidian-vault/阶段/阶段 38 - Tool Calling 生成质量攻坚.md`，并更新 `obsidian-vault/阶段汇报索引.md` 与 `obsidian-vault/阶段索引.md`。
- 已运行 `python -m pytest -q`，结果 `780 passed`。
- 已运行 `python scripts/score_stage30_quality.py`，结果 `overall=91.52 grade=A release_decision=pass`。
- 已运行 `python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120`，结果 `rows=11 execute=true failed=0`。
- 已完成浏览器 smoke：桌面最新回答 `mode=tool_calling_agent`、有引用、无横向溢出、console errors=0；390x844 移动端无横向溢出、console errors=0。
- 当前未执行 `git add`、`git commit`、`git tag`、`git push` 或创建 PR，停在用户人工核验前状态。
- citation gap 补强后已重跑最终验证：`python -m pytest -q -> 783 passed`；Stage 30 `91.52 / A / pass`；production smoke execute `rows=11 failed=0`；浏览器桌面/390x844 只读 smoke 均无横向溢出、console errors=0。Browser runtime 文本输入受虚拟剪贴板限制，默认 mode 执行由 production smoke 覆盖。

## 完成标准

- 评测集从 8 条扩充到 20-30 条，覆盖 11+ 类场景。
- Judge 质量门已显式攻坚，结果诚实记录（达标或未达标均写归因）。
- tool_calling_agent 的 final answer 生成策略已优化并验证。
- 默认链路稳定性已回归，三处入口确认走 tool_calling_agent。
- Stage 30 维持 91.52 / A / pass。
- 全量 pytest 通过；production smoke 通过；浏览器 smoke 通过。
- 裁定报告已输出。
- 未提交，等待用户人工核验。
## Six-Metric Gate Update

User review refined the Stage 38 Judge requirement: the final gate now considers all six Judge metrics, not only `answer_coverage`, `citation_support`, and `safety_leak_check`.

Required averages for a pass:

```text
faithfulness >= 0.80
answer_coverage >= 0.80
citation_support >= 0.80
refusal_correctness >= 0.80
conciseness >= 0.80
safety_leak_check >= 0.80
```

Implementation update:
- `scripts/judge_stage38_tool_calling_quality.py` now summarizes all six averages.
- `judge_gate` checks all six metrics and still blocks on any high-risk row.
- `--summarize-existing` rebuilds the summary CSV from existing real Judge rows without new provider calls.

Final 24-case result:

```text
baseline: faith=0.958 / cov=0.775 / cit=0.731 / refusal=0.958 / concise=0.960 / safety=1.000 / gate=review_required
structured_final_answer: faith=0.981 / cov=0.808 / cit=0.867 / refusal=0.921 / concise=0.925 / safety=1.000 / gate=pass
```

Human verification should inspect the two `refusal_correctness` anomalous rows even though the average is above the gate.
