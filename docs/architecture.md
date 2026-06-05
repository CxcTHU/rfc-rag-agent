# 架构说明

## 总体流程

```text
资料来源
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
```

## 初始分层

```text
API 层：FastAPI 路由
Schema 层：Pydantic 请求和响应模型
Service 层：导入、切分、检索、问答业务逻辑
DB 层：文档、chunk、问答日志元数据
Model Provider 层：聊天模型和 embedding 模型适配
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
