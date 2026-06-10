# Progress Log（阶段 20）

## Session: 2026-06-10

### Goal / Thread Setup

- 已设置线程 goal：持续推进阶段 20「中文检索默认链路落地与评测判定增强」，直到开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前。
- 已修改当前线程名称为：阶段20-中文检索默认链路落地与评测判定增强。
- 使用 Planning with Files 维护根目录 `task_plan.md`、`findings.md`、`progress.md`。

### Startup Reading

已按入口规则阅读/核对：

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/stage19_chinese_analysis_retrieval_tuning.md`
- `docs/stage19_literature_review.md`
- `task_plan.md`
- `findings.md`
- `progress.md`

规划技能说明已读取：`C:\Users\admin\.codex\skills\planning-with-files\SKILL.md`。

### Git / Tag / Main Status

启动命令结果：

```text
git status -sb
## main...origin/main

git log --oneline -5
12184d7 Merge phase 19 chinese analysis and retrieval tuning
ffb4756 Complete phase 19 chinese analysis and retrieval tuning
4db90c7 Merge phase 18 corpus expansion, evaluation and quality system
c56fc62 Complete phase 18 corpus expansion, evaluation and quality system
d633b95 Merge phase 17 retrieval architecture upgrade
```

阶段 19 核验：

```text
phase-19-complete -> ffb4756
ffb4756 Complete phase 19 chinese analysis and retrieval tuning
parent: 4db90c7
```

- `ffb4756` 是阶段 19 最终功能提交，非 merge commit。
- `12184d7` 是阶段 19 合并提交，父提交为 `4db90c7` 与 `ffb4756`。
- `phase-19-complete` 是 `main` 祖先。
- 未移动任何已有阶段 tag。

分支状态：

```text
git switch -c codex/phase-20-default-chain-and-eval-upgrade main
Switched to a new branch 'codex/phase-20-default-chain-and-eval-upgrade'
```

当前分支：`codex/phase-20-default-chain-and-eval-upgrade`。

### Phase 0: 启动校准

- Status: complete
- 解决的问题：确认阶段 20 从含阶段 19 合并的正确 `main` 起步，并把阶段 20 的 Phase 顺序、验证口径和人工核验前边界写入磁盘工作记忆。
- 在 RAG 链路中的位置：阶段启动与评测/默认链路设计前置层；此 Phase 不改检索代码。
- 为什么现在做：阶段 20 要决定是否把阶段 19 的 `source_type_reweight` 接入默认链路，必须先确认基线正确、阶段 19 tag/main 已闭环、旧规划文件已切换到阶段 20，避免从错误历史状态继续开发。

已完成：

- 创建 goal。
- 重命名线程。
- 读取项目入口文件、阶段 19 文档、旧规划文件。
- 运行 Git 状态与最近提交检查。
- 核验 `phase-19-complete -> ffb4756` 且 `ffb4756` 非 merge。
- 核验 `main` 含 `12184d7 Merge phase 19...`。
- 从 `main` 创建并切到 `codex/phase-20-default-chain-and-eval-upgrade`。
- 校准 `task_plan.md` 为阶段 20 Phase 0-10 顺序、验证方式、文档收尾要求和完成标准。
- 校准 `findings.md`，记录 stage19 中文难评测集、检索调优、`source_type_reweight`、默认链路、`has_topic_anchor`、双索引、切换门槛和数据安全边界。
- 校准 `progress.md`，记录阶段启动、Git/tag/main 状态和未提交边界。

验证结果：

- `git status -sb`：当前分支 `codex/phase-20-default-chain-and-eval-upgrade`，仅 `task_plan.md`、`findings.md`、`progress.md` 修改。
- `git branch --show-current`：`codex/phase-20-default-chain-and-eval-upgrade`。
- 规划文件内容检查通过：`task_plan.md` 含 Phase 0-10、`coverage_ratio`、`responsibility_gate`、不创建 `phase-20-complete` tag；`findings.md` 含 `phase-19-complete`、`ffb4756`、`12184d7`、`source_type_reweight`、`Default Switch Gate`；`progress.md` 含分支和未提交边界。

Phase 0 结论：

- 阶段 20 启动基线正确。
- 阶段 19 tag/main 状态正确。
- Planning with Files 已切换到阶段 20。
- 当前可进入 Phase 1 设计文档。

### Phase 1: 阶段 20 设计文档

- Status: complete
- 解决的问题：把阶段 20 的评测判定升级、真实 Jina query 校验、默认链路接入门槛、`responsibility_gate`、安全边界和完成标准先写成设计文档，避免后续代码改动没有统一依据。
- 在 RAG 链路中的位置：评测层与检索默认链路设计层；它定义后续是否改默认 `HybridSearchService` / Brain hybrid 路径，以及责任拒答门应插在生成前的哪条边界。
- 为什么现在做：阶段 20 的核心风险是“用错误指标切默认链路”或“责任拒答门误伤正常学习题”。先写设计文档可以固定口径，再进入脚本和代码实现。

完成工作：

- 新增 `docs/stage20_default_chain_and_eval_upgrade.md`。
- 新增 `tests/test_stage20_default_chain_and_eval_upgrade.py`。

验证结果：

```text
.venv\Scripts\python.exe -m pytest tests\test_stage20_default_chain_and_eval_upgrade.py -q
3 passed in 0.03s
```

Phase 1 结论：

- 阶段 20 的评测判定、真实 Jina query-only 边界、默认链路切换门槛、`responsibility_gate` 和人工核验前边界已写入设计文档并有测试锁定。

### Phase 2: 评测判定升级

- Status: complete
- 解决的问题：阶段 19 的 `precision@1` 主要依赖 `expected_source_hit` 关键词命中，容易让题录卡片因为标题/摘要关键词密集而被判为好结果。Phase 2 要改成答案级 `coverage_ratio`，用 `expected_answer_points` 判断证据是否覆盖答案要点。
- 在 RAG 链路中的位置：评测层；它不直接改变线上检索结果，但会决定 Phase 4 是否允许把 `source_type_reweight` 接入默认 hybrid 链路。
- 为什么现在做：如果不先修判定口径，就可能因为旧关键词偏置错误地阻止或推动默认链路切换。

完成工作：

- 新增 `scripts/evaluate_stage20_eval_upgrade.py`。
- 新增 `data/evaluation/stage20_eval_upgrade_results.csv`。
- 新增 `data/evaluation/stage20_eval_upgrade_summary.csv`。
- 新增 `tests/test_stage20_eval_upgrade.py`。
- 更新 `docs/stage20_default_chain_and_eval_upgrade.md`，加入阶段 20 评测升级产物与 deterministic 结果。

验证结果：

```text
.venv\Scripts\python.exe -m py_compile scripts\evaluate_stage20_eval_upgrade.py
pass

