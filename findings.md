# Phase 37 Submission Findings

Phase 37 real-provider comparison is now usable and no longer blocked by provider rate limits:

```text
react_agent: errors=0, refused=1/8, avg_time_to_final=28.0s, same_refusal=8/8, same_top_source=8/8
tool_calling_agent: errors=0, refused=1/8, avg_time_to_final=13.5s, same_refusal=8/8, same_top_source=7/8
```

Decision finding: tool calling is a viable parallel candidate and follows mainstream agent-runtime practice after the execution budget, skip-as-tool-result, near-duplicate guard, evidence convergence, and citation repair refinements. It should not become the default automatically because source ordering still differs in 1/8 real-provider rows and the tiered-provider tradeoff remains unresolved.

# 阶段 36 发现与关键决策

## 当前 Git 基线

阶段 35 与多轮意图路由补充已完成提交、tag、合并并推送：

```text
main / origin/main -> dc751fb Merge pull request #5 from CxcTHU/codex/phase35-multiturn-intent-router
phase-35-complete -> 7877308 Complete phase 35 remediation with Judge gate documented
phase-35-complete is ancestor of main
当前规划线程分支 -> main
```

关键决策：阶段 36 从 `main -> dc751fb` 创建新分支，多轮路由补充作为已验收基线纳入，**不重复验收**；既有阶段 tag 不移动。

Codex Phase 0 校准结果：

```text
当前开发分支 -> codex/phase-36-generation-reliability-and-conversation-stability
phase-35-complete -> 7877308a2f2102213a244d8f8ceb393e89153652
main -> dc751fb60a7a2f0749a2d40a083385ded4f4e950
merge-base check -> phase-35-complete is ancestor of main
工作树基线 -> task_plan.md / findings.md / progress.md 为规划线程遗留未提交改动，阶段 36 继续在此基础上维护
```

关键决策补充：Phase 0 只做校准和分支切换，不修改既有 tag，不提交，不重复验收 commit `0af4a87` 的多轮意图路由补充。

## 观察 1：阶段 36 的「不追分」原则源自阶段 35 教训

阶段 35 试图把所有指标都推过门，结果 citation_validator 接进生产 Brain 的 drop 模式让 answer_coverage 退了 0.115、citation_support 退了 0.115。阶段 35 续整改虽然把 validator 从生产解耦，但代价是承认「追分扭曲了产品」。

阶段 36 的反应是：**主线做稳，不做提分项目**。Stage 30 维持 `91.52 / A / pass`，Judge gate 不强行包装。

关键判断：阶段 36 是「先把真实用户对话体验和生成可靠性做稳」，验收口径换成稳定性，不再用单一指标做闭环。

## 观察 2：Judge gate 显式攻坚但有时限退出

阶段 35 续整改证明：

- citation_validator 死路（deterministic 后处理删句子伤覆盖）。
- Strict citation prompt profile 死路（citation 升、coverage 降）。
- Coverage-first prompt profile 死路（两者都不稳）。

但**没试过**：

- Outline-first 答题策略（LLM 先列要点 anchored 到 chunk_id，再填充内容）。
- Answer provider A/B（V4-Pro vs V3.2-Thinking 或同家族其他 chat model）。

关键决策：阶段 36 Phase 4 把两条都跑一次离线实验（≥ 20 条真实 Judge 样本）。通过则写决策报告由用户决定是否接生产；不通过则诚实写归因，不再继续追。**最多 2 周时限**，避免重蹈阶段 35 反复调 prompt 的覆辙。

## 观察 3：拒答可解释性是用户体感改善最大的方向

现在拒答只给 refusal_reason 短文本。用户的真实痛点：

- off-topic 时不知道怎么改写问题进 RFC / 水利领域。
- evidence_insufficient 时不知道是「资料库没有」还是「我问错了关键词」。

关键判断：这一项的产品改善幅度大于「把 Judge cov 拉到 0.80」。理由是：用户每次拒答都看得到这段文本，而 Judge 分数他们看不到。

关键决策：拒答可解释性是阶段 36 主线之一。要求：

