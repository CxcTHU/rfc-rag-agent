# 现场快照

更新时间：2026-07-18

## Phase 66 验收后低延迟默认提升现场

- 用户已明确确认：已验收的低延迟链路应成为默认生产行为。
- `agent_short_loop_enabled`、`phase64_route_first_enabled`、
  `phase64_retrieval_fanout_enabled` 现在代码默认均为 true；显式 false 只用于有界诊断/A/B。
- 普通命令 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` 的验收复核没有通过 shell
  注入上述三个变量；当时的受控服务已停止，PID 20024 当前不再运行。
- 该次受保护 `/health/retrieval-contract` 返回三个值均为 true；Agent 省略模型默认仍为
  `deepseek-v4-flash`，不要把全局 `CHAT_MODEL_NAME` 与 Agent 默认混为一谈。
- UI 新增 `final_answer_generating / waiting_final_model`，避免最终模型 TTFT 被显示成
  `evidence_sufficient` 卡住；React 生产包已重建。
- 验证：完整后端 `1936 passed, 1 skipped`；前端 `32 passed`，lint/build 通过。
- 用户于 2026-07-18 已授权本地、Obsidian、GitHub 与新 CPU 同步。提交范围仍不得包含既有
  `.playwright-cli/`、`output/`、根目录 PNG 或 Phase 64 Obsidian 的无关格式化改动。
- 两题复测是定向性能证据，不是广义 latency release gate；不得夸大验收范围。
- GitHub PR #43 当前 frontend check 阻塞：unit/lint/build 已通过，但 Linux build 证明已提交的
  `frontend/dist/index.html` 在 `</div>` 后多一个空行。用户已确认删除该空行、重跑前端 build/diff gate
  并推送；PR 尚未合并、`phase-66-complete` tag 尚未创建。
- 上述 CI 问题已由 `d86dd0e1` 修复，PR #43 十项 checks 全部通过并合并为 `1af07fc1`；
  `phase-66-complete` 已推送并指向 `d86dd0e1`。

## Phase 67 CPU 迁移现场

- 旧维护入口仍是 `rfc-cpu`（Tailscale + SSH key），部署目录
  `/home/ubuntu/rfc-rag-agent-stage44-smoke`；旧三容器健康，app network mode 为 host，DB/Redis
  只绑定 `127.0.0.1:15432/16379`。旧 `data/` 约 6.8 GiB，Docker volumes 约 2.6 GiB。
- 新机维护入口为 `rfc-cpu-new`，现在通过独立 Tailscale 节点连接；`rfc-cpu-new-public` 是公网 SSH
  回退。部署目录同上，Docker/Compose/Nginx/Cloudflare/Tailscale 均已安装并验证。旧机
  `/var/lib/tailscale` 身份状态没有复制。
- 用户授权后，稳定维护别名已完成切换：`rfc-cpu` 与 `rfc-cpu-new` 均连接新 CPU；
  `rfc-cpu-old` 明确保留旧 CPU 回滚入口，`rfc-cpu-new-public` 保留新 CPU 公网 SSH 回退。
- 首次迁移直接导入的 app 镜像 `79aec024f642` 创建于 Phase 66 之前；尽管宿主机源码已有
  `1af07fc1` 标记，容器内仍缺少 Phase 66 默认值与新前端资产。该错误已补正：当前 live image 为
  `rfc-rag-agent:phase66-1af07fc1` / `1296fcc926a0`，OCI revision 绑定完整 merge commit。Phase 66
  无 `pyproject.toml` 依赖变化，因此在 Docker Hub 超时条件下基于旧镜像离线覆盖全部合并 runtime
  代码、Alembic、scripts 与 `frontend/dist`；旧镜像保留 `pre-phase66-79aec024` 标签。
- 当前 app/db/redis 均 healthy；app 为 host network，DB/Redis 仅监听回环。live 配置确认 short-loop、
  route-first、retrieval fan-out 均为 true，默认模型为 `deepseek-v4-flash`，新等待态和
  `index-DDE0lgzL.js` 均已生效。认证 Agent 与 Judge 分别 200，Judge 为 completed。
- PostgreSQL 关键表计数完全一致：`1153 / 51738 / 74067 / 61 / 28 / 220`；Redis dbsize 均为 0。
  durable `data/` 排除易变 `logs/` 后 rsync dry-run 无差异，images/FAISS/KG 文件数一致。
- 公网入口已按旧机真实拓扑补正为 Cloudflare Tunnel，而不是开放安全组端口。新
  `cloudflared-rfc-rag-agent.service` active/enabled、4 connections；四域名健康 200，认证原图和
  真实 Agent 域名链路 200。旧 Cloudflare connector inactive/disabled，保留配置供回滚。
- 新机禁用了两个长期连接超时的用户级 SSH 隧道，启用与旧机实际工作方式一致的系统级 Python provider
  forward；18443/18444 正常监听。旧机同类失效单元也已停用，新机不再需要的 BGE SSH 私钥已删除。
  当前生产 `.env.prod` 仍直接使用 SaaS provider，因此系统级 forward 是备用出口。
- 旧 CPU、旧数据库和旧服务保持在线；新机 DB dump 与旧机 transfer 备份暂留到用户验收后再清理。
  一次性服务器间迁移密钥已双端删除，本机 `rfc-cpu-new` 公钥入口正常。
- Cloudflare、Tailscale 与 provider forward 均 active/enabled；旧 Cloudflare connector
  inactive/disabled。Tailscale 节点密钥当前到期时间为 2027-01-14，若要长期免维护连接，仍需在
  Tailscale 管理台关闭该节点 key expiry。新 CPU 尚无经验证的异机/定时备份，这是迁移后的持久化风险。

## Phase 66 收口状态

- 当前授权动作：用户要求按 `AGENT.MD / AGENTS.md` 执行阶段 66 本地 Git、GitHub PR/merge 与
  Obsidian 阶段文件同步。
- 收口范围：Tool Calling Runtime 真正瘦身、文本/上传图片统一 coordinator 链路、typed tool
  registry/adapters、固定常用 Agent 回归集、默认 Flash 修正、纯图检索延迟修复、拒答展示策略修复。
- 质量证据：PostgreSQL/pgvector judge-backed A/B packet 已通过；A/B 各 30 text + 4 image，
  query/judge failure 均为 0，B overall `0.870343137254902`，A overall
  `0.8264705882352942`。
- 验收边界：这不是 Phase65 holdout/judge 总门禁通过，也不是完整高成本 latency release gate；
  SQLite A/B 仅为 runtime smoke，不作为 final evidence。
- 安全边界：不要提交 `output/`、`.env`、密钥/token、provider raw response、raw answer、
  `reasoning_content`、完整 chunk、私有日志或原始上传图片。
- 下一步：仅暂存 Phase66 相关代码、测试、文档与
  `obsidian-agent开发/阶段/阶段 66 - Tool Calling Runtime 真正瘦身/` 四类文件，运行必要检查后
  commit、push、创建 PR 到 `main`，检查通过再 merge。

## 工作区

- 唯一开发工作区：`G:\Codex\program\rfc-rag-agent`。
- 分支：`codex/phase-64-mainstream-agent-latency`；Phase65 代码尚未提交，按宪法等待用户人工核验。
- Phase65 隔离 worktree 仅保留为迁移来源/恢复参考，不再用于后续开发。

## 65A 实施状态

- Tasks 1–4 已完成并迁入主工作区。
- 主工作区迁移复审：无 Critical/Important；定向交叉回归 `129 passed`，完整回归
  `1598 passed, 1 skipped`。质量报告的 HTML 内嵌 JSON、`/quality-report/data.json`
  与 `/quality-report/export.csv` 均返回 `blocked/stale/local_integrity_only`；CSV 按钮
  只调用服务端端点，不再导出历史 PASS。
- 关键文件：
  - `scripts/phase65_gate_manifest.py`
  - `scripts/phase65_agent_gate.py`
  - `scripts/evaluate_phase65_agent_gate.py`
  - `scripts/verify_phase65_test_receipt.py`
  - `scripts/score_stage30_quality.py`

## 当前外部验收门槛

Task 5 的真实 baseline 已按用户裁定视为完成，不再阻塞后续阶段：

- 旧完整 90 rows：`88/90 ok`；两个失败点随后已定向修复。
- 目标失败 case 复测：`phase64-followup-02` 与 `phase64-long-02`，2 cases × 3 runs =
  6 rows，`6/6 ok`，cold-cache receipt 全部 `valid`。
- 30 cases × 1 run = 30 rows，`30/30 ok`，cold-cache receipt 全部 `valid`。

provider `usage` 不含 `cost`/`total_cost`。用户已明确移除费用收据门禁，评测器不再因
`missing_usage_receipt` 阻断；cold-cache 隔离和检索契约继续强制。不要再重跑完整 90 rows
baseline，除非用户重新明确要求。

原主工作区本地数据库存在非空语料；Phase65 服务需要在不暴露配置/密钥的前提下，受控
地使用该数据源并满足 `require_pgvector`。

## 本轮预检

- 主工作区真实 baseline 阶段性结果：目标 2×3 为 `6/6 ok`，30×1 为 `30/30 ok`；
  安全输出位于 `output/phase65/baseline-after-salt-target2-*` 与
  `output/phase65/baseline-fasttimeout-30x1-*`（`output/` 未跟踪，不应提交）。
- `baseline-final-90-*` 是旧完整 90 rows 产物，结果为 `88/90 ok`。后续失败点已定向
  修复并复测通过。`baseline-incremental-90-*` 是后来误启的新跑，仅作增量写入测试参考，
  不作为 baseline 结论。
- Phase65 focused regression：`103 passed`；`py_compile` 通过；`git diff --check`
  仅 CRLF 警告。主工作区完整后端回归历史仍为 `1598 passed, 1 skipped`，本轮未重跑全量。
- 当前本地 8001 使用进程环境启动：`AGENT_SHORT_LOOP_ENABLED=true`、
  `PHASE64_ROUTE_FIRST_ENABLED=true`、`RETRIEVAL_RUNTIME_ENABLED=true`、
  `RETRIEVAL_RUNTIME_DEFAULT_ENABLED=true`、`AGENT_FINAL_MAX_TOKENS=160`、
  `CHAT_MODEL_TIMEOUT_SECONDS=15`；未写入 `.env`。服务 PID 可重新检查 8001 监听。
- `evaluate_phase65_agent_gate.py --execute` 优先从自身进程环境读取 `--token-env`，
  未设置时才从主工作区 `.env` 读取同名变量。当前 `.env` 仍没有
  `PHASE65_AUTH_TOKEN` 变量名；恢复时可在任一路径设置短期令牌，禁止把值写入交接、
  日志或产物。

## 65B 当前实现

- 用户已人工验收 65B Runtime / Tool-calling 拆解内容为 PASS。该验收覆盖职责拆分、默认
  RunCoordinator 接管、模块化可测试性和 fail-closed runtime 边界；不等同于 Phase65 总 closeout
  PASS。当前唯一明确保留风险是拆解后端到端延迟收益尚未稳定证明，后续继续作为性能证据项处理。
- `runtime_contracts.py`、`runtime_events.py`、`planning_policy.py`、
  `tool_executor.py`、`evidence_state_machine.py`、`final_answer_controller.py`、
  `checkpoint_repository.py` 与 `run_coordinator.py` 已建立并各有定向测试。
- `checkpoint_repository.py` 已拥有 run-store、resume 决策、安全序列化和快照；
  `runtime_checkpoint.py` 仅兼容导出，服务已改从新边界导入。`ToolCallingAgentService`
  已委托 PlanningPolicy、ToolExecutor、FinalAnswerController 和 CheckpointRepository 的
  已迁移路径；普通无上传图片 query 现在默认由 RunCoordinator 接管。
- 模型最终内容的引用校验/单次修复与流式缺引用补救均已迁入
  `FinalAnswerController`；`ToolExecutor` 对 checkpoint 中的 completed tool ID
  fail-closed，不会重复调用检索工具。显式与自动 resume 已复用同一个 runtime run。
- `ToolExecutor.execute_short_loop()` 已透传 iteration、deadline 和 completed-tool guard；
  快速路径升级后的第二次检索现在使用 `runtime-retrieval-2`，与 `RunCoordinator` 的执行语义保持一致。
- `RunCoordinator` 已把 iteration/deadline 传给 `ToolExecutor`，并在每次工具执行后写入
  安全 `tool_execution_completed` checkpoint。该状态只保存 completed tool id、工具名、成功标记和
  selected count，不保存答案、chunk、provider 原文或密钥。
- `CheckpointRepository.completed_tool_ids()` 已能从安全 checkpoint 状态读取 completed tool ids；
  `RunCoordinator` 会在每次工具执行前透传该集合给 `ToolExecutor`，恢复/重入时可 fail-closed
  跳过已完成工具调用。
- `CheckpointRepository.complete()` 会保留已有安全 checkpoint 状态并追加 `stop_reason`，
  不再用仅含 stop_reason 的状态覆盖 completed tool ids、sources 等安全恢复元数据。
- `EvidenceStateMachine` 已把 `deadline_exhausted` 作为 fail-closed 终态：工具执行返回
  deadline exhausted 时直接拒答，不再尝试升级或二次检索；`RunCoordinator` 有对应集成测试。
- `RunCoordinator` 已接管最终生命周期 checkpoint：answer 路径写
  `final_answer_completed`，refuse/escalate 路径写 `final_answer_refused`，随后再 `complete()`。
  状态仅保存 action、stop_reason、evidence detail 和 citation 计数等安全元数据。
- `FinalAnswerController` 提供 `outcome_from_result()` 标准构造；`RunCoordinator` 会把
  final controller 返回值归一成 `FinalAnswerOutcome`，后续替换 service 主循环时可直接使用该合同。
- `RunCoordinator` 已内置默认 `FinalAnswerRequest` 构造，会从 request/planning/tool outcome
  提取 question、history、strategy、sources、search_results、tool call、runtime_state 和 prompt budgets；
  仍支持注入 builder，便于旧 service 渐进迁移。
- `final_result_assembler.py` 已接管 tool-calling 最终 `AgentQueryResult` 装配、safe trace 计数和
  reasoning summary；`ToolCallingAgentService.result_from_tool_calling_loop()` 现只做兼容委托。
- `final_result_assembler.py` 已接管最终模型失败 fallback：从已检索 sources 生成最多 3 条 cited
  evidence fallback，设置 `final_generation_failed` 安全 trace 和 runtime stop/final decision；
  `ToolCallingAgentService.result_from_final_generation_failure()` 现只做兼容委托。
- `final_result_assembler.py` 已接管 cached-evidence 最终结果装配：service 仍负责调用
  `FinalAnswerController.generate_evidence()`，但 stop/final decision、refusal、safe trace 和
  `AgentQueryResult` 装配统一由 assembler 完成。
- `final_result_assembler.py` 已接管 runtime checkpoint 恢复结果装配：service 仍负责
  checkpoint state 反序列化和恢复后的 `FinalAnswerController.generate_evidence()`，但 missing
  sources、恢复完成、citation 缺失拒答和最终 safe trace 由 assembler 统一处理。
- `final_result_assembler.py` 已接管 pre-tool refusal 早退结果装配：responsibility/off-topic
  gate 的判定与结构化日志仍留在 service，最终 `AgentQueryResult`、workflow step 和 trace
  由 assembler 统一生成。
- `RunCoordinator` 已新增可注入 `PreToolGateDecision` 入口门禁合同：plan/start checkpoint 后、
  tool execution 前可以 fail-closed 返回，跳过工具执行/evidence evaluation，并写最终 checkpoint。
  后续可把 responsibility/off-topic/resume 早期路径迁入该入口。
- service 的 responsibility/off-topic 早期门禁已抽成 `build_tool_calling_pre_tool_gate_decision()`。
  `ToolCallingAgentService.query()` 仍负责结构化 refusal 日志和返回，但门禁判定已返回
  `PreToolGateDecision`，可直接接入 `RunCoordinator` 的 pre-tool gate 插槽；测试覆盖
  resume 时不触发 off-topic gate 的既有语义。
- runtime resume 早期路径已抽成 `build_tool_calling_resume_gate_decision()`。无可恢复 run
  时返回 continue；可恢复 run 时复用 checkpoint 结果装配并返回 `PreToolGateDecision`。
  service 仍负责给旧 checkpoint 写 `resume_completed`，以保持现有持久化语义。
- semantic evidence cache 命中路径已抽成 `build_tool_calling_semantic_cache_gate_decision()`。
  未启用、identity 不可复用或未命中时返回 continue；命中时保留 semantic trace、runtime
  evidence、safe tool-result event 和 cached-evidence 最终回答生成，并返回 `PreToolGateDecision`。
- 新增 `build_tool_calling_combined_pre_tool_gate_decision()`，把 pre-tool refusal、runtime resume
  和 semantic evidence cache gate 串成一个按顺序短路的组合 gate。service 已分阶段调用该组合
  gate：早期只跑 responsibility/off-topic；preflight 后再跑 resume/cache，保持 image/preflight
  优先级不变。
- 新增 `ToolCallingCoordinatorGateAdapter`，实现 `RunCoordinator` 的
  `pre_tool_gate(request, planning, run)` 调用形状，并复用 service combined gate。当前已验证
  coordinator 能通过该 adapter 在工具执行前返回 service refusal；adapter 在 resume gate 返回时
  会调用 resume completion recorder，把被恢复的旧 run 写入 `resume_completed` 安全状态。
  默认 service 纯文本路径已切到 RunCoordinator，上传图片仍保留 legacy 多模态路径。
- `AGENT_RUN_COORDINATOR_ENABLED` 现在默认 `true`。无上传图片时，
  `ToolCallingAgentService.query()` 会走 `RunCoordinator -> ToolExecutor ->
  EvidenceStateMachine -> ToolCallingFinalAnswerFacade`，并返回既有 `AgentQueryResult` 形状；
  环境变量显式设为 `false` 可回退旧主循环。
- `RunCoordinator` 现在会在工具执行期间绑定 `LatencyTrace`、retrieval plan 和 Phase64
  route context；触发 fast-route escalation 后，第二轮工具执行会刷新为升级后的
  retrieval/route context，退出时恢复为默认上下文。
- `RunCoordinator` 的拒答路径会把 EvidenceStateMachine 的安全 detail 写入
  `runtime_state` 后再调用 final facade；`ToolCallingFinalAnswerFacade.refuse()` 会保留
  已有 detail，不再把所有拒答覆盖成 `insufficient_evidence`。`reranking_failed`
  仍作为 legacy detail 暴露，`deadline_exhausted` 现在归一为闭合 stop reason。
  facade 还会把白名单 detail 转成 bounded user-facing refusal message，避免开关路径只给
  泛化拒答。
- `RunCoordinator` 会通过 request event sink 发布安全 `agent_step` 生命周期事件；
  service 的 `AGENT_RUN_COORDINATOR_ENABLED` 开关路径现在把 `RuntimeEventBus` 传入
  `CoordinatorRequest`，因此 legacy SSE/event sink 仍能收到 planning/evidence/final step
  和 ToolExecutor 的 tool start/result。pre-tool gate 早退路径也会发布 `final_refuse`
  agent step，避免 responsibility/off-topic/resume/cache 早退在事件流里突然结束。
- `CoordinatorRequest` 已新增 `token_emitter`，默认 `FinalAnswerRequest` 会继续透传；
  `ToolCallingFinalAnswerFacade.generate()` 在 provider 支持 streaming 时复用
  `FinalAnswerController.stream_evidence()`，并用 token emitter 发送本地安全引用后缀，
  为 coordinator 路径接管 stream API 的最终回答 token 通道打基础。
- 显式 coordinator SSE 已修复 token 双写：`QueueStreamingChatModelProvider.stream_generate()`
  本身会把 provider token 投到 SSE 队列，因此 service 在检测到
  `stream_generate_emits_tokens` 标记时，不再额外把同一个 `emit_stream_token` 传给
  `FinalAnswerController`。对应 stream 测试现在校验 metadata answer 与实际 token 拼接一致。
- RunCoordinator 已新增可注入 HyDE query builder。显式 coordinator 路径在 semantic evidence
  cache miss 后，会复用 identity `hyde_passage` 或 legacy `generate_hyde_vector_query()`，
  并在普通检索工具执行期间绑定 `current_hyde_vector_query()`；显式 required table/figure
  preflight 不提前生成 HyDE，避免偏离 legacy preflight 顺序。HyDE 仍只用于 vector retrieval，
  不进入最终 citations。
- RunCoordinator 已支持 runtime policy-owned `tool_sequence`：planning action 可声明多个
  高层 evidence tools，coordinator 会按 `max_tool_calls/max_iterations` 截断执行，并把多个
  tool calls、workflow steps、search_results 和 sources 合并进标准 `FinalAnswerRequest`。
  `RetrievalAction` 对显式 table/figure 现在产出
  `search_tables/search_figures -> hybrid_search_knowledge`，先满足必需资产，再补文本支撑。
  `EvidenceStateMachine` 会优先检查 required tool 自身结果数，因此 required figure/table
  为空时不会因为 hybrid 文本来源存在而误答。
- `FinalAnswerController` 现在提供标准 `generate(FinalAnswerRequest) -> FinalAnswerOutcome`
  合同：非流式/流式最终回答、引用校验、至多一次修复、流式缺引用安全后缀、最终
  `AgentQueryResult` 装配、runtime stop/final decision 写入都在 controller 内完成。
  `ToolCallingFinalAnswerFacade.generate()` 已缩减为薄委托；provider 支持 streaming 且
  request 带 `token_emitter` 时，controller 会发出完整最终回答 token 和本地安全引用后缀。
- `FinalAnswerController.from_cached_evidence()` 与 `FinalAnswerController.from_checkpoint()`
  已接管 semantic evidence cache 命中和 runtime checkpoint 恢复后的最终回答生成与
  `AgentQueryResult` 装配；`ToolCallingAgentService` 中的 `result_from_cached_evidence()` /
  `result_from_runtime_checkpoint()` 仍保留兼容函数名，但已改为薄委托。
- 旧主循环中的 final-answer 底层调用已继续收敛：streaming final answer、evidence-convergence
  final answer、已有 model draft validate/repair 现在分别调用
  `FinalAnswerController.stream_final_evidence()`、`generate_final_evidence()` 和
  `validate_model_content()`。`tool_calling_service.py` 不再直接调用 controller 的底层
  `.generate_evidence()` / `.stream_evidence()` / `.validate_or_repair()`。注意旧主循环 SSE
  仍由 API 层负责完整 token 输出，controller 在旧路径只补发缺引用安全后缀，避免 token 双写。
- 旧主循环已有 9 个最终 answer/refuse 分支通过 `outcome_from_tool_calling_loop()` 兼容 helper
  先构造标准 `FinalAnswerOutcome` 再返回 result：evidence-convergence 成功、model-final-answer
  成功、final-content-without-citations 拒答、iteration-limit 拒答、上传图片 legacy fallback、
  required-tool/preflight 无结果、短循环证据不足、模型工具循环 reranking_failed、required figure
  evidence missing。checkpoint 写入时机保持旧行为，以避免影响 resume state 形状。当前
  `rg "return result_from_tool_calling_loop\(" app/services/agent/tool_calling_service.py`
  已无命中。
- 已新增 stream API 层验证：`AGENT_RUN_COORDINATOR_ENABLED=true` 时
  `/agent/query/stream` 可通过 coordinator 路径在最终模型结束前产出首个 token，metadata
  保留 `run_coordinator_enabled` 与 `streamed_token_count`。
- coordinator 开关路径已补显式表格/图片请求工具面回归：开启
  `AGENT_RUN_COORDINATOR_ENABLED=true` 时仍会按 `retrieval_required_tool` 使用
  `search_tables` / `search_figures`，并在 legacy event sink 中发布 `runtime-retrieval-1`
  的安全工具结果事件。
- fast-route 升级后的 coordinator final `agent_step` 已修正为使用实际最终工具轮次；
  二次检索后 final event 会报告 `iteration=2`，避免诊断 UI 把升级结果误标成首轮。
- `CoordinatorRequest.event_sink` 的 callable 合同已与实现对齐：除 `RuntimeEventBus.emit()`
  外，直接传入 `Callable[[RuntimeEvent], None]` 也会收到经过安全 payload 白名单过滤的
  `RuntimeEvent`。
- `RunCoordinator` 已补第二道预算防线：即便外部 evidence machine 违规返回 `escalate`，
  当 `max_tool_calls` 或 `max_iterations` 已不足以执行第二轮工具调用时，也不会调用
  `escalate_fast_route()`，而是按 `tool_budget_exhausted` 安全拒答。
- coordinator 开关灰度遇到上传图片时会显式保留 legacy 多模态路径：请求仍由旧
  `analyze_user_image` 分支处理，同时 trace 写入 `run_coordinator_enabled=false` 和
  `run_coordinator_skip_reason=uploaded_image_uses_legacy_multimodal_path`，避免默认开关试运行时
  难以区分“未开启”和“因图片链路暂未迁移而安全 fallback”。
- coordinator 状态 trace 已闭合：开关关闭的旧主循环会写
  `run_coordinator_enabled=false` / `run_coordinator_skip_reason=disabled`；上传图片 fallback
  写图片专用 skip reason；纯文本 coordinator 路径写 `run_coordinator_enabled=true` 并清空
  `run_coordinator_skip_reason`。
- `AGENT_RUN_COORDINATOR_ENABLED` 现在默认 `true`。本轮按 TDD 重新做默认切换红绿验证，
  补齐剩余兼容缺口：reranking/tool execution 错误分类与 fail-closed 文案、required
  figure/table 具体拒因、legacy preflight 诊断别名事件、visual evidence counts、以及
  responsibility/off-topic gate 在 checkpoint 创建前早退。旧主循环专属断言已显式钉到
  `AGENT_RUN_COORDINATOR_ENABLED=false` 回退路径。普通无上传图片 query 默认走
  `RunCoordinator -> ToolExecutor -> EvidenceStateMachine -> ToolCallingFinalAnswerFacade`；
  上传图片仍安全 fallback 到 legacy 多模态路径。
- coordinator service wiring 已补 final request 配置透传：`AGENT_RUN_COORDINATOR_ENABLED=true`
  时默认 `FinalAnswerRequest` 会继承 `ToolCallingAgentService.final_answer_strategy` 与
  `phase64_final_prompt_budgets(settings)`，避免灰度路径把 baseline/structured 策略或 Phase64
  final prompt budget 悄悄退回默认值。
- coordinator final facade 现在使用 `phase64_final_answer_provider(self.chat_model_provider, settings)`，
  与旧 Phase64 短路径一样保留最终回答 provider 包装和 `AGENT_FINAL_MAX_TOKENS` 输出上限语义。
- `ToolCallingCoordinatorGateAdapter` 现在保留显式表格/图片 required-tool preflight 优先级：
  当 planning action 已声明 `required_tool` 时，adapter 只允许责任/离题 gate 先行，跳过
  resume/cache gate，并在 trace 写入 `run_coordinator_pre_tool_gate_skip_reason=required_tool_preflight_priority`
  与 `run_coordinator_required_tool_preflight=<tool>`，避免 coordinator 开关路径用旧 resume/cache
  结果绕过必需资产检索。
- `RunCoordinator` 现在支持 post-preflight gate：当 required tool 已成功执行且取得检索结果后，
  coordinator 会把该工具调用注入 gate adapter 的 workflow/tool-call 列表，再运行
  resume/cache gate。这样显式表格/图片请求不会被 checkpoint/cache 绕过必需资产检索，同时仍恢复
  legacy 主循环“preflight 后复用安全 checkpoint/cache”的行为窗口。
- `RunCoordinator` 的 `tool_execution_completed` checkpoint 现在会累积 completed tool ids：
  fast-route escalation 或其他多工具路径写第二个工具 checkpoint 时，会保留第一个工具 id，
  确保中断恢复/重入 guard 能同时识别已完成的一、二轮工具调用。
- `RunCoordinator` 现在会在 request 带显式 `resume_run_id` 时调用 checkpoint `resume()` 边界复用
  既有 run；service 的 auto resume decision 选中 stopped run 时也会把该 run id 透传到
  `CoordinatorRequest.resume_run_id`。这样中断在工具执行后的恢复补答/完成 checkpoint 会落回同一个
  runtime run，而不是新建 run 后短路。
- `EvidenceStateMachine` 现在识别 `ToolExecutor` 的 completed-tool replay guard：
  当 outcome 标记 `skipped_completed_tool` 或 `error_category=completed_tool` 时，直接按
  `checkpoint_unavailable` / `completed_tool_replay_prevented` fail-closed，`RunCoordinator`
  不会升级或重复检索；final facade 会返回 bounded 用户可见拒答说明。
- `EvidenceStateMachine` 的升级决策现在同时尊重 `max_tool_calls` 与 `max_iterations`；
  当迭代预算不足以执行第二轮工具调用时，状态机本身会拒答而不是请求外层 coordinator
  再兜底。
- `tool_budget_exhausted` 现在作为 runtime stop detail 可正确归一为闭合
  `tool_budget_exhausted`，final facade 会返回 bounded 用户可见拒答说明，避免预算耗尽被
  trace 误标为 `internal_error`。
- 默认 RunCoordinator 全量后端收口已补齐剩余兼容缺口：显式 continue/resume 请求延后到
  resume gate，Phase64 fast-route 证据不足时保留最小来源升级语义，final prompt shape trace
  与 final LLM call counter 已由 `FinalAnswerController.generate()` 记录，Stage37/38 指标
  断言已兼容 policy-owned runtime 的较少模型调用。
- 65C Task 1 已新增候选侧 contract snapshot：`scripts/snapshot_phase65_agent_contract.py`、
  `tests/test_phase65_contract_snapshot.py` 和 `data/evaluation/phase65_contract_snapshot.json`。
  快照只保留 schema/tool/SSE/checkpoint/runtime event 的 hash 或枚举，不保留问题、答案、
  prompt、provider payload、证据文本或密钥。
- 65C Task 2 topology gate 已接入并跑通真实 probe：`scripts/verify_phase65_production_topology.py`
  和 `tests/test_phase65_production_topology.py` 覆盖 required component `skip/fail -> blocked`、
  全 pass、异常不泄露、Postgres/pgvector、Redis、auth、checkpoint 与 Agent SSE。真实 dev
  topology 运行在 Postgres `5433`、Redis `6379` 和受控 API `127.0.0.1:8011`（PID 32856）；
  `output/phase65/topology-8011.json` 显示 `postgres`、`pgvector`、`redis`、`auth`、
  `checkpoint`、`agent_sse` 全部 `pass`，且该文件未跟踪、不应提交。
- 65C Task 3 已从 fault taxonomy 基础推进到 bounded 真实模块注入：`scripts/run_phase65_fault_matrix.py`
  和 `tests/test_phase65_runtime_fault_matrix.py` 现在默认通过真实 `RunCoordinator`、
  `ToolExecutor`、`EvidenceStateMachine`、checkpoint persistence 和 pre-tool gate 的安全本地假依赖
  注入 9 类 fault，并且 `--concurrency/--requests` 会真实调度本地并发注入请求。
  `data/evaluation/phase65_fault_summary.json` 已更新为
  `execution_mode=bounded_module_boundary_injection`、`runtime_injection_coverage=core_runtime_faults`、
  `case_count=80`、`runtime_injected_case_count=80`、`configured_concurrency=8`、
  `configured_requests=80`、`bounded_load_completed_requests=80`、
  `bounded_load_failed_requests=0`、`bounded_load_max_inflight_observed=8`、
  `unique_fault_count=9`、`gate=pass`，且
  `unclassified_errors=0`、`completed_tool_replay_count=0`、`cancelled_work_leak_count=0`。
  本轮故障矩阵还暴露并修复了 planner 异常路径的 `LatencyTrace` 泄漏：`RunCoordinator.run()`
  现在把 `planning_policy.plan()` 纳入同一 `try/finally` 清理区。
- 65C Task 3 已补真实 API/SSE recovery smoke：`scripts/probe_phase65_runtime_recovery.py`
  和 `tests/test_phase65_runtime_recovery_smoke.py` 覆盖真实 authenticated SSE cancel 后 stopped
  run 可恢复，以及 `resume_run_id` / `resume_policy=force` 从 checkpoint 恢复且不重放已完成工具。
  受控 `127.0.0.1:8011` 实测 `output/phase65/runtime-recovery-8011.json` 为 `gate=pass`，
  `sse_cancel_marks_stopped=pass`、`resume_sse_from_checkpoint=pass`、`failed_required=[]`。
  该 JSON 只含 component/status/category/gate，不含 token、run id、答案、证据正文、provider
  payload 或密钥，且未跟踪、不应提交。
- 65C Task 4 已启动 paid paired A/B 执行前门禁：`scripts/phase65_agent_gate.py`
  新增 `build_paired_execution_preflight()`，`scripts/evaluate_phase65_agent_gate.py` 的 paired
  summary 现在会输出 `phase65-paired-preflight-v1` 安全摘要，并默认要求 contract/topology/fault
  gate 状态均为 `pass` 且显式 `--authorize-paid-run` 后，才允许 paired `--execute` 继续。
  本地 dry-run `output/phase65/paired-preflight-dry-run.json` 没有访问 API、没有跑 baseline；
  结果为 `gate=blocked`、`ready_to_execute=false`，阻断项包含 dry-run manifest 非 complete/cold
  与 `paid_execution_not_authorized`。该文件未跟踪、不应提交。
- 65C Task 6 的 final acceptance summary 已提前接入：`scripts/summarize_phase65_acceptance.py`
  与 `tests/test_phase65_acceptance_summary.py` 会把 contract/topology/fault/recovery/paired preflight/
  paired full/holdout/human acceptance 汇总为 `phase65-acceptance-summary-v1`。当前本地
  `output/phase65/acceptance-preflight-summary.json` 按预期为 `gate=blocked`：contract/topology/
  fault/recovery/endpoint readiness/paired execution preflight 为 `pass`，paired full、
  holdout 与 human acceptance 为 `missing`。该汇总没有跑 baseline，且未跟踪、不应提交。
- 65C Task 4 endpoint readiness preflight 已接入：`scripts/evaluate_phase65_agent_gate.py`
  支持 `--preflight-only --auto-auth`，只读取 endpoint contract/identity/cold-run receipt 支持和
  模型库存，不执行 case、不写结果/盲评 rows。当前已闭环：auto-auth 在 loopback endpoint
  公开注册关闭时会 bootstrap 本地短期 admin 评测账号，token 仅在内存中使用；远程 endpoint
  仍 fail-closed。`PHASE65_ENDPOINT_IDENTITY_LABEL` 已接入 endpoint identity hash，candidate
  8011 已以非敏感 lane label 运行；2026-07-15 重启后当前监听 PID 为 10764。最新
  `output/phase65/paired-endpoint-readiness.json` 显示 `endpoint_readiness.gate=pass`，baseline/
  candidate 的 auto-auth、contract fetch、endpoint identity、index fingerprint、cold-run
  receipts、model inventory 和 endpoint identity distinct 均为 `pass`。该文件未跟踪、不应提交。
- 65C Task 4 bounded judged smoke 已完成 endpoint+manifest preflight 验证：`paired-judged-smoke-v3`
  为 2 cases × 2 lanes，4/4 endpoint rows `ok=True`，cold-cache receipt 均为 `valid`，
  paired execution preflight 为 `pass`，contract gate 为 `pass`。本轮没有重跑完整 90-row
  baseline。smoke 暴露并修复：token/cost 缺失不再导致 `paired_rows_incomplete`；blind judge
  fenced JSON 与 nested `deltas` 可解析；judge provider empty content 会记录安全
  `blind_judge_provider_failed` 并 fail-closed 写 summary。当前 smoke 仍不是 full A/B：
  `paired-judged-smoke-v3-summary.json` 中 quality/runtime/Phase65 acceptance 为 blocked，
  judge_error_count=1，paired full、holdout、human acceptance 仍待完成。
- 2026-07-15 candidate targeted correction 已完成：不要重跑 baseline。`phase64-followup-02`
  已通过单 case candidate rerun，安全产物为
  `output/phase65/candidate-followup02-rerun-results.csv`。`candidate-30x1-corrected-results.csv`
  已覆盖为 30/30 `ok=True`，`paired-reuse-baseline-30x1-corrected-results.csv` 合并 baseline
  30/30 + candidate 30/30。`paired-reuse-baseline-30x1-corrected-summary.json` 仍 blocked，
  唯一原因 `evaluator_sha256_mismatch`；这是复用旧 baseline 与 targeted correction 的真实边界，
  不能声称正式 full A/B pass。
- 2026-07-15 acceptance/holdout gate 语义已修正：acceptance summary 现在把已有但 blocked 的
  paired summary 记录为 `paired_full_gate_not_pass`，不再误写成 missing。`evaluate_phase65_agent_gate.py`
  的 `holdout` mode 现在是真 A/B holdout：必须 baseline/candidate 两个 endpoint 且 distinct，
  schedule 写 baseline+candidate 双 lane；未传 `--runs` 时 holdout 默认每 case 1 次 A/B
  observation。当前仍没有 `data/evaluation/phase65_private_holdout_cases.csv`，因此 reviewer holdout
  未执行，不能伪造。
- 2026-07-15 holdout blind judge receipt 已补齐：`holdout --execute --execute-blind-judge`
  现在会对完整 baseline/candidate answer pair 生成 safe judge rows，并把 judge aggregate 写入
  `holdout_summary.judge_summary`。Acceptance summary 对 holdout gate 已收紧：clean rows 和 ≥12
  holdout cases 之外，还需要 matched judge summary；缺 judge 不再能 pass。当前 acceptance summary
  仍 blocked，阻断项是 `paired_full_gate_not_pass`、`holdout_summary_missing`、
  `human_acceptance_missing`。
- retrieval-contract 评测身份权限已在代码层修复：`app/core/security.py` 新增
  `require_authenticated_in_production()`，`app/api/health.py` 的 `/health/retrieval-contract`
  改为 production/auth 下任意 authenticated active user 可读；`/health/details` 仍是
  admin-only。对应测试确认未认证 contract 为 401，普通认证用户 contract 为 200，而
  details 仍为 403。8011 已刷新为当前代码并带 candidate lane label。
- 最新验证：`tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `22 passed`；
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `78 passed`；`tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py`
  为 `40 passed`；post-preflight gate 小集合为 `3 passed`；
  `tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py tests/test_phase65_evidence_state_machine.py tests/test_phase65_runtime_contracts.py`
  为 `90 passed`；`tests/test_agent_stream_api.py tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py`
  为 `88 passed`；PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `133 passed`；
  最新 FinalAnswerController/Coordinator/Service/Stream 组合为 `97 passed`；
  FinalAnswerController/Assembler/Coordinator/Service/Stream 组合为 `106 passed`；
  旧主循环 final-answer 收敛后的 FinalAnswerController/Assembler/Coordinator/Service/Stream 组合为
  `108 passed`；旧主循环剩余直接返回收敛后的上传图片 fallback、显式表格/图片 preflight、
  工具错误收敛、重复/近重复 evidence convergence 与 stream metadata 定向集合为 `7 passed`；
  显式 coordinator/default-disabled stream 小集合为 `4 passed`；coordinator 相关小集合为
  `8 passed`；RunCoordinator HyDE/cache-miss 红绿测试为 `2 passed`；coordinator/service/stream
  HyDE 小集合为 `9 passed`；FinalAnswerController/Assembler/Service/Coordinator/Stream 最新组合为
  `110 passed`；runtime-owned 多工具 sequence 与 required-tool fail-closed 小集合为 `5 passed`；
  RunCoordinator + EvidenceStateMachine 为 `32 passed`；
  FinalAnswerController/Assembler/Service/Coordinator/Evidence/Stream 组合为 `122 passed`；
  PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `143 passed`；Phase65 聚焦集合最近记录为
  `166 passed`；默认 true 落地后 service/stream/coordinator/evidence/tool-executor 中等回归为
  `108 passed`，`tests/test_agent_api.py` 为 `41 passed`，PowerShell 展开后的
  `tests/test_phase65_*.py` 文件合集为 `143 passed`；checkpoint resume run 复用后默认 true
  更宽 agent/API/runtime 回归为 `295 passed`；
  相关 `py_compile` 通过；`git diff --check` 仅有既有 CRLF 警告。
