# 项目进度

## 最新状态：2026-06-05

当前阶段：阶段 2，Embedding 与向量检索已完成。下一步准备进入阶段 3：引用式问答。

当前关键证据：

- `task_plan.md` 当前阶段为 `Stage 2 complete`。
- `POST /search/vector` 已实现。
- `scripts/build_vector_index.py` 已实现。
- `scripts/evaluate_vector_search.py` 已实现。
- `data/evaluation/vector_results.csv` 已生成。
- 向量检索评测：11/15 通过。
- 关键词 baseline：15/15 通过。
- 全量测试：63 个测试通过。

下一步：

- 新开或切换到阶段 3 分支 `codex/phase-3-cited-chat`。
- 实现引用式问答链路：问题 -> 检索 chunks -> 组织上下文 -> 生成回答 -> 返回来源。
- 阶段 3 不做 Agent 工具调用，先保证回答基于资料、能引用来源、资料不足时能拒答。

## 2026-06-04

当时阶段：阶段 1，本地资料导入与关键词检索已完成，并已合并到 `main`。下一步准备进入阶段 2：Embedding 与向量检索。

已完成：

- 明确项目主题：面向水利工程堆石混凝土技术的 RAG 问答 Agent。
- 编写项目指南 `AGENT.MD`。
- 创建初始项目目录。
- 准备连接 GitHub 仓库。
- 创建阶段 0 开发分支 `codex/phase-0-health-api`。
- 建立 FastAPI 应用入口 `app/main.py`。
- 实现健康检查接口 `GET /health`。
- 建立基础配置读取 `app/core/config.py`。
- 增加健康检查响应模型 `app/schemas/health.py`。
- 增加最小接口测试 `tests/test_health.py`。
- 增加项目依赖与测试配置 `pyproject.toml`。
- 在 `AGENT.MD` 中补充 Obsidian 知识库维护规则。
- 创建 Obsidian 知识库 `obsidian-vault/`。
- 为阶段 0 沉淀知识点笔记，并用双链连接阶段页与分类页。
- 更新 `AGENT.MD` 的协作与教学规则，要求新名词首次出现时结合本项目解释，并按“是什么 -> 在本项目哪里出现 -> 有什么作用 -> 面试怎么说”的顺序沉淀。
- 在 `AGENT.MD` 中补充本地 Quivr 项目作为 RAG 工程拆分参考，明确本项目学习其模块边界、数据流、配置方式和测试思路，但不直接复制代码。
- 增加 Obsidian 知识点 `obsidian-vault/知识点/新词解释机制.md`，并链接到阶段 0 与项目方法论分类。
- 重新阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、主要代码文件和测试文件，确认当前仍处于阶段 0 完成、准备进入阶段 1 的状态。

验证结果：

- `python -m pytest`：1 个测试通过。
- 本地服务验证：`GET http://127.0.0.1:8000/health` 返回 `{"status":"ok","service":"RFC-RAG-Agent","environment":"development"}`。
- 重新运行 `python -m pytest`：1 个测试通过。
- Git 当前分支为 `codex/phase-0-health-api`；更新前工作区干净，本次仅修改 `docs/progress.md`。
- 已确认本地参考项目 `G:\Codex\program\quivr` 存在，后续涉及架构、导入、检索、问答或评测设计时可按 `AGENT.MD` 规则参考其工程拆分思路。

阶段 0 知识点：

- FastAPI 用来声明 API 应用和路由。
- Pydantic schema 用来约束接口返回结构，避免返回格式随意变化。
- 配置读取集中放在 `app/core/config.py`，避免把环境变量散落在业务代码里。
- 测试使用 `TestClient` 模拟 HTTP 请求，能在不启动真实端口的情况下验证接口行为。
- 健康检查接口是服务可观测性的起点，后续可扩展为数据库、向量库和模型服务状态检查。

Obsidian 知识库已记录：

- `obsidian-vault/阶段/阶段 0 - FastAPI 工程底座.md`
- `obsidian-vault/知识点/FastAPI 应用入口与工厂函数.md`
- `obsidian-vault/知识点/API 路由分层.md`
- `obsidian-vault/知识点/健康检查接口.md`
- `obsidian-vault/知识点/Pydantic 响应模型.md`
- `obsidian-vault/知识点/Pydantic Settings 配置读取.md`
- `obsidian-vault/知识点/pytest 与 TestClient.md`
- `obsidian-vault/知识点/pyproject.toml 项目依赖管理.md`
- `obsidian-vault/知识点/uvicorn 与 ASGI 服务.md`
- `obsidian-vault/知识点/阶段分支开发.md`
- `obsidian-vault/知识点/Obsidian 双链知识库.md`
- `obsidian-vault/知识点/新词解释机制.md`

当前状态判断：

- 阶段 0 的 FastAPI 工程底座已经完成并通过测试。
- 最新项目规则强调“边做边讲清楚”，后续新增 REST、ORM、chunk、embedding、rerank 等概念时，需要及时解释并判断是否沉淀到 Obsidian。
- 阶段 1 应优先打通本地资料链路：Markdown/TXT 导入、文本清洗、chunk 切分、SQLite 保存和关键词检索。
- 阶段 1 设计时可以参考 Quivr 的 storage、processor、splitter、配置对象和测试组织方式，但本项目要保持简化，聚焦堆石混凝土资料与引用溯源。

遗留问题：

