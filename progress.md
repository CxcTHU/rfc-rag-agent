# Progress Log

## Session: 2026-06-07

### Phase 0: 阶段启动与规划校准

- Status: complete
- 解决的问题：从阶段 16 完成、提交、tag 并合并后的 `main` 起步，把当前线程、goal、分支、tag 和规划文件切换到阶段 17。
- 在 RAG 链路中的位置：阶段启动前置工作，确保 BM25、RRF、多路召回、上下文扩展和评测对比基于阶段 16 的稳定版本推进。
- 为什么现在做：阶段 16 已把真实质量风险闭环到可审阅状态；下一步最值得增强的是检索架构本身，而不是先引入 LangGraph 或更复杂 Agent。
- 已完成工作：
  - 设置本线程 goal。
  - 将线程标题修改为 `阶段17-检索架构升级`。
  - 阅读 Planning with Files 技能说明。
  - 读取并确认当前 Git 状态、`main`、`phase-16-complete` 和最近提交。
  - 确认 `main` 当前为 `ff48056 Merge phase 16 quality risk closure`。
  - 确认 `phase-16-complete -> aaba285`，且该 tag 是 `main` 祖先；未移动已有阶段 tag。
  - 从阶段 16 合并后的 `main` 创建并切换到 `codex/phase-17-retrieval-architecture-upgrade`。
  - 阅读阶段 17 启动所需文档、阶段 16 设计文档、阶段 16 质量闭环报告、旧规划文件。
  - 阅读 `app/services/retrieval`、`app/services/brain/service.py`、`app/api/search.py`、`app/schemas/search.py` 和搜索评测脚本。
  - 发现 README 与 docs/progress 顶部仍保留阶段 16 待人工核验旧表述，已记录为阶段 17 文档校准项。
  - 用 Planning with Files 重写阶段 17 的 `task_plan.md`、`findings.md`、`progress.md`。
  - 明确阶段 17 Phase 顺序：设计文档、上下文扩展、BM25、RRF 融合、Brain/context assembly、评测对比、回归验证、文档与 Obsidian 收尾。

## Current Evidence

| Evidence | Result | Status |
|---|---|---|
| Goal | active, 阶段 17 开发到人工核验前状态 | pass |
| Thread title | `阶段17-检索架构升级` | pass |
| Starting branch | `main` before branch creation | pass |
| Main merge | `ff48056 Merge phase 16 quality risk closure` | pass |
| Phase 16 tag | `phase-16-complete -> aaba285` | pass |
| Phase 16 tag ancestry | `phase-16-complete is ancestor of main` | pass |
| Stage 17 branch | `codex/phase-17-retrieval-architecture-upgrade` created | pass |
| Planning files | Rewritten for stage 17 | pass |
| Submit boundary | no add/commit/tag/push/PR until user approval | pass |

## Test Results

| Test | Expected | Actual | Status |
|---|---|---|---|
| Phase 0 Git checks | Stage 16 merged, tag stable, branch created | pass | pass |
| Phase 1 design tests | Stage 17 design document covers artifacts, BM25/RRF, context expansion, API safety and manual verification boundary | 3 passed | pass |
| Phase 2 context expansion tests | Adjacent context expansion keeps core chunk identity, avoids cross-document expansion and handles limits | 5 passed | pass |
| Phase 3 BM25 tests | BM25 supports English/Chinese domain terms, title/heading scores, stable ordering and invalid inputs | 5 passed | pass |
| Phase 4 RRF fusion tests | RRF combines BM25/vector ranks, keeps provenance, degrades to BM25 and rejects invalid inputs | 4 passed | pass |
| Phase 5 context assembly tests | RRF optional context expansion works with prompt builder while preserving core chunk citations | 19 passed | pass |
| Phase 5 Brain/chat/agent compatibility | Default Brain/chat/agent behavior remains stable after upgraded retrieval service changes | 31 passed | pass |
| Phase 6 evaluation script tests | Stage 17 evaluation decision/report helpers produce required fields | 3 passed | pass |
| Phase 6 deterministic evaluation run | Stage 17 upgraded retrieval compared against old hybrid baseline | upgraded=15/15; baseline=15/15; improved=0; regression=0 | pass |
| Phase 7 focused regression | Stage 17 + documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend tests | 97 passed | pass |
| Phase 7 full test suite | Entire repository test suite | 343 passed | pass |
| Phase 8 Obsidian drafts | Stage 17 page, Phase index, Phase 0-8 reports, indexes and knowledge points updated | 9 phase reports; 10-section checks pass | pass |
| Phase 8 final full test suite | Entire repository test suite after ordinary docs and Obsidian drafts | 343 passed | pass |
| Final Git state | Branch and tag state before handoff | branch=`codex/phase-17-retrieval-architecture-upgrade`; no tag points at HEAD; changes unstaged/uncommitted | pass |
| Phase 9 manual review tests | Manual review CSV schema, controlled vocabulary, non-acceptable rows carry evidence/tuning, known rank regression flagged | 6 passed | pass |
| Phase 9 stage17 eval+review tests | Stage 17 eval helpers and manual review validation together | 9 passed | pass |
| Phase 9 focused regression | stage17 upgrade/manual_review + documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend | 103 passed | pass |
| Phase 9 full test suite | Entire repository test suite after Phase 9 | 349 passed | pass |

