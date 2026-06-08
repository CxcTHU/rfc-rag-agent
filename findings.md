# Findings & Decisions

## Requirements

- 用户要求正式进入阶段 17：检索架构升级。
- 线程标题已修改为 `阶段17-检索架构升级`。
- goal 已设置为：完成阶段 17 的开发、测试、普通文档和 Obsidian 草稿收尾，并停在用户人工核验前状态。
- 目标分支为 `codex/phase-17-retrieval-architecture-upgrade`。
- 阶段 17 必须从阶段 16 完成、提交、合并到 `main`，并创建 `phase-16-complete` tag 的状态出发。
- 必须确认 `phase-16-complete` 指向阶段 16 最终功能提交，不移动已有阶段 tag。
- 阶段 17 开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR。
- 阶段 17 不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不新增爬虫或外部资料来源、不让真实 API 成为 CI 或本地全量测试前提。
- HyDE 仍只做离线实验，不进入默认链路或自动回归。
- HNSW/FAISS/Qdrant/PGVector 暂不作为第一优先级，除非评测证明 SQLite 全量扫描已成为瓶颈。
- 不得把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。

## Current Project Findings

- 当前工作区已切换到 `codex/phase-17-retrieval-architecture-upgrade`。
- `main` 当前提交为 `ff48056b8803471458cbf20618f541108b4d52a3`，提交信息为 `Merge phase 16 quality risk closure`。
- `phase-16-complete` 指向 `aaba285176d9162bad56e0a00bf2bd879261d1be`，是 `main` 的祖先。
- 已创建并切换阶段 17 分支。
- 旧 `task_plan.md`、`findings.md`、`progress.md` 均为阶段 16 工作记忆，需要改写为阶段 17。
- 当前 README 和 docs/progress 顶部仍保留“阶段 16 待人工核验”的旧文字，但 Git 状态证明阶段 16 已提交、打 tag 并合并；阶段 17 收尾需要修正入口文档状态。

## Stage 16 Quality Findings

- 阶段 16 decompose 当前闭环结论：真实重试后 `retry_completed`，根因为 `embedding_header_compatibility_and_chat_timeout`，不再是 high 阻断。
- 阶段 16 Answer Coverage 闭环表有 9 行：risk_after high=1、medium=3、low=5。
- 剩余 high 阻断样例为 `user_mixed_itz_strength`，根因是真实回答超时，不能证明 ITZ 与强度回答覆盖度。
- 3 条 medium 样例为 `source_detail_limited`，更适合后续通过检索、rerank 或上下文扩展改善证据细节。
- 阶段 17 不能用检索升级伪造成阶段 16 high 已解决；只能通过评测说明升级是否改善相关查询的召回和证据。

## Architecture Findings

- `documents` 表保存资料整体信息，`chunks` 表保存可检索片段，`chunk_embeddings` 表保存每个 chunk 的 embedding。
- `KeywordSearchService` 当前是规则关键词检索：query normalize、同义词扩展、标题/heading/content 加权、metadata 控制、来源均衡。
- `VectorSearchService` 当前使用 embedding 余弦相似度，并用 topic anchor 轻量提升主题相关结果。
- `HybridSearchService` 当前做法是关键词和向量各取候选，把各自分数按最大值归一化，再做加权相加和 both_match bonus。
- 阶段 17 要避免继续用不同尺度分数硬加权，改用 RRF 这种按排名融合的方式。
- `DecomposeRetrievalService` 当前在复杂问题拆解后调用 `HybridSearchService`，再按 `chunk_id` 去重并做 topic/source/both_match rerank。
- `BrainService` 的 hybrid 路径会先判断是否 decompose；若不拆解，则直接调用 `HybridSearchService`。
- `/chat` 和 Agent `answer_with_citations` 都复用 Brain，因此阶段 17 不能破坏 Brain 的旧输入输出。
- `/quality-report` 是只读质量报告入口，不参与检索升级，不触发真实 API。

## Evaluation Findings

- 旧评测脚本：
  - `scripts/evaluate_keyword_search.py`
  - `scripts/evaluate_vector_search.py`
  - `scripts/evaluate_hybrid_search.py`
- 旧结果：
  - `data/evaluation/keyword_results.csv`
  - `data/evaluation/vector_results.csv`
  - `data/evaluation/hybrid_results.csv`
- 阶段 17 应新增独立结果文件，不覆盖旧 baseline。
- 阶段 17 评测表至少记录 query_id、baseline_hit、upgraded_hit、source_match、rank_before、rank_after、retrieval_mode、decision、evidence。

## Data Source Findings

