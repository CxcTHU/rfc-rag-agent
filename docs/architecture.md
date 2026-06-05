# 架构说明

## 总体流程

```text
资料来源
-> source registry 登记与治理
-> 导入或爬取
-> 文本抽取
-> 清洗
-> 切分 chunk
-> embedding 向量化
-> 向量索引
-> 用户提问
-> 检索召回
-> 组织上下文
-> 大模型回答
-> 返回答案和引用来源
-> 前端工作台展示和操作
```

## 初始分层

```text
API 层：FastAPI 路由
Schema 层：Pydantic 请求和响应模型
Service 层：导入、切分、检索、问答业务逻辑
DB 层：文档、chunk、问答日志元数据
Source Registry 层：来源登记、去重、可信度、全文权限和重新索引
Model Provider 层：聊天模型和 embedding 模型适配
Frontend 层：来源、资料、检索、问答和引用来源展示
```

## 第一阶段原则

- 先做工程底座，再做复杂 Agent。
- 先做本地资料导入，再做爬虫。
- 先做检索，再做回答。
- 回答必须能追溯来源。

## 当前实现

阶段 0 已落地最小后端骨架：

```text
app/main.py
  创建 FastAPI 应用，注册路由

app/api/health.py
  提供 GET /health

app/core/config.py
  集中读取应用配置和模型配置占位字段

app/schemas/health.py
  定义健康检查响应结构

tests/test_health.py
  验证 /health 的 HTTP 状态码和 JSON 返回
```

这种结构的目的，是让后续阶段可以自然扩展：

```text
health.py -> documents.py -> search.py -> chat.py
config.py -> database config -> model provider config
health schema -> document/search/chat schemas
```

## 阶段 1 总体框架

阶段 1 的目标是打通第一条最小资料链路：

```text
本地 Markdown/TXT/PDF 文件
-> 保存原始文件
-> 解析正文
-> 清洗文本
-> 切分 chunk
-> 保存 documents 和 chunks
-> 关键词检索
-> 返回标题、来源和片段
```

本阶段参考 Quivr 的 `storage / processor / splitter` 思路，但只保留当前需要的最小版本：

```text
Quivr storage      -> 本项目保存原始文件到 data/raw/
Quivr processor    -> 本项目 parser 读取 Markdown/TXT 正文
Quivr splitter     -> 本项目 splitter 把堆石混凝土资料切成 chunk
Quivr vector store -> 阶段 2 再做，本阶段不接 embedding 和向量库
Quivr RAG workflow -> 阶段 3 以后再做，本阶段不接大模型
```

### 新词解释

```text
ingestion
  资料导入链路。把用户上传或指定的本地文件变成系统可检索的数据。

processor / parser
  文件处理器。负责按文件类型读取内容，例如 .md 按 Markdown 文本读，.txt 按普通文本读，.pdf 用 pypdf 抽取文字层。

chunk
  可检索资料片段。例如一篇堆石混凝土施工文章会被切成多个 500 到 900 字左右的小段。

metadata
  元数据。不是正文内容，而是标题、来源路径、文件类型、导入时间、chunk 序号等说明信息。

repository
  数据库读写层。API 和 service 不直接写 SQL，而是通过 repository 保存和查询 documents/chunks。

top_k
  返回最相关的前 K 条结果。例如 top_k=5 表示关键词检索返回 5 个最相关片段。
```

### 目录规划

阶段 1 先增加以下模块：

```text
app/
  api/
    documents.py        POST /documents/import, GET /documents, GET /documents/{document_id}/chunks
    search.py           POST /search
  db/
    session.py          创建 SQLite 连接
    models.py           documents 和 chunks 表模型
    repositories.py     文档和 chunk 的保存、查询
  schemas/
    document.py         导入和文档列表响应结构
    search.py           搜索请求和响应结构
  services/
    ingestion/
      loader.py         保存上传文件，计算 hash
    parser.py         解析 Markdown/TXT/PDF
      cleaner.py        清洗文本
      splitter.py       切分 chunk
      service.py        串起导入全流程
    retrieval/
      keyword_search.py 关键词检索
```

### 数据库设计

阶段 1 只落地 `documents` 和 `chunks` 两张核心表：

