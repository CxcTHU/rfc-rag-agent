# 阶段 39 发现与关键决策

## 当前 Git 基线

Phase 38 已由用户/前序流程完成提交并合并到 main：

```text
main / origin/main -> 33b63e0 Merge phase 38 tool calling generation quality
phase-38 complete commit -> ee6830a Complete phase 38 tool calling generation quality
当前开发分支 -> codex/phase-39-production-deployment
```

关键决策：阶段 39 已从 Phase 38 合并后的 main 出发。后续开发不再把 Phase 38 当作未提交工作区改动处理。

## Phase 0 校准结论

已完成启动校准：

```text
git status -sb -> main...origin/main 且仅 task_plan.md/findings.md/progress.md 有阶段 39 规划改动
git log --oneline -5 -> 33b63e0 Merge phase 38 tool calling generation quality
目标分支 -> codex/phase-39-production-deployment
```

阶段 38 的 Judge gate pass、默认 `tool_calling_agent` 链路稳定、production smoke 11 条和 Stage 30 `91.52 / A / pass` 已包含在合并后的 main 中。阶段 39 直接在该基线上推进生产部署与端到端体验，不重开检索、prompt 或评分策略。

## 观察 1：Dockerfile 和 docker-compose.yml 已严重过期

当前 Dockerfile 的 CMD 是：
```text
CMD ["chainlit", "run", "chainlit_app.py", "--host", "0.0.0.0", "--port", "8000", "--headless"]
```

但项目早已切换到 FastAPI + uvicorn 架构，实际入口是 `app/main.py` 的 `create_app()` → `app = create_app()`，通过 `uvicorn app.main:app` 启动。chainlit_app.py 虽然还存在，但不是主要入口。

docker-compose.yml 的 image tag 仍是 `rfc-rag-agent:phase27`，落后 12 个阶段。

关键决策：Dockerfile CMD 必须改为 `uvicorn app.main:app --host 0.0.0.0 --port 8000`。docker-compose.yml image tag 需要更新。chainlit_app.py 评估是否仍有用（如果有独立功能则保留，否则标记废弃）。

## 观察 2：项目完全没有结构化日志

在 `app/` 目录下搜索 `logging`、`logger`、`structlog` 结果为零。当前所有运行时信息只通过 print 或 uvicorn 默认 access log 输出。

这意味着：
- 无法在生产环境中追踪请求链路
- 无法按级别过滤日志
- 无法结构化查询某个 Agent 调用的耗时或错误

关键决策：用 Python 标准 logging 库配置 JSON 格式即可，不额外引入 structlog 依赖。日志必须覆盖请求入口（middleware）和 Agent 关键事件，但绝不记录 API key、Bearer token、raw provider response、reasoning_content。

## 观察 3：前端缺少基本交互反馈

当前前端状态：
- 发送消息后无加载指示器，用户不知道是否在处理
- 请求失败时无友好提示，可能看到浏览器原始错误
- [N] 引用是纯文本，不可点击，不显示来源信息
- 无会话标题管理

这些是"可用"到"好用"的关键差距，与后端检索/prompt 完全解耦，改前端不影响 Agent 链路。

关键决策：加载态用 CSS 动画，不引入新前端框架。错误提示用中文。引用展示用 hover tooltip 或展开面板。会话标题取首条消息前 N 个字。

## 观察 4：app/main.py 架构清晰，适合加 middleware

```text
app/main.py 结构：
- lifespan: init_db()
- create_app(): FastAPI() + 7 个 router + static mount
- app = create_app()
```

日志 middleware 可以直接加在 create_app() 里，作为 FastAPI middleware，拦截所有请求。Agent 调用链路的日志可以在 tool_calling_service.py 的 _emit 方法和 agent.py 的入口处加。

关键决策：middleware 只做请求级别日志（method、path、status、latency）。Agent 内部事件日志通过已有的 event_sink 模式扩展，不改变调用链结构。

## 观察 5：阶段 39 不动的边界

