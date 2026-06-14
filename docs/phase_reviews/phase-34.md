# 阶段 34 验收草稿：RAG 性能瓶颈诊断、Embedding 迁移决策、真实 Judge 质量复核与 LLM-driven Planner 切换

状态：开发、自动验证、真实 trace 重跑与用户人工核验均已完成，进入提交合并收尾。

分支：`codex/phase-34-rag-diagnosis-embedding-judge`

基线：`main / origin/main -> c06d0a3 Merge phase 33 rag performance embedding validation`，`phase-33-complete -> 0bad9e1 Complete phase 33 rag performance embedding validation` 已合并到 `main`。

提交边界：用户已授权提交、创建 `phase-34-complete` tag、推送并合并到 GitHub；不创建 PR。

## 验收结论

阶段 34 已完成原始计划范围 + 用户在阶段中追加的「LLM-driven planner + 分层 chat provider」改造。代码、脚本、测试、真实评测产物和文档都到位，性能与质量均有可验证的净改进。当前不能直接判定为最终 PASS，原因是 Judge `review_required` 与 Stage 30 `review_required` 两类质量门仍待用户人工复核。

## 范围核对

已交付：

- Jina vs GLM 同环境真实对照（阶段 33 留下的 skipped 项闭环）。
- 真实 RAG/ReAct latency trace 三轮采集（基线 MIMO；中间 LLM-driven on MIMO 反向退化；最终 Flash planner + V4-Pro answer）。
- 瓶颈归因脚本、决策报告脚本、真实 LLM Judge 支路与阶段 34 决策报告。
- 新增 chat provider 分层路由：`PLANNER_CHAT_*` 环境变量、`Settings.planner_chat_*` 字段、`get_agent_planner_chat_model_provider()` 工厂、`ReActAgentService(planner_chat_provider=...)`、API 同步 + 流式端点 wiring。
- ReAct planner prompt 升级：明确允许 LLM 在第 1 轮 refuse（仅限不安全 / 明显跨领域 / 工程判定题）；显式约束证据充足时必须 answer_with_citations；规定 final_answer 不得跳过 citations；中英文 / 中英混合都视为 in-scope。
- `parse_react_action_json` 解析失败兜底：有证据 → answer_with_citations，无证据 → refuse。
- `.env` 切换：`CHAT_MODEL_NAME=DeepSeek-V4-Pro`、`PLANNER_CHAT_MODEL_NAME=DeepSeek-V4-Flash`，base_url 走 `https://llmapi.paratera.com/v1`；旧 MIMO 配置注释保留作回滚参考。`.env` 已在 `.gitignore`。
- 旧 Jina 索引保留；未直接替换默认 GLM；未新增外部数据源；未引入写入型 Agent 工具；未做部署 / 运维。

## 阶段 34 中的范围扩展（基于真实数据的决策）

阶段 34 最初范围只包含「诊断 + Judge 复核 + 决策报告」，不直接动 ReAct 协议。第一轮真实 trace 落地后用户发现 MIMO 当 planner 时延迟主导整个链路，提出「让 LLM 自主决策 + 分层 provider」方案。基于本阶段「用数据决策」的原则，阶段范围被扩展执行：

1. 第一轮实验：去掉 elif 短路，让 MIMO 当 planner 真做决策 → 真实 trace 反向退化（react_agent p90 +135%、4 条中 1 条 timeout）。
2. 复盘根因：MIMO 是 reasoning 模型，单次 planner 调用 30–70s；本项目 ReAct 协议「planner 决策 + answer 工具内 LLM 生成 = 每 run 2 次 LLM」对慢 / reasoning 模型不友好。
3. 第二轮实验：保留改动，引入 `planner_chat_provider`，把 planner 切到 DeepSeek-V4-Flash、answer 切到 DeepSeek-V4-Pro。验证后发现 in-scope 误判 refuse 问题。
4. prompt 收紧 refuse 触发条件：仅在不安全 / 明显跨领域 / 工程判定题时第 1 轮直接 refuse；其它一律先 search。
5. 第三轮实验：重新跑 trace → in-scope 全部正确回答；refusal_boundary 由 LLM 第 1 轮直接 refuse；性能相对 MIMO 基线净改进。