- 后端全量 pytest `1726 passed, 1 skipped`；65C Task 1 contract/stream focused 回归
  `27 passed`；65C Task 2 topology 单测 `11 passed`，真实 topology focused 集合
  `30 passed`（Redis Stack checkpointer 已执行不 skip），Task1+Task2 小回归 `12 passed`；
  65C Task 3 fault matrix 单测最新为 `13 passed`，contract/topology/fault 小回归为
  `25 passed`，runtime 相邻回归为 `52 passed`，PowerShell 展开的 Phase65 文件合集为
  `170 passed`；65C Task 3 recovery smoke 单测为 `5 passed`，contract/topology/fault/recovery
  聚焦回归为 `30 passed`，相关 recovery/fault/topology/contract 脚本 `py_compile` 通过，
  recovery JSON 敏感词扫描无命中；65C Task 4 paired preflight 的
  `tests/test_phase65_agent_gate.py` 为 `22 passed`，
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_agent_gate.py` 为 `46 passed`，
  相关脚本 `py_compile` 通过，paired preflight JSON 敏感词扫描无命中；65C Task 6 acceptance
  summary 单测为 `2 passed`，
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_agent_gate.py tests/test_evaluate_phase65_agent_gate.py`
  为 `48 passed`，相关脚本 `py_compile` 通过，acceptance summary JSON 敏感词扫描无命中；
  endpoint readiness 追加后
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py`
  为 `51 passed`，相关脚本 `py_compile` 通过，paired endpoint readiness 与 acceptance summary
  JSON 敏感词扫描无命中；retrieval-contract 权限修复后
  `tests/test_health_details.py::test_retrieval_contract_allows_authenticated_non_admin_in_production`
  与 `tests/test_health_details.py::test_retrieval_contract_health_is_safe_and_content_free` 为 `2 passed`，
  `tests/test_health_details.py tests/test_stage44_auth.py` 为 `11 passed`，Phase65 聚焦含 health/auth
  集合为 `203 passed`，相关 `py_compile` 通过；
  前端单测 `31 passed`、lint 与 build 通过。

## 2026-07-15 baseline reuse waiver 交接

- 新增 `scripts/build_phase65_baseline_reuse_waiver.py` 与 acceptance summary 的
  `baseline_reuse_waiver` 组件。当前
  `output/phase65/baseline-reuse-waiver-30x1-corrected.json` 为 `gate=pass`，
  baseline/candidate 各 30 个 case-run 完全对齐，`failed_required=[]`。
- 刷新后的 `output/phase65/acceptance-preflight-summary.json` 仍是 `gate=blocked`，但 required
  blockers 只剩 `holdout_summary_missing` 与 `human_acceptance_missing`；paired execution preflight
  与 paired full 仍如实显示 `blocked`，由
  `baseline_reuse_waiver_for_paired_execution_preflight` 和
  `baseline_reuse_waiver_for_paired_full_gate` 显式替代。不要把这写成正式 full A/B pass。
- 本轮新增/相关验证：`tests/test_phase65_acceptance_summary.py` 为 `8 passed`；
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py
  tests/test_phase65_agent_gate.py tests/test_judge_phase65_agent_gate.py
  tests/test_merge_phase65_paired_results.py` 为 `90 passed`；更宽回归
  `tests/test_agent_tools.py tests/test_judge_phase65_agent_gate.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py
  tests/test_merge_phase65_paired_results.py tests/test_evaluate_phase63_e2e.py
  tests/test_phase65_agent_gate.py` 为 `130 passed`；相关 `py_compile` 通过。

