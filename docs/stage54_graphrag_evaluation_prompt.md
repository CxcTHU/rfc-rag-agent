# Phase 54 GraphRAG 真实数据填充与端到端评测 Goal Prompt

## 2026-06-25 Goal Update

当前 Phase 54 执行目标已按用户确认收敛为：全量 regex 铺图骨架，LLM 只对 high-value text/table chunk 做语义补充；54B 的正式 LLM 补充目标为 `2891` 条 high-value text + `1440` 条 table，已完成 `4331/4331` attempted。54C 图质量 gate 已通过。54D 已完成全量 retrieval-only、全量 answer-only 真实生成链路和 47 条 GLM-5.2 formal judge 真实评分；formal gate 已 `pass`。当前停在用户人工核验前，不执行 `git add`、commit、tag、push 或 PR。

阅读 agent 和其他相关文件，了解项目开发进度。
现在开始阶段 54 的开发，目标是用全量 regex 抽取建立知识图谱骨架，用真实 LLM 对高价值 chunk 做语义补充，并通过真实 API 端到端评测验证 GraphRAG 相对纯向量检索的提升。请为本线程设置一个 goal：

按照当前项目的 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，以及阶段 53 已完成的 GraphRAG 代码骨架（schema、extractor、graph_store、graph_search、LangGraph 集成、Adaptive RAG 标签），持续推进本项目开发，直到阶段 54 全部子阶段完成（采样验证、全量 regex 骨架、高价值 LLM 语义补充、建图质量检查、真实 API 评测、文档收尾），并停在用户人工核验前状态。

目标分支：

```text
codex/phase-54-graphrag-evaluation
```

执行要求：

1. 首先修改当前对话线程名称为：阶段54-GraphRAG真实数据与端到端评测。
2. 先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage53_adaptive_rag_graphrag.md`、`task_plan.md`、`findings.md`、`progress.md`。
3. 运行 `git status -sb` 和 `git log --oneline -5`，确认从 `main` 最新提交出发（Phase 53 已合并），创建新分支 `codex/phase-54-graphrag-evaluation`。
4. 保留 reranker stash/分支，不触碰 reranker 工作。
5. 开发完成前不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR；必须等待用户人工核验和明确授权。
6. 严格使用 Planning with Files：每个小 Phase 开始前重读 `task_plan.md`、`findings.md`、`progress.md`；每个小 Phase 完成后先自我验收，再更新三份规划文件，之后才进入下一小 Phase。
7. 本阶段子 Phase 必须按顺序推进：

   - **Phase 54A：采样抽取质量验证**（1-2 天）
     从 33182 条 text chunk 中随机采样 200 条（确保 heading_path 多样性），运行 `scripts/extract_phase53_graphrag_triples.py --execute --limit 200`，用真实 LLM 抽取三元组。**抽取 LLM 必须使用 planner chat provider（`deepseek-v4-flash`，即 `PLANNER_CHAT_MODEL_*` 配置），不要用主 chat model。** 选 flash 模型是因为抽取是高吞吐低延迟任务，33K chunk 用大模型成本不可接受。同时对相同 200 条跑 deterministic regex 抽取。对比两组结果：LLM vs regex 的 entity precision / recall、relation precision / recall。人工抽检 20 条，判断抽取质量是否达标（entity precision > 0.7, relation precision > 0.6）。如果不达标，迭代 `extractor.py` 的 LLM prompt 和后处理逻辑。输出采样质量报告 CSV。

   - **Phase 54B：全量 regex 骨架 + 高价值 LLM 语义补充**（2-3 天）
     对全部 33182 条 text chunk 跑 regex 高精度抽取（标准号引用关系、数值+单位），建立可靠图骨架。LLM 不再盲跑全部 text chunk，而是使用 `deepseek-v4-flash` planner provider 对高价值 text/table chunk 做语义补充，优先选择含 RFC/rock-filled concrete、材料、参数、标准引用、数值约束、跨文档概念、表格邻近章节的 chunk。脚本必须支持 `--resume`（中断恢复）、`--batch-size`（控制并发/速率）和候选选择策略。合并两组结果：regex 结果优先（高精度），LLM 补充 regex 难以捕获的语义关系（material_has_property、applies_to、standard_defines）。table chunk（1440 条）是高价值补充目标，应优先纳入 LLM/regex 补充。若 54C/54D 图质量或评测提升不足，再按缺口定向补抽 LLM。

   - **Phase 54C：知识图谱构建 + 质量检查**（1-2 天）
     从合并后的 extraction JSON 构建 NetworkX 知识图谱。执行实体归一化合并（同一标准号不同写法、同一材料中英文名）。输出图统计：节点数、边数、连通分量、度分布、实体类型分布、关系类型分布。质量检查：孤立节点比例 < 30%、最大连通分量覆盖 > 40% 节点。持久化 `data/knowledge_graph/domain_graph.json`（gitignore）。

   - **Phase 54D：真实 API 端到端评测**（2-3 天）
     编写 40-60 条评测用例，分类：
     - 标准引用链（"哪些标准引用了 X？"、"X 和 Y 的引用关系？"）
     - 跨文档材料属性（"C30 混凝土在不同标准中的水泥用量要求？"）
     - 参数溯源（"抗压强度测试方法在哪些标准中定义？"）
     - 多约束查询（"同时满足标准 A 和 B 对水灰比要求的材料？"）
     - 普通单文档问题（baseline 对照，图检索不应降低质量）
     - 负面样本（off-topic，图检索不应误触发）
     加载真实图数据，运行 graph-enhanced vs baseline（纯 hybrid+rerank）对比。**Judge 模型使用 GLM-5.2**（provider: `openai-compatible`, model: `GLM-5.2`, base_url: `https://llmapi.paratera.com`），API key 从 `.env` 的 `JUDGE_MODEL_API_KEY` 读取，不硬编码到代码或文档。选 GLM-5.2 做 judge 是因为它比 flash 更强，评分需要更高的理解能力。评分维度：accuracy、completeness、citation_quality，每项 1-5 分。输出 results / summary / ablation CSV。gate 标准：graph-enhanced 在跨文档关联类问题上的 completeness 和 accuracy 相对 baseline 有可量化提升，且普通问题不退化。

   - **Phase 54E：文档收尾与阶段报告**（1 天）
     更新 README、AGENT.MD、docs/progress.md、docs/architecture.md、docs/data_sources.md。写 `docs/phase_reviews/phase-54.md`。全量 pytest、Stage 30、`git diff --check`、敏感数据扫描。

