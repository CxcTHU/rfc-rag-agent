# 阶段 54 任务计划：GraphRAG 真实数据填充与端到端评测

## 总目标

Phase 53 完成了 GraphRAG 的代码骨架（schema、extractor、graph_store、graph_search、LangGraph 集成、Adaptive RAG 标签）。Phase 54 用全量 regex 抽取建立可靠图骨架，用真实 LLM 对高价值 chunk 做语义补充，并通过真实 API 端到端评测验证 graph-enhanced retrieval 相对纯向量检索的提升。

正式测评结论必须来自真实 API。deterministic / offline 测试只作为代码回归与 CI 护栏。

## 当前结论

状态：Phase 54A/54B/54C 已完成；Phase 54D 已完成 dry-run、全量 retrieval-only 和全量 answer-only 真实生成链路，正式 judge 评分待 `JUDGE_MODEL_*` 配置完成后执行。当前目标收敛为：完成 54D formal judge run，然后做 54E 文档收尾与最终回归；在 judge 不可用期间，先完成可验证文档、运行手册和配置对齐。

2026-06-25 追加 13：按用户确认，54B 不再继续追残余 hard-timeout LLM 行。补跑后 text LLM 为 `rows=2909`、`ok=2351`、`error=558`；table LLM 为 `rows=1440`、`ok=1320`、`error=120`。目标候选 `4331/4331` 已全部 attempted，且 ok rate 仍高于 70% gate。后续不再因这些 residual timeout 阻塞 54D/54E；只有 formal judged E2E 暴露具体覆盖缺口时才定向补抽。

2026-06-25 追加 14：GPU 服务器操作规则已确认。只有需要 private BGE-LoRA reranker 的 reranker-enabled 评测时，才通过 Chrome 打开 `https://ai.paratera.com/#/cloud/compute`，找到 `rfc-reranker-train-3090` 并点击 Web UI 的 `开机`；用完必须回到同一 Web UI 关机/节省，禁止用命令行关机控制计费。当前 formal judge 可先用 `RERANKING_ENABLED=false`，因此不需要立刻开 GPU。

2026-06-25 追加 15：Judge provider 诊断已完成：`https://llmapi.paratera.com/v1/chat/completions` endpoint 可达；用户更新 API key 模型权限后，GLM-5.2 最小 JSON 探针通过，`--preflight --require-judge` 通过，3 条 formal smoke 通过。

2026-06-25 追加 16：Phase 54D formal GLM-5.2 judge 全量 47 条完成并通过 gate：`completed_rows=47`、`error_rows=0`、`formal_judge_scored_rows=47`、`graph_intent_accuracy_delta=0.1471`、`graph_intent_completeness_delta=0.4412`、`graph_intent_citation_quality_delta=0.2647`、`ordinary_accuracy_delta=0.0000`、`negative_graph_false_positive_count=0`、`formal_judge_gate_decision=pass`。机器审计更新为 `complete=16`、`partial=0`、`missing=0`。

2026-06-25 追加：已同步 README、AGENT.MD、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/phase_reviews/phase-54.md 和 `docs/stage54_graphrag_evaluation_prompt.md` 的当前目标/状态。默认 `GRAPHRAG_GRAPH_PATH` 已对齐到 `data/knowledge_graph/domain_graph.json`。Focused GraphRAG/Phase54 regression `31 passed`。当前 formal acceptance 仍等待 judge provider 配置。

2026-06-25 追加 2（历史记录）：`scripts/evaluate_phase54_graphrag_e2e.py` 已新增 `--preflight` / `--require-judge`，用于不触发 API 的 formal judge 前置检查。当时本地 preflight 输出：cases/graph/chat/embedding 均 pass，`judge_provider_configured=fail`，`formal_judge_ready=fail`。后续用户更新 API key 模型权限后，该检查已通过。

2026-06-25 追加 3：54D summary 已新增 formal gate 判定。只有所有 rows 都是 `status=completed` 且有 judge 分数时，才输出 `formal_judge_gate_decision=pass|review_required`；部分 judge / answer-only / retrieval-only 仍输出 `pending` 或不输出 gate，避免把 smoke 当验收。当前 focused regression `34 passed`。

2026-06-25 追加 4：formal judge 前回归基线已完成：`python scripts/score_stage30_quality.py -> 91.52 / A / pass`，`python -m pytest -q -> 1249 passed, 1 skipped`。这不是 Phase 54E final acceptance，因为 formal judge rows 仍缺失；但证明当前分支在等待 judge 配置期间保持全量回归通过。

