# Phase 127: Expiring Contracts — USASpending Data Integration

**Status:** PLANNED
**Priority:** Medium — significantly increases expiring contract visibility with data already loaded
**Dependencies:** None — `usaspending_award` table and data already exist

---

## Problem

The Expiring Contracts page (`/awards/expiring`) currently shows very few results (e.g., 5 contracts) because `ExpiringContractService` only queries the `fpds_contract` table. The project never performed a bulk historical load of FPDS data — only incremental daily loads via `daily_load.bat` (`load awards`). However, a bulk historical load of USASpending data **was** performed, meaning `usaspending_award` contains far more contract data with expiration dates.

## Current State

- **`ExpiringContractService.cs`** queries only `FpdsContracts` (the `fpds_contract` table)
- **`v_expiring_contracts`** SQL view also queries only `fpds_contract`
- **`fpds_contract`**: Small dataset — only recent daily loads, no bulk historical import
- **`usaspending_award`**: Large dataset — bulk historical load completed, has `end_date` field equivalent to `ultimate_completion_date`

---

## Field Mapping

| ExpiringContractDto field | fpds_contract column | usaspending_award column |
|--------------------------|---------------------|------------------------|
| Piid | contract_id | piid |
| Description | description | description |
| AgencyName | agency_name | awarding_agency_name |
| NaicsCode | naics_code | naics_code |
| SetAsideType | set_aside_type | type_of_set_aside |
| VendorName | vendor_name | recipient_name |
| ContractValue | base_and_all_options | base_and_all_options_value |
| DollarsObligated | dollars_obligated | total_obligation |
| CompletionDate | ultimate_completion_date | end_date |
| DateSigned | date_signed | start_date |
| MonthsRemaining | (calculated) | (calculated) |
| MonthlyBurnRate | (calculated) | (calculated) |
| PercentSpent | (calculated) | (calculated) |

### Fields only available from fpds_contract (will be null for USASpending-sourced rows)
- `SolicitationNumber` (usaspending has `solicitation_identifier` — can map this)
- `VendorUei` -> usaspending has `recipient_uei`
- `ModificationNumber` filtering -> usaspending has no direct equivalent; use `award_type` filter instead (contracts only: A, B, C, D)

---

## Implementation Plan

### Task 1: Update SQL View `v_expiring_contracts`
- Add a UNION query to include `usaspending_award` rows
- Map USASpending columns to match the existing view schema
- Filter USASpending by `award_type IN ('A','B','C','D')` (contracts only, not grants/loans)
- Filter by `end_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 18 MONTH)`
- Deduplicate: when the same contract appears in both tables (match on `piid` / `contract_id`), prefer the FPDS row (more detailed)
- Add a `source` column (`'FPDS'` or `'USASPENDING'`) so the UI can indicate data provenance

### Task 2: Update `ExpiringContractService.cs`
- **Option A (preferred):** Query the updated `v_expiring_contracts` view instead of the `FpdsContracts` DbSet directly. This centralizes the UNION logic in SQL.
- **Option B:** Add a second EF Core query against `UsaSpendingAwards` and merge in C#. More flexible but duplicates filter logic.
- Deduplication: If the same PIID appears in both sources, keep the FPDS version (richer data).
- Incumbent health lookups (Entity join, SamExclusion join) should work for both sources since both have UEI fields (`vendor_uei` / `recipient_uei`).

### Task 3: Update `ExpiringContractDto`
- Add `Source` field (string: `"FPDS"` or `"USASpending"`) so the UI can display provenance
- No other DTO changes needed — all existing fields can be populated from either source

### Task 4: Update UI (ExpiringContractsPage)
- Add a small chip or indicator showing data source ("FPDS" / "USASpending")
- Optional: Add a source filter dropdown alongside the existing NAICS and set-aside filters
- Result count should increase significantly

### Task 5: Re-solicitation Detection
- Current logic matches `fpds_contract.solicitation_number` to `opportunity.solicitation_number`
- For USASpending rows, use `usaspending_award.solicitation_identifier` instead
- Same join logic, different source column

---

## Deduplication Strategy

Contracts may appear in both `fpds_contract` and `usaspending_award`. Deduplicate by:
1. Match on PIID (`fpds_contract.contract_id` = `usaspending_award.piid`)
2. When matched, prefer the FPDS row (has more granular fields like `modification_number`, `solicitation_number`, `extent_competed`)
3. In SQL view: use a LEFT JOIN + WHERE fpds IS NULL pattern, or UNION with ROW_NUMBER() partitioned by PIID

---

## Out of Scope
- Bulk loading historical FPDS data (separate effort, would also fix this but is more work)
- Modifying the daily load process
- Changes to other award-related features (AwardService, burn rate analysis already uses USASpending)

## Estimated Effort
- Small-medium: ~2-3 hours of implementation + testing
