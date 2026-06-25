# 阶段 54 Findings：GraphRAG 真实数据填充与端到端评测

## 已确认事实

- Phase 53 完成了 GraphRAG 代码骨架：schema（6 entity types, 5 relation types）、extractor（deterministic + LLM dual path）、graph_store（NetworkX MultiDiGraph + JSON persistence）、graph_search（entity matching + 1-2 hop traversal + hybrid fusion + fail-open）、LangGraph `search_graph_knowledge` 节点、Adaptive RAG `graph_enhanced_search` 策略标签。
- Phase 53 的 30 条评测是 dry-run（策略标签验证），未使用真实图数据或真实 API judge。
- 项目语料：documents=1146, chunks=50250（text=33182, table=1440, image_description=15628）。
- 当前知识图谱为空——Phase 53 只有代码，没有从 chunk 中实际抽取数据。`search_graph_knowledge` 在生产中会 fail-open 退回 hybrid search。
- chat provider（Paratera GLM 系列）支持 JSON 输出；Phase 52 的 `LLMMemoryIntentClassifier` 已验证 few-shot JSON 模式可行。
- embedding provider：GLM-Embedding-3（dim=2048），Phase 52 的 `PriorEvidenceRelevanceGate` 已验证 cosine similarity 在此 embedding 空间下有效。
- reranker（BGE-LoRA on GPU host）需要 SSH tunnel，Phase 54D 评测时需要开 GPU 服务器。

## 技术决策

### 抽取 LLM 选型：deepseek-v4-flash

GraphRAG 实体关系抽取使用 planner chat provider（`deepseek-v4-flash`，即 `PLANNER_CHAT_MODEL_*` 配置），不用主 chat model。原因：
- 33K chunk 全量抽取是高吞吐任务，flash 模型成本和延迟远低于大模型。
- `extractor.py` 的 `chat_model_provider` 参数应注入 planner provider 而非 main provider。
- Phase 52 的 `LLMMemoryIntentClassifier` 已验证 deepseek-v4-flash 的 JSON 输出能力足够。

### 抽取规模控制

33182 条 text chunk 全量 LLM 抽取估算（使用 deepseek-v4-flash）：
- 每条 chunk 平均 ~1000 字符，LLM prompt 含 schema + chunk = ~2000 tokens input + ~500 tokens output。
- 33182 * 2500 tokens ≈ 83M tokens。token 成本可控，但当前实测吞吐受 API 排队、timeout 和并发限制影响，盲跑全量 LLM 预计耗时 80 小时以上。
- Phase 54 不再把 33182 条 text chunk 全量 LLM 作为首轮 gate。正式路线是：regex 全量建骨架，LLM 只跑高价值 text/table chunk 做语义补充。
- LLM 补充仍需要 batch + resume 支持，防止中断丢失进度。
- rate limiting：Paratera 的 QPS 限制需要确认，脚本应支持 `--batch-size`、请求间隔和可恢复分批运行。

### regex 全量骨架的价值

RFC/建筑规范领域的标准号引用关系可以用 regex 高精度抽取：
- `GB/T 14902` 引用 `GB 50010`：在同一 chunk 中出现两个标准号 → `standard_references` 关系。
- 数值+单位（`320 kg/m³`、`0.45`、`28 MPa`）：regex 精确匹配 → `Value` 实体。
- 这些关系的 precision 接近 1.0，是图骨架的可靠基础。
- LLM 抽取的高价值在于 regex 难以捕获的语义关系：material_has_property、applies_to。

### 实体归一化策略

Phase 53 的 `normalize_entity_name()` 只做了 trim + casefold + 空白归一化。全量数据会暴露更多归一化需求：
- 标准号格式：`GB/T 14902`、`GB/T14902`、`GBT 14902`、`GBT14902` → 统一为 `gb/t 14902`。
- 材料别名：`rock-filled concrete` = `RFC` = `堆石混凝土`。
- Phase 53C 的 `TERM_PATTERNS` 已覆盖部分已知别名，可以复用。
- 对于未知别名，需要 embedding similarity 做模糊匹配（阈值需要调试）。

### 端到端评测 vs 组件评测

Phase 54D 做的是端到端评测（检索 → 生成 → 引用），不是单独评图检索组件。原因：
- 面试时能展示的是"GraphRAG 让回答更好了"，不是"GraphRAG 多召回了几个 chunk"。
- 端到端评测能暴露图检索引入噪声的风险（多召回的 chunk 如果不相关，会降低生成质量）。
- judge 同时评 accuracy、completeness、citation_quality 三个维度，比单一 recall 指标更全面。

