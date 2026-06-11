# 项目进度

## 最新状态：2026-06-11（阶段 21 LangGraph Agentic RAG，待人工核验前收尾）

当前阶段：阶段 21，LangGraph Agentic RAG。在 `claude/phase-21-langgraph-agentic-rag` 分支完成核心开发、回归验证和普通文档收尾；当前**尚未执行** `git add`、`git commit`、`git tag`、`git push`，也未创建 PR，等待用户人工核验和明确确认后才允许进入提交、tag 和 GitHub 推送流程。

阶段 21 完成内容：

- `docs/stage21_langgraph_agentic_rag.md` 设计文档。
- `pyproject.toml` 加 `langgraph>=0.2.0` 依赖。
- `app/services/agentic/` LangGraph agentic RAG 模块：状态图 retrieve → grade → rewrite → re-retrieve → generate → citation_check，硬迭代上界 MAX_ITERATIONS=3。
- `/agent/query` 新增 `mode="agentic"` 可选参数，不替换默认链路。
- `scripts/evaluate_stage21_agentic_rag.py` agentic vs baseline 对照评测。
- 首次评测受 SSL 错误影响，决策为 `inconclusive_high_error_rate`。
- 全量测试 **449 passed**。

Git 起点：阶段 20 已完成并合并到 `main`（`phase-20-complete -> 706047d`，合并提交 `8333d71`）。

## 历史状态：2026-06-10（阶段 20 中文检索默认链路落地与评测判定增强，已完成并合并）

阶段 20 已完成并合并到 `main`。`phase-20-complete -> 706047d`，合并提交 `8333d71`。

Git / tag / main 起点：

- 阶段 19 已完成人工核验、提交、创建 `phase-19-complete` tag（指向最终功能提交 `ffb4756`，非 merge）并合并到 `main`（合并提交 `12184d7`）。
- `phase-19-complete` 是 `main` 祖先；阶段 20 从含阶段 19 合并的 `main` 出发；未移动任何已有阶段 tag。

阶段 20 完成内容：

- 使用 Planning with Files 维护 `task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage20_default_chain_and_eval_upgrade.md` 设计文档，固定答案级 coverage ratio、真实 Jina query-only 校验、默认链路切换门槛、`responsibility_gate`、安全边界和完成标准。
- **Phase 2 评测判定升级**：新增 `scripts/evaluate_stage20_eval_upgrade.py`，复用阶段 19 中文难评测集，用 `expected_answer_points` 计算答案级 `coverage_ratio`，避免题录标题/摘要关键词偏置；输出 `stage20_eval_upgrade_results.csv` 与 `stage20_eval_upgrade_summary.csv`。
- **Phase 3 真实 Jina query 端校验**：同一脚本增加 `--real-query`，只生成 query embedding，复用已有 `jina-embeddings-v3` chunk embeddings，不重做 8918 条 chunk embedding；输出 `stage20_eval_upgrade_real_jina_results.csv` 与 `stage20_eval_upgrade_real_jina_summary.csv`。
- **Phase 4 默认链路接入决策**：新增 `scripts/build_stage20_default_chain_decision.py` 与 `data/evaluation/stage20_default_chain_decision.csv`；deterministic 与真实 Jina 均未满足 `Δp@1>=0.10`，因此保持 `keep_existing_hybrid`，不改默认 `HybridSearchService` / Brain hybrid 链路。
- **Phase 5 `responsibility_gate` 责任边界拒答门**：在 Brain 生成前拦截“判定/评定/是否合格/是否符合规范/能否用于工程”等责任判断问题，返回“系统不替代规范审查、工程设计、第三方检测或专家签字”的拒答提示；on-topic 学习题不误拒。
- **Phase 6 quality gate / 报告更新**：新增 `scripts/build_stage20_quality_report.py`、`data/evaluation/stage20_quality_summary.csv`、`docs/stage20_quality_report.md`，并更新 `GET /quality-report` 静态只读报告。
- **Phase 7 回归验证**：聚焦回归与全量测试通过，全量测试 **424 passed**；最终 quality gate 为 **pass/low**。

评测结果：

```text
Stage 20 deterministic coverage_ratio：
  hybrid_baseline              p@1=0.133 coverage=0.323 deep_top1=0.267 refusal_acc=1.000 decision=baseline
  hybrid_fulltext_boost        p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_metadata_demote       p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_topic_anchor_strict   p@1=0.133 coverage=0.273 deep_top1=0.733 refusal_acc=1.000 decision=keep_existing_hybrid

Stage 20 real Jina query-only：
  hybrid_baseline              p@1=0.133 coverage=0.323 deep_top1=0.267 refusal_acc=1.000 decision=baseline
  hybrid_fulltext_boost        p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_metadata_demote       p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_topic_anchor_strict   p@1=0.133 coverage=0.273 deep_top1=0.733 refusal_acc=1.000 decision=keep_existing_hybrid

Default chain decision:
  overall=keep_existing_hybrid
  blocker=delta_precision_at_1=+0.000<0.10

Quality gate:
  pass/low

Tests:
  focused stage20/api regression: 61 passed
  focused documents/sources/decompose/vector regression: 67 passed
  full tests: 424 passed
```

遗留风险：

- 默认链路未切换不是失败，而是数据门槛未通过后的诚实决策：候选重权显著提高 deep_fulltext top-1，但答案级 p@1 没有提升，不能把 `source_type_reweight` 焊进默认 hybrid。
- 真实 Jina query 校验本次为 completed，但真实 API 仍依赖本地 `.env`、网络和 provider 状态，不得成为 CI 或本地全量测试前提。
- `responsibility_gate` 已覆盖阶段 19 遗留的工程责任判断题；后续若出现新的责任类问法，应扩展触发模式并补正反例测试。
- 阶段 20 当前未提交、未打 `phase-20-complete` tag、未推送，等待用户人工核验。

下一阶段任务：

- 用户人工核验阶段 20 设计文档、评测升级脚本、真实 Jina query-only 结果、默认链路决策表、责任门、quality gate、普通文档与 Obsidian 草稿。
- 如确认通过，再执行提交、创建 `phase-20-complete` tag 并推送；tag 应指向阶段 20 最终功能提交，不要移动已有阶段 tag。
- 后续可考虑扩展答案级 judge：在不进入 CI 的前提下增加离线 LLM-judge 复核，或设计新的中文答案覆盖评测集继续观察 `source_type_reweight` 是否能跨过 `Δp@1` 门槛。

面试表达：

```text
阶段 20 我处理的是阶段 19 留下的两个核心问题：旧评测命中偏向题录卡片，以及工程责任边界没有专门拒答门。评测上，我把命中判定从“标题/摘要关键词是否出现”升级为答案级 coverage ratio，用 expected_answer_points 衡量 top-1 证据是否覆盖回答要点，并且用真实 Jina 只做 query 端校验，复用已有 8918 条 chunk embeddings，不重做索引。

默认链路决策上，我没有因为 deep_fulltext_top1 从 0.267 提升到 0.667/0.733 就直接切换，而是坚持 Δp@1、Δdeep_top1 和 refusal 三个门槛同时满足。结果候选配置的 Δp@1 仍是 0，所以保持 keep_existing_hybrid，把 source_type_reweight 留作候选开关。安全边界上，我在 Brain 生成前加 responsibility_gate，拦截“是否合格/是否符合规范/能否用于工程”这类责任判断题，避免系统替代规范审查或专家签字。最后用 quality gate 和 424 个全量测试证明默认 API 没被破坏。
```

## 历史状态：2026-06-10（阶段 19 中文全文文献分析与检索/评测调优，已完成并合并）

阶段 19 已在 `claude/phase-19-chinese-analysis-retrieval-tuning` 分支完成 Phase 0–4 开发、测试、普通文档和 Obsidian 草稿，经人工核验后提交为 `ffb4756`，创建 `phase-19-complete` tag，并通过合并提交 `12184d7` 合并到 `main`。

Git / tag / main 起点：

- 阶段 18 已完成人工核验、提交、创建 `phase-18-complete` tag（指向最终功能提交 `c56fc62`，非 merge）并合并到 `main`（合并提交 `4db90c7`），已 push 到 GitHub。
- `phase-18-complete` 是 `main` 祖先；阶段 19 从含阶段 18 合并的 `main` 出发；未移动任何已有阶段 tag。

阶段 19 完成内容：

- 使用 Planning with Files 维护 `task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage19_chinese_analysis_retrieval_tuning.md` 设计文档（目标、Phase 0 实证、四类难度难评测集、调优口径、决策门槛、安全边界、完成标准、面试表达）。
- **Phase 0 第一轮文献分析探索**：新增 `scripts/explore_chinese_corpus.py`（默认 deterministic，可选 `--real` 走 MIMO+Jina，带重试），产出 `data/evaluation/stage19_exploration_results.csv`（10 题：8 on-topic + 2 拒答）。
- **Phase 1 中文难评测集**：新增独立 `data/evaluation/stage19_chinese_hard_queries.csv`（19 题：5 cross_passage + 5 confusable + 5 parameter_detail + 4 refusal），不覆盖旧英文 `stage18_hard_queries.csv`；新增 `tests/test_stage19_chinese_hard_set.py`（11 passed）。
- **Phase 2 检索排序调优**：新增 `app/services/retrieval/source_type_reweight.py` 纯函数模块（4 套配置：baseline / fulltext_boost / metadata_demote / topic_anchor_strict），新增 `scripts/evaluate_stage19_retrieval_tuning.py` + 两份 CSV 结果，新增 `tests/test_stage19_retrieval_tuning.py`（11 passed）。
- **Phase 3 文献分析快照**：新增 `docs/stage19_literature_review.md`（面向人读，整合 Phase 0/2 数据 + 主题速览 + 面试表达）；未新增 build 脚本（阶段边界裁剪）。
- **Phase 4 回归 + 文档/Obsidian 收尾**：全量测试通过；同步入口文档；补 Obsidian 阶段 19。

评测结果（deterministic）：

```text
Phase 0 探索（10 题，8 on-topic + 2 refusal）：
  refused=1 refusal_matched=9/10
  on_topic_answered=8 deep_top1=0/8 metadata_top1=5/8
  errors=0

Phase 2 中文难评测集 19 题 × 4 配置：
  hybrid_baseline             p@1=0.400 deep_top1=0.000 meta_top1=1.000 refusal_acc=0.750
  hybrid_fulltext_boost       p@1=0.333 deep_top1=0.533 meta_top1=0.467 refusal_acc=0.750
  hybrid_metadata_demote      p@1=0.333 deep_top1=0.533 meta_top1=0.467 refusal_acc=0.750
  hybrid_topic_anchor_strict  p@1=0.200 deep_top1=0.733 meta_top1=0.267 refusal_acc=0.750
  overall=keep_existing_hybrid（Δp@1 门槛未达成，但 Δdeep_top1 全部≥0.20）

full tests: 408 passed
```

遗留风险：

- `cn_explore_refusal_mix_design` 等命中域词的工程责任判断题未被默认拒答门挡住，属阶段 19 遗留；阶段 20 已用 `responsibility_gate` 闭环。
- `expected_source_hit` 用关键词列表判 hit，对题录卡片偏向；阶段 20 已用答案级 `coverage_ratio` 与真实 Jina query-only 校验闭环。

后续承接：

- 阶段 20 已承接：(1) 用答案级 `coverage_ratio` 复核默认链路切换；(2) 用 `responsibility_gate` 闭环工程责任拒答边界；(3) 保留离线 LLM-judge 作为可选增强，不进入 CI 或默认链路。

面试表达：

```text
阶段 19 我没有继续堆模型或语料，而是把已经入库的约 340 篇中文深度全文真正用起来。第一轮真实/确定性 agent 探索就暴露了一个之前没被量化过的真实排序短板：8 道 on-topic 中文问题里没有一题 top-1 是深度全文，5 题被题录卡片占据。中文难评测集进一步在 15 道非拒答题上把 deep_top1 量化到 0.000，这是阶段 18 之后的真实瓶颈。

调优我没有引入新 reranker，而是用纯函数的 source_type_reweight 在 hybrid 候选之后做后处理，对照三种配置。结果是三组都能把 deep_top1 从 0.000 推到 0.53–0.73，但 precision@1 因关键词判定偏向题录而下降，按严格门槛（Δp@1 ≥ 0.10 且 Δdeep_top1 ≥ 0.20 且 refusal 不退化）保持 keep_existing_hybrid，并把三候选作为可配置开关留作后续切换依据。"先用起来 → 暴露真实问题 → 用难评测集量化 → 用纯函数对照 → 用门槛诚实决策"的闭环，是阶段 19 想传达的工程方法。
```

## 历史状态：2026-06-09（阶段 18 之后增量：中文全文语料 + 拒答边界校准，待人工核验）

在 `claude/phase-18-corpus-evaluation-quality` 分支、阶段 18 主体之后，由用户驱动追加了一段工作（详见 `docs/stage18_followup_chinese_corpus.md`）。是否单列为新阶段由用户人工核验时决定；当前**未提交、未打 tag、未推送**。

- **中文全文语料**：导入用户合法下载的中文文献。`scripts/import_papers_corpus.py` 扫描 `papers_NEW`（322 PDF + 2 CAJ），入库 **298 篇**；24 篇未入库（8 扫描需 OCR + 16 损坏）按用户决定放弃。新增依赖 `cryptography>=3.1` 解密知网 AES PDF。
- **语料规模**：documents **465**、chunks **8918**、深度全文（institutional+open_access）**约 340 篇**。
- **索引**：确定性 + 真实 Jina 均全覆盖 8918；`VectorIndexService.build_index` 新增 `sleep_seconds` 限速与 `max_retries` 退避重试（`build_vector_index.py` 暴露 `--sleep-seconds/--max-retries`），以遵守 Jina 速率限额、容忍瞬断。
- **中文问答验收**：`data/evaluation/cn_fulltext_queries.csv` + `cn_fulltext_results.csv`，真实 MIMO+Jina 验证——可答题忠实且带引用溯源，off-topic 不胡编。
- **off-topic 拒答校准（闭环阶段 18 high 风险）**：根因是 `EvidenceConfidence` 中文按单字切词导致 off-topic 单字偶然命中。修复：`workflow.py` 增加主题门 `has_topic_anchor` + `CORE_DOMAIN_TERMS`，作用于改写后查询。验证：off-topic 5/5 拒答（原 1/5）、on-topic 8/8 不误拒、难评测集 refusal 5/5。
- **质量门槛**：overall quality gate **review_required/high → review_required/medium**（refusal_boundary 闭环，仅余阶段 16 ITZ 的 medium）。
- **测试**：全量 **382 passed**（含新增 `tests/test_vector_index_retry.py`）。

## 最新状态：2026-06-08（阶段 18 语料扩充与评测/质量体系增强，待人工核验）

当前阶段：阶段 18，语料扩充与评测/质量体系增强。在 `claude/phase-18-corpus-evaluation-quality` 分支完成开发、测试、普通文档和 Obsidian 草稿，停在用户人工核验前：尚未执行 `git add`、`git commit`、`git tag`、`git push`，也未创建 PR。

Git / tag / main 起点：

- 阶段 17 已完成人工核验、提交、创建 `phase-17-complete` tag（指向最终功能提交 `5b5ef02`）并合并到 `main`（合并提交 `d633b95`）。
- `phase-17-complete` 是 `main` 祖先；阶段 18 从含阶段 17 合并的 `main` 出发；未移动任何已有阶段 tag。

阶段 18 完成内容：

- 使用 Planning with Files 维护 `task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage18_corpus_evaluation_quality.md` 设计文档。
- PDF 解析加固 `app/services/ingestion/pdf_text.py`：标题层级、表格、断词合并、公式/页眉页脚去噪；接入 `parser.read_pdf_text`，向后兼容。
- 语料深度扩充（诚实报数）：`scripts/expand_open_access_corpus.py` 用 OpenAlex 发现 866 -> RFC 相关 90 -> 许可允许开放获取 16，真实新导入 5 篇深度全文；深度全文 11 -> 16（open_access_pdf 10 -> 15），chunks 997 -> 1332；重建 deterministic 与 jina 双索引；重置并重新 sync source registry（open_access 10 -> 15）。RFC 窄领域开放全文有限，未达 40-60，按用户决策诚实报数。
- 难评测集 `data/evaluation/stage18_hard_queries.csv`（20 题）+ 多配置对比 `scripts/evaluate_stage18_hard_set.py`。
- quality gate `scripts/build_stage18_quality_report.py` + 增强 `/quality-report`（筛选 / 风险队列 / 导出）+ 只读导出端点。

评测结果（deterministic）：

```text
hard set 多配置 hit@8: 全部 15/15（recall 饱和）
hard set 多配置 precision@1: keyword 1.00, hybrid 0.93, bm25_rrf 0.93, bm25_rrf_context 0.93, vector 0.73
default_chain_decision: keep_existing_hybrid
refusal (brain_default evidence confidence): 1/5（off-topic 多数未拒答）
真实 Jina 校验: vector p@1 0.73 -> 1.00；refusal 仍 1/5
quality gate: review_required/high（高风险=off-topic 拒答边界偏松）
full tests: 377 passed
```

遗留问题：

- off-topic 拒答边界偏松：deterministic 与真实 Jina 下 5 题需拒答均仅 1 题被拒。属真实风险，已在 quality gate 显式阻断并写明原因；阶段 18 不静默修改默认拒答逻辑，留待后续独立校准 Phase（为 evidence confidence 增加主题相关度下限 / off-topic 守卫）。
- 阶段 16 `user_mixed_itz_strength` Answer Coverage 风险 carry-forward，未在阶段 18 范围内解决；阶段 18 新增 3D mesoscopic ITZ 全文后可在后续做真实回答复核。
- 语料深度全文未达 40-60 目标（RFC 窄领域开放全文有限）。
- 阶段 18 当前未提交、未打 `phase-18-complete` tag、未推送 GitHub，等待用户人工核验和明确确认。

下一阶段任务：

- 用户人工核验阶段 18 解析加固、语料扩充、难评测集、多配置对比、quality gate 和 `/quality-report` 增强。
- 如确认通过，再执行提交、创建 `phase-18-complete` tag 并推送；tag 应指向阶段 18 最终功能提交。
- 后续可做拒答边界校准 Phase（主题相关度下限 / off-topic 守卫），并视情评估 RRF/综述降权是否进默认链路。

面试表达：

