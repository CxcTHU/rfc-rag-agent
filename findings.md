# Findings & Decisions（阶段 21）

## Requirements

- 阶段 21：LangGraph Agentic RAG。
- 目标分支：`claude/phase-21-langgraph-agentic-rag`。
- 阶段 21 必须从已合并阶段 20 的 `main` 出发。
- 用 LangGraph 重构 agentic 编排，只用节点包裹现有检索/Brain 服务，不重写检索内核。
- 新能力以可配置 mode 接入，不改既有默认链路与 API 契约。
- 迭代必须有硬上界防死循环。
- 不做写入型 Agent 工具、不做登录系统、不做部署优化、不新增爬虫。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不得把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。

## Git / Tag / Main 起点（已核实）

| Item | Evidence | Result |
|---|---|---|
| 当前启动分支 | `git status -sb` | `main...origin/main`，工作区干净 |
| 最近提交 | `git log --oneline -5` | `edfe9ff docs: reference goal...` → `39c06e3` → `8333d71 Merge phase 20...` → `706047d Complete phase 20...` → `12184d7 Merge phase 19...` |
| 阶段 20 tag | `git rev-parse --short phase-20-complete` | `706047d` |
| 阶段 20 tag 提交 | `git show -s --format` | `706047d Complete phase 20 default chain and eval upgrade`，非 merge |
| main 合并提交 | `8333d71 Merge phase 20 default chain and eval upgrade` | pass |
| 祖先关系 | `git merge-base --is-ancestor phase-20-complete main` | pass |
| 阶段 21 分支 | `git switch -c claude/phase-21-langgraph-agentic-rag main` | 已创建 |

结论：阶段 20 已完成并合并；`phase-20-complete` 正确指向 `706047d`；阶段 21 从正确基线启动。

## Stage 20 Findings To Carry Forward

### p@1=0.133 瓶颈

- 中文难评测集 15 题（非拒答），答案级 coverage_ratio 判定下只有 2 题 top-1 命中。
- 候选 source_type_reweight 配置能把 deep_top1 从 0.267 拉到 0.667-0.733，但 p@1 不动。
- 结论：单次 hybrid + 后处理重权的天花板已现。需要换攻法：迭代式 agentic RAG。

### keep_existing_hybrid 默认链路

- 默认链路未切换，仍是 `HybridSearchService`（keyword 0.7 + vector 0.3 + both_match_bonus 0.15）。
- `/chat` 和 Agent `answer_with_citations` 都通过 `BrainService` 复用这条链路。
- 阶段 21 不改这条默认链路；agentic 是可选新 mode。

### responsibility_gate

- 在 `BrainService._generate_answer_step()` 中，位于证据评估之前、模型生成之前。
- 命中 `RESPONSIBILITY_GATE_PATTERNS` 则返回 `RESPONSIBILITY_REFUSAL_ANSWER`。
- 阶段 21 必须在 agentic generate 节点中复用。

## 现有服务理解

### HybridSearchService

- 路径：`app/services/retrieval/hybrid_search.py`
- 输入：query + top_k
- 流程：keyword fetch(3x) + vector fetch(3x) → merge → normalize → score = kw*0.7 + vec*0.3 + bonus → sort + top_k
- 输出：`list[HybridSearchResult]`（含 document_id, chunk_id, content, heading_path, score, keyword_score, vector_score）
- 阶段 21 用法：retrieve 节点直接调用 `HybridSearchService.search()`。

### BrainService

- 路径：`app/services/brain/service.py`
- 核心方法：`answer(question, config, history) -> BrainAnswerResult`
- 流程：filter_history → rewrite_query → retrieve → optional_rerank → generate_answer
- retrieve 步骤：根据 config.retrieval_mode 选择 vector/keyword/hybrid/auto；hybrid 路径还会检查 decompose_query。
- generate_answer 步骤：responsibility_gate → 空结果拒答 → evidence_confidence → build_rag_prompt → chat_model.generate → extract_citations
- 阶段 21 用法：agentic 图不调用 BrainService.answer()，而是拆开复用其内部组件。

### workflow.py 关键组件

- `EvidenceConfidence`：证据置信度评估结果（sufficient, score, matched_terms, missing_terms）
- `evaluate_evidence_confidence(query, results)`：用 query terms 在 evidence text 中的覆盖率判断
- `has_topic_anchor(query)`：主题门，查询是否含 CORE_DOMAIN_TERMS
- `evaluate_responsibility_gate(query)`：责任边界门
- `extract_citations(answer, allowed_source_ids)`：从生成答案中提取 [n] 引用
- `build_retrieval_outcome(raw_results, mode, min_score)`：过 min_score 过滤

### DecomposeRetrievalService

- 路径：`app/services/retrieval/decompose.py`
- `decompose_query(question)` → `DecomposedQuery`：规则式分解，匹配 TOPIC_RULES + 连接词
- `DecomposeRetrievalService.retrieve()` → `DecomposeRetrievalOutcome`：分解后每条子查询独立检索，merge 去重排序
- 阶段 21 用法：rewrite 节点可选调用 decompose_query，若分解成功则对子查询分别 re-retrieve。

### DeterministicChatModelProvider

- 路径：`app/services/generation/chat_model.py`
- 用于测试和离线开发，基于规则生成答案
- 提取 user message 中 source [n] 标记，构造 `Deterministic answer based on source [n]: {question}`
- 阶段 21 图必须用此 provider 跑通全部测试。

### AgentService（现有）