```text
documents
  id
  title
  source_type
  source_path
  file_name
  file_extension
  content_hash
  raw_path
  status
  created_at
  updated_at

chunks
  id
  document_id
  chunk_index
  content
  char_count
  heading_path
  start_char
  end_char
  created_at
```

为什么这样设计：

- `documents` 保存一篇资料的整体信息，后续可以展示“资料库里有哪些资料”。
- `chunks` 保存可检索片段，后续问答引用时能追溯到具体片段。
- `content_hash` 用于识别重复文件，避免同一篇资料被重复导入。
- `heading_path` 预留标题层级，后续处理论文、报告、规范类资料时能保留上下文。
- `start_char` 和 `end_char` 记录片段在原文中的大致位置，方便排查和引用。

### API 设计

```text
POST /documents/import
  输入：Markdown/TXT/PDF 文件，可选 title
  处理：保存原文件 -> 解析 -> 清洗 -> 切分 -> 入库
  输出：document_id、title、chunk_count、status

GET /documents
  输入：无
  处理：查询已导入资料
  输出：文档列表、每篇资料的 chunk 数量和导入状态

GET /documents/{document_id}/chunks
  输入：URL 路径中的 document_id
  处理：查询某篇资料下的全部 chunk
  输出：资料标题、来源路径、chunk 总数、每个 chunk 的内容、序号、字符数和位置

POST /search
  输入：query、top_k
  处理：用关键词在 chunks 中检索
  输出：命中的片段、所属文档标题、chunk 序号、简单相关性分数
```

### 关键词检索策略

阶段 1 先做确定性关键词检索，不接 embedding。

```text
query
-> 清洗查询词
-> 在 chunk content 和 document title 中匹配
-> 按命中次数、标题命中、片段长度做简单评分
-> 返回 top_k
```

为什么先这样做：

- 不需要模型 API，也不需要向量库，能最快验证“资料能导入、能被搜到”。
- 关键词检索结果容易解释，适合第一阶段调试。
- 后续阶段 2 接入 embedding 后，可以把关键词结果作为对照基线。

### 真实资料切分微调

第一批资料卡导入后，splitter 采用以下补充规则：

- 跳过 Markdown 资料卡开头的 `source_id`、`url`、`copyright_note` 等元信息块，避免把来源登记字段当作知识正文。
- 新 chunk 起点优先贴近段落、换行、句号等自然边界，避免从 URL、英文单词或中文句子中间开始。
- `heading_path` 按 chunk 开始位置计算，用来表示该片段所属标题层级。
- 摘要型资料卡如果正文少于 `chunk_size`，保留为一个完整 chunk；长论文或长报告仍按长度和自然边界切成多个 chunk。

### PDF 原文导入

阶段 1 已增加最小 PDF 支持：

- 使用 `pypdf` 抽取 PDF 文字层。
- 每页文本前增加 `## Page N`，方便后续检查 chunk 所在页。
- 仅支持有文字层的 PDF；扫描版 PDF 暂不做 OCR。
- 开放全文 PDF 保存在 `data/fulltext/open_access/`，该目录不提交到 Git。
- 来源、许可、分类和本地文件名记录在 `data/fulltext_manifest.csv` 与 `docs/source_catalog.md`。

为什么这样设计：

- 阶段 1 先解决“能导入论文原文并检索”，不把 OCR、版面还原和表格识别一次性引入。
- PDF 全文可能受版权或机构访问限制，因此全文文件留在本地，仓库只保存来源清单和分类。
- 先用开放全文建立基线，再用 CNKI 机构授权下载补齐中文早期核心论文。

### 题录元数据语料库

阶段 1 现在增加一条轻量资料链路：

```text
OpenAlex / Crossref / Semantic Scholar / CNKI导出 / Google Scholar辅助导出
-> 题录候选
-> RFC 相关性过滤
-> DOI 或题名去重
-> CSV / JSONL 保存
-> Markdown 题录卡片
-> ingestion service
-> documents/chunks
-> 关键词检索
```

这样设计的原因：
- 论文全文获取慢且受版权、机构授权和网站限制影响；题录和摘要通常更容易批量获取。
- 阶段 1 的目标是先扩大可检索范围，不急着把所有全文都放进库里。
- 题录卡片复用现有 Markdown parser、cleaner、splitter、repository 和 search，不需要提前新增复杂表结构。
- 对 Google Scholar 和 CNKI，优先支持导出文件导入，不把验证码、登录态和页面结构变化放进主链路。