```text
阶段 18 我补的是 RAG 系统真正的短板：语料深度和评测区分度，而不是再加模型。原来 115 篇只是题录、深度全文只有 11 篇，旧评测集又饱和到 15/15，所以阶段 17 的 BM25+RRF 看起来零增益。

我做了四件事：第一，加固 PDF 解析，把章节标题、表格、断词和公式噪声处理好，让全文 chunk 带上真实 heading_path；第二，用 OpenAlex 只下载许可允许的开放获取全文，加固解析后导入，深度全文从 11 提到 16——RFC 是窄领域，开放全文有限，我诚实报数没有为凑 40-60 造假；第三，专门建难评测集（跨段、易混淆、需拒答），在上面对比五种检索配置，发现 hit@8 仍饱和但 precision@1 有区分度，bm25_rrf 没赢过 hybrid，所以数据支持 keep_existing_hybrid；第四，把这些沉淀成 quality gate，并增强 /quality-report 的只读筛选、风险队列和导出。最关键的是，难评测集暴露了一个真实风险：明显 off-topic 的问题大多没被拒答，我没有掩盖，而是在 quality gate 里显式标成 high 阻断并写清原因，留给下一阶段做拒答边界校准。
```

## 历史状态：2026-06-08（阶段 17 含 Phase 9 人工复核完成，待人工核验）

当前阶段：阶段 17，检索架构升级已完成 Phase 0-8 开发，并追加完成 Phase 9「检索升级人工复核与接入建议」。当前状态按用户要求停在人工核验前：尚未执行 `git add`、`git commit`、`git tag`、`git push`，也未创建 PR。

### Phase 9 人工复核与默认链路接入建议（2026-06-08）

- 新增人工复核结果表 `data/evaluation/stage17_retrieval_upgrade_manual_review.csv`：14 acceptable、1 needs_tuning、0 regression、0 defer；1 条 default_switch_blocker。
- 逐条复核发现：headline「regression=0」是 hit 级定义，掩盖了 `mesoscopic_modeling` 的排序软退化（rank 2 -> 7，vector_rank=29，被泛主题综述文档挤占）；该样例标为 needs_tuning 与默认替换阻断证据。
- 5 条 `source_match=no` 中 4 条为等价主题文献换位（多为中文 query 下中文母语文献上浮），仍 top-1 命中，判 acceptable。
- 默认链路接入建议：`RRFHybridSearchService`、`BM25SearchService`、`ContextExpansionService` 保持候选/配置开关，**不替换默认 `HybridSearchService`、Brain、`/chat`、`/agent`**；阻断理由是评测集 hit 饱和零增益 + 综述上浮排序软退化。
- `scripts/evaluate_stage17_retrieval_upgrade.py` 的 `write_report` 已可复现地把 Phase 9 摘要纳入 `docs/stage17_retrieval_upgrade_report.md`；报告用已有结果 CSV 重生成，不跑检索、不碰 DB、不触发真实 API。
- 新增 `tests/test_stage17_manual_review.py`，强制非 acceptable / source_match=no 样例带证据与调优建议。
- 下一阶段依据：阶段 18 需构建更有区分度的难评测集，并对综述类文档加权或 topic-anchor rerank 做对照，再决定 RRF 是否进入默认链路。

当前关键证据：

- 当前分支：`codex/phase-17-retrieval-architecture-upgrade`。
- 阶段 16 已合并到 `main`，`main` 当前阶段 16 合并提交为 `ff48056 Merge phase 16 quality risk closure`。
- `phase-16-complete -> aaba285`，且是 `main` 祖先；未移动任何已有阶段 tag。
- 阶段 17 新增 `docs/stage17_retrieval_architecture_upgrade.md`。
- 阶段 17 新增 `app/services/retrieval/context_expansion.py`，支持同 document 相邻 chunk 上下文扩展，引用仍指向核心 chunk。
- 阶段 17 新增 `app/services/retrieval/bm25_search.py`，实现 BM25 lexical retriever，保留旧 keyword baseline。
- 阶段 17 新增 `app/services/retrieval/rrf_fusion.py`，实现 BM25+vector 多通道召回、按 `chunk_id` 去重、RRF ranking 和 provenance。
- 阶段 17 新增 `scripts/evaluate_stage17_retrieval_upgrade.py`、`data/evaluation/stage17_retrieval_upgrade_results.csv`、`docs/stage17_retrieval_upgrade_report.md`。
- 阶段 17 评测结果：upgraded=15/15，baseline=15/15，improved=0，regression=0。
- 默认链路决策：暂不自动替换旧 `HybridSearchService`；BM25+vector RRF 作为人工核验候选。
- 阶段 17 聚焦回归测试：97 个测试通过。
- 阶段 17 全量测试：343 个测试通过。

阶段 17 完成内容：

- 使用 Planning with Files 维护阶段 17 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 建立阶段 17 设计文档，明确检索流水线、BM25、RRF、context expansion、baseline 对比、安全边界和人工核验前收尾要求。
- 建立邻近 chunk 上下文扩展服务，不新增数据库表，不改变核心引用 chunk。
- 建立 BM25 lexical retriever，支持中英文领域术语、标题/heading/content 加权和稳定排序。
- 建立 BM25+vector RRF 融合服务，保留 matched_channels、bm25_rank、vector_rank、rrf_score 和 provenance。
- 生成阶段 17 检索升级评测表和报告。
- 确认阶段 17 不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report`。
- 确认阶段 17 不保存 API key、Bearer token、供应商原始敏感响应或受限全文。

遗留问题：

- 当前 baseline 查询集只能证明 BM25+vector RRF 无 regression，不能证明明显优于旧 hybrid；Phase 9 已确认根因是评测集 hit 饱和缺乏区分度。
- `filling_capacity_cn` 等 `source_match=no` 样例已在 Phase 9 人工复核：4 条等价文献换位判 acceptable，`mesoscopic_modeling` 排序退化判 needs_tuning，详见 `stage17_retrieval_upgrade_manual_review.csv`。
- `mesoscopic_modeling` 的排序软退化未即时调优修复（属检索重排调参，超出人工复核 Phase 边界），记录为 tuning_suggestion 留给阶段 18。
- 阶段 16 的 `user_mixed_itz_strength` 质量 high 阻断不能被阶段 17 检索升级自动视为已解决。
- 阶段 17 当前未提交、未打 `phase-17-complete` tag、未推送 GitHub，等待用户人工核验和明确确认。

下一阶段任务：

- 用户人工核验阶段 17 设计文档、BM25/RRF 代码、评测表、报告和默认链路决策。
- 如确认通过，再执行提交、创建 `phase-17-complete` tag 并推送；tag 应指向阶段 17 最终功能提交。
- 后续阶段 18 可进入质量报告与评测体系增强，把多套检索配置和风险队列接入更长期的只读报告。

面试表达：

```text
阶段 17 我没有先引入复杂 Agent 框架，而是升级检索架构。旧 hybrid 是关键词分数和向量分数归一化后加权，虽然稳定，但分数尺度并不天然一致。因此我新增 BM25 作为标准词法检索通道，再用 RRF 按排名融合 BM25 和 vector 结果，避免硬加权。上下文方面，我先用同文档相邻 chunk 做 parent-like context expansion，让回答看到更多前后文，同时引用仍指向核心 chunk。

评测上，我保留旧 hybrid baseline，新增 stage17_retrieval_upgrade_results.csv 对比 baseline_hit、upgraded_hit、rank_before、rank_after 和 decision。结果是 upgraded 15/15、baseline 15/15、regression 0，但没有明显优于旧 hybrid，所以默认链路暂不切换，只把 BM25+vector RRF 作为人工核验候选。
```

## 历史状态：2026-06-07（阶段 16 开发完成，待人工核验）

当前阶段：阶段 16，真实质量风险闭环已完成开发、测试、普通文档和 Obsidian 草稿收尾。当前状态按用户要求停在人工核验前：尚未执行 `git add`、`git commit`、`git tag`、`git push`，也未创建 PR。

当前关键证据：

- 当前分支：`codex/phase-16-real-quality-risk-closure`。
- 阶段 15 已合并到 `main`，`main` 当前阶段 15 合并提交为 `b5bad50 Merge phase 15 real review report`。
- `phase-15-complete -> a844948`，未移动任何已有阶段 tag。
- 阶段 16 新增 `docs/stage16_quality_risk_closure.md`。
- 阶段 16 新增 `scripts/analyze_stage16_decompose_diagnostics.py` 与 `data/evaluation/stage16_decompose_diagnostics.csv`。
- real decompose 当前闭环结论：追加显式真实重试后为 `status_after=retry_completed`，`root_cause=embedding_header_compatibility_and_chat_timeout`，`blocking_status=not_blocking`。
- 阶段 16 新增 `scripts/evaluate_stage16_answer_coverage_closure.py` 与 `data/evaluation/stage16_answer_coverage_closure.csv`。
- Answer Coverage 闭环表：9 行，`risk_after high=1`、`medium=3`、`low=5`。
- high 阻断样例仍为 `user_mixed_itz_strength`，根因为真实回答超时，不能证明 ITZ 与强度回答覆盖度。
- 阶段 16 新增 `scripts/build_stage16_quality_closure_report.py`、`data/evaluation/stage16_quality_closure_summary.csv`、`docs/stage16_quality_closure_report.md`。
- `GET /quality-report` 当前展示阶段 16 只读质量风险闭环报告，不触发真实 API。
- 阶段 16 quality gate：`review_required/high`，当前 high 阻断来自 Answer Coverage，不再来自 decompose。
- 阶段 16 脚本复跑稳定：decompose 诊断、Answer Coverage 闭环和质量报告均可重复生成。
- 阶段 16 聚焦回归测试：80 个测试通过。
- 阶段 16 全量测试：322 个测试通过。

阶段 16 完成内容：

- 使用 Planning with Files 维护阶段 16 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 建立阶段 16 设计文档，明确风险分级、排查流程、复核标准、安全边界和人工核验前收尾要求。
- 排查阶段 15 real decompose SSL EOF，将笼统 high/error 先分类为 provider/network 层 SSL EOF；随后追加真实重试，补齐 embedding provider `api-key` 兼容请求头，并用更长 chat timeout 跑通 decompose 10/10。
- 改进阶段 15 真实配置复跑的错误摘要压缩方式，长错误保留开头和结尾，避免未来丢失 traceback 尾部关键字。
- 对 `stage15_answer_coverage_review.csv` 中 1 条 high 和 8 条 medium 样例逐条闭环，输出 `risk_before`、`risk_after`、`root_cause`、`decision` 和 `next_action`。
- 生成阶段 16 质量闭环汇总表、Markdown 报告和 `/quality-report` 静态只读页面。
- 确认阶段 16 不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`。
- 确认阶段 16 不保存 API key、Bearer token、供应商原始敏感响应或受限全文。

遗留问题：

- `user_mixed_itz_strength` 仍为 Answer Coverage high/blocking，需要人工确认是否重跑真实回答或调整 timeout。
- 3 条 medium 样例为 `source_detail_limited`，建议保留人工审阅或后续补充更细证据。
- 阶段 16 当前未提交、未打 `phase-16-complete` tag、未推送 GitHub，等待用户人工核验和明确确认。

下一阶段任务：

- 用户人工核验阶段 16 质量表、报告页和 high/medium 风险结论。
- 如确认通过，再执行提交、创建 `phase-16-complete` tag 并推送；tag 应指向阶段 16 最终功能提交。
- 如人工核验认为仍需增强，可追加阶段 16 小 Phase，优先处理真实 decompose 重试、timeout 配置或 high 样例真实回答复跑。
- 后续阶段 17 可进入检索架构升级，但必须先确认阶段 16 阻断项是否放行。

面试表达：

```text
阶段 16 我没有用 deterministic 结果掩盖真实失败，而是把阶段 15 质量报告里的 high/medium 风险逐条闭环。real decompose 的 SSL EOF 先被分类为 provider/network 层问题，随后通过补齐 embedding 的 `api-key` 兼容请求头并把真实 chat timeout 提到 120 秒完成显式重试，结果 10/10 通过。Answer Coverage 的 9 条 high/medium 样例被拆成 1 high、3 medium、5 low，每条都有 root_cause、decision 和 next_action。

报告层面，我生成了阶段 16 quality closure summary、Markdown 报告和 /quality-report 只读页面。质量门禁仍是 review_required/high，但当前 high 阻断已经转为 Answer Coverage 样例，而不是 decompose。验证上，阶段 16 聚焦回归 80 个测试通过，全量测试 320 个通过，核心 search/vector/hybrid/chat/agent API 没有被破坏。
```

## 最新状态：2026-06-07（阶段 15 完成）

当前阶段：阶段 15，真实配置复跑与质量审阅报告已完成。下一步建议进入阶段 16：处理阶段 15 报告暴露的发布前质量风险，优先排查真实 decompose SSL EOF、复核 1 条 Answer Coverage high 风险样例，并继续推进 medium 样例人工审阅闭环；HyDE 仍只做离线实验，不进入默认链路或自动回归。

当前关键证据：

- 当前分支：`codex/phase-15-real-review-report`。
- 阶段 14 已合并到 `main`，`main` 阶段 14 合并提交为 `b9cb019 Merge phase 14 real quality calibration`。
- `phase-14-complete -> e5df149`，未移动已有阶段 tag。
- 阶段 15 新增 `docs/stage15_real_review_report.md`。
- 阶段 15 新增 `scripts/evaluate_stage15_real_config.py` 与 `data/evaluation/stage14_real/real_config_status.csv`。
- 阶段 15 真实配置复跑结果：vector 15/15、hybrid 15/15、user_questions 27/30、chat 6/6、agent 5/5、Brain workflow 18/18。
- 阶段 15 真实 decompose 复跑记录为 `error`，原因是真实 embedding 请求出现 `SSL: UNEXPECTED_EOF_WHILE_READING`，没有伪造成成功。
- 阶段 15 新增 `scripts/evaluate_stage15_answer_coverage_review.py` 与 `data/evaluation/stage15_answer_coverage_review.csv`。
- Answer Coverage 复核表：9 行，`high=1`、`medium=8`。
- 阶段 15 新增 `scripts/build_stage15_quality_report.py`、`data/evaluation/stage15_quality_summary.csv`、`docs/stage15_quality_report.md` 与 `app/frontend/quality_report.html`。
- 只读质量报告入口：`GET /quality-report`。
- 阶段 15 质量汇总表：14 行，风险统计 `high=4`、`low=7`、`medium=3`，overall quality gate 为 `review_required/high`。
- deterministic 回归保持稳定：vector 13/15、hybrid 15/15、user_questions 25/30、decompose 10/10、chat 6/6、agent 5/5、Brain workflow 18/18。
- 阶段 15 聚焦回归测试：112 个测试通过。
- 阶段 15 全量测试：300 个测试通过。
- 阶段 15 tag：`phase-15-complete`，阶段最终提交完成后指向该提交。

阶段 15 完成内容：

- 使用 Planning with Files 维护阶段 15 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 建立阶段 15 设计文档，明确真实配置复跑、graceful skip、Answer Coverage 复核、质量汇总和只读报告边界。
- 建立 `stage14_real` 真实配置结果目录，显式记录 completed/error/skipped 状态。
- 将真实配置状态合并回 `stage14_embedding_comparison.csv`，保留 deterministic baseline 与 real_config 对比。
- 建立阶段 15 Answer Coverage 复核表，记录 Faithfulness、Answer Coverage、Citation Quality、风险等级、回答摘要和 next action。
- 建立阶段 15 质量汇总表和只读报告页，展示真实配置状态、回答覆盖风险和 Decompose provenance 证据。
- 确认阶段 15 不改变 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`。

遗留问题：

- 真实 decompose 复跑仍有外部 embedding 请求 SSL EOF，属于发布前高优先级排查项。
- `user_mixed_itz_strength` 在真实 default_hybrid 结果中出现读取超时，被标为 Answer Coverage high 风险。
- 其余 8 条 medium 样例仍需要人工审阅确认回答是否真正覆盖期望技术点。
- 阶段 15 报告页是静态只读入口，还没有交互式筛选或在线表格钻取；这是有意保守，不在本阶段重构前端。

下一阶段任务：

- 复跑或重试真实 decompose，区分供应商网络问题、超时配置问题和 embedding provider 稳定性问题。
- 对 Answer Coverage high/medium 样例做人工审阅或真实模型摘要复核，形成可发布的质量门槛。
- 如需增强报告体验，优先做只读筛选和下载，不要改动核心 RAG API。
- 继续保留 deterministic baseline，真实配置只作为发布前质量校准依据。

面试表达：

```text
阶段 15 我把阶段 14 的质量校准表推进成了真实配置复跑和质量审阅报告。系统仍然保留 deterministic baseline 作为稳定回归，用它复跑 vector、hybrid、user questions、Decompose、chat、agent 和 Brain workflow；真实配置结果单独输出到 stage14_real，并显式记录 completed、skipped 或 error，不把真实 API 的失败伪造成成功。

