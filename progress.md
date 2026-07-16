# 当前进度

更新时间：2026-07-15

## Phase 65 已完成实现

- 65A 的 manifest、fail-closed quality gate、safe blind-judge receipt、A/B harness、
  runtime cold-cache/usage receipt、模型库存和 Stage30 stale gate 已在主工作区。
- Stage30 仅接受 v3 本地完整性测试收据；无 CI/可信 runner 证明时，任何结果都会
  标为 `local_integrity_only` 并阻断发布，而不会显示当前 PASS。
- 闭合 scope 覆盖实际 `app/`、`scripts/`、`tests/` 文件和 ignore 配置；被忽略的
  未跟踪运行时代码不能逃逸指纹。
- 主工作区 Phase65 迁移已独立复审通过；定向交叉测试 `129 passed`，完整回归
  `1598 passed, 1 skipped`。质量页及 JSON/CSV 导出均 fail-closed，不能以 Stage30
  历史 PASS 绕过当前 stale gate。
- 评测器认证令牌读取以进程环境为优先，并安全回退到本地 `.env` 的同名变量；令牌仅在
  内存中用于 Authorization header，不进入日志、manifest、CSV 或摘要。相关 65A
  focused regression 为 `110 passed`。
- 65B 已完成 contracts、safe event bus、PlanningPolicy、ToolExecutor、
  EvidenceStateMachine、FinalAnswerController、CheckpointSnapshot/Repository 和
  RunCoordinator 生命周期组合的首轮模块化；外部 SSE 形状与既有短路径保持兼容。
- 用户已人工验收 Runtime / Tool-calling 拆解开发内容本身为 PASS：认可从
  `tool_calling_service.py` 大主循环拆出 RunCoordinator、ToolExecutor、
  EvidenceStateMachine、FinalAnswerController、CheckpointRepository、PlanningPolicy、
  RuntimeEventBus 与 final result assembler 的方向与落地质量。该 PASS 只覆盖拆解/模块化范围；
  端到端延迟收益仍是后续性能证明项，Phase65 总 closeout 仍受 holdout/judge 与最终人工验收门禁约束。
- `FinalAnswerController` 现拥有模型最终内容的本地引用校验/单次修复，以及流式回答
  缺引用时的单次安全引用补救；服务层不再直接拼接后缀或进行重复修复。恢复请求中的
  已完成工具 ID 会在 ToolExecutor 边界被拒绝，避免重复检索。
- `ToolExecutor.execute_short_loop()` 已与普通工具执行对齐：透传 iteration、deadline 和
  completed-tool guard，并让快速路径升级的第二次检索使用 `runtime-retrieval-2`。
- `RunCoordinator` 已按 EvidenceStateMachine 的 answer/refuse/escalate 决策编排：拒答
  不会调用最终生成，一次快速路径升级后重新执行检索，异常第二次升级 fail-closed。
- `RunCoordinator` 的工具执行请求已传递 iteration/deadline，并在每次工具执行后写入
  安全 `tool_execution_completed` checkpoint；checkpoint 仅包含工具 id/name、成功标记和
  结果计数等 bounded metadata，不包含答案、chunk 或 provider 原文。
- `CheckpointRepository.completed_tool_ids()` 已提供安全读取边界；`RunCoordinator` 每次工具
  执行前都会读取 checkpoint 中已完成 tool ids 并传给 `ToolExecutor`，让恢复/重入路径避免重复工具调用。
- `CheckpointRepository.complete()` 现在保留已有安全 checkpoint 状态，只追加/覆盖
  `stop_reason`，避免完成态把 completed tool ids、sources 等安全恢复元数据覆盖掉。
- `EvidenceStateMachine` 现在识别 `deadline_exhausted` 工具执行结果并直接 fail-closed
  拒答，不再在 deadline 到期后触发快速路径升级；`RunCoordinator` 已覆盖该集成语义。
- `RunCoordinator` 现在拥有最终生命周期 checkpoint：answer 会写
  `final_answer_completed`，refuse/escalate 会写 `final_answer_refused`，随后再调用
  `complete()`；最终 checkpoint 只包含 action、stop_reason、evidence detail 和 citation 计数等安全元数据。
- `FinalAnswerController` 现提供标准 `FinalAnswerOutcome` 构造；`RunCoordinator` 会把 final
  controller 返回值统一归一为 `FinalAnswerOutcome`，内部不再依赖裸 result / 任意 namespace 形状。
- `RunCoordinator` 现在可默认从 CoordinatorRequest、planning 和 tool outcome 构造标准
  `FinalAnswerRequest`，同时保留可注入 builder 以支持旧 service 分阶段迁移；缺少
  `planning.runtime_state` 时 fail-fast。
- 新增 `final_result_assembler.py`，统一 tool-calling 最终 `AgentQueryResult` 装配、safe trace
  计数和 reasoning summary；`ToolCallingAgentService.result_from_tool_calling_loop()` 现为兼容委托。
- `final_result_assembler.py` 也已接管最终模型失败后的 cited evidence fallback：生成安全引用 fallback、
  标记 `final_generation_failed` trace、更新 runtime stop/final decision 并装配最终结果；service 同名函数仅兼容委托。
- cached-evidence 路径的最终结果装配也已迁入 `final_result_assembler.py`：service 保留证据回答生成，
  生成后委托 assembler 统一设置 `semantic_evidence_cache_hit` / `cached_evidence_without_citations`
  的 stop/final decision、refusal 和 safe trace。
- runtime checkpoint 恢复路径的最终结果装配已迁入 `final_result_assembler.py`：service 保留
  checkpoint 反序列化与恢复后证据回答生成，assembler 统一处理 missing sources、恢复完成、
  citation 缺失拒答和最终 safe trace。
- pre-tool refusal 早退出口也已迁入 `final_result_assembler.py`，responsibility/off-topic gate
  仍在 service 层判定与记录结构化日志，但 `AgentQueryResult`、workflow step 和 trace 由统一边界装配。
- `RunCoordinator` 已新增可注入 `PreToolGateDecision` 入口门禁合同：plan/start checkpoint 后、
  tool execution 前可 fail-closed 返回，跳过工具执行和 evidence evaluation，并写入最终 checkpoint。
  这为后续迁移 responsibility/off-topic/resume 早期路径提供主循环入口，不改变当前 service 默认路径。
- service 的 responsibility/off-topic 早期门禁已抽成 `build_tool_calling_pre_tool_gate_decision()`：
  现有 `ToolCallingAgentService.query()` 仍保留结构化 refusal 日志和外部行为，但门禁判定返回
  `PreToolGateDecision`，可直接接入 `RunCoordinator` 的 pre-tool gate 插槽；并覆盖 resume 时
  不触发 off-topic gate 的现有语义。
- runtime resume 早期路径已抽成 `build_tool_calling_resume_gate_decision()`：无可恢复 run 时
  返回 continue；可恢复 run 时复用 checkpoint 结果装配并返回 `PreToolGateDecision`。service
  仍负责给旧 checkpoint 写 `resume_completed`，以保持现有持久化语义。
- semantic evidence cache 命中路径已抽成 `build_tool_calling_semantic_cache_gate_decision()`：
  未启用、identity 不可复用或未命中时返回 continue；命中时保留 semantic trace、runtime evidence、
  safe tool-result event 和 cached-evidence 最终回答生成，并返回 `PreToolGateDecision`。
- 新增 `build_tool_calling_combined_pre_tool_gate_decision()`，把 pre-tool refusal、runtime resume
  和 semantic evidence cache gate 串成一个按顺序短路的组合 gate。`ToolCallingAgentService.query()`
  已改为分阶段调用该组合 gate：早期只跑 responsibility/off-topic；preflight 后再跑 resume/cache，
  保持 image/preflight 优先级不变。
- 新增 `ToolCallingCoordinatorGateAdapter`，实现 `RunCoordinator` 的
  `pre_tool_gate(request, planning, run)` 调用形状，并复用 service combined gate。当前已验证
  coordinator 能通过该 adapter 在工具执行前返回 service refusal；后续默认 service 纯文本路径
  已切到 RunCoordinator，上传图片仍保留 legacy 多模态路径。
- `ToolCallingCoordinatorGateAdapter` 现在支持注入 resume completion recorder；当 resume gate
  返回 `runtime_resume_completed` 或 `resume_checkpoint_without_sources` 时，会沿用旧 service 语义
  把被恢复的旧 run 写入 `resume_completed` 安全状态，避免 coordinator 开关路径恢复后重复消费旧 run。
- 最初新增灰度开关 `AGENT_RUN_COORDINATOR_ENABLED` 和 `ToolCallingFinalAnswerFacade`。开关打开且无
  上传图片时，`ToolCallingAgentService.query()` 会走 `RunCoordinator -> ToolExecutor ->
  EvidenceStateMachine -> ToolCallingFinalAnswerFacade`，并返回既有 `AgentQueryResult` 形状；
  后续已推进为默认开启，环境变量显式设为 `false` 可回退旧主循环。
- `RunCoordinator` 现在会在生命周期内绑定当前 `LatencyTrace`、retrieval plan 和 Phase64
  route context；触发 fast-route escalation 后，第二次工具执行会刷新为升级后的 retrieval/route
  context，并在退出时 reset，避免模块化主循环丢失旧 service 依赖的上下文变量。
- `RunCoordinator` 的拒答路径现在会在调用 final facade 前把 EvidenceStateMachine 的安全
  `sanitized_detail` / `stop_reason` 写入 `runtime_state`；final facade 不再把所有拒答盲写为
  `insufficient_evidence`。这样保留 `reranking_failed` 等 legacy detail，同时让
  `deadline_exhausted` 归一为闭合 stop reason。
- `ToolCallingFinalAnswerFacade.refuse()` 现在会把白名单拒答 detail 转成 bounded
  user-facing refusal message：deadline、rerank failure、required evidence missing 和
  evidence exhausted 都有可解释但不暴露原始证据/provider 细节的拒答说明。
- `RunCoordinator` 现在会通过 `CoordinatorRequest.event_sink` 向 `RuntimeEventBus` 发布安全
  `agent_step` 生命周期事件；`ToolCallingAgentService` 的 coordinator 开关路径会把
  runtime event bus 传入 request，因此 legacy SSE/event sink 可继续看到 planning/evidence/final
  step，以及 ToolExecutor 已有的 tool start/result 事件。
- `CoordinatorRequest` 已新增 `token_emitter` 合同并透传到默认 `FinalAnswerRequest`；
  `ToolCallingFinalAnswerFacade.generate()` 在 provider 支持 streaming 时会复用
  `FinalAnswerController.stream_evidence()`，并通过 token emitter 补发本地安全引用后缀，
  为 coordinator 路径接管流式最终回答打基础。
- coordinator 开关路径已补显式表格/图片请求的工具面回归：`AGENT_RUN_COORDINATOR_ENABLED=true`
  时仍会按 `retrieval_required_tool` 使用 `search_tables` / `search_figures`，并通过 legacy
  event sink 发布对应 `runtime-retrieval-1` 工具结果事件。
- fast-route 升级后的 coordinator final `agent_step` 现在保留实际最终工具轮次；二次检索后
  final event 会报告 `iteration=2`，避免前端/日志把升级后的最终回答误记为首轮。
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
- `checkpoint_repository.py` 已接管 AgentRuntimeRunRepository、ResumeDecision 与安全状态
  序列化；旧 `runtime_checkpoint.py` 是兼容 re-export，checkpoint/resume 定向回归 `15 passed`。

## 未完成

- 65C 综合验收：真实 A/B、盲评、Postgres/Redis/auth、前端/流式 UI 和故障恢复验证。

## 外部前置条件

- 受控评测认证：`PHASE65_AUTH_TOKEN`（真实 baseline/65C 所需；用户已授权 65B 先行）。
- 原语料库绑定的严格 pgvector 运行环境。
- cold-run 收据和模型库存。manifest-bound pricing snapshot 或逐请求 provider cost receipt
  为后续可选增强，不作为当前执行前置。

## 安全状态

- 未暂存、提交、tag、push、PR 或合并。
- 未持久化密钥、token、原始 provider 响应、答案、证据文本或隐藏推理。

## 2026-07-14 Codex 运行验证补充

- 修复 API/服务早退与最终生成异常路径的 Phase65 cold-cache receipt 缺失。
- 修复 stream API 对服务层非直流式 fallback token 的 trace 计数：metadata 的
  `streamed_token_count/time_to_final_ms` 会反映实际 SSE token。
- 修复 evaluator cold-cache namespace：加入单次 invocation salt，避免不同调试运行在
  相同 manifest/run/case 上互相污染为 `cache_hit`。
- 增加 evaluator 安全增量 rows/summary 写入，并为 Windows 文件锁增加原子 replace
  重试；该能力已测试，但用户已要求 baseline 视为完成，不再重跑完整 90 rows。
- Baseline 口径：旧完整 90 为 `88/90 ok`；两个失败 case 定向复测 `6/6 ok`；
  30×1 为 `30/30 ok`。用户已裁定 baseline 相当于完成，进入下一阶段。
