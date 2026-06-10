# 阶段 20 验收报告

- 验收人：Claude（技术验收）
- 验收日期：2026-06-10
- 分支：`codex/phase-20-default-chain-and-eval-upgrade`
- 基线：`main` 含 `12184d7 Merge phase 19 ...`，`phase-19-complete -> ffb4756`（未移动）
- 验收方式：直接核对工作区——读 diff、独立重跑测试、复现评测 CSV、扫描敏感信息、检查文档同步与提交边界（不依赖 Codex 口头汇报）

## 结论

**PASS** —— 达到阶段 20 目标（评测口径升级 + 真实 Jina query 校验 + 默认链路诚实决策 + 责任边界拒答门），已通过用户人工核验并提交。

- 功能提交：`706047d Complete phase 20 default chain and eval upgrade`
- 阶段 tag：`phase-20-complete -> 706047d`（指向功能提交，非 merge）
- 合并提交：`8333d71 Merge phase 20 default chain and eval upgrade`

## 验收明细

| 维度 | 核对方式 | 结果 |
|---|---|---|
| 范围对齐 | `git diff --stat` | PASS：仅 `brain/workflow.py`(+45)、`brain/service.py`(+26)、`frontend.py`(+8) 动到运行时；其余为文档/测试/脚本/CSV |
| 责任门正确性 | 精读 diff | PASS：纯函数，置于证据判断与模型生成之前，落在共享 `BrainService`，`/chat` 与 Agent 同覆盖 |
| 测试正反例 | 读 `test_brain_workflow.py` / `test_brain_service.py` | PASS：责任判定题拒答 + 概念/关键词学习题不误拒 |
| 全量测试 | 独立重跑 `pytest -q` | PASS：424 passed in 30.63s |
| 评测口径升级 | `stage20_eval_upgrade_summary.csv` | PASS：用 expected_answer_points 的 `coverage_ratio` 替代题录关键词命中 |
| 真实 Jina query 校验 | `stage20_eval_upgrade_real_jina_summary.csv` | PASS：`real_config_status=completed`，仅 query 端，未重做 chunk embedding |
| 默认链路决策 | `stage20_default_chain_decision.csv` | PASS：`keep_existing_hybrid`，阻断 `Δp@1=+0.000<0.10`（det 与 real 一致），诚实 |
| quality gate | `stage20_quality_summary.csv` | PASS：`pass/low`，6 行全 low |
| 安全/合规 | grep 全部 stage20 产物 | PASS：无密钥/Bearer/api-key 真值、无向量、无供应商原始 payload、无受限全文 |
| 文档同步 | AGENT.MD / README 顶部 | PASS：AGENT.MD 有阶段 20 章节且正确标注阶段 19 已合并，未滞后 |
| 提交边界（验收时） | `git tag` / `git diff --cached` | PASS：验收当时无 tag、无暂存、停在人工核验前；经用户授权后才提交 |

## 遗留观察（带入后续阶段）

1. **检索质量是真正未解的瓶颈**：中文难题集答案级 `p@1=0.133`（15 题命中 2）。候选重权把 `deep_top1` 拉到 0.67–0.73，但答案覆盖 p@1 未动 —— "深度全文上浮到 top-1，但召回段落未真正覆盖答案要点"。单次 hybrid + 后处理重权的天花板已现，需换攻法（passage 级召回 / 迭代式 agentic RAG / coverage 指标灵敏度复核）。日常题（阶段 6/10/11）仍稳定通过，0.133 是在对抗性难题集上。**已规划由阶段 21 LangGraph agentic RAG 从迭代自纠维度攻这个瓶颈。**
2. **责任门反例偏软**：反例用的是干净概念/关键词题，边界问法（如"…是否满足抗渗要求"会命中模式2）未压力测试。门偏保守是设计意图，不阻断；真实使用若误拒再扩反例集。
3. **责任门仅覆盖中文**：去空格 + 中文正则，英文责任问法不拦。语料中英混合，记录备查。

## 路线图决策（本阶段确认）

检索微调线（阶段 17–20）连续 4 个阶段结论均为"保持不变 / 边际增益"，已到边际收益递减区。换轨为能力跃迁路线：

- 阶段 21：Agent 编排升级，引入 LangGraph 做有状态 agentic RAG（retrieve → grade → rewrite/decompose → generate → reflect）。
- 阶段 22：前端升级 + 可观测。
- 阶段 23：正式部署（Docker Compose / env / 可选 pgvector）。
