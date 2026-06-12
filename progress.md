# 阶段 27 进度日志：Chainlit 前端 + Docker 容器化 + GitHub Actions CI

## 当前状态

- 当前阶段：阶段 27「Chainlit 前端 + Docker 容器化 + GitHub Actions CI」。
- 当前分支：`codex/phase-27-chainlit-docker-ci`。
- 前置条件：阶段 26 已完成提交、创建 `phase-26-complete` tag，并合并到 main。
- 阶段 27 状态：Phase 0-6 已完成，开发、测试、普通文档、Obsidian 草稿和阶段验收报告已收尾；Docker Desktop 安装后，Docker Compose 部署已实跑通过。
- 提交状态：用户已授权验收、提交阶段 27 整体开发工作、创建 `phase-27-complete` tag、合并并推送 GitHub。

## 阶段 27 目标概述

从阶段 26 完成后的 main 出发，实现三件事：

1. **Chainlit 前端**：新增专业级 AI 对话界面，并保留原 FastAPI API 与原生前端。Chainlit 直接调用 Python 服务层（不经过 HTTP 自调用），复用 `AgentService`、`detect_chitchat()`、`run_agentic_rag()`、`ConversationRepository` 等已有逻辑。支持流式输出（`stream_generate()` + `msg.stream_token()`）、引用展示（`cl.Text`）、agentic 步骤可视化（`cl.Step`）和会话管理。
2. **Docker 容器化**：`Dockerfile` + `docker-compose.yml`，打包 FastAPI + Chainlit，SQLite 数据卷挂载，`.env` 环境变量注入。镜像不含凭据或数据文件。
3. **GitHub Actions CI**：push/PR 触发 pytest 全量测试，使用 deterministic provider，不配置真实 API。

## 阶段 26 验收基线

- 阶段 26 验收结论：已提交、已打 `phase-26-complete` tag、已合并到 `main`。
- `phase-26-complete -> 5000d4fa790d95931862d3f8b2bfc34e91c91ee7 Complete phase 26 retrieval performance reranking`。
- 阶段 26 合并提交：`74afce9fa359c25b9730cf414cef69f3db0215da Merge phase 26 retrieval performance reranking`。
- 已验证 `phase-26-complete` 是 `main` 的祖先，未移动任何已有阶段 tag。
- 测试基线：511 passed。
- 关键交付：numpy 向量化（vector search 1456ms→335ms）、BM25+vector 并行、Cross-Encoder ReRankingProvider、端到端 hybrid 2199ms→733ms。

## Phase 0 日志：启动校准与文件计划

时间：2026-06-12

已完成：

- 已按入口规则读取 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`docs/stage26_retrieval_performance_reranking.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 已运行 `git status -sb`：启动时位于 `main...origin/main`，根目录 `task_plan.md`、`findings.md`、`progress.md` 有阶段 27 预填改动。
- 已运行 `git log --oneline -5`：最近提交为 `74afce9 Merge phase 26 retrieval performance reranking`、`5000d4f Complete phase 26 retrieval performance reranking` 等。
- 已确认 `phase-26-complete` 指向阶段 26 最终功能提交 `5000d4fa790d95931862d3f8b2bfc34e91c91ee7`，并已合并到 `main`。
- 已从阶段 26 合并后的 `main` 创建并切换到 `codex/phase-27-chainlit-docker-ci`。
- 已校准 planning 文件，将 Phase 0 标记完成并进入 Phase 1。

验证结果：

```text
git merge-base --is-ancestor phase-26-complete main -> passed
current branch -> codex/phase-27-chainlit-docker-ci
```

提交边界：

- 未执行 `git add`、`git commit`、`git tag`、`git push`。
- 未创建 `phase-27-complete` tag，等待阶段 27 全部开发与用户人工核验。

## Phase 1 日志：阶段 27 设计文档

时间：2026-06-12

已完成：

- 新增 `docs/stage27_chainlit_docker_ci.md`。
- 明确 Chainlit 是新增并行入口，FastAPI API 与原生 `app/frontend/` 工作台继续保留。
- 固化 `@cl.on_message` 链路：会话加载、闲聊短路、复杂度路由、default / agentic 执行、流式输出、引用展示、步骤可视化和消息持久化。
- 固化 Docker 边界：`.env`、SQLite、受限全文、Obsidian 不进入镜像。
- 固化 CI 边界：GitHub Actions 只跑 deterministic pytest，不配置真实 API key。

验证结果：

```text
docs/stage27_chainlit_docker_ci.md created
```

提交边界：

- 未执行 `git add`、`git commit`、`git tag`、`git push`。

## Phase 2 日志：Chainlit 前端集成

时间：2026-06-12

已完成：

- `pyproject.toml` 新增 `chainlit>=2.0.0`，本地安装验证为 Chainlit 2.11.1。
- 新增 `chainlit_app.py`，作为 Chainlit 入口；`@cl.on_chat_start` 创建会话，`@cl.on_message` 复用已有 `stream_agent_query_events()` 输出 token、metadata、done/error。
- Chainlit 消息使用 `msg.stream_token()` 流式追加回答，用 `cl.Text` 展示引用来源和 workflow markdown，用 `cl.Step` 展示 default/tool 或 agentic workflow 步骤。
- 新增 `.chainlit/config.toml`，按 Chainlit 2.11.1 schema 配置 UI、功能开关和安全项；禁用 unsafe HTML、audio 和 MCP。
- 新增 `chainlit.md`，作为项目专用欢迎页。
- 新增 `tests/test_chainlit_app.py`，覆盖事件解析、引用格式、workflow 格式、安全 metadata 和 Conversation 映射。
- 新增 `tests/__init__.py`，修复 Chainlit 依赖安装后顶层 `tests` 包遮蔽本仓库测试模块的问题。

问题与修复：

- 初始 `.chainlit/config.toml` 缺少 `[meta] generated_by`，Chainlit 2.11.1 判定为旧配置并拒绝启动；已按当前 schema 重写。
- `dataclass` 在 Chainlit 动态加载入口时触发 Python 3.13 兼容问题；已改为 `NamedTuple`。

验证结果：

```text
.\.venv\Scripts\python.exe -m pip install -e .
successfully installed chainlit-2.11.1

