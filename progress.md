# Progress Log

## Session: 2026-06-07

### Phase 0: 阶段启动与规划校准

- Status: complete
- 解决的问题：从阶段 13 完成并合并后的 `main` 起步，把当前线程、分支、tag 和规划文件切换到阶段 14。
- 在 RAG 链路中的位置：阶段启动前置工作，确保真实 embedding 对比、回答覆盖校准和 Decompose provenance 可读化基于最新 Brain、Decompose 和评测边界推进。
- 为什么现在做：阶段 13 已解决复杂问题证据合并，但 deterministic answer 不能证明真实 Answer Coverage，真实 embedding 与 provenance 可读化也仍需要阶段化校准。
- 已完成工作：
  - 将线程标题修改为 `阶段14-真实Embedding与回答覆盖校准`。
  - 阅读 Planning with Files 技能说明。
  - 读取并确认当前 Git 状态、`main`、`phase-13-complete` 和最近提交。
  - 确认 `main` 当前为 `27b25d3 Merge phase 13 decompose evidence merge`。
  - 确认 `phase-13-complete -> 69a28cd`，不移动已有阶段 tag。
  - 从阶段 13 合并后的 `main` 创建并切换到 `codex/phase-14-real-quality-calibration`。
  - 阅读阶段 14 启动所需文档、阶段 12 审阅报告、阶段 13 Decompose 文档、旧规划文件和关键代码入口。
  - 用 Planning with Files 重写阶段 14 的 `task_plan.md`、`findings.md`、`progress.md`。
- 验证结果：
  - 当前分支已切换到阶段 14 分支。
  - 阶段 13 tag 已确认。
  - Planning catchup 脚本不存在，已记录并改用当前 Git/文档状态恢复上下文。
  - 起点全量测试通过：`.venv\Scripts\python.exe -m pytest -q` -> `257 passed`。

## Current Evidence

| Evidence | Result | Status |
|---|---|---|
| Thread title | `阶段14-真实Embedding与回答覆盖校准` | pass |
| Starting branch | `main` tracking `origin/main` before branch creation | pass |
| Main merge | `27b25d3 Merge phase 13 decompose evidence merge` | pass |
| Phase 13 tag | `phase-13-complete -> 69a28cd` | pass |
| Stage 14 branch | `codex/phase-14-real-quality-calibration` created | pass |
| Planning files | Rewritten for stage 14 | pass |
| Baseline tests | `.venv\Scripts\python.exe -m pytest -q` -> `257 passed` | pass |

## Test Results

| Test | Expected | Actual | Status |
|---|---|---|---|
| Phase 0 baseline tests | Full suite passes | 257 passed | pass |
| Phase 1 design tests | Stage 14 design document covers artifacts, rubric, skip rules and boundaries | 3 passed | pass |
| Phase 2 embedding comparison tests | Stage 14 embedding comparison script handles completed, skipped and failed query summary | 6 passed | pass |
| Phase 2 embedding comparison run | `stage14_embedding_comparison.csv` generated | 14 rows; deterministic completed; real_config missing_results | pass |
| Phase 3 answer coverage tests | Stage 14 answer coverage script handles review, fail, unsupported pass and real skipped rows | 6 passed | pass |
| Phase 3 answer coverage run | `stage14_answer_coverage_review.csv` generated | 20 rows; low=1, medium=9, skipped=10 | pass |
| Phase 4 decompose provenance tests | Stage 14 provenance script parses rerank explanation into evidence rows | 3 passed | pass |
| Phase 4 decompose provenance run | `stage14_decompose_provenance_review.csv` generated | 50 rows; decomposed_rows=15; both_match_rows=40 | pass |
| Phase 5 stage14/focused tests | Stage 14 scripts, Decompose, Brain, evaluation and frontend tests pass | 49 passed | pass |
| Phase 5 vector evaluation | Deterministic vector baseline remains honest | 13/15 passed | pass |
| Phase 5 hybrid evaluation | Deterministic hybrid remains stable | 15/15 passed, rescued_vector=2, regressed_keyword=0 | pass |
| Phase 5 user question evaluation | Explicit deterministic user question baseline recorded | 25/30 passed, refusal_matched=30/30, source_hit_matched=25/30 | pass |
| Phase 5 decompose evaluation | Deterministic all-user Decompose remains stable | 10/10 passed | pass |
| Phase 5 chat evaluation | Deterministic chat remains stable | 6/6 passed | pass |
| Phase 5 agent evaluation | Deterministic Agent remains stable | 5/5 passed | pass |
| Phase 5 brain workflow evaluation | Deterministic Brain workflow remains stable | 18/18 passed | pass |
| Phase 5 API/frontend tests | API and frontend compatibility pass | 28 passed | pass |
| Phase 5 core service tests | Retrieval, generation, brain, agent and source services pass | 75 passed | pass |
| Phase 6 Obsidian section check | Phase 0-6 reports each contain 10 fixed sections | 7/7 files passed | pass |
| Phase 6 Obsidian git ignore check | Obsidian remains local-only | `!! obsidian-vault/` | pass |
| Phase 6 final full tests | Full suite passes | 275 passed | pass |

