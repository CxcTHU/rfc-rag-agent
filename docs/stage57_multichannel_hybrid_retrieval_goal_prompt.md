# Phase 57 Goal Prompt

阅读 agent 和其他相关文件，了解项目开发进度。

现在正式进入阶段 57 的开发。请为本线程设置一个 goal：

按照当前项目的 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，以及阶段 56“分层语义缓存与 Agent 延迟优化”的完成状态，持续推进本项目开发，直到阶段 57“多通道混合检索与默认链路真实评测”的开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。

目标分支建议为：

```text
codex/phase-57-multichannel-hybrid-retrieval
```

执行要求：

1. 首先修改当前对话线程名称为：阶段57-多通道混合检索与默认链路真实评测。
2. 先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`、`docs/phase_reviews/phase-56.md`。
3. 运行 `git status -sb` 和 `git log --oneline -5`，确认 Phase 56 完成状态和正确开发基线；保留用户已有改动，不重置 Git，不覆盖无关文件。
4. 创建或切换到 `codex/phase-57-multichannel-hybrid-retrieval` 分支。
5. 阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，不要创建 PR；必须等待用户人工核验和明确确认。
6. 严格使用 Planning with Files：每个小 Phase 开始前重读三份规划文件；每个小 Phase 完成后更新 `task_plan.md`、`findings.md`、`progress.md`。
7. 默认链路保持 `tool_calling_agent`。不要优先把 `search_graph_knowledge` 暴露给默认 tool-calling 模型；先把 graph/table-text/figure-caption 作为 `hybrid_search_knowledge` 内部候选通道。
8. 不让 LLM 临场决定 vector/BM25/graph/table/figure-caption 的底层组合；LLM 只做高层工具选择，检索 workflow 内核负责多路召回、去重、融合、rerank、dynamic K 和证据组织。
9. 不新增外部数据源、爬虫、PDF、写入型 Agent 工具、复杂默认 LangGraph workflow，不启用广义答案级 Semantic Cache 作为质量方案。
10. 不得写入真实 `.env`、`.env.prod`、数据库密码、JWT secret、Redis 密码、API key、Bearer token、供应商原始响应、`raw_response`、`reasoning_content`、hidden thought、完整 answer、完整 chunk、受限全文、私有日志或长期用户画像。

Phase 57 必须按以下顺序推进：

Phase 57A：启动校准与基线审计  
- 审计 `ToolCallingAgentService`、`AgentToolbox`、`HybridSearchService`、`GraphEnhancedSearchService`、`search_tables`、`search_figures`、Phase 56 cache/diagnostics。确认默认工具边界和为什么本阶段先做 retrieval kernel。

Phase 57B：多通道检索设计  
- 设计统一 candidate shape、channel gates、weighted RRF/RRF fusion、cache identity、diagnostics 和 rollback switches。graph 只在标准引用链、跨文档关系、参数范围、applies-to 等图意图下进入候选池；table-text 和 figure-caption 保持保守 gating。

Phase 57C：graph channel 并入 `hybrid_search_knowledge`  
- 复用现有 GraphRAG 数据与匹配逻辑，把 graph candidates 并入 keyword/vector 同一 dedupe/fusion/rerank/dynamic-K 路径；缺图或异常时 fail-open。

Phase 57D：table-text 与 figure-caption channel  
- table chunk 可作为表格/参数类文本候选进入统一 rerank；`search_tables` 仍负责明确原始表格请求。figure caption/metadata 只作为文本候选；`search_figures` 仍负责明确图片/曲线/破坏形态资产请求。

Phase 57E：融合、缓存、诊断集成  
- 完成 channel-aware fusion，扩展 retrieval cache identity，保留 BGE/GLM rerank cache 隔离，扩展 diagnostics 显示 channel eligibility、candidate counts、selected chunk ids/source previews/channel labels。

Phase 57F：确定性测试和质量回归  
- 补测试覆盖 channel gate、dedupe、fusion、graph fail-open、table/figure eligibility、cache identity、diagnostics。运行 focused tests 和 `python scripts/score_stage30_quality.py`。

Phase 57G：约 30 条真实默认链路测评  
- 构建约 30 个脱敏测评 case，必须走完整默认 `/agent/query` 或等价 `tool_calling_agent` 链路，调用真实 API：tool-calling chat、embedding、reranker、最终回答生成。覆盖 ordinary、graph-intent、table-intent、figure-caption/visual-adjacent、negative/boundary。输出只保存 case id、类别、配置、延迟、工具名、cache flags、channel counts、source/citation counts、selected chunk ids、短标题/source_type 预览、拒答标记和指标标签；不得保存完整答案、完整 chunk、provider raw response 或 secret。

Phase 57H：文档、Obsidian 与交班  
- 更新 README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、阶段报告和本地 Obsidian；最终停在人工核验前。

完成标准：

- 默认 `tool_calling_agent` 工具面保持稳定。
- `hybrid_search_knowledge` 成为 keyword/vector/graph/table-text/figure-caption 的统一多通道 workflow kernel。
- graph/table/visual-adjacent 能力通过统一候选池、rerank、dynamic K、缓存和诊断闭环，而不是靠 LLM 选择底层检索通道。
- 约 30 条真实默认链路 API 测评完成并脱敏记录。
- ordinary query 不回退；graph/table/visual-adjacent 类别有明确改善或诚实的 no-switch 结论。
- focused/broad regression 通过，Stage 30 仍为 pass。
- 最终汇报说明当前分支、主要改动、真实测评结果、测试结果、风险、未提交状态和人工核验重点。
