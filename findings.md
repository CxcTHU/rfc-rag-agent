# Phase 67 增补：步骤持久化 E2E 与同步发现

更新时间：2026-07-19

- 当前修复分支为 `codex/fix-workflow-step-persistence`，基于已合并 Phase 67 的 `origin/main`。
- 已有修复把安全 SSE 运行步骤保存到独立 `runtime_workflow_steps`，前端会话恢复优先使用该字段；最终 `workflow_steps` 与 `tool_calls` 的既有语义不变。
- 四端同步授权已由用户明确给出，但必须先通过小型 E2E 评测和 fresh 收口门禁。
- 既有 Phase 64 Obsidian 格式变更、`.playwright-cli/`、`output/` 与根目录截图不属于本增补，禁止暂存或覆盖。
- 新 CPU 稳定维护入口为 `rfc-cpu`（Tailscale），部署目录为 `/home/ubuntu/rfc-rag-agent-stage44-smoke`；公网入口继续由 Cloudflare Tunnel 提供。
- 现有 Playwright 使用 `frontend/e2e/mock-server.mjs` 在 4173 提供合成认证、会话、SSE 和静态生产包，测试为单 worker Chromium；可直接扩展，无需接触真实服务或真实数据。
- 当前 mock SSE 实时发送 planning + tool start/result，但持久化 metadata 仍只有两条 `workflow_steps`，恰好可作为本 bug 的旧行为对照；修复后的 E2E fixture 应增加独立 `runtime_workflow_steps`。
- `ThinkingPanel` 的完成态摘要稳定暴露“`N 个真实步骤`”，展开后每步为 `.thinking-step`；可在 reload 前后同时比较数量和标签序列。
- Auth logout 会清空 TanStack Query cache，而 active conversation id 单独保存在 localStorage；“退出后重新登录”可作为比单纯 reload 更强的数据库恢复路径，验证前端不依赖旧内存 events。
- 小型集合采用三类恢复路径：新合同 6 步 + 页面 reload、新合同无来源路径 + logout/login cache 清空、旧 metadata 合同 2 步兼容回退；每例均比较恢复前后的步骤数与展开标签序列。
- 首个单例 E2E 红灯得到刷新前 3 步、刷新后 2 步，证明测试能捕获原缺陷。
- 新增 `workflow-persistence-cases.json` 后，Chromium 评测为 `3 passed`：6-step reload、4-step reauth/cache reset、legacy 2-step fallback 均保持恢复前后数量与标签序列一致。

# Phase 67 CPU 迁移补正已验证事实

更新时间：2026-07-18

- Phase 66 最终本地 tree `d86dd0e1^{tree}` 与 GitHub merge commit `1af07fc1^{tree}` 均为
  `40867422d7f7d830e22c7c845c49f36c2b4c3aff`；增补提交 `999dbda4` 与 `d86dd0e1` 没有遗漏。
- 首次迁移 app image `79aec024f642` 创建于 2026-07-14，容器内无 `agent_default_chat_model`，仍服务
  `index-pLE_BYIm.js`；宿主机源码存在 Phase 66 标记不能证明运行容器已更新。
- Phase 66 相对 Phase 65 无 `pyproject.toml` 差异。Docker Hub 超时后，以旧镜像为离线依赖 base、
  覆盖 GitHub 合并 runtime 文件是有界且可验证的替代构建路径。
- 当前 live image 为 `rfc-rag-agent:phase66-1af07fc1` / `1296fcc926a0`，OCI revision 为完整
  `1af07fc145e32ed2cbf1a79d59f0877d802c408d`；旧镜像保留 `pre-phase66-79aec024` 标签。
- canary 与 live container 均确认 short-loop、route-first、retrieval fan-out 为 true，默认 Agent
  模型为 `deepseek-v4-flash`，`final_answer_generating` 与 `index-DDE0lgzL.js` 存在。
- 生产 app/db/redis healthy；app 为 host network，DB/Redis 仍只绑定回环。脱敏真实 Agent 为
  200、3 citations/12 sources，Judge 为 200/completed；未保留答案、token、provider raw response
  或 reasoning。
