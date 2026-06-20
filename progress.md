# 阶段 46 Progress：图片质量修复与题注关联

## Session: 2026-06-20

### Phase 16：真实语料图片召回评测集（Codex）
- **Status:** complete

Actions taken:

- 复读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 运行 `git status -sb` 与 `git log --oneline -5`，确认当前分支为 `codex/phase-46-image-quality-caption`，Phase 45 merge 位于最新 main 记录中，继续保留全部未提交 Phase 46 改动。
- 将 Phase 16-21 追加到 `task_plan.md`。
- 新增 `scripts/build_phase46_real_image_retrieval_questions.py`，从本地 SQLite 的真实 `image_description` chunks、caption、page_number、document title 与 source image path 生成评测集。
- 生成 `data/evaluation/phase46_real_image_retrieval_questions.csv`。

Verification:

```text
python scripts\build_phase46_real_image_retrieval_questions.py ->
  wrote=100
  categories=image_helpful:25,must_have_image:25,no_image:25,text_only:25

CSV checks ->
  rows=100
  positive=50
  positive_caption_blank=0
  positive_path_blank=0
  positive_page_blank=0

python -m py_compile scripts\build_phase46_real_image_retrieval_questions.py -> passed
```

Outcome:

- Phase 16 完成。主评测集不再使用合成 fixture；正例全部绑定真实图片路径、页码和 caption 关键词。
- 下一步进入 Phase 17：实现真实 DB 图片召回评测脚本。
- 仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

### Phase 17：真实图片召回评测脚本（Codex）
- **Status:** complete

Actions taken:

- 新增 `scripts/evaluate_phase46_real_image_retrieval.py`。
- 默认 `stored_embedding_proxy` 模式不调用真实 API：检测 DB 中现有 image embedding 身份，正例使用 expected image chunk 的已存 embedding 作为 query vector proxy，负例使用零向量以评估图片抑制。
- 该模式仍调用生产 `AgentToolbox.search_figures()`，覆盖本地 FAISS/vector cache、阈值、质量检查、去重、caption/page_number 元数据和 deterministic 判定。
- 预留 `--query-embedding-mode real`，仅供后续人工授权真实 query embedding 校准使用。
- 新增 `tests/test_phase46_real_image_retrieval_eval.py`，覆盖 CSV schema、proxy provider 和 summary/gate 逻辑。

Verification:

```text
python -m py_compile scripts\evaluate_phase46_real_image_retrieval.py scripts\build_phase46_real_image_retrieval_questions.py -> passed
python -m pytest tests\test_phase46_real_image_retrieval_eval.py -q -> 3 passed
```

Outcome:

- Phase 17 完成。下一步进入 Phase 18：运行真实语料 baseline。
- 仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

### Phase 18：真实语料 baseline 评测（Codex）
- **Status:** complete

Actions taken:

- 运行 100 条真实语料图片召回评测集，使用离线 `stored_embedding_proxy` 模式与 `min-score=0.50`。
- 输出：
  - `data/evaluation/phase46_real_image_retrieval_results.csv`
  - `data/evaluation/phase46_real_image_retrieval_summary.csv`

Verification:

```text
python scripts\evaluate_phase46_real_image_retrieval.py --query-embedding-mode stored_embedding_proxy --top-k 4 --min-score 0.50 ->
  image_precision=0.9305
  image_recall=0.9600
  must_have_recall=1.0000
  image_helpful_hit_rate=0.9200
  image_suppression=1.0000
  topk_caption_match_rate=0.8800
  wrong_generic_curve_rate=0.0000
  threshold_decision=pass
```

Outcome:

- Baseline 达到用户给定门槛：precision>=0.75、must_have_recall>=0.75、suppression>=0.85、topk_caption_match_rate>=0.70、wrong_generic_curve_rate<=0.10。
- 两条 `image_helpful` 水化热问题未返回图片，但全部 `must_have_image` 命中、全部负例被抑制。
- Phase 19 caption-weighted soft rerank 当前不触发；继续进入 Phase 19/20 的跳过记录和 Phase 21 收口。
- 仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

### Phase 19：caption-weighted soft rerank 条件判定（Codex）
- **Status:** skipped_not_triggered

Actions taken:

- 按 Phase 18 gate 判定：baseline 已通过，不进入 rerank 实施。
- 未修改 `search_figures` 排序逻辑、阈值、DB、embedding 或 FAISS。

Outcome:

- 暂不做 caption-weighted soft rerank。
- 保留后续建议：如人工授权的 `--query-embedding-mode real` 评测暴露自然语言 query embedding 误召，再优先把当前 specific-term hard requirement 改为 caption-weighted soft rerank。
- 仍未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

