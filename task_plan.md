# 阶段 36 任务计划：生成可靠性与多轮体验稳定化

## 目标

在阶段 35「检索质量校准与 Stage 30 评分破局」+ 多轮意图路由补充已完成、`phase-35-complete` tag 已打、所有改动已合并到 `main` 的基础上，进入阶段 36：把阶段 35 留下的两个真实用户体感问题做稳，**不追分、做稳**。

目标分支建议：`codex/phase-36-generation-reliability-and-conversation-stability`

核心原则：
- 不再把 deterministic 后处理（如阶段 35 的 citation_validator）接进生产链路。
- 不动 Stage 30 评分权重、等级阈值、release_decision 规则；Stage 30 维持 `91.52 / A / pass`。
- 不替换默认 chat / embedding / rerank provider；不动 chat provider 拓扑。
- 不引入新外部数据源、不做爬虫、不做架构迁移（tool-calling 协议迁移留给阶段 37 或后续）。
- 不做多用户 / Conversation owner 隔离。
- Judge gate 显式攻坚但**不强行包装通过**：试过了就诚实写结论。

## 当前基线

```text
main / origin/main -> dc751fb Merge pull request #5 from CxcTHU/codex/phase35-multiturn-intent-router
phase-35-complete -> 7877308 Complete phase 35 remediation with Judge gate documented
phase-35-complete 已合并到 main
当前阶段 36 分支 -> codex/phase-36-generation-reliability-and-conversation-stability（待 Codex 创建）
```

阶段 35 留下的开放项：

```text
Stage 30 = 91.52 / A / pass（GLM, hybrid_rrf_tail，干净通过）✅
Judge gate FAIL：cov=0.41 / cit=0.64 / safety=1.00（GLM 链路 + Judge prompt 修复后）❌
citation_validator 已从生产 Brain 解耦，保留为离线评测工具
多轮意图路由补充（翻译/转述、模型信息、能力说明、拒答原因）已合并 main（commit 0af4a87）
ReAct planner 解析失败兜底已对 in-scope 改为先搜索再 refuse
真实 Agent 链路 react p50 ~39s、p90 ~55s，性能不再是瓶颈
```

## Phase 顺序

### Phase 0：启动校准与阶段 36 规划落盘

状态：已完成。

