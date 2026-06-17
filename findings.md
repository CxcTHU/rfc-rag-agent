# 阶段 43 Findings：多轮对话质量与生产可观测性强化

## Requirements

- 主线 A：建立多轮对话评测集，实现最小分层会话记忆，量化四路 history 注入策略对比。
- 主线 B：补齐 request_id 贯穿链路追踪，新增 /health/details 诊断端点，新增 JSONL request trace。
- Stage 30 评分不得低于 91.52 / A / pass。
- 不做跨会话长期记忆，不做用户画像/私人偏好记忆。
- 不把 summary 当作可引用资料来源，不把模型生成的 memory 写成知识库事实。
- 不改变 Stage 30 评分规则、provider 拓扑或数据源边界。
- 不引入外部监控 SaaS（Prometheus/Grafana/Sentry/Datadog）。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始响应、raw_response、reasoning_content 写入 Git/CSV/文档/测试/Obsidian。

## Research Findings

### 多轮对话现状

- 阶段 24 引入多轮会话：`conversation_id` 注入 `/agent/query`，`ConversationRepository` 持久化 user/assistant 消息。
- 阶段 25 补充闲聊短路和 SSE 流式输出。
- `app/services/conversation/history.py` 实现了 summary 压缩机制：
  - 触发条件：非 summary 消息超过 16 条后触发压缩。
  - 压缩策略：保留最近 6 条非 summary 消息，其余压缩为 role="summary" 消息。
  - 压缩 prompt 要求保留用户目标、关键约束、已有结论、引用主题和未解决问题。
- 当前 history 注入点：Brain `rewrite_query` step 使用 history 做追问上下文补全。
- 尚未评测的盲区：追问检索命中率变化、指代/省略解析、话题切换后上下文污染、summary 丢失关键实体、带约束追问遵从度。

### request_id 现状

- Phase 39 已建立：`app/core/structured_logging.py` 有 `request_id_var`（contextvars）、`JsonLogFormatter`（JSON 格式化器）、`log_event()`（结构化事件）。
- `app/main.py` 的 request middleware 在请求入口 `new_request_id()` 并 `set_request_id()`，请求结束 `reset_request_id()`。
- 当前日志在 `app/api/agent.py`（query_received/answer_generated/refusal_triggered）和 `tool_calling_service.py`（tool_call_executed）有 request_id。
- 缺口：conversation loading、summary assembly、query rewrite、retrieval（keyword/vector/hybrid）、embedding provider call、rerank provider call 未注入 request_id。
- 缺口：没有按 request_id 汇总全链路日志的机制，排错需要手动 grep stdout。

### /health 现状

- `GET /health` 返回 `{"status": "healthy", "version": ...}`，是轻量心跳。
- 没有 DB、FAISS、provider 配置的诊断信息。
- Phase 39 做了 `scripts/run_production_smoke.py`（默认 dry-run），但这是外部测试脚本，不是运行时自检端点。

### 现有评测集覆盖

- Stage 38: 24 cases（单轮生成质量）。
- Stage 41: 12 queries（导入后检索质量）。
- Stage 42: 36 cases = Stage 38 24 + Stage 41 12（单轮 Judge gate=pass）。
- 多轮对话：阶段 24 有基本功能测试但无质量评测集。

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| 先做 entities + retrieval_anchors 两类 slot | 最小可验证单元，避免一口气做 5 类 slot 却无法证明每类的增量价值 |
| session memory 不持久化到新表 | 复用 Message metadata 或内存对象，保持最小侵入；后续如需持久化再加表 |
| memory 只注入 query rewrite / retrieval | 回答引用必须来自知识库证据，memory 不能替代；避免 summary 被当作引用来源 |
| JSONL request trace 而非 SQLite | JSONL 最简，可 grep、可 tail，无需额外 DB 迁移；后续如需查询再考虑 SQLite |
| /health/details 不做外部 provider 真实 ping | 避免健康检查触发付费 API 调用 |
| HTTPS reverse proxy 模板降为 stretch goal | 与多轮质量主题脱节，阶段 43 已够重；可在阶段 44 单独做 |
| 四路对比优先用 deterministic provider | 保持可复现；真实 provider 对比作为可选 `--execute` 模式 |

## Issues Encountered

