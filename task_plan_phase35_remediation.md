# Phase 35 Remediation Task Plan

## Phase A: Remove Leakage

Status: completed.

- Deleted the unsafe `rcc dam construction` synonym rule.
- Confirmed the remaining RCC synonym rule is domain-generic.

## Phase B: Score Density

Status: completed.

- Added score-density analysis.
- Verified the clean final score is not based on leaked gains.

## Phase C: Retrieval Strategy

Status: completed.

- Compared existing hybrid with BM25+vector RRF.
- Kept hybrid as the head ranker.
- Added `HybridRrfTailSearchService` to use RRF only as tail-slot recall supplementation.

## Phase D: Honest Validation

Status: completed with residual Judge risk.

- Stage 29 and Stage 30 pass under clean retrieval artifacts.
- Real Judge does not meet the requested citation/coverage dual gate and remains `review_required`.

## Phase E: Human Verification Stop

Status: current.

- Stop before staging, commit, tag, push, or PR.
