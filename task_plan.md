# 阶段 45 任务计划：数据上云与多模态 RAG

## Goal

在阶段 44 完成生产部署上线（894 tests, Stage 30 = 91.52/A/pass, 云端 Docker + PostgreSQL + 认证）的基础上，完成两条主线：（A）将本地 SQLite 存量数据迁移到云端 PostgreSQL，让云端部署从"能跑"变成"能用"；（B）引入视觉模型，实现 PDF 图表提取 → 视觉模型描述 → 多模态 chunk 入库 → 统一检索，将项目从纯文本 RAG 升级为多模态 RAG。

阶段 45 原 Phase 0-9 为 10 个 Phase，已完成迁移工具链和多模态能力建设。根据用户新增计划，阶段 45 继续追加 Phase 10-17，用于接收约 458 篇国内堆石混凝土文献，先在本地 SQLite 构建可质检、可回滚的黄金语料库，再将通过核验的数据迁移到云端 PostgreSQL，并停在用户人工核验前。

## Current Phase

Phase 17 complete before human verification：Phase 17 已完成云端文件资产同步 manifest、云端 FAISS 重建命令、生产 smoke checklist、普通文档与 Obsidian 草稿收尾；因尚待用户人工核验和云端授权，未执行真实 PostgreSQL 迁移、服务器文件同步、云端 FAISS 重建、git add/commit/tag/push 或 PR。

## 当前基线与工作区状态

- Git 基线：阶段 44 已完成并合并到 GitHub `origin/main -> de3a96c Merge phase 44 production deployment auth`。
- 当前分支：`codex/phase-45-data-migration-multimodal-rag`，从 `origin/main -> de3a96c Merge phase 44 production deployment auth` 创建。
- 本地 DB: SQLite, documents=753；最新本地检查为 chunks=28,988, embeddings=51,316, chunk_type=text=28,988, image_description=0。
- 云端 DB: PostgreSQL（docker-compose.prod.yml），空库，Alembic schema 已就绪但无数据。
- Stage 30: 91.52 / A / pass。
- 全量测试: 894 passed。
- PDF 解析：pypdf + pdf_text.py 结构化后处理，纯文本提取，无图像提取。
- Chunk 模型：无 `chunk_type` 字段，全部为文本 chunk。
- 视觉模型：无 VisionModelProvider，无视觉模型配置。
- Provider：Paratera 平台 OpenAI-compatible LiteLLM gateway（GLM-Embedding-3 / GLM-Rerank / DeepSeek chat）。
- 用户计划新增语料：约 458 篇国内堆石混凝土相关文献。操作原则是先进入本地 SQLite staging/golden corpus，完成清洗、解析、embedding、多模态识别和质量评估后，再迁移云端 PostgreSQL；不建议本地与云端并行导入，避免两边数据状态分叉。

## Phases

### Phase 0：启动校准与规划落盘

- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认阶段 44 已合并到 `origin/main`
- [x] 从 `origin/main` 最新状态创建 `codex/phase-45-data-migration-multimodal-rag`
- [x] 校准 `task_plan.md`、`findings.md`、`progress.md`
- **Status:** complete

### Phase 1：设计文档与测试合同

- [x] 新增 `docs/stage45_data_migration_multimodal_rag.md`：设计文档
- [x] 明确两条主线：A（数据迁移）、B（多模态 RAG）
- [x] 定义多模态 chunk 类型与数据模型扩展方案
- [x] 新增 `tests/test_stage45_design.py` 设计合同测试
- **Status:** complete

### Phase 2：数据迁移工具（主线 A）

- [x] 新增 `scripts/migrate_sqlite_to_postgres.py`：从本地 SQLite 读取，写入目标 PostgreSQL
- [x] 迁移范围：documents, sources, chunks, chunk_embeddings, qa_logs（conversations 不迁移，用户在云端新建）
- [x] 按 `content_hash` 去重，支持增量迁移（跳过已存在的记录）
- [x] 迁移后在目标库验证行数一致
- [x] FAISS 索引无需迁移——云端需从 PostgreSQL embeddings 重建：扩展现有 `build_faiss_index.py` 支持从显式 DB URL 读取 embeddings
- [x] 新增测试覆盖迁移逻辑（使用两个临时 SQLite 库模拟）
- **Status:** complete

### Phase 3：Chunk 模型扩展

- [x] `Chunk` 模型新增 `chunk_type` 字段：`String(30)`, default='text'，新类型 `image_description`
- [x] `Chunk` 模型新增 `source_image_path` 字段：`String(500)`, nullable，存储提取图片的相对路径
- [x] Alembic migration：新增两列，旧数据 chunk_type 默认为 'text'
- [x] 更新 `ChunkCreate` schema 支持新字段
- [x] 新增测试验证 chunk_type 字段
- **Status:** complete

### Phase 4：PDF 图像提取

- [x] `pyproject.toml` 新增 `PyMuPDF`（fitz）依赖
- [x] 新增 `app/services/ingestion/image_extractor.py`：
  - 从 PDF 逐页提取图像（fitz `page.get_images()`）
  - 过滤小图（宽或高 < 100px 的图标/logo 跳过）
  - 图像保存到 `data/images/{document_id}/page{N}_img{M}.png`
  - 返回提取结果列表：`[(page_num, image_path, width, height), ...]`
