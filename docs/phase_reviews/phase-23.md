# 阶段 23 验收报告

- 验收人：Claude（独立验收方）
- 开发方：Codex
- 验收日期：2026-06-11
- 分支：`codex/phase-23-agentic-eval-and-auto-routing`
- 基线：`phase-22-complete -> 1a5bf0c`

## 验收结论

**PASS**

阶段 23 的目标是修复阶段 21 因 SSL 错误导致的 inconclusive 评测、新增规则路由自动选择 default/agentic 链路、将前端模式控件从手动选择改为只读状态指示。三个目标均已达成，实现质量良好。

---

## 一、阶段 23 解决了什么问题

阶段 21 的 agentic vs baseline 对照评测因 SSL 错误（19 个查询中 14 个失败，error_rate=0.684）被判定为 `inconclusive_high_error_rate`，无法用于决策 agentic 是否值得投入。阶段 22 把 agentic 做成了前端可见的 opt-in 选项，但用户必须手动选择 default 还是 agentic——系统无法自行判断。

阶段 23 同时解决了这两个问题：

1. **评测可靠性**：用 DeterministicChatModelProvider + DeterministicEmbeddingProvider + 内存 SQLite 重做了评测，彻底隔离了真实 API 的 SSL/超时问题。
2. **自动路由**：新增 `classify_query_complexity()` 规则分类器，让 `/agent/query` 在用户不指定模式时自动判断复杂度，复杂查询走 agentic，简单查询走 default。
3. **前端适配**：将手动模式下拉框替换为只读状态指示器，反映系统自动路由的结果。

## 二、实际做出的改进

### 2.1 确定性评测脚本

`scripts/evaluate_stage23_agentic_auto_routing.py` 实现了完全隔离的对照评测：

- 4 个评测用例覆盖 simple_concept、complex_compare、complex_multi_evidence、refusal 四种类型。
- 使用合成 fixture（3 篇短文档）+ 确定性 provider，不依赖任何外部 API。
- 输出三份 CSV：results（逐条明细）、summary（汇总）、decision（最终判定）。
- 独立重跑结果：`error_rate=0.000`（default 和 agentic 都是零错误），`decision=reliable_auto_route_candidate`，`agentic_gain_count=1`。

**做得好的地方：**

- 评测脚本本身也被测试覆盖（`test_stage23_agentic_eval.py` 验证输出文件存在、decision 正确、不含 secrets）。
- 明确标注"不替代阶段 21 评测"——只是补充了一个无 SSL 干扰的确定性对照，而不是否定前期工作。
- `has_agentic_gain()` 的判定逻辑合理：仅在 default 路由只走到 search 而 agentic 能生成 answer-like 结果时才计为 gain。

### 2.2 规则路由分类器

`app/services/agent/routing.py` 新增了 `classify_query_complexity()` 函数：

| 信号 | 权重 | 示例 |
|---|---|---|
| comparison 关键词 | +2 | compare、对比、区别 |
| process/mechanism 关键词 | +1 | 流程、步骤、mechanism |
| multi_aspect 关键词 | +1 | jointly、综合、哪些因素 |
| cross_evidence/rewrite 关键词 | +2 | 多篇、术语、改写 |
| causal 关键词 | +1 | why、affect、为什么 |
| search + analysis 组合 | +2 | search AND compare/explain/summarize |
| 长度 ≥80 字符或 ≥22 token | +2 | — |
| 长度 ≥48 字符或 ≥14 token | +1 | — |
| ≥4 子句 | +2 | 逗号/分号/连词分隔 |
| ≥3 子句 | +1 | — |

判定阈值：score≥3 或 (score≥2 且含至少一个 strong signal)。

**做得好的地方：**

- 直接来源请求（"list sources"、"来源列表"等）走快速退出返回 `simple`，不干扰 `detect_intent` 的现有路由。
- 返回值 `QueryComplexityResult` 是 frozen dataclass，包含 score、reasons、signals——完全可追溯，便于调试和日志。
- 中英双语关键词覆盖，匹配项目的堆石混凝土领域。
- 没有修改已有的 `detect_intent()`——这是正确的边界控制。

### 2.3 `/agent/query` 自动路由

`app/api/agent.py` 的 `query_agent()` 新增了 `effective_mode` 逻辑：

- 当 `request.mode is None`（前端不传 mode）时，调用 `classify_query_complexity(request.question)` 判断复杂度，complex→agentic，simple→default。
- 当 `request.mode` 显式传入（"default" 或 "agentic"）时，直接使用——保留了调试和测试的显式覆盖能力。

### 2.4 前端只读状态指示

- `index.html`：`<select data-agent-mode>` 替换为 `<output data-agent-mode-status>系统自动</output>`，语义正确（`<output>` 是 HTML5 的只读计算结果元素）。
- `app.js`：`submitAgent()` 不再发送 `mode` 字段；请求前显示"判断中"，响应后显示实际路由结果（default/agentic）。
- 新增 `updateAgentModeStatus()` 函数，映射 auto→系统自动、pending→判断中、default→default、agentic→agentic。