.venv\Scripts\python.exe -m pytest tests\test_stage20_eval_upgrade.py -q
4 passed in 0.34s

.venv\Scripts\python.exe scripts\evaluate_stage20_eval_upgrade.py
stage20 eval upgrade (coverage_ratio) -> overall=keep_existing_hybrid
  hybrid_baseline              p@1=0.133 coverage=0.323 deep_top1=0.267 refusal_acc=0.750 decision=baseline
  hybrid_fulltext_boost        p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=0.750 decision=keep_existing_hybrid
  hybrid_metadata_demote       p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=0.750 decision=keep_existing_hybrid
  hybrid_topic_anchor_strict   p@1=0.133 coverage=0.273 deep_top1=0.733 refusal_acc=1.000 decision=keep_existing_hybrid

.venv\Scripts\python.exe -m pytest tests\test_stage20_default_chain_and_eval_upgrade.py tests\test_stage20_eval_upgrade.py -q
7 passed in 0.34s
```

问题与解决：

- 首次完整评测在 124 秒超时；改用更长超时后成功完成。
- 单元测试发现浮点边界 `0.500 - 0.400` 可能略小于 `0.10`，已在切换门槛比较中加入 `1e-9` 容差。

Phase 2 结论：

- `coverage_ratio` 判定升级已落地。
- deterministic 主结论仍是 `keep_existing_hybrid`：候选配置提升 deep top-1，但没有提升答案覆盖 p@1。

### Phase 3: 真实 Jina Query 端校验

- Status: complete
- 解决的问题：deterministic baseline 能稳定回归，但不能代表真实中文语义向量效果。Phase 3 要在不重做 8918 个 chunk embeddings 的前提下，用真实 Jina 只生成 query embedding 来校验 Phase 2 结论。
- 在 RAG 链路中的位置：真实模型发布前校准层；它只影响评测结果，不应成为 CI 或本地全量测试前提。
- 为什么现在做：默认链路切换必须同时看稳定 baseline 与真实 query 端表现；真实失败也要显式记录，不能被 deterministic 结果掩盖。

完成工作：

- 扩展 `scripts/evaluate_stage20_eval_upgrade.py --real-query`。
- 新增 `data/evaluation/stage20_eval_upgrade_real_jina_results.csv`。
- 新增 `data/evaluation/stage20_eval_upgrade_real_jina_summary.csv`。
- 扩展 `tests/test_stage20_eval_upgrade.py`，覆盖真实配置缺失时的 skipped 记录。
- 更新 `docs/stage20_default_chain_and_eval_upgrade.md`，加入真实 Jina query 端校验结果。

验证结果：

```text
.venv\Scripts\python.exe -m py_compile scripts\evaluate_stage20_eval_upgrade.py
pass

