# 阶段 43：多轮对话质量与生产可观测性强化

## 目标

阶段 43 从 Phase 42 已合并到 GitHub 的 `origin/main -> 5850139 Merge pull request #9 from CxcTHU/codex/phase-42-generation-quality-and-experience` 出发，目标分支为 `codex/phase-43-multi-turn-quality-and-observability`。Phase 42 完成了单轮生成质量校准和生产体验完善：`00e1424 Complete phase 42 generation quality and experience`，Stage 30 保持 `91.52 / A / pass`，真实 Judge 在 36 cases 上达到 `structured_final_answer answer_coverage=0.828 / citation_support=0.856 / safety_leak_check=1.000 / gate=pass`。

本阶段只推进两条主线：

```text
主线 A：多轮对话质量评测与会话内分层记忆
16+ multi-turn cases
-> no_history / recent_only / summary_recent / layered_memory 四路对比
-> 最小 session memory: entities + retrieval_anchors
-> memory 只辅助 query rewrite / retrieval
-> 回答引用仍必须来自知识库 sources

主线 B：request_id 追踪与自包含诊断
X-Request-ID 或自动 request_id
-> conversation / summary / memory / retrieval / provider / response 全链路结构化日志
-> data/logs/request_traces.jsonl 脱敏 request trace
-> GET /health/details
-> DB + FAISS + provider config 诊断，不做外部 ping
```

## 当前基线

- 本地 `main` 可能仍停在 `d7dfca1 Merge phase 41 post-import retrieval optimization`，但阶段 43 的正确开发起点是包含 Phase 42 GitHub 合并的 `origin/main -> 5850139`。
- 本地资料库基线仍为 `documents=753`，`indexable child chunks=19300`，GLM 与 deterministic embedding 全覆盖。
- 默认 Agent 链路继续使用 `tool_calling_agent` 和 `structured_final_answer`。
- 多轮机制已有 conversation message 持久化、recent messages 注入和 role="summary" 压缩，但没有多轮质量评测集。
- `app/services/conversation/history.py` 已有 summary 压缩，Brain `rewrite_query` step 已使用 history 做追问上下文补全。
- `app/core/structured_logging.py` 已有 `request_id_var`、`JsonLogFormatter`、`log_event()`，`app/main.py` 已从 `X-Request-ID` 或 `new_request_id()` 设置请求级 request_id。
- 当前 request_id 缺口是 conversation loading、summary assembly、memory assembly、query rewrite、retrieval、provider call 和 final response 没有形成统一可追踪 request trace。

## Phase 顺序

阶段 43 严格按 `task_plan.md` 推进，并在每个 Phase 完成后更新 `task_plan.md`、`findings.md`、`progress.md`：

1. Phase 0：启动校准与规划落盘。
2. Phase 1：设计文档与测试合同。
3. Phase 2：多轮对话评测集。
4. Phase 3：多轮质量 baseline 对比。
5. Phase 4：最小分层会话记忆。
6. Phase 5：多轮质量优化（条件执行）。
7. Phase 6：request_id 贯穿链路追踪。
8. Phase 7：健康诊断增强。
9. Phase 8：全量回归与 Stage 30。
10. Phase 9：浏览器 smoke。
11. Phase 10：文档与 Obsidian 收尾。

开发过程中暂不写 Obsidian 小 Phase 汇报；全部开发、测试和普通文档完成后统一补齐。

## 主线 A：多轮评测合同

新增 `data/evaluation/stage43_multi_turn_eval_cases.csv`，至少包含 16 组多轮对话，每组 2-4 轮，覆盖 8 类场景且每类至少 2 组：

- 追问。
- 指代/省略。
- 澄清。
- 话题切换。
- 引用前轮内容。
- 用户纠错。
- 带约束追问。
- 多轮拒答。

新增 `scripts/evaluate_stage43_multi_turn.py`，默认 deterministic，不调用真实 API。脚本支持 `--history-mode`：

- `no_history`：忽略 conversation_id，每轮独立检索和生成。
- `recent_only`：只注入最近 N 条 user/assistant 消息。
- `summary_recent`：注入 current summary + 最近 N 条消息，是现有默认链路基线。
- `layered_memory`：注入 Phase 4 的 session memory + recent messages。

