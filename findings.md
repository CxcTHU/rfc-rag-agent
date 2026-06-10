# Findings & Decisions（阶段 20）

## Requirements

- 用户要求为本线程设置长期 goal，并将线程标题改为「阶段20-中文检索默认链路落地与评测判定增强」。
- 目标分支：`codex/phase-20-default-chain-and-eval-upgrade`。
- 阶段 20 必须从已合并阶段 19 的 `main` 出发。
- 阶段 20 完成后必须停在用户人工核验前，不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。
- 阶段 20 不做写入型 Agent 工具、不做复杂 LangGraph workflow、不做登录系统、不做部署优化、不新增爬虫或外部资料来源。
- 不重做 chunk embedding；真实 Jina 只做 query 端校验，且不能成为 CI 或本地全量测试前提。
- HyDE 仍只做离线实验，不进入默认链路或自动回归。
- 默认链路是否切换必须由升级后的中文难评测集数据决定。
- 不得把 API key、Bearer token、供应商原始敏感响应、受限/受版权全文写入 Git、CSV、文档、测试或 Obsidian；中文全文与本地 DB 不入库。

## Git / Tag / Main 起点（已核实）

| Item | Evidence | Result |
|---|---|---|
| 当前启动分支 | `git status -sb` | `main...origin/main`，工作区干净 |
| 最近提交 | `git log --oneline -5` | `12184d7 Merge phase 19...`、`ffb4756 Complete phase 19...`、`4db90c7 Merge phase 18...` |
| 阶段 19 tag | `git rev-parse --short phase-19-complete` | `ffb4756` |
| 阶段 19 tag 提交 | `git show -s --format` | `ffb4756 Complete phase 19 chinese analysis and retrieval tuning`，父提交为 `4db90c7`，非 merge |
| main 合并提交 | `git show -s --format 12184d7` | 父提交为 `4db90c7` 与 `ffb4756`，是阶段 19 merge |
| 祖先关系 | `git merge-base --is-ancestor phase-19-complete main` | pass |
| 阶段 20 分支 | `git switch -c codex/phase-20-default-chain-and-eval-upgrade main` | 已创建并切换 |

结论：阶段 19 已完成并合并到 `main`；`phase-19-complete` 正确指向阶段 19 最终功能提交 `ffb4756`，未移动任何已有阶段 tag；阶段 20 已从正确基线启动。

## Stage 19 Findings To Carry Forward

### stage19_chinese_hard_queries

- 路径：`data/evaluation/stage19_chinese_hard_queries.csv`。
- 规模：19 题。
- 类型：5 cross_passage、5 confusable、5 parameter_detail、4 refusal。
- 作用：阶段 19 用它量化中文深度全文检索短板；阶段 20 继续复用，但要升级判定口径。
- 关键问题：阶段 19 的 `expected_source_hit` 主要基于标题/正文关键词，对 `metadata_record` 题录卡片有偏置，因为题录卡片标题/摘要本来关键词密度高。

### stage19_retrieval_tuning

- 路径：
  - `scripts/evaluate_stage19_retrieval_tuning.py`
  - `data/evaluation/stage19_retrieval_tuning_results.csv`
  - `data/evaluation/stage19_retrieval_tuning_summary.csv`
- 阶段 19 数据：
  - baseline：`precision@1=0.400`、`deep_fulltext_top1_rate=0.000`、`metadata_top1_rate=1.000`、`refusal_accuracy=0.750`。
  - `hybrid_fulltext_boost`：`precision@1=0.333`、`deep_fulltext_top1_rate=0.533`、`refusal_accuracy=0.750`。
  - `hybrid_metadata_demote`：`precision@1=0.333`、`deep_fulltext_top1_rate=0.533`、`refusal_accuracy=0.750`。
  - `hybrid_topic_anchor_strict`：`precision@1=0.200`、`deep_fulltext_top1_rate=0.733`、`refusal_accuracy=0.750`。
