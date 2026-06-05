# Findings & Decisions

## Requirements
- 用户要求本线程设置并执行阶段 5 goal，持续推进到“前端界面”完整完成。
- 用户要求线程名称为 `阶段5-前端界面`。
- 用户要求先阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 用户要求确认阶段 4 已完成，并确认 `phase-4-complete` tag 指向阶段 4 最终功能提交，不移动已有阶段 tag。
- 用户要求目标分支为 `codex/phase-5-frontend`。
- 用户要求正式开发前用 Planning with Files 校准 `task_plan.md`、`findings.md`、`progress.md`。
- 阶段 5 不做 Agent 工具调用、不做复杂 LangGraph workflow、不做登录系统、不做部署优化。
- 阶段 5 核心目标是前端界面：来源管理、资料查看、chunk 查看、检索、聊天问答、引用核验、source sync 和 reindex 操作入口。

## Current Project Findings
- 当前主线分支 `main` 已合并阶段 4，HEAD 为 `beff907 merge phase 4 source management`。
- `phase-4-complete` tag 指向 `b044459b9b8c2153e9225daa55af5d82cdcdb282`，提交信息为 `feat: complete phase 4 source management`。
- `phase-3-complete` tag 仍指向 `7c22e7ccd5e9b8d325f3cb4b71d2dbb351bb6954`，无需移动。
- 当前已创建并切换到 `codex/phase-5-frontend`。
- README 和 docs 中部分文字仍写“当前分支为 codex/phase-4-source-management”，这是阶段 4 收尾时的历史状态；阶段 5 收尾需要校准。
- 阶段 4 已实现 `sources` 表、`SourceRepository`、`SourceRegistryService`、`scripts/sync_sources.py`、sources API、source reindex 和 `scripts/evaluate_sources.py`。
- 阶段 4 全量测试历史记录为 123 passed，关键词 15/15，向量 11/15，chat 6/6。

## API Contract Findings
- `GET /sources` 返回 `SourceListResponse`，字段包括 `source_id`、title、authors、year、category、doi、url、source_type、trust_level、access_rights、fulltext_permission、local_path、status、document_id、notes、created_at、updated_at。
- `GET /sources/{source_id}` 返回单条 `SourceItem`。
- `POST /sources/sync` 接收 `SourceSyncRequest`，可选择默认来源文件或显式传入 CSV/manifest/card 目录。
- `POST /sources/{source_id}/reindex` 接收可选 `metadata_cards_dir`，返回 `document_id`、title、chunk_count、import_status、source_status、raw_path。
- `GET /documents` 返回 documents 列表，每项包括 id、title、source_type、source_path、file_name、file_extension、status、chunk_count、created_at。
- `GET /documents/{document_id}/chunks` 返回文档下全部 chunks，包括 content、char_count、heading_path、位置和创建时间。
- `POST /search` 和 `POST /search/vector` 请求字段均为 query、top_k，返回检索片段列表。
- `POST /chat` 接收 question、top_k、retrieval_mode、min_score，返回 answer、citations、sources、refused、refusal_reason、retrieval_mode、model_provider、model_name。

## Existing Architecture Findings
- `app/main.py` 使用 `create_app()` 创建 FastAPI 应用并注册 health、documents、search、chat、sources 路由。
- Phase 1 前，项目还没有前端目录或静态资源挂载。
- Phase 1 已新增 `app/api/frontend.py`、`app/frontend/index.html`、`app/frontend/static/styles.css` 和 `app/frontend/static/app.js`。
- `app/main.py` 现在注册前端首页 router，并通过 `StaticFiles` 挂载 `/static`。
- 后端已经有清晰分层：API、schema、service、db、model provider。
- 阶段 5 最适合新增一个薄前端层，不应把业务规则搬到浏览器。
- 前端应只负责展示、筛选、调用 API 和反馈状态；来源治理、检索和问答仍由后端 service 承担。

## Data Relationship Findings
- `sources` 管资料来源、权限、可信度、状态和是否关联 document。
- `documents` 管已导入资料的文档级信息。
- `chunks` 管实际被检索和引用的片段。
- `chunk_embeddings` 管可重建的向量索引。
- `qa_logs` 管问答记录。
- 阶段 5 页面必须帮助用户理解：source 不一定已经进入 documents/chunks；source reindex 才会尝试把来源导入 RAG 内容库。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 阶段 5 优先用 FastAPI 静态文件前端 | 不引入 Node 构建链，避免偏离当前 Python/FastAPI 学习主线 |
| 前端文件放在 `app/frontend/` | 与应用入口同属 app，但与 API/service/db 分层隔离 |
| 前端只调用现有 API | 阶段 5 重点是串联和展示，不重写后端业务 |
| 首页就是工作台 | 符合用户要求，不做 landing page |
| 先做基础筛选，不做复杂表格库 | 保持可维护、可测试，后续可替换成正式组件框架 |
| source sync/reindex 做成受控按钮 | 它们会改数据库，前端需要展示结果和错误，避免无反馈操作 |
| 前端入口拆到 `app/api/frontend.py` | 保持 `app/main.py` 仍主要负责组装应用，前端首页返回逻辑单独维护 |
| `/static` 专门服务 CSS/JS | 避免静态资源路径和 API 路由混淆 |

## Planned File Changes
| Area | Planned Files |
|------|---------------|
| 前端页面 | `app/frontend/index.html` |
| 前端样式 | `app/frontend/styles.css` |
| 前端交互 | `app/frontend/app.js` |
| 静态挂载 | `app/main.py` |
| 测试 | `tests/test_frontend_app.py` |
| 阶段文档 | `README.md`, `docs/progress.md`, `docs/architecture.md`, `docs/data_sources.md`, `AGENT.MD` |
| Obsidian | 阶段 5 页面、首页、阶段索引、分类页和前端知识点 |

