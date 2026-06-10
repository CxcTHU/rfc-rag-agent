# Task Plan: 阶段 20 - 中文检索默认链路落地与评测判定增强

## Goal

在阶段 19「中文全文文献分析与检索/评测调优」已完成、提交、创建 `phase-19-complete` tag（指向阶段 19 最终功能提交 `ffb4756`，非 merge）并合并到 `main`（合并提交 `12184d7`）的基础上，完成阶段 20「中文检索默认链路落地与评测判定增强」：

1. 用答案级 `coverage_ratio` 升级阶段 19 中文难评测集判定，削弱题录卡片关键词命中偏置。
2. 在不重做 chunk embedding 的前提下做真实 Jina query 端校验，真实失败必须显式记录，不伪造成成功。
3. 按数据门槛决定是否把 `source_type_reweight` 接入默认 hybrid 链路：`Δp@1>=0.10` 且 `Δdeep_top1>=0.20` 且 refusal 不退化才切换；否则诚实保持 `keep_existing_hybrid`。
4. 新增 `responsibility_gate`，拦截“判定/评定/出具/是否合格/是否符合规范”等工程责任问题，即使检索证据充足也拒答。
5. 更新 quality gate、阶段 20 结果表、普通文档和 Obsidian 本地阶段汇报，最终停在用户人工核验前：不 `git add`、不 commit、不 tag、不 push、不 PR。

核心链路：

```text
阶段 19 中文调优结论
-> 答案级 coverage_ratio 评测判定升级
-> 真实 Jina query 端校验（复用已有 8918 Jina chunk embeddings）
-> 默认链路接入决策（source_type_reweight 过门槛才切，可配置可关闭）
-> responsibility_gate 责任边界拒答门
-> quality gate / 报告更新
-> 回归 + 普通文档 + Obsidian
-> 停在人工核验待提交状态
```

## Boundaries

- 不做写入型 Agent 工具。
- 不做复杂 LangGraph workflow。
- 不做登录系统、不做部署优化。
- 不新增爬虫或外部资料来源。
- 不重做 chunk embedding；已有 deterministic 与 Jina 索引都覆盖 8918 chunks，只允许 query 端按需调用真实 Jina。
- 不让真实 API 成为 CI 或本地全量测试前提；真实 Jina 校验必须可选，并将失败写入结果表。
- HyDE 仍只做离线实验，不进入默认链路或自动回归。
- 默认链路是否切换必须由升级后的中文难评测集数据决定，不拍脑袋。
- 保留 deterministic baseline 与 real_config 边界，不用 deterministic 结果掩盖真实失败。
- 不把 API key、Bearer token、供应商原始敏感响应、受限/受版权全文写入 Git、CSV、文档、测试或 Obsidian；中文全文与本地 DB 不入库。
- 阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。

## Current Phase

Phase 10 complete: waiting for user manual verification.

## Phases

### Phase 0: 启动校准

- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage19_chinese_analysis_retrieval_tuning.md`、`docs/stage19_literature_review.md`、`task_plan.md`、`findings.md`、`progress.md`。
- [x] 运行 `git status -sb` 与 `git log --oneline -5`。
- [x] 确认阶段 19 已完成：`phase-19-complete -> ffb4756`，提交信息为 `Complete phase 19 chinese analysis and retrieval tuning`，父提交为 `4db90c7`，非 merge。
- [x] 确认 `main` 已含阶段 19 合并提交 `12184d7 Merge phase 19 chinese analysis and retrieval tuning`，且 `phase-19-complete` 是 `main` 祖先。
- [x] 从含阶段 19 合并的 `main` 创建并切换到 `codex/phase-20-default-chain-and-eval-upgrade`。
- [x] 使用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md`。
- 验证方式：Git/tag/main 检查命令输出；工作区状态检查；规划文件包含阶段 20 顺序、目标、验证、文档收尾和完成标准。
- 文档收尾要求：记录阶段 20 启动证据、正确基线、安全边界和未提交边界。
- Status: complete

### Phase 1: 阶段 20 设计文档

- [x] 新增 `docs/stage20_default_chain_and_eval_upgrade.md`。
- [x] 写清目标、输入、评测判定升级口径、默认链路接入门槛与回滚、`responsibility_gate` 设计、安全边界和完成标准。
- [x] 明确阶段 19 遗留项闭环方式：题录关键词偏置、真实 Jina query 校验、默认链路阻断/切换、工程责任拒答。
- [x] 新增 `tests/test_stage20_default_chain_and_eval_upgrade.py`，锁住设计文档关键边界。
- 验证方式：设计文档存在；测试或文档断言覆盖关键术语与门槛。
- 文档收尾要求：在 `findings.md` 记录关键架构决策；在 `progress.md` 记录 Phase 1 完成与验证。
- Status: complete

