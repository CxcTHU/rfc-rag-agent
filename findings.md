# Findings & Decisions

## Requirements

- 用户要求正式进入阶段 14：真实 Embedding 与回答覆盖校准。
- 线程标题已修改为 `阶段14-真实Embedding与回答覆盖校准`。
- 目标分支为 `codex/phase-14-real-quality-calibration`。
- 阶段 14 必须从阶段 13 已完成并合并到 `main` 的状态出发。
- 必须确认 `phase-13-complete` 指向阶段 13 最终功能提交，不移动已有阶段 tag。
- 阶段 14 不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不把 HyDE 接入默认链路或自动回归、不把真实 API 调用变成 CI 必跑前提。
- 阶段 14 重点是真实 embedding 对比、真实模型或人工 Answer Coverage 校准、Decompose provenance / rerank explanation 可读化、指标对比和质量结论。
- 必须保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 旧 API 不被破坏。
- 开发阶段不写 Obsidian 小 Phase 汇报；阶段收尾统一补齐。

## Current Project Findings

- 当前工作区已切换到 `codex/phase-14-real-quality-calibration`。
- `main` 当前提交为 `27b25d38f1c747dbe965bd447c60a975f8924cf7`，提交信息为 `Merge phase 13 decompose evidence merge`。
- `phase-13-complete` 指向 `69a28cdac12adc772dd1fd31854506cf4ca0ca6a`。
- 阶段 13 功能提交已被 `main` 合并；阶段 14 分支从合并后的 `main` 创建。
- 旧 `task_plan.md`、`findings.md`、`progress.md` 均为阶段 13 工作记忆，需要改写为阶段 14。
- Planning with Files 的 session-catchup 脚本在 `C:\Users\admin\.claude\skills\planning-with-files\scripts\session-catchup.py` 不存在；当前通过直接读取 Git、文档和旧记忆文件恢复上下文。

## Architecture Findings

