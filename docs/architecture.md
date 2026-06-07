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
-> Brain 中控层
-> 检索召回
-> 组织上下文
-> 大模型回答
-> 返回答案和引用来源
-> Agent 工具编排
-> 前端工作台展示和操作
```

## 初始分层

```text
API 层：FastAPI 路由
Schema 层：Pydantic 请求和响应模型
Service 层：导入、切分、检索、问答业务逻辑
Agent 层：受控工具封装、意图路由、工具调用记录和拒答约束
Brain 层：RAG workflow 中控、RetrievalConfig、WorkflowConfig、step 记录和 chat/agent 复用
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

阶段 8 完成时结果：

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

## 阶段 6 总体框架

阶段 6 的目标是把“能检索、能回答”推进到“质量可度量、优化可解释、结果可复现”。

```text
documents/chunks/sources/chunk_embeddings
-> keyword/vector/chat baseline
-> evaluation plan
-> retrieval error cases
-> HybridSearchService
-> POST /search/hybrid
-> hybrid evaluation
-> metrics comparison
-> frontend minimal mode selector
```

阶段 6 不做：

- Agent 工具调用。
- 复杂 LangGraph workflow。
- 登录系统。
- 部署优化。
- 大规模前端重构。

这些内容放到阶段 7 以后逐步处理。

### 评测计划

阶段 6 新增：

```text
docs/evaluation_plan.md
```

核心指标：

```text
Recall@K
Citation Accuracy
Faithfulness
Answer Coverage
Refusal Quality
```

当前自动化口径：

- `Recall@K` 由 keyword/vector/hybrid 评测脚本按期望标题、正文片段和 source_type 近似判断。
- `Citation Accuracy` 由 chat 评测脚本检查 citations 是否能映射到本次 sources，并检查期望来源是否命中。
- `Faithfulness` 当前用禁止词和拒答规则做轻量自动检查，后续接真实模型后可加入人工审阅或 LLM-as-judge。
- `Answer Coverage` 当前由期望词和来源命中近似承接。
- `Refusal Quality` 由 chat 评测集中的无依据问题验证。

### 混合检索服务

阶段 6 新增：

```text
app/services/retrieval/hybrid_search.py
```

`HybridSearchService` 复用已有两条召回链路：

```text
query
-> KeywordSearchService.search(fetch_k)
-> VectorSearchService.search(fetch_k)
-> 按 chunk_id 去重
-> keyword/vector 分数分别按最大分归一化
-> keyword_weight + vector_weight + both_match_bonus
-> source_type_rank 和稳定字段兜底排序
-> top_k results
```

默认权重：

```text
keyword_weight = 0.7
vector_weight = 0.3
both_match_bonus = 0.15
```

这样设计的原因：

- keyword baseline 当前 15/15，适合救回 deterministic vector 的弱召回。
- vector 仍保留语义召回能力，后续接真实 embedding provider 后可以继续受益。
- 不改写 `/search` 或 `/search/vector`，避免破坏 baseline。
- 权重和 bonus 可解释，适合写入错误案例和面试表达。

### API 与 Chat 集成

阶段 6 新增：

```text
POST /search/hybrid
```

请求字段与现有检索入口保持一致：

```text
query
top_k
```

响应结构与向量检索类似：

```text
query
top_k
provider
model_name
results
```

`POST /chat` 新增显式检索模式：

```text
retrieval_mode = "hybrid"
```

但 `auto` 模式仍保留阶段 3 的旧行为：先尝试 vector，有结果则使用 vector，只在无结果时 fallback 到 keyword。这样可以避免阶段 6 中途改变 chat baseline 的含义。

### 评测脚本与结果

阶段 6 新增和复用：

```text
scripts/evaluate_keyword_search.py
scripts/evaluate_vector_search.py
scripts/evaluate_hybrid_search.py
scripts/evaluate_chat.py
scripts/analyze_retrieval_errors.py

data/evaluation/keyword_results.csv
data/evaluation/vector_results.csv
data/evaluation/hybrid_results.csv
data/evaluation/chat_results.csv
data/evaluation/retrieval_error_cases.csv
```

当前结果：

```text
keyword baseline: 15/15 passed
vector search: 11/15 passed
hybrid search: 15/15 passed
chat evaluation: 6/6 passed
rescued_vector: 4
regressed_keyword: 0
retrieval error cases: 4 fixed_by_hybrid
full tests: 141 passed
```

### 前端最小展示

阶段 6 只在现有工作台中增加 hybrid 选项：