- `AGENT.MD` 的“当前推荐的第一步”曾停留在阶段 0 初始化任务；已在 2026-06-05 阶段 1 收尾时校准为阶段 2 启动建议。
- `AGENT.MD` 中检索策略部分曾有一处阶段表述需要校准；已在 2026-06-05 修正为阶段 1 先做关键词检索、阶段 2 再做向量检索。

依赖说明：

- `pyproject.toml` 中的 `httpx2>=2.3.0` 不是拼写错误；在当前安装到的 Starlette 新版分支里，它是 `TestClient` 优先使用的测试依赖，当前保留该写法。

面试表达：

```text
阶段 0 我没有直接接入大模型，而是先搭建 FastAPI 工程底座。
我把应用入口、路由、配置和响应模型分开，保证后续 documents、search、chat 等模块可以按同样结构扩展。
我实现了 /health 接口，并用自动化测试验证 HTTP 状态码和 JSON 返回结构。
这样可以证明服务可启动、接口可访问，也为后续 CI、部署和监控打基础。
```

下一步：

- 根据 `docs/architecture.md` 中的阶段 1 总体框架，先实现 SQLite 数据库层。
- 设计并落地 `documents` 与 `chunks` 两张表。
- 实现 Markdown/TXT 导入、文本清洗和 chunk 切分。
- 实现 `POST /documents/import`、`GET /documents` 和 `POST /search`。
- 完成关键词检索并补充最小自动化测试。

## 2026-06-04 阶段 1 启动记录

当前分支：`codex/phase-1-document-ingestion`

已完成：

- 正式进入阶段 1：本地资料导入与关键词检索。
- 按照 `AGENT.MD` 的要求重新确认阶段 1 目标：先打通本地资料链路，不接大模型，不接向量库。
- 参考本地 Quivr 项目的 `storage / processor / splitter` 模块边界，确定本项目阶段 1 只借鉴其工程拆分思路，不复制代码。
- 在 `docs/architecture.md` 中新增“阶段 1 总体框架”，明确数据流、目录规划、数据库表、API 草案、关键词检索策略和测试顺序。
- 增加 `SQLAlchemy` 依赖，用于 SQLite 数据库建模和读写。
- 新增 `app/db/session.py`，集中创建数据库连接、数据库会话和建表入口。
- 新增 `app/db/models.py`，定义 `documents` 和 `chunks` 两张表。
- 新增 `tests/test_db_models.py`，验证数据库表能创建，并能保存一篇资料及其 chunk。
- 新增 `app/services/ingestion/parser.py`，支持读取 Markdown/TXT，并从 Markdown 一级或多级标题中推断资料标题。
- 新增 `app/services/ingestion/cleaner.py`，清理 BOM、空字符、换行差异、多余空白和连续空行。
- 新增 `app/services/ingestion/splitter.py`，把长文本切成带 `chunk_index`、`char_count`、`heading_path`、`start_char`、`end_char` 的 chunk。
- 新增 `tests/test_ingestion_parser.py`、`tests/test_ingestion_cleaner.py`、`tests/test_ingestion_splitter.py`，分别验证解析、清洗和切分逻辑。
- 新增 `app/db/repositories.py`，封装 `documents` 和 `chunks` 的保存、查询和 chunk 计数逻辑。
- 新增 `app/services/ingestion/loader.py`，负责计算文件 hash，并把原始文件保存到 raw 目录。
- 新增 `app/services/ingestion/service.py`，把 parser、cleaner、splitter、loader 和 repository 串成完整导入链路。
- 新增 `tests/test_repositories.py`，验证 repository 可以保存和查询资料。
- 新增 `tests/test_ingestion_service.py`，验证 Markdown 文件能完成导入、切分、保存，重复文件不会重复入库，空文件会被拒绝。
- 新增 `python-multipart` 依赖，用于 FastAPI 接收上传文件。
- 新增配置项 `RAW_DATA_DIR`，用于控制原始资料保存目录。
- 新增 `app/schemas/document.py`，定义文档导入和文档列表接口的响应结构。
- 新增 `app/api/documents.py`，实现 `POST /documents/import` 和 `GET /documents`。
- 更新 `app/main.py`，注册 documents 路由，并在应用启动时自动创建数据库表。
- 新增 `tests/test_documents_api.py`，验证上传 Markdown 可完成导入，`GET /documents` 可返回文档列表，不支持的文件类型会返回 400。
- 在 `pyproject.toml` 中显式声明只打包 `app` 包，避免本地运行目录 `data/` 被 setuptools 误识别为顶层包。
- 新增 `app/services/retrieval/keyword_search.py`，实现阶段 1 的关键词检索服务。
- 新增 `app/schemas/search.py`，定义搜索请求和搜索结果响应结构。
- 新增 `app/api/search.py`，实现 `POST /search`。
- 更新 `app/main.py`，注册 search 路由。
- 新增 `tests/test_keyword_search.py`，验证关键词检索能返回命中的 chunk，并过滤无关 chunk。
- 新增 `tests/test_search_api.py`，验证完整 API 流程：上传 Markdown 后，可以通过 `POST /search` 搜到相关片段。
- 搜索结果已包含 `document_title`、`source_path`、`file_name`、`chunk_index`、`content` 和 `score`，满足阶段 1 对“来源、标题和片段”的基本要求。
- 新增 `GET /documents/{document_id}/chunks`，支持按资料编号查看该资料切出的全部 chunk。
- 新增 `tests/test_documents_api.py` 对 chunk 查看接口的正常返回和 404 场景测试。

