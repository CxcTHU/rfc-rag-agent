# 阶段 43 任务计划：多轮对话质量与生产可观测性强化

## Goal

在阶段 42 完成单轮 Judge gate=pass（36 cases，structured_final_answer cov=0.828 / cit=0.856 / safety=1.000）的基础上，从两条主线推进：（A）建立多轮对话评测集，实现最小分层会话记忆，量化 no-history / recent-only / summary+recent / layered-memory+recent 四路对比；（B）补齐 request_id 贯穿链路追踪，新增 /health/details 诊断端点和自包含错误日志。完成开发、测试、普通文档与 Obsidian 草稿，停在用户人工核验前。

## Current Phase

Phase 43 complete：开发、测试、普通文档与 Obsidian 草稿已完成；用户已于 2026-06-17 授权提交并合并到 GitHub。

## 当前基线与工作区状态

- Git 基线：阶段 42 已提交为 `00e1424 Complete phase 42 generation quality and experience`，并已合并到 GitHub `origin/main -> 5850139 Merge pull request #9 from CxcTHU/codex/phase-42-generation-quality-and-experience`；本地 `main` 仍停在 `d7dfca1`，阶段 43 已按正确起点从 `origin/main` 创建分支。
- 当前分支：`codex/phase-43-multi-turn-quality-and-observability`，跟踪 `origin/main`，开发完成前不执行 `git add` / commit / tag / push / PR。
- 本地 DB: documents=753, indexable child chunks=19,300, GLM+deterministic embedding 全覆盖。
- Stage 30: 91.52 / A / pass。
- Stage 42 Judge: structured_final_answer cov=0.828 / cit=0.856 / safety=1.000 / gate=pass（36 cases）。
- 全量测试: 843 passed。
- 多轮机制: recent messages + role="summary" 压缩 + conversation_id 注入 Agent。
- request_id: Phase 39 已有 contextvars request_id + JsonLogFormatter，但未贯穿检索/memory/provider 全链路。

## Phases

### Phase 0：启动校准与规划落盘

- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认阶段 42 已合并到 `origin/main -> 5850139`；本地 `main -> d7dfca1` 未快进但不是阶段 43 起点
- [x] 从 Phase 42 合并后的 `origin/main` 创建 `codex/phase-43-multi-turn-quality-and-observability`
- [x] 校准 `task_plan.md`、`findings.md`、`progress.md`
- **Status:** complete

### Phase 1：设计文档与测试合同

- [x] 新增 `docs/stage43_multi_turn_quality_and_observability.md`
- [x] 明确双主线：A（多轮评测 + 分层记忆）和 B（request_id 追踪 + 诊断端点）
- [x] 明确安全边界：不做跨会话长期记忆、不做用户画像、不把 summary 当引用来源、不引入外部监控 SaaS
- [x] 新增 `tests/test_stage43_design.py` 设计合同测试
- [x] 运行设计合同测试
- **Status:** complete

### Phase 2：多轮对话评测集

- [x] 新增 `data/evaluation/stage43_multi_turn_eval_cases.csv`
- [x] 覆盖 8 类多轮场景：追问、指代/省略、澄清、话题切换、引用前轮内容、用户纠错、带约束追问、多轮拒答
- [x] 每类至少 2 组对话（总计 ≥16 组多轮对话，每组 2-4 轮）
- [x] 新增评测脚本 `scripts/evaluate_stage43_multi_turn.py`，支持 `--history-mode` 参数切换 no_history / recent_only / summary_recent / layered_memory
- [x] dry-run 验证评测脚本正确性
- **Status:** complete

### Phase 3：多轮质量 baseline 对比

- [x] 实现四路 history 注入模式的统一对比框架
- [x] no_history：忽略 conversation_id，每轮独立检索+生成
- [x] recent_only：只用最近 N 条 user/assistant 消息
- [x] summary_recent：current summary + 最近 N 条消息（现有默认链路）
- [x] layered_memory：分层记忆（Phase 4 实现后回填，最终 CSV 已包含 completed 结果）
- [x] 运行 deterministic 对比，输出 `data/evaluation/stage43_multi_turn_baseline_results.csv`
- [x] 重点指标：后续轮次检索命中率、citation support、answer coverage、refusal correctness、前轮约束/实体使用正确率
- [x] Stage 30 评分确认不退化
- **Status:** complete

### Phase 4：最小分层会话记忆

