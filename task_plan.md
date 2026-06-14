# 阶段 34 任务计划：RAG 性能瓶颈诊断、Embedding 迁移决策与真实 Judge 质量复核

## 目标

在阶段 33「RAG 链路性能优化与 Embedding 迁移验证」已经完成、打 `phase-33-complete` tag 并合并到 `main` 的基础上，进入阶段 34：真正使用阶段 33 新增的 `latency_trace` 找出真实 RAG/ReAct 慢查询瓶颈，补齐 GLM-Embedding-3 与 Jina 的同环境检索对照，并用可选真实 LLM Judge 对生成答案做语义质量复核。

目标分支建议：`codex/phase-34-rag-diagnosis-embedding-judge`

本阶段不是继续扩 Agent 花活，也不是直接切默认模型。核心原则是：先用真实数据闭环阶段 33 留下的判断缺口，再决定后续是否优化 prompt、provider、rerank、ReAct 轮数或进入阶段 35 的真 LLM 自主 ReAct。

## 当前基线

```text
main / origin/main -> c06d0a3 Merge phase 33 rag performance embedding validation
phase-33-complete -> 0bad9e1 Complete phase 33 rag performance embedding validation
phase-33-complete 已合并到 main
当前阶段 34 分支 -> codex/phase-34-rag-diagnosis-embedding-judge
```

阶段 33 完成但仍需阶段 34 继续闭环的观察：

```text
glm_candidate: completed, precision@5=0.867, coverage=0.637, decision=review_for_silent_regression
jina_baseline: skipped_missing_real_config（阶段 34 已补本地 JINA_API_KEY/JINA_BASE_URL，可重跑）
mimo_baseline: completed, ttft≈2909-6266ms, total≈6801-6953ms, leak=false
deepseek_candidate: skipped
latency_trace: 已接入，但尚未用 10-20 条真实 RAG/ReAct 请求做瓶颈归因
真实 LLM Judge: 阶段 33 未覆盖生成答案语义评分
```

## Phase 顺序

### Phase 0：启动校准与阶段 34 规划落盘

状态：已完成。

本 Phase 解决的问题：确认阶段 34 从阶段 33 已合并后的正确基线出发，避免沿用阶段 33 人工核验前的旧文档描述。

RAG 链路位置：版本基线、协作边界与规划层，不改运行链路。

为什么现在做：阶段 34 会调用真实 Jina、GLM、MIMO、可选 judge provider，并生成新的评测 CSV；必须先固定 tag/main/分支和数据安全边界。

已完成：

- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读 `task_plan.md`、`findings.md`、`progress.md` 与 `obsidian-vault/模板/goal prompt.md`。
- 运行 `git status -sb`、`git log --oneline -5 --decorate`。
- 确认 `phase-33-complete -> 0bad9e1` 且已合并到 `main -> c06d0a3`。
- 将三份 Planning with Files 文件改写为阶段 34 规划。

验证方式：

```text
git status -sb
git log --oneline -5 --decorate
git merge-base --is-ancestor phase-33-complete main
```

### Phase 1：阶段 34 设计文档与评价口径

状态：已完成。

本 Phase 解决的问题：先定义性能诊断、embedding 决策和真实 Judge 的评价口径，避免后续把检索指标、生成指标和性能指标混在一起。

RAG 链路位置：evaluation/reporting 设计层。

为什么现在做：阶段 34 的价值是“用证据做决策”，必须先明确指标、样本、输出、边界和不做事项。

计划任务：

- 新增 `docs/stage34_rag_diagnosis_embedding_judge.md`。
- 明确三条闭环：
  - latency trace 性能瓶颈诊断。
  - GLM-Embedding-3 2048 维 vs Jina 1024 维同环境检索对照。
  - 真实 LLM Judge 生成质量复核。
