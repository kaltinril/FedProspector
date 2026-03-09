# Phase 77: USASpending Delta Loader

**Status**: COMPLETE
**Priority**: High
**Depends on**: Phase 65 (bulk loader improvements), Phase 44 (original bulk loader)

## Problem

Keeping `usaspending_award` current requires re-downloading and re-processing entire fiscal year Full archive files (~35-40M rows across all FYs). USASpending regenerates ALL archive files monthly — even closed FY files — because agencies post late modifications, corrections, de-obligations, and closeouts. Re-loading everything is expensive in time and bandwidth.

USASpending provides a Delta file (`FY(All)_All_Contracts_Delta_<date>.zip`) containing only records changed since the last monthly archive refresh. This file has the same 299-column format as Full files, plus one extra column (`correction_delete_ind`) to flag deletions. The delta file contains ~2M rows/month vs 35-40M in all Full files combined.

## Background

### Bulk CSV files are transaction-level, not award-level

The FY Full files contain transaction-level data — one row per contract modification. The existing `usaspending_bulk_loader.py` handles this by deduplicating with `ROW_NUMBER() OVER (PARTITION BY generated_unique_award_id ORDER BY last_modified_date DESC)` to keep only the latest row per award. It maps ~25 of the 299 columns via `CSV_COLUMN_MAP` and discards the rest.

### Delta file structure

- File: `FY(All)_All_Contracts_Delta_<date>.zip`
- Contains 2 CSVs, ~2M total rows (Feb 2026: 1M + 985K)
- Same 299-column format as Full files, plus `correction_delete_ind` (column 0)
- `correction_delete_ind` values per USASpending docs:
  - blank = **Added** (new record)
  - `"C"` = **Corrected** (modified record — treat as upsert)
  - `"D"` = **Deleted** (remove from local copy — agency corrections, duplicates, errors)
- Note: No "C" rows appeared in the Feb 2026 file — corrections appear with blank status
- D rows: 435 in ~2M rows (0.04%), covering 290 unique PIIDs
- D rows have ALL metadata blanked out — not just `contract_award_unique_key`, but also `award_or_idv_flag`, `award_type`, `idv_type`, and all dollar columns. Only populated fields: transaction key, PIID, modification_number, agency_id, and parent fields
- D rows DO have `award_id_piid` and `agency_id` populated — sufficient for matching in `usaspending_award`
- Multiple D-rows per PIID are common (one per modification being deleted): e.g., W911QY23C0039 (30 mods), FA862224FB003 (23 mods), 1331L522F13230035 (15 mods)
- **Practical impact**: D rows are actionable — soft-delete by matching `award_id_piid` via the existing `idx_usa_piid` index, sidestepping composite key reconstruction
- Spans ALL fiscal years in one file (FY1979 through FY2026)
- Heavy on recent years: FY2026 ~590K rows, FY2025 ~485K rows

### Key Research Findings

**Transaction key format** (100% consistent across all 985,358 data rows):
```
{agency_id}_{parent_agency}_{piid}_{modification}_{parent_piid}_{sequence}
```
- PIID is ALWAYS at segment position [2]
- `-NONE-` used as placeholder for absent parent/agency fields

**Award key format** (two patterns):

| Prefix | Segments | Count | Pattern |
|--------|----------|-------|---------|
| `CONT_AWD` | 6 | 934,022 | `CONT_AWD_{piid}_{agency}_{parent_agency}_{parent_piid}` |
| `CONT_IDV` | 4 | 50,901 | `CONT_IDV_{piid}_{agency}` |
| *(blank)* | — | 435 | All D-rows |

`CONT_IDV` rows always have `-NONE-` for both parent fields in the transaction key (all 50,901).

**D-row parent info analysis** (435 rows):
- 279 of 435 have a real parent PIID in the transaction key → definitely `CONT_AWD`
- 156 of 435 have `-NONE-` parents → ambiguous (could be `CONT_AWD` or `CONT_IDV`)

**PIID position 9 instrument code is NOT reliable for AWD-vs-IDV classification:**
- Tested against all 974,987 non-blank award_key rows: only 99.2% accurate
- Many instrument codes (especially numeric 0-9, and A, B, G, S, T) appear under both `CONT_AWD` and `CONT_IDV`

**Recommended delete strategy — soft-delete via `deleted_at` column:**
Add a `deleted_at DATETIME NULL` column to `usaspending_award`. D-rows trigger a soft-delete UPDATE instead of a hard DELETE:
```sql
UPDATE usaspending_award SET deleted_at = NOW() WHERE award_id_piid = ?
```
`idx_usa_piid` already exists on `award_id_piid`, so this UPDATE is indexed. No need to match on `agency_id` — PIID matching via the existing index is sufficient.