- 当前本地 8001 gate 配置为进程环境：`AGENT_SHORT_LOOP_ENABLED=true`、
  `PHASE64_ROUTE_FIRST_ENABLED=true`、`RETRIEVAL_RUNTIME_ENABLED=true`、
  `RETRIEVAL_RUNTIME_DEFAULT_ENABLED=true`、`AGENT_FINAL_MAX_TOKENS=160`、
  `CHAT_MODEL_TIMEOUT_SECONDS=15`。未写入 `.env`。
- 验证：focused regression `103 passed`；`py_compile` 通过；`git diff --check`
  仅有 CRLF 警告。
- 追加验证：`tests/test_phase65_run_coordinator.py` 为 `4 passed`；
  `tests/test_phase65_run_coordinator.py tests/test_phase65_tool_executor.py tests/test_phase65_checkpoint_repository.py`
  为 `14 passed`；RunCoordinator/evaluator 相关 `py_compile` 通过。
- 追加服务层验证：`tests/test_phase65_tool_executor.py tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py`
  为 `42 passed`。
- 追加恢复防重复验证：`tests/test_phase65_checkpoint_repository.py tests/test_phase65_run_coordinator.py tests/test_phase65_tool_executor.py`
  为 `17 passed`；Phase65 聚焦测试为 `141 passed`；`tests/test_tool_calling_agent_service.py`
  为 `33 passed`；相关 `py_compile` 通过。
- 追加 checkpoint 完成态验证：`tests/test_phase65_checkpoint_repository.py tests/test_phase65_run_coordinator.py`
  为 `13 passed`；Phase65 聚焦测试为 `142 passed`；相关 `py_compile` 通过。
- 追加 deadline fail-closed 验证：`tests/test_phase65_evidence_state_machine.py tests/test_phase65_run_coordinator.py`
  为 `13 passed`；Phase65 聚焦测试为 `144 passed`；`tests/test_tool_calling_agent_service.py`
  为 `33 passed`；相关 `py_compile` 通过。
- 追加最终 checkpoint 生命周期验证：`tests/test_phase65_run_coordinator.py` 为 `7 passed`；
  Phase65 聚焦测试为 `145 passed`；`tests/test_tool_calling_agent_service.py` 为 `33 passed`；
  相关 `py_compile` 通过。
- 追加 final outcome 合同验证：`tests/test_phase65_final_answer_controller.py tests/test_phase65_run_coordinator.py`
  为 `13 passed`；Phase65 聚焦测试为 `146 passed`；`tests/test_tool_calling_agent_service.py`
  为 `33 passed`；相关 `py_compile` 通过。
- 追加 final request 构造验证：`tests/test_phase65_run_coordinator.py` 为 `8 passed`；
  Phase65 聚焦测试为 `147 passed`；`tests/test_tool_calling_agent_service.py` 为 `33 passed`；
  相关 `py_compile` 通过。
- 追加 final result assembler 验证：`tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py`
  为 `34 passed`；Phase65 聚焦测试为 `148 passed`；相关 `py_compile` 通过。
- 追加 final generation failure fallback 迁移验证：
  `tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py`
  为 `35 passed`；Phase65 聚焦测试为 `149 passed`；相关 `py_compile` 通过。
- 追加 cached-evidence result 迁移验证：
  `tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py`
  为 `37 passed`；Phase65 聚焦测试为 `151 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 runtime checkpoint result 迁移验证：
  `tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py`
  为 `39 passed`；Phase65 聚焦测试为 `153 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 pre-tool refusal result 迁移验证：
  `tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py`
  为 `40 passed`；Phase65 聚焦测试为 `154 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 RunCoordinator pre-tool gate 验证：
  `tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `13 passed`；Phase65 聚焦测试为 `155 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 service pre-tool gate 抽取验证：
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `48 passed`；Phase65 聚焦测试为 `155 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 runtime resume gate 抽取验证：
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `50 passed`；Phase65 聚焦测试为 `155 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 semantic cache gate 抽取验证：
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `52 passed`；Phase65 聚焦测试为 `155 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 combined pre-tool gate 验证：
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `54 passed`；Phase65 聚焦测试为 `155 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 coordinator gate adapter 验证：
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `55 passed`；Phase65 聚焦测试为 `155 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 service run-coordinator 开关入口验证：
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `56 passed`；Phase65 聚焦测试为 `155 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 RunCoordinator runtime context 绑定与升级刷新验证：
  `tests/test_phase65_run_coordinator.py` 为 `11 passed`；
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `58 passed`。该验证覆盖工具执行期间绑定 latency trace、retrieval plan、Phase64
  route context，fast-route escalation 后刷新 retrieval/route context，退出后 reset。Phase65
  聚焦集合为 `157 passed`；相关 `py_compile` 通过；`git diff --check` 仅有既有 CRLF 警告。
- 追加 RunCoordinator 拒答 stop-reason 保真验证：
  `tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py` 为 `17 passed`；
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `61 passed`；其中 service facade 单测覆盖已有 `deadline_exhausted` 不被拒答 facade 覆盖。
  Phase65 聚焦集合为 `159 passed`；相关 `py_compile` 通过；`git diff --check`
  仅有既有 CRLF 警告。
- 追加 final facade bounded refusal message 验证：
  `tests/test_tool_calling_agent_service.py::test_final_answer_facade_refusal_preserves_existing_runtime_stop_reason`
  与 `tests/test_tool_calling_agent_service.py::test_final_answer_facade_refusal_uses_bounded_evidence_failure_message`
  为 `2 passed`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `62 passed`；Phase65 聚焦集合为 `159 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 final refusal checkpoint safe-detail 验证：
  `tests/test_phase65_run_coordinator.py` 为 `13 passed`；
  `tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py` 为 `18 passed`；
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `63 passed`；Phase65 聚焦集合为 `160 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 coordinator event sink 兼容验证：
  `tests/test_tool_calling_agent_service.py::test_service_query_can_use_run_coordinator_when_enabled`
  为 `1 passed`，覆盖 `AGENT_RUN_COORDINATOR_ENABLED=true` 时 legacy event sink 收到
  `agent_step`、`tool_call_start`、`tool_call_result` 和 final step；组合回归
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `63 passed`；Phase65 聚焦集合为 `160 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 pre-tool gate 早退 final event 验证：
  `tests/test_phase65_run_coordinator.py::test_coordinator_pre_tool_gate_can_return_before_tool_execution`
  为 `1 passed`，覆盖 gate return 时跳过工具执行但仍发布 plan 与 `final_refuse`
  两个安全 `agent_step`；`tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `18 passed`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `63 passed`；Phase65 聚焦集合为 `160 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 coordinator final streaming contract 验证：
  `tests/test_phase65_runtime_contracts.py::test_runtime_contracts_expose_only_data_fields`
  `tests/test_phase65_run_coordinator.py::test_coordinator_builds_standard_final_answer_request_by_default`
  `tests/test_tool_calling_agent_service.py::test_final_answer_facade_streams_and_emits_safe_citation_suffix`
  为 `3 passed`；`tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `18 passed`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `64 passed`；Phase65 聚焦集合为 `160 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 coordinator stream API 验证：
  `tests/test_agent_stream_api.py::test_run_coordinator_streams_final_answer_before_model_finishes`
  为 `1 passed`，覆盖 `AGENT_RUN_COORDINATOR_ENABLED=true` 时 `/agent/query/stream`
  通过 coordinator 路径在最终模型结束前产出首个 token，metadata trace 保留
  `run_coordinator_enabled` 与 `streamed_token_count`；相邻旧主循环 stream 对照与 coordinator
  stream 测试合计 `2 passed`。组合回归仍为 `64 passed`，Phase65 聚焦集合为 `160 passed`；
  相关 `py_compile` 通过，`git diff --check` 仅有既有 CRLF 警告。
- 追加 coordinator resume completion recorder 验证：
  `tests/test_tool_calling_agent_service.py::test_coordinator_gate_adapter_marks_resumed_run_completed`
  为 `1 passed`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `65 passed`；Phase65 聚焦集合为 `160 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 coordinator 显式工具面与升级事件轮次验证：
  `tests/test_tool_calling_agent_service.py::test_run_coordinator_preflights_explicit_table_request`
  `tests/test_tool_calling_agent_service.py::test_run_coordinator_preflights_explicit_figure_request`
  `tests/test_phase65_run_coordinator.py::test_coordinator_final_event_uses_escalated_iteration`
  为 `3 passed`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `68 passed`；Phase65 聚焦集合为 `161 passed`；相关 `py_compile` 通过；
  `git diff --check` 仅有既有 CRLF 警告。
- 追加 coordinator callable event sink 验证：
  `tests/test_phase65_run_coordinator.py::test_coordinator_event_sink_accepts_runtime_event_callable`
  通过。
- 追加 coordinator 预算防线验证：
  `tests/test_phase65_run_coordinator.py::test_coordinator_refuses_when_escalation_exceeds_tool_budget`
  为 `1 passed`；`tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `21 passed`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `70 passed`；Phase65 聚焦集合为 `163 passed`；相关 `py_compile` 通过。
- 追加 coordinator 上传图片 legacy fallback 诊断验证：
  `tests/test_tool_calling_agent_service.py::test_run_coordinator_enabled_uploaded_image_uses_legacy_multimodal_path`
  为 `1 passed`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `71 passed`；Phase65 聚焦集合为 `163 passed`；相关 `py_compile` 通过。
- 追加 coordinator disabled 状态 trace 验证：
  `tests/test_tool_calling_agent_service.py::test_service_query_marks_run_coordinator_disabled_when_feature_flag_off`
  与上传图片 fallback 诊断测试合计 `2 passed`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `72 passed`；Phase65 聚焦集合为 `163 passed`；相关 `py_compile` 通过。
- 追加 coordinator enabled 状态 trace 验证：
  `tests/test_tool_calling_agent_service.py::test_service_query_can_use_run_coordinator_when_enabled`
  覆盖成功路径 `run_coordinator_skip_reason == ""`。
- 追加 coordinator final strategy 透传验证：
  `tests/test_tool_calling_agent_service.py::test_run_coordinator_uses_service_final_answer_strategy`
  为 `1 passed`，覆盖 service 配置为 `baseline` 时 coordinator 最终 prompt 保持 baseline，
  不退回 `structured_final_answer`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `73 passed`；Phase65 聚焦集合为 `163 passed`；相关 `py_compile` 通过。
- 追加 coordinator Phase64 final provider 包装验证：
  `tests/test_tool_calling_agent_service.py::test_run_coordinator_uses_phase64_final_answer_provider`
  为 `1 passed`，覆盖 coordinator final facade 使用 `phase64_final_answer_provider()` 返回的
  provider，而不是绕过旧短路径的最终回答 cap 包装；
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `74 passed`；Phase65 聚焦集合为 `163 passed`；相关 `py_compile` 通过。
- 追加 coordinator required-tool preflight 优先级验证：
  `tests/test_tool_calling_agent_service.py::test_coordinator_gate_adapter_preserves_required_tool_preflight_priority`
  为 `1 passed`；相邻 gate/preflight 回归 `5 passed`；
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `75 passed`；Phase65 聚焦集合为 `163 passed`；相关 `py_compile` 通过。
- 追加 coordinator post-preflight resume/cache gate 验证：
  `tests/test_tool_calling_agent_service.py::test_coordinator_gate_adapter_preserves_required_tool_preflight_priority`
  `tests/test_tool_calling_agent_service.py::test_coordinator_gate_adapter_allows_post_preflight_resume_after_required_tool`
  `tests/test_phase65_run_coordinator.py::test_coordinator_runs_post_preflight_gate_after_required_tool_success`
  为 `3 passed`；`tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py tests/test_phase65_evidence_state_machine.py tests/test_phase65_runtime_contracts.py`
  为 `89 passed`；`tests/test_agent_stream_api.py tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py`
  为 `88 passed`。该补丁保持显式表格/图片 required-tool preflight 优先级，同时在
  required tool 成功取得结果后恢复旧主循环的 resume/cache 短路窗口，避免 coordinator
  灰度路径与 legacy 路径在 checkpoint/cache 复用时漂移。
- 追加 coordinator 多工具 checkpoint completed-id 累积验证：
  `tests/test_phase65_run_coordinator.py::test_coordinator_accumulates_completed_tool_ids_across_escalation_checkpoints`
  先红后绿，覆盖 fast-route escalation 后第二次 `tool_execution_completed` checkpoint 会保留
  `runtime-retrieval-1` 与 `runtime-retrieval-2`，而不是只保存最后一个 tool id。
  `tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py tests/test_phase65_evidence_state_machine.py tests/test_phase65_runtime_contracts.py`
  为 `90 passed`；PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `133 passed`；
  相关 `py_compile` 通过；`git diff --check` 仅有既有 CRLF 警告。