对应实现：
- `app/services/source_collection.py`：来源候选结构、分类、去重、摘要清洗、OpenAlex 摘要还原、Markdown 卡片生成。
- `scripts/collect_sources.py`：学术 API 发现，仍支持开放 PDF 可选下载。
- `scripts/collect_metadata_corpus.py`：题录优先采集、导出文件合并、CSV/JSONL 输出、Markdown 卡片入库。
- `data/metadata/rfc_papers_metadata.csv`：当前题录语料清单。
- `data/imports/metadata_corpus/`：生成的题录 Markdown 卡片。

### 测试顺序

```text
test_parser.py
  Markdown/TXT 能被解析成文本

test_cleaner.py
  多余空白、空字符能被清理

test_splitter.py
  长文本能切成多个 chunk，且保留 overlap

test_documents_api.py
  POST /documents/import 能导入示例文件
  GET /documents 能看到导入结果
  GET /documents/{document_id}/chunks 能查看某篇资料的 chunk

test_search.py
  POST /search 能搜到包含关键词的 chunk
```

阶段 1 完成标准：

```text
能导入 5 到 10 篇本地 Markdown/TXT 资料
SQLite 中能看到 documents 和 chunks
搜索“堆石混凝土”“自密实混凝土”“施工质量”等关键词能返回相关片段
返回结果包含 document title、chunk content、chunk_index 和 score
```

## 阶段 2 总体框架

阶段 2 的目标是打通第一条最小向量检索链路：

```text
documents/chunks
-> EmbeddingProvider
-> chunk_embeddings
-> VectorIndexService
-> 用户问题
-> query embedding
-> VectorSearchService
-> 返回 top_k 相似 chunks 和来源
```

本阶段参考 Quivr 的 `embedder / vector store / retriever` 模块边界，但先保留轻量实现：

```text
Quivr embedder      -> 本项目 EmbeddingProvider
Quivr vector store  -> 本项目先用 SQLite chunk_embeddings 表保存向量
Quivr retriever     -> 本项目 VectorSearchService
Quivr eval/tests    -> 本项目 keyword_queries.csv + evaluate_vector_search.py
```

阶段 2 不做：

- 引用式回答生成。
- 大模型聊天接口。
- Agent 工具调用。
- 复杂 workflow 编排。

这些内容放到阶段 3 或更后续阶段。

### 新词解释

```text
embedding
  文本向量。把用户问题或堆石混凝土资料片段变成一组数字，便于计算相似度。

EmbeddingProvider
  embedding 模型提供者。检索服务只依赖这个接口，不直接绑定某一家模型 API。

deterministic embedding
  确定性 embedding。同样输入永远得到同样向量，用于无 API key 的开发和自动化测试。

chunk_embeddings
  chunk 向量表。保存每个 chunk 的 embedding、provider、model_name、dimension 和 content_hash。

VectorIndexService
  向量索引构建服务。扫描 chunks，生成或更新 embedding，并写入 chunk_embeddings。

VectorSearchService
  向量检索服务。把用户问题向量化，再和 chunk_embeddings 中的向量计算相似度。

cosine similarity
  余弦相似度。用两个向量方向的接近程度表示问题和资料片段的相关性。

baseline
  对照基线。阶段 1 的关键词检索就是阶段 2 向量检索的 baseline。
```

### 目录规划

阶段 2 新增和扩展以下模块：

```text
app/
  api/
    search.py                 POST /search, POST /search/vector
  db/
    models.py                 ChunkEmbedding 模型
    repositories.py           ChunkEmbeddingRepository
  schemas/
    search.py                 VectorSearchRequest, VectorSearchResponse
  services/
    retrieval/
      embedding.py            EmbeddingProvider, DeterministicEmbeddingProvider
      vector_index.py         VectorIndexService
      vector_search.py        VectorSearchService
scripts/
  build_vector_index.py       构建 chunk_embeddings
  evaluate_vector_search.py   评测向量检索
data/
  evaluation/
    keyword_queries.csv
    keyword_results.csv
    vector_results.csv
```

### 数据库设计

阶段 2 在阶段 1 的 `documents` 和 `chunks` 基础上新增 `chunk_embeddings`：

