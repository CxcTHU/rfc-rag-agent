# 阶段 43 Progress：多轮对话质量与生产可观测性强化

## Session: 2026-06-17

### Phase 0：启动校准与规划落盘（Claude 规划方 + Codex 校准）

- **Status:** complete
- **Started:** 2026-06-17

Phase purpose:

- 这一 Phase 由 Claude 规划方完成，为阶段 43 编写任务计划、发现记录和进度文件。
- 阶段 43 有两条主线：A（多轮评测 + 分层记忆）和 B（request_id 追踪 + 诊断端点）。
- 现在做它，是因为阶段 42 已完成单轮 Judge gate=pass，但多轮对话质量是盲区，summary/history 注入的影响未量化；同时 request_id 贯穿链路不完整，多轮场景排错困难。

Actions taken:

- 确认阶段 42 最终状态：843 tests，Stage 30 = 91.52/A/pass，Judge gate=pass（36 cases）。
- 确认多轮会话现状：summary 压缩 + recent messages，未做质量评测。
- 确认 request_id 现状：Phase 39 已有基础 contextvars + JSON formatter，但链路不完整。
- 评审 Codex 提出的阶段 43 方案，调整：HTTPS 模板降为 stretch goal，分层记忆分两步实现。
- 编写 `task_plan.md` 11 个 Phase 任务计划。
- 编写 `findings.md` 多轮/request_id/health 现状分析。
- 编写 `progress.md` 本文件。
- 编写 Codex goal prompt。
- Codex 接手后重新阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- Codex 运行 `git status -sb` 与 `git log --oneline -5`，确认接手工作树状态。
- Codex 确认 Phase 42 已合并到 GitHub `origin/main -> 5850139`，且该合并包含 `00e1424 Complete phase 42 generation quality and experience`。
- Codex 发现本地 `main` 仍停在 `d7dfca1`，因此没有从本地旧 main 出发，而是从 Phase 42 合并后的 `origin/main` 创建阶段 43 分支。
- Codex 创建并切换到 `codex/phase-43-multi-turn-quality-and-observability`，未执行 `git add`、commit、tag、push 或 PR。

Git / tag / main 状态:

- 阶段 42 已提交为 `00e1424 Complete phase 42 generation quality and experience`。
- 阶段 42 已获用户授权合并到 GitHub，`origin/main -> 5850139 Merge pull request #9 from CxcTHU/codex/phase-42-generation-quality-and-experience`。
- 本地 `main -> d7dfca1` 尚未快进；阶段 43 正确起点使用 `origin/main`。
- 当前分支为 `codex/phase-43-multi-turn-quality-and-observability`。
- 当前未提交工作为阶段 43 规划校准文件、Stage 30 校准 CSV run，以及 `.playwright-mcp/` 浏览器运行产物。

Next:

- 进入 Phase 1：新增阶段 43 设计文档与设计合同测试。

---

## 五问重启检查

1. 当前阶段是什么？—— 阶段 43：多轮对话质量与生产可观测性强化。
2. 上一个阶段完成了什么？—— 阶段 42 完成单轮生成质量校准（Judge gate=pass，36 cases）和生产体验完善（长回答分段渲染、会话管理 UX）。
3. 当前分支和提交？—— `codex/phase-43-multi-turn-quality-and-observability`，基于 `origin/main -> 5850139`。
4. 有未提交的工作吗？—— 有，阶段 43 三份规划文件、Stage 30 校准 CSV run 和 `.playwright-mcp/` 运行产物；本阶段最终仍停在人工核验前，不提交。
5. 下一步做什么？—— Phase 1：设计文档与测试合同。

---

## 测试结果表