- 追加 completed-tool replay fail-closed 验证：
  `tests/test_phase65_evidence_state_machine.py::test_completed_tool_replay_fails_closed_without_escalation`
  `tests/test_phase65_run_coordinator.py::test_coordinator_refuses_completed_tool_replay_without_escalation`
  `tests/test_tool_calling_agent_service.py::test_final_answer_facade_refusal_uses_bounded_completed_tool_replay_message`
  为 `3 passed`；相邻 RunCoordinator/Evidence/Facade 小集合为 `28 passed`；
  `tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py` 为 `22 passed`；
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `77 passed`；Phase65 聚焦集合为 `165 passed`；相关 `py_compile` 通过。
- 追加 EvidenceStateMachine 迭代预算升级验证：
  `tests/test_phase65_evidence_state_machine.py` 为 `9 passed`；
  `tests/test_phase65_evidence_state_machine.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `31 passed`；`tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `77 passed`；Phase65 聚焦集合为 `166 passed`；相关 `py_compile` 通过。
- 追加 tool-budget bounded refusal 验证：
  `tests/test_tool_calling_agent_service.py::test_final_answer_facade_refusal_uses_bounded_tool_budget_message`
  与相邻 final facade 拒答测试合计 `4 passed`；
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_runtime_contracts.py`
  为 `78 passed`；Phase65 聚焦集合为 `166 passed`；相关 `py_compile` 通过。
- 追加 FinalAnswerController 标准 generate 合同：
  `FinalAnswerController.generate(FinalAnswerRequest)` 现在直接返回 `FinalAnswerOutcome`，
  负责最终回答生成/流式生成、引用校验/至多一次修复、流式缺引用安全后缀、最终
  `AgentQueryResult` 装配和 runtime final decision/stop reason 写入；`ToolCallingFinalAnswerFacade.generate()`
  已缩减为薄委托。新增/更新测试覆盖非流式 repair 后返回标准 outcome、streaming 时通过
  `token_emitter` 发出完整最终 token 与安全引用后缀，以及 facade 继承该合同。
  验证：`tests/test_phase65_final_answer_controller.py tests/test_tool_calling_agent_service.py::test_final_answer_facade_streams_and_emits_safe_citation_suffix tests/test_agent_stream_api.py`
  为 `22 passed`；`tests/test_phase65_final_answer_controller.py tests/test_phase65_run_coordinator.py tests/test_tool_calling_agent_service.py tests/test_agent_stream_api.py`
  为 `97 passed`；PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `135 passed`；
  相关 `py_compile` 通过；`git diff --check` 仅有既有 CRLF 警告。
- 追加 cached-evidence/checkpoint finalization 入口迁移：
  `FinalAnswerController.from_cached_evidence()` 与 `FinalAnswerController.from_checkpoint()`
  现在返回标准 `FinalAnswerOutcome`，分别接管 semantic evidence cache 命中和 runtime checkpoint
  恢复后的最终回答生成、引用策略和 `AgentQueryResult` 装配。`result_from_cached_evidence()` 与
  `result_from_runtime_checkpoint()` 保留兼容函数名，但内部已改为薄委托。验证：
  `tests/test_phase65_final_answer_controller.py tests/test_phase65_final_result_assembler.py`
  及相邻 service resume/cache tests 为 `19 passed`；
  `tests/test_phase65_final_answer_controller.py tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_agent_stream_api.py`
  为 `106 passed`；PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `137 passed`；
  相关 `py_compile` 通过；`git diff --check` 仅有既有 CRLF 警告。
- 追加旧主循环 final-answer 底层调用收敛：
  新增 `FinalAnswerController.stream_final_evidence()`、`generate_final_evidence()` 与
  `validate_model_content()` 命名入口。旧 `ToolCallingAgentService.query()` 主循环中的
  streaming final answer、evidence-convergence final answer、已有 model draft validate/repair
  已改为调用这些 controller 入口；`tool_calling_service.py` 不再直接调用底层
  `.generate_evidence()` / `.stream_evidence()` / `.validate_or_repair()`。旧主循环 SSE
  继续由 API 层负责完整 token 输出，controller 在旧路径只补发缺引用安全后缀，避免双写 token。
  验证：失败回归
  `tests/test_tool_calling_agent_service.py::test_tool_calling_agent_streams_safe_citation_suffix_for_uncited_answer`
  与 `tests/test_agent_stream_api.py::test_agent_stream_api_defaults_to_tool_calling_metadata_done`
  已修复并通过；`tests/test_phase65_final_answer_controller.py tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_agent_stream_api.py`
  为 `108 passed`；PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `139 passed`；
  相关 `py_compile` 通过；`git diff --check` 仅有既有 CRLF 警告。
- 追加旧主循环标准 `FinalAnswerOutcome` 出口：
  新增 `outcome_from_tool_calling_loop()` 兼容 helper；旧主循环中的 evidence-convergence
  成功、model-final-answer 成功、final-content-without-citations 拒答和 iteration-limit 拒答分支
  现在先构造标准 `FinalAnswerOutcome`，再返回 `.result`。这保留现有 checkpoint 写入时机
  和用户可见响应形状，同时让最终 answer/refuse 分支逐步向统一 outcome 合同收敛。
  验证：关键 service 分支用例 `3 passed`；
  `tests/test_phase65_final_answer_controller.py tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_agent_stream_api.py`
  为 `108 passed`；PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `139 passed`；
  相关 `py_compile` 通过；`git diff --check` 仅有既有 CRLF 警告。
- 追加旧主循环剩余直接返回收敛：
  `tool_calling_service.py` 中剩余的上传图片 legacy fallback、required-tool/preflight 无结果、
  短循环证据不足、模型工具循环 reranking_failed、required figure evidence missing 等 5 个
  `return result_from_tool_calling_loop(...)` 分支已改为经
  `outcome_from_tool_calling_loop(...).result` 返回。当前旧主循环共有 9 个兼容 outcome 出口，
  `rg "return result_from_tool_calling_loop\(" app/services/agent/tool_calling_service.py`
  已无命中。验证：上传图片 fallback、显式表格/图片 preflight、工具错误收敛、重复/近重复
  evidence convergence 与 stream metadata 定向集合为 `7 passed`；
  `tests/test_phase65_final_answer_controller.py tests/test_phase65_final_result_assembler.py tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_agent_stream_api.py`
  为 `108 passed`；PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `139 passed`；
  `py_compile` 通过。
- 追加 RunCoordinator 默认开启预检与 SSE 修复：
  按 TDD 尝试把 `AGENT_RUN_COORDINATOR_ENABLED` 从默认关闭推进为默认开启时，新增默认开启测试
  先按预期红灯；改默认值后，基础 coordinator/stream 小集合暴露 SSE token 双写问题，已通过
  `QueueStreamingChatModelProvider.stream_generate_emits_tokens` 标记和 coordinator token_emitter
  选择修复，显式 coordinator stream 测试新增 `metadata["answer"] == streamed_answer` 回归断言。
  当时完整组合回归随后暴露默认开启仍未就绪：coordinator 会绕过 legacy HyDE cache-miss 生成，
  并改变部分旧模型 tool-loop 语义（例如旧 llm_call_count、多工具迭代、legacy preflight
  step_id 和若干拒答文案）。因此当轮曾撤回默认值，只保留显式开关路径；后续任务转为补齐
  RunCoordinator 的 HyDE/cache-miss 与必要 legacy/tool-loop 兼容语义。验证：显式 coordinator/default-disabled
  stream 小集合 `4 passed`，coordinator 相关小集合 `8 passed`，FinalAnswerController/Assembler/
  Service/Coordinator/Stream 组合回归恢复为 `108 passed`，PowerShell 展开后的
  `tests/test_phase65_*.py` 文件合集为 `139 passed`，相关 `py_compile` 通过。
- 追加 RunCoordinator HyDE cache-miss 接管：
  按 TDD 新增 RunCoordinator 单元红灯，证明工具执行期间需要绑定
  `current_hyde_vector_query()`；新增 service 红灯，证明显式
  `AGENT_RUN_COORDINATOR_ENABLED=true` 路径在 semantic evidence cache miss 时应像 legacy
  一样生成 HyDE。实现上给 `RunCoordinator` 增加可注入 `hyde_query_builder`，仅在普通检索
  工具执行前绑定 HyDE；显式 required table/figure preflight 不提前生成 HyDE，避免偏离 legacy
  preflight 语义。service 的 builder 复用现有 identity `hyde_passage` 或
  `generate_hyde_vector_query()`，并保持 `hyde_generated` / `hyde_used_for_vector` /
  `hyde_reason` / `hyde_model` trace。验证：两个红灯测试转绿为 `2 passed`；coordinator/service/
  stream 小集合为 `9 passed`；FinalAnswerController/Assembler/Service/Coordinator/Stream 组合为
  `110 passed`；PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `140 passed`；
  相关 `py_compile` 通过。后续 runtime-owned 多工具序列已补齐，并已重新推进到默认开启。
- 追加 RunCoordinator runtime-owned 多工具序列：
  按 TDD 新增 RunCoordinator 红灯，要求 planning action 声明
  `tool_sequence=("search_tables", "hybrid_search_knowledge")` 时，coordinator 在预算内按顺序执行
  多个工具，并把多个 tool calls、search_results 和 sources 合并进标准 `FinalAnswerRequest`。
  实现上 `RunCoordinator` 读取 `planning.action.tool_sequence`，按 `max_tool_calls/max_iterations`
  截断执行并合并 outcomes；`build_final_answer_request()` 可读取合并后的 tool calls/workflow steps。
  同时新增 required-tool 安全红灯：当 required figure/table 没有结果但 hybrid 有文本来源时，
  `EvidenceStateMachine` 必须按 `required_evidence_missing` fail-closed，避免必需资产缺失被文本证据
  误放行。`RetrievalAction` 现在对显式 table/figure 产出 runtime-owned sequence：
  `search_tables/search_figures -> hybrid_search_knowledge`，先取必需资产，再取文本支撑。验证：
  多工具/required-tool 小集合 `5 passed`；RunCoordinator + EvidenceStateMachine 为 `32 passed`；
  FinalAnswerController/Assembler/Service/Coordinator/Evidence/Stream 组合为 `122 passed`；
  PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集为 `143 passed`；相关 `py_compile` 通过。
- 追加 RunCoordinator 默认开启落地：
  按 TDD 复跑默认开启红绿验证后，补齐剩余真实兼容缺口：`ToolExecutor` 现在会把 reranker
  失败归类为 `reranking_failed`，普通工具执行失败按 `tool_execution_failed` fail-closed；
  final facade 会保留安全 reranking 错误和 required figure/table 的具体无结果拒因；显式
  table/figure preflight 在保留 `runtime-retrieval-N` checkpoint id 的同时补发 legacy
  `runtime-search_tables` / `runtime-search_figures` 诊断别名事件；RunCoordinator 会记录
  `runtime_state.evidence`，因此 visual follow-up 的 `runtime_evidence_counts.figure` 不再丢失；
  service coordinator 入口已把 responsibility/off-topic gate 前移到 checkpoint 创建之前，避免
  早期拒答依赖 DB 副作用。旧主循环专属断言（旧 `llm_call_count=2`、模型自由多 tool-call
  迭代、旧 direct-query 流式 suffix 行为）已显式钉到 `AGENT_RUN_COORDINATOR_ENABLED=false`
  回退路径。`app/core/config.py` 现将 `agent_run_coordinator_enabled` 默认设为 `true`，上传图片
  仍安全 fallback 到 legacy 多模态路径，环境变量仍可显式设为 `false` 回退。验证：
  默认环境 service/stream/coordinator/evidence/tool-executor 中等回归
  `tests/test_tool_calling_agent_service.py tests/test_agent_stream_api.py tests/test_phase65_run_coordinator.py tests/test_phase65_evidence_state_machine.py tests/test_phase65_tool_executor.py`
  为 `108 passed`；`tests/test_agent_api.py` 为 `41 passed`；PowerShell 展开后的
  `tests/test_phase65_*.py` 文件合集为 `143 passed`；
  `py_compile app/core/config.py app/services/agent/tool_calling_service.py app/services/agent/run_coordinator.py app/services/agent/tool_executor.py app/services/agent/evidence_state_machine.py`
  通过；`git diff --check` 对相关文件仅有 CRLF 提示。
- 追加 checkpoint resume run 复用：
  按 TDD 新增 RunCoordinator 红灯，要求 request 带显式 `resume_run_id` 时调用 checkpoint
  `resume()` 边界而不是 `start()` 新建 run；实现 `_start_or_resume_checkpoint()` 与
  `CheckpointRepository.resume()`。随后新增 service 红灯，要求 auto resume decision 选中
  stopped run 时，把该 run 的 `run_id` 写入 `CoordinatorRequest.resume_run_id`，使 coordinator
  在恢复补答/完成 checkpoint 时复用同一个 runtime run。验证：
  `tests/test_tool_calling_agent_service.py tests/test_phase65_run_coordinator.py tests/test_phase65_checkpoint_repository.py`
  为 `90 passed`；默认 true 的更宽 agent/API/runtime 回归
  `tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_tool_calling_agent_service.py tests/test_agent_tools.py tests/test_frontend_app.py tests/test_health_details.py tests/test_phase65_*.py`
  为 `295 passed`。
- 追加默认 RunCoordinator 全量后端收口：
  修复默认开启后剩余兼容缺口：显式 continue/resume 请求延后到 resume gate，Phase64 fast-route
  在证据不足时保留最小来源升级语义，`FinalAnswerController.generate()` 记录 final prompt shape
  trace 与 final LLM call counter，Stage37/38 历史指标断言改为兼容 policy-owned runtime 的
  较少模型调用。定向失败集合复测
  `tests/test_phase58h_runtime_checkpoint_cache.py::test_phase58h_tool_calling_service_resumes_from_checkpoint_sources`
  `tests/test_phase63_unified_agent_contract.py::test_phase63_flag_keeps_model_owned_tool_selection_loop`
  `tests/test_phase64_short_loop.py::test_short_loop_skips_generate_with_tools_and_streams_final_answer`
  `tests/test_phase64_short_loop.py::test_fast_path_escalates_once_before_generation_when_evidence_is_insufficient`
  `tests/test_phase64_short_loop.py::test_phase64_b_trace_records_final_prompt_shape`
  `tests/test_stage37_tool_calling_eval.py::test_stage37_eval_tracks_required_comparison_metrics`
  `tests/test_stage38_tool_calling_eval.py::test_stage38_eval_tracks_tool_calling_edge_metrics`
  为 `7 passed`；完整后端回归 `python -m pytest -q` 为 `1726 passed, 1 skipped`。
  相关 agent runtime 文件 `py_compile` 通过；`git diff --check` 仅有 CRLF 提示。65B 后端
  Runtime 模块化与默认 coordinator 接管已具备进入 65C 的回归证据。
- 65C Task 1 contract snapshot 启动并完成候选侧本地快照：
  按 TDD 新增 `tests/test_phase65_contract_snapshot.py`，先观察缺
  `scripts.snapshot_phase65_agent_contract` 的红灯；随后新增
  `scripts/snapshot_phase65_agent_contract.py`，只输出 request/response schema、工具 schema、
  SSE fixture、checkpoint schema 和 runtime event names 的 canonical hashes/枚举，不保存问题、
  答案、prompt、provider payload、证据文本或密钥。生成
  `data/evaluation/phase65_contract_snapshot.json`。验证：红灯转绿为 `1 passed`；
  `python -m py_compile scripts/snapshot_phase65_agent_contract.py` 通过；
  `python scripts/snapshot_phase65_agent_contract.py --out data/evaluation/phase65_contract_snapshot.json`
  生成安全快照；contract/stream focused 回归
  `tests/test_phase65_contract_snapshot.py tests/test_phase63_unified_agent_contract.py tests/test_agent_stream_api.py tests/test_stage40_streaming_output_safety.py`
  为 `27 passed`；快照敏感词扫描无命中；`git diff --check` 仅有 CRLF 提示。
- 65C Task 2 topology gate summary 启动：
  按 TDD 新增 `tests/test_phase65_production_topology.py`，先观察缺
  `scripts.verify_phase65_production_topology` 的红灯；随后新增
  `scripts/verify_phase65_production_topology.py`，实现 required topology components
  (`postgres`, `pgvector`, `redis`, `auth`, `checkpoint`, `agent_sse`) 的闭合 summary：
  任一 required component 为 `skip/fail` 时 gate 为 `blocked`，全部 `pass` 才 `pass`。
  验证：红灯转绿为 `3 passed`；contract snapshot + topology summary 小回归为 `4 passed`；
  两个脚本 `py_compile` 通过。真实 PostgreSQL/pgvector/Redis/auth/checkpoint/SSE 探针仍待接入，
  当前 CLI 默认输出 all-skip blocked summary，不能视为 topology gate pass。
- 65C Task 2 真实 topology probe 完成：
  继续按 TDD 为 `run_topology_probes()`、`probe_postgres()`、`probe_pgvector()`、
  `probe_redis()`、`probe_auth()`、`probe_agent_sse()`、`probe_checkpoint()` 和
  `build_probe_summary()` 增加可注入单元测试，覆盖异常不泄露、Postgres URL 强制、pgvector
  extension、Redis factory 状态、auth token 仅内存传递、SSE `done` 事件和 checkpoint
  合成 run roundtrip。真实环境侧：`docker compose -f docker-compose.dev.yml up -d db redis`
  后 `db`/`redis` 均 healthy；以 dev Postgres URL 执行 `python -m alembic upgrade head`
  退出 0；启动受控 API `127.0.0.1:8011`（PID 32856），显式绑定 dev Postgres、Redis、
  auth=true、deterministic chat provider、coordinator=true、reranking=false。运行
  `python scripts/verify_phase65_production_topology.py --base-url http://127.0.0.1:8011 ... --out output/phase65/topology-8011.json`
  返回 `gate=pass skipped_required=[] failed_required=[]`，JSON 中 `postgres`、`pgvector`、
  `redis`、`auth`、`checkpoint`、`agent_sse` 全部 `pass`。计划要求的 focused topology
  集合在设置 `PHASE50_REDIS_STACK_URL` 后为 `30 passed`，Redis Stack checkpointer 单测单独
  为 `1 passed` 且没有 skip。`tests/test_phase65_production_topology.py` 为 `11 passed`；
  contract snapshot + topology 小回归为 `12 passed`；相关脚本 `py_compile` 通过；`git diff --check`
  仅有 CRLF 提示。安全扫描命中仅为测试/脚本中的 forbidden-term/header 字段名，不是实际 token、
  密钥或 provider payload；`output/phase65/topology-8011.json` 无敏感命中且未跟踪。