```text
chunk_embeddings
  id
  chunk_id
  provider
  model_name
  dimension
  embedding_json
  content_hash
  created_at
  updated_at
```

为什么这样设计：

- `documents/chunks` 仍保存可引用的主数据。
- `chunk_embeddings` 只保存可重建的向量索引数据。
- `chunk_id` 用来从向量结果回到原始 chunk 和 document。
- `provider/model_name/dimension` 防止不同模型生成的向量混用。
- `content_hash` 用来判断向量是否过期。
- `embedding_json` 让 SQLite 阶段可以直接保存向量列表，后续迁移到 FAISS、Chroma 或 PGVector 时可以重建索引。

### API 设计

```text
POST /search
  阶段 1 关键词检索，继续作为 baseline。

POST /search/vector
  输入：query、top_k
  处理：query -> embedding -> 和 chunk embedding 计算余弦相似度
  输出：query、top_k、provider、model_name、results
  results：document_id、document_title、source_type、source_path、file_name、chunk_id、chunk_index、content、heading_path、score
```

### 向量索引构建策略

```text
chunks
-> 计算 content_hash
-> 查询同 provider/model 的已有 embedding
-> 未索引：生成 embedding 并插入
-> 已过期：重新生成 embedding 并更新
-> 未变化：跳过
```

索引构建由 `VectorIndexService` 负责，命令行入口是：

```powershell
python scripts/build_vector_index.py
```

### 向量检索策略

```text
query
-> EmbeddingProvider.embed_query()
-> 查询同 provider/model/dimension 的 chunk_embeddings
-> 跳过 stale embedding
-> cosine similarity
-> score 降序
-> 返回 top_k
```

当前使用 deterministic embedding，因此它主要证明工程链路可运行。真实语义效果需要后续接入真实 embedding 模型后继续评测。

### 评测策略

阶段 2 复用阶段 1 的评测集：

```text
data/evaluation/keyword_queries.csv
```

关键词检索评测输出：

```text
data/evaluation/keyword_results.csv
```

向量检索评测输出：

```text
data/evaluation/vector_results.csv
```

当前结果：

```text
keyword baseline: 15/15 passed
vector search: 11/15 passed
```

这说明：

- 阶段 2 的向量检索链路已经跑通。
- deterministic embedding 不足以证明真实语义效果优于关键词检索。
- 后续优化应复用这些 failure cases 做回归测试。

阶段 2 完成标准：

```text
能为已有 chunks 构建 embedding
能保存 chunk_embeddings
能通过 POST /search/vector 返回来源、标题、片段和 score
能复用关键词评测集输出向量检索评测结果
关键词 baseline 仍可用
全量自动化测试通过
```

## 阶段 3 总体框架

阶段 3 的目标是打通第一条最小引用式问答链路：

```text
用户问题
-> CitationAnswerService
-> VectorSearchService 或 KeywordSearchService
-> prompt_builder 组织上下文和来源编号
-> ChatModelProvider 生成回答
-> extract_citations 过滤引用
-> ChatResponse 返回答案、来源和拒答状态
-> qa_logs 保存问答记录
```

本阶段参考 Quivr 的 `LLMEndpoint`、RAG prompt、source index 和 response metadata 思路，但继续保持轻量 service 分层，不引入 LangGraph 或复杂 Agent workflow。

```text
Quivr LLMEndpoint          -> 本项目 ChatModelProvider
Quivr combine_documents    -> 本项目 prompt_builder / ContextSource
Quivr ParsedRAGResponse    -> 本项目 CitationAnswerResult / ChatResponse
Quivr RAGResponseMetadata  -> 本项目 citations / sources / model_provider / model_name / refused
```

阶段 3 不做：

- Agent 工具调用。
- 多轮聊天历史。
- 复杂 LangGraph workflow。
- 真实模型质量优化。
- rerank 或混合检索优化。

这些内容放到阶段 4 以后逐步处理。

### Generation 层

阶段 3 新增 `app/services/generation/`：

```text
app/services/generation/
  chat_model.py       ChatModelProvider、deterministic provider、OpenAI-compatible provider
  prompt_builder.py   ContextSource、RagPrompt、build_rag_prompt()
  answer_service.py   CitationAnswerService、引用提取、拒答和日志写入
```

为什么新增 generation 层：

