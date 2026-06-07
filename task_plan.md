# Task Plan: 阶段 16 - 真实质量风险闭环

## Goal

在阶段 15 已完成并合并到 `main` 的基础上，完成阶段 16：真实质量风险闭环。阶段 16 只处理阶段 15 质量报告已经暴露的发布前风险，不扩展新功能主线。

核心链路：

```text
stage15 quality report
-> real decompose SSL EOF 排查
-> stage15 high/medium Answer Coverage 复核
-> 必要的 timeout/retry/error 分类改进
-> stage16 quality closure summary/report
-> docs / Obsidian 草稿收尾
-> 停在用户人工核验前状态
```

本阶段不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不新增爬虫或外部资料来源、不让真实 API 成为 CI 或本地全量测试前提。HyDE 仍只做离线实验，不进入默认链路或自动回归。

阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。必须等待用户人工核验和明确确认后，才允许进入提交、tag 和 GitHub 推送流程。

## Current Phase

Phase 7 complete。按用户要求追加处理 decompose 运行问题：已复现 SSL EOF，修复 embedding provider `api-key` 兼容请求头，并在真实 chat timeout 120 秒下跑通 real decompose 10/10。当前仍停在人工核验前，尚未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

## Phases

### Phase 0: 阶段启动与规划校准

- [x] 设置线程 goal。
- [x] 将线程标题修改为 `阶段16-真实质量风险闭环`。
- [x] 阅读 Planning with Files 规则。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage15_real_review_report.md`、`docs/stage15_quality_report.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其为阶段 15 工作记忆。
- [x] 确认 `main` 已包含阶段 15 合并提交：`b5bad50 Merge phase 15 real review report`。
- [x] 确认 `phase-15-complete` 指向阶段 15 最终功能提交 `a844948`，不移动已有阶段 tag。
- [x] 从阶段 15 合并后的 `main` 创建并切换到 `codex/phase-16-real-quality-risk-closure`。
- [x] 使用 Planning with Files 校准阶段 16 的三份记忆文件。
- 验证方式：线程标题、goal、Git 分支/tag 检查、规划文件检查。
- 文档收尾要求：记录阶段 16 起点、tag 状态、当前分支、阶段 15 遗留风险和“待人工核验、不提交”边界。
- Status: complete

### Phase 1: 阶段 16 设计文档与闭环口径

- [x] 新增 `docs/stage16_quality_risk_closure.md`。
- [x] 明确阶段 16 的目标、输入、风险分级、排查流程、复核标准、安全边界和完成标准。
- [x] 明确真实 decompose SSL EOF 的诊断分类：供应商网络、超时配置、embedding provider 稳定性、脚本编排、真实配置缺失。
- [x] 明确 Answer Coverage high/medium 复核规则和 risk_before/risk_after 口径。
- [x] 明确质量门槛：可降级为 `closure_ready/medium` 或 `closure_ready/low` 的条件，以及仍保持 high 的阻断原因。
- [x] 新增设计文档测试，校验关键章节、输入输出、安全边界和 API 兼容承诺。
- 验证方式：文档测试和字段检查。
- 文档收尾要求：在 `findings.md` 记录阶段 16 技术决策和新词解释。
- Status: complete

### Phase 2: real decompose SSL EOF 排查与错误分类

- [x] 阅读 `scripts/evaluate_stage15_real_config.py`、`scripts/evaluate_decompose.py`、`app/services/retrieval/embedding.py`、`app/services/retrieval/decompose.py`。
- [x] 复核 `data/evaluation/stage14_real/real_config_status.csv` 和 `data/evaluation/stage14_embedding_comparison.csv` 中 decompose error 的记录。
- [x] 必要时改进真实配置复跑或 provider 调用的 timeout/retry/error 分类，但不能让真实 API 成为默认测试前提。
- [x] 建立阶段 16 decompose 诊断输出，记录 root_cause、reproducibility、safe_to_retry、blocking_status 和 next_action。
- [x] 补充测试覆盖网络错误、超时、SSL EOF、skipped、error redaction 和 deterministic 不受影响。
- 验证方式：脚本单测、mock 错误分类、必要时显式真实复跑或 skipped/error 记录。
- 文档收尾要求：在 `progress.md` 记录真实 decompose 当前状态和是否仍阻断。
- Status: complete