## 2026-07-15 reviewer holdout blocked receipt 交接

- 当前没有可用的 `data/evaluation/phase65_private_holdout_cases.csv`，因此 reviewer holdout 不能
  执行，也不能伪造成 pass。新增 `scripts/build_phase65_holdout_blocked_summary.py`，用于在缺私有
  holdout 集时写出安全 blocked receipt。
- 当前 `output/phase65/holdout-blocked-missing-private-cases.json` 为 `gate=blocked`，
  `failed_required=["private_holdout_cases_missing"]`，`holdout_case_count=0`。它不含 prompt、
  answer、evidence 正文、provider raw response 或密钥。
- 刷新后的 `output/phase65/acceptance-preflight-summary.json`：holdout 已从 `missing` 推进为
  `blocked`；当前 required blockers 为 `holdout_gate_not_pass` 与 `human_acceptance_missing`。
  下一步需要提供真实私有 holdout case set 并执行 baseline/candidate A/B + blind judge，随后再记录
  用户人工验收。
- 本轮验证：
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为 `52 passed`；
  `scripts/build_phase65_holdout_blocked_summary.py scripts/summarize_phase65_acceptance.py
  tests/test_phase65_acceptance_summary.py` 的 `py_compile` 通过。

## 2026-07-15 human acceptance pending packet 交接

