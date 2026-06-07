# 数据来源登记

本文件用于记录后续采集的堆石混凝土相关资料来源。

## 登记模板

```text
source_id:
标题:
URL:
来源类型:
作者或机构:
发布时间:
访问时间:
是否允许全文保存:
可信度评级:
备注:
```

## 当前状态

已完成阶段 4 source registry 来源治理。

阶段 4 已新增数据库表 `sources`，作为本项目的 source registry。它统一承接：

- `docs/data_sources.md` 中的人读来源登记。
- `data/fulltext_manifest.csv` 中的 PDF manifest。
- `data/source_candidates.csv` 中的公开学术 API 候选。
- `data/metadata/rfc_papers_metadata.csv` 中的题录元数据。
- `data/imports/metadata_corpus/*.md` 中的题录卡片。

当前同步结果：

- 输入来源候选：283 条。
- 写入 `sources` 表：125 条。
- 更新已有来源：132 次。
- 合并重复来源：26 次。
- 状态分布：`candidate=8`、`collected=117`。
- 全文保存权限分布：`institutional_access=2`、`metadata_only=110`、`open_access=10`、`unknown=3`。
- 可信度分布：`high=125`。

阶段 1 第一批试导入资料登记仍保留在下方，作为早期人工来源记录和历史审计依据。

本批资料采用“资料卡”形式导入：保存题录、公开摘要的转述、检索关键词和来源链接，不保存受版权限制的论文全文。

## 已登记来源（阶段 1 试导入）

| source_id | 标题 | 来源类型 | 作者或机构 | 发布时间 | URL | 是否允许全文保存 | 可信度评级 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rfc_seed_001 | 堆石混凝土及堆石混凝土大坝 / Study on rock-fill concrete dam | CNKI 摘要页、论文题录与公开摘要整理 | 金峰, 安雪晖, 石建军, 张楚汉 | 2005 | https://kns.cnki.net/kcms2/article/abstract?v=7jvqSXIa2LXUBdK4dw0XCLkKcRO8rkZ6LMUUPnH8IpFJ2iR8zuGHA1e5WffpBNepiDh_rfta6rS4U4LuO-qJaLhUnh5c-5CkPCagNMPVSAWdW7j2g4YjWYemqq7ziqRMfVTwwnFVvAbh46kqvSqjJUorkuOpi55gjpt5EPsoavCGJgU1GTvfUw==&uniplatform=NZKPT&language=CHS | 否，仅保存转述整理 | 高 | 用户补充确认的堆石混凝土开篇之作；ResearchGate 与行业页面作为辅助线索 |
| rfc_seed_002 | 堆石混凝土大坝施工方法 | 专利题录与公开资料整理 | 金峰, 安雪晖 | 2003 | https://www.civil.tsinghua.edu.cn/heen/info/1159/1950.htm | 否，仅保存转述整理 | 高 | 金峰教授主页列出的 RFC 施工方法专利 |
| rfc_seed_003 | 自密实混凝土充填堆石体试验研究 | 论文题录与引用线索整理 | 安雪晖, 金峰, 石建军 | 2005 | https://cjxy.usc.edu.cn/info/2369/1623.htm | 否，仅保存转述整理 | 中高 | 通过作者主页论文列表和相关引用页确认 |
| rfc_seed_004 | 自密实堆石混凝土力学性能的试验研究 | 公开摘要整理 | 石建军, 张志恒, 金峰, 张楚汉 | 2007 | https://rockmech.whrsm.ac.cn/CN/abstract/abstract25492.shtml | 否，仅保存转述整理 | 高 | 期刊官网摘要页 |
| rfc_seed_005 | Rock-filled concrete, the new norm of SCC in hydraulic engineering in China | 论文题录与摘要整理 | Xuehui An, Qiong Wu, Feng Jin 等 | 2014 | https://www.sciencedirect.com/science/article/pii/S0958946514001413 | 否，仅保存转述整理 | 高 | Cement and Concrete Composites 论文页 |
| rfc_seed_006 | Experimental study of filling capacity of self-compacting concrete and its influence on the properties of rock-filled concrete | 论文题录与摘要整理 | Yuetao Xie, David J. Corr, Mohend Chaouche, Feng Jin, Surendra P. Shah | 2014 | https://www.scholars.northwestern.edu/en/publications/experimental-study-of-filling-capacity-of-self-compacting-concret | 否，仅保存转述整理 | 高 | Northwestern Scholars 题录页 |
| rfc_seed_007 | Lattice Boltzmann-Discrete Element Modeling Simulation of SCC Flowing Process for Rock-Filled Concrete | 开放获取论文整理 | Song-Gui Chen, Chuan-Hu Zhang, Feng Jin 等 | 2019 | https://www.mdpi.com/1996-1944/12/19/3128 | 可开放访问，本项目仍只保存转述整理 | 高 | MDPI Materials 开放论文 |
| rfc_seed_008 | A Brief Review of Rock-Filled Concrete Dams and Prospects for Next-Generation Concrete Dam Construction Technology | 开放获取综述整理 | Feng Jin, Duruo Huang, Michel Lino, Hu Zhou | 2023 | https://www.engineering.org.cn/engi/CN/PDF/10.1016/j.eng.2023.09.020 | 可开放访问，本项目仍只保存转述整理 | 高 | Engineering 开放综述 |
| rfc_seed_009 | Filling the gaps in large concrete dams | 高校公开网页整理 | Tsinghua University | 2021 | https://www.tsinghua.edu.cn/en/info/1418/10419.htm | 否，仅保存转述整理 | 中高 | 清华大学英文新闻/特写 |
| rfc_seed_010 | 堆石混凝土绝热温升性能初步研究 | 论文题录与公开摘要整理 | 金峰, 李乐, 周虎, 安雪晖 | 2008 | https://sjwj.cbpt.cnki.net/portal/journal/portal/client/paper/65e4dbdb69e5e0bc75cdedaf22704c3e | 否，仅保存转述整理 | 高 | 覆盖水化热、温控和抗裂主题 |

