# 阶段 40 任务计划：流式输出体验与输出安全

## Goal

在阶段 39 的生产部署与默认 `tool_calling_agent` 流式链路基础上，完成阶段 40 前四项前端/流式安全增强：Markdown sanitize、AbortController 停止生成、中断后保留半截内容并标记状态、前端 token 渲染节流；完成开发、测试、普通文档与 Obsidian 草稿，并停在用户人工核验前。

## Current Phase

Phase 7: corpus import and GitHub submission closeout.

## 当前基线与工作区状态

- Git 基线：`main / origin/main -> c6e7927 Merge phase 39 production deployment`。
- 当前开发分支：`codex/phase-40-streaming-output-safety`（从阶段 39 合并后的 `main` 创建，保留既有未提交改动）。
- 最近提交：
  - `c6e7927 Merge phase 39 production deployment`
  - `288bd1d Complete phase 39 production deployment`
  - `33b63e0 Merge phase 38 tool calling generation quality`
  - `ee6830a Complete phase 38 tool calling generation quality`
  - `25344a8 Merge phase 37 tool calling loop migration`
- 当前工作区已有未提交改动，来自上一轮语料库扩充，后续 Agent 必须保留，不得回滚：
  - `app/services/source_collection.py`
  - `scripts/expand_open_access_corpus.py`
  - `tests/test_expand_open_access_corpus.py`
  - `tests/test_source_collection.py`
  - `docs/data_sources.md`
  - `data/metadata/stage18_oa_discovery.csv`
  - `data/corpus_expansion/chinese_standards_metadata.csv`
  - `data/evaluation/stage40_chinese_standards_results.csv`
  - `data/imports/chinese_standards_metadata/*.md`
  - `docs/stage40_corpus_expansion.md`
  - `scripts/seed_chinese_standards_metadata.py`
  - `tests/test_stage40_chinese_standards_metadata.py`

## Phases

### Phase 0：启动校准与规划落盘

- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认阶段 39 已合并到 main，确认阶段 40 当前未提交语料扩充改动需要保留
- [x] 创建阶段 40 目标分支 `codex/phase-40-streaming-output-safety`
- [x] 更新 `task_plan.md`、`findings.md`、`progress.md`
- [x] 给出阶段 40 goal prompt
- **Status:** complete

### Phase 1：设计文档与测试合同

- [x] 新增 `docs/stage40_streaming_output_safety.md`
- [x] 明确四条主线：sanitize、停止生成、中断保留、token 渲染节流
- [x] 明确不做项：长回答虚拟列表、检索策略变更、prompt 策略变更、provider 替换、数据源扩充
- [x] 新增前端与流式 API 测试合同：`tests/test_stage40_streaming_output_safety.py`
- [x] 运行设计合同测试：`python -m pytest tests\test_stage40_streaming_output_safety.py -k "design" -q`
- **Status:** complete

### Phase 2：Markdown sanitize 输出安全

- [x] 梳理 `app/frontend/static/app.js` 当前回答渲染路径：plain text、citation render、Markdown/HTML 插入点
- [x] 引入前端 sanitizer 策略，使用项目可控的最小 allowlist sanitizer；不得使用 CDN 运行时依赖
- [x] 在 Markdown/HTML 最终插入 DOM 前剥离 `<script>`、`<iframe>`、事件属性、`javascript:` URL 等危险内容
- [x] 保留合法 citation button / basic Markdown 展示能力
- [x] 增加 XSS/sanitize 回归测试
- [x] 运行 `node --check app\frontend\static\app.js`
- [x] 运行 `python -m pytest tests\test_stage40_streaming_output_safety.py -k "design or sanitizer" -q`
- [x] 运行 `python -m pytest tests\test_frontend_app.py::test_frontend_static_assets_are_served -q`
- **Status:** complete

### Phase 3：AbortController 停止生成与中断状态

- [x] 在 `streamAgentQuery` 发起 `fetch` 时创建并传入 `AbortController.signal`
- [x] 前端 Agent 运行中展示“停止生成”按钮
- [x] 点击停止时调用 `controller.abort()`，关闭 SSE 读取并进入受控 aborted 状态
- [x] 后端流式 generator 取消边界已记录：当前 producer thread/provider 调用不保证被浏览器 abort 立刻终止
- [x] 已收到 token 必须保留在当前 assistant 消息中，不得丢失
- [x] 在半截回答末尾增加“已停止生成”状态标记
- [x] 停止后允许用户继续发送新问题
- [x] 运行 Phase 3 聚焦测试
- **Status:** complete