- 新增 `scripts/build_phase65_human_acceptance_packet.py`，生成
  `phase65-human-acceptance-packet-v1`。该 packet 是用户人工验收入口，不代替用户 pass/fail。
- 当前 `output/phase65/human-acceptance-pending-packet.json` 为 `gate=blocked`，
  `status=pending_user_review`，包含 acceptance summary hash、当前 failed_required、review
  checklist 与下一步动作；不含 prompt、answer、evidence 正文、provider raw response 或密钥。
- 刷新后的 `output/phase65/acceptance-preflight-summary.json` 中 `human_acceptance` 已从
  `missing` 推进为 `blocked`；当前 required blockers 为 `holdout_gate_not_pass` 与
  `human_acceptance_not_pass`。下一步仍需要真实 reviewer holdout pass 和用户明确人工验收记录。
- 本轮验证：
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为 `53 passed`；
  `scripts/build_phase65_human_acceptance_packet.py scripts/build_phase65_holdout_blocked_summary.py
  scripts/build_phase65_baseline_reuse_waiver.py scripts/summarize_phase65_acceptance.py
  tests/test_phase65_acceptance_summary.py` 的 `py_compile` 通过；human/acceptance 两个 JSON 的
  敏感词扫描无命中。

## 2026-07-15 human acceptance recorder 交接