阶段 1 设计结论：

- 本阶段只支持 Markdown/TXT。
- 原始文件保存到 `data/raw/`。
- 解析、清洗、切分逻辑放到 `app/services/ingestion/`。
- 数据库存储放到 `app/db/`，先落地 `documents` 和 `chunks`。
- 检索放到 `app/services/retrieval/keyword_search.py`，先做可解释的关键词检索。
- API 层新增 `documents.py` 和 `search.py`，保持与阶段 0 的路由分层一致。

下一步：

- 用 5 到 10 篇真实 Markdown/TXT 堆石混凝土资料做本地试导入。
- 手动验证关键词如“堆石混凝土”“自密实混凝土”“施工质量”能返回合理片段。
- 根据真实资料效果微调 chunk_size、chunk_overlap 和关键词评分规则。

验证结果：

- `python -m pytest`：21 个测试通过。

## 2026-06-04 阶段 1 真实资料试导入记录

已完成：

- 使用公开学术页面、高校页面、期刊页面和开放获取论文，整理 10 条堆石混凝土资料卡到 `data/imports/rfc_seed/`。
- 用户补充确认 CNKI 摘要页为《堆石混凝土及堆石混凝土大坝》的主来源入口，已更新 `rfc_seed_001` 资料卡和 `docs/data_sources.md`。
- 通过本地导入链路写入 SQLite，当前资料库包含 10 篇 documents 和 17 个 chunks。
- 搜索校准覆盖关键词：金峰、堆石混凝土、自密实混凝土、施工质量、填充密实性、水化热、低碳筑坝、rock-filled concrete。
- 校准结果显示：开篇论文、施工方法专利、填充能力研究、绝热温升研究和 2023 年综述能被相关关键词召回。

设计说明：

- 本批资料只保存题录、公开摘要转述、检索关键词和来源链接，不保存受版权限制全文。
- CNKI 的 `kcms2/article/abstract?v=...` 链接可能包含临时参数，因此同时保留 ResearchGate、期刊页面或高校页面作为辅助线索。
- 现阶段资料卡中的题名、作者和来源也会进入 chunk 正文，便于关键词检索；后续阶段可以把这些信息拆成 metadata 字段，提高正文检索的纯净度。

验证结果：

- 本地数据库检查：10 篇 documents，17 个 chunks。
- 《堆石混凝土及堆石混凝土大坝》的 `source_path` 已更新为用户提供的 CNKI 摘要页。

## 2026-06-04 阶段 1 chunk 检查接口记录

已完成：

- 在 `app/db/repositories.py` 中增加按 `document_id` 查询文档和 chunk 的方法。
- 在 `app/schemas/document.py` 中增加 chunk 查看接口的响应结构。
- 在 `app/api/documents.py` 中实现 `GET /documents/{document_id}/chunks`。
- 在 `tests/test_documents_api.py` 中增加接口测试，覆盖正常查看 chunk 和文档不存在返回 404。

设计说明：

- 该接口用于提升阶段 1 的可观测性，方便直接检查真实资料被切分后的内容是否合理。
- API 层仍通过 repository 读取数据库，保持 API、schema、database 的分层清晰。

验证结果：

- `python -m pytest tests\test_documents_api.py`：4 个测试通过。

## 2026-06-04 阶段 1 splitter 真实资料微调记录

已完成：

- 检查 10 条真实堆石混凝土资料卡生成的 chunk，发现旧 splitter 会把 `source_id`、URL、`copyright_note` 等资料卡元信息切进正文。
- 发现旧 overlap 可能让新 chunk 从 URL、英文单词或元信息字段中间开始，影响 chunk 可读性和检索结果展示。
- 发现旧 `heading_path` 按 chunk 结束位置附近的标题计算，容易显示成 chunk 内最后一个标题，而不是 chunk 开始处所属标题。
- 更新 `app/services/ingestion/splitter.py`：
  - 自动跳过 Markdown 资料卡开头的元信息块。
  - 新 chunk 起点优先贴近段落、换行或句号等自然边界。
  - `heading_path` 改为按 chunk 开始位置计算。
- 更新 `tests/test_ingestion_splitter.py`，新增元信息跳过和自然边界起点测试。
- 使用新 splitter 重新切分 `data/imports/rfc_seed/` 下的 10 条资料卡，并刷新本地 SQLite 中的 chunks。

设计说明：

- 当前导入的是摘要型资料卡，每条资料卡正文大多在 500 到 800 字之间，因此重切后每篇资料保留 1 个 chunk 更合理。
- 这次不是减少知识量，而是去掉检索噪声，避免把来源登记字段当作知识正文。
- 后续导入长论文、长报告或规范时，splitter 仍会按 `chunk_size` 和自然边界切成多个 chunk。

校准结果：

- 数据库当前为 10 篇 documents，10 个 chunks。
- 搜索“堆石混凝土”时，《堆石混凝土及堆石混凝土大坝》排在前列。
- 搜索“水化热”时，《堆石混凝土绝热温升性能初步研究》排在前列。
- 搜索“填充密实性”时，能召回自密实混凝土充填试验和流动模拟相关资料。

验证结果：

- `python -m pytest tests\test_ingestion_splitter.py -q`：6 个测试通过。
- `python -m pytest`：25 个测试通过。