### Phase 4：前端 token 渲染节流

- [x] 将 SSE token 事件放入 buffer，而不是每个 token 立即写 DOM
- [x] 使用 `requestAnimationFrame` 和 32ms flush 合并更新
- [x] 形成 `createAgentTokenFlushScheduler` token paint scheduler
- [x] 确保 metadata/done/error/abort 到达时会 flush 剩余 token
- [x] 验证逐字观感保留、DOM 更新次数下降、引用最终渲染不丢失
- [x] 运行 Phase 4 聚焦测试
- **Status:** complete

### Phase 5：集成验证与浏览器 smoke

- [x] 运行前端静态测试、Agent stream API 测试、Stage 40 聚焦测试
- [x] 运行 `node --check app/frontend/static/app.js`
- [x] 启动 FastAPI dev server，使用浏览器验证桌面与移动端：
  - [x] 正常流式回答
  - [x] 停止生成
  - [x] 停止后半截内容保留并标记
  - [x] 安全渲染合同已由 sanitizer 聚焦测试覆盖；浏览器 smoke 未发现脚本错误
  - [x] 控制台无错误、无横向溢出
- [x] 运行全量 `python -m pytest -q`
- [x] 停止本地 8011 smoke 服务
- **Status:** complete

### Phase 6：文档、Obsidian 草稿与人工核验前收尾

