# 阶段 27 发现与关键决策

## 技术选型决策

### 为什么选 Chainlit 而非 Vue 3 + Vant 4

- **目标岗位**：后端 / AI 工程师，面试核心是 RAG 管线深度，不是前端框架能力。
- **风险控制**：引入 Vue 3 后面试官一定会追问 Vue 原理（响应式、虚拟 DOM、Composition API），答不上来反而减分。
- **时间效率**：Chainlit `pip install` + 几十行 Python 就能得到专业级对话界面，不需要学 Node/npm/Vite 构建链。
- **生态契合**：Chainlit 原生支持 LangGraph（项目阶段 21 已引入），流式输出、步骤可视化、引用展示开箱即用。
- **面试表达**："我选了和 LangGraph 生态最契合的前端方案，把工程精力集中在检索优化和重排序上"——这是工程判断力。

### 为什么不用 Streamlit / Gradio

- Streamlit 的 `st.chat_message` 定制能力有限，不支持 agentic 步骤可视化。
- Gradio 的 `ChatInterface` 面向 ML demo，不适合 RAG 的引用溯源和多轮会话。
- 面试官看到 Streamlit/Gradio 会觉得"就是个 demo app"，Chainlit 则明确面向 production AI 应用。

### 为什么不删除原有前端

- `app/frontend/` 和 FastAPI 端点保留，作为调试入口和 API 兼容层。
- 原有 `POST /agent/query/stream` SSE 端点有完整测试覆盖，删除会丢失回归保障。
- 部分测试依赖 FastAPI TestClient 访问前端静态文件和 API 端点。
- 保留双入口（Chainlit + FastAPI）展示架构灵活性。

## Chainlit 与 FastAPI 的关系

```text
用户浏览器
├── Chainlit (ws://localhost:8000)     ← 对话界面入口
│   └── 直接调用 Python 服务层
│       ├── detect_chitchat()
│       ├── AgentService.query()
│       ├── run_agentic_rag()
│       ├── HybridSearchService.search()
│       ├── ConversationRepository
│       └── stream_generate()
│
└── FastAPI (http://localhost:8001)     ← API / 调试入口（保留）
    ├── POST /agent/query
    ├── POST /agent/query/stream
    ├── POST /search/hybrid
    ├── GET /conversations
    └── GET /quality-report
```

- Chainlit 和 FastAPI 是两个独立进程，共享同一个 SQLite 数据库。
- Chainlit 不通过 HTTP 调用 FastAPI 端点，避免自调用增加的网络延迟和复杂度。
- 两者通过 `app.core.config.get_settings()` 共享配置。

## Chainlit 功能映射

| 现有功能 | Chainlit 对应 | 说明 |
|---------|-------------|------|
| SSE `event: token` | `msg.stream_token(token)` | Chainlit 原生支持流式 |
| 引用 citations | `cl.Text(name, content)` | 作为消息附件展示 |
| agentic workflow_steps | `cl.Step(name)` 上下文管理器 | 可嵌套，展示 retrieve→grade→rewrite→generate |
| 会话列表 / 历史 | Chainlit 原生线程管理 | 可映射到 ConversationRepository |
| 闲聊短路 | `@cl.on_message` 内判断 | 命中直接 `cl.Message(content=reply).send()` |
| 拒答展示 | 消息内文本标记 | `refused=True` 时在回复前加标注 |
| mode 指示器 | `cl.Step` 或消息 metadata | 展示实际走的 default/agentic 路径 |

## Docker 决策

### 镜像安全边界

- `.env` 通过 `env_file` 在 docker-compose 运行时注入，不 `COPY` 进镜像。
- `*.sqlite` 通过 volume 挂载，不打入镜像。
- `obsidian-vault/` 在 `.dockerignore` 中排除。
- `data/raw/` 中的 PDF 原始文件如需在容器内可用，通过 volume 挂载 `./data:/app/data`。

### 为什么用 docker-compose 而非单纯 Dockerfile

- 应用依赖 SQLite 数据目录和 `.env` 环境变量，docker-compose 的 `volumes` 和 `env_file` 把运行时配置和镜像分离。
- 后续如果加 PostgreSQL 或 Redis，docker-compose 可以直接加服务，不改 Dockerfile。

## CI 决策

### 为什么只跑 pytest 不跑 Docker build

- pytest 全量测试使用 deterministic provider，不需要真实 API key，CI 配置简单。
- Docker build 在 CI 中运行需要额外时间（安装 numpy + chainlit 约 2-3 分钟），且不验证业务逻辑。
- 可选项：在 CI 中加一个 `docker build .` 步骤验证 Dockerfile 有效性，但不运行容器内测试。

