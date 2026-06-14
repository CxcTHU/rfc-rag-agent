# 阶段 34 发现与关键决策

## 阶段中追加的关键发现：LLM-driven planner 与分层 chat provider

阶段 34 真实 trace 一上来就暴露 ReAct 慢的根因。基于「用数据决策」原则，本阶段在原计划基础上扩了范围，做了三轮闭环实验，结论值得后续阶段参考。

### 观察 0：现行 ReAct 协议 ≠ 主流 tool-calling 协议

仔细数过 LLM 调用次数后确认：

- 现行 elif 短路版：每 run 2 次 LLM 调用（iter1 planner + iter2 answer 工具内 LLM）。跟主流 tool-calling 协议（每 run 2 次 LLM）次数一致。
- 现行去掉 elif 版：每 run 3 次 LLM 调用（多 1 次 iter2 planner）。比主流多 1 次。
- 主流 tool-calling：planner 决策与 answer 生成在同一次 LLM forward 内完成；用 `tools` 参数返回 `tool_calls` 或文本。

我们不同的是「决策」和「生成」分散在不同 LLM 调用里。要彻底拿到主流那种「LLM 自主 + 单次调用」需要协议迁移，这是阶段 35 的事。

### 观察 1：MIMO 当 planner 是反向退化

第一轮实验（去掉 elif、让 MIMO 当 planner）真实跑：

```text
react_agent p50: 36.4s -> 87.9s (+141%)
react_agent p90: 40.5s -> 95.2s (+135%)
refusal_boundary_react: 超时失败 (60s+)
```

根因：MIMO 是 reasoning 模型，每次 planner 调用 30–70s。2 次 LLM 往返协议被 MIMO 单次成本放大。

关键判断：协议层的差距不能用 prompt 修，只能换模型或换协议。

### 观察 2：分层 chat provider 是阶段 34 范围内可行的解决方案

第二轮实验：planner 切轻量 Paratera DeepSeek-V4-Flash，answer 切 DeepSeek-V4-Pro（替换 MIMO）。

新增 `PLANNER_CHAT_*` 环境变量与 `planner_chat_provider` 注入：

- `planner_chat_provider=None` → 保留 elif 短路 + chat_model_provider，向后兼容。
- `planner_chat_provider=<Flash>` → 去掉 elif，LLM 每轮自主决策。

实测结果：

```text
react_agent p50: 87.9s (MIMO) -> 39.1s (Flash+Pro)   约 -55%
react_agent p90: 95.2s -> 55.0s                       约 -42%
react_agent 成功率: 3/4 (1 timeout) -> 4/4
refusal_boundary 第 1 轮直接 refuse: 17s -> 3.5s
```

关键决策：阶段 34 把 Flash + V4-Pro 写进 `.env`，作为生产配置；MIMO 注释保留。`.env` 已在 `.gitignore`。

### 观察 3：planner prompt 必须显式约束 refuse 触发条件

第一次 Flash + V4-Pro 跑时出现 `simple_filling_react` 和 `mixed_language_react` 第 1 轮就被 LLM 误判 refuse。根因：原 prompt 写「若 question 明显在 RFC 范围外则 refuse」，Flash 这种小模型对边界判断保守。

修复：

- 默认必须先 search（除非明显跨领域/不安全/工程判定题）。
- 显式列出 RFC、堆石混凝土、自密实混凝土、坝、温控、水化、耐久等关键词为 in-scope。
- 中文 / 英文 / 中英混合都视为 in-scope。
- 「When in doubt, prefer search_knowledge over refuse」作为兜底原则。

修复后第三轮真实 trace：in-scope 全部正确回答，refusal_boundary 由 LLM 第 1 轮即正确 refuse。

### 观察 4：协议层迁移留给阶段 35

阶段 34 拿到 -55% react_agent p50 的净改进已经够大；继续做协议迁移会触及：

- `ReActAgentService.query()` 主循环重写。
- `AgentToolbox.answer_with_citations` 内部 LLM 调用迁出，合并到 planner 那次调用。
- SSE 事件协议、`workflow_steps`、`tool_calls`、`citations` 兼容性。
- 全量 react 测试与 stream 协议测试。

工作量超出阶段 34 原始范围。阶段 35 主线建议为「tool-calling 协议迁移合并 planner + answer 到同一次 LLM forward」。

## 当前 Git 基线

阶段 33 已经完成提交、tag、合并和推送。阶段 34 的正确起点是最新 `main`：