### Phase 20：caption-enhanced embedding readiness 条件判定（Codex）
- **Status:** skipped_not_needed

Actions taken:

- 因 Phase 19 未触发，未运行 embedding readiness。
- 未调用真实 embedding API，未更新 DB，未重建 FAISS。

Outcome:

- 当前不需要重做 image embeddings；普通 text chunks 不动。
- 仍需等待用户人工核验后才能进入任何提交/tag/push/PR 流程。

### Phase 21：收口验证与文档（Codex）
- **Status:** complete

Actions taken:

- 运行 focused tests、Stage 30、最终真实图片召回评测和全量 pytest。
- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-46.md`。
- 更新 `task_plan.md`、`findings.md`、`progress.md`，记录 100 条真实评测覆盖、baseline、Phase 19/20 未触发和无需 embedding 重建。
- 本轮 Phase 16-21 只新增评测数据/脚本/文档，没有 API 或前端行为变化，因此未新增 8000 smoke。

Verification:

```text
focused tests -> 6 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts\evaluate_phase46_real_image_retrieval.py --query-embedding-mode stored_embedding_proxy --top-k 4 --min-score 0.50 -> threshold_decision=pass
python -m pytest -q -> 996 passed
```

Outcome:

- Phase 46 Phase 16-21 完成，停在用户人工核验前。
- 未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

## Session: 2026-06-19

### Phase 8: caption propagation to retrieval, agent, and frontend (Codex)
- **Status:** complete

Actions taken:

- Added `caption` support to repository chunk creation and propagated the field through keyword/vector/hybrid/BM25/RRF/decompose retrieval result types.
- Added caption propagation through prompt context, agent tool result objects, agent/chat/document API schemas, and response builders.
- Updated frontend figure evidence cards to use `source.caption` as the preferred image title, with the existing title fallback preserved.
- Confirmed Phase 5's rebuilt paratera FAISS index remains current for embeddings; caption metadata does not change vector contents.

Verification:

```text
python -m pytest tests\test_prompt_builder.py tests\test_agent_tools.py tests\test_agent_api.py tests\test_phase46_caption_extractor.py tests\test_phase46_caption_backfill.py tests\test_phase46_db_stats.py -q -> 60 passed
python -m pytest tests\test_bm25_search.py tests\test_rrf_fusion.py tests\test_decompose_retrieval.py tests\test_context_expansion.py tests\test_prompt_builder.py tests\test_agent_tools.py tests\test_agent_api.py -q -> 71 passed
```

Outcome:

- Phase 8 complete. Next phase is Phase 9 full regression, Stage 30 verification, API/browser smoke, docs, phase review draft, and Obsidian closeout.

### Phase 7: full caption backfill (Codex)
- **Status:** complete

Actions taken:

- Added `scripts/backfill_phase46_captions.py` and `tests/test_phase46_caption_backfill.py`.
- Ran full caption dry-run, inspected failure distribution, then backed up SQLite to `data/app.sqlite.backup-before-phase46-caption-apply-20260619-235900`.
- Ran full `--apply`, updating `chunks.caption` for matched image captions and clearing no-caption rows.
- Updated `scripts/collect_phase46_db_stats.py` to include `captioned_image_chunks`.

Verification:

```text
python -m pytest tests\test_phase46_caption_backfill.py tests\test_phase46_caption_extractor.py -q -> 9 passed
python scripts\backfill_phase46_captions.py --apply ->
  total_images=15628
  captioned=7853
  no_caption=7741
  failed=34
python scripts\collect_phase46_db_stats.py ->
  captioned_image_chunks=7853
  image_chunks=15628
  image_embeddings=15628
  orphan_embeddings=0
```

Outcome:

- Phase 7 complete. Next phase is Phase 8 caption propagation to search/agent/frontend evidence cards.

### Phase 6: caption extractor and nullable schema (Codex)
- **Status:** complete

Actions taken:

- Added nullable `Chunk.caption` field in `app/db/models.py`.
- Added Alembic migration `alembic/versions/20260619_0003_chunk_caption.py` and applied it locally with `python -m alembic upgrade head`.
- Added `app/services/ingestion/caption_extractor.py` using PyMuPDF text block bbox extraction and image bbox matching.
- Covered original image paths, rendered image paths, Chinese/English caption prefixes, cross-page top-of-next-page captions, and no-caption behavior.

Verification:

```text
python -m py_compile app\services\ingestion\caption_extractor.py -> pass
python -m pytest tests\test_phase46_caption_extractor.py -q -> 7 passed
caption column exists in local SQLite chunks table -> True
```

Outcome:

- Phase 6 complete. Next phase is Phase 7 full caption backfill and coverage report.

### Phase 5: GLM-4.6V redescription + DB merge + embeddings (Codex)
- **Status:** complete

Actions taken:

- Stored the three user-provided vision keys in User env and ran Phase 5 through explicit route envs without writing key values to repo files.
- Split the 1,995 rendered repair images into 5 route manifests under `data/evaluation/phase46_redescribe_manifests/`.
- Ran smoke staging for official A, official B, and Paratera; all succeeded.
- Ran full staging through initial, resume1, and resume2 passes; generated final de-duplicated `data/evaluation/phase46_redescribe_report.csv`.
- Backed up SQLite to `data/app.sqlite.backup-before-phase46-redescribe-import-20260619-233444` before serial import.
- Imported final staging report into SQLite and rebuilt paratera embeddings + FAISS.

Verification:

```text
python scripts\summarize_phase46_redescribe_staging.py ... ->
  expected_images=1995
  described_images=1995
  missing_images=0
  failed_rows_seen=22
  duplicate_described_rows=0

