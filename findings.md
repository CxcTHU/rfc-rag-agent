# Findings & Decisions

## Requirements

- 用户要求正式进入阶段 16：真实质量风险闭环。
- 线程标题已修改为 `阶段16-真实质量风险闭环`。
- goal 已设置为：完成阶段 16 的开发、测试、普通文档和 Obsidian 草稿收尾，并停在用户人工核验前状态。
- 目标分支为 `codex/phase-16-real-quality-risk-closure`。
- 阶段 16 必须从阶段 15 完成并合并到 `main` 的状态出发。
- 必须确认 `phase-15-complete` 指向阶段 15 最终功能提交，不移动已有阶段 tag。
- 阶段 16 开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。
- 阶段 16 不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不新增爬虫或外部资料来源、不让真实 API 成为 CI 或本地全量测试前提。
- HyDE 仍只做离线实验，不进入默认链路或自动回归。
- 不得把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。

## Current Project Findings

- 当前工作区已切换到 `codex/phase-16-real-quality-risk-closure`。
- `main` 当前提交为 `b5bad50a44e2329bab67bae1ea4634be5f7608c5`，提交信息为 `Merge phase 15 real review report`。
- `phase-15-complete` 指向 `a844948dbefded500cbbe76c442f11a0b83c3601`。
- `phase-15-complete` 指向的是阶段 15 最终功能提交；`main` 在该提交之后还有普通文档路线图提交和 merge commit。
- 旧 `task_plan.md`、`findings.md`、`progress.md` 均为阶段 15 工作记忆，需要改写为阶段 16。
- 当前阶段 15 报告暴露两个主要 high 风险来源：真实 decompose error 和 Answer Coverage high 样例。
- 阶段 16 的完成状态不是 commit/tag，而是“开发与验证完成，等待用户人工核验”。

## Architecture Findings

- `stage14_real` 是 `data/evaluation/stage14_real/`，保存真实配置复跑结果或 skipped/error 状态。
- `scripts/evaluate_stage15_real_config.py` 是阶段 15 真实配置复跑调度入口，负责 vector、hybrid、user_questions、decompose、chat、agent、brain_workflow。
- `scripts/evaluate_decompose.py` 是 Decompose 评测入口，真实配置下曾在 embedding 请求处出现 SSL EOF。
- `EmbeddingProvider` 位于 `app/services/retrieval/embedding.py`，负责把 query/chunk 转成向量；真实 provider 失败不能被 deterministic fallback 掩盖。
- `DecomposeRetrievalService` 位于 `app/services/retrieval/decompose.py`，负责子 query 检索、证据合并、按 chunk_id 去重和可解释 rerank。
- `BrainService` 复用 Decompose/hybrid 检索结果，并在生成前执行 evidence confidence。
- `/chat` 和 Agent `answer_with_citations` 都复用 Brain，因此阶段 16 不能破坏 Brain 的旧输入输出。
- `/quality-report` 是阶段 15 新增的只读质量报告入口，位于 evaluation/reporting 层，不触发真实 API 调用，不写数据库。

## Evaluation Findings

- 阶段 15 真实配置复跑结果：
  - vector 15/15。
  - hybrid 15/15。
  - user_questions 27/30。
  - decompose error，真实 embedding 请求出现 `SSL: UNEXPECTED_EOF_WHILE_READING`。
  - chat 6/6。
  - agent 5/5。
  - brain_workflow 18/18。
- 阶段 15 deterministic baseline：
  - vector 13/15。
  - hybrid 15/15。
  - user_questions 25/30。
  - decompose 10/10。
  - chat 6/6。
  - agent 5/5。
  - brain_workflow 18/18。
- `data/evaluation/stage15_answer_coverage_review.csv` 当前 9 行：1 条 high、8 条 medium。
- high 风险样例为 `user_mixed_itz_strength`，问题是 `RFC 里 rock 和 SCC 的界面 ITZ 会怎样影响强度？`，真实回答超时，Faithfulness/Answer Coverage 失败或缺失。
- 8 条 medium 样例都已有真实回答摘要和匹配来源，但 Answer Coverage 仍为 review，需要人工规则审阅。
- `data/evaluation/stage15_quality_summary.csv` 当前 14 行，风险统计 high=4、medium=3、low=7，overall quality gate 为 `review_required/high`。

## Data Source Findings