2026-06-25 追加 5：已新增 `docs/phase54_formal_judge_runbook.md`，把 judge preflight、3-case smoke、全量 formal run、gate 判读、失败处理、reranker/GPU 可选流程和安全边界固化成可复用操作手册。下一次补齐 `JUDGE_MODEL_*` 后按 runbook 执行即可。

2026-06-25 追加 6：`scripts/evaluate_phase54_graphrag_e2e.py` 已新增 `--summarize-existing`，可从已有 results CSV 离线重建 summary/gate，不调用 DB、embedding、answer provider 或 judge provider。已用 retrieval-only CSV smoke 验证，summary 可复算且不会误写 formal gate。

2026-06-25 追加 7：已新增 `docs/phase54_completion_audit.md`，逐项列出 Phase 54 验收要求、当前证据、状态和下一步。当前审计结论：54A/54B/54C 完成，54D formal judged E2E 缺 judge provider 配置，54E final closeout pending formal judge rows。

2026-06-25 追加 8：formal gate 已加固，除 `status=completed` 外还要求每行 6 个 judge score 字段完整；summary 新增 `formal_judge_scored_rows`。缺分数的 completed row 会保持 `formal_judge_gate_decision=pending`，避免坏 CSV 被误判为 pass/review_required。

2026-06-25 追加 9（历史记录）：已新增 `scripts/audit_phase54_completion.py`，生成机器可读 `data/evaluation/phase54_completion_audit.csv`。当时审计结果：`complete=13`、`partial=0`、`missing=3`；formal judge 完成后已更新为 `complete=16`、`partial=0`、`missing=0`。

2026-06-25 追加 10：已完成全量 `--execute-answers` 真实生成链路验证，47/47 cases 均为 `answer_only`，`error_rows=0`，5 条 negative off-topic 的 `graph_candidate_chunk_count=0` 且 `graph_used_match_count=0`。该结果证明真实检索+生成链路可跑通，但仍不是 formal judge acceptance。

2026-06-25 追加 11：`scripts/audit_phase54_completion.py` 已纳入 54E pre-judge 回归证据：Stage 30、full pytest、`git diff --check` 和 targeted sensitive scan。新增 `data/evaluation/phase54_prejudge_validation.csv` 记录脱敏状态。当前 pre-judge baseline：Stage 30 `91.52 / A / pass`，full pytest `1253 passed, 1 skipped`，diff check 无 whitespace error，Phase 54 answer-only CSV 敏感扫描无命中。

2026-06-25 追加 12：`scripts/evaluate_phase54_graphrag_e2e.py --preflight` 已增强为逐项 judge 配置检查。当前本地缺失字段为 `JUDGE_MODEL_PROVIDER`、`JUDGE_MODEL_NAME`、`JUDGE_MODEL_API_KEY`、`JUDGE_MODEL_BASE_URL`；preflight 只输出 true/false 和字段名，不输出任何密钥值。

## 当前边界

- 工作分支：`codex/phase-54-graphrag-evaluation`（从 Phase 53 合并后的 main 出发）
- 不切换到 reranker 开发分支，不处理 reranker 相关 stash / worktree。
- 不执行 `git add`、commit、tag、push、PR，停在用户核验前。
- 抽取使用配置的 chat provider（Paratera GLM 系列），脚本默认 dry-run。
- 评测 judge 使用真实 chat provider，`--execute` 才调用。
- 图数据（`data/knowledge_graph/`）为派生产物，gitignore。
- 不得写入 API key、隐藏推理、完整 chunk、完整模型原文或敏感内容。

## 目标产物