- 阶段 17 不新增外部文献资料来源。
- 阶段 17 只新增检索服务、评测脚本、评测 CSV、设计/报告文档和 Obsidian 本地草稿。
- 受限全文仍只允许保存在本地授权环境，不写入 Git、文档、CSV、测试或 Obsidian。
- 真实 API key 只允许存在本地 `.env` 或内存调用中。

## Technical Decisions

| Decision | Reason |
|---|---|
| 阶段 17 先写设计文档 | 检索架构升级会影响召回、排序、上下文和评测口径，必须先固定边界 |
| 保留旧 hybrid baseline | 旧 hybrid 已在多阶段评测中稳定，阶段 17 必须证明升级无回归 |
| BM25 作为新 lexical retriever | 比当前规则关键词更接近标准词法检索，适合与 vector 互补 |
| RRF 作为融合算法 | BM25 分数和向量余弦分数尺度不同，按排名融合更稳 |
| 父子块先用邻近上下文扩展 | 当前 schema 没有 parent_chunk 表；先不做数据库迁移，降低风险 |
| 默认链路是否切换取决于评测 | 如果升级没有优于旧 hybrid，则保持默认链路不变 |

## Phase Findings

### Phase 0

- Goal 已设置。
- 线程标题已修改为阶段 17。
- 已阅读 Planning with Files 技能说明。
- 已确认 `main` 是阶段 16 合并后的状态。
- 已确认 `phase-16-complete -> aaba285`，且是 `main` 祖先；不移动既有 tag。
- 已创建并切换阶段 17 分支。
- 已阅读阶段 17 启动所需文档、阶段 16 设计与报告、旧规划文件。
- 已阅读检索、Brain、search API 和搜索评测脚本。

### Phase 1

- Phase 1 目标是把阶段 17 的检索升级范围固化成可测试设计。
- 新增 `docs/stage17_retrieval_architecture_upgrade.md`。
- 文档明确阶段 17 的目标流水线：query normalize -> query expansion -> BM25 lexical retrieval -> vector retrieval -> merge -> deduplicate -> RRF ranking -> lightweight rerank -> context expansion -> evidence confidence -> context assembly。
- 文档明确 BM25 是新 lexical retriever，旧 `KeywordSearchService` 保留为 baseline。
- 文档明确 RRF 用排名融合，不允许继续用 BM25 和 vector 的不同尺度分数硬加权冒充融合。
- 文档明确父子块先用相邻 chunk / 同 document context expansion，不急于改数据库 schema。
- 文档明确 `/search`、`/search/vector`、`/search/hybrid`、`/chat`、`/agent/query`、`/quality-report` 兼容边界。
- 新增 `tests/test_stage17_retrieval_architecture_upgrade.py`。
- Phase 1 测试结果：`3 passed`。

### Phase 2

- Phase 2 目标是先解决“核心 chunk 命中但上下文不足”的问题。
- 当前数据库 `chunks` 表已有 `document_id` 和 `chunk_index`，足够支持不改 schema 的邻近上下文扩展。
- 新增 `app/services/retrieval/context_expansion.py`。
- 新增 `ExpandedSearchResult`，它保留核心 `chunk_id` 和 `chunk_index`，但 `content` 可替换为相邻 chunk 拼接后的上下文。
- 新增 `ContextExpansionService`，支持 `expand_result` 和 `expand_results`。
- 扩展规则只在同一个 `document_id` 内按 `chunk_index` 前后窗口拉取，不跨文档。
- 新增 `tests/test_context_expansion.py`。
- Phase 2 测试结果：`5 passed`。
- 当前决策：阶段 17 先不做 parent_chunk 表或数据库迁移；后续如章节级 parent chunk 需求明确，再设计 schema。

### Phase 3

- Phase 3 目标是新增标准词法检索器，补足旧规则关键词 baseline 的工程表达。
- 新增 `app/services/retrieval/bm25_search.py`。
- 新增 `BM25SearchService` 和 `BM25SearchResult`。
- BM25 复用现有 `normalize_text`、`expand_query_terms` 和 `SYNONYM_RULES`。
- 为中文无空格 query 补充 `expand_bm25_query_terms`：当 query 包含领域触发词，如“孔隙率”“抗压”，这些触发词也会作为独立 BM25 terms 保留。
- BM25 支持 title、heading、content 分区加权，并保留 `matched_terms`、`title_score`、`heading_score`、`content_score`。
- BM25 结果使用 source_type、document_id、chunk_index 做稳定排序，保留 metadata 控制。
- 新增 `tests/test_bm25_search.py`。
- Phase 3 测试结果：`5 passed`。

### Phase 4

