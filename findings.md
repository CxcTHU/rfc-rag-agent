# 阶段 23 发现与关键决策

## 启动校准发现

- 当前阶段目标：阶段 23「Agentic 评测闭环与自动模式路由」。
- 目标分支：`codex/phase-23-agentic-eval-and-auto-routing`。
- 阶段 22 最终提交：`1a5bf0c Complete phase 22 frontend agentic observability`。
- `phase-22-complete`、`main`、`origin/main` 已确认指向同一提交 `1a5bf0cde5f8b8e76ff1dafa6225fc7fa9f82cfd`。
- `phase-22-complete` 是 `main` 的祖先，且无需移动任何已有阶段 tag。
- 阶段 21 完成 tag：`phase-21-complete` 指向 `085bff4 Complete phase 21 LangGraph agentic RAG`。

## 阶段 21 agentic 评测问题

- 阶段 21 的 agentic 评测决策为 `inconclusive_high_error_rate`。
- 已记录关键指标：`agentic_error_rate=0.684`，default/baseline 错误率为 `0.000`。
- 阶段 21 验收背景中记录 agentic 侧出现 SSL/超时类调用失败，其中用户要求阶段 23 特别关注 SSL 错误 `14/19`。
- 现有 `data/evaluation/stage21_agentic_comparison_summary.csv` 显示：
  - `baseline_hybrid`：`non_refusal_total=15`、`p@1=0.000`、`avg_coverage=0.160`、`deep_top1=0.133`、`refusal_acc=1.000`、`error_rate=0.000`。
  - `agentic_rag`：`non_refusal_total=6`、`non_refusal_errors=9`、`p@1=0.000`、`avg_coverage=0.358`、`deep_top1=0.167`、`refusal_acc=1.000`、`error_rate=0.684`。
- 结论：阶段 21 结果不能证明 agentic 应成为默认路径。阶段 23 必须先隔离供应商 SSL/网络不稳定因素，形成 error_rate < 0.10 的可靠对照，再决定自动路由策略。

## Agentic vs Default 已有差异理解

- default/baseline 在阶段 21 评测中稳定完成，但召回/命中指标较弱。
- agentic 在成功样本上 `avg_coverage` 和 `deep_top1` 略高，但样本被高错误率严重污染，不能直接作为上线依据。
- 阶段 22 因此只把 agentic 做成可视化 opt-in 能力和只读可观测字段，没有把 agentic 设为默认。
- 阶段 23 的判断原则：如果可靠评测仍显示差异不大，应诚实写为“当前数据量/问题集下差异不大”，不能伪造达标。

## 当前 `detect_intent` 路由

位置：`app/services/agent/service.py`

- `detect_intent(question, source_id=None)` 先检查显式 `source_id` 或问题中的 `source_id`，命中则返回 `get_source_detail`。
- 包含 `来源详情`、`source detail`、`source详情` 时返回 `get_source_detail`。
- 包含 `来源列表`、`资料来源`、`list sources`、`sources list` 时返回 `list_sources`。
- 包含 `检索`、`搜索`、`查找`、`search`、`find`、`相关资料` 时返回 `search`。
- 其他问题默认返回 `answer`。
- 阶段 23 决策：不修改 `detect_intent` 内部逻辑；自动路由只决定 `/agent/query` 先走 default `AgentService` 还是 agentic LangGraph。

## 当前 `AgentService` 链路

位置：`app/services/agent/service.py`

- `AgentService.query()` 会先规范化问题、校验 `top_k` 和 `max_tool_calls`。
- 随后调用 `detect_intent()`。
- `get_source_detail`：解析 `source_id`，缺失时返回拒答“请提供要查询的 source_id。”，命中时调用 `self.toolbox.get_source_detail()`。
- `list_sources`：调用 `self.toolbox.list_sources(limit=top_k)`。
- `search`：调用 `self.toolbox.hybrid_search_knowledge(normalized_question, top_k=top_k)`。
- `answer`：调用 `self.toolbox.answer_with_citations(... retrieval_mode="hybrid" ...)`。
- default 模式响应由 `app/api/agent.py` 的 `agent_response_from_result()` 转为 API schema，并返回 `mode="default"`。

## 当前 Agentic LangGraph 链路

位置：`app/services/agentic/`