## 风险与缓解

1. **LLM 全量抽取耗时高** — 33K chunk * ~2500 tokens ≈ 83M tokens，token 成本可控但实测 API 吞吐过慢。缓解：regex 全量建图骨架，LLM 只对高价值 text/table chunk 做语义补充；后续由图质量和端到端评测缺口驱动定向补抽。
2. **抽取质量不稳定** — LLM 可能产生幻觉实体或错误关系。缓解：白名单过滤（Phase 53 schema 已有）、entity_names 交叉校验（关系的 subject/object 必须在已抽取 entities 中）、人工抽检。
3. **图过于稀疏** — 如果大量 chunk 没有可抽取的实体关系，图会很稀疏。缓解：table chunk 是高密度信息源（材料→参数→数值），text chunk 质量不够时追加 table chunk。
4. **GPU 服务器不可用** — reranker 需要 SSH tunnel 到 GPU host。Phase 54D 评测时需要开服务器。缓解：评测脚本支持 fail-open reranker（无 reranker 时用 hybrid RRF 排序），但正式评测应使用完整链路。
5. **图数据过大** — NetworkX 图 + JSON 可能超过 100MB。缓解：监控文件大小，如果过大考虑 pickle 或分片。

## Phase 54A 发现

- Phase 53 抽取脚本原本 `--execute` 使用主 `CHAT_MODEL_*`；Phase 54A 已补充 planner provider 路径，真实 GraphRAG 抽取应使用 `PLANNER_CHAT_MODEL_*`，避免误用主回答模型。
- 原始 LLM prompt 在 `PLANNER_CHAT_MODEL_TIMEOUT_SECONDS=10` 时 5/5 timeout。将脚本 timeout override 提升到 60 秒，并把 prompt 限制为最多 8 个高置信实体与 8 条关系后，真实 smoke 2/2 通过、20/20 通过。
- 采样最初按 heading bucket 排序会集中在同一文档分页；已改为优先跨 document 随机抽样，再用 heading bucket 补足，正式 smoke 覆盖论文、网页、标准和不同章节。
- 并发 4 可完成真实 20 条样本；并发 8 在本地尝试时长时间无完成项，疑似服务端排队或限流。54B 默认应保守使用 `--batch-size 4` 或更低，并依赖 `--resume`。
- 正式 200 条真实采样完成：`llm_rows=200`、`llm_error_rows=20`，错误均为 timeout。通过 `timeout_seconds=45`、`max_attempts=1`、`batch_size=4`、逐行原子落盘和 `--resume` 收敛。
- 200 条质量摘要：`llm_entity_total=1008`、`llm_relation_total=552`；regex 对照为 `regex_entity_total=793`、`regex_relation_total=645`。Overlap 低，说明 regex 与 LLM 抽取覆盖面不同，后续合并策略仍有价值。
- 20 条源文本锚定复核：`entity_precision=0.7914`、`relation_precision=0.6500`。实体达标有余量，关系刚过 0.6，Phase 54B 合并时应让 regex 高精度关系优先，并过滤 LLM 中 subject/object 无源文本锚点的关系。
- Windows 长跑写 JSON 偶发 `OSError: [Errno 22] Invalid argument`，已用临时文件 + `replace()` + 短重试修复。全量抽取必须继续使用原子写入。

## Phase 54B 运行记录