### 分支触发规则

- `main`：合并后跑，保证主线始终绿色。
- `codex/*` 和 `claude/*`：开发分支 push 时跑，尽早发现问题。
- PR 到 `main`：合并前必须通过，作为质量门。

## 数据安全边界

- Chainlit 界面上展示的 answer、citations、workflow_steps 来自已有 `AgentQueryResponse`，沿用阶段 25 的 metadata 安全边界。
- Chainlit 不暴露 raw_response、API key 或供应商原始敏感响应。
- Docker 镜像不包含 `.env`、API key 或 SQLite 数据文件。
- GitHub Actions 不配置真实 API 凭据，secrets 列表为空。

## Phase 0 启动校准发现

- 当前阶段 27 起点正确：`main` 和 `HEAD` 均在 `74afce9fa359c25b9730cf414cef69f3db0215da Merge phase 26 retrieval performance reranking`。
- `phase-26-complete` 指向 `5000d4fa790d95931862d3f8b2bfc34e91c91ee7 Complete phase 26 retrieval performance reranking`，并已通过 `git merge-base --is-ancestor phase-26-complete main` 验证已并入 `main`。
- 阶段 27 分支已从阶段 26 合并后的 `main` 创建为 `codex/phase-27-chainlit-docker-ci`。
- 根目录 `task_plan.md`、`findings.md`、`progress.md` 在启动时已有阶段 27 预填草稿，视为用户/上一轮规划成果，开发中保留并在该基础上校准。
- 阶段 27 必须保留原有 FastAPI API 与 `app/frontend/` 调试入口；Chainlit 是新增并行界面，不是删除旧接口后的替代品。

## Phase 1 设计文档发现

- Chainlit 最合适的集成点不是 FastAPI HTTP 自调用，而是直接复用服务层：`detect_chitchat()`、`classify_query_complexity()`、`AgentService.query()`、`run_agentic_rag()`、`ConversationRepository` 和 `ChatModelProvider.stream_generate()`。
- Chainlit 的 `cl.Message.stream_token()` 可以替代阶段 25 前端手写 SSE parser，但阶段 25 的 `/agent/query/stream` 端点仍应保留为 API 能力和回归测试入口。
- `cl.Step` 只用于展示只读 workflow，不引入写入型工具或新的外部副作用。
- Docker 镜像边界必须比普通 Python 项目更严格：`data/app.sqlite`、`data/raw`、`data/fulltext`、`.env`、`obsidian-vault` 都不得进入镜像上下文。
- CI 的质量门以 `pytest` 为主，真实 API 不进入 GitHub Actions；Docker build 可作为可选语法/依赖验证，不替代业务测试。

## Phase 2 Chainlit 集成发现

- Chainlit 2.11.1 会拒绝没有 `[meta] generated_by` 的旧式 `.chainlit/config.toml`，配置必须按当前 schema 提供 `[project]`、`[features]`、`[UI]` 和 `[meta]`。
- `chainlit run` 通过动态 `spec.loader.exec_module()` 加载入口文件，在 Python 3.13 下会触发 `dataclass` 对 `sys.modules[cls.__module__]` 的兼容问题；`ParsedStreamEvent` 改为 `NamedTuple` 后启动正常。
- 安装 Chainlit 后依赖中出现顶层 `tests` 包，会遮蔽本仓库 `tests.test_agent_api` 这种导入；新增 `tests/__init__.py` 让本地测试包解析稳定。
- 复用 `stream_agent_query_events()` 可以让 Chainlit 与 `/agent/query/stream` 共用同一条闲聊、default、agentic、持久化和 metadata 生成逻辑，减少双入口行为漂移。
- Chainlit 自动生成 `chainlit.md`，需要替换默认欢迎页，避免通用模板内容进入阶段交付。

## Phase 3 Docker 容器化发现

- 当前工作机没有 Docker CLI，`docker compose build` 无法执行，阶段内只能完成 Dockerfile / compose / dockerignore 静态校验；最终人工核验需要在安装 Docker Desktop 或 Docker Engine 的环境中重跑。
- `docker-compose.yml` 通过 volume 挂载 `./data:/app/data`，因此 SQLite 文件和本地全文不会进入镜像层；但运行容器时本机 `data/` 会暴露给容器，符合本地部署预期。
- `.dockerignore` 需要同时排除 `data/app.sqlite`、`*.sqlite`、`data/raw`、`data/fulltext`，因为这些路径分别覆盖单文件数据库、泛 SQLite 和受限/原始全文目录。
- Dockerfile 没有写入 `.env` 或任何 API key；凭据只由 compose 的 `env_file` 在运行时注入。

