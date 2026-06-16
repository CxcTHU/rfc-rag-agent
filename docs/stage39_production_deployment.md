# 阶段 39：生产部署与端到端体验

## 目标

阶段 39 在 Phase 38 已合并到 `main / origin/main -> 33b63e0 Merge phase 38 tool calling generation quality` 的基础上推进。当前 default Agent 链路已经稳定为 `tool_calling_agent`，`structured_final_answer` 通过六指标 Judge gate，Stage 30 保持 `91.52 / A / pass`。

本阶段目标不是继续调检索或生成质量，而是把系统从“本地能跑”推进到“可部署、可运维、可交付”。主线固定为：

```text
Dockerfile / docker-compose 更新
-> 结构化日志
-> 前端体验打磨
-> 部署文档与配置指南
-> 回归验证与人工核验前收尾
```

## 不动边界

阶段 39 严格不做以下变更：

- 不动检索策略：chunk 切分、FAISS/SQLite 索引策略、hybrid 权重、rerank 权重、BM25/RRF 候选策略均不调整。
- 不动 prompt 策略：Phase 38 的 compact citation-first `structured_final_answer` 保持不变。
- 不动 Stage 30 评分权重、等级阈值、release_decision 规则，Stage 30 必须维持 `91.52 / A / pass`。
- 不替换默认 embedding provider。
- 不替换默认 rerank provider。
- 不替换默认 chat provider。
- 不新增外部数据源，不爬新网页，不下载新 PDF，不重切 chunk，不重建语料。
- 不新增写入型 Agent 工具，不引入多用户登录系统，不引入 LangGraph 迁移。
- 不把 deterministic `citation_validator`、Judge 或其他后处理强接入生产回答链路。
- 不让真实 API 成为 CI 或本地全量 pytest 前提；真实 provider 只允许在显式 smoke 或人工验证命令中使用。

## 安全边界

所有新增代码、CSV、文档、测试和 Obsidian 草稿都不得写入：

- API key
- Bearer token
- Authorization header
- raw provider response
- `reasoning_content`
- hidden thought
- 用户完整原始问题全文日志
- 完整 chunk 全文
- 受限全文

日志、smoke 和文档只能保留脱敏、截断、可复核的工程字段。

## Phase 1 设计合同

阶段 39 的设计文档和测试必须固定：

- 当前基线：Phase 38 已合并，默认链路为 `tool_calling_agent`，Stage 30 为 `91.52 / A / pass`。
- 交付主线：Docker、结构化日志、前端体验、部署文档、回归验证。
- 验证标准：docker build 成功，生产 smoke 通过，浏览器 smoke 通过，全量 pytest 通过。
- 提交流程边界：阶段完成后不执行 `git add`、`git commit`、`git tag`、`git push`，不创建 PR，等待用户人工核验。

## Phase 2 Docker 部署更新

当前 Dockerfile 仍以 Chainlit 为 CMD：

```text
chainlit run chainlit_app.py --host 0.0.0.0 --port 8000 --headless
```

阶段 39 必须改为当前 FastAPI 入口：