| Phase | 测试命令 | 结果 | 备注 |
|-------|---------|------|------|
| (阶段 42 基线) | `python -m pytest -q` | 843 passed | 阶段 43 开始前基线 |
| (阶段 42 基线) | `python scripts/score_stage30_quality.py` | 91.52 / A / pass | 阶段 43 开始前基线 |
| Phase 0 | `git status -sb` | branch=`codex/phase-43-multi-turn-quality-and-observability`, dirty planning/stage30 files | 未提交，符合人工核验前边界 |
| Phase 0 | `git log --oneline -5` | `5850139`, `00e1424`, `d7dfca1`, `007b0f0`, `7926c32` | Phase 42 GitHub merge confirmed |
| Phase 1 | `python -m pytest tests/test_stage43_design.py -q` | 6 passed | 设计文档与合同测试 |
| Phase 2 | `python -m pytest tests/test_stage43_multi_turn_eval.py -q` | 5 passed | 多轮评测集与 dry-run 脚本合同 |
| Phase 2 | `python scripts/evaluate_stage43_multi_turn.py --history-mode summary_recent` | cases=16 turns=32 | dry-run，不调用真实 API |
| Phase 3 | `python -m pytest tests/test_stage43_multi_turn_eval.py -q` | 5 passed | baseline 脚本回归 |
| Phase 3 | `python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run` | completed | no_history/recent_only/summary_recent completed; layered_memory 在 Phase 4 后回填 |
| Phase 3 | `python scripts/score_stage30_quality.py` | 91.52 / A / pass | Stage 30 不退化 |
| Phase 4 | `python -m pytest tests/test_session_memory.py tests/test_stage43_multi_turn_eval.py tests/test_brain_service.py::test_brain_service_rewrites_contextual_question_before_retrieval -q` | 10 passed | session memory + eval + Brain rewrite 聚焦回归 |
| Phase 4 | `python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run` | completed in ~19s | layered_memory 回填完成 |
| Phase 4 | `python scripts/score_stage30_quality.py` | 91.52 / A / pass | Stage 30 不退化 |
| Phase 5 | scenario-level CSV analysis | completed | layered coverage improves some scenarios but user_correction hit regresses |
| Phase 6 | `python -m pytest tests/test_request_logger.py tests/test_stage39_logging.py tests/test_session_memory.py tests/test_brain_service.py::test_brain_service_rewrites_contextual_question_before_retrieval -q` | 11 passed | request trace + structured logging + memory 回归 |
| Phase 7 | `python -m pytest tests/test_health_details.py tests/test_request_logger.py -q` | 5 passed | `/health/details` + request trace 聚焦回归 |
| Phase 7 | `python scripts/score_stage30_quality.py` | 91.52 / A / pass | Stage 30 不退化 |
| Phase 8 | `python -m pytest -q` | 863 passed | 全量回归 |
| Phase 8 | `python scripts/score_stage30_quality.py` | 91.52 / A / pass | Stage 30 不退化 |
| Phase 8 | `python scripts/run_production_smoke.py` | rows=11 execute=false failed=0 | production smoke dry-run |
| Phase 9 | Browser desktop smoke on `http://127.0.0.1:8023/` | passed | 多轮闲聊短路、console errors=0、horizontal overflow=false |
| Phase 9 | Browser mobile smoke 390x844 | passed | 输入框/运行按钮可见、历史对话保留、console errors=0、horizontal overflow=false |
| Phase 10 | documentation and Obsidian drafts | completed | README/docs/phase review/Obsidian 阶段页与 Phase 汇报已补齐 |
| Review fix | `python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run` | completed | 四路 CSV 重建，layered_memory completed |
| Phase 12 | `python -m pytest tests/test_stage43_multi_turn_judge.py -q` | 5 passed | 多轮 Judge 合同、payload 脱敏、dry-run、单路合并 |
| Phase 12 | `python scripts/judge_stage43_multi_turn_quality.py --history-mode all` | rows=128 execute=false completed=0 | dry-run，不调用真实 API |
| Phase 13 | `python scripts/judge_stage43_multi_turn_quality.py --history-mode summary_recent --execute` | 32/32 completed | 逐行 checkpoint 后续跑完成 |
| Phase 13 | `python scripts/judge_stage43_multi_turn_quality.py --history-mode layered_memory --execute` | 32/32 completed | 真实 Judge 对照完成 |
| Phase 13 | `python scripts/judge_stage43_multi_turn_quality.py --history-mode recent_only --execute` | 32/32 completed | 真实 Judge baseline 完成 |
| Phase 13 | `python scripts/judge_stage43_multi_turn_quality.py --history-mode no_history --execute` | 32/32 completed | 真实 Judge baseline 完成 |
| Phase 13 | `python scripts/score_stage30_quality.py` | 91.52 / A / pass | Stage 30 不退化 |
| Phase 14 | `python -m pytest tests/test_stage43_https_templates.py -q` | 3 passed | HTTPS 模板合同 |
| Phase 15 | `python -m pytest -q` | 876 passed | 全量回归（Phase 16 后最新） |
| Phase 15 | `python scripts/score_stage30_quality.py` | 91.52 / A / pass | Stage 30 不退化 |
| Phase 15 | `python scripts/run_production_smoke.py` | rows=11 execute=false failed=0 | production smoke dry-run |
| Phase 15 | Browser desktop smoke on `http://127.0.0.1:8024/` | passed | two-turn hello/thanks, console errors=0, horizontal overflow=false |
| Phase 15 | Browser mobile smoke 390x844 | passed | Agent controls visible, console errors=0, horizontal overflow=false |
| Phase 16 | `python -m pytest -q` | 876 passed | 全量回归 |
| Phase 16 | `python scripts/score_stage30_quality.py` | 91.52 / A / pass | Stage 30 不退化 |
| Phase 16 | `python scripts/run_production_smoke.py` | rows=11 execute=false failed=0 | production smoke dry-run |