回答质量上，我用阶段 15 复核表承接阶段 14 的 medium/review 样例，把 Faithfulness、Answer Coverage 和 Citation Quality 分开记录，并用真实回答摘要和来源命中辅助判断。报告层面，我新增了 quality summary、Markdown 报告和 /quality-report 只读页面，用来展示真实配置状态、回答覆盖风险和 Decompose provenance。这个阶段的重点不是继续加功能，而是让发布前质量风险可见、可追踪、可复查。
```

## 最新状态：2026-06-07（阶段 14 完成）

当前阶段：阶段 14，真实 Embedding 与回答覆盖校准已完成。下一步建议进入阶段 15：复跑真实配置结果、建立真实回答人工审阅闭环，或将阶段 14 的质量校准表接入只读报告页；HyDE 仍只做离线实验，不进入默认链路或自动回归。

当前关键证据：

- 当前分支：`codex/phase-14-real-quality-calibration`。
- 阶段 13 已合并到 `main`，`main` 阶段 13 合并提交为 `27b25d3 Merge phase 13 decompose evidence merge`。
- `phase-13-complete -> 69a28cd`，未移动已有阶段 tag。
- 阶段 14 新增 `docs/stage14_real_quality_calibration.md`。
- 阶段 14 新增 `scripts/evaluate_stage14_embedding_comparison.py` 与 `data/evaluation/stage14_embedding_comparison.csv`。
- 阶段 14 新增 `scripts/evaluate_stage14_answer_coverage.py` 与 `data/evaluation/stage14_answer_coverage_review.csv`。
- 阶段 14 新增 `scripts/evaluate_stage14_decompose_provenance.py` 与 `data/evaluation/stage14_decompose_provenance_review.csv`。
- 显式 deterministic embedding 对比结果：vector 13/15、hybrid 15/15、user questions 25/30、decompose 10/10、chat 6/6、agent 5/5、Brain workflow 18/18。
- real_config 当前记录为 `missing_results` 或 `skipped`，因为 `data/evaluation/stage14_real/` 下没有阶段 14 真实结果 CSV；阶段 14 没有伪造真实模型成功结果。
- Answer Coverage 校准表：20 行，`low=1`、`medium=9`、`skipped=10`。
- Decompose provenance 可读化表：50 行证据级记录，`decomposed_rows=15`、`both_match_rows=37`。
- 阶段 14 聚焦测试：49 个测试通过。
- API/前端聚焦测试：28 个测试通过。
- 核心服务聚焦测试：75 个测试通过。
- 全量测试：275 个测试通过。
- 阶段 14 tag：`phase-14-complete`，阶段最终提交完成后指向该提交。

阶段 14 完成内容：

- 使用 Planning with Files 维护阶段 14 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 新增阶段 14 设计文档，明确真实 embedding 对比、Answer Coverage 校准、graceful skip、API 兼容和 HyDE 边界。
- 建立 embedding comparison 结果表，显式区分 deterministic baseline、real_config missing_results/skipped 和失败 query。
- 建立 Answer Coverage 校准表，把 Faithfulness、Answer Coverage、Citation Quality、risk_level 和 recommendation 结构化。
- 建立 Decompose provenance 可读化表，把长字符串 rerank explanation 拆成 evidence_rank、topic_terms、both_match、source_type、raw_score、final_score 等字段。
- 确认前端无需重构，因为阶段 14 的只读审阅需求已由 CSV 产物满足，旧 API schema 未改变。

遗留问题：

- `data/evaluation/stage14_real/` 尚无真实配置结果文件，因此真实 embedding / 真实 chat 的阶段 14 completed 指标仍待显式复跑。
- deterministic user questions 为 25/30，保留了 vector_only 来源命中不匹配边界，说明真实 embedding 或更强 rerank 仍有后续价值。
- deterministic answer 多数只能标为 Answer Coverage `review`，不能证明真实语言覆盖度。
- 阶段 14 质量表目前是 CSV，可读但还不是前端报告页。

下一阶段任务：

- 在明确成本、限流和 API key 边界后，把真实 vector/hybrid/user/decompose/chat/agent/brain workflow 结果输出到 `data/evaluation/stage14_real/`。
- 对 `stage14_answer_coverage_review.csv` 中 medium/review 样例做真实模型回答或人工摘要复核。
- 可把阶段 14 的三张质量表做成只读报告页，但不改变核心 RAG API。
- 继续保留 deterministic baseline，真实配置结果只作为发布前质量校准依据。

面试表达：

```text
阶段 14 我没有把真实模型结果和本地回归混在一起，而是先建立清晰的质量校准层。系统保留 deterministic baseline，用它稳定复跑 vector、hybrid、user questions、Decompose、chat、agent 和 Brain workflow；真实 embedding 或真实 chat 没有结果文件时，只记录 missing/skipped，不伪造成成功。

回答质量上，我把 Answer Coverage、Faithfulness 和 Citation Quality 拆开审阅。来源命中只能说明找到了资料，不代表回答覆盖了用户要点。所以阶段 14 新增校准表，把问题、期望要点、回答、证据、风险和建议放在一起；同时把 Decompose 的 provenance 和 rerank explanation 拆成证据级字段，让后续能判断每条证据为什么进入上下文。
```

## 历史状态：2026-06-07（阶段 13 完成）

当前阶段：阶段 13，Decompose 与可解释证据合并已完成。下一步建议进入阶段 14：真实 embedding 对比、真实模型 Answer Coverage 校准，或将 Decompose provenance 做成前端/评测可视化；HyDE 仍只做离线实验，不进入默认链路或自动回归。

当前关键证据：

- 当前分支：`codex/phase-13-decompose-evidence-merge`。
- 阶段 12 已合并到 `main`，`main` 最新阶段 12 合并提交为 `5c7bb58 merge phase 12 quality review context calibration`。
- `phase-12-complete -> d7b5bff`，未移动已有阶段 tag。
- 阶段 13 新增 `app/services/retrieval/decompose.py`，实现规则式 Decompose、子 query 检索、证据合并、`chunk_id` 去重、sub query provenance 和可解释 rerank。
- 阶段 13 已接入 Brain hybrid 检索路径：只有复杂问题被规则判断为 decomposed 时才走子 query 检索，单主题问题继续走原 hybrid。
- 阶段 13 新增 `scripts/evaluate_decompose.py` 与 `data/evaluation/stage13_decompose_results.csv`。
- 阶段 13 Decompose 评测：`6/6 passed`；全用户问题 Decompose 评测：`10/10 passed`。
- 用户问题评测：`29/30 passed`，`refusal_matched=30/30`，`source_hit_matched=29/30`。
- deterministic 回归保持稳定：chat 6/6、agent 5/5、Brain workflow 18/18、hybrid 15/15、vector 13/15。
- 聚焦测试：31 个测试通过。
- 全量测试：257 个测试通过。
- 阶段 13 tag：`phase-13-complete`，阶段最终提交完成后指向该提交。

阶段 13 完成内容：

- 使用 Planning with Files 维护阶段 13 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 将 `docs/stage13_decompose_plan.md` 从预研计划升级为设计文档，明确拆解规则、数据结构、评测指标和失败保护。
- 实现 `DecomposeRetrievalService`，支持按 keyword/vector/hybrid 检索子 query。
- 实现 `MergedEvidence`，让合并后的证据仍能作为 Brain 的普通检索结果，同时保留 sub query provenance 和 rerank explanation。
- 在 Brain hybrid 检索路径接入 Decompose，并继续复用 evidence confidence。
- 新增阶段 13 专属评测脚本和结果表，记录子 query、去重数量、provenance、source hit 和 answer coverage proxy。
- 确认前端无需重构，因为旧 API schema 未改变。

遗留问题：

- deterministic answer 仍不能单独证明真实 Answer Coverage，发布前仍需要真实模型或人工审阅。
- vector-only 在用户问题集上仍保留 1 条来源命中不匹配，作为真实 embedding 对比或更强 rerank 的后续输入。
- Decompose provenance 目前主要保存在内部结构和评测 CSV，尚未在前端可视化。
- HyDE 仍未进入默认链路，只适合阶段 14 以后离线实验。

下一阶段任务：

- 对比 deterministic、Jina 或其他真实 embedding 在用户问题与 Decompose 场景下的差异。
- 用真实模型或人工审阅复核 Decompose 后的 Answer Coverage。
- 评估是否把 sub query provenance 和 rerank explanation 以只读方式展示到前端。
- 如实验 HyDE，必须保持离线、显式、不可进入默认自动回归。

面试表达：

```text
阶段 13 我没有直接换更大的模型，而是先解决复杂问题的证据覆盖。系统会把明显多主题问题拆成最多 3 个子 query，分别用 hybrid 检索，再按 chunk_id 去重合并，并保留每条证据来自哪个 sub query。排序上使用可解释规则，综合原始分数、主题词命中、source_type、keyword/vector 双路命中和子问题覆盖度。

这样做的好处是：复杂问题能召回更完整的依据，同时不会破坏引用溯源和拒答边界。unsupported 问题不会被强行拆成可回答问题，最终仍经过 Brain evidence confidence。阶段 13 的评测脚本会输出子 query、去重数量、provenance 和 rerank explanation，因此质量提升是可复现、可解释的。
```

## 历史状态：2026-06-06（阶段 12 完成）

当前阶段：阶段 12，质量审阅与上下文最小补全已完成。下一步建议进入阶段 13：规则式 Decompose、子 query 检索、证据合并、按 `chunk_id` 去重和可解释 rerank；HyDE 只做离线实验，不进入默认链路或自动回归。

当前关键证据：

- 当前分支：`codex/phase-12-quality-review-context-calibration`。
- 阶段 11 已合并到 `main`，`main` 最新阶段 11 合并提交为 `09926f5 merge phase 11 user evaluation query expansion`。
- `phase-11-complete -> fcd174e`，未移动已有阶段 tag。
- 阶段 12 新增 `data/evaluation/stage12_quality_review_results.csv`，记录 6 条抽样的 Faithfulness、Answer Coverage、Citation Quality、风险等级和下一步建议。
- 阶段 12 新增 `docs/stage12_quality_review.md`，说明人工审阅方法、rubric、结果、风险和质量结论。
- 阶段 12 在 Brain workflow 的 `rewrite_query` 位置实现最小上下文补全，支持基于可选 `history` 的“它/这个技术/这类问题”等代词或省略问法补全。
- `/chat` 和 `/agent/query` 新增可选 `history` 字段，旧请求不传该字段仍兼容。
- 阶段 12 新增 `docs/stage13_decompose_plan.md`，为后续 Decompose、证据合并、去重排序和可解释 rerank 提供输入。
- 用户问题评测保持 `25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
- deterministic 回归保持稳定：chat 6/6、agent 5/5、Brain workflow 18/18。
- API/核心回归测试：47 个测试通过。
- 全量测试：244 个测试通过。
- 阶段 12 tag：`phase-12-complete`，阶段最终提交完成后指向该提交。

阶段 12 完成内容：

- 使用 Planning with Files 维护阶段 12 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 落地阶段 12 质量审阅结果表，把阶段 11 的审阅字段真正用于质量校准。
- 新增阶段 12 质量审阅报告，明确 default_hybrid、keyword_baseline、vector_only 的差异和风险。
- 在 Brain `filter_history -> rewrite_query` 中实现最小上下文补全。
- 为 `/chat`、`/agent/query`、`CitationAnswerService` 增加可选 `history` 支持，同时保持旧请求兼容。
- 明确 HyDE 只保留为离线实验建议，不进入默认链路或自动回归。
- 新增阶段 13 Decompose 预研计划，建议后续做规则式拆解、子 query 检索、证据合并、按 `chunk_id` 去重和可解释 rerank。

遗留问题：

- deterministic answer 仍主要用于稳定回归，不能单独证明真实回答的 Answer Coverage。
- vector_only 在真实用户问题集上仍有 5 条来源命中不匹配。
- 上下文补全仅支持最近历史问题和明确指代词，不支持复杂多轮记忆。
- Decompose、可解释 rerank、真实 embedding 对比和 HyDE 离线评估仍留给后续阶段。

下一阶段任务：

- 阶段 13 可实现规则式 Decompose：复杂问题拆成最多 3 个子 query，分别检索、合并证据、按 `chunk_id` 去重和排序。
- 复用阶段 11 `SYNONYM_RULES` 做子 query 主题词增强。
- 建立 Decompose 评测脚本，比较复杂问题的 Answer Coverage 是否提升。
- 保持 unsupported 不被误拆解成可回答问题。

面试表达：

```text
阶段 12 我把阶段 11 的人工审阅设计落成质量校准结果。自动评测继续检查拒答、来源命中和引用有效性，人工审阅结果表则检查 Faithfulness、Answer Coverage 和 Citation Quality。结论是默认 hybrid 来源命中可靠，但 deterministic 回答不能单独证明真实语言覆盖度，vector-only 仍有主题漂移。

工程上我没有做复杂长期记忆，而是在 Brain workflow 的 rewrite_query 位置实现最小上下文补全。用户如果问“它有哪些研究”，并传入上一轮问题，系统会把最近历史问题拼入检索 query，但对外仍保留原始问题。这样既能改善省略问法检索，又不会破坏引用、拒答和 API 旧请求兼容。
```

## 历史状态：2026-06-06（阶段 11 完成）

当前阶段：阶段 11，真实用户问题评测集与跨语言质量提升已完成。下一步建议进入阶段 12：把人工审阅抽样用于发布前质量校准，评估更强 rerank、真实 embedding 对比或审阅报告自动汇总；自动回归仍不要依赖真实 API key。

当前关键证据：

- 当前分支：`codex/phase-11-user-evaluation-query-expansion`。
- 阶段 10 已合并到 `main`，`main` 最新阶段 10 合并提交为 `c0bf8d6 merge phase 10 rag quality calibration`。
- `phase-10-complete -> 1454919`，未移动已有阶段 tag。
- 阶段 11 新增 `data/evaluation/user_questions.csv`，包含 10 条真实用户风格问题，覆盖中文口语、英文、中英混合、工程中文和 unsupported。
- 阶段 11 新增 `scripts/evaluate_user_questions.py` 与 `data/evaluation/user_question_results.csv`，可比较 `default_hybrid`、`keyword_baseline`、`vector_only`。
- 阶段 11 扩展跨语言 query expansion，覆盖 ITZ/界面、creep/徐变、freeze-thaw/抗冻、porosity/孔隙率、emission/碳排放、steel fiber/钢纤维、rock shear key/剪力键等术语。
- Brain evidence confidence 已支持扩展后的中英文证据词，降低中文问题被英文证据误判为低证据的风险。
- 阶段 11 新增 `docs/stage11_user_evaluation_plan.md` 和 `data/evaluation/user_question_review_samples.csv`，用于人工审阅或 LLM-as-judge 离线校准。
- 用户问题评测：`25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
- 用户问题分配置结果：`default_hybrid=10/10`、`keyword_baseline=10/10`、`vector_only=5/10`。
- deterministic 回归：keyword 15/15、vector 13/15、hybrid 15/15、chat 6/6、agent 5/5、Brain workflow 18/18。
- API 回归测试：16 个测试通过。
- 全量测试：230 个测试通过。
- 阶段 11 tag：`phase-11-complete`，阶段最终提交完成后指向该提交。

阶段 11 完成内容：

- 使用 Planning with Files 维护阶段 11 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 扩充真实用户问题评测集，并为每条问题记录 query_id、question、language_type、expected_source_hit、expected_refused、expected_answer_points 和 notes。
- 新增用户问题评测脚本，输出通过率、失败原因、拒答匹配、来源命中、引用有效性和配置名。
- 复用并扩展 `SYNONYM_RULES`，让中文工程词和英文论文术语互相增强。
- 增强 Brain 证据置信度，让跨语言证据词参与低证据判断。
- 建立人工审阅抽样表和 LLM-as-judge 离线设计，但不让 CI 或自动回归依赖真实模型裁判。
- 保持 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` API schema 不变。

遗留问题：

- deterministic `vector_only` 在真实用户问题集上仍有 5 条来源命中不匹配，主要是主题漂移或领域术语召回不足。
- Faithfulness 与 Answer Coverage 仍需要人工审阅或离线 LLM-as-judge 校准，自动脚本只做稳定近似。
- 真实 MIMO + Jina 可作为发布前校准，但依赖本地 `.env`、网络、限流和余额，不应成为自动测试前提。

下一阶段任务：

- 阶段 12 可把 `user_question_review_samples.csv` 真正用于人工审阅，形成发布前质量审阅报告。
- 可比较真实 Jina embedding 与 deterministic vector 在用户问题集上的差异。
- 可设计更强但仍可解释的 rerank 或 query rewrite，优先修复 vector-only 用户问题失败项。
- 可把 LLM-as-judge 作为离线分析工具，但不要接入必跑回归。

面试表达：

```text
阶段 11 我把 RAG 评测从标准测试题扩展到真实用户问法。新增用户问题集显式记录语言类型、期望来源、期望拒答和回答覆盖点，自动脚本比较 default_hybrid、keyword_baseline 和 vector_only 三种配置，稳定检查拒答、来源命中和引用有效性。

优化上我没有做黑盒调参，而是复用已有 SYNONYM_RULES 做可解释的跨语言 query expansion，例如把“徐变”映射到 creep，把“孔隙率”映射到 porosity/void，把“剪力键”映射到 rock shear keys。由于 vector topic anchor 也复用这套词表，增强会同时影响关键词检索和向量候选排序。最后我补了人工审阅和 LLM-as-judge 的离线设计，把 Faithfulness、Answer Coverage 和 Citation Quality 从自动近似扩展到可抽样审阅。
```

## 历史状态：2026-06-06（阶段 10 完成）

当前阶段：阶段 10，真实 RAG 质量校准与拒答边界优化已完成。下一步建议进入阶段 11：扩大真实用户问题评测集，并继续做跨语言 query expansion、人工审阅抽样或 LLM-as-judge 评测。

当前关键证据：