- 阶段 19 决策：三候选都显著提高 deep_top1，但 `precision@1` 未达 `Δp@1>=0.10`，因此 `keep_existing_hybrid`。
- 阶段 20 任务：判断 `precision@1` 的负向变化是否来自关键词命中偏置；用答案级 `coverage_ratio` 重新判定。

### source_type_reweight

- 路径：`app/services/retrieval/source_type_reweight.py`。
- 作用：对 hybrid 召回候选做纯函数后处理；按 source_type 对深度全文加权或题录降权，也可按主题锚点加权。
- 当前状态：阶段 19 只在评测脚本组合使用，未接入默认 `HybridSearchService` / Brain / API。
- 阶段 20 决策点：只有升级评测 + 真实 Jina query 校验后满足门槛，才把它接入默认 hybrid 链路；接入必须有配置开关和回滚。

## HybridSearchService / BrainService 默认链路理解

- `HybridSearchService` 是当前默认混合检索服务：keyword + vector 召回，归一化加权，both-match bonus，返回 `SearchResult` 风格结果。
- Brain hybrid 路径由 `BrainService.answer()` 统一编排；`/chat` 与 Agent `answer_with_citations` 复用 Brain。
- 因此默认链路若切换，不应在 `/chat` 或 Agent 里复制逻辑；应在 retrieval/Brain 边界统一接入，并保持 API schema 不变。
- 需要保证：
  - `POST /search/hybrid` 不破坏。
  - `POST /chat` 不破坏。
  - `POST /agent/query` 不破坏。
  - `POST /search` 与 `/search/vector` 不受影响。

## has_topic_anchor 主题门

- 路径：`app/services/brain/workflow.py`（阶段 18 增量）。
- 作用：低证据拒答前增加主题相关性判断；问题必须命中 RFC 核心领域词，避免 off-topic 问题只因单字或泛词命中而被回答。
- 阶段 19 发现：`cn_hq_refusal_engineering_responsibility` 和 `cn_explore_refusal_mix_design` 因命中域词，不会被主题门拦住。
- 阶段 20 决策：新增 `responsibility_gate`，补“同主题但不应替代工程责任判断”的拒答边界；不能用 `has_topic_anchor` 解决这类责任问题。

## Deterministic 与真实 Jina 双索引

- 阶段 19 文献快照记录：
  - 文档总数：465。
  - chunks：8918。
  - deterministic embedding：8918。
  - 真实 Jina embedding（`jina-embeddings-v3`，dim 1024）：8918。
- 阶段 20 约束：
  - 不重做 chunk embedding。
  - deterministic baseline 继续用于稳定回归。
  - 真实 Jina 只在 query 端生成 query embedding，并复用已有 8918 chunk embeddings。
  - 真实失败显式记录 `skipped` / `error`，不能用 deterministic 结果伪装真实通过。

## Default Switch Gate

阶段 20 继承并强化阶段 19 门槛：

```text
candidate_switch_allowed =
  delta_precision_at_1 >= 0.10
  and delta_deep_fulltext_top1_rate >= 0.20
  and refusal_accuracy >= baseline_refusal_accuracy
```

解释：

- `Δp@1>=0.10`：默认链路 top-1 质量要有足够增益。
- `Δdeep_top1>=0.20`：中文深度全文必须明显上浮，不能只在题录卡片里自嗨。
- refusal 不退化：拒答边界不能因为检索排序调优而放松。

如果三项不同时满足：保持 `keep_existing_hybrid`，把阻断原因写入结果表、设计文档、quality gate 和 `progress.md`。

## Data Safety Decisions

- `data/app.sqlite`、`data/raw/`、`data/fulltext/`、`obsidian-vault/` 都属于本地/忽略边界；不得纳入提交范围。
- 阶段 20 结果表只保存脱敏查询、配置、判定指标、来源类型、决策和 next_action，不保存受限全文。
- 真实 API key / Bearer token 只允许存在本地 `.env` 或运行时内存中。
- 真实供应商原始响应不得写入 CSV、文档、测试或 Obsidian；错误摘要必须脱敏。
- 真实 API 失败是有效质量状态，不能静默重试到成功后抹掉失败。