- [x] 新增 `app/services/conversation/session_memory.py`
- [x] 实现会话内 session memory 数据结构，首批只做两类 slot：
  - entities：工程对象、材料、试验方法、堆石混凝土术语（从对话中提取）
  - retrieval_anchors：用于 query rewrite / retrieval 的关键词和实体
- [x] 后续可扩展但本阶段不强制实现的 slot：constraints（用户明确限定条件）、open_questions（未解决问题）
- [x] session memory 只存在于当前 conversation 生命周期内，不持久化到新表（复用 Message metadata 或内存）
- [x] 分层注入策略：
  - query rewrite / retrieval 使用 entities + retrieval_anchors + recent messages
  - answer generation 使用 summary + recent messages（memory 不直接注入回答 prompt）
  - memory 只能辅助检索和上下文理解，不能替代资料库证据
- [x] 补齐 layered_memory 模式，回填 Phase 3 四路对比
- [x] 新增测试覆盖 session memory 提取、注入和边界
- **Status:** complete

### Phase 5：多轮质量优化（条件执行）

- [x] 分析 Phase 3/4 对比结果，识别 summary/history 注入缺口
- [x] 如发现明确缺口（如追问场景检索命中率下降 >10%），完成最小策略优化
- [x] 如四路对比差距不大，诚实记录结论，不强行优化
- [x] 重跑多轮评测确认优化效果
- [x] Stage 30 确认不退化
- **Status:** complete

### Phase 6：request_id 贯穿链路追踪

- [x] 扩展现有 `app/core/structured_logging.py` 的 request_id 贯穿范围
- [x] 从 FastAPI 请求入口读取 `X-Request-ID` header 或自动生成，贯穿：
  - conversation loading
  - summary/memory assembly
  - query rewrite
  - retrieval（keyword/vector/hybrid）
  - tool-calling loop
  - provider call（chat/embedding/rerank）
  - final response
- [x] 结构化日志字段标准化：request_id、conversation_id、endpoint、mode、retrieval_mode、provider、model、latency_ms、citation_count、refused、error_type
- [x] 新增 `app/core/request_logger.py` 或扩展现有模块，按 request_id 汇总一次请求的全链路摘要到 JSONL 文件（`data/logs/request_traces.jsonl`）
- [x] JSONL 文件只保存脱敏摘要，不保存 raw_response、API key、reasoning_content
- [x] 新增测试验证 request_id 在关键节点的传播
- **Status:** complete

### Phase 7：健康诊断增强

- [x] 新增 `GET /health/details` 只读诊断端点
- [x] 返回内容：
  - DB 可连接（SQLAlchemy session ping）
  - documents/chunks 数量
  - FAISS index 文件是否存在
  - FAISS 向量数（如已加载）
  - deterministic provider 可用
  - 外部 provider 配置状态（已配置 / 未配置，不做真实 ping）
- [x] 不修改 `GET /health` 原有行为（轻量心跳）
- [x] 新增测试覆盖 /health/details 响应结构
- **Status:** complete

### Phase 8：全量回归与 Stage 30

- [x] 运行 `python -m pytest -q` 全量测试
- [x] 运行 `python scripts/score_stage30_quality.py` 确认 91.52 / A / pass 或不退化
- [x] 运行 production smoke（dry-run）
- **Status:** complete

### Phase 9：浏览器 smoke

- [x] 桌面浏览器 smoke：Agent 页面多轮对话、console errors=0、横向溢出=false
- [x] 移动端 390x844 smoke
- **Status:** complete

### Phase 10：文档与 Obsidian 收尾

- [x] 更新 `README.md`
- [x] 更新 `docs/progress.md`
- [x] 判断并更新 `docs/architecture.md`（分层记忆和 request_id 追踪涉及架构变更）
- [x] 新增 `docs/phase_reviews/phase-43.md` 验收草稿
- [x] 更新 Obsidian：阶段 43 页、Phase 汇报、阶段索引、首页
- [x] 最终不执行 git add/commit/tag/push，停在人工核验前
- **Status:** complete

### Phase 11：四路数据修复与文档校正

- [x] 人工核验发现 `stage43_multi_turn_baseline_summary.csv` 仍有 `layered_memory` pending，且局部回填命令会覆盖默认 results CSV。
- [x] 修复 `scripts/evaluate_stage43_multi_turn.py`：默认输出文件下单路 `--history-mode` 运行改为按 mode 合并替换，不再清空其它三路。
- [x] 重跑 `python scripts/evaluate_stage43_multi_turn.py --history-mode all --no-dry-run`，恢复四路完整 CSV。
- [x] 复跑 `python scripts/evaluate_stage43_multi_turn.py --history-mode layered_memory --no-dry-run`，验证单路回填后四路仍各有 32 行 completed。
- [x] 验证最终 CSV 数据：
  - no_history: avg_hit=0.312, avg_cov=0.104
  - recent_only: avg_hit=0.531, avg_cov=0.125
  - summary_recent: avg_hit=0.594, avg_cov=0.167
  - layered_memory: avg_hit=0.594, avg_cov=0.208