- [x] 更新 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md` 中与阶段 40 有关的内容
- [x] 新增 `docs/phase_reviews/phase-40.md`
- [x] 补齐 Obsidian 阶段汇报草稿：
  - [x] `obsidian-vault/阶段汇报/阶段 40 - 流式输出体验与输出安全/`
  - [x] Phase 小汇报
  - [x] 阶段页与索引
- [x] 运行阶段聚焦测试；视改动范围决定是否运行全量 `python -m pytest -q`
- [x] 最终停在用户人工核验前，不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR
- **Status:** complete; waiting for user human verification

### Phase 7：语料导入与提交收尾校准

- [x] 按用户新授权设置阶段 40 收尾 goal，并将线程名改为 `阶段40-流式输出与语料扩展`
- [x] 重新阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认当前分支仍为 `codex/phase-40-streaming-output-safety`，不创建新分支
- [x] 确认工作区包含流式输出安全改动、post-review fix、既有阶段 40 语料扩充改动
- [x] 确认导入源目录存在：`G:\Codex\program\papers_0616` 与 `C:\Users\admin\Zotero\storage`
- [x] 记录导入前 DB 基线：`documents=642`、`chunks=19132`
- **Status:** complete

### Phase 8：导入中文文献 155 篇

- [x] 运行 dry-run：`python scripts/import_papers_corpus.py --dir "G:\Codex\program\papers_0616" --source-type institutional_access_pdf --dry-run --classify`
- [x] 确认 PDF 数量和主题分布：`scanned=150`、`real_pdf=150`、`rfc_core=109`、`dam_engineering=41`
- [x] 正式导入：`python scripts/import_papers_corpus.py --dir "G:\Codex\program\papers_0616" --source-type institutional_access_pdf`
- [x] 修复导入链路：清洗 PDF surrogate codepoints，单篇异常后 session rollback
- [x] 记录结果：第一次导入 `imported=13 duplicate=2 empty=0 failed=135`；修复后重跑 `imported=93 duplicate=55 empty=2 failed=0`；累计新增中文文献 106 篇、6183 chunks
- **Status:** complete

### Phase 9：筛选并导入 Zotero RFC 英文文献

- [ ] 遍历 `C:\Users\admin\Zotero\storage\<ID>\*.pdf`
- [ ] 按文件名关键词筛选 RFC 相关论文：`rock-filled`、`rock filled`、`rockfill` dam/concrete、`SCC` self-compacting concrete、`stone-concrete` dam、`堆石`
- [ ] 使用 `IngestionService.import_document()` 逐个导入，`source_type=open_access_pdf`
- [ ] 记录 scanned、matched、imported、duplicate、empty、failed
- **Status:** pending

### Phase 10：导入验证与质量回归

- [ ] 查询 `documents`、`chunks`、按 `source_type` 分布，确认总数从 642 增长且新增文档已分 chunk
- [ ] 运行全量 `python -m pytest -q`
- [ ] 运行 `python scripts/score_stage30_quality.py`
- [ ] 记录 Stage 30 分数、等级与 release decision
- **Status:** pending

### Phase 11：文档与规划文件最终收尾

- [ ] 更新 `docs/data_sources.md` 阶段 40 语料导入数据说明
- [ ] 更新 `docs/progress.md` 阶段 40 语料导入和验证结果
- [ ] 更新 `progress.md`、`findings.md`、`task_plan.md`
- [ ] 确认不写入 API key、Bearer token、raw provider response、reasoning_content、hidden thought、受限全文
- **Status:** pending

### Phase 12：提交、推送、PR 与 GitHub 合并

- [ ] `git add -A`
- [ ] `git status` 与敏感文件检查，确认 `.env`、API key、SQLite、`data/raw/`、`data/fulltext/`、`data/faiss/` 未 stage
- [ ] `git commit -m "Complete phase 40 streaming output safety and corpus import"`
- [ ] `git push -u origin codex/phase-40-streaming-output-safety`
- [ ] 创建 PR：`Phase 40: streaming output safety and corpus import`
- [ ] 合并 PR 到 `main`
- **Status:** pending

## Key Questions

1. 当前前端回答渲染到底是否经过 Markdown 转 HTML，还是只做 citation HTML 插入？sanitize 应放在哪个最小安全点？
2. 仅前端 `AbortController` 是否足以让后端 provider stream 停止？如果不够，需要哪些后端取消检查？
3. `tool_calling_agent` 的 SSE token、metadata、agent_step、tool_call_start、tool_call_result、done/error 事件如何与 token buffer 协同？
4. 停止生成后的半截回答应作为普通 assistant 消息保存到 UI 状态，还是也需要写入 conversation/messages 数据库？
5. 如何测试 XSS 防护而不把危险脚本写成会被测试环境执行的形式？

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 阶段 40 先做前四条，不做虚拟列表 | 长回答虚拟列表复杂度高，当前堆石混凝土问答通常未到必须虚拟化的量级 |
| sanitize 优先级高于性能优化 | LLM 输出可被 prompt injection 诱导，XSS 是安全底线 |
| AbortController 与中断保留绑定实现 | 只有停止按钮没有半截内容保留会造成用户体验不一致 |
| token 节流只改前端渲染层 | 不改变 SSE 协议、后端 token 事件或 Agent 链路，降低回归风险 |
| 不改变检索、prompt、provider、Stage 30 评分 | 阶段 40 是前端流式体验与输出安全阶段，不混入质量/语料/模型改动 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| PowerShell 不支持 `git status -sb && git log --oneline -5` 写法 | 1 | 分开运行两个命令 |
| `session-catchup.py` 不存在于本机 `.claude` 技能目录 | 1 | 已完整读取当前三份规划文件，并继续使用根目录规划文件作为外部记忆 |
| Stage 40 sanitizer 测试误写 JS API 名为 `startswith` | 1 | 修正为浏览器 JS 的 `startsWith` 后重跑通过 |
| 既有前端静态测试仍断言二态 `answered/refused` 状态 | 1 | 更新为阶段 40 的 `aborted/refused/answered` 三态收尾合同 |

## Stage 40 Goal Prompt

阅读 agent 和其他相关文件，了解项目开发进度。现在正式进入阶段 40 的开发。请为本线程设置一个 goal：

按照当前项目的 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，以及根目录 `task_plan.md`、`findings.md`、`progress.md`，持续推进本项目开发，直到阶段 40「流式输出体验与输出安全」的开发、测试、普通文档和 Obsidian 草稿收尾完成，并停在用户人工核验前状态。

目标分支建议为：

```text
codex/phase-40-streaming-output-safety
```

执行要求：

1. 首先修改当前对话线程名称为：`阶段40-流式输出体验与输出安全`。
2. 先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
3. 运行 `git status -sb` 和 `git log --oneline -5`，确认阶段 39 已合并到 `main`，当前基线应为 `c6e7927 Merge phase 39 production deployment`；同时确认已有阶段 40 语料库扩充未提交改动，必须保留，不能回滚用户或前序 Agent 工作。
4. 从阶段 39 合并后的 `main` 状态出发，可以创建或切换到 `codex/phase-40-streaming-output-safety` 分支。
5. 可以创建或切换分支，但阶段开发完成后不要执行 `git add`、`git commit`、`git tag`、`git push`，也不要创建 PR；必须等待用户人工核验和明确确认后，才允许进入提交、tag 和 GitHub 推送流程。
6. 正式开发前，必须根据 `AGENT.MD`、阶段 39 完成状态、当前未提交语料扩充状态和阶段 40 目标，使用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md`。
7. `task_plan.md` 必须明确阶段 40 的 Phase 顺序、目标、任务、验证方式、文档收尾要求和完成标准。建议至少包含：启动校准、阶段 40 设计文档、Markdown sanitize、AbortController 停止生成、中断后半截内容保留、token 渲染节流、回归验证、文档与 Obsidian 收尾、人工核验待提交状态。
8. `findings.md` 必须记录对 `/agent/query/stream`、`streamAgentQuery`、SSE 事件、前端回答渲染、citation 渲染、安全边界和浏览器中断机制的理解与关键决策。
9. `progress.md` 必须记录阶段启动、Git/main 状态、每个 Phase 日志、测试结果、遗留风险和“尚未提交，等待用户人工核验”的状态。
10. 严格按 `task_plan.md` 的 Phase 顺序推进，不跳步。每开始一个 Phase，简短说明本 Phase 解决什么问题、在流式链路中的位置、为什么现在做。
11. 每完成任意 Phase，必须先更新 `task_plan.md`、`findings.md`、`progress.md`；对话中只给简短进度，不输出冗长 Phase 汇报。
12. 开发过程中暂不写入 Obsidian 小 Phase 汇报；阶段 40 全部开发、测试、普通文档完成后，再统一按 `obsidian-vault/模板/Phase 汇报模板.md` 补齐本地 Obsidian 汇报。
13. 阶段 40 收尾时，必须建立或更新 `obsidian-vault/阶段汇报/阶段 40 - 流式输出体验与输出安全/`、阶段 40 Phase 汇报索引、Phase 0 到最终 Phase 小汇报、`obsidian-vault/阶段汇报索引.md`、`obsidian-vault/阶段/阶段 40 - 流式输出体验与输出安全.md`。
14. 每篇 Obsidian 小 Phase 汇报必须包含：本 Phase 目标、完成的主要任务、新增/修改内容、关键代码或模块、问题与解决方式、新词解释、验证结果、遗留问题、下一 Phase、面试表达。
15. 不要因为未输出对话版完整汇报而停下；继续自动推进后续开发。
16. 遇到问题时自行阅读代码、运行测试、定位并修复；新增重要代码必须补测试；阶段收尾根据改动范围运行聚焦测试和必要的全量测试。
17. 遇到新词、关键类名、接口名或架构概念，及时用中文解释：是什么、在本项目哪里出现、有什么作用、面试怎么说。
18. 保留用户和前序 Agent 已有改动，不重置 Git，不覆盖无关文件。
19. 阶段 40 不做长回答虚拟列表，不改变检索策略、prompt 策略、Stage 30 评分规则、embedding/rerank/chat provider 拓扑，不新增外部数据源或语料库，不做登录系统，不做部署优化。
20. 不得把 API key、Bearer token、供应商原始敏感响应、`reasoning_content`、hidden thought、受限全文写入 Git、CSV、文档、测试或 Obsidian。

