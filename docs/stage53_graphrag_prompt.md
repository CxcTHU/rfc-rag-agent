# Phase 53 GraphRAG 知识图谱增强检索 Goal Prompt

阅读 agent 和其他相关文件，了解项目开发进度。
现在开始阶段 53 的开发，目标是完成生产/测试配置收口、Adaptive RAG 显式包装、以及 GraphRAG 知识图谱增强检索。请为本线程设置一个 goal：

按照当前项目的 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，以及阶段 52 已完成的记忆模块语义升级和真实 API 测评，持续推进本项目开发，直到阶段 53 全部子阶段完成（配置收口、Adaptive RAG 包装、GraphRAG 实体抽取、图存储、图检索、融合集成、评测收尾），并停在用户人工核验前状态。

目标分支：

```text
codex/phase-53-graphrag
```

执行要求：

1. 首先修改当前对话线程名称为：阶段53-GraphRAG知识图谱增强检索。
2. 先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
3. 运行 `git status -sb` 和 `git log --oneline -5`，确认从 `main` 最新提交出发（Phase 52 已合并），创建新分支 `codex/phase-53-graphrag`。
4. 保留 reranker stash/分支，不触碰 reranker 工作。
5. 开发完成前不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR；必须等待用户人工核验和明确授权。
6. 严格使用 Planning with Files：每个小 Phase 开始前重读 `task_plan.md`、`findings.md`、`progress.md`；每个小 Phase 完成后先自我验收，再更新三份规划文件，之后才进入下一小 Phase。
7. 本阶段子 Phase 必须按顺序推进：

   - **Phase 53A：Prod/Test 配置收口**（前置清理，半天）
     将 `PLANNER_CHAT_MODEL_*` 在 `.env.prod` 中设为实际 LLM provider，使生产环境默认走 LLM planner 而非 DeterministicReActPlanner。确认 `conftest.py` 的 deterministic fixture 覆盖所有 planner 调用点，测试仍走 deterministic 路径。运行全量 pytest 确认无回归。

   - **Phase 53B：Adaptive RAG 显式包装**（1 天）
     在 planner 层增加 `AdaptiveRetrievalStrategy` 标签体系，将现有 planner 路由（search_knowledge / search_tables / search_figures / answer_from_prior / refuse）包装为显式的检索策略选择。在 `latency_trace` 中新增 `retrieval_strategy` 字段。补充 Adaptive RAG 相关文档，使面试时可以直接引用。不改变实际路由逻辑，只是标签化和可观测化。

   - **Phase 53C：领域实体关系 Schema + LLM 抽取**（3-4 天）
     定义 RFC/建筑规范领域的实体类型（Standard, Material, Parameter, Value, Organization, Method）和关系类型（standard_defines, standard_references, material_has_property, parameter_range, applies_to）。实现 LLM-based 实体关系抽取器，从 chunk text 中抽取结构化三元组。编写批量抽取脚本，先在 100 条 chunk 采样上验证质量，再扩展到全量。抽取结果存为 JSON。

   - **Phase 53D：知识图谱存储**（2 天）
     使用 NetworkX 构建内存知识图谱。节点为实体（带 type、chunk_ids 属性），边为关系（带 type、source_chunk_id 属性）。实现 JSON 持久化（build_graph + load_graph）。编写图统计脚本（节点数、边数、连通分量、度分布）。

   - **Phase 53E：图增强检索**（3 天）
     实现查询实体提取（从 user question 中抽取实体 mention）。实现图遍历检索（匹配实体节点 -> 1-2 hop 邻居 -> 收集关联 chunk_ids）。实现向量检索 + 图检索结果融合（去重、合并、rerank）。添加 fail-open 降级：图不可用时退回纯向量检索。

   - **Phase 53F：LangGraph 集成**（2 天）
     新增 `search_graph_knowledge` 工具/节点。planner 学习何时使用图检索（跨文档关联类问题、标准引用链类问题）。latency_trace 新增图检索相关字段（graph_entities_found、graph_chunks_retrieved、graph_retrieval_ms）。

   - **Phase 53G：评测与文档收尾**（2-3 天）
     编写 GraphRAG 评测集：30-50 条需要跨文档关联才能完整回答的问题。对比 baseline（纯向量+rerank）vs graph-enhanced，用真实 API judge 评分。输出评测 CSV 和 ablation 对照。更新全部文档，写 phase review。

8. 每开始一个小 Phase，简短说明本 Phase 解决什么问题、在 RAG 链路中的位置、为什么现在做。
9. 每完成一个小 Phase，必须运行该 Phase 的最小验收；通过后更新三份规划文件。
10. 现有测试必须仍全部通过。新增测试覆盖 GraphRAG 各组件。
11. 不得把 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk、受限全文或长期用户画像写入 Git、CSV、文档、测试或 Obsidian。
12. 阶段收尾必须运行 focused tests、全量 pytest、Stage 30 和 `git diff --check`。
13. 阶段收尾必须同步 `README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-53.md`。

核心链路：

```text
question
-> query entity extraction (LLM)
-> graph traversal (NetworkX, 1-2 hops)
-> graph chunk_ids
                              \
                               -> fusion + dedup + rerank -> answer
                              /
-> vector hybrid search (BM25 + embedding)
-> rerank (BGE-LoRA)
```

项目数据规模：

```text
documents=1146  chunks=50250
  text: 33182
  table: 1440
  image_description: 15628
```

完成标准：

- Prod 默认走 LLM planner，Test 走 deterministic，配置隔离清晰。
- Planner 路由有 Adaptive RAG 策略标签，latency_trace 可审计。
- 领域实体关系抽取覆盖 text chunk，抽取质量经人工抽检。
- NetworkX 知识图谱可构建、持久化、加载、统计。
- 图检索 + 向量检索融合可用，fail-open 降级正常。
- LangGraph 集成完成，planner 能路由到图检索。
- 评测集 30-50 条，graph-enhanced 相对 baseline 有可量化提升。
- 全量测试通过，Stage 30 仍为 A / pass。
- 最终停在人工核验前，未提交、未 tag、未 push、未 PR。
