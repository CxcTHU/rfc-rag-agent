# 阶段 36 进度日志：生成可靠性与多轮体验稳定化

## 当前状态

- 当前阶段：阶段 36 开发、测试、文档与用户人工核验已完成，正在执行提交、tag、推送与 GitHub 合并。
- 当前本地分支：`codex/phase-36-generation-reliability-and-conversation-stability`。
- 当前 Git 基线：`main / origin/main -> dc751fb Merge pull request #5 from CxcTHU/codex/phase35-multiturn-intent-router`。
- 最新阶段 tag：`phase-35-complete -> 7877308 Complete phase 35 remediation with Judge gate documented`。
- tag 合并状态：`phase-35-complete` 是 `main` 的祖先；多轮意图路由补充（commit 0af4a87）已用户人工验收并合并到 main。
- 当前提交边界：用户已于 2026-06-15 明确授权执行 `git add`、commit、`phase-36-complete` tag、push 与 GitHub merge。

## 阶段 35 验收基线

```text
阶段 35 主线提交：7877308 Complete phase 35 remediation with Judge gate documented
阶段 35 多轮补充提交：0af4a87 Add phase 35 multiturn intent routing supplement
阶段 35 merge 链：c9097b1 + dc751fb
phase-35-complete -> 7877308（不移动）
```

阶段 35 完成：

```text
Stage 30 = 91.52 / A / pass（GLM, hybrid_rrf_tail，干净通过）
HybridRrfTailSearchService 接入 Brain 生产路径
citation_validator 已从生产 Brain 解耦，保留为离线评测工具
Judge gate 显式标注 FAIL：cov=0.41 / cit=0.64 / safety=1.00（GLM 链路）
ReAct planner 解析失败兜底改为 in-scope 先 search
多轮意图路由补充：翻译/转述、模型信息、能力说明、拒答原因（已合并 main）
react p50 ≈ 39s / p90 ≈ 55s
全量 pytest 698 passed
```

阶段 35 留给阶段 36 的开放项：

```text
Judge gate FAIL 仍未解决（cov 0.41 / cit 0.64）；阶段 35 续整改未试 outline-first 与 answer provider A/B
拒答信息单薄：refusal_reason 只有短文本，没有改写建议或检索摘要
生产 smoke 仍是手动跑，没有脚本化
多轮路由补充已合并，但未做完整回归集
真实 LLM Judge 样本仍只 10 条，统计噪声大
```

## 阶段 36 启动决策

```text
主线：生成可靠性 + 用户对话体验稳定化，不追分。
       Stage 30 维持 91.52 / A / pass；Judge gate 显式攻坚但不强行包装。
目标分支：codex/phase-36-generation-reliability-and-conversation-stability
预期范围：拒答可解释性 + 生产 smoke 自动化 + Judge gate 离线 A/B 攻坚（≤ 2 周）+ 多轮路由模块化辅线 + 文档收尾
不动项：chat provider 拓扑、embedding/rerank provider、外部数据源、写入型 Agent 工具、tool-calling 协议迁移、多用户隔离、Stage 30 评分规则、生产链路引入 deterministic 后处理
风险点：Judge gate 攻坚仍可能失败；要求 Codex 试过即诚实写归因，不再追指标
```

## Phase 日志（待 Codex 填充）

### Phase 0：启动校准与阶段 36 规划落盘