- 阶段 21 引入 LangGraph agentic RAG，API 中通过 `run_agentic_rag()` 调用。
- 阶段 22 已把 agentic 结果中的 `workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category` 映射到前端只读可观测字段。
- API 映射位置：`app/api/agent.py` 的 `agent_response_from_agentic_result()`。
- 阶段 23 决策：agentic 链路作为复杂问题自动路由目标，但不能让真实 API 或供应商网络稳定性成为测试前提。

## 当前 `/agent/query` API 行为

位置：`app/api/agent.py`

- 当前逻辑：`request.mode == "agentic"` 时调用 `run_agentic_rag()`；其他情况走 default `AgentService.query()`。
- 阶段 23 目标：
  - `mode` 未传时，先调用 `classify_query_complexity()`。
  - `simple` 自动走 default。
  - `complex` 自动走 agentic。
  - 显式 `mode=default` 或 `mode=agentic` 时仍尊重用户选择，作为调试能力。

## 当前前端 mode 控件

位置：`app/frontend/index.html`、`app/frontend/static/app.js`

- 阶段 22 前端 Agent 面板中存在 `select[data-agent-mode]`，用户可手动选择 default / agentic。
- `submitAgent()` 当前会读取该下拉框；只有选择 `agentic` 时才向请求体写入 `mode="agentic"`。
- `renderAgentAnswer()` 已能展示响应里的 `mode` badge，`renderAgentWorkflowSteps()` 已能展示 agentic workflow steps。
- 阶段 23 决策：移除手动选择语义，改为只读状态指示器；提交时不发送 `mode`，响应后展示 API 返回的实际 `mode`。

## 数据安全边界

- 阶段 23 不新增爬虫或外部资料来源。
- 评测输出只保存必要指标、问题 ID、类别、判断结果和摘要，不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- deterministic provider / fixture 只用于隔离网络和供应商不稳定性，不让真实 API 成为 CI 或本地全量测试前提。
- 前端新增/保留字段均为只读观测，不引入写工具或用户敏感操作。

## 阶段 23 关键决策

- 先做可靠评测，再接入自动路由。
- 规则式复杂度分类优先，不引入 LLM 判断。
- 自动路由只在 `mode` 为空时生效，显式 `mode` 保留调试能力。
- 前端用户体验从“选择模式”改为“查看系统本次实际走了哪条链路”。
- 阶段收尾停在未提交状态，等待用户人工核验。

## Phase 1 设计决策

- 新增设计文档：`docs/stage23_agentic_eval_and_auto_routing.md`。
- 评测策略采用“两层评测”：默认 deterministic provider / fixture 隔离 SSL、真实 API、网络和配额问题；真实 provider 只作为人工可选复核。
- 阶段 23 对照集至少覆盖 `simple_concept`、`complex_rewrite`、`complex_compare`、`complex_multi_evidence`。
- 阶段 23 输出建议落在 `data/evaluation/stage23_agentic_auto_routing_*.csv`，只保存指标和摘要，不保存 secrets 或受限全文。
- 路由函数命名确定为 `classify_query_complexity`，输出 `simple` / `complex` 及判断依据。
- `/agent/query` 的 `mode` 为空时才自动路由；显式 `mode` 继续作为调试覆盖。
- 前端改造方向确定为只读状态指示器：请求前显示系统自动，响应后显示本次实际 `mode`。
- 设计文档当前先定义合同，最终评测结论会在 Phase 2/6 后回填同步。

## Phase 2 评测闭环发现

- 阶段 21 的真实 provider 路线保留为历史证据，阶段 23 不直接覆盖 `scripts/evaluate_stage21_agentic_rag.py`。
- 新增 `scripts/evaluate_stage23_agentic_auto_routing.py`，默认使用 deterministic chat/embedding provider 和 in-memory SQLite fixture。
- 阶段 23 fixture 覆盖：
  - `simple_concept`：简单填充能力概念题，default 与 agentic 均应稳定回答。
  - `complex_compare`：带 `Search and compare` 的复杂对比题，default `detect_intent` 会解析为 search-only，agentic 会进入 LangGraph 生成 answer-like 响应，这是当前可复现的 agentic 行为收益。
  - `complex_multi_evidence`：跨填充、温控、施工质量的多证据题，当前 default 与 agentic 主要表现为稳定 parity。
  - `refusal`：off-topic 拒答边界，default 与 agentic 都应拒答。
