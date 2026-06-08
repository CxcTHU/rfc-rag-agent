# 阶段 17 检索架构升级评测报告

本报告由 `scripts/evaluate_stage17_retrieval_upgrade.py` 生成，对比旧 hybrid baseline 与 BM25+vector RRF upgraded retrieval。

## 汇总

| Metric | Value |
|---|---|
| results_file | `data/evaluation/stage17_retrieval_upgrade_results.csv` |
| total_queries | 15 |
| baseline_hits | 15 |
| upgraded_hits | 15 |
| improved | 0 |
| neutral | 15 |
| regression | 0 |
| unresolved | 0 |
| default_decision | candidate_for_manual_review |

## 默认链路结论

阶段 17 默认不自动替换旧 `HybridSearchService`。只有人工核验评测表确认无关键回归后，才考虑把 BM25+vector RRF 接入默认 Brain hybrid。

## 数据安全边界

- 本报告不触发真实 API 调用。
- 本报告不保存 API key、Bearer token、供应商原始敏感响应或受限全文。
- 阶段 17 当前等待用户人工核验，尚不提交、不打 tag、不推送。

## Phase 9 人工复核摘要

人工复核结果表：`data/evaluation/stage17_retrieval_upgrade_manual_review.csv`。

| Metric | Value |
|---|---|
| reviewed_queries | 15 |
| acceptable | 14 |
| needs_tuning | 1 |
| regression | 0 |
| defer | 0 |
| source_mismatch | 5 |
| default_switch_blockers | 1 |
| phase9_default_recommendation | keep_existing_hybrid |

### 风险判断

- 升级检索在评测集上无 hit 级 regression，但存在排序软退化样例：mesoscopic_modeling（hit 指标掩盖的名次下降）。
- source_match=no 的样例多为等价主题文献换位（常见为中文 query 下中文母语文献上浮），仍 top-1 命中，判定 acceptable。

### 默认链路接入建议

- 保持 BM25 + vector RRF 与邻近 chunk 上下文扩展为候选能力 / 配置开关，暂不替换默认 `HybridSearchService`、Brain、`/chat`、`/agent`。
- 阻断原因：评测集 hit 已饱和（缺乏区分度）导致升级零增益，且存在综述文档上浮造成的排序软退化。

### 下一阶段依据

- 阶段 18 构建更有区分度的难评测集（跨段证据、易混淆术语、需拒答边界），并对综述类文档加权或 topic-anchor rerank 做对照，再决定 RRF 是否进入默认链路。
