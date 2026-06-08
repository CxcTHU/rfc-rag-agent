# Claude Code 入口文件

本项目的**唯一规则真相源是 `AGENT.MD`**。本文件只做转发，不复制规则，避免两份规则不同步。

## 开工前必做（每个新线程）

1. 完整阅读 `AGENT.MD`（项目定位、阶段路线、教学原则、Quivr 参考、收尾清单都在里面）。
2. 阅读 `README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`。
3. 运行 `git status -sb` 和 `git log --oneline -5`，确认上一个 Agent（Claude 或 Codex）留下的状态，不要覆盖未提交的工作。
4. 阅读根目录的 `task_plan.md`、`findings.md`、`progress.md`，它们是当前活跃阶段的工作记忆。

## 双 Agent 时间分片协作（Claude + Codex 轮流）

本项目由 Claude 和 Codex **轮流**开发，采用时间分片：同一时刻只有一个 Agent 在这个工作目录干活。详细规则见 `AGENT.MD` 的「Claude + Codex 双 Agent 协作规则」一节。最关键的三条：

- 开工前先读状态，确认接手点；交班前把工作区留在可理解状态。
- `AGENT.MD` 和 `docs/progress.md` 是共享文件，按 `AGENT.MD` 约定的时机更新，不要和另一个 Agent 抢改。
- 未经用户人工核验，不 `git add` / `commit` / `tag` / `push` / 建 PR。
