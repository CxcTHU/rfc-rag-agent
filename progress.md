# 阶段 34 进度日志：RAG 性能瓶颈诊断、Embedding 迁移决策与真实 Judge 质量复核

## 当前状态

- 当前阶段：阶段 34 Phase 7 + 阶段中追加的 Phase 8（LLM-driven planner + 分层 chat provider）已完成，停在用户人工核验前。
- chat provider 拓扑：Paratera DeepSeek-V4-Flash (planner) + Paratera DeepSeek-V4-Pro (answer)；MIMO 完全退出。
- react_agent 真实延迟：p50 由 MIMO baseline 87.9s 降至 39.1s（-55%），p90 由 95.2s 降至 55.0s（-42%），10/10 完成；refusal_boundary 由 LLM 第 1 轮即正确 refuse（3.5s）。
- 当前本地分支：`codex/phase-34-rag-diagnosis-embedding-judge`。
- 当前 Git 基线：`main / origin/main -> c06d0a3 Merge phase 33 rag performance embedding validation`。
- 阶段 tag：`phase-33-complete -> 0bad9e1 Complete phase 33 rag performance embedding validation`。
- tag 合并状态：`phase-33-complete` 是 `main` 的祖先。
- 当前提交边界：已有阶段 34 规划文件、设计文档、embedding 对照、latency trace、瓶颈分析、真实 Judge、决策报告脚本/测试/报告、普通文档和 Obsidian 改动；不执行 `git add`、commit、tag、push 或 PR。

## 阶段 33 验收基线

```text
阶段 33 功能提交：0bad9e1 Complete phase 33 rag performance embedding validation
阶段 33 merge commit：c06d0a3 Merge phase 33 rag performance embedding validation
phase-33-complete -> 0bad9e1
```

阶段 33 已完成：

```text
FAISS-only VectorIndexCache
query embedding cache
RAG/ReAct latency trace
GLM-Embedding-3 migration evaluation script
MIMO vs DeepSeek benchmark script
阶段 33 聚焦测试：16 passed
全量 pytest：643 passed
阶段 30 score：overall=83.17 grade=B release_decision=review_required
browser desktop/mobile smoke：通过
```

阶段 33 留给阶段 34 的主要缺口：

```text
jina_baseline 在阶段 33 中 skipped_missing_real_config
latency_trace 已接入但未做真实样本瓶颈分析
真实 LLM Judge 未覆盖最终生成答案语义评分
```

## 本次规划操作记录

已完成：

- 已读取 planning-with-files 技能规则。
- 已读取 `AGENT.MD`。
- 已读取 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 已读取根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 已读取 `obsidian-vault/模板/goal prompt.md`。
- 已运行 `git status -sb`、`git log --oneline -5 --decorate`。
- 已确认 `phase-33-complete -> 0bad9e1` 已合并到 `main -> c06d0a3`。
- 已尝试 planning-with-files session catchup；本机 `.claude` 路径下未找到 `session-catchup.py`，因此继续使用 Git 和本地文档上下文。
- 已将三份 Planning with Files 文件改写为阶段 34 规划。
- 已创建并切换到 `codex/phase-34-rag-diagnosis-embedding-judge` 分支。

已完成：

- 已完成阶段 34 真实 embedding 对照、latency trace 采集、真实 LLM Judge 和决策报告。
- 已同步普通文档与 Obsidian。

未执行：

- 未执行 `git add`、commit、tag、push 或 PR。

## 阶段 34 目标概述

阶段 34 要完成三条主线：

1. **同环境 embedding 对照**：用本地已补的 Jina 配置重跑 Jina baseline，与 GLM-Embedding-3 做公平对比。
2. **真实 latency trace 瓶颈诊断**：采集 10-20 条真实 RAG/ReAct 请求，计算各段耗时占比。
3. **真实 LLM Judge 质量复核**：用可选真实 judge 对最终答案的忠实度、覆盖度、引用支撑、拒答正确性和简洁度做脱敏评分。

阶段 34 的最终产物应是决策报告，而不是新默认模型或新 Agent 架构。

## 关键执行边界