- 四个生产域名 `/health` 均 200，公网前端服务 `index-DDE0lgzL.js`。Cloudflare、Tailscale 和 provider
  forward 均 active/enabled；旧 Cloudflare connector inactive/disabled。
- Tailscale 服务具备 systemd 持久化，但节点 key 当前到期时间为 2027-01-14；若要长期免维护连接，
  需在 Tailscale 管理台关闭该节点 key expiry。新 CPU 尚无经验证的定时异机备份。

# Phase 65 规划期已验证事实

更新时间：2026-07-14

## 当前 Runtime

- `app/services/agent/tool_calling_service.py` 当前为 2,823 行，
  `ToolCallingAgentService` 从第 226 行开始，`query()` 从第 256 行开始。
- `app/services/retrieval/hybrid_search.py` 当前为 1,970 行。Phase 65 只在建立稳定
  Runtime 边界所需处触及它，不据此认定检索算法需要整体重写。
- 当前 Runtime 并非全部写在一个 tool calling 文件里；`runtime.py`、
  `runtime_checkpoint.py`、`evidence_identity.py`、`route_first.py`、`tools.py`
  和 `latency_trace.py` 已承担部分支持能力，但请求生命周期与多项策略仍集中在
  `ToolCallingAgentService.query()`。

## Phase 66 发现

- Phase 65 的模块化方向正确，但 `tool_calling_service.py` 仍承担过多编排、prompt、gate、merge
  与兼容职责；阶段 66 已把这些职责继续外移，让主服务成为薄门面。
- 生产 `agent_run_coordinator_enabled` 这类双路径开关会让后续 agent 接班时误判真实入口；阶段 66
  已将其 deleted，并明确 rollback through Git。
- 当前主流 agent 工程方向更接近“一个 coordinator + typed tool registry + adapter ports”，而不是
  在服务层保留多套 loop。阶段 66 的四工具库存为 `hybrid_search_knowledge`、`search_tables`、
  `search_figures`、`analyze_user_image`。
- 本地结构与回归验证已通过：`tool_calling_service.py <= 260 lines`、
  `ToolCallingAgentService.query <= 80 lines`、`run_coordinator.py <= 120 lines`。早期 SQLite
  runtime smoke 仍只能视为辅助证据，不能作为 final acceptance。
- PostgreSQL/pgvector judge-backed A/B 质量包已通过：A/B 各 30 text + 4 image，query/judge failure
  均为 0，B overall `0.870343137254902` 高于 A overall `0.8264705882352942`。用户于
  2026-07-16 授权阶段 66 收口同步。
- Phase66 仍不能被夸大为广义 latency release gate：常用回归集已建立并暴露过 contract
  violations，纯图检索和 Flash 默认修复只是定向收敛；Phase65 holdout/judge 总门禁仍独立。
- 2026-07-18 验收后复核确认，55 秒级本地延迟并非模块化函数调用开销，而是普通 uvicorn
  启动仍默认关闭 short-loop、route-first 与 retrieval fan-out。两题并发定向复测的
  `time_to_final_ms` 从 `56240 / 54839` 降到 `26741 / 18573`；据用户确认，三个策略现已
  提升为默认生产行为。显式 false 只用于有界诊断/A/B，不代表第二套 runtime。

## 当前门禁可信度

- Phase 64 的完整 30-case × 3、A/B 共 180 次冷链路请求和盲评未运行。
- 已有三对方向性 A/B 中，B Flash 首 token P50/P95 为 17.480/18.683 秒，
  尚未证明 Phase 64 的 15 秒 P95 目标。
- `data/evaluation/stage30_engineering_health.json` 生成于 2026-06-13，仍记录
  `571 passed, 1 warning`。
- Phase65 已将质量页、JSON 与 CSV 导出收口为 `blocked/stale/local_integrity_only`；
  旧 Stage30 的 `91.52 / A / pass` 不再能作为当前发布证明，也不能通过前端 CSV
  导出旁路重现。
