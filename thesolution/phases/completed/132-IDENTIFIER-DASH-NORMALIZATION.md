# Phase 132: Federal Identifier Dash Normalization

**Status:** COMPLETE
**Depends on:** Phase 128 (Federal Identifier Extraction)

## Problem

Federal identifiers (solicitation numbers, PIIDs) are stored inconsistently across tables — some with dashes, some without. The government APIs send different formats for the same identifier:
- SAM.gov opportunity: `FA4484-20-S-C002` (with dashes)
- FPDS contract: `FA448420SC002` (without dashes)
- PIIDs and IDV PIIDs: consistently dashless in DB
- Solicitation numbers: mixed — 10,652 with dashes and 120,826 without in fpds_contract; 4,005 with and 42,273 without in opportunity

This causes cross-reference misses and complicates comparisons.

## Solution

Standardize all federal identifiers for **matching/cross-reference** to a single dashless,
uppercased canonical form, while **preserving the original value for display**.

### Design decision (chosen 2026-05-31): normalized column, original preserved

Rather than stripping dashes in-place (destructive — permanently loses the original
government-supplied format, and re-inserting dashes for display is not deterministic
across federal identifier formats), we add a **separate normalized column** alongside the
original:

- `opportunity.solicitation_number_normalized`
- `fpds_contract.solicitation_number_normalized`

The original `solicitation_number` column is left untouched (display value). All matching,
search, and cross-referencing keys off the normalized column with **exact match**.

### Canonical normalization rule (must be identical in SQL, Python, and C#)

`trim → uppercase → remove dashes`, matching Phase 128's `_normalize_identifier`
(`fed_prospector/etl/attachment_identifier_extractor.py`):

- SQL: `UPPER(REPLACE(TRIM(solicitation_number), '-', ''))`
- Python: `value.strip().upper().replace("-", "")`
- C#: `value.Trim().ToUpperInvariant().Replace("-", "")`

## Tasks

- [x] Task 1: Schema + backfill — added `solicitation_number_normalized` (indexed) to `opportunity` and `fpds_contract` in the Python DDL (`tables/30_opportunity.sql`, `tables/40_federal.sql`); idempotent migration `migrations/133_solicitation_number_normalized.sql` populates it via the canonical rule. **Applied to both dev (`127.0.0.1`) and prod (`192.168.0.137`, 2026-06-01).** Prod backfill: `opportunity` 117,423/117,423 and `fpds_contract` 135,782/135,782 non-empty rows populated (0 missing).
- [x] Task 2: ETL ingest normalization — `opportunity_loader` and `awards_loader` populate `solicitation_number_normalized` on upsert (via `_normalize_solicitation`); original column unchanged; hash field lists untouched (no spurious "changed" rows).
- [x] Task 3: User search normalization — `OpportunityService`/`AwardService` normalize user input and match against the normalized column; partial-search UX preserved (dashed and dashless inputs both hit).
- [x] Task 4: API response — `SolicitationNumberNormalized` mapped on the EF `Opportunity` and `FpdsContract` entities; DTOs return both original (display) and normalized; shared `IdentifierNormalizer.Normalize` in Core.
- [x] Task 5: Cross-references — cross-ref paths switched to exact match on the normalized column; `attachment_identifier_extractor` dual-search simplified to dashless-only exact match against the normalized columns (raw branch confirmed safe to drop — see Task 6 audit).
- [x] Task 6: Audit other identifier columns — completed; results below. PIID-type columns are 100% dashless; the two `solicitation_number` columns were the only mixed-format identifiers.
- [x] Task 7: Display formatting — verified all 9 UI solicitation-number render sites show the preserved original `solicitation_number`; no normalized form is surfaced and no dash re-insertion formatter was built.

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
- **Hash impact**: the new normalized column is derived data, not a government source field. Do NOT add it to the SHA-256 change-detection hash inputs in the loaders, or every existing row will spuriously flip to "changed" on the next load.
- **Display**: original `solicitation_number` is preserved verbatim — the normalized column is for matching only and should never be shown to users.

## Task 6 Audit Results (2026-05-31)

Re-validated the Data Audit identifier columns against the current DEV DB
(`127.0.0.1`). Dash detection: `col LIKE '%-%'` vs non-empty dashless.

| Column | With dashes | Without dashes | Action |
|--------|------------:|---------------:|--------|
| fpds_contract.contract_id | 0 | 228,039 | None — already dashless |
| fpds_contract.idv_piid | 0 | 130,431 | None — already dashless |
| fpds_contract.solicitation_number | mixed | mixed | Normalized column added (this phase) |
| opportunity.solicitation_number | mixed | mixed | Normalized column added (this phase) |
| sam_subaward.prime_piid | 0 | 9,550 | None — already dashless |
| usaspending_award.piid | 0 | 28,854,644 | None — already dashless (full 28.85M-row scan) |

Solicitation backfill (this phase, DEV DB): every non-empty source value was
normalized — `opportunity` 82,992/82,992 populated (0 missing);
`fpds_contract` 134,025/134,025 populated (0 missing).

**Finding:** All PIID-type identifier columns (contract_id, idv_piid,
prime_piid, usaspending_award.piid) are 100% dashless across all rows, so no
additional normalized columns are warranted. The two `solicitation_number`
columns were the only mixed-format identifiers, and both are now handled by the
dedicated `solicitation_number_normalized` columns added in this phase.