- 不动检索策略：chunk 大小、rerank 权重、hybrid 融合参数、embedding/rerank provider。
- 不动 prompt 策略：structured_final_answer 保持不变。
- 不动 Stage 30 评分权重、等级阈值、release_decision 规则。
- 不动 Agent 调用链路逻辑（tool_calling_service.py 的 query() 流程不改）。
- 不引入新外部数据源、不爬新网页。
- 不做多用户隔离、登录系统。
- 不写 API key / Bearer token / raw provider response / reasoning_content / hidden thought / 受限全文进任何提交物。

## Phase 1 设计文档决策

阶段 39 设计文档已固定五条主线：

```text
Dockerfile / docker-compose 更新
-> 结构化日志
-> 前端体验打磨
-> 部署文档与配置指南
-> 回归验证与人工核验前收尾
```

关键决策：

- 部署入口统一回到当前 FastAPI 应用：`uvicorn app.main:app --host 0.0.0.0 --port 8000`。
- 结构化日志使用 Python 标准 `logging` 输出 JSON，不引入 `structlog` 新依赖。
- 请求日志放在 FastAPI middleware，Agent 事件日志放在 Agent 调用路径附近，均只记录安全字段和截断摘要。
- 前端只增强加载态、中文错误、引用来源展示和会话标题，不改默认 `tool_calling_agent` 链路。
- 阶段 39 收尾必须同时覆盖全量 pytest、Stage 30、production smoke、docker build 和浏览器 smoke。

新词解释：

- `middleware`：请求进入具体路由前后的统一拦截层，适合记录请求耗时、状态码和 request_id。
- `结构化日志`：每行日志是 JSON，方便按字段查询和运维告警。
- `health check`：容器平台定期访问的健康检查命令，本项目用 `GET /health`。
- `hover 来源卡片`：鼠标悬停在 `[N]` 引用上显示来源标题和短摘要的前端浮层。

验证：

```text
python -m pytest tests/test_stage39_design.py -q -> 8 passed
```

## Phase 2 Docker 更新结论

Docker 入口已从旧 Chainlit 切回当前 FastAPI 应用：

```text
旧入口：chainlit run chainlit_app.py --host 0.0.0.0 --port 8000 --headless
新入口：uvicorn app.main:app --host 0.0.0.0 --port 8000
```

关键决策：

- Dockerfile 使用 `builder` / `runtime` 两阶段构建，builder 阶段生成 wheel，runtime 阶段安装 wheel 并只复制运行所需 `app/`。
- docker-compose image tag 更新为 `rfc-rag-agent:phase39-production-deployment`。
- healthcheck 使用 Python 标准库访问 `http://127.0.0.1:8000/health`，不引入 curl 依赖，也不触发真实 provider。
- `.dockerignore` 继续阻止 `.env`、本地 DB、全文目录和 Obsidian 进入构建上下文，并新增 tests 与 `data/evaluation` 排除。

验证：

```text
python -m pytest tests/test_stage39_docker.py tests/test_docker_assets.py -q -> 7 passed
docker build -t rfc-rag-agent:phase39-production-deployment . -> succeeded
docker version -> client available, failed to connect to dockerDesktopLinuxEngine
```

Docker build 复验已完成：Docker Desktop 启动后 Docker server `29.5.3` 可用，镜像 `rfc-rag-agent:phase39-production-deployment` 构建成功。

## Phase 3 结构化日志结论

阶段 39 已引入标准库 JSON 日志，不新增 `structlog` 依赖：

```text
app/core/structured_logging.py
-> JsonLogFormatter
-> request_id contextvar
-> sanitize_log_value()
-> safe_text_summary()
```

请求入口：

```text
FastAPI middleware
-> request_completed / request_failed
-> method / path / status_code / latency_ms / request_id
```

Agent 路径：

```text
query_received
tool_call_executed
answer_generated
refusal_triggered
```

关键决策：

- request log 不记录 query string、headers、body 或 Authorization。
- Agent log 不记录用户完整问题，仅记录截断 `question_summary`。
- tool-calling 的工具日志只记录 tool_name、succeeded 和截断 output_summary，不记录完整 chunk 或 provider 原始响应。
- JSON formatter 会按 key 名脱敏 `api_key`、`Authorization`、`Bearer/token`、`raw_response`、`reasoning_content`、secret/password 等字段。

新词解释：