- 65C Task 3 fault matrix 启动：
  按 TDD 新增 `tests/test_phase65_runtime_fault_matrix.py`，先观察缺
  `scripts.run_phase65_fault_matrix` 的红灯；随后新增 `scripts/run_phase65_fault_matrix.py`，
  建立闭合 fault taxonomy 和安全 summary 合同。当前覆盖计划中的 8 类 fault：
  planner invalid/timeout、optional channel timeout、required evidence missing、rerank failure、
  checkpoint write failure、deadline 和 cancel；summary 统计 `unclassified_errors`、
  `completed_tool_replay_count`、`cancelled_work_leak_count`，并在任一非零时 blocked。
  执行 `python scripts/run_phase65_fault_matrix.py --concurrency 8 --requests 80 --out data/evaluation/phase65_fault_summary.json`
  返回 `gate=pass unclassified_errors=0 completed_tool_replay_count=0 cancelled_work_leak_count=0`；
  JSON 已明确标注 `execution_mode=deterministic_taxonomy` 与
  `runtime_injection_coverage=pending`，因此不能替代后续真实 RunCoordinator/ToolExecutor/
  Checkpoint 注入、取消/恢复和 bounded load 矩阵。验证：fault matrix 单测 `10 passed`；
  topology + fault 小回归 `21 passed`；脚本 `py_compile` 通过；fault/topology JSON 敏感词扫描无命中。
- 65C Task 3 fault matrix 真实模块注入推进：
  按 TDD 新增 runtime injection 默认集合回归，先观察缺
  `run_runtime_injection_fault_matrix()` 的红灯；随后让 runner 默认构造真实
  `RunCoordinator`、`ToolExecutor`、`EvidenceStateMachine`、checkpoint persistence 和
  pre-tool gate 的本地假依赖场景，覆盖 planner invalid、planner timeout、optional channel
  timeout、required evidence missing、rerank failure、checkpoint write failure、deadline、
  cancel 和 completed-tool replay 共 9 类 fault。`data/evaluation/phase65_fault_summary.json`
  已更新为 `execution_mode=module_boundary_injection`、
  `runtime_injection_coverage=core_runtime_faults`、`runtime_injected_case_count=9`、
  `gate=pass`，且 `unclassified_errors=0`、`completed_tool_replay_count=0`、
  `cancelled_work_leak_count=0`。故障矩阵暴露并修复了 `RunCoordinator.run()` 中
  `planning_policy.plan()` 抛异常早于 `try/finally` 导致 `LatencyTrace` 上下文泄漏的问题；
  新增 `test_coordinator_resets_latency_trace_when_planning_raises` 固定该回归。验证：
  单个红灯转绿 `1 passed`；fault matrix 单测 `12 passed`；contract/topology/fault 小回归
  `24 passed`；runtime 相邻回归
  `tests/test_phase65_runtime_fault_matrix.py tests/test_phase65_run_coordinator.py tests/test_phase65_tool_executor.py tests/test_phase65_evidence_state_machine.py`
  为 `51 passed`；PowerShell 展开的 Phase65 文件合集为 `169 passed`；相关 `py_compile` 通过；
  `git diff --check` 对本轮触及文件通过；fault summary JSON 敏感词扫描无命中。
- 65C Task 3 bounded-load 注入推进：
  按 TDD 新增 `run_bounded_runtime_fault_matrix(concurrency, requests)` 的红灯测试，
  要求 `--concurrency/--requests` 真实执行对应数量的 module-boundary injection，而不是只写
  summary 配置字段。实现后 runner 使用 `ThreadPoolExecutor` 按配置上限调度本地注入请求，
  记录 `bounded_load_completed_requests`、`bounded_load_failed_requests`、
  `bounded_load_max_inflight_observed` 和 `unique_fault_count`，并保持 summary 只含 fault labels、
  stop reasons、runtime boundary、计数和 gate，不保存 prompt、答案、证据正文、provider payload
  或密钥。执行
  `python scripts/run_phase65_fault_matrix.py --concurrency 8 --requests 80 --out data/evaluation/phase65_fault_summary.json`
  后，JSON 为 `execution_mode=bounded_module_boundary_injection`、`case_count=80`、
  `runtime_injected_case_count=80`、`configured_concurrency=8`、`configured_requests=80`、
  `bounded_load_completed_requests=80`、`bounded_load_failed_requests=0`、
  `bounded_load_max_inflight_observed=8`、`unique_fault_count=9`、`gate=pass`，
  且 `unclassified_errors=0`、`completed_tool_replay_count=0`、
  `cancelled_work_leak_count=0`。验证：新增 bounded-load 红灯转绿为 `1 passed`；
  fault matrix 单测 `13 passed`；runtime 相邻回归 `52 passed`；
  contract/topology/fault 小回归 `25 passed`；PowerShell 展开的 Phase65 文件合集 `170 passed`；
  相关 `py_compile` 通过；fault summary JSON 敏感词扫描无命中；`git diff --check`
  对本轮触及文件通过（仅工作记忆 LF→CRLF 提示）。
- 65C Task 3 真实 API/SSE recovery smoke 推进：
  按 TDD 新增 `tests/test_phase65_runtime_recovery_smoke.py`，先观察缺
  `scripts.probe_phase65_runtime_recovery` 的红灯；随后新增
  `scripts/probe_phase65_runtime_recovery.py`，通过真实 authenticated SSE 链路验证两个必需
  runtime recovery 行为：客户端在首个 SSE 事件后关闭连接时，服务端会留下可恢复的 stopped
  run；对合成 stopped checkpoint 以 `resume_run_id`/`resume_policy=force` 继续 SSE 时，必须从
  checkpoint 恢复并且不重放已完成工具调用。summary 只保留 component/status/category/gate，
  不保存 token、run id、prompt、答案、证据正文、provider payload 或密钥。受控
  `127.0.0.1:8011` 实测生成 `output/phase65/runtime-recovery-8011.json`，结果为
  `gate=pass`、`sse_cancel_marks_stopped=pass`、`resume_sse_from_checkpoint=pass`、
  `failed_required=[]`。验证：recovery smoke 单测 `5 passed`；contract/topology/fault/recovery
  聚焦回归 `30 passed`；相关脚本 `py_compile` 通过；recovery JSON 敏感词扫描无命中。
