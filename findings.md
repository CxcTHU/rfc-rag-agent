# Findings & Decisions

## Requirements

- 用户要求持续推进到阶段 10：真实 RAG 质量校准与拒答边界优化完整完成。
- 线程标题已修改为 `阶段10-真实RAG质量校准与拒答边界优化`。
- 目标分支为 `codex/phase-10-rag-quality-calibration`。
- 阶段 10 必须从阶段 9.1 已完成并合并到 `main` 的状态出发。
- 必须确认 `phase-9-complete` 与 `phase-9.1-complete` 指向各自最终提交，不移动已有 tag。
- 阶段 10 不做登录系统、不做部署优化、不做大规模前端重构、不做写入型 Agent 工具、不扩展新模型 provider、不引入复杂 LangGraph workflow。
- 阶段 10 重点是真实 RAG 质量校准、检索证据置信度、拒答边界和可复现评测。
- 开发阶段不写 Obsidian 小 Phase 汇报，收尾时统一补齐。

## Current Project Findings

- 当前 goal 已激活，目标为阶段 10 完整完成。
- 当前工作区已切换到 `codex/phase-10-rag-quality-calibration`。
- `main` 最新合并提交为 `2528deb merge phase 9.1 real model evaluation`。
- `phase-9-complete` 指向 `9bdc8b015a6b8c03cee949c0b03376ce81bd55ea`。
- `phase-9.1-complete` 指向 `12d0443953a0a4c004975d98600d86ca16d9ba22`。
- 阶段 10 起点全量测试为 `208 passed`，完成当前开发后全量测试为 `216 passed`。

## Architecture Findings

- 阶段 8 已把 `/chat` 与 Agent `answer_with_citations` 收敛到 `BrainService`，因此阶段 10 的质量保护优先放在 Brain 层。
- `BrainService.retrieve()` 支持 `auto`、`vector`、`keyword`、`hybrid`；阶段 10 在生成前加入证据判断，不改变基础 search API schema。
- `build_retrieval_outcome()` 仍按 `min_score` 过滤结果；阶段 10 新增的 evidence confidence 处理“有结果但证据不足”的场景。
- `chunk_embeddings` 按 provider/model/dimension/content_hash 区分索引，Jina 1024 维索引与 deterministic 64 维索引可以并存。
- `OpenAICompatibleChatModelProvider` 与 `OpenAICompatibleEmbeddingProvider` 已能支持 MIMO 与 Jina，本阶段不需要扩展 provider。

## Existing Code Findings

- `app/services/retrieval/vector_search.py` 原本只按 cosine score 排序，容易在 vector-only 场景召回语义相近但主题偏移的片段。
- `app/services/retrieval/keyword_search.py` 已有领域词扩展与泛词降权，可复用于 topic anchor rerank。
- `app/services/retrieval/hybrid_search.py` 保留 `keyword_score` 与 `vector_score`，适合做 baseline 对比。
- `app/services/brain/workflow.py` 新增 `EvidenceConfidence`、`evaluate_evidence_confidence()`、`extract_evidence_terms()` 等证据判断工具。
- `app/services/brain/service.py` 在 `_generate_answer_step()` 中调用证据判断，低证据时返回默认拒答并跳过真实模型调用。

## API Contract Findings

- `POST /search`、`POST /search/vector`、`POST /search/hybrid` 仍只负责返回检索结果，不承担问答拒答。
- `POST /chat` 响应已有 `refused`、`refusal_reason`、`sources`、`citations` 字段，可以表达低证据拒答。
- `POST /agent/query` 通过 Agent toolbox 复用 Brain 引用问答，因此 Brain 低证据保护会覆盖 Agent 问答工具。
- 阶段 10 未新增 API 响应必填字段，避免破坏现有前端和测试。

## Evaluation Findings