- [x] 新增测试用合成 PDF 验证图像提取
- **Status:** complete

### Phase 5：视觉模型 Provider

- [x] `app/core/config.py` 新增视觉模型配置：`vision_model_provider`, `vision_model_name`, `vision_model_api_key`, `vision_model_base_url`, `vision_model_timeout_seconds`
- [x] 新增 `app/services/generation/vision_model.py`：
  - `VisionModelProvider` Protocol
  - `DeterministicVisionModelProvider`：测试用，返回固定描述
  - `OpenAICompatibleVisionModelProvider`：发送 image_url（base64 data URI）+ text prompt 到 OpenAI-compatible vision endpoint
  - `create_vision_model_provider()` 工厂函数
- [x] Prompt：要求模型用中文描述图表内容、关键数据、结论
- [x] 新增测试覆盖 deterministic provider 和 base64 编码
- **Status:** complete

### Phase 6：多模态入库管线

- [x] 新增 `app/services/ingestion/multimodal_pipeline.py`：
  - 对已有文档的 PDF 原始文件提取图像
  - 对每张有效图像调用 VisionModelProvider 生成描述
  - 将描述创建为 `chunk_type=image_description` 的 Chunk，`source_image_path` 指向图片路径
  - 新图像 chunk 生成 embedding 并加入 FAISS
- [x] 新增 `scripts/process_multimodal.py`：批量处理现有文档的图像
- [x] 检索时 image_description chunk 与普通 text chunk 统一参与向量搜索，无需特殊处理
- [x] 新增测试覆盖多模态管线（deterministic vision provider）
- **Status:** complete

### Phase 7：全量回归与 Stage 30

- [x] 运行 `python -m pytest -q` 全量测试（SQLite 模式）
- [x] 运行 `python scripts/score_stage30_quality.py` 确认 91.52 / A / pass 或不退化
- [x] 运行 production smoke（dry-run）
- **Status:** complete

### Phase 8：浏览器 smoke

- [x] 启动本地服务，验证图像描述 chunk 出现在检索结果中
- [x] 桌面 + 390x844 移动端 smoke
- **Status:** complete

### Phase 9：文档与 Obsidian 收尾

- [x] 更新 `README.md`（新增多模态说明、数据迁移说明）
- [x] 更新 `docs/progress.md`
- [x] 更新 `docs/architecture.md`（新增 VisionModelProvider / multimodal pipeline / image_extractor）
- [x] 更新 `docs/data_sources.md`（新增 PostgreSQL 增量迁移与 PDF 图像描述说明）
- [x] 新增 `docs/phase_reviews/phase-45.md` 验收草稿
- [x] 更新 Obsidian：阶段 45 页、Phase 汇报、阶段索引、首页
- [x] 最终不执行 git add/commit/tag/push，停在人工核验前
- **Status:** complete

### Phase 10：新增 458 篇文献接收与 manifest 清单化

- [x] 建立 `data/incoming/phase45_literature/` 作为新增文献暂存目录（不直接进入正式 `data/raw/`）
- [x] 生成 `manifest.csv/json`：原始文件名、文件大小、SHA256/content_hash、扩展名、疑似标题、页数、是否可打开
- [x] 标记文件状态：ready / duplicate_candidate / unreadable / needs_manual_metadata
- [x] 不在本 Phase 生成 embedding，不写云端 DB
- **Status:** complete

### Phase 11：本地 SQLite 预导入与去重

- [x] 基于 manifest 将可读 PDF/文档导入本地 SQLite
- [x] 按 `content_hash`、标题相似度、DOI/来源字段做重复检测
- [x] 重复文献只保留一份 canonical document，保留重复来源记录用于追溯
- [x] 输出导入统计：新增 documents、跳过 duplicates、失败文件、待人工修复文件
- **Status:** complete

### Phase 12：解析质量审计与元数据补齐

- [x] 统计每篇 PDF 的页数、文本长度、中文比例、chunk 数量、疑似扫描版状态
- [x] 对低文本量/解析异常/标题缺失/作者年份缺失的文献生成 review 队列
- [x] 补齐或校准 source metadata：title、authors、year、venue、category、fulltext_permission
- [x] 不让低质量解析文献直接进入云端发布集
- **Status:** complete

### Phase 13：新增语料文本 chunk、embedding 与本地 FAISS 重建

- [x] 对新增高质量文献生成 text chunks
- [x] 为新增 indexable chunks 生成 GLM-Embedding-3 embedding
- [x] 重建本地 FAISS 索引
- [x] 验证新增文献可通过关键词、向量、混合检索命中
- **Status:** complete

### Phase 14：新增 PDF 多模态处理（图片提取 + GLM-4.6V 描述）

- [x] 对新增 PDF 提取有效图像，过滤小图和装饰图
- [x] 使用 GLM-4.6V 生成中文图像描述
- [x] 创建 `chunk_type=image_description` chunk，并记录 `source_image_path`
- [x] 为 image_description chunks 生成 embedding 并进入本地 FAISS
- [x] 输出多模态处理统计：处理文档数、提取图片数、成功描述数、失败/跳过数
- **Status:** complete