Benefits of soft-delete over hard DELETE:
- **Reversible** — set `deleted_at = NULL` to restore a record
- **Cheap** — UPDATE in-place, no row movement in InnoDB (avoids page splits and fragmentation on a 29 GB table)
- **Auditable** — `deleted_at` timestamp shows when the deletion was applied
- **No cascading risk** — row stays in place, foreign key references remain valid

All queries filtering active records add `WHERE deleted_at IS NULL`. This is a small follow-up for existing queries in the UI, prospect manager, and views — not part of this phase's core work, but noted here for tracking.

### Data semantics — cumulative vs incremental

The CSV files are transaction-level (one row per contract modification). Dollar columns have different semantics:

| Column | Semantics | In our column map? |
|--------|-----------|-------------------|
| `federal_action_obligation` | **Incremental** — just this modification's amount | No (not mapped) |
| `total_dollars_obligated` | **Cumulative** — running total through this mod | Yes → `total_obligation` |
| `current_total_value_of_award` | **Cumulative** — current ceiling including options | Yes → `base_and_all_options_value` |

Because we map only cumulative columns, keeping the latest modification per award (via `ROW_NUMBER() ... ORDER BY last_modified_date DESC`) is correct. No summation across modifications is needed.

Verified against real data: award `CONT_IDV_03310323D0072_0300` shows `federal_action_obligation` of $3000, -$3000, $0... while `total_dollars_obligated` stays at the running total.

### Delta vs Full file timing

The Full and Delta files for the same month are generated from the **same data snapshot**. The Feb 2026 files (`20260206`) share the same date — loading the Full files means the same-month Delta is redundant.

The Delta file contains changes since the **previous month's** archive generation. So:
- We loaded Feb 6 Full files → our DB is current as of Feb 6
- The Feb 6 Delta covers Jan→Feb changes → already included in the Feb Full files
- Our first useful Delta will be the **March** file (~Mar 15), covering Feb 6→Mar ~6 changes

### Current table sizes

| Table | Rows | Size |
|-------|------|------|
| `usaspending_award` | ~28M | 29 GB (11.5 GB data + 17.8 GB indexes) |
| `usaspending_transaction` | ~93 | On-demand API loads only |
| `fpds_contract` | ~12K | SAM.gov API loads only |

### Data loading philosophy

