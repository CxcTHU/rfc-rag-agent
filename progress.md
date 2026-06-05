# Progress Log

## Session: 2026-06-05

### Phase 0: 阶段 4 启动与规划文件校准
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 使用 Codex 线程工具确认并重设当前线程标题为 `阶段4-数据采集与来源管理`。
  - 检查当前 goal，确认本线程需要持续推进阶段 4 到完整完成。
  - 确认当前分支为 `codex/phase-4-source-management`。
  - 确认当前工作区干净。
  - 确认 `phase-3-complete` tag 指向 `7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`，且不移动该 tag。
  - 确认当前 HEAD 为 `70cc39825d71aeb3efd8eea530c0d2c414444725`，阶段 4 分支从阶段 3 完成后的文档/流程状态切出。
  - 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
  - 阅读 `docs/corpus_pipeline.md` 和 `docs/source_catalog.md`，确认已有公开资料候选、全文 manifest 和 metadata-first 管道。
  - 按 Planning with Files 要求读取旧 `task_plan.md`、`findings.md`、`progress.md`。
  - 运行 Planning with Files session catchup 脚本，未发现需要同步的额外上下文。
  - 阅读 `app/db/models.py`、`app/db/repositories.py`、`app/services/source_collection.py`、`scripts/import_fulltext.py`、`scripts/collect_metadata_corpus.py`、`app/main.py` 和 `tests/test_source_collection.py`。
  - 查看 `data/fulltext_manifest.csv`、`data/source_candidates.csv`、`data/metadata/rfc_papers_metadata.csv` 的表头与样例行。
  - 将阶段 3 planning 文件重写为阶段 4 planning 文件。
- Files created/modified:
  - `task_plan.md` rewritten for Stage 4
  - `findings.md` rewritten for Stage 4
  - `progress.md` rewritten for Stage 4