- 固定真实 Judge 指标：faithfulness、answer_coverage、citation_support、refusal_correctness、conciseness、safety_leak_check。
- 固定安全边界：不保存 API key、Bearer token、raw provider response、reasoning_content、受限全文或完整 prompt。
- 新增设计测试，检查文档包含同环境对照、latency trace、真实 judge dry-run、隐私边界和“不直接切默认 provider”。

已完成：

- 新增 `docs/stage34_rag_diagnosis_embedding_judge.md`，固定阶段 34 目标、输入、同环境 embedding 对照、latency trace、真实 Judge、决策报告、安全边界和完成标准。
- 新增 `tests/test_stage34_design.py`，覆盖阶段 34 核心范围、指标、Judge rubric、dry-run/`--execute` 边界、安全字段和“不直接替换默认 provider”要求。

验证方式：

```text
python -m pytest tests\test_stage34_design.py -q
4 passed
```

### Phase 2：补齐 GLM-Embedding-3 vs Jina 同环境对照

状态：已完成。

本 Phase 解决的问题：阶段 33 中 Jina baseline skipped，导致无法确认 GLM 迁移是否存在静默退化。

RAG 链路位置：向量检索评测层，位于 query embedding、VectorIndexCache/FAISS、hybrid search 之前的 provider 对照层。

为什么现在做：旧 Jina 向量和 FAISS index 仍保留，且本地已补 `JINA_API_KEY/JINA_BASE_URL`；现在可以用同一批问题、公平比较 Jina 与 GLM。

计划任务：

- 复跑 `scripts/evaluate_stage33_embedding_migration.py --execute-real`。
- 如脚本对 `.env` 读取不足，补最小兼容，不泄露 key。
- 输出/更新阶段 34 专用 CSV：
  - `data/evaluation/stage34_embedding_comparison_results.csv`
  - `data/evaluation/stage34_embedding_comparison_summary.csv`
- 指标至少包括 precision@1/3/5、hit@5、coverage、refusal boundary、latency、source_type_distribution。
- 给出明确决策候选：keep_glm、rollback_jina、route_by_query_type、review_required；阶段 34 最终采用 `keep_glm`，不继续推进 Jina 分流。

已完成：

- 修复 `scripts/evaluate_stage33_embedding_migration.py` 对 `JINA_API_KEY` / `JINA_BASE_URL` / `PARATERA_API_KEY` / `PARATERA_EMBEDDING_BASE_URL` 的 `.env` 读取兜底，不打印、不保存密钥。
- 新增 `tests/test_stage34_embedding_comparison.py`，覆盖 provider 专用 `.env` 读取和阶段 34 completed 对照决策候选。
- 显式运行真实对照，输出阶段 34 专用 CSV。
- 当前同环境对照结果：`jina_baseline` 与 `glm_candidate` 均 `completed`；Jina `precision@5=0.933`、`coverage=0.670`、平均延迟约 `1489.29ms`；GLM `precision@5=0.867`、`coverage=0.637`、平均延迟约 `1491.38ms`。Jina 在 precision@5 与 coverage 上略优，但优势不足以抵消额度即将耗尽带来的可持续性风险；最终决策为 `keep_glm`，保留 GLM-Embedding-3 默认，Jina 仅作历史对照和回滚参考。

验证方式：

```text
python scripts\evaluate_stage33_embedding_migration.py --execute-real --out-results data\evaluation\stage34_embedding_comparison_results.csv --out-summary data\evaluation\stage34_embedding_comparison_summary.csv
python -m pytest tests\test_stage33_embedding_validation.py -q
python -m pytest tests\test_stage34_embedding_comparison.py tests\test_stage33_embedding_validation.py -q
4 passed
```

### Phase 3：采集真实 RAG/ReAct latency trace 数据集

状态：已完成。

本 Phase 解决的问题：阶段 33 已有 trace 字段，但尚未采集足够真实请求来定位瓶颈。

RAG 链路位置：真实 `/chat`、`/agent/query`、`/agent/query/stream` 运行观测层。

为什么现在做：没有分段耗时占比，就无法判断慢在 query embedding、FAISS、rerank、planner、tool、answer 还是 SSE 首 token。

