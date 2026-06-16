# 阶段 39 任务计划：生产部署与端到端体验

## 目标

在阶段 38 Judge gate 通过、默认链路稳定的基础上，把系统从"本地能跑"推到"可部署、可运维、可交付"。主线是 Docker 容器化更新、结构化日志、前端体验打磨和部署文档，不动检索策略、prompt 策略和评分规则。

目标分支建议：`codex/phase-39-production-deployment`

核心原则：
- Dockerfile / docker-compose 更新到当前 FastAPI + uvicorn 架构（旧版用 chainlit，已废弃）。
- 引入结构化日志（structlog 或标准 logging JSON），覆盖请求、Agent 调用、错误，不记录 API key / token / raw response / reasoning_content。
- 前端体验打磨：加载态、错误提示、引用来源跳转、会话标题。
- 不动检索策略（chunk、rerank、hybrid 参数）。
- 不动 prompt 策略（structured_final_answer 保持不变）。
- 不动 Stage 30 评分权重、等级阈值、release_decision 规则。
- 不替换默认 embedding / rerank / chat provider。
- 不引入新外部数据源。
- 不写 API key / Bearer token / raw provider response / reasoning_content / hidden thought / 受限全文进 Git、CSV、文档、测试或 Obsidian。

## 当前基线

```text
main / origin/main -> 33b63e0 Merge phase 38 tool calling generation quality
Dockerfile -> 旧版，CMD 用 chainlit run，已不适用当前 FastAPI + uvicorn 架构
docker-compose.yml -> image: rfc-rag-agent:phase27，旧版
app/main.py -> FastAPI create_app()，当前实际入口，通过 uvicorn app.main:app 启动
结构化日志 -> 无，app/ 下没有 logging/structlog 引用
前端 -> 基本可用，Enter 发送 / Shift+Enter 换行已实现，无加载态动画、无引用跳转、无错误友好提示
Stage 30 -> 91.52 / A / pass
Judge gate -> structured_final_answer pass（cov=0.808 / cit=0.867 / safety=1.000）
全量 pytest -> 785 passed
```

## Phase 顺序

### Phase 0：启动校准与阶段 39 规划落盘

任务：
- 阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/phase_reviews/phase-38.md、docs/stage38_tool_calling_quality_decision.md。
- 阅读 task_plan.md、findings.md、progress.md。
- 运行 git status -sb、git log --oneline -5 --decorate。
- 确认 Phase 38 已合并到 main。
- 从合并后的 main 创建或切换到 codex/phase-39-production-deployment 分支。

完成记录：
- 已阅读 AGENT.MD、README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md、docs/phase_reviews/phase-38.md、docs/stage38_tool_calling_quality_decision.md。
- 已阅读 task_plan.md、findings.md、progress.md。
- 已运行 `git status -sb` 与 `git log --oneline -5`，确认 `main / origin/main -> 33b63e0 Merge phase 38 tool calling generation quality`。
- 已确认 Phase 38 完成提交 `ee6830a Complete phase 38 tool calling generation quality` 已通过 `33b63e0` 合并到 main。
- 已从合并后的 main 创建并切换到 `codex/phase-39-production-deployment`。
- 启动时已有阶段 39 规划文件未提交改动，已作为用户/前序交接状态保留并继续校准。

### Phase 1：阶段 39 设计文档

任务：
- 新增 docs/stage39_production_deployment.md：固定主线（Docker 更新 / 结构化日志 / 前端体验 / 部署文档）和安全边界。
- 新增 tests/test_stage39_design.py，断言设计文档涵盖核心范围。

完成记录：
- 已新增 `docs/stage39_production_deployment.md`，固定 Docker、结构化日志、前端体验、部署文档、回归验证五条主线。
- 已明确不动检索策略、prompt 策略、Stage 30 评分规则、embedding/rerank/chat provider 和外部数据源。
- 已补充结构化日志、middleware、request_id、health check、hover 来源卡片、smoke、多阶段构建等新词解释。
- 已新增 `tests/test_stage39_design.py`，覆盖基线、主线、不动边界、敏感信息边界、Docker、日志、前端、部署和收尾验证。
- 已运行 `python -m pytest tests/test_stage39_design.py -q`，结果 `8 passed`。

### Phase 2：Dockerfile 与 docker-compose 更新