- 阶段 1/2 已经有 ingestion 和 retrieval。
- 阶段 3 需要独立承接 prompt、模型调用和答案生成。
- API 层不应该直接写检索、prompt 和模型调用细节。

### ChatModelProvider

`ChatModelProvider` 是聊天模型适配接口：

```text
messages -> ChatModelResult(answer, provider, model_name, raw_response)
```

当前实现：

- `DeterministicChatModelProvider`：用于本地开发和自动化测试。
- `OpenAICompatibleChatModelProvider`：预留国产大模型或兼容 OpenAI `/chat/completions` 的真实调用边界。

配置项：

```text
CHAT_MODEL_PROVIDER
CHAT_MODEL_NAME
CHAT_MODEL_API_KEY
CHAT_MODEL_BASE_URL
CHAT_MODEL_TEMPERATURE
CHAT_MODEL_TIMEOUT_SECONDS
```

### RAG prompt/context builder

`prompt_builder.py` 把检索结果转成模型可读上下文：

```text
SearchResultLike
-> ContextSource(source_id, chunk_id, document_title, content, score, ...)
-> RagPrompt(messages, context_text, sources)
```

来源编号规则：

- 每次回答内部从 `[1]` 开始编号。
- `source_id` 是本次回答的局部编号，不等于数据库 `chunk_id`。
- API 返回的 `sources` 保存 `source_id -> chunk_id` 的映射。

prompt 约束：

- 只基于给定资料回答。
- 回答中引用来源编号。
- 资料不足时拒答。
- 区分事实、推断和工程风险。
- 明确系统不替代规范审查、工程设计和专家判断。

### CitationAnswerService

`CitationAnswerService` 是阶段 3 的核心编排层：

```text
answer(question, top_k, retrieval_mode, min_score)
```

职责：

- 校验问题和参数。
- 根据 `retrieval_mode` 检索 chunks。
- `auto` 模式先向量检索，失败后关键词回退。
- 资料为空或低于 `min_score` 时拒答。
- 调用 `build_rag_prompt()`。
- 调用 `ChatModelProvider.generate()`。
- 从答案中提取 `[1]`、`[2]` 这类 citations。
- 只保留本次 sources 中存在的 citations。
- 返回 `CitationAnswerResult`。
- 默认保存 `qa_logs`。

返回结构：

```text
question
answer
citations
sources
refused
refusal_reason
retrieval_mode
model_provider
model_name
```

### Chat API

阶段 3 新增：

```text
POST /chat
```

请求结构 `ChatRequest`：

```text
question
top_k
retrieval_mode: auto | vector | keyword
min_score
```

响应结构 `ChatResponse`：

```text
question
answer
citations
sources
refused
refusal_reason
retrieval_mode
model_provider
model_name
```

`ChatSourceItem` 包含：

```text
source_id
document_id
document_title
source_type
source_path
file_name
chunk_id
chunk_index
heading_path
content
score
```

API 层保持薄封装：

- 用 Pydantic 校验请求。
- 用 `Depends(...)` 注入数据库、chat provider、embedding provider。
- 调用 `CitationAnswerService`。
- 把内部结果映射成对外响应。

### QA 日志

阶段 3 新增 `qa_logs` 表，对应 `QuestionAnswerLog`：

```text
qa_logs
  id
  question
  answer
  retrieved_chunk_ids
  citations
  model_provider
  model_name
  retrieval_mode
  refused
  refusal_reason
  created_at
```

设计原则：

- 记录排查需要的信息。
- 不保存 API key。
- 不保存 `ChatModelResult.raw_response`。
- `retrieved_chunk_ids` 和 `citations` 当前用 Text 保存 JSON 整数列表，后续迁移 PostgreSQL 时可升级为 JSON 字段。
- `CitationAnswerService` 默认写日志，测试或批处理可以用 `log_answers=False` 关闭。

### 评测策略

阶段 3 新增：

```text
data/evaluation/chat_queries.csv
scripts/evaluate_chat.py
data/evaluation/chat_results.csv
```

评测指标：

- 是否返回答案。
- 是否按预期拒答。
- 是否返回 sources。
- citations 是否能映射到 sources。
- 期望来源是否命中。
- 答案是否包含明显不在资料中的禁止词。

当前结果：

