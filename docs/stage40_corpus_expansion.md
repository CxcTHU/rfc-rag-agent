# Stage 40 Corpus Expansion

Date: 2026-06-16

## Scope

This stage expands the corpus without importing restricted standard full text.

Primary goals:

- Add Chinese hydraulic, hydropower, RFC, and related concrete standards as searchable metadata-only `standard_document` records.
- Re-run OpenAlex discovery for RFC English open-access papers with stricter `CC-BY / CC0` download filtering.
- Preserve legal access boundaries: public bibliographic and scope-level information is stored; purchased or institution-only standards are not downloaded or committed.

## Chinese Standards Added

Script:

```powershell
python scripts\seed_chinese_standards_metadata.py
```

Generated cards:

```text
data/imports/chinese_standards_metadata/
```

Manifest:

```text
data/corpus_expansion/chinese_standards_metadata.csv
```

Result summary:

```text
records=7
imported=7
document_id=1068..1074
standard_document documents: 9 -> 16
deterministic vector index: total=12745 indexed=29 updated=0 skipped=12716
```

Records:

| Standard | Imported role | Notes |
| --- | --- | --- |
| `NB/T 10077-2018`《堆石混凝土筑坝技术导则》 | RFC core standard | Metadata-only record; no restricted full text. |
| `DL/T 5806-2020`《水电水利工程堆石混凝土施工规范》 | RFC construction standard | Official public-standard catalog URL recorded. |
| `GB 50496-2018`《大体积混凝土施工标准》 | Related mass-concrete standard | Corrected from user-provided `GB/T 50496-2018`; public title uses `GB`. |
| `SL/T 352-2020`《水工混凝土试验规程》 | Hydraulic concrete testing | Corrected from user shorthand `SL 352-2020`. |
| `DL/T 5330-2015`《水工混凝土配合比设计规程》 | Hydraulic concrete mix design | Relevant to SCC and hydraulic concrete mix-design context. |
| `SL 314-2018`《碾压混凝土坝设计规范》 | Correction/comparison standard | Not an RFC technical guide; stored to prevent future retrieval confusion. |
| `DB52/T 1545-2020`《堆石混凝土拱坝技术规范》 | Historical/local RFC standard | Public catalog says it was abolished on 2026-03-30; retrieval should mention status. |

## OpenAlex OA Expansion

Queries:

```powershell
python scripts\expand_open_access_corpus.py `
  --query "rock-filled concrete durability" `
  --query "RFC dam seismic" `
  --query "self-compacting concrete large aggregate" `
  --limit 80 `
  --license-policy cc-by-or-cc0
```

Dry-run result:

```text
discovered=238 relevant=91
license_policy=cc-by-or-cc0 permissive_oa_with_pdf=10 not_yet_downloaded=10
```

Download/import result:

```text
downloaded_this_run=9
imported=0 duplicate=9 manifest_rows_added=0
```

The successfully downloaded papers were already present in the local corpus by content hash, so this pass did not increase `open_access_pdf` count. The remaining Hindawi PDF failed with HTTP 403:

```text
A Study on Adiabatic Temperature Rise Test and Temperature Stress Simulation of Rock-Fill Concrete
DOI: 10.1155/2018/3964926
license: cc-by
status: download_failed
reason: HTTP Error 403: Forbidden
```

## Pipeline Fixes

Two small collection fixes were added before the OA import:

- `app/services/source_collection.py`: RFC abbreviation matching now requires standalone English words such as `concrete`, `dam`, or `self-compacting`, avoiding false positives like medical `Random Forest Classifier (RFC)` papers.
- `scripts/expand_open_access_corpus.py`: added `--license-policy cc-by-or-cc0`, which excludes `CC-BY-NC`, `CC-BY-NC-ND`, and other non-redistribution-friendly variants from this expansion path while preserving the legacy Stage 18 behavior by default.

## Verification

Focused tests:

```text
python -m pytest tests\test_stage40_chinese_standards_metadata.py -q -> 5 passed
python -m pytest tests\test_expand_open_access_corpus.py tests\test_source_collection.py -q -> 15 passed
python -m pytest tests\test_expand_open_access_corpus.py tests\test_source_collection.py tests\test_stage40_chinese_standards_metadata.py -q -> 20 passed
```

Corpus checks:

```text
documents id>=1068 -> 7 Chinese standard_document records
sources source_id like std_cn_% -> 7 imported records with document_id bindings
document source_type counts include:
  institutional_access_pdf=325
  metadata_record=115
  open_access_pdf=15
  standard_document=16
  web_page=136
  wikipedia=25
```

## Next Expansion Candidates

- Broaden OpenAlex queries beyond the 10 already-covered CC-BY/CC0 PDFs, for example with durability, freeze-thaw, dam thermal control, SCC flow through coarse aggregate, and construction temperature field combinations.
- Add metadata-only Chinese encyclopedia and standards cards for `自密实混凝土`, `碾压混凝土坝`, `大体积混凝土`, and `水工混凝土`, then prune unrelated Wikipedia records.
- Add engineering case reports from official water-resource ministry/provincial public pages after reviewing each page's access and reuse terms.
- If the user provides purchased or institutional standard PDFs, save them locally as `institutional_access` and keep them out of Git.