- 不删除旧 Jina embedding/index。
- 不直接替换默认 MIMO provider。
- 不直接切默认 GLM/Jina embedding provider。
- 不新增外部数据源。
- 不做写入型 Agent 工具。
- 不做部署/运维。
- 不扩大成长期质量平台。
- 不上真 LLM 自主 ReAct；阶段 35 再评估。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不写入 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought 或受限全文。
- 阶段完成后停在用户人工核验前，不提交、不 tag、不 push、不建 PR。

## Phase 日志

### Phase 0：启动校准与阶段 34 规划落盘

状态：已完成。

本 Phase 解决的问题：确认阶段 34 的正确起点，并建立本阶段任务书、发现记录和进度日志。

RAG 链路位置：版本基线和协作边界，不改运行链路。

为什么现在做：阶段 34 会触发真实 provider、真实 judge 和多份评测 CSV，必须先确认阶段 33 已完成合并并固定安全边界。

已完成：

- 已读取项目规则、入口文档和阶段 33 关键状态。
- 已确认 `phase-33-complete -> 0bad9e1`，`main -> c06d0a3`。
- 已确认 `phase-33-complete` 已合并到 main。
- 已改写三份 Planning with Files 文件。

验证状态：

```text
git status -sb: 当前分支为 main，初始干净；规划文件改写后会出现未提交变更
git log --oneline -5 --decorate: main 顶部为 c06d0a3，phase-33-complete 指向 0bad9e1
git merge-base --is-ancestor phase-33-complete main: passed
```

### Phase 1：阶段 34 设计文档与评价口径

状态：已完成。

本 Phase 解决的问题：先固定阶段 34 的性能、检索和真实 Judge 评价口径，避免后续 Phase 把指标混在一起。

RAG 链路位置：evaluation/reporting 设计层，不进入默认 `/chat` 或 Agent 运行链路。

为什么现在做：阶段 34 后续会生成真实评测 CSV 和决策报告，必须先把指标、安全边界和不做事项写进文档并用测试锁住。

计划产物：

```text
docs/stage34_rag_diagnosis_embedding_judge.md
tests/test_stage34_design.py
```

已完成：

```text
新增 docs/stage34_rag_diagnosis_embedding_judge.md
新增 tests/test_stage34_design.py
python -m pytest tests\test_stage34_design.py -q -> 4 passed
```

### Phase 2：补齐 GLM-Embedding-3 vs Jina 同环境对照

状态：已完成。

本 Phase 解决的问题：补齐阶段 33 中 Jina baseline `skipped_missing_real_config` 的缺口，形成 Jina 与 GLM 的真实同环境对照。

RAG 链路位置：query embedding provider 与检索评测层，位于 HybridSearchService/VectorIndexCache 召回之前。

为什么现在做：没有同环境对照，就无法判断 GLM-Embedding-3 迁移是否存在静默退化，也无法决定阶段 35 是否继续沿 GLM 优化。

计划产物：

```text
data/evaluation/stage34_embedding_comparison_results.csv
data/evaluation/stage34_embedding_comparison_summary.csv
```

已完成：

```text
修复 scripts/evaluate_stage33_embedding_migration.py 的 Jina/GLM 专用 .env 读取兜底
新增 tests/test_stage34_embedding_comparison.py
python -m pytest tests\test_stage34_embedding_comparison.py tests\test_stage33_embedding_validation.py -q -> 4 passed
python scripts\evaluate_stage33_embedding_migration.py --execute-real --out-results data\evaluation\stage34_embedding_comparison_results.csv --out-summary data\evaluation\stage34_embedding_comparison_summary.csv --top-k 5
jina_baseline completed: p@1=0.667, p@3=0.800, p@5=0.933, coverage=0.670, avg_latency≈1489.29ms
glm_candidate completed: p@1=0.667, p@3=0.867, p@5=0.867, coverage=0.637, avg_latency≈1491.38ms
decision=keep_glm
reason=Jina 在 precision@5 与 coverage 上略优，但额度可持续性风险更高；保留 GLM-Embedding-3 默认，Jina 仅作历史对照和回滚参考
```

### Phase 3：采集真实 RAG/ReAct latency trace 数据集

状态：已完成。