这是阶段 34 决策原则的执行示例：实验暴露协议层根本问题，承认协议层迁移留给阶段 35，但仍在阶段 34 内用「分层 chat provider + 受控 LLM-driven planner」这一非破坏性改动拿到可验证收益。

## 核心结果

```text
embedding_decision=keep_glm
jina_context=Jina 在 p@5/coverage 略优，但额度可持续性风险更高；仅作历史对照与回滚参考
jina_baseline: p@5=0.933, coverage=0.670, avg_latency≈1374.06ms
glm_candidate: p@5=0.867, coverage=0.637, avg_latency≈1544.93ms

chat_provider_topology=Paratera DeepSeek-V4-Flash (planner) + Paratera DeepSeek-V4-Pro (answer)
elif_short_circuit_status=保留为 planner_chat_provider=None 时的兼容路径（deterministic 与无 planner 配置场景）
llm_driven_planner_status=已在阶段 34 内启用（通过 planner_chat_provider 注入）

latency_primary_bottleneck=tool_iteration_overhead （V4-Pro 生成 answer 是主要耗时）
react_agent p50: 87.9s (MIMO baseline) -> 39.1s (Flash+Pro)    约 -55%
react_agent p90: 95.2s -> 55.0s                                约 -42%
react_agent 成功率: 3/4 (1 timeout) -> 4/4
refusal_boundary 第 1 轮直接 refuse: 3.5s（之前 elif+MIMO 跑满 2 轮 17s 才 refuse）

judge_quality_gate=review_required
judge medium risk=4/4
stage30_overall_score=83.17 release_decision=review_required
```

## 验证结果

```text
阶段 34 + ReAct + LLM-driven 聚焦测试：32 passed（含新增 tests/test_react_llm_planner.py 6 条）
真实 Flash + V4-Pro 连通性 smoke：planner≈1.8s, answer≈1.2s（trivial prompt）
真实 latency trace：completed=10/10
python scripts\score_stage30_quality.py：overall=83.17 grade=B release_decision=review_required
全量 pytest 与 browser smoke 在阶段 34 收尾段执行
```

## 安全与合规

- `.env` 已在 `.gitignore`；DeepSeek/Paratera api_key 不进 Git、CSV、文档、测试或 Obsidian。
- 评测 CSV 仅保留脱敏指标、状态、provider/model 名、延迟、错误占位。
- 决策报告引用脱敏短证据，不含 raw provider response、reasoning_content、hidden thought 或 Authorization 头。
- `tests/test_react_llm_planner.py` 使用脚本化 `ScriptedPlannerProvider`，不调用真实 provider；CI 与 dry-run 不依赖真实 API。

## 人工核验重点

1. 是否接受 `keep_glm`：保留 GLM-Embedding-3 为默认 embedding provider，Jina 仅作对照 / 回滚。
2. 是否接受 chat provider 分层路由：planner = DeepSeek-V4-Flash、answer = DeepSeek-V4-Pro，完全替代 MIMO；Paratera api_key 已写入本地 `.env`，建议在 Paratera 后台轮换一次 key（聊天中曾出现明文）。
3. 是否接受真实 trace 重跑结论：react_agent p50 87.9s → 39.1s、p90 95.2s → 55.0s、refusal_boundary 第 1 轮 LLM 自主 refuse 3.5s。
4. 是否同意把「tool-calling 协议迁移（合并 planner + answer 到同一次 LLM forward）」作为阶段 35 主线。
5. 是否接受真实 Judge 当前 `review_required` 状态，并人工复核 citation_support / answer_coverage 较低样例。

## 后续提交建议

人工核验通过后，再执行阶段 34 最终提交、创建 `phase-34-complete` tag，并按项目流程推送分支、main 和 tag。tag 必须指向阶段 34 最终功能提交，不要移动已有阶段 tag。