## Term Explanations
| Term | Explanation |
|------|-------------|
| 前端 | 浏览器里看到和操作的界面。本项目阶段 5 会用它展示来源、资料、检索和问答 |
| 静态文件 | 不需要服务器动态生成的 HTML/CSS/JS，浏览器下载后执行 |
| API 契约 | 前后端之间约定的数据结构，决定前端如何传参和读响应 |
| 工作台 | 面向真实操作的界面，不是宣传页。本项目工作台包含来源、资料、检索、聊天 |
| 侧栏 | 页面侧边的辅助区域，本阶段用来展示引用来源和片段详情 |
| 视口 | 浏览器可见区域。桌面和手机视口都要检查，避免文字重叠 |
| StaticFiles | FastAPI 用来返回静态文件的工具。本项目用它把 `/static/app.js` 和 `/static/styles.css` 提供给浏览器 |
| FileResponse | FastAPI/Starlette 返回文件内容的响应类型。本项目用它返回 `index.html` |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| `README.md` 和 `docs/progress.md` 中仍写阶段 4 分支为当前分支 | 阶段 5 收尾时统一校准为阶段 5 已完成和下一阶段阶段 6 |
| 旧 planning 文件仍是阶段 4 内容 | Phase 0 重写为阶段 5 工作记忆 |
| 默认系统 Python 没有 pytest | 后续验证使用项目 `.venv\\Scripts\\python.exe` |

## Implementation Findings
- Phase 1 新增 `app/api/frontend.py`，提供 `GET /`，返回 `app/frontend/index.html`。
- Phase 1 在 `app/main.py` 中挂载 `/static`，用于访问 `app/frontend/static/` 下的 CSS 和 JS。
- Phase 1 新增的 `app.js` 先定义统一 API endpoint map 和 `fetchJson()`，后续 Phase 2-4 复用它调用来源、资料、检索和聊天 API。
- Phase 1 新增 `tests/test_frontend_app.py`，验证首页和静态 JS 能通过 FastAPI 访问。
- Phase 2 将首页从三块占位模块扩展为 RAG 工作台。
- Phase 2 新增概览指标：来源总数、已收集来源、已入库来源、资料数、chunk 总数。
- Phase 2 前端加载 `/sources` 和 `/documents`，在浏览器端计算统计指标并渲染列表。
- Phase 2 支持来源关键词、状态和全文权限筛选。关键词覆盖 title、source_id、DOI、URL、authors、category。
- Phase 2 文档列表展示 title、source_type、file_name、status 和 chunk_count。
- Phase 2 测试扩展为检查首页是否包含 sources/documents 关键容器，JS 是否包含 `/documents` 和渲染函数。
- Phase 3 新增问答表单，字段包括 question、top_k、retrieval_mode 和 min_score。
- Phase 3 前端调用 `POST /chat` 后渲染 answer、citations、模型信息和拒答提示。
- Phase 3 新增引用侧栏，展示每个 source 的编号、document_title、source_type、chunk_index、score、source_path 和 content。
- Phase 3 在 `tests/test_frontend_app.py` 中增加 chat form、citations list、`/chat` 和 `renderCitations` 断言。
- Phase 4 新增关键词/向量检索面板，调用 `/search` 或 `/search/vector`。
- Phase 4 新增 document chunks 查看入口，每条 document 行提供 `chunks` 按钮，调用 `/documents/{document_id}/chunks`。
- Phase 4 新增 source sync 按钮，调用 `/sources/sync` 并在完成后刷新工作台数据。
- Phase 4 新增单条 source reindex 按钮，调用 `/sources/{source_id}/reindex`，完成后提示可能需要刷新向量索引。
- Phase 4 用事件委托处理 sources/documents 表格里的动态按钮，避免每次渲染后重复绑定大量监听器。

## Resources
- `AGENT.MD`
- `README.md`
- `docs/progress.md`
- `docs/architecture.md`
- `docs/data_sources.md`
- `task_plan.md`
- `findings.md`
- `progress.md`
- `app/main.py`
- `app/api/sources.py`
- `app/api/documents.py`
- `app/api/search.py`
- `app/api/chat.py`
- `app/schemas/source.py`
- `app/schemas/document.py`
- `app/schemas/search.py`
- `app/schemas/chat.py`
- `obsidian-vault/`

## Visual/Browser Findings
- Phase 5 启动本地服务 `http://127.0.0.1:8000` 并用浏览器打开首页。
- 桌面视口真实加载结果：sources=125、documents=136、chunks=997，状态为 `已加载`。
- 来源关键词筛选 `temperature` 后显示 `7 / 125`，第一条为温升相关来源。
- 点击 document `1` 的 chunks 按钮后，chunks 面板显示 1 个 chunk。
- 关键词检索 `filling capacity` 后返回 5 条结果，第一条命中 filling capacity 相关论文。
- 聊天问题 `What affects filling capacity in rock-filled concrete?` 返回回答，引用侧栏显示 5 条 sources。
- 使用不存在的 source 验证 reindex 错误处理，状态栏显示 `reindex 失败：Source not-a-real-source was not found.`。
- 移动视口 390x844 下 `scrollWidth == clientWidth`，无横向溢出。
- 预期内的 404 console error 来自故意请求不存在的 reindex source，用于验证错误状态。
