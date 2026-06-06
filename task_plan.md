# Task Plan: 阶段 9 - 真实模型接入与模型评测

## Goal
在阶段 8 Brain 中控层与 RAG Workflow 配置化已完成并合并到 `main` 的基础上，进入阶段 9：真实模型接入与模型评测。

本阶段目标是让项目具备真实 chat model 与真实 embedding model 的可配置接入能力，同时保留 deterministic provider 作为本地稳定测试默认实现。阶段 9 要把模型配置、向量索引构建、Brain workflow、keyword/vector/hybrid/chat/agent/brain 评测连接成可复现的质量对比链路，为后续默认模型选择、成本控制和部署准备提供依据。

阶段 9 不做登录系统、不做部署优化、不做大规模前端重构、不做写入型 Agent 工具。重点是真实模型配置、模型边界、向量索引重建、评测可复现和质量对比。

## Current Phase
Phase 6 complete。阶段 9 开发、评测、普通文档和 Obsidian 本地知识库收尾已完成；最终功能提交和 `phase-9-complete` tag 由 Git 验证。

## Phases

### Phase 0: 阶段 9 启动与规划校准
- [x] 将线程标题修改为 `阶段9-真实模型接入与模型评测`。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/brain_workflow_design.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其记录阶段 8 工作记忆。
- [x] 确认阶段 8 已完成并合并到 `main`。
- [x] 确认 `phase-8-complete` 指向阶段 8 最终功能提交，且不移动已有 tag。
- [x] 从阶段 8 合并后的 `main` 创建并切换到 `codex/phase-9-real-model-evaluation`。
- [x] 使用 Planning with Files 将 `task_plan.md`、`findings.md`、`progress.md` 校准为阶段 9 工作记忆。
- [x] 运行阶段 9 起点基线测试。
- **验证方式:** `get_goal`、线程标题工具结果、`git status --short --branch`、`git log --oneline --decorate -n 16`、`git show phase-8-complete`、规划文件内容检查、起点全量测试。
- **Status:** complete

### Phase 1: 模型边界复核与阶段 9 设计文档
- [x] 新增 `docs/model_provider_evaluation.md`。
- [x] 复核 `ChatModelProvider`、`EmbeddingProvider`、`RetrievalConfig`、`WorkflowConfig` 和 Brain workflow 的职责边界。
- [x] 明确 deterministic provider 与 OpenAI-compatible provider 的定位、配置字段、失败处理、成本/速度/稳定性风险。
- [x] 明确阶段 9 不让业务 service 直接依赖具体模型 SDK，不让测试依赖真实 API key。
- [x] 增加设计文档断言测试，覆盖真实模型接入、embedding provider、vector index provider/model 记录、评测对比和阶段边界。
- **验证方式:** `tests/test_model_provider_evaluation_design.py`。
- **Status:** complete

### Phase 2: OpenAI-compatible EmbeddingProvider
- [x] 扩展 `app/services/retrieval/embedding.py`，新增 OpenAI-compatible embedding provider 或等价真实 embedding 适配层。
- [x] 支持 `model_name`、`api_key`、`base_url`、`dimension`、`timeout_seconds` 等配置。
- [x] 支持 `/embeddings` endpoint，解析 OpenAI-compatible embedding 响应，校验返回数量和向量维度。
- [x] 保留 deterministic provider 作为默认实现。
- [x] 让 `create_embedding_provider()` 支持显式参数和环境配置输入，不破坏现有调用。
- [x] 增加单元测试，使用 monkeypatch/mock，不访问真实网络，不需要真实 API key。
- **验证方式:** `tests/test_embedding_provider.py`。
- **Status:** complete

### Phase 3: 配置入口与向量索引脚本增强
- [x] 更新 `app/core/config.py` 和 `.env.example`，补齐真实 chat/embedding provider 配置字段。
- [x] 更新 API 依赖和脚本，让 `create_embedding_provider` 能消费 provider/model/api_key/base_url/dimension/timeout。
- [x] 增强 `scripts/build_vector_index.py`，支持 `--provider`、`--model-name`、`--base-url`、`--api-key`、`--dimension`、`--timeout-seconds`，并输出 provider、model、dimension、content_hash 相关摘要。
- [x] 确认 `VectorIndexService` 已按 provider/model/dimension/content_hash 保存和跳过索引。
- [x] 增加脚本或 service 测试，覆盖 provider/model 切换和索引记录。
- **验证方式:** `tests/test_vector_index_service.py`、新增或扩展脚本测试。
- **Status:** complete

### Phase 4: 模型评测对比脚本
- [x] 新增 `scripts/evaluate_model_configs.py` 或等价脚本。
- [x] 支持运行 deterministic baseline 和可选真实模型配置。
- [x] 至少汇总 keyword、vector、hybrid、chat、agent、brain workflow 的关键指标。
- [x] 输出 `data/evaluation/model_config_results.csv`，记录 config 名称、provider、model、embedding 维度、测试项、通过数、总数、风险说明。
- [x] 真实模型配置缺少 API key 时不得失败；应跳过真实配置并记录 skipped reason。
- [x] 增加评测脚本测试。
- **验证方式:** `tests/test_evaluate_model_configs.py`、运行评测脚本。
- **Status:** complete

