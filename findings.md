# Findings & Decisions

## Requirements
- 用户要求持续推进到阶段 9：真实模型接入与模型评测完整完成。
- 用户要求线程名称为 `阶段9-真实模型接入与模型评测`。
- 用户要求先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/brain_workflow_design.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 用户要求确认阶段 8 已完成并合并到 `main`，确认 `phase-8-complete` tag 指向阶段 8 最终功能提交，不移动已有阶段 tag。
- 用户要求目标分支为 `codex/phase-9-real-model-evaluation`。
- 用户要求正式开发前用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 9 不做登录系统、不做部署优化、不做大规模前端重构、不做写入型 Agent 工具。
- 阶段 9 重点是真实模型配置、模型边界、向量索引重建、评测可复现和质量对比。
- 阶段 9 必须保留 deterministic provider 作为本地稳定测试默认实现，所有测试不能依赖真实 API key。
- 阶段 9 收尾必须同步普通文档和 Obsidian 本地知识库，并创建 `phase-9-complete` tag。

## Current Project Findings
- 当前线程 goal 已激活，目标为阶段 9 完整完成。
- 当前线程标题已修改为 `阶段9-真实模型接入与模型评测`。
- 起点分支为 `main`，工作区干净。
- `main` 最新提交为 `5aeed3b merge phase 8 brain workflow`，说明阶段 8 已合并。
- `phase-8-complete` 指向 `5330ba3f5e1a474892810d562b15b9a7a0bcb808`，提交信息为 `feat: complete phase 8 brain workflow`。
- 已从 `main` 创建并切换到 `codex/phase-9-real-model-evaluation`。
- 旧 `task_plan.md`、`findings.md`、`progress.md` 均为阶段 8 工作记忆，符合本阶段启动前校准要求。
- README/docs 当前仍显示阶段 8 已完成，阶段 9 收尾需要更新口径。

## Architecture Findings
- 当前项目分层为 API、Schema、Service、Agent、Brain、DB、Source Registry、Model Provider、Frontend。
- 阶段 8 已把 `/chat` 和 Agent `answer_with_citations` 收拢到 Brain workflow。
- `BrainService` 依赖 `ChatModelProvider` 和 `EmbeddingProvider`，因此阶段 9 可以增强 provider 而不改 API schema。
- `RetrievalConfig` 已有 `model_provider` 字段，但当前主要记录 chat provider，不直接创建 provider。
- `VectorSearchService` 和 `HybridSearchService` 都通过 `EmbeddingProvider` 查询 `chunk_embeddings`。
- `VectorIndexService` 已按 provider、model_name、dimension、content_hash 保存或跳过 chunk embedding。
- 因此阶段 9 的最小高价值改动是补齐真实 embedding provider 和配置入口，再扩展评测脚本对比 deterministic 与真实配置。

## Existing Code Findings
- `app/services/generation/chat_model.py` 已实现 `DeterministicChatModelProvider` 和 `OpenAICompatibleChatModelProvider`。
- `OpenAICompatibleChatModelProvider` 使用标准库 `urllib.request`，不依赖第三方 SDK，边界轻量。
- `app/services/retrieval/embedding.py` 目前只有 `DeterministicEmbeddingProvider`，`create_embedding_provider()` 只接受 provider_name。
- `.env.example` 已有 embedding provider/name/api_key/base_url 字段，但代码尚未消费 model/api_key/base_url。
- `app/core/config.py` 已有 `embedding_provider`、`embedding_model_name`、`embedding_api_key`、`embedding_base_url` 字段，但缺少 embedding timeout 和 dimension。
- `scripts/build_vector_index.py` 当前支持 `--provider`、`--limit`、`--batch-size`，还不支持 model/api_key/base_url/dimension/timeout。
- `scripts/evaluate_vector_search.py`、`scripts/evaluate_hybrid_search.py`、`scripts/evaluate_chat.py`、`scripts/evaluate_agent.py`、`scripts/evaluate_brain_workflow.py` 已支持 provider 参数或通过 settings 创建 provider，但还不能完整传入真实 embedding 配置。