## 后续补充方向

- 增加更多工程应用案例资料，覆盖不同坝型和施工场景。
- 增加规范、规程或行业标准的公开目录信息，但不保存受版权限制全文。
- 对每条资料补充主题标签，例如概念、施工、质量控制、温控、力学性能、工程应用。

## 全文来源目录

阶段 1 已开始从资料卡扩展到论文原文导入。全文 PDF 的来源分类、访问权限和本地文件名见：

- `docs/source_catalog.md`
- `data/fulltext_manifest.csv`

全文 PDF 保存在 `data/fulltext/`，该目录已加入 `.gitignore`，用于本地私有资料库，不提交到 GitHub。

## 题录元数据来源目录

阶段 1 已新增题录优先语料库，用于在不下载更多全文的情况下扩大检索覆盖面。

当前题录文件：
- `data/metadata/rfc_papers_metadata.csv`
- `data/metadata/rfc_papers_metadata.jsonl`
- `data/imports/metadata_corpus/*.md`

当前来源：
- OpenAlex
- Crossref
- 后续可合并 Semantic Scholar、CNKI 导出、Google Scholar 辅助工具导出、Zotero/EndNote/RIS 导出

当前规模：
- 116 条题录记录。
- 69 条包含公开摘要。
- 115 条已作为 `metadata_record` 文档进入 SQLite 检索库。

合规说明：
- 题录语料只保存公开元数据和摘要，不保存未授权全文。
- Google Scholar 不作为直接网页爬取主链路；如需使用，优先通过可导出的题录文件进入本项目。
- CNKI 机构账号获取的内容优先走题录导出或本地私有导入，不公开再分发全文。

## Source Registry 关系说明

阶段 4 之后，来源治理以 `sources` 表为准，文档关系如下：

```text
docs/data_sources.md
  人读来源说明和合规边界

data/fulltext_manifest.csv
  PDF 全文清单，包含本地路径和访问权限

data/source_candidates.csv
  学术 API 发现的候选来源

data/metadata/rfc_papers_metadata.csv
  题录 CSV，适合批量导入和评测

data/imports/metadata_corpus/*.md
  题录 Markdown 卡片，可进入 documents/chunks

sources
  数据库来源登记库，统一保存来源元数据、去重键、权限、可信度、状态和 document 关联

documents/chunks
  已导入并可检索、可引用的内容库
```

同步入口：

```powershell
python scripts/sync_sources.py
```

来源评测入口：

```powershell
python scripts/evaluate_sources.py
```

重新索引入口：

```text
POST /sources/{source_id}/reindex
```

设计原则：