```text
main / origin/main -> c06d0a3 Merge phase 33 rag performance embedding validation
phase-33-complete -> 0bad9e1 Complete phase 33 rag performance embedding validation
phase-33-complete is ancestor of main
当前规划线程分支 -> main
```

关键决策：阶段 34 必须从阶段 33 合并后的 `main` 创建新分支，不从阶段 33 人工核验前旧文档状态继续。既有阶段 tag 不移动。

## 观察 1：入口文档存在滞后，Git 状态是阶段 34 基线依据

`AGENT.MD`、`README.md` 和 `docs/progress.md` 的顶部仍保留阶段 33 “等待人工核验”的描述，但 Git 已显示：

```text
phase-33-complete -> 0bad9e1
main -> c06d0a3 Merge phase 33 rag performance embedding validation
```

关键判断：阶段 34 planning 以 Git/tag/main 为准；阶段 34 收尾时应同步修正入口文档，把阶段 33 状态更新为已提交合并，把阶段 34 状态写成等待人工核验。

## 观察 2：阶段 34 应做证据闭环，而不是新 Agent 功能

阶段 33 已经完成 FAISS-only、query embedding cache 和 latency trace。剩下的问题不是“缺少新功能”，而是三个证据口未闭合：

- GLM-Embedding-3 vs Jina 没有同环境对照。
- latency trace 已接入但没有真实样本分析。
- 最终生成答案没有真实 LLM Judge 语义评分。

关键决策：阶段 34 主线是 `diagnose -> compare -> judge -> decide`，不是直接做真 LLM 自主 ReAct。真 LLM 自主 ReAct 可以作为阶段 35 候选。

## 观察 3：Jina 配置已补，但不能写入文档或 CSV

本地 `.env` 已补充：

```text
JINA_API_KEY=<redacted>
JINA_BASE_URL=https://api.jina.ai/v1
```

旧 Jina 索引仍在：

```text
data/faiss/jina_jina-embeddings-v3_dim1024.index
data/faiss/jina_jina-embeddings-v3_dim1024_ids.json
```

关键决策：阶段 34 可以直接重跑 Jina baseline，但任何文档、CSV、测试、Obsidian 和最终回复都不得写出 key 明文。只记录 provider/model/dimension/base host 和脱敏状态。

## 观察 4：GLM 迁移仍处于 review_for_silent_regression

阶段 33 真实 GLM query 侧结果：

```text
glm_candidate: completed
precision@5=0.867
coverage=0.637
avg_latency≈1469.98ms
decision=review_for_silent_regression
```

Jina baseline skipped 的根因是缺少当时的 Jina provider 配置，而不是 Jina 索引不存在。

关键决策：阶段 34 不能只复述阶段 33 结果，必须用同一题集、同一数据库、同一评测脚本重跑 Jina 与 GLM，并给出保留 GLM、回滚 Jina、按 query 类型分流或继续人工复核的建议。

## 观察 5：latency trace 需要变成瓶颈占比

阶段 33 已有字段：

- `query_embedding_latency_ms`
- `vector_search_latency_ms`
- `faiss_search_latency_ms`
- `numpy_search_latency_ms`
- `rerank_latency_ms`
- `planner_latency_ms`
- `tool_latency_ms`
- `answer_latency_ms`
- `time_to_first_token_ms`
- `time_to_final_ms`
- `iteration_count`
- `tool_call_count`

但阶段 33 只证明字段能输出，没有采集真实样本并计算占比。

关键决策：阶段 34 至少采集 10-20 条真实 `/agent/query` 或 `/agent/query/stream`，计算每段 p50/p90、均值、最大值和占比，判断主要瓶颈。

## 观察 6：真实 Judge 是生成质量证据，不替代阶段 30 总分

阶段 30 的 `83.17` 是规则评分，不是 LLM Judge 分。阶段 33 没有对最终答案做真实语义评分。

阶段 34 的真实 Judge 应评估：

- faithfulness：答案是否被证据支撑。
- answer_coverage：是否覆盖问题要点。
- citation_support：引用是否支撑对应说法。
- refusal_correctness：该拒答时是否拒答。
- conciseness：是否过长导致延迟和用户体验问题。
- safety_leak_check：是否泄露 `reasoning_content`、raw response、key 或 hidden thought。

关键决策：真实 Judge 作为辅助决策支路，默认 dry-run，不进入 CI，不替代阶段 30 总分；显式 `--execute` 才调用真实 provider。