- Phase 0 接手时工作树仍在 `codex/phase-42-generation-quality-and-experience`，且 `task_plan.md`、`findings.md`、`progress.md` 已由 Claude 规划方预填为阶段 43 草稿。
- 本地 `main` 仍停在 Phase 41 合并点 `d7dfca1 Merge phase 41 post-import retrieval optimization`，但 `origin/main` 已是 Phase 42 GitHub 合并提交 `5850139 Merge pull request #9 from CxcTHU/codex/phase-42-generation-quality-and-experience`，并包含 `00e1424 Complete phase 42 generation quality and experience`。
- 按阶段 43 要求，Codex 从 Phase 42 合并后的 `origin/main` 创建 `codex/phase-43-multi-turn-quality-and-observability`，未快进本地 `main`，也未执行 `git add` / commit / tag / push / PR。
- 接手时已有 `data/evaluation/stage30_quality_scores.csv` 与 `stage30_quality_summary.csv` 的新增 Stage 30 run 工作树改动（91.52 / A / pass），暂保留为现有校准产物，后续回归时统一核验。
- Phase 3 首次用线上 `HybridRrfTailSearchService` 执行四路 32-turn 对比时超时；原因是每个 turn 触发全库向量扫描，乘以多种 history mode 后成本过高。为保持阶段评测可复现且不改变线上链路，脚本改为一次加载轻量语料快照并在内存中做 lexical scoring。
- Phase 3 baseline 结果显示 history 注入有明显增益：`no_history avg_retrieval_hit=0.312`，`recent_only=0.531`，`summary_recent=0.594`；Phase 4 后已用真实 `layered_memory` 重建完整四路 CSV。
- Phase 3 Stage 30 复跑保持 `91.52 / A / pass`，未发现评分退化。
- Phase 4 实现 `SessionMemory(entities, retrieval_anchors)` 后，Brain 只在指代/省略类问题的 query rewrite 阶段追加“仅用于检索，不作为引用来源”的 memory hint；回答生成仍只引用 retrieval sources。
- Phase 4 回填四路结果中 `layered_memory` 曾低于 `summary_recent=0.594`。Phase 16 纠错优化后当前值为 `avg_retrieval_hit=0.594, avg_answer_coverage=0.208`。结论是 memory anchors 对覆盖率有增益；Phase 17 已复跑真实 Judge，默认策略仍不替换 summary_recent。
- Phase 5 按场景复核：layered memory 在 `clarification` coverage `0.333` 和 `reference_previous_turn` coverage `0.333` 优于 summary_recent，但 `user_correction` hit 从 `1.000` 降到 `0.750`，说明 retrieval anchors 可能带来前轮残留噪声。阶段 43 不把 layered memory 设为默认替换策略，只作为 query rewrite 的最小辅助能力保留。
- 人工核验反馈后复核并重建 `stage43_multi_turn_baseline_results.csv` 与 `stage43_multi_turn_baseline_summary.csv`：四路均为 `completed_turns=32`、`dry_run_turns=0`，summary 中不再存在未回填的 layered memory 行。Phase 16 后最终 summary 数字为 no_history `hit=0.312/cov=0.104`、recent_only `hit=0.531/cov=0.125`、summary_recent `hit=0.594/cov=0.167`、layered_memory `hit=0.594/cov=0.208`。
- Phase 6 采用 JSONL trace 而非 SQLite：`app/core/request_logger.py` 用 request context 聚合 `log_event()` 的安全字段，middleware 在请求结束写入 `data/logs/request_traces.jsonl`。该目录已加入 `.gitignore`，避免运行日志进入 Git。
- Phase 6 request trace 只保存脱敏摘要；测试覆盖 API key 和 raw_response redaction，并确认 `X-Request-ID` 会进入响应头和 JSONL trace。
- Phase 7 新增 `/health/details` 时保持 `/health` 轻量心跳不变。诊断端点只做本地 DB ping、documents/chunks 计数、FAISS `.index` + `_ids.json` metadata 检查、provider 配置布尔状态，不加载 FAISS 原生索引、不做外部 provider ping。
- Phase 7 响应只包含 provider/model/configured/enabled 等安全字段；测试确认响应中不出现 `api_key`、`Bearer`、`Authorization` 等敏感字段。
- Phase 8 全量回归从阶段 42 的 843 tests 增长到 863 tests，新增覆盖主要来自 Stage 43 多轮评测、session memory、request trace 和 health details；全量 `python -m pytest -q` 通过。
- Phase 8 复跑 Stage 30 仍为 `91.52 / A / pass`，production smoke 默认 dry-run `rows=11 execute=false failed=0`。
- Phase 9 浏览器 smoke 使用本地临时服务 `127.0.0.1:8023`，仅执行闲聊短路多轮（`你好` / `谢谢`），不触发真实 provider。桌面端与 390x844 移动端均为 console errors=0、horizontal overflow=false；临时服务已停止。
- Phase 10 已补齐 README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-43.md` 与 Obsidian 阶段页/Phase 汇报草稿。阶段 43 停在人工核验前，未执行 `git add`、commit、tag、push 或 PR。

## Claude 人工核验发现（2026-06-17）

### P1：四路评测数据与文档不一致

人工核验发现 `stage43_multi_turn_baseline_summary.csv` 仍有 `layered_memory` pending，且当时的三路 CSV 数字与文档数字不一致。复核后确认根因是评测产物没有在 Phase 4 后完整重建，且单路回填命令会覆盖默认 results CSV。

Phase 11 已重建四路 CSV，并以最终 `stage43_multi_turn_baseline_summary.csv` 为准：

| history_mode | completed_turns | dry_run_turns | avg_hit | avg_cov |
|---|---:|---:|---:|---:|
| no_history | 32 | 0 | 0.312 | 0.104 |
| recent_only | 32 | 0 | 0.531 | 0.125 |
| summary_recent | 32 | 0 | 0.594 | 0.167 |
| layered_memory | 32 | 0 | 0.594 | 0.208 |

修正后结论：`summary_recent` 与 `layered_memory` 的 retrieval hit 同为 0.594；`layered_memory` answer coverage 最高（0.208），说明 entities + retrieval_anchors 可以作为辅助检索信号继续保留。Phase 17 真实 Judge 复跑后 citation accuracy 仍低于 `summary_recent`，默认策略不替换。

### P2：results CSV 被局部重跑覆盖

已修复 `scripts/evaluate_stage43_multi_turn.py`：默认输出文件下单路 `--history-mode` 运行会读取既有 results CSV，按 `history_mode` 替换本次模式并保留其它模式。已用 `--history-mode layered_memory --no-dry-run` 复现验证，结果文件仍保持四路各 32 行 completed。

### 后续 Track（Phase 11-15）

- Track A：真实 LLM Judge 评判多轮生成质量（faithfulness / citation / coherence / refusal）
- Track B：基于 Judge 反馈决策 layered_memory 优化方向
- Stretch：HTTPS reverse proxy 模板

### Phase 12：多轮 Judge 设计与合同

- 新增 `docs/stage43_multi_turn_judge.md`，把多轮 Judge 维度固定为 `answer_faithfulness`、`citation_accuracy`、`context_coherence`、`refusal_consistency`。
- 新增 `scripts/judge_stage43_multi_turn_quality.py`，默认 dry-run 展开 32 turns x 4 history modes = 128 rows；显式 `--execute` 才生成答案并调用真实 Judge。
- 脚本复用 Phase 34/42 OpenAI-compatible Judge 形态和脱敏 helper，但使用 Stage 43 四维 parser，避免把 Stage 34 的六指标 schema 混入多轮评测。
- 输出 `stage43_multi_turn_judge_results.csv` / `stage43_multi_turn_judge_summary.csv` 只保存状态、计数、四维分数、risk、short_reason、next_action 和安全错误摘要；不保存完整答案、完整 chunk、raw provider response、`raw_response` 或 `reasoning_content`。
- 聚焦测试 `tests/test_stage43_multi_turn_judge.py` 覆盖四路展开、dry-run、payload 脱敏和分数归一化；`python -m pytest tests/test_stage43_multi_turn_judge.py -q` -> 4 passed。

### Phase 13：真实 Judge 执行与 layered_memory 决策

- 本地 `.env` 具备真实 provider 配置；首次全量 `--history-mode all --execute` 与单路 32 行运行均因 provider 耗时超过 10 分钟而超时。
- 已增强 `scripts/judge_stage43_multi_turn_quality.py`：默认结果文件下单路 `--execute` 支持逐行 checkpoint、重跑跳过 completed 行、按 history_mode 合并结果。该修复避免真实 Judge 长跑中断后丢失已完成结果。
- 最终真实 Judge 四路均完成 32/32，无 error/high risk：

| history_mode | faith | citation | coherence | refusal | gate |
|---|---:|---:|---:|---:|---|
| no_history | 0.678 | 0.603 | 0.794 | 0.778 | review_required |
| recent_only | 0.766 | 0.680 | 0.853 | 0.816 | review_required |
| summary_recent | 0.764 | 0.641 | 0.784 | 0.794 | review_required |
| layered_memory | 0.769 | 0.622 | 0.852 | 0.853 | review_required |

- 结论：`layered_memory` 相比 `summary_recent` 在四个 Judge 维度均有提升，尤其 context coherence 与 refusal consistency；但 citation accuracy 仍低于 0.8，整体 gate 仍为 `review_required`。因此不把 layered_memory 替换为默认策略，只保留为当前 query rewrite / retrieval 辅助，并把 constraints slot 与 stale-anchor invalidation 记录为后续优化方向。
- Stage 30 复跑仍为 `91.52 / A / pass`。

### Phase 14：HTTPS reverse proxy 模板

- 已完成 stretch goal：新增 `deploy/nginx-https.example.conf`、`deploy/Caddyfile.example` 与 `docs/deployment_https_reverse_proxy.md`。
- 模板只描述 `client -> HTTPS reverse proxy -> HTTP uvicorn 127.0.0.1:8000` 拓扑，不改 `Dockerfile`、`docker-compose.yml`、CI 或运行时默认配置。
- Nginx 模板对 `/agent/query/stream` 显式关闭 proxy buffering，避免 SSE token streaming 被代理缓冲；两套模板均传递 `X-Request-ID`，与 Phase 43 request trace 对齐。
- 新增 `tests/test_stage43_https_templates.py`，验证模板存在、streaming/request_id 边界和无 secret 文本；聚焦测试 3 passed。

### Phase 15：最终验证与收尾

- 全量 `python -m pytest -q` -> 876 passed。
- Stage 30 -> `91.52 / A / pass`，不退化。
- production smoke dry-run -> `rows=11 execute=false failed=0`。
- Browser desktop smoke on `127.0.0.1:8024`：Agent 页加载，`hello` / `thanks` 两轮闲聊追加成功，status=`answered`，console errors=0，horizontal overflow=false。
- Browser mobile smoke 390x844：Agent 区域、输入框、运行按钮可见，console errors=0，horizontal overflow=false。
- 临时服务已停止；未执行 `git add`、commit、tag、push 或 PR。

## Phase 16 纠错感知 layered_memory 优化

- Phase 13 真实 Judge 已指出 `layered_memory` 在 coherence/refusal 上有增益，但 citation accuracy 仍不足；后续优化方向是 `constraints slot / stale-anchor invalidation`。
- 本轮实现后，`SessionMemory` 保持当前会话内、检索辅助性质，新增 `constraints` 与 `stale_anchors` 只用于约束 query rewrite / retrieval，不作为引用来源。
- 纠错问题（如“更正一下 / 我说错了 / 想问”）会丢弃未在当前问题重申的旧 `retrieval_anchors`，并把当前问题中显式出现的领域词补为新 anchor；例如 `stage43_correction_02` 第 2 轮从旧“施工质量/质量控制”切换到“裂纹”。
- `BrainService._rewrite_query_step()` 在纠错问题上不再把上一轮完整原文前置到 query，避免旧目标绕过 memory slot 重新污染检索。
- 回填 `layered_memory` 后四路 CSV 仍完整：no_history / recent_only / summary_recent / layered_memory 各 32 completed。
- 最新 baseline：`layered_memory avg_retrieval_hit=0.594, avg_answer_coverage=0.208`，相比 Phase 13 记录的 0.198 coverage 有小幅提升；retrieval hit 已追平 `summary_recent=0.594`。
- 决策不变：不把 `layered_memory` 替换为默认策略；保留为 query rewrite / retrieval 辅助，并把纠错感知过滤作为已落地的安全增量。

## Phase 17 Phase 16 后真实 Judge 复跑

- 为避免默认 Judge CSV 跳过已 completed 的 layered_memory 行，`scripts/judge_stage43_multi_turn_quality.py` 新增 `--force-rerun`。
- Judge case 构造已修正为向 `build_memory_hint()` 传入当前问题，确保 `layered_memory` 的 Judge 输入覆盖 Phase 16 纠错感知 memory hint。
- 执行 `python scripts/judge_stage43_multi_turn_quality.py --history-mode layered_memory --execute --force-rerun`，结果文件保持四路各 32 completed，总计 128 completed。
- 复跑后 `layered_memory` Judge：faith=0.769, citation=0.622, coherence=0.852, refusal=0.853, gate=review_required。
- 对比 `summary_recent`：faith 0.769 > 0.764，coherence 0.852 > 0.784，refusal 0.853 > 0.794，但 citation 0.622 < 0.641。
- 结论：Phase 16 优化提升轻量 baseline 与上下文一致性/拒答维度，但真实 Judge 的 citation accuracy 仍是短板；默认策略不切换，继续保持 `summary_recent`。

## Safety Boundaries

- 不做跨会话长期记忆。
- 不做用户画像/私人偏好记忆。
- 不把 summary 当作可引用资料来源。
- 不把模型生成的 memory 写成知识库事实。
- 不引入新的外部数据源。
- 不让真实 API 成为 CI 或本地全量测试前提。
- Stage 30 必须保持 91.52 / A / pass 或不退化。
- JSONL 日志只保存脱敏摘要，不保存 raw_response、API key、reasoning_content。
- /health/details 不做外部 provider 真实 ping。