## Error Log

| Error | Attempt | Resolution |
|---|---|---|
| README/docs progress still say stage 16 pending manual verification | Phase 0 reading found stale top sections despite Git proving phase 16 is merged/tagged | Record as documentation calibration task for stage 17 |
| Stage 17 design test required explicit restricted fulltext wording | First Phase 1 design test run failed because the document had the combined phrase but not exact `不保存受限全文` | Added explicit safety bullet to `docs/stage17_retrieval_architecture_upgrade.md` |
| Chinese BM25 query missed contained domain terms | First BM25 test ranked English `strength` title above Chinese porosity/compression document | Added `expand_bm25_query_terms` to keep contained domain triggers such as `孔隙率` and `抗压` |
| PowerShell directory creation did not support `-LiteralPath` | First Obsidian directory creation command failed | Re-ran with `New-Item -Path`; directory creation succeeded |

### Phase 1: 阶段 17 设计文档与检索流水线口径

- Status: complete
- 解决的问题：阶段 17 涉及 BM25、RRF、上下文扩展、默认链路是否切换和评测对比，如果不先固定设计口径，后续容易把检索升级和核心 API 改动混在一起。
- 在 RAG 链路中的位置：retrieval/Brain 代码改动之前的架构设计层，定义多路召回、融合排序和上下文组装如何进入 RAG。
- 为什么现在做：阶段 16 已完成质量闭环；阶段 17 必须先说明“为什么升级检索、升级什么、如何证明升级有效”。
- 完成工作：
  - 新增 `docs/stage17_retrieval_architecture_upgrade.md`。
  - 明确阶段 17 输入、产物、目标流水线、父子块/邻近上下文策略、BM25、RRF、baseline 对比、API 边界和安全边界。
  - 明确如果升级未优于旧 hybrid，默认链路保持旧 `HybridSearchService`。
  - 新增 `tests/test_stage17_retrieval_architecture_upgrade.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage17_retrieval_architecture_upgrade.py -q` -> `3 passed`。

### Phase 2: 父子块或邻近上下文扩展

- Status: complete
- 解决的问题：检索命中的核心 chunk 可能足够精准，但内容太短，回答时缺少前后语境。
- 在 RAG 链路中的位置：检索召回之后、prompt context assembly 之前。
- 为什么现在做：BM25/RRF 后续会负责找核心证据；在那之前先建立上下文扩展工具，避免后续回答只看到孤立片段。
- 完成工作：
  - 新增 `app/services/retrieval/context_expansion.py`。
  - 新增 `ExpandedSearchResult` 和 `ContextExpansionService`。
  - 支持按 `document_id` 和 `chunk_index` 拉取相邻 chunk。
  - 保留核心 `chunk_id`、`chunk_index`、score 和来源字段，避免引用漂移。
  - 新增 `tests/test_context_expansion.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_context_expansion.py -q` -> `5 passed`。