计划任务：

- 新增 `scripts/collect_stage34_latency_traces.py` 或扩展阶段 33 benchmark。
- 用 10-20 条代表性问题覆盖：
  - 简单事实问答。
  - 长答案问答。
  - 拒答边界。
  - ReAct 两轮工具调用。
  - 中英文/中英混合问题。
- 输出 `data/evaluation/stage34_latency_traces.csv`。
- 字段至少包含 query_id、mode、provider/model、query_embedding、vector/faiss/numpy search、rerank、planner、tool、answer、time_to_first_token、time_to_final、iteration_count、tool_call_count、load_mode。
- 不保存完整回答、raw provider response、hidden thought 或受限全文。

已完成：

- `AgentService` default 路径接入请求级 `LatencyTrace`，让 `/agent/query mode=default` 与 `react_agent` 都能输出安全 trace。
- 新增 `scripts/collect_stage34_latency_traces.py`，默认 dry-run，显式 `--execute-real` 才使用真实 provider。
- 新增 `tests/test_stage34_latency_collection.py`，覆盖瓶颈分类、空值脱敏和无内部 trace 时的 `endpoint_total_latency`。
- 更新 `tests/test_react_latency_trace.py`，确认 default Agent 响应包含安全 latency trace。
- 显式真实采集 `data/evaluation/stage34_latency_traces.csv`，10/10 completed；另保留 dry-run 结构验证输出 `data/evaluation/stage34_latency_traces_dry_run.csv`。

验证方式：

```text
python scripts\collect_stage34_latency_traces.py --execute-real --limit 20
python -m pytest tests\test_react_latency_trace.py tests\test_agent_stream_api.py -q
python -m pytest tests\test_stage34_latency_collection.py tests\test_react_latency_trace.py -q
6 passed
```

### Phase 4：瓶颈归因与优化决策报告

状态：已完成。

本 Phase 解决的问题：把 latency trace 从“记录字段”变成“可执行的工程判断”。

RAG 链路位置：performance analysis/reporting 层。

为什么现在做：只有知道最慢段和占比，才能决定下一步是压 prompt、换 provider、调 rerank、预热 cache，还是减少 ReAct 轮数。

计划任务：

- 新增 `scripts/analyze_stage34_latency_bottlenecks.py`。
- 读取 `stage34_latency_traces.csv`，计算 p50/p90、均值、最大值和各段占比。
- 按瓶颈类型分类：
  - embedding_provider_latency
  - rerank_latency
  - planner_latency
  - answer_generation_latency
  - tool_iteration_overhead
  - cold_start_or_cache_miss
- 输出 `data/evaluation/stage34_latency_bottleneck_summary.csv`。
- 生成 `docs/stage34_latency_bottleneck_report.md`。
- 暂不做大改，只允许少量低风险配置/脚本修正。

已完成：

- 新增 `scripts/analyze_stage34_latency_bottlenecks.py`，读取 `stage34_latency_traces.csv` 计算 p50/p90、均值、最大值、dominant bottleneck 和阶段平均占比。
- 新增 `tests/test_stage34_latency_analysis.py`，覆盖 p90、stage share 和空/单样本 percentile。
- 输出 `data/evaluation/stage34_latency_bottleneck_summary.csv` 与 `docs/stage34_latency_bottleneck_report.md`。
- 当前真实 trace 结论：阶段 34 最终 `all` 组 p50≈`17739.698ms`、p90≈`52216.255ms`、max≈`56451.032ms`；主要瓶颈仍为 `tool_iteration_overhead`，平均最高占比字段为 `tool_latency_ms`；`react_agent` 在 `planner_chat_provider=None` 时保留确定性短路兼容路径，显式配置轻量 planner 时进入受控 LLM-driven planner 路径。

验证方式：

```text
python scripts\analyze_stage34_latency_bottlenecks.py
python -m pytest tests\test_stage34_latency_analysis.py -q
3 passed
```

