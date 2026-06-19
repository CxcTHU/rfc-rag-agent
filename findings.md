# 阶段 45 Findings：数据上云与多模态 RAG

## Requirements

- 主线 A：数据迁移，将本地 SQLite 存量数据（753 documents, 19,300 child chunks, 19,300 embeddings）增量迁移到云端 PostgreSQL。
- 主线 B：多模态 RAG，PDF 图像提取 → 视觉模型描述 → image_description chunk 入库 → 统一向量检索。
- Stage 30 评分不得低于 91.52 / A / pass。
- 不做跨会话长期记忆，不做用户画像/私人偏好记忆。
- 不把 summary 当作可引用资料来源。
- 不改变 Stage 30 评分规则、provider 拓扑或数据源边界。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、JWT secret、密码明文、供应商原始响应、raw_response、reasoning_content 写入 Git/CSV/文档/测试/Obsidian。

## Research Findings

### 数据迁移现状

- 云端 PostgreSQL 已由阶段 44 docker-compose.prod.yml 部署，Alembic schema 已 apply，但数据为空。
- 本地 SQLite 存量：documents=753, sources 多条, chunks=25,687（parent 6,402 + indexable child 19,300）, chunk_embeddings=19,300（paratera GLM-Embedding-3 2048-dim）, qa_logs 若干。
- FAISS 索引是本地文件（`data/faiss/paratera_GLM-Embedding-3_dim2048.index`），无法直接复制到 PostgreSQL 环境——需从 DB 中的 embedding_json 重建。
- 迁移不含 conversations（云端用户会新建）和 users（已通过注册创建）。

### PDF 解析与图像提取现状

- `app/services/ingestion/parser.py`：使用 `pypdf.PdfReader` 提取 PDF 文本，不提取图像。
- `app/services/ingestion/pdf_text.py`：deterministic 结构化后处理（标题识别、断词合并、页眉清洗），纯文本处理。
- `app/services/ingestion/splitter.py`：文本分块，chunk_size=800, overlap=120。
- 当前 Chunk 模型无 `chunk_type` 字段，所有 chunk 均为文本。
- PDF 原始文件存储在 `data/raw/` 目录，按 content_hash 命名。

### 图像提取技术选型

- **PyMuPDF（fitz）**：功能最全的 PDF 处理库，支持逐页图像提取（`page.get_images()`）、图像解码、坐标信息。MIT 许可，pip install 即可。
- **pdfplumber**：基于 pdfminer，图像提取能力弱于 PyMuPDF。
- **pypdf**：当前已用，图像提取接口有限且不稳定。
- **决策**：选择 PyMuPDF，功能全、社区活跃、与现有 pypdf 文本提取互不冲突。

### 视觉模型选型

- Paratera 平台（`https://llmapi.paratera.com/v1`）提供 OpenAI-compatible API，已用于 embedding/reranking/chat。
- 需要用户确认 Paratera 平台是否提供视觉模型（如 GLM-4V、CogVLM-2）。如不提供，备选：
  - DeepSeek-VL（如果 DeepSeek 端点支持 vision）
  - 其他 OpenAI-compatible vision endpoint
- **接口格式**：OpenAI vision API 格式，messages 中 content 为数组，包含 `{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}` 和 `{"type": "text", "text": "..."}`。
- **Prompt 策略**：要求模型用中文描述图表内容（标题、轴标签、关键数据点、趋势、结论），生成 200-500 字描述文本。
- **DeterministicVisionModelProvider**：测试用，返回固定格式描述，不调用真实 API。

### Chunk 模型扩展方案

- 新增 `chunk_type: String(30)` 字段，default='text'，新类型 'image_description'。
- 新增 `source_image_path: String(500)` 字段，nullable，存储提取图片相对路径（如 `data/images/42/page3_img1.png`）。
- Alembic migration 新增两列，旧数据自动填充 chunk_type='text', source_image_path=NULL。
- image_description chunk 的 `heading_path` 设为所在 PDF 页的最近章节标题 + `[图表]` 后缀。
- image_description chunk 使用与 text chunk 相同的 embedding provider 生成向量，统一加入 FAISS。

### 检索融合方案

- image_description chunk 参与正常向量检索，与 text chunk 一起排序，无需特殊路由。
- reranking 阶段同样处理 image_description chunk（reranker 看到的是文字描述，非图片）。
- 前端展示时可通过 chunk_type 区分来源，显示 `[图表描述]` 标签。

## Key Decisions

1. **数据迁移按表增量**：按 content_hash/source_id 去重，支持多次运行不会重复插入。conversations 和 users 不迁移。
2. **PyMuPDF 提取图像**：与现有 pypdf 文本提取并行，不替换文本链路。
3. **图像过滤**：宽或高 < 100px 跳过（logo/icon/装饰图），避免无意义描述噪声。
4. **视觉模型 Provider 遵循现有模式**：Protocol + Deterministic + OpenAICompatible，与 ChatModelProvider/EmbeddingProvider 一致。
5. **image_description chunk 统一检索**：不引入特殊多模态检索路由，复用现有向量搜索 + reranking。
6. **测试全走 deterministic**：视觉模型测试用 DeterministicVisionModelProvider，不让真实 API 成为测试前提。
7. **458 篇新增文献先本地、后云端**：新增国内堆石混凝土文献应先进入本地 SQLite staging/golden corpus，完成去重、解析质检、embedding、多模态描述和评估后，再迁移云端 PostgreSQL。云端只承接通过核验的数据发布，不承担清洗试错。
8. **云端发布包含文件资产**：PostgreSQL 只保存结构化数据和路径；真实 PDF 与提取图片仍需同步到服务器文件系统，否则 `raw_path` 与 `source_image_path` 在云端不可用。

## Phase 0 Calibration Findings

- Codex 已确认 `origin/main -> de3a96c Merge phase 44 production deployment auth`，阶段 44 已合并到远端 main。
- 当前开发分支已从 `origin/main` 创建为 `codex/phase-45-data-migration-multimodal-rag`。
- 已有 `phase-44-complete` tag 指向阶段 44 功能提交；阶段 45 不移动已有阶段 tag。
- 开工时工作区已有阶段 45 规划文件改动、Stage 30 CSV 改动和 `.playwright-mcp/` 未跟踪目录；按用户要求保留，不重置、不覆盖无关文件。
- 阶段 45 收尾前不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR，必须停在用户人工核验前状态。

## Phase 1 Findings

- `docs/stage45_data_migration_multimodal_rag.md` 已固定双主线设计：Track A 是 SQLite 到 PostgreSQL 增量迁移，Track B 是 PDF 图像提取、视觉描述、`image_description` chunk 和统一检索。
- 设计文档明确 `image_description` chunk 不需要特殊检索路由；它以文本描述形式复用现有 embedding、FAISS、rerank 和引用式回答链路。
- `tests/test_stage45_design.py` 覆盖阶段边界、敏感信息排除、10 个 Phase 规划、deterministic vision 和增量迁移合同。
- 聚焦验证：`python -m pytest tests/test_stage45_design.py -q -> 4 passed`。

## Phase 2 Findings

- `scripts/migrate_sqlite_to_postgres.py` 已实现可重复运行的迁移函数和 CLI，源库限制为 SQLite，目标库通过阶段 44 的 `create_database_engine()` 支持 PostgreSQL 或测试用 SQLite。
- 迁移范围为 `documents`、`sources`、`chunks`、`chunk_embeddings`、`qa_logs`；`users`、`conversations`、`messages` 不迁移，避免把本地开发会话状态复制到云端用户空间。
- 迁移会建立旧 ID 到目标 ID 的映射，保证 `chunks.parent_chunk_id`、`sources.document_id`、`chunk_embeddings.chunk_id` 指向目标库新记录。
- 增量去重规则：documents 按 `content_hash`，sources 按 `source_id`，chunks 按目标 `document_id + chunk_index`，embeddings 按目标 `chunk_id + provider + model_name`，qa_logs 按 question/answer/model/retrieval/created_at 组合。
- `scripts/build_faiss_index.py` 新增 `--database-url`，可从迁移后的 PostgreSQL embeddings 重建 FAISS，而不是复制本地索引文件。
- 聚焦验证：`python -m pytest tests/test_stage45_migration.py tests/test_faiss_index.py::test_list_current_embeddings_skips_parent_chunks -q -> 3 passed`；`python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py -q -> 6 passed`。