## 观察 7：DeepSeek 仍不能直接切默认 provider

阶段 33 MIMO baseline 可运行，DeepSeek candidate skipped。阶段 34 可以在 latency 和 judge 结果后评估 chat provider 下一步，但不能直接把 DeepSeek 变成默认 provider。

关键决策：如果阶段 34 发现 answer generation 是主要瓶颈，可以建议阶段 35/后续小阶段做 provider 对照或 prompt 压缩；默认 MIMO 不在阶段 34 直接切换。

## 观察 8：阶段 34 的评价口径必须先被测试锁住

Phase 1 新增 `docs/stage34_rag_diagnosis_embedding_judge.md` 和 `tests/test_stage34_design.py` 后，阶段 34 的关键口径已经从“对话要求”落到可回归检查：

- Embedding 对照必须是 GLM-Embedding-3 2048 维 vs Jina 1024 维同环境比较。
- 检索指标必须至少覆盖 `precision@1/3/5`、`hit@5`、`coverage`、`refusal boundary` 和 latency。
- Latency 诊断必须包含 p50/p90、均值、最大值和阶段占比。
- 真实 LLM Judge 必须默认 dry-run，显式 `--execute` 才调用真实 provider。
- 安全边界必须覆盖 API key、Bearer token、raw provider response、`reasoning_content`、hidden thought 和受限全文。

关键决策：后续 Phase 2-6 的脚本、CSV 和报告都应对齐这份设计文档；如果实现中发现字段名需要调整，应同步更新设计文档和测试，而不是让文档变成口号。

## 观察 9：Jina 与 GLM 同环境对照呈现混合信号

Phase 2 修复了阶段 33 迁移脚本读取 Jina 专用 `.env` 变量的问题，并显式运行真实同环境对照。结果：

```text
jina_baseline: completed, precision@1=0.667, precision@3=0.800, precision@5=0.933, coverage=0.670, avg_latency≈1374.06ms
glm_candidate: completed, precision@1=0.667, precision@3=0.867, precision@5=0.867, coverage=0.637, avg_latency≈1544.93ms
decision=keep_glm
```

关键判断：Jina 在 top-5 与 coverage 上略优，GLM 在 top-3 上更好；但 Jina 优势幅度不足以抵消额度即将耗尽带来的可持续性风险。阶段 34 最终不推进 Jina 分流，保留 GLM-Embedding-3 作为默认 embedding provider。

关键决策：旧 Jina 索引继续保留，但 Jina 结果只作为历史同环境对照和必要时的回滚参考；默认 embedding provider 保持 GLM-Embedding-3。

## 观察 10：default Agent 原先没有 latency_trace，需要补齐后才能公平采集

阶段 33 已让 `react_agent` 输出完整 `latency_trace`，但 default `AgentService` 的 `AgentQueryResult.latency_trace` 仍为空。Phase 3 为 default 路径增加请求级 `LatencyTrace`，让已有 `VectorSearchService`、`VectorIndexCache` 和 `HybridSearchService` 的 timer 能写入同一个 trace。

关键判断：这是向后兼容增强，因为 `AgentQueryResponse` 原本已有 `latency_trace` 字段；现在只是把空对象变成安全数值，不改变 `/agent/query` schema。

## 观察 11：真实 trace 首轮显示慢点集中在工具/回答与 planner

Phase 3 显式运行：

```text
python scripts\collect_stage34_latency_traces.py --execute-real --output data\evaluation\stage34_latency_traces.csv
```

结果 10/10 completed。初步观察：

- default 问答样例的 `tool_latency_ms` / `answer_latency_ms` 远高于 query embedding 和 vector search。
- react_agent 样例额外出现明显 `planner_latency_ms`，符合真实 provider 规划调用成本。
- `/chat` 当前没有内部 trace 字段，因此阶段 34 采集脚本把它诚实标记为 `endpoint_total_latency`，不伪造成 embedding 或 rerank 瓶颈。

关键决策：Phase 4 必须用统计脚本计算 p50/p90 和阶段占比，不能只凭这次人工扫表定性下结论。

## 观察 12：阶段 34 性能主瓶颈是工具/回答链路，不是 FAISS/vector search

Phase 4 分析 `data/evaluation/stage34_latency_traces.csv` 后得到：