- 当前结论：
  - 阶段 17 已具备 parent-like context expansion 的基础能力。
  - 当前暂不接入默认 Brain/chat 链路，等 BM25/RRF 和评测完成后再决定接入方式。

### Phase 3: BM25 lexical retriever

- Status: complete
- 解决的问题：旧关键词检索依赖手写命中规则和加权，缺少标准 lexical retrieval 算法，不适合直接与 vector 做架构级对比。
- 在 RAG 链路中的位置：query normalize/query expansion 之后、融合排序之前的词法召回通道。
- 为什么现在做：RRF 融合需要一个独立稳定的 BM25 排名通道；先建 BM25，后续才能和 vector 进行排名融合。
- 完成工作：
  - 新增 `app/services/retrieval/bm25_search.py`。
  - 新增 `BM25SearchService`、`BM25SearchResult`、BM25 IDF/TF 计算和 lexical length 估算。
  - 复用现有中英文术语归一化与同义词扩展。
  - 为中文无空格 query 补充领域触发词保留逻辑，解决“孔隙率/抗压”被整句吞掉的问题。
  - 新增 `tests/test_bm25_search.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_bm25_search.py -q` -> `5 passed`。

### Phase 4: BM25 + vector 多路召回与 RRF 融合

- Status: complete
- 解决的问题：BM25 分数和向量余弦分数不是同一尺度，直接加权容易不稳定。
- 在 RAG 链路中的位置：BM25 和 vector 两路召回之后、最终证据排序之前。
- 为什么现在做：Phase 3 已有 BM25 通道；现在需要将它与现有 vector 通道合成一个可评测的 upgraded retrieval。
- 完成工作：
  - 新增 `app/services/retrieval/rrf_fusion.py`。
  - 新增 `RRFHybridSearchService` 和 `RRFHybridSearchResult`。
  - 实现 BM25 + vector 候选 merge、按 `chunk_id` deduplicate、RRF ranking 和 provenance 记录。
  - 保留旧 `HybridSearchService`，不改变 `/search/hybrid` 默认行为。
  - 新增 `tests/test_rrf_fusion.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_rrf_fusion.py -q` -> `4 passed`。

### Phase 5: 轻量 rerank、evidence confidence 与 context assembly

- Status: complete
- 解决的问题：升级检索结果如果只返回孤立核心 chunk，回答上下文仍可能偏短；但如果直接把邻近 chunk 当引用，又会造成引用漂移。
- 在 RAG 链路中的位置：RRF 排序之后、prompt context assembly 之前。
- 为什么现在做：Phase 4 已有 RRF 融合结果；现在需要验证它能和上下文组装配合，同时不破坏 Brain 默认链路。
- 完成工作：
  - 扩展 `RRFHybridSearchService.search`，支持可选 `context_window` 和 `max_context_chars`。
  - `context_window=0` 为默认值，保持旧行为。
  - 启用上下文扩展时，`content` 包含相邻 chunk，`chunk_id` 仍指向核心命中 chunk。
  - `provenance` 记录 RRF 排名与 context expansion 信息。
  - 补充 RRF + prompt builder 测试。
  - 运行 Brain/chat/agent 聚焦测试，确认默认链路未被改变。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_rrf_fusion.py tests\test_context_expansion.py tests\test_prompt_builder.py -q` -> `19 passed`。
  - `.venv\Scripts\python.exe -m pytest tests\test_brain_service.py tests\test_brain_workflow.py tests\test_chat_api.py tests\test_agent_service.py -q` -> `31 passed`。
- 当前结论：
  - upgraded retrieval 已可选支持 context assembly。
  - 默认 Brain hybrid 路径暂不切换，等待阶段 17 评测对比后再决定。

### Phase 6: 阶段 17 评测与旧 baseline 对比

- Status: complete
- 解决的问题：BM25+vector RRF 已实现，但必须用独立评测证明它是否优于旧 hybrid，而不是凭感觉切默认链路。
- 在 RAG 链路中的位置：检索服务实现之后、默认链路决策之前的 evaluation/reporting 层。
- 为什么现在做：Phase 5 已确认升级检索可用于 context assembly 且不破坏 Brain；现在需要量化对比旧 baseline。
- 完成工作：
  - 新增 `scripts/evaluate_stage17_retrieval_upgrade.py`。
  - 新增 `tests/test_evaluate_stage17_retrieval_upgrade.py`。
  - 生成 `data/evaluation/stage17_retrieval_upgrade_results.csv`。
  - 生成 `docs/stage17_retrieval_upgrade_report.md`。
  - 评测表记录 baseline_hit、upgraded_hit、source_match、rank_before、rank_after、retrieval_mode、decision、evidence。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_evaluate_stage17_retrieval_upgrade.py -q` -> `3 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_stage17_retrieval_upgrade.py --provider deterministic` -> `upgraded=15/15 baseline=15/15 improved=0 regression=0`。