- 阶段 16 不新增外部文献资料来源。
- 阶段 16 只新增评测/诊断/报告产物，不改变 `sources`、`documents`、`chunks`、`chunk_embeddings` 的来源归属。
- 阶段 16 复核表只能保存来源标题、答案摘要、指标、错误摘要、根因分类和 next_action。
- 受限全文仍只允许保存在本地授权环境，不写入 Git、文档、CSV、测试或 Obsidian。
- 真实 API key 只允许存在本地 `.env` 或内存调用中。

## Technical Decisions

| Decision | Reason |
|---|---|
| 阶段 16 先写设计文档 | 风险闭环涉及真实错误分类、人工复核和质量门槛，必须先固定口径 |
| decompose SSL EOF 先分类再决定是否修复 | 外部网络或供应商错误不一定能在代码中彻底修复，但必须可复现、可审计 |
| Answer Coverage 闭环独立输出 stage16 CSV | 保留阶段 15 原始复核表，同时记录阶段 16 的闭环判断 |
| 保留 high 风险阻断可能 | 质量闭环不是制造通过率，仍 high 时必须诚实记录 |
| 不改变核心 RAG API | 阶段 16 是 evaluation/reporting 层工作，不是产品功能扩张 |
| 不提交、不打 tag、不推送 | 用户明确要求先人工核验，可能追加小阶段或功能 |

## Phase Findings

### Phase 0

- Goal 已设置。
- 线程标题已修改为阶段 16。
- 已阅读 Planning with Files 技能说明。
- 已确认 `main` 是阶段 15 合并后的状态。
- 已确认 `phase-15-complete -> a844948`，不移动既有 tag。
- 已创建并切换阶段 16 分支。
- 三份 Planning with Files 文件已校准为阶段 16。

### Phase 1

- Phase 1 目标是把阶段 16 的风险闭环口径固化成可测试设计。
- 新增 `docs/stage16_quality_risk_closure.md`。
- 文档明确阶段 16 只处理阶段 15 报告暴露的 real decompose error 和 Answer Coverage high/medium 风险。
- 文档定义 `data/evaluation/stage16_decompose_diagnostics.csv`、`data/evaluation/stage16_answer_coverage_closure.csv`、`data/evaluation/stage16_quality_closure_summary.csv` 和 `docs/stage16_quality_closure_report.md`。
- 文档把 decompose 真实错误拆成 `provider_network_ssl_eof`、`provider_timeout`、`real_config_missing`、`provider_response_error`、`script_timeout_or_partial_output` 和 `needs_manual_review`。
- 文档明确 `risk_before` / `risk_after` 不能只凭来源命中自动降级，Answer Coverage 需要看回答是否覆盖 `expected_answer_points`。
- 文档明确 `/quality-report` 保持只读，不触发真实 API，不写数据库，不改变核心 RAG API。
- 新增 `tests/test_stage16_quality_risk_closure.py`，覆盖核心产物、错误分类、Answer Coverage 闭环、API 兼容、安全边界和人工核验边界。
- Phase 1 测试结果：`3 passed`。

### Phase 2

- Phase 2 目标是把阶段 15 的 real decompose error 从笼统 high 风险变成可解释诊断结论。
- 已阅读 `scripts/evaluate_stage15_real_config.py`、`scripts/evaluate_decompose.py`、`app/services/retrieval/embedding.py` 和 `app/services/retrieval/decompose.py`。
- `real_config_status.csv` 中 decompose error 的 traceback 被阶段 15 截断，只保留到 `evaluate_question` 附近；阶段 16 诊断需要结合 `docs/progress.md` 中的 SSL EOF 记录。
- 新增 `scripts/analyze_stage16_decompose_diagnostics.py`。
- 新增 `tests/test_analyze_stage16_decompose_diagnostics.py`。
- 新增 `data/evaluation/stage16_decompose_diagnostics.csv`。
- 当前诊断结果：
  - status_before=`error`
  - status_after=`classified_external_provider_error`
  - error_type=`ssl_eof`
  - root_cause=`provider_network_ssl_eof`
  - reproducibility=`recorded_from_stage15_real_rerun`
  - safe_to_retry=`yes`
  - blocking_status=`manual_retry_required`
- 改进 `scripts/evaluate_stage15_real_config.py` 的错误摘要压缩方式：长错误保留开头和结尾，避免 traceback 末尾的 SSL/timeout 关键字被截掉。
- 阶段 16 没有默认重跑真实 decompose，没有访问真实 API。
- Phase 2 测试结果：诊断脚本 `7 passed`，阶段 15 真实配置回归 `13 passed`。

