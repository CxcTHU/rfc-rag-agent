# 阶段 38 进度日志：默认 Tool Calling 链路生成质量攻坚与扩展评测闭环

## 当前状态

- 当前阶段：阶段 38 Phase 6 已完成，等待用户人工核验。
- 当前本地分支：`codex/phase-38-tool-calling-generation-quality`。
- 当前 Git 基线：`main / origin/main -> 25344a8 Merge phase 37 tool calling loop migration`。
- 最新阶段 tag：`phase-37-complete -> 62eff40 Complete phase 37 tool calling loop migration`（已合并到 main）。
- Phase 37 状态：开发、测试、真实评测、默认链路切换、提交、tag 和 main 合并均已完成。
- 阶段 38 目标分支：`codex/phase-38-tool-calling-generation-quality`（已从 Phase 37 合并后的 main 创建）。

## 阶段 37 验收基线

```text
Phase 37 核心改动（已进入 main）：
- tool_calling_agent 成为默认：前端 app.js、后端 agent.py query/stream 两个入口
- 三个 bug 修复：GBK encoding、assistant tool_calls protocol、ChatToolCall forward reference
- stream 层 mode 解析修复：auto-route 到 tool_calling_agent 时跳过 QueueStreamingChatModelProvider
- 真实评测：tool_calling 13.5s avg / react 28.0s avg，0 errors，8/8 refusal match

验证结果：
python -m pytest -q -> 758 passed
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute -> rows=9 execute=true failed=0
```

Phase 36 Judge 攻坚留下的基线：
```text
baseline: cov=0.655 / cit=0.640 / safety=1.000
outline_first: cov=0.703 / cit=0.685 / safety=1.000
answer_provider_ab: cov=0.772 / cit=0.820 / safety=0.950
三组均 review_required，未接生产
```

## 阶段 38 启动决策

```text
主线：默认 tool_calling_agent 链路的回答质量、引用质量和评测置信度补齐。
       Stage 30 维持 91.52 / A / pass；Judge gate 显式攻坚但不强行包装。
目标分支：codex/phase-38-tool-calling-generation-quality
预期范围：评测集扩充 20-30 条 + tool-calling 专属生成策略 + Judge 质量门真实攻坚 + 默认链路稳定性回归
不动项：embedding/rerank provider、外部数据源、架构迁移、多用户隔离、Stage 30 评分规则、deterministic 后处理进生产
风险点：Judge gate 攻坚仍可能失败；tool_calling_agent final answer 质量需 baseline 后才知起点
```

## Phase 日志（待 Codex 填充）

### Phase 0：启动校准与阶段 38 规划落盘

- 状态：已完成。
- 已阅读全部入口、进度、架构、数据源、Phase 37 review/decision 和本地规划文件。
- 已运行 `git status -sb`、`git log --oneline -5 --decorate`。
- 已确认 `phase-37-complete -> 62eff40` 是 `main / origin/main -> 25344a8` 的祖先，Phase 37 已合并。
- 已从 `main` 创建并切换到 `codex/phase-38-tool-calling-generation-quality`。
- 新词解释：`tool_calling_agent baseline Judge` 指先不加新生成策略，直接用当前默认 tool-calling 链路跑真实 Judge，得到 answer_coverage、citation_support、safety_leak_check 起点；它是后续 A/B 的对照组。

### Phase 1：阶段 38 设计文档与评测口径

- 状态：已完成。
- 已新增 `docs/stage38_tool_calling_generation_quality.md`。
- 已新增 `tests/test_stage38_design.py`。
- 已锁定 Judge 评测口径：先跑 `tool_calling_agent baseline Judge`，再做 `baseline vs structured_final_answer`；最终答案生成保持 tool-calling 原生 final synthesis，不硬接旧 `answer_with_citations`。
- 已运行 `python -m pytest tests/test_stage38_design.py -q`，结果 `8 passed`。

### Phase 2：评测集扩充到 20-30 条