- 新增测试 `tests/test_stage23_agentic_eval.py`，验证评测集覆盖、输出文件、`error_rate < 0.10`、至少一个 agentic gain，以及不包含 `api_key` / `bearer` / `authorization`。
- 关键结论：阶段 23 评测先证明 SSL/真实 provider 错误已被 deterministic fixture 隔离；agentic 增益在当前 fixture 下主要体现在复杂“检索并比较”任务避免 default search-only 响应，其余复杂多证据题暂记录为差异不大或 parity。
- 已运行 `scripts/evaluate_stage23_agentic_auto_routing.py`：
  - default：`errors=0`、`error_rate=0.000`、`answer_like_count=2`。
  - agentic：`errors=0`、`error_rate=0.000`、`answer_like_count=3`、`agentic_gain_count=1`。
  - decision：`reliable_auto_route_candidate`。
- 已运行 `tests/test_stage23_agentic_eval.py -q`：`3 passed`。

## Phase 3 路由规则发现

- 新增模块：`app/services/agent/routing.py`。
- 新增函数：`classify_query_complexity(question)`。
- 新增结果类型：`QueryComplexityResult`，字段包含：
  - `complexity`：`simple` 或 `complex`。
  - `score`：规则累计分数，只用于解释和测试，不直接暴露为用户承诺。
  - `reasons`：判断依据。
  - `signals`：命中的规则信号。
- 复杂度规则只看问题文本，不调用 LLM。
- 强复杂信号包括：comparison、process/mechanism、multi_aspect、cross_evidence_or_rewrite、search_analysis_combo。
- 边界修正：短的 “What affects ...?” 概念题即使命中长度和因果词，也保持 `simple`；必须有足够分数或强复杂信号才判 `complex`。
- 直接 source/list/source detail 请求保持 `simple`，交给 default `AgentService` 内部 `detect_intent` 处理。
- 已运行 `tests/test_agent_routing.py -q`：`6 passed`。

## Phase 4 API 自动分流发现

- 修改位置：`app/api/agent.py`。
- `/agent/query` 现在先计算 `effective_mode`：
  - 显式 `request.mode` 存在时直接使用。
  - `request.mode is None` 时调用 `classify_query_complexity(request.question)`。
  - `complex` 自动走 `run_agentic_rag()`。
  - `simple` 自动走 default `AgentService.query()`。
- `detect_intent` 内部逻辑未修改；只有进入 default `AgentService` 后才继续判断 answer/search/list_sources/get_source_detail。
- 新增 API 测试覆盖：
  - 复杂题未传 `mode` 自动返回 `mode="agentic"`。
  - 复杂题显式 `mode="default"` 返回 `mode="default"` 且走 `hybrid_search_knowledge`。
  - 简单题显式 `mode="agentic"` 返回 `mode="agentic"`。
- 已运行 `tests/test_agent_routing.py tests/test_agent_api.py -q`：`17 passed`。

## Phase 5 前端只读模式指示器发现

- 修改 `app/frontend/index.html`：
  - 移除 `select[data-agent-mode]`。
  - 新增只读 `output[data-agent-mode-status]`，初始显示“系统自动”。
- 修改 `app/frontend/static/app.js`：
  - 删除读取 `document.querySelector("[data-agent-mode]")` 的逻辑。
  - 删除向请求体写入 `body.mode = "agentic"` 的逻辑。
  - 新增 `updateAgentModeStatus(mode)`。
  - 提交前显示“判断中”，响应后由 `renderAgentAnswer()` 使用 `result.mode` 更新为 `default` 或 `agentic`。
- 修改 `app/frontend/static/styles.css`：
  - 新增 `.readonly-field` 和 `.mode-indicator` 样式，保持 Agent 控制区布局稳定。
- 修改 `tests/test_frontend_app.py`：
  - 断言前端不再有 mode 下拉框和 agentic option。
  - 断言 JS 不再写 `body.mode = "agentic"`。
  - 断言只读状态指示器和更新函数存在。
- 已运行 `tests/test_frontend_app.py tests/test_agent_api.py tests/test_agent_routing.py -q`：`23 passed`。

