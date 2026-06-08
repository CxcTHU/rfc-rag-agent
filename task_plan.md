# Task Plan: 阶段 17 - 检索架构升级

## Goal

在阶段 16 已完成人工核验、提交、合并并创建 `phase-16-complete` tag 的基础上，完成阶段 17：检索架构升级。阶段 17 的重点不是引入复杂 Agent 框架，而是增强检索工程本身，让关键词精确匹配、语义向量召回、融合排序、上下文组装和质量评测形成更稳定的 RAG 检索流水线。

核心链路：

```text
阶段16质量结论
-> 检索架构设计
-> 父子块或邻近上下文扩展
-> BM25 lexical retriever
-> BM25 + vector 多通道召回
-> RRF 融合、去重、轻量 rerank
-> evidence confidence 与 context assembly
-> 对比旧 keyword/vector/hybrid baseline
-> API/Brain/chat/agent 兼容
-> 文档 / Obsidian 草稿收尾
-> 停在用户人工核验待提交状态
```

本阶段不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不新增爬虫或外部资料来源、不让真实 API 成为 CI 或本地全量测试前提。HyDE 仍只做离线实验，不进入默认链路或自动回归。HNSW/FAISS/Qdrant/PGVector 暂不作为第一优先级，除非评测证明 SQLite 全量扫描已成为瓶颈。

阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。必须等待用户人工核验和明确确认后，才允许进入提交、tag 和 GitHub 推送流程。

## Current Phase

Phase 9 complete。在 Phase 0-8 已完成开发、测试、普通文档和 Obsidian 草稿的基础上，追加完成阶段 17 小 Phase 9「检索升级人工复核与接入建议」：建立人工复核结果表、给出默认链路接入建议、补齐报告与文档。当前仍停在用户人工核验前状态，尚未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

## Phases

### Phase 0: 阶段启动与规划校准

- [x] 设置线程 goal。
- [x] 将线程标题修改为 `阶段17-检索架构升级`。
- [x] 阅读 Planning with Files 规则。
- [x] 确认当前 Git 起点：`main` 已包含阶段 16 合并提交。
- [x] 确认 `phase-16-complete` 指向阶段 16 最终功能提交且是 `main` 祖先，不移动已有阶段 tag。
- [x] 从阶段 16 合并后的 `main` 创建并切换到 `codex/phase-17-retrieval-architecture-upgrade`。
- [x] 阅读阶段 17 启动所需文档、阶段 16 设计和闭环报告、旧规划文件。
- [x] 阅读 `app/services/retrieval`、`app/services/brain`、`app/api/search.py`、搜索评测脚本和相关测试。
- [x] 使用 Planning with Files 校准阶段 17 的 `task_plan.md`、`findings.md`、`progress.md`。
- 验证方式：线程标题、goal、Git 分支/tag 检查、规划文件检查。
- 文档收尾要求：记录阶段 17 起点、tag 状态、当前分支、阶段 16 遗留质量风险和“不提交、不打 tag、不推送”边界。
- Status: complete

### Phase 1: 阶段 17 设计文档与检索流水线口径

- [x] 新增 `docs/stage17_retrieval_architecture_upgrade.md`。
- [x] 明确阶段 17 的目标、输入、检索流水线、父子块/邻近上下文策略、BM25、RRF、评测方法、安全边界和完成标准。
- [x] 明确旧 `KeywordSearchService`、`VectorSearchService`、`HybridSearchService` 的 baseline 地位。
- [x] 明确如果升级未优于旧 hybrid，默认链路保持旧 hybrid，不用不稳定升级覆盖稳定路径。
- [x] 补充设计文档测试，覆盖关键术语、产物、API 兼容、安全边界和 no submit 边界。
- 验证方式：文档测试和字段检查。
- 文档收尾要求：在 `findings.md` 记录阶段 17 技术决策和新词解释。
- Status: complete