.venv\Scripts\python.exe -m pytest tests\test_stage20_eval_upgrade.py -q
5 passed in 0.33s

.venv\Scripts\python.exe scripts\evaluate_stage20_eval_upgrade.py --real-query
stage20 eval upgrade (coverage_ratio_real_jina) -> overall=keep_existing_hybrid
  hybrid_baseline              p@1=0.133 coverage=0.323 deep_top1=0.267 refusal_acc=0.750 decision=baseline
  hybrid_fulltext_boost        p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=0.750 decision=keep_existing_hybrid
  hybrid_metadata_demote       p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=0.750 decision=keep_existing_hybrid
  hybrid_topic_anchor_strict   p@1=0.133 coverage=0.273 deep_top1=0.733 refusal_acc=0.750 decision=keep_existing_hybrid
```

安全检查：

- real results/summary 中 `real_config_status=completed`。
- 对 real results/summary 搜索 `sk-`、`Bearer`、`api-key`、`Authorization`、`token`、`jina_` 无命中。
- 未重做 chunk embedding；脚本未调用 `VectorIndexService`。

Phase 3 结论：

- 真实 Jina query 端校验完成，结论仍为 `keep_existing_hybrid`。
- 真实校验没有推翻 deterministic 主结论。

### Phase 4: 默认链路接入决策

- Status: complete
- 解决的问题：把 Phase 2/3 的升级判定结果转成默认链路决策，决定是否把 `source_type_reweight` 接入默认 `HybridSearchService` / Brain hybrid 路径。
- 在 RAG 链路中的位置：默认检索链路接入层，影响 `/search/hybrid`、`/chat`、`/agent/query` 是否采用候选重权。
- 为什么现在做：评测判定和真实 Jina 校验都已完成，已经具备判断默认链路能否切换的数据依据。

完成工作：

- 新增 `scripts/build_stage20_default_chain_decision.py`。
- 新增 `data/evaluation/stage20_default_chain_decision.csv`。
- 新增 `tests/test_stage20_default_chain_decision.py`。
- 更新 `docs/stage20_default_chain_and_eval_upgrade.md`，写入默认链路决策表。

验证结果：

```text
.venv\Scripts\python.exe -m py_compile scripts\build_stage20_default_chain_decision.py
pass

.venv\Scripts\python.exe -m pytest tests\test_stage20_default_chain_decision.py -q
3 passed in 0.03s

.venv\Scripts\python.exe scripts\build_stage20_default_chain_decision.py
stage20 default chain decision -> overall=keep_existing_hybrid
  hybrid_baseline              final=baseline det_dp1=+0.000 real_dp1=+0.000
  hybrid_fulltext_boost        final=keep_existing_hybrid det_dp1=+0.000 real_dp1=+0.000
  hybrid_metadata_demote       final=keep_existing_hybrid det_dp1=+0.000 real_dp1=+0.000
  hybrid_topic_anchor_strict   final=keep_existing_hybrid det_dp1=+0.000 real_dp1=+0.000