## Error Log

| Error | Attempt | Resolution |
|---|---|---|
| Planning with Files session catchup script not found | Tried `C:\Users\admin\.claude\skills\planning-with-files\scripts\session-catchup.py` | Not blocking; restored context by reading Git state, required docs, planning files and code |
| Stage 14 design test wording mismatch | Initial test expected exact boundary phrases not present in the document | Updated doc boundary wording; reran test to `3 passed` |
| real_config result files missing | Local settings include real embedding config, but `data/evaluation/stage14_real/*.csv` files are absent | Script writes `missing_results` rows instead of fake pass values |
| real user question result file missing | `data/evaluation/stage14_real/user_question_results.csv` is absent | Script writes `real_config` skipped rows instead of fake real model coverage |
| Explicit deterministic user question baseline differs from stage 13 latest record | Forced deterministic run is 25/30 while phase 13 docs mention 29/30 | Stage 14 records this as a quality boundary: deterministic baseline is stable but weaker than prior default/real-config-influenced result |

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | Phase 0 of stage 14: startup, planning and baseline verification |
| Where am I going? | Toward real embedding comparison, Answer Coverage calibration, Decompose provenance readability, regression, docs, Obsidian, commit and `phase-14-complete` |
| What's the goal? | Complete stage 14: Real Embedding and answer coverage calibration |
| What have I learned? | Stage 13 is merged; deterministic baseline is stable but cannot prove real Answer Coverage; existing scripts already provide most inputs for stage 14 |
| What have I done? | Renamed thread, confirmed main/tag, created branch, rewrote planning files for stage 14 |

### Phase 1: 阶段 14 设计文档与评测口径固化

- Status: complete
- 解决的问题：阶段 14 同时涉及真实 embedding、真实/人工回答覆盖审阅和 Decompose provenance，如果没有先固定口径，后续脚本容易把真实 API 失败、deterministic baseline 和人工审阅混在一起。
- 在 RAG 链路中的位置：这是检索与回答质量校准的设计层，位于正式实现 embedding comparison、coverage review 和 provenance 可读化之前。
- 为什么现在做：阶段 13 已完成 Decompose 证据合并，阶段 14 要判断真实配置和回答覆盖质量，必须先明确可复现产物、skip 规则和 API 兼容边界。
- 完成工作：
  - 新增 `docs/stage14_real_quality_calibration.md`。
  - 明确真实 embedding 对比和 Answer Coverage 校准的输入、字段、流程和完成标准。
  - 明确 graceful skip 规则：真实 API 缺失、限流、超时、余额不足或维度不匹配不能伪造成成功。
  - 明确 Decompose provenance / rerank explanation 优先落在评测 CSV 或只读最小展示，不改变旧 API schema。
  - 新增 `tests/test_stage14_real_quality_calibration.py`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage14_real_quality_calibration.py -q` -> `3 passed`。

### Phase 2: 真实 Embedding 对比脚本与结果表

- Status: complete
- 解决的问题：阶段 14 需要明确比较 deterministic baseline 和真实 embedding 配置，但真实 API 或真实结果文件不一定存在，不能把缺失伪造成成功。
- 在 RAG 链路中的位置：位于 chunk_embeddings / vector / hybrid / Decompose / Brain 评测结果之上，把多套 suite 汇总为可对比质量表。
- 为什么现在做：Answer Coverage 校准之前，需要先知道检索侧 baseline 和真实配置状态，尤其要保留 vector-only 与用户问题失败边界。
- 完成工作：
  - 新增 `scripts/evaluate_stage14_embedding_comparison.py`。
  - 新增 `tests/test_evaluate_stage14_embedding_comparison.py`。
  - 生成 `data/evaluation/stage14_embedding_comparison.csv`。
  - 汇总 deterministic baseline：vector、hybrid、user_questions、decompose、chat、agent、brain_workflow。
  - 支持 `--include-real-config` 和 `--real-results-dir`。
  - 真实 embedding 配置缺失时输出 skipped；配置完整但结果文件缺失时输出 missing_results。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_evaluate_stage14_embedding_comparison.py -q` -> `6 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_stage14_embedding_comparison.py --include-real-config` -> `14 rows`。
  - deterministic baseline：vector `13/15`，hybrid `15/15`，user_questions `29/30`，decompose `10/10`，chat `6/6`，agent `5/5`，brain_workflow `18/18`。
  - real_config：当前为 `missing_results`，因为 `data/evaluation/stage14_real/` 中尚无阶段 14 真实结果 CSV。