## Phase 3 Findings

- `Chunk` 已新增 `chunk_type` 和 `source_image_path`；默认 `chunk_type="text"`，图片描述使用 `chunk_type="image_description"`。
- `ChunkCreate` 支持新字段，并保持老调用兼容；现有文本入库不传新字段时仍自动得到 text chunk。
- `DocumentChunkItem` 和 `/documents/{document_id}/chunks` 已返回 `chunk_type` 与 `source_image_path`，便于后续前端或人工检查识别图表描述来源。
- Alembic 新增 `20260618_0002_chunk_multimodal_fields.py`，给旧数据设置 `chunk_type` server default 为 `text` 后移除 default，并创建 `ix_chunks_chunk_type`。
- 聚焦验证：`python -m pytest tests/test_stage45_chunk_schema.py tests/test_stage45_migration.py tests/test_db_models.py tests/test_repositories.py -q -> 15 passed`；`python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py -q -> 9 passed`。

## Phase 4 Findings

- `pyproject.toml` 已新增 `PyMuPDF>=1.24.0`，本地测试环境安装了 `PyMuPDF 1.27.2.3`。
- `app/services/ingestion/image_extractor.py` 新增 `PdfImageExtractor`，使用 PyMuPDF 逐页读取 `page.get_images(full=True)` 并通过 pixmap 保存 PNG。
- `PdfImageExtractionConfig` 默认输出到 `data/images`，并以 `min_width=100`、`min_height=100` 过滤 logo/icon 等小图；`.gitignore` 已加入 `data/images/`。
- 提取结果使用 `ExtractedPdfImage(page_num, image_path, width, height)`，后续可直接传给视觉模型和多模态入库管线。
- 聚焦验证：`python -m pytest tests/test_stage45_image_extractor.py tests/test_stage45_chunk_schema.py -q -> 5 passed`；`python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py tests/test_stage45_image_extractor.py -q -> 11 passed`。

## Phase 5 Findings

- `app/core/config.py` 和 `.env.example` 已新增 `VISION_MODEL_*` 配置；默认留空时走 deterministic provider。
- `app/services/generation/vision_model.py` 新增 `VisionModelProvider` Protocol、`DeterministicVisionModelProvider`、`OpenAICompatibleVisionModelProvider` 和 `create_vision_model_provider()`。
- OpenAI-compatible provider 使用 chat/completions vision payload：`content` 数组同时包含文本 prompt 和 base64 data URI 图片。
- 默认视觉 prompt 要求中文描述图表标题、坐标轴、关键数据、趋势、结构关系和工程含义，并明确不编造图中没有的信息。
- 测试通过 monkeypatch 网络调用验证 payload，不触发真实视觉 API。
- 聚焦验证：`python -m pytest tests/test_stage45_vision_model.py -q -> 6 passed`；`python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py tests/test_stage45_image_extractor.py tests/test_stage45_vision_model.py -q -> 17 passed`。

## Phase 6 Findings

- `app/services/ingestion/multimodal_pipeline.py` 新增 `MultimodalIngestionPipeline`，串联 PDF 图像提取、视觉描述、`image_description` chunk 创建和 embedding 构建。
- 管线按 `source_image_path` 去重，重复处理同一 PDF 时会跳过已有图片描述 chunk。
- `scripts/process_multimodal.py` 新增批处理入口，可处理单个 document 或全部 PDF；默认使用配置中的 vision/embedding provider，也可 `--skip-embeddings`。
- 统一检索已通过测试验证：`image_description` chunk 写入 embedding 后可被 `VectorSearchService` 正常召回，无需特殊检索路由。
- 聚焦验证：`python -m pytest tests/test_stage45_multimodal_pipeline.py tests/test_stage45_image_extractor.py tests/test_stage45_vision_model.py tests/test_stage45_chunk_schema.py -q -> 12 passed`；`python -m pytest tests/test_stage45_design.py tests/test_stage45_migration.py tests/test_stage45_chunk_schema.py tests/test_stage45_image_extractor.py tests/test_stage45_vision_model.py tests/test_stage45_multimodal_pipeline.py -q -> 18 passed`。

## Phase 7 Findings

- 首次全量回归出现 1 个测试锚点失败：`tests/test_stage44_design.py` 仍读取根目录 `task_plan.md` 断言 Phase 44 计划；阶段 45 接手后根目录计划已切换为当前阶段，因此将该测试改为读取长期历史文档 `docs/progress.md` 中的 Phase 44 记录。
- 修正后验证：`python -m pytest tests/test_stage44_design.py tests/test_stage45_design.py -q -> 7 passed`。
- 全量回归：`python -m pytest -q -> 912 passed`。
- Stage 30：`python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`。
- Production smoke dry-run：`python scripts/run_production_smoke.py -> rows=11 execute=false failed=0`。

## Phase 8 Findings

- 桌面 smoke：本阶段服务启动在 `http://127.0.0.1:8015`，页面标题 `RFC-RAG-Agent`，auth gate 正常渲染，console errors=0，horizontal overflow=false。
- 为验证图像描述检索，创建临时 SQLite `data/stage45_browser_smoke.sqlite`，只包含一个 `chunk_type=image_description` 的测试 chunk 和 deterministic embedding；该文件属于 gitignored runtime 数据。
- 浏览器内 `fetch('/search/vector')` 查询 `抗压强度 增长` 返回 `count=1`，命中内容为 `图表显示堆石混凝土抗压强度随龄期增长，并在后期趋于稳定。`。
- 移动端 smoke：390x844 视口页面有内容，`scrollWidth=390`、`clientWidth=390`，horizontal overflow=false，console errors=0。
- Playwright sessions 已关闭，8015/8016 smoke 服务进程已停止。

## Phase 9 Findings