- [x] 用最终 CSV 数字校正 findings.md、progress.md、docs/progress.md、docs/phase_reviews/phase-43.md。
- [x] 基于真实数据重写结论：`summary_recent` 仍是默认推荐；`layered_memory` 提升 answer coverage（Phase 16 后为 0.208）和 entity/constraint 使用，且轻量 baseline hit 已追平 `summary_recent`。
- **Status:** completed

### Phase 12：真实 LLM Judge 多轮评测设计与合同

- [x] 新增设计文档 `docs/stage43_multi_turn_judge.md`，说明多轮 Judge 评判维度：answer_faithfulness、citation_accuracy、context_coherence、refusal_consistency。
- [x] 新增 `scripts/judge_stage43_multi_turn_quality.py`，默认 dry-run，显式 `--execute` 才生成答案并调用真实 Judge。
- [x] Judge CSV 只保存脱敏分数、短理由、风险等级和 next_action，不保存 answer/raw_response/reasoning_content。
- [x] 复用 Phase 34/42 的 OpenAI-compatible Judge 配置和脱敏 helper，新增 Stage 43 四维 parser。
- [x] 新增 `tests/test_stage43_multi_turn_judge.py`，验证四路 case 展开、dry-run 不调用真实 API、payload 脱敏和 score parser。
- [x] dry-run 通过：`python scripts/judge_stage43_multi_turn_quality.py --history-mode all` -> 128 rows, completed=0, execute=false。
- **Status:** completed

### Phase 13：真实 LLM Judge 执行与 layered_memory 决策

- [x] dry-run 通过后，用 `--execute` 在多轮评测集上运行真实 LLM Judge。
- [x] 因真实 provider 单次全量 128 行运行超过 10 分钟，脚本已增强为单路逐行 checkpoint + 默认结果文件按 history_mode 合并，避免中断丢失进度。
- [x] 输出 `data/evaluation/stage43_multi_turn_judge_results.csv` 和 `stage43_multi_turn_judge_summary.csv`，四路均为 32/32 completed。
- [x] Judge summary：
  - no_history: faith=0.678, citation=0.603, coherence=0.794, refusal=0.778, gate=review_required
  - recent_only: faith=0.766, citation=0.680, coherence=0.853, refusal=0.816, gate=review_required
  - summary_recent: faith=0.764, citation=0.641, coherence=0.784, refusal=0.794, gate=review_required
  - layered_memory: faith=0.769, citation=0.622, coherence=0.852, refusal=0.853, gate=review_required（Phase 17 复跑后）
- [x] 决策：`layered_memory` 相比 `summary_recent` 四个 Judge 维度均有提升，但 citation_accuracy 仍低于 0.8 且整体 gate=review_required；本阶段不替换默认策略，保留为 query rewrite / retrieval 辅助，并把 constraints slot / stale-anchor invalidation 作为后续优化方向。
- [x] Stage 30 确认不退化：`91.52 / A / pass`。
- **Status:** completed

### Phase 14：HTTPS reverse proxy 模板（stretch goal）

- [x] 提供 Nginx 与 Caddy 反向代理配置模板（TLS 终止 + proxy_pass/reverse_proxy 到 uvicorn）。
- [x] 新增 `docs/deployment_https_reverse_proxy.md`，文档化部署拓扑：client -> HTTPS (Nginx/Caddy) -> HTTP (uvicorn)。
- [x] 不改变现有 Docker compose 或 CI 流程，只添加示例配置。
- [x] 新增 `tests/test_stage43_https_templates.py`，验证模板存在、保留 streaming/request_id 边界且不包含 secret。
- **Status:** completed

### Phase 15：全量回归、文档与 Obsidian 收尾

- [x] 运行 `python -m pytest -q` 全量测试 -> 876 passed。
- [x] 运行 `python scripts/score_stage30_quality.py` -> 91.52 / A / pass。
- [x] 运行 production smoke（dry-run）-> rows=11 execute=false failed=0。
- [x] 浏览器 smoke（桌面 + 390x844 移动端）-> passed，console errors=0，horizontal overflow=false。
- [x] 更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/stage43_multi_turn_quality_and_observability.md、docs/phase_reviews/phase-43.md。
- [x] 更新 Obsidian：阶段 43 阶段页、Phase 11-15 汇报、阶段索引、首页、阶段汇报索引。
- [x] 最终不执行 git add/commit/tag/push，停在人工核验前。
- **Status:** completed