- 已新增 `scripts/extract_phase54_graphrag_full.py`，支持 `--mode llm|regex|merge|all`、`--resume`、`--batch-size`、`--flush-every`、planner provider LLM 抽取、regex 全量抽取与 regex-priority merge。
- 全量 regex text chunk 抽取已完成：`data/knowledge_graph/extraction_regex.json`，`rows=33182`、`errors=0`、`entities=134276`、`relations=91293`。输出为 `metadata` + `rows` payload，不保存完整 chunk content、raw_response 或 reasoning。
- 使用 regex 输出构图 smoke 通过：`data/knowledge_graph/domain_graph_regex.json`，`node_count=8181`、`edge_count=91293`、`connected_components=4127`。说明全量 regex extraction JSON 可被 Phase 53 图构建器消费。
- 全量 LLM text chunk 抽取已做真实探针：`data/knowledge_graph/extraction_text_chunks.json` 当前约 20 行，`ok=14`、`error=6`，错误均为 `Chat model request timed out`。按 `--batch-size 4 --timeout-seconds 45` 的实测吞吐估算，33182 条全量 LLM 可能需要 80-100 小时，且 token 量仍约 83M。
- 用户已确认正式路线调整为：regex 全量铺骨架，LLM 只跑高价值 chunk 做语义补充。Phase 54B 后续应实现高价值 chunk 选择、table chunk 优先补充、merge 输出和补抽策略记录，不再使用旧的 33182 text chunk 全量 LLM gate 作为首轮验收。
- 已实现 planner API key pool：`PLANNER_CHAT_MODEL_API_KEYS` 可与 `PLANNER_CHAT_MODEL_API_KEY` 合并去重，抽取线程按请求轮询 provider。真实 100 条 high-value text 对比显示三路 key + `batch_size=9` 比单 key 明显提速，错误率没有明显恶化；输出不保存 key。
- high-value text LLM 补充已扩展到 `rows=652`，其中 `ok=494`、`error=158`，错误均为 timeout；累计 `entities=3353`、`relations=2147`，主要补充 `material_has_property=1163` 与 `applies_to=561` 等语义边。
- table chunk LLM 补充已完成首批 `rows=200`，其中 `ok=176`、`error=24`，错误率 12%；累计 `entities=1081`、`relations=685`，表格对参数/数值关系补充效果好。
- 已生成 `data/knowledge_graph/extraction_merged.json`：`rows=33358`、`ok=26571`，由全量 regex + high-value text LLM + table LLM 合并得到。构图 smoke 通过：`node_count=10082`、`edge_count=93856`、`connected_components=4707`。敏感扫描无真实 key/raw_response/reasoning 命中，`sl csk-sm` 为 `sk-` 模式假阳性。

## Phase 54B LLM 覆盖规划

`scripts/plan_phase54_llm_coverage.py` 对全库 chunk 评分后确认 54B 的 LLM 补充目标：
- text chunk 总数 `33182`。高价值 text 目标定义为 `score >= 180`，共 `2891` 条。阈值依据：`score>=200` 只有 `1596` 条，低于原计划 2000-5000；`score>=150` 有 `5809` 条，超出首轮高价值范围且边际密度下降；`score>=180` 的 `2891` 条处在合理中点。
- table chunk 总数 `1440`。table 总量小，且材料/参数/数值关系密度高，因此目标为全部 `1440` 条。
- 54B LLM 补充总目标为 `4331` 条候选。当前目标内已 attempted `834` 条，还需 `3497` 条：text 目标内已完成 `634/2891`，table 已完成 `200/1440`。
- 验收口径：目标候选必须全部 attempted；`ok >= 70%`，错误类型仅允许 timeout 或可解释 JSON 解析错误；后续 54C/54D 若发现图质量或评测缺口，再按缺口重试/补抽。
- 54B 定量覆盖已完成：`completed_target=4331/4331`。text `rows=2909`、`ok=2313`、`ok_rate=0.7951`；table `rows=1440`、`ok=1320`、`ok_rate=0.9167`。错误主要为 timeout，仅 table 有 1 条 JSON 解析错误。
- 54B 完成后 merged extraction：`rows=34502`、`ok=27655`。正式图候选已构建：`node_count=16028`、`edge_count=104522`、`largest_connected_component_ratio=0.5689`、`isolated_node_ratio=0.3891`。最大连通分量达标，但孤立节点比例未达 `<30%`，54C 需要继续优化孤立 Value/噪声节点处理。

## 开放问题

- Paratera chat API 的 QPS 限制是多少？决定 batch-size 设置。
- ~~高价值 LLM 补充首轮规模使用 2000、3000 还是 5000 条 text chunk？~~ 已确定为 `score>=180` 的 2891 条 high-value text + 全量 1440 条 table chunk。
- table chunk 的 LLM 抽取 prompt 是否需要区别于 text chunk？table 的结构化信息密度更高，prompt 可能需要调整。
- ~~评测 judge 使用哪个模型？~~ 已使用 GLM-5.2（`https://llmapi.paratera.com`）完成 formal judge。2026-06-25 初次探针返回 HTTP 403（team not allowed to access model）；用户更新 API key 模型权限后，GLM-5.2 最小 JSON 探针、3 条 smoke 和全量 47 条 formal judge 均通过。

## 2026-06-25 Phase 54B residual timeout and GPU/Judge findings

