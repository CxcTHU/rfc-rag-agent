# 阶段 53 Progress：GraphRAG 知识图谱增强检索

## 2026-06-24 启动

- 设置线程 goal：完成阶段 53 开发，并在不确定或需要用户决策时停下来确认。
- 按入口要求读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 运行 `git status -sb`：`main...origin/main`，工作区干净。
- 运行 `git log --oneline -5`，确认 Phase 52 默认 reranker 链路已合并到 `main`。
- 首次读取 `docs/stage53_graphrag_prompt.md` 失败；随后通过 `git rev-list --objects --all` 找到 blob 并读取阶段 53 prompt。
- 已将线程标题改为：阶段53-GraphRAG知识图谱增强检索。
- 已创建并切换分支：`codex/phase-53-graphrag`。
- 已恢复 `docs/stage53_graphrag_prompt.md`。
- 已将 Planning with Files 三件套切换为阶段 53 计划。
- Phase 53A focused tests 首轮通过：`53 passed in 50.87s`。
- prod compose 配置检查通过：带本地 placeholder 的 `docker compose -f docker-compose.prod.yml config --quiet` 无输出、退出码 0。
- 首次全量 pytest 使用 `.venv` 因缺 `PIL/Pillow` 中断；`pyproject.toml` 已声明 `Pillow>=10.4.0`，已在 `.venv` 中补装 `Pillow-12.2.0`。
- 第二次全量 pytest 暴露 3 个图片分析测试失败：本地视觉 provider 环境污染导致 deterministic vision test-mode refusal 没生效。已把 `VISION_MODEL_*` 纳入 `tests/conftest.py` 清空列表。
- 失败用例重跑通过：`9 passed in 2.05s`。
- Phase 53A 全量验收通过：`1207 passed, 1 skipped, 1 warning in 227.16s`。

## 2026-06-24 Phase 53A 完成

完成内容：

- `.env.example` 将生产 planner provider/model 显式收口为 `openai-compatible` / `deepseek-v4-flash`，但不写入真实密钥。
- `docker-compose.prod.yml` 要求 `PLANNER_CHAT_MODEL_PROVIDER`、`PLANNER_CHAT_MODEL_NAME`、`PLANNER_CHAT_MODEL_API_KEY`、`PLANNER_CHAT_MODEL_BASE_URL` 来自本地 `.env.prod`。
- `tests/conftest.py` 清空 `PLANNER_CHAT_MODEL_*` 和 `VISION_MODEL_*`，测试保持 deterministic。
- `docs/deployment_guide.md` 更新生产 planner 与测试隔离说明。
- 新增/更新测试覆盖生产配置与测试隔离。

## 当前阶段

Phase 53B：Adaptive RAG 显式包装。

本 Phase 解决 planner 动作“做了什么检索策略”不够显式的问题。它位于 LangGraph/ReAct planner 与 retrieval tool 之间，只给既有路由补策略标签和 trace，不改变实际路由逻辑，为后续 GraphRAG 策略选择打审计基础。

## 2026-06-24 Phase 53B 完成

完成内容：

- 新增 `app/services/agent/adaptive_retrieval.py`，定义 `AdaptiveRetrievalStrategy` 与既有 planner action 的映射。
- `LatencyTrace` 新增默认字段 `retrieval_strategy=none`。
- ReAct 和 LangGraph planner 在选出 action 后记录 `retrieval_strategy`。
- LangGraph prior evidence 直接回答会标记为 `answer_from_prior_evidence`。
- 新增 `docs/stage53_adaptive_rag_graphrag.md`。
- 新增/更新 tests 覆盖 Adaptive RAG 映射和 trace。

验收：

```text
python -m pytest tests/test_phase53_adaptive_rag.py tests/test_phase50_langgraph_nodes.py tests/test_react_agent_service.py tests/test_phase50_langgraph_planner.py -q
-> 36 passed in 5.22s
```

## 当前阶段

Phase 53C：领域实体关系 Schema + LLM 抽取。

本 Phase 解决 GraphRAG 的输入问题：先把 chunk text 中的标准、材料、参数、数值、组织、方法和它们的关系抽成结构化三元组。它位于图存储和图检索之前，是后续 NetworkX graph 的数据来源。

## 2026-06-24 Phase 53C 完成

完成内容：
- 新增 `app/services/graphrag/schema.py`，定义实体/关系类型白名单、实体规范化、结果序列化和去重。
- 新增 `app/services/graphrag/extractor.py`，默认 deterministic 抽取，显式 `execute_llm=True` 才调用 chat model provider。
- 新增 `scripts/extract_phase53_graphrag_triples.py`，支持 100 条 chunk 采样和 JSON 输出；输出不包含完整 chunk、provider 原始响应、hidden reasoning 或密钥。
- 新增 `tests/test_phase53_graphrag_extraction.py`，覆盖 schema、规则抽取、fake LLM 抽取、批量输出安全边界。
- 更新 `docs/stage53_adaptive_rag_graphrag.md`，记录 53C schema、脚本用法和安全边界。

验收：
```text
python -m pytest tests/test_phase53_graphrag_extraction.py tests/test_phase53_adaptive_rag.py tests/test_phase50_langgraph_nodes.py tests/test_react_agent_service.py tests/test_phase50_langgraph_planner.py -q
-> 40 passed in 5.09s
```

## 当前阶段

Phase 53D：NetworkX 知识图谱存储。

本 Phase 将 53C 的实体和关系抽取结果构建为可持久化、可加载、可统计的内存知识图谱，为后续图增强检索提供稳定图数据结构。

## 2026-06-24 Phase 53D 完成