- 普通文档已补齐阶段 45 入口：`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `docs/phase_reviews/phase-45.md` 均记录了 SQLite→PostgreSQL 增量迁移、多模态管线、deterministic vision 测试边界和 Stage 30 不退化结果。
- Obsidian 已建立 `obsidian-vault/阶段汇报/阶段 45 - 数据上云与多模态 RAG/`，包含 Phase 0-9 小汇报和 `阶段 45 Phase 汇报索引.md`。
- Obsidian 入口已补齐：`obsidian-vault/阶段/阶段 45 - 数据上云与多模态 RAG.md`、`obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`。
- 每篇阶段 45 小 Phase 汇报均包含用户要求的 10 个固定部分：本 Phase 目标、完成的主要任务、新增/修改内容、关键代码或模块、问题与解决方式、新词解释、验证结果、遗留问题、下一 Phase、面试表达。
- 阶段 45 按要求停在人工核验前：未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

## Phase 10-17 Planning Findings

- 用户计划追加约 458 篇国内堆石混凝土相关文献；这批语料可能接近国内相关文献全集，因此更适合先作为本地黄金语料库建设任务，而不是直接上云。
- 推荐顺序：新增文献暂存与 manifest -> 本地 SQLite 导入与去重 -> 解析质量审计 -> 文本 embedding 与本地 FAISS -> PDF 图像提取与 GLM-4.6V 描述 -> 覆盖评估与人工抽检 -> SQLite 到 PostgreSQL 迁移 -> 云端文件资产同步与 FAISS 重建。
- 不建议本地和云端同时导入：清洗、去重、元数据修复、chunk 重建和图片描述重跑会导致两边状态迅速分叉，增加排错和回滚成本。
- 云端迁移前需要明确服务器 `DATABASE_URL`、raw PDF 目标路径、`data/images` 目标路径、FAISS 输出路径和生产 smoke 方式。
- 新词解释：manifest 是新增文献批次清单；golden corpus 是通过去重、质检和评估后可作为正式知识库发布的干净语料集；asset sync 是把数据库里引用的真实 PDF/图片文件同步到服务器。

## Phase 10 Findings

- 新增文献目录 `G:\Codex\program\papers_0618` 实际包含 458 个文件，其中 455 个 `.pdf`、3 个 `.caj`。
- 新增 `scripts/build_phase45_literature_manifest.py`，只扫描文件并生成清单，不写 SQLite、不写 PostgreSQL、不生成 chunk、不生成 embedding。
- 已生成 `data/incoming/phase45_literature/manifest.csv` 和 `data/incoming/phase45_literature/manifest.json`，字段包含原始路径、相对路径、文件名、扩展名、文件大小、SHA256/content_hash、PDF 头、是否可打开、页数、疑似标题、状态、重复原因和既有 document id。
- Phase 10 manifest 统计：`total=458`，`ready=324`，`duplicate_candidate=134`，`unreadable=0`，`needs_manual_metadata=0`。3 个 CAJ 由于文件名/标题弱重复被归入 `duplicate_candidate`，同时记录 `is_openable=false` 和缺失页数。
- 重复候选分布包括：37 个 `content_hash_matches_existing_document` 强重复、10 个 `title_matches_existing_document` 既有标题弱重复，以及若干批内标题重复候选。
- pypdf 在部分 PDF 上输出 `Multiple definitions ... /MediaBox` 等内部结构警告，但本阶段未出现 PDF 打不开；这些警告不阻断 Phase 10，后续 Phase 12 解析质量审计应继续关注文本长度、中文比例和疑似扫描版。
- 新词解释：`content_hash` 是文件内容的 SHA256 指纹，用来强去重；`duplicate_candidate` 是重复候选，包含文件完全相同和标题疑似相同两类，后续导入时不应直接重复创建正式 document。

## Phase 11 Findings

- 新增 `scripts/import_phase45_manifest_ready.py`，从 Phase 10 manifest 读取 `status=ready` 行导入本地 SQLite；`duplicate_candidate`、`unreadable`、`needs_manual_metadata` 均跳过。
- 导入前创建本地 SQLite 备份：`data/app.sqlite.backup-before-phase45-phase11-import-20260618`，作为 Phase 11 的回滚点。
- Phase 11 导入结果写入 `data/incoming/phase45_literature/phase11_import_summary.json` 和 `phase11_import_results.csv`。
- Phase 11 统计：`manifest_rows=458`，`ready_rows=324`，`imported=302`，`duplicate=0`，`skipped_not_ready=134`，`empty=22`，`failed=0`，`new_chunks=3237`。
- 本地 SQLite 总量从 `documents=753`、`chunks=28988` 变为 `documents=1055`、`chunks=32225`；`chunk_embeddings=51316` 保持不变，说明本 Phase 未生成 embedding。
- 22 篇 empty 文献多为会议通知、新闻短讯、扫描/版式异常或文本抽取为空的 PDF，应进入 Phase 12 review 队列，不直接进入云端发布集。
- 新词解释：`empty` 指 PDF 可打开但解析后没有可切分文本；`canonical document` 指去重后正式保留的一份文档记录，重复候选只作为审计线索，不重复建正式 document。

## Phase 12 Findings

- 新增 `scripts/audit_phase45_import_quality.py`，基于 Phase 10 manifest、Phase 11 import results 和本地 SQLite chunks 生成解析质量审计，不导出受限全文。
- 生成 `data/incoming/phase45_literature/phase12_quality_audit.csv`、`phase12_review_queue.csv` 和 `phase12_quality_summary.json`。
- Phase 12 质量摘要：`total_rows=458`，`imported_rows=302`，`cloud_candidate=75`，`review_required=249`，`skipped_duplicate_or_not_ready=134`，`empty_rows=22`，`suspected_scanned=160`，`sources_upserted=302`。
- 已为 302 篇新增 imported 文献 upsert `sources` 元数据草案：`source_id=phase45_0618_{content_hash[:16]}`，`source_type=institutional_access_pdf`，`trust_level=local_authorized`，`access_rights=institutional_access`，`fulltext_permission=institutional_access`，并关联 `document_id` 与 `local_path`。
- review_required 的阻断条件限定为解析质量问题或关键元数据缺失（如 empty、低文本/页、标题/年份缺失）；作者和期刊缺失记录在 `metadata_missing`，但不单独阻断高质量文本进入 Phase 13。
- 新词解释：`cloud_candidate` 是通过本地解析质量初筛、可进入后续 embedding/FAISS 和云端发布候选的文献；`review_queue` 是需人工复核或后续修复的文献清单；`suspected_scanned` 是根据每页文本量过低或空文本推断的疑似扫描版/抽取失败标记。

## Phase 13 Findings

- 新增 `scripts/index_phase45_cloud_candidates.py`，只为 Phase 12 `cloud_candidate` 文档的 text chunks 创建/校验 embedding，避免把 review_required 文献混入索引。
- 新增 `scripts/smoke_phase45_candidate_retrieval.py`，验证新增候选语料可通过 keyword、vector、hybrid 三种检索模式命中；输出只包含 query、命中数、top title/source/doc id，不保存 chunk 正文。
- Phase 12 标题校准后，当前严格 cloud_candidate 为 20 篇、238 个 text chunks；Phase 13 已清理旧候选范围中的非候选 embedding，并保持 `chunk_embeddings=51554`。
- 本地 FAISS 已从数据库 embeddings 重建：`provider=paratera`，`model=GLM-Embedding-3`，`dimension=2048`，`vectors=19538`，即原 19300 个有效 text vectors 加新增候选 238 个 vectors。
- 检索 smoke 结果：`清华大学 堆石混凝土 技术`、`堆石混凝土 施工 质量控制`、`胶结颗粒料 筑坝 技术` 在 keyword/vector/hybrid 三种模式下均返回 5 条命中。
- 风险记录：部分 PDF 的标题仍来自期刊页眉或 DOI/文章编号，已通过 Phase 12 review 队列保留为人工元数据校准问题；Phase 13 不导出正文，不把 review_required 文献写入当前候选 embedding 集。
- 新词解释：`FAISS` 是本地向量索引文件，用数据库里的 embedding 重建；`vector smoke` 是用真实 query embedding 做一次轻量检索验证；`prune_non_candidate_embeddings` 是删除不再属于 cloud_candidate 的新增文献 embedding，避免索引污染。

## Phase 14 Findings

- 新增 `scripts/process_phase45_candidate_multimodal.py`，读取 Phase 12 `cloud_candidate` 文档，逐篇提取 PDF 图像并调用配置的 VisionModelProvider 生成中文描述；脚本只创建 image_description chunks，不调用通用全库 embedding build。
- `scripts/index_phase45_cloud_candidates.py` 扩展 `--chunk-type image_description`，用于只给候选文档的图像描述 chunks 生成 embedding。
- 真实 GLM-4.6V 批处理结果：`candidate_documents=20`，`processed_documents=20`，`failed_documents=0`，`extracted_images=51`，`created_chunks=23`，`skipped_images=28`。第一次 3 篇超时后，使用更长本地进程超时重跑成功；已有图片按 `source_image_path` 幂等跳过。
- image_description embedding 结果：`total_chunks=51`，`indexed_chunks=23`，`skipped_chunks=28`，`provider=paratera`，`model_name=GLM-Embedding-3`，`dimension=2048`。
- 本地 FAISS 重建后 `vectors=19589`，即原 19300 + Phase 13 text 238 + Phase 14 image_description 51。
- 图像描述检索 smoke：`浇筑点 块石 上游 下游 2m` 和 `压力试验设备 试件 压板` 的 vector top 命中 `chunk_type=image_description`；hybrid top 仍常由 text chunk 主导，符合当前 keyword 权重更高的融合策略。
- 新词解释：`source_image_path` 是 image_description chunk 指向提取图片文件的路径；`GLM-4.6V` 是本阶段用于真实图片描述的视觉模型；`idempotent image processing` 指重复运行时已存在图片描述不会重复创建 chunk。

## Phase 15 Findings

- 新增 `data/evaluation/phase45_domestic_coverage_queries.csv`，包含 10 条国内堆石混凝土覆盖评测问题，不包含受限全文。
- 新增 `scripts/evaluate_phase45_domestic_coverage.py`，使用关键词检索比较导入前备份库与当前库，输出脱敏命中统计到 `phase45_domestic_coverage_results.csv` 和 `phase45_domestic_coverage_summary.csv`。
- 覆盖评测摘要：baseline_before_phase11 对 10 个 query 均有既有库命中，但 Phase45 命中为 0；current_phase45 对 10 个 query 均有命中，其中 2 个 query 出现 Phase45 新增文献命中，总 Phase45 hits=2。
- Stage 30 回归保持不退化：`overall=91.52`，`grade=A`，`release_decision=pass`。
- 生成 `data/evaluation/phase45_spotcheck_sample.csv`，包含 30 篇抽检样本：20 篇 cloud_candidate + 10 篇 review_required，字段只包含元数据、chunk 数、image_description 数和抽检重点，不导出正文。
- 风险记录：新增语料确实带来覆盖增量，但当前严格 cloud_candidate 只有 20 篇，主要原因是大量 PDF 元数据标题/年份抽取不稳定；Phase 16/17 前仍应把 review queue 作为人工核验重点，而不是盲目全量上云。
- 新词解释：coverage evaluation 是覆盖评估，用于看新增语料是否带来新的可检索命中；spotcheck sample 是人工抽检样本表；noise 是低质量解析、错误标题或无关文献带来的检索干扰。

## Phase 16 Findings

- 新增 `scripts/prepare_phase45_cloud_migration.py`，只读本地 SQLite，生成云端迁移 readiness 报告；不连接云端 PostgreSQL，不复制文件，不重建云端 FAISS。
- 生成 `data/incoming/phase45_literature/phase16_migration_readiness.json`。
- readiness 关键计数：`documents=1055`，`sources=982`，`chunks=32276`，`chunk_embeddings=51605`，`qa_logs=215`。
- 数据一致性：`documents_missing_content_hash=0`，`duplicate_content_hash_groups=0`，`paratera_glm_embedding_rows=19589`，`paratera_glm_bad_dimension_rows=0`，`image_description_chunks=51`，`image_description_embeddings=51`。
- 迁移范围明确为 `documents,sources,chunks,chunk_embeddings,qa_logs`；排除 `users,conversations,messages`，当前本地排除表计数为 users=2、conversations=5、messages=83。
- `ready_for_authorized_migration=false` 是刻意状态：等待用户人工核验和明确云端 PostgreSQL 授权后才能执行真实迁移。
- 新词解释：readiness report 是迁移前体检报告；excluded tables 是明确不迁移的运行时/用户表；authorized migration 是用户核验并授权后的真实云端迁移动作。

## Phase 17 Findings

- 新增 `scripts/prepare_phase45_cloud_asset_sync.py`，只读取本地 SQLite、Phase 12 audit 和本地文件系统，生成云端文件资产同步 manifest；不连接服务器、不复制文件、不执行真实云端命令。
- 生成 `data/incoming/phase45_literature/phase17_asset_sync_manifest.json`，记录 `cloud_candidate_documents=20`、`raw_pdf_files=20`、`raw_pdf_missing=0`、`extracted_image_files=51`、`extracted_image_missing=0`。
- 资产同步被拆成数据库与文件两部分：PostgreSQL 迁移只处理 `documents/sources/chunks/chunk_embeddings/qa_logs`，服务器文件系统还必须同步 `data/raw/` PDF 与 `data/images/` PNG。
- 云端 FAISS 不复制本地索引文件；manifest 中记录待授权命令，要求从云端 PostgreSQL embeddings 重建。
- 新词解释：asset sync manifest 是文件资产同步清单；smoke checklist 是上线后轻量核验清单；human verification gate 是用户人工核验与授权闸门。

## Phase 18-20 Findings

- Claude 指出的 QR、Elsevier logo、低信息图片问题已通过 `scripts/clean_phase45_low_value_images.py` 处理。第一轮真实 GLM 图片描述中删除 4 个低价值 chunk，2 个倒置/方向异常 chunk 标记为 review 但保留。
- 扩容候选后曾用 deterministic vision 跑通新增图片链路，生成 1090 个模板描述；这些模板描述不适合作为真实黄金语料，已全部删除，避免污染向量库。
- `scripts/audit_phase45_import_quality.py` 已增强标题/年份修复规则：标题避开 DOI、期刊页眉、卷期页码、出版社页；年份可从前几个 text chunks 补齐。
- 修复后 `cloud_candidate=235`、`review_required=89`，说明原 review 队列中确实有大量高质量文献被 metadata 误判拦截。
- 本地 GLM embeddings 当前为 `22006` 条：19300 baseline + 2660 Phase45 text + 46 image_description。
- 覆盖评估改善：current Phase45 hits 从 2 增至 11，覆盖 query 从 2 个增至 4 个。
- 新词解释：low-value image chunk 是没有工程信息量的图片描述；metadata repair 是对标题/年份等结构化字段的规则修复；deterministic template chunk 是测试 provider 生成的固定描述，不应进入真实语料发布集。

## Phase 21 Findings

- 用户切换到智谱官方 GLM-4.6V endpoint 后，使用 `--document-ids-file` 续跑上一轮失败的 77 篇文档；脚本已支持从文本文件读取待重试 document_id，便于断点续跑。
- 官方 endpoint 续跑结果：`selected_documents=77`、`processed_documents=63`、`failed_documents=14`、`extracted_images=535`、`created_chunks=515`、`skipped_images=20`。
- 合并第一轮 Paratera 样本与第二轮智谱官方续跑后，前 100 篇 PDF 样本中已有 86 篇完成真实 GLM-4.6V 图片解析；剩余 14 篇中 13 篇为 `provider_timeout`，1 篇为 `image_pixmap_conversion_failed`。
- 二次低价值图片清理删除 48 个 QR/logo/低信息量 image_description chunks；当前全库 `image_description` chunks=744，且 744 个均已生成 GLM-Embedding-3 embedding。
- 本地 FAISS 已从数据库 embeddings 重建，`provider=paratera`、`model=GLM-Embedding-3`、`dimension=2048`、`vectors=22704`，说明图片描述已经进入统一向量检索候选集。
- `scripts/process_multimodal.py` 已增加默认 checkpoint 输出：传入 `--output-dir` 时每完成一篇会刷新 `process_multimodal_results.csv` 和 `process_multimodal_summary.json`，后续大批量处理断线后可从已失败/未完成 document_id 继续。
- Stage 30 回归保持 `91.52 / A / pass`；阶段相关测试 `tests/test_stage45_process_multimodal_script.py tests/test_stage45_image_quality_cleanup.py tests/test_stage45_candidate_indexing.py` 为 10 passed；全量测试 928 passed。
- 原 14 篇失败样本继续补跑后，最新 100 篇样本状态为 `processed=98`、`failed=2`；失败队列拆为 `provider_timeout=1`（document_id=20）和 `image_pixmap_conversion_failed=1`（document_id=187）。
- `PdfImageExtractor` 已优化为单张坏图转换失败时跳过该图并继续处理同篇 PDF，避免一张异常内嵌图拖垮整篇文档。
- 全库中断批次和 14 篇补跑带来的新增 image_description 已完成低价值清理、embedding 补齐与 FAISS 重建；当前 FAISS vectors=22977。
- 最终样本评估输出位于 `data/incoming/phase45_literature/phase21_final_sample_stats/`：100 篇样本中 98 篇完成，879 个 image_description chunks 均有 embedding，低价值 remove 候选为 0，5 个图表型向量查询中 3 个召回 image_description 且为 Top1，质量门槛通过。
- 已生成 `next_import_channel_plan.md`，建议下一步先对全库 PDF 分类，再按普通图文类、多图重载类、超时专项类、提取异常类分队列并发导入；当前已停止在全库分类前。

## Phase 22 Findings

- 本地三个目录 `papers_0616`、`papers_0618`、`papers_0609` 合计 932 个文献文件，其中 PDF=927、CAJ=5；按 SHA256 去重后唯一 hash=832，本地重复额外文件=100。
- 补入前 DB 已覆盖本地唯一 hash=707；`build_phase45_missing_literature_manifest.py` 生成 missing manifest 后确认缺口为 125 个唯一文件。
- missing manifest 导入结果：ready=124，imported=91，empty=33，skipped_not_ready=1，failed=0，新增 text chunks=957。导入后 DB documents=1146、PDF documents=853。
- 导入后重新核验三目录覆盖：DB 已覆盖本地唯一 hash=798，剩余 34 个唯一文件未入库，其中 33 个为文本解析为空的 PDF，1 个为 CAJ/不可读。
- missing 批次质量审计：imported_rows=91，cloud_candidate=69，review_required=55，empty_rows=33，suspected_scanned=33，sources_upserted=91。
- 新增 69 篇 cloud_candidate 的 text embedding 已完成：total_chunks=723，indexed_chunks=723；FAISS 重建后 vectors=23700。
- 三路 API 可行性测试通过：官方 GLM 单路成功、官方同 key 双路并发成功、Paratera 单路成功。
- 直接三进程并发写 SQLite 不可行：官方 A/B 在创建 chunks 时触发 `sqlite3.OperationalError: database is locked`；这不是模型连通性问题，而是 SQLite 单写者限制。
- 已落地两段式通道：`process_multimodal_to_staging.py` 并发执行图片提取和视觉描述，只写 staging CSV；`import_multimodal_staging.py` 单进程串行把 described rows 合并为 image_description chunks。
- staging 小批量验证通过：官方 A/B 并发输出 29 条 described 图片描述，Paratera C 对已存在图片正确 skipped_existing；串行合并创建 29 个 chunks，无 SQLite lock。
- staging 合并后完成低价值清理、image_description embedding 补齐和 FAISS 重建，当前 vectors=23748。
- 最新未完成多模态队列：PDF=853，已完成多模态文档=142，未完成=711，三类队列 official_a/official_b/paratera_c 各 237。

## Phase 25 Findings

- 每队 20 篇的三路 staging 放大验证可行，但官方 A 路出现长尾停滞；checkpoint 已保留成功描述，停掉进程不会丢失已完成 staging rows。
- official_b 20 篇完整完成：extracted_images=118，described_images=117，failed_images=1。
- paratera_c 20 篇完整完成：extracted_images=76，described_images=73，failed_images=3。
- official_a checkpoint：extracted_images=127，described_images=122，failed_images=5；因长时间无进展手动停止，后续未完成文档会重新进入队列。
- 串行 staging 合并结果：staging_rows=321，described_rows=312，created_chunks=312。
- 低价值图片清理删除 35 个 chunks；image_description embedding 补齐 indexed_chunks=277、skipped_chunks=1065。
- FAISS 重建后 vectors=24025。
- 未完成多模态队列从 711 降至 665，已完成多模态文档从 142 增至 188。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 15 passed。
- 新词解释：`document-ids-file` 是断点续跑清单，每行一个 document_id；`provider_timeout` 是视觉模型请求连接或响应超时的脱敏归类；`image_pixmap_conversion_failed` 是 PyMuPDF 将 PDF 内嵌图片转换为像素图失败。

## Phase 26 Findings

- 每队 30 篇三路 staging 可以继续产出有效结果，但三路均在 30 分钟窗口出现长尾超时；更大批量前需要把超时/大图/慢响应文档单独归队处理。
- Phase26 staging 实际落盘 rows=442，其中 described_rows=436、failed_rows=6；串行入库 created_chunks=436，没有发生 SQLite 写锁。
- 低价值图片清理删除 27 个 chunks，主要用于继续压低 QR、logo、低信息装饰图进入检索的概率。
- image_description embedding 补齐 indexed_chunks=409、skipped_chunks=1342；FAISS 重建后 vectors=24434。
- 未完成多模态队列从 665 降至 618，已完成多模态文档从 188 增至 235；下一轮剩余三队 official_a/official_b/paratera_c 各 206 篇。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 15 passed。
- 新词解释：`长尾超时` 指少量 PDF 或图片请求耗时显著高于大多数样本，不能让它们阻塞主批次；`checkpoint/CSV` 是已完成图片描述的中间结果，可在停止进程后继续串行入库。

## Phase 27 Findings

- 已知失败隔离后，每队 20 篇三路 staging 可完整跑完；说明 `236`、`187` 等异常文档反复进入主队列是前一轮不稳定的重要原因之一。
- 队列分类新增 `--isolate-known-failures` 后，未完成 618 篇中只有 `236` 仍需 timeout 专项处理，`187` 进入 non-timeout failed 专项；其余 616 篇进入主批次。
- staging 脚本新增 `processed_document_ids.txt`、`failed_document_ids.txt`、`no_image_document_ids.txt`，解决了“无有效图片 PDF 没有 chunk，因此被无限重复跑”的问题。
- Phase27 三路完整处理 60 篇：staging_rows=211，described_rows=208，created_chunks=208；清理后补 image_description embedding indexed_chunks=175。
- 重新分类时通过 `--include-staging-processed` 读取 processed id 文件，真实未完成从 618 降至 558，而不是只按 image_description chunk 粗略扣减。
- FAISS 重建后 vectors=24609。

## Phase 28 Findings

- 从 document id 412 起，三路各 20 篇再次出现长尾超时；说明后续语料段存在图片量较大或视觉 API 响应较慢的 PDF，不能只靠固定 20 篇批量推进。
- Phase28 采用 partial staging 策略：已成功描述的 156 张图片先入库、清理、embedding、FAISS，但出现过 rows 的 12 篇 PDF 标记为 partial，不视为完成。
- 队列分类新增 `--partial-document-ids-file` 与 `--include-staging-partial`，防止半处理文档因为已有部分 image_description chunk 被误判为已完成。
- Phase28 清理删除 22 个低价值 chunks；image_description embedding 补齐 indexed_chunks=134；FAISS 重建后 vectors=24743。
- 重新分类结果保持未完成=558、主队列=556、partial=12；这符合“partial 图片入库，但文档仍需后续续跑补全”的预期。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 18 passed。
- 新词解释：`partial document` 是已有部分图片被识别入库、但 PDF 批处理未完整结束的文档；`processed id file` 是文档级完成证据，比“是否已有 image_description chunk”更可靠。

## Phase 29 Findings

- 单文档图片上限策略可行：`--max-new-images-per-document 20` 让已部分处理的大图 PDF 快速续跑，已存在图片会 skipped_existing，不会重复创建 chunk。
- Phase29 三路各 3 篇全部完成，staging_rows=19，其中 described_rows=3、skipped_existing_images=16；这说明 Phase28 已经为这些文档处理过大部分当前可见图片。
- 串行合并 created_chunks=3；低价值清理删除 1 个 chunk；image_description embedding 补齐 indexed_chunks=2。
- 队列重分从未完成=558 降至 549，extra_completed 从 60 增至 69；partial 仍为 12，因为 Phase28 标记的其他半处理文档仍待后续续跑。
- FAISS 重建后 vectors=24745。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`max-new-images-per-document` 是每篇 PDF 单轮最多处理的新图片数量，用来把大 PDF 拆成多次可控批处理；`skipped_existing` 表示图片路径已经存在 image_description chunk，本轮跳过以保证幂等。

## Phase 30 Findings

- 三路每队 10 篇 capped 主批次可以完整跑完，但耗时约 20-25 分钟，说明后续全库处理仍应保持小批量和 checkpoint。
- Phase30 staging_rows=580，其中 described_rows=451、failed_images=11、skipped_existing_images=118；大量 skipped_existing 证明续跑幂等逻辑生效。
- 串行入库 created_chunks=451；低价值清理删除 54 个 chunks；image_description embedding 补齐 indexed_chunks=397。
- FAISS 重建后 vectors=25142，较 Phase29 增加 397 个有效图片文本向量。
- 队列重分后未完成从 549 降至 541，extra_completed 从 69 增至 77，partial 从 12 增至 34；这是大图 PDF 分片处理的正常表现：图片文本增长快，但文档完成数需要多轮 capped pass 才会明显下降。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`capped 主批次` 指每篇 PDF 限量处理新图片的常规批处理；`partial state` 是文档需要后续继续补图片的状态，不等于失败。

## Phase 31 Findings

- 每队 12 篇 capped 批次超过当前 30 分钟窗口，三路均需要按 checkpoint 收束；后续主批次应回落到每队 10 篇，或对 partial 文档单独用更小批量续跑。
- Phase31 虽未增加 completed 文档数，但成功入库 described_rows=552；这是图片文本覆盖的实质进展。
- skipped_existing=388，说明重复续跑时已有图片被正确跳过；failed_images=5，错误量相对可控。
- 低价值图片清理删除 80 个 chunks；image_description embedding 补齐 indexed_chunks=472。
- FAISS 重建后 vectors=25614，较 Phase30 增加 472 个有效图片文本向量。
- 队列重分后未完成保持 541，partial 从 34 增至 40；这是 partial 批次的预期结果，代表更多大图文档需要后续 capped pass。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`checkpoint 收束` 是批处理超时后停止进程，但保留已写 CSV 并继续入库已完成图片；`批量窗口` 是当前命令允许的最大运行时间，本轮为 30 分钟。

## Phase 32 Findings

- 回到每队 10 篇后，三路 capped staging 再次完整完成，证明 batch-10 是当前 30 分钟窗口内更稳的吞吐点。
- Phase32 staging_rows=1412，其中 described_rows=556、skipped_existing=843、failed_images=13；高 skipped_existing 表明 partial 文档续跑幂等生效，已有图片不会重复入库。
- 串行入库 created_chunks=556；低价值清理删除 90 个 chunks；image_description embedding 补齐 indexed_chunks=466。
- FAISS 重建后 vectors=26080，较 Phase31 增加 466 个有效图片文本向量。
- 队列重分后未完成从 541 降至 537，extra_completed 从 77 增至 81，partial 从 40 增至 42；大图 PDF 仍需多轮 capped pass 才能完全完成。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`稳态续跑` 指在不超时的批量参数下反复执行同一闭环；当前稳态参数是三路各 10 篇、每篇最多 20 张新图。

## Phase 33 Findings

- Phase33 batch-10 继续完整跑完，证明当前参数可以作为连续推进全库多模态识别的稳定操作点。
- staging_rows=1814，其中 described_rows=585、skipped_existing=1215、failed_images=14；随着 partial 文档反复续跑，skipped_existing 会持续升高，这是幂等续跑的正常现象。
- 串行入库 created_chunks=585；低价值清理删除 95 个 chunks；image_description embedding 补齐 indexed_chunks=490。
- FAISS 重建后 vectors=26570，较 Phase32 增加 490 个有效图片文本向量。
- 队列重分后未完成从 537 降至 536，extra_completed 从 81 增至 82，partial 从 42 增至 45；当前阶段主要是在补齐大图 PDF 的图片级覆盖，document completed 下降会慢于向量增长。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`图片级覆盖` 指 PDF 中每张有效工程图片都有对应中文描述和 embedding；它比“文档完成数”更细粒度，当前阶段二者会不同步增长。

## Phase 34 Findings

- Phase34 batch-10 继续完整跑完，运行时间低于 30 分钟窗口，说明该批量仍是稳定参数。
- staging_rows=2171，其中 described_rows=535、skipped_existing=1627、failed_images=9；skipped_existing 继续升高，表明大图 partial 文档已被多轮覆盖。
- 串行入库 created_chunks=535；低价值清理删除 100 个 chunks；image_description embedding 补齐 indexed_chunks=435。
- FAISS 重建后 vectors=27005，较 Phase33 增加 435 个有效图片文本向量。
- 队列重分后未完成从 536 降至 531，extra_completed 从 82 增至 87，partial 从 45 增至 46；本轮开始更明显地消化 partial 文档。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`partial 消化` 指通过多轮 capped pass 把曾经半处理的 PDF 补到文档级完成状态。

## Phase 35 Findings

- Phase35 首次 official_a/official_b staging 出现异常：两路 1 分钟内 produced described_images=0 且 failed_images 很高。入库前检查 summary 发现不符合正常模式，重跑 official 两路后恢复正常。
- 最终 staging_rows=2230，其中 described_rows=531、skipped_existing=1690、failed_images=9；Paratera C 正常，official A/B 重跑正常。
- 串行入库 created_chunks=531；低价值清理删除 121 个 chunks；image_description embedding 补齐 indexed_chunks=410。
- FAISS 重建后 vectors=27415，较 Phase34 增加 410 个有效图片文本向量。
- 队列重分后未完成从 531 降至 525，extra_completed 从 87 增至 93，partial 从 46 增至 48；队列 first ids 已推进到 1060 段，说明前面大图文档正在被消化。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`summary sanity check` 是入库前检查 described/failed/skipped 的比例；如果 described=0 且 failed 激增，应先重跑 staging，不能把异常失败结果当成真实处理结果。

## Phase 36 Findings

- Phase36 三路 batch-10 正常完成，没有出现 Phase35 的 official 环境异常；summary 比例稳定。
- staging_rows=2452，其中 described_rows=534、skipped_existing=1910、failed_images=8；skipped_existing 继续升高，说明 partial 文档多轮续跑持续幂等。
- 串行入库 created_chunks=534；低价值清理删除 133 个 chunks；image_description embedding 补齐 indexed_chunks=401。
- FAISS 重建后 vectors=27816，较 Phase35 增加 401 个有效图片文本向量。
- 队列重分后未完成从 525 降至 518，extra_completed 从 93 增至 100，partial 从 48 增至 51；队列 first ids 推进到 1070 段，partial 消化效率进一步改善。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`队列 first ids 推进` 是指每路待处理清单开头的 document_id 变大，说明前面反复 partial 的文档被逐步完成或移出主队列。

## Phase 37 Findings

- Phase37 batch-10 正常完成，继续证明三路每队 10 篇、每篇 20 张新图上限是当前稳定操作点。
- staging_rows=2530，其中 described_rows=514、skipped_existing=2002、failed_images=14；skipped_existing 首次超过 2000，说明前段大图 PDF 大部分图片已经有描述。
- 串行入库 created_chunks=514；低价值清理删除 121 个 chunks；image_description embedding 补齐 indexed_chunks=393。
- FAISS 重建后 vectors=28209，较 Phase36 增加 393 个有效图片文本向量。
- 队列重分后未完成从 518 降至 509，extra_completed 从 100 增至 109，partial 从 51 增至 54；未完成 PDF 本轮下降 9，partial 文档进入明显收尾段。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`收尾段` 指同一批大图 PDF 经过多轮 capped pass 后，新增图片逐渐减少、已存在图片跳过增多、文档级完成开始加速。

## Phase 38 Findings

- Phase38 batch-10 继续正常完成，summary 比例健康，没有 provider/env 异常。
- staging_rows=2449，其中 described_rows=521、skipped_existing=1919、failed_images=9；大图 partial 文档继续通过幂等跳过已有图片来补剩余图片。
- 串行入库 created_chunks=521；低价值清理删除 132 个 chunks；image_description embedding 补齐 indexed_chunks=389。
- FAISS 重建后 vectors=28598，较 Phase37 增加 389 个有效图片文本向量。
- 队列重分后未完成从 509 降至 503，extra_completed 从 109 增至 115，partial 从 54 增至 59；距离未完成跌破 500 只差 4 篇。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`有效图片文本向量` 指通过低价值清理后保留的 image_description chunk 已生成 embedding 并进入 FAISS。

## Phase 39 Findings

- Phase39 batch-10 正常完成；official_b 出现 MuPDF page tree 格式提示，但脚本跳过坏页后继续完成，未影响 staging 汇总。
- staging_rows=2547，其中 described_rows=534、skipped_existing=2004、failed_images=9；summary 比例保持健康。
- 串行入库 created_chunks=534；低价值清理删除 142 个 chunks；image_description embedding 补齐 indexed_chunks=392。
- FAISS 重建后 vectors=28990，较 Phase38 增加 392 个有效图片文本向量。
- 队列重分后未完成从 503 降至 495，extra_completed 从 115 增至 123，partial 从 59 增至 63；阶段性跌破 500。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`MuPDF page tree 格式提示` 是 PDF 内部页索引结构异常，当前提取器按页级容错处理，不让单页坏结构中断整篇 PDF。

## Phase 40 Findings

- Phase40 batch-10 正常完成；official_b 仍有 MuPDF page tree 格式提示，但批处理完整结束，summary 健康。
- staging_rows=2475，其中 described_rows=548、skipped_existing=1916、failed_images=11；当前批次继续稳定提供 500 级图片描述增量。
- 串行入库 created_chunks=548；低价值清理删除 133 个 chunks；image_description embedding 补齐 indexed_chunks=415。
- FAISS 重建后 vectors=29405，较 Phase39 增加 415 个有效图片文本向量。
- 队列重分后未完成从 495 降至 489，extra_completed 从 123 增至 129，partial 从 63 增至 68；主队列持续清理中。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`稳定清库` 指使用已验证批量参数连续降低未完成队列，而不是继续调大并发或单批规模。

## Phase 41 Findings

- Phase41 batch-10 正常完成，summary 健康；official_b 仍出现 MuPDF page tree 格式提示，但页级容错继续有效。
- staging_rows=2617，其中 described_rows=523、skipped_existing=2091、failed_images=3；failed_images 降到较低水平。
- 串行入库 created_chunks=523；低价值清理删除 127 个 chunks；image_description embedding 补齐 indexed_chunks=396。
- FAISS 重建后 vectors=29801，较 Phase40 增加 396 个有效图片文本向量。
- 队列重分后未完成从 489 降至 481，extra_completed 从 129 增至 137，partial 从 68 增至 70；剩余 400 段 partial 文档继续减少。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`页级容错` 指 PDF 某些页解析异常时，只跳过该页相关图片提取，不中断整篇 PDF 或整批任务。

## Phase 42 Findings

- Phase42 batch-10 正常完成，三路 summary 健康，没有 MuPDF 异常提示。
- staging_rows=2350，其中 described_rows=493、skipped_existing=1847、failed_images=10；本轮图片增量略低，但文档完成数下降明显。
- 串行入库 created_chunks=493；低价值清理删除 136 个 chunks；image_description embedding 补齐 indexed_chunks=357。
- FAISS 重建后 vectors=30158，首次超过 30000。
- 队列重分后未完成从 481 降至 471，extra_completed 从 137 增至 147，partial 从 70 增至 71；本轮未完成 PDF 下降 10。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`FAISS 破三万` 指当前向量索引中可检索向量总数超过 30000，其中包含 text chunks 和 image_description chunks。

## Phase 43 Findings

- Phase43 batch-10 正常完成，summary 健康，没有 provider/env 异常。
- staging_rows=2303，其中 described_rows=490、skipped_existing=1803、failed_images=10；图片增量稳定在 500 左右。
- 串行入库 created_chunks=490；低价值清理删除 143 个 chunks；image_description embedding 补齐 indexed_chunks=347。
- FAISS 重建后 vectors=30505，较 Phase42 增加 347 个有效图片文本向量。
- 队列重分后未完成从 471 降至 460，extra_completed 从 147 增至 158，partial 从 71 增至 75；主队列下降 11，清库速度继续改善。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`清库速度` 指每轮处理后未完成 PDF 队列减少的数量，它会随着早期 partial 文档逐渐补完而提高。

## Phase 44 Findings

- Phase44 official_a 超过 30 分钟窗口，按 checkpoint 收束并标记 partial；official_b/paratera_c 完整完成。该策略保留已完成图片描述，同时避免误判 official_a 文档完成。
- staging_rows=2145，其中 described_rows=496、skipped_existing=1633、failed_images=16；official_a checkpoint 提供 153 条 described rows。
- 串行入库 created_chunks=496；低价值清理删除 131 个 chunks；image_description embedding 补齐 indexed_chunks=365。
- FAISS 重建后 vectors=30870，较 Phase43 增加 365 个有效图片文本向量。
- 队列重分后未完成从 460 降至 440，extra_completed 从 158 增至 178，partial 从 75 增至 76；主队列大幅下降 20。
- Stage 30 保持 91.52 / A / pass；阶段相关测试 19 passed。
- 新词解释：`checkpoint 收束` 在本轮再次验证有效：超时路不阻塞整批，已完成图片仍可入库，文档级完成状态由 partial 清单保护。

- 当前本地 SQLite 中 `file_extension=.pdf` 且 `raw_path` 存在的文档为 762 篇，符合用户判断的七八百篇论文量级。
- `scripts/process_multimodal.py` 已支持按全库 PDF 选择 `--limit 100` 样本，并输出 `process_multimodal_results.csv` 与 `process_multimodal_summary.json`。
- 本次全库前 100 篇样本真实 GLM-4.6V 解析结果：`selected_documents=100`、`processed_documents=23`、`failed_documents=77`、`extracted_images=160`、`created_chunks=160`。
- 失败主因是 provider 返回 `provider_quota_exhausted`，即 GLM-4.6V 资源包/余额不足；错误结果 CSV 已脱敏，不保存供应商原始 JSON。
- 低价值图片清理后，删除 21 个 QR/logo/低信息图片描述；当前全库 `image_description` chunks=205，其中 GLM image embeddings=46。
- 新增的 139 个有效样本图片描述还没有 GLM embedding，因为 GLM-Embedding-3 同样返回资源包不足。待资源包恢复后应只补跑 `image_description` embedding，再重建 FAISS。
- 新词解释：provider_quota_exhausted 表示模型服务资源包不足；sample run 是抽样批处理；image parsing 指 PDF 图片提取与视觉模型描述，不等同于 embedding 入索引。

## Phase 45 Throughput Diagnostic Findings

- 上次中断后仍有 3 个真实视觉处理进程在后台运行，分别对应 `official_a`、`official_b` 和 `paratera_c` 队列；本次已先停止，避免继续消耗真实 API。
- 既有历史 staging summary 只能看到 described/skipped/failed 数量，不能回答 P50/P90/P95、provider 成功率、PDF 提取耗时、API 耗时和实际并发峰值，因此新增 `multimodal_timing.csv` 作为图片级计时表。
- 小批量探针范围：三路各 2 篇 PDF，每篇最多 5 张新图；结果为 extracted_images=744，skipped_existing_images=714，api_attempted_images=30，successful_descriptions=30，failed_descriptions=0。
- 吞吐核心指标：avg_api_ms=6030.179，p50_api_ms=3952.611，p90_api_ms=12285.779，p95_api_ms=17974.331，concurrency_peak=3。
- Provider 对比：official_a 10/10 成功，avg_api_ms=6535.103；official_b 10/10 成功，avg_api_ms=2517.972；paratera_c 10/10 成功，avg_api_ms=9037.462，P95=23668.363。
- PDF 提取总耗时 38.116 秒，API 调用累计耗时 180.905 秒，staging 三路耗时累计 219.06 秒；import 0.405 秒，embedding 3.285 秒，FAISS rebuild 约 14.9 秒。
- 结论：当前“三路并发”实际只是三个进程各自串行调用视觉 API，峰值并发约等于 3；如果 provider 没有限流优势，吞吐不会线性提高。
- 次级瓶颈：每轮为跳过已处理图像仍需重新提取整篇 PDF 图片，本次 744 张提取图里只有 30 张真正进入 API，重复提取/路径比对浪费明显。
- 新词解释：P50/P90/P95 是耗时百分位，表示 50%/90%/95% 的请求不超过该耗时；concurrency_peak 是通过 API 调用开始/结束时间重建的真实同时在飞调用数；staging/import 是先写 CSV 暂存再串行写 SQLite 的两段式入库。
- 优化方向：先建立 image-level remaining manifest/cache，避免每轮重复扫描大量已完成图片；再在单 provider 内增加受控 worker 并发，例如 official key 内部 2-3 workers，配合 rate-limit/backoff 和 checkpoint；最后用 analyzer 比较吞吐，而不是只看“处理了多少篇文档”。

## Phase 46 Findings: image-level cache and full PDF image coverage

- Image-level remaining manifest/cache is now the canonical way to resume multimodal image work. It compares extracted image paths with existing `chunks.source_image_path`, so completed images are skipped before calling the vision API.
- The long-run staging writer now uses atomic checkpoint writes with retry. This fixed the Windows `OSError 22` failure observed after multi-hour checkpoint runs.
- Five-route GLM-4.6V concurrency is feasible with two official old-key routes, two official new-key routes, and one Paratera route. The analyzer measured `concurrency_peak=5`.
- Throughput after optimization:
  - Probe: 25 / 25 successful, avg API 10.11s, P95 17.36s.
  - Full queue partial: 1173 attempted, 1153 successful, 20 failed, avg API 11.88s, P95 27.43s.
  - Remaining queue: 3750 attempted, 3680 successful, 70 failed, avg API 12.25s, P95 27.76s.
  - All-PDF residual queue: 1893 attempted, 1881 successful, 12 failed, avg API 9.30s, P95 21.77s.
- Final all-PDF coverage: 853 PDF documents, 14968 valid extracted images, 14956 images completed with real vision descriptions, `image_description` chunks, embeddings, and FAISS vectors. Remaining pending images: 12 across 9 documents.
- Final vector state: `image_description` chunks=14956, `image_description` embeddings=14956, total embeddings=69655, FAISS vectors=37639.
- Low-value image cleanup was run in review mode after the large batches. It identified 792 remove candidates and 85 review candidates, but no deletion was applied in this final pass; these should be reviewed manually before destructive cleanup.
- Stage 30 did not regress: `overall=91.52 grade=A release_decision=pass`.
- Full verification passed: `python -m pytest -q -> 944 passed`; `python scripts/run_production_smoke.py -> rows=11 execute=false failed=0`.
- New term: `image-level remaining manifest` means a per-image queue that records document id, page, image path, size, and status. It is finer-grained than document-level queues and prevents large PDFs from being repeatedly rescanned and reprocessed.

## Phase 47 Findings: low-value cleanup and orientation repair

- The project did not intentionally mirror images in code. The previous extractor used `fitz.Pixmap(pdf, xref)` to save raw embedded image objects. Some PDFs display those image objects through page transformation matrices, so raw xref extraction can appear rotated or mirrored compared with the PDF page.
- The repair strategy is to re-render each affected image from its displayed rectangle on the PDF page (`page.get_image_rects(xref)` + clipped page render), not to blindly rotate by keywords.
- `data/images/1318` contained three images that the user identified as inverted. All three were re-rendered from document 1318 page display and backed up under `data/incoming/phase45_literature/phase45_orientation_fix_doc1318_retry/backups/`.
- Global orientation repair processed 85 review candidates: 83 fixed, 2 failed. The 2 failed images from document 421 were restored from backup and removed as low-information circular icon-like chunks.
- Low-value cleanup was applied in two passes: first deleted 792 clear remove candidates, then deleted 4 residual remove candidates after re-description. Total image-description chunks after cleanup: 14158.
- Repaired images were re-described with real GLM-4.6V so chunk text no longer keeps stale "inverted/rotated" descriptions from before the image fix. `import_multimodal_staging.py --update-existing` updates existing chunks by `source_image_path` and deletes stale embeddings for re-indexing.
- Final vector state after cleanup and repair: `image_description_chunks=14158`, `image_description_embeddings=14158`, total embeddings=68857, FAISS vectors=36841.
- Stage 30 remained stable: `overall=91.52 grade=A release_decision=pass`; full tests remained stable: `944 passed`.

## Phase 48 Findings: image evidence display gap

- The user-reported "no image displayed" issue was not an ingestion failure. Images, `image_description` chunks, embeddings, and FAISS vectors already existed.
- The missing link was response wiring: retrieval results did not expose `chunk_type` and `source_image_path` through Agent sources, and the frontend did not have a browser-safe `image_url` or figure-card renderer.
- The fix derives `image_url` only when `source_image_path` starts with `data/images/`, producing `/assets/images/...`; other paths are not exposed as image assets.
- `/assets/images` is served from local `data/images/`, so frontend cards show true PDF-extracted images rather than model-generated illustrations.
- Agent API smoke for `堆石混凝土施工流程图` returned 8 sources with 8 image URLs; `/assets/images/442/page156_img1.png` returned HTTP 200.
- New term: `image_url` is a browser-safe URL derived from the stored `source_image_path`. It is presentation metadata, not a new corpus source.
## Phase 49 Findings: figure UX and evidence fallback

- Enlarged figures should stay inside the current Agent page. Opening extracted figures in a new browser page made review awkward, so the frontend now uses an in-page lightbox with close button, backdrop close, and `Escape`.
- Reader-facing figure labels should not expose internal chunk ids. Cards now render as `Figure 1`, `Figure 2`, etc., and show source paper title plus a derived page/image label.
- A text-only top-k retrieval result can still point to a paper that has relevant figure evidence. The Agent response now enriches such answers with same-document `image_description` chunks when no image source is already present.
- The enrichment is intentionally bounded and source-safe: it only uses existing `image_description` chunks from the same document and only exposes browser URLs derived from `data/images/`.
- Manual review found cropped/fragment-like images. This is a remaining extraction-quality issue, not a response-wiring issue; the next phase should add stronger filtering or page-region rendering for extreme aspect ratio and partial figures.
- Verification passed for frontend syntax, focused Agent/frontend tests, and local image-source smoke.
