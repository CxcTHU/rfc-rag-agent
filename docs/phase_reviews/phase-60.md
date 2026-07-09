# Phase 60 Review: Structured TableRAG Ingestion Sidecar

## Scope

Phase 60 adds a structured TableRAG sidecar without switching the default Agent/Search behavior.

Implemented:

```text
alembic/versions/20260709_0009_structured_table_rag.py
app/db/models.py -> table_extraction_runs, document_tables, columns, rows, cells, retrieval units, retrieval unit embeddings
app/services/ingestion/table_extractor.py -> TableChunk.rows preserved
app/services/table_rag/
scripts/backfill_phase60_structured_tables.py
scripts/generate_phase60_table_retrieval_units.py
scripts/evaluate_phase60_table_rag.py
scripts/evaluate_phase60_table_rag_quality.py
tests/test_phase60_structured_table_rag.py
docs/stage60_structured_table_rag_goal_prompt.md
docs/stage60_structured_table_rag_design.md
```

## Behavior

- Existing `chunks.chunk_type="table"` remains untouched and continues to serve compatibility, citation, and Markdown fallback roles.
- `search_tables`, `hybrid_search`, and `tool_calling_agent` are not switched to the new sidecar.
- Structured ingestion can rebuild table objects from PyMuPDF rows or fallback Markdown chunks.
- Retrieval units are separate objects, not ordinary chunks.
- `StructuredTableSearchService` returns hydrated headers, data rows, matched units, and citation metadata.

## Validation

Real local PostgreSQL ingestion on 2026-07-09:

```text
target: local PostgreSQL rfc_rag_dev, credential redacted
backup: data/exports/phase60_before_table_rag.backup, 513167733 bytes
alembic current -> 20260709_0009
small dry-run -> seen_docs=5 processed_docs=2 tables_seen=5 units=74 errors=0
small write -> tables_created=5 units=74 errors=0
full dry-run -> seen_docs=860 processed_docs=268 tables_seen=1700 units=61531 errors=0
full write -> tables_created=1695 tables_skipped=5 units=61531 errors=0
```

Final database counts:

```text
document_tables=1700
document_table_columns=10137
document_table_rows=10732
document_table_cells=72900
table_retrieval_units=61531
table_extraction_runs=865 completed, error_sum=0
mapped_table_chunks=1700
distinct_documents=268
```

Table recall quality evaluation:

```text
script: scripts/evaluate_phase60_table_rag_quality.py
output: data/evaluation/phase60_table_rag_quality_eval.csv
source_alignment: 1700/1700 exact matches against source table chunk Markdown
sampled_recall_cases=400
overall top1=0.8725
overall top5=0.9600
caption top1=0.8571 top5=0.9643
schema top1=0.8932 top5=0.9806
row top1=0.9143 top5=0.9714
cell top1=0.8125 top5=0.9125
```

Quality loop fixes:

```text
Initial recall quality was below target because retrieval-unit recall was capped below the real 61531-unit corpus, broad control terms such as table/表格 could dominate SQL prefiltering, and large numeric tables could accumulate too many same-route matches.
Final search filters broad control terms from retrieval-unit prefiltering, raises the candidate cap, caps table score contribution per route, boosts exact caption/phrase matches, and weakens numeric-only matching.
The eval generator filters non-discriminative fallback captions and placeholder headers for recall cases; source-alignment still covers all 1700 tables.
```

Current focused validation:

```text
python -m py_compile app\db\models.py app\services\ingestion\table_extractor.py app\services\table_rag\__init__.py app\services\table_rag\models.py app\services\table_rag\normalization.py app\services\table_rag\extraction.py app\services\table_rag\retrieval_units.py app\services\table_rag\repository.py app\services\table_rag\search.py scripts\backfill_phase60_structured_tables.py scripts\generate_phase60_table_retrieval_units.py scripts\evaluate_phase60_table_rag.py alembic\versions\20260709_0009_structured_table_rag.py tests\test_phase60_structured_table_rag.py -> passed
python -m pytest tests\test_phase60_structured_table_rag.py -q -> 4 passed
python -m pytest tests\test_phase60_structured_table_rag.py tests\test_db_models.py tests\test_repositories.py -q -> 14 passed
python -m pytest tests\test_agent_tools.py tests\test_hybrid_search.py -q -> 43 passed
python scripts\generate_phase60_table_retrieval_units.py --dry-run -> tables_seen=1700 units=61531
python scripts\generate_phase60_table_retrieval_units.py -> tables_updated=1700 units=61531
python scripts\evaluate_phase60_table_rag.py --out data\evaluation\phase60_table_rag_eval.csv -> cases=5 rows=5, negative result_count=0
python scripts\evaluate_phase60_table_rag_quality.py --sample-size 400 --out data\evaluation\phase60_table_rag_quality_eval.csv -> source_exact_rate=1.0000 top1=0.8725 top5=0.9600
git diff --check -> no whitespace errors; CRLF warnings only
targeted changed-file secret-shape scan -> no real key/token/header patterns found
```

Human verification:

```text
User manual verification passed on 2026-07-09. Phase 60 is authorized for local closeout, GitHub merge, and CPU-server sync.
```

The new worktree does not contain `data/app.sqlite`, so DB-backed dry-run/eval is intentionally left for the user's local corpus database or a sanitized database copy. A temporary SQLite `alembic upgrade head` attempt is not a valid Phase 60 migration gate because the existing historical `20260618_0002` migration uses `ALTER COLUMN`, which SQLite rejects before reaching Phase 60.

## Merge Risk

Low-to-medium. The phase touches shared `app/db/models.py` and `table_extractor.TableChunk`, but keeps default runtime/search code paths unchanged. The main merge risk is Alembic ordering if another backend thread also adds migrations after `20260629_0008`.

## Text-to-SQL Boundary

Text-to-SQL is not a first entry point. A future Text-to-SQL layer must:

- run only after candidate `table_id` recall,
- query only read-only `document_table_*` / `table_retrieval_*` tables,
- inject `table_id IN (...)`,
- forbid DDL/DML,
- enforce LIMIT and timeout.