### Current Evidence
| Item | Evidence | Status |
|------|----------|--------|
| Thread title | `阶段4-数据采集与来源管理` | pass |
| Branch | `codex/phase-4-source-management` | pass |
| Phase 3 tag | `phase-3-complete -> 7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954` | pass |
| Existing tests from phase 3 | `docs/progress.md` records `106 passed` | historical pass |
| Source code baseline | `source_collection.py`, `collect_metadata_corpus.py`, `import_fulltext.py` inspected | pass |
| Planning with Files | `task_plan.md`, `findings.md`, `progress.md` now describe Stage 4 | pass |

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| phase 0 git status check | branch/status inspection | on phase 4 branch, no user changes overwritten | `codex/phase-4-source-management` | pass |
| phase 3 tag check | tag inspection | `phase-3-complete` remains on phase 3 final functional commit | `7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954` | pass |
| planning file calibration | inspect rewritten files | reflect Stage 4 goal, phases, decisions and progress | Stage 4 files written | pass |
| source repository tests | `python -m pytest tests\test_source_repository.py -q` | pass | 4 passed | pass |
| source db compile | `python -m py_compile app\db\models.py app\db\repositories.py tests\test_source_repository.py` | pass | pass | pass |
| existing db/repository regression | `python -m pytest tests\test_db_models.py tests\test_repositories.py -q` | pass | 5 passed | pass |
| source registry service first run | `python -m pytest tests\test_source_registry_service.py -q` | pass | 1 failed, 4 passed | fail |
| source registry service after fix | `python -m pytest tests\test_source_registry_service.py tests\test_source_repository.py -q` | pass | 9 passed | pass |
| source registry compile | `python -m py_compile app\services\source_registry.py tests\test_source_registry_service.py` | pass | pass | pass |
| source collection regression | `python -m pytest tests\test_source_collection.py -q` | pass | 9 passed | pass |
| sync sources first run | `python -m pytest tests\test_sync_sources.py -q` | pass | 1 failed, 2 passed | fail |
| sync sources after fix | `python -m pytest tests\test_sync_sources.py tests\test_source_registry_service.py -q` | pass | 8 passed | pass |
| sync sources compile | `python -m py_compile app\services\source_registry.py scripts\sync_sources.py tests\test_sync_sources.py` | pass | pass | pass |
| phase 3 source tests | `python -m pytest tests\test_sync_sources.py tests\test_source_registry_service.py tests\test_source_repository.py -q` | pass | 12 passed | pass |
| real source sync smoke | `python scripts\sync_sources.py` | sync existing project source files | total=283, created=125, updated=132, duplicates=26 | pass |
| real sources distribution | SQLite query over `sources` | source counts and distributions available | sources=125; status candidate=8/collected=117; permission institutional_access=2/metadata_only=110/open_access=10/unknown=3 | pass |
| sources API tests | `python -m pytest tests\test_sources_api.py -q` | pass | 3 passed | pass |
| source management combined tests | `python -m pytest tests\test_source_repository.py tests\test_source_registry_service.py tests\test_sync_sources.py tests\test_sources_api.py -q` | pass | 15 passed | pass |
| sources API compile | `python -m py_compile app\api\sources.py app\schemas\source.py app\services\source_registry.py app\main.py tests\test_sources_api.py tests\test_sync_sources.py` | pass | pass | pass |
| documents/chat API regression | `python -m pytest tests\test_documents_api.py tests\test_chat_api.py -q` | pass | 9 passed | pass |
| source evaluation tests | `python -m pytest tests\test_evaluate_sources.py -q` | pass | 2 passed | pass |
| source evaluation compile | `python -m py_compile scripts\evaluate_sources.py tests\test_evaluate_sources.py` | pass | pass | pass |
| real source evaluation | `python scripts\evaluate_sources.py --out data\evaluation\source_registry_metrics.csv` | source metrics written | total_sources=125; linked_documents=0; merged_duplicates=14 | pass |
| full pytest regression | `python -m pytest -q` | all tests pass | 123 passed | pass |
| keyword evaluation regression | `python scripts\evaluate_keyword_search.py --queries data\evaluation\keyword_queries.csv --out data\evaluation\keyword_results.csv` | evaluation pass | 15/15 passed | pass |
| vector evaluation regression | `python scripts\evaluate_vector_search.py --queries data\evaluation\keyword_queries.csv --out data\evaluation\vector_results.csv --keyword-results data\evaluation\keyword_results.csv --skip-index-build` | evaluation baseline remains acceptable | 11/15 passed; keyword baseline 15/15 | pass |
| chat evaluation regression | `python scripts\evaluate_chat.py --queries data\evaluation\chat_queries.csv --out data\evaluation\chat_results.csv` | chat evaluation pass | 6/6 passed; refused=1; citation_failures=0 | pass |
| phase 6 full pytest regression | `python -m pytest -q` | all tests pass after docs and knowledge-base updates | 123 passed | pass |
| phase 6 source evaluation | `python scripts\evaluate_sources.py --out data\evaluation\source_registry_metrics.csv` | source metrics remain stable | total_sources=125; linked_documents=0; merged_duplicates=14 | pass |
| phase 6 keyword evaluation | `python scripts\evaluate_keyword_search.py --queries data\evaluation\keyword_queries.csv --out data\evaluation\keyword_results.csv` | keyword baseline remains stable | 15/15 passed | pass |
| phase 6 vector evaluation | `python scripts\evaluate_vector_search.py --queries data\evaluation\keyword_queries.csv --out data\evaluation\vector_results.csv --keyword-results data\evaluation\keyword_results.csv --skip-index-build` | vector baseline remains stable | 11/15 passed; keyword baseline 15/15 | pass |
| phase 6 chat evaluation | `python scripts\evaluate_chat.py --queries data\evaluation\chat_queries.csv --out data\evaluation\chat_results.csv` | chat baseline remains stable | 6/6 passed; refused=1; citation_failures=0 | pass |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-06-05 | 当前 planning 文件仍记录阶段 3 内容 | 1 | 按用户新要求先用 Planning with Files 重写为阶段 4 流程文件 |
| 2026-06-05 | `derive_status()` 对已有 `local_path` 的 institutional PDF 仍返回默认 `candidate` | 1 | 调整状态判断顺序，让 `downloaded`、`saved` 或已有本地路径的来源返回 `collected` |
| 2026-06-05 | `tests/test_sync_sources.py` 在 session 关闭后访问 SQLAlchemy source 对象属性，触发 detached instance | 1 | 在 session 内提前取出断言需要的字段，再关闭 session |
| 2026-06-05 | 新增 reindex 辅助函数时意外打断 `read_metadata_card()` 的 return 逻辑，导致 metadata cards 读取为 0 | 1 | 补回字段组装和 `return SourceCandidate(...)`，组合测试恢复 15 passed |