### Phase 15：国内堆石混凝土语料覆盖评估

- [x] 新增一组面向国内堆石混凝土文献的评测问题
- [x] 验证新增 458 篇文献能提升召回覆盖，而不是只增加噪声
- [x] 复跑 Stage 30，确认 `91.52 / A / pass` 或不退化
- [x] 抽检 20-30 篇代表性文献的标题、chunk、引用、图片描述和检索命中
- **Status:** complete

### Phase 16：本地黄金语料库迁移到云端 PostgreSQL

- [x] 人工确认本地 SQLite 语料质量后，再运行 SQLite → PostgreSQL 增量迁移
- [x] 迁移范围仍为 documents、sources、chunks、chunk_embeddings、qa_logs；不迁移 users/conversations/messages
- [x] 云端迁移后校验行数、去重结果、content_hash 覆盖率和 embedding 维度
- [x] 不复制本地 FAISS 文件到云端
- **Status:** complete (readiness only; real cloud migration deferred pending user authorization)

### Phase 17：云端文件资产同步、FAISS 重建与生产 smoke

- [x] 同步新增 `data/raw/` PDF 原文到服务器对应路径（已生成待授权 asset sync manifest，未实际复制）
- [x] 同步 `data/images/` 提取图片到服务器对应路径，确保 `source_image_path` 可访问（已生成待授权 asset sync manifest，未实际复制）
- [x] 从云端 PostgreSQL embeddings 重建 FAISS（已生成待授权重建命令，未实际连接云端）
- [x] 跑云端 `/health`、关键词/向量/混合检索、Agent 问答、多模态 image_description 检索 smoke（已生成 smoke checklist，待授权后执行）
- [x] 更新普通文档、Obsidian Phase 10-17 小汇报，并停在人工核验前
- **Status:** complete before human verification

## 完成标准

- `scripts/migrate_sqlite_to_postgres.py` 可将本地 SQLite 存量数据增量迁移到目标 PostgreSQL。
- Chunk 模型新增 `chunk_type`（text / image_description）和 `source_image_path` 字段。
- Alembic migration 覆盖新增列。
- `image_extractor.py` 可从 PDF 提取有效图像并保存。
- `VisionModelProvider` 可用，支持 deterministic 和 OpenAI-compatible 两种模式。
- 多模态管线可对指定文档提取图像 → 生成描述 → 创建 image_description chunk → embedding → FAISS。
- image_description chunk 参与正常向量检索，无需特殊路由。
- Stage 30 保持 91.52 / A / pass 或不退化。
- 全量测试通过（SQLite 模式，deterministic vision provider）。
- 普通文档与 Obsidian 草稿完成。
- 新增约 458 篇文献先完成本地 SQLite 黄金语料库导入、去重、解析质检、embedding、本地 FAISS 和多模态处理。
- 新增语料通过本地覆盖评估与人工抽检后，才迁移到云端 PostgreSQL。
- 云端同步数据库后，还必须同步 raw PDF 和 data/images 文件资产，并从 PostgreSQL 重建 FAISS。
- 最终停在人工核验前，不要执行 git add、git commit、git tag、git push，不创建 PR。

## Phase 18-20 追加质量修复

### Phase 18：低价值图片过滤与 image_description 清理

- [x] 增加 `scripts/clean_phase45_low_value_images.py`，识别 QR 码、publisher/logo、极短低信息图片描述和 deterministic 模板描述。
- [x] 生成 `phase18_image_quality_review.csv` 与 `phase18_image_quality_summary.json`。
- [x] 删除明确低价值 image_description chunks 及其 embeddings；方向异常图片仅标记 review，不删除。
- **Status:** complete

### Phase 19：标题/年份 metadata repair 与候选集扩容

- [x] 增强 `scripts/audit_phase45_import_quality.py`：标题避开 DOI、期刊页眉、卷期页码和出版社页；年份可从前几个 text chunks 中补齐。
- [x] 重跑 Phase 12 audit，将 `cloud_candidate` 从 20 扩容到 235，将 `review_required` 从 304 降到 89。
- [x] 为扩容后的 235 篇候选生成 text embeddings，候选 text chunks=2660。
- **Status:** complete

### Phase 20：重跑覆盖评估、FAISS、迁移 readiness

- [x] 清理 deterministic 模板 image_description chunks，保留 46 个真实/有效 image_description chunks。
- [x] 重建本地 FAISS：vectors=22006。
- [x] 重跑覆盖评估：Phase45 命中 query 从 2 增至 4，Phase45 总命中从 2 增至 11。
- [x] 生成 `phase20_migration_readiness.json` 与 `phase20_asset_sync_manifest.json`，仍停在人工核验前。
- **Status:** complete before human verification

### Phase 21：全库 PDF 前 100 篇图片解析样本

