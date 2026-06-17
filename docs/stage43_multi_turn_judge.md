# 阶段 43 多轮 LLM Judge 设计

## 目标

Phase 12-13 在既有 Stage 43 多轮检索 baseline 之外，新增真实 LLM Judge 对多轮生成质量的离线评判。它复用 Phase 34/42 的 Judge 边界：默认 dry-run，不调用真实 API；只有显式 `--execute` 且本地 `.env` 配置完整时才调用真实 Judge。

## 评判维度

Judge 只输出四个多轮相关分数：

- `answer_faithfulness`：回答是否只基于检索到的知识库证据，不把 summary、memory 或前轮聊天当作事实来源。
- `citation_accuracy`：回答中的引用是否能被 sources 支撑，拒答时是否没有伪造引用。
- `context_coherence`：追问、指代、省略、用户纠错和话题切换是否正确理解当前轮语境。
- `refusal_consistency`：多轮拒答和责任边界是否稳定，不因历史上下文污染而回答不该回答的问题。

输出还包括 `risk_level`、`short_reason`、`next_action`。CSV 不保存完整答案、完整 chunk、raw provider response、`raw_response`、`reasoning_content`、API key、Bearer token 或 Authorization header。

## 执行模式

```powershell
python scripts/judge_stage43_multi_turn_quality.py
python scripts/judge_stage43_multi_turn_quality.py --history-mode all --execute
```

dry-run 只验证 case、history mode、输出 schema 和 Judge 配置状态。真实执行分两步：先用当前 Agent/Brain 链路生成回答，再把脱敏 payload 交给 OpenAI-compatible Judge。若 `.env` 缺少 Judge provider/base_url/model/key，脚本写 `skipped`，不能把 dry-run 冒充成真实 Judge。

## layered_memory 决策口径

Phase 13 基于 deterministic baseline 与 Judge summary 一起决策：

- 如果 `layered_memory` 在 `context_coherence` 或 `answer_faithfulness` 上明显优于 `summary_recent`，但检索 hit 仍不足，可考虑后续新增 `constraints` slot 或 stale-anchor invalidation。
- 如果 `layered_memory` 无明显增益或用户纠错场景风险更高，则保持当前策略：作为 query rewrite / retrieval 辅助，不替换默认 `summary_recent`。

该决策不改变 Stage 30 评分规则、provider 拓扑或数据源边界。