### Phase 3

- Phase 3 目标是把阶段 15 的 1 条 high 和 8 条 medium Answer Coverage 风险逐条闭环。
- 新增 `scripts/evaluate_stage16_answer_coverage_closure.py`。
- 新增 `tests/test_evaluate_stage16_answer_coverage_closure.py`。
- 新增 `data/evaluation/stage16_answer_coverage_closure.csv`。
- 阶段 16 闭环逻辑只读取阶段 15 脱敏答案摘要、来源标题、expected_answer_points、review_note 和指标，不调用真实 API。
- 为中文连续句补充阶段 16 领域关键词检查，避免把中文 expected_answer_points 整句当成一个词而误判未覆盖。
- 当前闭环结果：
  - risk_after high=1。
  - risk_after medium=3。
  - risk_after low=5。
- 唯一 high：`user_mixed_itz_strength`，root_cause=`provider_timeout`，decision=`blocking`，原因是真实回答超时，尚不能证明 Answer Coverage。
- medium：
  - `user_cn_colloquial_compactness`：source_detail_limited，现场检测细节不足。
  - `user_en_steel_fiber_filling`：source_detail_limited，回答方向正确但上下文细节有限。
  - `user_cn_shear_key`：source_detail_limited，主要基于题名/元数据确认关系，机理细节不足。
- low：
  - `user_en_freeze_thaw`
  - `user_cn_creep`
  - `user_mixed_cost_emission`
  - `user_cn_porosity_compression`
  - `user_en_seismic_ratio`
- Phase 3 测试结果：`7 passed`。

### Phase 4

- Phase 4 目标是把 decompose 诊断和 Answer Coverage 闭环结果汇总成发布前质量结论，并更新 `/quality-report` 只读页面。
- 新增 `scripts/build_stage16_quality_closure_report.py`。
- 新增 `tests/test_build_stage16_quality_closure_report.py`。
- 新增 `data/evaluation/stage16_quality_closure_summary.csv`。
- 新增 `docs/stage16_quality_closure_report.md`。
- 更新 `app/frontend/quality_report.html` 为阶段 16 质量风险闭环报告入口。
- 当前 quality gate 为 `review_required/high`，不是全部通过：
  - real decompose 仍为 `provider_network_ssl_eof`，需要人工核验时显式重试真实 provider。
  - `user_mixed_itz_strength` 仍为 Answer Coverage high/blocking，因为真实回答超时，不能证明覆盖 ITZ 与强度的期望点。
  - 3 条 medium 为 `source_detail_limited`，建议保留人工审阅。
  - 5 条 low 可作为阶段 16 闭环通过证据。
- `/quality-report` 仍是只读 HTML 报告，不触发真实 API，不写数据库，不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat` 或 `POST /agent/query`。
- Phase 4 测试结果：`2 passed`。

### Phase 5

- Phase 5 目标是证明阶段 16 的诊断、闭环表、质量报告和前端只读入口没有破坏既有 RAG/API 链路。
- 阶段 16 三个脚本复跑稳定：
  - `scripts/analyze_stage16_decompose_diagnostics.py` -> `provider_network_ssl_eof`，`manual_retry_required`。
  - `scripts/evaluate_stage16_answer_coverage_closure.py` -> 9 rows，high=1、medium=3、low=5。
  - `scripts/build_stage16_quality_closure_report.py` -> 6 rows，quality gate=`review_required/high`。
- 聚焦回归覆盖阶段 16、frontend、search、vector、hybrid、decompose、chat、brain、agent、sources、documents，结果为 `80 passed`。
- 全量测试结果为 `320 passed`。
- 唯一测试修正是 `tests/test_frontend_app.py`：旧断言仍检查“阶段 15 质量审阅报告”，阶段 16 已将页面标题更新为“阶段 16 质量风险闭环报告”，因此同步测试期望。
- 当前质量结论保持诚实阻断：阶段 16 完成风险分类和部分降级，但仍等待人工核验，不提交、不打 tag、不推送。

### Phase 6

- Phase 6 目标是完成普通文档、AGENT 判断和 Obsidian 草稿收尾，并停在用户人工核验前。
- 已更新 `README.md`：
  - 当前阶段改为阶段 16 待人工核验。
  - 补充阶段 16 核心产物、脚本运行方式、质量闭环结果和 `320 passed`。
- 已更新 `docs/progress.md`：
  - 新增阶段 16 最新状态，记录分支、阶段 15 tag/main 状态、产物、测试、遗留风险和面试表达。
- 已更新 `docs/architecture.md`：
  - 补充阶段 16 evaluation/reporting 闭环数据流。
  - 明确 `/quality-report` 仍只读，不改变核心 API。
- 已更新 `docs/data_sources.md`：
  - 明确阶段 16 只新增诊断、复核和报告产物，不新增资料来源。
  - 明确不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- 已更新 `AGENT.MD`：
  - 补充阶段 16 分支、产物、测试结果、关键经验。
  - 明确阶段 16 当前没有 tag，需用户人工核验后才允许提交、tag、push。
- 已补齐 Obsidian：
  - `obsidian-vault/阶段/阶段 16 - 真实质量风险闭环.md`
  - `obsidian-vault/阶段汇报/阶段 16 - 真实质量风险闭环/阶段 16 Phase 汇报索引.md`
  - Phase 0 到 Phase 6 的 7 篇小 Phase 汇报。
  - `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`、`obsidian-vault/分类/评测体系.md`。
  - 新增知识点 `obsidian-vault/知识点/真实质量风险闭环.md`。
- Obsidian 小 Phase 汇报 10 项小节检查：Phase 0 到 Phase 6 均包含 `## 1. 本 Phase 目标` 和 `## 10. 面试表达`。
- `.gitignore` 已确认包含 `obsidian-vault/` 和 `obsidian-vault/**`。
- 当前仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR 创建。