- 65C Task 4 paired A/B 执行前门禁启动：
  按 TDD 新增 `tests/test_phase65_agent_gate.py` 断言，先观察缺
  `build_paired_execution_preflight()` 的红灯；随后在 `scripts/phase65_agent_gate.py`
  增加 safe preflight summary，复用 manifest comparison，并叠加 contract/topology/fault
  gate 与 paid-run 授权门禁。之后新增 evaluator dry-run summary 测试，先观察
  `paired_execution_preflight` 缺失红灯，再在 `scripts/evaluate_phase65_agent_gate.py`
  中接入 summary，并新增 `--contract-gate-status`、`--topology-gate-status`、
  `--fault-gate-status` 与 `--authorize-paid-run` 参数；paired `--execute` 时若 preflight
  非 `pass` 会 fail-closed。执行
  `python scripts/evaluate_phase65_agent_gate.py --mode paired --baseline-base-url http://127.0.0.1:8001 --candidate-base-url http://127.0.0.1:8011 --runs 1 --limit 2 --contract-gate-status pass --topology-gate-status pass --fault-gate-status pass --summary-out output/phase65/paired-preflight-dry-run.json`
  为 dry-run，本轮没有访问 API、没有跑 baseline；summary 为 `gate=blocked`、
  `ready_to_execute=false`，阻断原因为 dry-run manifest 不是 complete/cold 且
  `paid_execution_not_authorized`。验证：`tests/test_phase65_agent_gate.py` 为 `22 passed`；
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_agent_gate.py` 为 `46 passed`；
  相关脚本 `py_compile` 通过；paired preflight JSON 敏感词扫描无命中。
- 65C Task 6 final acceptance summary 提前接入：
  按 TDD 新增 `tests/test_phase65_acceptance_summary.py`，先观察缺
  `scripts.summarize_phase65_acceptance` 的红灯；随后新增
  `scripts/summarize_phase65_acceptance.py`，只读取 contract/topology/fault/recovery/paired
  preflight/paired full/holdout/human acceptance 的安全 gate/status 字段，生成
  `phase65-acceptance-summary-v1`。该汇总 fail-closed：任一 required gate 非 `pass`、paired
  full summary 缺失、holdout summary 缺失或未记录人工验收，都会输出 `gate=blocked`。
  测试还固定了 summary 中不能出现 prompt/answer 等敏感字段名；实现过程中安全扫描发现说明文本中
  的敏感词命中，已改为安全表述。执行
  `python scripts/summarize_phase65_acceptance.py --contract-snapshot data/evaluation/phase65_contract_snapshot.json --topology-summary output/phase65/topology-8011.json --fault-summary data/evaluation/phase65_fault_summary.json --recovery-summary output/phase65/runtime-recovery-8011.json --paired-preflight-summary output/phase65/paired-preflight-dry-run.json --out output/phase65/acceptance-preflight-summary.json`
  当前按预期返回 blocked：contract/topology/fault/recovery 为 `pass`，paired preflight 为
  `blocked`，paired full/holdout/human acceptance 为 `missing`。本轮没有访问 API、没有跑 baseline。
  验证：acceptance summary 单测 `2 passed`；
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_agent_gate.py tests/test_evaluate_phase65_agent_gate.py`
  为 `48 passed`；相关脚本 `py_compile` 通过；acceptance summary JSON 敏感词扫描无命中。
- 65C Task 4 endpoint readiness preflight 推进：
  按 TDD 新增 paired `--preflight-only` 测试，先观察缺 CLI 参数的红灯；随后在
  `scripts/evaluate_phase65_agent_gate.py` 增加 `--preflight-only`，只 fetch endpoint contract、
  endpoint identity、index fingerprint、cold-run receipt 支持和模型库存，不执行任何 case、
  不写 results/judge rows。继续新增 `--auto-auth` 测试，先观察缺 `_auto_auth_token()` 的红灯；
  实现后复用 topology probe 的临时 register/login/me 流程为每个 endpoint 获取内存 token。
  真实运行发现 8001 临时 auth 注册失败、8011 临时 auth 成功但 retrieval-contract 返回 403，
  因此再按 TDD 让 preflight-only 对 auto-auth/contract fetch 失败写出 blocked readiness summary，
  而不是直接异常退出。执行
  `python scripts/evaluate_phase65_agent_gate.py --mode paired --preflight-only --auto-auth --baseline-base-url http://127.0.0.1:8001 --candidate-base-url http://127.0.0.1:8011 --runs 1 --limit 2 --contract-gate-status pass --topology-gate-status pass --fault-gate-status pass --summary-out output/phase65/paired-endpoint-readiness.json`
  没有执行 case、没有跑 baseline；当前 `endpoint_readiness.gate=blocked`，阻断项包括
  `baseline_auto_auth_not_ready`、`candidate_contract_fetch_not_ready` 和 endpoint identity/cold
  receipt/model inventory 未就绪。acceptance summary 已新增 `--endpoint-readiness-summary`
  并接入该结果；当前仍 fail-closed blocked。验证：
  preflight-only 目标测试 `3 passed`；
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py`
  为 `51 passed`；相关脚本 `py_compile` 通过；paired endpoint readiness 与 acceptance summary
  JSON 敏感词扫描无命中。
- 65C Task 4 retrieval-contract 评测身份权限修复：
  用 systematic debugging 定位到 endpoint readiness 的真实阻断：`/health/retrieval-contract`
  在 production/auth 开启时依赖 `require_admin_in_production`，而 auto-auth 创建的是普通临时用户，
  因此 8011 返回 403；8001 还因 public registration 关闭，临时用户注册失败。按 TDD 在
  `tests/test_health_details.py` 新增 production/auth 场景红灯：未认证请求必须 401，普通认证用户应可读取
  安全 retrieval-contract，但同一用户仍不能读取 `/health/details`。实现上新增
  `require_authenticated_in_production()`，只把 `retrieval-contract` 改为 production
  authenticated-only，`health/details` 继续 admin-only。验证：目标 health tests `2 passed`；
  `tests/test_health_details.py tests/test_stage44_auth.py` 为 `11 passed`；
  Phase65 聚焦含 health/auth 集合为 `203 passed`；相关 `py_compile` 通过。注意：运行中的
  8011 仍是旧 uvicorn 进程，endpoint readiness 产物仍反映旧进程状态；需要刷新/重启后重跑
  `--preflight-only --auto-auth`。
- 65C Task 4 endpoint readiness 闭环：
  用 systematic debugging 继续定位 preflight-only 卡点：刷新 8011 后，公开注册关闭导致
  topology auto-auth 仍可能失败；同时 evaluator 在 auto-auth 失败并跳过 contract fetch 时，会把
  `contract_fetch` 误报为 `pass`。按 TDD 新增红灯测试后，`scripts/evaluate_phase65_agent_gate.py`
  现在只允许 loopback endpoint 在公开注册关闭时 bootstrap 本地短期 admin 评测账号，登录后 token
  仅在内存中使用；远程 endpoint 仍 fail-closed。readiness summary 已修正为没有实际 contract
  时 `contract_fetch=blocked`，preflight-only 遇到 identical endpoint identity 时也会输出
  blocked summary 而不是无细节 ValueError。继续发现 baseline 旧进程和 candidate 新进程共享主工作区
  磁盘文件，旧的 endpoint identity 会受当前磁盘源码哈希影响而无法区分 lane；因此新增
  `PHASE65_ENDPOINT_IDENTITY_LABEL`，只把 label hash 纳入 identity，不输出 label 原文。candidate
  8011 已以该非敏感 label 重启到 PID 30796。最新执行
  `python scripts/evaluate_phase65_agent_gate.py --mode paired --preflight-only --auto-auth --baseline-base-url http://127.0.0.1:8001 --candidate-base-url http://127.0.0.1:8011 --runs 1 --limit 2 --contract-gate-status pass --topology-gate-status pass --fault-gate-status pass --summary-out output/phase65/paired-endpoint-readiness.json`
  没有执行 case、没有重跑 baseline；`endpoint_readiness.gate=pass`，baseline/candidate 的
  auto-auth、contract fetch、endpoint identity、index fingerprint、cold-run receipts、model
  inventory 与 endpoint identity distinct 均为 `pass`。命令整体 exit 1 是预期，因为
  paired execution preflight 仍处于 dry-run manifest incomplete/non-cold 且未带
  `--authorize-paid-run` 的 blocked 状态。更新 acceptance summary 后，contract/topology/fault/
  recovery/endpoint readiness 为 `pass`，paired execution preflight、paired full、holdout 和
  human acceptance 仍阻断。验证：新增 targeted tests 红绿通过；`tests/test_evaluate_phase65_agent_gate.py
  tests/test_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py` 为 `54 passed`；
  `tests/test_phase65_model_inventory.py` 与关键 health contract 测试合计 `6 passed`。
- 65C Task 4 bounded judged smoke 推进：
  在 endpoint readiness 通过后，执行 2 cases × 2 lanes 的 bounded paired smoke，确认
  complete/cold manifest 与 `--authorize-paid-run` 的 paired execution preflight 可为 `pass`，
  且没有重跑 90-row baseline。smoke 暴露两个 gate/evaluator 问题：第一，`_collect_metrics()`
  仍把 token/cost 缺失视作 paired rows incomplete，与用户已移除费用门禁的要求冲突；已按 TDD
  改为 token/cost 只影响 optional ratio，缺失时保持 `candidate_token_ratio/candidate_cost_ratio=null`，
  不再破坏 row completeness。第二，blind judge provider 会返回 fenced JSON、nested `deltas` 或偶发
  empty content；已新增 `_parse_blind_judge_payload()` 支持 fenced JSON 与 nested deltas，新增
  `_safe_judge_blind_pair()` 将 provider empty content 等异常转为安全
  `blind_judge_provider_failed`，让 evaluator fail-closed 写 summary，而不是崩溃。最新
  `paired-judged-smoke-v3` 完成 4/4 endpoint rows，paired execution preflight 为 `pass`，
  contract gate 为 `pass`，judge error count 为 1（provider empty content），quality/runtime/
  Phase65 acceptance 仍 blocked；这只是 bounded smoke，不冒充 full A/B。重新运行
  `scripts/summarize_phase65_acceptance.py` 后，acceptance summary 中 contract/topology/fault/
  recovery/endpoint readiness/paired execution preflight 均为 `pass`，paired full、holdout、
  human acceptance 仍 `missing`。验证：gate/evaluator 相关红绿测试通过，
  `tests/test_phase65_agent_gate.py` 为 `23 passed`，`tests/test_evaluate_phase65_agent_gate.py`
  为 `33 passed`，组合聚焦验证为 `61 passed`。
- 2026-07-15 Codex 继续 65C candidate targeted correction：
  用户明确要求不要再重跑 baseline，因此本轮只处理 candidate 30×1 剩余失败
  `phase64-followup-02`。定位结果：该样本 `history_json` 有上下文，candidate 已调用
  `search_figures`，但图像召回为 0 并拒答；问题不是 tool route，而是视觉 follow-up 图像证据
  召回过度依赖 vector-only 候选。按 TDD 新增
  `test_search_figures_uses_keyword_image_fallback_for_contextual_visual_followup`，随后在
  `app/services/agent/tools.py` 为 `search_figures` 增加 keyword `image_description` 候选兜底，
  并继续复用既有图片质量、去重、specific requirement 与 generic visual fallback 规则。
  另修复单行 candidate retry 被 judge receipt contract 误挡的问题：
  `JudgeReceiptContract` 默认仍要求正式 A/B 双向均衡；仅单 lane targeted retry 且不执行
  blind judge 时允许 `require_balanced_mapping=False`。
  重启 candidate 8011 后仅执行
  `phase64-followup-02`，结果写入
  `output/phase65/candidate-followup02-rerun-results.csv`：`ok=True`、`search_figures`
  召回/metadata 均为 12、引用 6、未拒答、cold-cache receipt `valid`。
  已覆盖更新 `candidate-30x1-corrected-results.csv`，当前 candidate 30/30 `ok=True`；
  合并 `baseline-fasttimeout-30x1-rows.csv` 与 corrected candidate 后，
  `paired-reuse-baseline-30x1-corrected-results.csv` 为 baseline 30/30、candidate 30/30。
  严格 summary
  `paired-reuse-baseline-30x1-corrected-summary.json` 仍按真实性 fail-closed blocked，
  原因为 `evaluator_sha256_mismatch`，因为该证据复用了旧 baseline manifest 且 candidate
  含 targeted correction，并非一次同 evaluator 的正式 full A/B。
  验证：新增/相关小测试 `3 passed`，receipt/evaluator 小测试 `4 passed`，相关聚焦集合
  `80 passed`，最终组合
  `tests/test_agent_tools.py tests/test_judge_phase65_agent_gate.py tests/test_evaluate_phase65_agent_gate.py tests/test_merge_phase65_paired_results.py tests/test_evaluate_phase63_e2e.py`
  为 `95 passed`；相关 `py_compile` 通过。未暂存、未提交、未重跑 baseline。