- `contextvar`：Python 的请求上下文变量，适合在异步请求中保存 request_id，避免不同请求串号。
- `JsonLogFormatter`：把标准 logging record 转成单行 JSON 的 formatter。
- `redaction`：脱敏，把敏感字段替换成 `[redacted]`。

验证：

```text
python -m pytest tests/test_stage39_logging.py -q -> 4 passed
python -m pytest tests/test_health.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_tool_calling_agent_service.py tests/test_stage39_logging.py -q -> 56 passed
```

## Phase 4 前端体验打磨结论

前端继续使用现有原生 HTML/CSS/JS，不引入新框架，也不修改 Agent 链路。

关键实现：

- `conversationTitleFromQuestion()`：新建会话时用首条用户问题生成最多 18 字的简短标题，避免全部都叫“新对话”。
- `userFriendlyErrorMessage()`：把 timeout、provider 不可用、503、网络失败等错误映射成中文友好提示，不展示堆栈或底层 provider 详情。
- `citationReferenceHtml()` / `renderAnswerWithCitationLinks()`：把回答正文中的 `[N]` 变成 `button.citation-ref`，hover/focus 时展示来源标题、source_type 和短摘要。
- `loading-spinner`：Agent 思考态加入 CSS spinner，token 到达后继续复用原有流式渲染。

新词解释：

- `hover/focus`：鼠标悬停或键盘聚焦时触发浮层，兼顾鼠标和键盘用户。
- `aria-label`：给按钮提供屏幕阅读器可读的说明，避免只有 `[N]` 时语义不足。
- `静态资源版本`：HTML 中 `app.js?v=...` 的查询参数，用来让浏览器刷新缓存。

验证：

```text
python -m pytest tests/test_frontend_app.py -q -> 10 passed
node --check app/frontend/static/app.js -> passed
```

遗留复验：Phase 6 启动服务后进行浏览器 desktop + 390x844 mobile smoke，重点检查加载态、错误提示和引用 hover 卡片。

## Phase 5 部署文档与配置指南结论

新增部署指南：

```text
docs/deployment_guide.md
```

关键内容：

- 明确阶段 39 Docker 默认入口为 `uvicorn app.main:app --host 0.0.0.0 --port 8000`。
- 明确旧 `chainlit_app.py` 仅作为历史界面保留，不是 Docker 默认启动入口。
- 记录 `docker build`、`docker compose up --build`、`GET /health` 和 production smoke 命令。
- 说明 `./data:/app/data` 数据卷、SQLite 位置和 `.dockerignore` 数据边界。
- 补齐结构化日志字段和敏感信息禁止写入边界。

`.env.example` 已补齐：

```text
PLANNER_CHAT_MODEL_*
RERANKING_*
```

README 新增 `Docker Quick Start`，指向 `docs/deployment_guide.md`。

验证：

```text
python -m pytest tests/test_stage39_deployment_docs.py -q -> 4 passed
```

## Phase 6 回归验证与收尾结论

阶段 39 已完成开发、测试、普通文档和 Obsidian 草稿，停在人工核验前状态。

验证结果：

```text
python -m pytest tests/test_stage39_design.py tests/test_stage39_docker.py tests/test_docker_assets.py tests/test_stage39_logging.py tests/test_frontend_app.py tests/test_stage39_deployment_docs.py -q -> 33 passed
python -m pytest -q -> 804 passed in 69.92s
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8010 --timeout-seconds 120 -> rows=11 execute=true failed=0
browser smoke -> desktop/mobile passed, consoleErrors=[]
docker build -> succeeded
```

关键结论：

- 阶段 39 没有修改检索策略、prompt 策略、Stage 30 评分规则、embedding/rerank provider 或外部数据源。
- 结构化日志已覆盖请求入口和 Agent 路径，且只写安全字段、截断摘要和脱敏结果。
- 前端加载态、中文错误提示、首问会话标题和 `[N]` 引用来源 hover/focus 展示已落地。
- README、部署指南、`.env.example`、docs/progress、architecture、data_sources 和 phase review 已更新。
- Obsidian 阶段页、Phase 汇报索引、Phase 0-6 小汇报和总索引已补齐。
- 当前未执行 `git add`、commit、tag、push 或创建 PR。