- 新增 `scripts/record_phase65_human_acceptance.py`。它只把用户显式 `--decision pass|fail`
  和 `--confirm-checklist` 转成安全 `phase65-human-acceptance-record-v1`，不会自行判断验收。
- 防误签规则：当 packet 的 failed_required 里还有非 human gate 时，`--decision pass` 会被拒绝。
  当前使用 `output/phase65/human-acceptance-pending-packet.json` 尝试 pass，输出
  `error_category=cannot_pass_with_open_non_human_gates`，且
  `output/phase65/human-acceptance-record-attempt.json` 未创建。
- 本轮验证：
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为 `56 passed`；
  `scripts/record_phase65_human_acceptance.py scripts/build_phase65_human_acceptance_packet.py
  scripts/summarize_phase65_acceptance.py tests/test_phase65_acceptance_summary.py` 的 `py_compile` 通过。

## 2026-07-15 private holdout intake 交接

- 新增 `scripts/prepare_phase65_holdout_intake.py` 与 `tests/test_phase65_holdout_intake.py`。
  它生成 header-only 模板 `output/phase65/phase65_private_holdout_cases.template.csv` 和
  `output/phase65/holdout-intake-packet.json`，用于指导填充真实
  `data/evaluation/phase65_private_holdout_cases.csv`。