### Phase 2: 父子块或邻近上下文扩展

- [x] 复核 `documents`、`chunks`、`chunk_embeddings` schema，优先采用不改数据库的相邻 chunk / 同 document context expansion。
- [x] 建立可复用 context expansion 工具，支持按 `document_id` 和 `chunk_index` 拉取相邻上下文。
- [x] 保证返回给 API 的核心 chunk 字段兼容，扩展上下文只进入回答上下文或解释字段，不破坏旧响应模型。
- [x] 补充测试覆盖首尾 chunk、跨 document 禁止扩展、空结果、上下文长度控制。
- 验证方式：服务单测、Brain/prompt 相关测试。
- 文档收尾要求：记录父子块与邻近上下文的取舍，说明为何暂不做数据库迁移。
- Status: complete

### Phase 3: BM25 lexical retriever

- [x] 新增或改进 BM25 lexical retriever，保留 `KeywordSearchService` 作为旧 baseline。
- [x] 设计中文/英文分词策略，复用现有 query normalize、synonym expansion 和领域术语。
- [x] 支持标题、heading、content、source_type 权重。
- [x] 补充空查询、中文术语、英文短语、标题加权、排序稳定性和 metadata 控制测试。
- 验证方式：BM25 单测和 keyword baseline 兼容测试。
- 文档收尾要求：在 `findings.md` 解释 BM25 是什么、在本项目哪里出现、有什么作用、面试怎么说。
- Status: complete

### Phase 4: BM25 + vector 多路召回与 RRF 融合

- [x] 新增或改进 BM25+vector 融合服务。
- [x] 实现 merge、deduplicate、RRF ranking、可解释 score/provenance，不用不同尺度分数硬加权冒充融合。
- [x] 保留旧 `HybridSearchService` 输出，新增 upgraded retrieval 产物或服务名称，避免破坏旧 API。
- [x] 明确 keyword_score、vector_score、bm25_rank、vector_rank、rrf_score、matched_channels 等 provenance 字段。
- [x] 补充 RRF、去重、并列排序、单通道退化、空结果和异常输入测试。
- 验证方式：融合服务单测、旧 hybrid 回归。
- 文档收尾要求：记录 RRF 和 deduplicate 的新词解释与关键决策。
- Status: complete

### Phase 5: 轻量 rerank、evidence confidence 与 context assembly

- [x] 把升级检索结果接入轻量 rerank 或现有 topic anchor / evidence confidence 逻辑，保持可解释。
- [x] 判断 Brain 默认是否切换到升级检索；若评测未证明更优，则保留旧 hybrid 默认，只提供阶段 17 评测入口。
- [x] 校准 context assembly，让邻近上下文服务回答，但引用仍追溯到核心 chunk。
- [x] 补充 Brain、chat、agent 兼容测试。
- 验证方式：Brain workflow、chat、agent 聚焦测试。
- 文档收尾要求：说明默认链路是否改变及原因。
- Status: complete

### Phase 6: 阶段 17 评测与旧 baseline 对比

- [x] 新增阶段 17 评测脚本和结果表。
- [x] 评测表至少记录 query_id、baseline_hit、upgraded_hit、source_match、rank_before、rank_after、retrieval_mode、decision、evidence。
- [x] 复跑 keyword/vector/hybrid baseline，不覆盖旧结果；阶段 17 输出独立 CSV。
- [x] 生成阶段 17 检索架构升级报告，说明优势、回归、默认链路决策和后续建议。
- [x] 若升级未优于旧 hybrid，明确阻断原因并保持默认链路不变。
- 验证方式：评测脚本单测、CSV schema 检查、脚本复跑。
- 文档收尾要求：在 `progress.md` 记录所有评测命令和结果。
- Status: complete

### Phase 7: API/Brain/chat/agent 回归验证