### Phase 2: 评测判定升级

- [x] 升级阶段 19 中文难评测集评测脚本或新增阶段 20 脚本，用答案级 `coverage_ratio` 判定替代偏向题录卡片的关键词命中。
- [x] `coverage_ratio` 至少基于 `expected_answer_points` 覆盖情况；可选离线 LLM-judge 只能作为显式可选模式，不进入 CI 必跑。
- [x] 去掉或降低 `expected_source_hit` 对题录卡片关键词密度的偏置，让 `precision@1` 更贴近“答案要点是否被证据覆盖”。
- [x] 生成阶段 20 结果表，至少包含：`query_id`、`config`、`judge_mode`、`hit`、`coverage_ratio`、`deep_fulltext_top1`、`refusal_matched`、`decision`、`next_action`。
- [x] 补充阶段 20 评测升级测试并运行聚焦测试。
- 验证方式：脚本可 deterministic 复跑；CSV schema 测试；阶段 19 中文难评测集可重跑。
- 文档收尾要求：记录 coverage_ratio 公式、去关键词偏置原因、结果与风险。
- Status: complete

### Phase 3: 真实 Jina Query 端校验

- [x] 在不重做 chunk embedding 的前提下，用已有 `openai-compatible / jina-embeddings-v3 / dim=1024` chunk 索引做 query 端真实 Jina 校验。
- [x] 真实模式必须显式可选；API key/base URL 只从本地 `.env` 读取，不写入任何文件。
- [x] 真实调用失败时写入 `error` / `skipped` / `real_config_status` 类字段，不伪造成成功。
- [x] 保留 deterministic baseline 与 real_config 两套结果边界。
- 验证方式：无真实配置时应稳定 skipped；有真实配置时只调用 query embedding，不重建索引；测试覆盖 skipped/error 状态。
- 文档收尾要求：记录真实 Jina 成功/失败状态、是否影响默认链路决策、为何不作为全量测试前提。
- Status: complete

### Phase 4: 默认链路接入决策

- [x] 用升级后的判定结果比较 baseline 与候选 `source_type_reweight` 配置。
- [x] 判断是否满足切换门槛：`Δp@1>=0.10` 且 `Δdeep_top1>=0.20` 且 refusal 不退化。
- [x] 若满足：把 `source_type_reweight` 接入默认 hybrid 链路，并提供配置开关与默认回滚；保持 API schema 不变。
- [x] 若不满足：保持 `keep_existing_hybrid`，写明阻断原因与后续 next_action。
- [x] 接入时必须可配置、可关闭；不得静默 fallback 掩盖配置差异。
- 验证方式：默认链路单元测试；配置开关测试；`POST /search/hybrid`、Brain、`/chat`、`/agent/query` 回归。
- 文档收尾要求：在设计文档、结果表、quality gate 和 progress 中同步最终决策。
- Status: complete

### Phase 5: `responsibility_gate` 责任边界拒答门

- [x] 新增工程责任拒答门，拦截“判定/评定/出具/是否合格/是否符合规范/配合比是否可用”等责任判断问题。
- [x] 即使检索证据充足，也返回“系统不替代规范审查、工程设计、第三方检测或专家签字”的拒答提示。
- [x] 补阶段 19 遗留 `cn_hq_refusal_engineering_responsibility`。
- [x] 加正反例评测，确保 on-topic 学习题、概念解释题、资料检索题不误拒。
- 验证方式：Brain/chat/agent 相关测试；中文难评测集 refusal 正确率；误拒反例测试。
- 文档收尾要求：记录责任边界的业务含义、触发词、非触发场景与面试表达。
- Status: complete

### Phase 6: Quality Gate / 报告更新

- [x] 建立或更新阶段 20 quality summary / report 产物。
- [x] 明确阶段 19 的默认链路遗留与工程责任边界遗留的闭环状态。
- [x] 如更新 `/quality-report`，保持只读，不触发真实 API、不写数据库、不改登录/权限体系。
- [x] 阶段 20 结果表必须与报告/文档引用一致。
- 验证方式：报告生成脚本测试；`GET /quality-report` 回归；CSV 字段测试。
- 文档收尾要求：`docs/progress.md` 与 `docs/stage20_default_chain_and_eval_upgrade.md` 同步 quality gate 状态。
- Status: complete

### Phase 7: 回归验证