- 采样质量报告：`data/evaluation/phase54_extraction_sample_quality.csv`：complete
- LLM 语义补充结果：`data/knowledge_graph/extraction_text_chunks.json` / `data/knowledge_graph/extraction_table_chunks.json`（gitignore）：complete（4331/4331 目标候选 attempted）
- regex 抽取结果：`data/knowledge_graph/extraction_regex.json`（gitignore）：complete
- 合并抽取结果：`data/knowledge_graph/extraction_merged.json`（gitignore）：complete
- 知识图谱：`data/knowledge_graph/domain_graph.json`（gitignore）：complete（54C gate passed）
- 图统计报告：`data/evaluation/phase54_graph_stats.csv`：complete
- 评测用例：`data/evaluation/phase54_graphrag_eval_cases.csv`：complete（47 cases）
- 评测结果：`data/evaluation/phase54_graphrag_eval_results.csv`：dry-run complete；formal judge pending
- 评测摘要：`data/evaluation/phase54_graphrag_eval_summary.csv`：dry-run complete；formal judge pending
- ablation 对照：`data/evaluation/phase54_graphrag_eval_ablation.csv`：dry-run complete；formal judge pending
- 评测脚本：`scripts/evaluate_phase54_graphrag_e2e.py`：complete（dry-run / retrieval-only / answer-only / judge modes）
- 阶段报告：`docs/phase_reviews/phase-54.md`：draft in progress
- Formal judge runbook：`docs/phase54_formal_judge_runbook.md`：complete
- Completion audit：`docs/phase54_completion_audit.md`：pre-judge complete；final update pending formal judge
- Completion audit CSV：`data/evaluation/phase54_completion_audit.csv`：pre-judge complete；final update pending formal judge
- Existing-result summary rebuild：`scripts/evaluate_phase54_graphrag_e2e.py --summarize-existing`：complete

## 阶段拆分

### Phase 54A：采样抽取质量验证

状态：complete

目标：
- 从 33182 条 text chunk 中随机采样 200 条（确保 heading_path 多样性覆盖不同文档/章节）。
- 对采样 chunk 运行 LLM 抽取（`--execute --limit 200`）。抽取 LLM 使用 planner chat provider（`deepseek-v4-flash`），不用主 chat model——flash 模型适合高吞吐抽取任务。
- 对相同 chunk 运行 deterministic regex 抽取。
- 对比 LLM vs regex：entity count、relation count、type 分布。
- 人工抽检 20 条 LLM 抽取结果，评估 entity precision 和 relation precision。
- 如果 entity precision < 0.7 或 relation precision < 0.6，迭代 prompt / 后处理。
- 输出采样质量报告 CSV。

验收：
- 采样 200 条 LLM 抽取完成，JSON 输出无敏感数据。
- 人工抽检 20 条，entity precision >= 0.7。
- 质量报告 CSV 包含 entity/relation count、type 分布、precision 估计。

完成结果：
- 新增 `scripts/evaluate_phase54_extraction_sample.py`，支持多文档/heading 多样化采样、planner provider LLM 抽取、deterministic regex 对照、逐条/逐批落盘、`--resume`、`--batch-size`、`--timeout-seconds`。
- `scripts/extract_phase53_graphrag_triples.py` 已支持 `--provider-role planner`、`--sample-diverse`、planner provider timeout override，并强制 `--execute` 时使用 `PLANNER_CHAT_MODEL_*`。
- LLM prompt 已收紧为最多 8 个高置信实体与 8 条高置信关系，降低响应长度和超时概率。
- 正式 200 条真实 planner LLM 采样已完成，输出 `data/evaluation/phase54_extraction_sample_llm.json`、`phase54_extraction_sample_regex.json`、`phase54_extraction_sample_quality.csv`、`phase54_extraction_manual_review.csv`。
- 质量摘要：`llm_rows=200`、`llm_error_rows=20`、`llm_entity_total=1008`、`llm_relation_total=552`；regex 对照 `regex_entity_total=793`、`regex_relation_total=645`。
- 20 条源文本锚定复核：`entity_precision=0.7914`、`relation_precision=0.6500`，达到 Phase 54A gate。
- 敏感字段扫描通过：输出不含 API key、Bearer token、provider raw response、reasoning_content、hidden thought、完整 chunk content。

### Phase 54B：全量 regex 骨架 + 高价值 LLM 语义补充

状态：complete

目标：
- 对全部 33182 条 text chunk 跑 regex 高精度抽取（标准号、标准号间引用、数值+单位），建立全量图骨架。
- 对高价值 text chunk 做 LLM 语义补充（使用 `deepseek-v4-flash` planner provider）。高价值 text 的正式目标定义为 `score >= 180`，共 2891 条；该阈值位于 top high-value band，落在原计划 2000-5000 条范围内。
- 对全部 1440 条 table chunk 做 LLM/regex 抽取，因为 table chunk 总量小且对材料→参数→数值关系密度更高。
- 脚本支持 `--resume`（从已有输出继续，不重复已完成的 chunk_id）、`--batch-size`（控制并发/速率）和可配置候选选择策略，避免一次性盲跑 33182 条 LLM。
- 合并策略：regex entity/standard_references/数值关系优先保留（高精度），LLM 补充 `material_has_property`、`applies_to`、`standard_defines` 等语义关系。
- 如果 Phase 54C/54D 的图质量或端到端评测不达标，再按失败问题定向补抽 LLM，而不是预先全量 LLM。
- 输出合并后的 extraction JSON。