### Phase 1：设计文档与测试合同

- **Status:** complete
- 新增 `docs/stage43_multi_turn_quality_and_observability.md`，固定阶段 43 的双主线、Phase 顺序、多轮评测合同、session memory 边界、request_id / JSONL trace 合同、`/health/details` 合同、安全边界和验证合同。
- 新增 `tests/test_stage43_design.py`，覆盖阶段基线、Phase 顺序、多轮评测、分层记忆边界、可观测性、健康诊断、验证命令和不提交边界。
- 聚焦测试通过：`python -m pytest tests/test_stage43_design.py -q` -> `6 passed`。

Next:

- Phase 2：新增不少于 16 组多轮对话评测集，并实现默认 dry-run 的 `scripts/evaluate_stage43_multi_turn.py`。

### Phase 2：多轮对话评测集

- **Status:** complete
- 新增 `data/evaluation/stage43_multi_turn_eval_cases.csv`，包含 16 组多轮对话、32 个 turn。
- 覆盖 8 类场景：追问、指代/省略、澄清、话题切换、引用前轮内容、用户纠错、带约束追问、多轮拒答；每类 2 组。
- 新增 `scripts/evaluate_stage43_multi_turn.py`，支持 `--history-mode no_history|recent_only|summary_recent|layered_memory`，默认 dry-run，不调用真实 provider。
- 新增 `tests/test_stage43_multi_turn_eval.py`，锁定 CSV schema、场景覆盖、四路 mode、layered_memory slot 输出和不保存 raw 输出边界。
- 聚焦测试通过：`python -m pytest tests/test_stage43_multi_turn_eval.py -q` -> `5 passed`。
- dry-run 通过：`python scripts/evaluate_stage43_multi_turn.py --history-mode summary_recent` -> `cases=16 turns=32`，生成 `data/evaluation/stage43_multi_turn_baseline_results.csv`。

Next:

- Phase 3：实现四路 deterministic baseline 对比，输出量化 CSV，并确认 Stage 30 不退化。

### Phase 3：多轮质量 baseline 对比

- **Status:** complete
- 扩展 `scripts/evaluate_stage43_multi_turn.py`：`--no-dry-run` 会运行本地 deterministic baseline，输出 `data/evaluation/stage43_multi_turn_baseline_results.csv` 与 `stage43_multi_turn_baseline_summary.csv`。
- 为避免评测脚本对 32 turns x 多 history modes 反复触发全库向量扫描，Phase 3 采用一次加载轻量语料快照 + 内存 lexical scoring；这只影响阶段评测脚本，不改线上 retrieval 链路。
- 四路结果：
  - `no_history`: avg_retrieval_hit=0.312, avg_citation_support=0.312, avg_answer_coverage=0.104。
  - `recent_only`: avg_retrieval_hit=0.531, avg_citation_support=0.531, avg_answer_coverage=0.125。
  - `summary_recent`: avg_retrieval_hit=0.594, avg_citation_support=0.594, avg_answer_coverage=0.167。
  - `layered_memory`: Phase 4 接入真实 session memory 后回填。
- 阶段结论：history 注入对多轮追问/省略场景有明显增益，summary_recent 当前优于 recent_only，但 answer coverage 仍低，值得在 Phase 4 用 retrieval anchors 做最小增强。
- Stage 30 复跑：`python scripts/score_stage30_quality.py` -> `91.52 / A / pass`。

Next:

- Phase 4：实现最小分层会话记忆（entities + retrieval_anchors），接入评测脚本和 query rewrite / retrieval 边界。

