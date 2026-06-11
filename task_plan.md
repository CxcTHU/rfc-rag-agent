# 阶段 23 任务计划：Agentic 评测闭环与自动模式路由

## 目标

在阶段 22「前端 Agentic 可视化与可观测增强」已完成并合并到 `main` 的基础上，完成阶段 23「Agentic 评测闭环与自动模式路由」：修复或隔离阶段 21 agentic 评测中的 SSL 高错误率问题，形成可靠的 agentic vs default 对照结论，新增规则式问题复杂度路由，在 `/agent/query` 默认入口自动分流 default/agentic，前端改为只读模式指示器，并同步普通文档与 Obsidian 本地知识库。阶段完成后停在用户人工核验前，不提交、不打 tag、不推送。

## 硬约束

- 阶段 23 开发完成前后均不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。
- 不移动任何已有阶段 tag，尤其是 `phase-22-complete`。
- 保留用户或其他 session 的已有改动，不重置 Git，不覆盖无关文件。
- 不做登录系统、部署优化、Streaming/SSE、新爬虫或外部资料源。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- `detect_intent` 内部规则保持不变；自动路由只决定 `/agent/query` 走 default `AgentService` 还是 agentic LangGraph。
- 保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`GET /quality-report` 不被破坏。

## Phase 顺序

### Phase 0：启动校准与文件计划

**状态：已完成**

**解决的问题**：确认阶段 22 的最终状态、tag、main 起点和阶段 23 分支，避免在错误基线上继续开发。

**RAG 链路位置**：阶段起点校准，不改运行链路。

**为什么现在做**：阶段 23 依赖阶段 22 的前端 agentic 可观测能力和阶段 21 的 LangGraph agentic 链路，必须先确认二者已进入 `main`。

**任务**
- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读阶段 21、22 设计文档与 phase review，以及根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 核对 `phase-22-complete` tag、`main`、`origin/main` 是否指向同一阶段 22 最终提交。
- 从阶段 22 合并后的 `main` 创建或切换到 `codex/phase-23-agentic-eval-and-auto-routing`。
- 将根目录三份 Planning with Files 文件校准为阶段 23。

**验证方式**
- `git status -sb`
- `git log --oneline -5`
- `git show -s --format=... phase-22-complete`
- `git show -s --format=... main`
- `git merge-base --is-ancestor phase-22-complete main`

**完成标准**
- 当前分支为 `codex/phase-23-agentic-eval-and-auto-routing`。
- `phase-22-complete` 不移动，且已并入 `main`。
- `task_plan.md`、`findings.md`、`progress.md` 已切换为阶段 23。

### Phase 1：阶段 23 设计文档

**状态：已完成**

**解决的问题**：把评测修复、自动路由、前端只读状态和安全边界先固化成可审查设计。

**RAG 链路位置**：横跨评测脚本、`/agent/query` API、default AgentService、agentic LangGraph、前端 Agent 面板。

**为什么现在做**：先明确完成标准和边界，后续代码实现、测试和文档可以对齐同一个设计。

**任务**
- 新增 `docs/stage23_agentic_eval_and_auto_routing.md`。
- 说明阶段 21 `inconclusive_high_error_rate` 的原因和阶段 23 的隔离/修复策略。
- 说明可靠 agentic vs default 对照评测方案、指标和诚实结论原则。
- 说明 `classify_query_complexity` 规则式设计和判断依据输出。
- 说明 `/agent/query` 自动分流逻辑、显式 `mode` 覆盖语义、前端只读模式指示器、安全边界和完成标准。

**验证方式**
- 人工阅读文档结构是否覆盖阶段 23 验收项。
- 后续代码和测试以此文档为实现合同。

**完成标准**
- 设计文档存在且覆盖评测、路由、API、前端、测试、安全与收尾标准。

### Phase 2：Agentic 评测修复与可靠对照设计

**状态：已完成**

**解决的问题**：阶段 21 agentic 评测因 SSL/超时导致错误率过高，无法支持 agentic 是否应进入默认路径的判断。

**RAG 链路位置**：离线评测层，围绕 default hybrid/AgentService 与 agentic LangGraph 的可比性建立可靠证据。

**为什么现在做**：没有可靠对照就不应把 agentic 自动接入真实入口。

**任务**
- 阅读并必要时重构 `scripts/evaluate_stage21_agentic_rag.py` 或新增阶段 23 评测脚本。
- 在真实 API 不可用时，使用 deterministic provider / fixture 隔离供应商 SSL 问题。
- 构造能覆盖简单概念题与复杂多步/改写/跨段合并题的对照集。
- 输出阶段 23 评测结果、汇总和决策文件，目标 error_rate < 0.10。
- 诚实记录 agentic 与 default 的差异；若差异不大，明确写为当前数据量/问题集下差异不大。

