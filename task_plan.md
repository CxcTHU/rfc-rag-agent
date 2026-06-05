# Task Plan: 阶段 4 - 数据采集与来源管理

## Goal
在阶段 3 已完成引用式问答的基础上，建立可靠的资料来源治理链路：公开资料候选 / 题录 / PDF manifest -> source registry -> 来源去重 -> 可信度与权限标记 -> 原文或题录入库 -> 支持重新索引 -> 为后续前端和 Agent 工具调用打基础。

阶段 4 不做 Agent 工具调用、不做复杂 LangGraph workflow、不做前端界面。本阶段优先保证来源记录、去重、权限、状态、导入和重建索引这条最小稳定链路可运行、可测试、可讲清楚。

## Current Phase
Phase 6 complete，阶段 4 文档、Obsidian、本地验证、最终提交、`phase-4-complete` tag 和 GitHub 推送收尾完成；阶段 4 已达到完成标准。最终提交为 `b044459b9b8c2153e9225daa55af5d82cdcdb282`。

## Phases

### Phase 0: 阶段 4 启动与规划文件校准
- [x] 将线程标题确认并修改为 `阶段4-数据采集与来源管理`。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- [x] 阅读 `docs/corpus_pipeline.md`、`docs/source_catalog.md`，确认阶段 1 已形成 CSV、manifest、metadata corpus 三条来源管道。
- [x] 确认阶段 3 已完成，`phase-3-complete` tag 指向 `7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`。
- [x] 确认不移动已有阶段 tag。
- [x] 创建或切换到 `codex/phase-4-source-management` 分支。
- [x] 使用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md` 为阶段 4 工作记忆。
- [x] 梳理现有来源相关实现：`app/services/source_collection.py`、`scripts/collect_sources.py`、`scripts/collect_metadata_corpus.py`、`scripts/import_fulltext.py`、`tests/test_source_collection.py`。
- **Status:** complete

### Phase 1: source registry 数据模型与仓储
- [x] 新增 `sources` 表，作为阶段 4 的 source registry。
- [x] 字段覆盖：`source_id`、title、authors、year、venue、category、doi、url、pdf_url、local_path、source_type、trust_level、access_rights、fulltext_permission、status、document_id、notes、created_at、updated_at。
- [x] 增加归一化字段：`normalized_doi`、`normalized_url`、`normalized_title`，用于去重。
- [x] 在 `app/db/models.py` 中新增 `Source` SQLAlchemy 模型，并与 `Document` 建立可选关联。
- [x] 在 `app/db/repositories.py` 中新增 `SourceCreate` 和 `SourceRepository`，支持创建、更新、按 source_id 查询、按重复键查询、列表、计数。
- [x] 新增 `tests/test_source_repository.py`，覆盖建表、保存、查询、去重键查询和 document 关联。
- [x] 运行本 Phase 相关测试，并更新三份 planning 文件。
- **Status:** complete

### Phase 2: 来源归一化、去重与治理规则
- [x] 新增 `app/services/source_registry.py`，承接来源登记业务。
- [x] 复用并扩展 `normalize_doi()`、`normalize_title()`，新增 URL 归一化。
- [x] 实现 DOI、URL、标题归一化三层去重：DOI 优先，其次 URL，最后标题。
- [x] 实现重复来源合并：保留更完整的题录、摘要、PDF URL、本地路径、分类和发现渠道。
- [x] 实现可信度评级规则，例如高校/期刊/DOI/开放论文优先高可信，普通候选或未知来源为中低可信。
- [x] 实现全文权限字段：`open_access`、`institutional_access`、`metadata_only`、`unknown`。
- [x] 实现来源状态字段：`candidate`、`collected`、`imported`、`duplicate`、`rejected`。
- [x] 新增 `tests/test_source_registry_service.py`，覆盖归一化、去重、合并、可信度、权限和状态判断。
- [x] 运行本 Phase 相关测试，并更新三份 planning 文件。
- **Status:** complete

### Phase 3: 从现有 CSV / manifest / metadata corpus 导入来源
- [x] 支持读取 `data/source_candidates.csv`。
- [x] 支持读取 `data/fulltext_manifest.csv`，兼容其字段少于 `SourceCandidate.CSV_FIELDS` 的情况。
- [x] 支持读取 `data/metadata/rfc_papers_metadata.csv`。
- [x] 支持扫描 `data/imports/metadata_corpus/*.md`，把已生成的题录卡片和 source_id 对齐到 source registry。
- [x] 新增命令行脚本 `scripts/sync_sources.py`，可把上述来源同步到 `sources` 表。
- [x] 脚本默认幂等：重复运行不会重复造来源记录，而是更新已有记录或合并 duplicate。
- [x] 新增脚本测试，覆盖 CSV 导入、manifest 导入、metadata corpus 导入和重复导入。
- [x] 运行本 Phase 相关测试，并更新三份 planning 文件。
- **Status:** complete

### Phase 4: 重新索引入口与来源管理 API
- [x] 实现 source reindex 入口：已登记来源如果有 `local_path`，可重新导入原文；如果只有题录，可重新生成 metadata card 后入库。
- [x] reindex 后更新 `sources.document_id` 和 `sources.status`。
- [x] 必要时触发或提示运行向量索引刷新，保证 documents/chunks 和 chunk_embeddings 可重建。
- [x] 新增 `app/schemas/source.py`，定义 source 列表、详情、同步和 reindex 响应结构。
- [x] 新增 `app/api/sources.py`，提供 `GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`。
- [x] 在 `app/main.py` 注册 sources router。
- [x] 新增 API 测试，覆盖来源列表、详情、同步入口、reindex 成功和资料缺失时的可理解错误。
- [x] 运行本 Phase 相关测试，并更新三份 planning 文件。
- **Status:** complete

### Phase 5: 阶段 4 测试、评测脚本与回归验证
- [x] 汇总并运行 source registry 相关单元测试、脚本测试和 API 测试。
- [x] 保证已有 documents/search/vector/chat 测试不被破坏。
- [x] 补充一个来源管理评测或 smoke 脚本，至少能报告 sources 总数、重复数、权限分布、状态分布、已导入 document 数。
- [x] 运行关键词评测、向量评测、chat 评测，确认阶段 4 不破坏阶段 1-3 链路。
- [x] 阶段收尾前运行 `python -m pytest -q` 全量测试。
- [x] 更新三份 planning 文件，记录所有测试结果和发现的问题。
- **Status:** complete

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag
- [x] 更新 `README.md`：说明阶段 4 已实现 source registry、来源同步、去重、权限、状态、reindex 和 API/脚本用法。
- [x] 更新 `docs/progress.md`：记录阶段 4 完成内容、验证方式、遗留问题、下一阶段任务、面试表达、最终提交号和 tag 名称。
- [x] 更新 `docs/architecture.md`：补充 `sources` 表、source registry service、来源导入、reindex 和 API 数据流。
- [x] 判断并更新 `AGENT.MD`：阶段 4 已改变后续线程默认起点，因此已校准为阶段 5 前端启动建议。
- [x] 更新本地 Obsidian 知识库：阶段 4 页面、首页、阶段索引、分类页和重要知识点。
- [x] 创建最终阶段提交。
- [x] 创建 `phase-4-complete` tag，确保 tag 指向阶段 4 最终功能提交。
- [x] 最终汇报阶段提交号和 tag 名称。
- **Status:** complete

## Key Questions
1. `sources` 表和现有 `documents/chunks` 是什么关系？
   - 初步答案：`sources` 管“资料来源与治理状态”，`documents/chunks` 管“已经入库并可检索的内容”。一个 source 可以尚未入库，也可以通过 `document_id` 指向已导入的 document。
2. 阶段 4 是否真的做网页爬虫？
   - 初步答案：先不做复杂爬虫。现有 `collect_sources.py` 已支持小规模公开学术 API 采集；本阶段优先把这些候选进入 source registry，并把合法边界、去重和重建索引打通。
3. 去重按什么优先级？
   - 初步答案：DOI 最强，URL 次之，归一化标题兜底。重复记录不丢弃关键信息，而是合并更完整字段，并记录 duplicate 关系或 duplicate 状态。
4. 可信度和权限是否是同一个字段？
   - 初步答案：不是。可信度回答“这条来源可靠程度如何”；权限回答“本项目能否保存全文”。二者分开，避免高可信但不能保存全文的论文被误处理。
5. reindex 到底刷新什么？
   - 初步答案：reindex 是把已登记 source 对应的 PDF 或 metadata card 重新导入 `documents/chunks`，必要时再构建 `chunk_embeddings`。阶段 4 先提供入口，不做复杂后台任务。

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 阶段 4 先写 planning 文件再开发 | 用户明确要求先使用 Planning with Files 编写阶段流程文件，避免开发顺序和阶段目标漂移 |
| 使用 `sources` 表作为 source registry | 现有来源散落在 docs、CSV、manifest 和 metadata cards 中，缺少统一查询、去重、状态管理入口 |
| `sources` 不替代 `documents/chunks` | 来源治理和可检索正文是两个层次，分开后更容易支持候选、拒绝、重复、已导入等状态 |
| 去重优先级为 DOI -> URL -> 标题 | DOI 是论文最稳定标识；URL 可覆盖网页或题录页；标题归一化用于没有 DOI/URL 的历史资料 |
| `trust_level` 与 `fulltext_permission` 分开 | 一个来源可能高可信但只能保存题录，也可能开放获取但仍需记录许可；分字段更清楚 |
| 阶段 4 同时提供脚本和轻量 API | 脚本适合批量同步来源，API 为阶段 5 前端和阶段 7 Agent 工具调用打基础 |
| reindex 先做同步入口，不做后台任务队列 | 当前项目仍是 SQLite + 本地脚本阶段，先保持最小可运行链路 |

## Planned File Changes
| Area | Planned Files |
|------|---------------|
| 数据模型与仓储 | `app/db/models.py`, `app/db/repositories.py`, `tests/test_source_repository.py` |
| 来源治理服务 | `app/services/source_registry.py`, `tests/test_source_registry_service.py` |
| 来源同步脚本 | `scripts/sync_sources.py`, `tests/test_sync_sources.py` |
| 来源 API/schema | `app/api/sources.py`, `app/schemas/source.py`, `app/main.py`, `tests/test_sources_api.py` |
| 评测或 smoke 脚本 | `scripts/evaluate_sources.py`, `tests/test_evaluate_sources.py` |
| 文档 | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `docs/corpus_pipeline.md`, `AGENT.MD` if needed |
| Obsidian | `obsidian-vault/阶段/阶段 4 - 数据采集与来源管理.md`, related category pages and knowledge notes |

## Term Explanations
| Term | Explanation |
|------|-------------|
| source registry | 来源登记库。本项目阶段 4 会用 `sources` 表统一管理题录、网页、PDF manifest 和本地文件的来源状态 |
| `sources` 表 | 数据库表，保存每条来源的标题、URL、DOI、权限、可信度、状态和对应 document |
| `Source` | SQLAlchemy 模型，对应 `sources` 表，是阶段 4 来源登记库的数据库表示 |
| `SourceRepository` | 来源仓储层，封装 `sources` 表的保存、查询、更新、重复键查找和计数 |
| `SourceRegistryService` | 来源登记服务，负责把 `SourceCandidate` 转成数据库来源记录，并处理去重、合并和治理规则 |
| DOI | Digital Object Identifier，论文的稳定编号；在本项目用于判断同一论文是否被多个 API 重复发现 |
| URL 归一化 | 把 URL 清洗成更稳定的比较形式，例如去掉末尾斜杠、统一大小写域名，用于去重 |
| 标题归一化 | 把标题去空白、统一大小写后比较，用于没有 DOI/URL 时识别重复来源 |
| trust_level | 可信度评级，表示来源可靠程度，例如高校、期刊官网、DOI 记录通常更可信 |
| fulltext_permission | 全文保存权限，表示本项目能否保存原文，例如 open_access、institutional_access、metadata_only |
| status | 来源状态，表示来源处于候选、已收集、已导入、重复或拒绝等阶段 |
| metadata corpus | 题录元数据语料库，当前对应 `data/metadata/rfc_papers_metadata.csv` 和 `data/imports/metadata_corpus/*.md` |
| manifest | 清单文件，当前主要是 `data/fulltext_manifest.csv`，记录 PDF 来源、本地路径和访问权限 |
| reindex | 重新索引，把已登记来源对应的资料重新导入 documents/chunks，并按需要刷新向量索引 |
| smoke script | 冒烟脚本，用少量检查确认一条链路基本可用，例如统计来源数量、权限分布和已入库数量 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 当前 planning 文件仍是阶段 3 工作记忆 | 1 | 按用户新增要求，先用 Planning with Files 重写为阶段 4 规划文件 |

## Notes
- 本文件由 Planning with Files 流程维护，是阶段 4 的工作记忆。
- 任何阶段开发必须按本文件 Phase 顺序推进。
- 每个 Phase 完成后，必须先更新 `task_plan.md`、`findings.md`、`progress.md`，再输出“Phase 阶段汇报”。
- 阶段 4 的重点是资料来源治理，不是问答生成质量优化。