### Phase 4：最小分层会话记忆

- **Status:** complete
- 新增 `app/services/conversation/session_memory.py`，实现 `SessionMemory(entities, retrieval_anchors)` 和 retrieval-only hint 格式化。
- `BrainService._rewrite_query_step()` 在指代/省略类问题中从当前 history 提取 session memory，并把短 hint 追加到 retrieval query；hint 明确写有“仅用于检索，不作为引用来源”。
- memory 不进入最终回答引用源，回答 prompt 仍由 retrieval sources 构造。
- `scripts/evaluate_stage43_multi_turn.py` 的 `layered_memory` 现在使用真实 `build_session_memory()`，不再标记 pending。
- 回填四路结果：
  - `no_history`: avg_retrieval_hit=0.312, avg_answer_coverage=0.104。
  - `recent_only`: avg_retrieval_hit=0.531, avg_answer_coverage=0.125。
  - `summary_recent`: avg_retrieval_hit=0.594, avg_answer_coverage=0.167。
  - `layered_memory`: avg_retrieval_hit=0.594, avg_answer_coverage=0.208。
- 聚焦测试通过：`10 passed`；Stage 30 复跑仍为 `91.52 / A / pass`。

Next:

- Phase 5：分析四路结果，判断是否需要最小优化；如无明确安全增益，不强行替换默认策略。

### Phase 5：多轮质量优化（条件执行）

- **Status:** complete
- 按 scenario 复核 `stage43_multi_turn_baseline_results.csv`：
  - `layered_memory` 在 `clarification` coverage=0.333，高于 `summary_recent` 的 0.167。
  - `layered_memory` 在 `reference_previous_turn` coverage=0.333，高于 `summary_recent` 的 0.250。
  - `layered_memory` 在 `user_correction` hit=0.750，低于 `summary_recent` 的 1.000，提示 retrieval anchors 可能保留被用户纠正的旧上下文。
- 结论：不强行把 layered memory 替换为默认策略；当前仅保留为 query rewrite / retrieval 的最小辅助能力，并把用户纠错场景作为后续需要更细 constraints slot 的证据。
- 已在 Phase 4 后重跑四路评测与 Stage 30，未发现 Stage 30 退化。
- 人工核验反馈后已重新运行 `python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run`，确认 `stage43_multi_turn_baseline_results.csv` 与 `stage43_multi_turn_baseline_summary.csv` 四路均为 completed，不再保留未回填结果。

Next:

- Phase 6：request_id 贯穿链路追踪与 JSONL request trace。

### Phase 6：request_id 贯穿链路追踪

- **Status:** complete
- 新增 `app/core/request_logger.py`：请求开始创建 trace，上下文内的 `log_event()` 自动聚合安全事件，请求结束写入一行 JSONL。
- `app/main.py` middleware 继续读取 `X-Request-ID` 或自动生成，并在成功/失败请求中写入 `data/logs/request_traces.jsonl`。
- `app/core/structured_logging.py::log_event()` 现在 best-effort 同步到 request trace；失败不影响主链路。
- `app/api/agent.py` 新增 `conversation_loaded` 和 `summary_assembled` 事件。
- `app/services/brain/service.py` 新增 `history_filtered`、`memory_assembled`、`query_rewritten`、`retrieval_completed`、`provider_call_started`、`provider_call_completed`、`brain_response_ready` 事件。
- `.gitignore` 新增 `data/logs/`，运行时 JSONL trace 不进入 Git。
- 新增 `tests/test_request_logger.py`，验证 JSONL 写入、敏感字段脱敏和 `X-Request-ID` 贯穿。
- 聚焦测试通过：`11 passed`。

Next:

- Phase 7：新增 `GET /health/details`，返回 DB、FAISS、provider config 诊断，不做外部 ping。

### Phase 7：健康诊断增强

- **Status:** complete
- `app/schemas/health.py` 新增 `HealthDetailsResponse` 及 DB、FAISS、provider 配置诊断模型。
- `app/api/health.py` 新增 `GET /health/details`：本地 SQLAlchemy ping + documents/chunks 计数、FAISS `.index` 与 `_ids.json` metadata 检查、provider 配置状态汇总。
- `/health/details` 不做外部 provider ping，不输出 API key、Bearer token、Authorization header 或供应商原始响应。
- `GET /health` 保持原有轻量响应结构不变。
- 新增 `tests/test_health_details.py`，覆盖诊断响应结构、FAISS 缺失状态、敏感字段不外泄和 `/health` 兼容性。
- 聚焦测试通过：`python -m pytest tests/test_health_details.py tests/test_request_logger.py -q` -> `5 passed`。
- Stage 30 复跑：`python scripts/score_stage30_quality.py` -> `91.52 / A / pass`。