## Phase 4 CI 发现

- GitHub Actions 不需要真实 API key；显式 deterministic 环境变量可以防止 CI 读取仓库外的真实 provider 配置。
- `actions/setup-python@v5` 的 pip cache 足以覆盖当前依赖安装；不引入额外 CI 服务，避免把阶段 27 扩成部署流水线。
- CI workflow 只在 GitHub 上真实触发后才能看到最终状态；本地阶段可用静态测试和本地 pytest 验证配置意图。

## Phase 5 验证发现

- 全量测试在新增 Chainlit、Docker、CI 后为 520 passed，较阶段 26 基线 511 增加 9 个测试。
- Chainlit 2.11.1 页面 shell 能加载但 `/project/settings` 会在缺少 `asyncpg` 时返回 500；新增 `asyncpg>=0.30.0` 后该端点恢复 200，浏览器 console error 清零。
- FastAPI 原生工作台和 Chainlit 入口可以并行运行在不同端口，验证了阶段 27 的双入口架构。
- 当前浏览器 MCP 工具没有输入/点击能力，Chainlit 交互式发消息未在浏览器中自动执行；已通过 `chainlit_app.py` 单元测试、服务启动和 FastAPI SSE/API 冒烟覆盖核心链路。
- Docker 实跑验证仍受本机无 Docker CLI 限制，需列为人工核验重点。

## Phase 6 文档与 Obsidian 收尾发现

- README 顶部曾停留在阶段 26 提交合并状态，已改为阶段 27 开发/测试/文档完成、等待人工核验，并把阶段 26 作为已合并基线保留。
- `docs/data_sources.md` 中阶段 26 的“尚未提交”历史描述已过期；阶段 27 新增单独边界，明确 Chainlit/Docker/CI 不新增外部资料来源，且阶段 27 当前未提交。
- `AGENT.MD` 底部当前推荐第一步曾停留在阶段 25，已更新为阶段 27 人工核验重点。
- Obsidian 首页、阶段索引和阶段汇报索引曾停留在阶段 26，已同步到阶段 27，并新增 Chainlit、Docker、CI 三个知识点。
- 阶段 27 收尾后最重要的人工核验项是 Docker Compose 实跑，其次是浏览器中实际发送 Chainlit 消息查看 token、citations 和 Step 展示。

## Phase 7 前端视觉升级发现

- 用户参考图更像“AI 产品 landing + 右侧 demo panel”，不适合强行改 Chainlit 内部布局；更稳的做法是升级 `app/frontend/` 原生入口。
- 原生前端已有完整 data 属性和 API 绑定，视觉升级应尽量保留这些 DOM hook，避免重写 `app.js`。
- Docker 当前默认跑 Chainlit，FastAPI 原生前端仍可通过 `uvicorn app.main:app` 单独核验；是否把 Docker 默认入口切到 FastAPI 应等前端优化效果确认后再决定。
- 右侧 demo panel 不应做假输入框或纯静态 mock，而应继续承载真实 `data-agent-form`，这样视觉展示和 RAG 链路核验是同一个入口。
- 原生首页存在 sources/documents 表格，移动端最稳的处理是给表格容器内部滚动，而不是让整页横向滚动或把表格拆成新组件。
- `updateMetric()` 原先只更新第一个匹配节点；Phase 7 首页会在 hero stats 和 summary metrics 同时展示同名指标，因此改为 `querySelectorAll()` 同步更新。
- 用户反馈“前端有点杂乱”后，最稳的信息架构不是继续在首页堆模块，而是把问答和资料库拆成两个视图；这能保留一个 HTML/JS 入口，同时让用户认知负担显著降低。
- 当前不需要引入路由库或多 HTML 页面，`data-view-target` + `data-view` 的原生切换已经足够支撑“开始问答 / 资料库”两个界面。
- 首页文案应更贴近项目主题，主标题使用“面向堆石混凝土的 RAG 智能检索系统”，能力文案只保留混合检索、流式回答、结构化分块，避免把 Rerank、Docker、Agentic 等工程细节提前暴露给普通用户。
- `.env` 中真实 reranking 配置当前可读到 `RERANKING_PROVIDER=jina`、model、base_url 和 API key；最小真实调用可以连通并解析结果。但短中文 smoke 只证明 key 与接口可用，不等价于中文堆石混凝土排序质量已经通过校准。
- 真实 reranking key 配置后，默认读取 `.env` 的服务构造会影响部分定时类测试；凡是测试目标不是 rerank 质量或真实 provider 连通性，都应显式传入 `reranking_enabled=False` 或 monkeypatch provider，避免真实 API 成为全量测试前提。