```

Phase 4 结论：

- 不接入默认链路。
- `source_type_reweight` 继续保留为候选/评测开关。
- 阻断原因是 `Δp@1=+0.000<0.10`；候选 deep top-1 上浮不足以单独证明默认链路应该切换。

### Phase 5: `responsibility_gate` 责任边界拒答门

- Status: complete
- 解决的问题：阶段 19 遗留的 `cn_hq_refusal_engineering_responsibility` 是同主题但要求系统替代规范审查/工程判定的问题，`has_topic_anchor` 无法拦截。Phase 5 要新增责任边界拒答门。
- 在 RAG 链路中的位置：生成前安全门；应在 Brain workflow 中早于模型回答，确保 `/chat` 和 Agent 共用同一责任边界。
- 为什么现在做：默认链路决策已收口为不切，下一项阶段 19 遗留就是责任边界拒答；先修这个门，再更新 quality gate。

完成工作：

- 更新 `app/services/brain/workflow.py`：新增 `RESPONSIBILITY_REFUSAL_ANSWER`、`RESPONSIBILITY_GATE_PATTERNS`、`ResponsibilityGate`、`evaluate_responsibility_gate()`。
- 更新 `app/services/brain/service.py`：在 `_generate_answer_step()` 中、证据置信度与模型生成前调用责任门；`_refuse()` 支持传入责任边界拒答答案。
- 更新 `tests/test_brain_workflow.py`：责任门正反例测试。
- 更新 `tests/test_brain_service.py`：BrainService 责任拒答与普通学习题不误拒测试。
- 重跑 deterministic / real Jina stage20 eval，并重建默认链路决策表。
- 更新 `docs/stage20_default_chain_and_eval_upgrade.md` 中 refusal accuracy 和责任门闭环说明。

验证结果：

```text
.venv\Scripts\python.exe -m py_compile app\services\brain\workflow.py app\services\brain\service.py
pass

.venv\Scripts\python.exe -m pytest tests\test_brain_workflow.py tests\test_brain_service.py -q
21 passed in 2.18s

.venv\Scripts\python.exe scripts\evaluate_stage20_eval_upgrade.py
stage20 eval upgrade (coverage_ratio) -> overall=keep_existing_hybrid
  hybrid_baseline              p@1=0.133 coverage=0.323 deep_top1=0.267 refusal_acc=1.000 decision=baseline
  hybrid_fulltext_boost        p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_metadata_demote       p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_topic_anchor_strict   p@1=0.133 coverage=0.273 deep_top1=0.733 refusal_acc=1.000 decision=keep_existing_hybrid

.venv\Scripts\python.exe scripts\evaluate_stage20_eval_upgrade.py --real-query
stage20 eval upgrade (coverage_ratio_real_jina) -> overall=keep_existing_hybrid
  hybrid_baseline              p@1=0.133 coverage=0.323 deep_top1=0.267 refusal_acc=1.000 decision=baseline
  hybrid_fulltext_boost        p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_metadata_demote       p@1=0.133 coverage=0.273 deep_top1=0.667 refusal_acc=1.000 decision=keep_existing_hybrid
  hybrid_topic_anchor_strict   p@1=0.133 coverage=0.273 deep_top1=0.733 refusal_acc=1.000 decision=keep_existing_hybrid
```

问题与解决：

- 正反例测试首次失败，是因为学习题 query 没有被关键词检索召回，走了无资料拒答；调整测试 fixture，使学习题稳定命中资料后验证“不误拒”通过。

Phase 5 结论：

- 阶段 19 遗留 `cn_hq_refusal_engineering_responsibility` 已闭环。
- on-topic 学习题不误拒。
- 默认链路仍不切换，阻断原因仍为 `Δp@1=+0.000<0.10`。

### Phase 6: Quality Gate / 报告更新

- Status: complete
- 解决的问题：把 Phase 2-5 的结果汇总成阶段 20 quality gate，让默认链路遗留和责任边界遗留有明确闭环状态。
- 在 RAG 链路中的位置：evaluation/reporting 层；只读总结，不触发真实 API、不写数据库、不改变核心 API schema。
- 为什么现在做：核心评测与责任门都已完成，需要用 quality gate 把“哪些已闭环、哪些仍阻断”固定为可人工核验的证据。

完成工作：

- 新增 `scripts/build_stage20_quality_report.py`。
- 新增 `data/evaluation/stage20_quality_summary.csv`。
- 新增 `docs/stage20_quality_report.md`。
- 更新 `app/frontend/quality_report.html` 为阶段 20 质量门槛只读报告。
- 更新 `app/api/frontend.py`，让 `GET /quality-report` 和 CSV 导出读取阶段 20 quality summary。
- 新增 `tests/test_stage20_quality_report.py`。
- 更新 `tests/test_frontend_app.py`，同步阶段 20 报告标题和导出文件名。

当前 quality gate 结果：

```text
.venv\Scripts\python.exe scripts\build_stage20_quality_report.py
stage 20 quality gate: 6 rows
risk counts: low=4, medium=2
quality gate: review_required/medium
wrote summary to data\evaluation\stage20_quality_summary.csv
wrote markdown to docs\stage20_quality_report.md
wrote html to app\frontend\quality_report.html
```

验证结果：

```text
.venv\Scripts\python.exe -m py_compile scripts\build_stage20_quality_report.py app\api\frontend.py
pass