.\.venv\Scripts\python.exe -m pytest tests\test_chainlit_app.py tests\test_agent_stream_api.py tests\test_agent_api.py -q
30 passed, 1 warning in 10.25s

.\.venv\Scripts\chainlit.exe run chainlit_app.py --host 127.0.0.1 --port 8010 --headless
GET http://127.0.0.1:8010 -> 200
```

提交边界：

- 未执行 `git add`、`git commit`、`git tag`、`git push`。

## Phase 3 日志：Docker 容器化

时间：2026-06-12

已完成：

- 新增 `Dockerfile`：基于 `python:3.11-slim`，安装项目依赖，暴露 8000，默认运行 `chainlit run chainlit_app.py --host 0.0.0.0 --port 8000 --headless`。
- 新增 `docker-compose.yml`：构建应用镜像，映射 `8000:8000`，运行时读取 `.env`，挂载 `./data:/app/data`，容器内使用 `sqlite:////app/data/app.sqlite`。
- 新增 `.dockerignore`：排除 `.env`、`.venv`、`.git`、`.claude`、`.codex`、`obsidian-vault`、SQLite/DB、`data/raw`、`data/fulltext`、日志等。
- 新增 `tests/test_docker_assets.py`，验证 Docker 配置不显式复制敏感文件，compose 使用运行时 env 和数据卷。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_docker_assets.py -q
3 passed in 0.05s