## Technical Decisions

| Decision | Rationale |
|---|---|
| Phase 20 先升级判定，再谈默认链路切换 | 阶段 19 已证明旧 hit 判定偏向题录卡片；不先修判定会误导默认链路决策 |
| `coverage_ratio` 作为主判定 | 更贴近答案要点覆盖，不只看标题/摘要关键词 |
| LLM-judge 仅可选离线 | 真实模型不稳定、有成本、有密钥边界，不适合作为 CI 必跑 |
| 真实 Jina 只做 query 端校验 | 既复用已有 Jina chunk 索引，又避免重做 8918 chunk embeddings |
| 默认链路切换必须可配置可关闭 | 阶段 19 候选效果有争议，必须保留回滚 |
| `responsibility_gate` 独立于 `has_topic_anchor` | 责任边界是“同主题但不能替代审查”的问题，不能靠 off-topic 主题门解决 |
| 不新增外部资料来源 | 阶段 20 是评测与默认链路闭环，不是语料扩充阶段 |

## Phase Findings

### Phase 0: 启动校准

- 已完成入口阅读、Git/tag/main 核验和阶段 20 分支创建。
- 已确认阶段 19 完整闭环：`phase-19-complete -> ffb4756`，`main` 已含 `12184d7` merge。
- 已把根目录 Planning with Files 文件从阶段 19 切换为阶段 20：
  - `task_plan.md` 明确 Phase 0-10 顺序、验证方式、文档收尾要求和完成标准。
  - `findings.md` 记录阶段 19 关键证据、默认链路理解、切换门槛和安全边界。
  - `progress.md` 记录线程 goal、标题、Git/tag/main 状态、分支和未提交边界。
- 当前工作区只包含上述三个规划文件变更；尚未进入代码改动。

### Phase 1: 阶段 20 设计文档

- 新增 `docs/stage20_default_chain_and_eval_upgrade.md`。
- 设计文档已固定阶段 20 核心口径：
  - 用答案级 `coverage_ratio` 取代题录关键词偏置主判定。
  - 真实 Jina 只做 query 端校验，不重做 chunk embeddings。
  - 默认链路切换必须同时满足 `delta_precision_at_1 >= 0.10`、`delta_deep_fulltext_top1_rate >= 0.20`、`refusal_accuracy >= baseline_refusal_accuracy`。
  - `source_type_reweight` 过门槛才接入默认 hybrid，且必须配置可关闭、可回滚。
  - `responsibility_gate` 独立处理同主题但要求工程责任判断的问题。
  - 不提交、不打 `phase-20-complete` tag、不 push、不 PR。
- 新增 `tests/test_stage20_default_chain_and_eval_upgrade.py`，断言设计文档包含核心产物、默认链路门槛、真实 API 安全边界和人工核验前限制。
- 验证结果：`.venv\Scripts\python.exe -m pytest tests\test_stage20_default_chain_and_eval_upgrade.py -q` -> 3 passed。

### Phase 2: 评测判定升级

- 新增 `scripts/evaluate_stage20_eval_upgrade.py`。
- 新增结果表：
  - `data/evaluation/stage20_eval_upgrade_results.csv`
  - `data/evaluation/stage20_eval_upgrade_summary.csv`
- 新增测试：`tests/test_stage20_eval_upgrade.py`。
- 判定变化：
  - 不再用 `expected_source_hit` 作为主 hit 判定。
  - 非拒答题用 top-1 证据的 `expected_answer_points` 覆盖率计算 `coverage_ratio`。
  - 为降低题录标题偏置，top-1 coverage evidence 有意排除 `document_title`，只用 `heading_path + content`。
  - 拒答题仍用 Brain refused 与 expected_refused 对齐来计算 `refusal_accuracy`。
