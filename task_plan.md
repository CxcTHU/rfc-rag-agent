# 当前执行计划

更新时间：2026-07-18

## Phase 67：CPU 服务器迁移

目标：以 GitHub 已合并的 Phase 66 版本为应用代码真相源，以现有 `rfc-cpu` 生产运行态为服务器
本地状态真相源，将 Agent、`.env.prod`、PostgreSQL、Redis 与 `data/` 运行资产整体迁移到新 CPU。

1. [x] 盘点新旧 CPU 的容量、Docker/Compose、部署目录、容器、网络、服务与资产规模。
2. [x] 在新 CPU 安装本机维护公钥，配置独立 `rfc-cpu-new` SSH 入口；旧 `rfc-cpu` 保持不变。
3. [x] 从 `origin/main` 生成不含 Git/本地脏改动的部署包并传到新 CPU。
4. [x] 在旧 CPU 生成一致性 PostgreSQL dump 与 Redis/运行资产迁移收据，不把凭据复制回本地。
5. [x] 通过旧 CPU 到新 CPU 的加密链路传输 `.env.prod`、数据库备份与 `data/` 资产。
6. [x] 在新 CPU 安装缺失依赖，恢复部署目录、PostgreSQL、Redis 与运行资产。
7. [x] 使用旧机已验证的相同镜像摘要启动生产 compose，确认 app 为 host network，DB/Redis 仅绑定回环地址。
8. [x] 执行脱敏内网 smoke：`/health`、前端、认证保护、代表性 Agent 查询、来源/图片原文打开，并核对关键计数。
9. [x] 更新 Phase 67 普通文档、Obsidian、工作记忆与交接；旧 CPU 在用户核验前保持在线作为回滚源。
10. [x] 补迁并切换 Cloudflare Tunnel：新 connector 建立 4 条连接，四个生产域名健康检查 200；旧 connector 已停止并禁用。
11. [x] 新机以独立身份加入 tailnet；`rfc-cpu-new` 已切到 Tailscale SSH 并验证，`rfc-cpu-new-public` 保留公网回退。
12. [x] 将稳定 `rfc-cpu` 维护别名切向新机；旧机保存为 `rfc-cpu-old`，并分别验证主机身份和 Agent 健康。
13. [x] 复核 live container 而不只检查宿主源码，识别首次迁移仍运行 Phase 66 之前的旧 app image。
14. [x] 从 GitHub merge tree 同步全部 Phase 66 runtime 文件，构建带 revision 的离线覆盖镜像并保留旧镜像回滚标签。
15. [x] 先做 18045 canary，再切生产 app；验证配置默认值、等待态、前端 asset、容器网络与健康状态。
16. [x] 执行脱敏真实 Agent + Judge smoke，并复核四域名、Cloudflare/Tailscale/provider forward 的 active/enabled。
17. [ ] 完成本地/Obsidian 阶段 67 收口、显式暂存、测试、安全扫描、GitHub PR/checks/merge。
18. [ ] 用户确认阶段 67 观察期结束后，决定何时清理旧机与迁移备份。

### Phase 67 错误记录

| 错误 | 尝试 | 处理 |
| --- | --- | --- |
| 旧 CPU 首次盘点命令的嵌套 SQL/SSH 引号被 PowerShell 提前解析 | 1 | 已改为 literal here-string 和拆分命令，主机盘点成功。 |
| tag 推送后的 `git show phase-66-complete^{commit}` 被 PowerShell 误解析 | 1 | 改用 `git rev-list -n 1 phase-66-complete` 验证目标为 `d86dd0e1`。 |
| 新机从 Docker Hub 拉取 Redis 镜像超时 | 1 | 从旧机加密直传并导入三份已验证镜像，镜像摘要与旧机完全一致。 |
| 用宿主源码标记和旧机镜像摘要误判 Phase 66 已上线 | 1 | 对比 host/live container/image creation/frontend asset，确认旧 app image 不含 Phase 66；改用带 Git revision 的独立镜像并验证 live container。 |
| 标准 Docker build 即使 `--pull=false` 仍查询 `python:3.11-slim` 并因 Docker Hub 超时失败 | 1 | 证明 Phase 66 无依赖声明变化后，以旧生产镜像为离线 base，只覆盖合并 runtime 文件；canary 通过后切换。 |
| `data/logs/request_traces.jsonl` 在旧机运行期间持续变化 | 1 | 将其按服务器本地易变日志处理；排除 `logs/` 后 durable data rsync dry-run 为零差异。 |
| readiness 脚本对 SaaS reranker 调用不存在的 `/health` 返回错误 | 1 | 不把该通用 private-BGE 探针作为 SaaS 门禁；改用真实认证 Agent 查询验证当前 provider/rerank 链。 |
| 将旧机公网入口误判为云安全组/NAT，而遗漏 Cloudflare Tunnel | 1 | 重新审计所有 system/user systemd 服务，定位 `cloudflared-rfc-rag-agent.service`；补迁后经四域名与 Nginx marker 验证切流。 |
| PowerShell 双引号命令提前执行 `$(...)`，首次临时公钥安装被本地 shell 解析 | 1 | 停止后续安装，确认真实 authorized_keys 路径后改用无命令替换的分步公钥写入。 |
| 新机复制的两个用户级 SSH 隧道持续连接超时 | 1 | 对照旧机日志发现同类服务已重启 1.7 万/3.2 万次；禁用失效单元，补上旧机真正工作的系统级 Python provider forward。 |

## Phase 66 验收后增量：低延迟生产默认提升

