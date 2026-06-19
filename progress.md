# 阶段 45 Progress：数据上云与多模态 RAG

## Session: 2026-06-18

### Phase 0：启动校准与规划落盘（Claude 规划方）

- **Status:** complete
- **Started:** 2026-06-18

Phase purpose:

- 这一 Phase 由 Claude 规划方完成，为阶段 45 编写任务计划、发现记录和进度文件。
- 阶段 45 有两条主线：A（数据迁移到云端 PostgreSQL）、B（多模态 RAG — PDF 图像提取 + 视觉模型描述 + 统一检索）。
- 现在做它，是因为阶段 44 已完成生产部署但云端 PostgreSQL 是空库，用户无法在云端做真实查询；同时项目一直是纯文本 RAG，PDF 中大量图表/公式/架构图信息未被利用，多模态识别是用户明确提出的下一步方向。

Actions taken:

- 确认阶段 44 最终状态：894 tests，Stage 30 = 91.52/A/pass，云端 Docker + PostgreSQL + 认证已通过公网 smoke。
- 审查数据迁移需求：本地 SQLite 753 documents + 19,300 embeddings，云端 PostgreSQL 空库。
- 审查 PDF 解析现状：pypdf 文本提取 + pdf_text.py 结构化，无图像提取能力。
- 审查 provider 架构：ChatModelProvider / EmbeddingProvider / ReRankingProvider 三种 Protocol，均有 Deterministic + OpenAICompatible 实现。
- 审查 Chunk 模型：无 chunk_type 字段，全部为文本 chunk。
- 编写 `task_plan.md`（10 个 Phase: 0-9）、`findings.md`（技术选型 + 数据模型扩展方案）、`progress.md`。

Outcome:

- 规划文件就绪，等待 Codex 接手执行 Phase 1-9。

### Phase 0：启动校准与规划落盘（Codex 接手校准）

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决阶段 45 的正式开工基线问题：确认阶段 44 已合并、分支从正确的 `origin/main` 创建，并把 Claude 规划方留下的 Phase 0-9 计划校准为 Codex 可继续执行的状态。
- 现在做它，是因为数据迁移和多模态 RAG 都会触及数据库、schema、入库链路和检索链路，必须先确认不在阶段 44 功能分支上继续开发，也不能误移动已有阶段 tag。

Actions taken:

- 完整阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 运行 `git status -sb` 与 `git log --oneline -5 --decorate`，确认开工时存在本地未提交改动并按要求保留。
- 执行 `git fetch origin`，确认 `origin/main -> de3a96c Merge phase 44 production deployment auth`。
- 从 `origin/main` 创建并切换到 `codex/phase-45-data-migration-multimodal-rag`。
- 校准 `task_plan.md`、`findings.md`、`progress.md`，记录 Phase 0 完成状态和禁止提交/tag/push/PR 边界。

Outcome:

- Phase 0 完成。下一步进入 Phase 1：设计文档与测试合同。

### Phase 1：设计文档与测试合同

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决阶段 45 的设计合同问题：先明确数据迁移和多模态 RAG 的目标、边界、验收标准和测试口径，再进入会影响数据库和检索链路的实现。
- 现在做它，是因为主线 A 会写跨数据库迁移脚本，主线 B 会扩展 chunk 模型、PDF 入库和 provider 架构；没有设计合同容易把迁移、真实 API、云部署 smoke 和本地回归边界混在一起。

Actions taken:

- 新增 `docs/stage45_data_migration_multimodal_rag.md`，记录 Track A/Track B、baseline、迁移范围、chunk 模型扩展、VisionModelProvider、安全边界和验收标准。
- 新增 `tests/test_stage45_design.py`，覆盖阶段 45 设计文档、敏感信息排除、10 个 Phase 规划、阶段 44 merge baseline、deterministic vision 和增量迁移合同。
- 校准 `task_plan.md` 中 Phase 1 状态和人工核验前禁止 `git add/commit/tag/push/PR` 的边界措辞。

Verification:

- `python -m pytest tests/test_stage45_design.py -q -> 4 passed`

Outcome:

- Phase 1 完成。下一步进入 Phase 2：数据迁移工具。

### Phase 2：数据迁移工具（主线 A）

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决云端 PostgreSQL 有 schema 但没有语料的问题：把本地 SQLite 的 documents、sources、chunks、chunk_embeddings 和 qa_logs 增量迁移到目标库。
- 现在做它，是因为阶段 44 已经证明云端可部署和可登录，但没有迁移语料时云端 RAG 仍然不能真正检索；同时 FAISS 应从目标库 embeddings 重建，不能依赖复制本地索引文件。

Actions taken:

- 新增 `scripts/migrate_sqlite_to_postgres.py`，提供 `migrate_sqlite_to_target()` 复用函数和 CLI。
- 迁移脚本限制源库为 SQLite，目标库复用阶段 44 的 `create_database_engine()`，支持 PostgreSQL，测试中使用临时 SQLite 模拟。
- 实现 documents / sources / chunks / chunk_embeddings / qa_logs 的增量迁移；users / conversations / messages 明确不迁移。
- 实现旧 ID 到目标 ID 的映射，覆盖 source-document、parent-child chunk、embedding-chunk 的引用关系。
- 扩展 `scripts/build_faiss_index.py`，新增 `--database-url`，支持从迁移后的目标数据库读取 embeddings 重建 FAISS。
- 新增 `tests/test_stage45_migration.py`，覆盖迁移可重复运行、引用映射、以及 FAISS 从显式数据库 URL 构建。

Verification:

- `python -m pytest tests/test_stage45_migration.py tests/test_faiss_index.py::test_list_current_embeddings_skips_parent_chunks -q -> 3 passed`
- `python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py -q -> 6 passed`

New terms:

- 增量迁移：脚本可以多次运行，已经迁移过的记录会被识别并跳过，不会重复插入。
- ID 映射：源库和目标库的主键通常不同，迁移时需要记录“源 ID 对应目标 ID”，再用目标 ID 重建外键关系。
- FAISS 派生索引：FAISS `.index` 文件由数据库中的 embedding 生成，是可重建运行时产物，不作为数据库迁移对象。

Outcome:

- Phase 2 完成。下一步进入 Phase 3：Chunk 模型扩展。

### Phase 3：Chunk 模型扩展

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决多模态 RAG 的数据模型表达问题：让系统能区分普通文本 chunk 和由 PDF 图片生成的描述 chunk，并记录图片来源路径。
- 现在做它，是因为后续 Phase 4-6 会提取图片、生成视觉描述并入库；如果 `chunks` 表不能表达 `image_description`，后续管线只能把图片描述伪装成普通文本，难以追踪和验证。

Actions taken:

- 在 `app/db/models.py::Chunk` 新增 `chunk_type` 和 `source_image_path` 字段。
- 在 `app/db/repositories.py::ChunkCreate` 和 `DocumentRepository.create_with_chunks()` 中支持新字段，并保持默认 `chunk_type="text"`。
- 在 `app/schemas/document.py` 和 `app/api/documents.py` 中让文档 chunk 列表返回新字段。
- 新增 Alembic migration `alembic/versions/20260618_0002_chunk_multimodal_fields.py`，为旧数据补 `chunk_type="text"` 并增加 `source_image_path`。
- 新增 `tests/test_stage45_chunk_schema.py`，覆盖默认 text chunk、image_description chunk 和 Alembic migration 合同。

Verification:

- `python -m pytest tests/test_stage45_chunk_schema.py tests/test_stage45_migration.py tests/test_db_models.py tests/test_repositories.py -q -> 15 passed`
- `python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py -q -> 9 passed`

New terms:

- `chunk_type`：chunk 的内容类型标记，本阶段支持 `text` 和 `image_description`。
- `image_description` chunk：由图片经过视觉模型描述后生成的文本 chunk，后续会像普通文本一样生成 embedding 并进入检索。
- `source_image_path`：图片描述 chunk 对应的本地图片路径，用于追踪该描述来自 PDF 中哪张提取图片。

Outcome:

- Phase 3 完成。下一步进入 Phase 4：PDF 图像提取。

### Phase 4：PDF 图像提取

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决 PDF 图表进入多模态链路前的文件提取问题：从 PDF 中提取有效图片、过滤小图，并保存为后续视觉模型可读取的 PNG 文件。
- 现在做它，是因为视觉模型 Provider 应只负责“看图并描述”，不应同时承担 PDF 解包、图像尺寸过滤和运行时文件管理。

Actions taken:

- 在 `pyproject.toml` 新增 `PyMuPDF>=1.24.0`，并在当前测试环境安装 PyMuPDF。
- 在 `.gitignore` 新增 `data/images/`，把提取图片视为本地运行时产物。
- 新增 `app/services/ingestion/image_extractor.py`，实现 `PdfImageExtractor`、`PdfImageExtractionConfig` 和 `ExtractedPdfImage`。
- 提取器使用 PyMuPDF 逐页读取图片 xref，统一保存为 PNG，并过滤宽或高小于 100px 的图片。
- 新增 `tests/test_stage45_image_extractor.py`，用合成 PDF 验证有效图片保存、小图过滤和非 PDF 输入快速失败。

Verification:

- `python -m pytest tests/test_stage45_image_extractor.py tests/test_stage45_chunk_schema.py -q -> 5 passed`
- `python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py tests/test_stage45_image_extractor.py -q -> 11 passed`

New terms:

- PyMuPDF / `fitz`：Python PDF 处理库，本阶段用于从 PDF 页面中提取图片。
- xref：PDF 内部对象引用编号，PyMuPDF 用它定位页面中嵌入的图片对象。
- pixmap：图片像素数据对象，可由 PyMuPDF 保存为 PNG。

Outcome:

- Phase 4 完成。下一步进入 Phase 5：视觉模型 Provider。

### Phase 5：视觉模型 Provider

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决图片如何变成可检索文本的问题：抽象出视觉模型 Provider，让图片描述能力可替换、可测试，并保持真实 API 不进入本地全量测试前提。
- 现在做它，是因为 Phase 6 多模态入库管线需要稳定调用“描述图片”的接口，而不是把真实视觉 API 细节写死在管线里。

Actions taken:

- 在 `app/core/config.py` 和 `.env.example` 新增 `VISION_MODEL_PROVIDER`、`VISION_MODEL_NAME`、`VISION_MODEL_API_KEY`、`VISION_MODEL_BASE_URL`、`VISION_MODEL_TIMEOUT_SECONDS`。
- 新增 `app/services/generation/vision_model.py`，实现 `VisionModelProvider` Protocol。
- 实现 `DeterministicVisionModelProvider`，用于测试和本地 deterministic 回归。
- 实现 `OpenAICompatibleVisionModelProvider`，发送 OpenAI-compatible vision chat payload：文本 prompt + base64 `image_url`。
- 实现 `image_to_data_uri()`、响应解析和 `create_vision_model_provider()` 工厂函数。
- 新增 `tests/test_stage45_vision_model.py`，通过 monkeypatch 验证 payload，不调用真实 API。

Verification:

- `python -m pytest tests/test_stage45_vision_model.py -q -> 6 passed`
- `python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py tests/test_stage45_image_extractor.py tests/test_stage45_vision_model.py -q -> 17 passed`

New terms:

- VisionModelProvider：视觉模型抽象接口，输入图片路径，输出文字描述。
- base64 data URI：把图片 bytes 编码进 `data:image/png;base64,...` 字符串，供 OpenAI-compatible vision 接口读取。
- OpenAI-compatible vision payload：chat/completions 请求中 `content` 使用数组，同时传文本和图片。

Outcome:

- Phase 5 完成。下一步进入 Phase 6：多模态入库管线。

### Phase 6：多模态入库管线

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决端到端多模态入库问题：把 PDF 图像提取、视觉模型描述、`image_description` chunk 创建和 embedding 写入串成一条可测试管线。
- 现在做它，是因为只有图片描述真正写入 `chunks` 并生成 embedding 后，它才能像普通文本一样参与向量检索；单独有提取器和 provider 还不构成多模态 RAG。

Actions taken:

- 新增 `app/services/ingestion/multimodal_pipeline.py`，实现 `MultimodalIngestionPipeline` 和 `MultimodalDocumentResult`。
- 管线读取 PDF 文档的 `raw_path`，提取有效图片，调用 `VisionModelProvider.describe_image()` 生成中文描述。
- 管线创建 `chunk_type="image_description"` 的 chunk，并记录 `source_image_path`。
- 管线可注入 `EmbeddingProvider`，创建新 chunk 后调用 `VectorIndexService` 为新增描述生成 embedding，并使向量缓存失效。
- 管线按 `source_image_path` 跳过已处理图片，支持重复运行。
- 新增 `scripts/process_multimodal.py`，支持处理单个 document 或全部 PDF，并可选择跳过 embedding。
- 新增 `tests/test_stage45_multimodal_pipeline.py`，用合成 PDF、静态视觉描述和 deterministic embedding 验证 image_description chunk 可被普通向量检索召回。

Verification:

- `python -m pytest tests/test_stage45_multimodal_pipeline.py tests/test_stage45_image_extractor.py tests/test_stage45_vision_model.py tests/test_stage45_chunk_schema.py -q -> 12 passed`
- `python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py tests/test_stage45_image_extractor.py tests/test_stage45_vision_model.py tests/test_stage45_multimodal_pipeline.py -q -> 18 passed`

New terms:

- 多模态入库管线：把非文本信息先转成可检索文本，再写入原有 RAG 数据结构的流程。
- 统一检索：图片描述 chunk 和普通文本 chunk 使用同一套 embedding、向量检索和 rerank 链路，不新增特殊路由。
- 幂等处理：同一张已提取图片再次处理时会被识别并跳过，不重复创建 chunk。

Outcome:

- Phase 6 完成。下一步进入 Phase 7：全量回归与 Stage 30。

### Phase 7：全量回归与 Stage 30

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决阶段 45 新增能力是否破坏既有系统的问题：全量测试、Stage 30 评分和 production smoke dry-run 必须保持通过。
- 现在做它，是因为 Phase 1-6 已改动依赖、数据库模型、Alembic、迁移脚本、PDF 处理、provider、embedding 和检索链路，进入浏览器 smoke 前必须先确认后端与质量门槛稳定。

Actions taken:

- 运行首次全量 `python -m pytest -q`，发现 1 个旧测试锚点失败：Phase 44 测试仍把当前根目录 `task_plan.md` 当作 Phase 44 计划。
- 将 `tests/test_stage44_design.py` 的 Phase 44 计划断言改为读取长期历史记录 `docs/progress.md`，避免当前阶段计划切换造成误报。
- 重新运行 Phase 44/45 设计测试、全量测试、Stage 30 评分和 production smoke dry-run。

Verification:

- `python -m pytest tests/test_stage44_design.py tests/test_stage45_design.py -q -> 7 passed`
- `python -m pytest -q -> 912 passed`
- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python scripts/run_production_smoke.py -> rows=11 execute=false failed=0`

New terms:

- 测试锚点：测试读取的“权威事实来源”。阶段切换后，当前 `task_plan.md` 会服务新阶段，历史阶段断言应锚定 `docs/progress.md` 或对应阶段文档。
- production smoke dry-run：只验证 smoke 用例定义和预期结构，不访问真实服务，不要求云端或真实 API 可用。

Outcome:

- Phase 7 完成。下一步进入 Phase 8：浏览器 smoke。

### Phase 8：浏览器 smoke

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决前端页面和浏览器内 API 检索是否正常的问题：确认页面在桌面和移动视口可加载、无 console errors、无横向溢出，并验证 `image_description` chunk 能通过搜索 API 召回。
- 现在做它，是因为 Phase 7 已完成后端全量回归；浏览器 smoke 是进入最终文档和 Obsidian 收尾前的用户体验检查。

Actions taken:

- 启动阶段 45 本地服务到 `http://127.0.0.1:8015`，用 Playwright CLI 检查桌面页面。
- 创建临时 SQLite `data/stage45_browser_smoke.sqlite`，写入一个 `chunk_type=image_description` chunk 并生成 deterministic embedding。
- 启动临时服务到 `http://127.0.0.1:8016`，用浏览器内 `fetch('/search/vector')` 查询图像描述 chunk。
- 切换到 390x844 移动视口检查页面内容、console errors 和横向溢出。
- 关闭 Playwright sessions，并停止 8015/8016 两个 uvicorn smoke 进程。

Verification:

- Desktop smoke 8015：page title `RFC-RAG-Agent`，auth gate rendered，console errors=0，horizontal overflow=false。
- Browser API smoke 8016：`/search/vector` 返回 `status=200`、`count=1`，命中图像描述 chunk 内容。
- Mobile smoke 390x844：页面有内容，`scrollWidth=390`、`clientWidth=390`，horizontal overflow=false，console errors=0。

New terms:

- 浏览器内 API smoke：通过真实浏览器环境执行 `fetch()` 调用本地 API，验证编码、路由和响应结构，而不只用命令行请求。
- 横向溢出：页面内容宽度超过视口宽度，移动端会出现左右滚动；本阶段检查为 false。

Outcome:

- Phase 8 完成。下一步进入 Phase 9：普通文档与 Obsidian 收尾。

### Phase 9：文档与 Obsidian 收尾

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决阶段 45 的交付沉淀问题：把开发结果写回普通文档和 Obsidian，使用户人工核验时能看到完整的设计、实现、验证和复盘入口。
- 现在做它，是因为 Phase 0-8 已完成代码、测试、质量回归和浏览器 smoke；收尾必须在不提交、不打 tag、不 push 的前提下，把项目状态停在清晰的待核验位置。

Actions taken:

- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，补充阶段 45 数据迁移和多模态 RAG 的状态说明。
- 新增 `docs/phase_reviews/phase-45.md`，记录阶段 45 验收草稿、验证结果和人工核验前禁止动作。
- 建立 `obsidian-vault/阶段汇报/阶段 45 - 数据上云与多模态 RAG/`，补齐 Phase 0-9 小汇报和阶段汇报索引。
- 新增 `obsidian-vault/阶段/阶段 45 - 数据上云与多模态 RAG.md`。
- 更新 `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`，挂上阶段 45 入口。
- 更新 `task_plan.md`、`findings.md`、`progress.md`，标记 Phase 9 完成并记录最终待人工核验状态。

Verification:

- Phase 7 全量回归已通过：`python -m pytest -q -> 912 passed`。
- Stage 30 已确认不退化：`python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`。
- Production smoke dry-run 已通过：`python scripts/run_production_smoke.py -> rows=11 execute=false failed=0`。
- Phase 8 浏览器 smoke 已通过：桌面和移动端无 console error、无横向溢出，`image_description` chunk 可通过 `/search/vector` 召回。