- 2026-07-15 Codex 继续修正 65C acceptance/holdout gate 语义：
  复核 `scripts/summarize_phase65_acceptance.py` 后发现，当 `paired_summary` 已存在但 gate 为
  blocked 时，acceptance summary 仍把失败项写成 `paired_full_summary_missing`，容易误导后续
  agent。按 TDD 新增
  `test_acceptance_summary_distinguishes_blocked_paired_summary_from_missing`，修复后现在输出
  `paired_full_gate_not_pass`，next action 为“resolve blocked paired A/B summary...”。已刷新
  `output/phase65/acceptance-preflight-summary.json`，当前 components 为 contract/topology/fault/
  recovery/endpoint readiness/paired preflight `pass`，paired full `blocked`，holdout/human acceptance
  `missing`。
  继续对照 65C Task 5 发现 evaluator 的 `holdout` mode 原先只跑 candidate lane，且默认继承
  `--runs=3`；这与计划中“one A/B observation per holdout case”不一致。按 TDD 新增 holdout
  endpoint 与 scheduling 测试后，`holdout` mode 现在必须同时提供 baseline/candidate endpoint、
  endpoint 必须 distinct，dry-run/execute 均按 baseline+candidate 双 lane 排程；未显式传
  `--runs` 时 holdout 默认为 1。验证：
  `tests/test_phase65_acceptance_summary.py` 为 `3 passed`；
  holdout targeted tests 为 `4 passed`；
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py` 为
  `45 passed`；更宽相关回归
  `tests/test_agent_tools.py tests/test_judge_phase65_agent_gate.py tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py tests/test_merge_phase65_paired_results.py tests/test_evaluate_phase63_e2e.py`
  为 `101 passed`；相关 `py_compile` 通过。
- 2026-07-15 Codex 继续补齐 holdout blind judge receipt：
  按 systematic debugging 确认根因：`evaluate_phase65_agent_gate.py` 已会为 holdout 收集
  baseline/candidate answer pair，但 blind judge loop 被 `args.mode == "paired"` 限制，导致
  `--mode holdout --execute-blind-judge` 写出 0 条 judge rows；同时 acceptance summary 只要求
  clean holdout rows，未要求 holdout judge receipt。按 TDD 新增
  `test_holdout_execute_blind_judge_writes_safe_judge_receipts` 与
  `test_acceptance_summary_requires_holdout_judge_receipts`，修复后 holdout execute blind judge
  会写 safe judge rows，并把 `judge_summary` 纳入 `holdout_summary`；acceptance 的
  `_holdout_status()` 现在要求 matched judge summary（paired_count=holdout_case_count、
  case_set_sha256 匹配、四个 lower bound finite 且 ≥ -0.05），否则 blocked/fail-closed。
  刷新 `output/phase65/acceptance-preflight-summary.json` 后仍为 blocked，原因保持：
  `paired_full_gate_not_pass`、`holdout_summary_missing`、`human_acceptance_missing`。
  验证：
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py` 为
  `47 passed`；更宽相关回归
  `tests/test_agent_tools.py tests/test_judge_phase65_agent_gate.py tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py tests/test_merge_phase65_paired_results.py tests/test_evaluate_phase63_e2e.py`
  为 `103 passed`；相关 `py_compile` 通过。
- 2026-07-15 Codex 继续落地 baseline reuse waiver：
  用户明确要求不要再重跑 baseline，并确认当前阶段已有 baseline 与 provider receipt/授权。
  为避免后续 agent 在 `evaluator_sha256_mismatch` 上反复卡住，本轮按 TDD 新增
  `build_baseline_reuse_waiver()` 与
  `scripts/build_phase65_baseline_reuse_waiver.py`。waiver 默认 fail-closed：必须显式
  `--user-authorized-baseline-reuse`，paired summary 必须只因
  `evaluator_sha256_mismatch` blocked，paired CSV 必须 baseline/candidate 各 30 个 case-run
  完全对齐、两侧均 `ok=True`、无 error category、HTTP 非 200、cold receipt 异常或 completed
  tool replay。还修复了 CSV UTF-8 BOM 导致 `variant` header 读不到的问题，并补回归测试。
  已用现有 corrected evidence 生成
  `output/phase65/baseline-reuse-waiver-30x1-corrected.json`：`gate=pass`、
  `baseline_pair_count=30`、`candidate_pair_count=30`、`failed_required=[]`。
  刷新 `output/phase65/acceptance-preflight-summary.json` 后，components 中
  `baseline_reuse_waiver=pass`，`paired_execution_preflight` 与 `paired_full_gate` 仍如实显示
  `blocked`，但通过 `evidence_substitutions` 被 waiver 替代；当前 required blockers 只剩
  `holdout_summary_missing` 与 `human_acceptance_missing`。验证：
  `tests/test_phase65_acceptance_summary.py` 为 `8 passed`；相关 gate/evaluator 集合为
  `90 passed`；更宽回归
  `tests/test_agent_tools.py tests/test_judge_phase65_agent_gate.py tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_acceptance_summary.py tests/test_merge_phase65_paired_results.py tests/test_evaluate_phase63_e2e.py tests/test_phase65_agent_gate.py`
  为 `130 passed`；相关 `py_compile` 通过。未重跑 baseline，未暂存/提交。
- 2026-07-15 Codex 继续推进 reviewer holdout receipt：
  当前工作区仍没有可用的 `data/evaluation/phase65_private_holdout_cases.csv`，因此不能伪造 reviewer
  holdout pass，也不应把 holdout 继续留成 summary missing。按 TDD 新增
  `scripts/build_phase65_holdout_blocked_summary.py`，生成
  `phase65-holdout-blocked-summary-v1` 安全 blocked receipt；该脚本只记录缺失原因、0 个 holdout
  case、期望最小 case 数与下一步动作，不调用 provider，不写 prompt、answer、evidence 正文或原始响应。
  当前 `output/phase65/holdout-blocked-missing-private-cases.json` 为 `gate=blocked`、
  `failed_required=["private_holdout_cases_missing"]`、`holdout_case_count=0`。
  刷新 `output/phase65/acceptance-preflight-summary.json` 后，holdout 从 `missing` 推进为
  `blocked`；当前 components 中 baseline reuse waiver/contract/topology/fault/recovery/endpoint
  readiness 为 `pass`，paired preflight/full 仍如实 `blocked` 但被 waiver 替代，剩余 required
  blockers 为 `holdout_gate_not_pass` 与 `human_acceptance_missing`。验证：
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为 `52 passed`，
  相关 `py_compile` 通过。未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 继续推进 human acceptance packet：
  为避免 human acceptance 继续停留在 `missing`，按 TDD 新增
  `scripts/build_phase65_human_acceptance_packet.py` 与
  `phase65-human-acceptance-packet-v1`。该 packet 从当前 acceptance summary 生成，记录
  `acceptance_summary_sha256`、当前 failed_required、review checklist 与下一步动作；它是用户人工
  验收入口，不代替用户 pass/fail，不写 prompt、answer、evidence 正文、provider raw payload 或密钥。
  当前 `output/phase65/human-acceptance-pending-packet.json` 为 `gate=blocked`、
  `status=pending_user_review`。刷新 `output/phase65/acceptance-preflight-summary.json` 后，
  `human_acceptance` 从 `missing` 推进为 `blocked`，当前 required blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。验证：
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为 `53 passed`；
  相关 `py_compile` 通过；`human-acceptance-pending-packet.json` 与
  `acceptance-preflight-summary.json` 的敏感词扫描无命中。未重跑 baseline，未代签 human
  acceptance，未暂存/提交。
