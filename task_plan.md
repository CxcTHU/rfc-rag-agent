# 阶段 27 任务计划：Chainlit 前端 + Docker 容器化 + GitHub Actions CI

## 目标

在阶段 26「检索性能优化 + Cross-Encoder 重排序」已完成并合并到 `main` 的基础上，完成阶段 27：新增 Chainlit 专业级 AI 对话界面（流式输出、引用展示、步骤可视化、会话管理），并保留原 FastAPI API 与原生前端；用 Docker + docker-compose 容器化应用；用 GitHub Actions 建立 CI 管线自动运行全量测试。阶段完成后停在用户人工核验前，不提交、不打 tag、不推送。

## 硬约束

- 阶段 27 开发完成前后均不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR。
- 不移动任何已有阶段 tag，尤其是 `phase-26-complete`。
- 保留用户或其他 session 的已有改动，不重置 Git，不覆盖无关文件。
- 不做用户认证/登录系统。
- 不引入 `torch` / `sentence-transformers` 等重量级依赖。
- 不让真实 API 成为 CI 或本地全量测试前提。
- 不把 API key、Bearer token、供应商原始敏感响应、受限全文写入 Git、CSV、文档、测试或 Obsidian。
- 保证 `POST /search`、`POST /search/vector`、`POST /search/hybrid`、`POST /chat`、`POST /agent/query`、`POST /agent/query/stream`、`GET /quality-report` 不被破坏。
- FastAPI API 层完整保留，Chainlit 作为前端界面层对接已有后端逻辑，不替代 API。
- Docker 镜像不包含 `.env`、API key、SQLite 数据文件或 Obsidian 知识库。
- GitHub Actions CI 只使用 deterministic provider，不在 CI 中配置真实 API 凭据。

## Phase 顺序

### Phase 0：启动校准与文件计划

**状态：已完成**

**解决的问题**：确认阶段 26 的最终状态、tag、main 起点和阶段 27 分支。

**RAG 链路位置**：阶段起点校准，不改运行链路。

**为什么现在做**：阶段 27 依赖阶段 26 的性能优化和重排序，必须先确认已进入 `main`。

**任务**
- 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 阅读阶段 26 设计文档、phase review，以及根目录 `task_plan.md`、`findings.md`、`progress.md`。
- 核对 `phase-26-complete` tag 指向阶段 26 最终功能提交，且已合并到 main。
- 从阶段 26 完成并合并后的 main 出发，创建或切换到 `codex/phase-27-chainlit-docker-ci`。
- 将根目录三份 Planning with Files 文件校准为阶段 27。

**验证方式**
- `git status -sb`
- `git log --oneline -5`
- `git merge-base --is-ancestor phase-26-complete main`

**完成标准**
- 当前分支为 `codex/phase-27-chainlit-docker-ci`。
- `phase-26-complete` 不移动，且已并入 `main`。
- `task_plan.md`、`findings.md`、`progress.md` 已切换为阶段 27。

**执行记录**
- 已读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage26_retrieval_performance_reranking.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 已确认 `phase-26-complete -> 5000d4fa790d95931862d3f8b2bfc34e91c91ee7 Complete phase 26 retrieval performance reranking`。
- 已确认 `phase-26-complete` 已合并到 `main`，当前 `main`/起点 HEAD 为 `74afce9fa359c25b9730cf414cef69f3db0215da Merge phase 26 retrieval performance reranking`。
- 已从阶段 26 合并后的 `main` 创建并切换到 `codex/phase-27-chainlit-docker-ci`。
- 未移动任何已有阶段 tag，未执行 `git add`、`git commit`、`git tag`、`git push`。

### Phase 1：阶段 27 设计文档

**状态：已完成**

**解决的问题**：把 Chainlit 接入、Docker 容器化和 CI 管线的设计先固化成可审查合同。

**RAG 链路位置**：横跨前端层、部署层和测试自动化。

**为什么现在做**：先明确 Chainlit 与现有 FastAPI 的集成方式、Docker 分层策略和 CI 触发规则，后续实现可以对齐。

**任务**
- 新增 `docs/stage27_chainlit_docker_ci.md`。
- 说明 Chainlit 集成方式：Chainlit 直接调用 Python 服务层（`AgentService`、`detect_chitchat()`、`run_agentic_rag()`、`HybridSearchService`），不经过 HTTP 自调用；FastAPI API 端点保留给外部客户端。
- 说明 Chainlit 功能映射：
  - `@cl.on_message` → 闲聊短路 / default AgentService / agentic LangGraph
  - `cl.Message.stream_token()` → 流式输出（复用 `stream_generate()`）
  - `cl.Step` → agentic workflow 步骤可视化（retrieve / grade / rewrite / generate）
  - `cl.Text` / `cl.Element` → 引用来源、citations 展示
  - 会话管理 → 复用 `ConversationRepository`
