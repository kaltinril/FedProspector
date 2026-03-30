# Phase 132: Federal Identifier Dash Normalization

**Status:** PLANNED
**Depends on:** Phase 128 (Federal Identifier Extraction)

## Problem

Federal identifiers (solicitation numbers, PIIDs) are stored inconsistently across tables — some with dashes, some without. The government APIs send different formats for the same identifier:
- SAM.gov opportunity: `FA4484-20-S-C002` (with dashes)
- FPDS contract: `FA448420SC002` (without dashes)
- PIIDs and IDV PIIDs: consistently dashless in DB
- Solicitation numbers: mixed — 10,652 with dashes and 120,826 without in fpds_contract; 4,005 with and 42,273 without in opportunity

This causes cross-reference misses and complicates comparisons.

## Solution

Standardize all federal identifiers to dashless format throughout the system.

## Tasks

- [ ] Task 1: Backfill — strip dashes from existing `solicitation_number` in `opportunity` and `fpds_contract`
- [ ] Task 2: ETL ingest normalization — strip dashes from solicitation numbers during `opportunity_loader` and `awards_loader` upsert, before writing to DB
- [ ] Task 3: User search normalization — strip dashes from user-pasted identifiers before searching
- [ ] Task 4: API response normalization — ensure API responses return dashless identifiers (or both raw + normalized)
- [ ] Task 5: Verify cross-references — after normalization, confirm Phase 128 cross-ref hit rate improves
- [ ] Task 6: Audit other identifier columns for similar issues
- [ ] Task 7: Display formatting — re-insert dashes for display when the correct dashed format is known (e.g., PIID structure: `{AAC}-{FY}-{Type}-{Serial}`). Store dashless, display dashed. Could be a simple UI formatter or CSS class.

## Data Audit (from Phase 128 investigation)

| Column | With dashes | Without dashes |
|--------|------------|----------------|
| fpds_contract.contract_id | 0 | 224,679 |
| fpds_contract.idv_piid | 0 | 129,009 |
| fpds_contract.solicitation_number | 10,652 | 120,826 |
| opportunity.solicitation_number | 4,005 | 42,273 |
| sam_subaward.prime_piid | 0 | 9,550 |
| usaspending_award.piid | 0 | 28,713,058 |

## Notes

- PIIDs are already clean (dashless everywhere) — no action needed
- Solicitation numbers are the primary problem
- Phase 128 currently uses dual search (dashless + raw) for cross-referencing as a workaround
- Once this phase completes, Phase 128 cross-ref can simplify to dashless-only exact match