## 2026-06-04 阶段 1 论文原文导入记录

已完成：

- 新增 `pypdf` 依赖，用于抽取 PDF 文字层。
- 更新 `app/services/ingestion/parser.py`，支持导入 `.pdf` 文件。
- PDF 解析会按页加入 `## Page N` 标记，方便后续检查 chunk 来源页。
- 更新 `tests/test_ingestion_parser.py`，新增 PDF 文字抽取测试。
- 更新 `tests/test_documents_api.py`，将不支持格式测试从 PDF 改为 DOCX。
- 更新 `app/services/ingestion/service.py`，支持传入 `source_type`，用于标记 `open_access_pdf`。
- 更新 `tests/test_ingestion_service.py`，验证自定义来源类型可以写入数据库。
- 新增 `data/fulltext_manifest.csv`，记录 PDF 原文的标题、作者、年份、分类、访问权限、许可备注、URL、PDF URL 和本地文件名。
- 新增 `docs/source_catalog.md`，建立来源分类目录和 CNKI / 机构访问优先下载清单。
- 更新 `.gitignore`，忽略 `data/fulltext/`，避免将论文全文提交到 GitHub。

本次已下载开放全文 PDF：

- `Research on Rock-Filled Concrete Dam`
- `Lattice Boltzmann-Discrete Element Modeling Simulation of SCC Flowing Process for Rock-Filled Concrete`
- `Experimental Research on the Properties of Rock-Filled Concrete`
- `Filling Capacity Evaluation of Self-Compacting Concrete in Rock-Filled Concrete`
- `A Brief Review of Rock-Filled Concrete Dams and Prospects for Next-Generation Concrete Dam Construction Technology`
- `A Mesoscale Comparative Analysis of the Elastic Modulus in Rock-Filled Concrete for Structural Applications`
- `A Comprehensive Literature Review on the Elastic Modulus of Rock-filled Concrete`
- `Seismic Behavior of Rock-Filled Concrete Dam Compared with Conventional Vibrating Concrete Dam Using Finite Element Method`
- `3D mesoscopic numerical investigation on the uniaxial compressive behavior of rock-filled concrete with different ITZ and aggregate properties`
- `Full-Scale micromechanical simulation of rock-filled concretes using Peridynamics`

导入结果：

- 当前数据库总计：20 篇 documents，800 个 chunks。
- 资料卡：10 篇 documents，10 个 chunks。
- 开放全文 PDF：10 篇 documents，790 个 chunks。

搜索校准：

- `rock-filled concrete dam review` 能召回 2023 年 Engineering 综述全文。
- `filling capacity` 能召回填充能力相关资料卡和 2020 年 Materials 全文。
- `elastic modulus` 能召回 2024 年 Buildings 和 ETASR 弹性模量论文。
- `seismic behavior` 能召回 2024 年 Infrastructures 地震响应论文。
- `Peridynamics` 能召回 2025 年 Acta Geotechnica 全文。
- `hydration heat` 目前仍需要补充中文温控全文，下一批优先下载《堆石混凝土绝热温升性能初步研究》。

设计说明：

- 开放全文 PDF 可进入本地全文库，但不提交到远程仓库。
- CNKI 机构访问论文只用于本地私有学习和检索，不公开再分发全文。
- 不使用网盘盗版、破解下载、绕过验证码或反爬限制的来源。
- 当前 PDF 解析只支持文字层，不支持扫描版 OCR。

验证结果：

- `python -m pytest tests\test_ingestion_parser.py tests\test_documents_api.py -q`：8 个测试通过。
- `python -m pytest`：27 个测试通过。

## 2026-06-04 阶段 1 CNKI 机构访问原文导入记录

已完成：

- 使用用户已登录的 Chrome / CNKI 页面下载《堆石混凝土及堆石混凝土大坝》PDF。
- 在 `C:\Users\admin\Downloads` 中发现 5 个重复下载文件，保留原下载不动，复制最新文件到 `data/fulltext/cnki_pending/`。
- 复制后的稳定文件名为 `rfc_cnki_2005_jin_an_study_on_rock_fill_concrete_dam.pdf`。
- 检查 PDF 有文字层：共 6 页，前 3 页可抽取 4231 个字符。
- 更新 `data/fulltext_manifest.csv`，新增 `rfc_cnki_001`，来源类型为 `institutional_access_pdf`。
- 更新 `docs/source_catalog.md`，在“已下载机构访问全文”中登记该论文。
- 导入 SQLite，新增 document_id `21`，切分出 11 个 chunks。

校准结果：

- 当前数据库：21 篇 documents，811 个 chunks。
- 搜索“堆石混凝土大坝”可召回 CNKI 原文第 1 页和第 5 页相关 chunk。
- 搜索“新坝型”可召回 CNKI 原文摘要相关 chunk。
- 搜索“自密实混凝土 填充 堆石体”可召回 CNKI 原文中关于 1500 mm 堆石体填充能力、流动距离和施工质量控制的 chunk。

设计说明：

- 该 PDF 来自机构账号授权访问，只用于本地私有检索，不提交到 GitHub，不公开再分发全文。
- Chrome 下载列表中的重复文件暂不删除，避免误删用户原始下载记录。
- 当前 PDF 抽取文本中存在少量 `` 等 PDF 编码符号，后续可在 cleaner 中增加针对 PDF 的符号清洗规则。