## API Contract Findings
- `POST /search` 不依赖 embedding provider，是关键词 baseline。
- `POST /search/vector` 依赖当前 settings 创建的 embedding provider，并返回 provider/model_name。
- `POST /search/hybrid` 依赖 embedding provider，同时保留 keyword fallback/融合。
- `POST /chat` 通过 `CitationAnswerService` 进入 Brain workflow。
- `POST /agent/query` 通过 `AgentService` 和 `AgentToolbox` 调用 hybrid/search/chat/source 工具。
- 阶段 9 不应改变这些 API 的请求和响应结构，只增强 provider 创建和错误提示。

## Evaluation Findings
- 当前检索评测主数据集是 `data/evaluation/keyword_queries.csv`。
- 当前问答评测主数据集是 `data/evaluation/chat_queries.csv`。
- 当前 Agent 评测主数据集是 `data/evaluation/agent_queries.csv`。
- 阶段 8 已新增 `data/evaluation/brain_workflow_results.csv`，可比较 `default_hybrid`、`keyword_baseline`、`vector_only`。
- 阶段 9 应新增模型配置对比结果，至少记录 deterministic baseline；真实配置缺少 API key 时应记录 skipped，而不是让测试失败。
- 真实模型评测要复用现有评测脚本，避免另起一套不可比较指标。

## Data Source Findings
- 阶段 9 不新增外部资料来源，不改变 source registry 合规边界。
- 真实模型 API 是模型服务调用，不是文献资料来源。
- 新增的 `model_config_results.csv` 属于评测产物，不包含受限全文。

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| 新增 OpenAI-compatible embedding provider | 当前 chat 已有真实模型边界，embedding 是阶段 9 的主要缺口 |
| 继续使用标准库 HTTP | 与现有 chat provider 一致，避免引入 SDK 依赖和版本不稳定 |
| deterministic 默认不变 | 保证离线开发、自动测试、无 API key 环境都能稳定运行 |
| `create_embedding_provider()` 增加可选参数 | 兼容旧调用，同时支持真实模型配置 |
| 缺少真实模型 key 时评测跳过真实配置 | 阶段 9 要可复现，不让私密环境决定测试成败 |
| 新增模型配置评测汇总脚本 | 把 keyword/vector/hybrid/chat/agent/brain 指标聚合到一个阶段 9 结果文件 |

## Planned File Changes

| Area | Planned Files |
|------|---------------|
| 设计文档 | `docs/model_provider_evaluation.md`, `tests/test_model_provider_evaluation_design.py` |
| Embedding provider | `app/services/retrieval/embedding.py`, `tests/test_embedding_provider.py` |
| 配置入口 | `app/core/config.py`, `.env.example`, `app/api/search.py`, `app/api/chat.py`, `app/api/agent.py` |
| Vector index | `scripts/build_vector_index.py`, related tests |
| Evaluation | `scripts/evaluate_model_configs.py`, `data/evaluation/model_config_results.csv`, `tests/test_evaluate_model_configs.py` |
| Documentation | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | 阶段 9 页面、Phase 汇报、首页、阶段索引、分类页和知识点 |

## Term Explanations

| Term | Explanation |
|------|-------------|
| provider | 模型适配器。本项目用 provider 把业务代码和具体模型 API 隔开 |
| OpenAI-compatible embedding | 兼容 OpenAI `/embeddings` 格式的向量接口，输入文本，返回数字向量 |
| API key | 调用真实模型服务的密钥，只能放本地 `.env`，不能提交 |
| dimension | 向量维度，例如 1024 或 1536；索引和检索必须使用同一维度 |
| content_hash | chunk 正文的哈希，用来判断索引是否已经是最新 |
| model config evaluation | 模型配置评测，用同一批问题比较不同 provider/model 配置 |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| 暂无 | 暂无 |