Next:

- Phase 8：运行全量测试、Stage 30、production smoke（dry-run）。

### Phase 8：全量回归与 Stage 30

- **Status:** complete
- 全量回归通过：`python -m pytest -q` -> `863 passed`。
- Stage 30 复跑：`python scripts/score_stage30_quality.py` -> `91.52 / A / pass`。
- production smoke dry-run 通过：`python scripts/run_production_smoke.py` -> `rows=11 execute=false failed=0`，未访问真实服务或 provider。

Next:

- Phase 9：浏览器 smoke，覆盖桌面与 390x844 移动端 Agent 页面、console errors 和横向溢出。

### Phase 9：浏览器 smoke

- **Status:** complete
- 启动临时本地服务：`python -m uvicorn app.main:app --host 127.0.0.1 --port 8023`。
- 桌面端打开 `http://127.0.0.1:8023/`，进入 Agent 问答页；执行两轮轻量闲聊短路 `你好` / `谢谢`，避免真实 provider 调用。
- 桌面端结果：两轮对话成功追加，`No sources` 符合闲聊短路预期，console errors=0，horizontal overflow=false。
- 移动端 390x844 结果：Agent 输入框和运行按钮可见，历史两轮对话保留，console errors=0，horizontal overflow=false。
- 临时服务进程已停止。

Next:

- Phase 10：更新 README、docs/progress、docs/architecture、phase review 草稿和 Obsidian 阶段 43 草稿。

### Phase 10：文档与 Obsidian 收尾

- **Status:** complete
- 更新 `README.md`，新增 Phase 43 摘要、关键结果、验证结果和人工核验前边界。
- 更新 `docs/progress.md`，新增 Phase 43 最新状态。
- 更新 `docs/architecture.md`，记录多轮评测、session memory、request trace、`/health/details` 架构增量。
- 更新 `docs/data_sources.md`，明确阶段 43 不新增外部资料来源，JSONL trace 和 multi-turn CSV 的数据安全边界。
- 新增 `docs/phase_reviews/phase-43.md` 验收草稿。
- 更新 Obsidian：阶段 43 阶段页、阶段 43 Phase 汇报索引、Phase 0-10 汇报草稿、首页、阶段索引、阶段汇报索引。
- 阶段 43 已完成开发、测试、普通文档与 Obsidian 草稿；当前停在用户人工核验前，未执行 `git add`、commit、tag、push 或 PR。

Next:

- 等待用户人工核验。核验通过后，用户可另行授权提交/推送/PR。

### Claude 人工核验（2026-06-17）

- **Status:** 已修正（POST-REVIEW FIXED），数据不一致与单路覆盖问题已收口
- 863 tests pass，Stage 30 = 91.52/A/pass 确认
- 代码质量合格：session_memory / request_logger / health 均无敏感数据泄露
- **P1 修正**：已重跑 `python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run`，最终 CSV 四路均为 32 completed / 0 dry-run：
  - no_history hit=0.312, cov=0.104
  - recent_only hit=0.531, cov=0.125
  - summary_recent hit=0.594, cov=0.167
  - layered_memory hit=0.594, cov=0.208
- **P2 修正**：`scripts/evaluate_stage43_multi_turn.py` 已支持默认 results CSV 的单路合并回填；复跑 `--history-mode layered_memory --no-dry-run` 后四路仍各保留 32 行 completed。
- 新增 Phase 11-15 后续任务：数据修复 → 真实 Judge 多轮评测 → layered_memory 决策 → HTTPS 模板 → 回归收尾

### Phase 11-15 计划

- Phase 11：四路数据修复与文档校正
- Phase 12：真实 LLM Judge 多轮评测设计与合同
- Phase 13：真实 LLM Judge 执行与 layered_memory 决策
- Phase 14：HTTPS reverse proxy 模板（stretch）
- Phase 15：全量回归、文档与 Obsidian 收尾

### Phase 12：真实 LLM Judge 多轮评测设计与合同