验收：
- regex text chunk 覆盖率 = 100%，且可被 `build_knowledge_graph()` 正常消费。
- LLM 语义补充覆盖目标候选：2891 条 `score>=180` high-value text + 1440 条 table chunk，总计 4331 条候选。当前基线统计来自 `data/evaluation/phase54_llm_coverage_plan.json`。
- 目标候选行必须全部 attempted；成功率目标 `ok >= 70%`，错误行只允许 timeout/可解释 JSON 解析错误，后续按 54C/54D 缺口重试。
- 合并 JSON 文件可被 `build_knowledge_graph()` 正常消费。
- Phase 54C/54D 如果暴露图稀疏或评测提升不足，必须记录缺口并追加定向 LLM 补抽。
- 抽取输出不包含完整 chunk content、raw_response、reasoning_content。

完成结果：
- LLM 覆盖规划：`data/evaluation/phase54_llm_coverage_plan.json`，`completed_target=4331/4331`。
- text LLM：`rows=2909`、`ok_rate=0.7951`。
- table LLM：`rows=1440`、`ok_rate=0.9167`。
- merged extraction：`data/knowledge_graph/extraction_merged.json`，`rows=34502`、`ok=27655`。
- focused tests：`18 passed`。

### Phase 54C：知识图谱构建 + 质量检查

状态：complete

目标：
- 从合并 extraction JSON 构建 NetworkX 知识图谱。
- 实体归一化增强：
  - 标准号格式统一（"GB/T 14902" / "GB/T14902" / "GBT14902" → 同一节点）。
  - 材料中英文别名合并（如 "rock-filled concrete" / "堆石混凝土" / "RFC"）。
  - 利用 Phase 53C 的 `TERM_PATTERNS` 做已知别名合并。
- 图统计输出：节点数、边数、连通分量、度分布、entity type 分布、relation type 分布。
- 质量门槛：
  - 孤立节点（degree=0）占比 < 30%。
  - 最大连通分量覆盖 > 40% 节点。
  - 如果不达标，分析原因并调整归一化策略。
- 持久化 `data/knowledge_graph/domain_graph.json`。
- `.gitignore` 包含 `data/knowledge_graph/`。

验收：
- 图构建完成，`graph_stats()` 输出合理。
- 孤立节点 < 30%，最大连通分量 > 40%。
- `save_graph()` → `load_graph()` round-trip 一致。
- 图统计报告 CSV 输出。

### Phase 54D：真实 API 端到端评测

状态：complete（case set、runner、retrieval-only、full answer-only 和 full formal judge 均已完成）

GPU 服务器管理：
- 开工前通过 Chrome 打开 `https://ai.paratera.com/#/cloud/compute`，启动 GPU 实例（BGE-LoRA reranker 需要 SSH tunnel 到 GPU host）。
- 评测完成后立即回到平台页面，将实例切为"节省模式"。严禁 CLI shutdown（不会停止计费）。

目标：
- 编写 40-60 条评测用例（手工编写，基于真实语料内容），分类：
  - standard_reference_chain（10-15 条）：标准引用链、标准间关系。
  - cross_document_property（10-15 条）：同一材料/参数在不同文档中的定义对比。
  - parameter_tracing（5-10 条）：参数在哪些标准中被定义/引用。
  - multi_constraint（5-10 条）：同时满足多个标准约束的查询。
  - ordinary_baseline（5-10 条）：普通单文档问题，baseline 对照。
  - negative_offtopic（3-5 条）：off-topic 问题，图检索不应误触发。
- 评测脚本 `scripts/evaluate_phase54_graphrag_e2e.py`：
  - 加载真实图数据（`data/knowledge_graph/domain_graph.json`）。
  - 对每条 case，分别跑 graph-enhanced 检索和 baseline（纯 hybrid+rerank）检索。
  - Judge 模型：GLM-5.2（provider: `openai-compatible`, model: `GLM-5.2`, base_url: `https://llmapi.paratera.com`），API key 从 `.env` 的 `JUDGE_MODEL_API_KEY` 读取。选 GLM-5.2 是因为 judge 需要比 flash 更强的理解力。
  - 评分维度：accuracy、completeness、citation_quality，每项 1-5 分。
  - 输出 results / summary / ablation CSV。
  - 默认 dry-run，`--execute` 才调用真实 API。