- 主工作区完整后端回归为 `1598 passed, 1 skipped`；这证明本地代码回归，不能替代
  当前代码、模型、语料和索引的 Agent 级真实门禁。

## 65A baseline 预检（主工作区）

- `PHASE65_AUTH_TOKEN` 当前未设置。主工作区的受控 8001 服务已正常启动，`/health`
  返回 200；未携带认证访问 retrieval-contract 返回预期 401。
- 评测器优先从其自身进程环境读取 `--token-env` 指定的变量；未设置时才在内存中读取
  主工作区 `.env` 的同名变量。本地 `.env` 当前不存在 `PHASE65_AUTH_TOKEN` 变量名。
  两种路径都不得把令牌发入对话、日志或评测产物。
- 非联网 baseline 排程已验证 `cases=30`、`runs=3`、`expected_rows=90`，且只写安全
  元数据到本地 `output/`；65A focused tests 为 `110 passed`。
- 因缺认证、严格 pgvector/非空语料契约及已验证 provider 收据均未满足，不能执行或
  伪造 90 条真实 baseline，也不能越过 65A 进入 Runtime 模块化。

## 仓库与协作现场

- 当前分支仍是 `codex/phase-64-mainstream-agent-latency`，HEAD 为 `1884ed35`。
- `phase-64-complete` 指向 `271710df`，`origin/main` 已包含该提交；远端 main
  当前为 `e0a209c1`，本地 main 仍停留在 Phase 63 合并提交。
- 开工时已有未跟踪 `.playwright-cli/`、`output/` 和根目录截图，均不属于
  Phase 65 规划交付物；本轮生成的 `.superpowers/` 也是本地临时状态。
- 本轮尚未修改业务代码、运行测试、创建 Phase 65 分支、暂存或提交。

## 2026-07-15 追加事实

- `phase64-followup-02` 的 CSV `history` 为空但 `history_json` 非空；evaluator 会把该
  history_json 注入请求，因此这是合法 follow-up 样本。
- candidate 失败时已观察到工具链为 `search_figures|hybrid_search_knowledge|final_answer`，
  但 `search_figures` 选中 0、引用 0、拒答；根因不是工具路由，而是视觉证据召回。
- `search_figures` 原本已有 visual follow-up grounding 与 generic visual fallback，但真实
  样本仍 0 图，说明 vector-only 图像候选在“常见破坏形态 + 图片支持”这类 broad visual follow-up
  上不稳。新增 keyword `image_description` 候选兜底后，targeted rerun 该样本通过。
- 单 case × 1 run 的 targeted retry 会让正式 `JudgeReceiptContract` 因 A/B 匿名映射无法双向均衡
  而报 `invalid_judge_receipt_contract`。这不是付费授权问题；已通过 lane-only receipt contract
  开关解决，且正式 paired judge 默认严格性不变。
- 当前 corrected paired 证据为行级闭环：baseline 30/30、candidate 30/30。但严格 Phase65
  acceptance 仍 blocked，原因是 `evaluator_sha256_mismatch`。这是真实边界，不能在文档或 UI 中
  表述为正式 full A/B 已通过。
- acceptance summary 旧逻辑会把“paired summary 存在但 blocked”误标为
  `paired_full_summary_missing`；已修正为 `paired_full_gate_not_pass`。
- evaluator 旧 `holdout` mode 只跑 candidate lane，且不传 `--runs` 时继承 3-run 默认；
  这不符合 Phase65 计划的 reviewer holdout A/B observation。当前已修正为 holdout 必须 baseline+
  candidate 双 endpoint、双 lane、distinct endpoint，默认每 case 1 次 A/B observation。
- evaluator 旧 `holdout --execute-blind-judge` 不会实际生成 judge rows，因为 judge loop 只允许
  `paired` mode；acceptance 旧逻辑也没有要求 holdout judge receipt。当前已修正：holdout blind
  judge 会写安全 judge rows，并把 judge summary 纳入 holdout summary；acceptance 需要 matched
  judge summary 才允许 holdout gate pass。
