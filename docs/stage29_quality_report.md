# 阶段 29 质量报告：真实 Embedding 重建与端到端质量闭环

本报告由 `scripts/build_stage29_quality_report.py` 生成，只读汇总阶段 29 的脱敏评测结果，不触发真实 API、不写数据库。

## 语料与索引状态

- documents：635
- chunks：12716
- sources：673
- chunk_embeddings：25432
- provider 分布：deterministic/hash-token-v1/dim=64:12716;jina/jina-embeddings-v3/dim=1024:12716
- document source_type 分布：institutional_access_pdf:325;local_file:10;metadata_record:115;open_access_pdf:15;standard_document:9;web_page:136;wikipedia:25

## 真实 Jina 评测结果

- total_queries：18
- non_refusal_total：15
- precision@1：0.600
- precision@3：0.867
- precision@5：0.933
- avg coverage_ratio：0.664
- refusal_accuracy：1.000
- source_type_distribution：institutional_access_pdf:17;metadata_record:6;open_access_pdf:5;standard_document:25;web_page:28;wikipedia:9

## 质量门槛汇总

| Section | Metric | Status | Value | Risk | Recommendation |
| --- | --- | --- | --- | --- | --- |
| embedding_rebuild | provider_coverage | completed | documents=635, chunks=12716, chunk_embeddings=25432, deterministic/hash-token-v1/dim=64:12716;jina/jina-embeddings-v3/dim=1024:12716 | low | Jina 与 deterministic 双索引完整；人工核验前不要提交或打 tag。 |
| real_jina_quality | precision_and_coverage | completed | p@1=0.600, p@3=0.867, p@5=0.933, coverage=0.664 | medium | 重点复核 p@5 未命中与 coverage<0.5 的样例，不伪造成全部通过。 |
| new_corpus_coverage | source_type_distribution | completed | institutional_access_pdf:17;metadata_record:6;open_access_pdf:5;standard_document:25;web_page:28;wikipedia:9 | low | 新语料已进入 top-k；继续关注 Wikipedia dam applications 召回失败样例。 |
| refusal_boundary | refusal_accuracy | closed | 1.000 over 3 refusal queries | low | 工程签字、密钥泄露、绕过付费墙三类边界当前均正确拒答。 |
| known_issues | manual_review_queue | review_required | p@5_misses=1, low_coverage=2 | medium | 人工核验 stage29_wiki_dam_applications 与 stage29_web_rfc_advantages。 |
| api_regression | full_tests | passed | 556 passed, 1 warning | low | 阶段 8 将再次运行全量回归，确认核心 API 未被破坏。 |
| overall | stage29_quality_gate | review_required | medium | medium | 阶段 29 功能完成后应停在用户人工核验前，不提交、不打 tag、不 push。 |

## 人工复核队列

- `stage29_wiki_dam_applications`：category=wikipedia，p@5=false，coverage=0.250，top1=web_page / Introduction。
- `stage29_web_rfc_advantages`：category=web，p@5=true，coverage=0.250，top1=web_page / Filling the gaps in large concrete dams。

## 结论

阶段 29 已完成真实 Jina v3 全量索引重建，并保留 deterministic 索引用于 CI。真实评测显示新语料已经进入 top-k 召回，拒答边界当前稳定；但仍存在 Wikipedia dam applications 未命中和个别覆盖率偏低样例，需在用户人工核验时重点查看。