New terms:

- Obsidian 阶段页：面向复盘的阶段总览，概括阶段目标、关键模块、验证结果和面试表达。
- Phase 汇报索引：连接某个大阶段内所有小 Phase 汇报的目录。

Outcome:

- Phase 9 完成。阶段 45 开发、测试、普通文档和 Obsidian 草稿已完成，当前停在用户人工核验前状态；尚未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

### Phase 10-17：新增 458 篇文献导入与云端发布规划

- **Status:** planned
- **Started:** 2026-06-18

Phase purpose:

- 这一组追加 Phase 解决新增约 458 篇国内堆石混凝土文献如何进入阶段 45 的问题。
- 现在做它，是因为 Phase 0-9 已完成迁移工具链和多模态能力建设，但真实语料还没有迁移云端，也没有对新增国内文献进行批量导入、去重、质检、多模态处理和云端发布。

Actions planned:

- Phase 10：新增文献接收与 manifest 清单化。
- Phase 11：本地 SQLite 预导入与去重。
- Phase 12：解析质量审计与元数据补齐。
- Phase 13：新增语料文本 chunk、embedding 与本地 FAISS 重建。
- Phase 14：新增 PDF 多模态处理，使用 GLM-4.6V 生成图片描述。
- Phase 15：国内堆石混凝土语料覆盖评估与人工抽检。
- Phase 16：本地黄金语料库迁移到云端 PostgreSQL。
- Phase 17：云端文件资产同步、FAISS 重建与生产 smoke。

Decision:

- 不采用“本地和云端同时导入”。新增文献先在本地 SQLite 建成可评估、可回滚的黄金语料库；通过质量核验后，再用阶段 45 迁移脚本增量发布到云端 PostgreSQL。

Outcome:

- 阶段 45 已从 Phase 0-9 扩展为 Phase 0-17。下一步从 Phase 10 开始，等待用户提供新增 458 篇文献文件或文件目录。

### Phase 10：新增 458 篇文献接收与 manifest 清单化

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决新增文献正式入库前的“批次账本”问题：先把 `G:\Codex\program\papers_0618` 下的文件逐一登记为 manifest，确认文件类型、大小、SHA256/content_hash、是否可打开、页数、疑似标题和重复候选状态。
- 现在做它，是因为后续 Phase 11 会写入本地 SQLite；在写库前先有 manifest，才能避免重复导入、不可读文件混入和后续云端状态分叉。

Actions taken:

- 新增 `scripts/build_phase45_literature_manifest.py`，支持扫描 `*.pdf` 和 `*.caj`，用 SHA256 生成 `content_hash`，用 pypdf 检查 PDF 是否可打开并读取页数/标题。
- 脚本读取本地 SQLite 既有 documents 的 `content_hash` 和标题，用文件哈希做强重复候选，用标题归一化做弱重复候选。
- 生成 `data/incoming/phase45_literature/manifest.csv` 和 `data/incoming/phase45_literature/manifest.json`。
- 新增 `tests/test_stage45_literature_manifest.py`，覆盖 ready、duplicate_candidate、CAJ 不可直接解析、CSV/JSON 写出。

Verification:

- `python -m pytest tests/test_stage45_literature_manifest.py -q -> 2 passed`
- `python scripts/build_phase45_literature_manifest.py --input-dir "G:\Codex\program\papers_0618" --output-dir data/incoming/phase45_literature --sqlite-path data/app.sqlite -> total=458 ready=324 duplicate_candidate=134`

New terms:

- manifest：批次清单，只记录文件状态和元数据，不等于入库。
- content_hash：文件内容 SHA256 指纹，用来识别完全相同的文件。
- duplicate_candidate：重复候选，既包括 content_hash 强重复，也包括标题/文件名弱重复。

Outcome:

- Phase 10 完成。新增 458 个文件已清单化：455 个 PDF、3 个 CAJ；当前 ready 324、duplicate_candidate 134。本 Phase 未生成 embedding，未写云端 DB。下一步进入 Phase 11：基于 ready 集合做本地 SQLite 预导入与去重。

### Phase 11：本地 SQLite 预导入与去重

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决新增文献进入本地黄金语料库候选集的问题：只导入 Phase 10 manifest 中的 ready 文献，重复候选和不可解析文件不重复创建正式 document。
- 现在做它，是因为 Phase 12 的解析质量审计需要基于本地 SQLite 里的 documents/chunks 统计文本长度、chunk 数和疑似扫描版风险。

Actions taken:

- 新增 `scripts/import_phase45_manifest_ready.py`，从 `manifest.csv` 读取 ready 行并调用现有 `IngestionService` 入库。
- 新增 `tests/test_stage45_manifest_import.py`，验证只导入 ready 行、跳过 duplicate_candidate、同一文件重复导入时幂等返回 duplicate。
- 导入前备份 `data/app.sqlite` 到 `data/app.sqlite.backup-before-phase45-phase11-import-20260618`。
- 执行真实导入并生成 `data/incoming/phase45_literature/phase11_import_summary.json` 与 `phase11_import_results.csv`。

Verification:

- `python -m pytest tests/test_stage45_manifest_import.py tests/test_stage45_literature_manifest.py -q -> 3 passed`
- `python scripts/import_phase45_manifest_ready.py --manifest data/incoming/phase45_literature/manifest.csv --output-dir data/incoming/phase45_literature --raw-dir data/raw --source-type institutional_access_pdf -> imported=302 empty=22 failed=0 new_chunks=3237`
- DB 核验：`documents=1055`，`chunks=32225`，`chunk_embeddings=51316`；embedding 数未变化，符合 Phase 11 边界。

New terms:

- empty：PDF 可打开，但解析后没有可切分正文，常见于扫描版、短讯、会议通知或版式抽取失败。
- canonical document：去重后正式保留的一份 document；重复候选不重复入库，只保留在 manifest/import results 中供审计。

Outcome:

- Phase 11 完成。新增 302 篇文献进入本地 SQLite，新增 3,237 个 text chunks；134 条 duplicate_candidate 跳过，22 篇 empty 进入后续 review 队列。本 Phase 未生成 embedding，未写云端 DB。下一步进入 Phase 12：解析质量审计与元数据补齐。

### Phase 12：解析质量审计与元数据补齐

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决新增文献能否进入后续索引和云端发布候选集的问题：统计页数、文本长度、中文比例、chunk 数量、疑似扫描版状态，并把低质量解析文献放入 review 队列。
- 现在做它，是因为 Phase 13 会为新增语料生成 embedding 和重建 FAISS；如果不先拦截低质量解析，噪声会进入检索索引。

Actions taken:

- 新增 `scripts/audit_phase45_import_quality.py`，读取 manifest、Phase 11 import results 和本地 SQLite chunks，生成质量审计 CSV、review 队列和 summary。
- 新增 `tests/test_stage45_quality_audit.py`，覆盖低文本/empty 识别、cloud_candidate 判定和 source metadata upsert。
- 执行 Phase 12 审计，并为 302 篇 imported 文献 upsert `sources` 元数据草案。

Verification:

- `python -m pytest tests/test_stage45_quality_audit.py tests/test_stage45_manifest_import.py tests/test_stage45_literature_manifest.py -q -> 4 passed`
- `python scripts/audit_phase45_import_quality.py --db-path data/app.sqlite --manifest data/incoming/phase45_literature/manifest.csv --import-results data/incoming/phase45_literature/phase11_import_results.csv --output-dir data/incoming/phase45_literature --upsert-sources -> cloud_candidate=75 review_required=249 sources_upserted=302`

New terms:

- cloud_candidate：通过本地质量初筛、可进入后续 embedding/FAISS 和云端发布候选的文献。
- review_queue：需要人工复核或后续修复的文献清单。
- suspected_scanned：疑似扫描版或文本抽取失败标记，当前由空文本或每页文本量过低触发。

Outcome:

- Phase 12 完成。质量审计产物已生成：`phase12_quality_audit.csv`、`phase12_review_queue.csv`、`phase12_quality_summary.json`。标题校准后当前 20 篇 cloud_candidate 可进入 Phase 13，其余 review_required 暂不进入云端发布集。下一步进入 Phase 13：新增语料 text chunk、embedding 与本地 FAISS 重建。

### Phase 13：新增语料 text chunk、embedding 与本地 FAISS 重建

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决新增高质量语料能否进入向量检索的问题：只给 Phase 12 的 cloud_candidate 文档生成 GLM-Embedding-3 embedding，并从数据库重建本地 FAISS。
- 现在做它，是因为 Phase 12 已经把 review_required 文献隔离出来；此时生成 embedding 可以避免低质量解析进入索引。

Actions taken:

- 新增 `scripts/index_phase45_cloud_candidates.py`，读取 `phase12_quality_audit.csv`，只处理 `review_status=cloud_candidate` 的 document chunks。
- 新增 `tests/test_stage45_candidate_indexing.py`，验证只索引候选文档、不索引 review 文档，并支持幂等跳过已有 embedding。
- 扩展脚本支持 `--prune-non-candidates`，用于清理标题校准后不再属于候选集的新增文献 embedding。
- 新增 `scripts/smoke_phase45_candidate_retrieval.py`，验证 keyword/vector/hybrid 三种检索模式。
- 从数据库重建本地 FAISS：`data/faiss/paratera_GLM-Embedding-3_dim2048.index` 与 ids metadata。