## Phase 0 Findings
- 阶段 9 启动校准已完成。
- 线程标题已改为 `阶段9-真实模型接入与模型评测`。
- 阶段 8 已合并到 `main`，`phase-8-complete` tag 指向 `5330ba3`。
- 阶段 9 分支 `codex/phase-9-real-model-evaluation` 已创建。
- Planning with Files 三份文件已从阶段 8 工作记忆切换为阶段 9 工作记忆。
- 起点全量测试为 `189 passed`，说明阶段 9 从稳定的阶段 8 合并状态出发。

## Phase 1 Findings
- 新增 `docs/model_provider_evaluation.md`，固定阶段 9 的真实模型接入、provider 边界、向量索引重建、评测对比和阶段不做事项。
- 新增 `tests/test_model_provider_evaluation_design.py`，断言设计文档覆盖 `ChatModelProvider`、`EmbeddingProvider`、`OpenAICompatibleEmbeddingProvider`、配置字段、`build_vector_index`、模型评测 CSV 和 skipped config。
- Phase 1 测试结果为 `2 passed`。
- 设计结论：真实模型只接在 provider 层；业务 service 继续依赖协议；测试继续使用 deterministic 或 mock HTTP；缺少真实 API key 的评测应记录 skipped。

## Phase 2 Findings
- 新增 `OpenAICompatibleEmbeddingProvider`，支持 `model_name`、`api_key`、`base_url`、`dimension`、`timeout_seconds`。
- `OpenAICompatibleEmbeddingProvider` 调用兼容 `/embeddings` 的 HTTP endpoint，按 `data[].index` 排序并解析 embedding 向量。
- `create_embedding_provider()` 现在兼容旧的 provider_name 调用，同时支持真实 provider 的 model/key/base_url/dimension/timeout 参数。
- deterministic provider 仍是默认实现，旧测试和旧调用路径不需要配置真实 key。
- 新增/扩展 `tests/test_embedding_provider.py`，使用 monkeypatch mock `urlopen`，不访问真实网络。
- Phase 2 测试结果为 `12 passed`。

## Phase 3 Findings
- `app/core/config.py` 新增 `embedding_dimension` 和 `embedding_timeout_seconds`。
- `.env.example` 新增 `EMBEDDING_DIMENSION` 和 `EMBEDDING_TIMEOUT_SECONDS`，真实 key 仍只允许本地填写。
- `app/api/search.py`、`app/api/chat.py`、`app/api/agent.py` 的 embedding dependency 已改为传入 provider/model/api_key/base_url/dimension/timeout。
- `scripts/build_vector_index.py` 新增 `--model-name`、`--api-key`、`--base-url`、`--dimension`、`--timeout-seconds`，并在输出中标明 `content_hash=tracked`。
- 新增 `tests/test_build_vector_index.py`，覆盖 CLI 参数优先、settings fallback 和 deterministic 默认。
- Phase 3 测试结果：`tests/test_embedding_provider.py tests/test_vector_index_service.py tests/test_build_vector_index.py` 共 `20 passed`。
- 脚本 smoke run：`scripts/build_vector_index.py --limit 1 --batch-size 1` 输出 deterministic provider/model/dimension/content_hash 摘要。

## Phase 4 Findings
- 新增 `scripts/evaluate_model_configs.py`，汇总 keyword、vector、hybrid、chat、agent、brain workflow 六类评测结果。
- 新增 `tests/test_evaluate_model_configs.py`，覆盖 passed 统计、deterministic baseline、真实配置缺失 skipped、完整真实配置读取 real results dir 和 CSV 写出。
- 新增 `data/evaluation/model_config_results.csv`。
- 当前输出 12 行：deterministic baseline 6 行 completed，real_config 6 行 skipped。
- deterministic baseline 当前汇总：keyword 15/15，vector 11/15，hybrid 15/15，chat 6/6，agent 5/5，brain_workflow 12/18。
- real_config skipped 原因：本地 `.env` 未配置真实 chat/embedding provider、model、API key、base URL 和 embedding dimension。
- Phase 4 测试结果为 `6 passed`。