```text
all: completed=10, p50≈24471.897ms, p90≈40478.155ms, max≈47937.265ms
dominant_bottleneck=tool_iteration_overhead
top_stage_by_share=tool_latency_ms, top_stage_share≈0.744
default: p50≈18200.757ms, dominant_bottleneck=tool_iteration_overhead
react_agent: p50≈36427.353ms, dominant_bottleneck=tool_iteration_overhead
chat: endpoint_total_latency only
```

关键判断：阶段 33 的 FAISS-only 和 query embedding cache 已经把 vector/FAISS 查询成本压到次要位置；真实慢点主要来自 answer/tool 总耗时，react_agent 还叠加 planner latency。

关键决策：阶段 34 后续报告应建议优先评估 prompt 长度、MIMO answer generation 延迟、ReAct planner prompt/轮数和 rerank recall，而不是优先重写 FAISS。

## 观察 13：真实 Judge 完成但质量门禁仍是 review_required

Phase 5 新增 `scripts/judge_stage34_generation_quality.py`，先 dry-run，再显式执行：

```text
python scripts\judge_stage34_generation_quality.py --execute --limit 4
```

真实结果：

```text
completed_rows=4
avg_faithfulness=0.925
avg_answer_coverage=0.675
avg_citation_support=0.613
avg_refusal_correctness=1.000
avg_conciseness=0.887
avg_safety_leak_check=0.750
high=0, medium=4, low=0
judge_quality_gate=review_required
```

关键判断：真实 Judge 没有给出 high 阻断，但 citation_support 与 answer_coverage 不足，尤其 `stage29_wiki_hydraulic_engineering` 的 answer_coverage/citation_support 为 0，需要人工复核。阶段 34 不能把 Judge 结果写成 pass。

关键决策：Phase 6 决策报告中，Judge 分支应给出 `review_required`，并建议后续先处理 citation/coverage 或 prompt/检索证据装配，而不是直接上更复杂 ReAct。

## 观察 14：阶段 34 总决策是先做小优化和复核，延后真 LLM 自主 ReAct

Phase 6 输出：

```text
embedding_decision=keep_glm
latency_primary_bottleneck=tool_iteration_overhead
chat_provider_next_action=keep_flash_planner_pro_answer_and_tune_answer_prompt_length_or_top_k
judge_quality_gate=review_required
stage30_overall_score=83.17
phase35_recommendation=phase35_should_keep_glm_default_and_use_jina_only_as_rollback_reference_and_evaluate_tool_calling_protocol_migration_to_merge_planner_and_answer_into_one_llm_call_and_tune_answer_prompt_length_or_top_k_or_streaming_first_token_and_review_judge_medium_risk_answers
submit_state=user_confirmed_ready_for_commit_tag_push_merge
```

关键判断：阶段 34 的证据支持保留 GLM-Embedding-3 默认，不继续推进 Jina 分流，也不支持马上进入真 LLM 自主 ReAct。更稳的 Phase 35 方向是：稳定 GLM 默认 embedding 路径，再压 prompt/provider/工具轮数，最后补 Judge medium 风险答案的人工复核。

关键决策：阶段 34 收尾报告先明确“未提交、等待人工核验”；用户确认后允许进入提交、打 tag、推送和合并流程。

## 观察 15：收尾验证通过，但仍保持人工核验门禁

阶段 34 收尾已完成聚焦测试、全量 pytest、阶段 30 分数复核和浏览器 smoke：

```text
阶段 34 + ReAct 聚焦测试：32 passed
全量 pytest：666 passed
stage30 score：overall=83.17 grade=B release_decision=review_required
browser smoke：desktop 与 390x844 mobile Agent 查询通过，均有折叠思考过程和最终答案，无横向溢出，console errors=0
```

关键判断：自动化和浏览器回归说明阶段 34 改动没有破坏默认 Agent、ReAct trace、全量测试和前端主要路径；但保留 GLM 默认的 embedding 决策、tool/answer 瓶颈归因和 Judge medium 风险样例仍属于需要用户人工确认的发布门禁。

关键决策：阶段 34 现在停在人工核验前状态；不执行 `git add`、commit、tag、push 或 PR。

## 观察 16：LLM-driven planner 暴露的是协议层延迟问题

Claude 的复核指出：主流 agent（Claude Code、Codex、Cursor Composer、LangGraph `create_react_agent` 一类）通常是一轮 agent step 一次 LLM 调用。模型在同一个响应里要么输出最终文本，要么输出结构化 `tool_calls`；框架执行工具后把 tool result 追加进 history，再进入下一轮。

本项目阶段 34 的 LLM-driven planner 实验则是两次往返协议：

