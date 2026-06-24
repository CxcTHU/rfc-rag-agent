# 阶段 53 Findings：GraphRAG 知识图谱增强检索

## 已确认事实

- 当前 `main / origin/main` 已包含 Phase 52 默认 reranker 链路合并：`29229270 Merge pull request #20 from CxcTHU/codex/phase-52-default-reranker-chain`。
- 阶段 53 目标分支已创建：`codex/phase-53-graphrag`。
- 用户指定的 `docs/stage53_graphrag_prompt.md` 不在当前 HEAD，但作为 Git blob 存在：`557f438744e2d1b0f4c842d8ba5b6ca9c849d704`。
- 阶段 53 要求严格按 53A 到 53G 顺序推进，且每个小 Phase 完成后更新 `task_plan.md`、`findings.md`、`progress.md`。

## Phase 53A 研究笔记

- 53A 的核心不是改测试行为，而是把生产 planner 配置和测试 deterministic 路径隔离清楚。
- 不能把真实 API key 写入 `.env.prod`、模板、测试或文档。若 `.env.prod` 是本地秘密文件，只能检查/调整非敏感配置；可提交文件应使用 `.env.prod.example` 或文档说明。
- 需要检查 `conftest.py` 中是否已有环境变量隔离 fixture，以及 `/agent/query mode="langgraph_agent"` 是否通过 `planner_chat_provider` 注入。
- 生产 `.env.prod` 不存在且 `.env.*` 被 gitignore；阶段 53A 采用“可提交模板 + compose 必填变量”方式收口，不创建或打印真实 `.env.prod`。
- `docker-compose.prod.yml` 已通过 placeholder 环境变量验证配置有效。
- `tests/conftest.py` 原本只清空 reranker 环境；阶段 53A 已补齐 planner 与 vision provider 清空，避免本地真实配置污染测试。

## 待确认/观察

- `.env.prod` 是否存在且是否被 gitignore；如果包含真实密钥，只做最小非输出检查，不打印内容。
- `PLANNER_CHAT_MODEL_*` 的生产实际 provider 应优先沿用现有 `CHAT_MODEL_*`/规划模型配置模式，不能凭空写入密钥。
- 当前全量测试规模较大，应先跑 Phase 53A focused tests，再跑全量 pytest。
- 全量 pytest 补齐 Pillow 后暴露本地 `VISION_MODEL_*` 环境污染风险：图片分析测试期望 deterministic vision，但真实/本地视觉配置会让路径非拒答。测试入口应同时清空 vision provider 变量，保持 CI/local regression 不触发真实视觉 API。

## Phase 53B 研究笔记

- 53B 只做标签化和可观测化，不改变 planner 既有 action 路由。
- 标签应覆盖现有 planner route：knowledge search、table search、figure search、image analysis、prior evidence answer、refuse/final answer。
- `latency_trace` 已有 `planner_model`、`planner_latency_ms` 等字段；新增 `retrieval_strategy` 应保持字符串枚举，不记录 query、chunk 或 provider 原始响应。
- 实现采用独立 `adaptive_retrieval.py`，避免把策略标签散落到具体工具中。
- ReAct runtime event 的 `agent_step` payload 可以带 `retrieval_strategy`，该字段只含枚举标签，不含 query/chunk。
- 53B focused tests 覆盖 action 映射、prior evidence strategy、LangGraph trace、ReAct trace。

## Phase 53C 研究笔记