- deterministic 结果：
  - `hybrid_baseline`: `p@1=0.133`, `avg_coverage=0.323`, `deep_top1=0.267`, `refusal_acc=0.750`。
  - `hybrid_fulltext_boost`: `p@1=0.133`, `avg_coverage=0.273`, `deep_top1=0.667`, `refusal_acc=0.750`。
  - `hybrid_metadata_demote`: `p@1=0.133`, `avg_coverage=0.273`, `deep_top1=0.667`, `refusal_acc=0.750`。
  - `hybrid_topic_anchor_strict`: `p@1=0.133`, `avg_coverage=0.273`, `deep_top1=0.733`, `refusal_acc=1.000`。
- Phase 2 决策：`overall=keep_existing_hybrid`。候选 deep top-1 明显上浮，但 `Δp@1=0.000<0.10`，仍未满足默认链路切换门槛。
- 运行记录：
  - 首次实际脚本运行 124 秒超时；原因是完整评测需要多次扫描本地检索候选与 8918 条向量。
  - 调整为更长超时后完整运行成功，用时约 164 秒。
  - 单元测试发现 `0.500 - 0.400` 浮点误差会让刚好达标的 `0.10` 被误判，已加入 `1e-9` 容差。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage20_eval_upgrade.py -q` -> 4 passed。
  - `.venv\Scripts\python.exe -m pytest tests\test_stage20_default_chain_and_eval_upgrade.py tests\test_stage20_eval_upgrade.py -q` -> 7 passed。

### Phase 3: 真实 Jina Query 端校验

- 已扩展 `scripts/evaluate_stage20_eval_upgrade.py --real-query`。
- 真实模式行为：
  - 只创建真实 embedding provider 用于 query embedding。
  - 复用已有 `jina-embeddings-v3` chunk embeddings。
  - 不调用 `VectorIndexService`，不重做 8918 chunk embeddings。
  - 缺少真实配置时写 `real_config_status=skipped`。
  - 调用失败时写 `real_config_status=error` 与脱敏错误摘要。
- 新增真实输出：
  - `data/evaluation/stage20_eval_upgrade_real_jina_results.csv`
  - `data/evaluation/stage20_eval_upgrade_real_jina_summary.csv`
- 真实 Jina query 校验结果为 `completed`，无 error。
- real summary：
  - `hybrid_baseline`: `p@1=0.133`, `avg_coverage=0.323`, `deep_top1=0.267`, `refusal_acc=0.750`。
  - `hybrid_fulltext_boost`: `p@1=0.133`, `avg_coverage=0.273`, `deep_top1=0.667`, `refusal_acc=0.750`。
  - `hybrid_metadata_demote`: `p@1=0.133`, `avg_coverage=0.273`, `deep_top1=0.667`, `refusal_acc=0.750`。
  - `hybrid_topic_anchor_strict`: `p@1=0.133`, `avg_coverage=0.273`, `deep_top1=0.733`, `refusal_acc=0.750`。
- 真实 Jina 决策：`overall=keep_existing_hybrid`，与 deterministic 一致。阻断原因仍是 `delta_precision_at_1=+0.000<0.10`。
- 敏感字段检查：`Select-String` 对 real results/summary 搜索 `sk-`、`Bearer`、`api-key`、`Authorization`、`token`、`jina_` 无命中。

### Phase 4: 默认链路接入决策

- 新增 `scripts/build_stage20_default_chain_decision.py`。
- 新增 `data/evaluation/stage20_default_chain_decision.csv`。
- 新增 `tests/test_stage20_default_chain_decision.py`。
- 决策逻辑：
  - deterministic summary 必须过门槛。
  - real Jina summary 必须存在且不反驳门槛。
  - 两者都过，才允许 `switch_default_candidate`。
- 实际结果：
  - `hybrid_fulltext_boost`: deterministic `Δp@1=+0.000`, real `Δp@1=+0.000`, final `keep_existing_hybrid`。
  - `hybrid_metadata_demote`: deterministic `Δp@1=+0.000`, real `Δp@1=+0.000`, final `keep_existing_hybrid`。
  - `hybrid_topic_anchor_strict`: deterministic `Δp@1=+0.000`, real `Δp@1=+0.000`, final `keep_existing_hybrid`。
- 阻断原因：全部候选都是 `delta_precision_at_1=+0.000<0.10`；虽然 `Δdeep_top1` 达标，但答案覆盖 p@1 没有提升。
- 工程决策：本阶段不改默认 `HybridSearchService` / Brain hybrid 链路，不新增默认回滚配置；`source_type_reweight` 继续作为候选/评测开关保留。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage20_default_chain_decision.py -q` -> 3 passed。
  - `.venv\Scripts\python.exe scripts\build_stage20_default_chain_decision.py` -> `overall=keep_existing_hybrid`。

