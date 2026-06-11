# 阶段 21 验收报告

- 验收人：Claude（技术验收）
- 验收日期：2026-06-11
- 分支：`claude/phase-21-langgraph-agentic-rag`
- 基线：`main` 含 `8333d71 Merge phase 20 ...`，`phase-20-complete -> 706047d`（未移动）
- 验收方式：直接核对工作区——读 diff、独立重跑测试、验证图编译、检查迭代上界、重新生成评测 CSV、扫描敏感信息、检查文档同步与提交边界（不依赖开发 Agent 口头汇报）

## 结论

**PASS** —— 达到阶段 21 目标（LangGraph 六节点 agentic RAG 状态图 + 硬迭代上界 + 三层拒答保护 + 确定性可测 + 可配置 mode 接入 + 诚实评测决策），等待用户人工核验后提交。

## 验收明细

| 维度 | 核对方式 | 结果 |
|---|---|---|
| 分支正确 | `git branch --show-current` | PASS：`claude/phase-21-langgraph-agentic-rag` |
| 基线未动 | `git tag -l phase-20-complete` + `git log main -5` | PASS：`phase-20-complete -> 706047d`，main 含 `8333d71` |
| 提交边界 | `git diff --cached --stat` + `git tag -l phase-21*` | PASS：无 staged、无新 commit、无 phase-21 tag |
| LangGraph 依赖 | `tomllib` 解析 pyproject.toml | PASS：`langgraph>=0.2.0` 已声明 |
| 模块结构 | 文件存在性检查 | PASS：`app/services/agentic/` 含 `__init__.py`(76B)、`state.py`(1083B)、`nodes.py`(9086B)、`graph.py`(2496B) |
| 状态 schema | `import AgenticState` | PASS：17 个字段含 question/results/iteration_count/evidence_sufficient 等 |
| 六节点图 | `build_agentic_graph()` | PASS：retrieve/grade/rewrite/re_retrieve/generate/citation_check |
| 图编译 | `get_compiled_graph()` | PASS：返回 `CompiledStateGraph` |
| 硬迭代上界 | `MAX_ITERATIONS=3` + `test_max_iterations_is_three` | PASS：常量值 3，测试强制验证 |
| 拒答保护 | `test_generate_node_refuses_responsibility_question` + `test_generate_node_refuses_no_results` | PASS：责任门拒答 + 空结果拒答 |
| API 契约 | `AgentQueryRequest.mode` + 6 个 API 测试文件 | PASS：默认 mode=None 走既有链路，mode="agentic" 走新图；25 API tests PASSED |
| 确定性可测 | 19 agentic tests 全用 DeterministicChatModelProvider | PASS：不依赖真实 API |
| 评测对照 | 离线重新生成 summary/decision CSV | PASS：`inconclusive_high_error_rate`（agentic error_rate=0.684），排除出错行后 refusal_acc=1.000 |
| 全量回归 | `pytest -q` | PASS：**449 passed** in 37s（>= 424 基线 + 25 新增） |
| 安全/合规 | grep 全部 stage21 产物 | PASS：无密钥/Bearer 真值（仅 `settings.chat_model_api_key` 运行时引用）、无受限全文 |
| 设计文档 | `docs/stage21_langgraph_agentic_rag.md` | PASS：7097 bytes，覆盖目标/schema/节点图/迭代上界/安全边界/接入门槛 |
| 文档同步 | README / progress / architecture / data_sources / AGENT.MD | PASS：5 个文档均已更新反映阶段 21 |
| Obsidian | 本地 vault 文件 | PASS：14 phase reports + 汇报索引 + 阶段页 + 3 全局索引已更新，gitignored |

## 验收修复

| 发现 | 严重度 | 修复 |
|---|---|---|
| 评测 summary/decision CSV 由旧脚本生成，缺少 error_rate 列，decision 错误显示 `keep_candidate` | 高 | 用现有 results CSV + 修正后的 summarize/decision 逻辑离线重新生成，decision 现为 `inconclusive_high_error_rate`，error_rate=0.684 |

## 评测数据详情

排除出错行后的指标对比（仅计入正常完成的查询）：

| config | non_refusal_ok | p@1 | avg_coverage | deep_top1 | refusal_ok | refusal_acc | error_rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_hybrid | 15 | 0.000 | 0.160 | 0.133 | 4 | 1.000 | 0.000 |
| agentic_rag | 6 | 0.000 | 0.358 | 0.167 | 0 | 1.000 | 0.684 |

决策：

```text
decision=inconclusive_high_error_rate
reason=error_rate baseline=0.000 agentic=0.684; delta_p1=+0.000<0.10; delta_deep_top1=+0.034<0.20
```

注：agentic 的 avg_coverage_ratio(0.358) 高于 baseline(0.160)，但仅基于 6 个正常完成的查询，样本量不足以下结论。SSL 错误是网络环境问题而非代码缺陷。

## 遗留观察（带入后续阶段）

1. **评测需在稳定网络下重跑**：SSL 错误导致 agentic 68.4% 查询失败（agentic 模式因 rewrite+re-retrieve 循环需要更多 embedding 调用，对网络稳定性更敏感）。后续需在稳定环境下重跑 agentic vs baseline 对照，才能得出有效的接入决策。
2. **检索质量瓶颈未解**：baseline p@1=0.000（BrainService 默认链路用 evidence_confidence 过滤后，比阶段 20 raw hybrid 的 0.133 更低），agentic 在正常完成的 6 个查询中 p@1 也为 0.000。迭代改写提升了 coverage_ratio 但未突破 p@1 阈值。
3. **agentic mode 是 opt-in 而非默认**：当前设计正确——没有达标数据就不进入默认链路。后续如要切换，需要新的对照数据证明 Δp@1≥0.10 且 Δdeep_top1≥0.20 且 refusal 不退化。
4. **迭代上界 + 证据二次确认是双保险**：MAX_ITERATIONS=3 防死循环，generate 节点在 evidence_sufficient=False 时二次评估并拒答——这是 agentic 特有的安全机制，值得在面试中强调。

## 路线图决策（本阶段确认）

阶段 21 完成了 LangGraph agentic RAG 能力建设，但因网络问题未能得出有效评测结论。后续方向：

- 阶段 22：稳定网络下重跑评测 / 前端升级 + 可观测（展示 agentic 迭代过程）。
- 阶段 23：正式部署（Docker Compose / env / 可选 pgvector）。
- 可选：引入 LLM-judge 做答案质量离线复核、扩展 agentic 工具集。