- off-topic 给「这样改写可以进 RFC 领域」的建议（脱敏，不暴露内部规则原文）。
- evidence_insufficient 给「检索到了 N 条来源，覆盖了 X 方面，还缺 Y」（真实命中的脱敏摘要，不让 LLM 编造）。

## 观察 4：生产 smoke 自动化是工程债

每次阶段验收都要手动跑一遍 `/health`、`/quality-report`、`/agent/query` 各模式 + `/agent/query/stream`，没有脚本化。

关键决策：阶段 36 把这个固化成 `scripts/run_production_smoke.py`，默认 dry-run，`--execute` 跑真实端点；输出脱敏 CSV；阶段 36 收尾必须一键通过。

## 观察 5：多轮意图路由补充已合并，但模块化是否必要待 Codex 判断

阶段 35 补充已经在 commit 0af4a87 合并：翻译/转述、模型信息、能力说明、拒答原因等意图分支。用户已经人工验收。

关键判断：是否抽取为独立 `intent_router.py` 模块**由 Codex 看代码决定**——如果现有代码已经分得清，本 Phase 降级为「补回归测试集 + 更新文档」；如果散在 `app/api/agent.py` 里看不清，再抽取。

关键决策：阶段 36 不强制重构。**重构没有产品价值**，回归集和测试覆盖才是关键。

## 观察 6：阶段 36 不动的边界（保守清单）

- 不替换默认 chat / embedding / rerank provider；不动 chat provider 拓扑。
- 不引入新外部数据源、不爬新网页、不切 chunk。
- 不做 tool-calling 协议迁移（留给阶段 37 或后续候选）。
- 不做多用户 / Conversation owner 隔离。
- 不做写入型 Agent 工具。
- 不接任何 deterministic 后处理（含 citation_validator）进生产链路。
- 不改 Stage 30 评分规则。

## 观察 7：阶段 36 的安全边界

跟阶段 30/34/35 一致：

- 不写 API key / Bearer token / Authorization header / raw provider response / reasoning_content / hidden thought / 受限完整 chunk 进任何 CSV / 文档 / 测试 / Obsidian。
- 拒答可解释性的检索摘要必须脱敏（截断到 ≤ 200 字符）。
- 改写建议不暴露内部规则原文（不让用户能反推 SYNONYM_RULES、prompt 全文、安全规则）。
- 生产 smoke CSV 只保存 endpoint、状态、耗时、关键字段是否齐全、refused、citation_count、validator_marker。

## 观察 8：可能的阶段 37 候选方向（不在阶段 36 范围）

- tool-calling 协议迁移（合并 planner + answer 到同一次 LLM forward）。
- 多用户 Conversation owner/user 隔离。
- 真实 LLM Judge 周期化跑 + 写回评分报告。
- 阶段 36 Judge 攻坚若失败，重新校准 Judge 评分口径或换 rubric。

阶段 36 完成后，根据 Judge 攻坚结果和拒答可解释性收尾情况决定下一阶段方向。

## Phase 1 设计文档决策

阶段 36 设计文档已固定三条主线：

```text
拒答可解释性升级 -> 生产 smoke 自动化 -> Judge gate 离线攻坚
```

关键约束已写入 `docs/stage36_generation_reliability_and_conversation_stability.md` 并由 `tests/test_stage36_design.py` 锁定：

- Stage 30 维持 `91.52 / A / pass`，不改评分权重、等级阈值或 release_decision 规则。
- Judge gate 只做离线攻坚，样本不少于 20 条，时限不超过 2 周；达不到就诚实归因。
- `citation_validator` 和其他 deterministic 后处理不得接回生产链路。
- 不替换默认 chat / embedding / rerank provider，不动 chat provider 拓扑，不新增外部数据源。
- 拒答解释必须脱敏，`evidence_insufficient` 单条摘要不超过 200 字符。

新词解释：