### Phase 5: `responsibility_gate` 责任边界拒答门

- 新增 `RESPONSIBILITY_REFUSAL_ANSWER`、`RESPONSIBILITY_GATE_PATTERNS`、`ResponsibilityGate`、`evaluate_responsibility_gate()`。
- `BrainService._generate_answer_step()` 在证据置信度与模型生成前调用责任门；命中后返回责任边界拒答，而不是默认“资料不足”拒答。
- `_refuse()` 增加可选 `answer` 参数，默认仍为 `DEFAULT_REFUSAL_ANSWER`，避免影响普通低证据/无资料拒答。
- 正例触发：
  - `请判定本工程的堆石混凝土配合比设计是否符合规范要求？`
- 反例放行：
  - `堆石混凝土配合比通常关注哪些指标？`
  - `资料中提到的抗压强度影响因素有哪些？`
  - `规范审查和文献问答有什么区别？`
- 测试：
  - `tests/test_brain_workflow.py` 新增责任门纯函数正反例。
  - `tests/test_brain_service.py` 新增 BrainService 责任拒答与学习题不误拒测试。
- 结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_brain_workflow.py tests\test_brain_service.py -q` -> 21 passed。
  - 重跑 `scripts/evaluate_stage20_eval_upgrade.py` 后 deterministic 四配置 `refusal_acc=1.000`。
  - 重跑 `scripts/evaluate_stage20_eval_upgrade.py --real-query` 后真实 Jina 四配置 `refusal_acc=1.000`。
  - `cn_hq_refusal_engineering_responsibility` 在 deterministic 与 real results 中均 `hit=true/refusal_matched=true/refused=true`。

### Phase 6: Quality Gate / 报告更新

- 新增 `scripts/build_stage20_quality_report.py`，把阶段 20 的 deterministic summary、real Jina summary、结果明细和默认链路决策表汇总为质量门槛。
- 新增或更新阶段 20 质量产物：
  - `data/evaluation/stage20_quality_summary.csv`
  - `docs/stage20_quality_report.md`
  - `app/frontend/quality_report.html`
- 更新 `app/api/frontend.py`，让 `GET /quality-report` 与 CSV 导出指向阶段 20 quality summary；页面仍为只读静态 HTML，不触发真实 API、不写数据库、不改登录/权限体系。
- 更新 `tests/test_frontend_app.py`，使前端回归断言阶段 20 报告标题与 `stage20_quality_summary.csv` 导出文件名。
- 新增 `tests/test_stage20_quality_report.py`，覆盖 quality summary schema、默认链路阻断、责任边界闭环和 HTML 报告关键内容。
- 当前 quality gate 结果：
  - `eval_judge_upgrade`: `completed`，`risk_level=low`。
  - `real_jina_query_validation`: `completed`，`risk_level=low`。
  - `default_chain_decision`: `keep_existing_hybrid`，`risk_level=low`。
  - `responsibility_gate`: `closed`，`matched=4/4`，`risk_level=low`。
  - `api_regression`: Phase 6 初始为 `pending`，Phase 7 全量回归后已重建为 `passed`。
  - `overall`: Phase 6 初始为 `review_required/medium`，Phase 7 后最终为 `pass/low`。
- 关键决策：quality gate 把阶段 19 两个遗留点分开闭环。默认链路遗留不是“已切换”，而是“经升级判定后数据不足以切换，保留 keep_existing_hybrid”；责任边界遗留则已由 `responsibility_gate` 闭环。
- 验证结果：
  - `.venv\Scripts\python.exe scripts\build_stage20_quality_report.py` -> 生成 6 行 summary，当前 `quality_gate=review_required/medium`。
  - `.venv\Scripts\python.exe -m pytest tests\test_stage20_quality_report.py tests\test_frontend_app.py -q` -> 7 passed。

### Phase 7: 回归验证

- 聚焦回归第一组覆盖阶段 20 新增内容与用户点名 API 入口：
  - `tests/test_stage20_default_chain_and_eval_upgrade.py`
  - `tests/test_stage20_eval_upgrade.py`
  - `tests/test_stage20_default_chain_decision.py`
  - `tests/test_stage20_quality_report.py`
  - `tests/test_search_api.py`
  - `tests/test_vector_search_api.py`
  - `tests/test_hybrid_search.py`
  - `tests/test_chat_api.py`
  - `tests/test_agent_api.py`
  - `tests/test_frontend_app.py`
  - `tests/test_brain_workflow.py`
  - `tests/test_brain_service.py`
- 聚焦回归第一组结果：`.venv\Scripts\python.exe -m pytest ... -q` -> 61 passed。
- 聚焦回归第二组覆盖 documents/sources/decompose/vector index 与评测周边：
  - `tests/test_documents_api.py`
  - `tests/test_sources_api.py`
  - `tests/test_sync_sources.py`
  - `tests/test_source_repository.py`
  - `tests/test_source_registry_service.py`
  - `tests/test_source_collection.py`
  - `tests/test_vector_search.py`
  - `tests/test_vector_index_service.py`
  - `tests/test_vector_index_retry.py`
  - `tests/test_decompose_retrieval.py`
  - `tests/test_stage13_decompose_plan.py`
  - `tests/test_evaluate_decompose.py`
  - `tests/test_evaluate_chat.py`
  - `tests/test_evaluate_agent.py`
  - `tests/test_evaluate_brain_workflow.py`
- 聚焦回归第二组结果：`.venv\Scripts\python.exe -m pytest ... -q` -> 67 passed。
- 全量测试结果：`.venv\Scripts\python.exe -m pytest -q` -> 424 passed。
- 全量测试通过后重建 quality gate：`.venv\Scripts\python.exe scripts\build_stage20_quality_report.py --full-tests-status passed` -> `quality_gate=pass/low`，6 行均为 `risk_level=low`。
- 最终质量报告回归：`.venv\Scripts\python.exe -m pytest tests\test_stage20_quality_report.py tests\test_frontend_app.py -q` -> 7 passed。
- 结论：`POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 未被阶段 20 改动破坏；默认链路仍保持 `keep_existing_hybrid`。