```text
app/frontend/index.html
app/frontend/static/app.js
```

搜索模式：

```text
keyword
vector
hybrid
```

聊天检索模式：

```text
auto
hybrid
vector
keyword
```

前端仍只负责选择模式和调用 API；混合检索排序、去重和评分逻辑都在后端 service 中。

### 阶段 6 完成标准

```text
docs/evaluation_plan.md 已建立
keyword/vector/chat baseline 已复跑
retrieval_error_cases.csv 已生成
hybrid search service/API/chat mode 已实现
hybrid_results.csv 可对比优化前后指标
旧 search/vector/chat/sources/frontend 测试不被破坏
前端能最小展示 hybrid 检索模式
全量自动化测试通过
```

## 阶段 7 总体框架

阶段 7 的目标是把阶段 6 稳定的 RAG 能力包装成受控、只读优先、可测试、可追踪的 Agent 工具调用链路。

```text
用户任务
-> POST /agent/query
-> AgentService
-> AgentToolbox
-> search / hybrid search / citation chat / sources
-> AgentQueryResult
-> answer + tool_calls + sources + citations + refused + reasoning_summary
-> 前端 Agent 面板展示
```

阶段 7 不做：

- 复杂 LangGraph workflow。
- 登录系统。
- 部署优化。
- 联网爬虫扩展。
- 自动执行写入型 source reindex。

### Agent 目录

阶段 7 新增：

```text
app/
  api/
    agent.py
  schemas/
    agent.py
  services/
    agent/
      __init__.py
      tools.py
      service.py
scripts/
  evaluate_agent.py
data/
  evaluation/
    agent_queries.csv
    agent_results.csv
docs/
  agent_design.md
```

### 工具层

`AgentToolbox` 是 Agent 的工具封装层。

当前只读工具：

```text
search_knowledge
  复用 KeywordSearchService，保留关键词 baseline。

hybrid_search_knowledge
  复用 HybridSearchService，作为搜索类任务默认工具。

answer_with_citations
  复用 CitationAnswerService，返回 answer、citations、sources 和 refused。

list_sources
  复用 SourceRepository，列出已登记来源。

get_source_detail
  复用 SourceRepository，查询单条来源详情。
```

工具返回统一结构：

```text
AgentToolResult
  answer
  search_results
  sources
  citations
  refused
  refusal_reason
  tool_call
```

工具调用记录：

```text
AgentToolCallRecord
  tool_name
  input_summary
  output_summary
  succeeded
  error
```

这样设计的原因：

- API 和前端可以直接展示工具调用过程。
- 评测脚本可以检查工具是否选对。
- 失败时可以返回可理解的失败记录，而不是让异常逃逸。

### 编排层

`AgentService` 是阶段 7 的轻量编排服务。

职责：

- 校验 `question`、`top_k` 和 `max_tool_calls`。
- 用规则式意图路由判断任务类型。
- 控制最多工具调用步数。
- 调用 `AgentToolbox`。
- 汇总 `answer`、`tool_calls`、`sources`、`search_results`、`citations`、`refused` 和 `reasoning_summary`。

当前意图路由：

```text
搜索 / 检索 / 查找
-> hybrid_search_knowledge

来源列表
-> list_sources

来源详情 + source_id
-> get_source_detail

来源详情但缺少 source_id
-> 拒答，提示需要 source_id

其他问答
-> answer_with_citations
```

第一版不用 LLM 做规划，是为了保证阶段 7 的行为稳定、可解释、可自动测试。后续如果接入 LLM 规划，也必须保留只读优先、最大步数、权限字段、工具调用记录和评测回归。

### Agent API

阶段 7 新增：

```text
POST /agent/query
```

请求字段：

```text
question
top_k
max_tool_calls
source_id
```

响应字段：

```text
question
answer
tool_calls
search_results
sources
citations
refused
refusal_reason
reasoning_summary
```

API 层保持薄封装：只做请求校验、依赖注入和响应映射，不直接写检索、问答或来源查询逻辑。

### 评测策略

阶段 7 新增：

```text
data/evaluation/agent_queries.csv
scripts/evaluate_agent.py
data/evaluation/agent_results.csv
```

Agent 评测检查：

- 期望工具是否被调用。
- 拒答是否符合预期。
- 需要来源的任务是否返回 sources。
- 需要引用的任务 citations 是否能映射到 sources。
- 期望来源标题或内容词是否命中。
- 工具调用次数是否受控。

当前结果：