- 状态：已完成。
- 已读：`AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、阶段 35 review/remediation、Stage 35 设计、Judge summary 与 safety attribution、三份规划文件和 goal prompt 模板。
- Git 校准：`phase-35-complete -> 7877308`，`main -> dc751fb`，`phase-35-complete` 是 `main` 的祖先；未移动任何 tag。
- 分支：已从 `main` 创建并切换到 `codex/phase-36-generation-reliability-and-conversation-stability`。
- 提交边界：未执行 `git add`、commit、tag、push 或 PR。

### Phase 1：阶段 36 设计文档与评价口径

- 状态：已完成。
- 新增 `docs/stage36_generation_reliability_and_conversation_stability.md`，固定主线、辅线、不做事项、安全边界、Judge 离线门槛和最终验收标准。
- 新增 `tests/test_stage36_design.py`，用文档断言锁定阶段 36 的核心约束。
- 验证：`python -m pytest tests/test_stage36_design.py -q` -> `5 passed`。

### Phase 2：拒答可解释性升级

- 状态：已完成。
- 新增 `app/services/agent/refusal_explainer.py`，实现 off-topic 改写建议与 evidence_insufficient 安全检索摘要。
- `/agent/query` schema 未新增字段；解释追加到已有 `reasoning_summary`。
- `AgentToolbox.answer_with_citations()` 在拒答且无 sources 时补只读 hybrid 检索，用于生成真实来源摘要；不调用 LLM、不写库。
- 新增 `tests/test_refusal_explainer.py`，并补充 Agent API 拒答解释测试。
- 验证：`python -m pytest tests/test_refusal_explainer.py tests/test_agent_api.py tests/test_agent_tools.py tests/test_agent_service.py -q` -> `42 passed`。

### Phase 3：生产 smoke 自动化

- 状态：已完成。
- 新增 `scripts/run_production_smoke.py`，默认 dry-run，`--execute` 才访问真实端点。
- 覆盖 `/health`、`/quality-report`、`/quality-report/data.json`、正常 RAG、多轮转述、模型信息和 `/agent/query/stream`。
- 输出 `data/evaluation/stage36_production_smoke_results.csv`，仅包含安全字段。
- 新增 `tests/test_run_production_smoke.py`。
- 验证：`python -m pytest tests/test_run_production_smoke.py -q` -> `5 passed`。
- 验证：`python scripts/run_production_smoke.py` -> `rows=7 execute=false failed=0`。
- 真实 `--execute`：留到阶段收尾时启动服务后一键运行。

### Phase 4：Judge gate 显式离线攻坚（≤ 2 周）

- 状态：已完成（真实 20 题 A/B 已落盘，Judge gate 未通过，未包装通过）。
- 新增 `app/services/generation/outline_first_strategy.py`，作为离线候选策略，默认不接生产。
- 新增 `scripts/judge_stage36_strategy_ab.py`，覆盖 `baseline`、`outline_first`、`answer_provider_ab` 三组。
- 新增 `tests/test_stage36_judge_strategy_ab.py`。
- 新增/更新 `data/evaluation/stage36_judge_strategy_ab_results.csv`、`data/evaluation/stage36_judge_strategy_ab_summary.csv`、`docs/stage36_judge_strategy_decision.md`。
- 验证：`python -m pytest tests/test_stage36_judge_strategy_ab.py -q` -> `6 passed`。
- dry-run：`python scripts/judge_stage36_strategy_ab.py` -> `rows=60 queries=20 execute=false`。
- 真实执行：`python scripts/judge_stage36_strategy_ab.py --execute --limit 20 --timeout-seconds 180` -> completed_rows=60。
- 当前 Judge 结论：baseline `0.655/0.640/1.000`、outline_first `0.703/0.685/1.000`、answer_provider_ab `0.772/0.820/0.950`，三组均为 `review_required`。
- 不得宣称通过，不接生产；后续若继续攻坚，应先分析 answer_coverage 缺口。

### Phase 5：多轮路由模块化（辅线）

- 状态：已完成。
- 新增 `app/services/agent/intent_router.py`，抽取多轮转述、模型信息、能力说明、拒答原因和 history prefix 处理。
- `app/api/agent.py` 已调用 intent router 纯函数，API 层保留会话编排。
- 新增 `tests/test_intent_router.py`，覆盖 8 类意图回归集。
- 验证：`python -m pytest tests/test_intent_router.py tests/test_agent_api.py -q` -> `30 passed`。
- 遗留观察：英文 `it` 仍是子串触发，可能误命中 `quality`/`durability`；阶段 36 不改变历史行为，只记录后续可优化点。

### Phase 6：文档、Obsidian 与阶段收尾验证

- 状态：已完成，用户人工核验已通过，进入提交合并收尾。
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`；按协作规则未抢改 `AGENT.MD`。
- 已新增 `docs/phase_reviews/phase-36.md`、`docs/stage36_judge_strategy_decision.md`。
- 已新增 Obsidian 阶段 36 阶段页、Phase 0-6 汇报、阶段 36 汇报索引，并同步首页、阶段索引、阶段汇报索引。
- 验证：`python -m pytest -q` -> `724 passed`。
- 验证：`python scripts/score_stage30_quality.py` -> `stage30 quality score overall=91.52 grade=A release_decision=pass`。
- 验证：`python scripts/run_production_smoke.py --execute` -> `rows=7 execute=true failed=0`。
- 浏览器 smoke：桌面 `scrollWidth=clientWidth=1265`、console errors=0；390x844 移动端 `scrollWidth=bodyScrollWidth=375`、console errors=0。
- 提交前微调：前端聊天框改为 Enter 发送、Shift+Enter 换行；非正常 RAG 问答的 meta/路由回复默认中文。
- 当前提交边界：用户已授权提交、tag、push 与 GitHub merge。

## 提交边界（贯穿全阶段）

- 用户人工核验并明确授权后，允许执行 `git add`、`git commit`、`git tag`、`git push`、GitHub merge，并创建 `phase-36-complete` tag。
- 不替换默认 chat / embedding / rerank provider；不动 chat provider 拓扑。
- 不引入新外部数据源、不爬新网页、不切 chunk、不做架构迁移、不做多用户隔离。
- 不接 deterministic 后处理（含 citation_validator）进生产链路。
- 不写 API key / Bearer token / raw provider response / reasoning_content / hidden thought / 完整 chunk 全文进任何提交物。
