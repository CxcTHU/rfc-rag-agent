# 阶段 23：Agentic 评测闭环与自动模式路由

## 目标

阶段 21 已经实现 LangGraph Agentic RAG，阶段 22 已经把 agentic 链路的 `workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category` 暴露到前端作为只读可观测字段。本阶段解决两个尚未闭环的问题：

```text
阶段 21 agentic 评测 inconclusive_high_error_rate
-> 隔离 SSL/供应商不稳定因素，得到可靠 agentic vs default 对照
-> 判断哪些问题值得走 agentic
-> /agent/query 未传 mode 时自动分流
-> 前端从“用户选择模式”改为“只读显示本次实际模式”
```

核心产物是一个可复现、可测试、可解释的自动路由闭环，而不是把 agentic 无条件设为默认链路。

## 范围

本阶段做：

- 隔离或修复阶段 21 agentic 评测中的 SSL/超时问题。
- 产出阶段 23 agentic vs default 的可靠对照结果，目标 `error_rate < 0.10`。
- 新增规则式问题复杂度判断函数 `classify_query_complexity`，至少区分 `simple` 与 `complex`，并输出判断依据。
- `/agent/query` 未传 `mode` 时自动分流：简单问题走 default，复杂问题走 agentic。
- `/agent/query` 显式传 `mode=default` 或 `mode=agentic` 时仍尊重用户选择，保留调试能力。
- 前端 Agent 面板把阶段 22 的 mode 下拉框改成只读状态指示器；提交时不再发送 `mode`，响应后显示 API 返回的实际 `mode`。
- 补充评测、路由、API、前端测试。
- 同步普通文档和 Obsidian 本地知识库。

本阶段不做：

- 不修改 `detect_intent` 内部规则。
- 不改变 `/chat` 默认问答链路。
- 不做登录系统、部署优化、Streaming/SSE。
- 不新增爬虫或外部资料来源。
- 不新增写入型 Agent 工具。
- 不让真实 API 成为 CI 或本地全量测试前提。

## 阶段 21 问题回顾

阶段 21 的 `scripts/evaluate_stage21_agentic_rag.py` 对比了 `baseline_hybrid` 与 `agentic_rag`，但 agentic 侧出现高错误率，最终决策为：

```text
decision = inconclusive_high_error_rate
agentic_error_rate = 0.684
```

阶段 22 验收也确认：由于阶段 21 对照被 SSL/超时类错误污染，agentic 只能作为 opt-in 能力展示，不能直接成为默认路径。

因此阶段 23 的第一原则是：先修复或隔离评测不稳定性，再做自动路由。若可靠评测显示 agentic 增益不明显，文档必须诚实记录“当前数据量/问题集下差异不大”，不能为了达标伪造结论。

## 评测修复方案

阶段 23 使用“两层评测”策略：

1. **供应商隔离层**：新增或扩展阶段 23 评测脚本，默认使用 deterministic provider / fixture。这样 SSL、真实 API 配额、网络抖动不会进入 CI 或本地全量测试。
2. **真实环境可选层**：若本机 `.env`、网络和 provider 可用，可以手动运行真实 API 复核，但真实运行结果只作为人工补充，不作为测试前提。

默认评测输出建议为：

```text
data/evaluation/stage23_agentic_auto_routing_results.csv
data/evaluation/stage23_agentic_auto_routing_summary.csv
data/evaluation/stage23_agentic_auto_routing_decision.csv
```

输出只保存问题 ID、问题类别、期望复杂度、default/agentic 结果摘要、错误标记、命中/覆盖指标和决策结论，不保存 API key、Bearer token、供应商原始敏感响应或受限全文。

## 对照评测集设计

可靠对照集至少覆盖四类问题：

| 类别 | 目标 | 预期路由 |
|---|---|---|
| `simple_concept` | 单步概念、定义、资料来源列表等问题 | `simple` / default |
| `complex_rewrite` | 原始问题需要术语改写或拆解才能召回证据 | `complex` / agentic |
| `complex_compare` | 需要对比、差异、优缺点、适用场景的多方面问题 | `complex` / agentic |
| `complex_multi_evidence` | 需要跨段证据合并、流程解释、原因链条的问题 | `complex` / agentic |