- Gate 标准：
  - graph-enhanced 在跨文档类问题（reference_chain + cross_document + parameter_tracing + multi_constraint）上的 avg_completeness 相对 baseline 提升 > 0.3 分。
  - ordinary_baseline 类问题的 avg_accuracy 不下降（delta >= -0.1）。
  - negative_offtopic 不产生 false positive graph 路由。

验收：
- 评测用例 40 条以上。
- graph-enhanced 在跨文档类问题上有可量化提升。
- 普通问题质量不退化。
- 输出 CSV 不包含敏感数据。

当前结果：
- 47 条评测用例已完成，覆盖 graph intent、ordinary baseline 和 negative off-topic。
- dry-run 已完成，runner 默认不调用真实 API。
- `--execute-retrieval` 全量 47 条已完成，reranker disabled：`retrieval_only_rows=47`、`error_rows=0`、`negative_graph_false_positive_count=0`。
- `--execute-answers` 全量 47 条已完成：`answer_only_rows=47`、`error_rows=0`，只写 answer length，不写 answer text；5 条 negative off-topic 仍无 graph false positive。
- `--preflight --require-judge` 已完成无 API 前置检查，当前 `judge_provider_configured=false`，输出 `data/evaluation/phase54_graphrag_eval_preflight.csv`。
- formal judge summary 会自动输出 `graph_intent_accuracy_delta`、`graph_intent_completeness_delta`、`graph_intent_citation_quality_delta`、`ordinary_accuracy_delta`、`formal_judge_gate_decision` 和 `formal_judge_gate_reason`。
- 正式 `--execute` judge 已完成：`completed_rows=47`、`error_rows=0`、`formal_judge_gate_decision=pass`。

### Phase 54E：文档收尾与阶段报告

状态：in_progress（draft docs/runbook now; final closeout after formal judge）

目标：
- 更新 README、AGENT.MD、docs/progress.md、docs/architecture.md、docs/data_sources.md。
- 写 `docs/phase_reviews/phase-54.md`，包含：
  - 抽取质量统计（entity count / type 分布 / precision）。
  - 图统计（节点数 / 边数 / 连通分量）。
  - 端到端评测结果（graph-enhanced vs baseline 关键指标对比）。
  - 面试话术建议（如何在面试中讲 GraphRAG 故事）。
- 全量 pytest、Stage 30、`git diff --check`、敏感数据扫描。
- 最终停在人工核验前。

验收：
- 全量 pytest 通过。
- Stage 30 仍为 A / pass。
- `git diff --check` 无 whitespace error。
- CSV 敏感字段扫描无命中。
- 所有文档同步完成。

当前 pre-judge 验证：
- Stage 30：`overall=91.52`、`grade=A`、`release_decision=pass`。
- Full pytest：`1249 passed, 1 skipped`。
- Final acceptance 仍需 formal `--execute` judge 结果和最后一轮回归/安全扫描。

## 关键技术决策

### regex 骨架 + LLM 语义补充混合策略

纯 LLM 抽取的 recall 高但 precision 不稳定，并且 33182 条 text chunk 全量 LLM 抽取在当前 API 吞吐下耗时过长。纯 regex 的 precision 高但语义 recall 低。Phase 54 采用混合策略：
- regex 对全部 text chunk 建立高精度骨架（标准号、标准间引用、数值+单位）。
- LLM 只对高价值 text/table chunk 做语义补充（material_has_property、applies_to、standard_defines 等 regex 难以捕获的关系）。
- 合并时 regex 结果优先，LLM 去重后补充。
- 后续以 Phase 54C 图质量和 Phase 54D 端到端评测结果驱动定向补抽，而不是预先盲跑 33182 条 LLM。

### 评测设计

端到端评测不是单独评图检索组件，而是评整个 RAG 链路（检索 → 生成 → 引用）在有/无图数据下的差异。这样能证明 GraphRAG 对最终回答质量的实际影响，而非仅仅证明图检索能多召回几个 chunk。

### 图数据管理