- [x] 保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 不被破坏。
- [x] 运行 documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend 相关聚焦回归。
- [x] 运行阶段 17 新增测试。
- [x] 运行全量测试。
- 验证方式：聚焦回归和全量测试。
- 文档收尾要求：记录测试结果、残余风险和人工核验重点。
- Status: complete

### Phase 8: 普通文档、Obsidian 草稿与待人工核验收尾

- [x] 更新 `README.md`，说明阶段 17 当前能力、评测结果、默认链路决策、使用边界和下一阶段建议。
- [x] 更新 `docs/progress.md`，记录阶段 17 完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充阶段 17 检索流水线、BM25/RRF、context expansion 和 Brain/API 边界。
- [x] 更新 `docs/data_sources.md`，说明阶段 17 只新增评测/报告产物，不新增资料来源、不保存受限全文或 API key。
- [x] 判断并更新 `AGENT.MD`，记录阶段 17 经验、下一阶段建议和人工核验后再提交/tag/push的流程约束。
- [x] 统一补齐 Obsidian 本地知识库：阶段 17 阶段页、阶段汇报目录、Phase 0 到最终 Phase 汇报、索引、分类页和知识点。
- [x] 确认每篇 Obsidian Phase 汇报包含 10 个固定小节。
- [x] 确认 `obsidian-vault/` 仍被 Git 忽略，不纳入后续提交。
- [x] 确认没有执行 `git add`、`git commit`、`git tag`、`git push` 或 PR 创建。
- [x] 最终汇报当前分支、主要改动、测试结果、未提交状态和人工核验重点。
- 验证方式：文档检查、Obsidian 小节检查、Git 状态检查。
- 文档收尾要求：所有普通文档与 Obsidian 阶段知识库同步完成，但停在用户人工核验前。
- Status: complete

### Phase 9: 检索升级人工复核与接入建议

- [x] 确认当前分支、Git 状态、`phase-16-complete` tag、`main` 合并状态，以及 Phase 0-8 未 add/commit/tag/push；不移动已有 tag。
- [x] 逐条复核 `data/evaluation/stage17_retrieval_upgrade_results.csv` 中 `source_match=no`、排序变化明显、evidence 较弱样例。
- [x] 新增 `data/evaluation/stage17_retrieval_upgrade_manual_review.csv`，含 query_id、query、baseline_hit、upgraded_hit、source_match、rank_before、rank_after、review_decision、retrieval_risk、evidence、acceptance_reason、tuning_suggestion、default_chain_recommendation、notes。
- [x] review_decision 使用 acceptable/needs_tuning/regression/defer，不把未验证样例伪造成成功。
- [x] 明确判断 `RRFHybridSearchService`、`BM25SearchService`、`ContextExpansionService` 是否进入默认 `/search/hybrid`、Brain、chat、agent；证据不足时建议保持候选/配置开关，不偷偷替换默认 `HybridSearchService`。
- [x] 让 `scripts/evaluate_stage17_retrieval_upgrade.py` 的 `write_report` 可复现地纳入 Phase 9 摘要，并据已有结果 CSV 重生成报告（不跑检索、不碰 DB、不触发真实 API）。
- [x] 新增 `tests/test_stage17_manual_review.py`，校验复核表列齐全、取值合法、退化样例必须有证据与调优建议。
- [x] 更新 `docs/stage17_retrieval_upgrade_report.md` 与 `docs/stage17_retrieval_architecture_upgrade.md` 的 Phase 9 结论。
- [x] 追加 `task_plan.md`、`findings.md`、`progress.md`、`docs/progress.md` 的 Phase 9，并按需更新 README、docs/architecture、docs/data_sources、AGENT.MD 的阶段 17 最终结论。
- [x] 补 Obsidian 阶段 17 Phase 9 小汇报（10 小节）并更新索引；Obsidian 不提交 Git。
- [x] 运行聚焦回归与全量测试，确认既有链路未被破坏。
- [x] 停在用户人工核验前，不执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。
- 验证方式：复核表校验测试、报告字段检查、聚焦回归、全量测试、Git 状态检查。
- 文档收尾要求：在 `findings.md` 与 `progress.md` 记录复核结论、默认链路接入建议和人工核验重点。
- Status: complete