8. **GPU 服务器管理**：本项目的 BGE-LoRA reranker 运行在 Paratera 平台的 GPU 服务器上，通过 SSH tunnel 访问。GPU 服务器按时计费，必须通过平台 Web UI 开关：
   - **启动**：只有 reranker-enabled 复核需要 private BGE-LoRA reranker 时，用 Chrome browser tools 打开 `https://ai.paratera.com/#/cloud/compute`，找到 `rfc-reranker-train-3090` 并启动。平台已登录，如果 session 失效则重新登录（密码自动填充）。启动后等待实例 running 状态，再建立 SSH tunnel。
   - **关闭**：评测完成后，立即回到 `https://ai.paratera.com/#/cloud/compute`，将 GPU 实例从 Web UI 关机/节省。**严禁**用 CLI 命令（`shutdown`、`poweroff`、`halt`）关闭服务器——CLI 关机只停操作系统，平台层面仍可能计费。
   - Phase 54A-54C 不需要 GPU 服务器（LLM 抽取走 Paratera 云端 chat API，不走 GPU 服务器）。formal judge 本身也不需要 GPU；GPU 只影响 reranker-enabled 复核。
9. 每开始一个小 Phase，简短说明本 Phase 解决什么问题、在 GraphRAG 链路中的位置、为什么现在做。
10. 每完成一个小 Phase，必须运行该 Phase 的最小验收；通过后更新三份规划文件。
11. 现有测试必须仍全部通过。新增测试覆盖真实图数据加载和端到端检索路径。
12. 不得把 API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 chunk、受限全文或长期用户画像写入 Git、CSV、文档、测试或 Obsidian。抽取脚本输出不保存完整 chunk content，只保存 chunk_id、document_id、短 title、entities、relations 和脱敏 metadata。
13. 阶段收尾必须运行 focused tests、全量 pytest、Stage 30 和 `git diff --check`。
14. 阶段收尾必须同步 `README.md`、`AGENT.MD`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-54.md`。

核心链路：

```text
Phase 53 code skeleton (extractor, graph_store, graph_search, LangGraph node)
    |
    v
Phase 54A: 200 chunk LLM sample -> quality validation
    |
    v
Phase 54B: 33182 text chunks -> regex skeleton
    |      high-value text/table chunks -> LLM semantic supplement
    |      regex-priority merge -> extraction JSON
    v
Phase 54C: extraction JSON -> NetworkX graph -> normalize -> persist
    |
    v
Phase 54D: real graph + real API -> graph-enhanced vs baseline -> judge -> ablation
    |
    v
Phase 54E: docs + regression + closeout
```

项目数据规模：

```text
documents=1146  chunks=50250
  text: 33182    <- 主要抽取目标
  table: 1440    <- 高价值补充目标
  image_description: 15628  <- 本阶段不抽取
```

完成标准：

- 采样 200 条抽取质量经人工抽检达标（entity precision > 0.7）。
- 全量 regex text chunk 抽取完成，高价值 text/table chunk LLM 语义补充完成，extraction JSON 输出。
- NetworkX 知识图谱构建完成，图统计合理（孤立节点 < 30%，最大连通分量 > 40%）。
- 真实 API 评测 40-60 条，graph-enhanced 在跨文档类问题上相对 baseline 有可量化提升。
- 普通单文档问题质量不退化。
- 全量测试通过，Stage 30 仍为 A / pass。
- 最终停在人工核验前，未提交、未 tag、未 push、未 PR。

## 2026-06-25 当前执行目标覆盖说明

Phase 54A/54B/54C 已完成，不再作为当前执行目标：

```text
54A sample extraction quality -> complete
54B full regex skeleton + high-value text/table LLM supplement -> complete
54C formal graph build and graph-quality gate -> complete
```

当前目标已完成：

```text
1. JUDGE_MODEL_* transient config verified.
2. preflight --require-judge passed.
3. formal --execute --limit 3 smoke passed.
4. full formal --execute --resume completed 47/47 rows.
5. summary / ablation / formal gate generated.
6. completion audit reports complete=16 / partial=0 / missing=0.
7. final-sync README / AGENT.MD / docs / planning files.
8. stop before human verification; no git add/commit/tag/push/PR.
```

当前正式评测事实：

```text
cases_total=47 pass
graph_file_exists=pass
chat_provider_configured=pass
embedding_provider_configured=pass
judge_provider_configured=pass
formal_judge_ready=pass
completed_rows=47
error_rows=0
formal_judge_scored_rows=47
graph_intent_accuracy_delta=0.1471
graph_intent_completeness_delta=0.4412
ordinary_accuracy_delta=0.0000
negative_graph_false_positive_count=0
formal_judge_gate_decision=pass
completion_audit=complete 16 / partial 0 / missing 0
```

54B residual hard-timeout 行不阻塞当前结论；若后续 reranker-enabled 复核或人工审阅显示具体覆盖缺口，再按缺口定向补抽。