1. [x] 用 TDD 锁定干净环境下 short-loop、route-first、retrieval fan-out 默认开启。
2. [x] 将三个生产默认值提升为 true，并保留显式 false 的有界兼容覆盖。
3. [x] 同步 `.env.example`、README、架构与 Phase 66 review 的默认行为说明。
4. [x] 修正默认切换暴露的 complex-route identity、semantic cache 与统一 HyDE 测试合同。
5. [x] 使用无 shell 覆盖的普通 uvicorn 命令启动 8000，并从受保护健康契约验证默认值。
6. [x] 完整后端回归 `1936 passed, 1 skipped`；前端单测、lint、build 通过。
7. [x] 用户于 2026-07-18 明确授权本地、Obsidian、GitHub 与新 CPU 同步。
8. [x] 将验收后默认提升、最终模型等待态和验证边界同步到 Phase 66 Obsidian/评审/交接。
9. [x] 仅暂存 Phase 66 范围文件，并通过 staged diff 与敏感信息扫描。
10. [x] 提交并推送 Phase 66 验收后增量，创建 PR #43。
11. [x] GitHub 十项 checks 通过后合并 PR #43；创建并推送 `phase-66-complete` tag，目标 `d86dd0e1`。

### Phase 66 收口错误记录

| 错误 | 尝试 | 处理 |
| --- | --- | --- |
| 前端使用了不存在的 `npm test` script | 1 | 读取 `package.json` scripts 后改用仓库定义的测试命令，不重复该命令。 |
| Vite build 在 Windows 将 `frontend/dist/index.html` 写成 CRLF，`git diff --check` 报行尾空白 | 1 | 对该生成文件做一次机械 LF 归一化，再重跑 build 产物与 diff gate。 |
| 首次 LF 归一化命令中的 PowerShell 反引号被 JavaScript 模板字符串解析 | 1 | 改用 `[char]13/[char]10` 表达换行，归一化与 diff gate 成功。 |
| GitHub frontend check 在 `git diff --exit-code -- dist` 失败 | 1 | 已定位为 Windows build 产物 `frontend/dist/index.html` 比 Linux Vite 输出多一个空行；用户已批准删除该空行并重建/复核。 |
| `inspect_pr_checks.py` 在 Windows 用 GBK 解码 Actions UTF-8 日志失败 | 1 | 改用 `gh api` 读取具体 job 日志，成功取得根因；不重复该脚本路径。 |

## 当前阶段

Phase 65「Agent 真实质量门禁与 Runtime 模块化」正在主工作区执行。
用户已指定后续开发只在 `G:\Codex\program\rfc-rag-agent` 进行；不再以隔离
Phase65 worktree 作为开发位置。

## 已完成

1. [x] 65A Task 1：安全 manifest、工作树指纹与安全产物边界。
2. [x] 65A Task 2：可比较 manifest、盲评收据、质量/相对性能门禁。
3. [x] 65A Task 3：安全 A/B harness、运行时 cold-cache/usage 收据与模型库存。
4. [x] 65A Task 4：Stage30 stale gate、闭合 scope、v3 本地完整性测试收据。
5. [x] 将上述已审阅代码迁入主工作区；主工作区交叉回归 `129 passed`、完整回归
   `1598 passed, 1 skipped`，迁移复审通过。质量页/导出已统一 fail-closed，历史 Stage30
   PASS 不可绕过 stale gate。

## 当前外部验收门槛

65A Task 5（重构前真实 baseline）已按用户裁定视为完成，不再阻塞后续阶段。
2026-07-14 已验证：

- 完整旧 90 rows：`88/90 ok`；两个失败点随后已定向修复。
- 目标失败 case 复测：`phase64-followup-02` 与 `phase64-long-02`，2 cases × 3 runs =
  6 rows，`6/6 ok`，cold-cache receipt 全部 `valid`。
- 30 cases × 1 run = 30 rows：`30/30 ok`，cold-cache receipt 全部 `valid`。

provider 的安全 usage 不含 `cost`/`total_cost`，但用户已明确要求费用不作为当前阶段的
阻断条件。评测器现保留安全 token/耗时观测，并继续严格要求 cold-cache 隔离、检索契约与
运行正确性。不要再重跑完整 90 rows baseline，除非用户重新明确要求。价格快照/逐请求费用
收据改为后续可选增强。

## 65B 当前进度

- [x] 人工验收：用户已确认 Runtime / Tool-calling 拆解开发内容本身 PASS。验收范围是
  `RunCoordinator`、`ToolExecutor`、`EvidenceStateMachine`、`FinalAnswerController`、
  `CheckpointRepository`、`PlanningPolicy`、`RuntimeEventBus` 与 `final_result_assembler.py`
  对原 `tool_calling_service.py` 大主循环的职责拆分、默认 coordinator 接管和可测试性改进。
  唯一保留风险是拆解后的端到端延迟收益尚未稳定证明；该风险继续作为性能优化/holdout judge
  证据项处理，不阻断对“拆解开发内容”的人工认可。