任务：
- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-35.md`、`docs/phase_reviews/phase-35-remediation.md`、`docs/stage35_retrieval_quality_calibration.md`、`data/evaluation/stage35_glm_llm_judge_summary.csv`、`data/evaluation/stage35_safety_leak_attribution.csv`。
- 阅读 `task_plan.md`、`findings.md`、`progress.md`、`obsidian-vault/模板/goal prompt.md`。
- 运行 `git status -sb`、`git log --oneline -5 --decorate`、`git merge-base --is-ancestor phase-35-complete main`。
- 确认 `phase-35-complete -> 7877308`、`main -> dc751fb`，未移动任何已有阶段 tag。
- 从 main 创建并切换到 `codex/phase-36-generation-reliability-and-conversation-stability`。

完成记录：
- 已设置线程 goal，并将线程名改为「阶段36-生成可靠性与多轮体验稳定化」。
- 已阅读阶段 36 要求的入口、进度、架构、数据源、阶段 35 review/remediation、Stage 35 设计与 Judge CSV。
- 已核对 `phase-35-complete -> 7877308`、`main -> dc751fb`，且 `phase-35-complete` 是 `main` 的祖先；未移动任何已有阶段 tag。
- 已从 `main` 创建并切换到 `codex/phase-36-generation-reliability-and-conversation-stability`；规划文件未提交状态保留。

### Phase 1：阶段 36 设计文档与评价口径

状态：已完成。

任务：
- 新增 `docs/stage36_generation_reliability_and_conversation_stability.md`：固定主线 = 拒答可解释性 + 生产 smoke + Judge gate 离线攻坚；辅线 = 多轮路由模块化；不做事项；安全边界；验收口径。
- 验收口径明确：Stage 30 维持 `91.52 / A / pass`；Judge gate 不强行包装；多轮误拒答 / 拒答原因 / 流式/非流式一致性 / 生产 smoke **必须全部稳定**。
- 新增 `tests/test_stage36_design.py`，断言设计文档涵盖核心范围、不替换默认 provider、不引入危险后处理、Judge gate 离线时限。

完成记录：
- 已新增 `docs/stage36_generation_reliability_and_conversation_stability.md`。
- 已新增 `tests/test_stage36_design.py`，覆盖阶段目标、拒答可解释性、production smoke、Judge 离线门槛、provider/评分/数据安全边界。
- 已运行 `python -m pytest tests/test_stage36_design.py -q`，结果 `5 passed`。

### Phase 2：拒答可解释性升级

状态：已完成。

任务：
- off-topic 拒答时附带「如果你想问 RFC / 水利工程 / 混凝土相关问题，可以这样改写」类提示（脱敏，不暴露内部规则原文）。
- evidence_insufficient 拒答时返回「检索到了哪些来源摘要、覆盖哪些方面、还缺什么关键词」（摘要必须脱敏，不暴露完整 chunk 内容）。
- 不让 LLM 编造检索结果摘要；只展示真实命中的 source title / source_type / 短摘要。
- 改动限于 `app/services/agent/`、`app/services/generation/prompt_builder.py`、可能新增 `app/services/agent/refusal_explainer.py`。
- 不修改 `/agent/query` 响应 schema，新字段（如有）走 metadata 兼容。
- 新增聚焦测试覆盖：off-topic 改写建议、evidence_insufficient 摘要、不泄漏完整 chunk、不泄漏内部规则文本。

完成记录：
- 新增 `app/services/agent/refusal_explainer.py`，在输出层生成 off-topic 改写建议和 evidence_insufficient 安全检索摘要。
- `/agent/query` 外部 schema 未新增字段；解释追加到已有 `reasoning_summary`，并随既有 metadata 持久化。
- `AgentToolbox.answer_with_citations()` 在拒答且无 sources 时补一次只读 hybrid 检索，用于生成安全摘要；不调用 LLM、不写库、不改变 provider。
- 新增 `tests/test_refusal_explainer.py`，并补充 Agent API 拒答解释测试。
- 已运行 `python -m pytest tests/test_refusal_explainer.py tests/test_agent_api.py tests/test_agent_tools.py tests/test_agent_service.py -q`，结果 `42 passed`。

### Phase 3：生产 smoke 自动化

状态：已完成。

任务：
- 新增 `scripts/run_production_smoke.py`：默认 dry-run；`--execute` 跑真实端点。
- 覆盖：`GET /health`、`GET /quality-report`、`GET /quality-report/data.json`、`POST /agent/query` 正常 RAG、`POST /agent/query` 多轮转述（依赖阶段 35 补充的 intent router）、`POST /agent/query` meta（模型信息）、`POST /agent/query/stream` 流式。
- 输出 `data/evaluation/stage36_production_smoke_results.csv`：每行 endpoint、状态、耗时、关键字段是否齐全、refused、citation_count、validator_marker（必须为 false）。
- 新增 `tests/test_run_production_smoke.py`，覆盖 dry-run 行为、字段完整性、敏感字段不入 CSV。
- 阶段 36 收尾标准：smoke 一键通过。

完成记录：
- 新增 `scripts/run_production_smoke.py`，默认 dry-run，显式 `--execute` 才访问真实端点。
- 覆盖 `/health`、`/quality-report`、`/quality-report/data.json`、三类 `/agent/query`、`/agent/query/stream`。
- 输出 `data/evaluation/stage36_production_smoke_results.csv`，只保留 endpoint、状态、耗时、关键字段、refused、citation_count、validator_marker、sensitive_field_detected 和 error_summary 等安全字段。
- 新增 `tests/test_run_production_smoke.py`。
- 已运行 `python -m pytest tests/test_run_production_smoke.py -q`，结果 `5 passed`。
- 已运行 `python scripts/run_production_smoke.py` dry-run，生成 7 行计划结果；`--execute` 留到阶段收尾真实服务 smoke。

### Phase 4：Judge gate 显式离线攻坚（时限 ≤ 2 周）

状态：已完成（真实 20 题 A/B 已落盘，Judge gate 未通过，未包装通过）。

任务（**离线**，不接生产，不动默认链路）：
- A 方案：outline-first 答题策略——LLM 第一次输出 outline + 每个要点 anchored 到 source chunk_id；第二次填充每个要点内容。新增 `app/services/generation/outline_first_strategy.py` 作为可选 strategy（默认关闭）。
- B 方案：answer provider A/B——把 `DeepSeek-V3.2-Thinking` 当 V4-Pro 的离线对照（仍走 Paratera，不动 planner）。
- 真实 Judge 复跑 ≥ 20 条（扩大样本），baseline / A / B 三组对照。
- 输出 `data/evaluation/stage36_judge_strategy_ab_results.csv` 与 summary。
- 决策：若任一方案在 ≥ 20 条上 cov ≥ 0.80 且 cit ≥ 0.80 且 safety ≥ 0.80 → 写决策报告说明是否接生产；若两条都达不到 → 写诚实归因（Judge gate 是评测体系瓶颈，还是模型能力上限），不强行包装成通过。
- 不删除 citation_validator 离线工具；不接进生产。

完成记录：
- 新增 `app/services/generation/outline_first_strategy.py`，实现离线 outline-first 两步生成候选策略，默认不接生产。
- 新增 `scripts/judge_stage36_strategy_ab.py`，支持 `baseline`、`outline_first`、`answer_provider_ab` 三组离线对照，默认 dry-run，显式 `--execute` 才调用真实 provider/Judge。
- 新增 `tests/test_stage36_judge_strategy_ab.py`。
- 已运行 `python -m pytest tests/test_stage36_judge_strategy_ab.py -q`，结果 `6 passed`。
- 已运行 `python scripts/judge_stage36_strategy_ab.py`，生成 20 条真实问题 x 3 策略 = 60 行 dry-run 计划。
- 已运行真实 `python scripts/judge_stage36_strategy_ab.py --execute --limit 20 --timeout-seconds 180`，落盘 20 条真实问题 x 3 策略 = 60 条 completed Judge row。
- 真实结果：baseline cov=0.655 / cit=0.640 / safety=1.000；outline_first cov=0.703 / cit=0.685 / safety=1.000；answer_provider_ab cov=0.772 / cit=0.820 / safety=0.950。
- 已更新 `docs/stage36_judge_strategy_decision.md`，诚实记录三组均为 `review_required`，任何策略都不得接生产、不得包装为通过。

### Phase 5：多轮路由模块化（辅线，按情况）

状态：已完成。

阶段 35 已经补的翻译/转述、模型信息、能力说明、拒答原因路由可能仍散在 `app/api/agent.py`。

任务（仅当确实分散时做）：
- 抽取为 `app/services/agent/intent_router.py`，定义 intent 类型、回归测试集。
- 回归集至少覆盖：上一轮翻译、追问、问来源、问模型、问为什么拒答、闲聊、off-topic、正常领域问答。
- 如果 Codex 判断现有代码已模块化合理，本 Phase 可降级为「补回归测试集 + 更新文档」，不强制重构。

完成记录：
- 新增 `app/services/agent/intent_router.py`，抽取多轮转述、模型信息、能力说明、拒答原因等意图触发规则。
- `app/api/agent.py` 已改为调用 `intent_router.classify_meta_intent()`、`intent_router.is_followup_transform_request()` 和 `intent_router.strip_assistant_history_prefix()`。
- 新增 `tests/test_intent_router.py`，覆盖上一轮翻译、追问、问来源、问模型、问为什么拒答、闲聊、off-topic、正常领域问答 8 类意图。
- 已运行 `python -m pytest tests/test_intent_router.py tests/test_agent_api.py -q`，结果 `30 passed`。

### Phase 6：文档、Obsidian 与阶段收尾验证

状态：已完成，用户人工核验已通过，进入提交合并收尾。

任务：
- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、按需 `AGENT.MD`。
- 新增 `docs/phase_reviews/phase-36.md` 验收草稿。
- Obsidian 阶段 36 阶段页 + Phase 0–6 汇报 + 首页 / 阶段索引 / 阶段汇报索引同步。
- 运行阶段 36 聚焦测试、全量 pytest、`scripts/score_stage30_quality.py`（必须仍 91.52）、`scripts/run_production_smoke.py --execute`（必须全过）。
- 浏览器 smoke：桌面 + 390x844 移动端验证 `/quality-report`（仍 91.52 A pass）与 Agent 查询无回归。

完成记录：
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 已新增 `docs/phase_reviews/phase-36.md` 验收草稿。
- 已新增 Obsidian 阶段 36 阶段页、Phase 0-6 小 Phase 汇报与阶段 36 汇报索引，并同步首页、阶段索引、阶段汇报索引。
- 已运行 `python -m pytest -q`，结果 `724 passed`。
- 已运行 `python scripts/score_stage30_quality.py`，结果 `overall=91.52 grade=A release_decision=pass`。
- 已运行 `python scripts/run_production_smoke.py --execute`，结果 `rows=7 execute=true failed=0`。
- 浏览器 smoke：桌面视口 `scrollWidth=clientWidth=1265`、console errors=0；390x844 移动端 `scrollWidth=bodyScrollWidth=375`、console errors=0。
- 提交前微调：前端聊天框改为 Enter 发送、Shift+Enter 换行；meta/非 RAG 路由回复默认中文。
- 当前状态：用户已授权执行 `git add`、commit、`phase-36-complete` tag、push 与 GitHub merge。

## 完成标准

- `phase-35-complete` 已确认合并到 `main`，阶段 36 分支从正确基线创建。
- 拒答可解释性已落地：off-topic 给改写建议、evidence_insufficient 给检索摘要；不泄漏 chunk 全文或内部规则。
- 生产 smoke 一键通过，CSV 含安全字段。
- Judge gate 离线攻坚已显式做过 outline-first + answer provider A/B（≥ 20 条真实样本）；结果通过则写决策报告并由用户决定是否接生产；不通过则诚实写归因，不强行包装。
- Stage 30 维持 `91.52 / A / pass`，规则未改、provider 未换、数据源未扩。
- 多轮路由按需模块化或仅补回归集；回归集覆盖 8 类意图。
- 不接 deterministic 后处理（如 citation_validator）进生产链路。
- 不写 API key / Bearer token / raw provider response / reasoning_content / hidden thought / 完整 chunk 全文进任何提交物。
- 全量 pytest 通过；新增聚焦测试通过；浏览器 smoke 桌面 + 移动端无横向溢出、console errors=0。
- 用户人工核验通过后，允许提交、创建 `phase-36-complete` tag、push 与 GitHub merge。
