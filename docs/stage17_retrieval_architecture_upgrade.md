# 阶段 17 设计：检索架构升级

## 目标

阶段 17 的目标是升级 RAG 检索工程，而不是先引入更复杂的 Agent 框架。阶段 16 已完成真实质量风险闭环：real decompose 已通过显式重试完成，剩余 high 风险来自 `user_mixed_itz_strength` 的 Answer Coverage。阶段 17 要在不新增外部资料来源、不让真实 API 成为默认测试前提的边界内，增强检索召回、融合排序、上下文组装和评测对比。

核心链路：

```text
stage16 quality conclusion
-> retrieval architecture design
-> context expansion
-> BM25 lexical retriever
-> BM25 + vector multi-channel retrieval
-> RRF fusion
-> deduplicate and lightweight rerank
-> evidence confidence
-> context assembly
-> baseline comparison report
-> manual verification before commit/tag/push
```

阶段 17 不用 deterministic baseline 掩盖真实质量问题，也不把阶段 16 的 Answer Coverage high 阻断伪造成已解决。检索升级只能通过评测说明是否改善了召回、排名和证据细节。

## 阶段输入

阶段 17 复用现有工程与评测产物：

```text
app/services/retrieval/keyword_search.py
app/services/retrieval/vector_search.py
app/services/retrieval/hybrid_search.py
app/services/retrieval/decompose.py
app/services/brain/service.py
app/api/search.py
data/evaluation/keyword_queries.csv
data/evaluation/keyword_results.csv
data/evaluation/vector_results.csv
data/evaluation/hybrid_results.csv
data/evaluation/stage16_answer_coverage_closure.csv
docs/stage16_quality_closure_report.md
```

阶段 17 推荐新增产物：

```text
docs/stage17_retrieval_architecture_upgrade.md
app/services/retrieval/context_expansion.py
app/services/retrieval/bm25_search.py
app/services/retrieval/rrf_fusion.py
scripts/evaluate_stage17_retrieval_upgrade.py
data/evaluation/stage17_retrieval_upgrade_results.csv
data/evaluation/stage17_retrieval_upgrade_manual_review.csv
docs/stage17_retrieval_upgrade_report.md
```

## 检索流水线

阶段 17 的目标流水线：

```text
query normalize
-> query expansion
-> BM25 lexical retrieval
-> vector retrieval
-> merge candidates
-> deduplicate by chunk_id
-> RRF ranking
-> lightweight topic/source rerank
-> context expansion
-> evidence confidence
-> context assembly for RAG prompt
```

`query normalize` 是查询归一化，例如统一大小写、连字符和中英文术语写法。`query expansion` 是查询扩展，例如把“堆石混凝土”扩展到 “rock-filled concrete / RFC”，复用现有 `SYNONYM_RULES`。

## 父子块与上下文扩展

父子块策略的理想形态是：

```text
child chunk 负责精准召回
parent chunk 负责回答上下文扩展
```

当前数据库 schema 只有 `documents`、`chunks`、`chunk_embeddings`，没有独立的 parent chunk 表。阶段 17 先采用兼容方案：

```text
命中核心 chunk
-> 按 document_id 和 chunk_index 拉取前后相邻 chunk
-> 只把扩展文本用于 context assembly
-> 引用和 API 响应仍指向核心 chunk
```

这样可以改善“召回片段太短、回答缺少上下文”的问题，同时避免本阶段做数据库迁移。如果后续资料量和结构化章节需求扩大，再设计 parent_chunk schema。

## BM25 Lexical Retriever

BM25 是标准词法检索算法，用词频、逆文档频率和文档长度归一化计算 query 与 chunk 的匹配程度。阶段 17 新增或改进 BM25 lexical retriever，保留旧 `KeywordSearchService` 作为 baseline。

设计要求：

- 支持中文术语、英文短语和中英混合 query。
- 复用现有 `normalize_text`、`expand_query_terms` 和领域同义词规则。
- 对 document title、heading_path、content 设置不同权重。
- 对 `metadata_record` 做合理控制，避免题录记录挤掉全文或开放全文证据。
- 空 query、无结果、并列分数必须稳定。

BM25 的输出可以包含：

```text
bm25_score
matched_terms
title_score
heading_score
content_score
```

## RRF 融合

RRF 是 Reciprocal Rank Fusion，倒数排名融合。它的核心思想是用每个通道的排名来融合，而不是直接把 BM25 分数和向量余弦分数相加。

推荐公式：

```text
rrf_score = sum(1 / (rank_constant + rank_in_channel))
```

阶段 17 要求：

- BM25 与 vector 各自召回候选。
- 按 `chunk_id` 去重。
- 同一 chunk 可合并 `matched_channels`、`bm25_rank`、`vector_rank`、`bm25_score`、`vector_score`、`rrf_score`。
- 排序优先使用 `rrf_score`，再用 source_type、document_id、chunk_index 保证稳定。
- 不得用不同尺度分数硬加权冒充融合。

## Baseline 对比

阶段 17 必须保留旧结果，新增独立评测表，不覆盖旧 baseline。

推荐输出：

```text
data/evaluation/stage17_retrieval_upgrade_results.csv
docs/stage17_retrieval_upgrade_report.md
```

评测字段至少包含：

```text
query_id
query
baseline_hit
upgraded_hit
source_match
rank_before
rank_after
retrieval_mode
decision
evidence
baseline_top_titles
upgraded_top_titles
```

`decision` 口径：

| 条件 | decision |
|---|---|
| upgraded 命中且 rank_after 优于 rank_before | improved |
| upgraded 命中但排名相同或略差，无关键回归 | neutral |
| baseline 命中但 upgraded 未命中 | regression |
| 两者都未命中 | unresolved |