```text
planner LLM call -> 解析 JSON action -> 执行工具 -> answer LLM call
```

这意味着 1 个 ReAct iteration 可能消耗 2 次 MIMO 往返。MIMO 这类慢/reasoning 模型单次调用已经可能达到几十秒；拆成 planner + answer 后，延迟会按 iteration 放大。这解释了为什么真实 trace 的 p90 从早期约 37.97s 上升到后续 LLM planner 实验中的约 89.69s，慢点不是单纯 prompt 可修，而是协议层设计不贴近主流 tool-calling agent。

关键判断：阶段 34 不应继续硬调 MIMO planner prompt。正确方向是在阶段 34 内保留这次反向退化实验作为证据，同时把 planner 改成显式配置的轻量 provider；后续再独立评估 tool-calling 单次往返架构、planner timeout fallback 和 planner cache。

关键决策：阶段 34 已把 LLM planner 收敛为受控分层路由：`planner_chat_provider=None` 时保持确定性短路兼容路径，显式配置 `PLANNER_CHAT_*` 时用轻量 planner 驱动 action 选择；决策报告把 next action 写成 `keep_flash_planner_pro_answer_and_tune_answer_prompt_length_or_top_k`，并保留 tool-calling 架构迁移为阶段 35 候选方向。

## 风险与防线

- 风险：真实 Jina/GLM API 失败。
  - 防线：写 `skipped` / `error` 与脱敏原因，不伪造成通过。
- 风险：真实 Judge 泄露 provider 原始响应。
  - 防线：只保存分数、短理由、risk 和 next_action，不保存 raw response。
- 风险：latency trace 保存完整问题、答案或受限全文。
  - 防线：保存 query_id、类别、短摘要或脱敏字段，不保存完整受限内容。
- 风险：阶段 34 演变成完整质量平台或新 Agent 架构。
  - 防线：只做诊断、评测、报告和必要小修，不做真 LLM 自主 ReAct。
- 风险：同环境对照不公平。
  - 防线：同题集、同数据库、同 top_k、同 rerank 设置、同 source/citation 判定口径。
- 风险：配置 key 被写入 Git。
  - 防线：`.env` gitignored，文档中只写变量名和 redacted 状态。

## 阶段 34 核心决策输出

阶段 34 最终应能回答：

1. GLM-Embedding-3 相比 Jina 是否存在检索静默退化？
2. 如果有退化，应该回滚 Jina、保留 GLM 还是分 query 类型路由？
3. 真实 ReAct 慢查询的主要瓶颈是哪一段？
4. MIMO 是否真是主要耗时来源？
5. 生成答案是否通过真实 Judge 的 faithfulness、coverage、citation 和 refusal 检查？
6. 阶段 35 是否适合上真 LLM 自主 ReAct，还是应先做 prompt/provider/rerank 小优化？

## 新词解释