- 2026-07-15 Codex 继续推进 human acceptance recorder：
  按 TDD 新增 `scripts/record_phase65_human_acceptance.py` 与
  `phase65-human-acceptance-record-v1`。recorder 只接受显式 `--decision pass|fail` 和
  `--confirm-checklist`；`pass` 决策会检查 human acceptance packet 中的 failed_required，
  若存在非 human gate（例如当前 `holdout_gate_not_pass`）则拒绝写入 pass record。当前实际命令
  `--decision pass` 已被正确拒绝，输出安全 JSON
  `error_category=cannot_pass_with_open_non_human_gates`，且
  `output/phase65/human-acceptance-record-attempt.json` 未创建。验证：
  `tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为
  `56 passed`；相关 `py_compile` 通过。未重跑 baseline，未代签 human acceptance，未暂存/提交。
- 2026-07-15 Codex 继续推进 private holdout intake：
  为解除 reviewer holdout 阻断的下一步提供可执行入口，按 TDD 新增
  `scripts/prepare_phase65_holdout_intake.py` 与 `tests/test_phase65_holdout_intake.py`。
  该脚本生成 header-only 模板 `output/phase65/phase65_private_holdout_cases.template.csv` 和
  intake packet `output/phase65/holdout-intake-packet.json`；模板只有列名，没有真实 case，
  `template_is_executable=false`，直接拿模板校验会得到
  `holdout_requires_twelve_unique_cases`，防止误把模板当 holdout pass。validator 要求至少 12 个
  唯一 case 且 question 非空，并只输出 case count/hash 等安全元数据。当前
  `data/evaluation/phase65_private_holdout_cases.csv` 仍不存在，未伪造 holdout。验证：
  `tests/test_phase65_holdout_intake.py tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py`
  为 `59 passed`；相关 `py_compile` 通过；intake packet/template 敏感词扫描无命中。未重跑
  baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 继续推进 Phase65 closeout audit：
  为把阶段收口状态从散落产物汇总为单一安全入口，按 TDD 新增
  `scripts/audit_phase65_closeout.py` 与 `tests/test_phase65_closeout_audit.py`。audit 汇总
  `acceptance-preflight-summary.json`、`holdout-intake-packet.json` 与
  `human-acceptance-pending-packet.json`，只输出 gate/status、failed_required 与下一步动作，不写
  prompt、answer、evidence 正文、provider raw payload 或密钥。当前
  `output/phase65/closeout-audit.json` 为 `gate=blocked`、`ready_for_closeout=false`；
  components 中 acceptance summary、holdout intake、human acceptance packet 均为 `blocked`；
  failed_required 为 `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。验证：
  `tests/test_phase65_closeout_audit.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为 `61 passed`；
  相关 `py_compile` 通过；closeout audit 敏感词扫描无命中。未重跑 baseline，未执行真实 holdout，
  未代签 human acceptance，未暂存/提交。
- 2026-07-15 Codex 继续加强 private holdout 隔离：
  复核 `evaluate_phase65_agent_gate.py` 后确认 public/default case 来源为
  `data/evaluation/phase64_latency_cases.csv`。按 TDD 新增 overlap 测试后，
  `scripts/prepare_phase65_holdout_intake.py` 的 validator 现在支持 `--exclude-cases`（默认 public
  case CSV），若 private holdout case_id 与公开/已用 case_id 重叠，会拒绝并返回
  `holdout_overlaps_excluded_cases`。这能防止 reviewer holdout 被 public baseline cases 复制污染。
  已重新生成 `output/phase65/holdout-intake-packet.json` 与模板校验产物；intake packet 现在显式写出
  `public_overlap_guard=true` 与 `excluded_cases_path=data\\evaluation\\phase64_latency_cases.csv`。真实
  `data/evaluation/phase65_private_holdout_cases.csv` 仍不存在，closeout audit 仍为
  `ready_for_closeout=false`。验证：
  `tests/test_phase65_holdout_intake.py` 为 `4 passed`；更宽相关回归
  `tests/test_phase65_holdout_intake.py tests/test_phase65_closeout_audit.py
  tests/test_phase65_acceptance_summary.py tests/test_evaluate_phase65_agent_gate.py` 为 `62 passed`；
  相关 `py_compile` 通过；intake 产物敏感词扫描无命中。未重跑 baseline，未执行真实 holdout，
  未暂存/提交。
- 2026-07-15 Codex 继续加强 evaluator 级 private holdout 隔离：
  为避免操作方绕过 intake 直接调用 evaluator，按 TDD 新增
  `test_holdout_cli_rejects_overlap_with_cases_argument`。当前
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 会把 `--cases`（默认
  `data/evaluation/phase64_latency_cases.csv`）作为 public/frozen 排除集传入
  `validate_holdout_cases()`；若 holdout case_id 与该集合重叠，会在 evaluator 本体拒绝为
  `holdout_overlaps_public_cases`。验证：targeted
  `test_holdout_rejects_overlap_with_public_cases` 与
  `test_holdout_cli_rejects_overlap_with_cases_argument` 为 `2 passed`；相关回归
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_closeout_audit.py tests/test_phase65_acceptance_summary.py` 为 `64 passed`；
  `py_compile` 通过。未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 继续加强 holdout acceptance proof：
  上一轮 evaluator 已能拒绝 public/frozen case_id 重叠；本轮按 TDD 将该事实纳入正式
  acceptance 所需证据。`scripts/evaluate_phase65_agent_gate.py --mode holdout` 生成的
  `holdout_summary` 现在包含 `public_overlap_exclusion_proven`、`excluded_case_count` 与
  `excluded_case_set_sha256`；`scripts/summarize_phase65_acceptance.py` 现在要求这些字段存在且有效，
  否则即使 clean A/B rows 与 holdout judge summary 都满足，也只会给 `holdout_gate=blocked`。
  已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`，当前仍为 blocked，failed_required 仍是
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。验证：targeted
  `test_acceptance_summary_requires_holdout_public_overlap_proof` 与
  `test_holdout_execute_blind_judge_writes_safe_judge_receipts` 为 `2 passed`；相关回归
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_closeout_audit.py tests/test_phase65_acceptance_summary.py` 为 `65 passed`；
  相关 `py_compile` 通过。未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 继续加强 holdout real-execution proof：
  为避免 dry-run 或手写 summary 被当成 reviewer holdout pass，按 TDD 新增
  `test_acceptance_summary_requires_holdout_real_execution_proof`。当前
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 生成的 `holdout_summary` 会写入
  `execution_mode` 与 `executed_ab_row_count`；acceptance 要求 `execution_mode=real_api` 且
  `executed_ab_row_count >= holdout_case_count * 2` 才允许 `holdout_gate=pass`。已刷新
  `output/phase65/acceptance-preflight-summary.json` 与 `output/phase65/closeout-audit.json`；
  当前仍为 blocked，failed_required 仍是 `holdout_gate_not_pass` 与
  `human_acceptance_not_pass`。验证：targeted real-execution/evaluator receipt tests 为
  `2 passed`；相关回归
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_closeout_audit.py tests/test_phase65_acceptance_summary.py` 为 `66 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 继续加强 human acceptance 防陈旧签字：
  为避免旧 packet/旧 summary 上签出的 pass record 被复用到新证据状态，按 TDD 新增
  `test_human_acceptance_record_must_match_current_pre_human_summary`。当前
  `scripts/summarize_phase65_acceptance.py` 会先从当前非 human 证据计算 canonical pre-human
  acceptance summary hash，再要求 `phase65-human-acceptance-record-v1` 的
  `acceptance_summary_sha256` 与该 hash 一致；否则 `human_acceptance` 保持 `blocked`。
  已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`；当前仍为 blocked，failed_required 仍是
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。验证：human acceptance targeted tests 为
  `2 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `67 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 继续加强 human acceptance recorder 签字时校验：
  为把防陈旧签字提前到 recorder 动作本身，按 TDD 新增
  `test_human_acceptance_recorder_rejects_stale_current_summary` 与
  `test_human_acceptance_recorder_cli_rejects_stale_current_summary`。当前
  `scripts/record_phase65_human_acceptance.py` 的 `pass` 决策必须提供
  `current_acceptance_summary` / `--current-acceptance-summary`，且 packet 中的
  `acceptance_summary_sha256` 必须与当前 summary hash 匹配；否则拒绝为
  `human_acceptance_summary_mismatch`。已刷新 `output/phase65/acceptance-preflight-summary.json`
  与 `output/phase65/closeout-audit.json`；当前仍为 blocked，failed_required 仍是
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。验证：recorder targeted tests 为
  `3 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `69 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 移除裸 human acceptance pass 旁路：
  为避免 `summarize_phase65_acceptance.py --human-acceptance pass` 绕过
  `phase65-human-acceptance-record-v1` 的 hash 绑定，按 TDD 新增
  `test_direct_human_acceptance_pass_does_not_bypass_record_requirement`。当前 direct
  `human_acceptance="pass"` 只会让 human gate 保持 `blocked`；CLI `--human-acceptance` 只接受
  `fail`，pass 必须来自 record summary。已刷新 `output/phase65/acceptance-preflight-summary.json`
  与 `output/phase65/closeout-audit.json`；当前仍为 blocked，failed_required 仍是
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。验证：
  `tests/test_phase65_acceptance_summary.py` 为 `19 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `70 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 收紧 closeout human artifact 校验：
  为避免 closeout audit 只看顶层 `gate=pass` 而误收错误格式 human artifact，按 TDD 新增
  `test_closeout_audit_requires_human_acceptance_record_not_generic_pass_packet`。当前
  `scripts/audit_phase65_closeout.py` 要求 closeout 支撑的人验收 artifact 必须是
  `phase65-human-acceptance-record-v1`，且 nested `human_acceptance_summary` 为
  `gate=pass/status=accepted`；普通 packet 或错误格式 `gate=pass` 只能 blocked。已刷新
  `output/phase65/closeout-audit.json`，当前仍为 blocked。验证：
  `tests/test_phase65_closeout_audit.py` 为 `3 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `71 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 绑定 closeout 使用的 human receipt：
  为防止 closeout 传入另一个 accepted record，按 TDD 新增
  `test_closeout_audit_rejects_human_record_that_does_not_match_acceptance_summary`。
  当前 `scripts/summarize_phase65_acceptance.py` 在 human gate pass 时写入
  `human_acceptance_summary_sha256`；`scripts/audit_phase65_closeout.py` 会重新计算传入 human
  record 的 nested `human_acceptance_summary` hash 并与 acceptance summary 比对，不匹配则
  `human_acceptance_packet=blocked`。已刷新 `output/phase65/acceptance-preflight-summary.json`
  与 `output/phase65/closeout-audit.json`，当前仍为 blocked。验证：
  `tests/test_phase65_closeout_audit.py` 为 `4 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `72 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 绑定 closeout 使用的 holdout case set：
  为防止 closeout 传入另一个通过的 holdout intake validation，按 TDD 新增
  `test_closeout_audit_rejects_holdout_intake_that_does_not_match_acceptance_summary`。当前
  `scripts/summarize_phase65_acceptance.py` 在 holdout gate pass 时写入
  `holdout_case_set_sha256`；`scripts/audit_phase65_closeout.py` 会要求
  `phase65-holdout-intake-validation-v1` 的 `holdout_case_set_sha256` 与 acceptance summary 匹配，
  否则 `holdout_intake=blocked`。已刷新 `output/phase65/acceptance-preflight-summary.json`
  与 `output/phase65/closeout-audit.json`，当前仍为 blocked。验证：targeted holdout/human
  hash tests 为 `2 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `73 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 收紧 closeout acceptance summary 内部结构校验：
  为避免极简手写 `gate=pass` acceptance summary 被 closeout 信任，按 TDD 新增
  `test_closeout_audit_rejects_minimal_handwritten_acceptance_pass_summary`。当前
  `scripts/audit_phase65_closeout.py` 要求 pass summary 具备 `phase65_acceptance=pass`、空
  `failed_required`、关键 components 为 pass，并且 paired full/preflight pass 或显式 baseline
  reuse substitutions。已刷新 `output/phase65/closeout-audit.json`，当前仍为 blocked。验证：
  `tests/test_phase65_closeout_audit.py` 为 `6 passed`；相关回归
  `tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py` 为 `74 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 收紧 closeout holdout intake case-count 校验：
  为避免 closeout 只信任 `ready_to_run_holdout=true` 与 case-set hash，按 TDD 新增
  `test_closeout_audit_rejects_holdout_intake_with_too_few_cases`。当前
  `scripts/audit_phase65_closeout.py` 会在 closeout 层再次要求
  `phase65-holdout-intake-validation-v1` 的 `holdout_case_count >= 12`；case 数不足时
  `holdout_intake=blocked`，不能让 `ready_for_closeout=true`。已刷新
  `output/phase65/closeout-audit.json`，当前仍为 blocked。验证：
  `tests/test_phase65_closeout_audit.py` 为 `7 passed`。未重跑 baseline，未执行真实 holdout，
  未暂存/提交。
- 2026-07-15 Codex 收紧 human acceptance recorder 字段校验：
  为避免极简手写 accepted human summary 绕过人工验收门，按 TDD 新增
  `test_human_acceptance_summary_requires_recorder_fields` 与
  `test_closeout_audit_rejects_human_record_missing_recorder_fields`。当前
  `scripts/summarize_phase65_acceptance.py` 要求 human pass summary 必须有 recorder 产生的
  `status=accepted`、`decision=pass`、`review_checklist_confirmed=true`、
  `open_non_human_gate_count=0`、非空 `reviewer_label` 与匹配的当前 summary hash；
  `scripts/audit_phase65_closeout.py` 在 closeout 层也要求这些 recorder 字段。已刷新
  `output/phase65/acceptance-preflight-summary.json` 与 `output/phase65/closeout-audit.json`，
  当前仍为 blocked，failed_required 仍是 `holdout_gate_not_pass` 与
  `human_acceptance_not_pass`。未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 收紧 closeout holdout intake public-overlap 校验：
  为避免 closeout 只看 intake 的 ready/hash 而漏掉 public/frozen overlap 结果，按 TDD 新增
  `test_closeout_audit_rejects_holdout_intake_with_overlap_count`。当前
  `scripts/audit_phase65_closeout.py` 会在 closeout 层再次要求
  `phase65-holdout-intake-validation-v1` 的 `excluded_case_overlap_count == 0`；overlap 计数非零时
  `holdout_intake=blocked`。已刷新 `output/phase65/closeout-audit.json`，当前仍为 blocked。
  验证：红灯测试先为 `1 failed`；实现后 closeout + holdout intake tests 为 `13 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 收紧 holdout summary schema version 校验：
  为避免旧格式或手写 pass-looking holdout summary 被 acceptance 误收，按 TDD 新增
  `test_acceptance_summary_requires_holdout_summary_schema_version`。当前
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 会写入
  `schema_version=phase65-holdout-summary-v1`，而 `scripts/summarize_phase65_acceptance.py` 要求该
  schema 后才允许 `holdout_gate=pass`。已刷新
  `output/phase65/acceptance-preflight-summary.json` 与 `output/phase65/closeout-audit.json`，当前仍为
  blocked，failed_required 仍是 `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。验证：
  targeted red test 先为 `1 failed`；实现后 acceptance + evaluator tests 为 `66 passed`。
  未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 收紧 closeout holdout intake required-columns 校验：
  为避免手写最小 pass intake 缺少 reviewer holdout CSV 列契约，按 TDD 新增
  `test_closeout_audit_rejects_holdout_intake_missing_required_columns`。当前
  `scripts/audit_phase65_closeout.py` 会在 closeout 层再次要求
  `phase65-holdout-intake-validation-v1.required_columns` 精确等于
  `HOLDOUT_TEMPLATE_FIELDS`。已刷新 `output/phase65/closeout-audit.json`，当前仍为 blocked。
  验证：红灯测试先为 `1 failed`；实现后 `tests/test_phase65_closeout_audit.py` 为
  `10 passed`。未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 收紧 holdout A/B lane completeness 校验：
  为避免仅凭总 `executed_ab_row_count` 证明真实 holdout，而没有 baseline/candidate 两条 lane 的
  对称覆盖，按 TDD 新增 `test_acceptance_summary_requires_holdout_ab_lane_counts`。当前
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 会写入
  `baseline_ab_row_count` 与 `candidate_ab_row_count`；
  `scripts/summarize_phase65_acceptance.py` 要求两者都等于 `holdout_case_count` 才允许
  `holdout_gate=pass`。已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`，当前仍为 blocked，failed_required 仍是
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。验证：红灯测试先为 `1 failed`；
  实现后 targeted tests 为 `3 passed`，acceptance + evaluator tests 为 `67 passed`。未重跑
  baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 收紧 holdout A/B lane case-set hash 校验：
  为避免 baseline/candidate lane 数量都正确但覆盖不同 holdout case 集，按 TDD 新增
  `test_acceptance_summary_requires_holdout_ab_lane_case_set_hashes`。当前
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 会写入
  `baseline_ab_case_set_sha256` 与 `candidate_ab_case_set_sha256`；
  `scripts/summarize_phase65_acceptance.py` 要求两者都等于 `holdout_case_set_sha256` 才允许
  `holdout_gate=pass`。已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`，当前仍为 blocked，failed_required 仍是
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。验证：红灯测试先为 `1 failed`；
  实现后 targeted tests 为 `3 passed`，acceptance + evaluator tests 为 `68 passed`。未重跑
  baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 将 holdout A/B lane case-set hash 延伸到 closeout：
  按 TDD 新增 closeout 对抗用例，确认 `candidate_ab_case_set_sha256` 与
  `holdout_case_set_sha256` 不一致时最终收口必须 blocked。`scripts/summarize_phase65_acceptance.py`
  现在在 holdout pass 时把两条 lane hash 写入 acceptance summary；
  `scripts/audit_phase65_closeout.py` 会在 acceptance summary 自检中二次校验两条 lane hash 都等于总
  holdout hash。已重新生成 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`，当前仍 blocked，剩余 required blockers 仍是
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 收紧 holdout blind-judge summary schema/receipt 校验：
  为避免旧格式或手写 lower-bound 字段伪装成 reviewer holdout blind judge pass，按 TDD 新增
  `test_judge_summary_binds_receipt_contract_when_available` 与
  `test_acceptance_summary_requires_holdout_judge_summary_schema`。当前
  `scripts/judge_phase65_agent_gate.py` 生成 `schema_version=phase65-judge-summary-v1`、
  `receipt_contract_sha256` 与 `judge_expected_pairs`；`scripts/summarize_phase65_acceptance.py`
  要求 holdout `judge_summary` 的 schema、expected pair count、case-set hash 与 receipt contract hash
  同时满足后才允许 `holdout_gate=pass`。已重新生成
  `output/phase65/acceptance-preflight-summary.json` 与 `output/phase65/closeout-audit.json`，当前仍
  blocked，剩余 required blockers 仍是 `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。未重跑
  baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 将 holdout blind-judge receipt hash 延伸到 closeout：
  按 TDD 新增 closeout 对抗用例，确认 pass-looking acceptance summary 缺
  `holdout_judge_receipt_contract_sha256` 时最终收口必须 blocked。当前
  `scripts/summarize_phase65_acceptance.py` 会在 holdout pass 时透出
  `holdout_judge_receipt_contract_sha256`；`scripts/audit_phase65_closeout.py` 要求该字段为合法
  SHA-256。已重新生成 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`，当前仍 blocked，剩余 required blockers 仍是
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。未重跑 baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 将 reviewer holdout case count 绑定到 closeout：
  按 TDD 新增 closeout 对抗用例，确认 acceptance summary 的 `holdout_case_count` 与
  `phase65-holdout-intake-validation-v1.holdout_case_count` 不一致时最终收口必须 blocked。当前
  `scripts/summarize_phase65_acceptance.py` 会在 holdout pass 时透出 `holdout_case_count`；
  `scripts/audit_phase65_closeout.py` 要求 intake count 与 acceptance count 完全一致。已重新生成
  `output/phase65/acceptance-preflight-summary.json` 与 `output/phase65/closeout-audit.json`，当前仍
  blocked，剩余 required blockers 仍是 `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。未重跑
  baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 将 reviewer holdout 真实执行证明绑定到 closeout：
  按 TDD 新增 closeout 对抗用例，确认 pass-looking acceptance summary 缺
  `holdout_execution_mode=real_api` 与 A/B 执行行数证明时最终收口必须 blocked。当前
  `scripts/summarize_phase65_acceptance.py` 会在 holdout pass 时透出 `holdout_execution_mode`、
  `holdout_executed_ab_row_count`、`holdout_baseline_ab_row_count` 与
  `holdout_candidate_ab_row_count`；`scripts/audit_phase65_closeout.py` 要求总执行行数至少为
  `holdout_case_count * 2`，且 baseline/candidate 两条 lane 行数都等于 `holdout_case_count`。已重新生成
  `output/phase65/acceptance-preflight-summary.json` 与 `output/phase65/closeout-audit.json`，当前仍
  blocked，剩余 required blockers 仍是 `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。未重跑
  baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 将 reviewer holdout public/frozen overlap proof 绑定到 closeout：
  按 TDD 新增 closeout 对抗用例，确认 pass-looking acceptance summary 缺
  `holdout_excluded_case_count` 与 `holdout_excluded_case_set_sha256` 时最终收口必须 blocked。当前
  `scripts/summarize_phase65_acceptance.py` 会在 holdout pass 时透出这两个安全证明字段；
  `scripts/audit_phase65_closeout.py` 要求 excluded count 大于 0 且 excluded case-set hash 合法。已重新生成
  `output/phase65/acceptance-preflight-summary.json` 与 `output/phase65/closeout-audit.json`，当前仍
  blocked，剩余 required blockers 仍是 `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。未重跑
  baseline，未执行真实 holdout，未暂存/提交。