- 状态：已完成。
- 已新增 `scripts/evaluate_stage38_tool_calling_quality.py`，输出 `stage38_tool_calling_quality_results.csv`、`stage38_tool_calling_quality_summary.csv`，并预留 real-provider 输出路径。
- 已新增 `tests/test_stage38_tool_calling_eval.py`。
- 评测集已扩展到 24 条，覆盖 16 类场景和 tool-calling edge case。
- 已运行 `python -m pytest tests/test_stage38_tool_calling_eval.py -q`，结果 `5 passed`。
- 已运行 `python scripts/evaluate_stage38_tool_calling_quality.py`，结果：`react_agent errors=0 same_refusal=24/24 same_top_source=24/24`；`tool_calling_agent errors=0 same_refusal=23/24 same_top_source=20/24`。

### Phase 3：Tool Calling 专属 Final Answer 生成策略

- 状态：已完成。
- 已在 `ToolCallingAgentService` 增加 `baseline` / `structured_final_answer` 策略参数，默认使用 `structured_final_answer`。
- 已把结构化生成要求接入 tool-calling 原生 final synthesis prompt，覆盖常规 tool loop、evidence convergence 和 citation repair。
- `baseline` 保留为 Phase 4 A/B 对照；未硬接旧 `answer_with_citations`，未接 `citation_validator`。
- 已运行 `python -m pytest tests/test_tool_calling_agent_service.py tests/test_stage38_design.py tests/test_stage38_tool_calling_eval.py -q`，结果 `28 passed`。
- 已重跑 `python scripts/evaluate_stage38_tool_calling_quality.py`，结果 `tool_calling_agent errors=0 same_refusal=23/24 same_top_source=20/24`。

### Phase 4：Judge 质量门真实攻坚

- 状态：已完成。
- 已新增 `scripts/judge_stage38_tool_calling_quality.py` 和 `tests/test_stage38_tool_calling_judge.py`。
- 已运行 `python -m pytest tests/test_stage38_tool_calling_judge.py -q`，结果 `4 passed`。
- 已运行 `python scripts/judge_stage38_tool_calling_quality.py --limit 24` dry-run，生成 48 行计划结果。
- 已运行 `python scripts/judge_stage38_tool_calling_quality.py --execute --limit 24 --timeout-seconds 180`，完成 24 cases x 2 strategies 真实 Judge。
- 真实结果：baseline `cov=0.869 / cit=0.794 / safety=1.000 / gate=review_required`；structured_final_answer `cov=0.808 / cit=0.729 / safety=1.000 / gate=review_required`。
- 已新增 `docs/stage38_tool_calling_quality_decision.md` 草稿，明确两组均未过 Judge gate，不强行包装。

### Phase 5：默认链路稳定性回归

- 状态：已完成。
- 已确认前端默认 `mode` 为 `tool_calling_agent`。
- 已将 `/agent/query`、`/agent/query/stream` 的省略 `mode` 默认行为锁定为 `tool_calling_agent`。
- 显式 `mode="default"`、`mode="react_agent"`、`mode="agentic"`、`mode="tool_calling_agent"` 均保留；其中 `react_agent` 继续作为显式回滚路径。
- 已增强 `scripts/run_production_smoke.py`：新增默认 query/stream 用例，增加 `expected_mode`、`actual_mode`、`mode_matched` 字段，mode 不匹配会失败。
- 已补 `ToolCallingAgentService` provider capability 护栏：provider 不支持 `generate_with_tools` 时返回受控 503。
- 已运行 `python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_run_production_smoke.py -q`，结果 `44 passed`。
- 已运行 `python -m pytest tests/test_stage38_design.py tests/test_stage38_tool_calling_eval.py tests/test_stage38_tool_calling_judge.py tests/test_tool_calling_agent_service.py -q`，结果 `32 passed`。
- 已运行 `python scripts/run_production_smoke.py`，结果 `rows=11 execute=false failed=0`。
- 已重跑 `python scripts/evaluate_stage38_tool_calling_quality.py`，结果 `tool_calling_agent errors=0 same_refusal=23/24 same_top_source=20/24`。
- 新词解释：`mode_matched` 是 production smoke 的默认链路校验字段，表示响应里的实际 `mode` 是否等于该用例期望的 mode。