- Phase 4 目标是把 BM25 与 vector 两路召回融合成可解释 upgraded retrieval。
- 新增 `app/services/retrieval/rrf_fusion.py`。
- 新增 `RRFHybridSearchService` 和 `RRFHybridSearchResult`。
- 融合逻辑先分别调用 `BM25SearchService` 与 `VectorSearchService`，再按 `chunk_id` 去重。
- RRF 分数只使用 `bm25_rank` 与 `vector_rank`，不硬加权 BM25 原始分数和 vector 余弦分数。
- `RRFHybridSearchResult` 记录 `bm25_score`、`vector_score`、`bm25_rank`、`vector_rank`、`rrf_score`、`matched_channels` 和 `provenance`。
- 向量索引缺失时，服务可退化到 BM25 单通道结果。
- 旧 `HybridSearchService` 未被替换，仍是默认 baseline。
- 新增 `tests/test_rrf_fusion.py`。
- Phase 4 测试结果：`4 passed`。

### Phase 5

- Phase 5 目标是让 upgraded retrieval 能服务 prompt context assembly，同时不提前切换默认 Brain 路径。
- 扩展 `RRFHybridSearchService.search`，新增可选参数 `context_window` 和 `max_context_chars`。
- 默认 `context_window=0`，因此旧调用不会自动扩展上下文。
- 启用 `context_window>0` 时，服务复用 `ContextExpansionService`，把相邻 chunk 拼接进 `content`，并保留核心 `chunk_id`。
- `RRFHybridSearchResult` 新增 `core_content`、`context_chunk_ids`、`context_window`。
- `provenance` 追加上下文窗口和扩展 chunk id，方便解释来源过程。
- 当前决策：阶段 17 评测完成前不切换 Brain 默认 hybrid；升级检索先作为独立服务和评测入口。
- Phase 5 context/prompt 聚焦测试结果：`19 passed`。
- Phase 5 Brain/chat/agent 聚焦测试结果：`31 passed`。

### Phase 6

- Phase 6 目标是用独立评测表证明 upgraded retrieval 是否优于旧 hybrid baseline。
- 新增 `scripts/evaluate_stage17_retrieval_upgrade.py`。
- 新增 `tests/test_evaluate_stage17_retrieval_upgrade.py`。
- 生成 `data/evaluation/stage17_retrieval_upgrade_results.csv`。
- 生成 `docs/stage17_retrieval_upgrade_report.md`。
- 评测字段包含 query_id、baseline_hit、upgraded_hit、source_match、rank_before、rank_after、retrieval_mode、decision、evidence。
- 实际 deterministic 评测结果：upgraded=15/15，baseline=15/15，improved=0，neutral=15，regression=0，unresolved=0。
- 报告 default_decision 为 `candidate_for_manual_review`。
- 当前默认链路决策：不自动替换旧 `HybridSearchService`；因为阶段 17 当前只证明无 regression，没有证明在 baseline 查询集上更优。

### Phase 7

- Phase 7 目标是证明阶段 17 新增检索服务、评测脚本和报告没有破坏既有 RAG/API 链路。
- 聚焦回归覆盖阶段 17、keyword/vector/hybrid/decompose、search/vector API、chat、Brain、agent、sources、documents、frontend。
- 聚焦回归结果：`97 passed`。
- 全量测试结果：`343 passed`。
- 当前质量结论：阶段 17 新增能力可作为人工核验候选；默认 `HybridSearchService` 仍不替换。

### Phase 8