Verification:

- `python -m pytest tests/test_stage45_candidate_indexing.py tests/test_stage45_quality_audit.py -q -> 2 passed`
- `python scripts/index_phase45_cloud_candidates.py --audit data/incoming/phase45_literature/phase12_quality_audit.csv --output data/incoming/phase45_literature/phase13_embedding_summary.json --batch-size 8 --sleep-seconds 0.1 --prune-non-candidates -> candidate_documents=20 total_chunks=238 skipped_chunks=238`
- `python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 --output-dir data/faiss -> vectors=19538`
- `python scripts/smoke_phase45_candidate_retrieval.py --output data/incoming/phase45_literature/phase13_retrieval_smoke.csv -> keyword/vector/hybrid 均有命中`
- DB 核验：`chunk_embeddings=51554`，即原 51316 加新增候选 238。

New terms:

- FAISS：本地向量索引，由数据库里的 embedding 派生，可重建，不直接作为云端迁移对象。
- prune non-candidate embeddings：删除不再属于候选集的新增文献 embedding，避免 review_required 文献进入索引。
- retrieval smoke：轻量检索冒烟测试，只记录命中数量和来源标题，不保存 chunk 正文。

Outcome:

- Phase 13 完成。当前 20 篇 cloud_candidate 的 238 个 text chunks 已进入 GLM-Embedding-3 与本地 FAISS；关键词、向量、混合检索均可命中。下一步进入 Phase 14：新增 PDF 多模态处理（图片提取 + GLM-4.6V 描述）。

### Phase 14：新增 PDF 多模态处理（图片提取 + GLM-4.6V 描述）

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决新增候选 PDF 中图像/图表信息进入 RAG 的问题：提取有效图片，用 GLM-4.6V 生成中文描述，创建 `chunk_type=image_description` chunks，并让这些描述进入统一向量检索。
- 现在做它，是因为 Phase 13 已经完成 text chunks 的 embedding 与 FAISS；多模态描述可以作为同一批候选文献的补充证据进入索引。

Actions taken:

- 新增 `scripts/process_phase45_candidate_multimodal.py`，只处理 Phase 12 `cloud_candidate` 文档，创建 image_description chunks，不调用通用全库 embedding build。
- 扩展 `scripts/index_phase45_cloud_candidates.py`，支持 `--chunk-type image_description`，用于限定索引图像描述 chunks。
- 使用本地进程环境配置真实 GLM-4.6V 进行图片描述；API key 只放在进程环境中，未写入文件、测试、CSV、文档或 Obsidian。
- 重跑失败超时文档，利用 `source_image_path` 去重跳过已处理图片，最终完成全部候选文档。
- 重建本地 FAISS，并运行 image_description 检索 smoke。

Verification:

- `python -m pytest tests/test_stage45_candidate_indexing.py tests/test_stage45_multimodal_pipeline.py tests/test_stage45_vision_model.py -q -> 10 passed`
- `python scripts/process_phase45_candidate_multimodal.py ... -> candidate_documents=20 processed_documents=20 failed_documents=0 extracted_images=51 created_chunks=23 skipped_images=28`
- `python scripts/index_phase45_cloud_candidates.py --chunk-type image_description --prune-non-candidates -> total_chunks=51 indexed_chunks=23 skipped_chunks=28`
- `python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 --output-dir data/faiss -> vectors=19589`
- `python scripts/smoke_phase45_candidate_retrieval.py --query "浇筑点 块石 上游 下游 2m" --query "压力试验设备 试件 压板" -> vector top 命中 image_description`

New terms:

- image_description chunk：由 PDF 图片经视觉模型描述生成的文本 chunk。
- source_image_path：image_description chunk 对应的本地图片路径。
- idempotent processing：重复运行不会为同一图片重复创建 chunk。

Outcome:

- Phase 14 完成。20 篇候选文献完成图像提取和 GLM-4.6V 描述，共 51 个 image_description chunks 进入本地 SQLite、embedding 和 FAISS。下一步进入 Phase 15：国内堆石混凝土语料覆盖评估。

### Phase 15：国内堆石混凝土语料覆盖评估

- **Status:** complete
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决新增 458 篇文献是否带来有效覆盖增量的问题：新增评测问题，比较导入前后检索覆盖，复跑 Stage 30，并生成代表性文献抽检样本。
- 现在做它，是因为 Phase 13/14 已经让候选文本和图片描述进入本地 FAISS；继续云端准备前必须先判断新增语料是有效补充还是噪声。

Actions taken:

- 新增 `data/evaluation/phase45_domestic_coverage_queries.csv`，包含 10 条国内堆石混凝土覆盖评测问题。
- 新增 `scripts/evaluate_phase45_domestic_coverage.py`，对比导入前备份库和当前库的关键词覆盖命中，不导出 chunk 正文。
- 运行 Stage 30 质量评分。
- 生成 `data/evaluation/phase45_spotcheck_sample.csv`，包含 30 篇抽检样本。

Verification:

- `python scripts/evaluate_phase45_domestic_coverage.py ... -> baseline Phase45 hits=0; current Phase45 hits=2`
- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `data/evaluation/phase45_spotcheck_sample.csv -> rows=30`

New terms:

- coverage evaluation：覆盖评估，用来判断新增语料是否带来新的检索命中。
- spotcheck sample：人工抽检样本表，用于核对标题、chunk、引用、图片描述和检索命中。
- noise：低质量解析或错误元数据导致的检索干扰。

Outcome:

- Phase 15 完成。新增语料已有可观测覆盖增量，Stage 30 不退化，但 review queue 和标题/年份元数据仍是云端发布前的核心人工核验点。下一步进入 Phase 16：本地黄金语料库迁移到云端 PostgreSQL 准备。

### Phase 16：本地黄金语料库迁移到云端 PostgreSQL 准备

- **Status:** complete (readiness only)
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决云端迁移前的本地 readiness 问题：确认迁移表、排除表、行数、content_hash 覆盖率、重复 hash、embedding 维度和 image_description embedding 状态。
- 现在做它，是因为 Phase 15 已完成覆盖评估，但用户人工核验尚未完成；因此只能做准备和校验，不能执行真实云端迁移。

Actions taken:

- 新增 `scripts/prepare_phase45_cloud_migration.py`，只读本地 SQLite，输出迁移 readiness JSON。
- 生成 `data/incoming/phase45_literature/phase16_migration_readiness.json`。
- 明确真实迁移仍使用既有 `scripts/migrate_sqlite_to_postgres.py`，迁移表为 documents/sources/chunks/chunk_embeddings/qa_logs。

Verification:

- `python scripts/prepare_phase45_cloud_migration.py --db-path data/app.sqlite --audit data/incoming/phase45_literature/phase12_quality_audit.csv --output data/incoming/phase45_literature/phase16_migration_readiness.json`
- readiness 摘要：`documents=1055`，`sources=982`，`chunks=32276`，`chunk_embeddings=51605`，`documents_missing_content_hash=0`，`duplicate_content_hash_groups=0`，`paratera_glm_bad_dimension_rows=0`，`image_description_embeddings=51`。

New terms:

- readiness report：迁移前体检报告，用于判断是否满足执行条件。
- excluded tables：明确不迁移的表，本阶段为 users、conversations、messages。
- authorized migration：用户人工核验并授权后才执行的真实云端迁移。

Outcome:

- Phase 16 完成准备态。未执行真实 PostgreSQL 迁移，未复制本地 FAISS 到云端，等待用户人工核验和云端授权。下一步进入 Phase 17：云端文件资产同步、FAISS 重建与生产 smoke 准备 + 文档/Obsidian 收尾。

### Phase 17：云端文件资产同步、FAISS 重建与生产 smoke 准备 + 文档/Obsidian 收尾

- **Status:** complete before human verification
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本 Phase 解决本地黄金语料库如何安全进入云端发布前状态的问题：先生成 raw PDF、提取图片、数据库迁移、云端 FAISS 重建和 smoke 的可执行清单，而不是在未经人工核验时直接操作服务器。
- 现在做它，是因为 Phase 16 已确认本地 SQLite 迁移 readiness，但真实云端 PostgreSQL、服务器文件资产同步和生产 smoke 都必须等待用户授权。

Actions taken:

- 新增 `scripts/prepare_phase45_cloud_asset_sync.py`，生成只读的云端资产同步 manifest。
- 生成 `data/incoming/phase45_literature/phase17_asset_sync_manifest.json`，列出 20 份候选 PDF 与 51 张提取图片，缺失数均为 0。
- 在 manifest 中记录待授权数据库迁移命令、云端 FAISS 重建命令和 smoke checklist。
- 更新普通文档和 Obsidian Phase 10-17 小汇报。

Verification:

- `python scripts/prepare_phase45_cloud_asset_sync.py --db-path data/app.sqlite --audit data/incoming/phase45_literature/phase12_quality_audit.csv --output data/incoming/phase45_literature/phase17_asset_sync_manifest.json -> raw_pdf_files=20 extracted_image_files=51 missing=0`
- 全量测试与最终 `git status -sb` 在阶段收尾命令中复核。

New terms:

- asset sync manifest：文件资产同步清单，说明哪些本地 PDF 和图片需要复制到服务器对应路径。
- smoke checklist：生产环境轻量核验清单，包括 `/health`、关键词/向量/混合检索、Agent 问答和 image_description 检索。
- human verification gate：人工核验闸门，未通过前不执行真实云端迁移、文件同步、提交、tag、push 或 PR。