## Phase 6 回归验证发现

- 阶段 21/22/23 聚焦回归：
  - 命令：`.\.venv\Scripts\python.exe -m pytest tests\test_stage23_agentic_eval.py tests\test_agent_routing.py tests\test_agent_api.py tests\test_frontend_app.py tests\test_agentic_graph.py tests\test_stage21_agentic_eval.py -q`
  - 结果：`51 passed in 4.32s`。
- 全量测试：
  - 命令：`.\.venv\Scripts\python.exe -m pytest -q`
  - 结果：`463 passed in 31.21s`。
- 浏览器验证：
  - 临时服务：`http://127.0.0.1:8001`，验证后已停止。
  - 桌面视口：无 `select[data-agent-mode]`；`output[data-agent-mode-status]` 文本为“系统自动”；console errors=0；无横向溢出。
  - 移动视口 `390x844`：无 `select[data-agent-mode]`；只读状态仍可见；无横向溢出。
- 浏览器验证未提交 Agent 问题，避免触发真实 provider；自动路由行为已由 deterministic API 测试覆盖。

## Phase 7 普通文档同步发现

- 已更新 `README.md`：
  - 当前阶段改为阶段 23「Agentic 评测闭环与自动模式路由」。
  - 记录当前分支、未提交/未打 tag/未推送状态、阶段 22 合并基线、评测结果、自动路由、前端只读指示器、测试结果和边界。
  - 阶段 22 要点改为历史基线，并说明阶段 23 已将手动模式选择升级为只读状态指示。
- 已更新 `docs/progress.md`：
  - 新增阶段 23 最新状态块。
  - 记录 Git/tag/main 起点、完成内容、评测结论、验证结果、遗留风险、下一步和面试表达。
  - 阶段 22 状态移动为历史状态，避免把阶段 22 误写为当前阶段。
- 已更新 `docs/architecture.md`：
  - 架构主链路加入 Agent 自动模式路由。
  - 新增阶段 23 自动路由架构段落，说明 `/agent/query` 的 `effective_mode` 分支、`classify_query_complexity`、default `AgentService`、agentic LangGraph 和前端 `data-agent-mode-status`。
  - 记录阶段 23 评测脚本与 CSV 产物的架构位置。
- 已更新 `docs/data_sources.md`：
  - 明确阶段 23 不新增外部资料来源、不新增爬虫、不让真实 API 成为测试前提。
  - 登记阶段 23 设计文档、评测脚本和三份 CSV 的用途与安全边界。
- 已更新 `AGENT.MD`：
  - 增加阶段 23 分支名。
  - 将阶段 22 前端 Agentic 规则升级为阶段 23 之后的前端 Agentic 与自动路由规则。
  - 固化 `/agent/query` 自动路由只在 `mode` 为空时生效、显式 mode 必须尊重、`detect_intent` 不为自动路由改内部规则、前端只读模式指示器和 deterministic 评测结论边界。
- 窄范围校验：
  - 前端源码中旧 `document.querySelector("[data-agent-mode]")` 和 `body.mode = "agentic"` 已不存在。
  - `rg` 命中的 `select[data-agent-mode]` / `mode 下拉框` 均为历史说明、测试断言或计划记录，不是运行时旧控件。
- 遇到并处理的操作错误：
  - 第一次读取 Planning with Files skill 使用了错误路径 `C:\Users\admin\.agents\...`，已改用 `C:\Users\admin\.codex\skills\planning-with-files\SKILL.md`。
  - 第一次 `rg` 在 PowerShell 中使用双引号正则导致管道符被错误拆分，已改用单引号正则重跑。
  - 浏览器验证留下 `.playwright-mcp/page-*.yml` 临时文件，已确认是验证快照，后续在最终清理中移除，不作为阶段 23 产物。

## Phase 8 Obsidian 收尾发现

- 已阅读 `obsidian-vault/模板/Phase 汇报模板.md`，确认每篇小 Phase 汇报必须包含固定 10 项。
- 已参考阶段 22 的 Obsidian 目录、阶段页和 Phase 汇报索引格式。
- 新增阶段 23 Obsidian 目录：
  - `obsidian-vault/阶段汇报/阶段 23 - Agentic 评测闭环与自动模式路由/`