- Phase 8 目标是完成普通文档、AGENT 判断和 Obsidian 草稿收尾，并停在用户人工核验前。
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD`。
- 已补齐 Obsidian：
  - `obsidian-vault/阶段/阶段 17 - 检索架构升级.md`
  - `obsidian-vault/阶段汇报/阶段 17 - 检索架构升级/阶段 17 Phase 汇报索引.md`
  - Phase 0 到 Phase 8 的 9 篇小 Phase 汇报。
  - `obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`、`obsidian-vault/阶段汇报索引.md`。
  - 新增知识点 `BM25 词法检索`、`RRF 排名融合`、`邻近 Chunk 上下文扩展`。
- Obsidian 小 Phase 汇报 10 项小节检查：9 篇均通过。
- `.gitignore` 已确认忽略 `obsidian-vault/`。
- 文档收尾后全量测试结果：`343 passed`。
- 当前仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR 创建。

### Phase 9

- Phase 9 目标是为阶段 17 新增的 BM25、RRF、context expansion 补齐人工复核证据和默认链路接入建议。
- 逐条复核 `data/evaluation/stage17_retrieval_upgrade_results.csv`，实际数据有料可核：
  - 5 条 `source_match=no`：`filling_capacity_cn`、`mesoscopic_modeling`、`cold_joint_shear`、`compactness_detection`、`recycled_aggregate`。
  - 其中 4 条为等价主题文献换位（多为中文 query 下中文母语文献上浮），仍 top-1 命中，判 acceptable。
  - `mesoscopic_modeling` 排序 `rank_before=2 -> rank_after=7`（vector_rank=29），被泛主题综述文档挤占前排，判 needs_tuning。
  - `construction_management` 轻微 `1 -> 2`，同文献仍 top-2，判 acceptable。
- 关键发现：headline「regression=0」用的是 hit 级定义，掩盖了 `mesoscopic_modeling` 的排序软退化；人工复核把它显式标为 needs_tuning 和默认替换阻断证据。
- 新增 `data/evaluation/stage17_retrieval_upgrade_manual_review.csv`：14 acceptable、1 needs_tuning、0 regression、0 defer；1 条 default_switch_blocker。
- 让 `scripts/evaluate_stage17_retrieval_upgrade.py` 的 `write_report` 可复现地纳入 Phase 9 摘要；用已有结果 CSV 重生成报告，不跑检索、不碰 DB、不触发真实 API（.env 当前为真实 provider，必须避免默认真实调用）。
- 新增 `tests/test_stage17_manual_review.py`，强制退化/非 acceptable 样例必须带证据和调优建议，防止把未验证样例伪造成通过。
- 默认链路接入结论：`RRFHybridSearchService`、`BM25SearchService`、`ContextExpansionService` 保持候选/配置开关，**不替换默认 `HybridSearchService`、Brain、`/chat`、`/agent`**。阻断理由是评测集 hit 饱和（零增益）+ 综述上浮造成排序软退化。
- 下一阶段依据：阶段 18 需要更有区分度的难评测集，并对综述类文档加权或 topic-anchor rerank 做对照，再决定是否默认接入。
- Phase 9 未对 `mesoscopic_modeling` 做即时调优修复：那属于检索重排调参，会影响所有查询，超出「人工复核」Phase 边界；按要求记录为 tuning_suggestion，留给阶段 18 验证。

## Term Explanations

| Term | Meaning in this project |
|---|---|
| BM25 | 经典词法检索算法，用 query 词频、资料片段频率和片段长度来计算匹配分数 |
| lexical retriever | 词法检索器，按字面词、短语、术语匹配 chunk；适合术语精确匹配 |
| vector retriever | 向量检索器，按 embedding 语义相似度匹配 chunk；适合语义近似表达 |
| RRF | Reciprocal Rank Fusion，倒数排名融合；用各通道排名而不是原始分数融合 |
| parent chunk | 父块；比命中的 child chunk 更大的上下文单元，本阶段先用相邻 chunk 近似 |
| child chunk | 子块；较小、适合精准召回的 chunk |
| context assembly | 上下文组装；把检索结果整理成给大模型阅读的引用上下文 |
| evidence confidence | 证据置信度；Brain 生成回答前判断检索证据是否足够 |
| provenance | 检索来源过程记录；说明某条结果来自哪些召回通道和排名 |
| baseline | 基线；旧 keyword/vector/hybrid 评测结果，用来判断新方案是否更好 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| README/docs 顶部仍写阶段 16 待核验 | Git 已有 `phase-16-complete` 和 `Merge phase 16 quality risk closure` | 阶段 17 收尾时同步修正入口文档 |
| 旧 hybrid 使用硬加权融合 | `HybridSearchService` normalize 后加权 keyword/vector | 阶段 17 新增 BM25+vector RRF，保留旧 hybrid baseline |
| 当前 schema 无 parent chunk | `chunks` 只有 document_id/chunk_index/content 等字段 | 先做邻近上下文扩展，暂不迁移数据库 |
| 剩余 high 来自 Answer Coverage | `user_mixed_itz_strength` 真实回答超时 | 阶段 17 可评测检索改善，但不伪造成质量闭环通过 |
| PowerShell 目录创建命令不支持 `-LiteralPath` | 创建 Obsidian 阶段 17 目录时首次命令失败 | 改用 `New-Item -Path` 创建目录 |

## Resources

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage16_quality_risk_closure.md`
- `docs/stage16_quality_closure_report.md`
- `app/services/retrieval/keyword_search.py`
- `app/services/retrieval/vector_search.py`
- `app/services/retrieval/hybrid_search.py`
- `app/services/retrieval/decompose.py`
- `app/services/brain/service.py`
- `app/api/search.py`
- `app/schemas/search.py`
- `scripts/evaluate_keyword_search.py`
- `scripts/evaluate_vector_search.py`
- `scripts/evaluate_hybrid_search.py`
- `tests/test_keyword_search.py`
- `tests/test_vector_search.py`
- `tests/test_hybrid_search.py`
- `tests/test_decompose_retrieval.py`
- `tests/test_brain_service.py`
- `tests/test_search_api.py`