**验证方式**
- 运行阶段 23 评测脚本。
- 检查输出 CSV/汇总文件无敏感原文、无 key/token。
- 检查 error_rate 是否低于 0.10；若不是，记录原因并修复或隔离。
- 已运行：`.\.venv\Scripts\python.exe scripts\evaluate_stage23_agentic_auto_routing.py`，结果 default/agentic `error_rate=0.000`。
- 已运行：`.\.venv\Scripts\python.exe -m pytest tests\test_stage23_agentic_eval.py -q`，结果 `3 passed`。

**完成标准**
- 阶段 21 SSL 高错误率被修复或隔离。
- 产生可复现的阶段 23 agentic vs default 对照结果。

### Phase 3：问题复杂度路由规则

**状态：已完成**

**解决的问题**：自动判断简单问题继续走 default，复杂问题尝试 agentic，避免让用户手动选择模式。

**RAG 链路位置**：`/agent/query` 入口前置路由层，在 default AgentService 和 agentic LangGraph 之前。

**为什么现在做**：评测结论明确后，需要把“哪些问题值得 agentic”落成可测试的规则。

**任务**
- 新增或扩展 agent 路由模块，实现 `classify_query_complexity`。
- 至少输出 `simple` / `complex` 和判断依据。
- 规则式优先，不引入 LLM 判断。
- 覆盖问题长度、子句数、对比/流程/多方面/综合/跨段证据合并等关键词。
- 为规则添加单元测试。

**验证方式**
- 运行新增路由单元测试。
- 检查简单概念题判为 `simple`，多步/对比/流程/多方面问题判为 `complex`，并返回可解释理由。
- 已运行：`.\.venv\Scripts\python.exe -m pytest tests\test_agent_routing.py -q`，结果 `6 passed`。

**完成标准**
- 路由函数稳定、可解释、无外部依赖。

### Phase 4：`/agent/query` 自动分流集成

**状态：已完成**

**解决的问题**：API 在不传 `mode` 时自动选择 default 或 agentic，同时保留显式 `mode` 调试能力。

**RAG 链路位置**：FastAPI `/agent/query` 到 default `AgentService.query()` / agentic `run_agentic_rag()` 的分支点。

**为什么现在做**：路由函数已可测试后，才能安全接入用户入口。

**任务**
- 修改 `app/api/agent.py`，当 `mode` 为空时调用 `classify_query_complexity`。
- `simple` 自动走 default；`complex` 自动走 agentic。
- 显式 `mode=default` 或 `mode=agentic` 时尊重用户选择。
- 不改变 `detect_intent` 内部逻辑。
- 补测试覆盖自动分流、显式覆盖、响应 `mode` 字段。

**验证方式**
- 运行 API 层相关测试。
- 以 mock/stub 保证无需真实 LLM/API。
- 已运行：`.\.venv\Scripts\python.exe -m pytest tests\test_agent_routing.py tests\test_agent_api.py -q`，结果 `17 passed`。

**完成标准**
- `/agent/query` 默认自动分流，显式模式仍可用于调试。
- default 模式行为不变。

### Phase 5：前端只读模式指示器

**状态：已完成**

**解决的问题**：阶段 22 的 mode 下拉框仍把模式选择暴露给用户；阶段 23 要改成系统自动路由后的只读结果展示。

**RAG 链路位置**：前端 Agent 面板，请求前不发送 mode，请求后读取响应 `mode` 展示实际链路。

**为什么现在做**：API 已能自动分流后，前端才能去掉手动选择。

**任务**
- 将 `app/frontend/index.html` 的 mode 下拉框改为只读状态指示器。
- 修改 `app/frontend/static/app.js`，提交时不再发送 `mode`，响应后显示 `result.mode`。
- 保留 `workflow_steps`、`iteration_count`、`invalid_citations`、`refusal_category` 只读可观测字段。
- 补充前端测试。

**验证方式**
- 运行前端相关测试。
- 必要时用本地浏览器验证控件不再可手动选择，响应后可见实际 `mode`。
- 已运行：`.\.venv\Scripts\python.exe -m pytest tests\test_frontend_app.py tests\test_agent_api.py tests\test_agent_routing.py -q`，结果 `23 passed`。

**完成标准**
- 用户不再手动选模式，系统返回的 actual mode 清晰可见。

### Phase 6：回归验证与质量门

**状态：已完成**

**解决的问题**：阶段 23 涉及 API、评测脚本、前端和文档，需要确认既有检索、问答、质量报告接口未受破坏。

**RAG 链路位置**：全链路回归。

**为什么现在做**：功能开发完成后必须先测试，再进入文档收尾。

**任务**
- 运行阶段 23 新增测试。
- 运行后端/API/前端相关回归测试。
- 运行全量测试，目标 >= 451。
- 若失败，定位并修复，补充必要测试。