### Phase 8: 普通文档收尾

- 更新 `README.md`：
  - 顶部当前阶段切换到阶段 20。
  - 写明当前分支、未提交/未 tag/未 push/未 PR 边界。
  - 写明阶段 19 已合并：`phase-19-complete -> ffb4756`，merge `12184d7`。
  - 写明阶段 20 核心产物、默认链路决策、quality gate `pass/low`、全量 424 passed。
- 更新 `docs/progress.md`：
  - 新增阶段 20 最新状态、Git 起点、完成内容、评测结果、遗留风险、下一阶段任务和面试表达。
  - 把阶段 19 段落从“待人工核验”改为“已完成并合并”，并说明阶段 20 已承接其遗留。
- 更新 `docs/architecture.md`：
  - 新增阶段 20 架构章节，说明 coverage ratio、真实 Jina query-only、默认链路门槛、`responsibility_gate`、quality gate 和 API 边界。
  - 明确阶段 20 不改变默认 `HybridSearchService` / Brain hybrid 检索排序，真正进入运行链路的是责任边界安全门。
- 更新 `docs/data_sources.md`：
  - 新增阶段 20 产物清单和读取边界。
  - 明确阶段 20 不新增外部资料来源、不新增爬虫、不保存受限全文、不重做 chunk embedding。
