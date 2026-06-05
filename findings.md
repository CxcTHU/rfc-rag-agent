# Findings & Decisions

## Requirements
- 用户要求本线程设置并执行阶段 4 goal，持续推进到“数据采集与来源管理”完整完成。
- 用户要求首先修改线程名称为 `阶段4-数据采集与来源管理`。
- 用户要求先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 用户要求先根据 AGENT 和项目开发进度，用 Planning with Files 编写本阶段流程文件，再按规划文件开发。
- 用户要求确认阶段 3 已完成，并确认 `phase-3-complete` tag 指向阶段 3 最终功能提交，不移动已有阶段 tag。
- 用户要求目标分支为 `codex/phase-4-source-management`。
- 阶段 4 不做 Agent 工具调用、不做复杂 LangGraph workflow、不做前端界面。
- 阶段 4 核心目标是来源治理：source registry、去重、可信度、权限、状态、导入、reindex、API 或脚本、测试、文档和 Obsidian 收尾。

## Current Project Findings
- 当前线程名称已确认为 `阶段4-数据采集与来源管理`。
- 当前分支为 `codex/phase-4-source-management`。
- 当前 HEAD 为 `70cc39825d71aeb3efd8eea530c0d2c414444725`，提交信息为 `chore: keep obsidian vault local`。
- `phase-3-complete` tag 指向 `7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`，提交信息为 `feat: complete phase 3 cited chat`。
- `phase-3-complete` 之后还有流程/文档性质提交，例如要求阶段完成 tag 和 Obsidian 本地化；按 AGENT 规则不移动已有阶段 tag。
- 阶段 3 已实现：
  - `ChatModelProvider`
  - RAG prompt/context builder
  - `CitationAnswerService`
  - `POST /chat`
  - `qa_logs`
  - chat 评测脚本
  - 全量测试 106 passed 的阶段 3 证据
- 现有数据库主链路是：
  - `documents` 保存已导入资料
  - `chunks` 保存可检索片段
  - `chunk_embeddings` 保存向量
  - `qa_logs` 保存问答日志
- 当前还没有 `sources` 表或统一 source registry。

## Data Source Relationship Findings
- `docs/data_sources.md`
  - 面向人读的来源登记文档。
  - 记录 10 条阶段 1 种子来源。
  - 同时说明全文目录和题录元数据目录的位置。
- `docs/source_catalog.md`
  - 面向全文 PDF 的来源分类目录。
  - 记录 10 条开放全文和 1 条机构访问全文。
  - 强调访问权限、主题分类和本地文件位置。
- `data/fulltext_manifest.csv`
  - 面向脚本的 PDF manifest。
  - 当前字段少于 `SourceCandidate.CSV_FIELDS`，例如缺少 `venue`、`discovered_via`、`abstract`、`keywords`、`language`、`citation_count`。
  - 已记录 `source_id`、title、authors、year、category、source_type、access_rights、license_or_terms、url、pdf_url、local_path、status、notes。
- `data/source_candidates.csv`
  - 由 `scripts/collect_sources.py` 生成。
  - 记录公开学术 API 发现的候选来源。
  - 当前包括 open_access_candidate、metadata、closed 等访问状态。
- `data/metadata/rfc_papers_metadata.csv`
  - 由 `scripts/collect_metadata_corpus.py` 生成。
  - 当前 116 条题录记录，69 条含摘要。
  - 来源包括 OpenAlex、Crossref，后续可合并 Semantic Scholar、CNKI 导出、Google Scholar 辅助工具导出、Zotero/EndNote/RIS 导出。
- `data/imports/metadata_corpus/*.md`
  - 题录记录生成的 Markdown 卡片。
  - 当前通过 ingestion service 以 `metadata_record` 类型导入 `documents/chunks`。
  - 这种方式可检索，但没有独立来源治理表，阶段 4 需要补齐。
- `documents/chunks`
  - 当前是可检索内容库，不是来源登记库。
  - 一个 document 可能来自本地 PDF、开放 PDF、机构访问 PDF或 metadata card。

## Existing Source Code Findings
- `app/services/source_collection.py`
  - 已有 `SourceCandidate` 数据结构和 `CSV_FIELDS`。
  - 已有 DOI 和标题归一化：`normalize_doi()`、`normalize_title()`。
  - 已有候选去重：`dedupe_candidates()`。
  - 已有主题分类、相关性过滤、Markdown 题录卡片生成和 PDF 下载辅助函数。
  - 阶段 4 可复用这些函数，但需要新增数据库持久化和状态治理。
