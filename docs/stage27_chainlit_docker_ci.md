# 阶段 27：Chainlit 前端 + Docker 容器化 + GitHub Actions CI

## 目标

阶段 27 在阶段 26「检索性能优化 + Cross-Encoder 重排序」已经提交、打 tag 并合并到 `main` 的基础上推进。目标是补齐三个工程化短板：

```text
Chainlit 专业对话界面
-> 复用 detect_chitchat / AgentService / run_agentic_rag
-> 流式输出、引用展示、agentic 步骤可视化、会话管理
-> Docker / docker-compose 容器化
-> GitHub Actions 自动运行 pytest
```

本阶段不删除 FastAPI API，不删除原生 `app/frontend/` 调试入口。Chainlit 是并行新增的 AI 对话界面，FastAPI 仍作为外部客户端、自动化测试和调试入口。

## 起点

阶段 26 状态：

```text
phase-26-complete -> 5000d4fa790d95931862d3f8b2bfc34e91c91ee7
main merge commit -> 74afce9fa359c25b9730cf414cef69f3db0215da
baseline tests -> 511 passed
```

阶段 27 分支：

```text
codex/phase-27-chainlit-docker-ci
```

开发完成后停在用户人工核验前，不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR，不创建 `phase-27-complete` tag。

## Chainlit 集成方式

### 进程边界

阶段 27 采用双入口架构：

```text
chainlit_app.py
  Chainlit 对话界面入口，直接调用 Python 服务层。

app/main.py
  FastAPI API 与原生前端入口，继续提供既有 HTTP contract。
```

Chainlit 不通过 HTTP 调用本机 FastAPI 端点，避免自调用带来的网络开销、端口耦合和测试复杂度。它直接复用已有服务层：

```text
detect_chitchat()
classify_query_complexity()
AgentService.query()
run_agentic_rag()
ConversationRepository
ChatModelProvider.stream_generate()
```

### 消息链路

Chainlit 用户消息进入 `@cl.on_message` 后按以下顺序处理：

```text
用户消息
-> 取得或创建 Conversation
-> 加载 history
-> detect_chitchat(question)
   -> 命中：直接返回预设友好回复，保存会话消息，跳过 summary
-> classify_query_complexity(question)
   -> simple/default：AgentService.query()
   -> complex/agentic：run_agentic_rag()
-> msg.stream_token(token)
-> cl.Text 展示 citations / sources
-> cl.Step 展示 agentic workflow
-> 保存 user / assistant 消息
```

### 流式输出

阶段 25 已为 `ChatModelProvider` 增加：

```python
stream_generate(messages) -> Iterator[str]
```

Chainlit 使用 `cl.Message.stream_token()` 展示逐 token 输出。default 与 agentic 路径仍复用现有业务编排；只有最终生成文本的展示变成 Chainlit 原生流式。

测试继续使用 `DeterministicChatModelProvider.stream_generate()`，不让真实 API 成为 CI 或本地全量测试前提。

### 步骤可视化

agentic 路径返回的 `workflow_steps` 映射到 `cl.Step`：

```text
retrieve
grade
rewrite
re_retrieve
generate
citation_check
```

每个 step 展示节点名、输入摘要、输出摘要、成功/失败状态和错误摘要。default 路径也可展示一个轻量 step，说明本轮走的是 default AgentService。

### 引用展示

引用展示分两层：

- 消息正文保留回答文本和 `[1]`、`[2]` 等 citation marker。
- `cl.Text` 附件展示引用来源清单，包括 citation id、document title、source type、chunk id、score 和片段摘要。

Chainlit 展示内容只来自已有 `AgentQueryResponse` / `AgenticResult` 的安全字段，不展示 API key、Authorization header、供应商原始响应或受限全文。

### 会话管理

Chainlit 的 thread/session 与项目已有 `ConversationRepository` 建立映射：

```text
Chainlit session/thread id
-> cl.user_session["conversation_id"]
-> Conversation.id
-> Message rows
```

`ConversationRepository` 仍是唯一会话读写边界。阶段 27 不做用户登录，也不做跨用户隔离；这延续阶段 24 的明确边界。后续如引入认证，需要给 `Conversation` 增加 owner/user 维度。

## Docker 容器化设计

### Dockerfile

基础镜像：

```text
python:3.11-slim
```

分层策略：

```text
COPY pyproject.toml
RUN pip install ...
COPY . .
EXPOSE 8000
CMD chainlit run chainlit_app.py --host 0.0.0.0 --port 8000
```

这样可以让依赖安装层复用 Docker cache，减少重复构建时间。

### docker-compose