`data/knowledge_graph/` 整个目录 gitignore，因为：
- extraction JSON 可能很大（数万条 chunk 的三元组）。
- 图数据是从代码 + 语料派生的，可重新构建。
- 避免意外把 chunk 内容或 LLM 原始输出提交到 Git。

## 交班注意

本计划从 Phase 53 合并后的 main 出发。确认 Phase 53 已合并（含 graphrag 代码骨架、Adaptive RAG 标签、LangGraph graph_search 节点）后再创建分支。
## 2026-06-25 Phase 54D dry-run update

Phase 54D evaluation scaffold is in place:
- `data/evaluation/phase54_graphrag_eval_cases.csv` contains 47 sanitized cases, within the planned 40-60 range.
- `scripts/evaluate_phase54_graphrag_e2e.py` supports dry-run by default, `--execute-retrieval` for local retrieval comparison, and `--execute` for retrieval + answer generation + judge.
- Dry-run outputs are `phase54_graphrag_eval_results.csv`, `phase54_graphrag_eval_summary.csv`, and `phase54_graphrag_eval_ablation.csv`.
- `--execute` fails fast unless both answer and judge providers are configured, so dry-run/retrieval-only rows cannot be mistaken for formal real API conclusions.

Formal Phase 54D result is still pending. Next required action is to run the real chain with the intended provider configuration and, if the default reranker path is required, ensure the private BGE-LoRA service/tunnel is available.

Runner hardening after the first retrieval-only attempt:
- `--limit` supports small smoke batches.
- `--resume` skips rows whose status is already `completed` or `retrieval_only`; dry-run rows are intentionally not treated as completed work.
- During retrieval/execute mode, result and summary CSVs are refreshed after every case so long runs leave resumable progress.
- A deterministic retrieval smoke with `--limit 2 --resume` passed and produced `retrieval_only_rows=2`, `error_rows=0`.

Graph retrieval safety repair before formal 54D judge:
- Short ASCII graph nodes no longer match by substring against ordinary English words.
- Query token matching filters common English stopwords so values such as `about 6 C` do not anchor off-topic graph traversal.
- Graph matches used for DB/fusion are capped to 200 while raw candidate counts remain visible.
- Real embedding retrieval-only negative smoke passed: 5/5 off-topic cases produced zero graph candidates.

Full retrieval-only gate before real judge:
- Real embedding retrieval-only over all 47 cases passed with reranker disabled.
- `retrieval_only_rows=47`, `error_rows=0`, `negative_graph_false_positive_count=0`.
- Graph traversal remains broad for in-domain graph questions, but the fusion cap bounds actual graph matches to at most 200.
- Baseline and graph top chunk matched in `43/47` rows; if formal judge lift is weak, next tuning target should be graph fusion weighting/case design rather than more LLM extraction volume.

Real generation smoke before judge:
- `--execute-answers` runs retrieval and real answer generation, writes only answer lengths, and intentionally does not write answer text or judge scores.
- Full answer-only run passed for all 47 cases: `answer_only_rows=47`, `error_rows=0`.
- Formal Phase 54D acceptance still requires `--execute` rows with judge scores; answer-only rows are not acceptance evidence.

## 2026-06-25 Phase 54C update

Current goal is narrowed to finishing Phase 54C graph-quality repair first, then moving to Phase 54D real API end-to-end evaluation. Phase 54B LLM coverage remains the formal baseline: full regex skeleton plus high-value LLM semantic supplement, with target coverage `4331/4331`.

Phase 54C graph-quality strategy:
- Keep the full regex + LLM merged extraction as the input.
- Preserve isolated `Standard`, `Material`, `Parameter`, `Method`, and `Organization` nodes because they can still act as graph query anchors through `chunk_ids`.
- Prune only degree-zero `Value` nodes before saving the formal Phase 54 graph. These nodes are mostly standalone numeric/unit fragments and add little relationship value while inflating isolated-node ratio.

Formal Phase 54C graph after pruning:
```text
domain_graph.json
node_count=11396
edge_count=104522
isolated_node_count=1604
isolated_node_ratio=0.1408
largest_connected_component_node_count=9119
largest_connected_component_ratio=0.8002
pruned_isolated_value_nodes=4632
```

Phase 54C gate status: passed. Next step is Phase 54D real API GraphRAG vs baseline evaluation.

## 2026-06-25 Goal reset: formal judge readiness and final closeout