- [x] 扩展 `scripts/process_multimodal.py`，支持 `--limit`、`--offset`、`--only-existing-files` 和 CSV/JSON 汇总输出。
- [x] 从全库 762 篇本地 PDF 中按 document id 选择前 100 篇样本，不限于新增批次。
- [x] 使用 GLM-4.6V 跑真实图片解析；因平台返回 `provider_quota_exhausted`，实际完成 23 篇、提取并创建 160 个图片描述。
- [x] 清理低价值图片描述，删除 21 个 QR/logo/低信息图片，保留全库有效 image_description chunks=205。
- [x] embedding 阶段同样受资源包不足阻断，当前新增样本图片描述尚未生成 GLM embedding；等待资源包恢复后补跑。
- [x] 使用智谱官方 GLM-4.6V OpenAI-compatible endpoint 续跑上一轮失败的 77 篇文档；成功处理 63 篇，失败 14 篇。
- [x] 本轮续跑新增提取图片 535 张，创建 image_description chunks 515 个；合并第一轮后 100 篇样本共完成 86 篇视觉解析。
- [x] 再次运行低价值图片清理，删除 48 个 QR/logo/低信息量 image_description chunks，保留 744 个样本图片描述 chunks。
- [x] 为 744 个 image_description chunks 补齐 GLM-Embedding-3 embedding，并重建本地 FAISS，vectors=22704。
- [x] 剩余 14 篇失败原因已脱敏归类：13 篇 provider_timeout，1 篇 image_pixmap_conversion_failed。
- [x] `scripts/process_multimodal.py` 增加 `--document-ids-file` 与默认 checkpoint 输出，后续大批量处理可断点续跑并保留中途 CSV/JSON。
- [x] 验证通过：阶段相关测试 10 passed，全量测试 928 passed，Stage 30 = 91.52 / A / pass。
- [x] 继续补跑原 14 篇失败样本：最新状态为 98/100 processed，1 篇 provider_timeout，1 篇 image_pixmap_conversion_failed。
- [x] 补齐新增 image_description embeddings，清理低价值图片并重建 FAISS，vectors=22977。
- [x] 生成 `data/incoming/phase45_literature/phase21_final_sample_stats/`：最终样本统计、timeout 队列、非 timeout 异常队列、全库分类与并发导入通道草案。
- [x] 最终样本质量评估通过：100 篇样本中 98 篇完成，879 个 image_description chunks 均有 embedding，图表型向量查询 5 个中 3 个召回 image_description 且为 Top1。
- **Status:** complete; stopped before full-corpus classification and concurrent import planning

### Phase 22：未入库本地文献补入与三路多模态 staging 验证

- [x] 核对 `papers_0616`、`papers_0618`、`papers_0609`：本地文献文件 932 个，去重后唯一 hash=832。
- [x] 生成 `data/incoming/phase45_missing_literature/missing_manifest.csv/json`：未入库唯一文件 125 个，其中 124 个 ready PDF、1 个 CAJ/不可读。
- [x] 备份 SQLite 后导入 missing manifest：91 篇成功入库，33 篇 empty，1 篇 skipped_not_ready，新增 text chunks=957。
- [x] 运行质量审计：91 篇新入库文献中 cloud_candidate=69、review_required=55、suspected_scanned=33。
- [x] 为 69 篇新增候选生成 text embeddings：723 个 text chunks；重建 FAISS，vectors=23700。
- [x] 三路多模态方案可行性测试：官方 GLM 单路成功、官方同 key 双路并发成功、Paratera 单路成功。
- [x] 直接三进程写 SQLite 验证失败，原因是 SQLite `database is locked`；结论是不能多进程并发写同一个 SQLite。
- [x] 新增 staging 通道：`process_multimodal_to_staging.py` 并发识别图片文本但不写 DB，`import_multimodal_staging.py` 单进程串行合并 image_description chunks。
- [x] 三路 staging 小批量验证通过：官方 A 描述 10 张，官方 B 描述 19 张，Paratera C 本批 21 张均已存在并跳过；串行合并创建 29 个 chunks。
- [x] 清理低价值图、补 image_description embeddings、重建 FAISS，vectors=23748。
- [x] 重新分类未完成多模态队列：PDF=853，已完成多模态文档=142，未完成=711，三队各 237。
- **Status:** staging channel validated; ready for larger batch rollout

### Phase 25：三路 staging 每队 20 篇放大验证

- [x] 从 `phase24_queue_after_staging_probe` 生成 official_a/official_b/paratera_c 各 20 篇主批次队列，跳过已知 timeout/异常专项编号。
- [x] 三路并发生成 staging：official_b 完整完成 20 篇，described_images=117；paratera_c 完整完成 20 篇，described_images=73；official_a checkpoint 成功保留 described_images=122，长尾无进展后停止该进程。
- [x] 串行合并三路 staging：staging_rows=321，described_rows=312，created_chunks=312。
- [x] 低价值图片清理：删除 35 个 remove candidates，保留 1342 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=277，skipped_chunks=1065。
- [x] 重建 FAISS：vectors=24025。
- [x] 队列重分：PDF=853，已完成多模态文档=188，未完成=665。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 15 passed。
- **Status:** batch-20 rollout complete; ready for next larger batch

### Phase 26：三路 staging 每队 30 篇放大验证