- `task_plan.md` 当前阶段为 `Phase 6 complete`，阶段 10 已完成文档、Obsidian、最终验证、提交准备和 tag 收尾。
- 当前分支：`codex/phase-10-rag-quality-calibration`。
- 阶段 3 tag：`phase-3-complete -> 7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`，未移动。
- 阶段 4 最终提交：`b044459b9b8c2153e9225daa55af5d82cdcdb282`。
- 阶段 4 tag：`phase-4-complete -> b044459b9b8c2153e9225daa55af5d82cdcdb282`。
- 阶段 5 最终功能提交：`8c885e6cc714cc985933438697a7eb2523b26722`。
- 阶段 5 tag：`phase-5-complete -> 8c885e6cc714cc985933438697a7eb2523b26722`。
- 阶段 6 最终功能提交：由 `phase-6-complete` tag 指向的提交标识。
- 阶段 6 tag：`phase-6-complete`。
- 阶段 7 最终功能提交：由 `phase-7-complete` tag 指向的提交标识。
- 阶段 7 tag：`phase-7-complete`。
- 阶段 8 最终功能提交：由 `phase-8-complete` tag 指向的提交标识。
- 阶段 8 tag：`phase-8-complete`。
- 阶段 9 最终功能提交：由 `phase-9-complete` tag 指向的提交标识。
- 阶段 9 tag：`phase-9-complete`。
- 阶段 9.1 补充提交：由 `phase-9.1-complete` tag 指向的提交标识。
- 阶段 9.1 tag：`phase-9.1-complete`。
- 阶段 10 最终功能提交：由 `phase-10-complete` tag 指向的提交标识。
- 阶段 10 tag：`phase-10-complete`。
- 阶段 4 分支和 tag 已推送到 GitHub。
- `sources` 来源登记表已实现。
- `SourceRepository` 和 `SourceRegistryService` 已实现。
- `scripts/sync_sources.py` 已实现。
- sources API 已实现：`GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`。
- `scripts/evaluate_sources.py` 已实现。
- 真实来源同步：输入 283 条来源候选，创建 125 条来源记录，更新 132 次，合并重复 26 次。
- 来源评测：`total_sources=125`、`linked_documents=0`、`merged_duplicates=14`。
- 来源状态分布：`candidate=8`、`collected=117`。
- 全文保存权限分布：`institutional_access=2`、`metadata_only=110`、`open_access=10`、`unknown=3`。
- 可信度分布：`high=125`。
- `POST /chat` 已实现。
- `ChatModelProvider`、RAG prompt/context builder、`CitationAnswerService` 已实现。
- `qa_logs` 问答日志已落地。
- `scripts/evaluate_chat.py` 已实现。
- `data/evaluation/chat_results.csv` 已生成。
- Chat 评测：6/6 通过。
- `POST /search/vector` 已实现。
- `scripts/build_vector_index.py` 已实现。
- `scripts/evaluate_vector_search.py` 已实现。
- `data/evaluation/vector_results.csv` 已生成。
- 向量检索评测：13/15 通过。
- 关键词 baseline：15/15 通过。
- `docs/evaluation_plan.md` 已新增。
- `scripts/analyze_retrieval_errors.py` 已新增。
- `data/evaluation/retrieval_error_cases.csv` 已生成。
- `HybridSearchService` 已实现。
- `POST /search/hybrid` 已实现。
- `scripts/evaluate_hybrid_search.py` 已实现。
- `data/evaluation/hybrid_results.csv` 已生成。
- 混合检索评测：15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- 错误案例状态：4 个 vector 失败均为 `fixed_by_hybrid`。
- Chat 评测：6/6 通过。
- `docs/agent_design.md` 已新增。
- Agent 工具层已实现：`search_knowledge`、`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- Agent 编排服务已实现，支持规则式意图路由、最大工具调用步数限制、拒答和 `reasoning_summary`。
- `POST /agent/query` 已实现。
- `scripts/evaluate_agent.py` 已实现。
- `data/evaluation/agent_queries.csv` 和 `data/evaluation/agent_results.csv` 已生成。
- Agent 评测：5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `docs/brain_workflow_design.md` 已新增。
- `app/services/brain/` 已实现 Brain 中控层、配置模型、workflow step 记录和回答编排服务。
- `CitationAnswerService` 已迁移为 Brain 兼容门面，`POST /chat` 与 Agent `answer_with_citations` 复用同一条 Brain workflow。
- `scripts/evaluate_brain_workflow.py` 已新增。
- `data/evaluation/brain_workflow_results.csv` 已生成。
- Brain workflow 评测：18 次 config-query run；`keyword_baseline=6/6`，`default_hybrid=6/6`，`vector_only=6/6`。
- `docs/model_provider_evaluation.md` 已新增。
- `OpenAICompatibleEmbeddingProvider` 已实现，支持兼容 `/embeddings` 的真实 embedding API。
- `.env.example` 已补齐真实 embedding provider 配置字段：model、API key、base URL、dimension、timeout。
- `scripts/build_vector_index.py` 已支持 provider、model、API key、base URL、dimension、timeout 参数。
- `scripts/evaluate_model_configs.py` 已新增。
- `data/evaluation/model_config_results.csv` 已生成。
- 模型配置评测：deterministic baseline completed；阶段 10 已新增 `failed` 与 `pass_rate` 字段，并另行完成真实 MIMO + Jina 校准评测。
- 前端工作台已实现：来源管理、资料列表、chunk 查看、关键词/向量/混合检索、聊天问答、Agent 问答、工具调用记录、引用来源侧栏、source sync 和 source reindex 入口。
- 浏览器验证：桌面加载 sources=125、documents=136、chunks=997；移动视口 390x844 无横向溢出。
- 阶段 6 浏览器 smoke check：搜索模式包含 `keyword/vector/hybrid`，聊天检索模式包含 `auto/hybrid/vector/keyword`。
- 阶段 7 浏览器 smoke check：Agent 面板提交“检索 filling capacity 相关资料”后状态为 `answered`，工具调用为 `hybrid_search_knowledge`，返回 5 条混合检索结果。
- Jina 真实向量索引重建：997 个 chunk，995 个新写入，2 个已存在跳过；阶段 10 复核时数据库已有 Jina 索引 997 条。
- Jina vector 阶段 10 评测：15/15 通过。
- Jina hybrid 阶段 10 评测：15/15 通过。
- 真实 MIMO chat + Jina embedding 阶段 10 校准：chat 6/6、agent 5/5、brain workflow 18/18。
- 新增阶段 10 失败案例表：`data/evaluation/real_rag_failure_cases.csv`，记录 4 条真实 RAG 失败案例。
- 新增 Brain evidence confidence 低证据拒答保护，unsupported query 在生成前拒答。
- 新增 vector topic anchor rerank，deterministic vector 从 11/15 提升到 13/15。
- 全量测试：216 个测试通过。

下一步：

- 阶段 10 分支 `codex/phase-10-rag-quality-calibration` 已完成核心开发、验证、普通文档、Obsidian、最终测试和阶段 tag 收尾。
- 阶段 10 收尾时确认 `phase-10-complete` tag 指向阶段 10 最终功能提交。
- 阶段 10 之后，建议进入阶段 11：扩大真实用户问题评测集、跨语言 query expansion、人工审阅抽样或 LLM-as-judge。
- 不要移动已有阶段 tag：`phase-4-complete`、`phase-5-complete`、`phase-6-complete`、`phase-7-complete`、`phase-8-complete`、`phase-9-complete`、`phase-9.1-complete`。

## 2026-06-06 阶段 10 完成记录：真实 RAG 质量校准与拒答边界优化

当前分支：`codex/phase-10-rag-quality-calibration`

当前阶段：阶段 10 已完成核心开发、回归验证和真实模型校准。该阶段不移动 `phase-9-complete` 或 `phase-9.1-complete`，新增 `phase-10-complete` 作为阶段 10 最终功能提交的标识。

阶段 tag：`phase-10-complete`。

已完成：

- 使用 Planning with Files 维护阶段 10 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 9.1 已合并到 `main`，并确认 `phase-9-complete` 与 `phase-9.1-complete` 未移动。
- 新增 `scripts/analyze_real_rag_failures.py`，把阶段 9.1 真实模型失败拆成可诊断案例。
- 新增 `data/evaluation/real_rag_failure_cases.csv`，记录 unsupported under-refusal、vector topic drift 和 cross-language topic gap。
- 在 `app/services/brain/workflow.py` 新增 `EvidenceConfidence` 与 query-token coverage 规则。
- 在 `BrainService._generate_answer_step()` 中加入生成前低证据检查，证据不足时直接拒答，不调用真实模型硬生成。
- 在 `app/services/retrieval/vector_search.py` 新增 topic anchor rerank，让 vector-only 候选排序更贴合问题主题。
- 增强 `scripts/evaluate_model_configs.py`，新增 `failed` 和 `pass_rate` 字段。
- 新增和更新对应测试，覆盖失败分析、低证据拒答、vector rerank 和 model config 指标。
- 根据真实模型质量判断，单独复跑阶段 10 MIMO + Jina 校准评测，不覆盖 deterministic baseline。

设计结论：

- `EvidenceConfidence` 解决“检索有结果但证据不足”的问题，不等同于模型自信分。
- 低证据拒答放在 Brain 生成前，可以同时保护 `/chat` 与 Agent 引用问答工具。
- `topic anchor rerank` 不把 vector-only 静默改成 hybrid，只在向量候选内部调整排序，因此 baseline 仍可比较。
- deterministic provider 继续作为自动回归基线；真实 MIMO + Jina 作为最终体验校准更好，但不适合作为唯一自动测试依据。

验证结果：

- `python scripts\analyze_real_rag_failures.py`：生成 4 条失败案例。
- `python -m pytest tests\test_analyze_real_rag_failures.py -q`：3 个测试通过。
- `python -m pytest tests\test_brain_workflow.py tests\test_brain_service.py tests\test_answer_service.py tests\test_chat_api.py tests\test_agent_service.py -q`：31 个测试通过。
- `python -m pytest tests\test_vector_search.py tests\test_vector_search_api.py tests\test_evaluate_vector_search.py tests\test_hybrid_search.py tests\test_evaluate_hybrid_search.py tests\test_brain_service.py tests\test_evaluate_brain_workflow.py -q`：29 个测试通过。
- `python -m pytest tests\test_evaluate_model_configs.py -q`：7 个测试通过。
- `python scripts\evaluate_vector_search.py --provider deterministic --skip-index-build`：13/15 通过。
- `python scripts\evaluate_hybrid_search.py --provider deterministic`：15/15 通过，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py --chat-provider deterministic --embedding-provider deterministic`：6/6 通过。
- `python scripts\evaluate_agent.py --chat-provider deterministic --embedding-provider deterministic`：5/5 通过。
- `python scripts\evaluate_brain_workflow.py --chat-provider deterministic --embedding-provider deterministic`：`default_hybrid=6/6`、`keyword_baseline=6/6`、`vector_only=6/6`。
- `python scripts\evaluate_model_configs.py --include-real-config`：deterministic keyword 15/15、vector 13/15、hybrid 15/15、chat 6/6、agent 5/5、brain_workflow 18/18。
- `python -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py -q`：16 个测试通过。
- `python -m pytest -q`：216 个测试通过。
- `python scripts\evaluate_vector_search.py --provider openai-compatible --skip-index-build --out data\evaluation\stage10_jina_vector_results.csv`：Jina vector 15/15。
- `python scripts\evaluate_hybrid_search.py --provider openai-compatible --vector-results data\evaluation\stage10_jina_vector_results.csv --out data\evaluation\stage10_jina_hybrid_results.csv`：Jina hybrid 15/15。
- `python scripts\evaluate_chat.py --chat-provider openai-compatible --embedding-provider openai-compatible --out data\evaluation\stage10_mimo_jina_chat_results.csv`：MIMO + Jina chat 6/6。
- `python scripts\evaluate_agent.py --chat-provider openai-compatible --embedding-provider openai-compatible --out data\evaluation\stage10_mimo_jina_agent_results.csv`：MIMO + Jina agent 5/5。
- `python scripts\evaluate_brain_workflow.py --chat-provider openai-compatible --embedding-provider openai-compatible --out data\evaluation\stage10_mimo_jina_brain_workflow_results.csv`：MIMO + Jina Brain workflow 18/18。

遗留问题：

- deterministic vector 仍有 2 条未命中，适合后续用跨语言 query expansion 或更丰富领域词典继续优化。
- 真实模型评测依赖本地 `.env`、网络、限流和余额，不能作为 CI 或本地自动回归的唯一依据。
- 当前 evidence confidence 采用轻量 query-token coverage，后续可加入多来源一致性、LLM-as-judge 或人工审阅抽样。

下一阶段任务：

- 阶段 11 可扩大真实用户问题评测集，覆盖更多中文口语问法、工程场景和跨语言术语。
- 可补充 query expansion 或 rerank 对比实验，尤其关注 deterministic vector 剩余失败。
- 可建立人工审阅抽样表，验证 faithfulness 和 answer coverage 的主观质量。

面试表达：

```text
阶段 10 我没有继续扩模型 provider，而是把真实模型暴露出的 RAG 失败转成可解释、可回归的质量保护。

我先写失败案例分析脚本，把 MIMO + Jina Brain workflow 的失败拆成 unsupported 低证据拒答、vector-only 主题漂移和跨语言术语 gap。然后在 Brain 生成答案前加入 EvidenceConfidence，用 query-token coverage 判断召回片段是否足够支撑回答。这样即使真实向量模型对无意义问题召回了片段，系统也会在生成前拒答，而不是让模型硬编。

针对 vector-only 误召回，我在向量候选内部加了 topic anchor rerank，复用已有领域词扩展做轻量主题锚点排序，但不把 vector-only 静默改成 hybrid，也不改变 API schema。最终 deterministic Brain workflow 从 12/18 提升到 18/18；真实 Jina vector 达到 15/15，MIMO + Jina Brain workflow 达到 18/18。这个阶段体现的是：真实模型用于质量校准，deterministic baseline 用于稳定回归。
```

## 2026-06-06 阶段 9.1 补充记录：Jina 向量与 MIMO 真实评测

当前分支：`codex/phase-9-real-model-evaluation`

当前阶段：阶段 9.1 已完成。该补充阶段不移动 `phase-9-complete`，新增 `phase-9.1-complete` 作为真实 Jina + MIMO 补充验证提交的标识。

阶段补充 tag：`phase-9.1-complete`。

已完成：

- 本地 `.env` 配置 Jina embedding：`openai-compatible`、`jina-embeddings-v3`、1024 维；`.env` 已被 Git 忽略。
- 为 `OpenAICompatibleEmbeddingProvider` 增加 `Accept` 和 `User-Agent` 请求头，解决 Jina smoke index 初次返回 403 的问题。
- 使用 Jina 重建真实向量索引：997 个 chunk，995 个新写入，2 个 smoke run 已存在并跳过。
- 更新 vector/hybrid/chat/agent/brain workflow 评测脚本，让它们从 settings 读取完整 embedding provider 配置。
- 根据 MIMO 官方文档校准 Token Plan 接入：订阅 key 使用 `tp-...`，中国集群 OpenAI-compatible base URL 使用 `https://token-plan-cn.xiaomimimo.com/v1`。
- 为 `OpenAICompatibleChatModelProvider` 增加 `api-key`、`Accept` 和 `User-Agent` 请求头，同时保留 `Authorization: Bearer`，兼容 MIMO 和常规 OpenAI-compatible 服务。
- 使用真实 MIMO `mimo-v2.5-pro` 做 smoke test，返回 `MIMO_OK`。
- 单独生成真实组合评测文件：`mimo_jina_chat_results.csv`、`mimo_jina_agent_results.csv`、`mimo_jina_brain_workflow_results.csv`。
- 保持 deterministic provider 仍是自动测试默认路径；真实模型评测通过显式 `--chat-provider openai-compatible` 运行，避免 CI 或本地回归依赖真实密钥和余额。

验证结果：

- Jina smoke index：2 个 chunk 成功写入。
- Jina full index：total=997，indexed=995，skipped=2。
- `python scripts\evaluate_vector_search.py --skip-index-build`：Jina vector 14/15 通过。
- `python scripts\evaluate_hybrid_search.py`：Jina hybrid 15/15 通过，`rescued_vector=1`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py --chat-provider openai-compatible --out data\evaluation\mimo_jina_chat_results.csv`：6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_agent.py --chat-provider openai-compatible --out data\evaluation\mimo_jina_agent_results.csv`：5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_brain_workflow.py --chat-provider openai-compatible --out data\evaluation\mimo_jina_brain_workflow_results.csv`：15/18 通过；`default_hybrid=5/6`，`keyword_baseline=6/6`，`vector_only=4/6`。
- `python -m pytest tests\test_chat_model_provider.py tests\test_evaluate_chat.py tests\test_evaluate_agent.py tests\test_evaluate_brain_workflow.py -q`：26 个测试通过。
- `python -m pytest -q`：208 个测试通过。

遗留问题：

- `mimo_jina_brain_workflow_results.csv` 中仍有 3 个失败项：`vector_only/filling_capacity`、`default_hybrid/unsupported`、`vector_only/unsupported`。
- 当前 unsupported 拒答主要依赖检索结果是否为空；真实向量模型更容易为无意义词召回相似但无关片段，因此需要低置信度保护。
- 当前 hybrid 对真实向量召回已有提升，但还没有基于 query 类型动态调整 keyword/vector 权重。

下一阶段任务：

- 建议阶段 10：真实 RAG 质量校准与拒答边界优化。
- 增加低置信度拒答规则，例如最低相似度、关键词交叉验证、证据覆盖率和多来源一致性。
- 分析 `filling_capacity` 在 vector-only 下的失败原因，决定是优化 query expansion、hybrid 权重还是加入 rerank。
- 保留 deterministic baseline 和真实 MIMO + Jina 评测入口，持续做前后指标对比。

面试表达：

```text
阶段 9.1 我没有移动阶段 9 的完成 tag，而是把真实模型接入后的效果做成补充验证。

我先用 Jina 的真实 embedding 重建了 997 个 chunk 的向量索引，并复跑 vector 和 hybrid 评测。结果 vector 从 deterministic 的 11/15 提升到 14/15，hybrid 仍保持 15/15，说明真实 embedding 提升了语义召回，但 hybrid 仍是更稳的默认选择。

然后我按 MIMO 官方文档修正 Token Plan 接入方式：Token Plan key 是 tp 前缀，base URL 使用 token-plan-cn，并且请求头需要 api-key。我让 ChatModelProvider 同时支持 api-key 和 Bearer，既兼容 MIMO，也不破坏其他 OpenAI-compatible 服务。真实 MIMO + Jina 下，chat 6/6、agent 5/5、brain workflow 15/18。剩余失败集中在纯向量召回和 unsupported 拒答边界，这为阶段 10 的质量校准提供了清晰目标。
```

## 2026-06-06 阶段 9 完成记录：真实模型接入与模型评测

当前分支：`codex/phase-9-real-model-evaluation`

当前阶段：阶段 9 已完成。下一步建议由用户确认阶段 10 方向：Agent 权限审计与写入工具安全设计、部署工程化或更大规模用户问题评测。

阶段最终功能提交：由 `phase-9-complete` tag 指向的提交标识。

阶段 tag：`phase-9-complete`。

已完成：

- 使用 Planning with Files 维护阶段 9 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 8 已完成并合并到 `main`，且 `phase-8-complete` tag 指向阶段 8 最终功能提交，未移动已有阶段 tag。
- 新增 `docs/model_provider_evaluation.md`，明确真实模型 provider 边界、配置字段、向量索引重建、评测对比和阶段边界。
- 新增 `OpenAICompatibleEmbeddingProvider`，支持兼容 OpenAI `/embeddings` 的真实 embedding API。
- 扩展 `create_embedding_provider()`，兼容旧调用，同时支持 provider/model/api_key/base_url/dimension/timeout 参数。
- 更新 `.env.example` 和 `app/core/config.py`，补齐真实 embedding 配置字段。
- 更新 search/chat/agent API 的 embedding provider dependency，让 API 能消费真实 embedding 配置但不改变响应结构。
- 增强 `scripts/build_vector_index.py`，支持 provider、model、API key、base URL、dimension 和 timeout 参数。
- 新增 `scripts/evaluate_model_configs.py` 和 `data/evaluation/model_config_results.csv`，汇总 deterministic baseline 与可选真实模型配置。
- 新增测试：`tests/test_model_provider_evaluation_design.py`、`tests/test_build_vector_index.py`、`tests/test_evaluate_model_configs.py`，并扩展 `tests/test_embedding_provider.py`。

阶段 9 设计结论：

- `ChatModelProvider` 和 `EmbeddingProvider` 是模型隔离层，业务 service 不直接依赖具体模型 API。
- deterministic provider 继续作为默认实现，保证本地测试和无密钥环境稳定。
- 真实 embedding provider 采用 OpenAI-compatible `/embeddings` 边界，便于接入国产兼容模型服务。
- 切换真实 embedding 后必须按 provider/model/dimension 重建向量索引，否则 vector/hybrid search 查不到对应索引。
- 本地未配置真实 API key 时，模型配置评测记录 `real_config=skipped`，不让阶段验证失败。

验证结果：

- `python -m pytest tests\test_model_provider_evaluation_design.py -q`：2 个测试通过。
- `python -m pytest tests\test_embedding_provider.py -q`：12 个测试通过。
- `python -m pytest tests\test_embedding_provider.py tests\test_vector_index_service.py tests\test_build_vector_index.py -q`：20 个测试通过。
- `python scripts\build_vector_index.py --limit 1 --batch-size 1`：默认 deterministic 索引路径正常输出。
- `python -m pytest tests\test_evaluate_model_configs.py -q`：6 个测试通过。
- `python scripts\evaluate_model_configs.py --include-real-config`：12 行输出；deterministic baseline completed，real_config skipped。
- `python scripts\evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts\evaluate_vector_search.py`：vector 11/15 通过。
- `python scripts\evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_agent.py`：agent 5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_brain_workflow.py`：18 次 config-query run；`keyword_baseline=6/6`，`default_hybrid=4/6`，`vector_only=2/6`。
- `python scripts\evaluate_sources.py`：`total_sources=125`，`merged_duplicates=14`。
- `python -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py -q`：16 个测试通过。
- `python -m pytest -q`：205 个测试通过。