```text
agent evaluation: 5/5 passed
refused=1
tool_failures=0
citation_failures=0
full tests=163 passed
```

## 阶段 8 总体框架

阶段 8 的目标是把阶段 3-7 已经跑通的 RAG 问答、检索和 Agent 回答能力收拢到一个轻量 Brain 中控层。

核心数据流：

```text
POST /chat 或 AgentToolbox.answer_with_citations
-> CitationAnswerService 兼容门面
-> RetrievalConfig / WorkflowConfig
-> BrainService.answer()
-> filter_history
-> rewrite_query
-> retrieve
-> optional_rerank
-> generate_answer
-> answer / citations / sources / qa_logs
```

阶段 8 不改变外部 API 响应结构：

```text
POST /chat
  仍然返回 question、answer、citations、sources、refused、retrieval_mode、model_provider、model_name

POST /agent/query
  仍然返回 answer、tool_calls、search_results、sources、citations、refused、reasoning_summary
```

### Brain 模块

阶段 8 新增：

```text
app/services/brain/__init__.py
app/services/brain/config.py
app/services/brain/workflow.py
app/services/brain/service.py
```

`BrainService` 的职责：

- 接收用户问题和 `RetrievalConfig`。
- 按 `WorkflowConfig` 执行 RAG workflow。
- 复用 `KeywordSearchService`、`VectorSearchService`、`HybridSearchService`。
- 复用 `build_rag_prompt`、`ChatModelProvider`、citation 提取和 `QuestionAnswerLogRepository`。
- 返回 `BrainAnswerResult`，其中包含 answer、citations、sources、refused、retrieval_mode、model 信息和 workflow step 记录。

Brain 不负责：

- 不直接写 SQL。
- 不联网爬取新资料。
- 不自动执行 source reindex。
- 不替代 source registry、documents/chunks 或 retrieval service。
- 不引入复杂 LangGraph workflow。

### 配置模型

`RetrievalConfig` 控制一次问答的检索和生成参数：

```text
retrieval_mode: auto / keyword / vector / hybrid
top_k
min_score
max_history
rerank_top_n
prompt_profile
model_provider
workflow_config
```

`WorkflowConfig` 默认步骤：

```text
filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer
```

第一版实现中：

- `filter_history` 是历史过滤占位，用于后续多轮问答。
- `rewrite_query` 是问题改写占位，用于后续 query expansion。
- `retrieve` 复用现有检索服务。
- `optional_rerank` 使用可解释截断，为后续真实 reranker 预留位置。
- `generate_answer` 复用现有引用式问答链路。

### 与 Quivr 的取舍

本阶段借鉴 Quivr 的三个思想：

- Brain 作为中控对象。
- RetrievalConfig 作为检索与生成参数包。
- WorkflowConfig 作为 RAG 步骤描述。

但本项目不照搬 Quivr 代码，也不引入 LangGraph。阶段 8 的选择是先用普通 Python service 固定边界，让 `/chat` 和 Agent 共用一条可测试、可评测的工作流。

### 配置化评测

阶段 8 新增：

```text
scripts/evaluate_brain_workflow.py
data/evaluation/brain_workflow_results.csv
tests/test_evaluate_brain_workflow.py
```

评测比较三种配置：

```text
default_hybrid
keyword_baseline
vector_only
```

CSV 记录：

- config 名称
- configured / actual retrieval mode
- top_k、min_score、rerank_top_n
- workflow steps
- workflow_succeeded
- citations_valid
- expected_source_hit
- refusal_matched

当前结果：

```text
default_hybrid: 4/6 passed
keyword_baseline: 6/6 passed
vector_only: 2/6 passed
```

这个结果说明阶段 8 已经能对不同 Brain 配置做可复现比较；阶段 10 和阶段 11 已在此基础上进一步提升 Brain workflow 和真实用户问题评测质量。

### 阶段 8 完成标准

```text
docs/brain_workflow_design.md 已建立
app/services/brain/ 已建立
RetrievalConfig / WorkflowConfig 已实现
BrainService 五步 workflow 已实现
CitationAnswerService 已复用 Brain
Agent answer_with_citations 已复用同一路径
Brain 配置化评测脚本和结果 CSV 已生成
search/vector/hybrid/chat/agent/sources/frontend 回归通过
全量自动化测试通过：189 passed
```

## 阶段 9 总体框架

阶段 9 的目标是补齐真实模型接入与模型评测闭环。

阶段 9 不改变外部 API 响应结构，而是增强 Model Provider 层：