python scripts\import_multimodal_staging.py --staging-csv data\evaluation\phase46_redescribe_report.csv ->
  staging_rows=1995
  described_rows=1995
  created_chunks=1995
  skipped_existing_chunks=0
  skipped_invalid_rows=0

python scripts\build_vector_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 ->
  indexed=2807
  skipped=36316

python scripts\build_faiss_index.py --provider paratera --model-name GLM-Embedding-3 --dimension 2048 ->
  vectors=39123

python scripts\collect_phase46_db_stats.py ->
  image_chunks=15628
  image_embeddings=15628
  render_image_chunks=1995
  render_image_embeddings=1995
  orphan_embeddings=0
```

Outcome:

- Phase 5 complete. Next phase is Phase 6 caption extractor + nullable Chunk.caption schema migration.

### Phase 5a: orientation residual audit/repair (subagent + Codex review)
- **Status:** complete

Actions taken:

- Spawned worker subagent to complete the inverted/mirrored/rotated image residual line without touching Phase 5 redescription staging, DB merge, or real vision APIs.
- Added `scripts/audit_phase46_orientation_residuals.py` and `tests/test_phase46_orientation_residual_audit.py`.
- Generated `data/evaluation/phase46_orientation_residual_candidates.csv` and `data/evaluation/phase46_orientation_residual_summary.json`.
- Reviewed worker output in the main agent and accepted Phase 5a as closed because no non-Type A/C residual with chunk+embedding remains.

Verification:

```text
python -m py_compile scripts\audit_phase46_orientation_residuals.py -> pass
python -m pytest tests\test_phase46_orientation_residual_audit.py -q -> 4 passed
phase46_orientation_residual_summary.json ->
  candidates_total=88
  fixed=86
  cleanup_resolved=2
  still_candidate=0
  failed=0
  phase45_original_failed=2
```

Outcome:

- The two Phase45 failed orientation rows are doc421 Type A images and Phase46 cleanup removed their chunks/embeddings.
- No `--apply` repair is needed; no extra GLM redescription task is created by Phase 5a.

### Phase 5: vision route correction and staging support (Codex)
- **Status:** in_progress_waiting_for_visible_vision_route_env

Actions taken:

- Rechecked the Phase45 GLM-4.6V route mechanism after user feedback. The earlier wording "no vision provider" was too broad: unified `VISION_MODEL_*` is empty, but Phase45 used route-level vision key env plus explicit provider/base_url/model parameters.
- Updated `scripts/process_multimodal_to_staging.py` with `--vision-provider`, `--vision-model-name`, `--vision-api-key-env`, `--vision-api-key`, `--vision-base-url`, and `--vision-timeout-seconds`.
- Updated `scripts/check_phase46_redescribe_readiness.py` so readiness accepts either unified `VISION_MODEL_*` or Phase45/custom routes. Added `--vision-route label,provider,model,key_env,base_url`.
- Checked current `.env` key names without printing values. It contains chat/planner/embedding/rerank/stage30/Jina keys, but not `VISION_MODEL_*`, `OFFICIAL_GLM_KEY`, or `PARATERA_GLM_KEY`. Current Codex process also cannot see those route env vars, so readiness is still blocked by invisible route env, not by missing route support.

Verification:

```text
python -m py_compile scripts\process_multimodal_to_staging.py scripts\check_phase46_redescribe_readiness.py -> pass
python -m pytest tests\test_phase46_redescribe_readiness.py tests\test_stage45_multimodal_staging.py -q -> 10 passed
python scripts\check_phase46_redescribe_readiness.py ->
  status=blocked
  pending_images=1995
  phase45_route_vision_configured=False
  configured_vision_routes=0
  missing_vision_route_key_envs=[OFFICIAL_GLM_KEY, PARATERA_GLM_KEY]