## 2026-06-04 阶段 1 语料库自动扩容管道记录

已完成：

- 新增 `app/services/source_collection.py`，封装来源候选的结构、分类、去重、文件名清洗和 PDF 校验逻辑。
- 新增 `scripts/collect_sources.py`，支持从 OpenAlex、Semantic Scholar、Crossref 批量发现堆石混凝土相关论文候选，并可下载开放 PDF。
- 新增 `scripts/import_fulltext.py`，支持从 manifest 和本地目录批量导入 PDF，重复文件会通过 content hash 识别为 duplicate。
- 新增 `scripts/import_zotero.py`，支持 Zotero 本地 API 可用时读取 Zotero 条目和 PDF 附件并导入。
- 新增 `tests/test_source_collection.py`，验证主题分类、DOI 去重和安全文件名生成。
- 新增 `docs/corpus_pipeline.md`，记录学术 API、Zotero、本地 PDF 的自动扩容方式。

验证结果：

- `scripts/import_fulltext.py --manifest data\fulltext_manifest.csv`：已导入 PDF 均识别为 duplicate，没有重复入库。
- `scripts/import_zotero.py --query "rock-filled concrete"`：当前 Zotero 本地 API 不可用，脚本给出可理解提示。
- `python -m pytest`：30 个测试通过。

当前限制：

- 本机直连 OpenAlex、Semantic Scholar、Crossref 时出现 `SSL: UNEXPECTED_EOF_WHILE_READING`，PowerShell 和 Python 都复现。
- 判断为当前网络或代理层中断 HTTPS 连接；API 管道已实现，但需要配置代理或换网络后才能批量拉取候选。
- Zotero 当前未发现本地配置文件，需要先启动 Zotero Desktop 并启用本地 API。

## 2026-06-04 阶段 1 三通道扩容运行记录

用户要求使用三条通道获取资料，并及时反馈问题。

已运行：

- 学术 API 通道：`scripts/collect_sources.py`
- 本地 PDF / manifest 通道：`scripts/import_fulltext.py`
- Zotero 附件通道：`scripts/import_zotero.py`

学术 API 通道结果：

- 查询词：`rock-filled concrete`、`rock-filled concrete dam`、`self-compacting concrete rock-filled concrete`。
- OpenAlex 和 Crossref 成功返回候选。
- Semantic Scholar 返回 `HTTP 429`，表示当前请求被限流，后续需要降低频率或配置 API key。
- `data/source_candidates.csv` 当前记录 40 条候选。
- 其中 4 条包含 PDF URL，但本轮自动下载均失败：
  - MDPI `/pdf` 链接返回 403；该类链接后续应转换为 `mdpi-res.com` 静态 PDF 地址。
  - Springer 部分链接返回 HTML，不是直接 PDF，可能是受限或书籍资源。
  - EasyChair 预印本链接返回 404。
- 候选清单中出现相邻但不完全相关主题，例如 `concrete-faced rock-fill dam`，后续应增加 RFC 相关性过滤。

本地 PDF / manifest 通道结果：

- 扫描 `data/fulltext_manifest.csv`、`data/source_candidates.csv`、`data/fulltext/open_access/`、`data/fulltext/cnki_pending/`、`data/fulltext/open_access_auto/`。
- 已存在 PDF 均识别为 `duplicate`，没有重复入库。
- 数据库保持 21 篇 documents，811 个 chunks。

Zotero 通道结果：

- Zotero 本地 API 当前不可用。
- `zotero.py status --json` 显示未发现 Zotero profile / prefs file，`api_running=false`。
- `scripts/import_zotero.py` 给出提示：需要先启动 Zotero Desktop 并启用本地 API。

下一步改进：

- 为 `collect_sources.py` 增加更严格的堆石混凝土相关性过滤，排除混凝土面板堆石坝等相邻主题。
- 为 Semantic Scholar 增加 API key 支持和退避重试。
- 为 MDPI 链接增加 `/pdf` 到 `mdpi-res.com` 静态 PDF 的转换规则。
- 启动 Zotero Desktop 后重跑 Zotero 通道。

## 2026-06-04 阶段 1 题录优先语料库扩容记录

用户调整方向：当前不再需要更多论文全文，优先从 Google Scholar、CNKI 等大型学术入口及开放学术 API 获取可直接获得的题名、作者、期刊、摘要、关键词、DOI 和链接等题录语料，追求数量更大。

设计判断：
- 不把 Google Scholar 页面硬爬作为主链路，因为 Google Scholar 没有官方公开批量 API，直接抓页面容易触发验证码，且摘要字段不稳定。
- 不把 CNKI 全文批量抓取作为主链路，因为机构账号授权和网站访问边界需要保留；当前优先支持 CNKI 导出的题录/摘要文件导入。
- 主链路改为 `metadata-first`：先用 OpenAlex、Crossref、Semantic Scholar 等来源扩大题录覆盖面，再把高价值记录或已授权全文逐步补入。