### Phase 1: source registry 数据模型与仓储
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 在 `app/db/models.py` 中新增 `Source` SQLAlchemy 模型，对应 `sources` 表。
  - 为 `Document` 新增 `sources` 关系，为 `Source` 新增可选 `document` 关系。
  - `sources` 表新增基础来源字段、治理字段和归一化去重字段。
  - 在 `app/db/repositories.py` 中新增 `SourceCreate`。
  - 新增 `SourceRepository`，支持 create、update、save/upsert、按 id 查询、按 `source_id` 查询、按 DOI/URL/title 重复键查询、列表和计数。
  - 新增 `tests/test_source_repository.py`，验证来源保存、更新、重复键查询、列表/计数和 document 关联。
  - 运行 Phase 1 聚焦测试、编译检查和旧数据库仓储回归。
- Files created/modified:
  - `app/db/models.py` modified
  - `app/db/repositories.py` modified
  - `tests/test_source_repository.py` created
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 2: 来源归一化、去重与治理规则
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `app/services/source_registry.py`。
  - 定义 `SourceRegistryService`、`SourceRegistryResult`、`SourceRegistrySummary`。
  - 新增 `candidate_to_source_create()`，把采集层 `SourceCandidate` 转换为数据库层 `SourceCreate`。
  - 新增 `normalize_url()`，配合已有 `normalize_doi()` 和 `normalize_title()` 形成三层去重键。
  - 实现 DOI、URL、标题优先级去重。
  - 实现重复来源合并，保留更完整的 PDF URL、摘要、分类、发现渠道、引用数、权限和状态。
  - 实现 `derive_trust_level()`、`derive_fulltext_permission()`、`derive_status()`。
  - 新增 `tests/test_source_registry_service.py`，覆盖 URL 归一化、候选转换、DOI/URL/标题去重、合并和权限/可信度/状态规则。
  - 首次测试发现已有本地路径的 institutional PDF 仍被默认状态识别为 `candidate`；已修复为 `collected`。
  - 运行 Phase 2 聚焦测试、Phase 1 仓储测试和旧 source collection 回归。
- Files created/modified:
  - `app/services/source_registry.py` created
  - `tests/test_source_registry_service.py` created
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 3: 从现有 CSV / manifest / metadata corpus 导入来源
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 扩展 `app/services/source_registry.py`，新增现有来源文件读取函数。
  - 新增 `read_existing_source_candidates()`，支持合并读取 source candidates CSV、fulltext manifest、metadata CSV 和 metadata cards。
  - 新增 `read_metadata_cards()` 和 `read_metadata_card()`，支持从 `data/imports/metadata_corpus/*.md` 解析题录来源。
  - 新增 `scripts/sync_sources.py`，默认同步项目现有来源文件到 `sources` 表。
  - `scripts/sync_sources.py` 支持 `--candidate-csv`、`--fulltext-manifest`、`--metadata-csv`、`--metadata-cards-dir` 和 `--no-defaults`。
  - 新增 `tests/test_sync_sources.py`，覆盖 metadata card 解析、CSV/manifest/card 同步、重复导入幂等和默认路径过滤。
  - 首次同步脚本测试发现 session 关闭后访问 SQLAlchemy 对象属性导致 detached instance；已改为在 session 内取值。
  - 运行脚本测试、服务测试、仓储测试和编译检查。
  - 使用真实项目数据运行 `scripts/sync_sources.py`，本地 `sources` 表已同步 125 条来源记录。
- Files created/modified:
  - `app/services/source_registry.py` modified
  - `scripts/sync_sources.py` created
  - `tests/test_sync_sources.py` created
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 4: 重新索引入口与来源管理 API
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 在 `SourceRegistryService` 中新增 `reindex_source()`。
  - 新增 `SourceReindexResult`、`SourceNotFoundError`、`SourceReindexError`。
  - 新增 metadata-only 来源的 metadata card 生成能力。
  - reindex 复用 `IngestionService.import_document()`，导入成功后更新 `sources.document_id` 和 `status=imported`。
  - 新增 `app/schemas/source.py`。
  - 新增 `app/api/sources.py`。
  - 在 `app/main.py` 注册 sources router。
  - 新增 `tests/test_sources_api.py`，覆盖来源同步、列表、详情、metadata reindex 和缺失 source 404。
  - 组合测试发现 `read_metadata_card()` 被 reindex 辅助函数打断；已补回 return 逻辑并通过回归。
  - 运行 sources API 测试、source 管理组合测试、编译检查和 documents/chat API 回归。