- baseline reuse waiver 已落地：当前 corrected paired 仍如实保留 `paired_full_gate=blocked`
  与 `evaluator_sha256_mismatch`，但新增 `phase65-baseline-reuse-waiver-v1` 安全收据作为
  用户授权的替代证据。waiver 只允许 `evaluator_sha256_mismatch` 这一 blocker，且要求
  baseline/candidate 各 30 个 case-run 行级对齐、全部 `ok=True`、无错误类别、无非 200 HTTP、
  无 cold receipt 异常、无 completed tool replay；其它 blocked 原因不能被豁免。当前
  `output/phase65/baseline-reuse-waiver-30x1-corrected.json` 为 `gate=pass`、
  `failed_required=[]`；该步之后 acceptance summary 一度剩余
  `holdout_summary_missing` 与 `human_acceptance_missing`，下一条已把 holdout missing 推进为
  显式 blocked receipt。
- 缺私有 reviewer holdout 集的状态已从 missing 推进为显式 blocked receipt：当前
  `data/evaluation/phase65_private_holdout_cases.csv` 不存在或不可用，因此不能执行/伪造 holdout
  pass。`output/phase65/holdout-blocked-missing-private-cases.json` 记录
  `private_holdout_cases_missing`、`holdout_case_count=0` 与安全下一步；刷新后的 acceptance summary
  当时剩余 blocker 为 `holdout_gate_not_pass` 与 `human_acceptance_missing`；下一条已把 human
  acceptance missing 推进为显式 pending packet。
- human acceptance pending packet 已落地：`output/phase65/human-acceptance-pending-packet.json`
  记录 `status=pending_user_review`、当前 acceptance summary hash、验收 checklist 与下一步动作；
  不包含 prompt、answer、evidence 正文、provider raw payload 或密钥。刷新后的 acceptance summary
  中 `human_acceptance=blocked`，当前 blockers 为 `holdout_gate_not_pass` 与
  `human_acceptance_not_pass`。
- human acceptance recorder 已落地且防误签：`scripts/record_phase65_human_acceptance.py`
  需要显式 `--decision pass|fail` 与 `--confirm-checklist`。当前 holdout 仍 blocked 时，尝试
  `--decision pass` 会被拒绝为 `cannot_pass_with_open_non_human_gates`，不会写出 pass record。
- private holdout intake 已落地：`scripts/prepare_phase65_holdout_intake.py` 会生成 header-only
  模板和 intake packet，模板不能作为 executable holdout evidence；validator 要求至少 12 个唯一
  case 且 question 非空。当前真实 `data/evaluation/phase65_private_holdout_cases.csv` 仍不存在。
- Phase65 closeout audit 已落地：`output/phase65/closeout-audit.json` 当前为
  `gate=blocked`、`ready_for_closeout=false`，failed_required 为 `holdout_gate_not_pass` 与
  `human_acceptance_not_pass`。它是当前判断阶段是否可收口的单一安全摘要入口。
- private holdout validator 已增加 public-case overlap guard：默认排除
  `data/evaluation/phase64_latency_cases.csv` 中已有 case_id，重叠时拒绝为
  `holdout_overlaps_excluded_cases`，避免把 public baseline cases 冒充 reviewer holdout。
- evaluator 本体也已增加 public-case overlap guard：`--mode holdout` 现在把 `--cases` 作为
  public/frozen 排除集传入 `validate_holdout_cases()`，默认覆盖
  `data/evaluation/phase64_latency_cases.csv`。因此即使跳过 intake 直接运行 evaluator，重叠
  case_id 也会被拒绝为 `holdout_overlaps_public_cases`。这补上了 intake-only guard 可被绕过的
  缺口；真实 reviewer holdout pass 仍必须来自未与 public/frozen set 重叠的私有 case set。
- holdout acceptance 现在要求 public/frozen overlap proof：`holdout_summary` 必须携带
  `public_overlap_exclusion_proven=true`、正数 `excluded_case_count` 与合法
  `excluded_case_set_sha256`，否则 `_holdout_status()` 不会返回 `pass`。这防止旧格式或手写
  holdout summary 只凭 clean/judge 字段绕过 public/frozen 隔离证明。