若真实语料和 deterministic provider 下无法观察到 agentic 明显增益，结论应写为：

```text
当前数据量/问题集下差异不大；阶段 23 仍仅把 agentic 自动路由到复杂问题，
并保留显式 mode 覆盖和可观测字段，方便后续继续积累证据。
```

## 评测指标

阶段 23 不只看单一命中率，而是同时记录稳定性和行为差异：

- `error_rate`：default 或 agentic 执行失败比例。可靠对照目标 `< 0.10`。
- `refusal_accuracy`：拒答类问题是否保持正确边界。
- `answer_coverage`：回答是否覆盖期望要点。
- `deep_top1`：top-1 是否来自深度全文资料。
- `agentic_gain`：agentic 是否在复杂问题上比 default 更好。
- `default_parity`：简单问题上 default 是否与 agentic 无明显差异或更轻量。

其中 `agentic_gain` 只作为评测结论字段，不作为运行时代码的硬编码逻辑。

## 阶段 23 对照结果

已新增并运行 deterministic 对照脚本：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_stage23_agentic_auto_routing.py
```

输出文件：

```text
data/evaluation/stage23_agentic_auto_routing_results.csv
data/evaluation/stage23_agentic_auto_routing_summary.csv
data/evaluation/stage23_agentic_auto_routing_decision.csv
```

本轮结果：

| 方法 | total | errors | error_rate | answer_like_count | refusal_matches |
|---|---:|---:|---:|---:|---:|
| `default_agent_service` | 4 | 0 | 0.000 | 2 | 1/1 |
| `agentic_langgraph` | 4 | 0 | 0.000 | 3 | 1/1 |

决策：

```text
decision = reliable_auto_route_candidate
default_error_rate = 0.000
agentic_error_rate = 0.000
agentic_gain_count = 1
```

诚实结论：阶段 23 deterministic fixture 已经隔离阶段 21 的 SSL/真实 provider 错误，满足 `error_rate < 0.10`。当前可复现的 agentic 增益集中在复杂“Search and compare”任务：default `detect_intent` 会把它解析为 search-only，而 agentic LangGraph 能生成 answer-like 响应。其他简单概念题和多证据解释题在当前小样本下主要表现为稳定 parity，不能声称 agentic 全面优于 default。

## 问题复杂度路由

新增规则式函数：

```python
classify_query_complexity(question: str) -> QueryComplexityResult
```

建议返回：

```text
complexity: "simple" | "complex"
score: int
reasons: list[str]
signals: list[str]
```

规则只使用问题文本本身，不调用 LLM。

### 复杂信号

问题命中以下信号时倾向 `complex`：

- 问题较长，例如中文非空字符数达到阈值，或英文 token 数达到阈值。
- 子句较多，例如包含多个逗号、分号、顿号、问号，或出现“并且/同时/分别/以及”等连接词。
- 对比类关键词：`对比`、`比较`、`区别`、`差异`、`优缺点`、`vs`、`versus`、`compare`。
- 流程类关键词：`流程`、`步骤`、`机制`、`路径`、`先后`、`如何形成`。
- 多方面关键词：`多方面`、`分别`、`哪些因素`、`综合`、`结合`、`影响`、`原因`。
- 跨证据/改写倾向：`跨段`、`多篇`、`证据合并`、`术语`、`别名`、`换一种说法`。

没有复杂信号、较短、单一意图的问题倾向 `simple`。

## API 自动分流

`POST /agent/query` 的阶段 23 行为：

```text
if request.mode is explicit:
    effective_mode = request.mode
else:
    routing = classify_query_complexity(request.question)
    effective_mode = "agentic" if routing.complexity == "complex" else "default"

if effective_mode == "agentic":
    run_agentic_rag(...)
else:
    AgentService.query(...)