### Phase 3: Answer Coverage high/medium 风险闭环

- [x] 建立阶段 16 复核脚本，读取 `data/evaluation/stage15_answer_coverage_review.csv`。
- [x] 优先处理 high 风险样例 `user_mixed_itz_strength`。
- [x] 审阅 8 条 medium 样例，确认 Faithfulness、Answer Coverage 和 Citation Quality。
- [x] 输出 `data/evaluation/stage16_answer_coverage_closure.csv`。
- [x] 输出字段至少包含 query_id、risk_before、risk_after、faithfulness、answer_coverage、citation_quality、root_cause、evidence、decision、next_action。
- [x] 复核逻辑只使用已有脱敏摘要、来源标题、expected_answer_points 和可解释规则，不保存供应商原始响应。
- [x] 补充测试覆盖 high 降级、medium 保留、fail 保留、字段完整性和安全边界。
- 验证方式：脚本单测、CSV schema 检查、9 条复核结果生成。
- 文档收尾要求：在 `findings.md` 记录高风险样例根因、8 条 medium 样例结论和面试表达。
- Status: complete

### Phase 4: 质量汇总与只读报告更新

- [x] 新增或更新阶段 16 质量汇总脚本。
- [x] 输出 `data/evaluation/stage16_quality_closure_summary.csv`。
- [x] 生成 `docs/stage16_quality_closure_report.md`。
- [x] 必要时最小更新 `app/frontend/quality_report.html`，展示阶段 16 闭环状态；不重构工作台，不改变核心 API。
- [x] 汇总真实 decompose 错误闭环、Answer Coverage risk_before/risk_after、quality gate 和下一阶段建议。
- [x] 如果仍存在 high 风险，必须明确阻断原因；不能伪造成全部通过。
- [x] 补充报告/前端测试。
- 验证方式：报告脚本运行、报告测试、前端只读入口测试、API 兼容测试。
- 文档收尾要求：记录报告入口的使用方式、只读边界和安全边界。
- Status: complete

### Phase 5: 回归验证与阶段 16 质量结论

- [x] 复跑阶段 16 新增脚本。
- [x] 运行阶段 16 新增测试。
- [x] 运行 documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend 相关聚焦回归。
- [x] 运行全量测试。
- [x] 汇总 decompose 闭环状态、Answer Coverage 闭环状态、quality gate、遗留风险和下一阶段依据。
- 验证方式：评测脚本输出、聚焦测试、全量测试。
- 文档收尾要求：`progress.md` 记录所有测试命令和结果。
- Status: complete

### Phase 6: 普通文档、Obsidian 草稿与待人工核验收尾

- [x] 更新 `README.md`，说明阶段 16 当前能力、风险闭环结果、使用边界和下一阶段建议。
- [x] 更新 `docs/progress.md`，记录阶段 16 完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充阶段 16 evaluation/reporting 闭环数据流；如无需改变核心架构，说明原因。
- [x] 更新 `docs/data_sources.md`，说明阶段 16 只新增评测/报告产物，不新增资料来源、不保存受限全文或 API key。
- [x] 判断并更新 `AGENT.MD`，记录阶段 16 经验、下一阶段建议和“开发后先人工核验再提交/tag/push”的流程约束。
- [x] 统一补齐 Obsidian 本地知识库：阶段 16 阶段页、阶段汇报目录、Phase 0 到最终 Phase 汇报、索引、分类页和知识点。
- [x] 确认每篇 Obsidian Phase 汇报包含 10 个固定小节。
- [x] 确认 `obsidian-vault/` 仍被 Git 忽略，不纳入后续提交。
- [x] 确认没有执行 `git add`、`git commit`、`git tag`、`git push` 或 PR 创建。
- [x] 最终汇报当前分支、主要改动、测试结果、未提交状态和人工核验重点。
- 验证方式：文档检查、Obsidian 小节检查、Git 状态检查。
- 文档收尾要求：所有普通文档与 Obsidian 阶段知识库同步完成，但停在用户人工核验前。
- Status: complete