- 模板不是可执行 holdout evidence：`template_is_executable=false`，用模板直接校验会输出
  `holdout_requires_twelve_unique_cases`。validator 要求至少 12 个唯一 case 且 `question`
  非空，只输出 case count/hash 等安全元数据。
- 当前 `data/evaluation/phase65_private_holdout_cases.csv` 仍不存在；没有伪造 holdout，没有跑
  baseline/candidate holdout。
- 本轮验证：
  `tests/test_phase65_holdout_intake.py tests/test_phase65_acceptance_summary.py
  tests/test_evaluate_phase65_agent_gate.py` 为 `59 passed`；相关 `py_compile` 通过。

## 2026-07-15 Phase65 closeout audit 交接

- 新增 `scripts/audit_phase65_closeout.py` 与 `tests/test_phase65_closeout_audit.py`，把
  acceptance summary、holdout intake 与 human acceptance packet 汇总为
  `phase65-closeout-audit-v1`。
- 当前 `output/phase65/closeout-audit.json` 为 `gate=blocked`、`ready_for_closeout=false`；
  components 中 acceptance summary、holdout intake、human acceptance packet 均为 `blocked`；
  failed_required 为 `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：
  `tests/test_phase65_closeout_audit.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为 `61 passed`；
  相关 `py_compile` 通过；closeout audit 敏感词扫描无命中。

## 2026-07-15 private holdout overlap guard 交接

- `scripts/prepare_phase65_holdout_intake.py` 的 validator 现在支持 `--exclude-cases`，默认排除
  `data/evaluation/phase64_latency_cases.csv` 中已有 case_id。若 private holdout 与 public/frozen
  case 重叠，会拒绝为 `holdout_overlaps_excluded_cases`。
- `output/phase65/holdout-intake-packet.json` 已显式记录 `public_overlap_guard=true` 与
  `excluded_cases_path=data\\evaluation\\phase64_latency_cases.csv`，便于后续 reviewer/operator
  直接确认隔离门禁。
- 这一步只增强 intake 校验，未创建真实 `data/evaluation/phase65_private_holdout_cases.csv`，未执行
  holdout。`output/phase65/closeout-audit.json` 仍为 `ready_for_closeout=false`。
- 本轮验证：
  `tests/test_phase65_holdout_intake.py` 为 `4 passed`；相关回归
  `tests/test_phase65_holdout_intake.py tests/test_phase65_closeout_audit.py
  tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为 `62 passed`；
  相关 `py_compile` 通过。

## 2026-07-15 evaluator-level holdout overlap guard 交接

- `scripts/evaluate_phase65_agent_gate.py --mode holdout` 现在会把 `--cases` 作为 public/frozen
  排除集传入 `validate_holdout_cases()`；默认值为
  `data/evaluation/phase64_latency_cases.csv`。若 private holdout 与 public/frozen case_id 重叠，
  evaluator 本体会拒绝为 `holdout_overlaps_public_cases`。
- 这一步补的是绕过 intake 直接跑 evaluator 的缺口；没有创建真实
  `data/evaluation/phase65_private_holdout_cases.csv`，没有重跑 baseline，也没有执行真实 holdout。
- 本轮验证：targeted
  `tests/test_evaluate_phase65_agent_gate.py::test_holdout_rejects_overlap_with_public_cases`
  与
  `tests/test_evaluate_phase65_agent_gate.py::test_holdout_cli_rejects_overlap_with_cases_argument`
  为 `2 passed`；相关回归
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_closeout_audit.py tests/test_phase65_acceptance_summary.py` 为 `64 passed`；
  相关 `py_compile` 通过。

## 2026-07-15 holdout overlap proof acceptance 交接

- evaluator 级拒绝重叠之外，`holdout_summary` 现在还会写出
  `public_overlap_exclusion_proven`、`excluded_case_count` 与 `excluded_case_set_sha256`，证明
  本次 holdout 与 public/frozen case set 的隔离检查确实执行过。
- `scripts/summarize_phase65_acceptance.py` 已把这些 proof 字段纳入 `holdout_gate=pass`
  必要条件；旧格式或手写 summary 缺少该 proof 时，即使 clean rows 和 judge summary 满足，也只会
  blocked，不会 pass。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：targeted
  `tests/test_phase65_acceptance_summary.py::test_acceptance_summary_requires_holdout_public_overlap_proof`
  与
  `tests/test_evaluate_phase65_agent_gate.py::test_holdout_execute_blind_judge_writes_safe_judge_receipts`
  为 `2 passed`；相关回归
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_closeout_audit.py tests/test_phase65_acceptance_summary.py` 为 `65 passed`；
  相关 `py_compile` 通过。

## 2026-07-15 holdout real-execution proof acceptance 交接

- `holdout_summary` 现在写出 `execution_mode` 与 `executed_ab_row_count`。
- `scripts/summarize_phase65_acceptance.py` 要求 `execution_mode=real_api` 且
  `executed_ab_row_count >= holdout_case_count * 2`，才允许 `holdout_gate=pass`。dry-run 或缺执行证明
  的旧格式 summary 即使其它字段 clean，也只能 blocked。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：targeted
  `tests/test_phase65_acceptance_summary.py::test_acceptance_summary_requires_holdout_real_execution_proof`
  与
  `tests/test_evaluate_phase65_agent_gate.py::test_holdout_execute_blind_judge_writes_safe_judge_receipts`
  为 `2 passed`；相关回归
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_closeout_audit.py tests/test_phase65_acceptance_summary.py` 为 `66 passed`。

## 2026-07-15 human acceptance hash binding 交接