.venv\Scripts\python.exe -m pytest tests\test_stage20_quality_report.py tests\test_frontend_app.py -q
7 passed in 0.66s
```

Phase 6 结论：

- 阶段 20 quality gate 已落地。
- 阶段 19 默认链路遗留已闭环为：升级判定与真实 Jina 均未满足切换门槛，保持 `keep_existing_hybrid`，阻断原因写入结果表和报告。
- 阶段 19 工程责任边界遗留已闭环为：`responsibility_gate` 命中 4/4，拒答准确率 1.000。
- Phase 6 初始 quality gate 为 `review_required/medium`，唯一主要原因是 Phase 7 全量回归尚未完成；Phase 7 全量测试通过后已重建为 `pass/low`。

### Phase 7: 回归验证

- Status: complete
- 解决的问题：确认阶段 20 新增评测、责任门和质量报告没有破坏现有 RAG API、Brain、Agent、前端报告和既有测试。
- 在 RAG 链路中的位置：端到端回归层；覆盖 `/search`、`/search/vector`、`/search/hybrid`、`/chat`、`/agent/query`、`/quality-report` 以及 documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend 测试。
- 为什么现在做：代码和报告层已经收口，进入普通文档前必须先用聚焦回归与全量测试证明行为稳定，再把最终测试数写入 docs 和 Obsidian。

完成工作：

- 运行阶段 20 + 用户点名 API 入口聚焦回归。
- 运行 documents/sources/decompose/vector index 周边回归。
- 运行全量 pytest。
- 全量测试通过后，用 `--full-tests-status passed` 重建阶段 20 quality gate。
- 重跑质量报告与前端报告测试，确认最终 HTML/CSV/API 读取一致。

验证结果：

```text
.venv\Scripts\python.exe -m pytest tests\test_stage20_default_chain_and_eval_upgrade.py tests\test_stage20_eval_upgrade.py tests\test_stage20_default_chain_decision.py tests\test_stage20_quality_report.py tests\test_search_api.py tests\test_vector_search_api.py tests\test_hybrid_search.py tests\test_chat_api.py tests\test_agent_api.py tests\test_frontend_app.py tests\test_brain_workflow.py tests\test_brain_service.py -q
61 passed in 8.13s

.venv\Scripts\python.exe -m pytest tests\test_documents_api.py tests\test_sources_api.py tests\test_sync_sources.py tests\test_source_repository.py tests\test_source_registry_service.py tests\test_source_collection.py tests\test_vector_search.py tests\test_vector_index_service.py tests\test_vector_index_retry.py tests\test_decompose_retrieval.py tests\test_stage13_decompose_plan.py tests\test_evaluate_decompose.py tests\test_evaluate_chat.py tests\test_evaluate_agent.py tests\test_evaluate_brain_workflow.py -q
67 passed in 6.54s

.venv\Scripts\python.exe -m pytest -q
424 passed in 29.68s

.venv\Scripts\python.exe scripts\build_stage20_quality_report.py --full-tests-status passed
quality gate: pass/low

.venv\Scripts\python.exe -m pytest tests\test_stage20_quality_report.py tests\test_frontend_app.py -q
7 passed in 0.63s
```

Phase 7 结论：

- `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 未被破坏。
- documents/search/vector/hybrid/decompose/chat/brain/agent/sources/frontend 相关测试通过。
- 阶段 20 最终 quality gate 为 `pass/low`。
- 可以进入 Phase 8 普通文档收尾。

### Phase 8: 普通文档收尾

- Status: complete
- 解决的问题：把阶段 20 的设计、结果、默认链路决策、测试数、安全边界和面试表达同步到普通项目文档，避免只停留在脚本和临时报告里。
- 在 RAG 链路中的位置：项目知识与维护文档层；不改运行时代码，但让后续 Agent 和人工核验能理解当前默认链路为什么保持不切换。
- 为什么现在做：回归已经通过，quality gate 已经是最终 `pass/low`；现在可以把稳定结果写入 README、docs/progress、architecture、data_sources 和必要的 AGENT.MD 判断，再进入 Obsidian 草稿。