- [x] Task 1：typed contracts 与闭合 stop-reason 映射。
- [x] Task 2：安全 RuntimeEventBus，兼容既有 SSE 投影且不污染首答案 token 指标。
- [x] Task 3：`PlanningPolicy` 已接管初始上下文组装、Route-First、identity、检索计划与诊断。
- [x] Task 4：`ToolExecutor` 已接管白名单工具分派、短路径、预检与图像补偿；短路径检索会透传 iteration/deadline/completed-tool guard；服务内执行与工具事件助手已移除。
- [x] Task 5：证据状态机已完成转移表，并接入短路径、模型工具循环与默认 `RunCoordinator` 生命周期；reranking/tool execution 错误、required figure/table 缺证、completed-tool replay、deadline/budget 耗尽均按闭合 stop reason fail-closed，最终 facade 只输出 bounded 用户可见拒答。
- [x] Task 6：`FinalAnswerController` 已接管非流式证据回答、流式 token/首答案计时、模型最终内容的本地引用校验/至多一次修复和流式后单次安全引用补救；并提供标准 `generate(FinalAnswerRequest) -> FinalAnswerOutcome` 合同和 `FinalAnswerOutcome` 构造。标准 `generate()` 会生成或流式生成最终回答、执行引用校验/修复、组装最终 `AgentQueryResult`，并在 provider 支持 streaming 时通过 `token_emitter` 发出完整最终回答 token 与本地安全引用后缀；`ToolCallingFinalAnswerFacade.generate()` 已改为薄委托。`FinalAnswerController.from_cached_evidence()` 与 `from_checkpoint()` 已接管 cached evidence / runtime checkpoint 恢复的最终回答生成与 result assembly，旧 service 兼容函数改为薄委托。旧 service 主循环中的 streaming final answer、evidence-convergence final answer、已有 model draft validate/repair 也已改为调用 controller 的命名入口（`stream_final_evidence()`、`generate_final_evidence()`、`validate_model_content()`），`tool_calling_service.py` 不再直接调用底层 `generate_evidence()` / `stream_evidence()` / `validate_or_repair()`。新增 `outcome_from_tool_calling_loop()` 兼容出口，旧主循环 9 个最终 answer/refuse 直接返回分支均已改为先构造标准 `FinalAnswerOutcome` 再返回 `result`，覆盖 evidence-convergence、model-final-answer、final-content-without-citations、iteration-limit、上传图片 legacy fallback、required-tool/preflight 无结果、短循环证据不足、reranking_failed、required figure evidence missing 等路径。`rg "return result_from_tool_calling_loop\(" app/services/agent/tool_calling_service.py` 已无命中；`RunCoordinator` 已能默认构造标准 `FinalAnswerRequest`。
- [x] Task 6a：`final_result_assembler.py` 已接管 tool-calling 最终 `AgentQueryResult` 装配、safe trace 计数、reasoning summary、pre-tool refusal、最终模型失败 fallback、cached-evidence 和 runtime-checkpoint 结果装配；旧 service helper 仅兼容委托或保留生成入口。
- [x] Task 7：`checkpoint_repository.py` 现拥有安全快照、run-store、resume 决策与序列化；`runtime_checkpoint.py` 已降为兼容导出，服务改从新边界导入。`ToolExecutor` 会拒绝重复的 completed tool ID；`RunCoordinator` 已能从 checkpoint 读取 completed tool IDs 并透传给执行边界；显式 `resume_run_id` 会通过 `CheckpointRepository.resume()` 复用既有 run，auto resume decision 选中 stopped run 时 service 也会把该 run id 透传给 `CoordinatorRequest`，因此 checkpoint 恢复/最终补答会落回同一个 runtime run，而不是新建 run 后再短路。相关 focused 回归 `90 passed`，默认 true 更宽 agent/API/runtime 回归 `295 passed`，完整后端回归 `1726 passed, 1 skipped`。
- [x] Task 8：`RunCoordinator` 已按证据决策区分回答、拒答和唯一一次升级，且第二次升级 fail-closed；工具执行请求会传递 iteration/deadline/completed-tool guard，并在工具执行后持久化安全的 `tool_execution_completed` checkpoint；多工具/升级场景下 `tool_execution_completed` 现在会累积既有 completed tool ids，不会因第二次检索覆盖第一次工具 id；最终 answer/refuse 会先写入 `final_answer_completed` / `final_answer_refused` 再 complete；并已新增可注入 `PreToolGateDecision` 入口门禁，在工具执行前可 fail-closed 返回并写最终 checkpoint。service 的 responsibility/off-topic 入口 gate 已前移到 checkpoint 创建之前，runtime resume 与 semantic evidence cache gate 仍在需要 run/checkpoint 的阶段执行；`ToolCallingCoordinatorGateAdapter` 已能把 service gate 注入 `RunCoordinator` 并在 resume gate 返回时把被恢复的旧 run 标记为 `resume_completed`。RunCoordinator 已支持 post-preflight gate、HyDE cache-miss builder、runtime policy-owned `tool_sequence`、required table/figure -> hybrid 文本补证、多工具合并、required-tool fail-closed、SSE 安全事件、stream token 透传、QueueStreaming 双写规避、completed-tool replay guard、预算耗尽 fail-closed、visual evidence counts 诊断、required figure/table 具体拒因、Phase64 fast-route 最小证据升级、final prompt trace/counters 和 legacy preflight 诊断别名事件。`AGENT_RUN_COORDINATOR_ENABLED` 现在默认 `true`：普通无上传图片 query 默认走 `RunCoordinator -> ToolExecutor -> EvidenceStateMachine -> ToolCallingFinalAnswerFacade`；上传图片仍安全 fallback 到 legacy 多模态路径；环境变量显式设为 `false` 可回退旧主循环。默认环境验证：service/stream/coordinator/evidence/tool-executor 中等回归 `108 passed`，`tests/test_agent_api.py` 为 `41 passed`，PowerShell 展开后的 `tests/test_phase65_*.py` 文件合集 `143 passed`，checkpoint resume 复用后更宽回归 `295 passed`，完整后端回归 `1726 passed, 1 skipped`，相关 `py_compile` 通过，`git diff --check` 仅 CRLF 提示。

## 后续顺序