- 更新 `AGENT.MD`：
  - 阶段路线更新为阶段 0-19 已有 tag。
  - 阶段 19 已合并，阶段 20 当前分支和人工核验前提交边界写入规则真相源。
- 文档一致性检查：
  - 搜索旧表达 `阶段 19 当前` / `阶段 19.*待人工` / `阶段 19 当前没有` 无命中。
  - 搜索阶段 20 关键词能在 README、progress、architecture、data_sources、AGENT 中命中。
- 验证结果：`.venv\Scripts\python.exe -m pytest tests\test_stage20_default_chain_and_eval_upgrade.py tests\test_stage20_quality_report.py tests\test_frontend_app.py -q` -> 10 passed。

### Phase 9: Obsidian 本地知识库收尾

- 新增阶段 20 Obsidian 目录：`obsidian-vault/阶段汇报/阶段 20 - 中文检索默认链路落地与评测判定增强/`。
- 新增 `阶段 20 Phase 汇报索引.md`，说明这是按用户要求在开发、测试、普通文档完成后统一回填，依据为 `docs/progress.md`、Planning with Files 与测试结果。
- 新增 Phase 0 到 Phase 10 共 11 篇小汇报：
  - `阶段 20 Phase 0 - 启动校准.md`
  - `阶段 20 Phase 1 - 阶段 20 设计文档.md`
  - `阶段 20 Phase 2 - 评测判定升级.md`
  - `阶段 20 Phase 3 - 真实 Jina Query 端校验.md`
  - `阶段 20 Phase 4 - 默认链路接入决策.md`
  - `阶段 20 Phase 5 - responsibility_gate 责任边界拒答门.md`
  - `阶段 20 Phase 6 - Quality Gate 与报告更新.md`
  - `阶段 20 Phase 7 - 回归验证.md`
  - `阶段 20 Phase 8 - 普通文档收尾.md`
  - `阶段 20 Phase 9 - Obsidian 本地知识库收尾.md`
  - `阶段 20 Phase 10 - 人工核验待提交状态.md`
- 新增阶段页 `obsidian-vault/阶段/阶段 20 - 中文检索默认链路落地与评测判定增强.md`。
- 更新 `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`。
- 顺手把 Obsidian 阶段 19 页从“待人工核验”修正为“已完成并合并”，与 Git 真相一致。
- 验证结果：
  - 阶段 20 汇报目录共 12 个文件（索引 + 11 篇 Phase 汇报）。
  - Phase 0-10 每篇均包含固定 10 项标题。
  - `git check-ignore -v obsidian-vault/...` 显示由 `.gitignore:32:obsidian-vault/` 排除。

### Phase 10: 人工核验待提交状态

- 当前分支：`codex/phase-20-default-chain-and-eval-upgrade`。
- `git status -sb --untracked-files=all` 显示仅工作区修改/新增，未 staged。
- `git diff --cached --stat` 与 `git diff --cached --name-only` 无输出，确认未执行 `git add`。
- `phase-19-complete -> ffb4756`，`ffb4756 Complete phase 19 chinese analysis and retrieval tuning`；`12184d7 Merge phase 19 chinese analysis and retrieval tuning` 仍在 log 顶部，`phase-19-complete` 是 `main` 祖先。
- `phase-20-complete` tag 不存在，未创建阶段 20 tag。
- 阶段 20 CSV schema 检查通过：结果表只包含 query/config/judge/status/指标/决策/来源标题等脱敏字段，不含正文 content 字段或供应商原始响应字段。
- 高置信敏感信息扫描：
  - stage20 代码/文档/CSV 未命中真实 `sk-...`、`Bearer ...`、`jina_...`、`*_API_KEY=实际值` 形态。
  - stage20 输出未命中 `raw_response`、`provider_response`、`supplier_response`、`authorization`、`api_key`、`bearer token`。
  - README 中既有 `EMBEDDING_API_KEY=your-local-secret` 是文档占位示例，不是实际密钥。
