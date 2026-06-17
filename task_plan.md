# 阶段 42 任务计划：生成质量校准与生产体验完善

## Goal

在阶段 41 完成导入后检索质量优化（19,300 child chunks 双覆盖、FAISS 重建、GLM p@5=1.000 / coverage=0.972）的基础上，从两条主线推进：（A）扩展 LLM Judge 评测集并覆盖新语料，针对低分样例做 prompt 微调，争取 Judge gate 从 review_required 推到 pass；（C）完成阶段 40 暂缓的长回答分段渲染，并完善会话管理 UX（删除、重命名）。完成开发、测试、普通文档与 Obsidian 草稿，停在用户人工核验前。

## Current Phase

Phase 8: 文档与 Obsidian 收尾（已完成，停在用户人工核验前）。

## 当前基线与工作区状态

- Git 基线：阶段 41 已提交为 `007b0f0 Complete phase 41 post-import retrieval optimization`，并已本地合并到 `main -> d7dfca1 Merge phase 41 post-import retrieval optimization`；当前阶段 42 分支为 `codex/phase-42-generation-quality-and-experience`。
- 本地 DB: documents=753, indexable child chunks=19,300, GLM+deterministic embedding 全覆盖。
- Stage 30: 91.52 / A / pass。
- Stage 38 Judge 最佳成绩: structured_final_answer cov=0.808 / cit=0.867 / safety=1.000 / gate=pass（但 baseline gate 仍 review_required）。
- 全量测试: 830 passed。
- 前端: 原生 HTML/CSS/JS，已有会话列表、Agent 问答、流式输出、停止生成、token 节流、sanitize。
- 长回答分段渲染: Phase 40 明确暂缓，尚未实现。

## Phases

### Phase 0：启动校准与规划落盘

- [x] 阅读 `AGENT.MD`、`README.md`、`docs/progress.md`、`docs/architecture.md`、`docs/data_sources.md`
- [x] 运行 `git status -sb` 与 `git log --oneline -5`
- [x] 确认阶段 41 已合并到 main
- [x] 从新 main 创建 `codex/phase-42-generation-quality-and-experience`
- [x] 校准 `task_plan.md`、`findings.md`、`progress.md`
- **Status:** complete

### Phase 1：设计文档与测试合同

- [x] 新增 `docs/stage42_generation_quality_and_experience.md`
- [x] 明确两条主线：A（Judge 评测扩展 + prompt 微调）和 C（长回答渲染 + 会话管理 UX）
- [x] 明确安全边界和不做项
- [x] 新增 `tests/test_stage42_design.py` 设计合同测试
- [x] 运行设计合同测试
- **Status:** complete

### Phase 2：Judge 评测集扩展

- [x] 将阶段 41 新增 12 条评测题 + 阶段 38 的 24 条合并为扩展 Judge 评测基础
- [x] 新增或扩展 Judge 评测脚本，支持对新语料运行 tool_calling_agent + structured_final_answer
- [x] dry-run 验证评测脚本正确性
- [x] 运行 `--execute` 真实 Judge（需真实 provider）
- [x] 输出 Judge 结果 CSV：answer_coverage、citation_support、safety_leak_check、gate
- **Status:** complete

### Phase 3：低分样例分析与 prompt 微调

- [x] 从 Judge 结果中筛选 coverage < 0.8 或 citation < 0.8 的低分样例
- [x] 归因分析：prompt 引用规则缺失、context 不足、answer 过短/过泛、新语料术语未覆盖
- [x] 针对性微调 `prompt_builder.py` / tool-calling final-answer prompt（引用密度、覆盖面、术语扩展）
- [x] 重跑 Judge 验证微调效果
- [x] 如 gate 仍为 review_required，诚实记录未达标原因和剩余差距
- **Status:** complete

### Phase 4：长回答分段渲染

- [x] 分析当前长回答 DOM 渲染瓶颈（token 数量 > 2000 时的 reflow 成本）
- [x] 实现分段渲染策略：将长回答按段落或固定 token 数分段插入 DOM，避免单次大量 innerHTML
- [x] 保持 citation、sanitize、AbortController 等已有功能不受影响
- [x] 不引入 React/Vue/Node 构建链
- [x] 添加前端回归测试
- **Status:** complete

### Phase 5：会话管理 UX

- [x] 实现会话删除功能（前端按钮 + 后端 API）
- [x] 实现会话重命名功能（前端 right-click context menu + 后端 API）
- [x] 确保删除/重命名后 UI 状态正确收敛
- [x] 添加前端和 API 回归测试
- [x] 桌面 + 移动端 UX 验证
- **Status:** complete

### Phase 6：全量回归与 Stage 30

- [x] 运行 `python -m pytest -q` 全量测试
- [x] 运行 `python scripts/score_stage30_quality.py` 确认评分
- [x] 运行 production smoke（dry-run 或 --execute）
- **Status:** complete

### Phase 7：浏览器 smoke

- [x] 桌面浏览器 smoke：
  - [x] Agent 页面加载与已有回答分段渲染
  - [x] 长回答分段 DOM 结构可见，多段回答已拆为 `.answer-segment`
  - [x] 会话删除/重命名
  - [x] 停止生成仍可用
  - [x] 无横向溢出、console errors=0
- [x] 移动端 390x844 smoke
- **Status:** complete

### Phase 8：文档与 Obsidian 收尾

- [x] 更新 `README.md`
- [x] 更新 `docs/progress.md`
- [x] 判断并更新 `docs/architecture.md`
- [x] 新增 `docs/phase_reviews/phase-42.md` 验收草稿
- [x] 更新 Obsidian：阶段 42 页、Phase 汇报、阶段索引、首页
- [x] 最终不执行 git add/commit/tag/push，停在人工核验前
- **Status:** complete

## 完成标准

- Judge 评测覆盖新语料，有可追踪 CSV 结果和 gate 结论。
- 如 prompt 微调提升了 Judge 分数，改动已落地并通过回归；如未达 pass gate，诚实记录差距。
- 长回答分段渲染已实现，大段回答不触发严重卡顿。
- 会话删除/重命名功能可用，前后端状态一致。
- Stage 30 维持 91.52/A/pass 或更高。
- 全量测试通过。
- 普通文档与 Obsidian 草稿完成。
- 最终停在人工核验前，不 git add/commit/tag/push/PR。
## Submission Update

2026-06-17: Phase 42 development, verification, docs, and final frontend refinements are complete. The user explicitly authorized committing, pushing, creating a GitHub PR, and merging Phase 42. Do not create or move a phase tag unless separately requested.