docker compose build
failed: docker command not found
```

环境限制：

- 当前机器未安装 Docker CLI，无法实际执行 `docker compose up --build`。阶段 5/人工核验需在有 Docker 的环境补跑容器启动验证。

提交边界：

- 未执行 `git add`、`git commit`、`git tag`、`git push`。

## Phase 4 日志：GitHub Actions CI 管线

时间：2026-06-12

已完成：

- 新增 `.github/workflows/ci.yml`。
- 触发范围：push 到 `main`、`codex/**`、`claude/**`，PR 到 `main`。
- 运行环境：`ubuntu-latest` + Python 3.11。
- 安装和测试命令：`python -m pip install -e ".[dev]"`、`python -m pytest -q`。
- CI 显式使用 deterministic chat / embedding / reranking provider，不配置真实 API key。
- 扩展 `tests/test_docker_assets.py`，静态验证 CI workflow 的触发、Python 版本、安装命令、pytest 命令和 deterministic provider 设置。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest tests\test_docker_assets.py tests\test_chainlit_app.py tests\test_agent_stream_api.py tests\test_agent_api.py -q
34 passed, 1 warning in 11.83s
```

提交边界：

- 未执行 `git add`、`git commit`、`git tag`、`git push`。

## Phase 5 日志：端到端验证与回归

时间：2026-06-12

已完成：

- 运行全量测试。
- 启动 FastAPI 临时服务 `http://127.0.0.1:8020`，验证旧 API 与原生前端。
- 启动 Chainlit 临时服务 `http://127.0.0.1:8021`，验证新入口页面、配置端点和浏览器 console。
- 修复 Chainlit 2.11.1 缺 `asyncpg` 导致 `/project/settings` 500 的问题，`pyproject.toml` 新增 `asyncpg>=0.30.0`。
- 验证完成后已停止临时服务并清理 smoke 日志/PID 文件。

验证结果：

```text
.\.venv\Scripts\python.exe -m pytest -q
520 passed, 1 warning in 56.85s

FastAPI:
GET http://127.0.0.1:8020/health -> 200
POST /agent/query -> 200
POST /agent/query/stream -> 200, contains event: done
POST /search/hybrid -> 200
GET /quality-report -> 200
Browser desktop/mobile -> RFC RAG 工作台 loaded, console errors=0

Chainlit:
GET http://127.0.0.1:8021 -> 200
GET /project/settings?language=zh-CN -> 200
Browser desktop/mobile -> RFC-RAG-Agent loaded, console errors=0
```

环境限制：

- 当前机器未安装 Docker CLI，无法执行 `docker compose up --build`。此项需用户人工核验时在有 Docker 的环境补跑。

提交边界：

- 未执行 `git add`、`git commit`、`git tag`、`git push`。

## Phase 6 日志：文档同步、Obsidian 收尾与人工核验待提交状态

时间：2026-06-12

已完成：

- 更新 `README.md`，把当前阶段切换为阶段 27，补充 Chainlit、Docker Compose 启动方式和 520 passed 验证结果。
- 更新 `docs/progress.md`，记录阶段 27 完成内容、验证结果、Docker CLI 限制和人工核验边界。
- 更新 `docs/architecture.md`，加入 Chainlit 并列入口、Docker Compose 和 GitHub Actions CI 架构。
- 更新 `docs/data_sources.md`，说明阶段 27 不新增外部资料来源，Chainlit/Docker/CI 不写入密钥、供应商原始响应或受限全文。
- 更新 `AGENT.MD`，加入阶段 27 之后的 Chainlit / Docker / CI 规则，并把当前推荐第一步改为阶段 27 人工核验。
- 新增 Obsidian 阶段 27 阶段页、Phase 汇报索引、Phase 0-6 小汇报。
- 新增 Obsidian 知识点：`Chainlit 对话界面`、`Docker 容器化部署`、`GitHub Actions CI`，并更新相关分类页、首页、阶段索引和阶段汇报索引。
- 清理浏览器 smoke 产生的 `.playwright-mcp` 临时日志目录。

验证结果：

```text
沿用 Phase 5 全量验证：520 passed, 1 warning
FastAPI / Chainlit desktop/mobile browser smoke: console errors=0
Docker Compose 已在本机实跑通过：docker compose up --build -d
```

提交边界：

- 未执行 `git add`、`git commit`、`git tag`、`git push`。
- 未创建 `phase-27-complete` tag。
- 未创建 PR。
- 当前状态按用户要求停在人工核验前。

## 阶段 27 验收与提交授权日志

时间：2026-06-12

已完成：

- 用户明确要求验收阶段 27 开发工作，提交阶段 27 整体开发工作，并上传 merge 至 GitHub。
- 已读取 `AGENT.MD`、README、docs/progress、docs/architecture、docs/data_sources，确认阶段提交规则。
- 已复核阶段 27 新增 Chainlit、Docker、CI、测试和文档范围。
- 已运行全量测试，结果 520 passed。
- 已新增 `docs/phase_reviews/phase-27.md`，验收结论 PASS。

验证结果：

```text
python -m pytest -q
520 passed, 1 warning in 70.02s

docker --version
failed: docker command not found
```

提交边界：

- 用户随后要求先完成 Docker 部署，但暂不提交，因为前端界面还需要优化。
- 当前不创建 `phase-27-complete` tag，不 merge，不 push。

## Docker Desktop 与 Compose 实跑日志

时间：2026-06-12

已完成：

- Docker Desktop 已下载安装到 `G:\Docker\Docker`，WSL 数据目录配置为 `G:\Docker\wsl`。
- Docker CLI 已进入 PATH。
- Docker 自检通过。
- 项目镜像 `rfc-rag-agent:phase27` 已通过 `docker compose up --build -d` 构建并启动。
- 容器 `rfc-rag-agent-rfc-rag-agent-1` 状态为 Up，端口映射 `0.0.0.0:8000->8000/tcp`。

验证结果：

```text
docker --version
Docker version 29.5.3

docker compose version
Docker Compose version v5.1.4

docker run --rm hello-world
Hello from Docker!

docker compose up --build -d
Image rfc-rag-agent:phase27 Built
Container rfc-rag-agent-rfc-rag-agent-1 Started

GET http://127.0.0.1:8000
200

GET http://127.0.0.1:8000/project/settings?language=zh-CN
200
```

当前状态：

- Docker 容器仍在后台运行，可访问 `http://127.0.0.1:8000`。
- 暂不提交阶段 27，等待前端界面优化。

## Phase 7 日志：原生前端视觉升级与可用首页

时间：2026-06-12

已完成：

- 用户提供深色科技风 RAG 产品首页参考图，希望把当前前端做成类似风格。
- 本 Phase 只优化原生 FastAPI 前端 `app/frontend/`，不改 RAG 后端链路，不替换 Chainlit，不提交。
- 目标是让 `GET /` 成为可展示的深色科技风首页，同时保留真实 Agent 流式问答、引用、workflow、会话和资料管理入口。
- 已重构 `app/frontend/index.html`，把首页升级为顶部导航 + 左侧 hero + 能力卡片 + 右侧真实 Agent demo + 资料库工作台的深色科技风布局。
- 已根据用户反馈继续优化为两个界面：`开始问答` 和 `资料库` 通过顶部导航切换，默认显示问答页，资料库独立展示指标、筛选、sources 和 documents。
- 已将首页主标题改为“面向堆石混凝土的 RAG 智能检索系统”，并把小能力点精简为混合检索、流式回答、结构化分块。
- 已重写 `app/frontend/static/styles.css`，补齐桌面和移动端响应式约束，移动端表格改为容器内滚动，避免页面异常拉长。
- 已小改 `app/frontend/static/app.js`，让重复指标节点能同步更新，并新增原生视图切换逻辑。
- 已更新 `tests/test_frontend_app.py`，覆盖新首页结构、关键文案、真实 Agent hook 和静态资源特征。
- 聚焦回归通过：

```text
python -m pytest tests/test_frontend_app.py tests/test_docker_assets.py tests/test_chainlit_app.py -q
15 passed, 1 warning in 1.59s

python -m pytest -q
520 passed, 1 warning in 83.56s
```

- FastAPI preview `GET http://127.0.0.1:8022` 返回 200。
- 桌面 1280x720 与移动 390x844 浏览器 smoke 均无 console error。
- 浏览器补充验证：点击顶部“资料库”后切换到 `#library-view` 成功，console error/warning 为 0。
- Reranking API key 最小真实 smoke：`.env` 中 `RERANKING_PROVIDER=jina`、model/base_url/api_key 均已配置；对 `api.jina.ai` 发起 1 个 query + 2 个候选的最小 rerank 调用成功，返回 2 条结果并完成解析。未打印 key，未保存供应商原始响应。
- 提交前最终回归：`python -m pytest -q` -> 520 passed, 1 warning in 145.76s。
- 提交前修复测试隔离：本机 `.env` 配置真实 Jina reranking 后，两个离线定时测试曾误触发真实 rerank；已在 `tests/test_agent_stream_api.py` 和 `tests/test_hybrid_search.py` 中显式禁用/隔离 rerank provider，保证 CI 和本地全量测试不以真实 API 为前提。
- Docker 容器入口仍保持 Chainlit，已跑通的 Docker 部署链路不改；原生 FastAPI 首页可通过 `uvicorn app.main:app` 单独核验。
- 当前仍不执行 `git add`、不 commit、不创建 `phase-27-complete` tag、不 merge、不 push，等待用户人工核验。

## 架构决策

### Chainlit 集成方式

- Chainlit 作为独立入口 `chainlit_app.py`，直接导入 Python 服务层。
- FastAPI 入口 `app/main.py` 和原有 API 端点完整保留，供外部客户端、测试和调试使用。
- 不删除 `app/frontend/`（原生前端保留为备用/调试入口）。
- Chainlit 和 FastAPI 共享同一个 SQLite 数据库和 `Settings` 配置。

### Docker 分层策略

```text
FROM python:3.11-slim
  → COPY pyproject.toml → pip install（依赖缓存层）
  → COPY . .（代码层）
  → EXPOSE 8000
  → CMD chainlit run chainlit_app.py --host 0.0.0.0 --port 8000
```

- `.dockerignore` 排除 `.venv`、`__pycache__`、`.git`、`obsidian-vault`、`.env`、`*.sqlite`、`.claude`、`.codex`。
- docker-compose 通过 `volumes: ./data:/app/data` 挂载 SQLite。
- docker-compose 通过 `env_file: .env` 注入 API 配置。

### CI 管线设计

- 触发：push 到 `main`、`codex/*`、`claude/*`，PR 到 `main`。
- 环境：`ubuntu-latest`、Python 3.11。
- 步骤：checkout → setup-python → pip install → pytest -q。
- 全量测试使用 deterministic provider，不需要真实 API key。

## 遗留风险

- Chainlit 版本兼容性需要确认（Chainlit 更新较快，API 可能有 breaking changes）。
- Docker 构建时间取决于依赖安装（numpy、chainlit 等），需要利用层缓存优化。
- GitHub Actions 首次配置后需要在 GitHub 上验证实际触发效果。
- 阶段 27 当前尚未提交、尚未创建 `phase-27-complete` tag、尚未推送，需等待用户人工核验和明确确认。