完成工作：

- 更新 `README.md` 顶部当前阶段与“当前已经实现”清单。
- 更新 `docs/progress.md`，新增阶段 20 最新状态，并把阶段 19 改为已完成并合并的历史基线。
- 更新 `docs/architecture.md`，新增阶段 20 架构章节。
- 更新 `docs/data_sources.md`，新增阶段 20 评测/报告产物与合规边界。
- 更新 `AGENT.MD`，写入阶段 19 已合并、阶段 20 当前分支和人工核验前提交边界。

验证结果：

```text
rg "阶段 19 当前|阶段 19.*待人工|当前阶段：阶段 19|phase-19-complete tag 和推送|阶段 19 当前没有" README.md docs\progress.md docs\architecture.md docs\data_sources.md AGENT.MD
no matches

rg "stage20_default_chain|coverage_ratio|responsibility_gate|stage20_quality|phase-20-complete|424 passed|pass/low" README.md docs\progress.md docs\architecture.md docs\data_sources.md AGENT.MD
matches in README / docs / AGENT

.venv\Scripts\python.exe -m pytest tests\test_stage20_default_chain_and_eval_upgrade.py tests\test_stage20_quality_report.py tests\test_frontend_app.py -q
10 passed in 0.65s
```

Phase 8 结论：

- 普通文档已同步阶段 20。
- 阶段 19 不再被入口文档描述为待人工核验。
- Obsidian 尚未更新，按用户要求留到 Phase 9 一次性补齐。

### Phase 9: Obsidian 本地知识库收尾

- Status: complete
- 解决的问题：把阶段 20 的每个 Phase 以本地 Obsidian 草稿形式沉淀，补齐阶段页、阶段汇报索引、首页和阶段索引，便于用户复盘与面试表达。
- 在 RAG 链路中的位置：本地知识管理层；不影响运行时代码、不进入 Git 提交范围。
- 为什么现在做：开发、测试和普通文档已经完成，符合“阶段 20 开发过程中暂不写 Obsidian，全部完成后统一补齐”的要求。

完成工作：

- 创建 `obsidian-vault/阶段汇报/阶段 20 - 中文检索默认链路落地与评测判定增强/`。
- 新增阶段 20 Phase 汇报索引。
- 新增 Phase 0 到 Phase 10 共 11 篇小汇报；每篇均包含 10 项固定小节。
- 新增 `obsidian-vault/阶段/阶段 20 - 中文检索默认链路落地与评测判定增强.md`。
- 更新 `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`。
- 修正 Obsidian 阶段 19 页状态为已完成并合并。

验证结果：

```text
阶段 20 汇报目录文件数：12（索引 + Phase 0-10）
Phase 0-10 小汇报 10 项标题检查：全部 ok
git check-ignore -v obsidian-vault/...
.gitignore:32:obsidian-vault/
```

Phase 9 结论：

- Obsidian 本地知识库已同步阶段 20。
- `obsidian-vault/` 仍被 Git 忽略，不应纳入提交范围。

### Phase 10: 人工核验待提交状态

- Status: complete
- 解决的问题：在结束前确认阶段 20 已停在用户人工核验前状态，没有执行提交、tag、push 或 PR，也没有把敏感信息/受限全文写入可提交文件。
- 在 RAG 链路中的位置：发布前审计层；不改业务逻辑，只核对工作区、报告、测试和安全边界。
- 为什么现在做：开发、测试、普通文档和 Obsidian 均已完成，必须用最终检查把状态固定为“可人工核验但未提交”。

完成工作：

- 检查当前分支、最近提交、阶段 19 tag/main 状态。
- 确认 `phase-20-complete` tag 不存在。
- 确认 `git diff --cached` 为空，未执行 `git add`。
- 检查 stage20 CSV schema 和文件大小。
- 扫描 stage20 代码、文档、CSV 和 Obsidian，确认无真实 API key、Bearer token、供应商原始响应或受限全文字段。
- 确认 `obsidian-vault/` 被 `.gitignore` 排除。

验证结果：