- 2026-07-15 Codex 建立并执行 Phase65 private holdout A/B：
  新增 `data/evaluation/phase65_private_holdout_cases.csv`，包含 12 条 reviewer holdout case，覆盖
  ordinary、relationship、table、figure 与 boundary/refusal。`prepare_phase65_holdout_intake.py`
  校验通过：`holdout_case_count=12`、`excluded_case_overlap_count=0`。按 TDD 修复
  `scripts/evaluate_phase65_agent_gate.py`：holdout intake 的 `question` 字段现在会映射为底层执行器需要的
  `query` 字段；blind judge 增加最多 3 次安全重试，并对 transient judge answer 输入做有界裁剪，避免超长
  prompt 诱发 provider 不稳定。真实执行命令使用 baseline `127.0.0.1:8001` 与 candidate
  `127.0.0.1:8011`，未重跑 baseline 90-row。最终第三轮 `output/phase65/holdout-results.csv`
  为 24/24 real A/B rows `ok=True`、`cold_cache_receipt_status=valid`，`holdout_summary.clean=true`；
  但 blind judge 只形成 5/12 安全 receipt，`judge_error_count=7`，且已有 lower bound 为负，因此
  `holdout_gate` 仍为 blocked。已刷新 `output/phase65/acceptance-preflight-summary.json` 与
  `output/phase65/closeout-audit.json`，当前 required blockers 仍是 `holdout_gate_not_pass` 与
  `human_acceptance_not_pass`。相关回归：
  `tests/test_evaluate_phase65_agent_gate.py tests/test_phase65_holdout_intake.py
  tests/test_phase65_acceptance_summary.py tests/test_phase65_closeout_audit.py
  tests/test_judge_phase65_agent_gate.py -q` 为 `106 passed`。未暂存/提交。

- 2026-07-15 Codex 完成 Phase66 Tool Calling Runtime 真正瘦身的本地实现验证：
  `tool_calling_service.py` 缩到 233 行，`ToolCallingAgentService.query` 缩到 64 行，
  `run_coordinator.py` 缩到 90 行，满足 `tool_calling_service.py <= 260 lines`、
  `ToolCallingAgentService.query <= 80 lines`、`run_coordinator.py <= 120 lines`。生产
  `agent_run_coordinator_enabled` flag 已 deleted，回退策略明确为 rollback through Git。生产工具库存固定为
  `hybrid_search_knowledge`、`search_tables`、`search_figures`、`analyze_user_image`。验证收据：
  `output/phase66/final/runtime-structure.json`、`output/phase66/final/fault-matrix.json`、
  `output/phase66/final/runtime-recovery.json`、`output/phase66/evaluation/summary.json`、
  `output/phase66/evaluation/review-packet.md`。全量后端 `1897 passed, 1 skipped`，前端 unit/lint/build
  passed，compileall passed，结构 snapshot `--check` passed。fresh Phase66 evaluator 当前为
  `review_required`，human acceptance 为 `human_acceptance_pending`；未暂存、未提交、未 tag、未 push。
- 2026-07-15 Codex 继续补齐 Phase66 evaluator 收据门禁：
  `scripts/evaluate_phase66_runtime_convergence.py --collect` 不再是未实现占位，而是要求显式
  `--observations` Phase66 receipt；`--merge` 会检查 30 text + 4 image 配对覆盖，且 B 的 completion、
  answer_accuracy、citation_correctness、overall 不得低于 A。TDD 红灯先失败于缺 `collect_results`，实现后
  `tests/test_evaluate_phase66_runtime_convergence.py -q` 为 `8 passed`；CLI smoke 使用
  `output/phase66/evaluation/collect-smoke-observations.json` 输出 `review_required`，证明不完整收据不会伪装成
  pass。刷新后的 `output/phase66/evaluation/summary.json` 仍为 `review_required`，等待真实 A/B observation
  文件与人工验收。
- 2026-07-15 Codex 为 Phase66 evaluator 增加 HTTP observation 采集入口：
  新增 `data/evaluation/phase66_runtime_convergence_cases.csv`，包含 30 个 text case 和 4 个 image case；
  `--collect-http` 会向 `/agent/query` POST case，并只落盘安全字段：case_id、modality、HTTP status、工具名、
  citation/source/tool 计数、refused、elapsed_ms、error_category、completion_score，不落盘 prompt、answer、
  source text、provider payload、token 或凭据。TDD 红灯先失败于缺 `collect_http_observations`，实现后
  `tests/test_evaluate_phase66_runtime_convergence.py -q` 为 `12 passed`；不可达端口 full smoke 生成
  30 text + 4 image observation，`failed_case_count=34`、`unknown_error_count=0`、status=`review_required`，
  证明完整覆盖但失败的 observation 不会被标成 collected/pass。Phase66/evaluator focused 回归为
  `69 passed`，结构 gate 与 `git diff --check` 通过。
- 2026-07-15 Codex 采集 Phase66 本地 deterministic A/B runtime observation：
  创建 baseline worktree `G:\Codex\program\rfc-rag-agent-phase66-baseline`（detached `be23e215`），为
  A/B 各复制独立 SQLite，避免共享 `data/app.sqlite` 时的 `database is locked`。A 在 `127.0.0.1:8768`，
  B 在 `127.0.0.1:8769`，均显式关闭 auth/pgvector/rerank/BM25 warmup 并使用 deterministic
  chat/embedding/runtime_identity/vision provider。A/B query smoke 均成功。随后运行
  `--collect-http`：A 与 B 都完成 30 text + 4 image，`failed_case_count=0`、`unknown_error_count=0`；
  `--merge` 生成 `output/phase66/evaluation/summary.json`，其中 `paired_text_cases=30`、
  `paired_image_cases=4`，但 status 仍为 `review_required`、reason=`missing_phase66_quality_metrics`，
  因为当前 observation 只证明 runtime completion，不包含 answer_accuracy/citation_correctness/overall/judge
  指标。observation 文件敏感词扫描未命中 answer/source text/prompt/token/Authorization/Bearer；8768/8769
  自启服务已停止。
- 2026-07-15 Codex 更正 Phase66 A/B 验收边界：
  上述 SQLite A/B 只能作为本地隔离 runtime smoke，不能作为阶段 66 final acceptance。原因是主流/生产型
  Agent 证据应靠近实际 PostgreSQL/pgvector 拓扑；SQLite 会掩盖或改变 pgvector 检索、事务/锁行为、
  索引、迁移和真实语料一致性。后续 Phase66 最终质量/运行时 gate 应切换到 PostgreSQL/pgvector A/B；
  SQLite 结果仅保留为“服务可跑通且 evaluator 安全落盘”的辅助证据。
- 2026-07-15 Codex 为 Phase66 evaluator 增加内存态 judge 质量收据：
  `--collect-http --judge` 会在收到 `/agent/query` 响应后，把 answer/source/citation/refusal 仅作为内存请求发送给
  `/agent/judge`，observation 只落盘 `answer_accuracy_score`、`citation_correctness_score`、`overall_score`、
  `judge_status` 与安全错误类别，不落盘 answer/source/prompt/provider payload。TDD 新增测试确认敏感 answer/source
  被送入 fake judge 但不会写入 `observations.json`；judge 失败会计入 `judge_failed_count` 并保持
  `review_required`。验证：`tests/test_evaluate_phase66_runtime_convergence.py -q` 为 `14 passed`；
  Phase66/evaluator focused 为 `71 passed`；结构 gate 与 `git diff --check` 通过。当前尚未获得真实
  judge-backed A/B quality packet，因此 `output/phase66/evaluation/summary.json` 仍为 `review_required`。
- 2026-07-16 Codex 补齐 Phase66 PostgreSQL/pgvector final evidence：
  本机 dev PG 容器 `rfc-rag-postgres-dev` 使用 pgvector `0.8.3`，源库 `rfc_rag_dev` 具备
  `documents=1153`、`chunks=51738`、`chunk_embeddings=74067`、`embedding_vector rows=42051`。
  为避免 SQLite smoke 被误当 final evidence，创建独立 PG clone：
  `rfc_rag_phase66_a_20260716` 与 `rfc_rag_phase66_b_20260716`。baseline A（`be23e215`）跑
  A 库，candidate B 跑 B 库，服务端口 `8780/8781`；PG runtime-only A/B 均完成
  30 text + 4 image，`failed_case_count=0`、`unknown_error_count=0`，但因缺 judge metrics 仍
  `review_required`。随后按 TDD 修复 evaluator：judge payload 在内存态裁剪到
  `/agent/judge` schema 上限（answer <= 8000、sources <= 12、source content <= 1200、citations <= 50），
  并对 transient judge HTTP 429/5xx 最多重试 3 次；`tests/test_evaluate_phase66_runtime_convergence.py -q`
  更新为 `16 passed`。fixed PG judge-backed A/B 输出到
  `output/phase66/evaluation_pg_judge_fixed/`：A summary `overall=0.8264705882352942`、
  `answer_accuracy=0.7676470588235295`、`citation_correctness=0.6867647058823529`、
  `judge_failed_count=0`；B summary `overall=0.870343137254902`、
  `answer_accuracy=0.7948529411764705`、`citation_correctness=0.7823529411764706`、
  `judge_failed_count=0`。merge summary 为 `status=passed`、`paired_text_cases=30`、
  `paired_image_cases=4`、reason=`phase66_pairing_quality_non_regression`。安全扫描未命中
  Authorization/Bearer/api_key/provider payload/sensitive answer/source 样例；8780/8781 已停止。
- 2026-07-16 Codex 阶段 66 收口同步授权：
  用户要求严格按 `AGENT.MD / AGENTS.md` 执行本地 Git、GitHub PR/merge 与 Obsidian 阶段文件同步。
  本次收口范围是 Phase66 Tool Calling 真正瘦身、统一 coordinator 链路、PG/pgvector judge-backed
  非回归证据、固定常用 Agent 回归集、默认 Flash 修正、纯图检索延迟修复以及拒答展示策略修复。
  不重跑完整高成本 baseline，不提交 `output/` 运行产物，不提交 `.env`、密钥、provider raw response、
  raw answer、reasoning_content、完整 chunk 或私有日志。阶段 66 可进入 commit/PR/merge；Phase65
  holdout/judge 总门禁仍是独立事项，不随 Phase66 收口自动变为 pass。