任务：
- 更新 Dockerfile：CMD 改为 uvicorn app.main:app，安装依赖用 pyproject.toml，多阶段构建减小镜像。
- 更新 docker-compose.yml：image tag 更新，环境变量管理，health check 配置。
- 新增 .dockerignore 排除测试、评测数据、.env、__pycache__、.git 等。
- 本地 docker build 验证（构建成功即可，不要求启动完整服务）。
- 新增 tests/test_stage39_docker.py，断言 Dockerfile 和 docker-compose.yml 存在并包含关键配置。

完成记录：
- 已将 `Dockerfile` 改为多阶段构建：builder 阶段用 `pyproject.toml` 构建 wheel，runtime 阶段安装 wheel 并复制 `app/`。
- 已将容器 CMD 从旧 Chainlit 入口改为 `uvicorn app.main:app --host 0.0.0.0 --port 8000`。
- 已将 `docker-compose.yml` image 更新为 `rfc-rag-agent:phase39-production-deployment`，补充 `APP_ENV=production`、数据卷和 `/health` healthcheck。
- 已更新 `.dockerignore`，排除 tests、data/evaluation、.env、本地数据库、全文目录、Obsidian 和日志。
- 已更新 `tests/test_docker_assets.py` 并新增 `tests/test_stage39_docker.py`。
- 已运行 `python -m pytest tests/test_stage39_docker.py tests/test_docker_assets.py -q`，结果 `7 passed`。
- 已启动 Docker Desktop，确认 Docker server `29.5.3` 可用，并运行 `docker build -t rfc-rag-agent:phase39-production-deployment .`，构建成功。

### Phase 3：结构化日志

任务：
- 引入 Python 标准 logging，配置 JSON 格式输出（不额外引入 structlog 依赖，用标准库即可）。
- 在请求入口（FastAPI middleware）记录请求日志：method、path、status_code、latency_ms。
- 在 Agent 调用路径记录关键事件：query_received、tool_call_executed、answer_generated、refusal_triggered。
- 确保不记录 API key、Bearer token、raw provider response、reasoning_content、用户原始问题全文（可记录 truncated 摘要）。
- 新增 tests/test_stage39_logging.py。

完成记录：
- 已新增 `app/core/structured_logging.py`，提供 JSON formatter、request_id context、日志字段脱敏和文本截断。
- 已在 `app/main.py` 增加 FastAPI middleware，记录 `request_completed` / `request_failed`，包含 method、path、status_code、latency_ms、request_id。
- 已在 `app/api/agent.py` 记录 Agent 入口 `query_received` 和最终 `answer_generated` / `refusal_triggered`。
- 已在 `app/services/agent/tool_calling_service.py` 记录 tool-calling runtime 的 `query_received`、`tool_call_executed`、`answer_generated`、`refusal_triggered`。
- 日志字段只保留 mode、计数、状态、截断 question_summary 和安全摘要，不写 API key、Bearer token、raw response、reasoning_content、完整问题或完整 chunk。
- 已新增 `tests/test_stage39_logging.py`。
- 已运行 `python -m pytest tests/test_stage39_logging.py -q`，结果 `4 passed`。
- 已运行 `python -m pytest tests/test_health.py tests/test_agent_api.py tests/test_agent_stream_api.py tests/test_tool_calling_agent_service.py tests/test_stage39_logging.py -q`，结果 `56 passed`。

### Phase 4：前端体验打磨

任务：
- 加载态：Agent 请求期间显示加载指示器（spinner 或脉冲动画）。
- 错误提示：请求失败时显示友好中文错误提示，不暴露内部错误详情。
- 引用来源展示优化：[N] 引用可点击或 hover 显示来源标题和摘要。
- 会话标题：根据首条消息自动生成简短会话标题。
- 保持桌面和移动端响应式布局不退步。
- 新增或更新 tests/test_frontend_app.py 中的相关断言。

