# Phase 54 Review Draft: GraphRAG Real Data And Evaluation

Status: in progress before user human verification. No `git add`, commit, tag, push, or PR has been performed.

## Scope

Phase 54 turns the Phase 53 GraphRAG skeleton into a real derived knowledge graph and starts end-to-end evaluation. The chosen extraction strategy is full regex skeleton plus high-value LLM semantic supplement, not full-corpus LLM extraction.

## Extraction Results

Phase 54A validated LLM extraction on 200 sampled text chunks:

```text
llm_rows=200
llm_error_rows=20
manual_review_entity_precision=0.7914
manual_review_relation_precision=0.6500
```

Phase 54B completed the formal supplement target:

```text
regex_text_rows=33182
regex_entities=134276
regex_relations=91293
high_value_text_target=2891
table_target=1440
llm_target_attempted=4331/4331
text_llm_ok_rate=0.7951
table_llm_ok_rate=0.9167
merged_rows=34502
merged_ok=27655
```

## Graph Quality

The first merged graph failed the isolated-node gate because many standalone `Value` nodes were degree-zero fragments. Phase 54C keeps isolated `Standard`, `Material`, `Parameter`, `Method`, and `Organization` anchors, but prunes isolated `Value` nodes.

Formal graph:

```text
path=data/knowledge_graph/domain_graph.json
node_count=11396
edge_count=104522
isolated_node_count=1604
isolated_node_ratio=0.1408
largest_connected_component_node_count=9119
largest_connected_component_ratio=0.8002
pruned_isolated_value_nodes=4632
```

Phase 54C gate passes.

## E2E Evaluation Status

Phase 54D artifacts:

```text
data/evaluation/phase54_graphrag_eval_cases.csv -> 47 cases
scripts/evaluate_phase54_graphrag_e2e.py
data/evaluation/phase54_graphrag_eval_results*.csv
data/evaluation/phase54_graphrag_eval_summary*.csv
data/evaluation/phase54_graphrag_eval_ablation*.csv
```

Current completed runs:

```text
dry-run -> cases=47
retrieval-only with real embedding and reranker disabled -> retrieval_only_rows=47, error_rows=0
negative_graph_false_positive_count=0
graph_used_match_max=200
same_top_chunk_count=43 / 47
answer-only full -> answer_only_rows=47, error_rows=0
post-answer-only regression -> Stage 30 91.52 / A / pass; full pytest 1253 passed, 1 skipped
```

Formal quality acceptance has passed with GLM-5.2 judge scoring and reranker disabled:

```text
total_cases=47
completed_rows=47
error_rows=0
formal_judge_scored_rows=47
graph_intent_accuracy_delta=0.1471
graph_intent_completeness_delta=0.4412
graph_intent_citation_quality_delta=0.2647
ordinary_accuracy_delta=0.0000
negative_graph_false_positive_count=0
formal_judge_gate_decision=pass
formal_judge_gate_reason=all_phase54d_gates_passed
```

The final formal artifacts are:

```text
data/evaluation/phase54_graphrag_eval_results_real_api.csv
data/evaluation/phase54_graphrag_eval_summary_real_api.csv
data/evaluation/phase54_graphrag_eval_ablation_real_api.csv
```

Dry-run, retrieval-only, and answer-only outputs remain supporting evidence only; the formal conclusion above comes from `status=completed` rows with complete judge scores.

Detailed formal run instructions are in `docs/phase54_formal_judge_runbook.md`.
Current requirement-by-requirement status is tracked in `docs/phase54_completion_audit.md`.

Run the formal judge after configuring local `.env`:

```powershell
$env:RERANKING_ENABLED='false'
python scripts\evaluate_phase54_graphrag_e2e.py --preflight --require-judge `
  --summary-output data\evaluation\phase54_graphrag_eval_preflight.csv
```

The preflight command does not call model providers. It checks case count, graph file presence, chat provider config, judge provider config, embedding provider config, and formal judge readiness. The final preflight returned `formal_judge_ready=pass`.

After preflight passes, run:

```powershell
$env:RERANKING_ENABLED='false'
python scripts\evaluate_phase54_graphrag_e2e.py --execute --resume --progress `
  --results-output data\evaluation\phase54_graphrag_eval_results_real_api.csv `
  --summary-output data\evaluation\phase54_graphrag_eval_summary_real_api.csv `
  --ablation-output data\evaluation\phase54_graphrag_eval_ablation_real_api.csv
```

Start with `--limit 3` if checking provider stability. Only rows with `status=completed` and judge scores count toward the Phase 54D gate.

The summary writer produces a conservative formal gate:

```text
formal_judge_gate_decision=pending
  -> not all rows are status=completed, or at least one completed row lacks all judge scores
formal_judge_gate_decision=pass
  -> full judged run satisfies all gates
formal_judge_gate_decision=review_required
  -> full judged run exists but at least one gate fails
```

The gate checks graph-intent completeness lift, graph-intent accuracy non-regression, ordinary baseline accuracy non-regression, and negative off-topic graph false positives.