### 2.5 测试

- 新增 `test_agent_routing.py`：6 个测试覆盖 simple/complex 分类、直接来源快速退出、短搜索保持简单、空输入拒绝。
- 新增 `test_stage23_agentic_eval.py`：3 个测试覆盖评测集类型、确定性输出、无 secrets。
- `test_agent_api.py` 新增 3 个测试：复杂查询自动路由到 agentic、显式 default 覆盖复杂自动路由、显式 agentic 覆盖简单自动路由。
- `test_frontend_app.py` 更新断言：确认无 mode 下拉框、无 `body.mode = "agentic"` 发送、有只读状态指示器和 `updateAgentModeStatus`。
- 全量 **463 passed**，较阶段 22 基线 451 增加 12 个测试。

## 三、边界把控

以下"不做"的边界全部守住了：

- **没有修改 `detect_intent()`**——规则路由分类器是独立的新函数，不干扰现有意图识别。
- **没有把 agentic 强制为默认**——auto-routing 是条件性的，简单查询仍走 default。
- **没有引入 ML 模型做路由**——当前是纯规则，无额外依赖，符合项目阶段。
- **没有让真实 API 成为测试/评测前提**——全部使用确定性 provider。
- **没有引入前端构建链**——继续原生 HTML/CSS/JS。
- **显式模式覆盖保留**——API 层面仍支持 `mode="default"` 和 `mode="agentic"` 的显式传入，供调试和测试使用。
- **评测 CSV 不含 secrets**——经独立扫描确认，输出文件只有指标和摘要。
- **提交边界正确**——工作区有修改但无 staged changes，无 `phase-23-complete` tag，等待人工核验。

## 四、不足与遗留

1. **评测用例偏少（4 例）**：agentic_gain_count=1 虽然通过了阈值，但统计意义有限。后续如果要更有信心地调整路由阈值，需要扩大评测集（建议 15-20 例，涵盖更多边界条件如中英混合查询、极长/极短问题）。

2. **causal 关键词范围较宽**："how" 和 "affect" 覆盖面广，理论上 "how to pour concrete" 这样的简单操作性问题也会触发 +1 分。当前被 `is_complex_score` 的阈值保护（需要 score≥3 或 score≥2+强信号），实际误判风险低，但值得关注。

3. **请求失败时模式指示器卡在"判断中"**：`submitAgent()` 在发请求前调用 `updateAgentModeStatus("pending")`，但如果 `fetchJson` 抛出异常，catch handler 只更新了 API 状态栏，没有把模式指示器恢复为"系统自动"。这是一个小 UI 问题，不影响功能但体验不完美。

4. **路由决策不体现在 API 响应中**：auto-routing 的判断过程（score、reasons、signals）没有返回给前端或写入响应。目前只能看到最终 mode 是什么，看不到为什么选择了这个 mode。如果后续需要调试路由行为，可以考虑在响应中增加 `routing_detail` 字段。

5. **`refusal_category_from_refusal` 被重构为两个函数**：Phase 22 的单一 `refusal_category_from_refusal()` 现在有了一个 `refusal_category_from_agentic_result()` 包装器。重构合理，但函数命名略有冗余（前缀重复 `refusal_category_from_`），不阻断。

## 五、对阶段目标的总体评价

阶段 23 的核心贡献是让系统从"用户手动选模式"进化到"系统自动判断"。这是一个架构层面的正确方向——RAG 系统不应该让用户操心底层走哪条检索链路。

确定性评测修复了阶段 21 遗留的 SSL 不可靠问题，证明了 agentic 链路在复杂查询上确实优于 default 的 search-only 路由。虽然评测规模小，但方法正确、可复现。

从简历/面试角度看，阶段 23 展示了一个完整的"评测驱动优化"循环：发现评测不可靠 → 隔离变量重做评测 → 用评测结论指导架构决策（自动路由）→ 测试覆盖。这比单纯"加了一个功能"更有说服力。

## 六、人工核验建议

用户在确认前建议：

1. 启动本地服务（`uvicorn app.main:app`），打开 Agent 面板，确认模式控件已变为只读指示器（显示"系统自动"）。
2. 提交一个简单问题（如"What affects filling capacity?"），确认返回 `mode: "default"`，指示器显示"default"。
3. 提交一个复杂问题（如"Search and compare filling capacity and thermal control mechanisms"），确认返回 `mode: "agentic"`，指示器显示"agentic"，workflow 步骤列表正常展示。
4. 在 DevTools Network 面板确认请求体不含 `mode` 字段（系统自动路由，不由前端指定）。
5. （可选）断开后端后提交请求，观察模式指示器是否卡在"判断中"——这是已知的小 UI 问题。
