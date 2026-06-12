# 阶段 27 验收报告：Chainlit 前端 + Docker 容器化 + GitHub Actions CI

验收日期：2026-06-12

验收结论：PASS。

阶段 27 范围与目标对齐：新增 Chainlit 对话界面入口，保留 FastAPI API 与原生前端；新增 Dockerfile、docker-compose 和 `.dockerignore`；新增 GitHub Actions pytest CI；全量测试通过，且不依赖真实 API。用户安装 Docker Desktop 后，已完成 `docker compose up --build -d` 实跑核验，容器内 Chainlit 首页和 settings 接口均返回 200。随后新增 Phase 7，将原生 FastAPI 首页升级为深色科技风 RAG 产品首页，并将“开始问答”和“资料库”拆成两个可切换界面；Docker 默认 Chainlit 入口保持不变。

## 逐项核对

| 核对项 | 证据 | 结论 |
| --- | --- | --- |
| 阶段起点 | `phase-26-complete -> 5000d4f`，已并入 `main -> 74afce9` | PASS |
| Chainlit 入口 | `chainlit_app.py` 新增 `@cl.on_chat_start`、`@cl.on_message`，复用 `stream_agent_query_events()`、`ConversationRepository` 和 provider 工厂 | PASS |
| 闲聊/default/agentic 链路 | Chainlit 入口复用阶段 25/23 的 service 层事件流，未复制新业务分叉 | PASS |
| 流式输出 | `token` 事件映射到 `msg.stream_token()`；`metadata` 转为 `AgentQueryResponse` | PASS |
| 引用与步骤展示 | `sources_markdown()`、`workflow_markdown()`、`emit_workflow_steps()` 输出 citations 与 workflow steps | PASS |
| FastAPI 兼容 | 原 `/agent/query`、`/agent/query/stream`、`/search/hybrid`、`/quality-report` 测试与 smoke 通过 | PASS |
| 原生前端视觉升级 | `app/frontend/` 升级为深色科技风首页，保留真实 Agent demo、资料库工作台、data hook 和移动端响应式布局；“开始问答”和“资料库”可切换 | PASS |
| Docker 资产 | `Dockerfile`、`docker-compose.yml`、`.dockerignore` 存在；测试覆盖不复制 `.env`、SQLite、Obsidian、原始全文；`docker compose up --build -d` 启动成功 | PASS |
| CI 资产 | `.github/workflows/ci.yml` 使用 Python 3.11、deterministic provider、`python -m pytest -q` | PASS |
| 安全合规 | 未发现阶段 27 新增真实 API key、Bearer token、Authorization 真值、供应商原始敏感响应或受限全文 | PASS |
| 文档同步 | README、docs/progress、docs/architecture、docs/data_sources、AGENT.MD、Obsidian 草稿已同步 | PASS |
| 可选真实 reranking smoke | 本地 `.env` 中 `RERANKING_PROVIDER=jina`，最小 rerank 调用成功并完成解析；未打印 key，未保存供应商原始响应 | PASS |

## 独立复验记录

```text
git merge-base --is-ancestor phase-26-complete main
-> passed

git tag --list phase-27-complete
-> empty before验收提交

python -m pytest -q
-> 520 passed, 1 warning in 70.02s

python -m pytest tests/test_frontend_app.py tests/test_docker_assets.py tests/test_chainlit_app.py -q
-> 15 passed, 1 warning

python -m pytest -q
-> 520 passed, 1 warning in 73.67s

python -m pytest tests/test_frontend_app.py tests/test_docker_assets.py tests/test_chainlit_app.py -q
-> 15 passed, 1 warning in 1.59s

python -m pytest -q
-> 520 passed, 1 warning in 83.56s

真实 reranking 配置隔离修复后复验：
python -m pytest tests/test_agent_stream_api.py::test_agent_stream_yields_first_token_before_model_finishes tests/test_hybrid_search.py::test_hybrid_search_runs_keyword_and_vector_in_parallel -q
-> 2 passed in 1.76s

python -m pytest -q
-> 520 passed, 1 warning in 145.76s

浏览器前端 smoke
-> 默认进入“开始问答”；顶部导航切换到 #library-view 成功；console error/warning 为 0

真实 reranking API key 最小 smoke
-> provider=jina，base host=api.jina.ai，api key 已配置；最小 rerank 调用成功，返回 2 条结果并完成解析

docker --version
-> Docker version 29.5.3

docker compose version
-> Docker Compose version v5.1.4

docker run --rm hello-world
-> Hello from Docker

docker compose up --build -d
-> image rfc-rag-agent:phase27 built; container rfc-rag-agent-rfc-rag-agent-1 started

docker compose ps
-> STATUS Up; PORTS 0.0.0.0:8000->8000/tcp

GET http://127.0.0.1:8000
-> 200

GET http://127.0.0.1:8000/project/settings?language=zh-CN
-> 200
```

敏感信息扫描说明：扫描命中了历史文档中的安全规则说明、测试用假 key 和 `risk-...` 字符串误报；未发现阶段 27 新增真实密钥或供应商原始敏感响应。

测试隔离说明：本机 `.env` 已配置真实 Jina reranking key。验收复跑时发现两个离线定时测试误触发真实 rerank，导致测试耗时超过断言阈值；已在相关测试中显式禁用/隔离 reranking provider，保证全量测试不依赖真实 API。

## 改进建议

1. 后续可增加 GitHub Actions 中的可选 `docker build .`，用于提前发现 Dockerfile 依赖安装问题。
2. Chainlit 浏览器端可在后续补自动化发送消息验证，覆盖真实 UI 输入、token 增量、citations 附件和 Step 展示。
3. 当前 Chainlit 未做登录和用户隔离；如计划公开部署，需要在 Conversation 增加 owner/user 维度，并补权限测试。
4. 如后续希望 Docker 一条命令同时暴露新版原生 FastAPI 首页，可在 docker-compose 中追加 FastAPI 服务；本阶段保持 Docker 默认入口为 Chainlit。

## 后续阶段观察

阶段 27 已把项目从“本地 API/工作台可用”推进到“有可演示聊天界面、容器化入口、CI 质量门和产品化首页”。本次验收结论为 PASS，用户已授权提交、创建阶段 tag、合并并推送 GitHub。若继续上线方向，再补生产部署事项：域名/HTTPS、反向代理、生产 `.env` 管理、容器日志、数据卷备份和认证权限。