- `scripts/summarize_phase65_acceptance.py` 现在会从当前非 human 证据计算 canonical pre-human
  acceptance summary hash，并要求 human pass record 的 `acceptance_summary_sha256` 与之匹配。
- 这意味着旧 packet/旧 summary 上签出的 `phase65-human-acceptance-record-v1` 不能复用到新的
  contract/topology/fault/recovery/paired/holdout 证据状态；hash 不匹配时 human gate 仍为 blocked。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：targeted
  `tests/test_phase65_acceptance_summary.py::test_human_acceptance_record_must_match_current_pre_human_summary`
  与
  `tests/test_phase65_acceptance_summary.py::test_human_acceptance_recorder_pass_unblocks_human_gate_when_only_human_is_open`
  为 `2 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `67 passed`。

## 2026-07-15 human acceptance recorder current-summary 校验交接

- `scripts/record_phase65_human_acceptance.py` 现在支持 `--current-acceptance-summary`；`pass`
  决策必须提供当前 acceptance summary，并要求其 hash 与 packet 内
  `acceptance_summary_sha256` 匹配。
- 若 packet 是旧 summary 生成的，或当前 summary 在 packet 生成后发生变化，recorder 会拒绝为
  `human_acceptance_summary_mismatch`，不会写出 pass record。这样 stale 签字会在签字动作本身被挡住，
  不必等最终 summarize 才发现。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：targeted
  `tests/test_phase65_acceptance_summary.py::test_human_acceptance_recorder_rejects_stale_current_summary`、
  `tests/test_phase65_acceptance_summary.py::test_human_acceptance_recorder_cli_rejects_stale_current_summary`
  与
  `tests/test_phase65_acceptance_summary.py::test_human_acceptance_recorder_pass_unblocks_human_gate_when_only_human_is_open`
  为 `3 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `69 passed`。

## 2026-07-15 direct human pass bypass removal 交接

- `scripts/summarize_phase65_acceptance.py` 不再允许 direct `human_acceptance="pass"` 或 CLI
  `--human-acceptance pass` 让 human gate 通过；pass 必须来自带 hash 绑定的
  `phase65-human-acceptance-record-v1`。
- `--human-acceptance fail` 仍保留，用于显式记录人工验收失败；这不会产生 pass。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：`tests/test_phase65_acceptance_summary.py` 为 `19 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `70 passed`。

## 2026-07-15 closeout human record schema guard 交接

- `scripts/audit_phase65_closeout.py` 现在要求 closeout 支撑的人验收 artifact 必须是
  `phase65-human-acceptance-record-v1`，且 nested `human_acceptance_summary` 为
  `gate=pass/status=accepted`。普通 pending packet 或错误格式 `gate=pass` artifact 不能让
  `human_acceptance_packet` component 通过。
- 已刷新 `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：`tests/test_phase65_closeout_audit.py` 为 `3 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `71 passed`。

## 2026-07-15 closeout human receipt hash binding 交接

- `scripts/summarize_phase65_acceptance.py` 在 human gate pass 时写入
  `human_acceptance_summary_sha256`。
- `scripts/audit_phase65_closeout.py` 会重新计算传入
  `phase65-human-acceptance-record-v1` 内 nested `human_acceptance_summary` 的 hash，并与
  acceptance summary 的 `human_acceptance_summary_sha256` 比对。不匹配时
  `human_acceptance_packet` component 为 `blocked`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：`tests/test_phase65_closeout_audit.py` 为 `4 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `72 passed`。

## 2026-07-15 closeout holdout case-set hash binding 交接

- `scripts/summarize_phase65_acceptance.py` 在 holdout gate pass 时写入
  `holdout_case_set_sha256`。
- `scripts/audit_phase65_closeout.py` 要求传入的
  `phase65-holdout-intake-validation-v1` 中 `holdout_case_set_sha256` 与 acceptance summary 匹配；
  不匹配时 `holdout_intake` component 为 `blocked`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：targeted holdout/human hash tests 为 `2 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `73 passed`。

## 2026-07-15 closeout acceptance summary structure guard 交接

- `scripts/audit_phase65_closeout.py` 现在不再只信任 acceptance summary 的顶层 `gate=pass`。
- pass acceptance summary 必须同时具备 `phase65_acceptance=pass`、空 `failed_required`、关键
  components 为 pass；paired 证据必须是 paired full/preflight pass，或带有明确
  baseline reuse waiver substitutions。
- 极简手写 `gate=pass` summary 会让 `acceptance_summary` component 保持 `blocked`，不能让
  `ready_for_closeout=true`。
- 已刷新 `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：`tests/test_phase65_closeout_audit.py` 为 `6 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `74 passed`。

## 2026-07-15 closeout holdout intake case-count guard 交接

- `scripts/audit_phase65_closeout.py` 现在会在 closeout 层再次要求
  `phase65-holdout-intake-validation-v1` 的 `holdout_case_count >= 12`。
- 即使 intake 顶层是 `gate=pass`、`ready_to_run_holdout=true`，并且
  `holdout_case_set_sha256` 与 acceptance summary 匹配，case 数不足仍会让
  `holdout_intake` component 保持 `blocked`。
- 已刷新 `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：红灯测试先确认为 `1 failed`，实现后 `tests/test_phase65_closeout_audit.py` 为
  `7 passed`。

## 2026-07-15 human acceptance recorder-field guard 交接

- `scripts/summarize_phase65_acceptance.py` 现在要求 human gate pass 的
  `phase65-human-acceptance-summary-v1` 除了当前 pre-human acceptance summary hash 匹配外，还必须
  具备 recorder 形态字段：`status=accepted`、`decision=pass`、
  `review_checklist_confirmed=true`、`open_non_human_gate_count=0` 与非空 `reviewer_label`。
- `scripts/audit_phase65_closeout.py` 在 closeout 层也要求 nested human summary 具备同样的 recorder
  字段，并要求其中的 `acceptance_summary_sha256` 是合法 SHA-256。极简手写 accepted record 不能让
  `human_acceptance_packet` component 通过。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：两个红灯测试分别先确认为 `1 failed`；实现后 targeted human tests 为 `3 passed`，
  acceptance + closeout 合并测试为 `28 passed`。

## 2026-07-15 closeout holdout intake public-overlap guard 交接

- `scripts/audit_phase65_closeout.py` 现在会在 closeout 层再次要求
  `phase65-holdout-intake-validation-v1` 的 `excluded_case_overlap_count == 0`。
- 因此即使 intake validation 顶层为 `gate=pass`、`ready_to_run_holdout=true`，并且
  `holdout_case_set_sha256` 与 acceptance summary 匹配，只要 public/frozen overlap 计数非零，
  `holdout_intake` component 仍为 `blocked`。
- 已刷新 `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：红灯测试先确认为 `1 failed`；实现后
  `tests/test_phase65_closeout_audit.py tests/test_phase65_holdout_intake.py` 为 `13 passed`。

## 2026-07-15 holdout summary schema-version guard 交接

- `scripts/evaluate_phase65_agent_gate.py --mode holdout` 现在生成的 `holdout_summary` 带
  `schema_version=phase65-holdout-summary-v1`。
- `scripts/summarize_phase65_acceptance.py` 现在要求 holdout summary schema 为
  `phase65-holdout-summary-v1` 后，才允许 `holdout_gate=pass`。缺 schema 的旧格式/手写 summary
  会被标记为 `blocked`，即使其它字段看起来 clean。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：红灯测试先确认为 `1 failed`；实现后
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为
  `66 passed`。

## 2026-07-15 closeout holdout intake required-columns guard 交接

- `scripts/audit_phase65_closeout.py` 现在会在 closeout 层再次要求
  `phase65-holdout-intake-validation-v1.required_columns` 精确等于
  `scripts.prepare_phase65_holdout_intake.HOLDOUT_TEMPLATE_FIELDS`。
- 因此手写最小 pass intake 即使有 `gate=pass`、`ready_to_run_holdout=true`、case 数、overlap=0
  与匹配的 case-set hash，只要缺少列契约，`holdout_intake` component 仍为 `blocked`。
- 已刷新 `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：红灯测试先确认为 `1 failed`；实现后
  `tests/test_phase65_closeout_audit.py` 为 `10 passed`。

## 2026-07-15 holdout A/B lane completeness guard 交接

- `scripts/evaluate_phase65_agent_gate.py --mode holdout` 现在在 `holdout_summary` 中写入
  `baseline_ab_row_count` 与 `candidate_ab_row_count`。
- `scripts/summarize_phase65_acceptance.py` 现在要求两条 lane 都等于 `holdout_case_count`，并仍要求
  `executed_ab_row_count >= holdout_case_count * 2`。因此只有总行数足够、但缺少 baseline 或
  candidate lane 证明的 holdout summary 不能让 `holdout_gate=pass`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：红灯测试先确认为 `1 failed`；实现后 targeted tests 为 `3 passed`，
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为
  `67 passed`。

## 2026-07-15 holdout A/B lane case-set hash guard 交接