### Phase 6：裁定报告、文档与阶段收尾

- 状态：已完成。
- 已更新普通文档：`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage38_tool_calling_quality_decision.md`。
- 已新增 `docs/phase_reviews/phase-38.md`。
- 已补齐 Obsidian：阶段 38 目录、Phase 汇报索引、Phase 0-6 小汇报、阶段主页、阶段汇报索引和阶段索引。
- 已运行 `python -m pytest -q`，结果 `780 passed`。
- 已运行 `python scripts/score_stage30_quality.py`，结果 `overall=91.52 grade=A release_decision=pass`。
- 已运行 `python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120`，结果 `rows=11 execute=true failed=0`。
- 浏览器 smoke：桌面最新回答 `mode=tool_calling_agent`、有引用、console errors=0、horizontal overflow=false；390x844 移动端 console errors=0、horizontal overflow=false。
- 用户人工核验前追加 citation gap 补强：已新增离线分析脚本，确认原 structured 主要是 prompt citation gap；已把 `structured_final_answer` 优化为 compact citation-first。
- 已运行 `python -m pytest tests/test_tool_calling_agent_service.py tests/test_stage38_citation_gap_analysis.py tests/test_stage38_tool_calling_eval.py tests/test_stage38_tool_calling_judge.py -q`，结果 `27 passed`。
- 已运行 `python scripts/evaluate_stage38_tool_calling_quality.py`，结果 `tool_calling_agent errors=0 same_refusal=23/24 same_top_source=20/24`。
- 已运行 `python scripts/judge_stage38_tool_calling_quality.py --execute --limit 24 --timeout-seconds 180`，最终结果：structured_final_answer `cov=0.808 / cit=0.867 / safety=1.000 / gate=pass`。
- citation gap 补强后已运行最终验证：`python -m pytest -q -> 783 passed`；`python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`；production smoke execute `rows=11 failed=0`；浏览器桌面/390x844 只读 smoke 均无横向溢出、console errors=0。Browser runtime 文本输入受虚拟剪贴板限制，默认 mode 执行由 production smoke 覆盖。
- 当前停在用户人工核验前；未执行 `git add`、commit、tag、push 或 PR。

## 提交边界（贯穿全阶段）

- 尚未提交，等待用户人工核验。
- 不替换默认 embedding / rerank provider；不动 provider 拓扑。
- 不引入新外部数据源、不爬新网页、不切 chunk、不做架构迁移、不做多用户隔离。
- 不接 deterministic 后处理（含 citation_validator）进生产链路。
- 不改 Stage 30 评分权重、等级阈值、release_decision 规则。
- 不写 API key / Bearer token / raw provider response / reasoning_content / hidden thought / 受限全文进任何提交物。
## Six-Metric Gate Update

Stage 38 now uses a six-metric Judge gate after the user's review note. The gate requires all averages to be at least `0.80`: `faithfulness`, `answer_coverage`, `citation_support`, `refusal_correctness`, `conciseness`, and `safety_leak_check`.

The existing 48 real Judge rows were summarized again with:

```text
python scripts/judge_stage38_tool_calling_quality.py --summarize-existing
```

Result:

```text
baseline: faith=0.958 / cov=0.775 / cit=0.731 / refusal=0.958 / concise=0.960 / safety=1.000 / gate=review_required
structured_final_answer: faith=0.981 / cov=0.808 / cit=0.867 / refusal=0.921 / concise=0.925 / safety=1.000 / gate=pass
```

`structured_final_answer` remains the Stage 38 candidate. The two refusal-correctness anomalies remain a human-verification focus.