- 阶段 9 deterministic baseline：keyword 15/15、vector 11/15、hybrid 15/15、chat 6/6、agent 5/5、Brain workflow 12/18。
- 阶段 9.1 真实 Jina + MIMO：Jina vector 14/15、Jina hybrid 15/15、MIMO + Jina chat 6/6、agent 5/5、Brain workflow 15/18。
- 阶段 9.1 的真实 Brain workflow 失败项包括：
  - `vector_only/filling_capacity`：未拒答，但召回主题偏向 elastic modulus / mesoscale。
  - `default_hybrid/unsupported`：乱字符串 unsupported query 仍生成回答。
  - `vector_only/unsupported`：同一 unsupported query 仍生成回答。
- 阶段 10 deterministic 结果：
  - vector 13/15
  - hybrid 15/15
  - chat 6/6
  - agent 5/5
  - Brain workflow 18/18
  - full tests 216 passed
- 阶段 10 真实模型校准结果：
  - Jina vector 15/15
  - Jina hybrid 15/15
  - MIMO + Jina chat 6/6
  - MIMO + Jina agent 5/5
  - MIMO + Jina Brain workflow 18/18

## Data Source Findings

- 阶段 10 不新增外部文献资料来源，不改变 source registry 合规边界。
- Jina 与 MIMO 是模型服务，不是文献资料来源。
- 真实 API key 只允许存在本地 `.env`，不能写入文档、CSV、测试或 Obsidian。
- 阶段 10 新增的 CSV 只保存问题、结果、来源标题、片段摘要、分数和诊断，不保存密钥或受限全文。

## Technical Decisions

| Decision | Reason |
|---|---|
| 质量保护优先放在 Brain 层 | `/chat` 与 Agent 引用问答共享 Brain workflow |
| 不改变基础 search API schema | 阶段 10 是 RAG 问答质量校准，不是检索 API 重构 |
| 不把 vector-only 静默 fallback 到 hybrid | vector-only 是评测 baseline，必须保留语义 |
| unsupported 使用可解释 evidence confidence 拒答 | 真实向量可能对乱字符串也返回正分结果，不能只看是否有结果 |
| topic anchor 只参与排序，不覆盖 cosine score | 保留向量结果可解释性和 baseline 可比性 |
| deterministic 用于稳定回归，真实模型用于质量校准 | 真实模型更贴近用户体验，但受网络、限流、费用和密钥影响 |

## Phase Findings

### Phase 0

- 线程标题、分支、阶段 tag、阶段 9.1 合并状态均已确认。
- 起点全量测试 `208 passed`，说明进入阶段 10 时主链路稳定。

### Phase 1

- 新增 `scripts/analyze_real_rag_failures.py`。
- 新增 `data/evaluation/real_rag_failure_cases.csv`，记录 4 条失败案例。
- 新增 `tests/test_analyze_real_rag_failures.py`，测试结果 `3 passed`。
- unsupported 根因是低证据 under-refusal；filling_capacity 根因是 vector topic drift；mesoscopic_modeling 根因是跨语言术语 gap。

### Phase 2

- 新增 Brain evidence confidence 机制。
- 第一版规则采用 query-token coverage，阈值为 `0.2`。
- 低证据拒答会清空 sources/citations，并在 workflow step 中记录拒答原因。
- 相关测试结果：Brain workflow/service/answer/chat/agent 组合测试 `31 passed`，Brain workflow evaluator 测试 `3 passed`。
- Phase 2 后 deterministic Brain workflow 从 12/18 提升到 14/18。

### Phase 3

- 新增 vector topic anchor rerank。
- `TOPIC_ANCHOR_BOOST` 试过 `0.25`，发现影响 Brain thermal_control，最终使用 `0.20`。
- deterministic vector 提升到 13/15。
- deterministic hybrid 保持 15/15，`regressed_keyword=0`。
- deterministic Brain workflow 达到 18/18。

### Phase 4

- `scripts/evaluate_model_configs.py` 新增 `failed` 与 `pass_rate` 字段。
- `tests/test_evaluate_model_configs.py` 新增 pass_rate 与 schema 断言。
- model config 结果能直接对比 deterministic 各 suite 的通过率。
- 本地 `.env` 有真实模型配置时，`--include-real-config` 会查找 `data/evaluation/real/` 预计算结果；目录缺失时标记 `missing_results`，不是模型失败。