1. 65B 后端 Runtime 模块化与默认 `RunCoordinator` 接管已完成到完整后端回归通过；不要再重复 90-row baseline，除非用户重新明确要求。
2. 65C Task 1 已完成候选侧 contract snapshot：新增安全快照脚本/测试和 `data/evaluation/phase65_contract_snapshot.json`，focused contract 回归 `27 passed`。
3. 65C Task 2 已完成真实 topology gate：dev Postgres/pgvector、Redis Stack、auth register/login/me、checkpoint roundtrip 和 authenticated Agent SSE probe 全部 `pass`，`output/phase65/topology-8011.json` 为安全本地产物。
4. 65C Task 3 已推进到 bounded module-boundary injection 与真实 API/SSE recovery smoke：
   `scripts/run_phase65_fault_matrix.py`
   现在默认通过真实 `RunCoordinator` / `ToolExecutor` / `EvidenceStateMachine` /
   checkpoint / pre-tool gate 注入 9 类 fault，并且 `--concurrency/--requests`
   会真实调度本地并发注入请求，而不是只写配置字段。当前安全
   `data/evaluation/phase65_fault_summary.json` 为 `execution_mode=bounded_module_boundary_injection`、
   `runtime_injection_coverage=core_runtime_faults`、`case_count=80`、
   `runtime_injected_case_count=80`、`bounded_load_completed_requests=80`、
   `bounded_load_failed_requests=0`、`bounded_load_max_inflight_observed=8`。
   本轮还修复了 planner 异常早于 `try/finally` 导致 LatencyTrace 泄漏的问题。
   `scripts/probe_phase65_runtime_recovery.py` 与
   `tests/test_phase65_runtime_recovery_smoke.py` 已补真实 API/SSE cancel-resume
   recovery smoke；受控 `127.0.0.1:8011` 下
   `output/phase65/runtime-recovery-8011.json` 为 `gate=pass`，
   `sse_cancel_marks_stopped=pass`、`resume_sse_from_checkpoint=pass`、
   `failed_required=[]`，且该文件为本地安全产物，不应提交。
5. 65C Task 4 已启动 paid paired A/B 执行前门禁：`scripts/phase65_agent_gate.py`
   新增 `build_paired_execution_preflight()`，`scripts/evaluate_phase65_agent_gate.py`
   在 paired summary 中输出安全 preflight，并默认要求显式
   `--authorize-paid-run` 与 contract/topology/fault gate 状态均为 `pass` 后才允许
   `--execute`。本地 dry-run `output/phase65/paired-preflight-dry-run.json` 显示
   contract/topology/fault 已标为 `pass`，但因 dry-run manifest 不是 complete/cold 且
   `paid_execution_not_authorized`，`gate=blocked`、`ready_to_execute=false`。这一步没有访问 API，
   没有跑 baseline。
6. 65C Task 6 的最终验收汇总层已提前启动：`scripts/summarize_phase65_acceptance.py`
   与 `tests/test_phase65_acceptance_summary.py` 会把 contract/topology/fault/recovery/paired
   preflight/paired full/holdout/human acceptance 汇总为单个 fail-closed 安全 summary。
   本地 `output/phase65/acceptance-preflight-summary.json` 当前为 `gate=blocked`：
   contract/topology/fault/recovery/endpoint readiness/paired execution preflight 为 `pass`，
   但 paired full、holdout 和 human acceptance 仍 `missing`。该汇总没有把 smoke 冒充 full，
   没有跑 baseline，且不含 prompt、答案、证据正文、provider payload 或密钥。
7. 65C Task 4 endpoint readiness 已打通：`evaluate_phase65_agent_gate.py`
   的 `--preflight-only --auto-auth` 现在可在本地 loopback endpoint 公开注册关闭时，自动
   bootstrap 一个短期 admin 评测账号并只在内存中使用 token；`/health/retrieval-contract`
   已从 production admin-only 收敛为 authenticated-only，`/health/details` 仍保持 admin-only。
   另新增 `PHASE65_ENDPOINT_IDENTITY_LABEL`，只把 label hash 纳入 endpoint identity，不输出
   原文；candidate 8011 已用 `candidate` lane label 重启。最新
   `output/phase65/paired-endpoint-readiness.json` 为 `endpoint_readiness.gate=pass`：
   baseline/candidate 的 auto-auth、contract fetch、endpoint identity、index fingerprint、
   cold-run receipts 和 model inventory 均为 `pass`，且 endpoint identity distinct 为 `pass`。
   没有执行 case、没有重跑 baseline。
8. 65C Task 4 bounded judged smoke 已跑通 endpoint+manifest preflight：2 cases × 2 lanes =
   4 rows 全部 `ok=True`，cold-cache receipt 均为 `valid`，paired execution preflight 为 `pass`。
   本轮还修复了两个 smoke 暴露的问题：token/cost 缺失不再导致 `paired_rows_incomplete`
   （ratio 保持 null），judge fenced JSON / nested `deltas` 可解析；judge provider 空 content
   会被记录为安全 `blind_judge_provider_failed` 并 fail-closed 写入 summary，而不是让 evaluator
   崩溃。当前 `output/phase65/paired-judged-smoke-v3-summary.json` 中 contract gate 为 `pass`，
   但 quality/runtime/Phase65 acceptance 仍 blocked：1 个 judge provider failure，且 2-case smoke
   不等同 full paired A/B。
9. 下一步继续 65C Task 4：准备正式 paired full A/B 与 holdout/human acceptance；随后进入
   前端/流式 UI 与最终人工验收。
   不要再重跑完整 90-row baseline，除非用户重新明确要求；费用快照/逐请求 provider cost 收据作为
   后续可选增强，不阻断当前阶段。

## 2026-07-15 Codex 追加：65C candidate targeted correction