```text
POST /search/vector 或 POST /search/hybrid
-> API dependency 创建 EmbeddingProvider
-> VectorSearchService / HybridSearchService
-> chunk_embeddings 按 provider/model/dimension 查询
-> 返回检索结果

POST /chat 或 AgentToolbox.answer_with_citations
-> CitationAnswerService
-> BrainService
-> ChatModelProvider + EmbeddingProvider
-> 返回 answer/citations/sources
```

阶段 9 新增：

```text
docs/model_provider_evaluation.md
OpenAICompatibleEmbeddingProvider
EMBEDDING_DIMENSION
EMBEDDING_TIMEOUT_SECONDS
scripts/build_vector_index.py provider/model/dimension 参数
scripts/evaluate_model_configs.py
data/evaluation/model_config_results.csv
```

### Provider 边界

`ChatModelProvider` 管“怎么生成回答”。

`EmbeddingProvider` 管“怎么把问题或资料片段变成向量”。

业务 service 不直接知道具体模型厂商，只调用统一方法：

```text
chat_model_provider.generate(messages)
embedding_provider.embed_texts(texts)
embedding_provider.embed_query(query)
```

这样后续替换国产兼容模型、OpenAI-compatible 模型或本地模型时，不需要重写 retrieval、Brain、Agent 或 API schema。

### 真实 embedding 索引

`chunk_embeddings` 的唯一约束包含：

```text
chunk_id
provider
model_name
```

同时保存：

```text
dimension
content_hash
embedding_json
```

阶段 9 之后，同一份 chunk 可以同时存在 deterministic 索引和真实模型索引。切换真实 embedding provider 后必须重建向量索引，检索时才会命中当前 provider/model/dimension 对应的 embedding。

阶段 9.1 已使用 Jina `jina-embeddings-v3` 重建真实向量索引：997 个 chunk 中 995 个新写入，2 个已存在跳过。Jina provider 使用 1024 维向量，因此检索时必须继续按 provider=`openai-compatible`、model=`jina-embeddings-v3`、dimension=`1024` 查询，不能混用 deterministic 索引。

### 模型配置评测

阶段 9 新增模型配置汇总评测：

```text
scripts/evaluate_model_configs.py
data/evaluation/model_config_results.csv
```

它汇总：

```text
keyword
vector
hybrid
chat
agent
brain_workflow
```

当前结果：

```text
deterministic_baseline:
  keyword 15/15
  vector 11/15
  hybrid 15/15
  chat 6/6
  agent 5/5
  brain_workflow 12/18

real_config:
  skipped because local real model configuration is incomplete
```

这说明阶段 9 已具备真实模型接入和可对比评测入口，但默认仍保留 deterministic，避免本地测试依赖 API key、网络、限流和模型供应商状态。

### 阶段 9.1 真实 Jina 与 MIMO 补充验证

阶段 9.1 没有改变外部 API contract，而是验证真实 provider 能被现有 RAG 链路消费：

```text
Jina embeddings
-> chunk_embeddings(provider/model/dimension/content_hash)
-> vector / hybrid retrieval
-> Brain workflow
-> MIMO chat answer
-> citations / sources / refusal evaluation
```

实现上的关键点：

```text
OpenAICompatibleEmbeddingProvider
  增加 Accept 和 User-Agent 请求头，兼容 Jina API 行为

OpenAICompatibleChatModelProvider
  同时发送 Authorization: Bearer 和 api-key
  保留 Accept、Content-Type 和 User-Agent
  兼容常规 OpenAI-compatible 服务和 MIMO Token Plan
```

真实组合评测结果：

```text
Jina vector: 14/15
Jina hybrid: 15/15
MIMO + Jina chat: 6/6
MIMO + Jina agent: 5/5
MIMO + Jina brain_workflow: 15/18
full tests: 208 passed
```

架构结论：真实 MIMO + Jina 组合证明 provider 边界有效，业务层无需知道具体供应商差异。剩余 3 个 brain workflow 失败项集中在 `vector_only` 和 `unsupported` 边界，说明下一阶段不应继续扩 provider，而应优化检索置信度、拒答判断和 hybrid/rerank 策略。

## 阶段 10 真实 RAG 质量校准与拒答边界优化

阶段 10 的目标不是新增模型 provider，而是在真实模型已经能运行的基础上，校准 RAG 的质量边界。

本阶段处理的失败链路是：

```text
真实 Jina / MIMO 评测结果
-> 失败案例分析
-> Brain 生成前证据置信度检查
-> vector-only 候选主题锚点重排
-> deterministic 与真实模型结果对比
```