### Phase 3: Answer Coverage 校准结果表

- Status: complete
- 解决的问题：来源命中和引用有效不等于回答覆盖，阶段 14 需要把 Answer Coverage、Faithfulness 和 Citation Quality 拆成可审阅字段。
- 在 RAG 链路中的位置：位于 Brain/chat/user question 结果之后，用于判断回答质量是否足以支撑阶段结论。
- 为什么现在做：阶段 12 已证明 deterministic answer 不能证明真实语言覆盖度；阶段 13 提升了证据覆盖后，需要把回答覆盖校准结构化。
- 完成工作：
  - 新增 `scripts/evaluate_stage14_answer_coverage.py`。
  - 新增 `tests/test_evaluate_stage14_answer_coverage.py`。
  - 生成 `data/evaluation/stage14_answer_coverage_review.csv`。
  - 默认读取 `user_question_results.csv` 的 `default_hybrid` 行，结合 `user_questions.csv` 和 `stage13_decompose_results.csv` 输出校准表。
  - 支持 `--include-real-config`；真实 user question 结果文件缺失时写 skipped。
  - deterministic answer 覆盖度默认标为 `review`，unsupported 正确拒答标为 `low/pass`。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_evaluate_stage14_answer_coverage.py -q` -> `6 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_stage14_answer_coverage.py --include-real-config` -> `20 rows`。
  - 风险统计：`low=1`，`medium=9`，`skipped=10`。

### Phase 4: Decompose Provenance 与 Rerank Explanation 可读化

- Status: complete
- 解决的问题：阶段 13 的 `rerank_explanations` 已有解释信息，但多条证据挤在一个长字段里，不利于人工审阅和指标对比。
- 在 RAG 链路中的位置：位于 Decompose 评测结果之后，把合并证据、provenance 和 rerank 解释变成证据级审阅表。
- 为什么现在做：阶段 14 要解释真实 embedding 和回答覆盖校准结论，必须能看清每条 evidence 为什么进入上下文。
- 完成工作：
  - 新增 `scripts/evaluate_stage14_decompose_provenance.py`。
  - 新增 `tests/test_evaluate_stage14_decompose_provenance.py`。
  - 生成 `data/evaluation/stage14_decompose_provenance_review.csv`。
  - 将 `sub_queries`、`topic_terms`、`both_match`、`source_type`、`raw_score`、`final_score`、`deduplicated_count` 拆成字段。
  - 判断前端暂不需要修改：现有 API schema 未变，CSV 已满足只读审阅需求。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_evaluate_stage14_decompose_provenance.py -q` -> `3 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_stage14_decompose_provenance.py` -> `50 evidence rows, decomposed_rows=15, both_match_rows=40`。

### Phase 5: 阶段 14 回归验证与质量结论