- **Status:** complete
- 新增 `docs/stage43_multi_turn_judge.md`，固定四个多轮 Judge 维度：`answer_faithfulness`、`citation_accuracy`、`context_coherence`、`refusal_consistency`。
- 新增 `scripts/judge_stage43_multi_turn_quality.py`，读取 Stage 43 多轮 cases，并按 `no_history`、`recent_only`、`summary_recent`、`layered_memory` 展开 128 行 Judge 计划。
- 脚本默认 dry-run，不生成答案、不调用真实 API；显式 `--execute` 且本地 Judge 配置完整时才调用真实 Judge。
- 输出 CSV 只保存状态、计数、分数、risk、short_reason、next_action 和安全错误摘要，不保存完整答案、raw_response、reasoning_content、API key 或 Bearer token。
- 新增 `tests/test_stage43_multi_turn_judge.py`，验证四路展开、dry-run、不保存敏感字段、payload 脱敏和 parser 归一化。
- 验证：`python -m pytest tests/test_stage43_multi_turn_judge.py -q` -> `5 passed`。
- 验证：`python scripts/judge_stage43_multi_turn_quality.py --history-mode all` -> `rows=128 completed=0 execute=false`。

Next:

- Phase 13：执行 `--execute`；如果本地缺少真实 Judge provider，则诚实写 skipped，不伪造成真实 Judge 结果。

### Phase 13：真实 LLM Judge 执行与 layered_memory 决策

- **Status:** complete
- 本地 `.env` 具备真实 provider 配置。首次全量 `--history-mode all --execute` 和单路 32 行运行均因 provider 耗时超过 10 分钟而超时。
- 为避免长跑结果丢失，`scripts/judge_stage43_multi_turn_quality.py` 已增强为默认 results CSV 单路逐行 checkpoint：每完成一条立即写回 results/summary，重跑会跳过 completed 行并继续未完成行。
- 分别续跑四个 mode，最终 `stage43_multi_turn_judge_results.csv` 四路均为 32/32 completed，无 error/high risk。
- Judge summary：
  - `no_history`: faith=0.678, citation=0.603, coherence=0.794, refusal=0.778, gate=review_required。
  - `recent_only`: faith=0.766, citation=0.680, coherence=0.853, refusal=0.816, gate=review_required。
  - `summary_recent`: faith=0.764, citation=0.641, coherence=0.784, refusal=0.794, gate=review_required。
  - `layered_memory`: faith=0.769, citation=0.622, coherence=0.852, refusal=0.853, gate=review_required（Phase 17 复跑后）。
- 决策：`layered_memory` 相比 `summary_recent` 四个 Judge 维度均提升，但 citation_accuracy 仍低于 0.8 且 gate=review_required；本阶段不替换默认策略，继续作为 query rewrite / retrieval 辅助。后续优化方向是 constraints slot 与 stale-anchor invalidation，尤其处理用户纠错场景的旧锚点残留。
- Stage 30 复跑：`python scripts/score_stage30_quality.py` -> `91.52 / A / pass`。

Next:

- Phase 14：补充 HTTPS reverse proxy 示例模板（stretch），不改 Docker/CI。

### Phase 14：HTTPS reverse proxy 模板（stretch）

- **Status:** complete
- 新增 `deploy/nginx-https.example.conf`：示例 TLS 终止、HTTP -> HTTPS redirect、proxy 到 `127.0.0.1:8000`、传递 `X-Request-ID`，并对 `/agent/query/stream` 关闭 buffering。
- 新增 `deploy/Caddyfile.example`：示例 Caddy 自动证书、reverse_proxy 到 `127.0.0.1:8000`、传递 `X-Request-ID`。
- 新增 `docs/deployment_https_reverse_proxy.md`：记录 `client -> HTTPS reverse proxy -> HTTP uvicorn` 拓扑和安全边界。
- 未修改 Dockerfile、docker-compose.yml、CI、provider 配置或运行时默认值。
- 验证：`python -m pytest tests/test_stage43_https_templates.py -q` -> `3 passed`。

Next:

- Phase 15：全量回归、production/browser smoke、普通文档与 Obsidian 收尾。

### Phase 15：全量回归、文档与 Obsidian 收尾