- [x] 修复 `phase64-followup-02` candidate-only 失败：根因不是工具路由，而是视觉 follow-up 的
  `search_figures` 召回过度依赖 vector-only 候选；已为 `search_figures` 增加 keyword
  `image_description` 候选兜底，并继续走原有图片质量、去重、specific/relaxed 过滤。
- [x] 保持正式 paired judge 严格性：`JudgeReceiptContract` 默认仍要求 A/B 匿名映射双向均衡；
  仅 candidate/baseline 单 lane `--case-id` targeted retry 且未执行 blind judge 时，允许
  `require_balanced_mapping=False` 的 lane-only receipt contract，避免单行修复被 judge 合同误挡。
- [x] 只重测 `phase64-followup-02` candidate：`output/phase65/candidate-followup02-rerun-results.csv`
  显示 `ok=True`、`expected_tool=search_figures`、`citation_count=6`、`selected_count=12`、
  `live_selected_count=12`、`counts_match=True`、`refused=False`、cold-cache receipt `valid`。
- [x] 更新 corrected candidate 与复用 baseline 的安全证据：`candidate-30x1-corrected-results.csv`
  现为 30/30 `ok=True`；`paired-reuse-baseline-30x1-corrected-results.csv` 合并通过，
  baseline 30/30、candidate 30/30。
- [ ] 严格 Phase65 paired full gate 仍未通过：`paired-reuse-baseline-30x1-corrected-summary.json`
  当前 `phase65_acceptance=blocked`，唯一 manifest comparison 原因为
  `evaluator_sha256_mismatch`。这是复用旧 baseline + targeted candidate correction 的真实边界；
  不应伪造成正式 full A/B pass。若用户坚持严格 pass，必须在同一 evaluator/manifest 下跑正式
  paired full，或先设计并接受“baseline reuse waiver”规则。
- [x] 修正 acceptance/holdout 语义：
  `scripts/summarize_phase65_acceptance.py` 现在区分 `paired_full_summary_missing` 与
  `paired_full_gate_not_pass`，不会把已存在但 blocked 的 paired summary 误报成 missing。
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 现在要求 baseline/candidate 两个
  endpoint、要求 endpoint distinct，并按 A/B 双 lane 排程；未显式传 `--runs` 时 holdout 默认为
  每 case 一次 A/B observation，避免继承 public paired/baseline 的 3-run 默认。
- [x] 补齐 holdout blind judge receipt 语义：
  `--mode holdout --execute --execute-blind-judge` 现在会在 baseline/candidate answer pair
  完整时生成 safe judge rows，并把 `judge_summary` 写入 `holdout_summary`。Acceptance summary
  现在要求 holdout summary 同时具备 clean A/B rows、≥12 case、tuning/primary-latency exclusion
  proof，以及 matched holdout judge summary；缺 judge summary 会 blocked，不会被当作 pass。
- [x] 落地 baseline reuse waiver，避免反复重跑已完成 baseline：
  新增 `scripts/build_phase65_baseline_reuse_waiver.py` 与
  `phase65-baseline-reuse-waiver-v1` 安全收据。该 waiver 必须显式带
  `--user-authorized-baseline-reuse`，且只在 paired summary 唯一 blocker 为
  `evaluator_sha256_mismatch`、baseline/candidate 30 个 case-run 完全对齐、两侧 row 均
  `ok=True` 且无错误类别/重放异常时 pass；其它 blocked 原因不能被豁免。
  当前 `output/phase65/baseline-reuse-waiver-30x1-corrected.json` 为 `gate=pass`，
  baseline/candidate 各 30、`failed_required=[]`。Acceptance summary 现在记录
  `evidence_substitutions=["baseline_reuse_waiver_for_paired_execution_preflight",
  "baseline_reuse_waiver_for_paired_full_gate"]`，因此不再把旧 dry-run preflight 或
  corrected paired summary 的 `evaluator_sha256_mismatch` 作为继续推进阻断；但
  `paired_full_gate` 本身仍显示 `blocked`，不伪造成正式 full A/B pass。
- [x] baseline reuse 后的 acceptance 状态曾短暂剩余
  `holdout_summary_missing` 与 `human_acceptance_missing`；下一项已把缺私有 holdout 集推进为
  显式 blocked receipt，因此不再是 missing。
- [x] 产出缺私有 reviewer holdout 集时的显式 blocked receipt：
  新增 `scripts/build_phase65_holdout_blocked_summary.py` 与
  `phase65-holdout-blocked-summary-v1`。当 `data/evaluation/phase65_private_holdout_cases.csv`
  不存在或不可用时，脚本只写安全状态摘要，不接触 provider、不保存 prompt/answer/evidence。
  当前 `output/phase65/holdout-blocked-missing-private-cases.json` 为 `gate=blocked`，
  `failed_required=["private_holdout_cases_missing"]`，`holdout_case_count=0`。
  刷新后的 `output/phase65/acceptance-preflight-summary.json` 现在把 holdout 从 `missing`
  推进为 `blocked`，剩余 required blockers 为 `holdout_gate_not_pass` 与
  `human_acceptance_missing`。
- [ ] 当前 Phase65 acceptance 仍未最终通过：reviewer holdout 需要真实私有 holdout case set 后
  执行 baseline/candidate A/B + blind judge；human acceptance 仍需用户人工验收记录。