- holdout acceptance 现在要求 real execution proof：`holdout_summary` 必须携带
  `execution_mode=real_api` 且 `executed_ab_row_count >= holdout_case_count * 2`。这防止 dry-run
  或缺执行证明的旧格式 summary 被误当成 reviewer holdout pass。
- human acceptance pass record 现在要求当前证据 hash 绑定：`phase65-human-acceptance-record-v1`
  里的 `acceptance_summary_sha256` 必须匹配当前非 human 证据计算出的 canonical pre-human
  acceptance summary hash，否则 human gate 不会 pass。这防止旧 packet/旧 summary 的人工签字被
  复用到新证据状态。
- human acceptance recorder 现在也在签字时校验当前 summary：`pass` 决策必须提供
  `current_acceptance_summary` / `--current-acceptance-summary`，且 hash 必须匹配 packet。
  不匹配时拒绝为 `human_acceptance_summary_mismatch`，避免生成稍后必然会被 summary 拒绝的
  陈旧 pass record。
- 裸 human acceptance pass 旁路已关闭：`human_acceptance="pass"` / `--human-acceptance pass`
  不再能让 human gate 通过；pass 必须来自带 hash 绑定的
  `phase65-human-acceptance-record-v1`。`--human-acceptance fail` 仍可用于显式失败。
- closeout audit 现在要求正式 human acceptance record：顶层 `gate=pass` 不再足够，human artifact
  必须是 `phase65-human-acceptance-record-v1`，且 nested summary 为 `gate=pass/status=accepted`。
  普通 packet 或错误格式 pass artifact 不能让 closeout ready。
- closeout audit 现在还要求 human receipt 与 acceptance summary 绑定：acceptance pass summary 会
  写入 `human_acceptance_summary_sha256`；closeout 重新计算传入 record 的 nested summary hash，
  不匹配则 blocked。这防止收口时替换成另一个 accepted human record。
- closeout audit 现在还要求 holdout intake 与 acceptance summary 绑定：acceptance pass summary 会
  写入 `holdout_case_set_sha256`；closeout 要求 pass intake validation 的
  `holdout_case_set_sha256` 与之匹配。这防止收口时替换成另一个通过的 private holdout case set。
- closeout audit 现在还要求 acceptance summary 内部结构完整：极简 `gate=pass` 不再足够；必须有
  `phase65_acceptance=pass`、空 `failed_required`、关键 components pass，以及 paired full/preflight
  pass 或 baseline reuse substitutions。这防止用手写最小 pass summary 绕过真实门禁状态。
- closeout audit 现在还会二次检查 holdout intake 的 case 数：即使 intake validation 顶层 pass、
  `ready_to_run_holdout=true` 且 case-set hash 匹配，`holdout_case_count < 12` 也会 blocked。
  这避免 closeout 过度信任上游 ready 标签。
- human acceptance 现在要求 recorder 形态字段：仅有 `gate=pass/status=accepted` 与 hash 匹配不再
  足够；summary 和 closeout 都要求 `decision=pass`、checklist 确认、`open_non_human_gate_count=0`
  和非空 reviewer。人工验收 pass 必须像真实签字收据，而不是薄 pass 标签。
- closeout audit 现在会二次检查 holdout intake 的 public/frozen overlap 结果：
  `excluded_case_overlap_count` 必须为 0。仅有 ready/hash/case-count 不再足够，避免把与公开/冻结
  cases 重叠的 reviewer holdout 带入收口。
- holdout acceptance 现在要求正式 `phase65-holdout-summary-v1` schema：旧格式或手写 summary 即使
  具备 clean、real_api、case hash、judge summary 等 pass-looking 字段，也不能让
  `holdout_gate=pass`。evaluator 的 holdout mode 已开始写该 schema。
- holdout acceptance 现在要求 A/B lane completeness：`baseline_ab_row_count` 与
  `candidate_ab_row_count` 都必须等于 `holdout_case_count`。仅有总执行行数足够不再能证明 reviewer
  holdout 的 baseline/candidate 两条 lane 都完整覆盖。