### Phase 7

- 用户要求先解决当前 decompose 运行问题。
- 显式运行 `scripts/evaluate_decompose.py --embedding-provider openai-compatible --chat-provider openai-compatible --include-all --out data/evaluation/stage16_decompose_real_retry_results.csv`，首次复现 SSL EOF。
- 最小 embedding 探针显示：同一 provider 同时携带 `Authorization: Bearer` 和 `api-key` 请求头时，`/embeddings` 返回 200。
- 修复 `OpenAICompatibleEmbeddingProvider`：补齐 `api-key` 请求头，与 `OpenAICompatibleChatModelProvider` 保持一致。
- 修复后 real decompose 已越过 embedding SSL EOF；随后真实 chat 生成出现 30 秒读取超时。
- 用真实 embedding + deterministic chat 验证 decompose 检索链路：`10/10 passed`。
- 用真实 embedding + 真实 chat，并设置 `CHAT_MODEL_TIMEOUT_SECONDS=120` 验证完整 decompose：`10/10 passed`。
- 新增 `data/evaluation/stage16_decompose_real_retry_results.csv` 和 `data/evaluation/stage16_decompose_real_embedding_retry_results.csv`。
- 扩展 `scripts/analyze_stage16_decompose_diagnostics.py`：
  - 支持读取 retry results。
  - 支持识别项目 CSV 中的 `yes/no` 布尔值。
  - retry 全通过时输出 `status_after=retry_completed`、`blocking_status=not_blocking`。
- 更新 `scripts/build_stage16_quality_closure_report.py` 的 overall 文案：decompose 已重试通过后，剩余 high 阻断指向 Answer Coverage。
- 当前 decompose 结论：不再是 high 阻断；阶段 16 quality gate 仍为 `review_required/high`，原因是 Answer Coverage 仍有 1 条 high。

## Term Explanations