- `sources` 管“这条资料来源是什么、是否可信、能否保存、是否已导入”。
- `documents/chunks` 管“这条资料实际进入 RAG 检索后的正文和片段”。
- `fulltext_permission` 与 `trust_level` 分开记录，避免把版权/授权问题和来源质量混在一起。
- 对受限全文，保留题录、摘要、合法来源链接和本地授权路径，不公开分发全文。

## 前端展示入口

阶段 5 已新增前端工作台：

```text
GET /
```

来源相关界面能力：

- 查看 `sources` 列表。
- 按关键词、状态、全文保存权限筛选来源。
- 查看来源可信度、全文权限、年份、分类、URL/DOI 和 `document_id`。
- 触发 `POST /sources/sync` 同步现有来源文件。
- 触发 `POST /sources/{source_id}/reindex` 重新导入单条来源。

资料相关界面能力：

- 查看 `documents` 列表。
- 查看每篇资料的 chunk 数量。
- 点击资料查看 `documents/{document_id}/chunks`。
- 在聊天引用侧栏中核验回答依据的具体 chunk。

阶段 5 的界面不改变数据来源合规边界：受限全文仍不公开分发，前端只展示本地系统已登记或已导入的来源和片段。

## 阶段 6 评测与数据来源边界

阶段 6 进入检索优化与评测，没有新增外部资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 6 使用的评测数据来自现有本地项目文件：

```text
data/evaluation/keyword_queries.csv
data/evaluation/chat_queries.csv
data/evaluation/keyword_results.csv
data/evaluation/vector_results.csv
data/evaluation/chat_results.csv
```

阶段 6 新增的评测输出是对现有资料库和现有评测集的分析结果：

```text
data/evaluation/hybrid_results.csv
data/evaluation/retrieval_error_cases.csv
```

它们不包含新的受限全文，只记录查询、期望命中、命中结果、通过状态、失败原因、改进建议和 hybrid 优化后的状态。

阶段 6 的核心关系是：

```text
sources
-> documents/chunks
-> chunk_embeddings
-> keyword/vector/hybrid retrieval
-> evaluation results
-> error cases
```

合规结论：

- `sources` 仍然负责来源可信度、全文权限和状态。
- `documents/chunks` 仍然只保存已导入的本地资料或题录卡片。
- `chunk_embeddings` 是由 chunks 派生出的可重建索引数据。
- `hybrid_results.csv` 和 `retrieval_error_cases.csv` 是评测产物，不是新的资料来源。
- 阶段 6 没有公开分发受限全文，也没有引入新的爬虫链路。

## 阶段 7 Agent 化与数据来源边界

阶段 7 进入 Agent 化，没有新增外部资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

Agent 工具只读取现有数据：

```text
sources
documents/chunks
chunk_embeddings
qa_logs
data/evaluation/*.csv
```

阶段 7 新增的 Agent 工具：

```text
search_knowledge
hybrid_search_knowledge
answer_with_citations
list_sources
get_source_detail
```

这些工具复用现有 service 和 repository：

```text
KeywordSearchService
HybridSearchService
CitationAnswerService
SourceRepository
```

阶段 7 新增的评测输入和输出：

```text
data/evaluation/agent_queries.csv
data/evaluation/agent_results.csv
```

它们不包含新的受限全文，只记录 Agent 任务、期望工具、期望拒答、来源命中、引用有效性和工具调用结果。

阶段 7 的核心关系是：

```text
sources
-> documents/chunks
-> keyword/vector/hybrid retrieval
-> citation chat
-> Agent read-only tools
-> agent evaluation results
-> frontend tool call display
```

合规结论：

- Agent 不新增联网爬虫链路。
- Agent 不绕过 `sources` 的可信度、全文权限和状态记录。
- Agent 不自动执行 `POST /sources/{source_id}/reindex` 等写入型动作。
- `agent_results.csv` 是评测产物，不是新的资料来源。
- 受限全文仍只保存在本地授权环境中，不公开分发。

## 阶段 8 Brain Workflow 与数据来源边界

阶段 8 进入 Brain 中控层与 RAG Workflow 配置化，没有新增外部资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

Brain workflow 只读取或复用现有数据：

```text
sources
documents/chunks
chunk_embeddings
qa_logs
data/evaluation/*.csv
```

阶段 8 新增的评测输出：

```text
data/evaluation/brain_workflow_results.csv
```

它不是新的资料来源，而是对现有 chat 评测集和现有资料库的配置化评测产物。该 CSV 记录不同 Brain 配置下的：