- 说明 Docker 分层：基础镜像 `python:3.11-slim`，安装依赖层，复制代码层，暴露端口。
- 说明 docker-compose：应用服务 + SQLite 数据卷挂载 + `.env` 环境变量。
- 说明 GitHub Actions CI：push/PR 触发，`pip install` + `pytest`，deterministic provider，不配置真实 API。
- 说明安全边界和完成标准。

**验证方式**
- 人工阅读文档覆盖阶段 27 验收项。

**完成标准**
- 设计文档存在且覆盖 Chainlit 集成、Docker、CI、安全与收尾标准。

**执行记录**
- 已新增 `docs/stage27_chainlit_docker_ci.md`。
- 文档覆盖 Chainlit 双入口架构、服务层直接调用、`@cl.on_message` 处理顺序、`stream_generate()` 与 `msg.stream_token()` 流式映射、`cl.Step` workflow 展示、`cl.Text` 引用展示、`ConversationRepository` 会话映射、Docker / docker-compose / `.dockerignore` 安全边界、GitHub Actions CI 触发和 deterministic provider 约束。
- 已明确 Chainlit 不删除 FastAPI API，也不删除原生 `app/frontend/` 调试入口。

### Phase 2：Chainlit 前端集成

**状态：已完成**

**解决的问题**：当前原生 HTML/CSS/JS 前端界面粗糙，缺乏专业感。

**RAG 链路位置**：前端展示层，对接已有 Agent/Agentic/检索/会话服务。

**为什么现在做**：后端已稳定（26 阶段、511+ 测试），前端是部署前最后的体验短板。

**任务**
- `pyproject.toml` 新增 `chainlit` 依赖。
- 新增 `chainlit_app.py`（项目根目录），作为 Chainlit 入口。
- 实现 `@cl.on_chat_start`：初始化 DB Session、加载或创建 Conversation。
- 实现 `@cl.on_message`：
  - 调用 `detect_chitchat()`，命中直接回复。
  - 未命中：`classify_query_complexity()` → default `AgentService.query()` 或 `run_agentic_rag()`。
  - 流式输出：使用 `stream_generate()` + `msg.stream_token()`。
  - 引用展示：从 `AgentQueryResult` / `AgenticResult` 提取 citations，用 `cl.Text` 元素展示。
  - 步骤可视化：agentic 路径的 retrieve / grade / rewrite / generate 用 `cl.Step` 展示。
- 实现会话管理：Chainlit 线程 ID 映射到 `Conversation.id`，复用 `ConversationRepository`。
- 保留原有 FastAPI API 端点和原生前端（不删除 `app/frontend/`），Chainlit 作为独立入口并行可用。
- 新增 `.chainlit/config.toml` 配置项目名称、主题色等。
- 补充 Chainlit 集成测试。

**验证方式**
- `chainlit run chainlit_app.py` 可启动。
- 浏览器验证：闲聊短路、RAG 问答流式输出、引用展示、步骤可视化。

**完成标准**
- Chainlit 界面可用，覆盖闲聊、default、agentic 三条路径。
- 流式输出、引用、步骤可视化正常。
- FastAPI 原有 API 不受影响。

**执行记录**
- `pyproject.toml` 已新增 `chainlit>=2.0.0`，本地实际安装验证版本为 Chainlit 2.11.1。
- 新增 `chainlit_app.py`，使用 `@cl.on_chat_start` 初始化 Conversation，使用 `@cl.on_message` 复用 `stream_agent_query_events()` 接入闲聊、default AgentService、agentic LangGraph、流式 token、metadata、引用和步骤展示。
- 新增 `.chainlit/config.toml`，按 Chainlit 2.11.1 当前 schema 配置项目名、布局、CoT 展示、安全项和禁用 MCP/audio。
- 新增 `chainlit.md`，替换 Chainlit 默认欢迎页。
- 新增 `tests/test_chainlit_app.py`，覆盖 SSE event 解析、引用 markdown、workflow markdown、安全 metadata 和 Conversation 映射。
- 新增 `tests/__init__.py`，避免 Chainlit 依赖带来的顶层 `tests` 包遮蔽本仓库测试模块。
- 已验证 `chainlit_app.py` 可在真实 Chainlit 包存在时导入，且短暂启动 `chainlit run chainlit_app.py --host 127.0.0.1 --port 8010 --headless` 后首页返回 HTTP 200。