遗留问题：

- 当前真实模型配置未在本机运行，因为 `.env` 没有真实 API key、base URL、model 和 embedding dimension。
- 真实 embedding 的质量、成本、速度和稳定性需要用户本地配置后复跑同一批评测来量化。
- 当前没有自动后台索引任务；切换真实 embedding 后仍需手动运行 `scripts/build_vector_index.py`。

下一阶段任务：

- 可进入 Agent 权限审计与写入工具安全设计。
- 可进入部署工程化、日志观测和运行说明完善。
- 可扩大用户问题评测集，覆盖更多工程案例和中文问法。

面试表达：

```text
阶段 9 我补齐了真实模型接入和评测闭环，但没有把系统默认切到真实模型。

我先复核了 ChatModelProvider 和 EmbeddingProvider 的边界：业务层只依赖 provider 协议，不直接依赖具体模型 SDK。Chat 侧已有 OpenAI-compatible provider，所以本阶段重点补齐 OpenAICompatibleEmbeddingProvider，支持兼容 /embeddings 的真实向量接口，同时保留 deterministic provider 作为默认测试实现。

工程上我让 .env、API 依赖和 build_vector_index.py 都能传入 provider、model、API key、base URL、dimension 和 timeout。chunk_embeddings 已经按 provider/model/dimension/content_hash 保存，所以真实模型索引和本地索引可以并存，不会误用。评测上我新增 evaluate_model_configs.py，把 keyword、vector、hybrid、chat、agent 和 brain workflow 的结果汇总成模型配置对比表；没有真实 API key 时 real_config 会被标记为 skipped，而不是让测试失败。最终全量测试 205 个通过，说明真实模型边界已经接入，但本地稳定性仍由 deterministic baseline 保证。
```

## 2026-06-06 阶段 8 完成记录：Brain 中控层与 RAG Workflow 配置化

当前分支：`codex/phase-8-brain-workflow`

当前阶段：阶段 8 已完成。下一步建议由用户确认阶段 9 方向：真实模型接入与模型评测、Agent 权限审计、部署工程化或更大规模用户问题评测。

阶段最终功能提交：由 `phase-8-complete` tag 指向的提交标识。

阶段 tag：`phase-8-complete`。

已完成：

- 使用 Planning with Files 维护阶段 8 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 7 已完成并合并到 `main`，且 `phase-7-complete` tag 指向阶段 7 最终功能提交，未移动已有阶段 tag。
- 新增 `docs/brain_workflow_design.md`，明确 Brain 中控层目标、与 Quivr 的对应关系、workflow 步骤、配置化评测和阶段边界。
- 新增 `app/services/brain/config.py`，实现 `RetrievalConfig`、`WorkflowConfig` 和 `WorkflowStepConfig`。
- 新增 `app/services/brain/workflow.py`，定义 `BrainAnswerResult`、`BrainRetrievalOutcome`、`BrainWorkflowStepRecord`、引用提取和检索结果过滤函数。
- 新增 `app/services/brain/service.py`，实现轻量 `BrainService`，按 `filter_history -> rewrite_query -> retrieve -> optional_rerank -> generate_answer` 执行 workflow。
- `filter_history` 和 `rewrite_query` 第一版为 no-op，但保留结构化 step 记录。
- `retrieve` 复用现有 keyword/vector/hybrid service，`auto` 模式保持 vector 优先、keyword fallback。
- `optional_rerank` 第一版采用可解释截断；`rerank_top_n=0` 表示暂不重排。
- `generate_answer` 复用 `build_rag_prompt`、`ChatModelProvider`、citation 提取和 `qa_logs`。
- 改造 `CitationAnswerService` 为兼容门面，`POST /chat` 和 Agent `answer_with_citations` 共享 Brain workflow。
- 新增 `scripts/evaluate_brain_workflow.py` 和 `data/evaluation/brain_workflow_results.csv`，比较 `default_hybrid`、`keyword_baseline`、`vector_only` 三种配置。
- 阶段 8 不引入复杂 LangGraph workflow，不联网爬取新资料，不自动执行 source reindex，不新增前端配置面板。

阶段 8 设计结论：

- Brain 是内部中控层，不替代 keyword/vector/hybrid/source/chat/agent 等既有 service，而是统一编排它们。
- `RetrievalConfig` 解决“本次问答怎么检索、召回多少、是否重排、用什么 prompt/model provider”的问题。
- `WorkflowConfig` 解决“RAG 链路按哪些步骤执行”的问题。
- Chat 和 Agent 共用 Brain 后，后续真实模型接入、query rewrite 或 rerank 不需要分别改两套回答逻辑。
- 配置化评测证明本项目可以用同一批问题横向比较不同检索配置，而不是只看单次演示。

验证结果：

- `python -m pytest tests\test_brain_workflow_design.py -q`：2 个测试通过。
- `python -m pytest tests\test_brain_config.py -q`：13 个测试通过。
- `python -m pytest tests\test_brain_workflow.py tests\test_brain_service.py -q`：8 个测试通过。
- `python -m pytest tests\test_answer_service.py tests\test_chat_logging.py tests\test_chat_api.py tests\test_agent_tools.py -q`：24 个测试通过。
- `python -m pytest tests\test_agent_api.py tests\test_agent_service.py -q`：11 个测试通过。
- `python -m pytest tests\test_evaluate_brain_workflow.py -q`：3 个测试通过。
- `python scripts\evaluate_brain_workflow.py`：18 次 config-query run；`keyword_baseline=6/6`，`default_hybrid=4/6`，`vector_only=2/6`。
- `python scripts\evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts\evaluate_vector_search.py`：vector 11/15 通过。
- `python scripts\evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_agent.py`：agent 5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_sources.py`：`total_sources=125`，`merged_duplicates=14`。
- `python -m pytest -q`：189 个测试通过。

遗留问题：

- 当前 `filter_history` 和 `rewrite_query` 是结构化 no-op，后续阶段可接入真实多轮历史压缩和 query rewrite。
- 当前 `optional_rerank` 是可解释截断，不是真实 reranker；后续可以接入 cross-encoder 或 LLM rerank。
- 当前 deterministic embedding 仍不代表真实语义模型效果；阶段 9 如果接真实 embedding，需要复用现有评测集重新对比。
- `CitationAnswerService` 对外不暴露 workflow steps；如前端需要展示 Brain 过程，应另行设计响应字段或内部调试接口。

下一阶段任务：

- 优先建议阶段 9：真实模型接入与模型评测。
- 可选方向：Agent 权限审计与写入工具安全设计。
- 可选方向：部署工程化、日志观测和运行说明完善。
- 可选方向：扩大用户问题评测集，覆盖更多工程案例和中文问题。

面试表达：

```text
阶段 8 我把原先分散在 CitationAnswerService 和 Agent 工具里的 RAG 问答编排抽成了 Brain 中控层，而不是直接上复杂 LangGraph。

BrainService 接收 RetrievalConfig 和 WorkflowConfig，按 filter_history、rewrite_query、retrieve、optional_rerank、generate_answer 五步执行。前两步第一版是 no-op，但保留结构化 step 记录；retrieve 复用 keyword/vector/hybrid；generate_answer 继续复用 prompt builder、模型 provider、citation 提取和 qa_logs。

这样做的价值是：/chat 和 Agent answer_with_citations 共享同一条回答路径，后续接真实模型、query rewrite 或 rerank 时只需要改 Brain workflow，不用维护两套逻辑。验证上，我新增了 Brain 配置化评测脚本，同一批 chat 问题可以比较 default_hybrid、keyword_baseline 和 vector_only，最终全量测试 189 个通过，说明这是一个可配置、可复用、可评测的 RAG 中控层，而不是只靠演示跑通的问答接口。
```

## 2026-06-06 阶段 7 完成记录：Agent 化

当前分支：`codex/phase-7-agent-tools`

当前阶段：阶段 7 已完成。下一步建议由用户确认真实模型接入、权限审计、部署工程化或更细粒度用户评测方向。

阶段最终功能提交：由 `phase-7-complete` tag 指向的提交标识。

阶段 tag：`phase-7-complete`。

已完成：

- 使用 Planning with Files 维护阶段 7 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 6 已完成，且 `phase-6-complete` tag 指向 `fa11702150d79e036159f427f567051e92bfe8c2`，未移动已有阶段 tag。
- 新增 `docs/agent_design.md`，说明 Agent 工具边界、调用流程、权限约束、失败处理和评测方式。
- 新增 `app/services/agent/tools.py`，实现只读工具：`search_knowledge`、`hybrid_search_knowledge`、`answer_with_citations`、`list_sources`、`get_source_detail`。
- 新增 `app/services/agent/service.py`，实现规则式意图路由、最大工具调用步数限制、拒答和可审计摘要。
- 新增 `app/schemas/agent.py` 和 `app/api/agent.py`，实现 `POST /agent/query`。
- 在 `app/main.py` 注册 Agent API，保持 search、vector、hybrid、chat 和 sources 既有 API 不变。
- 新增 `data/evaluation/agent_queries.csv`、`scripts/evaluate_agent.py` 和 `data/evaluation/agent_results.csv`。
- 前端工作台新增 Agent 面板，展示回答、引用标签和工具调用记录。
- 开发完成后再统一补写 Obsidian Phase 汇报，符合本阶段用户要求。

阶段 7 设计结论：

- 第一版 Agent 采用只读工具优先，不自动执行 source reindex 等写入型动作。
- Agent 工具必须复用现有 service 和 repository，不绕过 sources、documents/chunks、hybrid search、chat citation 和日志链路。
- 第一版编排采用保守规则式意图路由，避免在 RAG 链路稳定前引入复杂 LangGraph workflow。
- `tool_calls` 和 `reasoning_summary` 是审计字段，帮助用户看见 Agent 调用了什么工具、为什么调用、是否成功。
- Agent 评测必须检查工具选择、来源命中、引用有效性和拒答，而不只是 HTTP 200。

验证结果：

- `python -m pytest tests\test_agent_design.py -q`：2 个测试通过。
- `python -m pytest tests\test_agent_tools.py -q`：6 个测试通过。
- `python -m pytest tests\test_agent_service.py -q`：6 个测试通过。
- `python -m pytest tests\test_agent_api.py tests\test_search_api.py tests\test_chat_api.py tests\test_sources_api.py -q`：16 个测试通过。
- `python -m pytest tests\test_evaluate_agent.py -q`：3 个测试通过。
- `python scripts\evaluate_agent.py`：5/5 通过，`refused=1`，`tool_failures=0`，`citation_failures=0`。
- `python scripts\evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts\evaluate_vector_search.py`：vector 11/15 通过。
- `python scripts\evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts\evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts\evaluate_sources.py`：`total_sources=125`，`merged_duplicates=14`。
- `python -m pytest tests\test_frontend_app.py -q`：3 个测试通过。
- 浏览器 smoke check：`http://127.0.0.1:8002/` 页面可提交 Agent 问题并展示 `hybrid_search_knowledge` 工具调用记录。
- `python -m pytest -q`：163 个测试通过。

遗留问题：

- 当前 Agent 意图路由是规则式，适合阶段 7 的可控可测目标；后续若引入真实 LLM 规划，需要保留权限、步数和评测约束。
- 当前 Agent 工具只读优先；写入型工具如 reindex 需要显式字段、人工确认或更严格测试后再接入。
- 当前 Agent 评测集规模较小，后续可扩展更多任务类型和用户日志回放。
- 当前仍使用 deterministic provider 作为本地稳定测试实现，真实模型效果需要后续专项评测。

下一阶段任务：

- 用户确认后，可进入真实模型接入与模型评测。
- 或进入 Agent 权限审计与写入工具安全设计。
- 或进入部署工程化、日志观测和使用说明完善。

面试表达：

```text
阶段 7 我把阶段 6 已经稳定的 RAG 能力包装成受控 Agent 工具调用链路，而不是直接上复杂 workflow。

我先用 docs/agent_design.md 固定工具边界和权限约束，然后新增 AgentToolbox，把关键词检索、混合检索、引用式问答和来源查询封装为只读工具。AgentService 做保守规则式意图路由：搜索类走 hybrid_search_knowledge，问答类走 answer_with_citations，来源类走 sources 工具。POST /agent/query 返回 answer、tool_calls、sources、citations、refused 和 reasoning_summary，前端也能展示工具调用记录。

这样设计的核心是可控和可审计：Agent 不能绕过 source registry、documents/chunks、hybrid search、引用和拒答机制。验证上我新增 Agent 评测脚本，结果 5/5 通过，同时复跑 keyword 15/15、vector 11/15、hybrid 15/15、chat 6/6 和全量 163 个测试。这个阶段证明项目不是一个随意调用工具的 demo，而是一个可回归、只读优先、来源可追踪的 RAG Agent。
```

## 2026-06-05 阶段 6 完成记录：检索优化与评测

当前分支：`codex/phase-6-evaluation`

当前阶段：阶段 6 已完成。下一步准备进入阶段 7：Agent 化。

阶段最终功能提交：由 `phase-6-complete` tag 指向的提交标识。

阶段 tag：`phase-6-complete`。

已完成：

- 使用 Planning with Files 维护阶段 6 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 5 已完成并合并，且 `phase-5-complete` tag 指向 `8c885e6cc714cc985933438697a7eb2523b26722`，未移动已有阶段 tag。
- 新增 `docs/evaluation_plan.md`，定义 Recall@K、Citation Accuracy、Faithfulness、Answer Coverage、Refusal Quality。
- 复跑 keyword、vector、chat baseline。
- 新增 `scripts/analyze_retrieval_errors.py` 和 `data/evaluation/retrieval_error_cases.csv`，记录失败问题、失败原因、期望依据、改进建议和优化后状态。
- 新增 `HybridSearchService`，合并关键词和向量召回，按 chunk 去重，对分数归一化并重排。
- 新增 `POST /search/hybrid`，保留 `POST /search` 和 `POST /search/vector` 既有行为。
- 扩展 `POST /chat` 的显式 `retrieval_mode="hybrid"`，但不改变 `auto` 的既有行为。
- 新增 `scripts/evaluate_hybrid_search.py` 和 `data/evaluation/hybrid_results.csv`，对比 keyword、vector、hybrid 三条链路。
- 前端工作台新增 hybrid 检索模式选择，保持最小改动。
- 开发完成后再统一补写 Obsidian Phase 汇报，符合本阶段用户要求。

阶段 6 设计结论：

- 先建立评测计划和 baseline，再做优化，避免凭感觉调参。
- 保留 keyword 和 vector baseline，hybrid 作为独立入口，便于优化前后对比。
- deterministic embedding 仍适合本地稳定测试；真实语义效果后续可接真实 embedding provider 继续评测。
- 混合检索优先使用保守、可解释的加权重排，不引入复杂 Agent workflow。
- 前端只暴露 hybrid 选项，不做界面重构。

验证结果：

- `python scripts/evaluate_keyword_search.py`：keyword 15/15 通过。
- `python scripts/evaluate_vector_search.py`：vector 11/15 通过，4 个 `keyword_only_pass`。
- `python scripts/evaluate_chat.py`：chat 6/6 通过，`refused=1`，`citation_failures=0`。
- `python scripts/evaluate_hybrid_search.py`：hybrid 15/15 通过，`rescued_vector=4`，`regressed_keyword=0`。
- `python scripts/analyze_retrieval_errors.py`：4 个 vector 失败均为 `fixed_by_hybrid`。
- `python -m pytest tests\test_frontend_app.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_search_api.py -q`：14 个测试通过。
- 浏览器 smoke check：`http://127.0.0.1:8001/` 页面可见 hybrid 搜索和 hybrid 聊天检索模式。
- `python -m pytest -q`：141 个测试通过。

遗留问题：

- 当前 hybrid 权重是保守静态规则，尚未做真实用户日志驱动调参。
- 当前 deterministic embedding 不代表真实语义模型效果；后续接真实 embedding provider 后应继续复用同一评测集。
- Chat `auto` 模式暂未默认切换到 hybrid，以避免改变既有 baseline 含义；后续可在阶段 7 或真实模型评测后再决定。
- 阶段 6 不做 Agent 工具调用，Agent 化留到阶段 7。

下一阶段任务：

- 阶段 7 进入 Agent 化。
- 将稳定的 search、hybrid search、chat、sources/reindex 能力包装为受控工具。
- 设计工具调用权限、最大步数、日志和失败回退。
- 优先做只读工具，例如知识库搜索、资料总结、来源对比、术语抽取。

面试表达：

```text
阶段 6 我重点解决 RAG 质量怎么证明的问题。

我先写评测计划，把 Recall@K、Citation Accuracy、Faithfulness、Answer Coverage 和 Refusal Quality 映射到当前脚本和 CSV 结果。然后复跑 baseline：关键词检索 15/15，向量检索 11/15，chat 6/6，并把 4 个向量失败案例沉淀成错误案例表。

优化时我没有直接上复杂 Agent 或外部模型，而是实现可解释的 hybrid search。它同时召回关键词和向量结果，按 chunk 去重，对两路分数归一化，再通过权重和双路命中奖励重排。最终 hybrid search 达到 15/15，救回 4 个 vector-only 失败，且没有 keyword baseline 退化。这个阶段体现的是工程评测闭环：有 baseline、有错误分析、有优化策略、有指标对比、有回归测试。
```

## 2026-06-05 阶段 5 完成记录：前端界面

当前分支：`codex/phase-5-frontend`