### 失败案例分析

阶段 10 新增：

```text
scripts/analyze_real_rag_failures.py
data/evaluation/real_rag_failure_cases.csv
tests/test_analyze_real_rag_failures.py
```

失败案例表记录：

- 失败问题。
- 失败配置。
- 失败原因。
- 召回片段标题。
- 期望依据。
- 改进建议。

它把阶段 9.1 的失败拆成三类：

```text
unsupported_low_evidence
vector_topic_drift
cross_language_topic_gap
```

### Evidence Confidence

阶段 10 在 Brain workflow 中新增 `EvidenceConfidence`。

它解决的问题是：检索有结果，不代表证据足够回答。

数据流：

```text
BrainService.retrieve()
-> BrainRetrievalOutcome(results)
-> evaluate_evidence_confidence(question, results)
-> confidence.sufficient?
   -> yes: build prompt and call ChatModelProvider
   -> no: return DEFAULT_REFUSAL_ANSWER without model generation
```

当前规则使用轻量 query-token coverage：

```text
question
-> normalize and extract evidence terms
-> compare with result title / heading / content
-> matched_terms / query_terms
-> coverage >= 0.20 means sufficient
```

设计取舍：

- 不依赖真实模型自评，保证 deterministic 测试可复现。
- 不改变基础 search API schema。
- 不把低证据片段交给真实模型硬生成。
- 先覆盖乱字符串式 unsupported query，避免过度拒答正常工程问题。

### 低证据拒答

低证据拒答发生在 Brain 的 `generate_answer` 步骤之前。

当证据不足时，系统返回：

```text
answer = DEFAULT_REFUSAL_ANSWER
sources = []
citations = []
refused = true
refusal_reason = evidence confidence insufficient
```

因为 `/chat` 和 Agent `answer_with_citations` 都复用 Brain，因此这条保护同时覆盖：

```text
POST /chat
POST /agent/query -> answer_with_citations
```

### Topic Anchor Rerank

阶段 10 在 `VectorSearchService` 中新增 topic anchor rerank。

原向量检索：

```text
query embedding
-> cosine similarity
-> top_k
```

阶段 10 后：

```text
query embedding
-> cosine similarity candidates
-> topic anchor score from query terms and document text
-> combined internal rank score
-> top_k
```

实现要点：

- 复用 `keyword_search.expand_query_terms()` 的领域词扩展。
- `TOPIC_ANCHOR_BOOST = 0.20`。
- 返回给 API 和 CSV 的 `score` 仍是 cosine score。
- topic anchor 只参与内部排序，不改变 `POST /search/vector` 响应结构。
- 不把 vector-only 静默 fallback 到 hybrid，保留 baseline 可解释性。

### 阶段 10 评测结果

deterministic 结果：

```text
vector: 13/15
hybrid: 15/15
chat: 6/6
agent: 5/5
brain_workflow:
  default_hybrid 6/6
  keyword_baseline 6/6
  vector_only 6/6
full tests: 216 passed
```

真实 MIMO + Jina 校准结果：

```text
Jina vector: 15/15
Jina hybrid: 15/15
MIMO + Jina chat: 6/6
MIMO + Jina agent: 5/5
MIMO + Jina brain_workflow:
  default_hybrid 6/6
  keyword_baseline 6/6
  vector_only 6/6
```

架构结论：阶段 10 后，真实模型更适合做最终体验校准，deterministic provider 更适合做稳定回归。RAG 质量保护应优先放在 Brain 生成前，而不是只靠 prompt 要求模型“不要胡编”。

## 阶段 11 真实用户问题评测集与跨语言质量提升

阶段 11 不改变外部 API schema，而是在评测层、检索词表和 Brain 证据判断层补强真实用户问法覆盖。

核心数据流：

```text
data/evaluation/user_questions.csv
-> scripts/evaluate_user_questions.py
-> BrainService.answer()
-> keyword / vector / hybrid retrieval
-> query expansion / topic anchor
-> Brain evidence confidence
-> answer / refusal / sources / citations
-> data/evaluation/user_question_results.csv
-> data/evaluation/user_question_review_samples.csv
```

### 用户问题评测集

阶段 11 新增：

```text
data/evaluation/user_questions.csv
scripts/evaluate_user_questions.py
data/evaluation/user_question_results.csv
tests/test_user_questions.py
tests/test_evaluate_user_questions.py
```