### Phase 7: 追加 real decompose 运行修复

- [x] 显式复跑 real decompose 到阶段 16 retry 文件，不覆盖阶段 15 原始结果。
- [x] 复现原始 SSL EOF，定位到 embedding 请求兼容性问题。
- [x] 用最小 embedding POST 探针确认同时携带 `Authorization` 和 `api-key` 可返回 200。
- [x] 修复 `OpenAICompatibleEmbeddingProvider`，补齐 `api-key` 请求头，与 chat provider 行为一致。
- [x] 补充 embedding provider 请求头测试。
- [x] 用真实 embedding + deterministic chat 验证 decompose 检索链路：10/10。
- [x] 用真实 embedding + 真实 chat，并将 chat timeout 提高到 120 秒验证完整 decompose：10/10。
- [x] 扩展 stage16 decompose diagnostics，让成功 retry CSV 可把 decompose 标为 `retry_completed/not_blocking`。
- [x] 重新生成 `stage16_decompose_diagnostics.csv`、`stage16_quality_closure_summary.csv`、`docs/stage16_quality_closure_report.md` 和 `/quality-report`。
- [x] 同步 README、docs/progress、docs/architecture、AGENT.MD 中的 decompose 最新结论。
- 验证方式：embedding provider 测试、diagnostics/report 测试、real decompose retry。
- 文档收尾要求：说明 decompose 已不再是 high 阻断；当前剩余 high 来自 Answer Coverage。
- Status: complete

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `codex/phase-16-real-quality-risk-closure` |
| Previous tags | `phase-15-complete` and older phase tags remain unmoved |
| No submit actions | no `git add`, no commit, no tag, no push, no PR |
| Design doc | `docs/stage16_quality_risk_closure.md` exists and covers risk closure flow |
| Decompose closure | real decompose SSL EOF is classified or fixed without fake success |
| Coverage closure | `data/evaluation/stage16_answer_coverage_closure.csv` covers 1 high + 8 medium rows |
| Quality summary | Stage 16 quality summary/report shows risk_before/risk_after and quality gate |
| API contract | search/vector/hybrid/chat/agent and `/quality-report` remain compatible |
| Tests | Stage 16 focused tests and full test suite pass |
| Docs | README, docs/progress, docs/architecture, docs/data_sources and AGENT.MD judgment updated |
| Obsidian | Stage 16 local knowledge base updated and remains ignored by Git |
| Final state | Waiting for user manual verification before commit/tag/push |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支为 `codex/phase-16-real-quality-risk-closure` | 与阶段 16 目标和用户要求一致 |
| 从阶段 15 合并后的 `main` 创建阶段 16 分支 | `main` 当前已包含阶段 15 合并提交，是正确起点 |
| 不移动已有阶段 tag | 阶段 tag 必须稳定指向各阶段最终功能提交 |
| 阶段 16 不提交、不打 tag、不推送 | 用户要求先人工核验，可能追加功能和小阶段 |
| 保留 deterministic baseline | 自动回归必须不依赖真实 API、网络、余额和限流 |
| 真实 decompose 失败可记录为闭环分类 | 阶段 16 目标是风险闭环，不是伪造全部通过 |
| 复核只读质量产物 | 阶段 16 是质量闭环，不改变核心 RAG API |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| 真实质量风险闭环 | 把阶段 15 报告里的 high/medium 风险逐条排查、复核、分类并记录 next_action |
| SSL EOF | HTTPS 连接在读取时被异常中断；本项目里出现在真实 embedding 请求中 |
| root_cause | 根因分类，用来说明风险来自网络、超时、provider、脚本编排、资料不足还是回答覆盖不足 |
| risk_before / risk_after | 闭环前后的风险等级，证明阶段 16 是否降低了发布前风险 |
| quality gate | 阶段质量闸口，说明当前能否进入下一阶段或仍需人工阻断 |
| closure summary | 阶段 16 的闭环汇总表，用于替代单纯“high=几个”的静态状态 |

## Notes

- 本文件由 Planning with Files 维护，是阶段 16 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 16 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 6 统一补齐。
- 阶段 16 收尾后必须停在用户人工核验前，不提交、不打 tag、不推送。