- config 名称
- 实际检索模式
- workflow steps
- 来源命中
- citation 有效性
- 拒答匹配
- 模型提供方和模型名称

阶段 8 的核心关系是：

```text
sources
-> documents/chunks
-> chunk_embeddings
-> keyword/vector/hybrid retrieval
-> Brain workflow
-> chat/agent answer
-> brain workflow evaluation results
```

合规结论：

- Brain 不联网爬取新资料。
- Brain 不绕过 `sources` 的可信度、全文权限和状态记录。
- Brain 不自动执行 `source reindex` 等写入型动作。
- `brain_workflow_results.csv` 是评测产物，不是新的资料来源。
- 受限全文仍只保存在本地授权环境中，不公开分发。

## 阶段 9 真实模型接入与数据来源边界

阶段 9 进入真实模型接入与模型评测，没有新增外部文献资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 9 新增的是模型服务配置和评测产物：

```text
docs/model_provider_evaluation.md
scripts/evaluate_model_configs.py
data/evaluation/model_config_results.csv
data/evaluation/mimo_jina_chat_results.csv
data/evaluation/mimo_jina_agent_results.csv
data/evaluation/mimo_jina_brain_workflow_results.csv
```

真实模型 API 不是资料来源。它只用于：

```text
chunks -> embedding vectors
prompt/context -> chat answer
evaluation results -> quality comparison
```

阶段 9 不保存真实模型服务返回的受限文献全文；`model_config_results.csv` 只保存配置名、评测项、通过数、总数、provider/model 名称和 skipped reason。

阶段 9.1 使用 Jina embedding 和 MIMO chat 做真实模型补充评测。Jina 和 MIMO 都是模型服务，不是文献资料来源；新增的 `mimo_jina_*_results.csv` 只保存问题、通过状态、来源标题、引用数量、provider/model 名称和错误摘要，不保存 API key，也不新增受限全文。

合规结论：

- `sources` 仍然负责资料来源、可信度、权限和状态。
- `documents/chunks` 仍然只保存已导入的本地资料或题录卡片。
- `chunk_embeddings` 是由 chunks 派生出的可重建索引数据。
- 真实 API key 只允许放在本地 `.env`，不得提交到 Git。
- MIMO Token Plan key、Jina API key 和任何真实模型凭证不得写入源码、文档或评测 CSV。
- 阶段 9 没有公开分发受限全文，也没有引入新的爬虫链路。

## 阶段 10 真实 RAG 质量校准与数据来源边界