- `outline-first`：先生成带 source/chunk 锚点的答案提纲，再填充正文。在本项目只作为 `app/services/generation/` 下的离线候选策略，用来测试能否同时提升 coverage 和 citation support。面试中可表达为“先约束证据骨架，再生成自然语言”。
- `answer provider A/B`：同一检索证据下只替换回答模型做对照，避免把 planner、embedding、rerank 混成变量。阶段 36 仅离线使用。
- `production smoke`：真实端点最小冒烟检查，覆盖 `/health`、`/quality-report`、`/agent/query` 和 SSE 流式链路；它验证服务可用性，不替代 pytest。

## Phase 2 拒答可解释性决策

阶段 36 没有修改 `/agent/query` 顶层 schema，而是把解释写入已有 `reasoning_summary`：

```text
reasoning_summary = 原有摘要 | refusal_explanation: ...
```

这样前端、SSE metadata、会话消息 metadata 都能继续兼容，且不需要新增 response 字段。

新增模块：

```text
app/services/agent/refusal_explainer.py
```

作用：

- `off_topic`：给安全改写建议，引导用户问堆石混凝土、混凝土材料、施工质量、水利工程或工程案例相关问题。
- `evidence_insufficient`：使用真实 source title / source_type / 短 content snippet 生成检索摘要；单条摘要不超过 200 字符。
- 不输出内部规则名、prompt 原文、完整 chunk、API key、Bearer token、raw provider response、reasoning_content 或 hidden thought。

为支持 `evidence_insufficient` 摘要，`AgentToolbox.answer_with_citations()` 在拒答且没有 sources 时补一次只读 `HybridSearchService` 检索，只用于展示安全摘要。这一步不调用 LLM、不写数据库、不改变默认 provider，也不改变 Brain 拒答阈值。

新词解释：

- `refusal_explainer`：拒答解释器，位于 Agent 输出层，把拒答类别和安全来源摘要转成人能读的下一步建议。面试中可说“拒答不是只给一个错误码，而是告诉用户怎么把问题改到系统可回答范围内”。
- `evidence_insufficient`：证据不足拒答，表示问题可能在领域内，但检索结果无法可靠支撑答案。本项目中由 Brain 的 evidence confidence 触发，阶段 36 只增强解释，不放宽门槛。

## Phase 3 生产 smoke 自动化决策

新增脚本：

```text
scripts/run_production_smoke.py
data/evaluation/stage36_production_smoke_results.csv
tests/test_run_production_smoke.py
```

设计决策：

- 默认 dry-run，只写计划行；显式 `--execute` 才调用真实服务端点。
- 使用 Python 标准库 `urllib`，不新增依赖。
- 覆盖 `/health`、`/quality-report`、`/quality-report/data.json`、正常 RAG、多轮转述、模型信息和 `/agent/query/stream`。
- CSV 不保存 response body，只保存状态、耗时、关键字段是否齐全、refused、citation_count、validator_marker、sensitive_field_detected、error_summary。
- `validator_marker` 用于确认阶段 35 的 `citation_validator` 标记没有重新出现在生产输出。
- `sensitive_field_detected` 用于发现 API key、Bearer token、Authorization、raw_response、reasoning_content、hidden thought 等泄漏标记。

关键决策：Phase 3 只完成 dry-run 与脚本测试；真实 `--execute` 必须等阶段收尾时服务启动后统一运行。

## Phase 4 Judge Gate 离线攻坚结论

新增能力：

```text
app/services/generation/outline_first_strategy.py
scripts/judge_stage36_strategy_ab.py
tests/test_stage36_judge_strategy_ab.py
docs/stage36_judge_strategy_decision.md
```

实现范围：

- `baseline`：当前默认 Agent answer 链路。
- `outline_first`：先生成带 source marker 的证据提纲，再生成最终答案。
- `answer_provider_ab`：同一检索证据下切换 answer provider/model，对照 `DeepSeek-V3.2-Thinking` 等候选。

执行观察：

```text
dry-run: 20 queries * 3 strategies = 60 rows
real --execute --limit 20 --timeout-seconds 180: completed_rows=60
baseline: cov=0.655, cit=0.640, safety=1.000, gate=review_required
outline_first: cov=0.703, cit=0.685, safety=1.000, gate=review_required
answer_provider_ab: cov=0.772, cit=0.820, safety=0.950, gate=review_required
```