- 用户确认不再继续追 54B 残余 hard-timeout LLM 行。补跑后 text LLM 为 `rows=2909`、`ok=2351`、`error=558`；table LLM 为 `rows=1440`、`ok=1320`、`error=120`。目标候选 `4331/4331` 已全部 attempted，且 ok rate 仍高于 70% gate。后续只在 formal judged E2E 暴露具体覆盖缺口时定向补抽。
- `scripts/extract_phase54_graphrag_full.py` 已新增 `--retry-failed`，可在 `--resume` 时只重试非 `ok` 行，并按 `chunk_id` 替换旧失败行，不追加重复行。该能力保留给后续缺口驱动补抽使用。
- GPU 服务器 `rfc-reranker-train-3090` 当前在 Paratera Web UI 中显示 `已关机 / 关机不计费`，配置为 RTX3090 1 卡 24GB。只在 reranker-enabled 评测需要 private BGE-LoRA reranker 时开机；开关机必须通过 Chrome 打开的 Paratera Web UI 完成，不能用 CLI 关机控制计费。
- Formal judge 本身不需要 GPU；GPU 只影响 reranker-enabled 检索链路。当前已用 `RERANKING_ENABLED=false` 完成 judge 闭环；如果后续要做 reranker-enabled 对照，再按 Web UI 规则启动 GPU。
- Judge endpoint 兼容性已修复：`OpenAICompatibleChatModelProvider` 对 `https://llmapi.paratera.com` root base URL 使用 `/v1/chat/completions`，与 vision provider 保持一致。最小探针证明 endpoint 可达。
- Phase 54D formal judge 结果：`completed_rows=47`、`error_rows=0`、`formal_judge_scored_rows=47`、`graph_intent_accuracy_delta=0.1471`、`graph_intent_completeness_delta=0.4412`、`graph_intent_citation_quality_delta=0.2647`、`ordinary_accuracy_delta=0.0000`、`negative_graph_false_positive_count=0`、`formal_judge_gate_decision=pass`。

## 2026-06-25 Goal/config findings

- Runtime GraphRAG tool configuration was still pointing at the old Phase 53 evaluation graph path. It has been aligned to `data/knowledge_graph/domain_graph.json`, matching the Phase 54 formal graph and the E2E evaluator default.
- Historical local config check reported `judge=False` while `chat=True`, `planner=True`, and `embedding=True`. After the user updated API key model permissions, transient GLM-5.2 judge config passed preflight and completed the formal run.
- The current review/runbook explicitly distinguishes evidence levels: dry-run is case design, retrieval-only is retrieval plumbing, answer-only is real generation smoke without stored answer text, and only `status=completed` judge rows are formal Phase 54D acceptance evidence.
- `--preflight --require-judge` now proves formal readiness without API calls. Current output confirms all non-judge prerequisites pass and only judge provider configuration fails. This should be the first command after adding `JUDGE_MODEL_*`, before any expensive formal run.
- Formal Phase 54D gate calculation is now machine-readable in the summary. It remains deliberately conservative: `formal_judge_gate_decision` is `pending` until every row is `status=completed`; only full judged runs can produce `pass` or `review_required`. The gate checks graph-intent completeness delta, graph-intent accuracy delta, ordinary accuracy non-regression, and negative off-topic graph false positives.
- Pre-judge full regression is clean: Stage 30 remains `91.52 / A / pass`, and full pytest reports `1253 passed, 1 skipped`. This is useful readiness evidence but not a substitute for formal judge completion.
- The formal judge runbook is now a separate document. This reduces handoff risk: the next run should first execute `--preflight --require-judge`, then a `--limit 3` smoke, then the full `--execute --resume` run, and only then interpret `formal_judge_gate_decision`.
- `--summarize-existing` reduces final-run operational risk: after a long formal judge run, summary/gate rows can be rebuilt from the existing results CSV without calling any provider. Retrieval-only smoke confirmed it recomputes retrieval metrics and does not emit formal gate rows when judge scores are absent.
- A requirement-by-requirement completion audit now exists at `docs/phase54_completion_audit.md`. It deliberately marks formal judged E2E evaluation as missing, even though extraction, graph quality, retrieval-only, answer-only, docs, Stage 30, and full pytest baselines are complete.
- Formal gate now requires complete judge scores, not only `status=completed`. This catches interrupted or malformed result rows where a row might be marked completed but one of the six judge score columns is blank.
- `scripts/audit_phase54_completion.py` converts the Markdown completion audit into a repeatable no-provider-call check. After formal judge completion, current output is `complete=16`, `partial=0`, `missing=0`.
## 2026-06-25 Phase 54D dry-run findings