```

关键约束：

- 显式 `mode=default` 继续走 default，方便调试和回归。
- 显式 `mode=agentic` 继续走 agentic，方便排查图节点。
- 自动路由只在 `mode` 为空时生效。
- default 链路内部仍由 `detect_intent` 判断 `answer` / `search` / `list_sources` / `get_source_detail`。
- `detect_intent` 不知道也不需要知道 agentic 自动路由。
- 响应 `mode` 字段必须表示本次实际链路：`default` 或 `agentic`。

## 前端改造

阶段 22 前端 Agent 面板包含 `default` / `agentic` 下拉框。阶段 23 改为只读状态指示器：

```text
模式：系统自动
提交后：本次走 default 或 本次走 agentic
```

交互规则：

- 用户不再手动选择模式。
- `submitAgent()` 不再向请求体写入 `mode`。
- 收到响应后读取 `result.mode` 并更新只读状态。
- 结果区继续展示 mode badge、iteration badge、workflow steps、invalid citations、refusal category。
- `workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category` 继续是只读可观测字段，不引入用户写操作。

## 安全边界

- 不保存 credentials、Bearer token、真实供应商敏感响应。
- 评测 CSV 不保存受限全文。
- deterministic fixture 只包含项目内可提交的最小合成片段和指标。
- agentic workflow steps 只展示脱敏摘要。
- 自动路由不等于自动工程判断；责任边界拒答规则继续有效。

## 测试方案

聚焦测试：

```text
tests/test_agent_routing.py
tests/test_agent_api.py
tests/test_frontend_app.py
tests/test_stage23_agentic_eval.py
```

必须覆盖：

- `classify_query_complexity` 的 simple/complex/理由输出。
- `/agent/query` 未传 `mode` 时 simple 自动走 default。
- `/agent/query` 未传 `mode` 时 complex 自动走 agentic。
- 显式 `mode=default` 覆盖自动 complex 判断。
- 显式 `mode=agentic` 覆盖自动 simple 判断。
- 前端不再包含手动 mode 下拉框。
- 前端请求体不再发送 `mode`。
- 前端根据响应 `mode` 更新只读状态指示器。
- `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 回归不破坏。

全量验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

目标：全量测试通过，测试数量不低于阶段 22 的 451，并包含阶段 23 新增测试。

## 完成标准

- 本设计文档就位，并在阶段收尾时填入最终评测结论。
- 阶段 21 SSL/超时问题被修复或 deterministic 隔离，阶段 23 对照结果 `error_rate < 0.10`。
- agentic vs default 对照结论诚实记录。
- `classify_query_complexity` 稳定、可解释、无外部依赖。
- `/agent/query` 未传 `mode` 自动分流；显式 `mode` 继续覆盖。
- 前端 mode 下拉框改为只读状态指示器。
- 既有核心 API 不破坏。
- 新增测试和全量测试通过，目标 >= 451。
- README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、必要的 `AGENT.MD` 判断、Obsidian 本地知识库同步。
- 最终停在人工核验待提交状态，不 commit、不 tag、不 push、不 PR。

## 新词解释与面试表达

- **自动模式路由**：API 根据问题复杂度自动选择 default 或 agentic。面试时可以说：我没有直接把慢而复杂的 agentic 设成全局默认，而是用可解释规则在入口分流，简单问题保持稳定链路，复杂问题进入可观测的 LangGraph。
- **规则式复杂度分类**：不调用 LLM，只用问题长度、子句、关键词和多步信号判断问题复杂度。面试时可以说：第一版路由优先可测试、可解释、可回归，避免把“路由器本身”变成新的黑盒。
- **deterministic provider**：本地确定性模型替身，避免测试依赖真实 API。面试时可以说：真实 provider 可以手动复核，但 CI 和全量测试必须在无 key、无网络的情况下跑通。
- **只读状态指示器**：前端不让用户选择内部链路，只展示系统本次实际选择。面试时可以说：这降低用户认知负担，同时保留响应里的 mode、workflow steps 等可观测信息，方便排查。