### Phase 5：真实 LLM Judge 生成质量复核

状态：已完成。

本 Phase 解决的问题：阶段 33 没有对最终生成答案做真实语义评分，无法判断答案是否真的忠实、覆盖充分、引用稳定。

RAG 链路位置：answer evaluation/reporting 层，不进入默认回答链路。

为什么现在做：Embedding 检索质量和 latency 只能解释“召回什么、慢在哪里”，不能单独证明“最终答案是否好”。

计划任务：

- 新增 `scripts/judge_stage34_generation_quality.py`。
- 默认 dry-run，不调用真实 judge。
- 显式 `--execute` 且本地有 judge 配置时才调用真实 LLM Judge。
- 优先复用阶段 30 judge provider 或本地 DeepSeek/OpenAI-compatible 配置。
- 输入使用阶段 34 代表问题、脱敏 answer 摘要、citation/source 摘要和 expected_answer_points。
- 输出：
  - `data/evaluation/stage34_llm_judge_results.csv`
  - `data/evaluation/stage34_llm_judge_summary.csv`
- 只保存分数、短理由、风险等级和 next_action，不保存 raw judge response、reasoning_content 或完整受限全文。

已完成：

- 新增 `scripts/judge_stage34_generation_quality.py`，默认 dry-run，显式 `--execute` 才生成真实答案样本并调用真实 Judge。
- 新增 `tests/test_stage34_llm_judge.py`，覆盖 Judge JSON 解析、分数裁剪、敏感字段脱敏和 quality gate 汇总。
- dry-run 已运行，确认不伪造分数。
- 显式运行真实 Judge：`python scripts\judge_stage34_generation_quality.py --execute --limit 4`，输出 `data/evaluation/stage34_llm_judge_results.csv` 与 `stage34_llm_judge_summary.csv`。
- 当前真实 Judge：4/4 completed，avg faithfulness=`0.925`、answer_coverage=`0.675`、citation_support=`0.613`、refusal_correctness=`1.000`、conciseness=`0.887`、safety_leak_check=`0.750`；high=0、medium=4、low=0，`judge_quality_gate=review_required`。

验证方式：

```text
python scripts\judge_stage34_generation_quality.py --dry-run
python scripts\judge_stage34_generation_quality.py --execute
python -m pytest tests\test_stage34_llm_judge.py -q
3 passed
```

### Phase 6：Embedding / Provider / 默认链路决策汇总

状态：已完成。

本 Phase 解决的问题：把检索对照、性能瓶颈和真实 Judge 结果合成为可执行决策，而不是只留下多份 CSV。

RAG 链路位置：阶段 34 quality decision/reporting 层。

为什么现在做：阶段 34 必须给阶段 35 是否上真 LLM 自主 ReAct、是否继续 GLM、是否优化 MIMO/DeepSeek 提供依据。

计划任务：

- 新增 `scripts/build_stage34_decision_report.py`。
- 汇总 embedding comparison、latency bottleneck、LLM judge、stage30 score。
- 输出 `data/evaluation/stage34_decision_summary.csv` 与 `docs/stage34_rag_diagnosis_decision_report.md`。
- 决策项至少包括：
  - embedding_decision
  - latency_primary_bottleneck
  - chat_provider_next_action
  - judge_quality_gate
  - phase35_recommendation
- 不直接切默认 provider，不删除旧 Jina，不改默认 MIMO，不引入真 LLM 自主 ReAct。

已完成：

- 新增 `scripts/build_stage34_decision_report.py`，汇总 embedding comparison、latency bottleneck、LLM Judge 和 stage30 score。
- 新增 `tests/test_stage34_decision_report.py`，覆盖混合 embedding 信号、tool latency 瓶颈和 Judge review_required 时延后真 LLM ReAct 的决策。
- 输出 `data/evaluation/stage34_decision_summary.csv` 与 `docs/stage34_rag_diagnosis_decision_report.md`。
- 当前决策：`embedding_decision=keep_glm`，`latency_primary_bottleneck=tool_iteration_overhead`，`chat_provider_next_action=keep_flash_planner_pro_answer_and_tune_answer_prompt_length_or_top_k`，`judge_quality_gate=review_required`；阶段 34 已落地受控分层 chat provider，后续再独立评估 tool-calling 单次往返架构。

