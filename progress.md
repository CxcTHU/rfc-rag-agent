# Progress Log

## Session: 2026-06-06

### Phase 0: 阶段 9 启动与规划校准
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 从阶段 8 已完成并合并到 `main` 的稳定状态出发。
  - 建立阶段 9 真实模型接入与模型评测开发的正确分支、文档和工作记忆。
  - 将 Planning with Files 三份文件重写为阶段 9 工作记忆。
- Actions taken:
  - 使用 `get_goal` 确认当前线程 goal 已激活，目标为阶段 9 完整完成。
  - 使用 Codex 线程工具将当前线程标题修改为 `阶段9-真实模型接入与模型评测`。
  - 使用 Planning with Files 技能并阅读其规则。
  - 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/brain_workflow_design.md`。
  - 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认它们记录阶段 8 工作记忆。
  - 运行 Planning with Files session catchup 检查，未发现需要恢复的额外输出。
  - 检查 Git 工作区，起点为 `main` 且无未提交改动。
  - 确认 `main` 最新提交为 `5aeed3b merge phase 8 brain workflow`。
  - 确认 `phase-8-complete` 指向 `5330ba3f5e1a474892810d562b15b9a7a0bcb808`，提交信息为 `feat: complete phase 8 brain workflow`。
  - 确认目标分支 `codex/phase-9-real-model-evaluation` 此前不存在。
  - 从 `main` 创建并切换到 `codex/phase-9-real-model-evaluation`。
  - 阅读现有 `EmbeddingProvider`、`ChatModelProvider`、`VectorIndexService`、`build_vector_index.py`、`.env.example` 和相关测试。
  - 将 `task_plan.md`、`findings.md`、`progress.md` 重写为阶段 9 工作记忆。
  - 运行阶段 9 起点全量测试，结果为 189 passed。
- Files created/modified:
  - `task_plan.md` rewritten for Stage 9
  - `findings.md` rewritten for Stage 9
  - `progress.md` rewritten for Stage 9

### Phase 1: 模型边界复核与阶段 9 设计文档
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 先用文档固定真实模型接入、provider 边界、索引重建、评测对比和阶段不做事项。
  - 明确 deterministic provider 与 OpenAI-compatible provider 的职责。
  - 为后续 embedding provider 和评测脚本实现提供可测试边界。
- Actions taken:
  - 新增 `docs/model_provider_evaluation.md`，说明真实模型 provider 边界、配置字段、向量索引重建、评测对比和阶段不做事项。
  - 新增 `tests/test_model_provider_evaluation_design.py`，断言设计文档覆盖阶段 9 关键边界。
  - 运行阶段 9 设计文档测试，结果为 2 passed。
- Files created/modified:
  - `docs/model_provider_evaluation.md`
  - `tests/test_model_provider_evaluation_design.py`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 2: OpenAI-compatible EmbeddingProvider
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 补齐真实 embedding provider 适配层。
  - 让真实向量模型能够通过 `EmbeddingProvider` 协议进入 vector index、vector search、hybrid search 和 Brain workflow。
  - 保持 deterministic provider 默认不变，测试不访问真实网络。
- Actions taken:
  - 扩展 `app/services/retrieval/embedding.py`，新增 `OpenAICompatibleEmbeddingProvider`。
  - 支持 OpenAI-compatible `/embeddings` 请求、响应解析、数量校验和维度校验。
  - 保留 deterministic provider 默认行为。
  - 扩展 `create_embedding_provider()`，支持 provider/model/api_key/base_url/dimension/timeout 可选参数。
  - 扩展 `tests/test_embedding_provider.py`，用 monkeypatch mock HTTP，不访问真实网络。
  - 运行 embedding provider 测试，结果为 12 passed。
- Files created/modified:
  - `app/services/retrieval/embedding.py`
  - `tests/test_embedding_provider.py`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 3: 配置入口与向量索引脚本增强
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 把 Phase 2 新增的真实 embedding provider 接入 `.env`、API 依赖和索引脚本。
  - 让向量索引构建可以显式选择 provider、model、dimension 和真实 API 配置。
  - 保持旧命令默认 deterministic 不变。
- Actions taken:
  - 更新 `app/core/config.py`，新增 embedding dimension 和 timeout 配置。
  - 更新 `.env.example`，补齐真实 embedding 配置字段。
  - 更新 search/chat/agent API 的 embedding provider dependency，让它们消费 provider/model/api_key/base_url/dimension/timeout。
  - 增强 `scripts/build_vector_index.py`，支持真实 embedding provider CLI 参数，并输出 provider/model/dimension/content_hash 摘要。
  - 新增 `tests/test_build_vector_index.py`。
  - 运行 embedding/index/script 相关测试，结果为 20 passed。
  - 运行 `scripts/build_vector_index.py --limit 1 --batch-size 1`，默认 deterministic 路径正常输出。
- Files created/modified:
  - `app/core/config.py`
  - `.env.example`
  - `app/api/search.py`
  - `app/api/chat.py`
  - `app/api/agent.py`
  - `scripts/build_vector_index.py`
  - `tests/test_build_vector_index.py`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 4: 模型评测对比脚本
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 新增一个阶段 9 汇总评测入口，记录 deterministic baseline 和可选真实模型配置。
  - 真实模型缺少 API key 时记录 skipped，不影响本地测试。
  - 输出模型配置对比 CSV，作为阶段 9 质量结论依据。
- Actions taken:
  - 新增 `scripts/evaluate_model_configs.py`，汇总六类评测结果，并支持真实模型配置 skipped/real results dir。
  - 新增 `tests/test_evaluate_model_configs.py`。
  - 运行模型配置评测脚本测试，结果为 6 passed。
  - 运行 `scripts/evaluate_model_configs.py --include-real-config`，生成 `data/evaluation/model_config_results.csv`。
  - 当前 deterministic baseline 指标：keyword 15/15，vector 11/15，hybrid 15/15，chat 6/6，agent 5/5，brain_workflow 12/18。
  - 当前 real_config 因缺少真实模型环境变量被记录为 skipped。
- Files created/modified:
  - `scripts/evaluate_model_configs.py`
  - `tests/test_evaluate_model_configs.py`
  - `data/evaluation/model_config_results.csv`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 5: 回归验证与阶段 9 评测运行
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 复跑阶段 9 要求的所有评测和回归测试。
  - 记录真实模型接入后的当前质量结论和 skipped 状态。
  - 确认现有 API contract 没有被 provider 改造破坏。
- Actions taken:
  - 复跑 keyword、vector、hybrid、chat、agent、brain workflow、source 和 model config 评测。
  - 运行 API 回归测试，覆盖 search/vector/hybrid/chat/agent。
  - 运行全量测试。
  - 记录阶段 9 质量结论：deterministic baseline 未退化；真实模型配置本地缺失，model config 评测按 skipped 记录。
- Files created/modified:
  - `data/evaluation/keyword_results.csv`
  - `data/evaluation/vector_results.csv`
  - `data/evaluation/hybrid_results.csv`
  - `data/evaluation/chat_results.csv`
  - `data/evaluation/agent_results.csv`
  - `data/evaluation/brain_workflow_results.csv`
  - `data/evaluation/source_registry_metrics.csv`
  - `data/evaluation/model_config_results.csv`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag
- **Status:** complete
- **Started:** 2026-06-06
- **Completed:** 2026-06-06
- Phase 目标：
  - 将阶段 9 的模型 provider、配置、评测和风险结论同步到普通文档。
  - 补齐 Obsidian 本地知识库的小 Phase 汇报和阶段页。
  - 创建阶段最终提交和 `phase-9-complete` tag。
- Actions taken:
  - 更新 README，补充阶段 9 当前状态、真实模型配置、向量索引重建、模型配置评测结果和默认推荐。
  - 更新 `docs/progress.md`，记录阶段 9 完成内容、验证结果、遗留问题、下一阶段方向和面试表达。
  - 更新 `docs/architecture.md`，补充真实模型 provider、OpenAI-compatible embedding、索引重建和模型配置评测数据流。
  - 更新 `docs/data_sources.md`，说明阶段 9 不新增外部资料来源，真实模型 API 不属于资料来源，模型配置 CSV 属于评测产物。
  - 更新 `AGENT.MD`，将项目状态校准到阶段 9 完成后，并保留下一阶段候选方向。
  - 统一补齐 Obsidian 本地知识库：阶段 9 阶段页、阶段汇报索引、Phase 0 到 Phase 6 汇报、首页/阶段索引/阶段汇报索引和 3 篇知识点。
  - 检查 Obsidian 阶段 9 的 7 篇 Phase 汇报，每篇均包含 10 个固定栏目。
  - 复跑阶段 9 模型配置评测：12 rows；deterministic baseline completed，real_config 因缺少真实模型配置 skipped。
  - 复跑全量测试：205 passed。
- Files created/modified:
  - `README.md`
  - `docs/progress.md`
  - `docs/architecture.md`
  - `docs/data_sources.md`
  - `AGENT.MD`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
  - `obsidian-vault/阶段/阶段 9 - 真实模型接入与模型评测.md`
  - `obsidian-vault/阶段汇报/阶段 9 - 真实模型接入与模型评测/阶段 9 Phase 汇报索引.md`
  - `obsidian-vault/阶段汇报/阶段 9 - 真实模型接入与模型评测/Phase 0 - 启动与规划校准.md`
  - `obsidian-vault/阶段汇报/阶段 9 - 真实模型接入与模型评测/Phase 1 - 模型边界设计文档.md`
  - `obsidian-vault/阶段汇报/阶段 9 - 真实模型接入与模型评测/Phase 2 - OpenAI-compatible EmbeddingProvider.md`
  - `obsidian-vault/阶段汇报/阶段 9 - 真实模型接入与模型评测/Phase 3 - 配置入口与向量索引脚本.md`
  - `obsidian-vault/阶段汇报/阶段 9 - 真实模型接入与模型评测/Phase 4 - 模型配置评测脚本.md`
  - `obsidian-vault/阶段汇报/阶段 9 - 真实模型接入与模型评测/Phase 5 - 回归验证与阶段评测.md`
  - `obsidian-vault/阶段汇报/阶段 9 - 真实模型接入与模型评测/Phase 6 - 文档知识库提交与标签.md`

## Current Evidence

| Item | Evidence | Status |
|------|----------|--------|
| Goal | `get_goal` returned active stage 9 objective | pass |
| Thread title | `阶段9-真实模型接入与模型评测` | pass |
| Starting branch | `main` before switch | pass |
| Clean worktree before branch switch | `git status --short --branch` showed no changes | pass |
| Phase 8 merge | `5aeed3b merge phase 8 brain workflow` on `main` | pass |
| Phase 8 tag | `phase-8-complete -> 5330ba3f5e1a474892810d562b15b9a7a0bcb808` | pass |
| Phase 9 branch | `codex/phase-9-real-model-evaluation` created | pass |
| Planning with Files | `task_plan.md`, `findings.md`, `progress.md` now describe Stage 9 | pass |
| Startup full tests | `python -m pytest -q` | pass |
| Stage 9 docs | README, AGENT, progress, architecture and data source docs updated | pass |
| Obsidian closeout | Stage 9 page, phase report index and Phase 0-6 reports completed | pass |
| Obsidian template check | 7 phase reports each contain 10 required headings | pass |
| Final model config evaluation | deterministic completed; real_config skipped with missing env reason | pass |
| Final full tests | 205 passed | pass |

## Test Results

| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| goal check | `get_goal` | active stage 9 goal | active | pass |
| thread rename | Codex thread title | `阶段9-真实模型接入与模型评测` | renamed | pass |
| clean worktree check | `git status --short --branch` | no changes before branch switch | no changes | pass |
| phase 8 tag check | `git show phase-8-complete` | points to final phase 8 commit | `5330ba3 feat: complete phase 8 brain workflow` | pass |
| phase 9 branch check | `git switch -c codex/phase-9-real-model-evaluation` | new phase 9 branch | switched successfully | pass |
| phase 9 startup full tests | `.venv\Scripts\python.exe -m pytest -q` | existing suite remains green | 189 passed | pass |
| phase 1 design doc test | `.venv\Scripts\python.exe -m pytest tests\test_model_provider_evaluation_design.py -q` | design doc assertions pass | 2 passed | pass |
| phase 2 embedding provider tests | `.venv\Scripts\python.exe -m pytest tests\test_embedding_provider.py -q` | embedding provider assertions pass | 12 passed | pass |
| phase 3 embedding/index/script tests | `.venv\Scripts\python.exe -m pytest tests\test_embedding_provider.py tests\test_vector_index_service.py tests\test_build_vector_index.py -q` | provider/index/script assertions pass | 20 passed | pass |
| phase 3 vector index smoke | `.venv\Scripts\python.exe scripts\build_vector_index.py --limit 1 --batch-size 1` | default deterministic index command works | provider/model/dimension/content_hash summary printed | pass |
| phase 4 model config tests | `.venv\Scripts\python.exe -m pytest tests\test_evaluate_model_configs.py -q` | model config evaluation assertions pass | 6 passed | pass |
| phase 4 model config run | `.venv\Scripts\python.exe scripts\evaluate_model_configs.py --include-real-config` | model config CSV generated | 12 rows; real_config skipped | pass |
| phase 5 keyword evaluation | `.venv\Scripts\python.exe scripts\evaluate_keyword_search.py` | keyword baseline remains green | 15/15 passed | pass |
| phase 5 vector evaluation | `.venv\Scripts\python.exe scripts\evaluate_vector_search.py` | vector baseline remains reproducible | 11/15 passed | pass |
| phase 5 hybrid evaluation | `.venv\Scripts\python.exe scripts\evaluate_hybrid_search.py` | hybrid remains green | 15/15 passed | pass |
| phase 5 chat evaluation | `.venv\Scripts\python.exe scripts\evaluate_chat.py` | chat remains green | 6/6 passed | pass |
| phase 5 agent evaluation | `.venv\Scripts\python.exe scripts\evaluate_agent.py` | agent remains green | 5/5 passed | pass |
| phase 5 brain workflow evaluation | `.venv\Scripts\python.exe scripts\evaluate_brain_workflow.py` | brain workflow comparison remains stable | 18 runs; 12/18 passed | pass |
| phase 5 source evaluation | `.venv\Scripts\python.exe scripts\evaluate_sources.py` | source metrics produced | total_sources=125 | pass |
| phase 5 model config evaluation | `.venv\Scripts\python.exe scripts\evaluate_model_configs.py --include-real-config` | model config comparison produced | deterministic completed; real skipped | pass |
| phase 5 API regression | `.venv\Scripts\python.exe -m pytest tests\test_search_api.py tests\test_vector_search_api.py tests\test_chat_api.py tests\test_agent_api.py -q` | API contracts remain stable | 16 passed | pass |
| phase 5 full tests | `.venv\Scripts\python.exe -m pytest -q` | all tests pass | 205 passed | pass |
| phase 6 Obsidian template check | Phase 0-6 report heading count | 10 headings per report | 7 reports passed | pass |
| phase 6 final model config evaluation | `.venv\Scripts\python.exe scripts\evaluate_model_configs.py --include-real-config` | model config comparison remains reproducible | 12 rows; deterministic completed; real skipped | pass |
| phase 6 final full tests | `.venv\Scripts\python.exe -m pytest -q` | all tests pass after docs and closeout | 205 passed | pass |

## Error Log

| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 无 | 无 | 无 | 暂无 |

## 5-Question Reboot Check

| Question | Answer |
|----------|--------|
| Where am I? | Phase 6 complete，当前分支 `codex/phase-9-real-model-evaluation` |
| Where am I going? | 阶段 9：真实模型接入与模型评测 |
| What's the goal? | 补齐真实 chat/embedding 模型配置和评测闭环，保留 deterministic 默认，支持向量索引重建和模型配置对比 |
| What have I learned? | ChatModelProvider 已有 OpenAI-compatible 边界；EmbeddingProvider 目前只有 deterministic；VectorIndexService 已按 provider/model/dimension/content_hash 保存索引，适合扩展真实 embedding |
| What have I done? | 完成阶段 9 的真实模型 provider 接入、索引脚本配置增强、模型配置评测、回归验证、普通文档和 Obsidian 收尾；最终提交和 `phase-9-complete` tag 由 Git 验证 |
