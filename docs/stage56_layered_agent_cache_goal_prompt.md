# Phase 56 Goal Prompt

阅读 agent 和其他相关文件，了解项目开发进度。

现在正式进入阶段 56 的开发。请为本线程设置一个 goal：

按照当前项目的 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，以及 Phase 55“生产上线前部署闭环”和 GLM reranker fallback / provider egress forwarder 补充提交结果，持续推进本项目开发，直到阶段 56“分层语义缓存与 Agent 延迟优化”的开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。

目标分支建议为：

```text
codex/phase-56-layered-agent-cache
```

执行要求：

1. 首先修改当前对话线程名称为：阶段56-分层语义缓存与Agent延迟优化。
2. 先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`、`docs/phase55_production_readiness.md`、`docs/phase55_completion_audit.md`。
3. 运行 `git status -sb` 和 `git log --oneline -5`，确认 Phase 55 已合并到 `main / origin/main`，确认当前基线包含 `Add GLM reranker fallback` 与 provider egress forwarder 补充；保留用户已有改动，不重置 Git，不覆盖无关文件。
4. 从最新 `main` 创建或切换到 `codex/phase-56-layered-agent-cache` 分支。
5. 阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR；必须等待用户人工核验和明确确认。
6. 严格使用 Planning with Files：每个小 Phase 开始前重读 `task_plan.md`、`findings.md`、`progress.md`；每个小 Phase 完成后先自我验收，再更新三份规划文件。
7. 本阶段不做 provider/model 降级，不关闭 tool calling，不新增外部数据源，不做写入型 Agent 工具，不处理域名/HTTPS。
8. 不得读取、打印、提交或写入真实 `.env`、`.env.prod`、数据库密码、JWT secret、Redis 密码、API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 answer、完整 chunk、受限全文或长期用户画像。

Phase 56 必须按以下顺序推进：

Phase 56A：当前缓存与延迟基线审计
- 审计 Redis client、query embedding cache、answer-level Semantic Cache、LangGraph checkpoint、tool-calling service、AgentToolbox、hybrid search、pgvector/FAISS fallback、BGE/GLM rerank fallback 和 `latency_trace`。
- 用脱敏方式复现“同一问题冷/热两次仍然完整跑 Agent 链路”的现状，说明旧 Semantic Cache 为什么没有减少思考时间。

Phase 56B：缓存 identity、版本和失效策略
- 设计 retrieval/rerank/tool-result cache key：包含 cache schema version、语料/图谱版本、embedding provider/model/dim、normalized query、source/filter args、top_k/fetch_k、retrieval mode、candidate id hash、reranker provider/model/recall_k。
- 明确 PostgreSQL restore/import、FAISS refresh、GraphRAG rebuild、embedding/reranker 变更后的 invalidation 或 version bump。

Phase 56C：retrieval candidate cache
- 基于 Redis 增加检索候选缓存，缓存 chunk ids、安全分数和来源标签；请求时从 DB hydrate 内容，不把完整 chunk 作为持久缓存契约。
- 支持 Redis 不可用时 fail-open，且不破坏 pgvector HNSW 优先、FAISS fallback 的现有语义。

Phase 56D：rerank order cache
- 基于 query + candidate id list/hash + reranker identity 缓存重排顺序和安全分数。
- 区分 BGE primary 与 GLM fallback，BGE 关闭时不得误用 BGE cache。

Phase 56E：tool result cache
- 在 `tool_calling_agent` 的只读工具层增加安全 tool-result cache，覆盖 `hybrid_search_knowledge`、`search_knowledge`、`search_tables`、`search_figures` 等适合缓存的路径。
- 对 history、用户上传图片、source-filter 或不安全上下文保守 bypass；不把最终答案缓存作为主路径。

Phase 56F：answer-level cache guardrail
- 保持生产默认 `SEMANTIC_CACHE_ENABLED=false`，除非用户单独批准。
- 若保留该能力，收紧 eligibility 和 `cache_context`，纳入 corpus/version、answer strategy、provider、retrieval/rerank identity、source id set。

Phase 56G：可观测性、配置和部署说明
- 扩展 `latency_trace` / SSE metadata，显示 retrieval/rerank/tool cache hit/miss、backend、stale reason、saved_ms 估计和 cache summary。
- 更新 `.env.example`、部署文档和 Redis Stack runbook，说明 TTL、开关、flush/invalidation、fail-open。

Phase 56H：评测、测试和收尾
- 新增 focused tests 覆盖 cache key 稳定性、隐私边界、Redis fail-open、HNSW->FAISS fallback、BGE/GLM reranker identity、tool cache eligibility。
- 新增或扩展冷/热重复查询评测脚本，输出脱敏 CSV；运行 focused tests、`python scripts/score_stage30_quality.py`，如改代码路径则运行 full pytest；运行 `git diff --check` 和敏感字段扫描。
- 更新 README、AGENT.MD handoff、docs/progress.md、docs/architecture.md、docs/data_sources.md、阶段报告和本地 Obsidian 知识库。

完成标准：

- 相同或高度相似的 standalone Agent 问题第二次能命中 retrieval/rerank/tool-result 至少一层缓存，并通过 trace 证明耗时下降。
- Phase 56 的提速不依赖广泛开启最终答案 Semantic Cache。
- Redis 关闭或异常时正常回答链路 fail-open。
- HNSW/FAISS、BGE/GLM fallback 语义保持正确。
- 不泄露任何 secret、token、provider raw response、完整 answer、完整 chunk、受限全文或长期用户画像。
- 最终汇报说明当前分支、主要改动、测试结果、冷/热延迟证据、未提交状态、人工核验重点，以及用户确认后再提交/tag/push 的建议。

## Phase 56J 补充目标：证据链可观测性与动态 K 评测

用户人工核验时发现：仅显示“跳过了哪个工具”不足以解释两次同样问题为何答案证据差距明显。阶段 56 需要追加完成以下工作：

1. 保留已经完成的“跳过工具名”显示。
2. 在 Agent 思考过程或 metadata 中补齐执行工具的实际证据链：
   - 实际执行的工具名；
   - 被跳过的工具名和原因；
   - 实际传给工具的检索 query；
   - retrieval candidate chunk ids；
   - rerank cache hit/miss、fallback、fallback used、provider/model；
   - 最终进入上下文的 selected chunk ids、source title 和 source_type 预览；
   - tool-result cache hit/miss；
   - answer-level `semantic_cache_hit`。
3. 以上诊断只允许保存/展示安全元数据，不得展示完整 chunk、完整 answer、provider raw response、hidden reasoning、secret、token、受限全文或私有日志。
4. 不允许为 `GB/T`、标准、抗压强度或任何领域实体写硬编码检索规则。若需要改善 evidence selection，必须通过通用排序/阈值/诊断机制完成。
5. 增加动态 rerank K 配置：
   - `RERANKING_DYNAMIC_TOP_K_ENABLED=false` 默认关闭；
   - `RERANKING_DYNAMIC_MIN_RESULTS=4`；
   - `RERANKING_DYNAMIC_MAX_RESULTS=12`；
   - `RERANKING_DYNAMIC_RELATIVE_SCORE_THRESHOLD=0.65`；
   - `RERANKING_RECALL_K=75` 继续作为候选池大小；
   - 选择规则：先保留前 `min_results` 条基础证据，再从后续 reranked candidates 中保留 `score >= best_score * relative_threshold` 的条目，最多到 `max_results`。
6. 扩展 Phase 56 评测脚本和脱敏 CSV：除了冷/热缓存命中，还要评测证据链诊断字段是否存在、动态 K 是否按 rerank 分数返回多于固定 top_k 的 selected evidence。
7. 更新 `task_plan.md`、`findings.md`、`progress.md`、`docs/progress.md` 和阶段报告；完成 focused tests、Phase 56 eval、必要的静态检查，并继续停在用户人工核验前，不执行 `git add`、commit、tag、push 或 PR。