评测结果输出到 `data/evaluation/stage43_multi_turn_baseline_results.csv`，字段只保存脱敏指标和摘要，例如 case_id、turn_index、scenario、history_mode、status、retrieval_hit、expected_source_hit、citation_support、answer_coverage、refusal_correctness、entity_or_constraint_used、top_source_title、error_summary。不得保存完整回答、完整 chunk 正文、raw provider response、`raw_response`、`reasoning_content`、API key、Bearer token 或 Authorization header。

## 主线 A：分层会话记忆边界

新增 `app/services/conversation/session_memory.py`，实现最小 session memory。首批只做两类 slot：

- `entities`：工程对象、材料、试验方法、堆石混凝土术语、文献主题等当前会话内显式出现的实体。
- `retrieval_anchors`：用于 query rewrite / retrieval 的关键词、标准号、英文缩写、关键中文术语和源标题片段。

本阶段不做跨会话长期记忆，不做用户画像，不做私人偏好记忆，不新增 user profile，不把 memory 写入新的长期表。memory 可从当前 conversation 的 messages 或当前请求上下文重建；如果后续复用 Message metadata，也必须只限当前 conversation 生命周期。

注入策略：

```text
conversation messages
-> summary + recent messages
-> session_memory(entities, retrieval_anchors)
-> query rewrite / retrieval candidate expansion
-> knowledge base retrieval
-> answer generation only cites retrieved sources
```

memory 只能辅助检索和上下文理解，不能替代资料库证据。回答中的 `[N]` 引用仍必须来自知识库 retrieval sources；summary、recent messages 和 memory 均不得成为 citation source。

## 主线 B：request_id 与 JSONL trace

阶段 43 延续 Phase 39 的 request_id contextvars，不改变 `GET /health` 轻量心跳行为。请求入口继续优先读取 `X-Request-ID`，缺失时自动生成 request_id，并写入响应头。

需要让 request_id 贯穿：

- conversation loading。
- summary assembly。
- memory assembly。
- query rewrite。
- keyword / vector / hybrid retrieval。
- tool-calling loop。
- embedding / rerank / chat provider call。
- final response。

结构化日志字段标准化为安全摘要字段：`request_id`、`conversation_id`、`endpoint`、`mode`、`retrieval_mode`、`provider`、`model`、`latency_ms`、`citation_count`、`refused`、`error_type`、`event`、`status`。字段不得包含完整问题、完整回答、完整 chunk、raw provider JSON、API key、Bearer token、Authorization header、`reasoning_content` 或 hidden thought。

新增或扩展 `app/core/request_logger.py`，将一次请求的关键事件按 request_id 汇总写入 `data/logs/request_traces.jsonl`。JSONL 是本阶段的最小自包含诊断，不引入 SQLite request_logs，不接 Sentry、Datadog、Prometheus、Grafana 或其他外部监控 SaaS。

## 主线 B：/health/details 合同

新增 `GET /health/details`，只读返回运行时诊断信息：

- DB 可连接。
- documents/chunks 数量。
- FAISS index 文件是否存在。
- FAISS 向量数或 metadata 数量（可用时返回；不可用时返回 unknown/skipped）。
- deterministic provider 可用。
- 外部 provider 配置状态：已配置 / 未配置 / 部分配置。

`/health/details` 不做外部 provider 真实 ping，不触发付费 API，不重建 FAISS，不写数据库，不重新导入语料。`GET /health` 继续保持轻量心跳，避免破坏 Docker healthcheck 和既有 smoke。

## 验证合同

阶段 43 收尾至少运行：

```powershell
python -m pytest tests/test_stage43_design.py -q
python -m pytest -q
python scripts/score_stage30_quality.py
python scripts/run_production_smoke.py
```

多轮评测至少运行：

```powershell
python scripts/evaluate_stage43_multi_turn.py --history-mode no_history
python scripts/evaluate_stage43_multi_turn.py --history-mode recent_only
python scripts/evaluate_stage43_multi_turn.py --history-mode summary_recent
python scripts/evaluate_stage43_multi_turn.py --history-mode layered_memory
```

浏览器 smoke 覆盖桌面与 `390x844` 移动端：

- Agent 页面多轮对话。
- 追问或指代问题可得到带引用回答。
- 引用来源仍来自知识库 sources。
- console errors=0。
- 横向溢出=false。

## 安全与提交边界

阶段 43 不做：