阶段 10 进入真实 RAG 质量校准与拒答边界优化，没有新增外部文献资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 10 复用现有数据：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/*.csv
```

阶段 10 新增或更新的评测产物：

```text
data/evaluation/real_rag_failure_cases.csv
data/evaluation/vector_results.csv
data/evaluation/hybrid_results.csv
data/evaluation/brain_workflow_results.csv
data/evaluation/model_config_results.csv
data/evaluation/stage10_jina_vector_results.csv
data/evaluation/stage10_jina_hybrid_results.csv
data/evaluation/stage10_mimo_jina_chat_results.csv
data/evaluation/stage10_mimo_jina_agent_results.csv
data/evaluation/stage10_mimo_jina_brain_workflow_results.csv
```

这些文件不是新的资料来源。它们只记录：

- 评测问题。
- 期望命中条件。
- 通过或失败状态。
- 命中标题和来源类型。
- 引用数量和拒答状态。
- provider/model 名称。
- 失败原因和改进建议。

阶段 10 的核心关系是：

```text
已有 sources / documents / chunks
-> deterministic or Jina chunk_embeddings
-> keyword / vector / hybrid retrieval
-> Brain evidence confidence
-> chat / agent / brain workflow evaluation
-> stage 10 quality conclusion
```

合规结论：

- 阶段 10 不新增爬虫链路。
- 阶段 10 不新增外部文献或受限全文。
- Jina 和 MIMO 仍然是模型服务，不是资料来源。
- `stage10_*_results.csv` 是质量校准结果，不是资料库。
- `real_rag_failure_cases.csv` 是失败分析表，不包含受限全文，只保存可追溯标题、简短证据摘要和诊断。
- 真实 API key 只允许放在本地 `.env`，不得写入源码、文档、CSV 或 Obsidian。
- 自动回归继续优先使用 deterministic provider，避免把真实模型密钥、网络和余额变成测试前提。

## 阶段 11 真实用户问题评测与数据来源边界

阶段 11 进入真实用户问题评测集与跨语言质量提升，没有新增外部文献资料来源，也没有改变阶段 4 建立的 source registry 合规边界。

阶段 11 复用现有数据：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/keyword_queries.csv
data/evaluation/chat_queries.csv
data/evaluation/agent_queries.csv
```

阶段 11 新增或更新的评测产物：

```text
data/evaluation/user_questions.csv
data/evaluation/user_question_results.csv
data/evaluation/user_question_review_samples.csv
docs/stage11_user_evaluation_plan.md
```

这些文件不是新的资料来源。它们只记录：

- 用户问题。
- 语言类型。
- 期望来源命中。
- 期望拒答状态。
- 期望回答要点。
- 自动评测通过或失败状态。
- 来源标题、答案摘要、审阅字段和 judge prompt。

阶段 11 的核心关系是：

```text
已有 sources / documents / chunks
-> keyword / vector / hybrid retrieval
-> user question evaluation
-> cross-language query expansion
-> manual review samples
-> stage 11 quality conclusion
```

合规结论：

- 阶段 11 不新增爬虫链路。
- 阶段 11 不新增外部文献或受限全文。
- `user_questions.csv` 是评测输入，不是资料库。
- `user_question_results.csv` 和 `user_question_review_samples.csv` 是质量评测产物，不保存受限全文。
- 审阅抽样表只保存来源标题、答案摘要、审阅字段和必要备注，不保存完整论文正文。
- Jina、MIMO 或其他真实模型仍然是模型服务，不是资料来源。
- 真实 API key 只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- 自动回归继续使用 deterministic provider；真实模型只适合发布前质量校准或离线审阅。

## 阶段 12 质量审阅与上下文最小补全产物

阶段 12 新增或更新的评测与设计产物：

```text
data/evaluation/stage12_quality_review_results.csv
docs/stage12_quality_review.md
docs/stage13_decompose_plan.md
```

这些文件不是新的文献资料来源。它们只记录：

- 审阅样本 ID 和用户问题 ID。
- 语言类型和评测配置。
- 期望回答要点。
- Faithfulness、Answer Coverage、Citation Quality 的人工或离线审阅结论。
- 风险等级、审阅备注和下一步建议。
- 阶段 13 Decompose 的后续设计边界。

阶段 12 的上下文补全也不新增资料来源。它只在检索前使用调用方传入的可选 `history`，把“它”“这个技术”等省略问法补成更完整的检索 query。补全后的 query 不会写入 `sources`、`documents`、`chunks` 或 `chunk_embeddings`。

合规结论：

- 阶段 12 不新增爬虫链路。
- 阶段 12 不新增外部文献或受限全文。
- `stage12_quality_review_results.csv` 是质量审阅产物，不是资料库。
- `docs/stage13_decompose_plan.md` 是后续设计文档，不是资料来源。
- 质量审阅只保存来源标题、答案摘要、审阅字段和必要备注，不保存完整论文正文。
- HyDE 只保留为离线实验建议，不进入默认链路或自动回归。
- 真实 API key 仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。

## 阶段 13 Decompose 与证据合并产物

阶段 13 新增或更新的工程与评测产物：

```text
app/services/retrieval/decompose.py
scripts/evaluate_decompose.py
data/evaluation/stage13_decompose_results.csv
docs/stage13_decompose_plan.md
```

这些文件不是新的文献资料来源。它们只记录：

- 规则式拆解后的 sub query。
- 每个问题的检索、合并、去重和 rerank 解释。
- 来源命中、拒答匹配、provenance 和 answer coverage proxy 等评测字段。
- 阶段 13 的设计边界和质量结论。

阶段 13 不新增外部资料来源，不新增爬虫链路，不保存受限全文。Decompose 只读取现有：

```text
sources
documents/chunks
chunk_embeddings
data/evaluation/user_questions.csv
```

合规结论：

- `stage13_decompose_results.csv` 是质量评测产物，不是资料库。
- sub query provenance 只说明证据由哪个子问题召回，不改变资料来源归属。
- 真实 API key 仍只允许放在本地 `.env`，不得写入源码、文档、CSV、测试或 Obsidian。
- HyDE 仍只作为离线实验建议，不进入默认链路或自动回归。