- `scripts/evaluate_phase65_agent_gate.py --mode holdout` 现在在 `holdout_summary` 中写入
  `baseline_ab_case_set_sha256` 与 `candidate_ab_case_set_sha256`。
- `scripts/summarize_phase65_acceptance.py` 现在要求两条 lane 的 case-set hash 都等于
  `holdout_case_set_sha256`。因此 baseline/candidate lane 数量即使都等于 holdout case 数，只要两条
  lane 覆盖的 case set 不一致，也不能让 `holdout_gate=pass`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮验证：红灯测试先确认为 `1 failed`；实现后 targeted tests 为 `3 passed`，
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为
  `68 passed`。

## 2026-07-15 closeout lane case-set hash guard 交接

- acceptance pass summary 现在会携带 holdout 两条 lane 的
  `baseline_ab_case_set_sha256` 与 `candidate_ab_case_set_sha256`。
- `scripts/audit_phase65_closeout.py` 在最终 closeout 的 acceptance summary 自检中二次要求两条 lane
  hash 都等于 `holdout_case_set_sha256`。如果只提供总 holdout hash，或 baseline/candidate 任一 lane
  hash 不一致，`components.acceptance_summary` 会是 `blocked`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮 TDD 验证：新增用例先确认为 `2 failed`；实现后 targeted tests 为 `2 passed`，
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py` 为 `34 passed`。

## 2026-07-15 holdout blind-judge summary schema/receipt guard 交接

- `scripts/judge_phase65_agent_gate.py` 的 `summarize_judge_rows()` 现在生成
  `schema_version=phase65-judge-summary-v1`，并在有 `JudgeReceiptContract` 时写入
  `receipt_contract_sha256`。
- `scripts/summarize_phase65_acceptance.py` 现在要求 holdout `judge_summary` 同时满足：
  `schema_version=phase65-judge-summary-v1`、`paired_count == holdout_case_count`、
  `judge_expected_pairs == holdout_case_count`、`case_set_sha256 == holdout_case_set_sha256`、
  `receipt_contract_sha256` 为合法 SHA-256，以及四个 judge lower bound 均不低于 `-0.05`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮 TDD 验证：新增用例先确认为 `3 failed`；实现后 targeted tests 为 `3 passed`，
  `tests/test_judge_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py
  tests/test_evaluate_phase65_agent_gate.py` 为 `83 passed`。

## 2026-07-15 closeout holdout judge receipt hash guard 交接

- acceptance pass summary 现在会透出 `holdout_judge_receipt_contract_sha256`，来源是 holdout
  `judge_summary.receipt_contract_sha256`。
- `scripts/audit_phase65_closeout.py` 在最终 closeout 的 acceptance summary 自检中要求
  `holdout_judge_receipt_contract_sha256` 为合法 SHA-256。pass-looking acceptance summary 如果只写
  `holdout_gate=pass`、holdout case-set hash 和 lane hash，但没有 blind-judge receipt contract hash，
  `components.acceptance_summary` 会是 `blocked`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮 TDD 验证：新增用例先确认为 `2 failed`；实现后 targeted tests 为 `2 passed`，
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py` 为 `36 passed`。

## 2026-07-15 closeout holdout case-count binding guard 交接

- acceptance pass summary 现在会透出 `holdout_case_count`。
- `scripts/audit_phase65_closeout.py` 在 closeout 的 holdout intake 自检中要求
  `phase65-holdout-intake-validation-v1.holdout_case_count` 与 acceptance summary 中的
  `holdout_case_count` 完全一致。数量不一致时，`components.holdout_intake` 会是 `blocked`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮 TDD 验证：新增用例先确认为 `2 failed`；实现后 targeted tests 为 `2 passed`，
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py` 为 `37 passed`。

## 2026-07-15 closeout holdout real-execution proof guard 交接

- acceptance pass summary 现在会透出 `holdout_execution_mode`、
  `holdout_executed_ab_row_count`、`holdout_baseline_ab_row_count` 与
  `holdout_candidate_ab_row_count`。
- `scripts/audit_phase65_closeout.py` 在 closeout 的 acceptance summary 自检中要求
  `holdout_execution_mode=real_api`，`holdout_executed_ab_row_count >= holdout_case_count * 2`，
  且 baseline/candidate 两条 lane 行数都等于 `holdout_case_count`。缺少这些字段时，
  `components.acceptance_summary` 会是 `blocked`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮 TDD 验证：新增用例先确认为 `2 failed`；实现后 targeted tests 为 `2 passed`，
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py` 为 `38 passed`。

## 2026-07-15 closeout holdout public-overlap proof guard 交接

- acceptance pass summary 现在会透出 `holdout_excluded_case_count` 与
  `holdout_excluded_case_set_sha256`，来源于 holdout summary 的 public/frozen exclusion proof。
- `scripts/audit_phase65_closeout.py` 在 closeout 的 acceptance summary 自检中要求
  `holdout_excluded_case_count > 0` 且 `holdout_excluded_case_set_sha256` 为合法 SHA-256。缺失这些字段时，
  `components.acceptance_summary` 会是 `blocked`。
- 已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 `blocked`，剩余 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- 本轮 TDD 验证：新增用例先确认为 `2 failed`；实现后 targeted tests 为 `2 passed`，
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py` 为 `39 passed`。

## 2026-07-15 private holdout A/B executed but judge blocked 交接

- 已建立真实 holdout case file：`data/evaluation/phase65_private_holdout_cases.csv`，12 条 case，覆盖
  ordinary、relationship、table、figure、boundary/refusal。`output/phase65/holdout-intake-template-validation.json`
  当前为 `gate=pass`、`holdout_case_count=12`、`excluded_case_overlap_count=0`。
- 已按 TDD 修复 evaluator 与 intake 字段不一致：`phase65_private_holdout_cases.csv` 模板字段为
  `question`，底层 `execute_case()` 需要 `query`；`validate_holdout_cases()` 现在会安全映射。新增测试先红后绿。
- 已按 TDD 加固 blind judge：`_safe_judge_blind_pair()` 最多安全重试 3 次，`_bounded_blind_judge_text()`
  对 transient judge 输入做有界裁剪。仍不落盘 prompt、answer、provider raw response、reasoning content 或密钥。
- 已执行真实 holdout A/B，baseline `http://127.0.0.1:8001`、candidate `http://127.0.0.1:8011`。
  第三轮 `output/phase65/holdout-results.csv` 为 24/24 rows `ok=True`，两条 lane cold-cache receipt 均
  `valid`；`output/phase65/holdout-summary.json` 中 `holdout_summary.clean=true`、
  `execution_mode=real_api`、`executed_ab_row_count=24`、两条 lane row count 均为 12。
- 当前 holdout 仍 blocked：blind judge 只形成 5/12 安全 receipt，`judge_error_count=7`，且已有 judge
  lower bounds 为负；`scripts/summarize_phase65_acceptance.py` 刷新后仍为
  `failed_required=["holdout_gate_not_pass","human_acceptance_not_pass"]`。这不是缺 case 或未执行，而是
  “judge evidence 不完整 / candidate 未被证明优于 baseline”。
- 刷新后的 `output/phase65/closeout-audit.json` 仍为 `ready_for_closeout=false`。后续要么继续提升 judge
  provider 稳定性/receipt 覆盖率，要么基于真实 holdout 结果承认 candidate 在该 reviewer set 上未过门槛并回到
  candidate 修复。
- 最新验证：
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_judge_phase65_agent_gate.py -q` 为 `106 passed`。未暂存、未提交、未重跑完整 90-row baseline。

## 恢复顺序

1. 阅读 `AGENT.MD`、本文件、`task_plan.md`、`progress.md`、`findings.md`。
2. 运行 `git status -sb` 和 `git log --oneline -5`。
3. 检查 `PHASE65_AUTH_TOKEN` 是否已由操作方设置（不得输出值）。
4. 启动主工作区代码的受控 8001 服务，安全读取 health/retrieval-contract。
5. 65B 后端 Runtime 模块化与默认 RunCoordinator 接管已具备完整回归证据；不得暂存或提交。
6. 下一步继续 65C：endpoint readiness、bounded judged smoke preflight、candidate 30×1 targeted
   correction、baseline reuse waiver、holdout blocked receipt、human acceptance pending packet、
   human acceptance recorder、private holdout intake、private/public overlap guard 与 closeout audit
   已完成；继续准备真实 reviewer holdout。只有 holdout 通过后，用户才能用 recorder 写入 human
   acceptance pass，并使 closeout audit 进入 `ready_for_closeout=true`。
   不要再重跑完整 90-row baseline，除非用户重新明确要求。当前 8011 受控 API 可继续用于
   65C 验证；如不再需要，可停止 PID 10764。
   pricing snapshot 或 provider
   实际 cost 为后续增强，不阻断当前 cold-run/检索契约 baseline。
7. 后续每完成 paired/holdout/human acceptance 证据后，重新运行
   `scripts/summarize_phase65_acceptance.py` 更新安全 acceptance summary；只有该 summary 以及
   Phase65 summarize gate 都为 pass，才能进入最终人工核验/收尾文档。