**验证结果**
```text
.\.venv\Scripts\python.exe -m pytest tests\test_chainlit_app.py tests\test_agent_stream_api.py tests\test_agent_api.py -q
30 passed, 1 warning

chainlit smoke:
GET http://127.0.0.1:8010 -> 200
```

### Phase 3：Docker 容器化

**状态：已完成**

**解决的问题**：项目只能在本机运行，无法分享或部署。

**RAG 链路位置**：部署层，封装应用运行环境。

**为什么现在做**：Chainlit 就绪后，需要把整个应用打包成可移植的容器。

**任务**
- 新增 `Dockerfile`：
  - 基础镜像 `python:3.11-slim`。
  - 安装依赖（利用 Docker 层缓存：先复制 `pyproject.toml`，再 `pip install`，再复制代码）。
  - 暴露端口（Chainlit 默认 8000）。
  - 入口命令 `chainlit run chainlit_app.py --host 0.0.0.0 --port 8000`。
- 新增 `docker-compose.yml`：
  - 应用服务，映射端口 8000:8000。
  - SQLite 数据目录通过 volume 挂载 `./data:/app/data`。
  - `.env` 通过 `env_file` 注入环境变量（不打入镜像）。
- 新增 `.dockerignore`：排除 `.venv`、`__pycache__`、`.git`、`obsidian-vault`、`.env`、`*.sqlite`、`.claude`、`.codex`。
- 验证 `docker-compose up --build` 可启动应用。

**验证方式**
- `docker-compose up --build` 成功启动。
- 浏览器访问容器内 Chainlit 可正常对话。

**完成标准**
- `Dockerfile` + `docker-compose.yml` + `.dockerignore` 存在。
- 容器内应用可启动，Chainlit 界面可访问。
- 镜像不包含 `.env`、API key 或 SQLite 数据文件。

**执行记录**
- 已新增 `Dockerfile`，基于 `python:3.11-slim`，安装项目依赖并以 `chainlit run chainlit_app.py --host 0.0.0.0 --port 8000 --headless` 启动。
- 已新增 `docker-compose.yml`，挂载 `./data:/app/data`，用 `.env` 运行时注入配置，并设置容器内 `DATABASE_URL=sqlite:////app/data/app.sqlite`。
- 已新增 `.dockerignore`，排除 `.env`、`.venv`、`.git`、`.claude`、`.codex`、`obsidian-vault`、SQLite/DB、受限全文目录、raw data 和日志。
- 已新增 `tests/test_docker_assets.py`，静态验证 Dockerfile、compose 和 dockerignore 的关键边界。
- 当前环境未安装 Docker CLI，`docker compose build` 无法执行；已记录为环境限制，后续人工核验需在安装 Docker 的机器上运行 `docker compose up --build`。

**验证结果**
```text
.\.venv\Scripts\python.exe -m pytest tests\test_docker_assets.py -q
3 passed

docker compose build
failed: docker command not found
```

### Phase 4：GitHub Actions CI 管线

**状态：已完成**

**解决的问题**：没有自动化测试管线，代码质量依赖人工运行 pytest。

**RAG 链路位置**：CI/CD 自动化，不改业务链路。

**为什么现在做**：容器化完成后，CI 是部署前最后一个工程化基础设施。

**任务**
- 新增 `.github/workflows/ci.yml`：
  - 触发条件：push 到 `main`、`codex/*`、`claude/*` 分支，以及 PR 到 `main`。
  - 运行环境：`ubuntu-latest`、`python 3.11`。
  - 步骤：checkout → setup python → pip install (含 dev 依赖) → pytest -q。
  - 不配置真实 API key，所有测试使用 deterministic provider。
- 可选：添加 Docker 构建验证步骤（`docker build .` 能成功）。
- 补充 CI 相关说明到 README。

**验证方式**
- CI 配置文件语法正确（`actionlint` 或人工审查）。
- 本地模拟：`pip install -e ".[dev]" && python -m pytest -q` 通过。

**完成标准**
- `.github/workflows/ci.yml` 存在。
- CI 配置使用 deterministic provider，不依赖真实 API。
- README 说明 CI 状态。