- `EmbeddingProvider` 是向量模型适配层，当前有 `DeterministicEmbeddingProvider` 和 `OpenAICompatibleEmbeddingProvider`。
- `chunk_embeddings` 记录 provider、model_name、dimension、content_hash 和 embedding_json；真实 embedding 切换后必须按 provider/model/dimension 重建索引。
- `VectorSearchService` 按当前 embedding provider 查询匹配索引；如果 provider/model/dimension 不匹配，vector 检索不会误用旧索引。
- `HybridSearchService` 组合 keyword/vector 召回，保留 both-match 信号和可解释合并基础。
- `BrainService` 默认 workflow 是 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer`。
- 阶段 13 已在 Brain hybrid 路径中接入 Decompose：先 `decompose_query()`，只有 decomposed 时才调用 `DecomposeRetrievalService`。
- `MergedEvidence` 像普通 SearchResultLike 一样进入 Brain，同时保留 `sub_queries`、`both_match`、`topic_score`、`final_score` 和 `explanation`。
- `evaluate_evidence_confidence()` 位于 Brain 生成前，阶段 14 不能绕过低证据拒答。

## Existing Code Findings

- `scripts/evaluate_model_configs.py` 已能汇总 deterministic 与 real_config 结果，并在真实配置缺失时输出 skipped。
- `scripts/evaluate_vector_search.py` 支持 `--provider`、`--skip-index-build`，可显式使用 deterministic 或真实 embedding provider。
- `scripts/evaluate_hybrid_search.py` 与 vector 评测类似，是阶段 14 真实 embedding 对比的重要输入。
- `scripts/evaluate_user_questions.py` 比较 `default_hybrid`、`keyword_baseline`、`vector_only`，输出来源命中、拒答、引用有效性和答案文本。
- `scripts/evaluate_decompose.py` 输出 sub query、去重、provenance、source hit、answer_coverage_proxy 和 rerank_explanations。
- `docs/stage12_quality_review.md` 已定义 Faithfulness、Answer Coverage、Citation Quality 的人工审阅 rubric。
- `docs/stage13_decompose_plan.md` 已定义 Decompose、provenance、可解释 rerank 和 HyDE 边界。

## Evaluation Findings

- 阶段 13 Decompose 评测：`6/6 passed`。
- 阶段 13 全用户问题 Decompose 评测：`10/10 passed`。
- 阶段 13 用户问题评测：`29/30 passed`，`refusal_matched=30/30`，`source_hit_matched=29/30`。
- deterministic 回归保持稳定：chat 6/6、agent 5/5、Brain workflow 18/18、hybrid 15/15、vector 13/15。
- 阶段 12 审阅结论仍成立：deterministic answer 适合稳定回归，但不能单独证明真实 Answer Coverage。
- 阶段 13 遗留问题是：vector-only 仍有 1 条来源命中不匹配；Decompose provenance 主要在内部结构和 CSV 中，尚未做更强可读化。

## Data Source Findings

- 阶段 14 不新增外部文献来源，不新增爬虫链路，不保存受限全文。
- 阶段 14 新增的设计文档、评测 CSV、审阅 CSV 和测试文件都是工程/评测产物，不是资料来源。
- 真实 API key 只允许存在本地 `.env`，不能写入文档、CSV、测试或 Obsidian。
- Answer Coverage 校准表可以保存问题、来源标题、片段摘要、答案和人工/规则判定，但不得保存供应商原始响应敏感字段或 API key。

## Technical Decisions

| Decision | Reason |
|---|---|
| 阶段 14 先写设计文档 | 真实 API、人工审阅和可读化边界复杂，需要先固定口径 |
| 保留 deterministic baseline | 保障本地回归稳定，避免网络和限流影响 CI |
| 真实配置缺失时写 skipped | 满足可复现，不伪造真实模型结果 |
| embedding 对比优先复用已有评测脚本 | 减少重复逻辑，保持阶段间指标可比较 |
| Answer Coverage 输出校准表 | 自动评测只能近似，需要把审阅证据结构化 |
| provenance 可读化优先放在评测产物 | 保持 API schema 兼容，避免阶段 14 变成前端重构 |
| HyDE 不进默认链路 | 避免假想答案污染引用和自动回归 |

## Phase Findings

### Phase 0

- 线程标题已修改为阶段 14。
- 已阅读 Planning with Files 技能说明。
- 已确认 `main` 是阶段 13 合并后的状态。
- 已确认 `phase-13-complete -> 69a28cd`，不移动既有 tag。
- 已创建并切换阶段 14 分支。
- 三份 Planning with Files 文件已校准为阶段 14。
- 起点全量测试通过：`.venv\Scripts\python.exe -m pytest -q` -> `257 passed`。

### Phase 1

- Phase 1 目标是把阶段 14 的真实 embedding 对比、Answer Coverage 校准、graceful skip 和 provenance 可读化边界固化成可测试设计。
- 新增 `docs/stage14_real_quality_calibration.md`。
- 文档明确阶段 14 不替换默认 RAG 链路，不让真实 API 成为自动回归前提。
- 文档定义 `data/evaluation/stage14_embedding_comparison.csv` 和 `data/evaluation/stage14_answer_coverage_review.csv` 两个核心产物。
- 文档复用阶段 12 的 Faithfulness、Answer Coverage、Citation Quality rubric。
- 文档明确真实 API 缺失、HTTP 429、超时、余额不足、维度不匹配等情况必须写 skipped 或 error。
- 新增 `tests/test_stage14_real_quality_calibration.py`，覆盖核心产物、质量 rubric、skip 规则、API 兼容和阶段边界。
- Phase 1 测试结果：`3 passed`。

### Phase 2

- Phase 2 目标是把真实 embedding 对比从文档设计变成可运行脚本和结构化结果表。
- 新增 `scripts/evaluate_stage14_embedding_comparison.py`。
- 新增 `tests/test_evaluate_stage14_embedding_comparison.py`。
- 新增 `data/evaluation/stage14_embedding_comparison.csv`。
- 脚本汇总 `vector`、`hybrid`、`user_questions`、`decompose`、`chat`、`agent`、`brain_workflow` 七个 suite。
- deterministic baseline 当前结果：vector `13/15`，hybrid `15/15`，user_questions `29/30`，decompose `10/10`，chat `6/6`，agent `5/5`，brain_workflow `18/18`。
- 当前本地真实 embedding 配置完整，但 `data/evaluation/stage14_real/` 下没有阶段 14 真实结果文件，因此 real_config 行记录为 `missing_results`，没有伪造成功指标。
- `failed_queries` 字段保留失败 query：deterministic vector 2 个失败，user_questions 1 个失败。
- Phase 2 测试结果：`6 passed`。

### Phase 3

- Phase 3 目标是把 Answer Coverage、Faithfulness、Citation Quality 变成阶段 14 可复核表，而不是只依赖来源命中。
- 新增 `scripts/evaluate_stage14_answer_coverage.py`。
- 新增 `tests/test_evaluate_stage14_answer_coverage.py`。
- 新增 `data/evaluation/stage14_answer_coverage_review.csv`。
- 默认校准表包含 10 条 `default_hybrid` deterministic 审阅行；因为 deterministic answer 多为规则式回显，answer_coverage 标为 `review`，不是强行 pass。
- unsupported 随机问题正确拒答，标为 `pass/pass/pass` 和 `low` 风险。
- `--include-real-config` 当前生成 10 条 `real_config` skipped 行，原因是 `data/evaluation/stage14_real/user_question_results.csv` 不存在；脚本没有伪造真实模型审阅。
- 校准表同时带入阶段 13 的 `decompose_applied` 和 provenance 摘要，服务 Phase 4 的可读化工作。
- Phase 3 测试结果：`6 passed`。

### Phase 4

- Phase 4 目标是把阶段 13 的长字符串 rerank explanation 拆成可逐条审阅的证据级结构。
- 新增 `scripts/evaluate_stage14_decompose_provenance.py`。
- 新增 `tests/test_evaluate_stage14_decompose_provenance.py`。
- 新增 `data/evaluation/stage14_decompose_provenance_review.csv`。
- 可读化表一行对应一个 top evidence，字段包括 evidence_rank、evidence_title、evidence_sub_query_count、topic_terms、both_match、source_type、raw_score、final_score、deduplicated_count、provenance_present、review_note。
- 当前输出 50 行证据级记录，其中 decomposed_rows=15、both_match_rows=40。
- 前端暂不修改：外部 API schema 未改变，CSV 已满足只读审阅需求，阶段 14 不做前端重构。
- Phase 4 测试结果：`3 passed`。

### Phase 5

- Phase 5 目标是确认阶段 14 新增脚本和评测产物不会破坏既有 RAG、Agent、API、source 和 frontend 入口。
- 阶段 14 聚焦测试通过：`49 passed`。
- 显式 deterministic vector：`13/15 passed`，失败为 `mesoscopic_modeling` 和 `construction_management`，均为 keyword_only_pass。
- 显式 deterministic hybrid：`15/15 passed`，`rescued_vector=2`，`regressed_keyword=0`。
- 显式 deterministic user questions：`25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。这与阶段 13 当前文档中的 29/30 不同，原因是 Phase 5 强制使用 deterministic embedding，保留了更多 vector_only 失败边界。
- deterministic Decompose 全用户评测：`10/10 passed`，`decomposed=3`，`refused=1`，`source_hit_matched=10/10`。
- chat：`6/6 passed`；agent：`5/5 passed`；Brain workflow：`18/18 passed`。
- API/前端聚焦测试：`28 passed`。
- 核心服务聚焦测试：`75 passed`。
- 阶段 14 comparison 结果已更新：deterministic user_questions 为 `25/30`，real_config 仍为 `missing_results`。
- 阶段 14 answer coverage 结果：`20 rows`，`low=1`，`medium=9`，`skipped=10`。
- 阶段 14 provenance review 结果：`50 evidence rows`，`decomposed_rows=15`，`both_match_rows=37`。