```text
chat evaluation: 6/6 passed
keyword baseline: 15/15 passed
vector evaluation: 11/15 passed
full tests: 106 passed
```

### 阶段 3 完成标准

```text
ChatModelProvider 可替换
RAG prompt 可构造
AnswerService 可返回 answer/citations/sources/refused/model 信息
POST /chat 可调用
资料不足时拒答
问答日志可追踪
chat 评测脚本可运行
旧关键词和向量评测仍可运行
全量自动化测试通过
```

## 阶段 4 总体框架

阶段 4 的目标是补齐资料来源治理层，让“有哪些资料来源、是否可信、能否保存全文、是否已经入库”这些问题有统一答案。

```text
公开资料候选 / PDF manifest / metadata CSV / metadata cards
-> SourceRegistryService
-> DOI / URL / 标题归一化
-> SourceRepository
-> sources 表
-> sync_sources.py 或 sources API
-> reindex_source()
-> IngestionService
-> documents/chunks
-> 后续向量索引刷新
```

阶段 4 不做：

- Agent 工具调用。
- 复杂 LangGraph workflow。
- 前端界面。
- 大规模爬虫。
- 检索召回质量优化。

这些内容放到阶段 5 以后逐步处理。

### Source Registry 层

阶段 4 新增 `app/services/source_registry.py`：

```text
SourceCandidate
-> candidate_to_source_create()
-> normalize_doi / normalize_url / normalize_title
-> derive_trust_level()
-> derive_fulltext_permission()
-> derive_status()
-> SourceRepository
-> sources
```

这个 service 位于“采集候选”和“数据库来源表”之间。它的作用不是下载更多论文，而是把已有来源变成可治理、可查询、可去重、可重新导入的结构化记录。

### sources 表

阶段 4 新增 `sources` 表：

```text
sources
  id
  source_id
  title
  normalized_title
  authors
  year
  venue
  category
  discovered_via
  doi
  normalized_doi
  url
  normalized_url
  pdf_url
  abstract
  keywords
  language
  citation_count
  source_type
  trust_level
  access_rights
  fulltext_permission
  license_or_terms
  local_path
  status
  notes
  document_id
  created_at
  updated_at
```

`sources.document_id` 可为空。这样一条来源可以先被登记为 `candidate` 或 `collected`，等用户确认或前端触发后，再通过 reindex 导入到 `documents/chunks`。

`sources` 和 `documents/chunks` 的关系：

```text
sources
  管来源、权限、状态、可信度、重复合并和 reindex 入口

documents/chunks
  管已经入库、可检索、可引用的正文或题录卡片
```

### 去重策略

阶段 4 使用三层去重：

```text
DOI -> URL -> 标题
```

设计原因：

- DOI 是论文最稳定标识，优先级最高。
- URL 可以识别网页、期刊页面、PDF 链接和题录页面。
- 标题归一化用于没有 DOI/URL 的题录或历史资料卡。

重复来源不会简单丢弃。当前策略是把更完整的字段合并到已有来源，并在 `notes` 中记录 `merged_duplicate_source_id=...`，方便后续审计。

### 可信度与权限

阶段 4 将可信度和全文保存权限分开：

```text
trust_level
  来源可靠程度，例如 high / medium / low。

fulltext_permission
  本项目能否保存全文，例如 open_access / institutional_access / metadata_only / unknown。
```

这样设计是为了避免把两个问题混在一起：一篇期刊论文可能很可信，但项目只能保存题录；一份开放 PDF 可以保存全文，但仍需要记录来源和许可。

### 来源状态

阶段 4 使用固定字符串表达来源生命周期：

```text
candidate
collected
imported
duplicate
rejected
```

含义：

- `candidate`：已发现但未收集原文。
- `collected`：已有本地路径、题录卡片或可用来源信息。
- `imported`：已经通过 reindex 进入 `documents/chunks`。
- `duplicate`：被识别为重复来源。
- `rejected`：因不相关、质量低或权限不合适而拒绝。

### 来源同步脚本

阶段 4 新增：

```text
scripts/sync_sources.py
```

默认读取：

```text
data/source_candidates.csv
data/fulltext_manifest.csv
data/metadata/rfc_papers_metadata.csv
data/imports/metadata_corpus/*.md
```

真实同步结果：

```text
total=283
created=125
updated=132
duplicates=26
```