- Status: complete
- 解决的问题：确认阶段 14 新增设计、脚本和 CSV 不破坏既有检索、问答、Agent、Brain workflow、source 和前端入口。
- 在 RAG 链路中的位置：这是实现和文档收尾之间的质量门，负责把阶段 14 的可运行性和质量结论固定下来。
- 为什么现在做：阶段 14 的核心产物已经生成，必须先复跑评测和聚焦测试，再进入普通文档、Obsidian 和 tag 收尾。
- 完成工作：
  - 复跑阶段 14 新增脚本测试和 Decompose/Brain/evaluation/frontend 聚焦测试。
  - 显式 deterministic 复跑 vector、hybrid、user questions、decompose、chat、agent、Brain workflow。
  - 复跑 API/frontend 兼容测试和核心 service 测试。
  - 重新生成阶段 14 embedding comparison、answer coverage review 和 decompose provenance review。
- 验证结果：
  - `.venv\Scripts\python.exe -m pytest tests\test_stage14_real_quality_calibration.py tests\test_evaluate_stage14_embedding_comparison.py tests\test_evaluate_stage14_answer_coverage.py tests\test_evaluate_stage14_decompose_provenance.py tests\test_evaluate_decompose.py tests\test_decompose_retrieval.py tests\test_brain_service.py tests\test_evaluate_user_questions.py tests\test_evaluate_brain_workflow.py tests\test_frontend_app.py -q` -> `49 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_vector_search.py --provider deterministic --skip-index-build` -> `13/15 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py --provider deterministic` -> `15/15 passed`，`rescued_vector=2`，`regressed_keyword=0`。
  - `.venv\Scripts\python.exe scripts\evaluate_user_questions.py --embedding-provider deterministic` -> `25/30 passed`，`refusal_matched=30/30`，`source_hit_matched=25/30`。
  - `.venv\Scripts\python.exe scripts\evaluate_decompose.py --embedding-provider deterministic --include-all` -> `10/10 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_chat.py --embedding-provider deterministic` -> `6/6 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_agent.py --embedding-provider deterministic` -> `5/5 passed`。
  - `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py --embedding-provider deterministic` -> `18/18 passed`。
  - API/frontend 聚焦测试 -> `28 passed`。
  - 核心 service 聚焦测试 -> `75 passed`。

### Phase 6: 普通文档、Obsidian、最终测试、提交与 tag

- Status: complete, pending final commit and tag
- 解决的问题：把阶段 14 的代码、评测、普通文档、Obsidian 本地知识库和 Git 阶段锚点统一收口。
- 在 RAG 链路中的位置：这是质量校准进入下一阶段前的验收层，负责让代码、评测产物、文档和知识库对齐。
- 为什么现在做：阶段 14 的脚本、结果表和回归验证已完成，必须在创建阶段 tag 前完成文档和最终验证。
- 已完成工作：
  - 更新 `README.md`，补充阶段 14 能力、评测结果、使用边界和下一阶段建议。
  - 更新 `docs/progress.md`，记录阶段 14 完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
  - 更新 `docs/architecture.md`，补充 embedding comparison、Answer Coverage review 和 Decompose provenance review 数据流。
  - 更新 `docs/data_sources.md`，说明阶段 14 只新增评测/审阅产物，不新增资料来源、不保存受限全文或 API key。
  - 更新 `AGENT.MD`，把后续起点校准为阶段 14 完成后的阶段 15。
  - 补齐 Obsidian 阶段 14 阶段页、阶段汇报目录、Phase 0-6 小 Phase 汇报、阶段汇报索引、阶段索引、首页、分类页和知识点页。
  - 校验 Obsidian Phase 0-6 汇报均包含 10 个固定小节。
  - 确认 `obsidian-vault/` 仍被 Git 忽略，不纳入提交。
  - 运行最终全量测试。
- 验证结果：
  - Obsidian Phase 0-6 汇报 10 小节检查：`7/7` 通过。
  - `git status --short --ignored obsidian-vault` -> `!! obsidian-vault/`。
  - `.venv\Scripts\python.exe -m pytest -q` -> `275 passed`。
  - 普通文档已同步 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD`。
  - 阶段 14 本地知识库已同步，且 `obsidian-vault/` 保持 Git 忽略。