### Phase 6

- Phase 6 目标是把阶段 14 的代码、评测产物、普通文档、Obsidian 本地知识库和最终全量测试统一收口。
- `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD` 已同步到阶段 14 完成状态，并把下一阶段建议校准到阶段 15。
- Obsidian 已补齐阶段 14 阶段页、Phase 0-6 汇报、阶段汇报索引、阶段索引、首页、分类页和知识点页。
- 每篇 Obsidian Phase 汇报均包含 10 个固定小节，`obsidian-vault/` 仍被 Git 忽略。
- 最终全量测试通过：`.venv\Scripts\python.exe -m pytest -q` -> `275 passed`。
- 阶段 14 最终提交和 `phase-14-complete` tag 应在这些收尾内容之后创建，tag 必须指向最终功能提交。

## Term Explanations

| Term | Explanation |
|---|---|
| 真实 embedding | 由外部 OpenAI-compatible embedding 服务生成的语义向量，在本项目通过 `OpenAICompatibleEmbeddingProvider` 接入 |
| provider/model/dimension | 向量索引的身份三元组，用来避免不同模型的 embedding 混用 |
| Answer Coverage | 回答是否覆盖 `expected_answer_points` 中的关键技术点 |
| Faithfulness | 回答是否严格来自检索证据，没有资料外断言 |
| Citation Quality | 引用是否能追溯并支撑回答中的关键说法 |
| Graceful skip | 外部真实模型不可用时，把结果记录为 skipped 或 error，而不是伪造成功或让本地测试失败 |
| Provenance | 证据来源说明，本项目中主要指 chunk 由哪个 sub query 召回 |
| Rerank explanation | 排序解释，说明为什么某条证据排在前面 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| Planning catchup 脚本不存在 | `session-catchup script not found` | 直接读取 Git、文档和旧 planning 文件恢复上下文，并记录在 Phase 0 |
| real_config 有配置但缺少阶段 14 真实结果文件 | `stage14_embedding_comparison.csv` 中 real_config 为 `missing_results` | 保留为可追踪状态，不伪造真实评测成功；后续如运行真实评测可把结果放入 `data/evaluation/stage14_real/` |
| deterministic answer 不能证明覆盖度 | `stage14_answer_coverage_review.csv` 中默认链路多数为 answer_coverage=`review` | 保留为人工/真实模型校准入口，不把 deterministic 回显当作真实回答质量 |
| Decompose explanation 原始字段过长 | `stage13_decompose_results.csv` 的 `rerank_explanations` 是多条解释拼接字符串 | 新增证据级 `stage14_decompose_provenance_review.csv`，拆出 rank、topic_terms、both_match、source_type 和分数 |
| 显式 deterministic 用户问题结果低于阶段 13 记录 | `evaluate_user_questions.py --embedding-provider deterministic` -> `25/30`，阶段 13 文档记录为 `29/30` | 阶段 14 区分 deterministic baseline 与真实/默认配置结果，保留 25/30 作为显式 deterministic 质量边界 |

## Resources

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/model_provider_evaluation.md`
- `docs/stage12_quality_review.md`
- `docs/stage13_decompose_plan.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `app/services/retrieval/embedding.py`
- `app/services/retrieval/vector_search.py`
- `app/services/retrieval/hybrid_search.py`
- `app/services/retrieval/decompose.py`
- `app/services/brain/service.py`
- `scripts/evaluate_model_configs.py`
- `scripts/evaluate_vector_search.py`
- `scripts/evaluate_hybrid_search.py`
- `scripts/evaluate_user_questions.py`
- `scripts/evaluate_decompose.py`
- `data/evaluation/user_questions.csv`
- `data/evaluation/stage13_decompose_results.csv`
