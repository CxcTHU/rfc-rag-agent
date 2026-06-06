# Progress Log

## Session: 2026-06-06

### Phase 0: 阶段启动与规划校准

- Status: complete
- 解决的问题：确认阶段 9.1 已完成并合并，当前线程、分支、tag 和规划文件进入阶段 10。
- 完成工作：
  - 确认当前 goal 为阶段 10 完整完成。
  - 将线程标题修改为 `阶段10-真实RAG质量校准与拒答边界优化`。
  - 阅读阶段 10 要求的项目文档与旧规划文件。
  - 确认 `main` 最新提交为 `2528deb merge phase 9.1 real model evaluation`。
  - 确认 `phase-9-complete -> 9bdc8b0`，`phase-9.1-complete -> 12d0443`。
  - 创建并切换到 `codex/phase-10-rag-quality-calibration`。
  - 用 Planning with Files 重写阶段 10 的 `task_plan.md`、`findings.md`、`progress.md`。
- 验证结果：
  - 起点全量测试：`.venv\Scripts\python.exe -m pytest -q` -> `208 passed`。

### Phase 1: 真实 RAG 失败案例复核与质量诊断

- Status: complete
- 解决的问题：先把阶段 9.1 的真实模型失败拆成可诊断、可改进的案例。
- 完成工作：
  - 新增 `scripts/analyze_real_rag_failures.py`。
  - 新增 `tests/test_analyze_real_rag_failures.py`。
  - 生成 `data/evaluation/real_rag_failure_cases.csv`。
  - 记录 4 条失败案例：
    - `brain_vector_only_filling_capacity`: source_miss / vector_topic_drift
    - `brain_default_hybrid_unsupported`: under_refusal / unsupported_low_evidence
    - `brain_vector_only_unsupported`: under_refusal / unsupported_low_evidence
    - `vector_mesoscopic_modeling`: vector_expected_source_miss / cross_language_topic_gap
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_analyze_real_rag_failures.py -q` -> `3 passed`。
  - `.venv\Scripts\python.exe scripts\analyze_real_rag_failures.py` -> `4 failure cases written`。

### Phase 2: 检索证据置信度与低证据拒答

- Status: complete
- 解决的问题：有召回片段但证据不足时，不把片段交给真实模型硬生成。
- 完成工作：
  - 在 `app/services/brain/workflow.py` 新增 `EvidenceConfidence` 与证据判断函数。
  - 在 `app/services/brain/service.py` 的生成前加入 evidence confidence 检查。
  - 低证据时返回默认拒答、清空 sources/citations，并记录 workflow step。
  - 新增 Brain workflow 与 Brain service 测试。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_brain_workflow.py tests\test_brain_service.py tests\test_answer_service.py tests\test_chat_api.py tests\test_agent_service.py -q` -> `31 passed`。
  - `.venv\Scripts\python.exe -m pytest tests\test_evaluate_brain_workflow.py -q` -> `3 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py --embedding-provider deterministic --out data\evaluation\brain_workflow_results.csv` -> default_hybrid 5/6, keyword_baseline 6/6, vector_only 3/6。

### Phase 3: vector-only 误召回优化

- Status: complete
- 解决的问题：降低 vector-only 语义漂移，让更贴题的证据进入 top_k，同时保留 vector-only baseline 语义。
- 完成工作：
  - 在 `app/services/retrieval/vector_search.py` 新增 topic anchor rerank。
  - 复用 keyword expansion 词表计算主题锚点。
  - 保留响应中的 cosine score，topic anchor 只影响排序。
  - 新增 vector rerank 测试。
  - 将 `TOPIC_ANCHOR_BOOST` 校准为 `0.20`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_vector_search.py tests\test_vector_search_api.py tests\test_evaluate_vector_search.py tests\test_hybrid_search.py tests\test_evaluate_hybrid_search.py tests\test_brain_service.py tests\test_evaluate_brain_workflow.py -q` -> `29 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_vector_search.py --provider deterministic --skip-index-build` -> `13/15 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py --provider deterministic` -> `15/15 passed`, `regressed_keyword=0`。
  - `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py --embedding-provider deterministic --out data\evaluation\brain_workflow_results.csv` -> default_hybrid 6/6, keyword_baseline 6/6, vector_only 6/6。

### Phase 4: 评测脚本与指标对比增强

- Status: complete
- 解决的问题：让阶段 10 的指标对比更直观，能直接看到 failed 与 pass_rate。
- 完成工作：
  - `scripts/evaluate_model_configs.py` 输出新增 `failed` 与 `pass_rate`。
  - `tests/test_evaluate_model_configs.py` 增加 pass_rate 与 CSV schema 测试。
  - 重新生成 `data/evaluation/model_config_results.csv`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_evaluate_model_configs.py -q` -> `7 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_model_configs.py --include-real-config` -> `12 rows written`。