当前阶段：阶段 5 已完成。下一步准备进入阶段 6：检索优化与评测。

阶段最终功能提交：`8c885e6cc714cc985933438697a7eb2523b26722`

阶段 tag：`phase-5-complete`，已指向阶段最终功能提交。

已完成：

- 使用 Planning with Files 维护阶段 5 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 4 已完成，且 `phase-4-complete` tag 指向 `b044459b9b8c2153e9225daa55af5d82cdcdb282`，未移动已有阶段 tag。
- 新增 `app/api/frontend.py`，提供 `GET /` 前端入口和 `/favicon.ico` 空响应。
- 在 `app/main.py` 中注册 frontend router，并挂载 `/static` 静态资源。
- 新增 `app/frontend/index.html`、`app/frontend/static/styles.css`、`app/frontend/static/app.js`。
- 前端工作台展示 sources、documents、状态、可信度、全文权限、年份、分类、URL/DOI 和 chunk 数量。
- 支持来源关键词、状态和全文权限筛选。
- 支持查看 document chunks。
- 支持关键词检索和向量检索。
- 支持调用 `POST /chat` 提问，展示 answer、citations、sources、refused、retrieval_mode 和模型信息。
- 支持引用来源侧栏，展示 document title、chunk、score、source_path 和片段内容。
- 支持 source sync 操作入口和单条 source reindex 操作入口。
- 新增 `tests/test_frontend_app.py`，验证首页、静态资源、favicon 和关键前端入口。

阶段 5 设计结论：

- 第一版前端采用 FastAPI 静态文件 + 原生 HTML/CSS/JS，不引入 Node/React 构建链。
- 前端是薄展示层，只调用现有 API，不重写来源治理、检索或问答业务逻辑。
- 首页直接是 RAG 工作台，不做营销 landing page。
- sources 和 documents 并列展示，帮助用户理解“来源治理”和“已入库内容”不是同一层。
- reindex 操作会提示必要时刷新向量索引，避免用户误以为 reindex 自动提升语义检索质量。

验证结果：

- `python -m pytest tests\test_frontend_app.py -q`：3 个测试通过。
- `python -m pytest tests\test_frontend_app.py tests\test_sources_api.py tests\test_documents_api.py -q`：9 个测试通过。
- `python -m pytest tests\test_frontend_app.py tests\test_chat_api.py tests\test_answer_service.py -q`：14 个测试通过。
- `python -m pytest tests\test_frontend_app.py tests\test_search_api.py tests\test_vector_search_api.py tests\test_documents_api.py tests\test_sources_api.py -q`：13 个测试通过。
- 浏览器验证桌面页面：sources=125、documents=136、chunks=997。
- 浏览器验证来源筛选：`temperature` -> `7 / 125`。
- 浏览器验证 chunk 查看：document 1 显示 1 个 chunk。
- 浏览器验证关键词检索：`filling capacity` 返回 5 条结果。
- 浏览器验证聊天：问题 `What affects filling capacity in rock-filled concrete?` 返回回答和 5 条引用。
- 浏览器验证 reindex 错误处理：不存在 source 返回可理解错误。
- 浏览器验证移动视口：390x844 下无横向溢出。
- `python -m pytest -q`：126 个测试通过。

遗留问题：

- 阶段 5 使用原生前端，适合当前最小工作台；如果后续交互复杂度提高，可迁移到 React/Next.js。
- 浏览器验证没有执行真实 source reindex 成功路径，避免验证时改动资料库；已验证入口和错误处理。
- 当前没有上传界面；阶段 5 优先完成资料查看、来源管理、检索和问答。
- 当前没有后台任务队列，source sync/reindex 仍是同步请求。

下一阶段任务：

- 阶段 6 进入检索优化与评测。
- 建议建立 `docs/evaluation_plan.md`。
- 继续复用关键词、向量、chat 评测集，补充错误案例分析。
- 优先考虑混合检索、rerank、真实 embedding 或 query expansion。

面试表达：

```text
阶段 5 我补齐了 RAG 系统的前端工作台。

我没有只做聊天框，而是把 sources、documents、chunks、search 和 chat 都串到一个界面里。用户可以先看资料来源是否可信、是否允许保存全文、是否已经入库，再查看资料片段、执行检索，最后通过聊天界面看到回答和引用来源侧栏。

技术上我采用 FastAPI 静态文件加原生 HTML/CSS/JS，避免在当前 Python 项目里过早引入复杂构建链。前端只负责展示、筛选和调用 API，来源治理、检索和问答仍放在后端 service。阶段 5 通过了浏览器验证和 126 个自动化测试，为后续检索优化和 Agent 工具调用提供了可操作入口。
```

## 2026-06-05 阶段 4 完成记录：数据采集与来源管理

当前分支：`codex/phase-4-source-management`

当前阶段：阶段 4 已完成。下一步准备进入阶段 5：前端界面。

阶段最终提交：`b044459b9b8c2153e9225daa55af5d82cdcdb282`

阶段 tag：`phase-4-complete`，已指向阶段最终提交并推送到 GitHub。

已完成：

- 使用 Planning with Files 维护阶段 4 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 确认阶段 3 已完成，且 `phase-3-complete` tag 指向 `7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`，未移动已有阶段 tag。
- 新增 `Source` SQLAlchemy 模型，对应 `sources` 表。
- `sources` 表保存来源标识、题名、作者、年份、分类、发现渠道、DOI、URL、PDF URL、摘要、关键词、语言、引用数、来源类型、可信度、访问权限、全文保存权限、状态、本地路径、备注和可选 `document_id`。
- 新增 `normalized_doi`、`normalized_url`、`normalized_title`，支持 DOI、URL、标题三层去重。
- 新增 `SourceCreate` 和 `SourceRepository`，支持来源保存、更新、查询、列表、计数和重复键查询。
- 新增 `SourceRegistryService`，负责来源登记、归一化、去重、重复来源合并、可信度评级、全文权限判断和状态判断。
- 新增来源同步能力，支持读取 `data/source_candidates.csv`、`data/fulltext_manifest.csv`、`data/metadata/rfc_papers_metadata.csv` 和 `data/imports/metadata_corpus/*.md`。
- 新增 `scripts/sync_sources.py`，可幂等同步现有 CSV / manifest / metadata corpus 到 `sources` 表。
- 新增 source reindex 入口：已有本地文件的来源可重新导入原文；metadata-only 来源可重新生成题录卡片后导入 `documents/chunks`。
- 新增 `app/schemas/source.py` 和 `app/api/sources.py`。
- 新增 API：`GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`。
- 新增 `scripts/evaluate_sources.py`，输出来源总数、已关联 document 数、重复合并线索、权限分布、状态分布和可信度分布。
- 新增测试：`tests/test_source_repository.py`、`tests/test_source_registry_service.py`、`tests/test_sync_sources.py`、`tests/test_sources_api.py`、`tests/test_evaluate_sources.py`。

阶段 4 设计结论：

- `sources` 表不替代 `documents/chunks`。`sources` 管来源治理，`documents/chunks` 管已导入并可检索的内容。
- DOI 是最强去重键，URL 次之，标题归一化兜底。
- 可信度 `trust_level` 和全文保存权限 `fulltext_permission` 必须分开。一个来源可以高可信但只能保存题录，也可以开放获取但仍需记录许可边界。
- `status` 先使用固定字符串表达最小生命周期：`candidate`、`collected`、`imported`、`duplicate`、`rejected`。
- 阶段 4 不做复杂爬虫、不做 Agent 工具调用、不做前端。先把来源登记、去重、权限、状态、导入和 reindex 链路稳定下来。

验证结果：

- `python -m pytest tests\test_source_repository.py tests\test_source_registry_service.py tests\test_sync_sources.py tests\test_sources_api.py -q`：15 个测试通过。
- `python -m pytest tests\test_evaluate_sources.py -q`：2 个测试通过。
- `python scripts\sync_sources.py`：`total=283`、`created=125`、`updated=132`、`duplicates=26`。
- `python scripts\evaluate_sources.py --out data\evaluation\source_registry_metrics.csv`：`total_sources=125`、`linked_documents=0`、`merged_duplicates=14`。
- `python -m pytest -q`：123 个测试通过。
- `python scripts\evaluate_keyword_search.py`：15/15 通过。
- `python scripts\evaluate_vector_search.py --skip-index-build`：11/15 通过。
- `python scripts\evaluate_chat.py`：6/6 通过，`refused=1`，`citation_failures=0`。

遗留问题：

- 真实来源评测中 `linked_documents=0`，说明 source registry 已登记来源，但尚未对所有来源批量执行 reindex。阶段 4 已提供入口，后续可由前端或运营脚本触发。
- 向量检索仍保持阶段 3 的 11/15 deterministic embedding 基线。本阶段没有做召回质量优化。
- SQLite 阶段没有引入数据库迁移工具，后续迁移 PostgreSQL 或多人协作时应补 Alembic。

下一阶段任务：

- 阶段 5 进入前端界面。
- 建议先做资料管理界面，展示 `sources`、`documents`、`chunks` 的关系。
- 再做聊天界面、引用来源侧栏、reindex 按钮和来源筛选。
- 暂时继续避免复杂 Agent workflow，先让非技术用户能看懂和操作 RAG 链路。

面试表达：

```text
阶段 4 我补齐了 RAG 项目的来源治理层。

阶段 1 到阶段 3 已经能导入资料、检索 chunks、生成带引用的回答，但资料来源仍散落在 CSV、PDF manifest、题录卡片和 documents 表里。阶段 4 我新增 sources 表作为 source registry，把来源候选、题录、PDF 清单和 metadata cards 统一登记，并用 SourceRegistryService 做 DOI、URL、标题三层去重。

我把可信度 trust_level、全文保存权限 fulltext_permission 和来源状态 status 分成独立字段，避免把“来源可靠”和“能否保存全文”混为一谈。来源可以先处于 candidate 或 collected 状态，等需要进入问答库时再通过 reindex 导入 documents/chunks。

同时我提供了 sync_sources.py、sources API 和 evaluate_sources.py。这样阶段 4 不只是加了一张表，而是形成了可同步、可查询、可重新索引、可评测的来源治理链路，为阶段 5 前端和后续 Agent 工具调用打基础。
```

## 2026-06-05 阶段 3 完成记录：引用式问答

当前分支：`codex/phase-3-cited-chat`

当前阶段：阶段 3 已完成。下一步准备进入阶段 4：数据采集与来源管理。

已完成：

- 使用 `planning-with-files` 维护阶段 3 规划文件：`task_plan.md`、`findings.md`、`progress.md`。
- 新增 `docs/stage3_learning_notes.md`，沉淀阶段 3 新词解释、设计原因、测试结果和面试表达。
- 新增 `app/services/generation/chat_model.py`，定义 `ChatModelProvider`、`ChatMessage`、`ChatModelResult`，实现 deterministic provider 和 OpenAI-compatible provider。
- 新增 `app/services/generation/prompt_builder.py`，把检索结果组织成带 `[1]`、`[2]` 编号的 RAG 上下文。
- 新增 `app/services/generation/answer_service.py`，实现 `CitationAnswerService`，支持检索、prompt 构造、模型调用、引用提取、拒答和日志写入。
- 新增 `app/schemas/chat.py` 和 `app/api/chat.py`，实现 `POST /chat`。
- 新增 `qa_logs` 问答日志表、`QuestionAnswerLog` 模型和 `QuestionAnswerLogRepository`。
- 新增 `scripts/evaluate_chat.py`、`data/evaluation/chat_queries.csv` 和 `data/evaluation/chat_results.csv`。
- 新增测试：`tests/test_chat_model_provider.py`、`tests/test_prompt_builder.py`、`tests/test_answer_service.py`、`tests/test_chat_api.py`、`tests/test_chat_logging.py`、`tests/test_evaluate_chat.py`。

阶段 3 设计结论：

- 本阶段参考 Quivr 的 `LLMEndpoint`、RAG prompt、source index 和 response metadata 思路，但不引入 LangGraph。
- `ChatModelProvider` 对齐模型调用抽象，避免业务服务绑定具体国产模型或 OpenAI-compatible API。
- prompt builder 负责给 sources 编号，AnswerService 负责过滤 citations，不能完全相信模型自己输出的来源编号。
- 拒答机制放在 service 层，不只靠 prompt。
- `/chat` 是薄 API，RAG 业务逻辑集中在 `CitationAnswerService`。
- `qa_logs` 是阶段 3 最小可观测性，支持后续排查检索、引用、拒答和模型配置问题。
- Chat 评测默认使用 deterministic chat provider，保证没有真实模型 key 也能稳定回归。

验证结果：

- `python scripts\evaluate_chat.py`：6/6 通过。
- `python scripts\evaluate_keyword_search.py`：15/15 通过。
- `python scripts\evaluate_vector_search.py --skip-index-build`：11/15 通过。
- `python -m pytest -q`：106 个测试通过。

已处理问题：

- `truncate_text()` 初版没有把 `... [truncated]` 后缀长度纳入计算，导致截断后仍超过 `max_chars`；已修复。
- deterministic provider 初版回显完整 RAG prompt，导致上下文里的 `[2]` 被误识别为答案引用；已新增 `extract_question()`，只提取问题正文。
- 首次真实 chat 评测为 4/6；质量控制问题期望词过窄，无依据英文问题被常见词误召回。已调整评测集，最终 6/6 通过。

遗留问题：

- 当前 deterministic chat provider 只用于稳定开发和评测，不代表真实国产大模型回答质量。
- 当前向量检索仍为 11/15，真实语义检索效果需要后续接入真实 embedding、混合检索或 rerank。
- 当前 `qa_logs` 使用 Text 存 JSON 字符串保存 id 列表，后续迁移 PostgreSQL 时可升级为 JSON 字段。
- 当前没有多轮聊天历史，阶段 3 只做单轮引用式问答。
- 当前没有 Agent 工具调用，符合阶段 3 目标；Agent 化留到后续阶段。

面试表达：

```text
阶段 3 我完成了引用式问答的最小稳定链路。

我先抽象 ChatModelProvider，把聊天模型供应商和业务逻辑解耦；再用 prompt_builder 把检索到的 chunks 组织成带来源编号的上下文；CitationAnswerService 负责检索、prompt 构造、模型调用、引用提取和拒答判断；最后通过 POST /chat 返回 answer、citations、sources、refused、retrieval_mode 和 model 信息。

为了保证可追溯，我让 citations 只能引用本次 sources 中存在的编号，并新增 qa_logs 记录问题、答案、召回 chunk、引用、模型和拒答状态。为了避免只靠演示判断效果，我新增了 chat 评测集和 evaluate_chat.py，当前 chat 评测 6/6 通过，全量测试 106 个通过。

这个阶段没有引入复杂 Agent workflow，而是先保证 RAG 问答链路稳定、可测试、可引用、可拒答。
```

## 2026-06-04

当时阶段：阶段 1，本地资料导入与关键词检索已完成，并已合并到 `main`。下一步准备进入阶段 2：Embedding 与向量检索。

已完成：

- 明确项目主题：面向水利工程堆石混凝土技术的 RAG 问答 Agent。
- 编写项目指南 `AGENT.MD`。
- 创建初始项目目录。
- 准备连接 GitHub 仓库。
- 创建阶段 0 开发分支 `codex/phase-0-health-api`。
- 建立 FastAPI 应用入口 `app/main.py`。
- 实现健康检查接口 `GET /health`。
- 建立基础配置读取 `app/core/config.py`。
- 增加健康检查响应模型 `app/schemas/health.py`。
- 增加最小接口测试 `tests/test_health.py`。
- 增加项目依赖与测试配置 `pyproject.toml`。
- 在 `AGENT.MD` 中补充 Obsidian 知识库维护规则。
- 创建 Obsidian 知识库 `obsidian-vault/`。
- 为阶段 0 沉淀知识点笔记，并用双链连接阶段页与分类页。
- 更新 `AGENT.MD` 的协作与教学规则，要求新名词首次出现时结合本项目解释，并按“是什么 -> 在本项目哪里出现 -> 有什么作用 -> 面试怎么说”的顺序沉淀。
- 在 `AGENT.MD` 中补充本地 Quivr 项目作为 RAG 工程拆分参考，明确本项目学习其模块边界、数据流、配置方式和测试思路，但不直接复制代码。
- 增加 Obsidian 知识点 `obsidian-vault/知识点/新词解释机制.md`，并链接到阶段 0 与项目方法论分类。
- 重新阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、主要代码文件和测试文件，确认当前仍处于阶段 0 完成、准备进入阶段 1 的状态。

验证结果：

- `python -m pytest`：1 个测试通过。
- 本地服务验证：`GET http://127.0.0.1:8000/health` 返回 `{"status":"ok","service":"RFC-RAG-Agent","environment":"development"}`。
- 重新运行 `python -m pytest`：1 个测试通过。
- Git 当前分支为 `codex/phase-0-health-api`；更新前工作区干净，本次仅修改 `docs/progress.md`。
- 已确认本地参考项目 `G:\Codex\program\quivr` 存在，后续涉及架构、导入、检索、问答或评测设计时可按 `AGENT.MD` 规则参考其工程拆分思路。

阶段 0 知识点：

- FastAPI 用来声明 API 应用和路由。
- Pydantic schema 用来约束接口返回结构，避免返回格式随意变化。
- 配置读取集中放在 `app/core/config.py`，避免把环境变量散落在业务代码里。
- 测试使用 `TestClient` 模拟 HTTP 请求，能在不启动真实端口的情况下验证接口行为。
- 健康检查接口是服务可观测性的起点，后续可扩展为数据库、向量库和模型服务状态检查。

Obsidian 知识库已记录：

- `obsidian-vault/阶段/阶段 0 - FastAPI 工程底座.md`
- `obsidian-vault/知识点/FastAPI 应用入口与工厂函数.md`
- `obsidian-vault/知识点/API 路由分层.md`
- `obsidian-vault/知识点/健康检查接口.md`
- `obsidian-vault/知识点/Pydantic 响应模型.md`
- `obsidian-vault/知识点/Pydantic Settings 配置读取.md`
- `obsidian-vault/知识点/pytest 与 TestClient.md`
- `obsidian-vault/知识点/pyproject.toml 项目依赖管理.md`
- `obsidian-vault/知识点/uvicorn 与 ASGI 服务.md`
- `obsidian-vault/知识点/阶段分支开发.md`
- `obsidian-vault/知识点/Obsidian 双链知识库.md`
- `obsidian-vault/知识点/新词解释机制.md`

当前状态判断：