- [x] 产出 human acceptance pending packet：
  新增 `scripts/build_phase65_human_acceptance_packet.py` 与
  `phase65-human-acceptance-packet-v1`。该 packet 从当前 acceptance summary 生成，记录
  验收 checklist、acceptance summary hash、当前 failed_required 与下一步动作；不写 prompt、
  answer、evidence 正文、provider raw payload 或密钥。当前
  `output/phase65/human-acceptance-pending-packet.json` 为 `gate=blocked`、
  `status=pending_user_review`。刷新后的
  `output/phase65/acceptance-preflight-summary.json` 中 `human_acceptance` 已从 `missing` 推进为
  `blocked`，当前 required blockers 为 `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- [ ] 当前 Phase65 acceptance 仍未最终通过：下一步需要真实 reviewer holdout pass，以及用户基于
  human acceptance packet 明确记录 pass/fail。
- [x] 产出 human acceptance recorder：
  新增 `scripts/record_phase65_human_acceptance.py` 与
  `phase65-human-acceptance-record-v1`。该 recorder 只接受显式 `--decision pass|fail` 与
  `--confirm-checklist`，并且默认禁止在任何非 human gate 仍 open 时记录 `pass`。当前用
  `output/phase65/human-acceptance-pending-packet.json` 尝试 `--decision pass` 被正确拒绝，
  输出安全 JSON：`error_category=cannot_pass_with_open_non_human_gates`，且未写出误签 record 文件。
- [ ] 当前 Phase65 acceptance 仍未最终通过：必须先解决 `holdout_gate_not_pass`，随后由用户
  基于 packet/recorder 明确记录 human acceptance。
- [x] 产出 private holdout intake/template：
  新增 `scripts/prepare_phase65_holdout_intake.py` 与 `phase65-holdout-intake-v1`。脚本生成
  header-only 模板 `output/phase65/phase65_private_holdout_cases.template.csv` 和 intake packet
  `output/phase65/holdout-intake-packet.json`；模板 `template_is_executable=false`，直接校验会
  blocked，避免误当真实 holdout 运行。validator 要求至少 12 个唯一 case、非空 question，生成
  `phase65-holdout-intake-validation-v1`。当前真实
  `data/evaluation/phase65_private_holdout_cases.csv` 仍不存在，未伪造。
- [x] 产出 Phase65 closeout audit：
  新增 `scripts/audit_phase65_closeout.py` 与 `phase65-closeout-audit-v1`，汇总
  acceptance summary、holdout intake 与 human acceptance packet。当前
  `output/phase65/closeout-audit.json` 为 `gate=blocked`、`ready_for_closeout=false`，
  components 为 acceptance/holdout intake/human packet 均 `blocked`，failed_required 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。该 audit 是当前阶段能否收口的
  单一安全摘要入口。
- [x] 加强 private holdout intake 的去重/隔离门禁：
  `scripts/prepare_phase65_holdout_intake.py` 的 validator 现在支持 `--exclude-cases`
  （默认 `data/evaluation/phase64_latency_cases.csv`），会拒绝与公开/已用 case_id 重叠的
  private holdout，错误为 `holdout_overlaps_excluded_cases`。这防止把 public baseline cases
  复制成 reviewer holdout。当前模板仍只是 header-only，真实
  `data/evaluation/phase65_private_holdout_cases.csv` 仍不存在。
- [x] 将 private/public overlap guard 下沉到 evaluator 本体：
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 现在会把 `--cases`（默认
  `data/evaluation/phase64_latency_cases.csv`）作为 holdout 排除集传入
  `validate_holdout_cases()`；即使绕过 intake 直接跑 evaluator，private holdout 与 public/frozen
  case_id 重叠也会被拒绝为 `holdout_overlaps_public_cases`。当前真实
  `data/evaluation/phase65_private_holdout_cases.csv` 仍不存在，未执行 holdout。
- [x] 将 public/frozen overlap proof 纳入 holdout acceptance：
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 生成的 `holdout_summary` 现在写入
  `public_overlap_exclusion_proven`、`excluded_case_count` 与 `excluded_case_set_sha256`；
  `scripts/summarize_phase65_acceptance.py` 现在要求这些字段存在且有效后，才允许
  `holdout_gate=pass`。因此旧的或手写的 holdout summary 即使 clean/judge 通过，也不能缺少
  public/frozen 排除证明。当前 acceptance/closeout 刷新后仍如实 `blocked`，剩余 blockers 为
  `holdout_gate_not_pass` 与 `human_acceptance_not_pass`。
- [x] 将 real execution proof 纳入 holdout acceptance：
  `holdout_summary` 现在写入 `execution_mode` 与 `executed_ab_row_count`；
  `scripts/summarize_phase65_acceptance.py` 要求 `execution_mode=real_api` 且
  `executed_ab_row_count >= holdout_case_count * 2`，才允许 holdout gate pass。dry-run 或缺少
  执行证明的旧格式 summary 即使其它字段看起来 clean，也只能 blocked。当前未执行真实 private
  holdout，acceptance/closeout 仍如实 `blocked`。
- [x] 将 holdout A/B lane completeness 纳入 acceptance：
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 现在写入
  `baseline_ab_row_count` 与 `candidate_ab_row_count`；`scripts/summarize_phase65_acceptance.py`
  要求两条 lane 都等于 `holdout_case_count`。仅有总 `executed_ab_row_count` 足够、但缺少任一 lane
  完整覆盖证明时，`holdout_gate` 仍为 blocked。
- [x] 将 holdout A/B lane case-set hash 纳入 acceptance：
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 现在写入
  `baseline_ab_case_set_sha256` 与 `candidate_ab_case_set_sha256`；
  `scripts/summarize_phase65_acceptance.py` 要求两条 lane 的 case-set hash 都等于
  `holdout_case_set_sha256`。这防止总数和 lane 数都正确、但 baseline/candidate 覆盖不同 case 集的
  holdout summary 被误收。
- [x] 将 holdout A/B lane case-set hash 纳入 closeout：
  acceptance pass summary 现在会携带 `baseline_ab_case_set_sha256` 与
  `candidate_ab_case_set_sha256`；`scripts/audit_phase65_closeout.py` 在最终收口时二次要求两者都
  等于 `holdout_case_set_sha256`。这避免最终 closeout 只看总 case-set hash、漏掉 lane 覆盖不一致。
- [x] 将 holdout blind-judge summary schema 与 receipt contract hash 纳入 acceptance：
  `scripts/judge_phase65_agent_gate.py` 的 `summarize_judge_rows()` 现在写入
  `schema_version=phase65-judge-summary-v1` 与 `receipt_contract_sha256`；
  `scripts/summarize_phase65_acceptance.py` 要求 holdout `judge_summary` 具备正式 schema、
  `judge_expected_pairs == holdout_case_count`、case-set hash 匹配和合法 receipt contract hash 后，才允许
  `holdout_gate=pass`。旧格式或手写聚合分数字段不能伪装成 blind judge receipt。
- [x] 将 holdout blind-judge receipt contract hash 纳入 closeout：
  acceptance pass summary 现在会透出 `holdout_judge_receipt_contract_sha256`；
  `scripts/audit_phase65_closeout.py` 在最终收口的 acceptance summary 自检中要求该字段为合法 SHA-256。
  这避免最终 closeout 只看 `holdout_gate=pass` 标签，而没有任何 blind-judge receipt 绑定证明。
- [x] 将 reviewer holdout case count 纳入 acceptance/closeout 绑定：
  acceptance pass summary 现在会透出 `holdout_case_count`；`scripts/audit_phase65_closeout.py`
  要求 `phase65-holdout-intake-validation-v1.holdout_case_count` 与 acceptance summary 中的
  `holdout_case_count` 完全一致。最终收口不能只依赖 case-set hash，还必须保留明确的 reviewer case
  数量证明。
- [x] 将 reviewer holdout 真实执行证明纳入 acceptance/closeout 绑定：
  acceptance pass summary 现在会透出 `holdout_execution_mode=real_api`、
  `holdout_executed_ab_row_count`、`holdout_baseline_ab_row_count` 与
  `holdout_candidate_ab_row_count`；`scripts/audit_phase65_closeout.py` 要求总执行行数至少为
  `holdout_case_count * 2`，且 baseline/candidate 两条 lane 行数都等于 `holdout_case_count`。最终收口不能
  只凭 hash 和 pass 标签缺失真实执行规模证明。
- [x] 将 reviewer holdout public/frozen overlap 排除证明纳入 acceptance/closeout 绑定：
  acceptance pass summary 现在会透出 `holdout_excluded_case_count` 与
  `holdout_excluded_case_set_sha256`；`scripts/audit_phase65_closeout.py` 要求二者合法存在。最终收口不能
  丢失“private holdout 已排除 public/frozen cases”的安全证明。
- [x] 将 holdout summary schema version 纳入 acceptance：
  `scripts/evaluate_phase65_agent_gate.py --mode holdout` 现在生成
  `schema_version=phase65-holdout-summary-v1`；`scripts/summarize_phase65_acceptance.py` 要求该
  schema 后才允许 `holdout_gate=pass`。旧格式或手写字段集合即使具备 clean、real_api、judge 等
  pass-looking 字段，也只能 blocked。
- [x] 将 human acceptance pass record 绑定到当前 pre-human acceptance summary：
  `scripts/summarize_phase65_acceptance.py` 现在会用当前非 human 证据计算 canonical pre-human
  acceptance summary hash，并要求 `phase65-human-acceptance-record-v1` 中的
  `acceptance_summary_sha256` 与之匹配。旧 packet/旧 summary 上签出的 human pass record 不能复用到
  新证据状态。当前没有有效 pass record，acceptance/closeout 仍如实 `blocked`。
- [x] 收紧 human acceptance recorder 字段校验：
  `scripts/summarize_phase65_acceptance.py` 现在要求 human gate pass 的 summary 除 hash 匹配外，还必须
  具备 recorder 产生的 `status=accepted`、`decision=pass`、`review_checklist_confirmed=true`、
  `open_non_human_gate_count=0` 与非空 `reviewer_label`。手写极简 accepted summary 不能让 human
  gate pass。
- [x] 将 human acceptance recorder 签字动作绑定到当前 acceptance summary：
  `scripts/record_phase65_human_acceptance.py` 现在支持 `--current-acceptance-summary`，且 `pass`
  决策必须提供当前 summary；packet 中的 `acceptance_summary_sha256` 必须与该文件 hash 匹配，否则
  拒绝为 `human_acceptance_summary_mismatch`。这把防陈旧签字从最终 summarize 提前到了签字动作本身。
- [x] 移除裸 human acceptance pass 旁路：
  `scripts/summarize_phase65_acceptance.py` 现在不再允许 `human_acceptance="pass"` 或 CLI
  `--human-acceptance pass` 直接让 human gate 通过；pass 只能来自带 hash 绑定的
  `phase65-human-acceptance-record-v1`。`--human-acceptance fail` 仍保留用于显式记录拒绝/失败状态。
- [x] 收紧 closeout audit 的 human acceptance artifact：
  `scripts/audit_phase65_closeout.py` 现在要求 closeout 支撑的 human artifact 必须是
  `phase65-human-acceptance-record-v1`，且 nested `human_acceptance_summary` 为
  `gate=pass/status=accepted`。普通 packet 或错误格式的 `gate=pass` 不再能让 closeout 的
  `human_acceptance_packet` component 通过。
- [x] 收紧 closeout audit 的 human recorder 字段校验：
  closeout 现在也要求 nested `human_acceptance_summary` 具备 recorder 字段：`decision=pass`、
  `review_checklist_confirmed=true`、`open_non_human_gate_count=0`、非空 `reviewer_label` 与合法
  `acceptance_summary_sha256`。手写 accepted record 即使 hash 匹配，也不能让 closeout ready。
- [x] 将 closeout human artifact 绑定到 acceptance summary 使用的 human receipt：
  `scripts/summarize_phase65_acceptance.py` 在 human gate pass 时写入
  `human_acceptance_summary_sha256`；`scripts/audit_phase65_closeout.py` 会重新计算传入
  human record 的 nested `human_acceptance_summary` hash 并与 acceptance summary 比对。closeout
  不能用另一个 accepted record 替换 acceptance summary 实际使用的 human receipt。
- [x] 将 closeout holdout intake 绑定到 acceptance summary 使用的 holdout case set：
  `scripts/summarize_phase65_acceptance.py` 在 holdout gate pass 时写入
  `holdout_case_set_sha256`；`scripts/audit_phase65_closeout.py` 会要求传入的
  `phase65-holdout-intake-validation-v1` 的 `holdout_case_set_sha256` 与 acceptance summary 匹配。
  closeout 不能用另一个 pass intake validation 替换实际通过 acceptance 的 holdout case set。
- [x] 收紧 closeout acceptance summary 内部结构校验：
  `scripts/audit_phase65_closeout.py` 现在要求 pass acceptance summary 同时具备
  `phase65_acceptance=pass`、空 `failed_required`、关键 components 为 pass，以及 paired full
  pass 或显式 baseline reuse substitution。极简手写 `gate=pass` 摘要不能让 closeout ready。
- [x] 收紧 closeout holdout intake case-count 校验：
  closeout 现在会在 `phase65-holdout-intake-validation-v1` 层再次要求
  `holdout_case_count >= 12`。即使 intake 顶层是 `gate=pass`、`ready_to_run_holdout=true` 且
  case-set hash 与 acceptance summary 匹配，case 数不足也不能让 closeout ready。
- [x] 收紧 closeout holdout intake public-overlap 校验：
  closeout 现在会二次要求 `phase65-holdout-intake-validation-v1` 的
  `excluded_case_overlap_count == 0`。即使 intake 顶层 pass、case 数达标且 case-set hash 匹配，
  只要 public/frozen overlap 计数非零，也不能让 closeout ready。
- [x] 收紧 closeout holdout intake required-columns 校验：
  closeout 现在会二次要求 `phase65-holdout-intake-validation-v1` 的 `required_columns` 精确等于
  `HOLDOUT_TEMPLATE_FIELDS`。缺少列契约或手写最小 pass intake 不能让 closeout ready。
- [x] 建立并执行真实 Phase65 private holdout A/B：
  已新增 12 条 `data/evaluation/phase65_private_holdout_cases.csv`，通过 intake validation 且与
  `data/evaluation/phase64_latency_cases.csv` 无 case_id 重叠。真实 holdout 使用 baseline
  `127.0.0.1:8001` 与 candidate `127.0.0.1:8011`，产出 24/24 clean real A/B rows，baseline/candidate
  lane 都完整覆盖 12 条 case，cold-cache receipt 均 valid。当前 `holdout_gate` 仍未 pass，原因从
  “缺私有 holdout / 未执行”变为“blind judge evidence 不完整且 lower-bound 未证明 candidate 优势”。
- [x] 加固 holdout evaluator 的执行字段与 judge 稳定性：
  `validate_holdout_cases()` 现在会把 intake 模板的 `question` 映射为底层执行器的 `query`；blind judge
  增加最多 3 次安全重试，并对 transient judge 输入做有界裁剪，不落盘原始 answer 或 provider payload。
  这提升了 receipt 形成率，但第三轮仍只有 5/12 judge receipts，说明后续需要继续处理 judge provider
  稳定性或选择更可靠的 judge 路径。

## Git 边界

未经用户人工核验与明确授权，不暂存、提交、tag、push、PR 或合并。

## Phase 66 当前任务状态

- [x] 完成 Tool Calling 真正瘦身：`tool_calling_service.py <= 260 lines`、
  `ToolCallingAgentService.query <= 80 lines`、`run_coordinator.py <= 120 lines`。
- [x] 删除生产 `agent_run_coordinator_enabled` 分叉；回退策略为 rollback through Git。
- [x] 保留四个生产工具：`hybrid_search_knowledge`、`search_tables`、`search_figures`、
  `analyze_user_image`。
- [x] 本地验证收据已生成：
  `output/phase66/final/runtime-structure.json`、
  `output/phase66/final/fault-matrix.json`、
  `output/phase66/final/runtime-recovery.json`。
- [x] 建立固定常用 Agent 回归集：
  `data/evaluation/agent_regression_cases.csv`，覆盖 30 text + 4 image，并让 evaluator
  输出 expected/forbidden tool、source/citation/refusal/latency contract violations。
- [x] 修复本轮人工发现的拒答展示策略：用户可见答案说明项目范围、拒答原因和可改问方向，
  内部仍保留 `refusal_category=off_topic` 等机器字段。
- [x] PostgreSQL/pgvector judge-backed A/B 质量包已通过：
  `output/phase66/evaluation_pg_judge_fixed/` 中 A/B 各 30 text + 4 image，query/judge failure
  均为 0，B overall `0.870343137254902` >= A overall `0.8264705882352942`。
- [x] 用户于 2026-07-16 授权阶段 66 收口同步：允许按 AGENT.MD 边界执行本地 commit、
  GitHub PR 与检查通过后的 merge。
- [ ] 仍需诚实保留的边界：不把 SQLite A/B smoke 当 final evidence；不把小样本/定向 latency
  修复夸大为完整高成本 latency release gate；Phase65 holdout/judge 总门禁仍是独立事项。
