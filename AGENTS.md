# Codex 入口文件（AGENTS.md）

本项目的**唯一规则真相源是 `AGENT.MD`**。本文件（以及 `AGENT.md`、`CLAUDE.md`）只做转发，不复制规则。

## 开工前必做（每个新会话）

1. 完整阅读 `AGENT.MD`。
2. 阅读 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
3. 运行 `git status -sb` 和 `git log --oneline -5`，确认上一个 Agent（Claude 或 Codex）留下的状态。
4. 阅读根目录 `task_plan.md`、`findings.md`、`progress.md`。

## 双 Agent 时间分片协作（Claude + Codex 轮流）

详见 `AGENT.MD` 的「Claude + Codex 双 Agent 协作规则」一节。核心：轮流开发、开工读状态、交班留干净状态、`AGENT.MD` 与 `docs/progress.md` 不抢改、未经用户核验不提交。