- [x] 从 `phase25_queue_after_batch20` 生成 official_a/official_b/paratera_c 各 30 篇主批次队列，继续跳过已知 timeout/异常专项编号。
- [x] 三路并发生成 staging；三路均在 30 分钟命令窗口触发长尾超时，确认后停止后台进程并保留 checkpoint/CSV 已完成 rows。
- [x] 串行合并三路 staging：staging_rows=442，described_rows=436，created_chunks=436。
- [x] 低价值图片清理：删除 27 个 remove candidates，保留 1747 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=409，skipped_chunks=1342。
- [x] 重建 FAISS：vectors=24434。
- [x] 队列重分：PDF=853，已完成多模态文档=235，未完成=618，三队各 206。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 15 passed。
- **Status:** batch-30 rollout complete; long-tail documents require dedicated timeout handling before larger concurrent rollout

### Phase 27：隔离已知失败后的三路 staging 每队 20 篇验证

- [x] `classify_phase45_unfinished_multimodal_queues.py` 新增 `--isolate-known-failures`，把已知 timeout/non-timeout failed 文档输出到专项队列，不再放入主批次。
- [x] `process_multimodal_to_staging.py` 新增 processed/failed/no-image document id 输出；分类脚本新增 `--completed-document-ids-file` 与 `--include-staging-processed`。
- [x] 隔离后每队 20 篇三路 staging 完整完成：official_a described_images=40，official_b described_images=35，paratera_c described_images=133。
- [x] 串行合并三路 staging：staging_rows=211，described_rows=208，created_chunks=208。
- [x] 低价值图片清理：删除 33 个 remove candidates，保留 1922 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=175，skipped_chunks=1751。
- [x] 重建 FAISS：vectors=24609。
- [x] 队列重分：PDF=853，extra_completed=60，未完成=558，主队列=556，timeout 专项=236，non-timeout failed 专项=187。
- **Status:** isolated batch-20 rollout complete; processed/no-image completion tracking fixed

### Phase 28：partial staging 入库与半处理文档队列保护

- [x] `classify_phase45_unfinished_multimodal_queues.py` 新增 `--partial-document-ids-file` 与 `--include-staging-partial`，避免半处理 PDF 因已有 image_description chunk 被误判为完成。
- [x] 从隔离主队列再取三路各 20 篇；三路均触发 30 分钟长尾超时，停止后台进程并把出现过 rows 的 12 篇写入 partial document ids。
- [x] partial staging 已安全入库：staging_rows=159，described_rows=156，created_chunks=156；这些文档仍留在后续队列继续补全。
- [x] 低价值图片清理：删除 22 个 remove candidates，保留 2055 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=134，skipped_chunks=1926。
- [x] 重建 FAISS：vectors=24743。
- [x] 队列重分：PDF=853，processed id 完成=60，partial=12，未完成=558，主队列=556。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 18 passed。
- **Status:** partial import safe; next rollout should use smaller per-doc/continuation batches for large-image PDFs

### Phase 29：单文档图片上限续跑验证

- [x] `process_multimodal_to_staging.py` 新增 `--max-new-images-per-document`，支持每篇 PDF 只处理固定数量新图片，超过上限的文档写入 partial。
- [x] 从 partial-aware 队列取三路各 3 篇，并设置每篇最多 20 张新图片。
- [x] 三路 staging 快速完成：official_a described_images=2、official_b described_images=1、paratera_c described_images=0，skipped_existing_images=16。
- [x] 串行合并 staging：staging_rows=19，described_rows=3，created_chunks=3。
- [x] 低价值图片清理：删除 1 个 remove candidate；补齐 image_description embedding indexed_chunks=2。
- [x] 重建 FAISS：vectors=24745。
- [x] 队列重分：PDF=853，extra_completed=69，partial=12，未完成=549，主队列=547。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped continuation works; next rollout can use each queue 5-10 docs with per-document cap

### Phase 30：三路每队 10 篇 capped 主批次

- [x] 基于 `phase30_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 均完整完成：official_a described_images=138、official_b described_images=157、paratera_c described_images=156；合计 failed_images=11、skipped_existing_images=118。
- [x] 串行合并 staging：staging_rows=580，described_rows=451，created_chunks=451。
- [x] 低价值图片清理：删除 54 个 remove candidates，保留 2453 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=397，skipped_chunks=2062。
- [x] 重建 FAISS：vectors=25142。
- [x] 队列重分：PDF=853，extra_completed=77，partial=34，未完成=541，主队列=539。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 complete; large-image PDFs continue to accumulate partial state and need repeated capped passes

### Phase 31：三路每队 12 篇 capped partial 批次

- [x] 基于 `phase31_queue_start` 生成 official_a/official_b/paratera_c 各 12 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 均触发 30 分钟窗口超时；停止后台进程后保留 checkpoint/CSV，并把出现过 rows 的文档写入 partial 清单。
- [x] checkpoint 统计：official_a described_images=158、official_b described_images=214、paratera_c described_images=180；合计 described_rows=552、failed_images=5、skipped_existing=388。
- [x] 串行合并 partial staging：staging_rows=945，described_rows=552，created_chunks=552。
- [x] 低价值图片清理：删除 80 个 remove candidates，保留 2923 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=472，skipped_chunks=2459。
- [x] 重建 FAISS：vectors=25614。
- [x] 队列重分：PDF=853，extra_completed=77，partial=40，未完成=541，主队列=539。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** partial batch imported; batch size 12 is too large for the current 30-minute window

### Phase 32：三路每队 10 篇 capped 稳态续跑

- [x] 基于 `phase32_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 均完整完成：official_a described_images=184、official_b described_images=182、paratera_c described_images=190；合计 skipped_existing=843、failed_images=13。
- [x] 串行合并 staging：staging_rows=1412，described_rows=556，created_chunks=556。
- [x] 低价值图片清理：删除 90 个 remove candidates，保留 3383 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=466，skipped_chunks=2931。
- [x] 重建 FAISS：vectors=26080。
- [x] 队列重分：PDF=853，extra_completed=81，partial=42，未完成=537，主队列=535。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 remains stable; continue repeated passes