- `scripts/collect_sources.py`
  - 用 OpenAlex、Semantic Scholar、Crossref、Unpaywall 发现候选来源。
  - 当前属于候选采集入口，不是 registry 同步入口。
- `scripts/collect_metadata_corpus.py`
  - 用 metadata-first 方式收集题录并生成 CSV/JSONL/Markdown 卡片。
  - 当前导入数据库时按 `Document.source_type == metadata_record` 和题名/source_path 去重。
  - 阶段 4 应把去重前移到 `sources` 表。
- `scripts/import_fulltext.py`
  - 从 manifest 和目录扫描 PDF，并调用 `IngestionService.import_document()` 入库。
  - 当前通过文件 hash 去重 document，但没有更新统一 source 状态。
- `tests/test_source_collection.py`
  - 已覆盖主题分类、DOI 去重、相关性过滤、MDPI PDF URL 转换、OpenAlex 摘要重建和题录 Markdown。
  - 阶段 4 需要新增 repository、service、script、API 级测试。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 使用 `sources` 表承载 source registry | CSV 和 docs 适合记录，不适合 API 查询、去重和 reindex；数据库表可以成为后续前端和 Agent 的稳定入口 |
| 保留 `SourceCandidate` 作为采集层结构 | 现有采集脚本已围绕它工作，阶段 4 不应重写采集层，而是新增 registry 层承接它 |
| `sources.document_id` 设计为可空 | 允许来源处于 candidate/collected 状态但尚未导入 documents/chunks |
| DOI、URL、标题三层去重 | 覆盖论文、网页、机构题录和无 DOI 资料卡等不同来源形式 |
| `trust_level` 独立于 `access_rights` | 可信度和访问权限是两件事，分开更容易解释和过滤 |
| `fulltext_permission` 独立于 `source_type` | `source_type` 描述来源类别，`fulltext_permission` 描述能否保存全文 |
| `status` 使用固定枚举字符串 | 阶段 4 不引入复杂状态机，先用 candidate/collected/imported/duplicate/rejected 表达最小生命周期 |
| API 和脚本都保留 | 脚本适合批量同步，API 适合阶段 5 前端和阶段 7 Agent 工具调用 |
| reindex 先做同步导入入口 | 当前项目还没有后台任务队列，先保证一条 source 可以重新导入到 documents/chunks |

## Planned File Changes
| Area | Planned Files |
|------|---------------|
| Source DB model | `app/db/models.py`, `app/db/repositories.py`, `tests/test_source_repository.py` |
| Source registry service | `app/services/source_registry.py`, `tests/test_source_registry_service.py` |
| Source sync script | `scripts/sync_sources.py`, `tests/test_sync_sources.py` |
| Source API/schema | `app/api/sources.py`, `app/schemas/source.py`, `app/main.py`, `tests/test_sources_api.py` |
| Source smoke/eval | `scripts/evaluate_sources.py`, `tests/test_evaluate_sources.py` |
| Docs and knowledge base | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `docs/corpus_pipeline.md`, `AGENT.MD`, `obsidian-vault/` |