如果升级未优于旧 hybrid，默认链路必须保持旧 `HybridSearchService` 不变，并在报告中写明原因。

## API 与 Brain 边界

阶段 17 必须保证以下入口不被破坏：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
GET /quality-report
```

默认建议是先把升级检索作为评测入口和服务能力落地，而不是立即替换 `/search/hybrid` 或 Brain 默认 hybrid。只有阶段 17 评测证明升级没有回归，并且测试覆盖 Brain/chat/agent 后，才允许考虑默认链路切换。

## 数据安全边界

- 阶段 17 不新增爬虫或外部资料来源。
- 阶段 17 不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- 阶段 17 不保存受限全文；受限资料仍只允许留在本地授权环境。
- 阶段 17 不让真实 API 成为 CI 或本地全量测试前提。
- 真实 provider 只能通过显式本地命令运行；默认测试使用 deterministic 或 mock。
- 阶段 17 不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR，等待用户人工核验。

## 阶段边界

阶段 17 不做：

- 不做写入型 Agent 工具。
- 不做复杂 LangGraph workflow。
- 不做登录系统。
- 不做部署优化。
- 不新增爬虫或外部资料来源。
- 不把 HyDE 接入默认链路或自动回归。
- 不优先引入 HNSW、FAISS、Qdrant、PGVector。

阶段 17 要做：

- 固化检索架构升级设计。
- 新增或改进 BM25 lexical retriever。
- 新增 BM25+vector RRF 融合能力。
- 建立邻近上下文扩展或明确 parent chunk 后续 schema。
- 建立阶段 17 评测表和报告，对比旧 hybrid baseline。
- 保证旧 API、Brain、chat、agent 和 `/quality-report` 不被破坏。
- 完成测试、普通文档、Obsidian 草稿，并停在用户人工核验前状态。

## 完成标准

- `docs/stage17_retrieval_architecture_upgrade.md` 存在并覆盖目标、输入、检索流水线、父子块/上下文策略、BM25、RRF、评测方法、安全边界和完成标准。
- BM25 lexical retriever 存在或被集成，并有分词、中文术语、标题/来源权重、空 query 和排序稳定性测试。
- BM25+vector 融合服务存在，包含 merge、deduplicate、RRF ranking、可解释 score/provenance；没有用不同尺度分数硬加权冒充融合。
- 父子块能力先采用相邻 chunk/同 document context expansion 或明确 schema 方案；如改数据库结构，必须有迁移/兼容测试。
- 阶段 17 评测表和报告存在，能对比旧 baseline 与 upgraded retrieval。
- 如果升级未优于旧 hybrid，默认链路保持不变并写明原因。
- 旧 search/vector/hybrid/chat/agent API 和 `/quality-report` 不被破坏。
- 阶段 17 测试、相关回归和最终全量测试通过。
- README、docs/progress.md、docs/architecture.md、docs/data_sources.md、AGENT.MD 判断和 Obsidian 本地知识库完成阶段收尾。
- 最终停在未提交状态，等待用户人工核验。

## Phase 9 人工复核结论

阶段 17 Phase 9 对 `data/evaluation/stage17_retrieval_upgrade_results.csv` 做逐条人工复核，结果记录在 `data/evaluation/stage17_retrieval_upgrade_manual_review.csv`，并在 `docs/stage17_retrieval_upgrade_report.md` 追加 Phase 9 摘要。

复核口径：

| review_decision | 含义 |
|---|---|
| acceptable | 升级结果可接受：命中稳定，或为等价主题文献换位且仍在 top-1/top-2 |
| needs_tuning | 仍命中但排序明显退化，需要后续调优后才考虑默认接入 |
| regression | 升级造成关键回归，必须阻断默认接入 |
| defer | 证据不足，暂缓判断 |

复核结论：

- 15 条查询中 14 条 acceptable、1 条 needs_tuning（`mesoscopic_modeling`，排序 2 -> 7）、0 regression、0 defer。
- 5 条 `source_match=no` 中 4 条为等价主题文献换位（多为中文 query 下中文母语文献上浮），仍 top-1 命中，判定 acceptable。
- `needs_tuning` 根因是中文多词宽查询下 RRF 让泛主题综述文档压过专题文档；这是 hit 指标掩盖的软退化。

默认链路接入建议：

- 保持 `RRFHybridSearchService`、`BM25SearchService`、`ContextExpansionService` 为**候选能力 / 配置开关**，暂不替换默认 `HybridSearchService`、Brain、`/chat`、`/agent`。
- 阻断理由：评测集 hit 已饱和（15/15）缺乏区分度，升级零增益；且存在 1 条综述上浮造成的排序软退化。不得偷偷替换默认链路。
- 后续条件：阶段 18 构建更有区分度的难评测集，并对综述类文档加权或 topic-anchor rerank 做对照，证明升级在难样例上真正更优后，再考虑默认接入。

## 面试表达

阶段 17 我优先升级检索架构，而不是先套 LangChain 或 LangGraph。原因是当前 RAG 系统最核心的质量瓶颈仍在“能不能召回正确证据、能不能把多路结果稳定排序、能不能给回答足够上下文”。

我把旧 keyword/vector/hybrid 保留为 baseline，新加 BM25 作为更标准的词法检索，再用 RRF 融合 BM25 和 vector。BM25 解决术语精确匹配，vector 解决语义近似召回，RRF 解决两路分数尺度不同、不能直接相加的问题。上下文上，我先用相邻 chunk 扩展模拟父子块，让命中的 child chunk 保持引用精确，同时给回答更多 parent-like context。最后通过阶段 17 评测表证明是否优于旧 hybrid；如果没有明显变好，就不切默认链路。