- Files created/modified:
  - `app/services/source_registry.py` modified
  - `app/schemas/source.py` created
  - `app/api/sources.py` created
  - `app/main.py` modified
  - `tests/test_sources_api.py` created
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 5: 阶段 4 测试、评测脚本与回归验证
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 新增 `scripts/evaluate_sources.py`，用于统计来源登记库的 smoke 指标。
  - 新增 `tests/test_evaluate_sources.py`，覆盖来源指标统计和 CSV 输出。
  - 运行来源评测脚本，生成 `data/evaluation/source_registry_metrics.csv`。
  - 运行 source evaluation 聚焦测试和编译检查。
  - 运行 `python -m pytest -q` 全量测试，确认 123 passed。
  - 运行关键词、向量和 chat 评测，确认阶段 4 未破坏阶段 1-3 检索与引用问答链路。
- Files created/modified:
  - `scripts/evaluate_sources.py` created
  - `tests/test_evaluate_sources.py` created
  - `data/evaluation/source_registry_metrics.csv` created
  - `data/evaluation/keyword_results.csv` regenerated
  - `data/evaluation/vector_results.csv` regenerated
  - `data/evaluation/chat_results.csv` regenerated
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag
- **Status:** complete
- **Started:** 2026-06-05
- Actions taken:
  - 更新 `README.md`，把当前阶段、测试数量、来源管理脚本、sources API 和阶段 4 面试表达校准为最新状态。
  - 更新 `docs/progress.md`，新增阶段 4 完成记录、验证结果、遗留问题、下一阶段任务和面试表达。
  - 更新 `docs/architecture.md`，新增阶段 4 source registry 架构、`sources` 表、去重策略、权限字段、状态字段、同步脚本、API、reindex 和来源评测说明。
  - 更新 `docs/data_sources.md` 和 `docs/corpus_pipeline.md`，说明 CSV、manifest、metadata corpus、`sources` 表与 `documents/chunks` 的关系。
  - 更新 `AGENT.MD`，把后续默认起点从阶段 4 校准为阶段 5 前端界面。
  - 更新本地 Obsidian 知识库：首页、阶段索引、阶段 4 页面、分类页和阶段 4 知识点。
  - 运行阶段收尾验证：全量测试、source evaluation、keyword evaluation、vector evaluation、chat evaluation。
  - 准备创建阶段最终提交与 `phase-4-complete` tag。
- Files created/modified:
  - `README.md` modified
  - `docs/progress.md` modified
  - `docs/architecture.md` modified
  - `docs/data_sources.md` modified
  - `docs/corpus_pipeline.md` modified
  - `AGENT.MD` modified
  - `obsidian-vault/首页.md` modified locally
  - `obsidian-vault/阶段索引.md` modified locally
  - `obsidian-vault/阶段/阶段 4 - 数据采集与来源管理.md` modified locally
  - `obsidian-vault/分类/*.md` modified locally
  - `obsidian-vault/知识点/Source Registry 来源登记库.md` created locally
  - `obsidian-vault/知识点/来源去重与归一化.md` created locally
  - `obsidian-vault/知识点/全文保存权限与可信度评级.md` created locally
  - `obsidian-vault/知识点/Source Reindex 重新索引入口.md` created locally
  - `obsidian-vault/知识点/来源登记库评测.md` created locally
  - `task_plan.md` modified
  - `findings.md` modified
  - `progress.md` modified

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 6 complete，当前分支 `codex/phase-4-source-management` |
| Where am I going? | 创建阶段最终提交和 `phase-4-complete` tag 后，阶段 4 即完成；下一大阶段是阶段 5 前端界面 |
| What's the goal? | 完成阶段 4 数据采集与来源管理：source registry、去重、权限、状态、导入、reindex、API/脚本、测试和文档收尾 |
| What have I learned? | 来源治理需要和检索内容分层；`sources` 负责候选、权限、可信度、状态和去重，`documents/chunks` 负责可检索正文或题录卡片；阶段收尾必须同步 README、docs、AGENT 和 Obsidian |
| What have I done? | 改线程名、确认分支/tag、用 Planning with Files 重写阶段 4 工作记忆；完成 `sources` 表、`SourceRepository`、`SourceRegistryService`、来源归一化/去重/权限/可信度/状态规则、`scripts/sync_sources.py`、sources API、source reindex、`scripts/evaluate_sources.py`、对应测试、阶段文档和 Obsidian 收尾；全量测试 123 passed |