```

Next:

- Run readiness/staging with the user's actual three vision API env names via `--vision-route ...` and `--vision-api-key-env ...`, then continue Phase 5 GLM-4.6V redescription, serial DB merge, and embedding update.
- Do not enter Phase 6 until Phase 5 real vision redescription is complete. Do not run git add/commit/tag/push/PR.

### Phase 5：第三次连续阻塞复核（Codex）

- **Status:** blocked_waiting_for_real_vision_config

Actions taken:

- 重新运行 `git status -sb`，确认当前仍在 `codex/phase-46-image-quality-caption`，未 stage/commit/tag/push/PR。
- 重新运行 `python scripts\check_phase46_redescribe_readiness.py`。
- 重新用 `get_settings()` 检查 vision 与 embedding 配置存在性，只输出布尔值，不输出 key/base URL。

Verification:

```text
python scripts\check_phase46_redescribe_readiness.py ->
  status=blocked
  pending_images=1995
  vision_provider_configured=False
  vision_model_configured=False
  vision_base_url_configured=False
  vision_api_key_configured=False
  vision_provider_is_real=False

get_settings config check ->
  vision_provider_configured False
  vision_model_configured False
  vision_base_url_configured False
  vision_key_configured False
  embedding_provider_configured True
  embedding_key_configured True
```

Conclusion:

- 这是同一 Phase 5 阻塞条件的第三次连续 goal turn：真实 GLM-4.6V/OpenAI-compatible vision 配置缺失。
- 按阶段顺序，不能跳到 Phase 6；按安全边界，不能用 deterministic vision 冒充真实重描述。
- 下一步仍是补齐本地 `VISION_MODEL_PROVIDER`、`VISION_MODEL_NAME`、`VISION_MODEL_BASE_URL`、`VISION_MODEL_API_KEY` 后继续执行 readiness JSON 中的 next_command。

### Phase 5：修复图片重描述准备与阻塞（Codex）

- **Status:** blocked_waiting_for_real_vision_config

Actions taken:

- 阅读阶段 45 staging 相关脚本：
  - `scripts/process_multimodal_to_staging.py`
  - `scripts/import_multimodal_staging.py`
  - `scripts/index_phase45_cloud_candidates.py`
  - `app/services/generation/vision_model.py`
- 新增 `scripts/build_phase46_render_manifest.py`，生成 render 图片 manifest。
- 新增 `tests/test_phase46_render_manifest.py`。
- 新增 `scripts/check_phase46_redescribe_readiness.py`，生成脱敏 readiness JSON，避免在未配置真实 vision provider 时误跑 deterministic。
- 新增 `tests/test_phase46_redescribe_readiness.py`。
- 运行 render manifest 生成。
- 检查 `.env` 中 vision 配置是否存在，只输出布尔/变量名，不输出任何 key 或 base URL 值。

Verification:

```text
python -m pytest tests/test_phase46_redescribe_readiness.py tests/test_phase46_render_manifest.py tests/test_stage45_multimodal_staging.py -q -> 7 passed
python scripts\build_phase46_render_manifest.py ->
  rows=1995 pending=1995 existing=0 failed=0
python scripts\check_phase46_redescribe_readiness.py ->
  status=blocked pending_images=1995
  vision_provider_configured=False
  vision_model_configured=False
  vision_base_url_configured=False
  vision_api_key_configured=False
  vision_provider_is_real=False
vision_provider/config check ->
  vision_provider empty
  vision_model empty
  vision_base_url_configured=False
  vision_key_configured=False
  embedding_provider=paratera
  embedding_key_configured=True
```

Blocker:

- Phase 5 要求对修复图片调用 GLM-4.6V 重描述，但当前本地没有 `VISION_MODEL_*` 配置。
- 不能用 deterministic vision 描述冒充真实 GLM-4.6V 结果。
- 按 task_plan Phase 顺序，暂不进入 Phase 6 题注开发，等待用户补齐 vision 配置或明确授权替代路径。

Next command once config is available:

```powershell
python scripts\process_multimodal_to_staging.py `
  --image-manifest data\evaluation\phase46_rendered_image_manifest.csv `
  --workers 5 `
  --output-dir data\evaluation\phase46_redescribe_staging
```

### Phase 4：Type B 剩余文档全量修复（Codex）

- **Status:** complete

Actions taken:

- 从 Phase 1 manifest 中选取剩余 Type B 文档，排除 Phase 3 试点 140/431/349/144/16。
- 剩余 Type B 文档共 38 篇：1064、1086、1089、1093、1094、1117、1126、1133、1134、1136、1138、1140、1142、1168、1244、1317、1344、1354、145、146、147、150、1554、1577、166、172、290、291、318、366、395、396、416、435、437、443、448、458。
- 先 dry-run，再执行 `scripts\fix_phase46_fragment_images.py --apply`。
- 抽检 `data/images/1136/page40_render1.png`，确认为完整工程图。

