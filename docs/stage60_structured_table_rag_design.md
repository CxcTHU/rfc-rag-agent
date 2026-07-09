# Phase 60 Structured TableRAG Design

Phase 60 upgrades table ingestion from Markdown-only table chunks to a sidecar structured TableRAG substrate. It does not switch the default Agent/Search path.

## Design Principles

- Keep `chunks.chunk_type="table"` as compatibility evidence, citation fallback, and Markdown display fallback.
- Store table structure in dedicated objects: table, column, row, cell, retrieval unit, extraction run.
- Do not put table retrieval units back into ordinary `chunks`.
- Do not make Text-to-SQL the first retrieval entry point. If added later, it must run only after candidate `table_id` recall and must be read-only over `document_table_*`.

## Data Model

New tables:

```text
table_extraction_runs
document_tables
document_table_columns
document_table_rows
document_table_cells
table_retrieval_units
table_retrieval_unit_embeddings
```

`document_tables` keeps document id, source table chunk id, page, bbox, caption/header text, raw and normalized rows, headers, units, quality score, structure hash, semantic metadata, and processing metadata.

`document_table_cells` stores row/column position, text, normalized text, optional numeric value, optional unit, header flag, and optional bbox metadata.

`table_retrieval_units` stores independently retrievable table text units:

```text
table_summary
table_schema
row_pack
column_pack
cell_fact
caption_context
```

## Ingestion Flow

```text
existing PDFs / existing table chunks
-> PyMuPDF find_tables rows/page/bbox/header_text
-> StructuredTableDraft
-> document_tables / columns / rows / cells
-> table_retrieval_units
-> optional table_retrieval_unit_embeddings
```

Markdown table chunks are parsed only as fallback when source PDF extraction is unavailable.

## Sidecar Retrieval Flow

```text
user query
-> TableQueryPlanner
-> table_summary / schema / row / column / cell unit scoring
-> exact header/cell match
-> numeric/unit filter
-> weighted fusion
-> hydrate document_tables / rows / cells
-> structured result with citation
```

The returned object contains `table_id`, `summary`, `caption`, `headers`, `rows`, `matched_units`, and `citation`.

The quality loop hardened sidecar retrieval:

```text
query -> TableQueryPlanner
-> SQL prefilter over retrieval units without broad control terms
-> exact header/cell and numeric/unit side channels
-> per-table per-route max fusion
-> exact phrase/caption boost
-> hydrate structured result
```

Per-route max fusion prevents large numeric tables from winning only because they contain many loosely matching cells.

## Safety Boundary

Phase 60 artifacts store derived structure and bounded metadata. Evaluation output stores only ids, counts, scores, matched unit types, pages, and table dimensions. It must not store full chunks, full answers, provider raw responses, hidden reasoning, secrets, restricted full text, private logs, or long-term user profiles.
