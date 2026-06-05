# Task Plan: 阶段 5 - 前端界面

## Goal
在阶段 4 已完成 source registry、来源同步、reindex 和引用式问答 API 的基础上，建立一个面向非技术用户的前端工作台。阶段 5 要让用户能通过界面查看来源、资料、chunk、检索结果、聊天回答和引用来源，并能触发来源同步或单条来源重新索引。

阶段 5 不做 Agent 工具调用、不做复杂 LangGraph workflow、不做登录系统、不做部署平台优化。本阶段优先保证前端入口可运行、信息架构清楚、核心 API 链路可操作、错误和空状态可理解、浏览器验证可复现。

## Current Phase
Phase 6 complete。阶段 5 文档、Obsidian、本地验证、最终功能提交和 `phase-5-complete` tag 收尾完成；阶段 5 已达到完成标准。最终功能提交为 `8c885e6cc714cc985933438697a7eb2523b26722`。

## Phases

### Phase 0: 阶段 5 启动与规划文件校准
- [x] 将线程标题修改为 `阶段5-前端界面`。
- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- [x] 阅读旧 `task_plan.md`、`findings.md`、`progress.md`，确认其仍记录阶段 4 工作记忆。
- [x] 确认当前主线已合并阶段 4，`main` 指向 `beff907 merge phase 4 source management`。
- [x] 确认 `phase-4-complete` tag 指向阶段 4 最终功能提交 `b044459b9b8c2153e9225daa55af5d82cdcdb282`，不移动该 tag。
- [x] 从 `main` 创建并切换到 `codex/phase-5-frontend` 分支。
- [x] 使用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md` 为阶段 5 工作记忆。
- [x] 输出 Phase 0 阶段汇报。
- **Status:** complete

### Phase 1: 前端架构与 API 契约
- [x] 梳理现有 API 契约：`GET /sources`、`GET /sources/{source_id}`、`POST /sources/sync`、`POST /sources/{source_id}/reindex`、`GET /documents`、`GET /documents/{document_id}/chunks`、`POST /search`、`POST /search/vector`、`POST /chat`。
- [x] 决定前端实现方式：采用 FastAPI 静态文件 + 原生 HTML/CSS/JS，避免阶段 5 引入过重构建链。
- [x] 明确页面结构：概览、来源管理、资料库、检索片段、聊天问答、引用来源侧栏。
- [x] 明确数据流、加载状态、错误状态、空数据状态和浏览器验证方式。
- [x] 新增前端入口、静态资源挂载和入口测试。
- **Status:** complete

### Phase 2: 资料与来源管理界面
- [x] 实现第一屏可用的 RAG 工作台，不做营销 landing page。
- [x] 展示 sources 列表和关键字段：标题、状态、可信度、全文权限、年份、分类、DOI/URL、document_id。
- [x] 支持来源关键词筛选、状态筛选、权限筛选。
- [x] 展示 documents 列表：标题、source_type、文件名、状态、chunk_count、创建时间。
- [x] 通过概览指标和并列表格展示 `sources` 与 `documents/chunks` 的关系。
- [x] 补充必要测试并更新规划文件。
- **Status:** complete

### Phase 3: 聊天问答界面与引用来源侧栏
- [x] 实现问题输入和回答展示区域。
- [x] 调用 `POST /chat`，支持 top_k、retrieval_mode 和 min_score。
- [x] 展示 answer、citations、sources、refused、refusal_reason、retrieval_mode、model_provider、model_name。
- [x] 用侧栏展示引用来源：标题、chunk、score、source_path 和片段内容。
- [x] 对拒答场景给出清楚提示。
- [x] 补充必要测试并更新规划文件。
- **Status:** complete

### Phase 4: 检索片段查看、source sync 与 reindex 操作
- [x] 提供关键词检索和向量检索入口。
- [x] 支持查看某篇 document 的 chunks。
- [x] 提供 source sync 操作入口。
- [x] 提供单条 source 的 reindex 操作入口。
- [x] 对成功、失败、空数据、接口错误提供清楚反馈。
- [x] 提示 reindex 后如需语义检索生效，可能还要刷新向量索引。
- [x] 补充必要测试并更新规划文件。
- **Status:** complete

### Phase 5: 前端测试、浏览器验证与体验修正
- [x] 运行前端入口和 API 集成相关测试。
- [x] 保证 documents/search/vector/chat/sources 既有测试不被破坏。
- [x] 启动本地服务。
- [x] 用浏览器验证：打开首页、查看 sources、查看 documents、查看 chunks、提问并看到回答和引用、触发 reindex 错误处理。
- [x] 检查桌面和移动视口下无明显重叠、文字可读、按钮可点击。
- [x] 运行全量测试。
- **Status:** complete

### Phase 6: 阶段收尾文档、Obsidian、提交与 tag
- [x] 更新 `README.md`，说明阶段 5 前端功能、启动方式、验证方式和下一阶段。
- [x] 更新 `docs/progress.md`，记录阶段 5 完成内容、验证结果、遗留问题、下一阶段任务和面试表达。
- [x] 更新 `docs/architecture.md`，补充前端架构、页面结构、API 调用链路。
- [x] 判断并更新 `docs/data_sources.md`，说明 source registry 在前端中的展示和操作入口。
- [x] 判断并更新 `AGENT.MD`，将后续默认起点校准为阶段 6：检索优化与评测。
- [x] 更新 Obsidian 本地知识库：首页、阶段索引、阶段 5 页面、分类页和重要知识点。
- [x] 创建阶段最终功能提交：`8c885e6cc714cc985933438697a7eb2523b26722`。
- [x] 创建 `phase-5-complete` tag，确保 tag 指向阶段 5 最终功能提交。
- [x] 最终汇报阶段提交号和 tag 名称。
- **Status:** complete

## Key Questions
1. 阶段 5 前端用什么技术实现？
   - 初步答案：当前项目是 FastAPI 后端，没有 Node/React 基础设施。阶段 5 优先采用 FastAPI 挂载静态 HTML/CSS/JS，少引依赖、易测试、易讲清楚。后续如果需要更复杂交互，再迁移到 React/Next.js。
2. 首页应该是什么？
   - 初步答案：首页直接是资料与来源工作台，不能做营销页。第一屏应能看到来源统计、资料统计、搜索/聊天入口和主要操作。
3. 前端要不要支持上传？
   - 初步答案：阶段 5 完成标准强调查看资料、管理来源、提问和核验引用。上传可保留后续扩展；本阶段优先把已有 API 串通。
4. reindex 后是否自动刷新向量索引？
   - 初步答案：阶段 4 只有 reindex 入口，没有后台任务队列。阶段 5 前端先触发 reindex 并提示需要刷新向量索引，是否自动构建视实现复杂度决定。
5. 如何验证前端不是只写了静态页面？
   - 初步答案：用测试确认前端入口可访问，用浏览器实际打开页面并检查 sources/documents/chunks/chat/reindex 或错误处理。

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 从 `main` 创建 `codex/phase-5-frontend` | 阶段 4 已合并到 `main`，从主线继续最稳妥 |
| 不移动 `phase-4-complete` tag | AGENT 要求阶段 tag 指向对应阶段最终功能提交 |
| 前端优先轻量实现 | 项目后端已稳定，阶段 5 目标是非技术用户可操作，不需要先引入重型前端构建链 |
| 第一屏做工作台 | 用户明确要求不是 landing page，RAG 项目应优先展示可操作数据和问答入口 |
| 每个 Phase 后更新三份规划文件 | Planning with Files 是本阶段工作记忆和恢复依据 |

## Planned File Changes
| Area | Planned Files |
|------|---------------|
| 前端静态资源 | `app/frontend/index.html`, `app/frontend/styles.css`, `app/frontend/app.js` |
| 前端路由挂载 | `app/main.py` |
| 前端测试 | `tests/test_frontend_app.py` |
| 文档 | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | `obsidian-vault/首页.md`, `obsidian-vault/阶段索引.md`, `obsidian-vault/阶段/阶段 5 - 前端界面.md`, `obsidian-vault/知识点/*.md`, `obsidian-vault/分类/*.md` |

## Term Explanations
| Term | Explanation |
|------|-------------|
| 前端工作台 | 面向用户的操作界面，本阶段用于查看来源、资料、chunk、检索结果和问答引用 |
| 静态资源 | HTML、CSS、JS 文件。它们由 FastAPI 直接返回给浏览器，不需要额外打包工具 |
| API 契约 | 前端和后端约定的数据格式，例如请求字段、响应字段和错误状态 |
| 引用来源侧栏 | 在回答旁边展示 citations 对应资料片段的区域，帮助用户核验回答依据 |
| 空数据状态 | 当没有来源、没有资料或没有检索结果时，界面给出的可理解提示 |
| reindex | 重新把已登记来源导入 `documents/chunks`，让它能进入 RAG 检索链路 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| 旧 planning 文件仍记录阶段 4 | 1 | 进入阶段 5 后重写 `task_plan.md`、`findings.md`、`progress.md` |

## Notes
- 本文件由 Planning with Files 维护，是阶段 5 的工作记忆。
- 每个 Phase 完成后，必须先更新 `task_plan.md`、`findings.md`、`progress.md`，再输出完整 Phase 阶段汇报。
- 阶段 5 的重点是前端体验和 API 串联，不是 Agent 化或检索质量优化。