`docker-compose.yml` 提供默认本地运行方式：

```text
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
```

`.env` 只在运行时注入，不进入镜像；SQLite 数据文件通过 `./data:/app/data` 挂载，不打包进镜像。

### .dockerignore

必须排除：

```text
.env
.venv
__pycache__
.git
.claude
.codex
obsidian-vault
*.sqlite
data/app.sqlite
data/raw
data/fulltext
```

镜像只包含应用代码、可提交配置、测试和文档，不包含 API key、Bearer token、SQLite 数据库、受限全文或 Obsidian 本地知识库。

## GitHub Actions CI

新增：

```text
.github/workflows/ci.yml
```

触发规则：

```text
push: main, codex/**, claude/**
pull_request: main
```

运行环境：

```text
ubuntu-latest
python-version: "3.11"
```

步骤：

```text
checkout
setup-python
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m pytest -q
```

CI 不配置真实 API key，不依赖 GitHub secrets。所有自动测试必须使用 deterministic provider 或合成 fixture。

可选增加 `docker build .`，用于验证 Dockerfile 语法和依赖安装，但业务质量门仍以 `pytest` 为准。

## API 兼容性

阶段 27 必须保证以下端点不被破坏：

```text
POST /search
POST /search/vector
POST /search/hybrid
POST /chat
POST /agent/query
POST /agent/query/stream
GET /quality-report
GET /
```

原生 `GET /` 工作台保留，便于调试 sources、documents、search、quality report 和旧 SSE 行为。

## 安全边界

- 不做登录系统。
- 不引入 `torch` 或 `sentence-transformers`。
- 不让真实 API 成为 CI 或本地全量测试前提。
- Chainlit metadata 不暴露 raw provider response。
- Docker 镜像不包含 `.env`、API key、SQLite 数据文件、受限全文或 Obsidian。
- GitHub Actions 不配置真实 API key 或 Bearer token。
- 文档、测试、CSV、Obsidian 不写入供应商原始敏感响应。

## 测试方案

新增或更新测试：

```text
tests/test_chainlit_app.py
tests/test_docker_assets.py
```

重点断言：

- `chainlit_app.py` 可以导入，核心 handler 依赖可替换为 deterministic provider。
- 闲聊短路路径不调用检索或真实模型。
- default 路径可返回 answer、citations、mode。
- agentic 路径可将 workflow steps 转为可展示结构。
- Dockerfile、docker-compose 和 `.dockerignore` 存在并排除敏感路径。
- FastAPI 既有 API 回归保持通过。

全量验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
docker-compose up --build
```

## 完成标准

- `docs/stage27_chainlit_docker_ci.md` 就位。
- `pyproject.toml` 新增 `chainlit` 依赖。
- 新增 `chainlit_app.py`，覆盖闲聊短路、default AgentService、agentic LangGraph、流式输出、引用和步骤可视化。
- 新增 `.chainlit/config.toml`。
- 新增 `Dockerfile`、`docker-compose.yml`、`.dockerignore`。
- 新增 `.github/workflows/ci.yml`。
- 原有 FastAPI API 和原生前端不被破坏。
- 全量测试通过，且不依赖真实 API。
- README、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`、`AGENT.MD` 和 Obsidian 已同步。
- 不提交、不创建 `phase-27-complete` tag、不推送 GitHub，停在用户人工核验前。

## 新词解释与面试表达

- **Chainlit**：面向 LLM/Agent 应用的 Python 对话界面框架。本项目用它替代手写聊天 UI，但仍复用原有 RAG 服务层。
- **Dockerfile**：容器镜像构建说明书。它描述如何从 Python 基础镜像安装依赖、复制代码并启动应用。
- **docker-compose**：本地多服务编排文件。本阶段先只编排应用服务和数据目录挂载，后续可扩展数据库或缓存服务。
- **GitHub Actions CI**：GitHub 的自动化流水线。每次 push 或 PR 自动安装依赖并运行测试，防止未跑测试的改动进入主线。

面试表达：

```text
阶段 27 我没有把项目改成复杂前端工程，而是选择 Chainlit 作为 AI 对话界面层。它和 LangGraph/RAG 生态契合，能原生支持流式输出、步骤可视化和引用展示，同时仍然只用 Python 维护。架构上我保留 FastAPI API 和原生调试工作台，Chainlit 直接调用服务层，避免本机 HTTP 自调用。部署上用 Dockerfile 和 docker-compose 分离镜像、环境变量和 SQLite 数据卷；质量上用 GitHub Actions 在 push/PR 时跑 deterministic pytest，确保真实 API key 不进入 CI。
```