- 新增阶段 23 汇报文件：
  - `阶段 23 Phase 汇报索引.md`
  - `阶段 23 Phase 0 - 启动校准.md`
  - `阶段 23 Phase 1 - 阶段 23 设计文档.md`
  - `阶段 23 Phase 2 - Agentic 评测修复与可靠对照.md`
  - `阶段 23 Phase 3 - 问题复杂度路由规则.md`
  - `阶段 23 Phase 4 - API 自动分流集成.md`
  - `阶段 23 Phase 5 - 前端只读模式指示器.md`
  - `阶段 23 Phase 6 - 回归验证与质量门.md`
  - `阶段 23 Phase 7 - 普通文档同步.md`
  - `阶段 23 Phase 8 - Obsidian 收尾.md`
  - `阶段 23 Phase 9 - 人工核验待提交状态.md`
- 新增阶段总览页：`obsidian-vault/阶段/阶段 23 - Agentic 评测闭环与自动模式路由.md`。
- 已更新全局入口：
  - `obsidian-vault/阶段汇报索引.md`
  - `obsidian-vault/阶段索引.md`
  - `obsidian-vault/首页.md`
- 已校正阶段 22 Obsidian 页和阶段 22 Phase 汇报索引的状态，反映 `phase-22-complete` 已完成并合并到 `main`。
- 已校验阶段 23 目录包含 10 篇小 Phase 草稿和 1 个索引。
- 已校验每篇阶段 23 小 Phase 汇报均包含 `## 10. 面试表达`、阶段双链和汇报索引双链。
- 操作问题：
  - 第一次读取模板路径未加引号，PowerShell 将 `Phase 汇报模板.md` 拆成多个参数；已改用带引号路径成功读取。

## Phase 9 最终待人工核验发现

- 已清理浏览器验证遗留的 `.playwright-mcp/page-*.yml` 临时快照目录；该目录不是阶段 23 产物。
- 阶段 23 deterministic 评测复跑结果：
  - default：`errors=0`、`error_rate=0.000`、`answer_like=2`。
  - agentic：`errors=0`、`error_rate=0.000`、`answer_like=3`、`agentic_gain_count=1`。
  - decision：`reliable_auto_route_candidate`。
- 全量测试复跑结果：`463 passed in 27.31s`。
- `git status -sb` 显示当前分支为 `codex/phase-23-agentic-eval-and-auto-routing`，存在阶段 23 修改和新增文件，未 staged。
- `git tag --list phase-23-complete` 无输出，说明尚未创建阶段 23 完成 tag。
- `HEAD`、`phase-22-complete`、`main`、`origin/main` 仍指向 `1a5bf0c Complete phase 22 frontend agentic observability`，阶段 23 改动保持为未提交工作树状态。
- 最终状态文本校验：已检索“进行中”和 Phase 9“待最终复核”状态，无有效残留，说明 Planning with Files 和 Phase 9 Obsidian 汇报不再停留在进行中状态。
- `obsidian-vault/` 被 `.gitignore` 忽略；阶段 23 Obsidian 草稿已本地更新，但不会出现在普通 `git status` 的待提交列表中。
- 操作问题：一次最终 `rg` 校验使用了包含换行和管道符的双引号正则，在 PowerShell 中被错误拆分；已改用简单单引号模式重跑。
- 后续建议：用户人工核验通过后，再执行 `git add`、`git commit`、创建 `phase-23-complete` tag，并按项目规则推送；提交前不要移动 `phase-22-complete` 或其他已有阶段 tag。

## 提交/合并确认

- 2026-06-11，用户明确要求：阅读 `AGENT.MD`，按项目要求提交阶段 23 的整体开发工作，并上传/merge 至 GitHub。
- 因此阶段 23 提交边界已解除，可以执行 `git add`、`git commit`、创建 `phase-23-complete` tag、推送分支和合并到 `main`。
- 仍需遵守阶段 tag 规则：`phase-23-complete` 必须指向阶段 23 最终功能提交；不得移动 `phase-22-complete` 或其他已有阶段 tag。
- 提交前复跑阶段 23 deterministic 评测：default/agentic `error_rate=0.000`，decision `reliable_auto_route_candidate`。
- 提交前复跑全量测试：`463 passed in 33.84s`。
- 提交前轻量敏感 token 模式扫描无命中。