已完成：
- 扩展 `app/services/source_collection.py` 的 `SourceCandidate`，新增 `abstract`、`keywords`、`language`、`citation_count` 字段。
- 修正来源过滤中的中文关键词乱码，使 `堆石混凝土`、`自密实堆石混凝土`、`混凝土面板堆石坝` 等中文判断可用。
- 新增 OpenAlex 摘要还原、Crossref/Semantic Scholar 摘要去标签、语言推断、JSONL 输出和题录 Markdown 卡片生成能力。
- 更新 `scripts/collect_sources.py`，使学术 API 采集从“PDF 候选优先”升级为“题录元数据优先，PDF 可选下载”。
- 新增 `scripts/collect_metadata_corpus.py`，支持：
  - 从 OpenAlex、Semantic Scholar、Crossref 批量采集题录元数据。
  - 跳过某个 API，例如 `--skip-semantic-scholar`。
  - 合并 CNKI、Google Scholar 辅助工具、EndNote、Zotero 或 Publish or Perish 导出的 CSV/TSV/RIS/EndNote 文本文件。
  - 生成 `data/metadata/rfc_papers_metadata.csv`、`data/metadata/rfc_papers_metadata.jsonl` 和 `data/imports/metadata_corpus/*.md`。
  - 将题录卡片以 `metadata_record` 类型导入 SQLite。
- 增加题录导入去重保护：重新生成卡片时，若数据库已存在相同 `metadata_record` 的题名或来源路径，则跳过，避免重复刷屏。

本轮运行命令：

```powershell
.\.venv\Scripts\python.exe scripts\collect_metadata_corpus.py `
  --skip-semantic-scholar `
  --query "rock-filled concrete" `
  --query "rock filled concrete" `
  --query "rock-fill concrete dam" `
  --query "self-compacting rock-filled concrete" `
  --query "self-compacting concrete prepacked rock" `
  --query "堆石混凝土" `
  --query "自密实堆石混凝土" `
  --query "金峰 堆石混凝土" `
  --limit 100 `
  --max-records 300 `
  --import-to-db
```

运行结果：
- OpenAlex + Crossref 共返回 562 条原始候选。
- RFC 相关性过滤后保留 116 条题录。
- 69 条含公开摘要。
- 生成 116 个 Markdown 题录卡片。
- 当前 SQLite：136 篇 documents、997 个 chunks。
- 来源类型分布：`local_file=10`、`open_access_pdf=10`、`institutional_access_pdf=1`、`metadata_record=115`。
- `data/metadata/rfc_papers_metadata.csv` 来源分布：OpenAlex 52 条、OpenAlex+Crossref 44 条、Crossref 20 条。

检索校准：
- `filling capacity` 可以命中填充能力相关题录、资料卡和 PDF chunk。
- `temperature rock-filled concrete` 可以命中温度场、绝热温升、施工参数影响等题录和全文片段。
- `Quality Control Instrumentation` 可以命中 RFC 大坝质量控制相关题录章节。
- 中文 `施工质量` 和 `堆石混凝土` 可以命中 CNKI 原文、早期资料卡和相关题录。

暴露问题：
- Semantic Scholar 未配置 API key 时容易返回 `HTTP 429`，当前用 `--skip-semantic-scholar` 保证批量运行速度。
- Crossref 的 `select` 字段不支持 `language`，已去掉该字段并完成补跑。
- 有 1 个题名对应两个 DOI，文件名已改为包含 `source_id`，避免卡片文件覆盖；数据库检索层仍按题名跳过重复显示。
- 当前 `metadata_record` 作为 Markdown 卡片进入 `documents/chunks`，这是阶段 1 的最小实现；后续阶段 4 更适合新增独立 `sources` 或 `papers` 表。

验证结果：
- `python -m pytest tests\test_source_collection.py -q`：9 个测试通过。
- `python -m pytest`：36 个测试通过。

## 2026-06-04 阶段 1 关键词检索评测与微调记录

用户要求：
- 建立 `data/evaluation/keyword_queries.csv`，记录问题、关键词、期望命中文档和备注。
- 编写 `scripts/evaluate_keyword_search.py`，自动运行关键词检索并输出命中结果。
- 根据结果微调关键词检索，重点检查中文、英文、同义词、标题加分和 `metadata_record` 是否过度刷屏。

已完成：
- 新增 `data/evaluation/keyword_queries.csv`，包含 15 个阶段 1 代表性问题，覆盖：
  - 施工质量 / 质量控制
  - 填充能力
  - 温升 / 水化热 / 温控
  - 弹性模量
  - 抗震 / seismic
  - 综述 / next generation
  - 细观 / 数值模拟
  - 冷缝 / 剪切
  - Peridynamics
  - 施工信息管理
  - 密实度检测
  - 坝型设计
  - 再生骨料
- 新增 `scripts/evaluate_keyword_search.py`：
  - 读取评测 CSV。
  - 调用 `KeywordSearchService`。
  - 判断期望题名、期望内容词和期望来源类型是否命中。
  - 输出 `data/evaluation/keyword_results.csv`。
  - 汇总每条查询的 pass/fail、hit_rank、hit_title、hit_source_type、metadata_ratio。
- 初次评测结果：11/15 通过。
- 失败集中在：
  - `弹性模量` 没有稳定召回 `elastic modulus`。
  - `细观 / 数值 / 模拟` 没有稳定召回 `mesoscopic / simulation`。
  - `peridynamics` 被 `rock-filled concrete / concrete` 等泛词淹没。
  - `quality control instrumentation RFC dam` 没有稳定召回质量控制章节。