- 当前结论：
  - 阶段 17 upgraded retrieval 在 baseline 查询集上没有 regression。
  - 当前也没有证明优于旧 hybrid，因此默认链路暂不自动替换，进入人工核验候选状态。

### Phase 7: API/Brain/chat/agent 回归验证

- Status: complete
- 解决的问题：阶段 17 新增 retrieval service、context expansion 和评测脚本，需要证明它们没有破坏既有 API 和 RAG workflow。
- 在 RAG 链路中的位置：阶段收尾验证层，位于评测报告之后、普通文档和 Obsidian 收尾之前。
- 为什么现在做：只有聚焦回归和全量测试通过后，文档才能写入可靠的阶段结论。
- 完成工作：
  - 运行阶段 17 新增测试。
  - 运行 keyword/vector/hybrid/decompose/search API 回归。
  - 运行 chat/Brain/agent 回归。
  - 运行 sources/documents/frontend 回归。
  - 运行全量测试。
- 验证结果：
  - 聚焦回归：`.venv\Scripts\python.exe -m pytest tests\test_stage17_retrieval_architecture_upgrade.py tests\test_context_expansion.py tests\test_bm25_search.py tests\test_rrf_fusion.py tests\test_evaluate_stage17_retrieval_upgrade.py tests\test_keyword_search.py tests\test_vector_search.py tests\test_hybrid_search.py tests\test_decompose_retrieval.py tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_brain_service.py tests\test_brain_workflow.py tests\test_agent_service.py tests\test_agent_api.py tests\test_sources_api.py tests\test_documents_api.py tests\test_frontend_app.py -q` -> `97 passed`。
  - 全量测试：`.venv\Scripts\python.exe -m pytest -q` -> `343 passed`。
- 当前结论：
  - 阶段 17 新增代码没有已知回归。
  - 默认 hybrid、Brain、chat、agent 仍保持兼容。

### Phase 8: 普通文档、Obsidian 草稿与待人工核验收尾

- Status: complete
- 解决的问题：阶段 17 已完成开发和验证，但项目入口文档、AGENT 判断和 Obsidian 本地知识库需要同步，否则后续线程可能仍停留在阶段 16。
- 在 RAG 链路中的位置：阶段收尾与知识沉淀层，位于质量验证之后、用户人工核验和版本提交之前。
- 为什么现在做：用户要求阶段完成后先不要提交和推送，因此必须把“开发完成但待人工核验”的状态写清楚，避免误创建 tag。
- 完成工作：
  - 更新 `README.md`，写入阶段 17 当前状态、产物、评测结果、默认链路决策和人工核验边界。
  - 更新 `docs/progress.md`，新增阶段 17 最新状态和面试表达。
  - 更新 `docs/architecture.md`，补充阶段 17 检索架构升级数据流。
  - 更新 `docs/data_sources.md`，说明阶段 17 不新增资料来源、不保存敏感响应或受限全文。
  - 更新 `AGENT.MD`，记录阶段 17 经验、分支、测试结果和“人工核验后再提交/tag/push”规则。
  - 新增 Obsidian 阶段 17 阶段页、Phase 汇报索引、Phase 0 到 Phase 8 汇报和知识点。
  - 更新 Obsidian 首页、阶段索引、阶段汇报索引、评测体系分类和 RAG 链路分类。