- The Phase 54D evaluation set now has `47` cases: standard-reference chains, cross-document property questions, parameter tracing, multi-constraint graph questions, ordinary baseline questions, and negative off-topic questions.
- The evaluation runner intentionally separates modes:
  - default dry-run writes sanitized design rows only;
  - `--execute-retrieval` runs local baseline vs graph retrieval;
  - `--execute` runs retrieval, answer generation, and judge.
- `--execute` requires configured answer and judge providers and fails fast otherwise. This prevents a deterministic/offline row from being treated as a real API quality conclusion.
- Result CSVs store chunk ids, title hashes, counts, answer lengths, judge scores, and short judge reasons only. They do not store full chunk content, provider raw responses, hidden reasoning, credentials, or raw model payloads.
- Formal quality conclusion is now available from the real provider run: `completed_rows=47`, `error_rows=0`, `formal_judge_gate_decision=pass`.
- A first full `--execute-retrieval` attempt with current real provider settings produced no output for more than 150 seconds and was stopped. The runner now supports `--limit`, `--resume`, and per-case CSV refresh so formal runs can be done in safe batches.
- Resume semantics are deliberate: only `completed` and `retrieval_only` rows are skipped. Existing dry-run rows do not count as completed retrieval or real API evaluation.
- Retrieval smoke exposed two graph false-positive risks before formal judge runs:
  - Single-letter and two-letter ASCII parameter nodes such as `W`, `CH`, and `NS` could match ordinary English words by substring.
  - Value nodes such as `about 6 C` could match off-topic text through stopwords such as `about`.
- Graph query matching now ignores single-character ASCII candidates, only allows two-character ASCII candidates through exact token matching, and filters common English stopwords from query terms.
- Graph traversal can still yield very large candidate sets for high-degree anchors. `GraphEnhancedSearchService` now caps graph matches used for DB/fusion to `200` while preserving the raw `graph_candidate_chunk_count` for observability.
- Real embedding retrieval-only smoke with reranker disabled now shows all 5 negative off-topic cases have `graph_candidate_chunk_count=0`, `graph_used_match_count=0`, and `error_rows=0`.
- Full retrieval-only Phase 54D run with real embedding and reranker disabled completed all 47 cases: `retrieval_only_rows=47`, `error_rows=0`, `negative_graph_false_positive_count=0`.
- Retrieval-side metrics show graph traversal remains broad for in-domain questions: `graph_candidate_avg=22397.9362`, `graph_candidate_max=25434`, while the production/fusion cap keeps actual graph matches to `graph_used_match_avg=178.7234`, `graph_used_match_max=200`.
- Baseline and graph top chunk were the same in `43/47` retrieval-only rows. This suggests the current graph boost/candidate cap is conservative; the formal judge run may show limited answer-level delta unless graph fusion weighting or case design is adjusted.
- `--execute-answers` was added for real retrieval + real answer generation without judge. The full 47-case answer-only run passed with `answer_only_rows=47`, `error_rows=0`, `baseline_answer_chars` present for 47 rows, and `graph_answer_chars` present for 47 rows. The CSV stores answer lengths only, not answer text.
- The status model is now explicit: `retrieval_only` proves retrieval ran, `answer_only` proves retrieval plus generation ran, and `completed` is reserved for rows with judge scores.

## 2026-06-25 Phase 54C findings

- The first formal merged graph had `node_count=16028`, `edge_count=104522`, `isolated_node_ratio=0.3891`, and `largest_connected_component_ratio=0.5689`. The largest connected component gate passed, but the isolated-node gate failed.
- Isolated node analysis showed `6236` isolated nodes, of which `4632` were `Value` nodes. Samples were mostly standalone numeric/unit fragments such as small MPa/mm/s/m values and malformed unit variants. These are weak graph relationship anchors and can pollute graph-enhanced retrieval.
- Graph search can use an isolated node's `chunk_ids` as a candidate entry point, so pruning every isolated node would lose useful exact entity anchors. The safer strategy is to keep isolated `Standard`, `Material`, `Parameter`, `Method`, and `Organization` nodes, and prune only degree-zero `Value` nodes.
- After pruning isolated `Value` nodes, the formal graph has `node_count=11396`, `edge_count=104522`, `isolated_node_count=1604`, `isolated_node_ratio=0.1408`, and `largest_connected_component_ratio=0.8002`. Phase 54C graph-quality gate passes.
- The implementation is explicit and reversible: `scripts/build_phase53_graphrag_graph.py --prune-isolated-value-nodes` calls `prune_isolated_nodes_by_type(..., node_types={"Value"})`. Default Phase 53 graph building behavior is unchanged.