- 路径：`app/services/agent/service.py`
- 功能：意图路由（answer/search/list_sources/get_source_detail）→ 调用 AgentToolbox 对应工具
- 关系：answer 意图通过 `answer_with_citations` → `CitationAnswerService` → `BrainService`
- 阶段 21 关系：agentic 图是独立的新能力，不修改 AgentService 的意图路由逻辑。

### 中文难评测集

- 路径：`data/evaluation/stage19_chinese_hard_queries.csv`
- 规模：20 题（16 非拒答 + 4 拒答）
- 实际非拒答题用于 p@1 判定：15 题（query_id 中有 19 条，但 csv 显示 20 行含 header，16 非拒答 + 4 refusal）
- 类型：cross_passage(5), confusable(5), parameter_detail(5), refusal(4)
- 每条含 expected_answer_points 用于 coverage_ratio 计算

### API 契约

必须保持不变的 endpoints：
- `POST /search` → keyword search
- `POST /search/vector` → vector search
- `POST /search/hybrid` → hybrid search
- `POST /chat` → citation-based chat (BrainService)
- `POST /agent/query` → agent with intent routing
- `GET /quality-report` → quality report HTML

## Technical Decisions

| Decision | Rationale |
|---|---|
| 新建 `app/services/agentic/` 模块 | 独立于现有 `agent/`（意图路由）和 `brain/`（单次流水线），避免污染 |
| 用 TypedDict 而非 dataclass 做 AgenticState | LangGraph 原生支持 TypedDict reducer pattern |
| 节点包裹而非重写 | 复用已验证的 HybridSearchService、evaluate_evidence_confidence、evaluate_responsibility_gate 等 |
| MAX_ITERATIONS=3 | 平衡改写重检索机会与防死循环；3 次足够覆盖 decompose + reformulate 场景 |
| generate 节点内置 responsibility_gate | 保持与 BrainService 一致的安全行为 |
| citation_check 标记不阻断 | 引用自检是质量信号，不应阻止生成结果返回 |
| agentic 作为可选 mode | 不替换默认 hybrid 链路，需评测达标才考虑接入 |
| 阶段 21 接入门槛继承阶段 20 | Δp@1≥0.10 AND Δdeep_top1≥0.20 AND refusal not degraded |

## Data Safety Decisions

- `data/app.sqlite`、`data/raw/`、`data/fulltext/`、`obsidian-vault/` 都属于本地/忽略边界。
- 阶段 21 评测结果表只保存脱敏查询、配置、指标、决策，不保存受限全文。
- 真实 API key / Bearer token 只允许存在本地 `.env` 或运行时内存中。
- LangGraph 图中不传递或存储 API credentials 到 state。

## Phase Findings

### Phase 0: 启动校准

- 已完成入口阅读、Git/tag/main 核验和阶段 21 分支创建。
- 已确认阶段 20 完整闭环：`phase-20-complete -> 706047d`，`main` 已含 `8333d71` merge。
- 已把根目录 Planning with Files 文件从阶段 20 切换为阶段 21。

### Phase 1-8: 设计、实现、测试

- 设计文档 `docs/stage21_langgraph_agentic_rag.md` 完成，覆盖状态 schema、节点图、迭代上界、确定性可测性、安全边界、接入门槛。
- `langgraph>=0.2.0` 加入 pyproject.toml。
- `app/services/agentic/` 模块完成：state.py（AgenticState + AgenticResult）, nodes.py（6 个节点 + grade_router）, graph.py（StateGraph + run_agentic_rag）。
- 19 个 agentic graph 测试全部通过（结构、节点单元、端到端、硬上界、拒答、引用自检）。
- `app/schemas/agent.py` 新增 `mode` 字段；`app/api/agent.py` 新增 agentic 路由和响应转换。
- 6 个 eval 测试通过（设计文档、pyproject、模块结构、eval 脚本、schema mode）。

### Phase 9: Agentic vs Baseline 评测

首次评测运行（2026-06-11）受 SSL 错误严重影响：

- **SSL 错误**: 从第 8 个 agentic 查询起，嵌入模型 API 连接开始出现 `[SSL: UNEXPECTED_EOF_WHILE_READING]`，导致 10/15 非拒答 agentic 查询和 4/4 拒答 agentic 查询全部失败。
- **错误处理缺陷（已修复）**: 原评测脚本在异常时默认 `refused=False`，导致：
  - errored refusal 查询被记为"未拒答"→ refusal_acc=0.000（伪）
  - errored non-refusal 查询的 coverage 被记为 0（混入正常 0）
- **修复**: 更新 `summarize_config()` 排除 errored 行参与指标计算，新增 `error_rate` 字段，`make_decision()` 在 error_rate>25% 时判定为 `inconclusive_high_error_rate`。

有效数据子集分析（5/15 non-refusal agentic + 5/15 non-refusal baseline 无错误）：
- baseline 和 agentic 在前 5 个 cross_passage 查询上表现一致（coverage_ratio 0.2-0.5，均未达 0.60 hit 阈值）
- 两者 p@1 均为 0.000，deep_top1 各有 1-2 个 hit

baseline 特殊情况：
- baseline 使用 BrainService.answer()，其内部 evidence_confidence 评估会拒答证据不足的查询
- 导致 baseline 对 8/15 非拒答查询实际执行了拒答（refused=true, 无 error）
- 这与 Phase 20 使用原始 HybridSearchService 结果不同，但对 Phase 21 内部一致对照是公平的

诚实决策：`inconclusive_high_error_rate` — 网络错误率过高，无法做可靠的接入/保留判定。agentic 图保留为候选 mode，不接入默认链路。代码和单元测试验证了 agentic 图逻辑正确（含拒答、责任门、迭代上界）。