**执行记录**
- 已新增 `.github/workflows/ci.yml`，push 到 `main`、`codex/**`、`claude/**` 和 PR 到 `main` 时运行。
- CI 使用 `ubuntu-latest` + Python 3.11，执行 `python -m pip install -e ".[dev]"` 和 `python -m pytest -q`。
- CI 环境变量显式设置 `CHAT_MODEL_PROVIDER=deterministic`、`EMBEDDING_PROVIDER=deterministic`、`RERANKING_PROVIDER=deterministic`，不配置真实 API key。
- 已扩展 `tests/test_docker_assets.py` 覆盖 CI workflow 静态校验。

**验证结果**
```text
.\.venv\Scripts\python.exe -m pytest tests\test_docker_assets.py tests\test_chainlit_app.py tests\test_agent_stream_api.py tests\test_agent_api.py -q
34 passed, 1 warning
```

### Phase 5：端到端验证与回归

**状态：已完成**

**解决的问题**：确认 Chainlit 前端、Docker 容器和 CI 管线全链路可用，既有功能未被破坏。

**RAG 链路位置**：全链路回归。

**为什么现在做**：功能开发完成后必须先测试，再进入文档收尾。

**任务**
- 运行全量测试，目标 >= 511（阶段 26 基线）。
- `docker-compose up --build` 验证容器启动和 Chainlit 可用。
- 浏览器桌面/移动验证 Chainlit 界面。
- 验证 FastAPI 原有 API 端点仍可访问。

**验证方式**
- `pytest` 全量测试。
- 容器内 Chainlit 可正常对话。
- 浏览器验证。

**完成标准**
- 全量测试通过，且不依赖真实 API。
- 容器内 Chainlit 和 FastAPI API 均可正常使用。

**执行记录**
- 已运行全量 pytest，结果 520 passed，超过阶段 26 基线 511。
- 已启动 FastAPI 临时服务 `127.0.0.1:8020`，验证 `/health`、`/agent/query`、`/agent/query/stream`、`/search/hybrid`、`/quality-report`。
- 已启动 Chainlit 临时服务 `127.0.0.1:8021`，验证首页和 `/project/settings` 为 200。
- 已用浏览器检查 FastAPI 原生工作台桌面/移动加载，console error 为 0。
- 已用浏览器检查 Chainlit 桌面/移动加载，console error 为 0。
- 首次 Chainlit 浏览器检查发现 `/project/settings` 500，根因是 Chainlit 2.11.1 data layer 运行时导入 `asyncpg`；已新增 `asyncpg>=0.30.0` 并验证修复。
- 当前环境无 Docker CLI，无法执行 `docker compose up --build`；保留为人工核验重点。

**验证结果**
```text
.\.venv\Scripts\python.exe -m pytest -q
520 passed, 1 warning in 56.85s

FastAPI:
GET /health -> 200
POST /agent/query -> 200
POST /agent/query/stream -> 200, contains event: done
POST /search/hybrid -> 200
GET /quality-report -> 200

Browser:
FastAPI desktop/mobile loaded, console errors=0
Chainlit desktop/mobile loaded, console errors=0
```

### Phase 6：文档同步、Obsidian 收尾与人工核验待提交状态

**状态：已完成**

**解决的问题**：把阶段 27 的设计、代码行为同步到项目文档和 Obsidian，并停在可核验状态。

**RAG 链路位置**：项目知识层和阶段交付边界。

**为什么现在做**：测试通过后文档才能准确描述最终行为。