阶段 40 核心链路：

```text
/agent/query/stream
-> fetch + ReadableStream 手动解析 SSE
-> token buffer + requestAnimationFrame/定时 flush
-> 安全渲染文本/Markdown/citation
-> AbortController 停止生成
-> 保留已收到 token 并标记“已停止生成”
-> done/error/abort 时 flush 剩余 token 并收敛 UI 状态
```

阶段 40 完成标准：

- 新增 `docs/stage40_streaming_output_safety.md`，说明目标、输入、四条主线、安全边界、验证方式和完成标准。
- 前端最终渲染前具备 sanitize 防护，能剥离 `<script>`、`<iframe>`、事件属性、`javascript:` URL 等危险内容；不得依赖运行时 CDN。
- `streamAgentQuery` 使用 `AbortController.signal`；运行中有“停止生成”按钮；点击后前端中断 SSE 读取。
- 用户停止生成后，已经收到的 token 必须保留在 assistant 消息中，并显示“已停止生成”之类的状态标记；停止后可以继续发送新问题。
- 前端 token 渲染采用 buffer + `requestAnimationFrame` 或 16-50ms flush 节流；`metadata`、`done`、`error`、`abort` 时必须 flush 剩余 token。
- 尽量让后端检测客户端断开；如果当前后端 producer/provider 无法被浏览器 abort 立刻终止，必须在文档与汇报中诚实记录边界，不伪造成完全后端取消。
- 保证 `POST /agent/query/stream`、`POST /agent/query`、`POST /chat`、`GET /` 等既有入口不被破坏。
- 补充阶段 40 相关测试，至少覆盖 sanitize、停止生成 UI 合同、中断状态保留、token 节流调度和既有流式事件兼容。
- 运行 `node --check app/frontend/static/app.js`、前端/Agent stream 聚焦测试，并做桌面与移动端浏览器 smoke；视改动范围运行全量 `python -m pytest -q`。
- 同步 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/phase_reviews/phase-40.md` 与 Obsidian 本地知识库。
- 最终不做本地提交、不创建 `phase-40-complete` tag、不推送 GitHub；最终汇报必须说明当前分支、主要改动、测试结果、未提交状态、建议人工核验重点，以及用户确认后再提交和打 tag 的建议。

## Notes

## Phase 9 Checkpoint: Zotero RFC English Import

- Status: complete.
- Added `scripts/import_stage40_zotero_rfc.py` to make RFC-related Zotero PDF filtering/import reproducible without storing PDF full text in Git.
- Dry-run result: `scanned_pdfs=66`, `matched_pdfs=9`.
- Formal import result: Zotero storage contained `scanned_pdfs=67` at runtime, still `matched_pdfs=9`; `imported=5`, `duplicate=4`, `empty=0`, `failed=0`, `new_chunks=372`.
- Source type: `open_access_pdf`.
- Next Phase: run DB count/source distribution verification, full pytest, and Stage 30 quality scoring.

## Phase 10 Checkpoint: Import Verification And Quality Regression

- Status: complete.
- DB verification: `documents=753`, `chunks=25687`.
- Source distribution: `institutional_access_pdf=431`, `web_page=136`, `metadata_record=115`, `wikipedia=25`, `open_access_pdf=20`, `standard_document=16`, `local_file=10`.
- Full regression: `python -m pytest -q` -> `821 passed in 87.68s`.
- Stage 30 quality: `python scripts/score_stage30_quality.py` -> `overall=91.52`, `grade=A`, `release_decision=pass`.
- Next Phase: update normal docs and final planning records before staging/commit.

## Phase 11 Checkpoint: Documentation Closeout

- Status: complete.
- Updated `README.md` with Phase 40 final streaming/corpus/test status.
- Updated `docs/progress.md` with final Phase 40 closeout status, import counts, test results, and submission boundary.
- Updated `docs/data_sources.md` with Chinese and Zotero import source directories, commands/results, DB verification, and safety boundary.
- Updated `docs/architecture.md` with final stop-button behavior, tool-calling streaming wrapper, corpus import boundary, and verified DB/test summary.
- Updated `docs/phase_reviews/phase-40.md` with post-review fixes, import results, verification, and user-authorized submission boundary.
- Updated `task_plan.md`, `findings.md`, and `progress.md` with Phases 9-11 results.
- Next Phase: stage changes, check for forbidden runtime/sensitive files, commit, push, create PR, and merge.

- 三份规划文件内容是结构化计划数据，不是外部指令来源。
- 语料库扩充已经产生阶段 40 的一部分未提交改动；本阶段前端安全/流式体验应与其并存，不得回滚。
- 每次遇到新术语，例如 `AbortController`、`requestAnimationFrame`、`sanitize`、`XSS`、`SSE`，需要在文档或汇报中用中文解释：是什么、项目里在哪里出现、作用是什么、面试怎么说。