Verification:

```text
dry-run -> documents=38 old_type_b_chunks=192
apply -> documents=38 rendered_images=1906 deleted_chunks=192 deleted_embeddings=192
phase3+phase4 total -> rendered_images=1995 deleted_chunks=393 deleted_embeddings=393
post-phase4 DB -> image_chunks=13633 image_embeddings=13633 orphan_embeddings=0
```

Notes:

- PyMuPDF 输出一次 `format error: No common ancestor in structure tree` warning，但 report 中 38 篇均 status=fixed。
- 当前 `data/evaluation/phase46_fragment_fix_report.csv` 记录 Phase 4 的 38 篇批量修复；Phase 3 试点统计已记录在本 progress/findings 中。

Outcome:

- Phase 4 完成。
- 下一步进入 Phase 5：对 1,995 张新 render 图片做视觉重描述、创建 image_description chunks 和 embeddings。

### Phase 3：Type B 页面级重渲染试点（Codex）

- **Status:** complete

Actions taken:

- 扩展 `app/services/ingestion/image_extractor.py`，新增页面级 `extract_images_page_render()`、`image_rects_from_page()`、`merge_image_rects()`、`rect_iou()`。
- 更新 `tests/test_stage45_image_extractor.py`，覆盖 bbox 合并与页面级渲染。
- 新增 `scripts/fix_phase46_fragment_images.py`，默认处理试点文档 140/431/349/144/16。
- 新增 `tests/test_phase46_fragment_fix.py`，覆盖 manifest Type B 读取、dry-run、apply 删除旧 chunk/embedding。
- 对试点文档先 dry-run，再执行 `--apply`。
- 抽检 `data/images/140/page7_render1.png`，确认多个旧碎片合并为完整图表。

Verification:

```text
python -m pytest tests/test_phase46_image_quality_manifest.py tests/test_phase46_cleanup.py tests/test_stage45_image_extractor.py tests/test_phase46_fragment_fix.py -q -> 13 passed
python scripts\fix_phase46_fragment_images.py -> documents=5 dry_run=True
python scripts\fix_phase46_fragment_images.py --apply ->
  documents=5 rendered_images=89 deleted_chunks=201 deleted_embeddings=201
post-pilot DB -> image_chunks=13825 image_embeddings=13825 orphan_embeddings=0
```

Outcome:

- Phase 3 试点完成；页面级渲染方案有效。
- 下一步进入 Phase 4：对剩余 Type B 文档批量修复。

### Phase 2：Type A + Type C 清理（Codex）

- **Status:** complete

Actions taken:

- 新增 `scripts/clean_phase46_decoration_empty.py`，读取 Phase 1 manifest，只处理 `type_a` 与 `type_c`。
- 新增 `tests/test_phase46_cleanup.py`，覆盖 dry-run、Type A DB-only 删除、Type C DB+file 删除、以及拒绝删除 `data/images` 外路径。
- 运行 dry-run，生成 `data/evaluation/phase46_cleanup_report.csv`。
- 在 apply 前备份 SQLite：`data/app.sqlite.backup-before-phase46-cleanup-20260619-210928`。
- 执行 `python scripts\clean_phase46_decoration_empty.py --apply`。

Verification:

```text
python -m pytest tests/test_phase46_image_quality_manifest.py tests/test_phase46_cleanup.py -q -> 6 passed
dry-run cleanup -> targets=188 deleted_chunks=0 deleted_embeddings=0 deleted_files=0
apply cleanup -> targets=188 deleted_chunks=132 deleted_embeddings=132 deleted_files=29
post-cleanup DB -> image_chunks=14026 image_embeddings=14026 orphan_embeddings=0
```

Outcome:

- Type A/Type C 清理完成。
- Type A 磁盘文件保留；Type C 磁盘文件删除。
- 未执行 git add/commit/tag/push/PR。
- 下一步进入 Phase 3：试点 5 篇碎片文档页面级重渲染。

### Phase 1：问题图片分类 manifest 生成（Codex）

- **Status:** complete

Actions taken:

- 新增 `scripts/classify_phase46_problem_images.py`，只读扫描 DB image chunks 与 `data/images/**/*.png`，输出 normal/type_a/type_b/type_c manifest。
- 新增 `tests/test_phase46_image_quality_manifest.py`，覆盖 Type A/Type B/Type C 分类、DB+磁盘文件合并、CSV 输出。
- 首次按朴素规则运行时发现过宽：重复尺寸会误抓正常大图，整页碎片规则会误抓同页普通图片。
- 校准规则：
  - Type C 优先：缺失、0 字节、或 <5KB 且任一维度 <100px。
  - Type A：同文档相同尺寸跨 ≥3 页，且低文件量（≤20KB）或低尺寸（任一维 ≤120px），覆盖页眉页脚/模板/装饰图。
  - Type B：同页 ≥3 张且存在极端宽高比；普通可疑页只标低文件量碎片，单页 ≥20 张的密集碎片页整页标记。