## Final Verification Targets

| Check | Expected |
|---|---|
| Branch | `codex/phase-17-retrieval-architecture-upgrade` |
| Previous tags | `phase-16-complete` and older phase tags remain unmoved |
| No submit actions | no `git add`, no commit, no tag, no push, no PR |
| Design doc | `docs/stage17_retrieval_architecture_upgrade.md` exists and covers retrieval upgrade flow |
| Context expansion | Adjacent or parent context strategy exists with tests and compatibility boundary |
| BM25 | BM25 lexical retriever exists or is integrated with tests |
| Fusion | BM25+vector RRF fusion exists with provenance and no hard scale mixing |
| Baseline comparison | Stage 17 evaluation table/report compares upgraded retrieval with old baseline |
| Manual review | `stage17_retrieval_upgrade_manual_review.csv` records per-query review_decision and default-chain recommendation |
| Default decision | Default retrieval changes only if evidence proves no regression; Phase 9 recommends keep_existing_hybrid |
| API contract | search/vector/hybrid/chat/agent and `/quality-report` remain compatible |
| Tests | Stage 17 focused tests and full test suite pass |
| Docs | README, docs/progress, docs/architecture, docs/data_sources and AGENT.MD judgment updated |
| Obsidian | Stage 17 local knowledge base updated and remains ignored by Git |
| Final state | Waiting for user manual verification before commit/tag/push |

## Decisions Made

| Decision | Rationale |
|---|---|
| 目标分支为 `codex/phase-17-retrieval-architecture-upgrade` | 与阶段 17 目标和用户要求一致 |
| 从阶段 16 合并后的 `main` 创建阶段 17 分支 | `main` 当前已包含阶段 16 合并提交，是正确起点 |
| 不移动已有阶段 tag | 阶段 tag 必须稳定指向各阶段最终功能提交 |
| 阶段 17 不提交、不打 tag、不推送 | 用户要求先人工核验，可能追加功能和小阶段 |
| 保留旧 hybrid baseline | 阶段 17 要证明升级有效，不能用新实现覆盖稳定旧链路 |
| 优先 BM25 + vector + RRF | 当前检索瓶颈是召回和排序可解释性，不是向量索引性能 |
| HNSW/外部向量库暂不优先 | 当前资料量尚未证明 SQLite 全量扫描是瓶颈 |

## Term Explanations

| Term | Meaning in this project |
|---|---|
| BM25 | 经典词法检索算法，用词频、文档频率和长度归一化衡量 query 与 chunk 的匹配度 |
| lexical retriever | 词法检索器，按字面词、短语、术语匹配资料；阶段 17 用 BM25 增强它 |
| RRF | Reciprocal Rank Fusion，倒数排名融合；用排名而非原始分数合并 BM25 与 vector |
| deduplicate | 去重；多路召回命中同一个 chunk 时只保留一个候选并合并来源信息 |
| provenance | 来源过程记录；说明结果来自 BM25、vector 或两者，以及排名和分数 |
| context expansion | 上下文扩展；核心 chunk 命中后，拉取相邻 chunk 或父级上下文帮助回答 |
| baseline | 基线；旧 keyword/vector/hybrid 结果，用来判断阶段 17 是否真的变好 |
| quality gate | 阶段质量闸口，说明当前能否进入下一阶段或仍需人工阻断 |

## Notes

- 本文件由 Planning with Files 维护，是阶段 17 的任务顺序与完成标准。
- 每个 Phase 完成后必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 17 开发过程中暂不写入 Obsidian 小 Phase 汇报；Phase 8 统一补齐。
- 阶段 17 收尾后必须停在用户人工核验前，不提交、不打 tag、不推送。