`user_questions.csv` 与阶段 10 的 `chat_queries.csv` 分开维护，原因是两者用途不同：

- `chat_queries.csv` 保留旧问答 baseline，适合长期稳定回归。
- `user_questions.csv` 覆盖更接近真实提问的语言形态，例如中文口语、英文问题、中英混合术语、工程中文和 unsupported。

新增字段中，`language_type` 用来标记问题语言形态，`expected_answer_points` 用来给人工审阅或 LLM-as-judge 判断回答覆盖度。

### 跨语言 Query Expansion

阶段 11 继续复用 `app/services/retrieval/keyword_search.py` 中的 `SYNONYM_RULES`：

```text
中文工程词
-> 英文论文术语
-> keyword search term expansion
-> vector topic anchor
-> evidence confidence expanded terms
```

这样做的好处是同一套可解释词表能服务三处能力：

- `KeywordSearchService`：提高中文、英文、中英混合问法的关键词召回。
- `VectorSearchService`：topic anchor 在向量候选内部做轻量主题重排。
- `BrainService`：evidence confidence 使用扩展后的中英文证据词，避免中文问题与英文证据之间的误拒答。

阶段 11 增强的术语包括：

```text
ITZ / 界面 / interfacial transition zone
creep / 徐变 / 长期变形
freeze-thaw / 冻融 / 抗冻
porosity / void / 孔隙率 / 孔洞
emission / cost / schedule / 碳排放 / 成本 / 工期
steel fiber / 钢纤维
rock shear keys / 剪力键
compactness / compaction detection / 灌满 / 密实度
```

### 离线审阅设计

阶段 11 新增：

```text
docs/stage11_user_evaluation_plan.md
data/evaluation/user_question_review_samples.csv
tests/test_stage11_user_evaluation_plan.py
```

自动评测适合稳定检查：

```text
Refusal Quality
Source Hit
Citation Quality
Forbidden Terms
```

人工审阅或 LLM-as-judge 离线校准适合检查：

```text
Faithfulness
Answer Coverage
Citation Quality
```

LLM-as-judge 在本项目中只作为离线质量裁判设计，不进入 CI，不作为自动回归前提，也不要求真实 API key。

### 阶段 11 评测结果

```text
keyword: 15/15
vector: 13/15
hybrid: 15/15
chat: 6/6
agent: 5/5
brain_workflow: 18/18
user_question_evaluation: 25/30
  default_hybrid: 10/10
  keyword_baseline: 10/10
  vector_only: 5/10
full tests: 230 passed
```

架构结论：阶段 11 把质量提升放在“评测输入更真实”和“术语增强更可解释”上，而不是改变 API 或引入黑盒 workflow。剩余的 vector-only 用户问题失败项保留为下一阶段真实 embedding、rerank 或人工审阅校准依据。

## 阶段 12 质量审阅与上下文最小补全

阶段 12 不改变核心 RAG 架构，而是在质量审阅层和 Brain `rewrite_query` step 做最小增强。

核心数据流：

```text
data/evaluation/user_question_review_samples.csv
-> data/evaluation/stage12_quality_review_results.csv
-> docs/stage12_quality_review.md
-> BrainService.answer(history=...)
-> filter_history
-> rewrite_query
-> retrieve
-> evidence confidence
-> generate_answer
```

### 质量审阅链路

阶段 12 新增：

```text
data/evaluation/stage12_quality_review_results.csv
docs/stage12_quality_review.md
tests/test_stage12_quality_review.py
```

质量审阅补足自动评测的不足：

- 自动评测负责检查拒答匹配、来源命中、引用编号和禁止词。
- 人工或离线审阅负责检查 Faithfulness、Answer Coverage 和 Citation Quality。

阶段 12 审阅结论：

```text
default_hybrid 来源命中可靠
keyword_baseline 仍是稳定可解释 baseline
vector_only 仍有主题漂移
deterministic answer 不能单独证明真实回答覆盖度
```

### Context Rewrite

阶段 12 在 `app/services/brain/service.py` 中实现最小上下文补全：

```text
history + current question
-> filter_history
-> rewrite_contextual_question()
-> retrieval question
```

触发条件保持保守：

- 当前问题含有“它”“这个技术”“这类问题”“上面”“刚才”等明确上下文指代。
- 存在最近历史问题。
- 只拼接最近历史问题，不做长期记忆、不做用户画像、不调用真实模型改写。

示例：

```text
history: 堆石混凝土徐变有什么研究？
question: 它有哪些研究？
rewritten query: 堆石混凝土徐变有什么研究？；追问：它有哪些研究？
```

