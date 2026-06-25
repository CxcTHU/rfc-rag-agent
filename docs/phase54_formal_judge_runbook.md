# Phase 54 Formal Judge Runbook

This runbook is for the final Phase 54D real API evaluation after local `JUDGE_MODEL_*` values are configured in `.env`. It does not store credentials and does not require writing any API key to Git, CSV, docs, tests, or Obsidian.

## Purpose

Phase 54D acceptance requires judged `status=completed` rows from:

```text
scripts/evaluate_phase54_graphrag_e2e.py --execute
```

Dry-run, retrieval-only, and answer-only rows are operational evidence only. They do not prove answer-quality lift.

## Preconditions

Expected local runtime state:

```text
data/knowledge_graph/domain_graph.json exists
data/evaluation/phase54_graphrag_eval_cases.csv has 47 cases
CHAT_MODEL_* is configured for answer generation
EMBEDDING_* is configured for retrieval
JUDGE_MODEL_* is configured for GLM-5.2 judge scoring
```

Required local `.env` keys for the formal judge are:

```text
JUDGE_MODEL_PROVIDER=openai-compatible
JUDGE_MODEL_NAME=GLM-5.2
JUDGE_MODEL_API_KEY=<local secret, do not commit>
JUDGE_MODEL_BASE_URL=https://llmapi.paratera.com
```

Run preflight first:

```powershell
python scripts\evaluate_phase54_graphrag_e2e.py --preflight --require-judge `
  --summary-output data\evaluation\phase54_graphrag_eval_preflight.csv
```

Do not start the formal run until `formal_judge_ready=pass`. The preflight reports each required judge field as a boolean and lists missing field names in `judge_model_missing_fields`; it never prints API key values.

## Recommended First Smoke

Use reranker disabled first to avoid depending on the private GPU tunnel:

```powershell
$env:RERANKING_ENABLED='false'
python scripts\evaluate_phase54_graphrag_e2e.py --execute --resume --progress --limit 3 `
  --results-output data\evaluation\phase54_graphrag_eval_results_real_api.csv `
  --summary-output data\evaluation\phase54_graphrag_eval_summary_real_api.csv `
  --ablation-output data\evaluation\phase54_graphrag_eval_ablation_real_api.csv
```

Inspect the summary CSV:

```powershell
Get-Content data\evaluation\phase54_graphrag_eval_summary_real_api.csv
```

The expected smoke state is `completed_rows=3`, `error_rows=0`, and `formal_judge_gate_decision=pending`. A smoke run is not acceptance evidence.

## Full Formal Run

After the smoke succeeds:

```powershell
$env:RERANKING_ENABLED='false'
python scripts\evaluate_phase54_graphrag_e2e.py --execute --resume --progress `
  --results-output data\evaluation\phase54_graphrag_eval_results_real_api.csv `
  --summary-output data\evaluation\phase54_graphrag_eval_summary_real_api.csv `
  --ablation-output data\evaluation\phase54_graphrag_eval_ablation_real_api.csv
```

The runner writes progress after every case, so it is safe to rerun with `--resume` after an interruption.

## Rebuild Summary Without API Calls

If the formal run has already produced a results CSV and you only need to refresh summary/gate rows:

```powershell
python scripts\evaluate_phase54_graphrag_e2e.py --summarize-existing `
  --results-output data\evaluation\phase54_graphrag_eval_results_real_api.csv `
  --summary-output data\evaluation\phase54_graphrag_eval_summary_real_api.csv `
  --ablation-output data\evaluation\phase54_graphrag_eval_ablation_real_api.csv
```

This mode does not call the database, embedding provider, answer provider, or judge provider. It reads existing rows and recomputes summary metrics only.

## Gate Interpretation

Formal acceptance evidence is in `phase54_graphrag_eval_summary_real_api.csv`.

Key rows:

```text
completed_rows
error_rows
formal_judge_scored_rows
graph_intent_accuracy_delta
graph_intent_completeness_delta
graph_intent_citation_quality_delta
ordinary_accuracy_delta
negative_graph_false_positive_count
formal_judge_gate_decision
formal_judge_gate_reason
```

Gate meanings:

```text
pending          not every row is status=completed, or at least one completed row lacks all judge scores
pass             all Phase 54D gates passed
review_required  at least one formal gate failed
```

Phase 54D gate expectations:

```text
graph_intent_completeness_delta >= 0.3
graph_intent_accuracy_delta >= 0.0
ordinary_accuracy_delta >= -0.1
negative_graph_false_positive_count == 0
error_rows == 0
formal_judge_scored_rows == completed_rows == total_cases
```

## If The Gate Fails

Use the failure reason to choose the next action:

```text
graph_intent_completeness_delta low
-> inspect graph fusion weighting and case coverage before extracting more LLM triples

graph_intent_accuracy_delta low
-> inspect graph false positives, noisy anchors, and graph_boost

ordinary_accuracy_delta low
-> reduce graph influence for ordinary queries or tighten graph-intent routing

negative_graph_false_positive_count > 0
-> inspect matched node labels and add conservative query matching filters

provider errors or timeouts
-> rerun with --resume after checking provider availability
```

## Optional Reranker Run

If the private BGE-LoRA reranker is required for the formal record, start the GPU instance through the Paratera web UI, establish the private tunnel, verify reranker health, and then rerun the formal command without forcing `RERANKING_ENABLED=false`.

After the run, switch the GPU instance to saving mode through the Paratera web UI. Do not use CLI shutdown commands for billing control.

## Safety Boundary

Result CSVs may contain ids, hashes, counts, answer lengths, scores, and short judge reasons only. They must not contain:

```text
API keys
Bearer tokens
Authorization headers
provider raw responses
raw answer text
hidden reasoning
full chunk content
restricted full text
service logs
```