## Term Explanations
| Term | Explanation |
|------|-------------|
| source registry | 来源登记库。阶段 4 用它统一管理资料候选、题录、PDF manifest 和已导入 document 的关系 |
| `SourceCandidate` | 现有采集层候选结构，在 `app/services/source_collection.py` 中定义；用于表示一条来自学术 API 或 manifest 的来源候选 |
| `sources` | 阶段 4 要新增的数据库表，用于保存来源元数据、去重键、权限、可信度、状态和 document 关联 |
| `Source` | SQLAlchemy 模型，对应 `sources` 表；它把一条来源记录变成数据库中的一行 |
| `SourceRepository` | 来源仓储层，负责读写 `sources` 表，避免 service 或 API 直接拼数据库查询 |
| `SourceRegistryService` | 来源登记服务，位于采集候选和 `sources` 表之间，负责归一化、去重、合并、可信度、权限和状态规则 |
| `sync_sources.py` | 阶段 4 来源同步脚本，把现有 CSV、manifest 和 metadata cards 批量同步到 `sources` 表 |
| `evaluate_sources.py` | 阶段 4 来源登记库评测脚本，统计来源总数、重复合并线索、权限分布、状态分布、可信度分布和已关联 document 数 |
| `SourceReindexResult` | 重新索引结果，包含更新后的 source 和本次 ingestion 返回的 document/chunk 信息 |
| sources API | 阶段 4 新增 API，允许外部查看来源、同步来源和触发重新索引 |
| `documents` | 已导入资料表，保存可检索内容的文档级信息 |
| `chunks` | 资料片段表，保存问答和检索时实际召回的片段 |
| DOI | 论文唯一标识，适合识别 OpenAlex、Crossref、Semantic Scholar 里重复出现的同一论文 |
| manifest | 来源清单文件，本项目当前主要指 `data/fulltext_manifest.csv` |
| metadata corpus | 题录元数据语料库，本项目当前由 `data/metadata/rfc_papers_metadata.csv` 和 metadata cards 组成 |
| access_rights | 访问权限描述，例如 open access、closed、metadata 或 institutional access |
| fulltext_permission | 本项目是否允许保存全文的明确字段，例如 open_access、institutional_access、metadata_only |
| trust_level | 来源可信度评级，用于后续筛选高质量来源 |
| reindex | 重新把来源对应资料导入 documents/chunks，并按需刷新向量索引 |
| idempotent | 幂等，表示同一个同步脚本重复运行不会重复制造相同来源记录 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| planning 文件仍是阶段 3 内容 | 已按 Planning with Files 重新校准为阶段 4 |
| `data/fulltext_manifest.csv` 字段少于 `SourceCandidate.CSV_FIELDS` | 阶段 4 导入逻辑需要兼容缺失字段，不能假设所有 CSV 字段完整 |
| 题录卡片已经进入 `documents/chunks`，但没有统一来源状态 | 阶段 4 通过 `sources.document_id` 和 `status` 把来源治理与已导入内容连接起来 |
| `tests/test_sync_sources.py` 在 session 关闭后访问 SQLAlchemy source 对象属性 | 已在 session 内提前取出断言字段，避免 detached instance |
| 新增 reindex 辅助函数时意外打断 `read_metadata_card()` 的 return 逻辑 | 已补回字段组装和 `return SourceCandidate(...)`，source 管理组合测试恢复通过 |