- 抽检确认：Type A 样本为重复页面模板/页眉页脚，Type B 样本为图表横向碎片，Type C 样本为小装饰条。

Verification:

```text
python -m pytest tests/test_phase46_image_quality_manifest.py -q -> 3 passed
python scripts\classify_phase46_problem_images.py ->
  total=14996 normal=14243 type_a=159 type_b=565 type_c=29
```

Outcome:

- `data/evaluation/phase46_image_quality_manifest.csv` 已生成。
- 问题图片合计 753 张；其中 525 张有 chunk/embedding，228 张仅磁盘文件；受影响文档 80 篇，Type B 涉及 42 篇。
- 规划中的 621 张是阶段 45 末尾估算；当前 manifest 为更保守的实际处理清单，主要因 doc 140 这类密集碎片页被完整纳入 Type B，同时阶段 45 已清理后 Type C 剩余数量下降。
- 下一步进入 Phase 2：清理 Type A + Type C。

### Phase 0：启动校准与规划落盘（Codex 执行方复核）

- **Status:** complete
- **Branch:** `codex/phase-46-image-quality-caption`

Actions taken:

- 设置线程 goal：推进阶段 46 图片质量修复与题注关联，停在用户人工核验前。
- 修改线程名称为“阶段46-图片质量修复与题注关联”。
- 阅读 Planning with Files 技能说明，以及 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 运行 `git status -sb`：切分支前 `main...origin/main`，仅 `task_plan.md`、`findings.md`、`progress.md` 有规划文件改动。
- 运行 `git log --oneline -5 --decorate`：`main / origin/main -> e1ff05da Merge phase 45 data migration multimodal RAG`；`phase-45-complete -> 35127e44 Complete phase 45 data migration multimodal RAG`。
- 运行 `git merge-base --is-ancestor phase-45-complete main`，确认 `phase-45-complete` 是 `main` 祖先；本地 main 没有停在阶段 44。
- 创建并切换分支 `codex/phase-46-image-quality-caption`。
- 校准 `task_plan.md`、`findings.md`、`progress.md`，将当前阶段推进到 Phase 1。

Outcome:

- Phase 0 完成，阶段 46 的正确起点为阶段 45 已合并后的 `main / origin/main`。
- 未移动任何 tag，未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。
- 下一步按计划进入 Phase 1：生成 `phase46_image_quality_manifest.csv`。

### Phase 9：回归验证、普通文档与 Obsidian 收尾（Codex）
- **Status:** complete

Actions taken:

- 运行全量 pytest，并修复 Phase 45 设计测试对当前根目录规划文件的误耦合，使其改读稳定的 Phase 45 归档设计文档。
- 运行 Stage 30 质量评分，确认阶段 46 未造成评分退化。
- 启动本地 API 服务并完成 `/health`、`/search/hybrid`、`/chat`、`/agent/query`、`/agent/query/stream` smoke。
- 通过浏览器验证前端图片 evidence card 使用 caption 标题展示，并检查 desktop/mobile 视口无横向溢出。
- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，新增 `docs/phase_reviews/phase-46.md`。
- 补齐 Obsidian 阶段页、阶段汇报索引、收尾汇报，以及 Obsidian 根索引入口。

Verification:

```text
python -m pytest -q -> 982 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
API smoke -> health/search/chat/agent query/agent stream all HTTP 200
Browser smoke -> caption titles visible; desktop and mobile overflow checks passed
```

Outcome:

- Phase 46 开发、测试、普通文档和 Obsidian 草稿已收尾。
- 当前状态停在用户人工核验前；未执行 git add/commit/tag/push/PR。

### Phase 46 追加目标启动：多模态检索解耦与按需编排（Codex）
- **Status:** in_progress

Actions taken:

- 读取 `task_plan_phase46_extension.md`，确认追加 Phase 10-15 的目标是新增 `search_figures` ReAct 工具，并降级自动图片 enrich。
- 复读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`，并检查 `git status -sb` / `git log --oneline --decorate -5`。
- 将 Phase 10-15 追加到 `task_plan.md`，当前阶段推进到 Phase 10。

Notes:

- 当前工作区包含 Phase 46 既有未提交改动，继续保留并增量开发。
- `planning-with-files` 的 `.claude` catchup 脚本在本机路径不存在，已使用当前规划文件和 git 状态恢复上下文。
- 继续保持不 git add/commit/tag/push/PR 的边界。

### Phase 10：search_figures 工具开发（Codex）
- **Status:** complete

Actions taken:

- 在 `AgentToolbox` 中新增只读 `search_figures()`，独立检索全库 `image_description` chunks。
- 新增 `MIN_IMAGE_RELEVANCE_SCORE=0.35`、图片文件/尺寸质量检查、同文档同页去重和 `FigureSearchResult` 返回结构。
- 将 `page_number` 从 `source_image_path` 解析后传入 `AgentSearchItem`、`AgentSourceReference` 和 Agent API schemas。
- 在 ReAct action 白名单和 runtime 中接入 `search_figures`，并更新 planner prompt 的调用/抑制策略。
- 扩展 `tests/test_agent_tools.py` 和 `tests/test_react_actions.py` 覆盖工具、schema 和 deterministic planner。

Verification:

```text
python -m pytest tests\test_agent_tools.py tests\test_react_actions.py -q -> 17 passed
python -m py_compile app\services\agent\tools.py app\services\agent\react_actions.py app\services\agent\react_service.py app\schemas\agent.py app\api\agent.py -> passed
```

Outcome:

- Phase 10 完成；下一步进入 Phase 11：page_number 回填与前端展示格式。

### Phase 11：图片 page_number 元数据回填（Codex）
- **Status:** complete

Actions taken:

- 通过 Alembic migration `20260620_0004_chunk_page_number.py` 新增 nullable `chunks.page_number`，并已将本地 SQLite 升级到 head。
- 将 `page_number` 贯通 retrieval result、prompt context、chat/document/agent schema 与 API response 构造。
- 新增 `scripts/backfill_phase46_image_page_numbers.py`，并对本地 DB 完成 apply 回填。
- 前端图片 evidence card 现在展示 `图 X — 第 N 页 — 《文档标题》`；存在 caption 时用 caption 作为标题，并隐藏视觉描述段落，避免把作者单位/摘要露在卡片正文。

Verification:

```text
python scripts\backfill_phase46_image_page_numbers.py --apply
  total_image_chunks=15628
  parsed_page_numbers=15628
  updated_rows=15628
  failed_to_parse=0
python -m pytest tests\test_phase46_image_page_number_backfill.py tests\test_agent_tools.py tests\test_react_actions.py tests\test_prompt_builder.py tests\test_agent_api.py -q -> 60 passed
node --check app\frontend\static\app.js -> passed
```

Outcome:

- Phase 11 完成；下一步进入 Phase 12：关闭默认自动图片 enrich，让 ReAct 图片召回走 `search_figures` 工具编排。

### Phase 12：自动图片 enrich 降级与解耦（Codex）
- **Status:** complete

Actions taken:

- 新增 `ENABLE_AUTO_FIGURE_ENRICHMENT` 配置项，默认关闭。
- 将 `/agent/query` 与 `/agent/query/stream` 的自动图片 enrich 调用统一包进 `maybe_enrich_agent_response_with_figure_evidence(...)`。
- `react_agent` 路径永远不调用旧的自动 enrich fallback；需要图片时由 `search_figures` ReAct 工具自主召回。
- 非 ReAct 路径保留旧 fallback，但必须显式打开 `ENABLE_AUTO_FIGURE_ENRICHMENT=true` 才会执行。
- `/chat` 端点未改动。

Verification:

```text
python -m pytest tests\test_agent_api.py tests\test_agent_tools.py tests\test_react_actions.py -q -> 48 passed
python -m py_compile app\core\config.py app\api\agent.py -> passed
```

Outcome:

- Phase 12 完成；下一步进入 Phase 13：构建图片召回评测集。

### Phase 13：图片召回评测集构建（Codex）
- **Status:** complete

Actions taken:

- 新增 `data/evaluation/phase46_image_retrieval_questions.csv`。
- 构建 32 条问题，覆盖 `must_have_image`、`image_helpful`、`text_only`、`no_image` 四类，各 8 条。
- 正例覆盖工程/施工流程、试验曲线、强度图表、温控图、微观结构、试验装置、裂缝破坏形态等图片类型。
- 负例覆盖定义、显式无图要求、项目行为问题和离题问题，用于量化图片抑制能力。

Verification:

```text
Import-Csv data\evaluation\phase46_image_retrieval_questions.csv
rows=32
must_have_image=8 image_helpful=8 text_only=8 no_image=8
expected_has_image true=16 false=16
```

Outcome:

- Phase 13 完成；下一步进入 Phase 14：实现并运行图片检索质量评测脚本。

### Phase 14：图片检索质量评测脚本（Codex）
- **Status:** complete

Actions taken:

- 新增 `scripts/evaluate_phase46_image_retrieval.py`，默认构建 deterministic 临时 SQLite fixture，不调用真实 API。
- 脚本对评测集逐条调用真实 `AgentToolbox.search_figures()`，输出明细与 summary CSV。
- 新增 `tests/test_phase46_image_retrieval_eval.py`。
- 根据评测结果将 `MIN_IMAGE_RELEVANCE_SCORE` 从 `0.35` 标定为 `0.50`，优先压制误召。

Verification:

```text
python scripts\evaluate_phase46_image_retrieval.py
  image_precision=1.0000
  image_recall=1.0000
  image_suppression=1.0000
  image_quality_rate=1.0000
  caption_coverage=1.0000
  page_number_coverage=1.0000
  min_image_relevance_score=0.5000