**任务**
- 更新 `README.md`：新增 Chainlit 启动方式、Docker 启动方式、阶段 27 验证结果。
- 更新 `docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
- 更新 `AGENT.MD`：新增阶段 27 之后 Chainlit、Docker 和 CI 维护规则。
- 建立或更新 Obsidian 阶段 27 目录、汇报索引和各 Phase 小汇报。
- 确认未创建 `phase-27-complete` tag。

**验证方式**
- `git status -sb`
- `git tag --list phase-27-complete`
- 文档无过期表述。

**完成标准**
- 当前分支保持阶段 27 分支。
- 所有阶段 27 改动未提交，等待用户人工核验。

**执行记录**
- 已更新 `README.md`，记录阶段 27 当前状态、Chainlit / Docker 启动方式、全量测试结果和人工核验边界。
- 已更新 `docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`，同步阶段 27 的功能、架构、数据边界和验证结果。
- 已更新 `AGENT.MD`，新增阶段 27 之后 Chainlit / Docker / CI 规则，并把当前推荐第一步改为阶段 27 人工核验。
- 已新增 Obsidian 阶段页、阶段 27 Phase 汇报索引、Phase 0-6 小汇报、Chainlit / Docker / CI 知识点，并更新首页、阶段索引、阶段汇报索引和相关分类页。
- 当前仍未执行 `git add`、`git commit`、`git tag`、`git push`，未创建 PR。

**验证结果**
```text
阶段 27 全量测试：520 passed, 1 warning
FastAPI / Chainlit browser smoke：desktop/mobile console errors=0
Docker CLI：当前环境未安装，docker compose up --build 待用户人工核验
phase-27-complete：未创建
```

### Phase 7：原生前端视觉升级与可用首页

**状态：已完成**

**解决的问题**：当前原生 FastAPI 前端偏后台表格工作台，不像可展示的 AI/RAG 产品首页。

**RAG 链路位置**：前端展示层，复用 `/agent/query/stream`、sources、documents、conversations 等已有 API，不改检索、生成、rerank 或数据库模型。

**为什么现在做**：Docker 部署已跑通，但用户明确前端界面还需要优化；先把本地可访问首页升级成深色科技风作品展示页，再考虑提交。

**任务**
- 参考用户截图，把 `app/frontend/index.html` 改成深色科技风：顶部导航、左侧 hero、能力卡片、右侧可用 Agent demo、资料库状态。
- 保留现有 data 属性和 JS 绑定，确保 Agent 问答、会话管理、来源同步、资料表格仍可用。
- 优化 `app/frontend/static/styles.css`，覆盖桌面和移动端，避免文字溢出、按钮挤压和横向滚动。
- 如需少量 JS 增强，只在 `app/frontend/static/app.js` 内做兼容性小改动，不引入 Node/React/Vue。
- 补充或调整前端测试。

**验证方式**
- `python -m pytest tests/test_frontend_app.py tests/test_docker_assets.py tests/test_chainlit_app.py -q`
- FastAPI 本地启动后浏览器桌面/移动 smoke。
- 确认 Docker/Chainlit 入口不被破坏。

**完成标准**
- 首页视觉接近用户提供的深色科技风参考。
- 原有 FastAPI API、原生前端工作台功能和 Chainlit/Docker 入口不被破坏。
- 暂不提交、暂不创建 tag、暂不 merge、暂不 push。

**执行记录**
- 已重构 `app/frontend/index.html`，新增深色科技风导航、hero、能力卡片、右侧真实 Agent demo 面板、资料库工作台和指标区域。
- 已根据人工反馈继续收敛信息架构：将“开始问答”和“资料库”拆成两个可切换视图，默认显示问答页，资料库通过顶部导航切换。
- 已将首页主标题改为“面向堆石混凝土的 RAG 智能检索系统”，能力展示精简为“混合检索、流式回答、结构化分块”三项。
- 已重写 `app/frontend/static/styles.css`，覆盖桌面与移动端响应式布局，表格在移动端使用内部横向滚动，避免整页被撑宽或拉长。
- 已小改 `app/frontend/static/app.js` 的 `updateMetric()` 和视图切换逻辑，支持同一指标多处同步刷新，并用 `data-view-target` / `data-view` 控制两个页面视图。
- 已更新 `tests/test_frontend_app.py`，覆盖新首页关键文案、结构 class、真实 Agent 面板 hook 和静态资源特征。

**验证结果**
```text
python -m pytest tests/test_frontend_app.py tests/test_docker_assets.py tests/test_chainlit_app.py -q
15 passed, 1 warning

python -m pytest -q
520 passed, 1 warning in 83.56s

FastAPI preview GET http://127.0.0.1:8022 -> 200
桌面 1280x720 浏览器 smoke：console error 0
移动 390x844 浏览器 smoke：console error 0

问答/资料库双视图补充验证：
顶部导航切换到 #library-view 成功
浏览器 console error/warning：0
聚焦回归：15 passed, 1 warning in 1.59s

Reranking API key 最小真实 smoke：
provider=jina，base host=api.jina.ai，api key 已配置；最小 rerank 调用成功，返回 2 条结果并完成解析。未打印 key，未保存供应商原始响应。

提交前最终回归：
python -m pytest -q
520 passed, 1 warning in 145.76s

真实 reranking 配置隔离：
修复两个离线测试误触发真实 rerank 的问题，确保真实 API 不成为全量测试前提。
```