## 2026-06-25 Goal reset findings

- The active Codex goal tool cannot edit objective text while a goal is active; it can only mark the goal complete or blocked. Because the formal judged E2E evaluation is not complete and there is still a concrete next action after judge configuration, the goal should not be marked complete or blocked.
- The project-level goal has been narrowed in the planning files instead: finish Phase 54D formal judged E2E evaluation, then do Phase 54E final closeout. Phase 54C is no longer an active work item.
- Fresh preflight confirms the remaining blocker is only judge configuration: cases, graph file, chat provider, and embedding provider pass; `judge_provider_configured=false` and `formal_judge_ready=false`.
- Fresh completion audit now reports `complete=16`, `partial=0`, `missing=0`.
- `phase54_prejudge_validation.csv` intentionally stores only compact check statuses for `full_pytest`, `git_diff_check`, and `phase54_sensitive_scan`; it does not store command logs, secrets, provider payloads, answer text, or raw chunk content.
- The machine audit now also checks `phase54_docs_synced` and `git_submission_boundary`. The docs sync check uses conservative markers across README, AGENT.MD, docs/progress, docs/architecture, docs/data_sources, phase review, stage prompt, and completion audit; the submission boundary check is backed by `phase54_prejudge_validation.csv` plus a clean `git diff --cached --name-only`.
- Phase 54 preflight now reports judge readiness at field granularity. Current local missing fields are `JUDGE_MODEL_PROVIDER`, `JUDGE_MODEL_NAME`, `JUDGE_MODEL_API_KEY`, and `JUDGE_MODEL_BASE_URL`. The report is intentionally value-blind: it prints only booleans and missing env var names, never secret values.
- No additional LLM extraction should be launched before formal judge results. The current extraction baseline already covers `4331/4331` high-value targets; more extraction should be driven by a concrete judged gap, not by intuition.

## 2026-06-25 Phase 54C graph-aware BGE comparison findings

- The initial reranker-enabled C attempt was rejected as the formal comparison because the pipeline reranked the hybrid baseline before graph fusion, then graph fusion sorted by stale hybrid scores plus graph boost. This made the BGE-improved baseline stronger while graph-expanded evidence did not receive a fair final evidence-selection step.
- Mainstream RAG/agent patterns point to the opposite ordering: retrieve and expand first, then rerank the fused candidate pool immediately before context assembly and answer synthesis. The implemented graph-aware C path now follows `hybrid/keyword/vector recall -> graph relation expansion -> fused candidates -> final BGE-LoRA rerank -> answer/judge`.
- `GraphEnhancedSearchService` now supports relation-focused graph matching, relation evidence hints in reranker candidate text, post-fusion reranking, and a small graph candidate quota so BGE sees graph-only candidates without letting graph candidates dominate the final pool.
- The formal graph-aware BGE run completed on the same 47 cases with GLM-5.2 answer generation and judge: `completed_rows=47`, `error_rows=0`, `formal_judge_scored_rows=47`, `formal_judge_gate_decision=pass`.
- Graph-aware BGE improved the formal graph-intent deltas over reranker-disabled formal judge: accuracy delta `0.1471 -> 0.4412`, completeness delta `0.4412 -> 0.5000`, citation-quality delta `0.2647 -> 0.2941`.
- Ordinary baseline accuracy delta also improved from `0.0000` to `0.2500`, but ordinary in-domain cases still produced broad graph candidate sets around 25k. The negative off-topic set remained clean: `negative_graph_false_positive_count=0` and `negative_graph_candidate_avg=0.0000`.
- Accepted C artifacts are `phase54_graphrag_eval_results_reranker_bge_graphaware.csv`, `phase54_graphrag_eval_summary_reranker_bge_graphaware.csv`, `phase54_graphrag_eval_ablation_reranker_bge_graphaware.csv`, and `phase54_graphrag_eval_comparison_reranker_bge_graphaware.csv`.

## 2026-06-25 Phase 54D finding

- The expanded standards corpus plus full standards LLM supplementation materially improves graph-intent answers when paired with final BGE reranking. The strongest D gains are citation quality (`+0.5882`) and graph-intent accuracy (`+0.5294`) with zero negative off-topic graph false positives.
- The main remaining risk is ordinary in-domain query routing. D produced `ordinary_accuracy_delta=-0.2500`, which fails the formal gate and keeps the result in `review_required`. The next production-hardening step should make graph expansion more selective for ordinary single-standard or single-document questions.