- 阶段 0 的 FastAPI 工程底座已经完成并通过测试。
- 最新项目规则强调“边做边讲清楚”，后续新增 REST、ORM、chunk、embedding、rerank 等概念时，需要及时解释并判断是否沉淀到 Obsidian。
- 阶段 1 应优先打通本地资料链路：Markdown/TXT 导入、文本清洗、chunk 切分、SQLite 保存和关键词检索。
- 阶段 1 设计时可以参考 Quivr 的 storage、processor、splitter、配置对象和测试组织方式，但本项目要保持简化，聚焦堆石混凝土资料与引用溯源。

遗留问题：

- `AGENT.MD` 的“当前推荐的第一步”曾停留在阶段 0 初始化任务；已在 2026-06-05 阶段 1 收尾时校准为阶段 2 启动建议。
- `AGENT.MD` 中检索策略部分曾有一处阶段表述需要校准；已在 2026-06-05 修正为阶段 1 先做关键词检索、阶段 2 再做向量检索。

依赖说明：

- `pyproject.toml` 中的 `httpx2>=2.3.0` 不是拼写错误；在当前安装到的 Starlette 新版分支里，它是 `TestClient` 优先使用的测试依赖，当前保留该写法。

面试表达：

```text
阶段 0 我没有直接接入大模型，而是先搭建 FastAPI 工程底座。
我把应用入口、路由、配置和响应模型分开，保证后续 documents、search、chat 等模块可以按同样结构扩展。
我实现了 /health 接口，并用自动化测试验证 HTTP 状态码和 JSON 返回结构。
这样可以证明服务可启动、接口可访问，也为后续 CI、部署和监控打基础。
```

下一步：

- 根据 `docs/architecture.md` 中的阶段 1 总体框架，先实现 SQLite 数据库层。
- 设计并落地 `documents` 与 `chunks` 两张表。
- 实现 Markdown/TXT 导入、文本清洗和 chunk 切分。
- 实现 `POST /documents/import`、`GET /documents` 和 `POST /search`。
- 完成关键词检索并补充最小自动化测试。

## 2026-06-04 阶段 1 启动记录

当前分支：`codex/phase-1-document-ingestion`

已完成：

- 正式进入阶段 1：本地资料导入与关键词检索。
- 按照 `AGENT.MD` 的要求重新确认阶段 1 目标：先打通本地资料链路，不接大模型，不接向量库。
- 参考本地 Quivr 项目的 `storage / processor / splitter` 模块边界，确定本项目阶段 1 只借鉴其工程拆分思路，不复制代码。
- 在 `docs/architecture.md` 中新增“阶段 1 总体框架”，明确数据流、目录规划、数据库表、API 草案、关键词检索策略和测试顺序。
- 增加 `SQLAlchemy` 依赖，用于 SQLite 数据库建模和读写。
- 新增 `app/db/session.py`，集中创建数据库连接、数据库会话和建表入口。
- 新增 `app/db/models.py`，定义 `documents` 和 `chunks` 两张表。
- 新增 `tests/test_db_models.py`，验证数据库表能创建，并能保存一篇资料及其 chunk。
- 新增 `app/services/ingestion/parser.py`，支持读取 Markdown/TXT，并从 Markdown 一级或多级标题中推断资料标题。
- 新增 `app/services/ingestion/cleaner.py`，清理 BOM、空字符、换行差异、多余空白和连续空行。
- 新增 `app/services/ingestion/splitter.py`，把长文本切成带 `chunk_index`、`char_count`、`heading_path`、`start_char`、`end_char` 的 chunk。
- 新增 `tests/test_ingestion_parser.py`、`tests/test_ingestion_cleaner.py`、`tests/test_ingestion_splitter.py`，分别验证解析、清洗和切分逻辑。
- 新增 `app/db/repositories.py`，封装 `documents` 和 `chunks` 的保存、查询和 chunk 计数逻辑。
- 新增 `app/services/ingestion/loader.py`，负责计算文件 hash，并把原始文件保存到 raw 目录。
- 新增 `app/services/ingestion/service.py`，把 parser、cleaner、splitter、loader 和 repository 串成完整导入链路。
- 新增 `tests/test_repositories.py`，验证 repository 可以保存和查询资料。
- 新增 `tests/test_ingestion_service.py`，验证 Markdown 文件能完成导入、切分、保存，重复文件不会重复入库，空文件会被拒绝。
- 新增 `python-multipart` 依赖，用于 FastAPI 接收上传文件。
- 新增配置项 `RAW_DATA_DIR`，用于控制原始资料保存目录。
- 新增 `app/schemas/document.py`，定义文档导入和文档列表接口的响应结构。
- 新增 `app/api/documents.py`，实现 `POST /documents/import` 和 `GET /documents`。
- 更新 `app/main.py`，注册 documents 路由，并在应用启动时自动创建数据库表。
- 新增 `tests/test_documents_api.py`，验证上传 Markdown 可完成导入，`GET /documents` 可返回文档列表，不支持的文件类型会返回 400。
- 在 `pyproject.toml` 中显式声明只打包 `app` 包，避免本地运行目录 `data/` 被 setuptools 误识别为顶层包。
- 新增 `app/services/retrieval/keyword_search.py`，实现阶段 1 的关键词检索服务。
- 新增 `app/schemas/search.py`，定义搜索请求和搜索结果响应结构。
- 新增 `app/api/search.py`，实现 `POST /search`。
- 更新 `app/main.py`，注册 search 路由。
- 新增 `tests/test_keyword_search.py`，验证关键词检索能返回命中的 chunk，并过滤无关 chunk。
- 新增 `tests/test_search_api.py`，验证完整 API 流程：上传 Markdown 后，可以通过 `POST /search` 搜到相关片段。
- 搜索结果已包含 `document_title`、`source_path`、`file_name`、`chunk_index`、`content` 和 `score`，满足阶段 1 对“来源、标题和片段”的基本要求。
- 新增 `GET /documents/{document_id}/chunks`，支持按资料编号查看该资料切出的全部 chunk。
- 新增 `tests/test_documents_api.py` 对 chunk 查看接口的正常返回和 404 场景测试。

阶段 1 设计结论：

- 本阶段只支持 Markdown/TXT。
- 原始文件保存到 `data/raw/`。
- 解析、清洗、切分逻辑放到 `app/services/ingestion/`。
- 数据库存储放到 `app/db/`，先落地 `documents` 和 `chunks`。
- 检索放到 `app/services/retrieval/keyword_search.py`，先做可解释的关键词检索。
- API 层新增 `documents.py` 和 `search.py`，保持与阶段 0 的路由分层一致。

下一步：

- 用 5 到 10 篇真实 Markdown/TXT 堆石混凝土资料做本地试导入。
- 手动验证关键词如“堆石混凝土”“自密实混凝土”“施工质量”能返回合理片段。
- 根据真实资料效果微调 chunk_size、chunk_overlap 和关键词评分规则。

验证结果：

- `python -m pytest`：21 个测试通过。

## 2026-06-04 阶段 1 真实资料试导入记录

已完成：

- 使用公开学术页面、高校页面、期刊页面和开放获取论文，整理 10 条堆石混凝土资料卡到 `data/imports/rfc_seed/`。
- 用户补充确认 CNKI 摘要页为《堆石混凝土及堆石混凝土大坝》的主来源入口，已更新 `rfc_seed_001` 资料卡和 `docs/data_sources.md`。
- 通过本地导入链路写入 SQLite，当前资料库包含 10 篇 documents 和 17 个 chunks。
- 搜索校准覆盖关键词：金峰、堆石混凝土、自密实混凝土、施工质量、填充密实性、水化热、低碳筑坝、rock-filled concrete。
- 校准结果显示：开篇论文、施工方法专利、填充能力研究、绝热温升研究和 2023 年综述能被相关关键词召回。

设计说明：

- 本批资料只保存题录、公开摘要转述、检索关键词和来源链接，不保存受版权限制全文。
- CNKI 的 `kcms2/article/abstract?v=...` 链接可能包含临时参数，因此同时保留 ResearchGate、期刊页面或高校页面作为辅助线索。
- 现阶段资料卡中的题名、作者和来源也会进入 chunk 正文，便于关键词检索；后续阶段可以把这些信息拆成 metadata 字段，提高正文检索的纯净度。

验证结果：

- 本地数据库检查：10 篇 documents，17 个 chunks。
- 《堆石混凝土及堆石混凝土大坝》的 `source_path` 已更新为用户提供的 CNKI 摘要页。

## 2026-06-04 阶段 1 chunk 检查接口记录

已完成：

- 在 `app/db/repositories.py` 中增加按 `document_id` 查询文档和 chunk 的方法。
- 在 `app/schemas/document.py` 中增加 chunk 查看接口的响应结构。
- 在 `app/api/documents.py` 中实现 `GET /documents/{document_id}/chunks`。
- 在 `tests/test_documents_api.py` 中增加接口测试，覆盖正常查看 chunk 和文档不存在返回 404。

设计说明：

- 该接口用于提升阶段 1 的可观测性，方便直接检查真实资料被切分后的内容是否合理。
- API 层仍通过 repository 读取数据库，保持 API、schema、database 的分层清晰。

验证结果：

- `python -m pytest tests\test_documents_api.py`：4 个测试通过。

## 2026-06-04 阶段 1 splitter 真实资料微调记录

已完成：

- 检查 10 条真实堆石混凝土资料卡生成的 chunk，发现旧 splitter 会把 `source_id`、URL、`copyright_note` 等资料卡元信息切进正文。
- 发现旧 overlap 可能让新 chunk 从 URL、英文单词或元信息字段中间开始，影响 chunk 可读性和检索结果展示。
- 发现旧 `heading_path` 按 chunk 结束位置附近的标题计算，容易显示成 chunk 内最后一个标题，而不是 chunk 开始处所属标题。
- 更新 `app/services/ingestion/splitter.py`：
  - 自动跳过 Markdown 资料卡开头的元信息块。
  - 新 chunk 起点优先贴近段落、换行或句号等自然边界。
  - `heading_path` 改为按 chunk 开始位置计算。
- 更新 `tests/test_ingestion_splitter.py`，新增元信息跳过和自然边界起点测试。
- 使用新 splitter 重新切分 `data/imports/rfc_seed/` 下的 10 条资料卡，并刷新本地 SQLite 中的 chunks。

设计说明：

- 当前导入的是摘要型资料卡，每条资料卡正文大多在 500 到 800 字之间，因此重切后每篇资料保留 1 个 chunk 更合理。
- 这次不是减少知识量，而是去掉检索噪声，避免把来源登记字段当作知识正文。
- 后续导入长论文、长报告或规范时，splitter 仍会按 `chunk_size` 和自然边界切成多个 chunk。

校准结果：

- 数据库当前为 10 篇 documents，10 个 chunks。
- 搜索“堆石混凝土”时，《堆石混凝土及堆石混凝土大坝》排在前列。
- 搜索“水化热”时，《堆石混凝土绝热温升性能初步研究》排在前列。
- 搜索“填充密实性”时，能召回自密实混凝土充填试验和流动模拟相关资料。

验证结果：

- `python -m pytest tests\test_ingestion_splitter.py -q`：6 个测试通过。
- `python -m pytest`：25 个测试通过。

## 2026-06-04 阶段 1 论文原文导入记录

已完成：

- 新增 `pypdf` 依赖，用于抽取 PDF 文字层。
- 更新 `app/services/ingestion/parser.py`，支持导入 `.pdf` 文件。
- PDF 解析会按页加入 `## Page N` 标记，方便后续检查 chunk 来源页。
- 更新 `tests/test_ingestion_parser.py`，新增 PDF 文字抽取测试。
- 更新 `tests/test_documents_api.py`，将不支持格式测试从 PDF 改为 DOCX。
- 更新 `app/services/ingestion/service.py`，支持传入 `source_type`，用于标记 `open_access_pdf`。
- 更新 `tests/test_ingestion_service.py`，验证自定义来源类型可以写入数据库。
- 新增 `data/fulltext_manifest.csv`，记录 PDF 原文的标题、作者、年份、分类、访问权限、许可备注、URL、PDF URL 和本地文件名。
- 新增 `docs/source_catalog.md`，建立来源分类目录和 CNKI / 机构访问优先下载清单。
- 更新 `.gitignore`，忽略 `data/fulltext/`，避免将论文全文提交到 GitHub。

本次已下载开放全文 PDF：

- `Research on Rock-Filled Concrete Dam`
- `Lattice Boltzmann-Discrete Element Modeling Simulation of SCC Flowing Process for Rock-Filled Concrete`
- `Experimental Research on the Properties of Rock-Filled Concrete`
- `Filling Capacity Evaluation of Self-Compacting Concrete in Rock-Filled Concrete`
- `A Brief Review of Rock-Filled Concrete Dams and Prospects for Next-Generation Concrete Dam Construction Technology`
- `A Mesoscale Comparative Analysis of the Elastic Modulus in Rock-Filled Concrete for Structural Applications`
- `A Comprehensive Literature Review on the Elastic Modulus of Rock-filled Concrete`
- `Seismic Behavior of Rock-Filled Concrete Dam Compared with Conventional Vibrating Concrete Dam Using Finite Element Method`
- `3D mesoscopic numerical investigation on the uniaxial compressive behavior of rock-filled concrete with different ITZ and aggregate properties`
- `Full-Scale micromechanical simulation of rock-filled concretes using Peridynamics`

导入结果：

- 当前数据库总计：20 篇 documents，800 个 chunks。
- 资料卡：10 篇 documents，10 个 chunks。
- 开放全文 PDF：10 篇 documents，790 个 chunks。

搜索校准：

- `rock-filled concrete dam review` 能召回 2023 年 Engineering 综述全文。
- `filling capacity` 能召回填充能力相关资料卡和 2020 年 Materials 全文。
- `elastic modulus` 能召回 2024 年 Buildings 和 ETASR 弹性模量论文。
- `seismic behavior` 能召回 2024 年 Infrastructures 地震响应论文。
- `Peridynamics` 能召回 2025 年 Acta Geotechnica 全文。
- `hydration heat` 目前仍需要补充中文温控全文，下一批优先下载《堆石混凝土绝热温升性能初步研究》。

设计说明：

- 开放全文 PDF 可进入本地全文库，但不提交到远程仓库。
- CNKI 机构访问论文只用于本地私有学习和检索，不公开再分发全文。
- 不使用网盘盗版、破解下载、绕过验证码或反爬限制的来源。
- 当前 PDF 解析只支持文字层，不支持扫描版 OCR。

验证结果：

- `python -m pytest tests\test_ingestion_parser.py tests\test_documents_api.py -q`：8 个测试通过。
- `python -m pytest`：27 个测试通过。

## 2026-06-04 阶段 1 CNKI 机构访问原文导入记录

已完成：

- 使用用户已登录的 Chrome / CNKI 页面下载《堆石混凝土及堆石混凝土大坝》PDF。
- 在 `C:\Users\admin\Downloads` 中发现 5 个重复下载文件，保留原下载不动，复制最新文件到 `data/fulltext/cnki_pending/`。
- 复制后的稳定文件名为 `rfc_cnki_2005_jin_an_study_on_rock_fill_concrete_dam.pdf`。
- 检查 PDF 有文字层：共 6 页，前 3 页可抽取 4231 个字符。
- 更新 `data/fulltext_manifest.csv`，新增 `rfc_cnki_001`，来源类型为 `institutional_access_pdf`。
- 更新 `docs/source_catalog.md`，在“已下载机构访问全文”中登记该论文。
- 导入 SQLite，新增 document_id `21`，切分出 11 个 chunks。

校准结果：

- 当前数据库：21 篇 documents，811 个 chunks。
- 搜索“堆石混凝土大坝”可召回 CNKI 原文第 1 页和第 5 页相关 chunk。
- 搜索“新坝型”可召回 CNKI 原文摘要相关 chunk。
- 搜索“自密实混凝土 填充 堆石体”可召回 CNKI 原文中关于 1500 mm 堆石体填充能力、流动距离和施工质量控制的 chunk。

设计说明：

- 该 PDF 来自机构账号授权访问，只用于本地私有检索，不提交到 GitHub，不公开再分发全文。
- Chrome 下载列表中的重复文件暂不删除，避免误删用户原始下载记录。
- 当前 PDF 抽取文本中存在少量 `` 等 PDF 编码符号，后续可在 cleaner 中增加针对 PDF 的符号清洗规则。

## 2026-06-04 阶段 1 语料库自动扩容管道记录

已完成：

- 新增 `app/services/source_collection.py`，封装来源候选的结构、分类、去重、文件名清洗和 PDF 校验逻辑。
- 新增 `scripts/collect_sources.py`，支持从 OpenAlex、Semantic Scholar、Crossref 批量发现堆石混凝土相关论文候选，并可下载开放 PDF。
- 新增 `scripts/import_fulltext.py`，支持从 manifest 和本地目录批量导入 PDF，重复文件会通过 content hash 识别为 duplicate。
- 新增 `scripts/import_zotero.py`，支持 Zotero 本地 API 可用时读取 Zotero 条目和 PDF 附件并导入。
- 新增 `tests/test_source_collection.py`，验证主题分类、DOI 去重和安全文件名生成。
- 新增 `docs/corpus_pipeline.md`，记录学术 API、Zotero、本地 PDF 的自动扩容方式。

验证结果：

- `scripts/import_fulltext.py --manifest data\fulltext_manifest.csv`：已导入 PDF 均识别为 duplicate，没有重复入库。
- `scripts/import_zotero.py --query "rock-filled concrete"`：当前 Zotero 本地 API 不可用，脚本给出可理解提示。
- `python -m pytest`：30 个测试通过。

当前限制：

- 本机直连 OpenAlex、Semantic Scholar、Crossref 时出现 `SSL: UNEXPECTED_EOF_WHILE_READING`，PowerShell 和 Python 都复现。
- 判断为当前网络或代理层中断 HTTPS 连接；API 管道已实现，但需要配置代理或换网络后才能批量拉取候选。
- Zotero 当前未发现本地配置文件，需要先启动 Zotero Desktop 并启用本地 API。

## 2026-06-04 阶段 1 三通道扩容运行记录

用户要求使用三条通道获取资料，并及时反馈问题。

已运行：

- 学术 API 通道：`scripts/collect_sources.py`
- 本地 PDF / manifest 通道：`scripts/import_fulltext.py`
- Zotero 附件通道：`scripts/import_zotero.py`

学术 API 通道结果：