脚本是幂等的：重复运行不会重复创建同一来源，而是更新已有来源或合并重复来源。

### 来源管理 API

阶段 4 新增：

```text
GET /sources
GET /sources/{source_id}
POST /sources/sync
POST /sources/{source_id}/reindex
```

API 层保持薄封装：

- 用 Pydantic schema 校验和组织响应。
- 用 repository 查询来源。
- 用 `SourceRegistryService` 执行 reindex。
- 把找不到来源映射成 404，把无法导入映射成可理解的 400。

### 重新索引

`reindex_source()` 的最小流程：

```text
source_id
-> 查询 sources
-> 如果 local_path 存在，导入原文件
-> 如果是 metadata-only，生成 metadata card 后导入
-> IngestionService.import_document()
-> 更新 sources.document_id
-> 更新 sources.status=imported
```

阶段 4 先提供入口，不做后台任务队列。后续前端可以把 reindex 做成按钮，Agent 工具阶段也可以把它包装成受控工具。

### 来源评测

阶段 4 新增：

```text
scripts/evaluate_sources.py
data/evaluation/source_registry_metrics.csv
```

当前指标：

```text
total_sources=125
linked_documents=0
merged_duplicates=14
status=candidate:8;collected:117
fulltext_permission=institutional_access:2;metadata_only:110;open_access:10;unknown:3
trust_level=high:125
```

`linked_documents=0` 表示当前 source registry 已登记来源，但尚未对真实库逐条执行 reindex。这个状态是可接受的，因为阶段 4 的目标是提供登记、治理和入口；批量导入或前端触发可在后续阶段继续推进。

### 阶段 4 完成标准

```text
sources 表可创建
来源可以从现有 CSV / manifest / metadata corpus 同步
来源可按 DOI / URL / 标题去重
可信度、全文权限和状态字段可用
sources API 可查询、同步和 reindex
来源评测脚本可运行
documents/search/vector/chat 测试不被破坏
全量自动化测试通过
```

## 阶段 5 总体框架

阶段 5 的目标是把阶段 1-4 的后端能力变成非技术用户可操作的浏览器工作台：

```text
FastAPI
-> GET /
-> app/frontend/index.html
-> app/frontend/static/app.js
-> 调用 sources/documents/search/chat API
-> 浏览器展示来源、资料、片段、检索结果、回答和引用
```

阶段 5 不做：

- Agent 工具调用。
- 复杂 LangGraph workflow。
- 登录系统。
- 部署平台优化。
- 检索质量优化。

这些内容放到阶段 6 和阶段 7。

### 前端目录

```text
app/
  api/
    frontend.py
  frontend/
    index.html
    static/
      app.js
      styles.css
```

`app/api/frontend.py` 提供：

```text
GET /
GET /favicon.ico
```

`app/main.py` 使用 `StaticFiles` 挂载：

```text
/static -> app/frontend/static
```

### 前端数据流

```text
页面加载
-> GET /health
-> GET /sources
-> GET /documents
-> 渲染概览指标、来源表、资料表
```

来源管理：

```text
GET /sources
-> 浏览器端关键词 / 状态 / 全文权限筛选
-> sources 表格
```

资料管理：

```text
GET /documents
-> documents 表格
-> 点击 chunks
-> GET /documents/{document_id}/chunks
-> chunks 面板
```

检索：

```text
POST /search 或 POST /search/vector
-> result cards
```

问答：

```text
POST /chat
-> answer
-> citations
-> sources sidebar
```

来源操作：

```text
POST /sources/sync
POST /sources/{source_id}/reindex
```

### 前端设计边界

- 前端只负责展示、筛选、发起 API 请求和反馈状态。
- 来源去重、可信度、权限、reindex、检索和问答仍由后端 service 负责。
- 第一版使用原生 HTML/CSS/JS，避免阶段 5 过早引入 Node 构建链。
- 首页就是工作台，不做 landing page。
- 桌面和移动视口都要保持可读，不出现横向溢出。

### 阶段 5 完成标准

```text
GET / 可访问
静态 CSS/JS 可访问
sources 和 documents 可展示
document chunks 可查看
keyword/vector search 可触发
chat 可触发并展示引用来源
source sync/reindex 有操作入口和反馈
浏览器桌面与移动视口验证通过
全量自动化测试通过
```