## Implementation Findings
- Phase 1 已新增 `Source` SQLAlchemy 模型，对应 `sources` 表。
- `sources` 表已覆盖来源登记所需核心字段：来源标识、题名、作者、年份、分类、发现渠道、DOI、URL、PDF URL、摘要、关键词、语言、引用数、来源类型、可信度、访问权限、全文保存权限、状态、本地路径、备注和可选 `document_id`。
- `sources` 表新增 `normalized_doi`、`normalized_url`、`normalized_title` 三个归一化字段，用于阶段 2 去重。
- `Source.document_id` 可为空，支持候选来源先登记，后续导入 `documents/chunks` 后再关联。
- `Document.sources` 和 `Source.document` 已建立关系，可从 source 追溯到已导入 document，也可从 document 查看关联来源。
- `SourceRepository` 已支持 create、update、save/upsert、按 id 查询、按 source_id 查询、按 DOI/URL/title 重复键查询、列表和计数。
- `tests/test_source_repository.py` 已覆盖来源保存、更新、重复键优先级查询、列表/计数和 document 关联。
- Phase 2 已新增 `app/services/source_registry.py`，把 `SourceCandidate` 转换为 `SourceCreate`，并集中计算归一化字段、可信度、权限和状态。
- `normalize_url()` 会统一 scheme/domain、去掉 fragment、去掉 `utm_` 跟踪参数、排序 query 参数，并保留对来源有意义的查询参数。
- `SourceRegistryService.register_candidate()` 支持先按 `source_id` 更新，再按 DOI、URL、标题查重。
- 如果发现重复来源，当前策略是不新增重复行，而是把更完整的字段合并到已有来源，并在 notes 中记录 `merged_duplicate_source_id`。
- `candidate_to_source_create()` 会把 `SourceCandidate` 转成 `SourceCreate`，并处理标题缺失、引用数解析、默认状态和权限。
- `derive_trust_level()` 当前把开放 PDF、机构 PDF、DOI、Crossref/OpenAlex、主要高校/期刊页面识别为高可信；有摘要、期刊或 URL 的普通候选识别为中可信。
- `derive_fulltext_permission()` 当前支持 `open_access`、`institutional_access`、`metadata_only`、`unknown`。
- `derive_status()` 会把 `downloaded`、`saved` 或已有 `local_path` 的来源识别为 `collected`，避免有本地 PDF 仍停留在默认 `candidate`。
- `tests/test_source_registry_service.py` 已覆盖 URL 归一化、候选转换、DOI 去重合并、URL/标题去重、权限/可信度/状态规则。
- Phase 3 已扩展 `source_registry.py`，新增 `read_existing_source_candidates()`、`read_metadata_cards()` 和 `read_metadata_card()`。
- `read_existing_source_candidates()` 可以合并读取 source candidates CSV、fulltext manifest、metadata CSV 和 metadata card 目录。
- `read_metadata_card()` 可以从生成的 Markdown 题录卡片中解析标题、source_id、作者、年份、期刊、分类、发现渠道、DOI、URL、语言、引用数、关键词和摘要。
- Phase 3 已新增 `scripts/sync_sources.py`，默认读取项目现有四类来源文件并同步到 `sources` 表。
- `scripts/sync_sources.py --no-defaults` 可只同步用户显式传入的文件，便于测试和后续批处理。
- `sync_sources()` 当前返回 `SourceRegistrySummary(total, created, updated, duplicates)`。
- 真实项目数据同步结果：输入 283 条来源候选，创建 125 条 `sources` 记录，更新 132 次，合并重复 26 次。
- 同步后本地 `sources` 表分布：status 为 `candidate=8`、`collected=117`；fulltext_permission 为 `institutional_access=2`、`metadata_only=110`、`open_access=10`、`unknown=3`；trust_level 当前为 `high=125`。
- Phase 4 已新增 source reindex 入口。`SourceRegistryService.reindex_source()` 会优先使用已有 `local_path` 导入；如果是 metadata-only 来源且有摘要、关键词、URL 或 DOI，则生成 metadata card 后导入。
- reindex 复用 `IngestionService.import_document()`，因此仍走现有 parser、cleaner、splitter、documents/chunks 入库链路。
- reindex 成功后会更新 `sources.document_id` 和 `sources.status=imported`。
- Phase 4 已新增 `app/schemas/source.py`，定义 source 列表、同步和 reindex 响应结构。
- Phase 4 已新增 `app/api/sources.py`，提供 `GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`。
- `app/main.py` 已注册 sources router。
- `tests/test_sources_api.py` 已覆盖同步、列表、详情、metadata-only reindex 和缺失 source 的 404。
- Phase 5 已新增 `scripts/evaluate_sources.py`，用于输出来源治理 smoke 指标。
- `evaluate_sources.py` 当前统计：sources 总数、已关联 documents 数、notes 中记录的重复合并线索数、status 分布、fulltext_permission 分布、trust_level 分布。
- Phase 5 已新增 `tests/test_evaluate_sources.py`，覆盖指标统计和 CSV 输出。
- 真实项目来源评测输出：`total_sources=125`、`linked_documents=0`、`merged_duplicates=14`、status 为 `candidate=8;collected=117`、fulltext_permission 为 `institutional_access=2;metadata_only=110;open_access=10;unknown=3`、trust 为 `high=125`。
- 阶段 4 全量测试通过：`python -m pytest -q` 为 123 passed。
- 阶段 4 回归评测通过基线：关键词 15/15，向量 11/15，chat 6/6 且 refused=1、citation_failures=0。
- Phase 6 已完成 README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/corpus_pipeline.md` 更新。
- `AGENT.MD` 需要更新，因为阶段 4 改变了后续线程默认起点；当前已校准为阶段 5 前端启动建议。
- Obsidian 本地知识库已更新首页、阶段索引、阶段 4 页面、分类页和阶段 4 知识点。该目录当前按项目规则保持本地化，不作为普通 Git 跟踪内容提交。
- Phase 6 收尾验证通过：全量测试 123 passed，关键词 15/15，向量 11/15，chat 6/6，来源评测 `total_sources=125`。
- 下一步应创建阶段最终提交并创建 `phase-4-complete` tag；最终提交号和 tag 指向由最终汇报给出。

## Resources
- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/corpus_pipeline.md`
- `docs/source_catalog.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `app/services/source_collection.py`
- `scripts/collect_sources.py`
- `scripts/collect_metadata_corpus.py`
- `scripts/import_fulltext.py`
- `data/fulltext_manifest.csv`
- `data/source_candidates.csv`
- `data/metadata/rfc_papers_metadata.csv`
- `data/imports/metadata_corpus/`
- `tests/test_source_collection.py`

## Visual/Browser Findings
- 未使用浏览器或视觉检查。