**验证方式**
- `pytest` 或项目既有测试命令。
- 记录测试数量、耗时、失败修复摘要。
- 已运行阶段 21/22/23 聚焦回归：`51 passed`。
- 已运行全量测试：`463 passed`。
- 已用本地浏览器检查桌面和 390x844 移动视口：mode 下拉框不存在，只读状态指示器存在，console errors=0，无横向溢出。

**完成标准**
- 全量测试通过，且不依赖真实 API。

### Phase 7：普通文档同步

**状态：已完成**

**解决的问题**：把阶段 23 的设计、代码行为、评测结论和验收状态同步到项目普通文档。

**RAG 链路位置**：项目知识层和维护者入口。

**为什么现在做**：测试通过后文档才能准确描述最终行为。

**任务**
- 更新 `README.md`。
- 更新 `docs/progress.md`。
- 更新 `docs/architecture.md`。
- 更新 `docs/data_sources.md`。
- 必要时更新 `AGENT.MD` 中阶段判断或开发指引。
- 将阶段 23 相关新词、关键类名、接口名和面试表达整理进文档。

**验证方式**
- 人工检查文档无过期“用户手动选 mode”表述。
- 检查文档不含 secrets、供应商敏感响应或受限全文。
- 已更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD`。
- 已运行窄范围检索，确认前端源码不再包含旧 `data-agent-mode` 选择器；命中的下拉框表述均为阶段 23 变更说明、测试断言或计划记录。

**完成标准**
- 普通文档与最终代码行为一致。

### Phase 8：Obsidian 本地知识库收尾

**状态：已完成**

**解决的问题**：按本项目阶段汇报规范，在全部开发、测试和普通文档完成后统一补齐 Obsidian 草稿。

**RAG 链路位置**：本地知识库与复盘材料，不影响运行链路。

**为什么现在做**：用户要求开发过程中暂不写小 Phase 汇报，阶段末统一收尾。

**任务**
- 阅读 `obsidian-vault/模板/Phase 汇报模板.md`。
- 建立或更新 `obsidian-vault/阶段汇报/阶段 23 - Agentic 评测闭环与自动模式路由/`。
- 新增阶段 23 Phase 汇报索引。
- 补齐 Phase 0 到最终 Phase 小汇报。
- 更新 `obsidian-vault/阶段汇报索引.md`。
- 更新 `obsidian-vault/阶段/阶段 23 - Agentic 评测闭环与自动模式路由.md`。
- 每篇小汇报包含：本 Phase 目标、完成的主要任务、新增/修改内容、关键代码或模块、问题与解决方式、新词解释、验证结果、遗留问题、下一 Phase、面试表达。

**验证方式**
- 检查 Obsidian 文件路径和双链。
- 检查每篇小汇报字段齐全。
- 已创建阶段 23 目录、阶段页、Phase 汇报索引和 Phase 0 到 Phase 9 小汇报草稿。
- 已更新 `obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段索引.md`、`obsidian-vault/首页.md`。
- 已校正阶段 22 Obsidian 页的状态为已完成并合并，避免与当前 `phase-22-complete` / `main` 状态冲突。
- 已检查阶段 23 每篇小 Phase 汇报均包含阶段链接、汇报索引链接和 `## 10. 面试表达`。

**完成标准**
- Obsidian 草稿完整但未提交，等待用户人工核验。

### Phase 9：最终待人工核验状态

**状态：已完成**

**解决的问题**：把阶段 23 停在“可核验、未提交”的边界，避免越过用户确认。

**RAG 链路位置**：阶段交付边界。

**为什么现在做**：用户明确要求不要提交、tag、push 或创建 PR。

**任务**
- 最后一次运行 `git status -sb`。
- 确认未创建 `phase-23-complete` tag。
- 汇总主要改动、测试结果、未提交状态和人工核验重点。
- 给出用户确认后建议的提交/tag/push流程，但不执行。

**验证方式**
- `git status -sb`
- `git tag --list phase-23-complete`
- 测试记录在 `progress.md`。
- 已复跑 `.\.venv\Scripts\python.exe scripts\evaluate_stage23_agentic_auto_routing.py`，结果 default/agentic `error_rate=0.000`，decision `reliable_auto_route_candidate`。
- 已复跑 `.\.venv\Scripts\python.exe -m pytest -q`，结果 `463 passed in 27.31s`。
- 已确认当前分支为 `codex/phase-23-agentic-eval-and-auto-routing`。
- 已确认 `phase-23-complete` tag 不存在。
- 已确认阶段 23 未 `git add`、未提交、未推送。

**完成标准**
- 当前分支保持阶段 23 分支。
- 所有阶段 23 改动未提交，等待用户人工核验。