Current working goal is reset from the earlier "finish 54C, then 54D/54E" wording to the narrower remaining scope:

- Keep Phase 54A/54B/54C as completed baselines: full regex skeleton, high-value text/table LLM supplement, and the pruned formal graph.
- Do not expand LLM extraction volume unless the formal judged E2E result exposes a concrete coverage gap.
- Continue Phase 54D only through the formal `--execute` run after `JUDGE_MODEL_*` is configured locally.
- Treat dry-run, retrieval-only, and answer-only rows as readiness evidence only, not acceptance evidence.
- Use `scripts/evaluate_phase54_graphrag_e2e.py --preflight --require-judge` before the expensive formal run.
- After formal judge rows exist, rerun `scripts/audit_phase54_completion.py`, update the Phase 54 docs, run final regression/safety checks, and stop before `git add`/commit/tag/push/PR.

Latest no-provider-call checks:

```text
python scripts/evaluate_phase54_graphrag_e2e.py --preflight --summary-output data/evaluation/phase54_graphrag_eval_preflight.csv
-> cases_total=pass value=47
-> graph_file_exists=pass
-> chat_provider_configured=pass
-> embedding_provider_configured=pass
-> judge_provider_configured=fail
-> formal_judge_ready=fail

python scripts/audit_phase54_completion.py --output data/evaluation/phase54_completion_audit.csv
-> complete=11 partial=0 missing=3

git diff --check
-> no whitespace errors; CRLF warnings only
```

## 2026-06-25 Phase 54C reranker-enabled comparison closeout

Current remaining Phase 54C comparison objective is now implemented and evaluated:

- Use regex full skeleton + high-value text/table LLM supplement as the graph baseline.
- Use the formal Phase 54 graph at `data/knowledge_graph/domain_graph.json`.
- Run the same 47-case E2E evaluation with GPU-hosted private BGE-LoRA enabled.
- Compare against the reranker-disabled formal GLM-5.2 judge baseline.
- Document results and stop before any Git submission action.

Accepted C pipeline:

```text
hybrid / keyword / vector recall
-> graph relation expansion and relation evidence hints
-> fused candidate pool
-> final GPU BGE-LoRA rerank
-> GLM-5.2 answer generation and judge
```

Formal C artifacts:

```text
data/evaluation/phase54_graphrag_eval_results_reranker_bge_graphaware.csv
data/evaluation/phase54_graphrag_eval_summary_reranker_bge_graphaware.csv
data/evaluation/phase54_graphrag_eval_ablation_reranker_bge_graphaware.csv
data/evaluation/phase54_graphrag_eval_comparison_reranker_bge_graphaware.csv
```

Formal C result:

```text
completed_rows=47
error_rows=0
formal_judge_scored_rows=47
formal_judge_gate_decision=pass
graph_intent_accuracy_delta=0.4412
graph_intent_completeness_delta=0.5000
graph_intent_citation_quality_delta=0.2941
ordinary_accuracy_delta=0.2500
negative_graph_false_positive_count=0
```

Remaining operational checklist:

- Run final no-secret/sanitized artifact scan.
- Stop local SSH tunnel.
- Shut down the Paratera GPU instance through the Web UI, not through CLI poweroff/shutdown.
- Keep repository unsubmitted until user human verification.

## Phase 54D Closeout Plan Update

- [x] Ingest user-provided local standards batch with text/table/image safeguards.
- [x] Run full LLM semantic supplementation for new standard text/table chunks.
- [x] Rebuild the domain graph from the standards-supplemented extraction output.
- [x] Rerun the same 47-case Phase 54 evaluation set with GPU-hosted BGE final reranking.
- [x] Record D metrics: graph-intent accuracy `+0.5294`, completeness `+0.4412`, citation quality `+0.5882`, ordinary accuracy `-0.2500`, negative graph false positives `0`.
- [x] Mark the D formal gate as `review_required` because ordinary in-domain routing regressed.
- [x] Shut down the GPU server after the BGE run.
- [x] Final regression test: Stage 30 `91.52 / A / pass`, full pytest `1267 passed, 1 skipped`, completion audit `complete=16 partial=0 missing=0`.
- [x] Final safety scan: staged diff has no real secret/password/private-key pattern; staged Phase 54 evaluation JSON/CSV has no full chunk text or provider raw response fields.
- [ ] Commit, tag, push, and GitHub merge after user authorization.