### Phase 5

- deterministic chat：6/6。
- deterministic agent：5/5。
- deterministic Brain workflow：default_hybrid 6/6、keyword_baseline 6/6、vector_only 6/6。
- deterministic model config：keyword 15/15、vector 13/15、hybrid 15/15、chat 6/6、agent 5/5、Brain workflow 18/18。
- API 回归测试：search/vector/chat/agent 相关 `16 passed`。
- 全量测试：`216 passed`。
- 真实模型校准：
  - `stage10_jina_vector_results.csv`：15/15。
  - `stage10_jina_hybrid_results.csv`：15/15。
  - `stage10_mimo_jina_chat_results.csv`：6/6。
  - `stage10_mimo_jina_agent_results.csv`：5/5。
  - `stage10_mimo_jina_brain_workflow_results.csv`：18/18。
- 结论：真实 ChatModel 与 EmbeddingModel 对最终质量判断更有价值，但阶段回归不能默认依赖真实服务。阶段 10 的正确姿势是 deterministic 保证可复现，MIMO + Jina 作为真实体验校准。

### Phase 6

- README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 和 `AGENT.MD` 已同步阶段 10 完成状态。
- Obsidian 本地知识库已新增阶段 10 阶段页、阶段 10 Phase 汇报索引、Phase 0-6 七篇 10 项汇报和关键知识点。
- Obsidian 仍由 `.gitignore` 排除，不进入 Git 提交。
- 最终 deterministic 关键评测结果：vector 13/15，hybrid 15/15，chat 6/6，agent 5/5，Brain workflow 18/18。
- 最终全量测试结果：216 passed。
- 阶段最终提交准备完成，`phase-10-complete` 将指向阶段 10 最终功能提交。

## Term Explanations

| Term | Explanation |
|---|---|
| Evidence Confidence | 判断检索证据是否足够支撑回答的规则，不等同于模型自信 |
| 低证据拒答 | 有召回结果但结果与问题缺少足够关联时拒绝回答 |
| query-token 覆盖率 | 问题有效词在证据文本中出现的比例 |
| topic anchor | 用问题中的核心主题词约束向量候选排序的轻量信号 |
| vector topic drift | 向量召回到语义相关但主题不满足用户问题的片段 |
| 真实模型校准 | 用真实 ChatModel/EmbeddingModel 评估体验与边界，而不是替代可复现测试 |

## Issues Encountered

| Issue | Evidence | Current handling |
|---|---|---|
| unsupported query 有检索结果导致不拒答 | 阶段 9.1 Brain workflow 失败 | Brain 生成前 evidence confidence 拦截 |
| vector_only/filling_capacity 召回主题偏移 | 阶段 9.1 失败案例 | topic anchor rerank 改善候选排序 |
| `mesoscopic_modeling` 跨语言术语 gap | Phase 1 失败案例 | 阶段 10 已由真实 Jina 15/15 修复；deterministic 留作后续 query expansion 方向 |
| 真实模型评测不适合作为自动回归唯一依据 | 依赖 API key、网络、费用和供应商稳定性 | deterministic 与真实模型结果分开记录 |

## Resources

- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `docs/evaluation_plan.md`
- `docs/agent_design.md`
- `docs/brain_workflow_design.md`
- `docs/model_provider_evaluation.md`
- `data/evaluation/real_rag_failure_cases.csv`
- `data/evaluation/vector_results.csv`
- `data/evaluation/hybrid_results.csv`
- `data/evaluation/brain_workflow_results.csv`
- `data/evaluation/model_config_results.csv`
- `data/evaluation/stage10_jina_vector_results.csv`
- `data/evaluation/stage10_jina_hybrid_results.csv`
- `data/evaluation/stage10_mimo_jina_chat_results.csv`
- `data/evaluation/stage10_mimo_jina_agent_results.csv`
- `data/evaluation/stage10_mimo_jina_brain_workflow_results.csv`