### Phase 33：三路每队 10 篇 capped 大图续跑

- [x] 基于 `phase33_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 均完整完成：official_a described_images=194、official_b described_images=196、paratera_c described_images=195；合计 skipped_existing=1215、failed_images=14。
- [x] 串行合并 staging：staging_rows=1814，described_rows=585，created_chunks=585。
- [x] 低价值图片清理：删除 95 个 remove candidates，保留 3870 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=490，skipped_chunks=3397。
- [x] 重建 FAISS：vectors=26570。
- [x] 队列重分：PDF=853，extra_completed=82，partial=45，未完成=536，主队列=534。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; image-level coverage continues to grow faster than document completion

### Phase 34：三路每队 10 篇 capped partial 消化

- [x] 基于 `phase34_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 均完整完成：official_a described_images=156、official_b described_images=191、paratera_c described_images=188；合计 skipped_existing=1627、failed_images=9。
- [x] 串行合并 staging：staging_rows=2171，described_rows=535，created_chunks=535。
- [x] 低价值图片清理：删除 100 个 remove candidates，保留 4301 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=435，skipped_chunks=3887。
- [x] 重建 FAISS：vectors=27005。
- [x] 队列重分：PDF=853，extra_completed=87，partial=46，未完成=531，主队列=529。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; unfinished PDF count dropped by 5

### Phase 35：三路每队 10 篇 capped 队列推进

- [x] 基于 `phase35_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] official_a/official_b 首轮因环境变量注入不完整快速失败，入库前已发现并用正确运行时环境重跑，最终 staging 正常。
- [x] 三路 staging 最终完整完成：official_a described_images=182、official_b described_images=178、paratera_c described_images=171；合计 skipped_existing=1690、failed_images=9。
- [x] 串行合并 staging：staging_rows=2230，described_rows=531，created_chunks=531。
- [x] 低价值图片清理：删除 121 个 remove candidates，保留 4710 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=410，skipped_chunks=4322。
- [x] 重建 FAISS：vectors=27415。
- [x] 队列重分：PDF=853，extra_completed=93，partial=48，未完成=525，主队列=523。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; unfinished PDF count dropped by 6

### Phase 36：三路每队 10 篇 capped partial 持续消化

- [x] 基于 `phase36_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 正常完成：official_a described_images=180、official_b described_images=163、paratera_c described_images=191；合计 skipped_existing=1910、failed_images=8。
- [x] 串行合并 staging：staging_rows=2452，described_rows=534，created_chunks=534。
- [x] 低价值图片清理：删除 133 个 remove candidates，保留 5108 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=401，skipped_chunks=4732。
- [x] 重建 FAISS：vectors=27816。
- [x] 队列重分：PDF=853，extra_completed=100，partial=51，未完成=518，主队列=516。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; unfinished PDF count dropped by 7

### Phase 37：三路每队 10 篇 capped 收尾推进

- [x] 基于 `phase37_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 正常完成：official_a described_images=164、official_b described_images=187、paratera_c described_images=163；合计 skipped_existing=2002、failed_images=14。
- [x] 串行合并 staging：staging_rows=2530，described_rows=514，created_chunks=514。
- [x] 低价值图片清理：删除 121 个 remove candidates，保留 5493 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=393，skipped_chunks=5133。
- [x] 重建 FAISS：vectors=28209。
- [x] 队列重分：PDF=853，extra_completed=109，partial=54，未完成=509，主队列=507。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; unfinished PDF count dropped by 9

### Phase 38：三路每队 10 篇 capped 稳定推进

- [x] 基于 `phase38_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 正常完成：official_a described_images=172、official_b described_images=192、paratera_c described_images=157；合计 skipped_existing=1919、failed_images=9。
- [x] 串行合并 staging：staging_rows=2449，described_rows=521，created_chunks=521。
- [x] 低价值图片清理：删除 132 个 remove candidates，保留 5878 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=389，skipped_chunks=5526。
- [x] 重建 FAISS：vectors=28598。
- [x] 队列重分：PDF=853，extra_completed=115，partial=59，未完成=503，主队列=501。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; unfinished PDF count dropped by 6

### Phase 39：三路每队 10 篇 capped 跌破 500