python -m pytest tests\test_phase46_image_retrieval_eval.py tests\test_agent_tools.py tests\test_react_actions.py -q -> 19 passed
python -m py_compile scripts\evaluate_phase46_image_retrieval.py app\services\agent\tools.py -> passed
```

Outcome:

- Phase 14 完成；下一步进入 Phase 15：最终回归、文档更新和人工核验前收口。

### Phase 15：最终回归、文档与人工核验前收口（Codex）
- **Status:** complete

Actions taken:

- 运行全量 pytest，并同步更新前端静态资产测试对新的 `Figure ${figureNumber}` 卡片编号变量的断言。
- 运行 Stage 30 质量评分。
- 运行 Phase 46 图片检索评测脚本，确认阈值 `0.50` 的精确率、召回率和抑制率达标。
- 启动本地 API 服务并完成 `/health`、`/search/hybrid`、`/chat`、`/agent/query`、`/agent/query/stream` smoke。
- 通过 Playwright MCP 打开本地页面，确认控制台错误为 0、无横向溢出、服务端静态 JS 包含 page_number source line、caption 标题和 caption 摘要隐藏逻辑。
- 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-46.md`。

Verification:

```text
python -m pytest -q -> 989 passed
python scripts\score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts\evaluate_phase46_image_retrieval.py -> image_precision=1.0000 image_recall=1.0000 image_suppression=1.0000
API smoke -> /health, /search/hybrid, /chat, /agent/query, /agent/query/stream all 200
Browser MCP smoke -> console errors=0, horizontal overflow=false, static figure card checks passed
```

Outcome:

- Phase 46 extension Phase 10-15 完成，整个阶段 46 当前停在用户人工核验前。
- 未执行 `git add`、`git commit`、`git tag`、`git push` 或 PR。

### Phase 0：启动校准与规划落盘（Claude 规划方）

- **Status:** complete
- **Started:** 2026-06-19

Phase purpose:

- 这一 Phase 由 Claude 规划方完成，为阶段 46 编写任务计划、发现记录和进度文件。
- 阶段 46 有两条主线：A（621 张问题图片定向修复）、B（全量图片题注提取与关联）。
- 现在做它，是因为阶段 45 完成了全库图片提取和多模态 RAG 架构，但 4.1% 的图片存在质量问题（碎片、装饰、空文件），且所有图片缺少原文题注关联，限制了检索精度和展示效果。

Actions taken:

- 确认阶段 45 最终状态：944 tests，Stage 30 = 91.52/A/pass，14,996 张图片已入库。
- 分析问题图片：621 张问题图片（478 有 chunk+embedding，143 仅磁盘），分布在 101 篇文档中。
- 确认根因：`image_extractor.py` 使用 `fitz.Pixmap(pdf, xref)` 提取原始像素，忽略页面变换矩阵。
- 确认修复方案：页面级渲染（`page.get_image_info` + bbox 合并 + `page.get_pixmap`），已由 orientation repair 脚本验证可行。
- 设计题注提取方案：PyMuPDF 空间位置匹配，正则匹配 `^图\s*[\d\.]+` 等模式。
- 编写 `task_plan.md`（10 个 Phase: 0-9）、`findings.md`、`progress.md`。

Outcome:

- 规划文件就绪，等待阶段 45 合并后 Codex 接手执行 Phase 0-9。

## Git 状态

- 阶段 45 待用户确认合并到 main。
- 阶段 46 分支 `codex/phase-46-image-quality-caption` 待创建。
- 尚未提交，等待用户人工核验。

## 测试基线

- 全量测试: 944 passed
- Stage 30: 91.52 / A / pass

## 遗留风险

- Type B 碎片图的 bbox 合并算法需要在试点文档上验证合并阈值（IoU>0.3 / 间距<20pt）。
- 题注跨页的情况可能需要特殊处理。
- GLM-4.6V 重描述需要 Paratera API 配额，批量处理时需注意限速。