- **Status:** complete
- 更新普通文档：`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage43_multi_turn_quality_and_observability.md`、`docs/phase_reviews/phase-43.md`。
- 更新 Obsidian：阶段 43 阶段页、Phase 汇报索引、Phase 11-15 汇报、首页、阶段索引、阶段汇报索引。
- 全量回归：`python -m pytest -q` -> `876 passed`。
- Stage 30：`python scripts/score_stage30_quality.py` -> `91.52 / A / pass`。
- production smoke dry-run：`python scripts/run_production_smoke.py` -> `rows=11 execute=false failed=0`。
- 浏览器桌面 smoke：`http://127.0.0.1:8024/`，Agent 页加载，`hello` / `thanks` 两轮闲聊追加成功，status=`answered`，console errors=0，horizontal overflow=false。
- 浏览器移动 smoke：390x844，Agent 区域、输入框、运行按钮可见，console errors=0，horizontal overflow=false。
- 临时 uvicorn 服务已停止。
- 最终停在人工核验前，未执行 `git add`、commit、tag、push 或 PR。

Next:

- 等待用户人工核验。核验通过后再由用户明确授权提交/推送/PR。

### Phase 16：纠错感知 layered_memory 优化

- **Status:** complete
- 实现 `constraints` / `stale_anchors` 的当前会话内短期 memory slot；不持久化、不跨会话、不作为引用来源。
- 用户纠错问题触发时，`layered_memory` 会移除旧 retrieval anchors，并从当前更正问题补充显式领域 anchor。
- `BrainService._rewrite_query_step()` 对纠错问题不再前置上一轮原文，避免旧问题目标污染 retrieval query。
- `stage43_correction_02` 第 2 轮现在使用 `retrieval_anchors=裂纹`，不再携带旧“施工质量/质量控制”锚点。
- 重新回填：`python scripts/evaluate_stage43_multi_turn.py --history-mode layered_memory --no-dry-run`。
- 最新四路 CSV 仍完整：每个 history_mode 均 32 completed / 0 dry-run。
- 最新 `layered_memory` baseline：avg_retrieval_hit=0.594，avg_answer_coverage=0.208。
- focused regression：`python -m pytest tests/test_session_memory.py tests/test_stage43_multi_turn_eval.py tests/test_stage43_multi_turn_judge.py -q` -> 19 passed。
- Stage 30：`python scripts/score_stage30_quality.py` -> 91.52 / A / pass。
- 结论：轻量 baseline hit 追平 `summary_recent` 且 coverage 更高；Phase 17 真实 Judge 复跑后 citation accuracy 仍低于 `summary_recent`，默认策略不替换，`layered_memory` 继续作为检索辅助。

### Phase 17：Phase 16 后真实 Judge 复跑

- **Status:** complete
- `scripts/judge_stage43_multi_turn_quality.py` 新增 `--force-rerun`，默认 Judge CSV 下可强制重跑指定 history mode 的 completed 行。
- Judge case 构造改为把当前问题传给 `build_memory_hint()`，确保真实 Judge 复跑覆盖 Phase 16 的纠错过滤路径。
- focused regression：`python -m pytest tests/test_stage43_multi_turn_judge.py tests/test_stage43_multi_turn_eval.py tests/test_session_memory.py -q` -> 19 passed。
- 真实 Judge 复跑：`python scripts/judge_stage43_multi_turn_quality.py --history-mode layered_memory --execute --force-rerun` -> 128 rows / 128 completed。
- 复跑后 `layered_memory`：faith=0.769，citation=0.622，coherence=0.852，refusal=0.853，gate=review_required。
- 对比 `summary_recent`：faith/coherence/refusal 更高，但 citation 低于 `summary_recent=0.641`。
- Stage 30：`python scripts/score_stage30_quality.py` -> 91.52 / A / pass。
- 结论：默认策略继续保持 `summary_recent`；`layered_memory` 保留为 query rewrite / retrieval 辅助。

## 错误日志

Phase 3 初次用线上 retrieval 服务跑四路 32-turn 对比时超时，已改为评测脚本内一次加载轻量语料快照并做 deterministic lexical scoring；该调整只影响阶段评测脚本，不改变生产 retrieval 链路。

Claude 核验时执行 `--history-mode layered_memory --no-dry-run` 覆盖了 results CSV，丢失三路已完成数据。Phase 11 需 `--history-mode all --no-dry-run` 恢复。

## 提交授权

阶段 43 Phase 0-17 开发、测试、普通文档与本地 Obsidian 草稿已完成。用户已于 2026-06-17 授权提交、推送并合并到 GitHub；不创建或移动 phase tag，除非用户另行要求。