- 更新 `app/services/retrieval/keyword_search.py`：
  - 增加 `SearchTerm`，让每个查询词带权重和“是否具体词”的标记。
  - 增加中英文同义词扩展，例如：
    - `弹性模量` -> `elastic modulus`
    - `细观` -> `mesoscopic / mesoscale`
    - `施工质量` -> `quality control / construction quality / instrumentation`
    - `温升 / 水化热` -> `temperature / hydration heat / adiabatic temperature rise`
    - `抗震` -> `seismic / earthquake`
  - 降低 `concrete`、`dam`、`rock-filled`、`堆石混凝土` 等领域泛词在多词查询中的权重。
  - 对命中次数做上限裁剪，避免长 PDF 中泛词重复次数过多导致分数虚高。
  - 加入来源均衡：当存在全文或资料卡命中时，`metadata_record` 在 top_k 中最多优先占约 60%，避免题录卡片刷屏。
  - 检索结果新增 `source_type`，便于 API 和评测识别来源类型。
- 更新 `app/schemas/search.py` 和 `app/api/search.py`，让 `POST /search` 返回每条结果的 `source_type`。
- 更新 `tests/test_keyword_search.py`：
  - 验证中文 `弹性模量 堆石混凝土` 可以召回英文 `Elastic Modulus` 题录。
  - 验证 `peridynamics` 这类具体词不会被泛词重复次数淹没。

最终评测结果：
- `scripts/evaluate_keyword_search.py`：15/15 通过。
- `metadata_ratio` 最高控制在 0.50。
- `data/evaluation/keyword_results.csv` 已记录本轮评测结果。

验证结果：
- `python -m pytest tests\test_keyword_search.py tests\test_search_api.py -q`：6 个测试通过。
- `python -m pytest`：38 个测试通过。
- `python -m py_compile scripts\evaluate_keyword_search.py app\services\retrieval\keyword_search.py app\schemas\search.py app\api\search.py`：通过。

面试表达：

```text
阶段 1 不只是实现关键词检索，还建立了一个小型检索评测集。评测集把典型问题、查询词和期望命中文档写成 CSV，再由脚本自动运行检索并输出命中排名和来源类型。根据评测结果，我发现关键词检索容易被领域泛词影响，所以加入了中英文同义词扩展、具体词加权、泛词降权和 metadata_record 来源均衡。最终 15 个代表性问题全部通过，形成了后续向量检索的 baseline。
```

## 2026-06-05 阶段 1 合并与文档校准记录

已完成：

- 将 `codex/phase-1-document-ingestion` 合并到 `main`。
- 推送远程 `origin/main`。
- 校准 `README.md`，明确当前阶段为阶段 1 已完成，并列出 documents/chunks、导入链路、关键词检索、评测集和测试覆盖。
- 校准 `obsidian-vault/阶段索引.md`，将阶段 1 从“计划中”移动到“已完成”，并把阶段 2 标为下一阶段。
- 校准 `obsidian-vault/首页.md`，将当前重点从阶段 0 更新为阶段 1 已完成、阶段 2 下一阶段。
- 校准 `obsidian-vault/阶段/阶段 1 - 本地资料导入与关键词检索.md`，将状态从“待开发”改为“已完成”，并补充完成内容、验证结果、知识点链接和面试表达。
- 校准 `AGENT.MD` 末尾的“当前推荐的第一步”，不再指向阶段 0 初始化，而是指向阶段 2 的 Embedding 与向量检索。
- 校准 `AGENT.MD` 的“检索策略”，修正为阶段 1 关键词检索、阶段 2 embedding 向量检索、后续再做 rerank 和引用式问答。

验证结果：

- 合并前运行 `python -m pytest`：38 个测试通过。

当前文档权威性：

- `docs/progress.md` 是最权威的阶段进度记录。
- `README.md` 是新读者入口。
- `AGENT.MD` 是后续 agent 的工作规则。
- `obsidian-vault/阶段索引.md` 是复习和知识库导航。

下一步：

- 新开阶段 2 分支 `codex/phase-2-vector-search`。
- 设计 embedding 模型选择、向量索引方案、chunk embedding 保存结构和向量检索评测方式。

## 2026-06-05 阶段 2 完成记录：Embedding 与向量检索

当前分支：`codex/phase-2-vector-search`

当前阶段：阶段 2 已完成。下一步准备进入阶段 3：引用式问答。

已完成：

- 使用 `planning-with-files` 生成并维护阶段 2 规划文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- 新增 `docs/stage2_learning_notes.md`，按步骤沉淀阶段 2 学习笔记和面试表达。
- 新增 `app/services/retrieval/embedding.py`：
  - 定义 `EmbeddingProvider` 抽象。
  - 实现 `DeterministicEmbeddingProvider`，用于无 API key 的本地开发和稳定测试。
  - 提供 `create_embedding_provider()`，为后续切换真实 embedding 模型预留入口。
- 新增 `chunk_embeddings` 表：
  - 记录 `chunk_id`、`provider`、`model_name`、`dimension`、`embedding_json`、`content_hash`。
  - 使用 `chunk_id + provider + model_name` 唯一约束避免重复索引。
  - 与 `chunks` 建立关联，删除 chunk 时可级联删除对应 embedding。
- 扩展 `ChunkEmbeddingRepository`：
  - 支持保存、更新、查询、列出和统计 chunk embeddings。
  - 支持 `serialize_embedding()` 和 `deserialize_embedding()`。
  - 支持批量索引时延迟提交，减少大量写入时的数据库提交次数。