If only the summary/gate rows need to be rebuilt after a completed run, use `--summarize-existing`; it reads the existing results CSV and does not call providers.

## Safety Boundary

Phase 54 outputs store derived ids, labels, counts, short titles/headings, title hashes, answer lengths, status labels, and judge metrics only. They must not store full chunk content, raw answers, provider raw responses, hidden reasoning, credentials, service logs, or restricted full text.

## Reranker-Enabled 54C Comparison

The private BGE-LoRA comparison run is now complete. The first naive BGE attempt was not accepted as the C result because it reranked the hybrid baseline before graph fusion and then let graph fusion sort by the old hybrid score plus graph boost. That design lifted the ordinary hybrid baseline but did not give graph-expanded evidence a fair final rerank step.

The accepted graph-aware design follows the common RAG/agent pattern:

```text
hybrid / keyword / vector recall
  -> graph relation expansion and evidence hints
  -> fused candidate pool
  -> final BGE-LoRA rerank
  -> answer generation and GLM-5.2 judge
```

Code-level changes:

```text
app/services/graphrag/graph_search.py
  final post-fusion rerank
  relation_focus filtering
  graph relation evidence hints
  graph candidate quota for final rerank

scripts/evaluate_phase54_graphrag_e2e.py
  reranker-enabled graph evaluation uses BGE as the final fused-evidence reranker
```

Formal graph-aware BGE artifacts:

```text
data/evaluation/phase54_graphrag_eval_results_reranker_bge_graphaware.csv
data/evaluation/phase54_graphrag_eval_summary_reranker_bge_graphaware.csv
data/evaluation/phase54_graphrag_eval_ablation_reranker_bge_graphaware.csv
data/evaluation/phase54_graphrag_eval_comparison_reranker_bge_graphaware.csv
```

Formal graph-aware BGE result:

```text
total_cases=47
completed_rows=47
error_rows=0
formal_judge_scored_rows=47
graph_intent_accuracy_delta=0.4412
graph_intent_completeness_delta=0.5000
graph_intent_citation_quality_delta=0.2941
ordinary_accuracy_delta=0.2500
negative_graph_false_positive_count=0
formal_judge_gate_decision=pass
```

Compared with reranker-disabled formal GLM-5.2 judge:

```text
graph_intent_accuracy_delta: +0.2941
graph_intent_completeness_delta: +0.0588
graph_intent_citation_quality_delta: +0.0294
ordinary_accuracy_delta: +0.2500
negative_graph_false_positive_count: no change, still 0
same_top_chunk_count: 43 -> 35
```

Risk note: ordinary baseline questions still produced broad graph candidate sets, although negative off-topic graph candidates remained zero. Future tuning should focus on graph trigger precision for in-domain-but-ordinary questions before making graph-aware BGE the default production path.

## Remaining Closeout

- Stop for user human verification. No `git add`, commit, tag, push, or PR has been performed.

Regression baseline:

```text
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest -q -> 1249 passed, 1 skipped
```

## Phase 54D Standards-Expanded Result

After the user added the standards batch under local `standards_0625`, Phase 54D ingested the standards, preserved table/image extraction boundaries, ran full LLM semantic supplementation for the new standard text/table chunks, rebuilt the graph, and reran the same 47-case evaluation set with GPU-hosted private BGE-LoRA final reranking.

LLM supplementation and graph rebuild:

```text
standards text LLM rows=1193 ok=1193
standards table LLM rows=260 ok=260
merged standards LLM rows=1453 ok=1453
domain graph node_count=14372 edge_count=114544
largest_connected_component_ratio=0.7935
isolated_node_ratio=0.1586
```

D artifacts:

```text
data/evaluation/phase54_graphrag_eval_results_d_full_standards_llm_bge.csv
data/evaluation/phase54_graphrag_eval_summary_d_full_standards_llm_bge.csv
data/evaluation/phase54_graphrag_eval_ablation_d_full_standards_llm_bge.csv
data/evaluation/phase54_graphrag_eval_comparison_d_full_standards_llm_bge.csv
```

D formal judge result:

```text
completed_rows=47
error_rows=0
formal_judge_scored_rows=47
graph_intent_accuracy_delta=0.5294
graph_intent_completeness_delta=0.4412
graph_intent_citation_quality_delta=0.5882
ordinary_accuracy_delta=-0.2500
negative_graph_false_positive_count=0
formal_judge_gate_decision=review_required
```

The D run confirms that standards expansion plus full LLM supplementation gives a large graph-intent and citation-quality lift. The remaining blocker is ordinary in-domain query routing: `ordinary_accuracy_delta=-0.2500`, so graph expansion should stay gated/tuned before becoming the default production chain.

Final closeout validation:

```text
python scripts/score_stage30_quality.py -> overall=91.52 grade=A release_decision=pass
python -m pytest -q -> 1267 passed, 1 skipped
python scripts/audit_phase54_completion.py --output data/evaluation/phase54_completion_audit.csv -> complete=16 partial=0 missing=0
git diff --check -> no whitespace errors; CRLF warnings only
```