- 同环境对照：是什么 -> 在同一数据库、同一题集、同一脚本和同一指标下，只替换被比较对象；在本项目哪里出现 -> GLM-Embedding-3 vs Jina；作用 -> 避免不同环境导致比较不公平；面试怎么说 -> “我没有拿历史分数硬比，而是在同一运行环境下对两个 embedding provider 做 A/B 对照。”
- latency bottleneck：是什么 -> 端到端耗时里占比最高或 p90 最慢的环节；在本项目哪里出现 -> `latency_trace`；作用 -> 指导下一步优化方向；面试怎么说 -> “先用 trace 找慢点，再决定优化 provider、prompt、rerank 还是 ReAct 轮数。”
- LLM Judge：是什么 -> 用另一个模型按 rubric 给答案质量打分；在本项目哪里出现 -> 阶段 34 生成质量复核；作用 -> 补足规则评分无法判断语义忠实度的问题；面试怎么说 -> “LLM Judge 不进 CI，只作为人工发布前复核证据。”
- decision gate：是什么 -> 根据指标给出继续、回滚、分流或人工复核的门禁结论；在本项目哪里出现 -> 阶段 34 决策报告；作用 -> 把 CSV 变成可执行工程判断；面试怎么说 -> “评测不是为了堆表格，而是为了决定默认链路是否该变。”
- dry-run：是什么 -> 只生成模拟或空跑结果，不调用真实外部模型；在本项目哪里出现 -> 阶段 34 embedding/Judge 脚本默认模式；作用 -> 保证本地测试和 CI 不依赖真实 API；面试怎么说 -> “真实调用必须显式开启，默认路径可重复、低成本、无密钥依赖。”
- keep_glm：是什么 -> 保留 GLM-Embedding-3 作为默认 embedding provider；在本项目哪里出现 -> 阶段 34 Jina/GLM 对照最终决策；作用 -> 在 Jina 小幅指标优势不足以抵消额度可持续性风险时，选择更可持续的默认链路；面试怎么说 -> “我没有只看单个指标优势，而是把质量、成本和可持续性一起纳入默认 provider 决策。”
- tool calling / function calling：是什么 -> 模型一次响应里可以直接输出结构化工具调用请求；在本项目哪里出现 -> 阶段 35 候选架构迁移方向；作用 -> 把“决定调工具”和“生成内容”合并到同一次 LLM 往返里；面试怎么说 -> “主流 agent 一轮通常一次 LLM 调用，工具请求是响应的一部分，不需要单独 planner call。”
- reasoning model：是什么 -> 调用时会先进行较长内部推理再输出结果的模型；在本项目哪里出现 -> MIMO/DeepSeek-R1 这类候选 provider 的延迟分析；作用 -> 解释 planner 延迟为什么被两次往返协议放大；面试怎么说 -> “reasoning model 适合高价值推理，不适合每轮都做低信息量 planner JSON。”
- 两次往返 ReAct 协议：是什么 -> planner 决策和 answer 生成分成两次 LLM 调用；在本项目哪里出现 -> 阶段 34 LLM-driven planner 实验；作用 -> 暴露 MIMO planner p90 延迟放大的根因；面试怎么说 -> “这个问题不是 prompt 慢，而是协议把一次 tool-calling step 拆成了两次远程模型调用。”
- endpoint_total_latency：是什么 -> 只有端到端总耗时、没有内部阶段 trace 时的耗时分类；在本项目哪里出现 -> 阶段 34 `/chat` trace 采集；作用 -> 避免把缺失的内部 trace 误判成某个具体阶段瓶颈；面试怎么说 -> “没有分段证据时，我只报告总耗时，不编造内部瓶颈。”
- tool_iteration_overhead：是什么 -> Agent 工具调用阶段累计耗时最高，可能包括检索、回答生成和工具编排；在本项目哪里出现 -> 阶段 34 latency bottleneck summary；作用 -> 指出慢点不在单纯向量搜索，而在工具/回答链路；面试怎么说 -> “trace 显示慢在工具和生成，不是 FAISS，所以优化方向要转到 prompt/provider/轮数。”
- safety_leak_check：是什么 -> Judge 检查答案或中间结果是否泄露敏感字段、hidden thought 或供应商原始信息的分数；在本项目哪里出现 -> 阶段 34 LLM Judge；作用 -> 保证真实评测不牺牲安全边界；面试怎么说 -> “质量评测不只看答案对不对，也要看有没有泄露不该暴露的模型内部或密钥信息。”
- phase35_recommendation：是什么 -> 阶段 34 基于数据给下一阶段的建议；在本项目哪里出现 -> `stage34_decision_summary.csv`；作用 -> 防止“做完评测没有行动方向”；面试怎么说 -> “我把检索、性能和 Judge 三类证据合成下一阶段建议，而不是只交几张表。”

## 面试表达准备

```text
阶段 34 我没有急着继续上真 LLM 自主 ReAct，而是把阶段 33 建好的观测能力真正用起来。阶段 33 已经能输出 latency trace，也保留了 Jina 和 GLM 两套 embedding 资产，但 Jina 同环境 baseline 当时没有跑通，最终答案也没有真实 Judge 语义评分。

所以阶段 34 的重点是证据闭环：第一，用同一批问题、同一套数据库和同一评测脚本补齐 GLM-Embedding-3 2048 维和 Jina 1024 维的对照，判断是否有静默退化；第二，采集真实 RAG/ReAct 的 latency trace，算出 embedding、FAISS、rerank、planner、tool、answer generation 和首 token 的耗时占比；第三，用可选真实 LLM Judge 对少量代表答案评估忠实度、覆盖度、引用支撑和拒答正确性。

这个阶段的技术深度不在引入新框架，而在用真实数据做工程决策：Jina 指标略优但额度风险更高，因此保留 GLM 默认；后续优先优化 chat provider/prompt/rerank 和工具轮数。这样阶段 35 如果再做真 LLM 自主 ReAct，就是建立在质量、成本和性能地基清楚的基础上，而不是炫技。
```