- 新增 `VectorIndexService`：
  - 扫描 chunks。
  - 判断已有 embedding 是否过期。
  - 批量调用 embedding provider。
  - 写入或更新 `chunk_embeddings`。
  - 返回 total、indexed、updated、skipped 等构建统计。
- 新增 `scripts/build_vector_index.py`：
  - 支持从命令行构建向量索引。
  - 默认使用 `.env` 中的 `EMBEDDING_PROVIDER`，未配置时使用 deterministic provider。
- 新增 `VectorSearchService`：
  - 把用户问题转成 query embedding。
  - 读取同一 provider/model/dimension 的 chunk embedding。
  - 计算余弦相似度并按 score 排序。
  - 跳过内容 hash 不一致的 stale embedding。
- 扩展 `app/api/search.py`：
  - 保留阶段 1 的 `POST /search` 关键词检索。
  - 新增 `POST /search/vector` 向量检索入口。
- 扩展 `app/schemas/search.py`：
  - 新增 `VectorSearchRequest`。
  - 新增 `VectorSearchResponse`，返回 provider 和 model_name，便于排查当前使用的 embedding 实现。
- 新增 `scripts/evaluate_vector_search.py`：
  - 复用 `data/evaluation/keyword_queries.csv`。
  - 输出 `data/evaluation/vector_results.csv`。
  - 读取 `data/evaluation/keyword_results.csv`，对比关键词 baseline 和向量检索结果。
- 新增和更新自动化测试：
  - `tests/test_embedding_provider.py`
  - `tests/test_db_models.py`
  - `tests/test_repositories.py`
  - `tests/test_vector_index_service.py`
  - `tests/test_vector_search.py`
  - `tests/test_vector_search_api.py`
  - `tests/test_evaluate_vector_search.py`

阶段 2 设计结论：

- 本阶段没有直接接入 FAISS、Chroma 或云端 embedding 模型，而是先用 SQLite + deterministic embedding 跑通最小链路。
- `documents` 和 `chunks` 仍是主数据源，`chunk_embeddings` 是可重建索引数据。
- 向量检索与关键词检索保持并行：
  - `POST /search` 是阶段 1 keyword baseline。
  - `POST /search/vector` 是阶段 2 vector search。
- 评测必须复用同一批问题，避免不同检索方式比较口径不一致。
- 当前 deterministic embedding 只能证明链路和工程边界可运行，不能证明真实语义召回效果已经优于关键词检索。

评测结果：

- `scripts/evaluate_keyword_search.py`：关键词 baseline 15/15 通过。
- `scripts/evaluate_vector_search.py`：向量检索 11/15 通过。
- 向量检索失败样例：
  - `filling_capacity_en`
  - `mesoscopic_modeling`
  - `peridynamics`
  - `construction_management`

验证结果：

- `python -m pytest tests/test_embedding_provider.py -q`：7 个测试通过。
- `python -m pytest tests/test_vector_index_service.py -q`：5 个测试通过。
- `python -m pytest tests/test_vector_search.py tests/test_vector_search_api.py -q`：7 个测试通过。
- `python -m pytest tests/test_evaluate_vector_search.py -q`：3 个测试通过。
- `python scripts/evaluate_vector_search.py`：向量检索 11/15，关键词 baseline 15/15。
- `python -m pytest -q`：63 个测试通过。

已处理问题：

- 写出 `def batched[T]` 后发现该语法只支持 Python 3.12；项目使用 Python 3.11，因此改为 `TypeVar` 写法。
- 首次运行向量评测脚本超时；定位为首次索引构建时逐条 commit 成本高，已改为 batch commit。
- 用户指出“新词解释”规则容易遗漏；已将新词解释写入 `AGENT.MD` 的自检要求、`task_plan.md` 验收项和 `docs/stage2_learning_notes.md`。

遗留问题：

- 当前 deterministic embedding 是稳定测试用实现，不是真实语义模型。
- 向量检索 11/15 弱于关键词 baseline 15/15，说明下一步需要真实 embedding、混合检索或 query expansion。
- 尚未实现引用式回答、上下文组织、拒答机制和聊天模型调用，这些属于阶段 3。
- 尚未接入 FAISS/Chroma/PGVector；当前 SQLite 向量保存适合阶段 2 最小链路和迁移前验证。

面试表达：

```text
阶段 2 我没有直接把文本丢进向量库，而是先把 embedding 模型调用、向量保存、索引构建、向量检索和评测拆成独立模块。

EmbeddingProvider 负责把文本转成向量；chunk_embeddings 表保存每个 chunk 的向量、模型信息、维度和内容 hash；VectorIndexService 负责批量构建索引；VectorSearchService 负责把用户问题向量化并按余弦相似度召回 chunk。API 层只暴露 /search/vector，不直接写检索细节。

为了防止只凭演示判断效果，我复用了阶段 1 的关键词评测集，对关键词 baseline 和向量检索使用同一批问题做对比。当前 deterministic embedding 下向量检索为 11/15，关键词 baseline 为 15/15，这说明工程链路已经打通，但真实语义效果还需要后续接入更好的 embedding 模型或混合检索。
```

下一步：

- 进入阶段 3：引用式问答。
- 先基于 `POST /search/vector` 的返回结果组织上下文。
- 新增聊天模型 provider 抽象。
- 实现 `POST /chat`，返回回答和来源。
- 遇到资料不足时明确拒答，不让模型硬编。
