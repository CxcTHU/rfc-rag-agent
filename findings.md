# 阶段 42 Findings：生成质量校准与生产体验完善

## Requirements

- 主线 A：扩展 LLM Judge 评测集覆盖新语料，分析低分样例根因，微调 prompt，争取 Judge gate pass。
- 主线 C：实现长回答分段渲染（Phase 40 暂缓的第五条），完善会话管理 UX（删除、重命名）。
- Stage 30 评分不得低于 91.52/A/pass。
- 不改变 Stage 30 评分规则、provider 拓扑或数据源边界。
- 不引入 React/Vue/Node 构建链。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始响应、raw_response、reasoning_content 写入 Git/CSV/文档/测试/Obsidian。

## Research Findings

### Judge 历史成绩

- Stage 36 Judge: baseline cov=0.655/cit=0.640, outline_first cov=0.703/cit=0.685, answer_provider_ab cov=0.772/cit=0.820/safety=0.950 — 全部 review_required。
- Stage 38 Judge: baseline cov=0.775/cit=0.731, structured_final_answer cov=0.808/cit=0.867/safety=1.000 — structured gate=pass, baseline gate=review_required。
- 结论：structured_final_answer 是当前最优策略，已为默认；但样本量有限（24 cases），新语料未覆盖。

### Judge 基础设施

- `scripts/judge_stage38_tool_calling_quality.py` 是最新 Judge 脚本，默认 dry-run，`--execute` 才调真实 provider。
- Judge 调用链：tool_calling_agent 生成答案 -> 脱敏 evidence_snippet -> Judge payload -> DeepSeek/OpenAI-compatible Judge -> 分数+短理由。
- 结果字段：answer_coverage、citation_support、safety_leak_check、risk_level、next_action。
- `scripts/judge_stage34_generation_quality.py` 提供核心 Judge client 和脱敏工具，被后续 judge 脚本复用。

### 评测集现状

- Stage 38: 24 cases，16 categories（`data/evaluation/stage38_eval_cases.csv`）。
- Stage 41: 12 queries，3 categories（`data/evaluation/stage41_post_import_retrieval_queries.csv`）。
- 合并后可达 ~36 cases，覆盖面显著提升。

### 前端会话管理现状

- `app/frontend/static/app.js` 和 `app/frontend/index.html` 已有会话列表功能。
- 后端 `app/api/agent.py` 已有 conversation CRUD：创建、读取、追加消息。
- 缺失：会话删除 API + 前端按钮、会话重命名 API + 前端 right-click context menu。
- `app/db/repositories.py` 有 `ConversationRepository`，需要新增 delete/rename 方法。

### 长回答渲染现状

- Phase 40 实现了 token buffer + rAF flush 节流，但不是分段渲染。
- 当回答超长（>2000 tokens）时，`finalizeAgentStreamingMessage()` 做一次性 innerHTML 赋值，可能触发大段 reflow。
- Phase 40 设计文档明确暂缓"长回答虚拟列表/分段虚拟渲染"。
- 阶段 42 目标：不做完整虚拟列表，而是做段落级分段渲染——流式阶段按段落 flush 到 DOM，最终渲染时分段插入而非单次 innerHTML。

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Judge 评测扩展到 ~36 cases | 24→36 增加统计信噪比，新语料题覆盖导入后检索质量 |
| 微调实际生效的 tool-calling final-answer prompt | 阶段 42 默认链路走 `ToolCallingAgentService` final synthesis，传统 `prompt_builder.py` 不是本阶段主路径 |
| 分段渲染而非虚拟列表 | 虚拟列表需要滚动容器重构；分段插入已能解决当前长度的 reflow 问题 |
| 会话删除采用 hard delete | 当前无认证和回收站模型，hard delete 与现有 CRUD 最一致；后续加认证再考虑 soft delete |
| 不引入前端框架 | 项目 Phase 22-27 已明确不引入 React/Vue/Node |
| Judge CSV 只保存脱敏指标 | 保留分数、短理由、风险等级和 next_action；不保存 raw answer、raw_response 或 reasoning_content |

## Issues Encountered

- Phase 41 接手时尚未提交且未合并到 `main`；按用户授权先将 Phase 42 三份规划草稿临时 stash，只提交/合并 Phase 41 本身，再从新 `main` 创建 Phase 42 分支并恢复规划草稿。
- 本地 `origin/main` 仍停在 Phase 39 合并点，当前只完成本地 `main` 合并；按阶段 42 要求不执行 push 或 PR。
- Phase 2 首轮真实 Judge 在 36 cases 上完成，`structured_final_answer` 为 `faith=0.982 / cov=0.790 / cit=0.829 / refusal=0.925 / concise=0.904 / safety=1.000`，无 high risk，但 coverage 均值低于 0.80，gate=`review_required`。
- 低分样例主要集中在比较题、多维题、quality control 新语料题，根因以 `answer_coverage_gap` 为主，少量为 `prompt_citation_gap` 和 refusal Judge artifact。
- Phase 3 微调位置从传统 `prompt_builder.py` 调整为实际生效的 `app/services/agent/tool_calling_service.py::final_answer_strategy_instruction()`，因为 Stage 42 默认链路是 tool-calling final synthesis。
- 微调后真实 Judge 复跑 36/36 completed，`faith=0.983 / cov=0.828 / cit=0.856 / refusal=0.953 / concise=0.931 / safety=1.000`，high=0，medium=17，gate=`pass`。剩余低分样例仍记录在 `data/evaluation/stage42_generation_low_score_analysis.csv`，进入人工核验而非继续盲调。
- Phase 4/5 聚焦回归后，全量测试为 `843 passed`；Stage 30 维持 `91.52 / A / pass`。
- Browser smoke 使用 `http://127.0.0.1:8001`：桌面和 `390x844` 移动端均无横向溢出、console errors=0；重命名、临时会话 hard delete、长回答分段 DOM、流式停止均可用。
- Production smoke 以默认 dry-run 运行，`rows=11 execute=false failed=0`，没有让真实 API 成为自动回归前提。

## Final State Before Human Verification

- 阶段 42 分支：`codex/phase-42-generation-quality-and-experience`。
- 阶段 41 已按用户授权提交并本地合并到 `main`，阶段 42 从 `main -> d7dfca1` 出发。
- 阶段 42 开发完成后未执行 `git add`、commit、tag、push 或 PR。
- 普通文档和本地 Obsidian 草稿已补齐，等待用户人工核验。
## Submission Update

2026-06-17: Phase 42 is no longer waiting for human verification. The user explicitly authorized submission and GitHub merge. Final frontend refinements are included in scope: left conversation sidebar, pointer-adjacent right-click rename/delete menu that does not switch conversations, fixed bottom composer, independent message/sidebar scrolling, and citation source drawer.