- 不做跨会话长期记忆。
- 不做用户画像或私人偏好记忆。
- 不把 summary、recent messages 或 memory 当作引用来源。
- 不把模型生成的 memory 写成知识库事实。
- 不新增外部数据源、爬虫、PDF 下载或受限全文写入。
- 不改变 Stage 30 评分规则、权重、等级阈值或 release decision。
- 不改变 provider 拓扑或数据源边界。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不接 Sentry、Datadog、Prometheus、Grafana 或外部监控 SaaS。
- 不把 API key、Bearer token、Authorization header、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk 正文或受限全文写入 Git、CSV、文档、测试、JSONL trace 或 Obsidian。
- 阶段 43 开发完成后不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR，停在用户人工核验前。

## 完成标准

- `docs/stage43_multi_turn_quality_and_observability.md` 与 `tests/test_stage43_design.py` 完成。
- 新增不少于 16 组多轮评测用例，覆盖 8 类场景。
- `no_history`、`recent_only`、`summary_recent`、`layered_memory` 四路对比可运行，并输出量化 CSV。
- 最小分层 session memory 已实现 `entities` 与 `retrieval_anchors`，并接入 query rewrite / retrieval。
- memory 不替代知识库证据，回答引用仍来自 retrieval sources。
- request_id 可追踪到 conversation、summary、memory、retrieval、provider 和 response。
- `data/logs/request_traces.jsonl` 可按 request_id 定位一次请求的脱敏摘要。
- `GET /health/details` 返回 DB、FAISS 和 provider config 诊断。
- Stage 30 维持 `91.52 / A / pass` 或不退化。
- 全量 pytest 通过。
- 桌面 + 移动浏览器 smoke 通过。
- README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-43.md` 与 Obsidian 草稿完成。

## Phase 11-15 补充收尾

人工核验后追加 Phase 11-15，用于修正 CSV 产物、补真实多轮 Judge、给出 layered_memory 决策，并完成 HTTPS 模板 stretch。

补充产物：

- `docs/stage43_multi_turn_judge.md`
- `scripts/judge_stage43_multi_turn_quality.py`
- `data/evaluation/stage43_multi_turn_judge_results.csv`
- `data/evaluation/stage43_multi_turn_judge_summary.csv`
- `deploy/nginx-https.example.conf`
- `deploy/Caddyfile.example`
- `docs/deployment_https_reverse_proxy.md`

真实 Judge 四路结果：

```text
no_history faith=0.678 citation=0.603 coherence=0.794 refusal=0.778 gate=review_required
recent_only faith=0.766 citation=0.680 coherence=0.853 refusal=0.816 gate=review_required
summary_recent faith=0.764 citation=0.641 coherence=0.784 refusal=0.794 gate=review_required
layered_memory faith=0.769 citation=0.622 coherence=0.852 refusal=0.853 gate=review_required
```

决策：Phase 17 对优化后的 `layered_memory` 复跑真实 Judge 后，faithfulness、context coherence、refusal consistency 仍优于 `summary_recent`，但 citation accuracy 低于 `summary_recent` 且仍低于 0.8，整体 gate 仍为 `review_required`。因此本阶段不替换默认会话策略；`layered_memory` 继续作为 query rewrite / retrieval 辅助。

## Phase 16 纠错感知 memory 优化

Phase 16 已落地第一版 constraints slot 与 stale-anchor invalidation：

- `SessionMemory` 扩展为 `entities + retrieval_anchors + constraints + stale_anchors`，仍只来自当前会话。
- 用户纠错问题触发时，未在当前问题重申的旧 `retrieval_anchors` 不再进入 retrieval hint。
- 当前更正问题中显式出现的领域词会补为新 anchor，例如 `stage43_correction_02` 第 2 轮补入 `裂纹`。
- `BrainService._rewrite_query_step()` 对纠错问题不再前置上一轮原文，避免旧目标绕过 memory slot 重新污染检索。
- 回填 `layered_memory` 后四路 CSV 仍各 32 completed；最新 `layered_memory avg_retrieval_hit=0.594, avg_answer_coverage=0.208`。

结论：轻量 baseline 中 `layered_memory` 已追平 `summary_recent=0.594` 的 hit rate，且 coverage 更高；真实 Judge 复跑后 citation accuracy 仍是短板，因此默认策略继续保持 `summary_recent`。