完成记录：
- 已在 `app/frontend/static/app.js` 增加 `conversationTitleFromQuestion()`，新建会话时用首条用户问题生成简短标题。
- 已增加 `userFriendlyErrorMessage()`，Agent 请求失败时展示中文友好错误，不直接暴露内部异常详情。
- 已增加 `citationReferenceHtml()` 与 `renderAnswerWithCitationLinks()`，将回答中的 `[N]` 渲染为可点击/hover 的来源引用。
- 已在思考态加入 `loading-spinner`，保留流式 token 到达后的状态切换。
- 已在 `app/frontend/static/styles.css` 增加 spinner 动画、引用按钮和 hover 来源卡片样式。
- 已更新静态资源版本为 `phase39-experience`。
- 已更新 `tests/test_frontend_app.py` 覆盖新前端体验合同。
- 已运行 `python -m pytest tests/test_frontend_app.py -q`，结果 `10 passed`。
- 已运行 `node --check app/frontend/static/app.js`，语法检查通过。
- 浏览器桌面/移动 smoke 留到 Phase 6 统一执行。

### Phase 5：部署文档与配置指南

任务：
- 新增 docs/deployment_guide.md：Docker 部署步骤、环境变量配置、数据卷挂载、健康检查。
- 更新 README.md：新增 Quick Start（Docker）段落。
- 新增 .env.example：列出所有环境变量及说明（不含实际 key 值）。

完成记录：
- 已新增 `docs/deployment_guide.md`，覆盖 FastAPI/uvicorn Docker 入口、build、compose、环境变量、数据卷、healthcheck、production smoke、结构化日志和常见问题。
- 已更新 `README.md`，新增 `Docker Quick Start`，说明阶段 39 Docker 默认入口为 FastAPI + uvicorn，并链接部署指南。
- 已更新 `.env.example`，补齐 planner chat provider 与 reranking provider 配置项，未写入真实 key。
- 已新增 `tests/test_stage39_deployment_docs.py`。
- 已运行 `python -m pytest tests/test_stage39_deployment_docs.py -q`，结果 `4 passed`。

### Phase 6：回归验证、文档与阶段收尾

任务：
- 全量 pytest 通过。
- Stage 30 维持 91.52 / A / pass。
- Production smoke 通过。
- Docker build 验证（构建成功，容器启动不报错）。
- 浏览器 smoke：桌面和移动端验证加载态、错误提示、引用展示。
- 更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md。
- 新增 docs/phase_reviews/phase-39.md 验收草稿。
- 补齐 Obsidian。
- 停在用户人工核验前状态。

完成记录：
- 已运行 Phase 39 focused suite：`python -m pytest tests/test_stage39_design.py tests/test_stage39_docker.py tests/test_docker_assets.py tests/test_stage39_logging.py tests/test_frontend_app.py tests/test_stage39_deployment_docs.py -q`，结果 `33 passed`。
- 已运行全量测试：`python -m pytest -q`，结果 `804 passed in 69.92s`。
- 已运行 Stage 30：`python scripts/score_stage30_quality.py`，结果 `overall=91.52 grade=A release_decision=pass`。
- 已在 8010 端口启动 FastAPI + uvicorn 并运行 production smoke：`python scripts/run_production_smoke.py --execute --base-url http://127.0.0.1:8010 --timeout-seconds 120`，结果 `rows=11 execute=true failed=0`。
- 已用浏览器完成 desktop 与 390x844 mobile smoke，页面可加载、无控制台错误、无横向溢出，引用按钮和 hover/focus 来源样式可用。
- 已更新 README.md、docs/progress.md、docs/architecture.md、docs/data_sources.md，并新增 `docs/phase_reviews/phase-39.md`。
- 已建立 `obsidian-vault/阶段汇报/阶段 39 - 生产部署与端到端体验/`，补齐阶段 39 Phase 汇报索引、Phase 0-6 小汇报、阶段页，并更新 Obsidian 总索引。
- 已启动 Docker Desktop，确认 Docker server `29.5.3` 可用，并运行 Docker build，镜像 `rfc-rag-agent:phase39-production-deployment` 构建成功。
- 当前停在用户人工核验前，未执行 `git add`、commit、tag、push 或创建 PR。

## 完成标准

- Dockerfile 和 docker-compose.yml 更新到 FastAPI + uvicorn，docker build 成功。
- Dockerfile 和 docker-compose.yml 已更新到 FastAPI + uvicorn；Docker build 已完成环境复验并构建成功。
- 结构化日志覆盖请求入口和 Agent 调用路径，JSON 格式，不泄露敏感信息。
- 前端加载态、错误提示、引用来源展示已实现。
- 部署文档和 .env.example 已就位。
- Stage 30 维持 91.52 / A / pass。
- 全量 pytest 通过；production smoke 通过；浏览器 smoke 通过。
- 未提交，等待用户人工核验。