- 查询词：`rock-filled concrete`、`rock-filled concrete dam`、`self-compacting concrete rock-filled concrete`。
- OpenAlex 和 Crossref 成功返回候选。
- Semantic Scholar 返回 `HTTP 429`，表示当前请求被限流，后续需要降低频率或配置 API key。
- `data/source_candidates.csv` 当前记录 40 条候选。
- 其中 4 条包含 PDF URL，但本轮自动下载均失败：
  - MDPI `/pdf` 链接返回 403；该类链接后续应转换为 `mdpi-res.com` 静态 PDF 地址。
  - Springer 部分链接返回 HTML，不是直接 PDF，可能是受限或书籍资源。
  - EasyChair 预印本链接返回 404。
- 候选清单中出现相邻但不完全相关主题，例如 `concrete-faced rock-fill dam`，后续应增加 RFC 相关性过滤。

本地 PDF / manifest 通道结果：

- 扫描 `data/fulltext_manifest.csv`、`data/source_candidates.csv`、`data/fulltext/open_access/`、`data/fulltext/cnki_pending/`、`data/fulltext/open_access_auto/`。
- 已存在 PDF 均识别为 `duplicate`，没有重复入库。
- 数据库保持 21 篇 documents，811 个 chunks。

Zotero 通道结果：

- Zotero 本地 API 当前不可用。
- `zotero.py status --json` 显示未发现 Zotero profile / prefs file，`api_running=false`。
- `scripts/import_zotero.py` 给出提示：需要先启动 Zotero Desktop 并启用本地 API。

下一步改进：

- 为 `collect_sources.py` 增加更严格的堆石混凝土相关性过滤，排除混凝土面板堆石坝等相邻主题。
- 为 Semantic Scholar 增加 API key 支持和退避重试。
- 为 MDPI 链接增加 `/pdf` 到 `mdpi-res.com` 静态 PDF 的转换规则。
- 启动 Zotero Desktop 后重跑 Zotero 通道。

## 2026-06-04 阶段 1 题录优先语料库扩容记录

用户调整方向：当前不再需要更多论文全文，优先从 Google Scholar、CNKI 等大型学术入口及开放学术 API 获取可直接获得的题名、作者、期刊、摘要、关键词、DOI 和链接等题录语料，追求数量更大。

设计判断：
- 不把 Google Scholar 页面硬爬作为主链路，因为 Google Scholar 没有官方公开批量 API，直接抓页面容易触发验证码，且摘要字段不稳定。
- 不把 CNKI 全文批量抓取作为主链路，因为机构账号授权和网站访问边界需要保留；当前优先支持 CNKI 导出的题录/摘要文件导入。
- 主链路改为 `metadata-first`：先用 OpenAlex、Crossref、Semantic Scholar 等来源扩大题录覆盖面，再把高价值记录或已授权全文逐步补入。

已完成：
- 扩展 `app/services/source_collection.py` 的 `SourceCandidate`，新增 `abstract`、`keywords`、`language`、`citation_count` 字段。
- 修正来源过滤中的中文关键词乱码，使 `堆石混凝土`、`自密实堆石混凝土`、`混凝土面板堆石坝` 等中文判断可用。
- 新增 OpenAlex 摘要还原、Crossref/Semantic Scholar 摘要去标签、语言推断、JSONL 输出和题录 Markdown 卡片生成能力。
- 更新 `scripts/collect_sources.py`，使学术 API 采集从“PDF 候选优先”升级为“题录元数据优先，PDF 可选下载”。
- 新增 `scripts/collect_metadata_corpus.py`，支持：
  - 从 OpenAlex、Semantic Scholar、Crossref 批量采集题录元数据。
  - 跳过某个 API，例如 `--skip-semantic-scholar`。
  - 合并 CNKI、Google Scholar 辅助工具、EndNote、Zotero 或 Publish or Perish 导出的 CSV/TSV/RIS/EndNote 文本文件。
  - 生成 `data/metadata/rfc_papers_metadata.csv`、`data/metadata/rfc_papers_metadata.jsonl` 和 `data/imports/metadata_corpus/*.md`。
  - 将题录卡片以 `metadata_record` 类型导入 SQLite。
- 增加题录导入去重保护：重新生成卡片时，若数据库已存在相同 `metadata_record` 的题名或来源路径，则跳过，避免重复刷屏。

本轮运行命令：

```powershell
.\.venv\Scripts\python.exe scripts\collect_metadata_corpus.py `
  --skip-semantic-scholar `
  --query "rock-filled concrete" `
  --query "rock filled concrete" `
  --query "rock-fill concrete dam" `
  --query "self-compacting rock-filled concrete" `
  --query "self-compacting concrete prepacked rock" `
  --query "堆石混凝土" `
  --query "自密实堆石混凝土" `
  --query "金峰 堆石混凝土" `
  --limit 100 `
  --max-records 300 `
  --import-to-db
```

运行结果：
- OpenAlex + Crossref 共返回 562 条原始候选。
- RFC 相关性过滤后保留 116 条题录。
- 69 条含公开摘要。
- 生成 116 个 Markdown 题录卡片。
- 当前 SQLite：136 篇 documents、997 个 chunks。
- 来源类型分布：`local_file=10`、`open_access_pdf=10`、`institutional_access_pdf=1`、`metadata_record=115`。
- `data/metadata/rfc_papers_metadata.csv` 来源分布：OpenAlex 52 条、OpenAlex+Crossref 44 条、Crossref 20 条。

检索校准：
- `filling capacity` 可以命中填充能力相关题录、资料卡和 PDF chunk。
- `temperature rock-filled concrete` 可以命中温度场、绝热温升、施工参数影响等题录和全文片段。
- `Quality Control Instrumentation` 可以命中 RFC 大坝质量控制相关题录章节。
- 中文 `施工质量` 和 `堆石混凝土` 可以命中 CNKI 原文、早期资料卡和相关题录。

暴露问题：
- Semantic Scholar 未配置 API key 时容易返回 `HTTP 429`，当前用 `--skip-semantic-scholar` 保证批量运行速度。
- Crossref 的 `select` 字段不支持 `language`，已去掉该字段并完成补跑。
- 有 1 个题名对应两个 DOI，文件名已改为包含 `source_id`，避免卡片文件覆盖；数据库检索层仍按题名跳过重复显示。
- 当前 `metadata_record` 作为 Markdown 卡片进入 `documents/chunks`，这是阶段 1 的最小实现；后续阶段 4 更适合新增独立 `sources` 或 `papers` 表。

验证结果：
- `python -m pytest tests\test_source_collection.py -q`：9 个测试通过。
- `python -m pytest`：36 个测试通过。

## 2026-06-04 阶段 1 关键词检索评测与微调记录

用户要求：
- 建立 `data/evaluation/keyword_queries.csv`，记录问题、关键词、期望命中文档和备注。
- 编写 `scripts/evaluate_keyword_search.py`，自动运行关键词检索并输出命中结果。
- 根据结果微调关键词检索，重点检查中文、英文、同义词、标题加分和 `metadata_record` 是否过度刷屏。

已完成：
- 新增 `data/evaluation/keyword_queries.csv`，包含 15 个阶段 1 代表性问题，覆盖：
  - 施工质量 / 质量控制
  - 填充能力
  - 温升 / 水化热 / 温控
  - 弹性模量
  - 抗震 / seismic
  - 综述 / next generation
  - 细观 / 数值模拟
  - 冷缝 / 剪切
  - Peridynamics
  - 施工信息管理
  - 密实度检测
  - 坝型设计
  - 再生骨料
- 新增 `scripts/evaluate_keyword_search.py`：
  - 读取评测 CSV。
  - 调用 `KeywordSearchService`。
  - 判断期望题名、期望内容词和期望来源类型是否命中。
  - 输出 `data/evaluation/keyword_results.csv`。
  - 汇总每条查询的 pass/fail、hit_rank、hit_title、hit_source_type、metadata_ratio。
- 初次评测结果：11/15 通过。
- 失败集中在：
  - `弹性模量` 没有稳定召回 `elastic modulus`。
  - `细观 / 数值 / 模拟` 没有稳定召回 `mesoscopic / simulation`。
  - `peridynamics` 被 `rock-filled concrete / concrete` 等泛词淹没。
  - `quality control instrumentation RFC dam` 没有稳定召回质量控制章节。
- 更新 `app/services/retrieval/keyword_search.py`：
  - 增加 `SearchTerm`，让每个查询词带权重和“是否具体词”的标记。
  - 增加中英文同义词扩展，例如：
    - `弹性模量` -> `elastic modulus`
    - `细观` -> `mesoscopic / mesoscale`
    - `施工质量` -> `quality control / construction quality / instrumentation`
    - `温升 / 水化热` -> `temperature / hydration heat / adiabatic temperature rise`
    - `抗震` -> `seismic / earthquake`
  - 降低 `concrete`、`dam`、`rock-filled`、`堆石混凝土` 等领域泛词在多词查询中的权重。
  - 对命中次数做上限裁剪，避免长 PDF 中泛词重复次数过多导致分数虚高。
  - 加入来源均衡：当存在全文或资料卡命中时，`metadata_record` 在 top_k 中最多优先占约 60%，避免题录卡片刷屏。
  - 检索结果新增 `source_type`，便于 API 和评测识别来源类型。
- 更新 `app/schemas/search.py` 和 `app/api/search.py`，让 `POST /search` 返回每条结果的 `source_type`。
- 更新 `tests/test_keyword_search.py`：
  - 验证中文 `弹性模量 堆石混凝土` 可以召回英文 `Elastic Modulus` 题录。
  - 验证 `peridynamics` 这类具体词不会被泛词重复次数淹没。

最终评测结果：
- `scripts/evaluate_keyword_search.py`：15/15 通过。
- `metadata_ratio` 最高控制在 0.50。
- `data/evaluation/keyword_results.csv` 已记录本轮评测结果。

验证结果：
- `python -m pytest tests\test_keyword_search.py tests\test_search_api.py -q`：6 个测试通过。
- `python -m pytest`：38 个测试通过。
- `python -m py_compile scripts\evaluate_keyword_search.py app\services\retrieval\keyword_search.py app\schemas\search.py app\api\search.py`：通过。

面试表达：

```text
阶段 1 不只是实现关键词检索，还建立了一个小型检索评测集。评测集把典型问题、查询词和期望命中文档写成 CSV，再由脚本自动运行检索并输出命中排名和来源类型。根据评测结果，我发现关键词检索容易被领域泛词影响，所以加入了中英文同义词扩展、具体词加权、泛词降权和 metadata_record 来源均衡。最终 15 个代表性问题全部通过，形成了后续向量检索的 baseline。
```

## 2026-06-05 阶段 1 合并与文档校准记录

已完成：

- 将 `codex/phase-1-document-ingestion` 合并到 `main`。
- 推送远程 `origin/main`。
- 校准 `README.md`，明确当前阶段为阶段 1 已完成，并列出 documents/chunks、导入链路、关键词检索、评测集和测试覆盖。
- 校准 `obsidian-vault/阶段索引.md`，将阶段 1 从“计划中”移动到“已完成”，并把阶段 2 标为下一阶段。
- 校准 `obsidian-vault/首页.md`，将当前重点从阶段 0 更新为阶段 1 已完成、阶段 2 下一阶段。
- 校准 `obsidian-vault/阶段/阶段 1 - 本地资料导入与关键词检索.md`，将状态从“待开发”改为“已完成”，并补充完成内容、验证结果、知识点链接和面试表达。
- 校准 `AGENT.MD` 末尾的“当前推荐的第一步”，不再指向阶段 0 初始化，而是指向阶段 2 的 Embedding 与向量检索。
- 校准 `AGENT.MD` 的“检索策略”，修正为阶段 1 关键词检索、阶段 2 embedding 向量检索、后续再做 rerank 和引用式问答。

验证结果：

- 合并前运行 `python -m pytest`：38 个测试通过。

当前文档权威性：

- `docs/progress.md` 是最权威的阶段进度记录。
- `README.md` 是新读者入口。
- `AGENT.MD` 是后续 agent 的工作规则。
- `obsidian-vault/阶段索引.md` 是复习和知识库导航。

下一步：

- 新开阶段 2 分支 `codex/phase-2-vector-search`。
- 设计 embedding 模型选择、向量索引方案、chunk embedding 保存结构和向量检索评测方式。

## 2026-06-05 阶段 2 完成记录：Embedding 与向量检索

当前分支：`codex/phase-2-vector-search`

当前阶段：阶段 2 已完成。下一步准备进入阶段 3：引用式问答。

已完成：

- 使用 `planning-with-files` 生成并维护阶段 2 规划文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
- 新增 `docs/stage2_learning_notes.md`，按步骤沉淀阶段 2 学习笔记和面试表达。
- 新增 `app/services/retrieval/embedding.py`：
  - 定义 `EmbeddingProvider` 抽象。
  - 实现 `DeterministicEmbeddingProvider`，用于无 API key 的本地开发和稳定测试。
  - 提供 `create_embedding_provider()`，为后续切换真实 embedding 模型预留入口。
- 新增 `chunk_embeddings` 表：
  - 记录 `chunk_id`、`provider`、`model_name`、`dimension`、`embedding_json`、`content_hash`。
  - 使用 `chunk_id + provider + model_name` 唯一约束避免重复索引。
  - 与 `chunks` 建立关联，删除 chunk 时可级联删除对应 embedding。
- 扩展 `ChunkEmbeddingRepository`：
  - 支持保存、更新、查询、列出和统计 chunk embeddings。
  - 支持 `serialize_embedding()` 和 `deserialize_embedding()`。
  - 支持批量索引时延迟提交，减少大量写入时的数据库提交次数。
- 新增 `VectorIndexService`：
  - 扫描 chunks。
  - 判断已有 embedding 是否过期。
  - 批量调用 embedding provider。
  - 写入或更新 `chunk_embeddings`。
  - 返回 total、indexed、updated、skipped 等构建统计。
- 新增 `scripts/build_vector_index.py`：
  - 支持从命令行构建向量索引。
  - 默认使用 `.env` 中的 `EMBEDDING_PROVIDER`，未配置时使用 deterministic provider。
- 新增 `VectorSearchService`：
  - 把用户问题转成 query embedding。
  - 读取同一 provider/model/dimension 的 chunk embedding。
  - 计算余弦相似度并按 score 排序。
  - 跳过内容 hash 不一致的 stale embedding。
- 扩展 `app/api/search.py`：
  - 保留阶段 1 的 `POST /search` 关键词检索。
  - 新增 `POST /search/vector` 向量检索入口。
- 扩展 `app/schemas/search.py`：
  - 新增 `VectorSearchRequest`。
  - 新增 `VectorSearchResponse`，返回 provider 和 model_name，便于排查当前使用的 embedding 实现。
- 新增 `scripts/evaluate_vector_search.py`：
  - 复用 `data/evaluation/keyword_queries.csv`。
  - 输出 `data/evaluation/vector_results.csv`。
  - 读取 `data/evaluation/keyword_results.csv`，对比关键词 baseline 和向量检索结果。
- 新增和更新自动化测试：
  - `tests/test_embedding_provider.py`
  - `tests/test_db_models.py`
  - `tests/test_repositories.py`
  - `tests/test_vector_index_service.py`
  - `tests/test_vector_search.py`
  - `tests/test_vector_search_api.py`
  - `tests/test_evaluate_vector_search.py`

阶段 2 设计结论：

- 本阶段没有直接接入 FAISS、Chroma 或云端 embedding 模型，而是先用 SQLite + deterministic embedding 跑通最小链路。
- `documents` 和 `chunks` 仍是主数据源，`chunk_embeddings` 是可重建索引数据。
- 向量检索与关键词检索保持并行：
  - `POST /search` 是阶段 1 keyword baseline。
  - `POST /search/vector` 是阶段 2 vector search。
- 评测必须复用同一批问题，避免不同检索方式比较口径不一致。
- 当前 deterministic embedding 只能证明链路和工程边界可运行，不能证明真实语义召回效果已经优于关键词检索。

评测结果：

- `scripts/evaluate_keyword_search.py`：关键词 baseline 15/15 通过。
- `scripts/evaluate_vector_search.py`：向量检索 11/15 通过。
- 向量检索失败样例：
  - `filling_capacity_en`
  - `mesoscopic_modeling`
  - `peridynamics`
  - `construction_management`

验证结果：

- `python -m pytest tests/test_embedding_provider.py -q`：7 个测试通过。
- `python -m pytest tests/test_vector_index_service.py -q`：5 个测试通过。
- `python -m pytest tests/test_vector_search.py tests/test_vector_search_api.py -q`：7 个测试通过。
- `python -m pytest tests/test_evaluate_vector_search.py -q`：3 个测试通过。
- `python scripts/evaluate_vector_search.py`：向量检索 11/15，关键词 baseline 15/15。
- `python -m pytest -q`：63 个测试通过。

已处理问题：

- 写出 `def batched[T]` 后发现该语法只支持 Python 3.12；项目使用 Python 3.11，因此改为 `TypeVar` 写法。
- 首次运行向量评测脚本超时；定位为首次索引构建时逐条 commit 成本高，已改为 batch commit。
- 用户指出“新词解释”规则容易遗漏；已将新词解释写入 `AGENT.MD` 的自检要求、`task_plan.md` 验收项和 `docs/stage2_learning_notes.md`。

遗留问题：

- 当前 deterministic embedding 是稳定测试用实现，不是真实语义模型。
- 向量检索 11/15 弱于关键词 baseline 15/15，说明下一步需要真实 embedding、混合检索或 query expansion。
- 尚未实现引用式回答、上下文组织、拒答机制和聊天模型调用，这些属于阶段 3。
- 尚未接入 FAISS/Chroma/PGVector；当前 SQLite 向量保存适合阶段 2 最小链路和迁移前验证。

面试表达：

```text
阶段 2 我没有直接把文本丢进向量库，而是先把 embedding 模型调用、向量保存、索引构建、向量检索和评测拆成独立模块。

EmbeddingProvider 负责把文本转成向量；chunk_embeddings 表保存每个 chunk 的向量、模型信息、维度和内容 hash；VectorIndexService 负责批量构建索引；VectorSearchService 负责把用户问题向量化并按余弦相似度召回 chunk。API 层只暴露 /search/vector，不直接写检索细节。

为了防止只凭演示判断效果，我复用了阶段 1 的关键词评测集，对关键词 baseline 和向量检索使用同一批问题做对比。当前 deterministic embedding 下向量检索为 11/15，关键词 baseline 为 15/15，这说明工程链路已经打通，但真实语义效果还需要后续接入更好的 embedding 模型或混合检索。
```

下一步：

- 进入阶段 3：引用式问答。
- 先基于 `POST /search/vector` 的返回结果组织上下文。
- 新增聊天模型 provider 抽象。
- 实现 `POST /chat`，返回回答和来源。
- 遇到资料不足时明确拒答，不让模型硬编。