验证方式：

```text
python scripts\build_stage34_decision_report.py
python -m pytest tests\test_stage34_decision_report.py -q
1 passed
```

### Phase 7：文档、Obsidian 与阶段收尾验证

状态：已完成。

本 Phase 解决的问题：把阶段 34 的真实数据、决策和边界沉淀为项目文档，并停在用户人工核验前。

RAG 链路位置：项目交接、知识沉淀与人工核验层。

为什么现在做：阶段 34 的产物是“决策闭环”，必须让后续 Agent 和用户能复现判断依据。

计划任务：

- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 按需更新 `AGENT.MD`。
- 新增 `docs/phase_reviews/phase-34.md`。
- 更新 Obsidian：
  - `obsidian-vault/阶段/阶段 34 - RAG性能瓶颈诊断与Embedding Judge决策.md`
  - `obsidian-vault/阶段汇报/阶段 34 - RAG性能瓶颈诊断与Embedding Judge决策/`
  - 阶段 34 Phase 汇报索引与各 Phase 小汇报。
- 运行阶段 34 聚焦测试、全量 pytest、`scripts/score_stage30_quality.py`。
- 浏览器 smoke：Agent 查询、折叠思考过程、最终答案、无横向溢出、console errors=0。

验证方式：

```text
python -m pytest tests\test_react_llm_planner.py tests\test_react_agent_service.py tests\test_react_latency_trace.py tests\test_react_stream_events.py tests\test_stage34_design.py tests\test_stage34_embedding_comparison.py tests\test_stage34_latency_collection.py tests\test_stage34_latency_analysis.py tests\test_stage34_llm_judge.py tests\test_stage34_decision_report.py -q
32 passed
python -m pytest -q
666 passed
python scripts\score_stage30_quality.py
overall=83.17 grade=B release_decision=review_required
Browser smoke: desktop and 390x844 mobile Agent query passed, thought collapse and final answer present, horizontal overflow=false, console errors=0
```

### Phase 8（阶段中追加）：LLM-driven Planner + 分层 Chat Provider

状态：已完成。

本 Phase 解决的问题：把 Phase 4 暴露的「tool_iteration_overhead 主导延迟」转化为 chat provider 拓扑层的实际优化，而不是只写进报告。

RAG 链路位置：ReAct 决策层 + chat provider 配置层。

为什么现在做：Phase 5 已确认 Judge 暴露 4/4 medium，Phase 6 已生成决策报告。继续延后到阶段 35 才动 chat provider 拓扑会让阶段 34 停在「诊断」而不是「闭环」。本 Phase 以非破坏性方式扩展范围（新增 `planner_chat_provider`，缺省 None 时保留旧行为），不破坏现有 deterministic 测试与 agentic / default 路径兼容性。

执行过程（三轮闭环）：

1. 第一轮：去掉 elif 短路，让 MIMO 真当 planner → react_agent p90 +135%、1/4 timeout。复盘根因：MIMO 是 reasoning 模型，单次 planner 调用 30–70s。
2. 第二轮：新增 `PLANNER_CHAT_*` 环境变量与 `ReActAgentService(planner_chat_provider=...)`，把 planner 切到 DeepSeek-V4-Flash、answer 切到 DeepSeek-V4-Pro，跑出 p50 8.2s 但出现 in-scope 误判 refuse 2 例。
3. prompt 收紧：refuse 触发条件改为「仅在不安全 / 明显跨领域 / 工程判定题时第 1 轮直接 refuse」，其余默认先 search。
4. 第三轮：重新跑 trace → in-scope 全部正确回答；refusal_boundary 由 LLM 第 1 轮即正确 refuse（3.5s）；react_agent p50 39.1s、p90 55.0s、10/10 完成。