- 53C 需要先做 schema 和 extractor，不应直接进入图存储。
- 抽取结果应是 JSON 派生物，默认 deterministic/dry-run；真实 LLM 抽取必须显式开启。
- 为避免保存完整 chunk，批量脚本输出应保存 chunk_id、document_id、短 title、实体、三元组和脱敏短 error/status，不保存 chunk content 或 provider raw response。
- 实体规范化要先做轻量版本：trim、大小写/空白归一、保留原文 mention，后续图阶段再统一节点合并。
- 53C 实现采用独立 `app/services/graphrag` 包：schema 负责白名单、规范化、dict round-trip 和去重；extractor 负责 deterministic 与 LLM 两条抽取路径。
- LLM 抽取只解析 `ChatModelResult.answer` 的 JSON，不保留 `raw_response`；unsupported entity/relation types 会被丢弃。
- 批量脚本 `scripts/extract_phase53_graphrag_triples.py` 输出派生 rows，不包含 `Chunk.content`、provider 原始响应或 hidden reasoning。
- 53C focused tests 覆盖 schema 白名单、deterministic 抽取、fake LLM JSON 解析、批量脚本安全输出边界。

## Phase 53D 研究笔记

- `.venv` 初始缺少 `networkx`，阶段 53D 已将 `networkx>=3.4.0` 加入 `pyproject.toml` 并安装本地 `networkx-3.6.1`。
- 图存储使用 `nx.MultiDiGraph`，允许同一节点对之间存在多种关系；JSON 持久化采用自定义 deterministic dict，避免 pickle。
- 节点 id 使用 `type:normalized_name`，节点属性包含 `type`、`name`、`normalized_name`、`mentions`、`chunk_ids`。
- 边属性包含 `type`、`source_chunk_id` 和可选短 `evidence`；不包含 chunk 正文或 provider 原始响应。
- 图统计基于 undirected view 计算连通分量和度分布，同时输出 node/edge type counts。

## Phase 53E 研究笔记

- 图增强检索实现为 `GraphEnhancedSearchService` wrapper，不替换现有 `HybridSearchService`，因此图不可用时能 fail-open 返回既有 hybrid 结果。
- 查询实体匹配基于图节点 `name`、`normalized_name` 与 `mentions`，再对 NetworkX graph 的 undirected view 做 1-2 hop 遍历。
- 图候选 chunk 来自节点 `chunk_ids` 和边 `source_chunk_id`；融合时按 `chunk_id` 去重，对既有 hybrid 命中进行小幅 graph boost，并追加 graph-only chunks。
- `LatencyTrace` 新增 graph search 摘要字段，只记录 available/fallback/error/count/hop/latency，不记录 query、chunk 正文或 provider 原始响应。
- 53E 尚未改变 LangGraph planner 路由；工具/节点集成留到 53F。

## Phase 53F 研究笔记

- `search_graph_knowledge` 已作为只读 ReAct action 接入，映射到 AgentToolbox 的 graph-enhanced retrieval 工具。
- Adaptive RAG strategy 新增 `graph_enhanced_search`，只作为安全枚举标签进入 latency trace/runtime events。
- Deterministic planner 仅对标准引用链、跨文档关系、知识图谱、linked concept 等明显 graph-shaped query 路由到图检索；普通问题仍默认 `search_knowledge`。
- LangGraph route 为 `planner -> search_graph_knowledge -> planner`，图工具有结果后 planner 进入 `answer_with_citations`。
- API/SSE 响应契约保持不变；新增工具名只出现在 `tool_calls`/`workflow_steps`，graph trace 字段仍为脱敏 operational metadata。

## Phase 53G 研究笔记

- GraphRAG 评测资产采用 30 条 manually authored dry-run cases，覆盖 standard_reference_chain、cross_document_material_property、parameter_range、method_applies_to、organization_standard、ordinary_hybrid_baseline 和 off-topic negative。
- `scripts/evaluate_phase53_graphrag_ablation.py` 默认 dry-run，只输出策略标签、case/category、expected_delta 和安全 summary；Phase 53G 不启用真实检索执行。
- Stage 30 脚本会重写 `data/evaluation/stage30_quality_summary.csv` 与追加 `stage30_quality_scores.csv`，本轮结果仍为 `91.52 / A / pass`。
- `git diff --check` 通过；Windows 工作区仅报告 LF/CRLF conversion warnings，不是 whitespace error。
- 全量 pytest 在安装 Pillow/networkx 后通过，当前总数为 `1226 passed, 1 skipped, 1 warning`。