诚实结论：

- Stage 36 已显式落地 outline-first + answer provider A/B 的离线攻坚脚本和测试。
- 当前本地真实 provider/Judge 链路已完成不少于 20 条真实 Judge；三组都没有同时达到 cov/cit/safety 全部 0.80。
- `answer_provider_ab` 的 citation_support 达到 0.820，但 answer_coverage 只有 0.772，仍未过 gate。
- `outline_first` 与 `answer_provider_ab` 只保留为离线候选；生产 Brain 路径保持不变。
- 后续若要继续 Judge 攻坚，应优先分析 answer_coverage 缺口，而不是接 deterministic 后处理或直接替换生产 provider。

新词解释：

- `completed Judge row`：一条完成了 answer 生成、Judge 调用并写入分数的评测记录。阶段 36 当前为 60，说明可以做离线策略对比，但由于 gate 未达标，不能作为生产切换依据。
- `review_required`：Judge 分数未达到阶段门槛，必须保留人工复核和风险归因，不能包装成 pass。

## Phase 5 多轮路由模块化决策

新增模块：

```text
app/services/agent/intent_router.py
tests/test_intent_router.py
```

抽取范围：

- followup transform：上一轮翻译、转述、总结、表格、要点化。
- meta intent：模型信息、能力说明、拒答原因解释。
- history prefix stripping：从 history 文本中取上一轮 assistant 内容。

`app/api/agent.py` 现在调用 `intent_router` 中的纯函数，API 层继续负责会话读写、调用 provider 和组装 response。这样路由规则可单测，API 编排仍保留在 API 层。

8 类回归：

```text
上一轮翻译 / 追问 / 问来源 / 问模型 / 问为什么拒答 / 闲聊 / off-topic / 正常领域问答
```

观察：英文 `FOLLOWUP_PRONOUNS` 仍使用子串匹配，`it` 可能命中 `quality`、`durability` 等词。阶段 36 未改变这条历史行为，只通过回归测试固定当前边界；若后续出现误路由，可在下一阶段把英文 pronoun 改为 token 级匹配。

新词解释：

- `intent_router`：意图路由器，判断用户这句话应走“转述上一轮”“回答模型信息”“解释拒答原因”还是进入正常 RAG。面试中可说“我把对话入口判断从 API 编排里抽成纯函数，便于回归测试和后续扩展”。

## Phase 6 收尾验证结论

普通文档已同步：

```text
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
docs/phase_reviews/phase-36.md
docs/stage36_generation_reliability_and_conversation_stability.md
docs/stage36_judge_strategy_decision.md
```

Obsidian 草稿已同步：

```text
obsidian-vault/阶段/阶段 36 - 生成可靠性与多轮体验稳定化.md
obsidian-vault/阶段汇报/阶段 36 - 生成可靠性与多轮体验稳定化/
obsidian-vault/首页.md
obsidian-vault/阶段索引.md
obsidian-vault/阶段汇报索引.md
```

最终验证：

```text
python -m pytest -q -> 724 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute -> rows=7 execute=true failed=0
浏览器桌面 smoke -> scrollWidth=clientWidth=1265, console errors=0
浏览器 390x844 smoke -> scrollWidth=bodyScrollWidth=375, console errors=0
```

生产 smoke 期间发现两个判定口径问题并已修正：

- `/quality-report/data.json` 返回的是评分行列表，不是汇总对象；脚本改为检查首行 `run_id`、`dimension`、`score`、`status`。
- 模型信息回答中出现“不会暴露 bearer tokens / raw provider responses / hidden thoughts”这类否定式安全说明；脚本改为只检测真实 token、Authorization、`raw_response`、`reasoning_content`、`hidden_thought` 等泄漏标记，避免把安全说明误判为泄漏。

阶段 36 已通过用户人工核验并获得提交合并授权。提交前追加两项体验微调：前端聊天框改为 Enter 发送、Shift+Enter 换行；模型信息、能力说明、拒答原因等 meta/非 RAG 路由回复默认中文。