- Obsidian 检查：`git status --short --ignored obsidian-vault` 显示 `!! obsidian-vault/`，确认本地知识库不进入提交范围。
- 最终状态：阶段 20 开发、测试、普通文档和 Obsidian 草稿完成；尚未提交、尚未创建 `phase-20-complete` tag、尚未 push、未创建 PR，等待用户人工核验。

## Term Explanations

| Term | Meaning in this project |
|---|---|
| 答案级 coverage ratio | 用 `expected_answer_points` 衡量回答或证据覆盖了多少期望要点，避免题录标题关键词带来的假命中 |
| 去关键词偏置 | 减少“题录卡片因为标题/摘要关键词密集而被判为好结果”的偏差 |
| query 端真实 Jina | 只调用 Jina 生成用户问题向量，和已有 chunk 向量比相似度 |
| 默认链路 | 用户正常调用 `/search/hybrid`、`/chat`、`/agent/query` 时实际走的检索路径 |
| 回滚开关 | 配置项允许关闭新默认链路，恢复旧 `HybridSearchService` 行为 |
| 工程责任问题 | 要系统替用户判定是否合格、是否符合规范、能否出具结论、配合比是否可用于工程等问题 |
| quality summary | 阶段 20 的质量门槛 CSV，用同一张表记录评测升级、真实 Jina、默认链路决策、责任门和回归状态，供报告与 `/quality-report` 读取 |
| Obsidian Phase 汇报 | 本地知识库里的小阶段复盘笔记，用 10 项固定结构记录目标、改动、验证、遗留和面试表达 |

## Issues / Risks

| Risk | Evidence | Planned Handling |
|---|---|---|
| 旧 `precision@1` 偏向题录 | 阶段 19 baseline meta_top1=1.000，但 deep_fulltext_top1=0.000 | Phase 2 用 `coverage_ratio` 升级判定 |
| 真实 API 可能失败 | 阶段 15/16/18 有真实 provider/network 失败记录 | Phase 3 显式 `skipped` / `error`，不作为全量测试前提 |
| 默认链路切换可能影响 chat/agent | Brain 与 Agent 共用检索链路 | Phase 4 数据未过门槛，保持 `keep_existing_hybrid`；Phase 7 做回归确认 |
| responsibility gate 可能误拒学习题 | 责任词与普通解释题可能相邻 | Phase 5 已加正反例测试；Phase 7 继续跑 Brain/chat/agent 回归 |
| 全量测试阶段性待完成 | Phase 6 quality gate 初始等待 Phase 7 回归 | Phase 7 已完成，424 passed；quality gate 已重建为 `pass/low` |
| Obsidian 不应提交 | `obsidian-vault/` 是本地知识库 | Phase 9 更新后确认 gitignore |

## Resources

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage19_chinese_analysis_retrieval_tuning.md`
- `docs/stage19_literature_review.md`
- `data/evaluation/stage19_chinese_hard_queries.csv`
- `data/evaluation/stage19_retrieval_tuning_results.csv`
- `data/evaluation/stage19_retrieval_tuning_summary.csv`
- `app/services/retrieval/source_type_reweight.py`
- `app/services/retrieval/hybrid_search.py`
- `app/services/brain/service.py`
- `app/services/brain/workflow.py`
- `scripts/evaluate_stage19_retrieval_tuning.py`
