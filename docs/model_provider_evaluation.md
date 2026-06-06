# 阶段 9 真实模型接入与模型评测设计

## 目标

阶段 9 的目标是把阶段 8 已经稳定的 Brain workflow 接到可配置的真实模型边界上，并用评测脚本比较不同模型配置的质量。

本阶段不是把业务代码绑定到某一家模型 SDK，也不是让测试依赖真实 API key。第一版继续保留 deterministic provider 作为默认实现，同时补齐 OpenAI-compatible embedding provider，让向量索引、vector search、hybrid search、chat、Agent 和 Brain workflow 都能在同一套 provider 抽象下运行。

核心链路：

```text
documents/chunks/sources
-> EmbeddingProvider / ChatModelProvider
-> build_vector_index
-> vector / hybrid retrieval
-> BrainService
-> chat / agent / brain workflow evaluation
-> deterministic 与真实模型配置对比
```

## 模型边界

### ChatModelProvider

`ChatModelProvider` 是聊天模型适配层。

当前已有两个实现：

| provider | 作用 | 是否默认 |
|----------|------|----------|
| `DeterministicChatModelProvider` | 本地规则式回答，用于测试和离线开发 | 是 |
| `OpenAICompatibleChatModelProvider` | 调用兼容 OpenAI `/chat/completions` 的真实模型服务 | 否 |

阶段 9 不重写 chat provider。它的重点是让配置说明、评测脚本和 Brain workflow 能清楚记录 chat provider 与 model name。

### EmbeddingProvider

`EmbeddingProvider` 是向量模型适配层。

阶段 9 之前只有：

```text
DeterministicEmbeddingProvider
```

阶段 9 新增：

```text
OpenAICompatibleEmbeddingProvider
```

它调用兼容 OpenAI `/embeddings` 的真实 embedding API，把资料 chunk 或用户问题转换成真实语义向量。业务代码仍然只依赖 `EmbeddingProvider` 协议，不直接依赖真实 API、SDK 或供应商名称。

## 配置字段

阶段 9 需要让 `.env.example` 和 `Settings` 覆盖真实模型所需字段：

```text
CHAT_MODEL_PROVIDER
CHAT_MODEL_NAME
CHAT_MODEL_API_KEY
CHAT_MODEL_BASE_URL
CHAT_MODEL_TEMPERATURE
CHAT_MODEL_TIMEOUT_SECONDS

EMBEDDING_PROVIDER
EMBEDDING_MODEL_NAME
EMBEDDING_API_KEY
EMBEDDING_BASE_URL
EMBEDDING_DIMENSION
EMBEDDING_TIMEOUT_SECONDS
```

默认规则：

- provider 为空时使用 deterministic。
- 真实 provider 必须显式配置 model name、API key 和 base URL。
- API key 只放在本地 `.env`，不得提交到 Git。
- 测试必须用 deterministic 或 mock HTTP，不访问真实网络。

## 向量索引重建

真实 embedding provider 会改变向量内容、维度和模型名称，因此切换 provider 后必须重建向量索引。

`chunk_embeddings` 已经保存：

```text
provider
model_name
dimension
content_hash
embedding_json
```

阶段 9 的 `scripts/build_vector_index.py` 应支持：

```text
--provider
--model-name
--base-url
--api-key
--dimension
--timeout-seconds
--limit
--batch-size
```

这样同一份 chunks 可以同时保存 deterministic 索引和真实模型索引，vector search 会按当前 provider/model/dimension 查询匹配的 embedding，不会误用旧索引。

## 评测对比

阶段 9 新增模型配置评测，目标不是让所有机器都能跑真实模型，而是让同一套脚本具备可复现对比能力。

建议新增：

```text
scripts/evaluate_model_configs.py
data/evaluation/model_config_results.csv
```

评测配置至少包含：

| config_name | chat provider | embedding provider | 行为 |
|-------------|---------------|--------------------|------|
| `deterministic_baseline` | deterministic | deterministic | 必跑，作为稳定 baseline |
| `real_config` | OpenAI-compatible | OpenAI-compatible | 有 API key 时运行，无 API key 时 skipped |

评测结果至少记录：

```text
config_name
suite
provider
model_name
dimension
passed
total
status
skipped_reason
notes
```

必须复用现有评测脚本和数据集：

```text
scripts/evaluate_keyword_search.py
scripts/evaluate_vector_search.py
scripts/evaluate_hybrid_search.py
scripts/evaluate_chat.py
scripts/evaluate_agent.py
scripts/evaluate_brain_workflow.py
```

## 风险与取舍

真实模型接入后有三类风险：

- 成本风险：每次索引和评测都会消耗模型调用额度。
- 速度风险：远程 embedding 和 chat API 比 deterministic 慢。
- 稳定性风险：网络、限流、模型更新、供应商错误都会影响结果。

阶段 9 因此保留 deterministic 默认实现，把真实模型设计成显式配置，并让评测脚本在缺少密钥时记录 skipped config，而不是失败退出。

## 阶段边界

阶段 9 不做：

- 不做登录系统。
- 不做部署优化。
- 不做大规模前端重构。
- 不做写入型 Agent 工具。
- 不让测试依赖真实 API key。
- 不把真实模型调用写进 keyword/vector/hybrid/chat/agent 的业务逻辑里。

阶段 9 要做：

- 补齐 OpenAI-compatible embedding provider。
- 完善真实模型配置说明。
- 增强向量索引脚本的 provider/model 参数。
- 新增模型配置评测输出。
- 复跑 keyword、vector、hybrid、chat、agent 和 brain workflow 评测。
- 明确推荐默认配置和真实模型风险。

## 完成标准

- `docs/model_provider_evaluation.md` 存在并覆盖 ChatModelProvider、EmbeddingProvider、OpenAI-compatible embedding、配置字段、向量索引重建、模型评测和阶段边界。
- `OpenAICompatibleEmbeddingProvider` 实现并有 mock 测试。
- deterministic provider 仍是默认实现。
- `scripts/build_vector_index.py` 支持真实 embedding provider 参数。
- 新增模型配置评测脚本和结果 CSV。
- 旧 API 和旧评测不被破坏。
- 阶段 9 收尾文档和 Obsidian 知识库完成。