Outcome:

- Phase 17 完成到“待人工核验/待授权执行”状态。阶段 45 追加工作已收束：新增 458 篇文献完成本地清单化、SQLite 导入、去重、质量审计、候选索引、多模态处理、覆盖评估、云端迁移准备和文档/Obsidian 草稿收尾。

### Phase 18-20：新增文献质量修复、候选集扩容与发布前重算

- **Status:** complete before human verification
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Phase purpose:

- 本追加阶段解决 Claude 复核指出的三个质量问题：低价值图片未完全过滤、标题/年份元数据误判过严、少量图片方向异常。
- 现在做它，是因为只有完成这些提纯动作，后续大批量导入/上云才不会把 QR、logo、错误标题和 deterministic 模板描述扩大成生产噪声。

Actions taken:

- 新增 `scripts/clean_phase45_low_value_images.py` 与 `tests/test_stage45_image_quality_cleanup.py`。
- 增强 `scripts/audit_phase45_import_quality.py` 的标题/年份修复规则，并重跑 Phase 12 audit。
- 删除低价值 image_description chunks 和 deterministic 模板 image_description chunks。
- 扩容候选集后重建 text embeddings、image embeddings、FAISS、覆盖评估、migration readiness 和 asset sync manifest。

Verification:

- `python -m pytest tests/test_stage45_image_quality_cleanup.py tests/test_stage45_quality_audit.py -q -> 3 passed`
- `python scripts/audit_phase45_import_quality.py ... -> cloud_candidate=235 review_required=89`
- `python scripts/index_phase45_cloud_candidates.py --chunk-type text -> total_chunks=2660 indexed_chunks=2441 skipped_chunks=219`
- `python scripts/build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 --output-dir data/faiss -> vectors=22006`
- `python scripts/evaluate_phase45_domestic_coverage.py ... -> current Phase45 total hits=11`
- `python scripts/prepare_phase45_cloud_asset_sync.py ... -> raw_pdf_files=235 extracted_image_files=46 missing=0`

Outcome:

- 新增文献本地黄金语料库从“链路跑通”提升到“可大批量导入前的质量修复状态”。真实云端迁移、服务器文件同步和生产 smoke 仍需用户人工核验与授权。

### Phase 21：全库 PDF 前 100 篇图片解析样本

- **Status:** sample complete with 14 retry candidates
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

#### 2026-06-18 智谱官方 endpoint 续跑更新

- 智谱官方 GLM-4.6V endpoint 续跑上一轮失败的 77 篇文档后，成功处理 63 篇，失败 14 篇；本轮新增提取图片 535 张、创建 image_description chunks 515 个、跳过 20 张图片。
- 合并第一轮和本轮续跑后，前 100 篇 PDF 样本中已有 86 篇完成真实视觉解析；剩余 14 篇中 13 篇为 `provider_timeout`，1 篇为 `image_pixmap_conversion_failed`。
- 二次低价值图片清理删除 48 个 QR/logo/低信息量 image_description chunks；当前全库保留 `image_description` chunks=744。
- 已为全部 744 个 image_description chunks 生成 GLM-Embedding-3 embedding，并重建本地 FAISS，vectors=22704。
- `scripts/process_multimodal.py` 已增加 `--document-ids-file` 和默认 checkpoint 输出；传入 `--output-dir` 时每完成一篇会刷新 CSV/JSON，后续大批量处理断线后可从已失败/未完成 document_id 继续。
- 验证：`python -m pytest tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_quality_cleanup.py tests/test_stage45_candidate_indexing.py -q -> 10 passed`；`python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`；`python -m pytest -q -> 928 passed`。
- 继续补跑原 14 篇失败样本后，最新 100 篇样本状态为 98 篇 processed、2 篇 failed；失败拆分为 document_id=20 的 `provider_timeout` 和 document_id=187 的 `image_pixmap_conversion_failed`。
- document_id=140 在专项补跑中成功，新增提取图片 110 张、创建 image_description chunks 80 个、跳过 30 张；随后完成低价值图片清理、image_description embedding 补齐与 FAISS 重建。
- `PdfImageExtractor` 已改为单张坏图转换失败时跳过并继续处理同篇 PDF，减少全库批处理被坏图阻断的风险。
- 最终样本评估：100 篇样本中 98 篇完成，879 个 image_description chunks 均有 embedding，低价值 remove 候选为 0，图表型向量查询 5 个中 3 个召回 image_description 且为 Top1，质量门槛通过。
- 当前停止在全库分类前：已生成 `data/incoming/phase45_literature/phase21_final_sample_stats/next_import_channel_plan.md`，建议下一步先按 PDF 图像数量、历史超时、提取异常、已完成状态分类，再分队列并发导入。

### Phase 22：未入库文献补入与三路 staging 多模态验证

- **Status:** staging channel validated; ready for larger batch rollout
- **Started:** 2026-06-18

Actions taken:

- 核对三个本地文献目录：`papers_0616`、`papers_0618`、`papers_0609` 合计 932 个文献文件，去重后唯一 hash=832。
- 新增 `scripts/build_phase45_missing_literature_manifest.py`，生成未入库唯一文件 manifest；缺口为 125 个唯一文件，其中 124 个 ready PDF、1 个 CAJ/不可读。
- 备份 SQLite 后导入 missing manifest：91 篇成功入库，33 篇 empty，1 篇 skipped_not_ready，新增 text chunks=957。
- 运行 missing 批次质量审计：cloud_candidate=69，review_required=55，suspected_scanned=33。
- 为新增 69 篇候选生成 text embeddings：723 个 chunks；重建 FAISS 后 vectors=23700。
- 测试三路 API：官方 GLM 单路成功、官方同 key 双路并发成功、Paratera 单路成功。
- 直接三进程写 SQLite 小批量验证失败，官方 A/B 均触发 `database is locked`；确认多进程并发写同一个 SQLite 不可行。
- 新增两段式 staging 通道：`process_multimodal_to_staging.py` 并发识别图片文本但不写 DB，`import_multimodal_staging.py` 单进程串行合并入库。
- 三路 staging 小批量验证通过：官方 A 描述 10 张，官方 B 描述 19 张，Paratera C 本批 21 张均为 skipped_existing；串行合并创建 29 个 image_description chunks。
- 清理低价值图片、补 image_description embeddings、重建 FAISS 后 vectors=23748。
- 重新分类未完成多模态队列：PDF=853，已完成多模态文档=142，未完成=711，official_a/official_b/paratera_c 各 237。

Verification:

- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 15 passed`
- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`

Next:

- 下一步应按 staging 通道扩大批次，而不是直接三进程写 SQLite。建议每队先放大到 20 篇，三路并发生成 staging，然后串行合并、清理、embedding、FAISS，再继续放大全库。

### Phase 25：三路 staging 每队 20 篇放大验证

- **Status:** complete; ready for next larger batch
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Actions taken:

- 基于 `phase24_queue_after_staging_probe` 生成三路各 20 篇队列，跳过已知 timeout/异常专项编号。
- 三路并发生成 staging：official_b 与 paratera_c 完整完成，official_a 通过 checkpoint 保留成功 rows 后因长尾无进展停止。
- 串行合并三路 staging 入 SQLite：created_chunks=312。
- 运行低价值图片清理：删除 35 个低价值 image_description chunks。
- 补 image_description embeddings：indexed_chunks=277，skipped_chunks=1065。
- 重建 FAISS：vectors=24025。
- 重新分类队列：PDF=853，已完成多模态文档=188，未完成=665。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 15 passed`

Next:

- 下一轮可继续用 staging 通道放大批次。建议每队 30-50 篇，但保留 checkpoint；对于长尾停滞的官方路，按 checkpoint 收束，不阻塞其他队列。

### Phase 26：三路 staging 每队 30 篇放大验证

- **Status:** complete; stop before larger rollout for timeout queue planning
- **Started:** 2026-06-18
- **Completed:** 2026-06-18

Actions taken:

- 基于 `phase25_queue_after_batch20` 生成三路各 30 篇队列，继续跳过已知 timeout/异常专项编号。
- 三路并发运行 staging；三路均触发 30 分钟命令超时，确认后台进程属于本批任务后停止，保留已写出的 checkpoint/CSV。
- 串行合并三路 staging 入 SQLite：staging_rows=442，described_rows=436，created_chunks=436。
- 运行低价值图片清理：删除 27 个低价值 image_description chunks。
- 补 image_description embeddings：indexed_chunks=409，skipped_chunks=1342。
- 重建 FAISS：vectors=24434。
- 重新分类队列：PDF=853，已完成多模态文档=235，未完成=618，official_a/official_b/paratera_c 各 206。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 15 passed`

Next:

- 先对剩余 618 篇按编号继续分队，但要额外建立 timeout/long-tail 队列；主批次建议缩小到每队 15-20 篇或加入单文档超时隔离，避免慢文档占住整个批次。

Phase purpose:

- 本 Phase 解决“不要只跑新增候选集，而要面向全库 PDF 估算多模态处理效果”的问题。
- 现在做它，是因为本地库已有 762 篇 PDF，后续全量多模态导入前需要先用 100 篇样本估算图片数量、失败率、低价值图片比例和模型资源消耗。

Actions taken:

- 扩展 `scripts/process_multimodal.py`，支持 `--limit 100`、`--only-existing-files` 和结果 CSV/JSON。
- 从全库 762 篇本地 PDF 中按 document id 选择前 100 篇样本。
- 使用 GLM-4.6V 真实解析图片，跳过 embedding，避免每篇重复重建索引。
- 清理低价值图片描述并脱敏错误 CSV。

Verification:

- `python -m pytest tests/test_stage45_process_multimodal_script.py tests/test_stage45_multimodal_pipeline.py -q -> 3 passed`
- `python scripts/process_multimodal.py --limit 100 --only-existing-files --skip-embeddings ... -> selected_documents=100 processed_documents=23 failed_documents=77 extracted_images=160 created_chunks=160`
- `python scripts/clean_phase45_low_value_images.py ... --apply -> total_image_chunks=226 remove_candidates=21 kept_chunks=203 review_candidates=2`

Outcome:

- 100 篇样本没有完整跑完：平台返回 `provider_quota_exhausted`，导致后续 77 篇真实视觉解析失败；embedding 阶段也被同一资源包问题阻断。
- 当前可观察效果：23 篇完成真实视觉解析，160 个图片描述经清理后净增 139 个有效 image_description chunks；全库有效 image_description chunks=205。

### Phase 27：隔离已知失败后的三路 staging 每队 20 篇验证

- **Status:** complete; isolated batch-20 path is stable
- **Started:** 2026-06-18
- **Completed:** 2026-06-19

Actions taken:

- 给 `scripts/classify_phase45_unfinished_multimodal_queues.py` 增加 `--isolate-known-failures`，把 timeout 和 non-timeout failed 文档输出到专项清单。
- 给 staging/queue 通道增加文档级完成证据：`processed_document_ids.txt`、`failed_document_ids.txt`、`no_image_document_ids.txt`，并支持 `--include-staging-processed` 自动扫描。
- 从隔离后的主队列生成三路各 20 篇，三路均完整完成。
- 串行合并 staging 入 SQLite：staging_rows=211，described_rows=208，created_chunks=208。
- 清理低价值图片：删除 33 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=175，skipped_chunks=1751。
- 重建 FAISS：vectors=24609。
- 重新分类队列：PDF=853，extra_completed=60，未完成=558，主队列=556。

Verification:

- `python -m pytest tests/test_stage45_queue_feasibility.py tests/test_stage45_multimodal_staging.py -q -> 6 passed`

Next:

- 后续分类应默认使用 `--include-staging-processed`，否则无有效图片文档会被重复处理。

### Phase 28：partial staging 入库与半处理文档队列保护

- **Status:** complete; partial import works and does not mark documents complete
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 给分类脚本增加 `--partial-document-ids-file` 与 `--include-staging-partial`，半处理文档不因已有部分 image_description chunk 被误判为完成。
- 从 Phase27 后主队列再取三路各 20 篇，三路均在 30 分钟窗口触发长尾超时，停止后台进程后保留 checkpoint/CSV。
- 将 checkpoint 中出现过 rows 的 12 篇写入 `partial_document_ids.txt`。
- 串行合并 partial staging 入 SQLite：staging_rows=159，described_rows=156，created_chunks=156。
- 清理低价值图片：删除 22 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=134，skipped_chunks=1926。
- 重建 FAISS：vectors=24743。
- 重新分类队列：PDF=853，extra_completed=60，partial=12，未完成=558，主队列=556。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 18 passed`

Next:

- 下一步应改用更细粒度的续跑策略：对 partial 文档优先单文档或每队 3-5 篇续跑；普通主队列继续每队 10-15 篇。每轮都使用 `--include-staging-processed --include-staging-partial` 重算队列。

### Phase 29：单文档图片上限续跑验证

- **Status:** complete; capped continuation is ready for broader rollout
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 给 `scripts/process_multimodal_to_staging.py` 增加 `--max-new-images-per-document`，可限制每篇 PDF 单轮处理的新图片数量；超过上限的文档写入 `partial_document_ids.txt`。
- 从 partial-aware 队列取三路各 3 篇，设置 `--max-new-images-per-document 20`。
- 三路 staging 全部完成：official_a described_images=2、official_b described_images=1、paratera_c described_images=0，合计 skipped_existing_images=16。
- 串行合并 staging 入 SQLite：staging_rows=19，described_rows=3，created_chunks=3。
- 清理低价值图片：删除 1 个 image_description chunk。
- 补 image_description embeddings：indexed_chunks=2，skipped_chunks=2060。
- 重建 FAISS：vectors=24745。
- 重新分类队列：PDF=853，extra_completed=69，partial=12，未完成=549，主队列=547。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 推荐下一轮采用两类队列：partial/large-image 队列每队 5 篇、`--max-new-images-per-document 20`；普通主队列每队 10-15 篇、也保留图片上限。每轮结束后必须串行 import、cleanup、embedding、FAISS、queue reclassify。

### Phase 30：三路每队 10 篇 capped 主批次

- **Status:** complete; continue with repeated capped passes
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase30_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均完整完成。
- official_a：extracted_images=237，described_images=138，skipped_existing_images=96，failed_images=3。
- official_b：extracted_images=175，described_images=157，skipped_existing_images=14，failed_images=4。
- paratera_c：extracted_images=168，described_images=156，skipped_existing_images=8，failed_images=4。
- 串行合并 staging 入 SQLite：staging_rows=580，described_rows=451，created_chunks=451。
- 清理低价值图片：删除 54 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=397，skipped_chunks=2062。
- 重建 FAISS：vectors=25142。
- 重新分类队列：PDF=853，extra_completed=77，partial=34，未完成=541，主队列=539。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续三路 capped pass。建议下一轮仍用每队 10 篇、每篇 20 张新图上限；如果耗时可接受，再尝试每队 12-15 篇。partial 数量上升是预期现象，代表大图 PDF 正在被分片处理。

### Phase 31：三路每队 12 篇 capped partial 批次

- **Status:** complete as partial import; batch size 12 is too slow for current window
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase31_queue_start` 生成三路各 12 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging；三路均触发 30 分钟命令超时。
- 停止本轮后台进程，保留 checkpoint/CSV，并将出现过 rows 的文档写入 `partial_document_ids.txt`。
- checkpoint 结果：official_a described_images=158、official_b described_images=214、paratera_c described_images=180。
- 串行合并 partial staging 入 SQLite：staging_rows=945，described_rows=552，created_chunks=552。
- 清理低价值图片：删除 80 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=472，skipped_chunks=2459。
- 重建 FAISS：vectors=25614。
- 重新分类队列：PDF=853，extra_completed=77，partial=40，未完成=541，主队列=539。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 主批次不要继续放大到每队 12。建议回到每队 10 篇、每篇 20 张新图上限；同时增加 partial 专项小批量续跑，逐步把 partial 文档消化成 completed。

### Phase 32：三路每队 10 篇 capped 稳态续跑

- **Status:** complete; batch-10 remains the stable operating point
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase32_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均完整完成。
- official_a：extracted_images=481，described_images=184，skipped_existing_images=294，failed_images=3。
- official_b：extracted_images=503，described_images=182，skipped_existing_images=320，failed_images=1。
- paratera_c：extracted_images=428，described_images=190，skipped_existing_images=229，failed_images=9。
- 串行合并 staging 入 SQLite：staging_rows=1412，described_rows=556，created_chunks=556。
- 清理低价值图片：删除 90 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=466，skipped_chunks=2931。
- 重建 FAISS：vectors=26080。
- 重新分类队列：PDF=853，extra_completed=81，partial=42，未完成=537，主队列=535。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass，不再上调到 12；如果要提高 completed 文档下降速度，应额外跑 partial 专项小批量，而不是扩大主批次。

### Phase 33：三路每队 10 篇 capped 大图续跑

- **Status:** complete; stable image-level coverage expansion
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase33_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均完整完成。
- official_a：extracted_images=682，described_images=194，skipped_existing_images=483，failed_images=5。
- official_b：extracted_images=561，described_images=196，skipped_existing_images=361，failed_images=4。
- paratera_c：extracted_images=571，described_images=195，skipped_existing_images=371，failed_images=5。
- 串行合并 staging 入 SQLite：staging_rows=1814，described_rows=585，created_chunks=585。
- 清理低价值图片：删除 95 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=490，skipped_chunks=3397。
- 重建 FAISS：vectors=26570。
- 重新分类队列：PDF=853，extra_completed=82，partial=45，未完成=536，主队列=534。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass。若要更快消化 partial，可另开 partial-only 队列，每队 3-5 篇、仍保留 20 张新图上限。

### Phase 34：三路每队 10 篇 capped partial 消化

- **Status:** complete; batch-10 remains stable and document completion improved
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase34_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均完整完成。
- official_a：extracted_images=723，described_images=156，skipped_existing_images=566，failed_images=1。
- official_b：extracted_images=738，described_images=191，skipped_existing_images=543，failed_images=4。
- paratera_c：extracted_images=710，described_images=188，skipped_existing_images=518，failed_images=4。
- 串行合并 staging 入 SQLite：staging_rows=2171，described_rows=535，created_chunks=535。
- 清理低价值图片：删除 100 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=435，skipped_chunks=3887。
- 重建 FAISS：vectors=27005。
- 重新分类队列：PDF=853，extra_completed=87，partial=46，未完成=531，主队列=529。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass。当前信号显示 partial 文档开始被消化，未完成 PDF 本轮下降 5；保持该节奏比放大批次更稳。