对外响应仍保留原始 `question`，补全后的 query 只用于检索、prompt 和 evidence confidence。这样既改善省略问法召回，又不改变用户看到的问题。

### Chat 与 Agent 接入

阶段 12 为 `/chat` 和 `/agent/query` 增加可选 `history` 字段：

```text
{
  "question": "它有哪些研究？",
  "history": ["堆石混凝土徐变有什么研究？"]
}
```

旧请求不传 `history` 仍保持兼容。Agent 不新增写入型工具，只把可选 history 传入已有 `answer_with_citations` 工具。

### 阶段 13 输入

阶段 12 新增：

```text
docs/stage13_decompose_plan.md
tests/test_stage13_decompose_plan.py
```

后续建议：

```text
original question
-> rule-based decompose
-> sub query retrieval
-> merge candidates
-> deduplicate by chunk_id
-> rerank by topic/source/score
-> Brain answer with citations
```

HyDE 只作为离线实验建议，不进入默认链路或 deterministic 自动回归。

阶段 12 评测结果：

```text
quality review tests: 8 passed
context rewrite focused tests: 52 passed
user questions: 25/30
chat: 6/6
agent: 5/5
Brain workflow: 18/18
API/core tests: 47 passed
full tests: 244 passed
```

架构结论：阶段 12 把质量校准和上下文补全都放在已有 Brain / evaluation 边界内，没有绕开引用、拒答和来源治理。后续阶段应优先做 Decompose 与可解释证据合并，而不是默认引入 HyDE 或复杂多轮记忆。

## 阶段 13 Decompose 与可解释证据合并

阶段 13 的目标是在 Brain 检索阶段增强复杂问题的证据覆盖，而不是替换 RAG 架构或改变外部 API。

核心数据流：

```text
BrainService._retrieve_with_hybrid()
-> decompose_query()
-> DecomposeRetrievalService.retrieve()
-> sub query hybrid retrieval
-> merge_sub_query_results()
-> MergedEvidence
-> build_retrieval_outcome()
-> evaluate_evidence_confidence()
-> build_rag_prompt()
-> ChatModelProvider
```

### 规则式 Decompose

阶段 13 新增：

```text
app/services/retrieval/decompose.py
tests/test_decompose_retrieval.py
```

核心结构：

```text
DecomposedQuery
  original_question
  sub_queries
  decomposed
  reason

SubQueryRetrievalResult
  sub_query
  retrieval_mode
  results

MergedEvidence
  普通 SearchResultLike 字段
  sub_queries
  keyword_score
  vector_score
  topic_score
  source_type_score
  both_match
  final_score
  explanation
```

规则边界：

- 子 query 最多 3 个。
- 只拆明显并列结构，例如“成本、工期和碳排放”“灌满以及密实度”“孔隙率和抗压表现”。
- 单主题问题继续使用原始 query。
- unsupported 乱字符串不强行拆解。
- 不调用真实模型拆解，避免自动回归依赖 API。

### Brain 集成

阶段 13 只在 hybrid 路径中接入 Decompose：

```text
question
-> decompose_query(question)
-> if decomposed: run sub query hybrid retrieval and merge evidence
-> else: keep original HybridSearchService
```

这样做有两个目的：

- 复杂问题能获得更完整证据。
- 单主题问题不多跑额外检索，避免 default_hybrid 退化。

阶段 13 初次接入时曾因“先执行 Decompose 服务再判断是否拆解”导致 Brain workflow `default_hybrid` 从 6/6 退到 5/6。修复后改为先运行轻量 `decompose_query()`，只有真正拆解时才执行子 query 检索，Brain workflow 恢复 18/18。

### 可解释 Rerank

`MergedEvidence` 的排序综合：

```text
normalized_retrieval_score
topic_match_bonus
source_type_bonus
both_match_bonus
sub_query_coverage_bonus
```

`explanation` 字段记录：

- 命中的 sub query 数量。
- 命中的主题词。
- 是否 keyword/vector 双路命中。
- source_type。
- raw_score 和 final_score。

这些信息目前用于评测 CSV 和调试，不改变 `/chat` 或 `/agent/query` 的响应 schema。

### 阶段 13 评测

阶段 13 新增：

```text
scripts/evaluate_decompose.py
data/evaluation/stage13_decompose_results.csv
tests/test_evaluate_decompose.py
```

评测字段包括：