本 Phase 解决的问题：把阶段 33 已接入的 trace 字段变成真实样本数据，覆盖 default、react_agent 和 `/chat` 端到端耗时。

RAG 链路位置：真实 `/agent/query`、`react_agent` 和 `/chat` 运行观测层。

为什么现在做：没有真实分段耗时，就无法判断瓶颈在 embedding、vector/FAISS、rerank、planner、tool 还是 answer generation。

计划产物：

```text
scripts/collect_stage34_latency_traces.py
data/evaluation/stage34_latency_traces.csv
```

已完成：

```text
更新 app/services/agent/service.py：default Agent 接入安全 latency_trace
新增 scripts/collect_stage34_latency_traces.py
新增 tests/test_stage34_latency_collection.py
更新 tests/test_react_latency_trace.py
python -m pytest tests\test_stage34_latency_collection.py tests\test_react_latency_trace.py -q -> 6 passed
python scripts\collect_stage34_latency_traces.py --execute-real --output data\evaluation\stage34_latency_traces.csv
stage34 latency traces: completed=10/10
```

### Phase 4：瓶颈归因与优化决策报告

状态：已完成。

本 Phase 解决的问题：把 trace CSV 里的分段耗时汇总成 p50/p90、阶段占比和主要瓶颈结论。

RAG 链路位置：performance analysis/reporting 层，不改默认运行链路。

为什么现在做：只有统计归因后，才能判断后续应该优化 embedding、FAISS、rerank、planner、tool 还是 answer generation。

计划产物：

```text
scripts/analyze_stage34_latency_bottlenecks.py
data/evaluation/stage34_latency_bottleneck_summary.csv
docs/stage34_latency_bottleneck_report.md
tests/test_stage34_latency_analysis.py
```

已完成：

```text
新增 scripts/analyze_stage34_latency_bottlenecks.py
新增 tests/test_stage34_latency_analysis.py
python -m pytest tests\test_stage34_latency_analysis.py -q -> 3 passed
python scripts\analyze_stage34_latency_bottlenecks.py
输出 data/evaluation/stage34_latency_bottleneck_summary.csv
输出 docs/stage34_latency_bottleneck_report.md
all final: p50≈17739.698ms, p90≈52216.255ms, dominant_bottleneck=tool_iteration_overhead
react_planner_decision=阶段 34 已落地受控分层 chat provider；planner_chat_provider=None 时保持确定性短路兼容路径，显式配置 PLANNER_CHAT_* 时启用轻量 LLM planner
```

### Phase 5：真实 LLM Judge 生成质量复核

状态：已完成。

本 Phase 解决的问题：补足规则评分不能判断最终答案语义忠实度、覆盖度和引用支撑的问题。

RAG 链路位置：answer evaluation/reporting 层，不进入默认回答链路。

为什么现在做：Embedding 对照和 latency 只能说明召回与性能，不能说明最终答案是否真正可靠。

计划产物：

```text
scripts/judge_stage34_generation_quality.py
data/evaluation/stage34_llm_judge_results.csv
data/evaluation/stage34_llm_judge_summary.csv
tests/test_stage34_llm_judge.py
```

已完成：

```text
新增 scripts/judge_stage34_generation_quality.py
新增 tests/test_stage34_llm_judge.py
python -m pytest tests\test_stage34_llm_judge.py -q -> 3 passed
python scripts\judge_stage34_generation_quality.py --limit 4 -> dry_run, no fake scores
python scripts\judge_stage34_generation_quality.py --execute --limit 4 -> completed=4/4, gate=review_required
avg_faithfulness=0.925
avg_answer_coverage=0.675
avg_citation_support=0.613
avg_refusal_correctness=1.000
high=0, medium=4, low=0
```

### Phase 6：Embedding / Provider / 默认链路决策汇总

状态：已完成。

本 Phase 解决的问题：把 embedding、性能和 Judge 三类 CSV 合并为可执行工程决策。

RAG 链路位置：阶段 34 quality decision/reporting 层。

为什么现在做：阶段 34 的目标不是堆评测文件，而是决定 GLM/Jina、MIMO/DeepSeek、prompt/rerank 和 Phase 35 的方向。

计划产物：