### Phase 35：三路每队 10 篇 capped 队列推进

- **Status:** complete; batch-10 stable, staging sanity check caught one env issue
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase35_queue_start` 生成三路各 10 篇队列。
- official_a/official_b 首轮因运行时环境变量注入不完整快速失败；入库前检查 summary 后重跑两路，最终结果正常。
- official_a：extracted_images=784，described_images=182，skipped_existing_images=598，failed_images=4。
- official_b：extracted_images=757，described_images=178，skipped_existing_images=576，failed_images=3。
- paratera_c：extracted_images=689，described_images=171，skipped_existing_images=516，failed_images=2。
- 串行合并 staging 入 SQLite：staging_rows=2230，described_rows=531，created_chunks=531。
- 清理低价值图片：删除 121 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=410，skipped_chunks=4322。
- 重建 FAISS：vectors=27415。
- 重新分类队列：PDF=853，extra_completed=93，partial=48，未完成=525，主队列=523。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass；每轮入库前先看 staging summary，避免把异常 provider/env 失败当作真实文档失败。

### Phase 36：三路每队 10 篇 capped partial 持续消化

- **Status:** complete; batch-10 stable and partial queue keeps moving
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase36_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均正常完成。
- official_a：extracted_images=910，described_images=180，skipped_existing_images=725，failed_images=5。
- official_b：extracted_images=860，described_images=163，skipped_existing_images=696，failed_images=1。
- paratera_c：extracted_images=682，described_images=191，skipped_existing_images=489，failed_images=2。
- 串行合并 staging 入 SQLite：staging_rows=2452，described_rows=534，created_chunks=534。
- 清理低价值图片：删除 133 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=401，skipped_chunks=4732。
- 重建 FAISS：vectors=27816。
- 重新分类队列：PDF=853，extra_completed=100，partial=51，未完成=518，主队列=516。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass。当前队列已推进到 1070 段，说明前段大图 partial 文档正在持续被消化。

### Phase 37：三路每队 10 篇 capped 收尾推进

- **Status:** complete; partial digestion is accelerating
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase37_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均正常完成。
- official_a：extracted_images=1009，described_images=164，skipped_existing_images=841，failed_images=4。
- official_b：extracted_images=825，described_images=187，skipped_existing_images=633，failed_images=5。
- paratera_c：extracted_images=696，described_images=163，skipped_existing_images=528，failed_images=5。
- 串行合并 staging 入 SQLite：staging_rows=2530，described_rows=514，created_chunks=514。
- 清理低价值图片：删除 121 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=393，skipped_chunks=5133。
- 重建 FAISS：vectors=28209。
- 重新分类队列：PDF=853，extra_completed=109，partial=54，未完成=509，主队列=507。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass。skipped_existing 已超过 2000，说明前段大图文档接近完成，后续 completed 下降可能会继续改善。

### Phase 38：三路每队 10 篇 capped 稳定推进

- **Status:** complete; approaching sub-500 unfinished PDFs
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase38_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均正常完成。
- official_a：extracted_images=900，described_images=172，skipped_existing_images=726，failed_images=2。
- official_b：extracted_images=891，described_images=192，skipped_existing_images=695，failed_images=4。
- paratera_c：extracted_images=658，described_images=157，skipped_existing_images=498，failed_images=3。
- 串行合并 staging 入 SQLite：staging_rows=2449，described_rows=521，created_chunks=521。
- 清理低价值图片：删除 132 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=389，skipped_chunks=5526。
- 重建 FAISS：vectors=28598。
- 重新分类队列：PDF=853，extra_completed=115，partial=59，未完成=503，主队列=501。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass；下一轮若保持当前趋势，未完成 PDF 有望跌破 500。

### Phase 39：三路每队 10 篇 capped 跌破 500

- **Status:** complete; unfinished PDF count is now below 500
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase39_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均正常完成。
- official_a：extracted_images=928，described_images=185，skipped_existing_images=740，failed_images=3。
- official_b：extracted_images=865，described_images=163，skipped_existing_images=700，failed_images=2。
- paratera_c：extracted_images=754，described_images=186，skipped_existing_images=564，failed_images=4。
- 串行合并 staging 入 SQLite：staging_rows=2547，described_rows=534，created_chunks=534。
- 清理低价值图片：删除 142 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=392，skipped_chunks=5915。
- 重建 FAISS：vectors=28990。
- 重新分类队列：PDF=853，extra_completed=123，partial=63，未完成=495，主队列=493。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass。当前已经跌破 500，后续重点是继续稳定清理剩余主队列，并最终单独处理 timeout/non-timeout failed 专项。

### Phase 40：三路每队 10 篇 capped 稳定清库

- **Status:** complete; stable clearing continues below 500 unfinished PDFs
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase40_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均正常完成。
- official_a：extracted_images=930，described_images=193，skipped_existing_images=733，failed_images=4。
- official_b：extracted_images=926，described_images=173，skipped_existing_images=749，failed_images=4。
- paratera_c：extracted_images=619，described_images=182，skipped_existing_images=434，failed_images=3。
- 串行合并 staging 入 SQLite：staging_rows=2475，described_rows=548，created_chunks=548。
- 清理低价值图片：删除 133 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=415，skipped_chunks=6307。
- 重建 FAISS：vectors=29405。
- 重新分类队列：PDF=853，extra_completed=129，partial=68，未完成=489，主队列=487。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass，后续在主队列接近清完后单独处理 timeout/non-timeout failed 专项。

### Phase 41：三路每队 10 篇 capped 主队列持续下降

- **Status:** complete; unfinished PDF count continues to decline
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase41_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均正常完成。
- official_a：extracted_images=1046，described_images=167，skipped_existing_images=878，failed_images=1。
- official_b：extracted_images=823，described_images=175，skipped_existing_images=646，failed_images=2。
- paratera_c：extracted_images=748，described_images=181，skipped_existing_images=567，failed_images=0。
- 串行合并 staging 入 SQLite：staging_rows=2617，described_rows=523，created_chunks=523。
- 清理低价值图片：删除 127 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=396，skipped_chunks=6722。
- 重建 FAISS：vectors=29801。
- 重新分类队列：PDF=853，extra_completed=137，partial=70，未完成=481，主队列=479。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass；当前主队列还有 479 篇，后续仍按稳定参数推进。

### Phase 42：三路每队 10 篇 capped FAISS 破三万

- **Status:** complete; FAISS vectors passed 30000 and queue dropped by 10
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase42_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均正常完成。
- official_a：extracted_images=1028，described_images=163，skipped_existing_images=863，failed_images=2。
- official_b：extracted_images=695，described_images=160，skipped_existing_images=530，failed_images=5。
- paratera_c：extracted_images=627，described_images=170，skipped_existing_images=454，failed_images=3。
- 串行合并 staging 入 SQLite：staging_rows=2350，described_rows=493，created_chunks=493。
- 清理低价值图片：删除 136 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=357，skipped_chunks=7118。
- 重建 FAISS：vectors=30158。
- 重新分类队列：PDF=853，extra_completed=147，partial=71，未完成=471，主队列=469。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass。当前主队列还有 469 篇，队列下降趋势稳定。

### Phase 43：三路每队 10 篇 capped 主队列加速下降

- **Status:** complete; queue clearing speed improved
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase43_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging，三路均正常完成。
- official_a：extracted_images=812，described_images=180，skipped_existing_images=630，failed_images=2。
- official_b：extracted_images=906，described_images=162，skipped_existing_images=740，failed_images=4。
- paratera_c：extracted_images=585，described_images=148，skipped_existing_images=433，failed_images=4。
- 串行合并 staging 入 SQLite：staging_rows=2303，described_rows=490，created_chunks=490。
- 清理低价值图片：删除 143 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=347，skipped_chunks=7475。
- 重建 FAISS：vectors=30505。
- 重新分类队列：PDF=853，extra_completed=158，partial=75，未完成=460，主队列=458。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass。当前主队列 458 篇，下降速度已进入 10 篇/轮附近。

### Phase 44：三路 capped partial 收束与主队列大幅下降

- **Status:** complete; partial checkpoint imported and main queue dropped sharply
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Actions taken:

- 基于 `phase44_queue_start` 生成三路各 10 篇队列。
- 使用 `--max-new-images-per-document 20` 运行三路 staging。
- official_a 触发 30 分钟窗口超时，停止后台进程后将 checkpoint 出现过 rows 的文档写入 `partial_document_ids.txt`。
- official_b 与 paratera_c 正常完成，并写入 `processed_document_ids.txt`。
- official_a checkpoint：described_images=153，skipped_existing_images=653，failed_images=7。
- official_b：described_images=167，skipped_existing_images=547，failed_images=7。
- paratera_c：described_images=176，skipped_existing_images=433，failed_images=2。
- 串行合并 staging 入 SQLite：staging_rows=2145，described_rows=496，created_chunks=496。
- 清理低价值图片：删除 131 个 image_description chunks。
- 补 image_description embeddings：indexed_chunks=365，skipped_chunks=7822。
- 重建 FAISS：vectors=30870。
- 重新分类队列：PDF=853，extra_completed=178，partial=76，未完成=440，主队列=438。

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_queue_feasibility.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_candidate_indexing.py -q -> 19 passed`

Next:

- 继续 batch-10 capped pass。若某一路超时，继续按 checkpoint/partial 策略收束，不阻塞其他完成路。

### Phase 45：吞吐诊断与三路并发实测

- **Status:** complete; bottleneck measured before resuming larger multimodal batches
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Phase purpose:

- 本 Phase 解决“多 API 并发为什么没有明显提速”的可观测性问题。之前只能看到每批处理了多少文档/图片，无法拆开 PDF 提取、视觉 API、staging/import、embedding 和实际并发峰值。
- 现在做它，是因为继续盲目扩大批量可能只会增加超时和重复扫描成本；必须先用小批量真实探针确定瓶颈，再决定下一步优化方向。

Actions taken:

- 停止上次中断后仍在后台运行的三路真实视觉处理进程。
- 为 `scripts/process_multimodal_to_staging.py` 增加 `multimodal_timing.csv`，记录 `extract_document`、`describe_image` 和 `staging_run` 的开始时间、结束时间、耗时、provider 标签和状态。
- 为 `scripts/import_multimodal_staging.py` 与 `scripts/index_phase45_cloud_candidates.py` 增加 `elapsed_seconds`。
- 新增 `scripts/analyze_phase45_throughput.py` 与 `tests/test_stage45_throughput_analysis.py`。
- 生成 `data/incoming/phase45_literature/phase45_throughput_queue_start/`，确认当前 all_pdf=853、unfinished=440、main_queue=438。
- 运行三路小批量探针：official_a / official_b / paratera_c 各取 2 篇、每篇最多 5 张新图。
- 将探针 staging 串行导入 SQLite，补齐新增 image_description embeddings，并重建 FAISS。

Diagnostic results:

- extracted_images=744，skipped_existing_images=714，api_attempted_images=30，successful_descriptions=30，failed_descriptions=0。
- avg_api_ms=6030.179，p50_api_ms=3952.611，p90_api_ms=12285.779，p95_api_ms=17974.331。
- provider success/avg：official_a=10/10, 6535.103ms；official_b=10/10, 2517.972ms；paratera_c=10/10, 9037.462ms。
- pdf_extract_total_seconds=38.116，api_call_total_seconds=180.905，staging_total_seconds=219.06，import_total_seconds=0.405，embedding_total_seconds=3.285。
- concurrency_peak=3，说明当前架构的真实视觉 API 并发峰值就是三路进程各一个串行调用。
- FAISS 重建后 vectors=30900。

Verification:

- `python -m pytest tests/test_stage45_multimodal_staging.py tests/test_stage45_candidate_indexing.py tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_extractor.py tests/test_stage45_throughput_analysis.py -q -> 17 passed`
- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- exact API key string scan returned no repository hits.

Next:

- 不建议直接放大全库批量。下一步应先做 image-level remaining manifest/cache，避免重复提取 700+ 已处理图片；再做受控 provider 内并发 worker 和限流退避，目标是把 concurrency_peak 从 3 提到可验证的 6-9，同时保持失败率可控。

### Phase 46: image-level remaining manifest, five-route concurrency, and full PDF image coverage

- **Status:** complete; stopped before human verification
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Phase purpose:

- This phase replaced document-level repeated multimodal passes with image-level remaining manifests, then used controlled five-route GLM-4.6V concurrency to finish nearly all remaining PDF images.

Actions taken:

- Added `scripts/build_phase45_remaining_image_manifest.py`.
- Extended `scripts/process_multimodal_to_staging.py` with image-manifest mode, worker support, provider labels, timing output, and robust atomic checkpoint writes.
- Verified a five-route real-provider probe, then ran two large queues and one all-PDF residual queue.
- Imported all successful staging rows serially into SQLite, generated GLM-Embedding-3 embeddings for every new `image_description` chunk, and rebuilt FAISS after each large batch.
- Generated final pending queue files under `data/incoming/phase45_literature/phase45_remaining_images_all_pdf_after_resume2/`, including `pending_images_12.csv` and `pending_images_12_summary.json`.

Final results:

- All-PDF scan: 853 PDF documents, 14968 valid extracted images.
- Completed images: 14956 with real vision description, `image_description` chunk, embedding, and FAISS vector.
- Pending images: 12 across 9 documents; left for later timeout/error-specific handling.
- Current DB vector state: `image_description_chunks=14956`, `image_description_embeddings=14956`, `total_embeddings=69655`.
- Final FAISS rebuild: vectors=37639.

Verification:

- `python -m pytest -q -> 944 passed`
- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python scripts/run_production_smoke.py -> rows=11 execute=false failed=0`

Next:

- Do not rerun the 14956 completed images. Use the final pending queue for any follow-up retry.
- Review low-value image cleanup candidates before applying deletion: latest review found 792 remove candidates and 85 review candidates.
- No git add/commit/tag/push/PR has been performed.

### Phase 47: low-value image cleanup and orientation repair

- **Status:** complete; stopped before human verification
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Phase purpose:

- This phase responds to human review findings: clear low-value image chunks should be removed, and side/rotated/inverted extracted images should be corrected to match the PDF page display.

Actions taken:

- Applied `scripts/clean_phase45_low_value_images.py --apply` and deleted 792 low-value `image_description` chunks plus their embeddings.
- Added `scripts/fix_phase45_orientation_images.py` to re-render affected images from their PDF page display rectangle, avoiding raw embedded-image rotation/mirror artifacts.
- Re-rendered all three images under `data/images/1318` after the user identified the whole folder as inverted.
- Re-rendered 83 of 85 global orientation-review images; restored the 2 failed document 421 files from backup and removed their low-information chunks/embeddings.
- Re-described 86 repaired images with GLM-4.6V, updated existing chunks with `--update-existing`, regenerated the 86 embeddings, and rebuilt FAISS.
- Ran a post-cleanup review, deleted 4 residual remove candidates, and rebuilt FAISS again.

Final results:

- `image_description_chunks=14158`
- `image_description_embeddings=14158`
- `total_embeddings=68857`
- `FAISS vectors=36841`

Verification:

- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- `python -m pytest -q -> 944 passed`

Notes:

- The code had not deliberately flipped images left/right. The artifact came from extracting raw PDF image xrefs rather than rendering the image as it appears on the PDF page.
- Backups for repaired images are under `data/incoming/phase45_literature/phase45_orientation_fix_*`.
- No git add/commit/tag/push/PR has been performed.

### Phase 48: image evidence response wiring and frontend figure cards

- **Status:** complete; stopped before human verification
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Phase purpose:

- This phase fixes the product gap where multimodal image descriptions were searchable but the Agent UI still rendered only text citations. The goal is to show real PDF-extracted figures when retrieved `image_description` chunks are part of the answer evidence.

Actions taken:

- Propagated `chunk_type` and `source_image_path` from keyword/vector/hybrid retrieval results into Agent search results and source references.
- Added safe `image_url` derivation for paths under `data/images/` and exposed local images through `/assets/images`.
- Added frontend figure evidence cards below Agent answers and image previews in the citation drawer.
- Kept the display limited to deduplicated image-description sources, preferring cited image sources and capping visible figures at 4.
- Restarted the local agent on `http://127.0.0.1:8000`.

Verification:

- `node --check app/frontend/static/app.js -> passed`
- `python -m pytest tests/test_agent_api.py tests/test_tool_calling_agent_service.py tests/test_frontend_app.py tests/test_stage45_multimodal_pipeline.py tests/test_stage45_multimodal_staging.py -q -> 59 passed`
- `python -m pytest -q -> 944 passed`
- `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`
- Static image smoke: `/assets/images/1059/page10_img1.png -> 200`; `/assets/images/442/page156_img1.png -> 200`
- Agent smoke: `/agent/query` for `堆石混凝土施工流程图` returned 8 sources with 8 `image_url` values.

Next:

- User should refresh the browser and ask the same figure-oriented question again. No git add/commit/tag/push/PR has been performed.

### Phase 49: figure lightbox, same-document figure fallback, and submit readiness

- **Status:** complete; user authorized submit/tag/push/merge
- **Started:** 2026-06-19
- **Completed:** 2026-06-19

Phase purpose:

- This phase closes the last product polish items from manual review: enlarged figures should stay on the current page, cards should use reader-facing figure numbering instead of chunk labels, and image evidence should still appear when the top-k answer evidence is text-only but the same cited paper has relevant image-description chunks.

Actions taken:

- Added an in-page figure lightbox with a close button, backdrop close, and `Escape` close.
- Changed figure cards to display `Figure 1`, `Figure 2`, etc.; removed visible chunk ids and added source paper title plus derived page/image labels.
- Extended Agent response enrichment to append same-document figure evidence from `image_description` chunks when no image source is returned by top-k retrieval.
- Bumped frontend asset versions to `phase45-figure-lightbox-fix1`.

Verification:

- `node --check app/frontend/static/app.js -> passed`
- `python -m pytest tests/test_frontend_app.py tests/test_agent_api.py -q -> 39 passed`
- Local Agent smoke for `界面微观结构` returned 2 image sources; the corresponding `/assets/images/...` URLs returned HTTP 200.

Known deferred issue:

- Some PDF-extracted images can still be cropped or fragment-like in the answer cards. The user accepted leaving this for the next phase, where extraction/display quality filters should handle extreme aspect ratio and partial-region artifacts.

Next:

- Phase 45 can now be committed, tagged, pushed, merged to GitHub, and left on `main` after the merge.