## Phase 5 Findings
- 复跑 keyword 评测：15/15 passed。
- 复跑 vector 评测：11/15 passed，仍有 4 个 keyword_only_pass，符合 deterministic embedding 既有基线。
- 复跑 hybrid 评测：15/15 passed，rescued_vector=4，regressed_keyword=0。
- 复跑 chat 评测：6/6 passed，refused=1，citation_failures=0。
- 复跑 agent 评测：5/5 passed，refused=1，tool_failures=0，citation_failures=0。
- 复跑 brain workflow 评测：18 runs，default_hybrid 4/6，keyword_baseline 6/6，vector_only 2/6，总计 12/18 passed。
- 复跑 source metrics：total_sources=125，merged_duplicates=14。
- 复跑 model config 评测：12 rows；deterministic baseline completed，real_config 因缺少真实模型配置 skipped。
- API 回归测试：`tests/test_search_api.py tests/test_vector_search_api.py tests/test_chat_api.py tests/test_agent_api.py` 共 16 passed。
- 全量测试：205 passed。
- 当前质量结论：阶段 9 没有改变 deterministic baseline；真实模型通道已实现和可评测，但本地未配置真实 API key，因此真实配置暂未运行，风险和成本需用户本地配置后再量化。
- 推荐默认配置：本地开发和自动化测试继续 deterministic；需要真实效果评估时，显式配置 OpenAI-compatible chat/embedding 并重建对应 provider/model/dimension 的向量索引。

## Phase 6 Findings
- README 已同步阶段 9 当前状态、真实模型配置入口、向量索引重建命令、模型配置评测结果和默认推荐。
- `docs/progress.md` 已记录阶段 9 完成内容、验证结果、遗留问题、下一阶段方向和面试表达。
- `docs/architecture.md` 已补充真实模型 provider 边界、OpenAI-compatible embedding、索引重建和模型配置评测数据流。
- `docs/data_sources.md` 已说明阶段 9 不新增外部资料来源；真实模型 API 属于模型服务调用，`model_config_results.csv` 属于评测产物。
- `AGENT.MD` 已校准到阶段 0 到阶段 9 完成后的项目状态，并保留下一阶段候选方向。
- Obsidian 本地知识库已补齐阶段 9 阶段页、阶段汇报索引、Phase 0 到 Phase 6 的小 Phase 汇报、首页/阶段索引/阶段汇报索引和 3 篇知识点。
- Obsidian Phase 汇报已逐篇检查，每篇均包含用户要求的 10 个栏目。
- 阶段 9 最终验证结论：deterministic provider 仍是默认配置，真实 chat/embedding 通道已接入到 provider 和评测边界；本地缺少真实模型密钥时，真实配置以 skipped 记录，不影响测试和评测可复现。
- Phase 6 最终验证结果：`scripts/evaluate_model_configs.py --include-real-config` 输出 12 行，deterministic completed、real_config skipped；全量测试 `205 passed`。

## Resources
- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/brain_workflow_design.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `.env.example`
- `app/core/config.py`
- `app/services/generation/chat_model.py`
- `app/services/retrieval/embedding.py`
- `app/services/retrieval/vector_index.py`
- `app/services/retrieval/vector_search.py`
- `app/services/retrieval/hybrid_search.py`
- `app/services/brain/service.py`
- `scripts/build_vector_index.py`
- `scripts/evaluate_vector_search.py`
- `scripts/evaluate_hybrid_search.py`
- `scripts/evaluate_chat.py`
- `scripts/evaluate_agent.py`
- `scripts/evaluate_brain_workflow.py`

## Current Hypotheses
- 如果先补齐 OpenAI-compatible embedding provider，再扩展索引脚本和评测脚本，阶段 9 可以最小改动实现真实模型接入闭环。
- 真实 chat provider 已存在，阶段 9 主要需要文档和评测层把它纳入模型配置对比。
- 真实 embedding 一旦改变 provider/model/dimension，必须重建向量索引，否则 vector/hybrid 搜索会查不到对应 provider/model 的 embedding。
- 阶段 9 应把“缺少真实 API key”的情况设计成可解释跳过，而不是报错中断。