### Phase 5: 回归验证与阶段 9 评测运行
- [x] 复跑 keyword、vector、hybrid、chat、agent、brain workflow 评测。
- [x] 运行阶段 9 模型配置对比评测。
- [x] 运行相关 API 测试，确认 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query` 不被破坏。
- [x] 运行全量测试。
- [x] 记录质量变化、成本/速度/稳定性风险和推荐默认配置。
- **验证方式:** 评测脚本输出、API 测试、`python -m pytest -q`。
- **Status:** complete

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag
- [x] 更新 `README.md`，说明阶段 9 真实模型配置、向量索引、评测对比和默认推荐。
- [x] 更新 `docs/progress.md`，记录阶段 9 完成内容、验证方式、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充真实模型 provider、embedding provider、索引重建和模型评测数据流。
- [x] 更新 `docs/data_sources.md`，说明阶段 9 不新增外部资料来源，新增模型评测 CSV 是评测产物。
- [x] 判断并更新 `AGENT.MD`，将后续起点校准到阶段 9 完成后的下一步。
- [x] 统一更新 Obsidian 本地知识库：阶段 9 页、阶段汇报索引、Phase 0 到最终 Phase 汇报、分类页和知识点。
- [x] 复跑全量测试和阶段评测。
- [x] 创建阶段最终功能提交。
- [x] 创建 `phase-9-complete` tag，确保 tag 指向阶段 9 最终功能提交。
- **验证方式:** 全量测试、评测脚本、Obsidian 10 项模板检查、Git tag 检查。
- **Status:** complete

## Final Verification Targets

| Check | Expected |
|-------|----------|
| Branch | `codex/phase-9-real-model-evaluation` |
| Stage 8 tag | `phase-8-complete` remains on stage 8 final functionality commit |
| Design doc | `docs/model_provider_evaluation.md` exists and covers model/provider/evaluation boundaries |
| Embedding provider | OpenAI-compatible embedding provider implemented without changing deterministic default |
| Config docs | `.env.example` and README explain real model settings without committing secrets |
| Vector index | script supports provider/model/dimension settings and persists provider/model/dimension/content_hash |
| Evaluation | deterministic vs optional real model comparison output exists |
| Regression | search/vector/hybrid/chat/agent/brain/source/frontend tests remain green |
| Full tests | `python -m pytest -q` passes |
| Tag | `phase-9-complete` points to final phase 9 functionality commit |

## Key Questions

1. 阶段 9 是否必须真的调用线上模型？
   - 初步答案：不强制。必须实现真实模型接入边界和可复现评测；没有 API key 时应跳过真实配置，测试仍使用 deterministic provider。
2. 为什么先做 OpenAI-compatible embedding？
   - 初步答案：项目已有 OpenAI-compatible chat provider，embedding 只有 deterministic。补齐 embedding 后，vector/hybrid/Brain 评测才能比较真实语义模型效果。
3. 是否改变 `/chat` 或 `/agent/query` 响应？
   - 初步答案：不改变。阶段 9 是 provider 和评测增强，保持 API contract 稳定。
4. 是否默认切换到真实模型？
   - 初步答案：不默认。默认仍 deterministic，真实模型通过 `.env` 或 CLI 显式启用。
5. 是否提交真实 API key？
   - 初步答案：绝不提交。`.env.example` 只写字段和说明，真实 key 留在本地 `.env`。

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 目标分支为 `codex/phase-9-real-model-evaluation` | 与阶段命名和用户要求一致 |
| 从 `main` 创建阶段 9 分支 | 阶段 8 已合并到 main，符合阶段切换规则 |
| 不移动 `phase-8-complete` | 阶段 tag 必须稳定指向阶段最终功能提交 |
| deterministic 继续作为默认 provider | 保证本地测试和 CI 不依赖真实 API key |
| 真实 embedding 采用 OpenAI-compatible 边界 | 与现有 chat provider 边界一致，便于接入国产兼容 API |
| 评测脚本支持跳过真实配置 | 避免缺少密钥时阶段评测失败，同时保留真实配置入口 |

## Planned File Changes

| Area | Planned Files |
|------|---------------|
| 设计文档 | `docs/model_provider_evaluation.md`, `tests/test_model_provider_evaluation_design.py` |
| Embedding provider | `app/services/retrieval/embedding.py`, `tests/test_embedding_provider.py` |
| 配置入口 | `app/core/config.py`, `.env.example`, API provider dependencies |
| Vector index | `scripts/build_vector_index.py`, `app/services/retrieval/vector_index.py`, related tests |
| Evaluation | `scripts/evaluate_model_configs.py`, `data/evaluation/model_config_results.csv`, `tests/test_evaluate_model_configs.py` |
| Stage docs | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | `obsidian-vault/阶段/阶段 9 - 真实模型接入与模型评测.md`, phase reports, categories, knowledge notes |

## Term Explanations

| Term | Explanation |
|------|-------------|
| ChatModelProvider | 聊天模型适配层，把 prompt 发给 deterministic 或真实 chat API，并返回统一结果 |
| EmbeddingProvider | 向量模型适配层，把堆石混凝土资料片段或用户问题转换成向量 |
| OpenAI-compatible API | 使用类似 OpenAI `/chat/completions` 或 `/embeddings` 请求/响应格式的模型服务，很多国产模型平台也兼容这种格式 |
| deterministic provider | 本地确定性 provider，不访问网络，用于稳定测试和离线开发 |
| model evaluation | 模型评测，用同一批问题比较不同模型/配置的检索、回答、引用和拒答质量 |
| skipped config | 被跳过的真实模型配置，例如缺少 API key 时不运行，但在结果中记录原因 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| 无 | 0 | 暂无 |

## Notes
- 本文件由 Planning with Files 维护，是阶段 9 的工作记忆。
- 每个 Phase 完成后，必须先更新 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 9 开发过程中暂不写入 Obsidian 小 Phase 汇报；全部开发、测试和普通文档收尾完成后，再统一补齐每个 Phase 的 Obsidian 笔记。
- 阶段 9 的重点是让真实模型接入可配置、可验证、可对比，而不是把项目变成线上依赖不可控的 demo。
