# Phase 35 Remediation Findings

- Test set leakage was confirmed and removed. The unsafe rule was `rcc dam construction -> alpe gera dam / road paving / vibratory rollers / compaction`; several expansion terms matched `stage29_wiki_dam_applications.expected_answer_points` literally.
- The remaining RCC rule is domain-generic abbreviation/synonym handling: `rcc / roller-compacted concrete / rolled concrete -> roller-compacted concrete / rolled concrete / rollcrete`.
- Final retrieval work avoids adding query-specific answer terms to `SYNONYM_RULES`.
- Mechanism-level retrieval fixes retained:
  - `source_type_rank` recognizes `web_page`, `wikipedia`, and `standard_document` before `metadata_record`.
  - deterministic reranking filters common English stopwords.
  - `HybridRrfTailSearchService` preserves hybrid top-3 ranking and uses BM25+vector RRF only for tail recall slots.
- Clean Stage 29 result: `retrieval_mode=hybrid_rrf_tail`, `p@1=0.867`, `p@3=0.933`, `p@5=1.000`, `coverage=0.731`, `refusal_accuracy=1.000`.
- Clean Stage 30 result: `overall=90.48`, `grade=A`, `release_decision=pass`, `deductions rows=0`.
- Scoring weights, grade boundaries, release-decision rules, provider topology, and external data sources were not changed.
- Real Judge remains a human-review risk: `answer_coverage=0.605`, `citation_support=0.455`, `high=0`, `judge_quality_gate=review_required`.
- Interview note: Reciprocal Rank Fusion means rank-based fusion across sparse and dense retrieval channels. In this project it appears in `RRFHybridSearchService`; Phase 35 uses it only as a tail recall supplement so it does not overwrite the stronger hybrid head ranking.