| Term | Meaning in this project |
|---|---|
| stage14_real | `data/evaluation/stage14_real/`，保存真实配置复跑结果或 error/skipped 状态 |
| real_config | 使用本地 `.env` 中真实 embedding/chat provider 的评测配置 |
| Decompose | 把复杂问题拆成子 query，再合并证据的检索增强能力 |
| SSL EOF | HTTPS 连接读取阶段异常结束，本项目阶段 15 出现在真实 embedding 请求中 |
| Answer Coverage | 回答是否覆盖用户问题期望的关键技术点 |
| Faithfulness | 回答是否忠于检索证据，没有引入来源外事实 |
| Citation Quality | 引用是否能追溯，并支撑回答中的关键说法 |
| root_cause | 风险或失败的根因分类，例如 provider_timeout、network_ssl_eof、answer_missing |
| quality gate | 阶段质量闸口，用来判断是否可以进入下一阶段或仍需人工阻断 |
| closure_ready/medium | 阶段 16 质量门槛状态；表示没有阻断型 high 风险，但仍有可接受的人工审阅或资料细节不足 |
| blocking | 阻断决策；表示风险仍不能放行到下一阶段，需要人工处理或外部状态变化 |
| provider_network_ssl_eof | 阶段 16 根因分类；表示真实 provider 或网络层在 HTTPS 读取阶段中断，不等同于本地 deterministic decompose 失败 |
| manual_retry_required | 阶段 16 阻断状态；表示当前不应伪造成通过，但可在人工核验时显式重试真实配置 |
| source_detail_limited | 阶段 16 根因分类；表示回答忠于来源且有引用，但当前资料或摘要细节不足，适合作为 medium 人工审阅项 |
| provider_timeout | 阶段 16 根因分类；表示真实模型或 provider 请求超时，不能证明回答覆盖度 |
| accepted_with_review | 阶段 16 决策；表示当前可以保留为人工审阅样例，但不能作为完全通过证据 |
| review_required/high | 阶段 16 总质量门槛；表示风险已分类并有 next_action，但仍存在发布前人工阻断项 |
| quality_closure_summary | 阶段 16 汇总表，把 decompose 和 Answer Coverage 的 risk_before/risk_after 合并成可审阅质量结论 |
| focused regression | 聚焦回归测试；只跑与本阶段改动和关键 API 有关的一组测试，用来快速发现连带破坏 |
| full test suite | 全量测试；运行全部测试文件，用来证明阶段收尾前整体链路没有已知回归 |
| manual verification handoff | 人工核验交接；开发和验证完成后先停下，等待用户检查后再提交、tag 和推送 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| 阶段 15 之后用户要求先人工核验 | 用户明确要求不要本地提交、不要提交 GitHub | 阶段 16 计划已加入 no commit/tag/push/PR 收尾标准 |
| real decompose SSL EOF | stage15 quality report 和 real_config_status 记录 decompose error | Phase 2 排查并建立错误分类或修复 |
| Answer Coverage high 风险 | `user_mixed_itz_strength` 真实回答超时 | Phase 3 优先闭环 |
| medium 样例仍需人工审阅 | 8 条 medium 都是 answer_coverage=review | Phase 3 建立可解释闭环表 |
| 阶段 15 错误摘要截断丢失尾部关键字 | `real_config_status.csv` 中 decompose 只保留 traceback 前半段 | 阶段 16 新增诊断脚本结合 progress 证据；同时改进未来错误摘要保留头尾 |
| 中文 expected_answer_points 分词过粗 | 阶段 15 的简单词项检查可能把中文句子当成一个整体词 | 阶段 16 增加领域关键词组检查，例如孔隙率/抗压、剪力键/冷缝、成本/工期/碳排放 |
| 阶段 16 仍有 high 阻断 | decompose 需要真实 provider 人工重试，`user_mixed_itz_strength` 真实回答超时 | Phase 4 quality gate 明确为 `review_required/high`，不伪造成通过 |
| 前端测试仍检查阶段 15 标题 | `test_quality_report_is_served_read_only` 失败，页面实际已更新为阶段 16 报告 | 同步测试断言到阶段 16 标题和人工核验边界；聚焦回归与全量测试均通过 |
| 阶段 16 不能立即创建 tag | 用户明确要求先人工核验，可能追加功能或小阶段 | 文档和 AGENT 均记录当前未提交、未 tag、未推送，等待用户明确确认 |

## Resources

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage15_real_review_report.md`
- `docs/stage15_quality_report.md`
- `data/evaluation/stage15_quality_summary.csv`
- `data/evaluation/stage15_answer_coverage_review.csv`
- `data/evaluation/stage14_real/real_config_status.csv`
- `data/evaluation/stage14_embedding_comparison.csv`
- `scripts/evaluate_stage15_real_config.py`
- `scripts/evaluate_decompose.py`
- `scripts/build_stage15_quality_report.py`
- `app/services/retrieval/embedding.py`
- `app/services/retrieval/decompose.py`
- `app/services/brain/service.py`
- `app/frontend/quality_report.html`
- `tests/test_evaluate_stage15_real_config.py`
- `tests/test_evaluate_stage15_answer_coverage_review.py`
- `tests/test_build_stage15_quality_report.py`
- `scripts/analyze_stage16_decompose_diagnostics.py`
- `data/evaluation/stage16_decompose_diagnostics.csv`
- `scripts/evaluate_stage16_answer_coverage_closure.py`
- `data/evaluation/stage16_answer_coverage_closure.csv`
- `scripts/build_stage16_quality_closure_report.py`
- `data/evaluation/stage16_quality_closure_summary.csv`
- `docs/stage16_quality_closure_report.md`