```text
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

目标：

- 使用多阶段构建，先安装依赖，再复制运行时代码，减少镜像体积和无关文件进入镜像的概率。
- 继续通过 `pyproject.toml` 安装项目依赖。
- 新增或更新 `.dockerignore`，排除 `.env`、`.git`、`.venv`、测试缓存、评测派生产物、Obsidian、本地数据库和全文目录。
- 更新 `docker-compose.yml` 的 image tag、环境变量、数据卷、healthcheck。
- health check 只访问 `GET /health`，不触发真实 provider、不写数据库、不读取受限全文。

新词解释：

- 多阶段构建：Dockerfile 中使用多个 `FROM` 阶段，把构建依赖和最终运行镜像拆开，最终镜像只携带运行所需文件。
- health check：容器平台定期访问的健康检查命令，用来判断服务是否可用，本项目使用 `/health`。

## Phase 3 结构化日志

阶段 39 使用 Python 标准 `logging` 配置 JSON 日志，不额外引入 `structlog`。

请求入口日志通过 FastAPI middleware 实现：

```text
method
path
status_code
latency_ms
request_id
event=request_completed 或 request_failed
```

Agent 事件日志覆盖：

```text
query_received
tool_call_executed
answer_generated
refusal_triggered
agent_error
```

Agent 日志只允许记录安全摘要，例如 `mode`、`conversation_id`、`tool_name`、`source_count`、`citation_count`、`refused`、`latency_ms`、截断后的 query 摘要。不得记录用户完整问题、工具回传完整片段、provider 原始响应或隐藏推理。

新词解释：

- 结构化日志：每行日志是机器可解析的 JSON，便于按字段查询、过滤和告警。
- middleware：FastAPI 请求进入路由前后的统一拦截层，适合记录请求耗时和状态码。
- request_id：请求级追踪编号，用来把同一次请求的入口日志和 Agent 事件日志关联起来。

## Phase 4 前端体验打磨

前端只做体验增强，不改 Agent 业务逻辑：

- 加载态：Agent 请求期间显示 spinner 或脉冲动画，让用户知道系统正在处理。
- 错误提示：请求失败时显示中文友好错误，不暴露堆栈、内部异常或 provider 原始错误。
- 引用来源展示：回答中的 `[N]` 引用可点击或 hover，展示对应来源标题、source_type 和短摘要。
- 会话标题：根据首条用户消息自动生成简短标题，刷新后仍兼容已有会话列表。
- 响应式：桌面和 390x844 移动视口无横向溢出，按钮和引用浮层不遮挡主要内容。

新词解释：

- hover 来源卡片：鼠标悬停在 `[N]` 引用上显示的小浮层，帮助用户快速理解来源，不需要跳离回答。
- smoke：小范围冒烟测试，用少量关键路径验证系统没有明显启动、接口或页面错误。

## Phase 5 部署文档与配置指南

新增 `docs/deployment_guide.md`，更新 README Quick Start，并补齐 `.env.example`。

部署文档必须覆盖：

- Docker build
- docker compose 启动
- 环境变量说明
- 数据卷挂载
- SQLite 数据位置
- 健康检查
- production smoke
- 常见故障排查
- 敏感信息禁止写入 Git 的说明

`.env.example` 只能包含变量名、默认空值或安全示例，不能包含真实 key。

## Phase 6 回归验证与收尾

阶段收尾必须完成：

```text
python -m pytest -q
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8000 --timeout-seconds 120
docker build
browser smoke desktop + 390x844 mobile
```

普通文档收尾：

- README.md
- docs/progress.md
- docs/architecture.md
- docs/data_sources.md
- docs/phase_reviews/phase-39.md

Obsidian 收尾在开发、测试和普通文档完成后统一进行，补齐：

- `obsidian-vault/阶段汇报/阶段 39 - 生产部署与端到端体验/`
- 阶段 39 Phase 汇报索引
- Phase 0 到最终 Phase 小汇报
- `obsidian-vault/阶段汇报索引.md`
- `obsidian-vault/阶段/阶段 39 - 生产部署与端到端体验.md`

每篇小 Phase 汇报必须包含本 Phase 目标、完成的主要任务、新增/修改内容、关键代码或模块、问题与解决方式、新词解释、验证结果、遗留问题、下一 Phase、面试表达。

## 完成标准

- Dockerfile 和 docker-compose.yml 更新到 FastAPI + uvicorn，docker build 成功。
- 结构化日志覆盖请求入口和 Agent 调用路径，JSON 格式，不泄露敏感信息。
- 前端加载态、错误提示、引用来源展示已实现并通过浏览器 smoke。
- 部署文档和 `.env.example` 已就位。
- 不动检索策略、prompt 策略、Stage 30 评分规则、embedding/rerank provider。
- Stage 30 维持 `91.52 / A / pass`。
- 全量 pytest 通过；production smoke 通过；浏览器 smoke 通过。
- 最终不提交、不打 tag、不推送、不创建 PR，停在用户人工核验前状态。