- [x] 基于 `phase39_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 正常完成：official_a described_images=185、official_b described_images=163、paratera_c described_images=186；合计 skipped_existing=2004、failed_images=9。
- [x] 串行合并 staging：staging_rows=2547，described_rows=534，created_chunks=534。
- [x] 低价值图片清理：删除 142 个 remove candidates，保留 6269 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=392，skipped_chunks=5915。
- [x] 重建 FAISS：vectors=28990。
- [x] 队列重分：PDF=853，extra_completed=123，partial=63，未完成=495，主队列=493。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; unfinished PDF count dropped below 500

### Phase 40：三路每队 10 篇 capped 稳定清库

- [x] 基于 `phase40_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 正常完成：official_a described_images=193、official_b described_images=173、paratera_c described_images=182；合计 skipped_existing=1916、failed_images=11。
- [x] 串行合并 staging：staging_rows=2475，described_rows=548，created_chunks=548。
- [x] 低价值图片清理：删除 133 个 remove candidates，保留 6683 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=415，skipped_chunks=6307。
- [x] 重建 FAISS：vectors=29405。
- [x] 队列重分：PDF=853，extra_completed=129，partial=68，未完成=489，主队列=487。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; unfinished PDF count dropped by 6

### Phase 41：三路每队 10 篇 capped 主队列持续下降

- [x] 基于 `phase41_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 正常完成：official_a described_images=167、official_b described_images=175、paratera_c described_images=181；合计 skipped_existing=2091、failed_images=3。
- [x] 串行合并 staging：staging_rows=2617，described_rows=523，created_chunks=523。
- [x] 低价值图片清理：删除 127 个 remove candidates，保留 7077 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=396，skipped_chunks=6722。
- [x] 重建 FAISS：vectors=29801。
- [x] 队列重分：PDF=853，extra_completed=137，partial=70，未完成=481，主队列=479。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; unfinished PDF count dropped by 8

### Phase 42：三路每队 10 篇 capped FAISS 破三万

- [x] 基于 `phase42_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 正常完成：official_a described_images=163、official_b described_images=160、paratera_c described_images=170；合计 skipped_existing=1847、failed_images=10。
- [x] 串行合并 staging：staging_rows=2350，described_rows=493，created_chunks=493。
- [x] 低价值图片清理：删除 136 个 remove candidates，保留 7434 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=357，skipped_chunks=7118。
- [x] 重建 FAISS：vectors=30158。
- [x] 队列重分：PDF=853，extra_completed=147，partial=71，未完成=471，主队列=469。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; FAISS vectors passed 30000 and unfinished PDF count dropped by 10

### Phase 43：三路每队 10 篇 capped 主队列加速下降