```text
git branch --show-current
codex/phase-20-default-chain-and-eval-upgrade

git log --oneline -5
12184d7 Merge phase 19 chinese analysis and retrieval tuning
ffb4756 Complete phase 19 chinese analysis and retrieval tuning
4db90c7 Merge phase 18 corpus expansion, evaluation and quality system
c56fc62 Complete phase 18 corpus expansion, evaluation and quality system
d633b95 Merge phase 17 retrieval architecture upgrade

git rev-parse --short phase-19-complete
ffb4756

git rev-parse --verify phase-20-complete
phase-20-complete tag not found

git diff --cached --name-only
<empty>

stage20 raw/provider response scan
no raw/provider response or secret field matches in stage20 outputs

git status --short --ignored obsidian-vault
!! obsidian-vault/
```

Phase 10 结论：

- 阶段 20 已完成开发、测试、普通文档和 Obsidian 草稿。
- 当前停在用户人工核验前状态。
- 尚未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

### Current Evidence

| Evidence | Result | Status |
|---|---|---|
| Thread title | 阶段20-中文检索默认链路落地与评测判定增强 | pass |
| Goal | active | pass |
| Current branch | `codex/phase-20-default-chain-and-eval-upgrade` | pass |
| Phase 19 tag | `phase-19-complete -> ffb4756` | pass |
| Phase 19 merge | `main` contains `12184d7` | pass |
| Tag ancestry | `phase-19-complete` is ancestor of `main` | pass |
| Planning files | updated through Phase 10 | pass |
| Submit boundary | no add/commit/tag/push/PR | pass |

### Test Results

| Test | Result | Status |
|---|---|---|
| Startup git/tag/main checks | pass | pass |
| Stage 20 design test | 3 passed | pass |
| Stage 20 eval upgrade tests | 7 passed with design tests | pass |
| Stage 20 default chain decision tests | 3 passed | pass |
| Brain responsibility gate tests | 21 passed | pass |
| Stage 20 quality report + frontend tests | 7 passed | pass |
| Stage 20/API focused regression | 61 passed | pass |
| Documents/sources/decompose/vector focused regression | 67 passed | pass |
| Full test suite | 424 passed | pass |
| Final quality report + frontend tests | 7 passed | pass |
| Phase 8 doc consistency tests | 10 passed | pass |
| Obsidian 10-item checks | pass | pass |
| Final manual-verification audit | pass | pass |

### Error Log

| Error | Attempt | Resolution |
|---|---|---|
| none | - | - |

### Residual Risks

- 阶段 20 真实 Jina query 校验可能因本地 `.env`、网络或 provider 状态失败；必须显式记录 skipped/error。
- 默认链路已决定不切换且回归通过；剩余风险是人工核验时重点确认是否接受 `keep_existing_hybrid` 决策解释。
- `responsibility_gate` 已有正反例和全量回归，剩余风险是后续新增责任类问法时可能需要扩展触发模式。
- 真实 Jina query 校验依赖本地 `.env` 与网络状态，本次结果已记录为 completed，但它不能成为 CI 或全量测试前提。

### Current State

- 尚未执行 `git add`。
- 尚未执行 `git commit`。
- 尚未创建 `phase-20-complete` tag。
- 尚未 push。
- 尚未创建 PR。
- 当前状态：阶段 20 已完成，等待用户人工核验；尚未提交、尚未打 tag、尚未推送。

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | 阶段 20 已完成，停在人工核验前状态 |
| Where am I going? | Phase 1 设计文档 -> Phase 2 coverage_ratio 评测升级 -> Phase 3 真实 Jina query 校验 -> Phase 4 默认链路决策 -> Phase 5 responsibility_gate -> Phase 6 quality gate -> Phase 7 回归 -> Phase 8 普通文档 -> Phase 9 Obsidian -> Phase 10 人工核验待提交 |
| What's the goal? | 完成阶段 20 开发、测试、普通文档和 Obsidian 草稿，停在人工核验前 |
| What have I learned? | 升级后的 `coverage_ratio` 与真实 Jina 都没有给默认链路切换提供足够 p@1 增益；责任边界问题可以在 Brain 生成前用独立 gate 闭环 |
| What have I done? | 完成 Phase 0-10：设计文档、评测脚本、真实 Jina 校验、默认链路决策表、`responsibility_gate`、quality summary/report、聚焦/全量回归、普通文档、Obsidian 和最终审计 |