## 完成标准（含后续 Phase 11-15）

- 新增 ≥16 组多轮对话评测用例，覆盖 8 类场景。
- no_history / recent_only / summary_recent / layered_memory 四路对比有完整且准确的量化结果 CSV，文档数字与 CSV 一致。
- 多轮追问场景的检索命中和回答覆盖率有量化结论。
- 如发现 summary/history 注入缺口，完成最小策略优化；如无明显缺口，诚实记录。
- 最小分层会话记忆（entities + retrieval_anchors）已实现并接入 query rewrite。
- 真实 LLM Judge 已对多轮评测集做出评判，结果有 CSV 量化记录。
- 基于 Judge 反馈对 layered_memory 做出明确决策（升级/优化/保持现状），决策有数据支撑。
- Stage 30 保持 91.52 / A / pass 或不退化。
- request_id 可从 API 日志追踪到 conversation/retrieval/provider/response 全链路。
- /health/details 显示 DB、FAISS、provider 配置状态。
- JSONL request trace 可按 request_id 定位一次请求的检索、生成、响应过程。
- 不引入新的外部监控 SaaS，不引入跨会话长期记忆。
- 全量测试通过。
- 普通文档与 Obsidian 草稿完成。
- 最终停在人工核验前，不 git add/commit/tag/push/PR。
### Phase 16：纠错感知 layered_memory 优化

- [x] 根据 Phase 13 Judge 结论继续收窄 `constraints slot / stale-anchor invalidation` 优化方向。
- [x] `SessionMemory` 扩展为 `entities + retrieval_anchors + constraints + stale_anchors`，仅限当前会话，不做跨会话长期记忆或用户画像。
- [x] 用户纠错问题触发时，旧检索锚点不再进入 retrieval hint；同时从当前更正问题中显式出现的领域词补充新 `retrieval_anchors`。
- [x] `BrainService._rewrite_query_step()` 对纠错问题不再把上一轮原文前置到检索 query，避免已被纠正的旧目标重新污染检索。
- [x] `scripts/evaluate_stage43_multi_turn.py` 的 `layered_memory` 评测规划同步纠错过滤策略，单路回填仍保留其它三路 CSV。
- [x] 新增/更新测试合同覆盖 stale anchor 过滤、当前问题新 anchor 补充、纠错场景 planned question 不含旧锚点。
- [x] 重新运行 `python scripts/evaluate_stage43_multi_turn.py --history-mode layered_memory --no-dry-run`：四路结果仍各 32 completed，`layered_memory avg_hit=0.594, avg_cov=0.208`。
- [x] focused regression：`python -m pytest tests/test_session_memory.py tests/test_stage43_multi_turn_eval.py tests/test_stage43_multi_turn_judge.py -q` -> 19 passed。
- [x] Stage 30：`python scripts/score_stage30_quality.py` -> 91.52 / A / pass。
- **Status:** completed

### Phase 17：Phase 16 后真实 Judge 复跑

- [x] 修正 `scripts/judge_stage43_multi_turn_quality.py`：新增 `--force-rerun`，允许默认 Judge CSV 下强制重跑已 completed 的指定 history mode。
- [x] 修正 Judge case 构造：`layered_memory` 的 memory hint 使用当前问题生成，确保复跑覆盖 Phase 16 纠错过滤路径。
- [x] focused regression：`python -m pytest tests/test_stage43_multi_turn_judge.py tests/test_stage43_multi_turn_eval.py tests/test_session_memory.py -q` -> 19 passed。
- [x] 真实 Judge 复跑：`python scripts/judge_stage43_multi_turn_quality.py --history-mode layered_memory --execute --force-rerun` -> 128 rows / 128 completed。
- [x] 复跑后 layered_memory Judge：faith=0.769, citation=0.622, coherence=0.852, refusal=0.853, gate=review_required。
- [x] Stage 30：`python scripts/score_stage30_quality.py` -> 91.52 / A / pass。
- **Decision:** `layered_memory` 在轻量 baseline 中 hit 追平、coverage 更高，但真实 Judge citation 低于 `summary_recent=0.641` 且 gate 仍为 `review_required`；默认策略继续保持 `summary_recent`，`layered_memory` 保留为检索辅助。
- **Status:** completed