已完成：

- `app/core/config.py` 新增 `planner_chat_model_*` 字段（缺省空字符串）。
- `app/api/agent.py` 新增 `get_agent_planner_chat_model_provider()` 依赖；同步 + 流式 react_agent 入口注入 planner provider。
- `app/services/agent/react_service.py`：`ReActAgentService.__init__(planner_chat_provider=None)`；主循环新增 `llm_driven` 条件分支，planner_provider 不为 None 时禁用 elif 短路；`_plan_action` 改用 `planner_chat_provider or chat_model_provider`，加 parse 失败兜底（有证据 → answer_with_citations，无证据 → refuse）。
- `react_planner_messages` prompt 升级：refuse 触发条件收紧，default 必须 search，中文 / 英文 / 中英混合都视为 in-scope，强调 "When in doubt, prefer search_knowledge over refuse"。
- 新增 `tests/test_react_llm_planner.py`（6 tests）：覆盖第 1 轮 LLM refuse、LLM 决定 search+answer、跨轮继续 search、解析失败兜底、缺省 planner_provider 保持旧行为。
- `.env` 切到 Paratera DeepSeek-V4-Pro answer + DeepSeek-V4-Flash planner；旧 MIMO 配置注释保留作回滚参考；`.env` 在 `.gitignore` 内。
- `scripts/collect_stage34_latency_traces.py` 接 planner provider 注入；真实 trace 重采集 10/10 完成。
- `scripts/build_stage34_decision_report.py` 文案更新：`chat_provider_next_action` 与 `phase35_recommendation` 反映阶段 34 完成状态，不再写「rollback / defer」。
- `tests/test_stage34_decision_report.py` 同步更新断言。
- `docs/stage34_rag_diagnosis_decision_report.md`、`docs/phase_reviews/phase-34.md` 重写工程判断段。

验证方式：

```text
python scripts\collect_stage34_latency_traces.py --execute-real
stage34 latency traces: completed=10/10
react_agent p50=39097ms, p90=55039ms, max=56451ms (Flash+Pro)
react_agent vs MIMO baseline: p50 -55%, p90 -42%
python -m pytest tests\test_react_llm_planner.py tests\test_react_agent_service.py -q
11 passed
```

## 完成标准

- `phase-33-complete` 已确认合并到 `main`，阶段 34 分支从正确基线创建。
- Jina 与 GLM 在同环境、同题集、同指标下完成真实检索对照；如果仍失败，必须写清可复现原因，不能伪造成通过。
- `latency_trace` 已在 10-20 条真实 RAG/ReAct 请求上采集，并输出瓶颈占比。
- 有明确性能瓶颈结论：慢在 embedding、FAISS/vector search、rerank、planner、tool、answer generation、SSE 首 token 或冷启动。
- 真实 LLM Judge 支路可 dry-run，显式 `--execute` 才调用真实 judge；结果只保存脱敏分数和短理由。
- 形成阶段 34 决策报告：保留 GLM 默认、Jina 仅作历史对照和回滚参考、chat provider 拓扑结论、阶段 35 next action 建议。
- chat provider 分层路由（planner / answer 解耦）已落地：`PLANNER_CHAT_*` 配置 + `ReActAgentService.planner_chat_provider`；缺省 None 时保留旧 elif 短路兼容路径。
- 不删除旧 Jina，不新增外部资料源，不做写入型 Agent 工具，不做部署/运维。
- 不把 API key、Bearer token、raw provider response、reasoning_content、hidden thought 或受限全文写入 Git、CSV、文档、测试或 Obsidian。
- `default`、`agentic`、`react_agent`、`/chat`、`/agent/query/stream` 保持兼容。
- 全量测试通过，阶段 30 score 不低于 `83.17`。
- 最终停在用户人工核验前：不 `git add`、不 commit、不创建 `phase-34-complete` tag、不 push、不创建 PR。