完成内容：
- 新增 `app/services/graphrag/graph_store.py`，使用 NetworkX `MultiDiGraph` 构建知识图谱。
- 节点含 `type`、`chunk_ids`、`name`、`normalized_name`、`mentions`；边含 `type`、`source_chunk_id` 和可选短 evidence。
- 图 JSON 持久化可重复 round-trip，避免使用 pickle。
- 新增 `scripts/build_phase53_graphrag_graph.py`，从 53C extraction JSON 构建图并输出统计。
- 新增 `tests/test_phase53_graphrag_graph_store.py`。
- `pyproject.toml` 新增 `networkx>=3.4.0`，本地 `.venv` 已安装 `networkx-3.6.1`。
- 更新 `docs/stage53_adaptive_rag_graphrag.md`，记录图 JSON 格式和统计脚本。

验收：
```text
python -m pytest tests/test_phase53_graphrag_graph_store.py tests/test_phase53_graphrag_extraction.py tests/test_phase53_adaptive_rag.py tests/test_phase50_langgraph_nodes.py tests/test_react_agent_service.py tests/test_phase50_langgraph_planner.py -q
-> 43 passed in 5.43s
```

## 当前阶段

Phase 53E：图增强检索。

本 Phase 在不破坏既有 hybrid/vector 检索的前提下，增加基于查询实体的 1-2 hop 图遍历和关联 chunk 收集，并在图不可用时 fail-open 回退。

## 2026-06-24 Phase 53E 完成

完成内容：
- 新增 `app/services/graphrag/graph_search.py`，实现图实体匹配、1-2 hop 遍历、graph chunk 收集和 hybrid 融合。
- 图增强检索保持 fail-open：图缺失或异常时返回既有 hybrid 检索结果。
- `LatencyTrace` 新增 graph search 摘要字段：latency、available、fallback、error、entity count、candidate chunk count、hop count。
- 新增 `tests/test_phase53_graph_enhanced_search.py`，覆盖遍历、融合去重、fail-open 与 trace。
- 更新 `docs/stage53_adaptive_rag_graphrag.md`，记录 53E 图增强检索行为。

验收：
```text
python -m pytest tests/test_phase53_graph_enhanced_search.py tests/test_phase53_graphrag_graph_store.py tests/test_phase53_graphrag_extraction.py tests/test_phase53_adaptive_rag.py tests/test_phase50_langgraph_nodes.py tests/test_react_agent_service.py tests/test_phase50_langgraph_planner.py -q
-> 47 passed in 6.24s
```

## 当前阶段

Phase 53F：LangGraph 集成。

本 Phase 将 graph-enhanced retrieval 暴露为 agent 工具/节点，并让 planner 能为跨文档关联和标准引用链问题选择图检索，同时保持 SSE/API 响应契约与脱敏 trace。

## 2026-06-24 Phase 53F 完成

完成内容：
- 新增 `search_graph_knowledge` ReAct action、Adaptive RAG `graph_enhanced_search` 标签、AgentToolbox 工具方法、LangGraph 节点和 builder route。
- Deterministic planner 对跨文档关系、标准引用链和知识图谱请求路由到 graph-enhanced retrieval。
- 图工具沿用 53E fail-open 行为，图缺失时回退 hybrid，并在 latency trace 记录脱敏 graph 摘要字段。
- 更新 LangGraph builder/nodes/planner tests 与 Adaptive RAG tests。
- 更新 `docs/stage53_adaptive_rag_graphrag.md`，记录 53F 集成面。

验收：
```text
python -m pytest tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_phase53_adaptive_rag.py tests/test_phase53_graph_enhanced_search.py tests/test_phase50_langgraph_planner.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_react_agent_service.py -q
-> 99 passed in 59.97s
```

## 当前阶段

Phase 53G：评测与文档收尾。

本 Phase 构建 GraphRAG 评测资产，跑阶段收尾测试门禁，并同步 README、AGENT、架构、数据源和 phase review 文档。

## 2026-06-24 Phase 53G 完成

完成内容：
- 新增 `data/evaluation/phase53_graphrag_queries.csv`，共 30 条 GraphRAG dry-run ablation cases。
- 新增 `scripts/evaluate_phase53_graphrag_ablation.py`，生成 results、summary、ablation CSV。
- 生成 `data/evaluation/phase53_graphrag_ablation_results.csv`、`phase53_graphrag_ablation_summary.csv`、`phase53_graphrag_ablation.csv`。
- 新增 `tests/test_phase53_graphrag_eval.py`。
- 同步 `README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-53.md`。

最终验收：
```text
python scripts/evaluate_phase53_graphrag_ablation.py
-> phase53_graphrag_ablation cases=30

python -m pytest tests/test_phase53_graphrag_eval.py tests/test_phase53_graph_enhanced_search.py tests/test_phase53_graphrag_graph_store.py tests/test_phase53_graphrag_extraction.py tests/test_phase53_adaptive_rag.py tests/test_phase50_langgraph_planner.py tests/test_phase50_langgraph_nodes.py tests/test_phase50_langgraph_builder.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_react_agent_service.py -q
-> 108 passed in 65.01s

python -m pytest -q
-> 1226 passed, 1 skipped, 1 warning in 237.07s

python scripts/score_stage30_quality.py
-> stage30 quality score overall=91.52 grade=A release_decision=pass

git diff --check
-> passed; CRLF conversion warnings only
```

## 当前阶段

阶段 53 开发已完成，停在用户人工核验前。

## 当前边界

- 不执行 `git add`、commit、tag、push、PR。
- 不触碰 reranker stash/分支。
- 不打印或写入真实密钥、Bearer token、供应商原始响应、完整 chunk 或受限全文。