### Phase 5: 回归验证与阶段 10 质量结论

- Status: complete
- 解决的问题：确认阶段 10 改动没有破坏 search/chat/agent/brain/API 链路，并用真实模型补充校准最终质量。
- 完成工作：
  - 复跑 deterministic chat、agent、Brain workflow、model config 评测。
  - 复跑 API 回归测试。
  - 复跑全量测试。
  - 检查真实配置与 Jina 索引：MIMO/Jina 配置完整，`jina-embeddings-v3` 索引 997 条。
  - 单独输出阶段 10 真实模型校准结果，不覆盖 deterministic baseline。
- 验证结果：
  - `.venv\Scripts\python.exe scripts\evaluate_chat.py --chat-provider deterministic --embedding-provider deterministic` -> `6/6 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_agent.py --chat-provider deterministic --embedding-provider deterministic` -> `5/5 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py --chat-provider deterministic --embedding-provider deterministic --out data\evaluation\brain_workflow_results.csv` -> default_hybrid 6/6, keyword_baseline 6/6, vector_only 6/6。
  - `.venv\Scripts\python.exe scripts\evaluate_model_configs.py --include-real-config` -> deterministic keyword 15/15, vector 13/15, hybrid 15/15, chat 6/6, agent 5/5, Brain workflow 18/18。
  - `.venv\Scripts\python.exe -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py -q` -> `16 passed`。
  - `.venv\Scripts\python.exe -m pytest -q` -> `216 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_vector_search.py --provider openai-compatible --skip-index-build --out data\evaluation\stage10_jina_vector_results.csv` -> `15/15 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py --provider openai-compatible --vector-results data\evaluation\stage10_jina_vector_results.csv --out data\evaluation\stage10_jina_hybrid_results.csv` -> `15/15 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_chat.py --chat-provider openai-compatible --embedding-provider openai-compatible --out data\evaluation\stage10_mimo_jina_chat_results.csv` -> `6/6 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_agent.py --chat-provider openai-compatible --embedding-provider openai-compatible --out data\evaluation\stage10_mimo_jina_agent_results.csv` -> `5/5 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py --chat-provider openai-compatible --embedding-provider openai-compatible --out data\evaluation\stage10_mimo_jina_brain_workflow_results.csv` -> default_hybrid 6/6, keyword_baseline 6/6, vector_only 6/6。
- 质量结论：
  - 真实 ChatModel 与 EmbeddingModel 确实更适合做最终体验判断；Jina 在阶段 10 后把真实 vector 从历史 14/15 提升到 15/15，MIMO + Jina Brain workflow 从历史 15/18 提升到 18/18。
  - deterministic provider 仍应作为稳定回归基线，因为它不依赖密钥、网络、限流和余额。
  - 阶段 10 的推荐用法是：deterministic 做自动回归，真实 MIMO + Jina 做发布前质量校准。

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag

- Status: complete
- 解决的问题：把阶段 10 的代码、评测和结论同步到普通文档、本地知识库、最终提交和阶段 tag。
- 完成工作：
  - 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
  - 补齐 Obsidian 阶段 10 阶段页、阶段汇报索引、Phase 0-6 汇报和知识点。
  - 确认 Obsidian 由 Git 忽略，不纳入提交。
  - 复跑最终 deterministic 关键评测。
  - 复跑最终全量测试。
  - 准备阶段提交与 `phase-10-complete` tag。