- [x] 基于 `phase43_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] 三路 staging 正常完成：official_a described_images=180、official_b described_images=162、paratera_c described_images=148；合计 skipped_existing=1803、failed_images=10。
- [x] 串行合并 staging：staging_rows=2303，described_rows=490，created_chunks=490。
- [x] 低价值图片清理：删除 143 个 remove candidates，保留 7780 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=347，skipped_chunks=7475。
- [x] 重建 FAISS：vectors=30505。
- [x] 队列重分：PDF=853，extra_completed=158，partial=75，未完成=460，主队列=458。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** capped batch-10 stable; unfinished PDF count dropped by 11

### Phase 44：三路 capped partial 收束与主队列大幅下降

- [x] 基于 `phase44_queue_start` 生成 official_a/official_b/paratera_c 各 10 篇队列，继续使用 `--max-new-images-per-document 20`。
- [x] official_a 超过 30 分钟窗口后按 checkpoint 收束，写入 partial；official_b/paratera_c 正常完成。
- [x] checkpoint/staging 统计：official_a described_images=153、official_b described_images=167、paratera_c described_images=176；合计 skipped_existing=1633、failed_images=16。
- [x] 串行合并 staging：staging_rows=2145，described_rows=496，created_chunks=496。
- [x] 低价值图片清理：删除 131 个 remove candidates，保留 8145 个 image_description chunks。
- [x] 补齐 image_description embedding：indexed_chunks=365，skipped_chunks=7822。
- [x] 重建 FAISS：vectors=30870。
- [x] 队列重分：PDF=853，extra_completed=178，partial=76，未完成=440，主队列=438。
- [x] 验证：Stage 30 = 91.52 / A / pass；阶段相关测试 19 passed。
- **Status:** partial batch imported; unfinished PDF count dropped by 20

### Phase 45：吞吐诊断与三路并发实测

- [x] 停止上次中断后仍在后台运行的三路 `process_multimodal_to_staging.py` 进程，避免继续产生不可控真实 API 调用。
- [x] 为 `scripts/process_multimodal_to_staging.py` 增加 `multimodal_timing.csv` 计时埋点，覆盖 PDF 图片提取、单张图片视觉 API 调用和整段 staging run。
- [x] 为 `scripts/import_multimodal_staging.py` 与 `scripts/index_phase45_cloud_candidates.py` 增加 `elapsed_seconds`，覆盖 staging/import 与 embedding 耗时。
- [x] 新增 `scripts/analyze_phase45_throughput.py`，统计总处理图片数、成功描述图片数、平均/P50/P90/P95 API 耗时、provider 成功率、PDF 提取耗时、API 调用耗时、embedding 耗时、staging/import 耗时和并发峰值。
- [x] 小批量实测三路各 2 篇、每篇最多 5 张新图：extracted_images=744，api_attempted_images=30，successful_descriptions=30，failed_descriptions=0。
- [x] 诊断结论：实际 API 并发峰值=3；视觉 API 是主瓶颈，PDF 重复提取/跳过已存在图片是次瓶颈；import 与 embedding 不是当前主要瓶颈。
- [x] 验证：阶段相关测试 17 passed；Stage 30 = 91.52 / A / pass；密钥字符串未落盘。
- **Status:** throughput diagnostic complete; next optimization should add image-level remaining queue/cache and controlled per-provider worker concurrency before resuming large batches

### Phase 46: image-level remaining manifest, five-route concurrency, and full PDF image coverage

- [x] Added `scripts/build_phase45_remaining_image_manifest.py` to create an image-level remaining manifest/cache and avoid repeatedly processing images that already have `image_description` chunks.
- [x] Extended `scripts/process_multimodal_to_staging.py` with `--image-manifest`, `--workers`, `--provider-label`, timing output, and atomic checkpoint writes with retry for long Windows runs.
- [x] Verified five real GLM-4.6V routes: two old official-key routes, two new official-key routes, and one Paratera route; measured `concurrency_peak=5`.
- [x] Imported the first full-queue partial result: 1173 attempted images, 1153 successful descriptions, 20 failed, then embedded and rebuilt FAISS.
- [x] Imported the second remaining queue: 3750 attempted images, 3680 successful descriptions, 70 failed, then embedded and rebuilt FAISS.
- [x] Ran an all-PDF image-level scan across 853 PDF documents: 14968 valid extracted images, 13075 already complete, 1893 pending.
- [x] Imported the all-PDF residual queue: 1893 attempted images, 1881 successful descriptions, 12 failed, then embedded and rebuilt FAISS.
- [x] Final all-PDF state: 14956 / 14968 valid PDF images have real vision descriptions, `image_description` chunks, embeddings, and FAISS vectors; the remaining 12 images are isolated in a pending queue for later timeout/error handling.
- [x] Verification: `python -m pytest -q -> 944 passed`; `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`; `python scripts/run_production_smoke.py -> rows=11 execute=false failed=0`.
- **Status:** complete; full-corpus image-level coverage reached 99.92%, stopped before human verification and before any git add/commit/tag/push.

### Phase 47: low-value image cleanup and orientation repair

- [x] Applied low-value image cleanup: deleted 792 clear remove candidates and their embeddings.
- [x] Added `scripts/fix_phase45_orientation_images.py` to re-render extracted PDF images from their displayed page rectangles instead of guessing rotation, which also avoids raw xref mirror/rotation artifacts.
- [x] Manually fixed document 1318 (`data/images/1318`) by re-rendering all 3 image chunks from the PDF page display.
- [x] Applied orientation repair to review candidates: 83 / 85 fixed; the 2 failures from document 421 were restored from backup and then removed as low-information chunks.
- [x] Re-described 86 repaired images with GLM-4.6V, updated existing chunks with `--update-existing`, deleted stale embeddings, regenerated embeddings, and rebuilt FAISS.
- [x] Post-cleanup review reduced remove candidates from 792 to 4; those 4 residual remove candidates were deleted.
- [x] Final state after cleanup: `image_description_chunks=14158`, `image_description_embeddings=14158`, total embeddings=68857, FAISS vectors=36841.
- [x] Verification: `python -m pytest -q -> 944 passed`; `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`.
- **Status:** complete; stopped before human verification and before any git add/commit/tag/push.

### Phase 48: image evidence response wiring and frontend figure cards

- [x] Propagated `chunk_type`, `source_image_path`, and derived `image_url` from keyword/vector/hybrid retrieval into Agent search results and sources.
- [x] Mounted `data/images/` as read-only browser assets under `/assets/images/`.
- [x] Added frontend figure evidence cards below Agent answers, using only real PDF-extracted `image_description` sources and limiting display to the most relevant deduplicated images.
- [x] Added image previews to the citation drawer for image-description sources.
- [x] Verification: focused tests `59 passed`; full `python -m pytest -q -> 944 passed`; `python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass`; local `/agent/query` returned image sources and static image URLs returned 200.
- **Status:** complete; service restarted on `http://127.0.0.1:8000`; stopped before human verification and before any git add/commit/tag/push.

### Phase 49: figure lightbox, evidence fallback, and closeout handoff

- [x] Updated frontend figure cards to open in an in-page lightbox instead of a new tab.
- [x] Added close affordances for enlarged images: close button, backdrop click, and `Escape`.
- [x] Renumbered displayed figures from `Figure 1`, `Figure 2`, etc.; removed chunk labels from the UI and showed source paper title plus derived page/image label.
- [x] Added Agent response enrichment so same-document `image_description` evidence can be returned when the top-k answer sources are text-only but relevant figures exist in the same paper.
- [x] Bumped static asset versions to `phase45-figure-lightbox-fix1`.
- [x] Verification: `node --check app/frontend/static/app.js -> passed`; `python -m pytest tests/test_frontend_app.py tests/test_agent_api.py -q -> 39 passed`; `/agent/query` for `界面微观结构` returned 2 image sources and both static image URLs returned HTTP 200.
- [x] Known issue deferred: some extracted figures are cropped or fragment-like due to PDF image extraction/display artifacts. The next phase should add stronger quality filters and/or page-region rendering for extreme-aspect-ratio/cropped fragments.
- **Status:** complete; user accepted deferring cropped-fragment repair to the next phase and authorized Phase 45 submit, tag, push, and GitHub merge.