- holdout acceptance 现在还要求 A/B lane case-set hash 绑定：`baseline_ab_case_set_sha256` 与
  `candidate_ab_case_set_sha256` 必须都等于 `holdout_case_set_sha256`。这防止两条 lane 数量正确但
  覆盖不同 case 集。
- closeout audit 现在也会二次检查 acceptance summary 中的 A/B lane case-set hash：最终收口时
  `baseline_ab_case_set_sha256` 与 `candidate_ab_case_set_sha256` 必须都等于
  `holdout_case_set_sha256`，避免只携带总 holdout hash 的 pass-looking summary 被误收。
- holdout acceptance 现在要求 blind-judge summary 具备正式 schema 与 receipt contract hash：
  `judge_summary.schema_version` 必须是 `phase65-judge-summary-v1`，`judge_expected_pairs` 必须等于
  `holdout_case_count`，`receipt_contract_sha256` 必须是合法 SHA-256。旧格式或手写 lower-bound 字段不能
  伪装成 reviewer holdout blind-judge receipt。
- closeout audit 现在要求 acceptance summary 透出 holdout blind-judge receipt contract hash：
  `holdout_judge_receipt_contract_sha256` 必须是合法 SHA-256。最终收口不能只信任
  `components.holdout_gate=pass`，还必须保留一条安全、可比对的 blind-judge receipt 绑定证明。
- closeout audit 现在要求 acceptance summary 与 holdout intake 的 reviewer case count 完全一致：
  acceptance pass summary 会透出 `holdout_case_count`；最终收口要求 intake validation 的
  `holdout_case_count` 与之相等，避免最终报告只保留 case-set hash 而丢失明确样本量证明。
- closeout audit 现在要求 acceptance summary 透出 reviewer holdout 真实执行证明：
  `holdout_execution_mode` 必须是 `real_api`，`holdout_executed_ab_row_count` 至少为
  `holdout_case_count * 2`，且 baseline/candidate lane 行数都必须等于 `holdout_case_count`。最终
  closeout 不能只凭 hash/pass 标签而缺失真实执行规模证明。
- closeout audit 现在要求 acceptance summary 透出 public/frozen overlap 排除证明：
  `holdout_excluded_case_count` 必须大于 0，`holdout_excluded_case_set_sha256` 必须是合法 SHA-256。
  最终 closeout 不能丢失 reviewer holdout 与 public/frozen cases 隔离的证明。
- closeout audit 现在会二次检查 holdout intake 的列契约：`required_columns` 必须精确等于
  `HOLDOUT_TEMPLATE_FIELDS`，避免手写最小 pass intake 缺少 reviewer holdout CSV schema 仍被收口。
- Phase65 private holdout 已从“缺 case 文件”推进为“真实 A/B 执行完成但 judge gate 未通过”：
  `data/evaluation/phase65_private_holdout_cases.csv` 已建立并通过 intake validation，真实 holdout 第三轮
  baseline `127.0.0.1:8001` vs candidate `127.0.0.1:8011` 产出 24/24 clean A/B rows，且两条 lane 的
  cold-cache receipt 均 valid。当前阻断不再是执行层，而是 blind judge 层：只形成 5/12 个安全 receipt，
  `judge_error_count=7`，且已形成 receipt 的 lower bounds 为负，不能证明 candidate 在 holdout 上优于或不劣于
  baseline。因此 `holdout_gate_not_pass` 仍是有效 blocker。
- Phase65 holdout 暴露两个后续改进点：第一，holdout case-set hash 当前只绑定 case_id 集，case 文本/rubric
  修订不会改变 hash，后续应升级为绑定 case_id + question + expected_tool + expected_graph_requirement 的完整
  holdout contract hash；第二，当前 off-topic/refusal router 对“彩票/股票预测”类明确离域问题不稳定，第三轮
  holdout 已改用现有 gate 能稳定覆盖的责任/处罚类 boundary case，但该离域泛化缺口应进入后续产品修复。