- 验证结果：
  - `.venv\Scripts\python.exe scripts\evaluate_vector_search.py --provider deterministic --skip-index-build --out data\evaluation\vector_results.csv` -> `13/15 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py --provider deterministic --vector-results data\evaluation\vector_results.csv --out data\evaluation\hybrid_results.csv` -> `15/15 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_chat.py --chat-provider deterministic --embedding-provider deterministic --out data\evaluation\chat_results.csv` -> `6/6 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_agent.py --chat-provider deterministic --embedding-provider deterministic --out data\evaluation\agent_results.csv` -> `5/5 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py --chat-provider deterministic --embedding-provider deterministic --out data\evaluation\brain_workflow_results.csv` -> default_hybrid 6/6, keyword_baseline 6/6, vector_only 6/6。
  - `.venv\Scripts\python.exe scripts\evaluate_model_configs.py --include-real-config` -> deterministic suites completed; real_config records `missing_results` for absent precomputed real directory。
  - `.venv\Scripts\python.exe -m pytest -q` -> `216 passed`。

## Current Evidence

| Evidence | Result | Status |
|---|---|---|
| Thread title | `阶段10-真实RAG质量校准与拒答边界优化` | pass |
| Current branch | `codex/phase-10-rag-quality-calibration` | pass |
| Main merge | `2528deb merge phase 9.1 real model evaluation` | pass |
| Phase 9 tag | `phase-9-complete -> 9bdc8b0` | pass |
| Phase 9.1 tag | `phase-9.1-complete -> 12d0443` | pass |
| Phase 1 failure table | 4 real RAG failure cases generated | pass |
| Phase 2 low-evidence guard | Brain refuses unsupported token with retrieved vector results | pass |
| Phase 3 vector rerank | deterministic vector improved to 13/15 | pass |
| Phase 3 hybrid eval | deterministic hybrid remains 15/15 | pass |
| Phase 3 Brain workflow | deterministic Brain workflow reached 18/18 | pass |
| Phase 4 model config summary | failed/pass_rate fields written | pass |
| Phase 5 full tests | 216 passed | pass |
| Phase 5 real Jina vector | 15/15 | pass |
| Phase 5 real MIMO + Jina Brain | 18/18 | pass |
| Phase 6 docs | README/docs/AGENT updated | pass |
| Phase 6 Obsidian | Stage 10 page, index and 7 Phase reports written locally | pass |
| Phase 6 final tests | 216 passed | pass |

## Test Results

| Test | Expected | Actual | Status |
|---|---|---|---|
| Phase 0 baseline tests | Full suite passes | 208 passed | pass |
| Phase 1 analyzer tests | New analyzer tests pass | 3 passed | pass |
| Phase 2 Brain tests | Low-evidence guard covered | 31 passed | pass |
| Phase 2 evaluator tests | Brain evaluator tests pass | 3 passed | pass |
| Phase 3 retrieval tests | Vector rerank and related flows pass | 29 passed | pass |
| Phase 4 model config tests | pass_rate/schema covered | 7 passed | pass |
| Phase 5 API tests | search/vector/chat/agent APIs stable | 16 passed | pass |
| Phase 5 full tests | All tests pass | 216 passed | pass |
| Stage 10 Jina vector | Real vector calibration passes | 15/15 | pass |
| Stage 10 Jina hybrid | Real hybrid calibration passes | 15/15 | pass |
| Stage 10 MIMO + Jina chat | Real chat calibration passes | 6/6 | pass |
| Stage 10 MIMO + Jina agent | Real agent calibration passes | 5/5 | pass |
| Stage 10 MIMO + Jina Brain | Real Brain calibration passes | 18/18 | pass |

## Error Log

| Error | Attempt | Resolution |
|---|---|---|
| `evaluate_vector_search.py` rejected `--embedding-provider` | Used wrong argument name | Re-ran with `--provider deterministic` |
| `evaluate_hybrid_search.py` rejected `--embedding-provider` | Used wrong argument name | Re-ran with `--provider deterministic` |
| `TOPIC_ANCHOR_BOOST=0.25` regressed Brain default_hybrid thermal_control | Overweighted topic anchors | Reduced boost to `0.20` |
| PowerShell string terminator error | Used a double-quoted rg expression containing double quotes | Re-ran with safer single-quoted/simple patterns |

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | Phase 6 of stage 10: docs, Obsidian, final verification, commit, tag |
| Where am I going? | Toward `phase-10-complete` pointing to the final stage 10 functionality commit |
| What's the goal? | Complete real RAG quality calibration and refusal boundary optimization |
| What have I learned? | Deterministic regression is stable; real MIMO + Jina confirms final quality after the guard and rerank |
| What have I done? | Added failure analysis, Brain low-evidence refusal, vector topic anchor rerank, model config pass_rate, deterministic and real evaluations |
