# 阶段 21：LangGraph Agentic RAG

## 目标

用 LangGraph 构建有状态 agentic RAG 编排图，通过检索 → 评估 → 改写/分解 → 重检索 → 生成 → 引用自检的迭代循环，攻克阶段 20 中文难评测集 p@1=0.133 的瓶颈。只用节点包裹现有检索/Brain 服务核心能力，不重写检索内核。新能力以可配置 mode 接入，不替换既有默认链路。

## 背景

阶段 17-20 连续四个阶段的检索微调结论均为"保持不变 / 边际增益"，已到边际收益递减区。p@1=0.133 的瓶颈表明：单次 hybrid + 后处理重权的天花板已现，需要换攻法。agentic RAG 通过自纠正循环（证据不足 → 改写查询 → 重检索 → 重评估）从迭代维度突破单次检索的局限。

## 状态 Schema

```python
from typing import TypedDict, Annotated
from operator import add

class AgenticState(TypedDict, total=False):
    # 输入
    question: str                           # 原始用户问题
    # 检索
    results: list                           # SearchResultLike 列表
    retrieval_queries: Annotated[list[str], add]  # 所有检索过的 query（含改写）
    # 评估
    evidence_sufficient: bool               # grade 节点输出
    confidence_score: float                 # evidence confidence score
    # 迭代控制
    iteration_count: int                    # 当前迭代次数（0-based）
    rewritten_query: str                    # 最新改写后的 query
    # 生成
    answer: str                             # 最终答案
    citations: list[int]                    # 提取的引用 [n]
    refused: bool                           # 是否拒答
    refusal_reason: str | None              # 拒答原因
    # 安全门
    responsibility_gate_triggered: bool     # 责任门是否命中
    # 引用自检
    invalid_citations: list[int]            # 无效引用列表
    # 工作流追踪
    workflow_steps: list                    # BrainWorkflowStepRecord 列表
    # 服务依赖（注入，不序列化）
    _db: object                             # SQLAlchemy Session
    _embedding_provider: object             # EmbeddingProvider
    _chat_model_provider: object            # ChatModelProvider
```

## 节点图

```text
START
  │
  ▼
retrieve ──→ grade ──┬── evidence_sufficient=True ──→ generate ──→ citation_check ──→ END
                      │
                      └── evidence_sufficient=False
                          │
                          ▼
                        rewrite ──→ re_retrieve ──→ grade (loop)
                          │
                          └── iteration_count >= MAX_ITERATIONS ──→ generate
```

### 节点定义

| 节点 | 输入（读 state） | 输出（写 state） | 包裹的现有服务 |
|---|---|---|---|
| `retrieve` | question | results, retrieval_queries | `HybridSearchService.search()` + `decompose_query()` |
| `grade` | question (or rewritten_query), results | evidence_sufficient, confidence_score | `evaluate_evidence_confidence()` + `has_topic_anchor()` |
| `rewrite` | question, results, iteration_count | rewritten_query, iteration_count+1 | 规则式 query reformulation + `decompose_query()` |
| `re_retrieve` | rewritten_query | results (merged), retrieval_queries | `HybridSearchService.search()` |
| `generate` | question, results, evidence_sufficient | answer, citations, refused, refusal_reason, responsibility_gate_triggered, workflow_steps | `evaluate_responsibility_gate()` + `build_rag_prompt()` + `ChatModelProvider.generate()` + `extract_citations()` |
| `citation_check` | answer, citations, results | invalid_citations | 验证 citations 对应的 source_id 在 results 中存在 |

### 条件边

| 源节点 | 条件 | 目标节点 |
|---|---|---|
| `grade` | `evidence_sufficient == True` | `generate` |
| `grade` | `evidence_sufficient == False AND iteration_count < MAX_ITERATIONS` | `rewrite` |
| `grade` | `evidence_sufficient == False AND iteration_count >= MAX_ITERATIONS` | `generate` |

## 迭代上界

- `MAX_ITERATIONS = 3`
- 迭代计数器 `iteration_count` 从 0 开始，每次 rewrite 节点 +1。
- grade 节点在 `iteration_count >= MAX_ITERATIONS` 时无条件走 generate，即使证据仍不足。
- 必须有测试强制验证：构造证据永远不足的场景，断言恰好 3 次迭代后终止。

## 确定性可测性

- 图的全部节点必须支持 `DeterministicChatModelProvider` + deterministic `EmbeddingProvider`。
- 不需要真实 API key 就能跑通所有测试。
- 测试通过构造 in-memory SQLite + 预填充 chunks + deterministic providers 来驱动图执行。

## 安全边界

- `responsibility_gate`：generate 节点内，在模型生成前执行 `evaluate_responsibility_gate()`。
- 空结果拒答：results 为空时 generate 节点返回 `DEFAULT_REFUSAL_ANSWER`。
- 低证据拒答：evidence_sufficient=False 且已达迭代上界时，generate 节点仍可基于低证据生成但标记 confidence。
- off-topic 拒答：`has_topic_anchor()` 在 grade 节点中执行。
- AgenticState 不存储 API credentials。
- 图不执行写入操作（不改数据库、不写文件）。

## 接入方式

- 新增 `app/services/agentic/` 模块，独立于 `agent/`（意图路由）和 `brain/`（单次流水线）。
- 提供 `run_agentic_rag(question, db, embedding_provider, chat_model_provider) -> AgenticResult` 入口函数。
- AgenticResult 包含 answer, citations, sources, refused, refusal_reason, workflow_steps, iteration_count, invalid_citations。
- 可通过 `/agent/query` 的 mode 参数或新增独立 endpoint 接入。
- 不替换默认 `/chat` 或 Brain hybrid 链路。

## 接入门槛

继承阶段 20 默认链路切换门槛：

```text
agentic_integration_allowed =
  delta_precision_at_1 >= 0.10
  AND delta_deep_fulltext_top1_rate >= 0.20
  AND refusal_accuracy >= baseline_refusal_accuracy
```

- baseline: keep_existing_hybrid（BrainService 默认链路）。
- agentic: LangGraph 状态图。
- 用 `data/evaluation/stage19_chinese_hard_queries.csv` 对照评测。
- 指标：coverage_ratio（答案要点覆盖率）, p@1, deep_top1。
- 达标：接入为新 mode（`agentic`）。
- 未达标：保留候选并写明阻断原因，不接入。

## 完成标准

1. 本设计文档 `docs/stage21_langgraph_agentic_rag.md` 就位。
2. `pyproject.toml` 加 `langgraph` 依赖。
3. `app/services/agentic/` 下状态图与节点实现，节点包裹现有服务。
4. agentic 图在 deterministic 下可复跑、无需真实 API。
5. 迭代上界有测试强制。
6. citations、拒答、responsibility_gate 行为保持不变，有测试覆盖。
7. agentic vs baseline 评测产出对比 CSV，诚实决策。
8. 既有 API 不被破坏（POST /search, /search/vector, /search/hybrid, /chat, /agent/query, GET /quality-report）。
9. 全量测试通过。
10. 文档（README, progress, architecture, data_sources, AGENT.MD）和 Obsidian 同步。
11. 停在人工核验前状态。