- [x] 补充阶段 20 相关测试，覆盖评测判定、真实 Jina skipped/error、默认链路开关、`responsibility_gate`。
- [x] 保证既有 documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend 测试不被破坏。
- [x] 确认 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 不被破坏。
- [x] 阶段收尾运行全量测试。
- 验证方式：聚焦测试 + `.venv\Scripts\python.exe -m pytest -q`。
- 文档收尾要求：在 `progress.md` 记录测试命令、结果、失败修复过程和残余风险。
- Status: complete

### Phase 8: 普通文档收尾

- [x] 同步 `README.md`。
- [x] 同步 `docs/progress.md`。
- [x] 同步 `docs/architecture.md`。
- [x] 同步 `docs/data_sources.md`。
- [x] 判断并同步 `AGENT.MD` 中对阶段路线、规则或经验的更新。
- [x] 给出阶段 20 面试表达。
- 验证方式：文档中阶段状态、结果表、测试数、默认链路决策一致。
- 文档收尾要求：普通文档先完成，再统一写 Obsidian 小 Phase 汇报。
- Status: complete

### Phase 9: Obsidian 本地知识库收尾

- [x] 建立或更新 `obsidian-vault/阶段汇报/阶段 20 - 中文检索默认链路落地与评测判定增强/`。
- [x] 建立阶段 20 Phase 汇报索引。
- [x] 补齐 Phase 0 到最终 Phase 小汇报，每篇包含 10 项：本 Phase 目标、完成的主要任务、新增/修改内容、关键代码或模块、问题与解决方式、新词解释、验证结果、遗留问题、下一 Phase、面试表达。
- [x] 更新 `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`、`obsidian-vault/阶段/阶段 20 - 中文检索默认链路落地与评测判定增强.md`。
- [x] 确认 `obsidian-vault/` 仍被 Git 忽略，不纳入提交范围。
- 验证方式：文件存在性检查；模板 10 项检查；Git ignore 检查。
- 文档收尾要求：Obsidian 只在阶段 20 全部开发、测试、普通文档完成后统一写入。
- Status: complete

### Phase 10: 人工核验待提交状态

- [x] 最终 `git status -sb`，确认未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。
- [x] 检查无 API key、Bearer token、供应商原始敏感响应、受限/受版权全文进入 Git、CSV、文档、测试或 Obsidian。
- [x] 最终汇报当前分支、主要改动、测试结果、未提交状态、人工核验重点，以及用户确认后再提交和打 tag 的建议。
- 验证方式：Git 状态、敏感信息扫描、全量测试结果、文档/Obsidian 文件检查。
- 文档收尾要求：停在用户人工核验前，不创建 `phase-20-complete` tag。
- Status: complete

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `codex/phase-20-default-chain-and-eval-upgrade` |
| Previous tag | `phase-19-complete -> ffb4756` and unchanged |
| Baseline | `main` contains `12184d7 Merge phase 19 chinese analysis and retrieval tuning` |
| No submit actions | no add/commit/tag/push/PR |
| Design doc | `docs/stage20_default_chain_and_eval_upgrade.md` |
| Eval upgrade | answer-level `coverage_ratio` results table exists |
| Real Jina | query-only validation, skipped/error explicit, no chunk re-embedding |
| Default chain | switch only if threshold passes; otherwise `keep_existing_hybrid` with reason |
| Responsibility gate | engineering responsibility questions refused; learning questions not over-refused |
| API contract | search/vector/hybrid/chat/agent + /quality-report compatible |
| Tests | focused + full tests pass |
| Docs | README/progress/architecture/data_sources/AGENT synced as needed |
| Obsidian | local phase 20 reports completed and gitignored |
| Final state | waiting for user manual verification |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| `coverage_ratio` | 答案级覆盖率：用期望回答要点衡量证据/回答覆盖多少，而不是只看题录标题或摘要关键词是否命中 |
| LLM-judge | 离线大模型裁判；可辅助人工审阅，但不能成为 CI 或本地全量测试前提 |
| query 端 Jina 校验 | 只把用户问题发给 Jina 生成 query embedding，复用已有 chunk embeddings，不重新生成 8918 个 chunk 向量 |
| `source_type_reweight` | 阶段 19 的检索后处理纯函数，按深度全文、题录、主题锚点对候选重新加权 |
| `responsibility_gate` | 工程责任边界拒答门，防止系统替代规范审查、第三方检测、工程设计或专家签字 |
| quality gate | 质量门禁；把评测结果、风险等级、默认链路决策和下一步动作沉淀成可复核状态 |

## Notes

- 本文件由 Planning with Files 维护，是阶段 20 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 20 开发过程中暂不写入 Obsidian 小 Phase 汇报；全部开发、测试、普通文档完成后，Phase 9 统一补齐。
- 阶段 20 收尾后必须停在用户人工核验前，不提交、不打 tag、不推送。