```text
scripts/build_stage34_decision_report.py
data/evaluation/stage34_decision_summary.csv
docs/stage34_rag_diagnosis_decision_report.md
tests/test_stage34_decision_report.py
```

已完成：

```text
新增 scripts/build_stage34_decision_report.py
新增 tests/test_stage34_decision_report.py
python -m pytest tests\test_stage34_decision_report.py -q -> 1 passed
python scripts\build_stage34_decision_report.py
输出 data/evaluation/stage34_decision_summary.csv
输出 docs/stage34_rag_diagnosis_decision_report.md
embedding_decision=keep_glm
latency_primary_bottleneck=tool_iteration_overhead
judge_quality_gate=review_required
phase35_recommendation=phase35_should_keep_glm_default_and_use_jina_only_as_rollback_reference_and_evaluate_tool_calling_protocol_migration_to_merge_planner_and_answer_into_one_llm_call_and_tune_answer_prompt_length_or_top_k_or_streaming_first_token_and_review_judge_medium_risk_answers
```

### Phase 7：文档、Obsidian 与阶段收尾验证

状态：已完成。

计划产物：

```text
README.md
docs/progress.md
docs/architecture.md
docs/data_sources.md
AGENT.MD（按需）
docs/phase_reviews/phase-34.md
obsidian-vault/阶段/阶段 34 - RAG性能瓶颈诊断与Embedding Judge决策.md
obsidian-vault/阶段汇报/阶段 34 - RAG性能瓶颈诊断与Embedding Judge决策/
```

已完成：

```text
更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD
新增 docs/phase_reviews/phase-34.md
建立 obsidian-vault/阶段/阶段 34 - RAG性能瓶颈诊断与Embedding Judge决策.md
建立阶段 34 Phase 汇报索引与 Phase 0-7 小汇报
更新 obsidian-vault/阶段汇报索引.md
```

验证状态：

```text
python -m pytest tests\test_react_llm_planner.py tests\test_react_agent_service.py tests\test_react_latency_trace.py tests\test_react_stream_events.py tests\test_stage34_design.py tests\test_stage34_embedding_comparison.py tests\test_stage34_latency_collection.py tests\test_stage34_latency_analysis.py tests\test_stage34_llm_judge.py tests\test_stage34_decision_report.py -q -> 32 passed
python -m pytest -q -> 666 passed
python scripts\score_stage30_quality.py -> overall=83.17 grade=B release_decision=review_required
Browser smoke -> desktop and 390x844 mobile Agent query passed, thought collapse and final answer present, horizontal overflow=false, console errors=0
```

## 当前遗留风险与人工核验重点

- 本地 `.env` 已配置 Jina 对照变量，但 key 不得写入任何可提交文件。
- 阶段 34 会调用真实 provider，网络、限流或余额失败必须写成 skipped/error，不能伪造成 pass。
- 真实 LLM Judge 结果不能替代阶段 30 的 `83.17` 总分，只能作为阶段 34 决策证据。
- latency trace 指向 tool/answer 链路与 ReAct planner 成本，本阶段只输出决策建议，不直接切默认 provider。

## 面试表达草稿

```text
阶段 34 我会把阶段 33 建好的观测和评测能力真正用于决策。阶段 33 已经优化了 FAISS-only 加载、加了 query embedding cache 和 latency trace，但还没有闭环三个问题：GLM 迁移是否真的不退化、真实慢查询到底慢在哪里、最终生成答案的语义质量是否可靠。

所以阶段 34 会用同环境 Jina vs GLM 对照解决检索质量问题，用 10-20 条真实 RAG/ReAct trace 解决性能瓶颈问题，再用可选真实 LLM Judge 解决答案忠实度和覆盖度问题。最后把三类证据合并成决策报告：Jina 虽在 precision@5 和 coverage 上略优，但额度可持续性风险更高，因此保留 GLM-Embedding-3 默认，Jina 只作为历史对照和回滚参考；阶段 34 已落地受控分层 chat provider，缺省配置保留确定性短路兼容路径，显式配置 PLANNER_CHAT_* 时启用轻量 LLM planner，后续再独立评估 tool-calling 单次往返架构。
```