- decompose_applied
- sub_query_count
- raw_result_count
- merged_result_count
- deduplicated_count
- provenance_present
- source_hit_matched
- answer_coverage_proxy
- rerank_explanations

阶段 13 结果：

```text
decompose evaluation: 6/6
all-user decompose evaluation: 10/10
user question evaluation: 29/30
Brain workflow: 18/18
chat: 6/6
agent: 5/5
hybrid: 15/15
vector baseline: 13/15
full tests: 257 passed
```

架构结论：阶段 13 把复杂问题处理放在检索证据层，而不是让模型自行长回答。系统继续保留引用、拒答、来源治理和 API 兼容边界。

## 阶段 14 真实 Embedding 与回答覆盖校准

阶段 14 的目标是在阶段 13 证据合并稳定后，把质量判断从“检索是否命中”推进到“真实配置状态和回答覆盖是否可审阅”。

核心数据流：

```text
sources/documents/chunks/chunk_embeddings
-> deterministic baseline
-> stage14 embedding comparison
-> stage14 answer coverage review
-> stage14 decompose provenance review
-> docs/progress / README / Obsidian quality conclusion
```

阶段 14 新增：

```text
docs/stage14_real_quality_calibration.md
scripts/evaluate_stage14_embedding_comparison.py
data/evaluation/stage14_embedding_comparison.csv
scripts/evaluate_stage14_answer_coverage.py
data/evaluation/stage14_answer_coverage_review.csv
scripts/evaluate_stage14_decompose_provenance.py
data/evaluation/stage14_decompose_provenance_review.csv
```

### Embedding Comparison

`stage14_embedding_comparison.csv` 汇总多套 suite：

```text
vector
hybrid
user_questions
decompose
chat
agent
brain_workflow
```

每行记录：

```text
config_name
suite
status
passed / total / failed / pass_rate
embedding_provider / embedding_model_name / embedding_dimension
chat_provider / chat_model_name
failed_queries
skipped_reason
```

阶段 14 的关键边界是：真实配置没有结果文件时，记录为 `missing_results` 或 `skipped`，而不是伪造成 passed。当前 deterministic baseline 结果为：

```text
vector: 13/15
hybrid: 15/15
user_questions: 25/30
decompose: 10/10
chat: 6/6
agent: 5/5
brain_workflow: 18/18
```

### Answer Coverage Review

`stage14_answer_coverage_review.csv` 把回答质量拆成三个维度：

```text
Faithfulness
Answer Coverage
Citation Quality
```

这张表不会把 deterministic answer 直接当作真实回答质量证明。当前默认链路多数样例标为 `answer_coverage=review`，意思是：检索来源和引用链路稳定，但仍需要真实模型回答或人工摘要确认是否覆盖核心技术点。

unsupported 随机问题被标为低风险，因为它正确拒答且不返回来源。

### Decompose Provenance Review

`stage14_decompose_provenance_review.csv` 把阶段 13 的长字符串 `rerank_explanations` 拆成证据级字段：

```text
evidence_rank
evidence_title
evidence_sub_query_count
topic_terms
both_match
source_type
raw_score
final_score
review_note
```

这样能直接审阅“某条证据为什么进入上下文”，而不需要人工从长字符串中拆解。当前输出为 50 条证据级记录，其中 15 条来自真正 decomposed 的问题，37 条具有 keyword/vector both-match 信号。

### API 与前端边界

阶段 14 不改变外部 API schema：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
```

前端暂不修改。原因是阶段 14 的只读审阅需求已经通过 CSV 产物满足；如果后续要做展示，应优先做报告页或只读表格，不重构核心工作台。

架构结论：阶段 14 把质量校准放在 evaluation/reporting 层，而不是把真实模型调用塞进默认链路。deterministic baseline 继续负责稳定回归，真实配置结果必须显式生成并与 baseline 分开记录。

### 阶段 9 完成标准

```text
OpenAICompatibleEmbeddingProvider implemented
.env.example documents real chat/embedding settings
build_vector_index supports provider/model/dimension/API parameters
model config evaluation output exists
search/vector/hybrid/chat/agent APIs remain stable
full tests: 208 passed
```

### 阶段 7 完成标准

```text
docs/agent_design.md 已建立
只读 Agent 工具层已实现
Agent 编排服务已实现
POST /agent/query 已实现
旧 search/vector/hybrid/chat/sources API 不被破坏
Agent 评测脚本和结果文件已生成
前端能最小展示 Agent 回答和工具调用记录
keyword/vector/hybrid/chat/agent 评测通过
全量自动化测试通过
```