- 验证结果：
  - Obsidian 阶段 17 下共有 9 篇 Phase 汇报和 1 篇 Phase 索引。
  - Phase 0 到 Phase 8 均包含固定 10 个小节。
  - `.gitignore` 确认包含 `obsidian-vault/`，阶段 17 Obsidian 文件被 Git 忽略。
  - 文档与 Obsidian 收尾后再次运行全量测试：`343 passed`。
  - `git tag --points-at HEAD` 无输出，确认当前未创建 `phase-17-complete` tag。
- 当前结论：
  - 阶段 17 收尾文档已同步。
  - 当前仍未提交、未打 tag、未推送，等待用户人工核验。

### Phase 9: 检索升级人工复核与接入建议

- Status: complete
- 解决的问题：阶段 17 升级评测显示 `upgraded=15/15, baseline=15/15, improved=0, regression=0`，但 hit 级 headline 掩盖了排序层变化；进入用户人工核验前，需要补齐逐条人工复核证据和默认链路接入建议。
- 在 RAG 链路中的位置：评测/复核层，位于阶段 17 评测报告之后、用户人工核验和版本提交之前。
- 为什么现在做：用户要求在 Phase 0-8 已完成但尚未提交的基础上追加 Phase 9，使阶段 17 以更完整状态进入人工核验、提交、tag 和推送流程。
- 完成工作：
  - 确认分支 `codex/phase-17-retrieval-architecture-upgrade`、HEAD `ff48056`、`phase-16-complete=aaba285` 为 `main` 祖先、HEAD 无 tag、Phase 0-8 未提交；未移动任何已有 tag。
  - 逐条复核 `data/evaluation/stage17_retrieval_upgrade_results.csv`，新增人工复核表 `data/evaluation/stage17_retrieval_upgrade_manual_review.csv`（14 acceptable、1 needs_tuning、0 regression、0 defer）。
  - 把 `mesoscopic_modeling`（rank 2 -> 7）标为 needs_tuning 与默认替换阻断证据；4 条等价文献换位的 `source_match=no` 标为 acceptable。
  - 扩展 `scripts/evaluate_stage17_retrieval_upgrade.py` 的 `write_report`，可复现地把 Phase 9 摘要写入报告；用已有结果 CSV 重生成 `docs/stage17_retrieval_upgrade_report.md`，不跑检索、不碰 DB、不触发真实 API。
  - 新增 `tests/test_stage17_manual_review.py`，强制非 acceptable/source_match=no 样例带证据与调优建议。
  - 更新 `docs/stage17_retrieval_architecture_upgrade.md` Phase 9 结论、`task_plan.md`、`findings.md`、`progress.md`、`docs/progress.md` 与 AGENT 阶段 17 证据。
  - 补 Obsidian 阶段 17 Phase 9 小汇报与索引（Git 忽略）。
- 默认链路接入建议：`RRFHybridSearchService`、`BM25SearchService`、`ContextExpansionService` 保持候选/配置开关，不替换默认 `HybridSearchService`、Brain、`/chat`、`/agent`；阻断理由是评测集 hit 饱和零增益 + 综述上浮排序软退化。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage17_manual_review.py tests\test_evaluate_stage17_retrieval_upgrade.py -q` -> `9 passed`。
  - 聚焦回归与全量测试结果见下方 Test Results 表。
- 当前结论：阶段 17 以 Phase 9 人工复核完整收尾，仍停在用户人工核验前，未 add/commit/tag/push。

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | Phase 9 complete; stage 17 fully wrapped, waiting for user manual verification before submission |
| Where am I going? | Toward user review, then commit/tag (`phase-17-complete`)/push only after explicit confirmation |
| What's the goal? | Add and complete stage 17 Phase 9 manual review + integration recommendation, then stop before add/commit/tag/push |
| What have I learned? | Hit-level "regression=0" masked a rank soft-degradation (mesoscopic_modeling 2->7); saturated eval set has no discrimination, so RRF stays candidate-only |
| What have I done? | Built manual review table, validation test, reproducible report Phase 9 summary, planning/entry/Obsidian updates; recommended keep_existing_hybrid |