1. **Monthly bulk** (automated, free) — keep `usaspending_award` current via delta file
2. **On-demand per contract** (user-initiated, free) — load `usaspending_transaction` via USASpending API when user clicks "load" in UI
3. **On-demand per contract** (user-initiated, burns SAM token) — load `fpds_contract` via SAM.gov API (auto-chained from #2)

## Goals

1. **Delta loading** — add `--delta` flag to `load usaspending-bulk` to download and process the delta file instead of a Full file
2. **Delete handling** — process `correction_delete_ind = "D"` rows by matching on `award_id_piid` to soft-delete in `usaspending_award` (set `deleted_at = NOW()`)
3. **No fiscal year required** — delta file spans all FYs, so `--fy` should not be required when `--delta` is used
4. **Reuse existing pipeline** — leverage `_normalize_csv_row()`, `_upsert_from_temp()`, and checkpoint infrastructure

## Implementation Plan

### Task 1: USASpending client — delta file download

- [x] Add `download_delta_file()` method to `usaspending_client.py`
- [x] Current `download_archive_file()` constructs URLs for `_Full_` files with a fiscal year parameter
- [x] Delta URL format: `https://files.usaspending.gov/generated_downloads/FY(All)_All_Contracts_Delta_<date>.zip`
- [x] Discover available delta file via the archive API endpoint (same pattern as Full files)
- [x] Return path to downloaded ZIP

### Task 2: Bulk loader — delta mode support

- [x] Accept a `delta=True` parameter in `USASpendingBulkLoader`
- [x] When in delta mode, skip the fiscal year requirement
- [x] Add `correction_delete_ind` to the column map (or read it separately during CSV processing)
- [x] During `_normalize_csv_row()`, preserve `correction_delete_ind` value for downstream use
- [x] During CSV processing, separate D-rows from non-D rows:
  - Non-D rows (blank/C status) go through the normal upsert pipeline
  - D-rows are collected separately — extract unique `award_id_piid` values
- [x] D-rows must NOT go through the upsert pipeline (they have blank data columns and would corrupt records)
- [x] After the upsert pass completes, execute a batch soft-delete pass:
  ```sql
  UPDATE usaspending_award SET deleted_at = NOW() WHERE award_id_piid = %s
  ```
- [x] Dedup D-rows to unique PIIDs before soft-deleting (e.g., 435 D-rows → 290 unique PIIDs)
- [x] This soft-deletes the entire award for each PIID — intended behavior since agencies delete whole awards
- [x] Sidesteps AWD-vs-IDV ambiguity: no need to reconstruct `contract_award_unique_key`
- [x] Log soft-delete count separately from upsert count

### Task 3: Temp table handling for soft-deletes

- [x] The existing `_upsert_from_temp()` uses `INSERT ... ON DUPLICATE KEY UPDATE` to merge temp into main
- [x] For delta mode, D-rows are excluded from temp table entirely (they have blank data columns)
- [x] Only non-D rows (blank/C status) are written to the temp table and upserted
- [x] After upsert completes, soft-delete the deduped `award_id_piid` values collected from D-rows via `UPDATE ... SET deleted_at = NOW()`
- [x] This is effectively Option B (upsert first, then soft-delete) but cleaner since D-rows never enter the temp table

### Task 4: CLI changes

- [x] Add `--delta` flag to `bulk_spending.py` CLI command
- [x] When `--delta` is passed, `--fy` becomes optional (not required)
- [x] When `--delta` is passed without `--fy`, load the delta file
- [x] Error if both `--delta` and `--fy` are provided (they are mutually exclusive)
- [x] Update `--help` text to explain delta vs full loading

### Task 5: Checkpoint integration

- [x] Reuse existing `usaspending_load_checkpoint` table
- [x] For delta loads, set `fiscal_year = 0` (or a sentinel value) since delta spans all FYs
- [x] Set `zip_file_name` to the delta file name (includes date for uniqueness)
- [x] Existing resume logic should work without modification — skip completed CSVs, resume partial batches

### Task 6: Logging and reporting

- [x] Log summary at end of delta load: rows upserted, rows deleted, total time
- [x] Log fiscal year distribution of processed rows (for operational visibility)
- [x] Log the delta file date so operator knows how current the data is

## Alternatives Considered (Not Implementing)

### A. Bulk load all transactions into usaspending_transaction
Would give burn rate data for all ~28M awards without on-demand loading. Estimated ~35-40M rows, ~15-20 GB storage. Rejected: massive storage cost for data most users will never look at. The on-demand flow already works and is free.

### B. Keep CSVs on disk, query on demand
Options explored: SQLite files per FY, CSV with lightweight index (award_key -> file:offset). Rejected: adds complexity for marginal benefit. On-demand API loading is simpler and already implemented.

### C. Remove FPDS auto-chain from on-demand loader
Currently `_process_usaspending()` in `demand_loader.py` auto-queues an `FPDS_AWARD` request. Could make FPDS a separate UI button so user controls when SAM.gov tokens are spent. Deferred: not in scope for this phase, but noted for future consideration.

## Files to Modify

| File | Changes |
|------|---------|
| `fed_prospector/api_clients/usaspending_client.py` | Add `download_delta_file()` method |
| `fed_prospector/etl/usaspending_bulk_loader.py` | Delta mode: handle `correction_delete_ind`, delete pass, no FY requirement |
| `fed_prospector/cli/bulk_spending.py` | Add `--delta` flag, make `--fy` optional when delta is used |
| `fed_prospector/db/schema/tables/70_usaspending.sql` | Add `deleted_at DATETIME NULL` column to `usaspending_award` |

## Testing

- [x] Unit test: `_normalize_csv_row()` correctly passes through `correction_delete_ind`
- [x] Unit test: D-rows are excluded from temp table and collected for batch soft-delete
- [x] Unit test: D-row dedup produces correct unique `award_id_piid` values
- [x] Integration test: load a small delta CSV with both upsert and soft-delete rows
- [x] Manual test: `python main.py load usaspending-bulk --delta` downloads and processes delta file
- [x] Manual test: verify row counts before/after delta load (upserts increased, soft-deletes marked)
- [x] Manual test: verify `--delta` and `--fy` together produces an error

## Estimated Effort

- Delta download method: ~30 minutes
- Bulk loader delta mode: ~2 hours (most complexity is in soft-delete handling and temp table logic)
- CLI changes: ~15 minutes
- Testing: ~1 hour
- **Total: ~4 hours**

## Operational Notes

- Delta file is regenerated monthly by USASpending, published by the 15th of each month
- Recommended schedule: run `--delta` monthly after the 15th when USASpending publishes new archives
- Delta loads should complete in minutes (2M rows) vs hours (35-40M rows for full reload)
- The `--fast` flag (index dropping) from Phase 65 is likely unnecessary for delta loads given the smaller row count, but remains compatible

## Follow-up: Soft-Delete Query Filter

After this phase lands, existing queries that read from `usaspending_award` will need `WHERE deleted_at IS NULL` added to exclude soft-deleted rows. Affected areas include UI search/list endpoints, prospect manager scoring queries, and any views or reports that aggregate award data. This is a small, mechanical follow-up — not part of this phase's core scope.
